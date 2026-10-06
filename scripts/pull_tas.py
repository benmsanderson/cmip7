"""Global-mean tas for UKESM1-3-LL, from the REF (no download).

    uv run scripts/pull_tas.py
"""

import argparse
from pathlib import Path

from cmip7ref import RefClient, anomalies, fetch_global_mean
from cmip7ref.checks import sanity_panel, year_ranges
from cmip7ref.reduce import write_csv
from cmip7ref.targets import MODEL


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--baseline", nargs=2, type=int, default=[1850, 1900], metavar=("START", "END"))
    p.add_argument("--out", type=Path, default=Path("data/ukesm_tas.csv"))
    args = p.parse_args()

    with RefClient() as client:
        df = fetch_global_mean(client, variable_id="tas", mip_era="CMIP7", source_id=MODEL)
    df["source"] = "ref"

    df = anomalies(df, baseline=tuple(args.baseline))
    write_csv(df, args.out, extra=["anomaly", "baseline", "baseline_member"])

    print("\nBaseline member matching (realisation index only):")
    for row in df[["experiment_id", "variant_label", "baseline_member"]].drop_duplicates().itertuples(index=False):
        print(f"  {row.experiment_id:15s} {row.variant_label:10s} <- {row.baseline_member}")
    year_ranges(df)
    sanity_panel(df, "tas", "global mean tas (degC)", f"{MODEL} annual global-mean tas (REF)")


if __name__ == "__main__":
    main()
