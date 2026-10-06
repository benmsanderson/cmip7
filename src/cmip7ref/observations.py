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


RONI_URL = "https://www.cpc.ncep.noaa.gov/products/analysis_monitoring/enso/roni/"
RONI_V5_URL = RONI_URL + "v5/"

# The seasons as the RONI tables column them, in order.
SEASONS = ["DJF", "JFM", "FMA", "MAM", "AMJ", "MJJ", "JJA", "JAS", "ASO", "SON", "OND", "NDJ"]


def roni(version: str = "v6", refresh: bool = False) -> pd.DataFrame:
    """CPC's Relative Oceanic Nino Index, scraped from their table.

    RONI is the Nino3.4 anomaly minus the tropical-mean (20N-20S) anomaly, then
    rescaled so its variance matches the original Nino3.4 index, on a 1991-2020
    base. It is published only as an HTML table, so this parses one.

    ``version`` picks the ERSST vintage: ``v6`` is the page's current index,
    ``v5`` the one matching the ONI file and the ERSSTv5 grids.
    """
    import re
    from html import unescape

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"roni_{version}.html"
    if refresh or not path.exists():
        url = RONI_V5_URL if version == "v5" else RONI_URL
        r = httpx.get(url, timeout=120, headers={"User-Agent": "Mozilla/5.0 cmip7ref/0.1"},
                      follow_redirects=True)
        r.raise_for_status()
        path.write_text(r.text)

    rows = []
    for block in re.findall(r"<tr[^>]*>(.*?)</tr>", path.read_text(errors="replace"), flags=re.S | re.I):
        cells = [unescape(re.sub(r"<[^>]+>", "", c)).strip()
                 for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", block, flags=re.S | re.I)]
        if not cells or not re.fullmatch(r"\d{4}", cells[0]):
            continue
        year = int(cells[0])
        for season, value in zip(SEASONS, cells[1:]):
            if re.fullmatch(r"-?\d+(\.\d+)?", value):
                rows.append({"year": year, "month": SEASON_CENTRE[season], "season": season,
                             "roni": float(value)})
    df = pd.DataFrame(rows).sort_values(["year", "month"]).reset_index(drop=True)
    df["source"] = f"CPC RONI (ERSST.{version})"
    return df


ERSST_URL = "https://downloads.psl.noaa.gov/Datasets/noaa.ersst.{version}/sst.mnmean.nc"


def ersst_regions(version: str = "v6", refresh: bool = False) -> pd.DataFrame:
    """Monthly Nino3.4 and tropical-mean SST from the gridded ERSST field.

    CPC publish the ONI and the RONI but not the tropical-mean series the RONI
    is built from, so to process observations the same way as the models we
    reduce the gridded field ourselves. Against the matching published table
    this reproduces CPC's RONI to 0.04 degC, which is the check that the recipe
    here is theirs.

    ``version`` should match whichever table is being compared against: CPC's
    current RONI page is ERSSTv6, whose high-frequency filter damps the most
    recent months - it puts JAS 2026 at +1.7 where v5 gives +2.1.
    """
    import xarray as xr

    from .indices import REGIONS, box_mean, monthly_frame

    CACHE.mkdir(parents=True, exist_ok=True)
    path = CACHE / f"ersst.{version}.sst.mnmean.nc"
    if refresh or not path.exists():
        with httpx.stream("GET", ERSST_URL.format(version=version), timeout=1800, follow_redirects=True) as r:
            r.raise_for_status()
            with open(path, "wb") as fh:
                for chunk in r.iter_bytes(1 << 20):
                    fh.write(chunk)

    ds = xr.open_dataset(path)
    frames = []
    for name, box in REGIONS.items():
        frame = monthly_frame(box_mean(ds["sst"], ds, box).compute())
        frame["region"] = name
        frames.append(frame)
    ds.close()
    out = pd.concat(frames, ignore_index=True)
    out["units"] = "degC"
    out["source"] = f"ERSST{version}"
    return out
