"""Plot helpers."""

from __future__ import annotations

import math
from collections.abc import Sequence

import matplotlib.pyplot as plt
import pandas as pd

# Historical is context, so it gets neutral ink. Scenarios use fixed
# categorical slots so a scenario keeps its colour in every figure.
FAMILY_STYLE = {
    "historical": {"color": "#52514e", "label": "historical"},
    "vl": {"color": "#2a78d6", "label": "VL"},
    "h": {"color": "#eb6834", "label": "H"},
    "l": {"color": "#1baf7a", "label": "L"},
    "ml": {"color": "#4a3aa7", "label": "ML"},
    "m": {"color": "#eda100", "label": "M"},
    "ln": {"color": "#e87ba4", "label": "LN"},
    # CMIP6 SSPs, ordered cold-to-hot like the CMIP7 scenarios above
    "ssp126": {"color": "#2a78d6", "label": "SSP1-2.6"},
    "ssp245": {"color": "#1baf7a", "label": "SSP2-4.5"},
    "ssp370": {"color": "#eda100", "label": "SSP3-7.0"},
    "ssp585": {"color": "#eb6834", "label": "SSP5-8.5"},
}

INK = "#0b0b0b"
MUTED = "#52514e"
GRID = "#e4e3df"


def _style_axes(ax: plt.Axes) -> None:
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(MUTED)
        ax.spines[side].set_linewidth(0.8)
    ax.tick_params(colors=MUTED, labelsize=9, width=0.8)
    ax.grid(axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.axhline(0, color=MUTED, linewidth=0.8)


def plot_trajectories(
    df: pd.DataFrame,
    families: Sequence[str] = ("historical", "vl", "h"),
    models: Sequence[str] | None = None,
    value: str = "anomaly",
    ylabel: str = "Global mean surface air temperature\nchange from 1850–1900 (°C)",
    title: str | None = None,
    titles: dict[str, str] | None = None,
) -> plt.Figure:
    """One panel per model: thin lines for members, a thick line for the ensemble mean.

    ``titles`` overrides the panel heading for a given source_id.
    """
    models = list(models) if models is not None else sorted(df["source_id"].unique())
    if not models:
        raise ValueError("no models to plot")
    ncol = min(len(models), 3)
    nrow = math.ceil(len(models) / ncol)
    fig, axes = plt.subplots(
        nrow, ncol, figsize=(4.2 * ncol + 0.6, 3.4 * nrow + 0.6), sharey=True, squeeze=False
    )

    for ax, model in zip(axes.flat, models):
        _style_axes(ax)
        sub = df[df["source_id"] == model]
        for fam in families:
            style = FAMILY_STYLE.get(fam, {"color": MUTED, "label": fam})
            fsub = sub[sub["family"] == fam]
            if fsub.empty:
                continue
            members = fsub.pivot_table(index="year", columns="variant_label", values=value)
            if members.shape[1] > 1:
                ax.plot(members.index, members.values, color=style["color"], linewidth=0.6, alpha=0.35)
            mean = members.mean(axis=1)
            n = members.shape[1]
            ax.plot(mean.index, mean.values, color=style["color"], linewidth=2, label=f"{style['label']} (n={n})")
            if fam != "historical":
                ax.annotate(
                    style["label"],
                    (mean.index[-1], mean.iloc[-1]),
                    xytext=(4, 0),
                    textcoords="offset points",
                    va="center",
                    fontsize=9,
                    color=INK,
                )
        exps = ", ".join(sorted(sub.loc[sub["family"].isin(families), "experiment_id"].unique()))
        ax.set_title((titles or {}).get(model, model), fontsize=11, color=INK, loc="left", pad=16)
        ax.text(0, 1.02, exps, transform=ax.transAxes, fontsize=7.5, color=MUTED, va="bottom")
        ax.legend(frameon=False, fontsize=8, loc="upper left", labelcolor=INK)
        ax.set_xlim(1850, max(2100, int(sub["year"].max())) + 8)

    for ax in axes.flat[len(models):]:
        ax.set_visible(False)
    for ax in axes[:, 0]:
        ax.set_ylabel(ylabel, fontsize=9, color=INK)

    if title:
        fig.suptitle(title, fontsize=12, color=INK, x=0.02, ha="left")
    fig.tight_layout()
    return fig
