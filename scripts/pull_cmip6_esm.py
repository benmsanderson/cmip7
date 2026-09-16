"""CMIP6 emissions-driven precedent: esm-hist and esm-ssp585, one member per model.

Read lazily from the Pangeo Zarr mirror rather than ESGF: ESGF advertises OPeNDAP
but every dodsC endpoint we tried returns 404, so the brief's "lazy over OPeNDAP"
is not available. Pangeo serves the same data over HTTPS and only the chunks we
touch are transferred, which is what makes reading one model level out of a 3-D
CO2 field affordable.

Pangeo's coverage is narrower than ESGF's: there is no nbp, rtmt or co2mass for
esm-ssp585 at all, and its only co2mass is GFDL-ESM4. Coverage found is printed
at the end.

    uv run scripts/pull_cmip6_esm.py
    uv run scripts/pull_cmip6_esm.py --variables tas fgco2
"""

import argparse
import traceback
from pathlib import Path

import dask
import pandas as pd

from cmip7ref import pangeo
from cmip7ref.experiments import driving, family
from cmip7ref.forcing import PGC_PER_PPM
from cmip7ref.reduce import annual_global_mean, annual_land_sum, compatible, to_ppm

EXPERIMENTS = ["esm-hist", "esm-ssp585", "esm-ssp534-over"]
# variable -> (table_id, reduction)
VARIABLES = {
    "tas": ("Amon", "mean"),
    "rtmt": ("Amon", "mean"),
    "nbp": ("Lmon", "land_sum"),
    "fgco2": ("Omon", "ocean_sum"),
    "co2": ("Amon", "co2"),
    "co2mass": ("Amon", "mass"),
}
# Physically possible range for an annual global series, by variable. Some
# published CMIP6 stores are simply wrong - BCC-CSM2-MR esm-ssp585 fgco2 averages
# -1e-7 kg m-2 s-1, some 450x the real flux and the wrong sign - and a series
# outside these bounds is excluded rather than allowed into a figure.
PLAUSIBLE = {
    "tas": (200.0, 350.0),        # K
    "rtmt": (-20.0, 20.0),        # W m-2
    "nbp": (-20.0, 20.0),         # PgC yr-1
    "fgco2": (-20.0, 20.0),       # PgC yr-1
    "co2": (150.0, 2000.0),       # ppm
    "co2mass": (150.0, 2000.0),   # ppm
}

# Atmospheric mass of dry air, for converting a CO2 burden in kg to ppm.
KG_AIR = 5.1352e18
MW_AIR, MW_CO2 = 28.9647, 44.009


def area_for(ds, like, source_id: str | None = None, ocean: bool = False):
    """Cell area that actually fits ``like``: from the store, else the fx field.

    Only a field whose dimensions match is returned - an atmosphere areacella
    is no use for an ocean field on a curvilinear grid, and silently pairing
    them broadcasts both grids together.
    """
    for name in ("areacella", "areacello", "areacell"):
        if name in ds and compatible(ds[name], like):
            return ds[name]
    if source_id is None:
        return None
    for name in (("areacello", "areacella") if ocean else ("areacella", "areacello")):
        area = pangeo.fx(source_id, name)
        if compatible(area, like):
            return area
    return None


def reduce_store(row, kind: str) -> pd.DataFrame | None:
    """Open one catalog row and reduce it to an annual global series."""
    ds = pangeo.open_store(row.zstore)
    da = ds[row.variable_id].chunk({"time": 12})
    units = da.attrs.get("units", "")

    if kind == "co2":
        da = pangeo.surface_level(da)
    if kind in ("mean", "co2"):
        values, fell_back = annual_global_mean(da, area_for(ds, da, row.source_id), source=row.zstore)
        if kind == "co2":
            values, units = to_ppm(values, units)
    elif kind == "mass":
        # co2mass is a global scalar in kg; convert the burden to ppm.
        annual = da.groupby(da["time"].dt.year).mean()
        values = annual.to_series() * (MW_AIR / MW_CO2) / KG_AIR * 1e6
        units, fell_back = "ppm", False
    else:  # land_sum / ocean_sum, both kg m-2 s-1 integrated over their mask
        area = area_for(ds, da, row.source_id, ocean=(kind == "ocean_sum"))
        if area is None:
            print("    skipped: no cell area available, and a sum cannot use cos-latitude weights")
            return None
        mask = pangeo.fx(row.source_id, "sftlf") if kind == "land_sum" else None
        if not compatible(mask, da):
            # fgco2 is already zero on land, so an unmasked sum is correct there.
            mask = (area * 0 + 100.0).rename("sftlf")
        values, fell_back = annual_land_sum(da, area, mask, source=row.zstore)
        units = "PgC yr-1"

    out = pd.DataFrame(
        {
            "source_id": row.source_id,
            "experiment_id": row.experiment_id,
            "variant_label": row.member_id,
            "grid_label": row.grid_label,
            "variable_id": row.variable_id,
            "year": values.index.astype(int),
            "value": values.to_numpy(),
            "units": units,
            "family": family(row.experiment_id),
            "driving": driving(row.experiment_id),
            "source": "pangeo",
            "mip_era": "CMIP6",
        }
    )
    ds.close()
    out.attrs["cos_latitude_fallback"] = fell_back
    return out


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--variables", nargs="+", default=list(VARIABLES))
    p.add_argument("--experiments", nargs="+", default=EXPERIMENTS)
    p.add_argument("--outdir", type=Path, default=Path("data"))
    args = p.parse_args()

    # One store at a time, in this process: the default threaded scheduler holds
    # several chunks of a high-resolution ocean field at once and gets the job
    # killed. This keeps peak memory to roughly one chunk.
    dask.config.set(scheduler="synchronous")

    args.outdir.mkdir(parents=True, exist_ok=True)
    coverage, written, failures, excluded = [], [], [], []
    for variable in args.variables:
        table, kind = VARIABLES[variable]
        frames = []
        for experiment in args.experiments:
            rows = pangeo.find(experiment, variable, table)
            coverage.append({"variable_id": variable, "experiment_id": experiment, "models": len(rows)})
            for row in rows.itertuples(index=False):
                print(f"  {variable:8s} {experiment:16s} {row.source_id:16s} {row.member_id}", flush=True)
                try:
                    out = reduce_store(row, kind)
                except Exception as exc:
                    failures.append((variable, experiment, row.source_id, f"{type(exc).__name__}: {exc}"))
                    print(f"    FAILED {type(exc).__name__}: {str(exc)[:120]}")
                    traceback.clear_frames(exc.__traceback__)
                    continue
                if out is None:
                    continue
                low, high = PLAUSIBLE[variable]
                median = float(out["value"].median())
                if not low <= median <= high:
                    excluded.append((variable, experiment, row.source_id, median))
                    print(f"    EXCLUDED: median {median:.3g} outside the plausible "
                          f"range {low} to {high} for {variable}")
                    continue
                frames.append(out)

        # Written per variable so that a crash on a later one keeps this one.
        if frames:
            g = pd.concat(frames, ignore_index=True)
            path = args.outdir / f"cmip6_esm_{variable}.csv"
            g.sort_values(["source_id", "experiment_id", "year"]).to_csv(path, index=False, float_format="%.6g")
            print(f"Wrote {path} ({len(g)} rows, {g.source_id.nunique()} models)", flush=True)
            written.append(g)

    if not written:
        print("nothing reduced")
        return
    df = pd.concat(written, ignore_index=True)

    print("\nCoverage found (models per variable and experiment):")
    print(pd.DataFrame(coverage).pivot_table(index="variable_id", columns="experiment_id",
                                             values="models", fill_value=0).to_string())

    print("\nModels with tas in both esm-hist and esm-ssp585:")
    tas = df[df.variable_id == "tas"]
    both = sorted(set(tas[tas.experiment_id == "esm-hist"].source_id) &
                  set(tas[tas.experiment_id == "esm-ssp585"].source_id))
    print(f"  {len(both)}: {', '.join(both)}")

    # The proxy error we quote for the CMIP7 near-surface CO2 series.
    print("\nNear-surface CO2 vs burden-derived CO2 (the CMIP7 proxy error):")
    have_both = set(df[df.variable_id == "co2"].source_id) & set(df[df.variable_id == "co2mass"].source_id)
    if not have_both:
        print("  no model on Pangeo has both co2 and co2mass; offset cannot be quantified here")
    for model in sorted(have_both):
        for experiment in sorted(df[df.source_id == model].experiment_id.unique()):
            sel = df[(df.source_id == model) & (df.experiment_id == experiment)]
            surface = sel[sel.variable_id == "co2"].set_index("year")["value"]
            burden = sel[sel.variable_id == "co2mass"].set_index("year")["value"]
            shared = surface.index.intersection(burden.index)
            if not len(shared):
                continue
            offset = (surface.loc[shared] - burden.loc[shared])
            print(f"  {model} {experiment}: mean offset {offset.mean():+.2f} ppm "
                  f"(range {offset.min():+.2f} to {offset.max():+.2f}, {len(shared)} yr), "
                  f"equivalent to {offset.mean() * PGC_PER_PPM:+.1f} PgC")

    if excluded:
        print(f"\n{len(excluded)} series excluded as non-physical (bad published data):")
        for variable, experiment, model, median in excluded:
            print(f"  {variable} {experiment} {model}: median {median:.4g}")

    if failures:
        print(f"\n{len(failures)} store(s) failed:")
        for variable, experiment, model, message in failures:
            print(f"  {variable} {experiment} {model}: {message[:100]}")


if __name__ == "__main__":
    main()
