"""Lazy CMIP6 access via the Pangeo Zarr mirror of ESGF.

ESGF's own OPeNDAP endpoints are advertised in the index but 404 at every node we
tried (CEDA, DKRZ), so "lazy, no downloads" is not achievable through ESGF
itself. The Pangeo copy on Google Cloud serves the same data as Zarr over plain
HTTPS with no credentials, and only the chunks we touch cross the network — which
is what makes reading a single model level out of a 3-D field affordable.

Its coverage is a subset of ESGF's: see docs/data_availability.md.
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import xarray as xr

CATALOG_URL = "https://storage.googleapis.com/cmip6/pangeo-cmip6.csv"
CACHE = Path(".cache/esgf/pangeo-cmip6.csv")


def catalog() -> pd.DataFrame:
    """The Pangeo CMIP6 catalog, cached locally."""
    if not CACHE.exists():
        CACHE.parent.mkdir(parents=True, exist_ok=True)
        pd.read_csv(CATALOG_URL).to_csv(CACHE, index=False)
    return pd.read_csv(CACHE, low_memory=False)


def lowest_member(df: pd.DataFrame) -> pd.DataFrame:
    """One member per model: the lowest realisation index available."""
    df = df.copy()
    df["r"] = df["member_id"].str.extract(r"^r(\d+)").astype(int)
    return df.sort_values(["source_id", "r", "member_id"]).groupby("source_id", as_index=False).first()


def find(experiment_id: str, variable_id: str, table_id: str | None = None) -> pd.DataFrame:
    """Catalog rows for one experiment and variable, one member per model."""
    cat = catalog()
    sel = cat[(cat.experiment_id == experiment_id) & (cat.variable_id == variable_id)]
    if table_id:
        sel = sel[sel.table_id == table_id]
    return lowest_member(sel) if len(sel) else sel


def open_store(zstore: str) -> xr.Dataset:
    """Open a catalog row's Zarr store over HTTPS."""
    from .reduce import time_decoding

    url = zstore.replace("gs://", "https://storage.googleapis.com/")
    return xr.open_zarr(url, consolidated=True, **time_decoding())


def surface_level(da: xr.DataArray) -> xr.DataArray:
    """Select the model level nearest the surface from a 3-D field.

    Pressure-like coordinates take their largest value; hybrid sigma
    coordinates (which run 0 at the top to ~1 at the surface) do too, so in
    both cases the surface is the maximum of the vertical coordinate.
    """
    vertical = next((d for d in da.dims if d in ("lev", "plev", "level", "alevel")), None)
    if vertical is None:
        return da
    coord = da[vertical]
    index = int(coord.to_numpy().argmax())
    out = da.isel({vertical: index})
    out.attrs["surface_level"] = f"{vertical}={float(coord[index]):.6g} {coord.attrs.get('units', '')}".strip()
    return out


FX_EXPERIMENT_ORDER = ("esm-hist", "historical", "piControl", "esm-piControl")


def fx(source_id: str, variable: str) -> xr.DataArray | None:
    """An fx/Ofx field (areacella, areacello, sftlf) for a model.

    Pangeo stores do not carry their cell areas, and these fields are published
    under whichever experiment the centre chose, so any experiment will do —
    the grid is the same.
    """
    cat = catalog()
    sel = cat[(cat.source_id == source_id) & (cat.variable_id == variable)]
    if sel.empty:
        return None
    order = {e: i for i, e in enumerate(FX_EXPERIMENT_ORDER)}
    sel = sel.assign(rank=sel.experiment_id.map(lambda e: order.get(e, len(order))))
    row = sel.sort_values(["rank", "member_id"]).iloc[0]
    try:
        return open_store(row.zstore)[variable].load()
    except Exception as exc:  # pragma: no cover - depends on the mirror
        print(f"    could not load {variable} for {source_id}: {type(exc).__name__}")
        return None
