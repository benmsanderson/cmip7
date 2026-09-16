import pytest

from cmip7ref import anomalies, latest_only, models_with, series_to_frame
from cmip7ref.experiments import driving, family


def _series(exp, variant, years, values, group=1, execution=1, model="M1"):
    return {
        "dimensions": {
            "source_id": model,
            "experiment_id": exp,
            "variable_id": "tas",
            "grid_label": "g1",
            "variant_label": variant,
            "region": "global",
            "statistic": "annual mean",
            "mip_era": "CMIP7",
        },
        "values": values,
        "index": [f"{y}-07-01T00:00:00" for y in years],
        "execution_group_id": group,
        "execution_id": execution,
        "value_units": "degrees_C",
    }


@pytest.mark.parametrize(
    "exp, fam",
    [
        ("historical", "historical"),
        ("esm-hist", "historical"),
        ("scen7-vl", "vl"),
        ("esm-scen7-h", "h"),
        ("esm-piControl", "piControl"),
        ("1pctCO2", None),
    ],
)
def test_family(exp, fam):
    assert family(exp) == fam


def test_driving():
    assert driving("esm-scen7-h") == "emissions"
    assert driving("scen7-h") == "concentration"


def test_latest_only_drops_stale_executions():
    old = _series("esm-hist", "r1", [1850], [1.0], group=7, execution=10)
    new = _series("esm-hist", "r1", [1850], [2.0], group=7, execution=20)
    other = _series("esm-hist", "r2", [1850], [3.0], group=8, execution=11)
    assert latest_only([old, new, other]) == [new, other]


def test_series_to_frame_parses_years_across_calendars():
    s = _series("esm-hist", "r1", [1850, 1851], [1.0, 2.0])
    s["index"] = ["1850-07-02T12:00:00", "1851-07-01T00:00:00"]
    df = series_to_frame([s])
    assert df["year"].tolist() == [1850, 1851]
    assert df["family"].unique().tolist() == ["historical"]


def test_models_with_requires_every_family():
    df = series_to_frame(
        [
            _series("esm-hist", "r1", [1850], [0.0], model="A"),
            _series("esm-scen7-vl", "r1", [2022], [0.0], model="A"),
            _series("esm-scen7-h", "r1", [2022], [0.0], model="A"),
            _series("historical", "r1", [1850], [0.0], model="B"),
            _series("scen7-vl", "r1", [2022], [0.0], model="B"),
        ]
    )
    assert models_with(df, ["historical", "vl", "h"]) == ["A"]


def test_anomalies_use_matching_member_then_model_mean():
    df = series_to_frame(
        [
            _series("esm-hist", "r1", [1850, 1851], [10.0, 12.0]),  # baseline 11
            _series("esm-hist", "r2", [1850, 1851], [13.0, 13.0]),  # baseline 13
            _series("esm-scen7-h", "r1", [2022], [15.0]),  # matches r1
            _series("esm-scen7-h", "r9", [2022], [15.0]),  # no match: model mean 12
        ]
    )
    out = anomalies(df, baseline=(1850, 1851)).set_index(["experiment_id", "variant_label", "year"])
    assert out.loc[("esm-scen7-h", "r1", 2022), "anomaly"] == pytest.approx(4.0)
    assert out.loc[("esm-scen7-h", "r9", 2022), "anomaly"] == pytest.approx(3.0)
    assert out.loc[("esm-hist", "r2", 1850), "anomaly"] == pytest.approx(0.0)
