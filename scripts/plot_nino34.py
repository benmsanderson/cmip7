"""Recent observed Nino3.4 against the CMIP6 ssp245 distribution.

Models and observations are processed identically: a centred 30-year running
monthly climatology is removed, then a 3-month running mean applied. That is the
continuous form of CPC's ONI, whose base period moves every five years, and
re-deriving the observed anomaly this way reproduces CPC's published ONI to
0.05 degC.

The model band is the spread of ENSO states the ensemble produces at a given
time. It is not a forecast envelope: model ENSO is not phase-locked to the real
world, so only the width of the band is meaningful, never its sign.

    uv run scripts/pull_nino34.py && uv run scripts/plot_nino34.py
"""

import argparse
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from cmip7ref.indices import anomalies_running, running_mean_3, window_complete  # noqa: E402
from cmip7ref.observations import oni  # noqa: E402

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BAND, BAND_DARK = "#bcd4f0", "#2a78d6"
ENSO_THRESHOLD = 0.5


def model_oni(df: pd.DataFrame, window: int) -> pd.DataFrame:
    """Per model: splice the experiments, remove a running climatology, smooth."""
    out = []
    for model, g in df.groupby("source_id"):
        g = g.sort_values(["year", "month"]).drop_duplicates(["year", "month"])
        g = g.assign(anomaly=anomalies_running(g, window_years=window, column="value"))
        g = g.assign(oni=running_mean_3(g, column="anomaly"))
        g = g.assign(window_complete=window_complete(g, window_years=window, column="value"))
        out.append(g[["source_id", "year", "month", "value", "anomaly", "oni", "window_complete"]])
    return pd.concat(out, ignore_index=True)


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
    p.add_argument("--window", type=int, default=30, help="running climatology length, years")
    # The band ends ~15 years before the model data does, because a centred
    # 30-year climatology needs that much run-off; pull data past 2060 to extend it.
    p.add_argument("--years", nargs=2, type=int, default=[1950, 2045], metavar=("START", "END"))
    p.add_argument("--dist-years", nargs=2, type=int, default=[2006, 2041],
                   metavar=("START", "END"), help="window for the distribution panel")
    p.add_argument("--pool-years", type=int, default=11,
                   help="centred window, in years, over which the ensemble distribution is pooled")
    p.add_argument("--min-models", type=int, default=10,
                   help="drop time steps covered by fewer models than this")
    p.add_argument("--out", type=Path, default=Path("figures/nino34_context.png"))
    p.add_argument("--csv", type=Path, default=Path("data/cmip6_nino34_oni.csv"))
    args = p.parse_args()

    models = model_oni(pd.read_csv(args.data), args.window)
    models.to_csv(args.csv, index=False, float_format="%.4f")
    print(f"Wrote {args.csv} ({models.source_id.nunique()} models)")

    obs = oni()
    # Process the observations exactly as the models are processed, so the
    # comparison is like for like, and keep CPC's official ONI alongside.
    obs["own"] = anomalies_running(obs, window_years=args.window, column="sst")
    obs["time"] = obs.year + (obs.month - 0.5) / 12
    models["time"] = models.year + (models.month - 0.5) / 12

    # Spread of ENSO states across the ensemble. Percentiles of 41 values at a
    # single month are themselves noisy, so each year pools every model and every
    # month within a centred window - the distribution moves slowly, the sampling
    # noise does not.
    # Only years with a complete climatology window: a truncated one leaves part
    # of the warming trend in the anomaly and would widen the band spuriously.
    valid = models.dropna(subset=["oni"])
    valid = valid[valid.window_complete]
    half = args.pool_years // 2
    years = range(int(valid.year.min()) + half, int(valid.year.max()) - half + 1)
    rows = []
    for year in years:
        block = valid[valid.year.between(year - half, year + half)]
        if block.source_id.nunique() < args.min_models:
            continue
        rows.append({
            "time": year, "n": block.source_id.nunique(),
            "p05": block.oni.quantile(0.05), "p25": block.oni.quantile(0.25),
            "p75": block.oni.quantile(0.75), "p95": block.oni.quantile(0.95),
        })
    spread = pd.DataFrame(rows)
    if spread.empty:
        raise SystemExit(f"no window has {args.min_models}+ models; lower --min-models")

    fig, (ax, ax2) = plt.subplots(
        1, 2, figsize=(14, 4.8), gridspec_kw={"width_ratios": [2.6, 1]}
    )

    # -- time series -------------------------------------------------------
    _style(ax)
    ax.fill_between(spread.time, spread.p05, spread.p95, color=BAND, alpha=0.55, linewidth=0,
                    label=f"CMIP6 ssp245, 5–95% ({int(spread.n.median())} models, "
                          f"{args.pool_years}-year pooling)")
    ax.fill_between(spread.time, spread.p25, spread.p75, color=BAND_DARK, alpha=0.28, linewidth=0,
                    label="CMIP6 ssp245, 25–75%")
    for level in (-ENSO_THRESHOLD, ENSO_THRESHOLD):
        ax.axhline(level, color=MUTED, linewidth=0.6, linestyle=(0, (4, 3)))
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.plot(obs.time, obs.own, color=INK, linewidth=1.1,
            label="Observed Niño3.4, processed as the models")

    peak = obs.loc[obs[obs.year >= 2024].own.idxmax()]
    ax.annotate(f"{peak.season} {int(peak.year)}  {peak.own:+.2f}\n(CPC ONI {peak.anomaly:+.2f})",
                (peak.year + (peak.month - 0.5) / 12, peak.own), xytext=(8, 2),
                textcoords="offset points", fontsize=9, color=INK)
    ax.plot([peak.year + (peak.month - 0.5) / 12], [peak.own], "o", color=INK, markersize=4)
    ax.set_xlim(*args.years)
    ax.set_ylabel("Niño3.4 anomaly (°C)\n30-year running base, 3-month mean", fontsize=9, color=INK)
    ax.set_title("Observed Niño3.4 against the CMIP6 range", fontsize=11, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK)

    # -- distribution ------------------------------------------------------
    _style(ax2)
    lo, hi = args.dist_years
    window = valid[valid.year.between(lo, hi)]
    ax2.hist(window.oni, bins=60, density=True, color=BAND, edgecolor=BAND_DARK, linewidth=0.4,
             label=f"CMIP6 ssp245 {lo}–{hi}")
    obs_window = obs[obs.year.between(1950, 2026)].dropna(subset=["own"])
    ax2.hist(obs_window.own, bins=60, density=True, histtype="step", color=INK, linewidth=1.2,
             label="Observed 1950–2026")
    ax2.axvline(peak.own, color=INK, linewidth=1.4)
    pct = (window.oni < peak.own).mean() * 100
    # Annotate below the legend, on whichever side of the line has room.
    ax2.annotate(f"{peak.season} {int(peak.year)}  {peak.own:+.2f} °C\n{pct:.1f}th pct of CMIP6",
                 (peak.own, ax2.get_ylim()[1] * 0.70), xytext=(10, 0), textcoords="offset points",
                 fontsize=8.5, color=INK, ha="left", va="center")
    ax2.set_xlabel("Niño3.4 anomaly (°C)", fontsize=9, color=INK)
    ax2.set_ylabel("density", fontsize=9, color=INK)
    ax2.set_title("Distribution of monthly values", fontsize=11, color=INK, loc="left")
    ax2.legend(frameon=False, fontsize=8, labelcolor=INK, loc="upper left")

    fig.text(0.005, -0.04,
             "The band is the spread of ENSO states across models at each time, not a forecast envelope: "
             "model ENSO is not phase-locked to observations, so its width is meaningful and its sign is not.",
             fontsize=8, color=MUTED)
    fig.tight_layout()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.out, dpi=200, bbox_inches="tight")
    print(f"Wrote {args.out}")

    # -- numbers for the slide --------------------------------------------
    print(f"\nObserved peak since 2024: {peak.season} {int(peak.year)} = {peak.own:+.2f} °C "
          f"(CPC's published ONI: {peak.anomaly:+.2f}; the gap is the truncated "
          f"climatology window at the end of the record)")
    print(f"  percentile within CMIP6 {lo}-{hi} monthly values: {pct:.2f}")
    exceed = (window.oni >= peak.own).mean()
    print(f"  CMIP6 months at or above it: {exceed * 100:.2f}%  "
          f"(about one month in {1 / exceed:.0f})" if exceed else "  never exceeded in CMIP6")
    per_model = window.groupby("source_id")["oni"].max()
    print(f"  models whose {lo}-{hi} maximum exceeds it: {(per_model >= peak.own).sum()} of {len(per_model)}")
    record = obs.loc[obs.own.idxmax()]
    print(f"\nObserved record: {record.season} {int(record.year)} = {record.own:+.2f} °C "
          f"(CPC ONI {record.anomaly:+.2f})")
    print("\nCMIP6 ONI standard deviation by period (ENSO amplitude):")
    for y0, y1 in ((1950, 1990), (1990, 2010), (2010, 2041)):
        s = valid[valid.year.between(y0, y1)]
        o = obs[obs.year.between(y0, y1)]
        extra = f"   observed {o.own.std():.2f}" if len(o) > 24 else ""
        print(f"  {y0}-{y1}: models {s.oni.std():.2f} °C{extra}")


if __name__ == "__main__":
    main()
