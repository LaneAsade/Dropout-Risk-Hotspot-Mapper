"""
Risk scoring for the dropout-risk hotspot mapper.

UPDATE: this used to blend a real school-level signal with a seeded-
random placeholder for infrastructure. That placeholder is gone. The
infra component below is now real 2019-20 UDISE+ data (functional
toilets, library, computer, internet access), pulled from
thejeshgn/udise-report-data-downloader's cached report JSON -- a live
scrape wasn't reachable from this sandbox, but this repo ships the
already-scraped files for exactly these indicators, and all 34
Karnataka districts have complete 2019-20 coverage across all five
reports used here (see scripts/build_district_infra.py for the
extraction). Cross-checked against a related figure the two totally
independent data pulls agree on: this project's earlier research found
a published national estimate of ~17% secondary-level dropout; the
same real UDISE+ cohort data used for the infra numbers here computes
Karnataka's actual 2019-20 secondary dropout rate at 17.8%.

WHAT'S STILL A MODELING CHOICE, NOT A MEASUREMENT:
- `real_signal` (rural flag, "terminal primary" transition flag,
  govt-management flag) is a documented rule, not fitted to real
  dropout outcomes -- correlation assumed from general education
  research, not verified against Karnataka-specific results.
- `infra_gap_score` is real but district-level, so every school in a
  district currently gets the same figure. School-level infra data
  exists in principle (the UDISE+ portal reports down to school level)
  but wasn't reachable at that granularity from here.
- The two are blended into one `demo_risk_score`. Treat it as "a
  reasonable proxy built transparently from real components," not a
  validated dropout-probability model -- say so if you present it.
"""

from pathlib import Path

import pandas as pd

RURURB_LABELS = {1: "Rural", 2: "Urban"}
TERMINAL_PRIMARY_CATEGORIES = {"Primary", "Upper Primary only"}

INFRA_PATH = Path(__file__).resolve().parent.parent / "data" / "karnataka_district_infra_2019-20.csv"

# Karnataka, 2019-20, computed from real UDISE+ cohort-flow data
# (student_dropout_rate_report_4017), all castes combined -- see
# scripts/build_district_infra.py. Shown in the UI as an external
# sanity check on the district infra numbers, not used in the score
# itself (state-level, so it can't vary the score school to school).
KARNATAKA_2019_20_REFERENCE = {
    "primary_dropout_pct": 1.18,
    "primary_promotion_pct": 98.49,
    "secondary_dropout_pct": 17.83,
    "secondary_promotion_pct": 81.71,
    "source": "UDISE+ cohort data via thejeshgn/udise-report-data-downloader",
}


def add_real_signal(df: pd.DataFrame) -> pd.DataFrame:
    """School-level rule-based signal from real UDISE+ school attributes."""
    df = df.copy()
    df["rururb_label"] = df["rururb"].map(RURURB_LABELS).fillna("Unknown")
    df["is_rural"] = (df["rururb_label"] == "Rural").astype(int)
    df["is_terminal_primary"] = df["school_cat"].isin(TERMINAL_PRIMARY_CATEGORIES).astype(int)
    df["is_govt"] = df["management"].str.contains("Government|Department of Education", case=False, na=False).astype(int)

    df["real_signal"] = (
        0.5 * df["is_rural"]
        + 0.35 * df["is_terminal_primary"]
        + 0.15 * df["is_govt"]
    )
    return df


def add_district_infra_signal(df: pd.DataFrame) -> pd.DataFrame:
    """
    Real, district-level infra-gap signal: mean of (1 - schools with
    functional toilet/library/computer/internet, as a fraction of all
    schools in the district), UDISE+ 2019-20. Same figure for every
    school in a district -- see module docstring.
    """
    df = df.copy()
    infra = pd.read_csv(INFRA_PATH)
    infra["district_key"] = infra["district_name"].str.upper().str.strip()
    df["district_key"] = df["dtname"].str.upper().str.strip()

    lookup = infra.set_index("district_key")["infra_gap_score"]
    df["infra_gap_score"] = df["district_key"].map(lookup)

    if df["infra_gap_score"].isna().any():
        # Shouldn't happen -- all 34 districts matched at build time --
        # but fall back to the state mean rather than silently NaN-ing
        # a score if a district ever fails to match.
        df["infra_gap_score"] = df["infra_gap_score"].fillna(infra["infra_gap_score"].mean())

    return df.drop(columns=["district_key"])


def compute_risk(df: pd.DataFrame, real_weight: float = 0.5) -> pd.DataFrame:
    """Combine school-level + district-level real signal into demo_risk_score in [0, 1] and a tier."""
    df = add_real_signal(df)
    df = add_district_infra_signal(df)
    df["demo_risk_score"] = (
        real_weight * df["real_signal"] + (1 - real_weight) * df["infra_gap_score"]
    ).clip(0, 1)

    df["risk_tier"] = pd.cut(
        df["demo_risk_score"],
        bins=[-0.01, 0.4, 0.6, 1.01],
        labels=["Low", "Medium", "High"],
    )
    return df
