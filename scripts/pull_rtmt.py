"""Net TOA radiative flux (rtmt) for UKESM1-3-LL, with control drift removed.

Each historical member is corrected against the segment of esm-piControl it
actually branched from: `branch_time_in_parent` puts esm-hist 1850 at control
year 2000 on UKESM's 360-day calendar, so the parallel control window is
2000-2171. Both raw and corrected values are kept.

    uv run scripts/pull_rtmt.py
"""

import argparse
from pathlib import Path

import pandas as pd

from cmip7ref import targets
from cmip7ref.checks import fallbacks, mean_over, members, sanity_panel, year_ranges
from cmip7ref.reduce import load_fx, parent_branch_year, reduce_item, write_csv
from cmip7ref.stac import StacClient

CONTROL = "esm-piControl"


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("data/ukesm_rtmt.csv"))
    args = p.parse_args()

    target = targets.RTMT
    with StacClient() as stac:
        items = targets.find(stac, target)
        paths = stac.download_all(items)
        fx = load_fx({v: [q for i in fs for q in stac.download(i, verbose=False)]
                      for v, fs in targets.find_fx(stac).items()})

    frames = [reduce_item(i, paths[i.id], kind="mean", area=fx.get("areacella")) for i in items]
    df = pd.concat(frames, ignore_index=True)

    control = df[df["experiment_id"] == CONTROL].set_index("year")["value"]
    print(f"\nControl: {CONTROL} covers {control.index.min()}-{control.index.max()}, "
          f"full-length mean {control.mean():+.3f} W m-2")

    # Correct each historical member against its own parallel control window.
    df["control_mean"] = float("nan")
    for item in items:
        if item.experiment_id == CONTROL:
            continue
        rows = (df["experiment_id"] == item.experiment_id) & (df["variant_label"] == item.variant_label)
        years = df.loc[rows, "year"]
        branch = parent_branch_year(paths[item.id])
        if branch is None:
            drift = control.mean()
            window = "full control (no branch metadata)"
        else:
            offset = branch - years.min()
            lo, hi = years.min() + offset, years.max() + offset
            segment = control[(control.index >= lo) & (control.index <= hi)]
            drift = segment.mean() if len(segment) else control.mean()
            window = f"control {lo:.0f}-{hi:.0f} ({len(segment)} yr)"
        df.loc[rows, "control_mean"] = drift
        print(f"  {item.experiment_id} {item.variant_label}: drift {drift:+.3f} W m-2 from {window}")

    df["value_corrected"] = df["value"] - df["control_mean"]
    write_csv(df, args.out, extra=["control_mean", "value_corrected"])

    members(df, targets.expected(target))
    year_ranges(df)
    fallbacks(frames)

    print("\nrtmt 2005-2014 mean (W m-2), raw and drift-corrected:")
    raw = mean_over(df, 2005, 2014, "esm-hist")
    hist = df[df["experiment_id"] == "esm-hist"]
    corrected = hist[hist["year"].between(2005, 2014)].groupby("variant_label")["value_corrected"].mean()
    for member in raw.index:
        print(f"  esm-hist {member:10s} raw {raw[member]:+.3f}   corrected {corrected[member]:+.3f}")

    sanity_panel(df, "rtmt", "rtmt (W m-2)", f"{targets.MODEL} annual global-mean net TOA flux")


if __name__ == "__main__":
    main()
