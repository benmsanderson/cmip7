"""Observed Nino3.4 and tropical-mean SST from gridded ERSSTv5.

CPC publish the ONI and the RONI, but not the tropical-mean series the RONI
subtracts, so the observations are reduced from the gridded field the same way
the models are. The published indices are fetched alongside, as a check.

    uv run scripts/pull_obs_sst.py
"""

import argparse
from pathlib import Path

from cmip7ref.observations import ersst_regions, oni, roni


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("data/obs_sst_regions.csv"))
    p.add_argument("--indices-out", type=Path, default=Path("data/obs_enso_indices.csv"))
    p.add_argument("--version", default="v6", choices=["v5", "v6"],
                   help="ERSST vintage; v6 matches CPC's current RONI page")
    p.add_argument("--refresh", action="store_true", help="refetch ERSST and the CPC tables")
    args = p.parse_args()

    regions = ersst_regions(version=args.version, refresh=args.refresh)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    regions.to_csv(args.out, index=False, float_format="%.4f")
    print(f"Wrote {args.out} ({len(regions)} rows)")
    for name, g in regions.groupby("region"):
        print(f"  {name:8s} {g.year.min()}-{g.year.max()}  mean {g.value.mean():.2f} degC")

    published = oni(refresh=args.refresh)[["year", "month", "season", "sst", "anomaly"]]
    published = published.rename(columns={"sst": "nino34_sst_3mon", "anomaly": "cpc_oni"})
    for version in ("v5", "v6"):
        r = roni(version, refresh=args.refresh).rename(columns={"roni": f"cpc_roni_{version}"})
        published = published.merge(r[["year", "month", f"cpc_roni_{version}"]], on=["year", "month"], how="outer")
    published = published.sort_values(["year", "month"])
    published.to_csv(args.indices_out, index=False, float_format="%.4f")
    print(f"Wrote {args.indices_out} ({len(published)} seasons, {published.year.min()}-{published.year.max()})")

    latest = published.dropna(subset=["cpc_roni_v6"]).iloc[-1]
    print(f"\nLatest published: {latest.season} {int(latest.year)}  "
          f"ONI {latest.cpc_oni:+.2f}   RONI(v6) {latest.cpc_roni_v6:+.2f}")


if __name__ == "__main__":
    main()
