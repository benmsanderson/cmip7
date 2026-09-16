import numpy as np
import pandas as pd
import pytest
import xarray as xr

from cmip7ref.reduce import annual_global_mean, annual_land_sum, to_ppm
from cmip7ref.stac import StacClient, StacItem
from cmip7ref.timeseries import anomalies, realisation, series_to_frame


def _grid(values_by_month, calendar="360_day"):
    """A tiny 2x2 monthly field; ``values_by_month`` is one value per month."""
    time = xr.date_range("1850-01-01", periods=len(values_by_month), freq="MS", calendar=calendar, use_cftime=True)
    data = np.repeat(np.asarray(values_by_month, float)[:, None, None], 4, axis=1).reshape(-1, 2, 2)
    return xr.DataArray(data, dims=("time", "lat", "lon"),
                        coords={"time": time, "lat": [-45.0, 45.0], "lon": [0.0, 180.0]})


def _area(values=((1.0, 1.0), (3.0, 3.0))):
    return xr.DataArray(np.asarray(values, float), dims=("lat", "lon"),
                        coords={"lat": [-45.0, 45.0], "lon": [0.0, 180.0]})


def test_annual_global_mean_weights_by_area():
    da = _grid([1.0] * 12)
    da[:, 1, :] = 5.0  # northern row
    values, fell_back = annual_global_mean(da, _area())
    # weights 1,1,3,3 -> (1+1+15+15)/8
    assert values.loc[1850] == pytest.approx(4.0)
    assert fell_back is False


def test_annual_mean_uses_month_lengths():
    # A standard calendar weights 31-day months more than February.
    monthly = [0.0] * 12
    monthly[0] = 31.0  # January
    da = _grid(monthly, calendar="standard")
    values, _ = annual_global_mean(da, _area())
    assert values.loc[1850] == pytest.approx(31.0 * 31 / 365)


def test_cos_latitude_fallback_flags_itself():
    da = _grid([1.0] * 12)
    with pytest.warns(UserWarning, match="cos-latitude"):
        _, fell_back = annual_global_mean(da, None, source="somefile.nc")
    assert fell_back is True


def test_annual_land_sum_converts_to_pgc():
    # 1e-9 kg m-2 s-1 over 1e12 m2 of land for a 360-day year.
    flux = _grid([1e-9] * 12)
    area = _area(((1e12, 1e12), (1e12, 1e12)))
    sftlf = _area(((100.0, 100.0), (0.0, 0.0)))  # southern row is land
    values, _ = annual_land_sum(flux, area, sftlf)
    expected = 1e-9 * 2e12 * 360 * 86400 / 1e12
    assert values.loc[1850] == pytest.approx(expected)


@pytest.mark.parametrize(
    "units, factor",
    [("1E-06", 1.0), ("ppm", 1.0), ("mol mol-1", 1e6), ("1", 1e6)],
)
def test_to_ppm_handles_cmip_unit_spellings(units, factor):
    series = pd.Series([4e-4], index=[1850])
    converted, out_units = to_ppm(series, units)
    assert out_units == "ppm"
    assert converted.iloc[0] == pytest.approx(4e-4 * factor)


def test_to_ppm_rejects_nonsense():
    with pytest.raises(ValueError, match="unexpected CO2 units"):
        to_ppm(pd.Series([1.0]), "kg")


def test_realisation_ignores_ipf_indices():
    assert realisation("r7i1p1f2") == "r7"
    assert realisation("r7i1p1f1") == "r7"
    assert realisation("nonsense") is None


def test_anomalies_match_on_realisation_across_f_index():
    def s(exp, variant, years, values):
        return {
            "dimensions": {"source_id": "M", "experiment_id": exp, "variable_id": "tas",
                           "grid_label": "g", "variant_label": variant},
            "values": values,
            "index": [f"{y}-07-01" for y in years],
            "execution_group_id": 1, "execution_id": 1, "value_units": "degrees_C",
        }

    df = series_to_frame([
        s("esm-hist", "r7i1p1f2", [1850, 1851], [10.0, 12.0]),   # baseline 11
        s("esm-scen7-h", "r7i1p1f1", [2022], [15.0]),            # same realisation, different f
    ])
    out = anomalies(df, baseline=(1850, 1851))
    scen = out[out.experiment_id == "esm-scen7-h"].iloc[0]
    assert scen["anomaly"] == pytest.approx(4.0)
    assert scen["baseline_member"] == "r7i1p1f2"


def test_stac_cql2_builds_in_and_eq():
    built = StacClient._cql2({"source_id": "UKESM1-3-LL", "variant_label": ["r5i1p1f1", "r1i1p1f1"]})
    assert built["op"] == "and"
    ops = {arg["op"] for arg in built["args"]}
    assert ops == {"=", "in"}


def test_stac_item_end_year_is_exclusive():
    """An item ending 2022-01-01 holds data through 2021."""
    item = StacItem("id", {"start_datetime": "1850-01-01T00:00:00Z", "end_datetime": "2022-01-01T00:00:00Z"}, {})
    assert item.years == (1850, 2021)
    ongoing = StacItem("id", {"start_datetime": "2022-01-16T00:00:00Z", "end_datetime": "2100-12-16T00:00:00Z"}, {})
    assert ongoing.years == (2022, 2100)


def test_compatible_rejects_mismatched_grids():
    """An atmosphere area must never be paired with an ocean field."""
    from cmip7ref.reduce import compatible

    ocean = xr.DataArray(np.zeros((2, 3, 4)), dims=("time", "y", "x"))
    atmos_area = _area()  # (lat, lon)
    assert compatible(atmos_area, ocean) is False
    assert compatible(None, ocean) is False

    ocean_area = xr.DataArray(np.ones((3, 4)), dims=("y", "x"))
    assert compatible(ocean_area, ocean) is True
    wrong_size = xr.DataArray(np.ones((3, 9)), dims=("y", "x"))
    assert compatible(wrong_size, ocean) is False


def test_land_sum_refuses_mismatched_area():
    from cmip7ref.reduce import annual_land_sum

    flux = _grid([1e-9] * 12)
    bad_area = xr.DataArray(np.ones((3, 4)), dims=("y", "x"))
    with pytest.raises(ValueError, match="do not fit field dims"):
        annual_land_sum(flux, bad_area, _area())
