"""
Resource-placement optimizer: where should K mobile-tutoring units be
based to cover the most risk-weighted demand?

This is a Maximal Covering Location Problem (MCLP) -- the standard OR
formulation for "place K facilities to cover the most weighted demand
within a service radius," the same shape as siting ambulances, patrol
cars, or (in the ParkSight precedent) patrol beats.

WHY A SEPARATE, COARSER GRID FROM clustering.py:
The ~8km hotspot-detection grid is the right resolution for *finding*
concentrated risk. It's the wrong resolution for *basing a van* -- at
8km spacing, Karnataka has 2,650 cells, most of them not meaningfully
different from their neighbors as a home base. A mobile unit serves a
wider catchment than that, so candidate/demand units here use a
~28km grid (roughly taluk scale, 312 cells) instead. Same "match the
unit to the decision" logic as the clustering fix.

WHY SOLVE THIS WITH AN ILP INSTEAD OF JUST GREEDY:
Greedy (repeatedly add whichever candidate covers the most remaining
demand) is a fine heuristic and ships here as a baseline for
comparison. On the plain version of this problem it lands at or very
near the ILP's answer almost every time -- that's a known property of
greedy on coverage problems, not a bug in the comparison. Where it
visibly falls short is under an added real constraint: a max-units-
per-district cap, so a state doesn't dump every unit into the two or
three districts with the most schools. Greedy has no clean way to look
ahead around a cap like that; the ILP handles it as one more
constraint. Both numbers are shown in the UI so the gap (however small
or large it turns out to be for the K and radius you pick) is visible
on your own data instead of asserted.
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import pulp

GRID_DEG = 0.25          # ~28km -- taluk-scale, the right unit for "where's the van based"
MIN_SCHOOLS_PER_SITE = 10  # candidate/demand cells need at least this many schools to count
EARTH_KM = 6371.0


def _haversine_km(lat1, lon1, lat2, lon2):
    """Vectorized haversine distance in km between two arrays of points."""
    lat1, lon1, lat2, lon2 = map(np.radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    return 2 * EARTH_KM * np.arcsin(np.sqrt(a))


def build_sites(schools_df: pd.DataFrame, min_schools: int = MIN_SCHOOLS_PER_SITE) -> pd.DataFrame:
    """Aggregate schools onto the coarse siting grid. Demand weight = summed risk score in the cell."""
    df = schools_df.copy()
    df["site_row"] = (df["latitude"] // GRID_DEG).astype(int)
    df["site_col"] = (df["longitude"] // GRID_DEG).astype(int)
    df["site_id"] = df["site_row"].astype(str) + "_" + df["site_col"].astype(str)

    sites = (
        df.groupby("site_id")
        .agg(
            school_count=("schcd", "count"),
            demand=("demo_risk_score", "sum"),
            high_risk_count=("risk_tier", lambda s: (s == "High").sum()),
            lat=("latitude", "mean"),
            lon=("longitude", "mean"),
            district=("dtname", lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0]),
        )
        .reset_index()
    )
    return sites[sites["school_count"] >= min_schools].reset_index(drop=True)


@dataclass
class OptimizeResult:
    sites: pd.DataFrame            # all candidate/demand sites, with 'chosen' and 'covered' flags
    chosen_ids: list = field(default_factory=list)
    ilp_coverage: float = 0.0
    greedy_coverage: float = 0.0
    total_demand: float = 0.0
    status: str = "Optimal"
    solve_seconds: float = 0.0


def _coverage_matrix(sites: pd.DataFrame, radius_km: float) -> np.ndarray:
    lat = sites["lat"].to_numpy()
    lon = sites["lon"].to_numpy()
    n = len(sites)
    covers = np.zeros((n, n), dtype=bool)  # covers[i, j] = site j is within radius of demand i
    for i in range(n):
        d = _haversine_km(lat[i], lon[i], lat, lon)
        covers[i] = d <= radius_km
    return covers


def greedy_coverage(sites: pd.DataFrame, covers: np.ndarray, k: int, max_per_district: int | None = None) -> tuple[list, float]:
    """Standard greedy max-coverage baseline: repeatedly add the site that covers the most
    currently-uncovered weighted demand. Respects the same per-district cap as the ILP, if set --
    a candidate that would breach its district's quota is skipped that round."""
    demand = sites["demand"].to_numpy()
    districts = sites["district"].to_numpy()
    n = len(sites)
    covered = np.zeros(n, dtype=bool)
    chosen: list[int] = []
    district_counts: dict[str, int] = {}
    for _ in range(min(k, n)):
        best_j, best_gain = -1, -1.0
        for j in range(n):
            if j in chosen:
                continue
            if max_per_district is not None and district_counts.get(districts[j], 0) >= max_per_district:
                continue
            newly = covers[:, j] & ~covered
            gain = demand[newly].sum()
            if gain > best_gain:
                best_j, best_gain = j, gain
        if best_j == -1 or best_gain <= 0:
            break
        chosen.append(best_j)
        covered |= covers[:, best_j]
        district_counts[districts[best_j]] = district_counts.get(districts[best_j], 0) + 1
    return chosen, float(demand[covered].sum())


def solve(schools_df: pd.DataFrame, k: int = 5, radius_km: float = 20.0, max_per_district: int | None = None) -> OptimizeResult:
    import time
    t0 = time.time()

    sites = build_sites(schools_df)
    n = len(sites)
    demand = sites["demand"].to_numpy()
    districts = sites["district"].to_numpy()
    covers = _coverage_matrix(sites, radius_km)

    # ---- ILP: maximize covered weighted demand, choose <= k facility sites ----
    prob = pulp.LpProblem("mobile_unit_siting", pulp.LpMaximize)
    y = [pulp.LpVariable(f"y_{j}", cat="Binary") for j in range(n)]   # facility opened at j?
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]   # demand i covered?

    prob += pulp.lpSum(demand[i] * x[i] for i in range(n))
    prob += pulp.lpSum(y) <= k
    if max_per_district is not None:
        for d in pd.unique(districts):
            idx = np.where(districts == d)[0]
            prob += pulp.lpSum(y[j] for j in idx) <= max_per_district
    for i in range(n):
        covering_js = np.where(covers[i])[0]
        if len(covering_js) == 0:
            prob += x[i] == 0
        else:
            prob += x[i] <= pulp.lpSum(y[j] for j in covering_js)

    prob.solve(pulp.PULP_CBC_CMD(msg=0))
    status = pulp.LpStatus[prob.status]

    chosen = [j for j in range(n) if pulp.value(y[j]) > 0.5]
    ilp_covered_demand = float(sum(demand[i] for i in range(n) if pulp.value(x[i]) > 0.5))

    greedy_chosen, greedy_covered_demand = greedy_coverage(sites, covers, k, max_per_district=max_per_district)

    sites = sites.copy()
    sites["chosen"] = False
    sites.loc[chosen, "chosen"] = True
    covered_mask = np.zeros(n, dtype=bool)
    for j in chosen:
        covered_mask |= covers[:, j]
    sites["covered"] = covered_mask

    return OptimizeResult(
        sites=sites,
        chosen_ids=sites.loc[chosen, "site_id"].tolist(),
        ilp_coverage=ilp_covered_demand,
        greedy_coverage=greedy_covered_demand,
        total_demand=float(demand.sum()),
        status=status,
        solve_seconds=time.time() - t0,
    )
