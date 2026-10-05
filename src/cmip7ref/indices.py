"""Regional SST indices, principally Nino3.4.

Extracting a box mean is fiddly across CMIP because grids and coordinate names
vary: ocean output is often on a curvilinear grid with 2-D ``latitude`` and
``longitude`` coordinates over ``(j, i)``, while regridded output has 1-D
``lat``/``lon``, and longitude runs either 0-360 or -180-180.
"""

from __future__ import annotations

import numpy as np
import xarray as xr

# Nino3.4: 5S-5N, 170W-120W (190-240 degrees east).
NINO34 = {"lat": (-5.0, 5.0), "lon": (190.0, 240.0)}

LAT_NAMES = ("lat", "latitude", "nav_lat")
LON_NAMES = ("lon", "longitude", "nav_lon")


def _coord(ds: xr.Dataset, names: tuple[str, ...]) -> xr.DataArray | None:
    for name in names:
        if name in ds.coords or name in ds.variables:
            return ds[name]
    return None


def box_mean(
    da: xr.DataArray,
    ds: xr.Dataset,
    box: dict = NINO34,
    weights: xr.DataArray | None = None,
) -> xr.DataArray:
    """Area-weighted mean of ``da`` over a lat/lon box.

    Works for 1-D and 2-D coordinates alike by masking rather than slicing, so
    curvilinear ocean grids need no special casing. Weights default to
    cos(latitude), which is adequate for a 10-degree-tall equatorial box.
    """
    lat, lon = _coord(ds, LAT_NAMES), _coord(ds, LON_NAMES)
    if lat is None or lon is None:
        raise ValueError(f"no latitude/longitude coordinates on {list(ds.coords)}")

    lat0, lat1 = box["lat"]
    lon0, lon1 = box["lon"]
    lon360 = lon % 360  # both conventions collapse onto 0-360
    mask = (lat >= lat0) & (lat <= lat1) & (lon360 >= lon0) & (lon360 <= lon1)
    if not bool(mask.any()):
        raise ValueError("the box selects no cells")

    if weights is None:
        weights = np.cos(np.deg2rad(lat))
    spatial = [d for d in da.dims if d != "time"]
    return da.where(mask).weighted(weights.fillna(0)).mean(dim=spatial)


def monthly_frame(series: xr.DataArray) -> "object":
    """Flatten a monthly index to year/month columns."""
    import pandas as pd

    time = series["time"]
    return pd.DataFrame(
        {
            "year": time.dt.year.to_numpy().astype(int),
            "month": time.dt.month.to_numpy().astype(int),
            "value": series.to_numpy(),
        }
    )


def anomalies_fixed(df, baseline: tuple[int, int] = (1991, 2020), column: str = "value"):
    """Anomalies against a fixed monthly climatology.

    This keeps the warming trend in the anomaly, so a recent observed value is
    measured against a past climate.
    """
    base = df[df.year.between(*baseline)].groupby("month")[column].mean()
    return df[column] - df["month"].map(base)


def anomalies_running(df, window_years: int = 30, column: str = "value"):
    """Anomalies against a centred running climatology, as CPC's ONI is defined.

    CPC updates the Nino3.4 base period every five years precisely so the index
    tracks ENSO rather than the background warming; a running climatology is the
    continuous version of that, and is what makes model and observed anomalies
    comparable in a warming climate.
    """
    out = df.copy().sort_values(["month", "year"])
    clim = (
        out.groupby("month")[column]
        .transform(lambda s: s.rolling(window_years, center=True, min_periods=max(10, window_years // 3)).mean())
    )
    return (out[column] - clim).reindex(df.index)


def window_complete(df, window_years: int = 30, column: str = "value"):
    """Whether a full centred climatology window was available for each row.

    At the start and end of a record the window is truncated, so the climatology
    is one-sided and some of the trend survives into the anomaly: for observed
    Nino3.4 this biases the most recent years low by 0.1-0.2 degC against CPC's
    ONI. Values flagged ``False`` are usable but not strictly comparable with
    interior ones.
    """
    out = df.copy().sort_values(["month", "year"])
    counts = out.groupby("month")[column].transform(
        lambda s: s.rolling(window_years, center=True, min_periods=1).count()
    )
    return (counts >= window_years).reindex(df.index)


def running_mean_3(df, column: str = "anomaly"):
    """Three-month running mean, the ONI's smoothing."""
    out = df.sort_values(["year", "month"])
    return out[column].rolling(3, center=True, min_periods=3).mean().reindex(df.index)
