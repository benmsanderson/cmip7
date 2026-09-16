"""Derived carbon-cycle series for UKESM1-3-LL.

Joins the pulled CO2, nbp and forcing CSVs into per-member annual series:
cumulative emissions, atmospheric growth, airborne fraction and the sink terms.

The r5 chain (esm-hist r5 -> esm-scen7-h/-vl r5) is the only member with CO2 in
both the historical and scenario periods; r4/r7/r8 are historical-only.

    uv run scripts/pull_co2.py && uv run scripts/pull_nbp.py && uv run scripts/pull_forcing.py
    uv run scripts/derive.py
"""

import argparse
from pathlib import Path

import pandas as pd

from cmip7ref.checks import sanity_panel
from cmip7ref.forcing import PGC_PER_PPM

SCENARIO_KEY = {"esm-scen7-h": "h", "esm-scen7-vl": "vl", "esm-hist": "historical"}
# Below this the airborne fraction is a ratio of two small numbers; VL emissions
# pass through zero late in the century.
MIN_EMISSIONS_PGC = 1.0


def emissions_for(emis: pd.DataFrame, experiment: str) -> pd.Series:
    """Global CO2 emissions in PgC yr-1 for the experiment's scenario."""
    key = SCENARIO_KEY[experiment]
    g = emis[emis["scenario"] == key].set_index("year")["passed_to_esm_PgC"]
    return g[~g.index.duplicated()]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data"))
    p.add_argument("--out", type=Path, default=Path("data/ukesm_derived.csv"))
    args = p.parse_args()

    co2 = pd.read_csv(args.data / "ukesm_co2.csv")
    nbp = pd.read_csv(args.data / "ukesm_nbp.csv")
    emis = pd.read_csv(args.data / "forcing_co2_emissions.csv")
    conc = pd.read_csv(args.data / "forcing_co2_concentration.csv")

    rows = []
    for (experiment, member), g in co2.groupby(["experiment_id", "variant_label"]):
        g = g.sort_values("year")
        ppm = g.set_index("year")["value"]
        emissions = emissions_for(emis, experiment).reindex(ppm.index)

        # Atmospheric growth from the modelled CO2; first year of a run has no
        # in-run predecessor, so it is left undefined rather than spliced.
        growth = ppm.diff() * PGC_PER_PPM
        land = (
            nbp[(nbp.experiment_id == experiment) & (nbp.variant_label == member)]
            .set_index("year")["value"]
            .reindex(ppm.index)
        )
        total_sink = emissions - growth
        # As emissions approach (or cross) zero the ratio stops being meaningful,
        # so the airborne fraction is only defined for a clearly positive input.
        airborne = (growth / emissions).where(emissions > MIN_EMISSIONS_PGC)
        # The annual ratio is noisy - interannual growth variability is large
        # next to one year of emissions - so the usual decadal-window estimator
        # (summed growth over summed emissions) is provided alongside it.
        window = dict(window=10, center=True, min_periods=10)
        airborne_10yr = growth.rolling(**window).sum() / emissions.rolling(**window).sum()
        airborne_10yr = airborne_10yr.where(emissions.rolling(**window).mean() > MIN_EMISSIONS_PGC)

        out = pd.DataFrame(
            {
                "source_id": g["source_id"].iloc[0],
                "experiment_id": experiment,
                "variant_label": member,
                "year": ppm.index,
                "co2_ppm": ppm.to_numpy(),
                "emissions_PgC": emissions.to_numpy(),
                "atm_growth_PgC": growth.to_numpy(),
                "airborne_fraction": airborne.to_numpy(),
                "airborne_fraction_10yr": airborne_10yr.to_numpy(),
                "sim_total_sink_PgC": total_sink.to_numpy(),
                "sim_land_sink_PgC": land.to_numpy(),
                "sim_ocean_sink_PgC": (total_sink - land).to_numpy(),
            }
        )
        rows.append(out)

    df = pd.concat(rows, ignore_index=True)

    # Cumulative emissions from 1850 follow the scenario pathway, not the member,
    # so they are computed once per scenario and joined on.
    cumulative = []
    hist = emis[emis.scenario == "historical"].set_index("year")["passed_to_esm_GtCO2"]
    hist = hist[(hist.index >= 1850) & (hist.index <= 2021)]
    for key in ("h", "vl"):
        scen = emis[emis.scenario == key].set_index("year")["passed_to_esm_GtCO2"]
        joined = pd.concat([hist, scen[scen.index > 2021]])
        cumulative.append(
            pd.DataFrame(
                {"scenario": key, "year": joined.index, "cumulative_emissions_GtCO2": joined.cumsum().to_numpy()}
            )
        )
    cumulative.append(
        pd.DataFrame(
            {"scenario": "historical", "year": hist.index, "cumulative_emissions_GtCO2": hist.cumsum().to_numpy()}
        )
    )
    cum = pd.concat(cumulative, ignore_index=True)
    df["scenario"] = df["experiment_id"].map(SCENARIO_KEY)
    df = df.merge(cum, on=["scenario", "year"], how="left")

    # Implied sink for the prescribed pathway: harmonised emissions minus the
    # growth of the concentration the concentration-driven runs would have seen.
    implied = []
    for key in ("historical", "h", "vl"):
        c = conc[conc.scenario == key].set_index("year")["value"].sort_index()
        e = emis[emis.scenario == key].set_index("year")["passed_to_esm_PgC"]
        years = c.index.intersection(e.index)
        implied.append(
            pd.DataFrame(
                {
                    "scenario": key,
                    "year": years,
                    "prescribed_co2_ppm": c.loc[years].to_numpy(),
                    "implied_total_sink_PgC": (e.loc[years] - c.diff().loc[years] * PGC_PER_PPM).to_numpy(),
                }
            )
        )
    df = df.merge(pd.concat(implied, ignore_index=True), on=["scenario", "year"], how="left")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, float_format="%.6g")
    print(f"Wrote {args.out} ({len(df)} rows)")

    print("\nDecadal means, esm-hist 2010-2019 (PgC yr-1 unless noted):")
    h = df[(df.experiment_id == "esm-hist") & df.year.between(2010, 2019)]
    for member, g in h.groupby("variant_label"):
        print(f"  {member:10s} growth {g.atm_growth_PgC.mean():5.2f}  land {g.sim_land_sink_PgC.mean():5.2f}  "
              f"ocean {g.sim_ocean_sink_PgC.mean():5.2f}  AF {g.airborne_fraction.mean():4.2f} "
              f"(10yr {g.airborne_fraction_10yr.mean():4.2f})")

    print("\nEnd of century (2100), r5 chain:")
    for experiment in ("esm-scen7-h", "esm-scen7-vl"):
        g = df[(df.experiment_id == experiment) & (df.year == 2100)]
        if g.empty:
            continue
        r = g.iloc[0]
        print(f"  {experiment:13s} CO2 {r.co2_ppm:6.1f} ppm (prescribed {r.prescribed_co2_ppm:6.1f})  "
              f"cumulative {r.cumulative_emissions_GtCO2:7.0f} GtCO2  "
              f"emissions {r.emissions_PgC:5.2f} PgC  AF {r.airborne_fraction:4.2f}")

    ok = df[["emissions_PgC", "atm_growth_PgC", "sim_land_sink_PgC"]].notna().all(axis=1)
    print(f"\nRows with a closed budget (emissions, growth and land all present): {ok.sum()} of {len(df)}")
    if (~ok).any():
        missing = df[~ok].groupby("experiment_id").size()
        print("  incomplete rows by experiment:", missing.to_dict())

    panel = df.rename(columns={"airborne_fraction_10yr": "value"}).assign(
        variable_id="airborne_fraction_10yr", units="1"
    )
    sanity_panel(panel.dropna(subset=["value"]), "airborne_fraction", "airborne fraction (10-year window)",
                 "UKESM1-3-LL airborne fraction, 10-year window")


if __name__ == "__main__":
    main()
