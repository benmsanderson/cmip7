# Data products

Annual global series behind the Milan talk figures. Every CSV is long format, one
row per year, with the columns

`source_id, experiment_id, variant_label, grid_label, variable_id, year, value, units, family, driving, source`

plus per-product extras noted below. `source` is `ref` (Climate REF API), `esgf`
(downloaded from the ESGF STAC index) or `pangeo` (read lazily from the Pangeo
Zarr mirror). Figures read these by raw GitHub URL, so **column names and file
names are a contract** — add columns rather than renaming them.

Regenerate everything with:

```bash
uv run scripts/pull_tas.py && uv run scripts/pull_co2.py && uv run scripts/pull_nbp.py
uv run scripts/pull_rtmt.py && uv run scripts/pull_forcing.py && uv run scripts/derive.py
uv run scripts/pull_cmip6_esm.py
```

## Files

| File | Contents | Members |
|---|---|---|
| `ukesm_tas.csv` | annual global-mean `tas` (°C), plus `anomaly`, `baseline`, `baseline_member` | every member the REF holds |
| `ukesm_co2.csv` | annual global-mean near-surface CO2 (ppm) | esm-hist r4/r5/r7/r8; scen7-h/vl r5 |
| `ukesm_nbp.csv` | annual global land carbon flux (PgC yr-1) | esm-hist r1/r5/r7/r8; scen7-h/vl r1/r5 |
| `ukesm_rtmt.csv` | annual global net TOA flux (W m-2), plus `control_mean`, `value_corrected` | esm-hist r1/r5/r7/r8; esm-piControl |
| `forcing_co2_concentration.csv` | prescribed global-mean CO2 (ppm) | historical, H, VL |
| `forcing_co2_emissions.csv` | global CO2 emissions (GtCO2 yr-1 and PgC yr-1) | historical, H, VL |
| `ukesm_derived.csv` | cumulative emissions, growth, airborne fraction, sinks | members with CO2 |
| `cmip6_esm_*.csv` | CMIP6 emissions-driven precedent, one member per model | see coverage below |
| `cmip6_nino34.csv` | monthly Niño3.4 SST (°C), historical + ssp245, 1950–2060 | 41 models, one member each |
| `cmip6_nino34_oni.csv` | the same as anomalies and 3-month-mean ONI, with `window_complete` | 41 models |

## Exact sources

CMIP7 model output, from the ESGF STAC API (`https://api.stac.esgf.ceda.ac.uk`,
CQL2 filters, HTTPServer download only — there is no OPeNDAP). All
`UKESM1-3-LL`, `g110`, monthly, DRS instance ids of the form
`MIP-DRS7.CMIP7.<activity>.UKNCSP.UKESM1-3-LL.<experiment>.<variant>.glb.mon.<variable>.<branding>.g110.<version>`:

| variable (branded) | experiment | members | version |
|---|---|---|---|
| `co2_tavg-h2m-hxy-u` | `esm-hist` | r4i1p1f1 | v20260826 |
| `co2_tavg-h2m-hxy-u` | `esm-hist` | r5i1p1f1 | v20260829 |
| `co2_tavg-h2m-hxy-u` | `esm-hist` | r7i1p1f2 | v20260901 |
| `co2_tavg-h2m-hxy-u` | `esm-hist` | r8i1p1f2 | v20260907 |
| `co2_tavg-h2m-hxy-u` | `esm-scen7-h` | r5i1p1f1 | v20260828 |
| `co2_tavg-h2m-hxy-u` | `esm-scen7-vl` | r5i1p1f1 | v20260828 |
| `nbp_tavg-u-hxy-lnd` | `esm-hist` | r1i1p1f1 | v20260814 |
| `nbp_tavg-u-hxy-lnd` | `esm-hist` | r5i1p1f1 | v20260829 |
| `nbp_tavg-u-hxy-lnd` | `esm-hist` | r7i1p1f2 | v20260901 |
| `nbp_tavg-u-hxy-lnd` | `esm-hist` | r8i1p1f2 | v20260907 |
| `nbp_tavg-u-hxy-lnd` | `esm-scen7-h` | r1i1p1f1, r5i1p1f1 | v20260825, v20260828 |
| `nbp_tavg-u-hxy-lnd` | `esm-scen7-vl` | r1i1p1f1, r5i1p1f1 | v20260825, v20260828 |
| `rtmt_tavg-u-hxy-u` | `esm-hist` | r1i1p1f1 | v20260814 |
| `rtmt_tavg-u-hxy-u` | `esm-hist` | r5i1p1f1 | v20260829 |
| `rtmt_tavg-u-hxy-u` | `esm-hist` | r7i1p1f2 | v20260901 |
| `rtmt_tavg-u-hxy-u` | `esm-hist` | r8i1p1f2 | v20260907 |
| `rtmt_tavg-u-hxy-u` | `esm-piControl` | r1i1p1f1 | v20260825 |
| `areacella_ti-u-hxy-u`, `sftlf_ti-u-hxy-u` | `esm-hist` | r5i1p1f1 | v20260829 |

`tas` is not downloaded: it comes from the REF's `esmvaltool/global-mean-timeseries`
diagnostic, filtered to the newest execution of each group.

Forcing inputs, from input4MIPs via the legacy ESGF Solr index:

| series | dataset | version |
|---|---|---|
| historical CO2 concentration | `input4MIPs.CMIP7.CMIP.CR.CR-CMIP-1-0-0.atmos.yr.co2.gm` | v20250228 |
| H CO2 concentration | `input4MIPs.CMIP7.ScenarioMIP.CR.CR-h-1-0-0.atmos.yr.co2.gm` | v20251211 |
| VL CO2 concentration | `input4MIPs.CMIP7.ScenarioMIP.CR.CR-vl-1-0-0.atmos.yr.co2.gm` | v20251211 |
| H CO2 emissions | `input4MIPs.CMIP7.ScenarioMIP.IIASA-IAMC.IIASA-IAMC-h-1-1-0.atmos.mon.CO2_em_anthro.gn` | v20260219 |
| VL CO2 emissions | `IIASA-IAMC-vl-1-1-0` equivalent | v20260219 |
| emissions grid area | `input4MIPs.CMIP7.ScenarioMIP.IIASA-IAMC.IIASA-IAMC-1-1-0.atmos.fx.areacella.gn` | v20260218 |
| historical CO2 emissions | Global Carbon Budget via OWID `owid-co2-data.csv` | fetched 17 Sep 2026 |

## Member policy

`r5i1p1f1` is the only member with the full set of variables continuing from
`esm-hist` into both scenarios, so every CO2-dependent product is **single-member
in the scenario period**. Historical coverage is ragged by design of the archive,
not by choice:

- `esm-hist` r1 has no near-surface CO2 (3-D only), so it is absent from the CO2 and derived products.
- `esm-hist` r4 has CO2 but no `nbp` or `rtmt`, so its derived rows have no land or ocean sink.

Scenario members are matched to historical members on the **realisation index
only** (`r<n>`, ignoring i/p/f), because the f-index differs between them
(`esm-hist r7i1p1f2` continues as `r7i1p1f1`). `baseline_member` in
`ukesm_tas.csv` records which historical member each baseline came from.
Emissions-driven members only ever take emissions-driven baselines.

## Formulas

| Quantity | Definition |
|---|---|
| global mean (`tas`, `rtmt`, CO2) | area-weighted mean with `areacella`, then a month-length-weighted annual mean |
| `nbp` | `sum(nbp x areacella x sftlf/100 x seconds per month) / 1e12`, PgC yr-1 |
| CO2 ppm | mole fraction x the file's unit scale (CMIP7 writes `1E-06`) |
| `atm_growth_PgC` | `d(co2_ppm)/dt x 2.124` |
| `emissions_PgC` | prescribed emissions (fossil and industrial + engineered CDR), GtCO2 / (44.009/12.011) |
| `airborne_fraction` | `atm_growth_PgC / emissions_PgC` |
| `airborne_fraction_10yr` | 10-year centred sum of growth over 10-year sum of emissions |
| `sim_total_sink_PgC` | `emissions_PgC - atm_growth_PgC` |
| `sim_land_sink_PgC` | `nbp` |
| `sim_ocean_sink_PgC` | `sim_total_sink_PgC - nbp` |
| `implied_total_sink_PgC` | harmonised emissions - `d(prescribed ppm)/dt x 2.124` |
| `cumulative_emissions_GtCO2` | cumulative from 1850: historical to 2021, then the scenario pathway |
| `value_corrected` (rtmt) | `rtmt` minus the `esm-piControl` mean over the parallel control window |

## Caveats

**Near-surface CO2 is a proxy for the atmospheric burden.** `co2mass` does not
exist anywhere in CMIP7, so the near-surface mole fraction stands in for it. It
is biased relative to a true burden: the one CMIP6 model on Pangeo carrying both
(GFDL-ESM4) shows the near-surface field running **1.6 ppm below** the
burden-derived value over `esm-hist`, about 3 PgC. UKESM1-0-LL and NorESM2-LM
carry `co2mass` on ESGF but not on Pangeo, so the offset rests on one model.

**The ocean sink is a residual** under a closed-budget assumption:
`emissions - atmospheric growth - nbp`. It is not `fgco2`, which was excluded
from this pull. Any drift or budget non-closure in the model lands in this term.

**`nbp` includes land-use fluxes as the model computes them**, while
`emissions_PgC` contains no land-use CO2 — the scenario files prescribe only
fossil, industrial and engineered-CDR emissions, and the ESM derives its
land-use flux from the land-use forcing. That is the correct budget for an
emissions-driven run, but it means **the airborne fraction here is not
comparable to the Global Carbon Budget's**, whose denominator also includes
land-use emissions. Ours runs about 0.60 for 2010-2019 where GCB's is nearer
0.5, and essentially all of that gap is definitional.

**`rtmt` is drift-corrected** by subtracting the `esm-piControl` mean over the
window each member actually branched from, read from `branch_time_in_parent`:
on UKESM's 360-day calendar, `esm-hist` r1 branches at control year 2000, r5 at
2160, r7 at 2240 and r8 at 2280. Drift is small (+0.07 to +0.10 W m-2). Both raw
and corrected values are kept.

**Historical and scenario emissions come from different compilations.** The
historical series is the Global Carbon Budget; the scenarios are area-summed
from the harmonised input4MIPs grids. They differ by +0.42 GtCO2 across the
2021/2022 join. The gridded scenario files are published at 5-yearly steps after
2025, so 60 of 79 years are **linearly interpolated**, flagged by the
`interpolated` column.

**Aviation is excluded.** `CO2_em_AIR_anthro` is a separate 3-D field costing
2.8 GB for the two scenarios, roughly 2% of emissions. `--with-aviation` on
`pull_forcing.py` adds it.

**Use `airborne_fraction_10yr` for figures.** The annual ratio is dominated by
interannual growth variability against a single year of emissions, and swings
between -1 and +3 before about 1960. The decadal-window column is the standard
estimator and is what the figures should show.

**The airborne fraction is undefined where emissions approach zero.** VL
emissions cross zero late in the century (-1.06 GtCO2 yr-1 by 2100), so the
ratio is masked below 1 PgC yr-1 of emissions rather than reported as a large
number.

**CMIP6 comparison values use cos-latitude weights** where the Pangeo store has
no cell-area field, which is exact for regular lat-lon grids and approximate
otherwise. Sums (`nbp`, `fgco2`) are never computed this way — they are skipped
if no area field is found.

**Two CMIP6 series are excluded, for opposite reasons.** MRI-ESM2-0 `fgco2` has
no cell-area field on a grid that matches its ocean output, and an area-weighted
sum cannot fall back to cos-latitude weights, so it is skipped. BCC-CSM2-MR
`esm-ssp585` `fgco2` is excluded as non-physical: the published field averages
-1e-7 kg m-2 s-1, about 450 times the real flux and the wrong sign, which
integrates to -2473 PgC yr-1. Each pull is screened against a plausible range
per variable and anything outside it is reported and dropped rather than written.

## Niño3.4

`cmip6_nino34.csv` holds the raw box mean (5°S–5°N, 170°W–120°W) so the anomaly
definition stays a plotting choice. `cmip6_nino34_oni.csv` adds the anomalies
used in `figures/nino34_context.png`, on **CPC's own base-period scheme**: a
30-year climatology held fixed across each 5-year block and centred on it,
falling back to the latest complete decade-aligned base (1991–2020 today) where
a centred one would need data the record does not have, then a 3-month running
mean. Re-deriving the *observed* anomaly this way gives **+2.14 °C for JAS 2026
against CPC's published +2.16**; what remains is base-period bookkeeping and the
2-decimal rounding of the published file.

Three things to respect when using it:

- **Observations are reprocessed, not taken as published**, so that models and
  observations get identical treatment. Both numbers appear on the figure.
- **`base_centred` marks blocks whose base period was properly centred.** Where
  it is false the base is a trailing fallback, which leaves some of the warming
  trend in the anomaly. The band and statistics use centred blocks only, which
  is why the band stops near 2041 rather than 2060; extending it means pulling
  model data past 2060.
- **One asymmetry is unavoidable**: a model can see its own future, so its
  present-day block gets a centred base, while the observations cannot and fall
  back to 1991–2020. `plot_nino34.py --realtime` forces the trailing base on
  both, the symmetric comparison, and the script reports the percentile under
  both conventions (96.6th centred, 98.5th real-time).
- **Weighting falls back where cell areas do not fit**: 34 models use
  `areacello`, 7 use cos-latitude (adequate for a 10°-tall equatorial box).

## CMIP6 coverage

ESGF's OPeNDAP endpoints are advertised but return 404 at every node tried, so
the CMIP6 layer reads the Pangeo Zarr mirror instead. Its coverage is narrower
than ESGF's: there is **no `nbp`, `rtmt` or `co2mass` for `esm-ssp585`** on
Pangeo, and no `esm-ssp534-over` for the variables wanted. `tas` is available for
9 models in both `esm-hist` and `esm-ssp585`. Per-file coverage is printed by
`pull_cmip6_esm.py` and recorded in the CSVs themselves.

| variable | esm-hist | esm-ssp585 | notes |
|---|---|---|---|
| `tas` | 13 | 9 | 9 models have both |
| `fgco2` | 11 | 7 | MRI-ESM2-0 skipped, BCC-CSM2-MR esm-ssp585 excluded |
| `nbp` | 3 | 0 | not published on Pangeo for the scenario |
| `co2` | 4 | 2 | 3-D field, lowest model level taken |
| `rtmt` | 1 | 0 | GFDL-ESM4 only |
| `co2mass` | 1 | 0 | GFDL-ESM4 only — the whole basis for the proxy-error estimate |

Ocean uptake for 2010-2019 comes out at 2.4-3.1 PgC yr-1 across models against
the Global Carbon Budget's ~2.5, and the land sink at 0.0-1.7 PgC yr-1, which is
the expected spread for `nbp` including land-use fluxes.
