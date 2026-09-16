"""Turn REF series values into tidy pandas DataFrames."""

from __future__ import annotations

from collections.abc import Iterable

import pandas as pd

from .client import RefClient
from .experiments import driving, family

GMT_DIAGNOSTIC = ("esmvaltool", "global-mean-timeseries")

MEMBER_KEYS = ["source_id", "experiment_id", "variant_label", "grid_label", "variable_id"]


def latest_only(series: Iterable[dict]) -> list[dict]:
    """Keep only the series from the newest execution of each execution group.

    The API returns values from every execution of a group, so re-runs show up
    as duplicates. Execution ids go up over time, so the highest one is the
    latest.
    """
    newest: dict[tuple, int] = {}
    for s in series:
        key = (s["execution_group_id"], *sorted(s["dimensions"].items()))
        newest[key] = max(newest.get(key, -1), s["execution_id"])
    return [
        s for s in series
        if s["execution_id"] == newest[(s["execution_group_id"], *sorted(s["dimensions"].items()))]
    ]


def series_to_frame(series: Iterable[dict]) -> pd.DataFrame:
    """Flatten series records into a long frame: one row per time step.

    Time is reduced to an integer ``year``. The series use a mix of
    calendars (360_day, proleptic_gregorian), and for annual means the year
    is all we need.
    """
    frames = []
    for s in series:
        d = dict(s["dimensions"])
        # CMIP6 names the ensemble member `member_id`; CMIP7 renamed it `variant_label`.
        d.setdefault("variant_label", d.get("member_id"))
        frames.append(
            pd.DataFrame(
                {
                    **{k: d.get(k) for k in MEMBER_KEYS},
                    "mip_era": d.get("mip_era"),
                    "region": d.get("region"),
                    "statistic": d.get("statistic"),
                    "year": [int(str(t)[:4]) for t in s["index"]],
                    "value": s["values"],
                    "units": s.get("value_units"),
                    "execution_id": s["execution_id"],
                }
            )
        )
    if not frames:
        return pd.DataFrame(columns=[*MEMBER_KEYS, "region", "statistic", "year", "value", "units", "execution_id"])
    df = pd.concat(frames, ignore_index=True)
    df["family"] = df["experiment_id"].map(family)
    df["driving"] = df["experiment_id"].map(driving)
    return df


def fetch_global_mean(client: RefClient, variable_id: str = "tas", mip_era: str = "CMIP7", **dimensions: str) -> pd.DataFrame:
    """Annual global-mean series from ESMValTool's global-mean-timeseries diagnostic."""
    raw = client.metric_values(
        *GMT_DIAGNOSTIC,
        value_type="series",
        mip_era=mip_era,
        variable_id=variable_id,
        **dimensions,
    )
    return series_to_frame(latest_only(raw))


def models_with(df: pd.DataFrame, families: Iterable[str]) -> list[str]:
    """Models that have at least one member in every one of ``families``."""
    need = set(families)
    have = df.groupby("source_id")["family"].agg(lambda f: set(f.dropna()))
    return sorted(m for m, fams in have.items() if need <= fams)


def anomalies(df: pd.DataFrame, baseline: tuple[int, int] = (1850, 1900)) -> pd.DataFrame:
    """Add an ``anomaly`` column relative to each model's historical baseline.

    Each scenario member is referenced to the historical member with the same
    variant_label, since that is the run it branches from. If there is no
    matching historical member, the model's historical ensemble-mean baseline is
    used instead.
    """
    y0, y1 = baseline
    hist = df[(df["family"] == "historical") & df["year"].between(y0, y1)]
    by_member = hist.groupby(["source_id", "variant_label"])["value"].mean()
    by_model = by_member.groupby("source_id").mean()

    def base(row: pd.Series) -> float:
        return by_member.get((row.source_id, row.variant_label), by_model.get(row.source_id, float("nan")))

    keys = df[["source_id", "variant_label"]].drop_duplicates()
    keys["baseline"] = [base(r) for r in keys.itertuples()]
    out = df.merge(keys, on=["source_id", "variant_label"], how="left")
    out["anomaly"] = out["value"] - out["baseline"]
    return out
