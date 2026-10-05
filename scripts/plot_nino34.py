"""Recent observed Nino3.4 against the CMIP6 ssp245 distribution.

The key figure is an apples-to-apples comparison: models and observations are
both measured against the **same fixed 1991-2020 climatology**, which is also
CPC's current operational base, so the observed current event reproduces their
published ONI (+2.14 here against +2.16 published).

A fixed base keeps the warming trend in the anomaly, deliberately. The model
band therefore rises through the century, and that is the point: it shows the
background Pacific warming that a future El Nino is measured on top of. For the
ENSO-only view, ``--scheme cpc`` switches both sides to CPC's shifting
base-period scheme, which removes the trend.

The band is the spread of ENSO states the ensemble produces at a given time. It
is not a forecast envelope: model ENSO is not phase-locked to the real world, so
only the width of the band is meaningful, never its sign.

    uv run scripts/pull_nino34.py && uv run scripts/plot_nino34.py
    uv run scripts/plot_nino34.py --scheme cpc     # ENSO without the trend
"""

import argparse
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from cmip7ref.indices import anomalies_cpc_blocks, anomalies_fixed, running_mean_3  # noqa: E402
from cmip7ref.observations import oni  # noqa: E402

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BAND, BAND_DARK = "#bcd4f0", "#2a78d6"
ENSO_THRESHOLD = 0.5


def anomalise(df: pd.DataFrame, column: str, scheme: str, baseline: tuple[int, int]) -> pd.DataFrame:
    """Add ``anomaly`` and ``base_centred`` under the chosen scheme."""
    if scheme == "fixed":
        return df.assign(anomaly=anomalies_fixed(df, baseline=baseline, column=column), base_centred=True)
    anomaly, centred = anomalies_cpc_blocks(df, column=column)
    return df.assign(anomaly=anomaly, base_centred=centred)


def model_oni(df: pd.DataFrame, scheme: str, baseline: tuple[int, int]) -> pd.DataFrame:
    """Per model: splice the experiments, remove the climatology, smooth."""
    out = []
    for _, g in df.groupby("source_id"):
        g = g.sort_values(["year", "month"]).drop_duplicates(["year", "month"])
        g = anomalise(g, "value", scheme, baseline)
        g = g.assign(oni=running_mean_3(g, column="anomaly"))
        out.append(g[["source_id", "year", "month", "value", "anomaly", "oni", "base_centred"]])
    return pd.concat(out, ignore_index=True)


def observed(scheme: str, baseline: tuple[int, int]) -> pd.DataFrame:
    """Observed Nino3.4 through the same scheme, with CPC's own ONI kept beside it."""
    # CPC's published ONI arrives as `anomaly`; keep it under its own name before
    # our own anomaly takes that column.
    obs = oni().rename(columns={"anomaly": "cpc_oni"})
    obs = anomalise(obs, "sst", scheme, baseline).rename(columns={"anomaly": "own"})
    obs["time"] = obs.year + (obs.month - 0.5) / 12
    return obs


def _style(ax):
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=9, width=0.8)
    ax.grid(color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data", type=Path, default=Path("data/cmip6_nino34.csv"))
    p.add_argument("--scheme", choices=["fixed", "cpc"], default="fixed",
                   help="fixed 1991-2020 base (default, keeps the trend) or CPC's shifting blocks")
    p.add_argument("--baseline", nargs=2, type=int, default=[1991, 2020], metavar=("START", "END"))
    p.add_argument("--years", nargs=2, type=int, default=[1950, 2060], metavar=("START", "END"))
    p.add_argument("--dist-halfwidth", type=int, default=15,
                   help="half-width, in years, of the model window compared against the observed peak")
    p.add_argument("--pool-years", type=int, default=11,
                   help="centred window, in years, over which the ensemble distribution is pooled")
    p.add_argument("--min-models", type=int, default=10)
    p.add_argument("--out", type=Path, default=Path("figures/nino34_context.png"))
    p.add_argument("--csv", type=Path, default=Path("data/cmip6_nino34_oni.csv"))
    args = p.parse_args()

    baseline = tuple(args.baseline)
    models = model_oni(pd.read_csv(args.data), args.scheme, baseline)
    models.to_csv(args.csv, index=False, float_format="%.4f")
    print(f"Wrote {args.csv} ({models.source_id.nunique()} models, {args.scheme} scheme)")

    obs = observed(args.scheme, baseline)
    valid = models.dropna(subset=["oni"])
    if args.scheme == "cpc":
        valid = valid[valid.base_centred]  # a fallback base leaves trend behind

    # Percentiles of 41 values at a single month are noisy, so each year pools
    # every model and month within a centred window.
    half = args.pool_years // 2
    rows = []
    for year in range(int(valid.year.min()) + half, int(valid.year.max()) - half + 1):
        block = valid[valid.year.between(year - half, year + half)]
        if block.source_id.nunique() < args.min_models:
            continue
        rows.append({"time": year, "n": block.source_id.nunique(),
                     "p05": block.oni.quantile(0.05), "p25": block.oni.quantile(0.25),
                     "p50": block.oni.quantile(0.50),
                     "p75": block.oni.quantile(0.75), "p95": block.oni.quantile(0.95)})
    spread = pd.DataFrame(rows)
    if spread.empty:
        raise SystemExit(f"no window has {args.min_models}+ models; lower --min-models")

    peak = obs.loc[obs[obs.year >= 2024].own.idxmax()]
    lo, hi = int(peak.year) - args.dist_halfwidth, int(peak.year) + args.dist_halfwidth
    window = valid[valid.year.between(lo, hi)]

    fig, (ax, ax2) = plt.subplots(1, 2, figsize=(14, 4.8), gridspec_kw={"width_ratios": [2.6, 1]})

    _style(ax)
    ax.fill_between(spread.time, spread.p05, spread.p95, color=BAND, alpha=0.55, linewidth=0,
                    label=f"CMIP6 ssp245, 5–95% ({int(spread.n.median())} models)")
    ax.fill_between(spread.time, spread.p25, spread.p75, color=BAND_DARK, alpha=0.28, linewidth=0,
                    label="CMIP6 ssp245, 25–75%")
    ax.plot(spread.time, spread.p50, color=BAND_DARK, linewidth=1.2, label="CMIP6 median")
    for level in (-ENSO_THRESHOLD, ENSO_THRESHOLD):
        ax.axhline(level, color=MUTED, linewidth=0.6, linestyle=(0, (4, 3)))
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.plot(obs.time, obs.own, color=INK, linewidth=1.1, label="Observed (CPC ERSSTv5)")

    ptime = peak.year + (peak.month - 0.5) / 12
    ax.annotate(f"{peak.season} {int(peak.year)}  {peak.own:+.2f}", (ptime, peak.own), xytext=(8, 2),
                textcoords="offset points", fontsize=9, color=INK)
    ax.plot([ptime], [peak.own], "o", color=INK, markersize=4)
    ax.set_xlim(*args.years)
    base_label = (f"anomaly from {baseline[0]}–{baseline[1]}" if args.scheme == "fixed"
                  else "CPC base-period scheme")
    ax.set_ylabel(f"Niño3.4 (°C)\n{base_label}, 3-month mean", fontsize=9, color=INK)
    ax.set_title("Observed Niño3.4 against the CMIP6 range, same baseline", fontsize=11, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK, ncol=2)

    _style(ax2)
    ax2.hist(window.oni, bins=60, density=True, color=BAND, edgecolor=BAND_DARK, linewidth=0.4,
             label=f"CMIP6 ssp245 {lo}–{hi}")
    ax2.hist(obs[obs.year.between(1991, 2026)].own.dropna(), bins=40, density=True, histtype="step",
             color=INK, linewidth=1.2, label="Observed 1991–2026")
    ax2.axvline(peak.own, color=INK, linewidth=1.4)
    pct = (window.oni < peak.own).mean() * 100
    ax2.annotate(f"{peak.season} {int(peak.year)}  {peak.own:+.2f} °C\n{pct:.1f}th pct of CMIP6",
                 (peak.own, ax2.get_ylim()[1] * 0.70), xytext=(10, 0), textcoords="offset points",
                 fontsize=8.5, color=INK, ha="left", va="center")
    ax2.set_xlabel("Niño3.4 anomaly (°C)", fontsize=9, color=INK)
    ax2.set_ylabel("density", fontsize=9, color=INK)
    ax2.set_title(f"Distribution, {lo}–{hi}", fontsize=11, color=INK, loc="left")
    ax2.legend(frameon=False, fontsize=8, labelcolor=INK, loc="upper left")

    note = ("Models and observations share one baseline, so the model band includes the background Pacific "
            "warming a future El Niño sits on top of. The band is the ensemble's spread of ENSO states, "
            "not a forecast envelope: its width is meaningful, its sign is not.")
    fig.text(0.005, -0.06, note, fontsize=8, color=MUTED)
    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=200, bbox_inches="tight")
    print(f"Wrote {args.out}")

    print(f"\nObserved peak since 2024: {peak.season} {int(peak.year)} = {peak.own:+.2f} °C"
          f"   (CPC published ONI {peak.cpc_oni:+.2f})")
    print(f"  against CMIP6 {lo}-{hi}: {pct:.1f}th percentile, "
          f"{(window.oni >= peak.own).mean() * 100:.2f}% of model months at or above it")
    per_model = window.groupby("source_id")["oni"].max()
    print(f"  models reaching it in {lo}-{hi}: {(per_model >= peak.own).sum()} of {len(per_model)}")

    # With a shared baseline the warming trend is retained, so it can be compared.
    def trend(df, column, y0, y1):
        s = df[df.year.between(y0, y1)].dropna(subset=[column])
        if len(s) < 60:
            return float("nan")
        x = (s.year + (s.month - 0.5) / 12).to_numpy()
        return float(pd.Series(s[column]).pipe(lambda v: __import__("numpy").polyfit(x, v.to_numpy(), 1)[0]) * 10)

    if args.scheme == "fixed":
        print("\nNiño3.4 warming trend (°C per decade), observed vs models:")
        for y0, y1 in ((1950, 2026), (1980, 2026), (1995, 2026)):
            ot = trend(obs, "own", y0, y1)
            mt = valid.groupby("source_id").apply(lambda g: trend(g, "oni", y0, y1),
                                                  include_groups=False).dropna()
            print(f"  {y0}-{y1}: observed {ot:+.3f} | models median {mt.median():+.3f} "
                  f"[{mt.quantile(0.05):+.3f}, {mt.quantile(0.95):+.3f}] | "
                  f"{(mt > ot).sum()} of {len(mt)} models warm faster")

    print("\nCMIP6 Niño3.4, median and spread by period (same baseline):")
    for y0, y1 in ((1950, 1990), (1991, 2020), (2021, 2040), (2041, 2060)):
        s = valid[valid.year.between(y0, y1)]
        o = obs[obs.year.between(y0, y1)]
        if s.empty:
            continue
        extra = f"   observed median {o.own.median():+.2f}, sd {o.own.std():.2f}" if len(o) > 24 else ""
        print(f"  {y0}-{y1}: models median {s.oni.median():+.2f}, sd {s.oni.std():.2f}{extra}")


if __name__ == "__main__":
    main()
