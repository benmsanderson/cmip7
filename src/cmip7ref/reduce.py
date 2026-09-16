"""Reduce downloaded monthly fields to annual global series.

The weighting depends on what the variable is:

* intensive quantities (``tas``, ``rtmt``, CO2 mole fraction) become an
  area-weighted **mean**;
* land carbon fluxes (``nbp``) become an area-weighted **sum** over the land
  fraction, converted to PgC yr-1.

Monthly to annual always uses calendar-aware month lengths — UKESM runs a 360-day
calendar, where every month weighs the same, but CMIP6 models do not.
"""

from __future__ import annotations

import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import xarray as xr

KG_PER_PG = 1e12
SECONDS_PER_DAY = 86400.0


def time_decoding() -> dict:
    """cftime decoding kwargs, across the xarray API change."""
    try:
        return {"decode_times": xr.coders.CFDatetimeCoder(use_cftime=True)}
    except AttributeError:  # xarray < 2025.1
        return {"use_cftime": True}


def open_files(paths: list[Path] | list[str]) -> xr.Dataset:
    """Open one dataset's netCDF files as a single time series."""
    return xr.open_mfdataset(
        sorted(str(p) for p in paths),
        **time_decoding(),
        combine="by_coords",
        data_vars="minimal",
        coords="minimal",
        compat="override",
    )


def _month_weights(da: xr.DataArray) -> xr.DataArray:
    """Days in each month, for calendar-aware annual averaging."""
    return da["time"].dt.days_in_month


def _year(da: xr.DataArray) -> xr.DataArray:
    return da["time"].dt.year


def cell_area(area: xr.DataArray | None, like: xr.DataArray, source: str = "") -> tuple[xr.DataArray, bool]:
    """Grid-cell area, falling back to cos(latitude) weights if fx is unusable.

    Returns the weights and whether the fallback was used. The fallback is
    proportional, not in m2, which is fine for means but not for sums.
    """
    if area is not None:
        return area, False
    latname = next((n for n in ("lat", "latitude", "j") if n in like.dims), None)
    if latname is None:
        raise ValueError("no latitude dimension to build fallback weights from")
    warnings.warn(f"falling back to cos-latitude weights: {source}", stacklevel=2)
    print(f"  WARNING: cos-latitude weights used (no usable areacella): {source}")
    return np.cos(np.deg2rad(like[latname])), True


def annual_global_mean(
    da: xr.DataArray, area: xr.DataArray | None = None, source: str = ""
) -> tuple[pd.Series, bool]:
    """Area-weighted global mean, then a calendar-weighted annual mean."""
    weights, fell_back = cell_area(area, da, source)
    spatial = [d for d in da.dims if d != "time"]
    gm = da.weighted(weights.fillna(0)).mean(dim=spatial)
    mw = _month_weights(gm)
    annual = (gm * mw).groupby(_year(gm)).sum() / mw.groupby(_year(mw)).sum()
    return annual.to_series(), fell_back


def annual_land_sum(
    da: xr.DataArray, area: xr.DataArray, sftlf: xr.DataArray, source: str = ""
) -> tuple[pd.Series, bool]:
    """Integrate a land flux in kg m-2 s-1 over land, giving PgC yr-1.

    Each month contributes flux x area x land fraction x seconds in that month,
    so the annual total respects the model calendar.
    """
    land_area = area * (sftlf / 100.0)
    spatial = [d for d in da.dims if d != "time"]
    per_second = (da * land_area).sum(dim=spatial)  # kg s-1
    seconds = _month_weights(per_second) * SECONDS_PER_DAY
    annual = (per_second * seconds).groupby(_year(per_second)).sum() / KG_PER_PG
    return annual.to_series(), False


def to_ppm(series: pd.Series, units: str | None) -> tuple[pd.Series, str]:
    """Convert a CO2 mole fraction to ppm, going by the file's units attribute."""
    u = (units or "").strip().lower()
    if u in ("mol mol-1", "mole mole-1", "1", ""):
        return series * 1e6, "ppm"
    if u in ("ppm", "umol mol-1", "ppmv"):
        return series, "ppm"
    try:
        # CMIP7 writes the scale factor itself, e.g. "1E-06" for ppm
        return series * float(u) * 1e6, "ppm"
    except ValueError:
        raise ValueError(f"unexpected CO2 units: {units!r}") from None


def reduce_item(
    item,
    paths: list[Path],
    kind: str,
    area: xr.DataArray | None = None,
    sftlf: xr.DataArray | None = None,
    source: str = "esgf",
) -> pd.DataFrame:
    """Reduce one STAC item to the project's long CSV schema.

    ``kind`` is ``"mean"`` (intensive), ``"land_sum"`` (PgC yr-1) or ``"co2"``
    (intensive, converted to ppm).
    """
    from .experiments import driving, family

    ds = open_files(paths)
    da = ds[item.variable_id]
    units = da.attrs.get("units", item.units)

    if kind == "land_sum":
        if area is None or sftlf is None:
            raise ValueError("land_sum needs areacella and sftlf")
        values, fell_back = annual_land_sum(da, area, sftlf, source=item.id)
        units = "PgC yr-1"
    else:
        values, fell_back = annual_global_mean(da, area, source=item.id)
        if kind == "co2":
            values, units = to_ppm(values, units)

    df = pd.DataFrame(
        {
            "source_id": item.source_id,
            "experiment_id": item.experiment_id,
            "variant_label": item.variant_label,
            "grid_label": item.grid_label,
            "variable_id": item.variable_id,
            "year": values.index.astype(int),
            "value": values.to_numpy(),
            "units": units,
            "family": family(item.experiment_id),
            "driving": driving(item.experiment_id),
            "source": source,
        }
    )
    df.attrs["cos_latitude_fallback"] = fell_back
    ds.close()
    return df


def load_fx(paths_by_var: dict[str, list[Path]]) -> dict[str, xr.DataArray]:
    """Load areacella / sftlf as DataArrays, tolerating an unreadable file."""
    out = {}
    for var, paths in paths_by_var.items():
        try:
            out[var] = open_files(paths)[var].load()
        except Exception as exc:  # pragma: no cover - depends on the archive
            print(f"  WARNING: could not read {var}: {exc}")
            out[var] = None
    return out


SCHEMA = [
    "source_id", "experiment_id", "variant_label", "grid_label", "variable_id",
    "year", "value", "units", "family", "driving", "source",
]


def write_csv(df: pd.DataFrame, path: Path, extra: list[str] = ()) -> None:
    """Write the long schema, in a stable column order and row order."""
    cols = SCHEMA + [c for c in extra if c in df.columns]
    path.parent.mkdir(parents=True, exist_ok=True)
    out = df[cols].sort_values(["variable_id", "experiment_id", "variant_label", "year"])
    out.to_csv(path, index=False, float_format="%.6g")
    print(f"Wrote {path} ({len(out)} rows)")


def parent_branch_year(paths: list[Path]) -> float | None:
    """Control-run year that a child run branched from, from its file attributes.

    ``branch_time_in_parent`` is in ``parent_time_units`` (days since a date) on
    the model calendar, so for UKESM's 360-day calendar 54000 days is 150 years.
    Returns ``None`` when the attributes are missing.
    """
    ds = xr.open_dataset(sorted(str(p) for p in paths)[0], decode_times=False)
    attrs, calendar = ds.attrs, ds["time"].attrs.get("calendar", "standard")
    ds.close()
    branch, units = attrs.get("branch_time_in_parent"), attrs.get("parent_time_units", "")
    if branch is None or "since" not in units:
        return None
    base_year = int(units.split("since")[1].strip()[:4])
    days_per_year = 360.0 if calendar == "360_day" else 365.25
    return base_year + float(branch) / days_per_year
