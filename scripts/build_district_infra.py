"""
Rebuilds backend/data/karnataka_district_infra_2019-20.csv from real
UDISE+ report data.

Source: thejeshgn/udise-report-data-downloader, which ships already-
scraped UDISE+ Public Report JSON (a live scrape wasn't reachable from
the sandbox this project was built in -- data.gov.in and
udiseplus.gov.in weren't on the network allowlist, but github.com was,
so a repo with pre-scraped report JSON was). Clone it first:

    git clone https://github.com/thejeshgn/udise-report-data-downloader.git

then run this script from the repo root you just cloned into (it reads
./raw/<report>/*.json relative to CWD) with an output path:

    python build_district_infra.py /path/to/karnataka_district_infra_2019-20.csv

What each report's "Total" field means, per that repo's own readme:
count of schools *with* that facility, broken down by school-stage
category and management type. Cross-checked here against
number_of_schools_report_1003 (total schools, same breakdown) --
functional-toilet Total never exceeded total-schools Total in spot
checks, which is what you'd expect if the interpretation is right.

Only Karnataka (UDISE state code 29) is pulled. All 34 districts had
complete 2019-20 coverage across all five reports used below at the
time this was run -- re-run and re-check district counts if the
upstream repo's data changes.
"""

import glob
import json
import os
import sys

import pandas as pd

STATE_CODE = "29"  # Karnataka
YEAR = "2019-20"

REPORTS = {
    "schools": "number_of_schools_report_1003",
    "toilet": "functional_toilet_facility_report_3061",
    "library": "schools_having_library_report_3031",
    "computer": "schools_having_computer_available_report_3109",
    "internet": "schools_having_internet_facility_report_3106",
}


def load_report(report_dir: str) -> dict:
    """Sum the 'Total' field across all management-type rows, per district."""
    out = {}
    pattern = f"raw/{report_dir}/*_district_{STATE_CODE}_*_NA_{YEAR}.json"
    for f in glob.glob(pattern):
        district_code = os.path.basename(f).split("_")[4]
        data = json.load(open(f))
        out[district_code] = sum(row.get("Total", 0) or 0 for row in data["rowValue"])
    return out


def main(out_path: str) -> None:
    totals = {name: load_report(path) for name, path in REPORTS.items()}

    districts = json.load(open("raw/UDISE_Districts.json"))["rowValue"]
    code_to_name = {
        r["udise_district_code"]: r["district_name"]
        for r in districts
        if r["udise_state_code"] == STATE_CODE
    }

    rows = []
    for code, name in code_to_name.items():
        total_schools = totals["schools"].get(code, 0)
        if not total_schools:
            continue
        rows.append({
            "district_code": code,
            "district_name": name,
            "total_schools_reported": total_schools,
            "toilet_gap": 1 - totals["toilet"].get(code, 0) / total_schools,
            "library_gap": 1 - totals["library"].get(code, 0) / total_schools,
            "computer_gap": 1 - totals["computer"].get(code, 0) / total_schools,
            "internet_gap": 1 - totals["internet"].get(code, 0) / total_schools,
        })

    df = pd.DataFrame(rows)
    gap_cols = ["toilet_gap", "library_gap", "computer_gap", "internet_gap"]
    df["infra_gap_score"] = df[gap_cols].mean(axis=1).clip(0, 1)
    df = df.sort_values("infra_gap_score", ascending=False)

    print(f"{len(df)} Karnataka districts extracted for {YEAR}")
    df.to_csv(out_path, index=False)
    print(f"Saved to {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python build_district_infra.py <output_csv_path>")
        sys.exit(1)
    main(sys.argv[1])
