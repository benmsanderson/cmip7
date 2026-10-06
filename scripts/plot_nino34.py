"""Recent observed ENSO against the CMIP6 ssp245 distribution: ONI or RONI.

Models and observations are treated identically throughout: the same Nino3.4 and
20N-20S boxes, the same fixed 1991-2020 climatology, the same 3-month running
mean, and for the RONI the same variance rescaling. Observations come from the
gridded ERSSTv5 field rather than CPC's published tables, so they go through the
very same code; doing so reproduces CPC's published RONI to 0.04 degC, which is
the check that this is their recipe and not merely something like it.

``--index oni``  Nino3.4 anomaly. A fixed baseline keeps the background warming
                 in, so the model band climbs through the century.
``--index roni`` Nino3.4 anomaly minus the tropical-mean anomaly, rescaled to the
                 Nino3.4 variance. The tropical warming is differenced out, so
                 this isolates ENSO from the mean state - which is the comparison
                 that survives the models' too-fast Pacific warming.

The band is the spread of ENSO states the ensemble produces at a given time, not
a forecast envelope: model ENSO is not phase-locked to the real world, so only
its width is meaningful, never its sign.

The two distribution panels answer "is this event unusual" properly rather than
loosely. Both compare models and observations **over the same years**, since a
model window containing future warming is not comparable with an observed record
that stops today. And both are restricted to one season, because ENSO is
phase-locked: boreal summer is its low-variance season, so an all-season
distribution understates how unusual a strong JJA value is. The third panel takes
the spring-to-summer change, which is what "rapid onset" actually means.

    uv run scripts/pull_nino34.py && uv run scripts/pull_obs_sst.py
    uv run scripts/plot_nino34.py --index roni
"""

import argparse
from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from cmip7ref.indices import anomalies_fixed, relative_index, running_mean_3  # noqa: E402

# Season centres, as the 3-month running mean labels them.
SEASON_MONTH = {"DJF": 1, "JFM": 2, "FMA": 3, "MAM": 4, "AMJ": 5, "MJJ": 6,
                "JJA": 7, "JAS": 8, "ASO": 9, "SON": 10, "OND": 11, "NDJ": 12}

INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e4e3df"
BAND, BAND_DARK = "#bcd4f0", "#2a78d6"
ENSO_THRESHOLD = 0.5


def smoothed_regions(df: pd.DataFrame, baseline: tuple[int, int]) -> pd.DataFrame:
    """Anomalies and 3-month means for each region, wide by region."""
    out = {}
    for region, g in df.groupby("region"):
        g = g.sort_values(["year", "month"]).drop_duplicates(["year", "month"])
        g = g.assign(anomaly=anomalies_fixed(g, baseline=baseline, column="value"))
        out[region] = g.assign(smooth=running_mean_3(g, column="anomaly")).set_index(["year", "month"])["smooth"]
    wide = pd.DataFrame(out)
    return wide


def build_index(df: pd.DataFrame, index: str, baseline: tuple[int, int], scale_period=None):
    """The chosen index for one model or for the observations, plus its rescale factor."""
    wide = smoothed_regions(df, baseline)
    if index == "oni":
        return wide["nino34"].rename("index"), float("nan")
    if "tropics" not in wide:
        raise SystemExit("the RONI needs a 'tropics' region; re-run scripts/pull_nino34.py")
    mask = None
    if scale_period is not None:
        years = wide.index.get_level_values("year")
        mask = (years >= scale_period[0]) & (years <= scale_period[1])
        mask = pd.Series(mask, index=wide.index)
    series, scale = relative_index(wide["nino34"], wide["tropics"], period=mask)
    return series.rename("index"), scale


def model_index(df: pd.DataFrame, index: str, baseline: tuple[int, int], scale_period=None,
                max_scale: float = 3.0):
    """The index per model, dropping any model the RONI is undefined for.

    The rescaling assumes Nino3.4 holds variance the tropical mean does not. A
    model whose two series are nearly identical has almost none, so the
    difference is noise and the rescale factor explodes - KACE-1-0-G correlates
    its Nino3.4 with its tropical mean at 0.98 and needs a factor of 4.8, which
    would amplify that noise into apparent ENSO swings.
    """
    out, scales, dropped = [], {}, []
    for model, g in df.groupby("source_id"):
        series, scale = build_index(g, index, baseline, scale_period)
        if index == "roni" and scale > max_scale:
            dropped.append((model, scale))
            continue
        scales[model] = scale
        out.append(series.reset_index().assign(source_id=model))
    for model, scale in dropped:
        print(f"  EXCLUDED {model}: rescale factor {scale:.2f} exceeds {max_scale}; its Niño3.4 is "
              "not distinguishable from its tropical mean")
    return pd.concat(out, ignore_index=True), pd.Series(scales, name="scale")


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
    p.add_argument("--index", choices=["oni", "roni"], default="roni")
    p.add_argument("--data", type=Path, default=Path("data/cmip6_sst_regions.csv"))
    p.add_argument("--obs", type=Path, default=Path("data/obs_sst_regions.csv"))
    p.add_argument("--published", type=Path, default=Path("data/obs_enso_indices.csv"))
    p.add_argument("--baseline", nargs=2, type=int, default=[1991, 2020], metavar=("START", "END"))
    p.add_argument("--scale-period", nargs=2, type=int, default=None, metavar=("START", "END"),
                   help="years the RONI variance rescaling is estimated over (default: all)")
    p.add_argument("--years", nargs=2, type=int, default=[1950, 2060], metavar=("START", "END"))
    p.add_argument("--season", default="JJA", choices=[*SEASON_MONTH, "all"],
                   help="season the distribution panels use; ENSO is phase-locked, so this matters")
    p.add_argument("--onset-from", default="MAM", choices=list(SEASON_MONTH),
                   help="season the onset-rate panel measures the change from")
    p.add_argument("--dist-years", nargs=2, type=int, default=None, metavar=("START", "END"),
                   help="years both distributions use (default: the observed record, matched)")
    p.add_argument("--pool-years", type=int, default=11)
    p.add_argument("--min-models", type=int, default=10)
    p.add_argument("--max-scale", type=float, default=3.0,
                   help="drop models whose RONI rescale factor exceeds this (observed is 1.26)")
    p.add_argument("--out", type=Path, default=None)
    p.add_argument("--csv", type=Path, default=None)
    args = p.parse_args()

    baseline = tuple(args.baseline)
    scale_period = tuple(args.scale_period) if args.scale_period else None
    out_path = args.out or Path(f"figures/{args.index}_context.png")
    csv_path = args.csv or Path(f"data/cmip6_{args.index}.csv")
    label = {"oni": "Niño3.4 anomaly (ONI)", "roni": "Relative Niño3.4 (RONI)"}[args.index]

    models, scales = model_index(pd.read_csv(args.data), args.index, baseline, scale_period, args.max_scale)
    models.to_csv(csv_path, index=False, float_format="%.4f")
    print(f"Wrote {csv_path} ({models.source_id.nunique()} models, {args.index})")
    if args.index == "roni":
        print(f"Variance rescale factor across models: median {scales.median():.2f} "
              f"[{scales.min():.2f}, {scales.max():.2f}]")

    obs_regions = pd.read_csv(args.obs)
    obs_source = str(obs_regions["source"].iloc[0]) if "source" in obs_regions else "observations"
    obs_series, obs_scale = build_index(obs_regions, args.index, baseline, scale_period)
    obs = obs_series.reset_index().rename(columns={"index": "value"})
    obs["time"] = obs.year + (obs.month - 0.5) / 12
    if args.index == "roni":
        print(f"Observed rescale factor: {obs_scale:.2f}")

    published = pd.read_csv(args.published)
    column = "cpc_oni" if args.index == "oni" else "cpc_roni_v6"
    check = obs.merge(published[["year", "month", "season", column]].dropna(), on=["year", "month"])
    print(f"Ours vs CPC published {column}: corr {check.value.corr(check[column]):.4f}, "
          f"mean |diff| {(check.value - check[column]).abs().mean():.3f} °C")

    valid = models.dropna(subset=["index"])
    half = args.pool_years // 2
    rows = []
    for year in range(int(valid.year.min()) + half, int(valid.year.max()) - half + 1):
        block = valid[valid.year.between(year - half, year + half)]
        if block.source_id.nunique() < args.min_models:
            continue
        rows.append({"time": year, "n": block.source_id.nunique(),
                     "p05": block["index"].quantile(0.05), "p25": block["index"].quantile(0.25),
                     "p50": block["index"].quantile(0.50),
                     "p75": block["index"].quantile(0.75), "p95": block["index"].quantile(0.95)})
    spread = pd.DataFrame(rows)
    if spread.empty:
        raise SystemExit(f"no window has {args.min_models}+ models; lower --min-models")

    peak = check.loc[check[check.year >= 2024].value.idxmax()]

    # Distributions compare the two over the SAME years: a model window holding
    # future warming is not comparable with an observed record that stops today.
    lo, hi = tuple(args.dist_years) if args.dist_years else (int(obs.year.min()), int(obs.year.max()))
    lo = max(lo, int(valid.year.min()))
    season_month = SEASON_MONTH.get(args.season)
    in_window = lambda d: d[d.year.between(lo, hi)]  # noqa: E731
    by_season = (lambda d: d[d.month == season_month]) if season_month else (lambda d: d)

    window = by_season(in_window(valid))
    obs_window = by_season(in_window(obs)).dropna(subset=["value"])
    peak_value = float(peak.value)

    # Onset: the change from one season to the chosen one, within the same year.
    onset_from = SEASON_MONTH[args.onset_from]
    def onset(df, value_column):
        wide = df.pivot_table(index=[c for c in ("source_id", "year") if c in df], columns="month",
                              values=value_column)
        if season_month is None or not {onset_from, season_month} <= set(wide.columns):
            return pd.Series(dtype=float)
        return (wide[season_month] - wide[onset_from]).dropna()

    model_onset = onset(valid[valid.year.between(lo, hi)], "index")
    obs_onset_all = onset(obs.assign(source_id="obs"), "value")
    obs_onset_years = pd.Index(obs_onset_all.index.get_level_values("year"))
    obs_onset = obs_onset_all[(obs_onset_years >= lo) & (obs_onset_years <= hi)]
    peak_onset = (float(obs_onset_all.xs(int(peak.year), level="year").iloc[0])
                  if len(obs_onset_all) and int(peak.year) in set(obs_onset_years) else float("nan"))

    fig, (ax, ax2, ax3) = plt.subplots(
        1, 3, figsize=(16, 4.6), gridspec_kw={"width_ratios": [2.3, 1, 1]}
    )

    _style(ax)
    ax.fill_between(spread.time, spread.p05, spread.p95, color=BAND, alpha=0.55, linewidth=0,
                    label=f"CMIP6 ssp245, 5–95% ({int(spread.n.median())} models)")
    ax.fill_between(spread.time, spread.p25, spread.p75, color=BAND_DARK, alpha=0.28, linewidth=0,
                    label="CMIP6 ssp245, 25–75%")
    ax.plot(spread.time, spread.p50, color=BAND_DARK, linewidth=1.2, label="CMIP6 median")
    for level in (-ENSO_THRESHOLD, ENSO_THRESHOLD):
        ax.axhline(level, color=MUTED, linewidth=0.6, linestyle=(0, (4, 3)))
    ax.axhline(0, color=MUTED, linewidth=0.8)
    ax.plot(obs.time, obs.value, color=INK, linewidth=1.1, label=f"Observed ({obs_source})")

    ptime = peak.year + (peak.month - 0.5) / 12
    ax.annotate(f"{peak.season} {int(peak.year)}  {peak.value:+.2f}", (ptime, peak.value), xytext=(8, 2),
                textcoords="offset points", fontsize=9, color=INK)
    ax.plot([ptime], [peak.value], "o", color=INK, markersize=4)
    ax.set_xlim(*args.years)
    ax.set_ylabel(f"{label} (°C)\nanomaly from {baseline[0]}–{baseline[1]}, 3-month mean",
                  fontsize=9, color=INK)
    title = ("Observed ENSO against the CMIP6 range, mean-state warming removed"
             if args.index == "roni" else "Observed Niño3.4 against the CMIP6 range, same baseline")
    ax.set_title(title, fontsize=11, color=INK, loc="left")
    ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK, ncol=2)

    season_label = args.season if season_month else "all seasons"

    def distribution(axis, model_values, obs_values, marker, xlabel, title):
        _style(axis)
        axis.hist(model_values, bins=34, density=True, color=BAND, edgecolor=BAND_DARK, linewidth=0.4,
                  label=f"CMIP6 ({len(model_values)})")
        axis.hist(obs_values, bins=18, density=True, histtype="step", color=INK, linewidth=1.2,
                  label=f"Observed ({len(obs_values)})")
        axis.axvline(marker, color=INK, linewidth=1.4)
        pct = (model_values < marker).mean() * 100
        axis.annotate(f"{int(peak.year)}  {marker:+.2f} °C\n{pct:.0f}th pct of CMIP6",
                      (marker, axis.get_ylim()[1] * 0.72), xytext=(8, 0), textcoords="offset points",
                      fontsize=8.5, color=INK, ha="left", va="center")
        axis.set_xlabel(xlabel, fontsize=9, color=INK)
        axis.set_ylabel("density", fontsize=9, color=INK)
        axis.set_title(title, fontsize=10.5, color=INK, loc="left")
        axis.legend(frameon=False, fontsize=8, labelcolor=INK, loc="upper left")
        return pct

    pct = distribution(ax2, window["index"], obs_window.value, peak_value,
                       f"{label} (°C)", f"{season_label} values, {lo}–{hi}")
    distribution(ax3, model_onset, obs_onset, peak_onset,
                 f"{args.onset_from} → {args.season} change (°C)",
                 f"{args.onset_from}→{args.season} onset, {lo}–{hi}") if len(model_onset) else None

    note = ("RONI subtracts the 20°N–20°S mean anomaly and rescales to the Niño3.4 variance, so the "
            "background warming is differenced out of both models and observations."
            if args.index == "roni" else
            "Models and observations share one baseline, so the band includes the background Pacific warming.")
    fig.text(0.005, -0.08, note + " The band is the ensemble's spread of ENSO states, not a forecast "
             "envelope: its width is meaningful, its sign is not. Both distributions use the same years for "
             f"models and observations, and the same season: ENSO is phase-locked, and {season_label} is not "
             "interchangeable with the annual spread.", fontsize=8, color=MUTED)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    print(f"Wrote {out_path}")

    print(f"\nObserved peak since 2024: {peak.season} {int(peak.year)} = {peak_value:+.2f} °C"
          f"   (CPC published {peak[column]:+.2f})")
    print(f"  {season_label} values, {lo}-{hi}, models and observations over the same years:")
    print(f"    {pct:.1f}th percentile of CMIP6 ({len(window)} model values), "
          f"{(window['index'] >= peak_value).mean() * 100:.2f}% at or above it")
    all_season = in_window(valid)["index"]
    print(f"    for contrast, against all seasons: {(all_season < peak_value).mean() * 100:.1f}th percentile "
          "- the annual spread understates a summer event, because ENSO is phase-locked")
    per_model = window.groupby("source_id")["index"].max()
    print(f"    models reaching it in {lo}-{hi}: {(per_model >= peak_value).sum()} of {len(per_model)}")
    obs_rank = int((obs_window.value > peak_value).sum()) + 1
    print(f"    rank in the observed record: {obs_rank} of {len(obs_window)} {season_label} values")

    if len(model_onset):
        pct_onset = (model_onset < peak_onset).mean() * 100
        rank_onset = int((obs_onset > peak_onset).sum()) + 1  # 1 = fastest on record
        print(f"\n  {args.onset_from}->{args.season} onset, {lo}-{hi}:")
        print(f"    {int(peak.year)} observed {peak_onset:+.2f} °C -> {pct_onset:.1f}th percentile of CMIP6 "
              f"(median {model_onset.median():+.2f}, 95th {model_onset.quantile(0.95):+.2f})")
        print(f"    rank in the observed record: {rank_onset} of {len(obs_onset)}")

    print("\n  Like-for-like medians, models vs observations over identical years:")
    for y0, y1 in ((1950, 2014), (1950, int(obs.year.max())), (2011, int(obs.year.max()))):
        mm = valid[valid.year.between(y0, y1)]["index"]
        oo = obs[obs.year.between(y0, y1)].value.dropna()
        if mm.empty or len(oo) < 24:
            continue
        print(f"    {y0}-{y1}: models {mm.median():+.2f} (sd {mm.std():.2f}) | "
              f"observed {oo.median():+.2f} (sd {oo.std():.2f}) | difference {oo.median() - mm.median():+.2f}")

    def trend(df, column_name, y0, y1):
        import numpy as np
        s = df[df.year.between(y0, y1)].dropna(subset=[column_name])
        if len(s) < 60:
            return float("nan")
        x = (s.year + (s.month - 0.5) / 12).to_numpy()
        return float(np.polyfit(x, s[column_name].to_numpy(), 1)[0] * 10)

    print(f"\n{label} trend (°C per decade), observed vs models:")
    for y0, y1 in ((1950, 2026), (1980, 2026)):
        ot = trend(obs, "value", y0, y1)
        mt = valid.groupby("source_id").apply(lambda g: trend(g, "index", y0, y1), include_groups=False).dropna()
        print(f"  {y0}-{y1}: observed {ot:+.3f} | models median {mt.median():+.3f} "
              f"[{mt.quantile(0.05):+.3f}, {mt.quantile(0.95):+.3f}] | "
              f"{(mt > ot).sum()} of {len(mt)} models warm faster")

    print(f"\n{label}, median and spread by period:")
    for y0, y1 in ((1950, 1990), (1991, 2020), (2021, 2040), (2041, 2060)):
        s = valid[valid.year.between(y0, y1)]
        o = obs[obs.year.between(y0, y1)]
        if s.empty:
            continue
        extra = f"   observed median {o.value.median():+.2f}, sd {o.value.std():.2f}" if len(o) > 24 else ""
        print(f"  {y0}-{y1}: models median {s['index'].median():+.2f}, sd {s['index'].std():.2f}{extra}")


if __name__ == "__main__":
    main()
