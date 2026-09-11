"""
Builds backend/data/karnataka_districts.geojson: real district boundary
polygons with district-name properties only (no risk stats -- those
are computed live by the backend from the same pipeline as everything
else, and joined onto this static geometry at request time. Keeping
scoring logic in one place, not duplicated into this script, is the
point).

Source: datameet/maps, Districts/Census_2011/2011_Dist.shp -- 2011
Census district boundaries for all of India (CC BY 2.5 India; see that
repo's Districts/README.md for provenance). Filtered to Karnataka (30
polygons) here.

RECONCILING TWO DIFFERENT "34 DISTRICTS": UDISE+ maintains its own
education-district codes, which don't line up 1:1 with the 2011 Census
revenue districts this boundary data uses -- Karnataka has 30 Census
districts but 34 UDISE+ districts, because four populous districts
(Bengaluru Urban, Belgaum, Tumkur, Uttara Kannada) are each split into
two UDISE+ districts with no matching boundary split available here.
Where that happens, this script tags ONE polygon (the old undivided
boundary) with BOTH UDISE+ child district names in `udise_districts`;
main.py averages their live stats (school-count-weighted) onto that
one polygon -- an honest simplification, not a precise sub-division.
Everywhere else it's a clean 1:1 rename (Bangalore -> Bengaluru,
Mysore -> Mysuru, Gulbarga -> Kalburgi, etc. -- Karnataka officially
Kannada-ized a number of district names circa 2014, after this 2011
boundary data's names were set).

Run from the repo root:
    python scripts/build_district_boundaries.py \
        /path/to/datameet-maps/Districts/Census_2011/2011_Dist.shp \
        backend/data/karnataka_districts.geojson
"""

import json
import sys

import shapefile

# census 2011 district name -> one or more UDISE+ dtname values.
# One-to-many entries are the four splits described above.
CENSUS_TO_UDISE = {
    "Bagalkot": ["Bagalkot"],
    "Bangalore": ["Bengaluru U North", "Bengaluru U South"],
    "Bangalore Rural": ["Bengaluru Rural"],
    "Belgaum": ["Belagavi", "Belagavi Chikkodi"],
    "Bellary": ["Ballari"],
    "Bidar": ["Bidar"],
    "Bijapur": ["Vijayapura"],
    "Chamrajnagar": ["Chamarajanagara"],
    "Chikkaballapura": ["Chikkaballapura"],
    "Chikmagalur": ["Chikkamangaluru"],
    "Chitradurga": ["Chitradurga"],
    "Dakshina Kannada": ["Dakshina Kannada"],
    "Davanagere": ["Davanagere"],
    "Dharwad": ["Dharwad"],
    "Gadag": ["Gadag"],
    "Gulbarga": ["Kalburgi"],
    "Hassan": ["Hassan"],
    "Haveri": ["Haveri"],
    "Kodagu": ["Kodagu"],
    "Kolar": ["Kolar"],
    "Koppal": ["Koppal"],
    "Mandya": ["Mandya"],
    "Mysore": ["Mysuru"],
    "Raichur": ["Raichur"],
    "Ramanagara": ["Ramanagara"],
    "Shimoga": ["Shivamogga"],
    "Tumkur": ["Tumakuru", "Tumakuru Madhugiri"],
    "Udupi": ["Udupi"],
    "Uttara Kannada": ["Uttara Kannada", "Uttara Kannada Sirsi"],
    "Yadgir": ["Yadagiri"],
}


def main(shp_path: str, out_path: str) -> None:
    sf = shapefile.Reader(shp_path)
    features = []
    matched_udise = set()

    ka_indices = [i for i, r in enumerate(sf.records()) if r["ST_NM"].strip() == "Karnataka"]
    for i in ka_indices:
        rec = sf.record(i)
        census_name = rec["DISTRICT"].strip()
        udise_names = CENSUS_TO_UDISE.get(census_name)
        if not udise_names:
            print(f"WARNING: no mapping for census district '{census_name}', skipping")
            continue
        matched_udise.update(udise_names)

        geom = sf.shape(i).__geo_interface__
        features.append({
            "type": "Feature",
            "geometry": geom,
            "properties": {
                "census_name": census_name,
                "udise_districts": udise_names,
            },
        })

    found_names = {sf.record(i)["DISTRICT"].strip() for i in ka_indices}
    unmapped_in_shapefile = found_names - set(CENSUS_TO_UDISE)
    if unmapped_in_shapefile:
        print(f"WARNING: found in shapefile but not in mapping dict: {unmapped_in_shapefile}")

    fc = {"type": "FeatureCollection", "features": features}
    with open(out_path, "w") as f:
        json.dump(fc, f)
    print(f"{len(features)} district polygons written, covering {len(matched_udise)} UDISE+ district names -> {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python build_district_boundaries.py <shapefile.shp> <out.geojson>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
