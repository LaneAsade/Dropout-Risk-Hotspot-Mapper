"""
Joins the static district boundary polygons (built once by
scripts/build_district_boundaries.py) with LIVE district-level risk
stats computed from the current schools dataframe -- so the choropleth
always reflects whatever risk.py's current scoring logic produces,
never a stale, separately-computed copy of it.
"""

import json
from pathlib import Path

import pandas as pd

GEOJSON_PATH = Path(__file__).resolve().parent.parent / "data" / "karnataka_districts.geojson"


def _weighted_district_stats(schools_df: pd.DataFrame) -> pd.DataFrame:
    return (
        schools_df.groupby("dtname")
        .agg(
            school_count=("schcd", "count"),
            avg_risk=("demo_risk_score", "mean"),
            high_risk_count=("risk_tier", lambda s: (s == "High").sum()),
        )
        .reset_index()
    )


def build_choropleth(schools_df: pd.DataFrame) -> dict:
    """Returns a GeoJSON FeatureCollection: real district boundaries, each
    carrying live risk stats as properties. For the four UDISE+ districts
    that share one 2011-census boundary (see build_district_boundaries.py),
    stats are combined school-count-weighted across the shared polygon."""
    fc = json.loads(GEOJSON_PATH.read_text())
    stats = _weighted_district_stats(schools_df).set_index("dtname")
    state_avg_risk = float(schools_df["demo_risk_score"].mean())

    for feature in fc["features"]:
        names = feature["properties"]["udise_districts"]
        rows = stats.loc[stats.index.intersection(names)]
        total_schools = int(rows["school_count"].sum())
        if total_schools > 0:
            avg_risk = float((rows["avg_risk"] * rows["school_count"]).sum() / total_schools)
            high_risk_count = int(rows["high_risk_count"].sum())
        else:
            avg_risk, high_risk_count = state_avg_risk, 0

        feature["properties"].update({
            "school_count": total_schools,
            "avg_risk": round(avg_risk, 3),
            "high_risk_count": high_risk_count,
            "risk_lift": round(avg_risk - state_avg_risk, 3),
            "display_name": " / ".join(names) if len(names) > 1 else names[0],
        })

    return fc
