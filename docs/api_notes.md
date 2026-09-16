# Climate REF API: assessment notes

Assessed 2026-09-16 against `https://api.climate-ref.org/api/v1`
(REF 0.18.0, API 0.8.1, data updated 2026-09-15). The API describes itself as a
work in progress that may change without warning, so re-check these notes when
something breaks. The OpenAPI spec is at `/api/v1/openapi.json`.

## What it is

The API serves the **outputs** of the Rapid Evaluation Framework's diagnostics
(ESMValTool, ILAMB, PMP), not the raw CMIP data. You get:

- **scalar values**: metrics such as RMSE, ECS, and TCR, with dimensions
- **series values**: 1-D series, for example annual global-mean `tas`, with an index and units
- metadata on executions, datasets, models and diagnostics
- per-execution archives (`/executions/{id}/archive`) with the full diagnostic output, including netCDF and plots

It is read-only and needs no authentication.

## Useful endpoints

| Endpoint | Use |
|---|---|
| `GET /utils/about` | REF version and last data update |
| `GET /models/?mip_era=CMIP7` | models with CMIP7 data (5 as of this date) |
| `GET /diagnostics/catalog?mip_era=CMIP7` | all diagnostics, with success counts and `group_by` |
| `GET /diagnostics/{provider}/{diag}/execution_groups?mip_era=CMIP7` | one group per model, experiment and member |
| `GET /diagnostics/{provider}/{diag}/values?value_type=series\|scalar` | **the data**, filterable by dimension |
| `GET /datasets/?dataset_type=cmip7&facets={"variable_id":"tas"}` | what raw data has been ingested |
| `GET /executions/{group_id}` | executions within a group (re-runs) |

## Gotchas

1. **User-agent.** Python's default `Python-urllib` user-agent gets a 403, while curl works. Send an explicit `User-Agent`.
2. **Page-size caps.** `/datasets` accepts at most `limit=100`, and `/values` at most `limit=500`. Responses are `{data, count, total_count}`, so paginate on `offset`.
3. **Dimension filters.** The `/values` endpoint accepts any dimension as an extra query param (`&source_id=UKESM1-3-LL&experiment_id=esm-hist`), even though the spec doesn't list them.
4. **`facets` on `/datasets`** must be a JSON object string. Other formats return `"facets must be a JSON object"`.
5. **Stale executions.** `/values` returns series from *every* execution of a group, so a re-run shows up as a duplicate with slightly different values. Keep the highest `execution_id` per group (`timeseries.latest_only`).
6. **Mixed calendars.** Series come in `360_day` and `proleptic_gregorian`, with mid-year timestamps. For annual means, reduce the index to the year.
7. **`format=csv`** exists on `/values` and gives a flat CSV. We use JSON because it keeps the execution ids.

## CMIP7 experiment naming

- Historical is `historical` (concentration-driven) or `esm-hist` (emissions-driven).
- ScenarioMIP experiments are `scen7-<name>` / `esm-scen7-<name>`, for example `esm-scen7-vl` and `esm-scen7-h`.
- CMIP7 uses `variant_label`, where CMIP6 used `member_id`, and grid labels like `g110`.

## Global-mean temperature

`esmvaltool/global-mean-timeseries` produces annual global-mean series with
`region=global` and `statistic=annual mean`. For CMIP7 it only covers `tas` at
present. As of this assessment, 40 series values cover 33 execution groups.

**Coverage.** Every CMIP7 `tas` dataset the REF has ingested also has a
global-mean series, so what's missing is ingestion, not processing. Only
UKESM1-3-LL has scenario data (`esm-scen7-vl` and `esm-scen7-h`, 2 members each).
Run `uv run scripts/inventory.py` for the current table.

## Possible next steps

- Use `/executions/{id}/archive` to pull the underlying netCDF for diagnostics that don't expose series.
- Use scalar values (ECS, TCR, TCRE, ZEC) as they appear for CMIP7 models.
- Pull CMIP6 series (`mip_era=CMIP6`) from the same endpoint for CMIP6-to-CMIP7 comparisons.
