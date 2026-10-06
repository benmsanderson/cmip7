"""Forcing inputs: prescribed CO2 concentrations and global CO2 emissions.

Concentrations come straight from input4MIPs, which publishes ready-made global
means (``grid_label=gm``, annual, ~38 kB). Nothing needs reducing.

Emissions are another matter. input4MIPs publishes **no** global-total CO2
emissions product — only gridded fields — and the advertised OPeNDAP endpoints
404, so a global total means either downloading gridded files and area-summing
them, or taking totals from elsewhere. For this talk we take global totals
(see data/README.md):

* historical: the Global Carbon Budget compilation, via OWID's ``co2`` (fossil
  and industry, which includes international aviation and shipping bunkers) and
  ``land_use_change_co2``;
* scenarios: area-summed from the harmonised input4MIPs gridded files, which are
  what was actually passed to the ESMs.

Aviation (``CO2_em_AIR_anthro``) is a separate 3-D field costing 2.8 GB for the
two scenarios, and is roughly 2% of the total; ``--with-aviation`` opts in.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pandas as pd

SOLR = "https://esgf-data.dkrz.de/esg-search/search"
CACHE = Path(".cache/esgf/input4mips")
OWID_CSV = "https://raw.githubusercontent.com/owid/co2-data/master/owid-co2-data.csv"

# grid_label=gm annual global-mean concentration datasets
CONCENTRATION_SOURCES = {
    "historical": "CR-CMIP-1-0-0",
    "h": "CR-h-1-0-0",
    "vl": "CR-vl-1-0-0",
}
# harmonised gridded emissions passed to the ESMs
EMISSION_SOURCES = {"h": "IIASA-IAMC-h-1-1-0", "vl": "IIASA-IAMC-vl-1-1-0"}
EMISSION_AREACELLA = "IIASA-IAMC-1-1-0"

PGC_PER_PPM = 2.124
KG_CO2_PER_KG_C = 44.009 / 12.011
MTCO2_PER_GTCO2 = 1000.0


def solr_files(**facets: str) -> list[tuple[str, str, int]]:
    """``(filename, http url, size)`` for an input4MIPs dataset."""
    params = {"mip_era": "CMIP7", "type": "File", "limit": 200, "format": "application/solr+json", **facets}
    r = httpx.get(SOLR, params=params, timeout=120, headers={"User-Agent": "cmip7ref/0.1"})
    r.raise_for_status()
    out: dict[str, tuple[str, int]] = {}
    for doc in r.json()["response"]["docs"]:
        urls = [u.split("|")[0] for u in doc.get("url", []) if u.split("|")[-1] == "HTTPServer"]
        if urls and doc["title"] not in out:  # replicas repeat; keep the first
            out[doc["title"]] = (urls[0], doc.get("size", 0))
    return [(name, url, size) for name, (url, size) in sorted(out.items())]


def download(url: str, dest: Path, expected: int = 0) -> Path:
    """Fetch a file into the cache, skipping it if already complete."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and (not expected or dest.stat().st_size == expected):
        return dest
    print(f"  downloading {dest.name} ({expected / 1e6:.0f} MB)", flush=True)
    with httpx.stream("GET", url, timeout=600, follow_redirects=True) as r:
        r.raise_for_status()
        with open(dest, "wb") as fh:
            for chunk in r.iter_bytes(1 << 20):
                fh.write(chunk)
    return dest


def concentration(key: str) -> pd.DataFrame:
    """Annual global-mean prescribed CO2 in ppm for ``historical``, ``h`` or ``vl``."""
    import xarray as xr

    source_id = CONCENTRATION_SOURCES[key]
    files = solr_files(source_id=source_id, variable_id="co2", grid_label="gm", frequency="yr")
    if not files:
        raise RuntimeError(f"no gm concentration file found for {source_id}")
    # The historical dataset is split across files (years 1-999, 1000-1749, ...),
    # so every file has to be read, not just the first.
    from .reduce import time_decoding

    paths = [download(url, CACHE / source_id / name, size) for name, url, size in files]
    ds = xr.open_mfdataset([str(p) for p in paths], **time_decoding(), combine="by_coords")
    da = ds["co2"].squeeze().sortby("time")
    df = pd.DataFrame(
        {
            "scenario": key,
            "year": da["time"].dt.year.to_numpy().astype(int),
            "value": da.to_numpy().ravel(),
            "units": da.attrs.get("units", "ppm"),
            "source_dataset": f"{source_id} ({len(paths)} file(s))",
        }
    )
    ds.close()
    return df.sort_values("year").reset_index(drop=True)


def emissions_historical() -> pd.DataFrame:
    """Global CO2 emissions 1750- from the Global Carbon Budget, via OWID.

    ``co2`` is fossil and industry; ``land_use_change_co2`` is the land-use term.
    Both are MtCO2 yr-1 in the source and are returned as GtCO2 yr-1.
    """
    path = download(OWID_CSV, CACHE / "owid-co2-data.csv")
    d = pd.read_csv(path, low_memory=False)
    w = d[d["country"] == "World"][["year", "co2", "land_use_change_co2"]].dropna(subset=["co2"])
    return pd.DataFrame(
        {
            "scenario": "historical",
            "year": w["year"].astype(int),
            "fossil_GtCO2": w["co2"] / MTCO2_PER_GTCO2,
            "cdr_GtCO2": 0.0,  # no appreciable engineered CDR in the historical record
            "landuse_GtCO2": w["land_use_change_co2"] / MTCO2_PER_GTCO2,
            "interpolated": False,
            "source_dataset": "Global Carbon Budget via OWID owid-co2-data.csv",
        }
    ).reset_index(drop=True)


def emissions_scenario(key: str, with_aviation: bool = False) -> pd.DataFrame:
    """Global CO2 emissions for H or VL, area-summed from the harmonised grids.

    The surface anthropogenic field is ~650 MB per scenario. Aviation is a
    separate 3-D field of ~1.4 GB per scenario and is only summed on request.
    """
    import numpy as np
    import xarray as xr

    from .reduce import time_decoding as _time_decoding

    source_id = EMISSION_SOURCES[key]
    area = _emission_areacella()
    variables = ["CO2_em_anthro"] + (["CO2_em_AIR_anthro"] if with_aviation else [])
    columns: dict[str, pd.Series] = {}
    for variable in variables:
        files = solr_files(source_id=source_id, variable_id=variable, grid_label="gn")
        paths = [download(url, CACHE / source_id / name, size) for name, url, size in files]
        ds = xr.open_mfdataset([str(p) for p in paths], **_time_decoding(), combine="by_coords")
        name = next(v for v in ds.data_vars if v.lower().startswith("co2"))
        da = ds[name]
        # kg m-2 s-1 x m2 -> kg s-1, then seconds per month on the file's calendar
        gridded = (da * area).sum(dim=[d for d in da.dims if d in ("lat", "lon")])
        seconds = da["time"].dt.days_in_month * 86400.0
        annual = (gridded * seconds).groupby(da["time"].dt.year).sum() / 1e12  # GtCO2 yr-1

        if "sector" in annual.dims:
            # Sectors 0-7 are fossil and industrial; 8 is BECCS and 9 is other
            # capture and removal, so the CDR term is separable.
            fossil = annual.sel(sector=slice(0, 7)).sum("sector").to_series()
            cdr = annual.sel(sector=slice(8, 9)).sum("sector").to_series()
        else:
            fossil, cdr = annual.to_series(), None
        columns[f"{variable}_fossil"] = fossil
        if cdr is not None:
            columns[f"{variable}_cdr"] = cdr
        ds.close()

    fossil_total = sum(v for k, v in columns.items() if k.endswith("_fossil"))
    cdr_total = sum((v for k, v in columns.items() if k.endswith("_cdr")), start=0 * fossil_total)

    # The gridded scenario files are published at 5-yearly steps after 2025, not
    # annually, so they are interpolated onto every year the way a model running
    # the scenario would. Interpolated rows are flagged.
    published = fossil_total.index.astype(int)
    years = pd.RangeIndex(published.min(), published.max() + 1, name="year")
    fossil = fossil_total.set_axis(published).reindex(years).interpolate("index")
    cdr = cdr_total.set_axis(published).reindex(years).interpolate("index")

    out = pd.DataFrame(
        {
            "scenario": key,
            "year": years.astype(int),
            "fossil_GtCO2": fossil.to_numpy(),
            "cdr_GtCO2": cdr.to_numpy(),
            "landuse_GtCO2": np.nan,  # handled interactively by the ESM, not prescribed
            "interpolated": ~years.isin(published),
            "source_dataset": f"{source_id} ({', '.join(variables)}, area-summed)",
        }
    )
    return out.reset_index(drop=True)


def _emission_areacella():
    """Grid-cell area for the input4MIPs emissions grid."""
    import xarray as xr

    files = solr_files(source_id=EMISSION_AREACELLA, variable_id="areacella")
    name, url, size = files[0]
    path = download(url, CACHE / EMISSION_AREACELLA / name, size)
    return xr.open_dataset(path)["areacella"].load()


def gtco2_to_pgc(x):
    """GtCO2 -> PgC."""
    return x / KG_CO2_PER_KG_C
