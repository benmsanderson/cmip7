"""Monthly Nino3.4 and tropical-mean SST for CMIP6 historical + ssp245.

Both regions come out of a single pass over each store, because the Nino3.4 box
is small but the stores chunk in time only: reading it costs the whole spatial
field anyway, so the 20S-20N belt the RONI needs is nearly free alongside it.

Read lazily from the Pangeo Zarr mirror. The stores chunk in time only, so a
Nino3.4 box still pulls the full spatial field for each time chunk: restricting
the years is what keeps this affordable, not restricting the area.

Writes raw SST (degC); anomalies are a plotting-time choice, made in
scripts/plot_nino34.py.

    uv run scripts/pull_nino34.py
    uv run scripts/pull_nino34.py --years 1950 2060 --variable tos
"""

import argparse
import traceback
from pathlib import Path

import dask
import pandas as pd

from cmip7ref import pangeo
from cmip7ref.indices import REGIONS, box_mean, monthly_frame
from cmip7ref.reduce import compatible

EXPERIMENTS = ("historical", "ssp245")
# A Nino3.4 mean outside this range means something went wrong (wrong box, a
# masked field read as zero, or kelvin that was not converted).
PLAUSIBLE_SST = (20.0, 34.0)


def extract(row, years: tuple[int, int], variable: str) -> pd.DataFrame | None:
    """Monthly means for every region of interest, from one pass over the store."""
    ds = pangeo.open_store(row.zstore)
    da = ds[variable].sel(time=slice(str(years[0]), str(years[1])))
    if da.sizes.get("time", 0) == 0:
        print("    no overlap with the requested years")
        return None

    area = pangeo.fx(row.source_id, "areacello" if variable == "tos" else "areacella")
    weights = area if compatible(area, da) else None
    units = da.attrs.get("units", "")

    # Both reductions are computed together: separate .compute() calls would
    # fetch every chunk twice, and these reads are what the run costs.
    lazy = {name: box_mean(da, ds, box, weights=weights) for name, box in REGIONS.items()}
    computed = dict(zip(lazy, dask.compute(*lazy.values())))

    frames = []
    for name, series in computed.items():
        out = monthly_frame(series)
        if units.lower() in ("k", "kelvin"):
            out["value"] -= 273.15
        out.insert(0, "source_id", row.source_id)
        out.insert(1, "experiment_id", row.experiment_id)
        out.insert(2, "variant_label", row.member_id)
        out["region"] = name
        out["grid_label"] = row.grid_label
        out["variable_id"] = variable
        out["units"] = "degC"
        out["weighting"] = "areacello" if weights is not None else "cos-latitude"
        out["source"] = "pangeo"
        out["mip_era"] = "CMIP6"
        frames.append(out)
    ds.close()
    return pd.concat(frames, ignore_index=True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--years", nargs=2, type=int, default=[1950, 2060], metavar=("START", "END"))
    p.add_argument("--variable", default="tos", choices=["tos", "ts", "tas"])
    p.add_argument("--models", nargs="+", help="restrict to these source_ids")
    p.add_argument("--out", type=Path, default=Path("data/cmip6_sst_regions.csv"))
    p.add_argument("--workers", type=int, default=4,
                   help="dask threads; these reads are network-bound, so a few help a lot")
    p.add_argument("--restart", action="store_true", help="ignore any existing output and start over")
    args = p.parse_args()

    # Network-bound, so threads overlap requests. Peak memory is a few chunks per
    # worker (~90 MB each for tos), well short of what killed the earlier job.
    dask.config.set(scheduler="threads", num_workers=args.workers)
    table = {"tos": "Omon"}.get(args.variable, "Amon")

    found = {e: pangeo.find(e, args.variable, table) for e in EXPERIMENTS}
    models = set(found["historical"].source_id) & set(found["ssp245"].source_id)
    if args.models:
        models &= set(args.models)
    print(f"{len(models)} models with {args.variable} in both {' and '.join(EXPERIMENTS)}")

    # Append per model, so a stopped run resumes instead of starting over.
    done: set[str] = set()
    if args.out.exists() and not args.restart:
        existing = pd.read_csv(args.out)
        if "region" not in existing.columns:
            print("  (existing file predates the tropical-mean region; starting over)")
            existing = existing.iloc[0:0]
        counts = existing.groupby("source_id").apply(
            lambda g: g.experiment_id.nunique() * g.region.nunique(), include_groups=False
        ) if len(existing) else pd.Series(dtype=int)
        done = set(counts[counts == len(EXPERIMENTS) * len(REGIONS)].index)
        print(f"resuming: {len(done)} models already complete in {args.out}")

    frames, failures, rejected = [], [], []
    for model in sorted(models):
        if model in done:
            continue
        for experiment in EXPERIMENTS:
            row = found[experiment][found[experiment].source_id == model]
            if row.empty:
                continue
            row = row.iloc[0]
            print(f"  {model:18s} {experiment:12s} {row.member_id:10s} {row.grid_label}", flush=True)
            try:
                out = extract(row, tuple(args.years), args.variable)
            except Exception as exc:
                failures.append((model, experiment, f"{type(exc).__name__}: {exc}"))
                print(f"    FAILED {type(exc).__name__}: {str(exc)[:110]}")
                traceback.clear_frames(exc.__traceback__)
                continue
            if out is None:
                continue
            median = float(out[out.region == "nino34"]["value"].median())
            if not PLAUSIBLE_SST[0] <= median <= PLAUSIBLE_SST[1]:
                rejected.append((model, experiment, median))
                print(f"    EXCLUDED: median SST {median:.2f} outside {PLAUSIBLE_SST} degC")
                continue
            frames.append(out)
            args.out.parent.mkdir(parents=True, exist_ok=True)
            header = not args.out.exists()
            out.to_csv(args.out, mode="a", header=header, index=False, float_format="%.4f")
            means = out.groupby("region")["value"].mean()
            print(f"    {len(out) // len(REGIONS)} months  "
                  + "  ".join(f"{k} {v:.2f} degC" for k, v in means.items())
                  + f"  ({out['weighting'].iloc[0]} weights)", flush=True)

    if not args.out.exists():
        print("nothing extracted")
        return
    df = pd.read_csv(args.out).drop_duplicates(["source_id", "experiment_id", "region", "year", "month"])
    df.to_csv(args.out, index=False, float_format="%.4f")
    print(f"\nWrote {args.out} ({len(df)} rows, {df.source_id.nunique()} models)")

    both = set(df[df.experiment_id == "historical"].source_id) & set(df[df.experiment_id == "ssp245"].source_id)
    print(f"Models with both experiments: {len(both)}")
    print("Weighting used:", df.groupby("weighting").source_id.nunique().to_dict())
    if rejected:
        print(f"\n{len(rejected)} excluded as implausible:")
        for model, experiment, median in rejected:
            print(f"  {model} {experiment}: median {median:.2f} degC")
    if failures:
        print(f"\n{len(failures)} failed:")
        for model, experiment, message in failures:
            print(f"  {model} {experiment}: {message[:100]}")


if __name__ == "__main__":
    main()
