"""Plot global-mean temperature for historical and ScenarioMIP scenarios.

Only models with historical and every requested scenario are plotted.

    uv run scripts/plot_gmt.py                      # historical + VL + H
    uv run scripts/plot_gmt.py --scenarios vl m h   # other scenarios
    uv run scripts/plot_gmt.py --mip-era CMIP6 --scenarios ssp126 ssp585 --models UKESM1-0-LL
"""

import argparse
from pathlib import Path

from cmip7ref import RefClient, anomalies, fetch_global_mean, models_with
from cmip7ref.client import DEFAULT_CACHE_DIR
from cmip7ref.plotting import plot_trajectories


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--scenarios", nargs="+", default=["vl", "h"])
    p.add_argument("--mip-era", default="CMIP7", help="CMIP7 or CMIP6")
    p.add_argument("--models", nargs="+", help="restrict to these source_ids")
    p.add_argument("--baseline", nargs=2, type=int, default=[1850, 1900], metavar=("START", "END"))
    p.add_argument("--out", type=Path, default=Path("figures/gmt_trajectories.png"))
    p.add_argument("--csv", type=Path, default=Path("figures/gmt_trajectories.csv"))
    p.add_argument("--no-cache", action="store_true", help="always refetch from the API")
    args = p.parse_args()

    families = ["historical", *args.scenarios]
    with RefClient(cache_dir=None if args.no_cache else DEFAULT_CACHE_DIR) as client:
        df = fetch_global_mean(client, variable_id="tas", mip_era=args.mip_era)

    models = models_with(df, families)
    if args.models:
        models = [m for m in models if m in args.models]
    print(f"Models with {' + '.join(families)}: {models or 'none'}")
    if not models:
        return

    df = anomalies(df[df["source_id"].isin(models) & df["family"].isin(families)], baseline=tuple(args.baseline))

    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.csv, index=False)
    y0, y1 = args.baseline
    fig = plot_trajectories(
        df,
        families=families,
        models=models,
        ylabel=f"Global mean surface air temperature\nchange from {y0}–{y1} (°C)",
        title=f"{args.mip_era} global mean temperature (Climate REF)",
    )
    fig.savefig(args.out, dpi=200)
    print(f"Wrote {args.out} and {args.csv}")


if __name__ == "__main__":
    main()
