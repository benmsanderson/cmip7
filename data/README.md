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
| `cmip6_sst_regions.csv` | monthly Niño3.4 and 20°N–20°S mean SST (°C), historical + ssp245, 1950–2060 | 41 models, one member each |
| `cmip6_oni.csv`, `cmip6_roni.csv` | the two indices derived from it | 41 and 40 models |
| `obs_sst_regions.csv` | the same two regions from gridded ERSSTv6, 1850–2026 | observations |
| `obs_enso_indices.csv` | CPC's published ONI and RONI (v5 and v6), for checking | observations |

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

## Niño3.4 and the RONI

`cmip6_sst_regions.csv` holds raw box means — Niño3.4 (5°S–5°N, 170°W–120°W) and
the 20°N–20°S belt the RONI subtracts — so the index definition stays a plotting
choice. Both regions come from one pass over each store; computing them
separately fetched every chunk twice, which is the whole cost of the run.

Two indices are built from it by `plot_nino34.py --index {oni,roni}`:

- **ONI**: the Niño3.4 anomaly. A fixed baseline keeps the background warming in,
  so the model band climbs through the century.
- **RONI**: Niño3.4 anomaly minus the tropical-mean anomaly, rescaled so its
  variance matches Niño3.4, exactly as CPC define it. The tropical warming is
  differenced out of both sides, so the band is flat and what remains is ENSO.

Observations are reduced from gridded **ERSSTv6** through the same code, because
CPC publish the ONI and RONI but not the tropical-mean series the RONI needs.
That reproduces CPC's published RONI with correlation 0.999 and a mean
difference of 0.035 °C, independently recovering their 1.26 rescale factor —
the check that this is their recipe and not merely something like it.

**The ERSST vintage matters for the event in progress.** CPC's RONI page is now
ERSSTv6, whose high-frequency filter damps the latest months: JAS 2026 is +1.7 in
v6 against +2.1 in v5, and CPC warn recent values can be revised for up to two
months. `pull_obs_sst.py --version v5` switches back.

**One model is dropped from the RONI.** KACE-1-0-G correlates its Niño3.4 with
its own tropical mean at 0.98, leaving a difference of 0.16 °C that the
rescaling would multiply by 4.8 — noise amplified into apparent ENSO. Models
needing a factor above 3 are excluded and named; the rest run 1.23–1.82 against
the observed 1.26.

The older single-region `cmip6_nino34.csv` was replaced by `cmip6_sst_regions.csv`. `cmip6_nino34_oni.csv` adds the anomalies used in
`figures/nino34_context.png`. The key figure uses a **fixed 1991-2020
climatology for both models and observations** — the same baseline on both
sides, and also CPC's current operational base, so the observed current event
reproduces their published ONI (+2.14 against +2.16). A fixed base keeps the
warming trend in the anomaly deliberately: the model band rises through the
century, showing the background Pacific warming a future El Niño sits on top of.

`--scheme cpc` switches both sides to **CPC's shifting base-period scheme**: a
30-year climatology held fixed across each 5-year block and centred on it,
falling back to the latest complete decade-aligned base (1991–2020 today) where
a centred one would need data the record does not have, then a 3-month running
mean. Re-deriving the *observed* anomaly this way gives **+2.14 °C for JAS 2026
against CPC's published +2.16**; what remains is base-period bookkeeping and the
2-decimal rounding of the published file.

Three things to respect when using it:

- **Observations are reprocessed, not taken as published**, so that models and
  observations get identical treatment. Both numbers appear on the figure.
- **`base_centred` (CPC scheme only) marks blocks whose base period was properly centred.** Where
  it is false the base is a trailing fallback, which leaves some of the warming
  trend in the anomaly. The band and statistics use centred blocks only, which
  is why the band stops near 2041 rather than 2060; extending it means pulling
  model data past 2060.
- **The distribution panels compare matched years and one season.** A model
  window containing future warming is not comparable with an observed record
  that stops today, so both sides use the same years; and ENSO is phase-locked,
  so boreal summer (its low-variance season) is not interchangeable with the
  annual spread. `--season` and `--dist-years` change both.
- **Over the historical period models and observations agree.** Like-for-like
  medians for 1950–2014 are −0.29 vs −0.28 (ONI) and −0.01 vs +0.02 (RONI). The
  divergence is recent: for 2011–2026 observations sit 0.46 °C below the model
  median on both indices. The models' spread is wider throughout (sd ~1.1 vs
  ~0.8), so CMIP6 ENSO is too variable in every period.
- **The scheme changes the headline percentile.** On the shared fixed baseline
  the JAS 2026 peak is at the 92.5th percentile of CMIP6 for 2011–2041; on the
  CPC scheme, which removes the trend from both sides, it is at the 96.6th. The
  difference is the background warming the models carry into that window.
- **Under `--scheme cpc` one asymmetry is unavoidable**: a model can see its own
  future, so its present-day block gets a centred base while the observations
  fall back to 1991–2020. The fixed baseline has no such problem, which is the
  main reason it is the default.
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
