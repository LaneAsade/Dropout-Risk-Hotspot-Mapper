"""
Hotspot detection.

FIRST ATTEMPT (worth knowing about, in case you get asked in judging):
plain DBSCAN over high-risk school *points* was the direct port of the
ParkSight patrol-hotspot pipeline, but it doesn't transfer cleanly here.
Parking violations are events -- density of violations directly means
"more problems here." Schools are fixed infrastructure -- density of
schools mostly just means "more people live here," irrespective of risk.
At a loose eps (5km) everything chained into one 53k-school "cluster";
at a tight eps (1.5km) it just re-discovered normal rural school spacing
as ~1,900 meaningless micro-clusters.

FIX: aggregate into fixed grid cells (~8km, roughly taluk-scale) and
rank cells by *relative* risk -- average risk score compared to the
state-wide average -- rather than by point density. A cell only counts
as a hotspot if it also clears a minimum school count, so a cell with
2 unlucky schools can't outrank a real concentration. This is the same
idea as the district-level LISA approach in the PLOS ONE precedent, just
at finer (sub-district) granularity, and it sidesteps the chaining
problem entirely because cell size doesn't depend on local density.

DBSCAN is still used, just downstream: *within* a chosen hotspot cell,
to group its individual high-risk schools for the drill-down list.
"""

import pandas as pd
from sklearn.cluster import DBSCAN

GRID_DEG = 0.08  # ~8-9km at Karnataka's latitude -- roughly taluk-scale
MIN_SCHOOLS_PER_CELL = 15  # cells with fewer schools are too noisy to rank


def find_hotspots(df: pd.DataFrame, min_schools: int = MIN_SCHOOLS_PER_CELL, top_n: int = 20):
    """
    Returns (schools_with_cell_id, hotspot_summary). Hotspot summary is
    the top_n grid cells ranked by (avg_risk - state_avg_risk), i.e. how
    far above the state baseline that cell runs, not raw school count.
    """
    df = df.copy()
    df["cell_row"] = (df["latitude"] // GRID_DEG).astype(int)
    df["cell_col"] = (df["longitude"] // GRID_DEG).astype(int)
    df["cell_id"] = df["cell_row"].astype(str) + "_" + df["cell_col"].astype(str)

    state_avg = df["demo_risk_score"].mean()

    cell_stats = (
        df.groupby("cell_id")
        .agg(
            school_count=("schcd", "count"),
            avg_risk=("demo_risk_score", "mean"),
            high_risk_count=("risk_tier", lambda s: (s == "High").sum()),
            centroid_lat=("latitude", "mean"),
            centroid_lon=("longitude", "mean"),
            district=("dtname", lambda s: s.mode().iat[0] if not s.mode().empty else s.iloc[0]),
        )
        .reset_index()
    )
    cell_stats["risk_lift"] = cell_stats["avg_risk"] - state_avg

    eligible = cell_stats[cell_stats["school_count"] >= min_schools].copy()
    hotspots = eligible.sort_values("risk_lift", ascending=False).head(top_n).reset_index(drop=True)
    hotspots["cluster_id"] = hotspots.index

    cell_to_cluster = dict(zip(hotspots["cell_id"], hotspots["cluster_id"]))
    df["cluster_id"] = df["cell_id"].map(cell_to_cluster).fillna(-1).astype(int)

    return df, hotspots[[
        "cluster_id", "district", "school_count", "high_risk_count",
        "avg_risk", "risk_lift", "centroid_lat", "centroid_lon",
    ]]


def schools_in_hotspot(schools_df: pd.DataFrame, cluster_id: int, eps_km: float = 1.5, min_samples: int = 3):
    """
    Sub-groups a single hotspot cell's high-risk schools with DBSCAN, so
    the UI can show 'these 3 schools are basically neighbors' inside the
    cell rather than one flat list. Small-scale use of DBSCAN, not for
    ranking significance.
    """
    subset = schools_df[
        (schools_df["cluster_id"] == cluster_id) & (schools_df["risk_tier"].isin(["Medium", "High"]))
    ].copy()
    if len(subset) < min_samples:
        subset["local_group"] = 0
        return subset
    coords = subset[["latitude", "longitude"]].to_numpy()
    eps_deg = eps_km / 111.0
    subset["local_group"] = DBSCAN(eps=eps_deg, min_samples=min_samples).fit_predict(coords)
    return subset
