# cmip7ref

A small analysis toolkit for CMIP7 output. It works from the
[Climate REF API](https://api.climate-ref.org/docs), so there are no raw data
downloads: it reads the diagnostic results the REF has already computed.

![GMT trajectories](figures/gmt_trajectories.png)

## Setup

```bash
uv sync
```

## Usage

```bash
uv run scripts/inventory.py     # what CMIP7 tas data the REF holds and has processed
uv run scripts/plot_gmt.py      # historical + VL + H global-mean temperature
uv run scripts/plot_gmt.py --scenarios vl m h --baseline 1995 2014
uv run pytest
```

API responses are cached in `.cache/ref-api/` for 6 hours. Use `--no-cache`
to force a refetch.

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
| `src/cmip7ref/client.py` | `RefClient`: HTTP, pagination, disk cache, endpoint helpers |
| `src/cmip7ref/timeseries.py` | series to DataFrame, stale-execution filtering, anomalies |
| `src/cmip7ref/experiments.py` | experiment families (`historical`/`esm-hist`, `scen7-*`/`esm-scen7-*`) |
| `src/cmip7ref/plotting.py` | trajectory panels |
| `scripts/` | runnable analyses |
| `docs/api_notes.md` | API assessment and gotchas |

## Method notes

- Concentration-driven and emissions-driven (`esm-`) runs are grouped into the same family. Panel subtitles show which experiment ids were used.
- Anomalies are taken relative to 1850–1900. Each scenario member uses the historical member with the same `variant_label` as its baseline, or the model's historical ensemble mean if there is no match.
- Thin lines are individual members. Thick lines are the ensemble mean.
