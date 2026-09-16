"""Land carbon flux (nbp) for UKESM1-3-LL, as annual global PgC yr-1.

Area-weighted sum over the land fraction, using areacella x sftlf/100 and
seconds per month on the model's 360-day calendar.

    uv run scripts/pull_nbp.py
"""

import argparse
from pathlib import Path

import pandas as pd

from cmip7ref import targets
from cmip7ref.checks import GCB_LAND_SINK_PGC, fallbacks, mean_over, members, sanity_panel, year_ranges
from cmip7ref.reduce import load_fx, reduce_item, write_csv
from cmip7ref.stac import StacClient


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("data/ukesm_nbp.csv"))
    args = p.parse_args()

    target = targets.NBP
    with StacClient() as stac:
        items = targets.find(stac, target)
        paths = stac.download_all(items)
        fx = load_fx({v: [q for i in fs for q in stac.download(i, verbose=False)]
                      for v, fs in targets.find_fx(stac).items()})

    frames = [
        reduce_item(i, paths[i.id], kind="land_sum", area=fx.get("areacella"), sftlf=fx.get("sftlf"))
        for i in items
    ]
    df = pd.concat(frames, ignore_index=True)
    write_csv(df, args.out)

    members(df, targets.expected(target))
    year_ranges(df)
    fallbacks(frames)

    print(f"\nLand sink 2010-2019 mean vs GCB 2025 ({GCB_LAND_SINK_PGC} PgC yr-1, 2015-2024):")
    for member, value in mean_over(df, 2010, 2019, "esm-hist").items():
        print(f"  esm-hist {member:10s} {value:6.2f} PgC yr-1   diff {value - GCB_LAND_SINK_PGC:+5.2f}")

    print("\nLand sink 2081-2100 mean by scenario:")
    for experiment in targets.SCENARIOS:
        for member, value in mean_over(df, 2081, 2100, experiment).items():
            print(f"  {experiment:13s} {member:10s} {value:6.2f} PgC yr-1")

    sanity_panel(df, "nbp", "nbp (PgC yr-1)", f"{targets.MODEL} annual global land carbon flux")


if __name__ == "__main__":
    main()
