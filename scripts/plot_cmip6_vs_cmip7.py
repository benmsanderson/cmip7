"""Compare a CMIP6 model's SSPs with a CMIP7 model's ScenarioMIP runs.

By default: UKESM1-0-LL (CMIP6, emissions-driven esm-hist plus SSP5-8.5) beside
UKESM1-3-LL (CMIP7, esm-hist plus VL and H).

The cleanest comparison would put CMIP6 esm-hist + esm-ssp585 against CMIP7
esm-hist + esm-scen7-h, since both would then be emissions-driven throughout.
The REF has not ingested esm-ssp585 (0 datasets as of 2026-09-16), so the CMIP6
scenario here is the concentration-driven ssp585. Pass
``--cmip6-historical historical`` to make the CMIP6 panel concentration-driven
throughout instead.

    uv run scripts/plot_cmip6_vs_cmip7.py
"""

import argparse
from pathlib import Path

import pandas as pd

from cmip7ref import RefClient, anomalies, fetch_global_mean
from cmip7ref.plotting import plot_trajectories


def select(df: pd.DataFrame, scenarios: list[str], historical_exp: str) -> pd.DataFrame:
    """Keep the requested scenarios plus one specific historical experiment_id."""
    return df[df["family"].isin(scenarios) | (df["experiment_id"] == historical_exp)]


def driving_note(df: pd.DataFrame) -> str:
    """Flag panels whose historical and scenario runs differ in driving mode."""
    mixed = []
    for model, g in df.groupby("source_id"):
        modes = g.groupby(g["family"].eq("historical").map({True: "hist", False: "scen"}))["driving"].agg(set)
        if len(modes.get("hist", set()) | modes.get("scen", set())) > 1:
            mixed.append(model)
    if not mixed:
        return "All runs shown are emissions-driven."
    return (
        f"{', '.join(mixed)}: historical is emissions-driven but the scenario is concentration-driven "
        "(esm-ssp585 is not held by the REF)."
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--cmip6-model", default="UKESM1-0-LL")
    p.add_argument("--cmip7-model", default="UKESM1-3-LL")
    p.add_argument("--cmip6-scenarios", nargs="+", default=["ssp585"])
    p.add_argument("--cmip6-historical", default="esm-hist", choices=["esm-hist", "historical"])
    p.add_argument("--cmip7-historical", default="esm-hist", choices=["esm-hist", "historical"])
    p.add_argument("--cmip7-scenarios", nargs="+", default=["h"])
    p.add_argument("--baseline", nargs=2, type=int, default=[1850, 1900], metavar=("START", "END"))
    p.add_argument("--out", type=Path, default=Path("figures/cmip6_vs_cmip7_gmt.png"))
    p.add_argument("--csv", type=Path, default=Path("figures/cmip6_vs_cmip7_gmt.csv"))
    args = p.parse_args()

    with RefClient() as client:
        six = fetch_global_mean(client, mip_era="CMIP6", source_id=args.cmip6_model)
        seven = fetch_global_mean(client, mip_era="CMIP7", source_id=args.cmip7_model)

    six = select(six, args.cmip6_scenarios, args.cmip6_historical)
    seven = select(seven, args.cmip7_scenarios, args.cmip7_historical)
    df = anomalies(pd.concat([six, seven], ignore_index=True), baseline=tuple(args.baseline))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.csv, index=False)

    y0, y1 = args.baseline
    fig = plot_trajectories(
        df,
        families=["historical", *args.cmip6_scenarios, *args.cmip7_scenarios],
        models=[args.cmip6_model, args.cmip7_model],
        titles={args.cmip6_model: f"{args.cmip6_model}  ·  CMIP6", args.cmip7_model: f"{args.cmip7_model}  ·  CMIP7"},
        ylabel=f"Global mean surface air temperature\nchange from {y0}–{y1} (°C)",
        title="CMIP6 SSPs vs CMIP7 ScenarioMIP, UKESM family (Climate REF)",
    )
    fig.text(0.02, -0.01, driving_note(df), fontsize=8, color="#52514e", va="top")
    fig.savefig(args.out, dpi=200, bbox_inches="tight")
    print(f"Wrote {args.out} and {args.csv}")
    print(
        df.groupby(["source_id", "family"])
        .apply(lambda g: g[g.year.between(2081, 2100)]["anomaly"].mean(), include_groups=False)
        .round(2)
        .to_string()
    )


if __name__ == "__main__":
    main()
