"""
FastAPI app for the dropout-risk hotspot mapper.

Computes risk + clusters once at startup and serves them from memory --
74k rows is small enough that there's no need for a database for this
prototype. Swap load_schools()/compute_risk() for real report-data
sources when moving past the demo stage.
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .data import load_schools
from .risk import compute_risk, KARNATAKA_2019_20_REFERENCE
from .clustering import find_hotspots
from . import optimizer
from . import boundaries

app = FastAPI(title="Dropout-Risk Hotspot Mapper (Karnataka demo)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # demo only -- lock this down before deploying
    allow_methods=["*"],
    allow_headers=["*"],
)

_schools = compute_risk(load_schools())
_schools, _hotspots = find_hotspots(_schools)
_district_geojson = boundaries.build_choropleth(_schools)


def _school_row(row) -> dict:
    return {
        "schcd": str(row.schcd),
        "schname": row.schname,
        "district": row.dtname,
        "management": row.management,
        "rural_urban": row.rururb_label,
        "school_cat": row.school_cat,
        "lat": float(row.latitude),
        "lon": float(row.longitude),
        "risk_score": round(float(row.demo_risk_score), 3),
        "risk_tier": str(row.risk_tier),
        "cluster_id": int(row.cluster_id),
    }


@app.get("/api/stats")
def stats():
    tier_counts = _schools["risk_tier"].value_counts().to_dict()
    return {
        "total_schools": int(len(_schools)),
        "districts": int(_schools["dtname"].nunique()),
        "risk_tier_counts": {str(k): int(v) for k, v in tier_counts.items()},
        "hotspot_count": int(len(_hotspots)),
        "karnataka_2019_20_reference": KARNATAKA_2019_20_REFERENCE,
    }


@app.get("/api/hotspots")
def hotspots():
    return [
        {
            "cluster_id": int(r.cluster_id),
            "district": r.district,
            "school_count": int(r.school_count),
            "high_risk_count": int(r.high_risk_count),
            "avg_risk": round(float(r.avg_risk), 3),
            "risk_lift": round(float(r.risk_lift), 3),
            "centroid_lat": float(r.centroid_lat),
            "centroid_lon": float(r.centroid_lon),
        }
        for r in _hotspots.itertuples()
    ]


@app.get("/api/schools")
def schools(
    cluster_id: int | None = Query(default=None),
    district: str | None = Query(default=None),
    risk_tier: str | None = Query(default=None),
    limit: int = Query(default=2000, le=10000),
):
    df = _schools
    if cluster_id is not None:
        df = df[df["cluster_id"] == cluster_id]
    if district is not None:
        df = df[df["dtname"].str.lower() == district.lower()]
    if risk_tier is not None:
        df = df[df["risk_tier"].astype(str).str.lower() == risk_tier.lower()]
    if df.empty and (cluster_id is not None or district is not None):
        raise HTTPException(status_code=404, detail="No schools match that filter")
    return [_school_row(r) for r in df.head(limit).itertuples()]


@app.get("/api/districts")
def districts():
    return sorted(_schools["dtname"].dropna().unique().tolist())


@app.get("/api/districts/geojson")
def districts_geojson():
    return _district_geojson


@app.get("/api/optimize")
def optimize(
    k: int = Query(default=10, ge=1, le=60),
    radius_km: float = Query(default=20.0, ge=2, le=100),
    equity: bool = Query(default=True, description="Cap units per district for geographic spread"),
    max_per_district: int = Query(default=1, ge=1, le=10),
):
    result = optimizer.solve(
        _schools,
        k=k,
        radius_km=radius_km,
        max_per_district=max_per_district if equity else None,
    )
    chosen = result.sites[result.sites["chosen"]].sort_values("demand", ascending=False)
    total = result.total_demand or 1.0
    return {
        "status": result.status,
        "solve_seconds": round(result.solve_seconds, 3),
        "k": k,
        "radius_km": radius_km,
        "equity_cap": max_per_district if equity else None,
        "total_demand": round(total, 1),
        "ilp_coverage": round(result.ilp_coverage, 1),
        "ilp_coverage_pct": round(100 * result.ilp_coverage / total, 2),
        "greedy_coverage": round(result.greedy_coverage, 1),
        "greedy_coverage_pct": round(100 * result.greedy_coverage / total, 2),
        "gap": round(result.ilp_coverage - result.greedy_coverage, 1),
        "chosen_sites": [
            {
                "site_id": r.site_id,
                "district": r.district,
                "lat": float(r.lat),
                "lon": float(r.lon),
                "school_count": int(r.school_count),
                "high_risk_count": int(r.high_risk_count),
                "demand": round(float(r.demand), 1),
            }
            for r in chosen.itertuples()
        ],
    }
