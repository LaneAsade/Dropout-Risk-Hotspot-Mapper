"""
Loads the real, geocoded Karnataka school list.

Source: datameet/udise_schools (github.com/datameet/udise_schools),
an open-download GeoJSON/CSV export of UDISE school locations
(school code, name, category, management, rural/urban flag, district,
lat/long). This is real government school data -- only the risk score
layered on top in risk.py is partly simulated. Filtered to Karnataka
here to keep the demo fast; the same pipeline runs on any state by
changing the filter in scripts/build_dataset.py.
"""

from pathlib import Path
import pandas as pd

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "karnataka_schools.csv"


def load_schools() -> pd.DataFrame:
    df = pd.read_csv(DATA_PATH, dtype={"schcd": str})
    df = df.dropna(subset=["latitude", "longitude"])
    return df
