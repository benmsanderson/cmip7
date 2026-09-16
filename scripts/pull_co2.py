"""Near-surface CO2 mole fraction for UKESM1-3-LL, reduced to annual global ppm.

`co2mass` does not exist in CMIP7, so this branded near-surface field
(`co2_tavg-h2m-hxy-u`) is the proxy for the atmospheric burden. It is published
for esm-hist r4/r5/r7/r8 and for the r5 scenario chain only.

    uv run scripts/pull_co2.py
"""

import argparse
from pathlib import Path

import pandas as pd

from cmip7ref import forcing, targets
from cmip7ref.checks import fallbacks, members, sanity_panel, value_at, year_ranges
from cmip7ref.reduce import load_fx, reduce_item, write_csv
from cmip7ref.stac import StacClient


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--out", type=Path, default=Path("data/ukesm_co2.csv"))
    args = p.parse_args()

    target = targets.CO2
    with StacClient() as stac:
        items = targets.find(stac, target)
        paths = stac.download_all(items)
        fx = load_fx({v: [q for i in fs for q in stac.download(i, verbose=False)]
                      for v, fs in targets.find_fx(stac).items()})

    frames = [reduce_item(i, paths[i.id], kind="co2", area=fx.get("areacella")) for i in items]
    df = pd.concat(frames, ignore_index=True)
    write_csv(df, args.out)

    members(df, targets.expected(target))
    year_ranges(df)
    fallbacks(frames)

    print("\nCO2 in the last historical year (2021) vs the prescribed CMIP7 historical pathway:")
    prescribed = forcing.concentration("historical").set_index("year")["value"]
    modelled = value_at(df, 2021, "esm-hist")
    for member, ppm in modelled.items():
        print(f"  {member:10s} {ppm:7.2f} ppm   prescribed {prescribed.get(2021, float('nan')):7.2f} ppm"
              f"   diff {ppm - prescribed.get(2021, float('nan')):+6.2f}")

    print("\nCO2 in 2100 vs the prescribed scenario pathways:")
    for scenario, experiment in (("h", "esm-scen7-h"), ("vl", "esm-scen7-vl")):
        target_ppm = forcing.concentration(scenario).set_index("year")["value"].get(2100, float("nan"))
        for member, ppm in value_at(df, 2100, experiment).items():
            print(f"  {experiment:13s} {member:10s} {ppm:7.2f} ppm   prescribed {target_ppm:7.2f} ppm"
                  f"   diff {ppm - target_ppm:+6.2f}")

    sanity_panel(df, "co2", "near-surface CO2 (ppm)", f"{targets.MODEL} annual global-mean near-surface CO2")


if __name__ == "__main__":
    main()
