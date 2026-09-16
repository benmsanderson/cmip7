"""Turn REF series values into tidy pandas DataFrames."""

from __future__ import annotations

import re
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
        empty = [*MEMBER_KEYS, "mip_era", "region", "statistic", "year", "value", "units", "execution_id"]
        return pd.DataFrame(columns=empty)
    df = pd.concat(frames, ignore_index=True)
    df["family"] = df["experiment_id"].map(family)
    df["driving"] = df["experiment_id"].map(driving)
    return df


def fetch_global_mean(
    client: RefClient, variable_id: str = "tas", mip_era: str = "CMIP7", **dimensions: str
) -> pd.DataFrame:
    """Annual global-mean series from ESMValTool's global-mean-timeseries diagnostic.

    Works for ``mip_era="CMIP6"`` too; there the member dimension is called
    ``member_id`` and is mapped onto ``variant_label``.
    """
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


def realisation(variant_label: str) -> str | None:
    """The ``r<n>`` part of a variant label.

    Historical and scenario members of the same realisation can differ in their
    i/p/f indices (``esm-hist r7i1p1f2`` continues as ``r7i1p1f1``), so the
    realisation index is what identifies a continuing run.
    """
    m = re.match(r"^(r\d+)", str(variant_label))
    return m[1] if m else None


def anomalies(df: pd.DataFrame, baseline: tuple[int, int] = (1850, 1900)) -> pd.DataFrame:
    """Add ``anomaly`` and ``baseline_member`` columns, relative to historical.

    Each member is referenced to the historical member with the same realisation
    index (ignoring i/p/f), since that is the run it branches from. Failing that,
    the model's historical ensemble mean is used and ``baseline_member`` records
    ``"ensemble-mean"``.

    Emissions-driven members take emissions-driven (``esm-``) historical
    baselines and concentration-driven members take concentration-driven ones;
    the two are never mixed.
    """
    y0, y1 = baseline
    df = df.copy()
    df["realisation"] = df["variant_label"].map(realisation)

    hist = df[(df["family"] == "historical") & df["year"].between(y0, y1)]
    by_member = hist.groupby(["source_id", "driving", "realisation"]).agg(
        baseline=("value", "mean"), baseline_member=("variant_label", "first")
    )
    by_model = hist.groupby(["source_id", "driving"])["value"].mean()

    keys = df[["source_id", "driving", "realisation"]].drop_duplicates()
    rows = []
    for k in keys.itertuples(index=False):
        key = (k.source_id, k.driving, k.realisation)
        if key in by_member.index:
            base, member = by_member.loc[key, "baseline"], by_member.loc[key, "baseline_member"]
        else:
            base = by_model.get((k.source_id, k.driving), float("nan"))
            member = "ensemble-mean"
        rows.append({**k._asdict(), "baseline": base, "baseline_member": member})

    out = df.merge(pd.DataFrame(rows), on=["source_id", "driving", "realisation"], how="left")
    out["anomaly"] = out["value"] - out["baseline"]
    return out.drop(columns="realisation")
