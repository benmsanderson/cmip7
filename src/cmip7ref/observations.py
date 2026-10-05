"""Observed Nino3.4, from NOAA CPC.

``oni.ascii.txt`` carries both the absolute Nino3.4 SST (``TOTAL``, a 3-month
running mean from ERSSTv5) and CPC's official ONI anomaly (``ANOM``). CPC
re-centres the ONI base period every five years, which is the discrete version
of the running climatology applied to the models, so the two are comparable.

Taking ``TOTAL`` as well lets us re-derive the anomaly with exactly the model
method as a cross-check.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd

ONI_URL = "https://www.cpc.ncep.noaa.gov/data/indices/oni.ascii.txt"
CACHE = Path(".cache/obs")

# The ONI's 3-month seasons, by the month they are centred on.
SEASON_CENTRE = {
    "DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
    "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12,
}


def oni(refresh: bool = False) -> pd.DataFrame:
    """CPC's Oceanic Nino Index: absolute SST and the official anomaly.

    Returns ``year, month, season, sst, anomaly`` with one row per overlapping
    3-month season, the month being the centre of that season.
    """
    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / "oni.ascii.txt"
    if refresh or not path.exists():
        r = httpx.get(ONI_URL, timeout=120, headers={"User-Agent": "cmip7ref/0.1"}, follow_redirects=True)
        r.raise_for_status()
        path.write_text(r.text)

    rows = []
    for line in path.read_text().splitlines()[1:]:
        parts = line.split()
        if len(parts) != 4:
            continue
        season, year, total, anom = parts
        rows.append(
            {
                "year": int(year),
                "month": SEASON_CENTRE[season],
                "season": season,
                "sst": float(total),
                "anomaly": float(anom),
            }
        )
    df = pd.DataFrame(rows).sort_values(["year", "month"]).reset_index(drop=True)
    df["source"] = "CPC ONI (ERSSTv5)"
    return df
