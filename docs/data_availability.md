# CMIP7 data availability for the Milan talk products

Inventory taken 17 September 2026. Everything below was queried live; no data was
downloaded. Counts will change as centres publish, so re-run the inventory before
relying on it.

## Where the data actually lives

| Source | Endpoint | What it gives us |
|---|---|---|
| Climate REF API | `https://api.climate-ref.org/api/v1` | annual global-mean `tas` series only, ready-reduced |
| ESGF STAC (CMIP7) | `https://api.stac.esgf.ceda.ac.uk` | all CMIP7 model output, as file URLs |
| ESGF Solr (legacy) | `https://esgf-data.dkrz.de/esg-search` | CMIP6 model output and CMIP7 input4MIPs forcing |

Three constraints follow from this split:

1. **The REF cannot supply anything but `tas`.** Its `global-mean-timeseries`
   diagnostic covers `tas` alone for CMIP7, and its `/datasets` records carry only
   `variable_id`, `source_id`, `experiment_id`, `variant_label` and a slug — no file
   paths, no URLs, no time ranges. It is an index, not a data service.
2. **CMIP7 model output is not in the legacy Solr index.** `mip_era=CMIP7` there
   returns input4MIPs forcing data almost exclusively; `source_id=UKESM1-3-LL`
   returns nothing. CMIP7 output is only in the STAC API, which takes **CQL2**
   filters (`filter-lang: cql2-json`) — the simpler STAC `query` extension rejects
   the `in` operator. `intake-esgf` is not the access route here.
3. **CMIP7 has no OPeNDAP.** Every CMIP7 item advertises `access: ["HTTPServer"]`,
   so files must be downloaded and cached. CMIP6 does have OPeNDAP, so the CMIP6
   comparison can stay lazy.

### REF vs ESGF disagree

The REF reports zero records for `fgco2` and only a single `co2` dataset. ESGF has
11 `fgco2` datasets and CO2 for nine member-experiments. This is REF ingestion lag,
not missing data. **Treat ESGF as authoritative for what exists.**

## CMIP7 model output: what exists at all

Members published per model and experiment (any variable):

| experiment | CanESM5-1 | CanESM6-0-MR | EC-Earth3-ESM-1-1 | UKCM2-0-LL | UKCM2a-0-HH | UKESM1-3-LL |
|---|---|---|---|---|---|---|
| `esm-hist` | 5 | – | – | – | – | **5** |
| `historical` | – | 5 | – | 1 | 2 | – |
| `esm-scen7-h` | – | – | – | – | – | **2** |
| `esm-scen7-vl` | – | – | 1 | – | – | **2** |
| `esm-piControl` | – | – | – | – | – | 1 |
| `piControl` | 1 | – | – | 1 | – | – |
| `1pctCO2` | 1 | 1 | – | 1 | – | 1 |
| `abrupt-4xCO2` | – | 1 | – | – | 1 | 1 |
| `amip` | – | – | – | – | 1 | – |
| `piClim-*` | – | – | – | 1 each | – | – |

UKESM1-3-LL is the only model with a historical-plus-scenario chain. EC-Earth3-ESM-1-1
has a single `esm-scen7-vl` member but no matching historical, so it cannot be used.

### Does not exist anywhere in CMIP7 (17 Sept 2026)

- `co2mass` — zero items, any model, any experiment.
- `esm-scen7-m`, and the concentration-driven `scen7-h` / `scen7-vl`. The Fast Track
  status sheet lists 8 emissions-driven and 4 concentration-driven members; only
  5 `esm-hist` / 2 `esm-scen7-h` / 2 `esm-scen7-vl` are published.
- Any `flat10` experiment (`esm-flat10`, `-zec`, `-cdr`).

### Time coverage

STAC `end_datetime` is an **exclusive** bound: `esm-hist` reports `2022-01-01` but its
last file is `...195001-202112.nc`. Actual coverage:

- `esm-hist`: **1850–2021**
- `esm-scen7-h`, `esm-scen7-vl`: **2022–2100**
- `esm-piControl`: 1999–2489 (branch-time numbering, 491 years)

This matches the REF `tas` series exactly (172 annual values historical, 79 scenario).

## UKESM1-3-LL: per-member coverage

`x` = published. Variables are given by branded name, which matters: `variable_id`
alone conflates the 8 GB 3-D CO2 field with the 114 MB near-surface one, and monthly
`tas` with daily `tas`/`tasmax`/`tasmin`.

| experiment | member | `tas` (mon) | `co2_tavg-h2m-hxy-u` | `co2` 3-D | `nbp` | `rtmt` | `fgco2` | fx |
|---|---|---|---|---|---|---|---|---|
| `esm-hist` | r1i1p1f1 | x | – | x | x | x | x | – |
| `esm-hist` | r4i1p1f1 | – | x | x | – | – | – | – |
| `esm-hist` | r5i1p1f1 | x | x | x | x | x | x | **x** |
| `esm-hist` | r7i1p1f2 | x | x | x | x | x | x | – |
| `esm-hist` | r8i1p1f2 | – | x | x | x | x | x | – |
| `esm-scen7-h` | r1i1p1f1 | x | – | x | x | x | x | – |
| `esm-scen7-h` | r5i1p1f1 | x | x | x | x | x | x | **x** |
| `esm-scen7-vl` | r1i1p1f1 | x | – | – | x | x | x | – |
| `esm-scen7-vl` | r5i1p1f1 | x | x | x | x | x | x | **x** |
| `esm-piControl` | r1i1p1f1 | x | – | x | x | x | x | – |

**`r5i1p1f1` is the only complete chain** — `esm-hist` → `esm-scen7-h` / `esm-scen7-vl`
with every variable including near-surface CO2 and the fx fields.

**fx fields are published only under `r5i1p1f1`** (`areacella` 53 kB, `sftlf` 69 kB,
`areacello` 1.9 MB, per experiment). They are reused across members, so the
cos-latitude fallback should never fire for UKESM1-3-LL.

Variant labels differ in the f-index across members (`r7i1p1f2`, `r8i1p1f2`), so
matching scenario to historical members must use the realisation index `r<n>` only.
On that rule both scenario members (r1, r5) find their historical counterpart.

### CO2 is only available as a near-surface mole fraction

`co2mass` does not exist, so the atmospheric burden cannot be read directly.
`co2_tavg-h2m-hxy-u` (near-surface CO2 mole fraction, ~114 MB per member) is the
substitute, available for `esm-hist` r4/r5/r7/r8 and `esm-scen7-h`/`-vl` r5. The 3-D
`co2_tavg-al-hxy-u` alternative is ~8 GB per member (73 GB in total) and is the only
CO2 for r1. **Near-surface CO2 is a proxy for the burden**, and the CMIP6 cross-check
below is how we quantify that error.

## Approved pull list, with versions

Exact STAC items, resolved 17 Sept 2026. All are `grid_label=g110`, monthly except fx.

| branded variable | experiment | member | version | years | size | files |
|---|---|---|---|---|---|---|
| `co2_tavg-h2m-hxy-u` | `esm-hist` | r4i1p1f1 | v20260826 | 1850–2021 | 114.0 MB | 2 |
| `co2_tavg-h2m-hxy-u` | `esm-hist` | r5i1p1f1 | v20260829 | 1850–2021 | 114.0 MB | 2 |
| `co2_tavg-h2m-hxy-u` | `esm-hist` | r7i1p1f2 | v20260901 | 1850–2021 | 114.0 MB | 2 |
| `co2_tavg-h2m-hxy-u` | `esm-hist` | r8i1p1f2 | v20260907 | 1850–2021 | 114.0 MB | 2 |
| `co2_tavg-h2m-hxy-u` | `esm-scen7-h` | r5i1p1f1 | v20260828 | 2022–2100 | 53.4 MB | 2 |
| `co2_tavg-h2m-hxy-u` | `esm-scen7-vl` | r5i1p1f1 | v20260828 | 2022–2100 | 53.7 MB | 2 |
| `nbp_tavg-u-hxy-lnd` | `esm-hist` | r1i1p1f1 | v20260814 | 1850–2021 | 66.3 MB | 2 |
| `nbp_tavg-u-hxy-lnd` | `esm-hist` | r5i1p1f1 | v20260829 | 1850–2021 | 66.3 MB | 2 |
| `nbp_tavg-u-hxy-lnd` | `esm-hist` | r7i1p1f2 | v20260901 | 1850–2021 | 66.3 MB | 2 |
| `nbp_tavg-u-hxy-lnd` | `esm-hist` | r8i1p1f2 | v20260907 | 1850–2021 | 66.3 MB | 2 |
| `nbp_tavg-u-hxy-lnd` | `esm-scen7-h` | r1i1p1f1 | v20260825 | 2022–2100 | 30.6 MB | 2 |
| `nbp_tavg-u-hxy-lnd` | `esm-scen7-h` | r5i1p1f1 | v20260828 | 2022–2100 | 30.6 MB | 2 |
| `nbp_tavg-u-hxy-lnd` | `esm-scen7-vl` | r1i1p1f1 | v20260825 | 2022–2100 | 30.6 MB | 2 |
| `nbp_tavg-u-hxy-lnd` | `esm-scen7-vl` | r5i1p1f1 | v20260828 | 2022–2100 | 30.6 MB | 2 |
| `rtmt_tavg-u-hxy-u` | `esm-hist` | r1i1p1f1 | v20260814 | 1850–2021 | 165.4 MB | 2 |
| `rtmt_tavg-u-hxy-u` | `esm-hist` | r5i1p1f1 | v20260829 | 1850–2021 | 165.4 MB | 2 |
| `rtmt_tavg-u-hxy-u` | `esm-hist` | r7i1p1f2 | v20260901 | 1850–2021 | 165.4 MB | 2 |
| `rtmt_tavg-u-hxy-u` | `esm-hist` | r8i1p1f2 | v20260907 | 1850–2021 | 165.4 MB | 2 |
| `rtmt_tavg-u-hxy-u` | `esm-piControl` | r1i1p1f1 | v20260825 | 1999–2489 | 472.3 MB | 6 |
| `areacella_ti-u-hxy-u`, `sftlf_ti-u-hxy-u` | each experiment | r5i1p1f1 | v202608–09 | – | 0.4 MB | 6 |

**Model-output total: 2.08 GB.** `tas` adds nothing — it comes from the REF.

Two coverage notes for the reducer: `esm-hist` r1 has no near-surface CO2 (3-D only),
and `esm-hist` r4 has CO2 but no `nbp` or `rtmt`. No member has the full set on its
own except r5.

## Forcing inputs (input4MIPs, legacy Solr)

**Concentrations are available as ready-made global means** — `grid_label=gm`,
annual, ~38 kB per file. No reduction needed:

| series | dataset id | version |
|---|---|---|
| historical CO2 | `input4MIPs.CMIP7.CMIP.CR.CR-CMIP-1-0-0.atmos.yr.co2.gm` | v20250228 |
| H CO2 | `input4MIPs.CMIP7.ScenarioMIP.CR.CR-h-1-0-0.atmos.yr.co2.gm` | v20251211 |
| VL CO2 | `input4MIPs.CMIP7.ScenarioMIP.CR.CR-vl-1-0-0.atmos.yr.co2.gm` | v20251211 |

**Emissions are gridded only.** No `gm` product exists for any CO2 emissions variable,
so global totals must be area-summed from the gridded fields:

| series | dataset | size |
|---|---|---|
| H anthropogenic CO2 | `IIASA-IAMC-h-1-1-0` `CO2_em_anthro` `gn`, 2022–2100 | 681 MB (1 file) |
| VL anthropogenic CO2 | `IIASA-IAMC-vl-1-1-0` `CO2_em_anthro` `gn`, 2022–2100 | 610 MB (1 file) |
| historical anthropogenic CO2 | `CEDS-CMIP-2025-04-18` `CO2_em_anthro` `gn`, 1750–2023 | 2.74 GB (6 files); 2.50 GB from 1850 |

**This is the budget risk.** Emissions forcing is ~3.8 GB, larger than the 2.08 GB of
model output. Options: accept it; restrict CEDS to 1850 onward (2.50 GB, saves little);
or take historical global totals from a non-ESGF source (GCB, or the IIASA scenario
database) and area-sum only the two scenario files (1.29 GB).

Two open questions on the emissions side, both affecting `cumulative_emissions_GtCO2`:

- `CO2_em_anthro` is the anthropogenic surface field. Aviation (`CO2_em_AIR_anthro`)
  is separate; open-burning CO2 is not published under `CO2_em_openburning` for CMIP7
  at all and would have to come from the `DRES-CMIP-BB4CMIP7` datasets under a
  different naming scheme.
- What UKESM was actually *passed* in its emissions-driven runs (fossil-and-industrial
  only, with land-use handled interactively?) is not determinable from the archive
  alone. Whatever we sum should be stated explicitly in `data/README.md` rather than
  labelled "total CO2 emissions".

## CMIP6 precedent (P4)

Lazy over OPeNDAP; no downloads. Models with `esm-ssp585`, monthly:

| variable | models | which |
|---|---|---|
| `tas` | 9 | ACCESS-ESM1-5, AWI-ESM-1-REcoM, BCC-CSM2-MR, CNRM-ESM2-1, CanESM5, GISS-E2-1-G-CC, MIROC-ES2L, MPI-ESM1-2-LR, UKESM1-0-LL |
| `fgco2` | 9 | as above, less AWI-ESM-1-REcoM, plus MRI-ESM2-0 |
| `nbp` | 7 | ACCESS-ESM1-5, CNRM-ESM2-1, CanESM5, GISS-E2-1-G-CC, MIROC-ES2L, MPI-ESM1-2-LR, UKESM1-0-LL |
| `co2mass` | 1 | UKESM1-0-LL |

`esm-ssp534-over` `tas`: 5 models (AWI-ESM-1-REcoM, CNRM-ESM2-1, MIROC-ES2L,
MPI-ESM1-2-LR, UKESM1-0-LL).

`co2mass` for `esm-hist` exists for **UKESM1-0-LL and NorESM2-LM** only. Those two are
the entire basis for the near-surface-CO2-vs-burden offset we intend to quote, and
only UKESM1-0-LL has `co2mass` in both `esm-hist` and `esm-ssp585`.

## Volume summary

| Component | Size | Access |
|---|---|---|
| CMIP7 model output (approved list) | 2.08 GB | download |
| CO2 concentrations (3 global-mean files) | ~0.1 MB | download |
| CO2 emissions, gridded | 1.29 GB scenarios + 2.50 GB historical | download |
| CMIP7 `tas` | – | REF API |
| CMIP6 precedent | – | OPeNDAP, lazy |

## Open decisions

1. **Historical emissions**: pay 2.50 GB for CEDS and area-sum, or source global
   totals elsewhere. Affects `cumulative_emissions_GtCO2` and historical
   `airborne_fraction` only.
2. **Which emissions components** count as "as passed to the ESM" — anthro surface
   alone, or plus aviation, or plus open burning.
3. **`esm-hist` r1 has no near-surface CO2**, so CO2-dependent derived series cannot
   cover r1. Confirm r5 is the intended chain for all CO2 products, with r4/r7/r8
   historical-only, as the brief implies.
