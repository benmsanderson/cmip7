import numpy as np
import pandas as pd
import pytest
import xarray as xr

from cmip7ref.indices import NINO34, anomalies_fixed, anomalies_running, box_mean, running_mean_3


def _regular(lon_convention="0-360"):
    """A regular lat/lon grid where only the Nino3.4 box holds 1.0."""
    lat = np.arange(-30.5, 31, 1.0)
    lon = np.arange(0.5, 360, 1.0) if lon_convention == "0-360" else np.arange(-179.5, 180, 1.0)
    time = xr.date_range("2000-01-01", periods=3, freq="MS", calendar="standard", use_cftime=True)
    data = np.zeros((len(time), len(lat), len(lon)))
    ds = xr.Dataset(coords={"time": time, "lat": ("lat", lat), "lon": ("lon", lon)})
    da = xr.DataArray(data, dims=("time", "lat", "lon"), coords=ds.coords)
    inbox = (da.lat >= -5) & (da.lat <= 5) & ((da.lon % 360) >= 190) & ((da.lon % 360) <= 240)
    return da.where(~inbox, 1.0), ds


@pytest.mark.parametrize("convention", ["0-360", "-180-180"])
def test_box_mean_selects_nino34_in_both_longitude_conventions(convention):
    da, ds = _regular(convention)
    assert box_mean(da, ds, NINO34).isel(time=0).item() == pytest.approx(1.0)


def test_box_mean_handles_curvilinear_coordinates():
    """Ocean grids carry 2-D latitude/longitude over (j, i) and must still work."""
    j, i = 40, 80
    lat2d = np.repeat(np.linspace(-30, 30, j)[:, None], i, axis=1)
    lon2d = np.repeat(np.linspace(0, 359, i)[None, :], j, axis=0)
    time = xr.date_range("2000-01-01", periods=2, freq="MS", calendar="standard", use_cftime=True)
    ds = xr.Dataset(
        coords={"time": time,
                "latitude": (("j", "i"), lat2d),
                "longitude": (("j", "i"), lon2d)}
    )
    da = xr.DataArray(np.zeros((len(time), j, i)), dims=("time", "j", "i"), coords=ds.coords)
    inbox = (ds.latitude >= -5) & (ds.latitude <= 5) & (ds.longitude >= 190) & (ds.longitude <= 240)
    da = da.where(~inbox, 2.0)
    assert box_mean(da, ds, NINO34).isel(time=0).item() == pytest.approx(2.0)


def test_box_mean_rejects_a_grid_with_no_coordinates():
    da = xr.DataArray(np.zeros((2, 3, 4)), dims=("time", "y", "x"))
    with pytest.raises(ValueError, match="no latitude/longitude"):
        box_mean(da, xr.Dataset(), NINO34)


def _monthly(years, values):
    return pd.DataFrame(
        {"year": np.repeat(years, 12), "month": np.tile(np.arange(1, 13), len(years)), "value": values}
    )


def test_anomalies_running_removes_a_trend_that_a_fixed_base_keeps():
    """The point of the running base: warming is removed, ENSO is not."""
    years = np.arange(1950, 2031)
    trend = np.repeat((years - 1950) * 0.02, 12)  # 0.02 degC per year
    df = _monthly(years, 26.0 + trend)

    # In the interior a centred window sits symmetrically on the trend, so it
    # absorbs it completely. Near the ends the window is truncated and some
    # trend survives - which is why edge years need care.
    running = anomalies_running(df, window_years=30)
    interior = running[df.year.between(1970, 2010)]
    assert interior.abs().max() < 0.02
    edge = running[df.year >= 2028]
    assert edge.abs().max() > 0.1

    fixed = anomalies_fixed(df, baseline=(1950, 1979))
    late = fixed[df.year >= 2020]
    assert late.mean() > 1.0  # the same trend survives a fixed base


def test_running_mean_3_smooths_a_single_spike():
    df = _monthly(np.arange(2000, 2003), np.zeros(36))
    df.loc[18, "value"] = 3.0
    df["anomaly"] = df["value"]
    smoothed = running_mean_3(df)
    assert smoothed.iloc[18] == pytest.approx(1.0)
    assert smoothed.iloc[17] == pytest.approx(1.0)
    assert smoothed.iloc[15] == pytest.approx(0.0)
