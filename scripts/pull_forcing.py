"""Prescribed CO2 concentrations and global CO2 emissions for historical, H and VL.

Concentrations come from input4MIPs as ready-made global means (grid_label=gm).
Emissions have no global-total product anywhere on ESGF, so:

* scenarios are area-summed from the harmonised gridded files that were passed to
  the ESMs (~1.3 GB for the two of them);
* the historical series is taken as a global total from the Global Carbon Budget
  compilation, rather than area-summing 2.5 GB of gridded CEDS.

    uv run scripts/pull_forcing.py
    uv run scripts/pull_forcing.py --with-aviation   # +2.8 GB, ~2% of the total
"""

import argparse
from pathlib import Path

import pandas as pd

from cmip7ref import forcing


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--with-aviation", action="store_true", help="also sum CO2_em_AIR_anthro (2.8 GB)")
    p.add_argument("--conc-out", type=Path, default=Path("data/forcing_co2_concentration.csv"))
    p.add_argument("--emis-out", type=Path, default=Path("data/forcing_co2_emissions.csv"))
    args = p.parse_args()

    conc = pd.concat([forcing.concentration(k) for k in ("historical", "h", "vl")], ignore_index=True)
    args.conc_out.parent.mkdir(parents=True, exist_ok=True)
    conc.to_csv(args.conc_out, index=False, float_format="%.6g")
    print(f"Wrote {args.conc_out} ({len(conc)} rows)")

    emis = pd.concat(
        [forcing.emissions_historical()]
        + [forcing.emissions_scenario(k, with_aviation=args.with_aviation) for k in ("h", "vl")],
        ignore_index=True,
    )
    # What the ESM is actually handed: fossil and industrial plus engineered CDR.
    # Land-use CO2 is not prescribed - the model computes it from the land-use
    # forcing, and it comes back out inside nbp.
    emis["passed_to_esm_GtCO2"] = emis["fossil_GtCO2"] + emis["cdr_GtCO2"].fillna(0)
    emis["passed_to_esm_PgC"] = forcing.gtco2_to_pgc(emis["passed_to_esm_GtCO2"])
    emis["total_incl_landuse_GtCO2"] = emis["passed_to_esm_GtCO2"] + emis["landuse_GtCO2"].fillna(0)
    emis.to_csv(args.emis_out, index=False, float_format="%.6g")
    print(f"Wrote {args.emis_out} ({len(emis)} rows)")

    print("\nConcentration (ppm):")
    for key, g in conc.groupby("scenario"):
        print(f"  {key:11s} {g.year.min()}-{g.year.max()}  "
              f"first {g.value.iloc[0]:.2f}  last {g.value.iloc[-1]:.2f}  [{g.source_dataset.iloc[0]}]")

    filled = emis.groupby("scenario")["interpolated"].sum()
    print("\nEmissions (GtCO2 yr-1):")
    for key, g in emis.groupby("scenario"):
        g = g.sort_values("year")
        s = g.set_index("year")
        print(f"  {key:11s} {g.year.min()}-{g.year.max()}  "
              f"2021 {s['passed_to_esm_GtCO2'].get(2021, float('nan')):6.2f}  "
              f"2100 {s['passed_to_esm_GtCO2'].get(2100, float('nan')):6.2f}  "
              f"CDR 2100 {s['cdr_GtCO2'].get(2100, float('nan')):6.2f}  "
              f"({int(filled[key])} of {len(g)} yr interpolated)  [{g.source_dataset.iloc[0]}]")

    hist_2021 = emis[(emis.scenario == "historical") & (emis.year == 2021)]["fossil_GtCO2"]
    scen_2022 = emis[(emis.scenario != "historical") & (emis.year == 2022)].set_index("scenario")["fossil_GtCO2"]
    print("\nHistorical-to-scenario join (the two come from different compilations):")
    for key, value in scen_2022.items():
        print(f"  {key}: 2022 {value:.2f} vs historical 2021 {float(hist_2021.iloc[0]):.2f} GtCO2 "
              f"(step {value - float(hist_2021.iloc[0]):+.2f})")
    if not args.with_aviation:
        print("\nAviation (CO2_em_AIR_anthro) excluded; --with-aviation adds it at a cost of 2.8 GB.")


if __name__ == "__main__":
    main()
