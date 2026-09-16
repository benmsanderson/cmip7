# cmip7ref

A small analysis toolkit for CMIP7 output. It reads the diagnostic results the
[Climate REF](https://api.climate-ref.org/docs) has already computed, and pulls
raw fields from the ESGF STAC index only where the REF has nothing.

![GMT trajectories](figures/gmt_trajectories.png)

## Setup

```bash
uv sync
```

## Usage

Exploratory plots, from the REF alone (no downloads):

```bash
uv run scripts/inventory.py     # what CMIP7 tas data the REF holds and has processed
uv run scripts/plot_gmt.py      # historical + VL + H global-mean temperature
uv run scripts/plot_gmt.py --mip-era CMIP6 --scenarios ssp126 ssp585 --models MIROC6
uv run scripts/plot_cmip6_vs_cmip7.py   # UKESM1-0-LL esm-hist+SSP5-8.5 vs UKESM1-3-LL esm-hist+H
```

Data products, written to [data/](data/) — see [data/README.md](data/README.md)
for the schema, the exact source datasets and the caveats:

```bash
uv run scripts/pull_tas.py        # REF series, no download
uv run scripts/pull_co2.py        # near-surface CO2 -> ppm
uv run scripts/pull_nbp.py        # land carbon flux -> PgC yr-1
uv run scripts/pull_rtmt.py       # net TOA flux, drift-corrected against esm-piControl
uv run scripts/pull_forcing.py    # prescribed CO2 concentrations and global emissions
uv run scripts/derive.py          # cumulative emissions, airborne fraction, sinks
uv run scripts/pull_cmip6_esm.py  # CMIP6 emissions-driven precedent, read lazily
uv run pytest
```

Each pull script prints its own coverage, year-range and sanity checks, and
writes a quick panel to `figures/checks/`.

REF responses are cached in `.cache/ref-api/` for 6 hours; ESGF downloads go to
`.cache/esgf/` (about 3.4 GB for the full set). Both are git-ignored.

From Python:

```python
from cmip7ref import RefClient, fetch_global_mean, anomalies, models_with

with RefClient() as client:
    df = fetch_global_mean(client, variable_id="tas")   # tidy long DataFrame
models = models_with(df, ["historical", "vl", "h"])
df = anomalies(df[df.source_id.isin(models)])
```

## Layout

| Path | Contents |
|---|---|
| `src/cmip7ref/client.py` | `RefClient`: REF API, pagination, disk cache |
| `src/cmip7ref/stac.py` | `StacClient`: ESGF STAC index, CQL2 search, resumable downloads |
| `src/cmip7ref/pangeo.py` | lazy CMIP6 access via the Pangeo Zarr mirror |
| `src/cmip7ref/reduce.py` | area- and calendar-weighted reduction to annual global series |
| `src/cmip7ref/forcing.py` | prescribed CO2 concentrations and global emissions |
| `src/cmip7ref/targets.py` | the approved pull list, members listed explicitly |
| `src/cmip7ref/timeseries.py` | REF series to DataFrame, stale-execution filtering, anomalies |
| `src/cmip7ref/experiments.py` | experiment families (`historical`/`esm-hist`, `scen7-*`, `ssp*`) |
| `src/cmip7ref/checks.py` | the coverage and sanity checks every script prints |
| `src/cmip7ref/plotting.py` | trajectory panels |
| `docs/api_notes.md` | REF API assessment and gotchas |
| `docs/data_availability.md` | what CMIP7 data exists, where, and at what size |

## Where the data comes from

- **The REF serves global-mean `tas` and nothing else** for CMIP7. Its dataset records carry no file paths and no time ranges.
- **CMIP7 model output is only in the ESGF STAC API**, not the legacy Solr index, and only over HTTP — there is no OPeNDAP.
- **CMIP6 is read from the Pangeo Zarr mirror**, because ESGF's advertised OPeNDAP endpoints return 404 at every node tried.
- **`co2mass` does not exist in CMIP7**; the branded near-surface `co2_tavg-h2m-hxy-u` stands in for it.

## Method notes

- Concentration-driven and emissions-driven (`esm-`) runs are grouped into the same family. Panel subtitles show which experiment ids were used.
- Anomalies are taken relative to 1850–1900. Scenario members are matched to historical members on the **realisation index only** (`r<n>`), since the f-index differs between them, and `baseline_member` records which historical member was used.
- Thin lines are individual members. Thick lines are the ensemble mean.
- CMIP6 works through the same code (`mip_era="CMIP6"`); its `member_id` dimension is mapped onto CMIP7's `variant_label`. 71 CMIP6 models have global-mean `tas`, 29 of them with historical and all four core SSPs.
- The CMIP6/CMIP7 comparison uses `esm-hist` on both sides, so the historical period is emissions-driven in both eras. Its CMIP6 scenario is concentration-driven because the REF holds no `esm-ssp585`; the figure carries a footnote saying so.
