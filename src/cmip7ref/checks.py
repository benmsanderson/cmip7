"""End-of-script checks, printed by every pull script.

These exist so that a missing member or a truncated run is visible at the point
of production rather than in the figure.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

CHECK_FIGURES = Path("figures/checks")

# Observational reference values quoted in the checks (not analysis inputs).
GCB_LAND_SINK_PGC = 2.4  # GCB 2025, 2015-2024 decadal mean


def members(df: pd.DataFrame, expected: list[tuple[str, str]], label: str = "") -> None:
    """Report found vs expected (experiment, member) pairs."""
    found = {(e, v) for e, v in df[["experiment_id", "variant_label"]].drop_duplicates().itertuples(index=False)}
    want = set(expected)
    print(f"\nMembers{' ' + label if label else ''}: {len(found)} found, {len(want)} expected")
    for exp, var in sorted(want - found):
        print(f"  MISSING {exp} {var}")
    for exp, var in sorted(found - want):
        print(f"  EXTRA   {exp} {var}")
    if found == want:
        print("  all expected members present")


def year_ranges(df: pd.DataFrame) -> None:
    """Report the year span of each member and flag gaps in the annual index."""
    print("\nYear ranges:")
    for (exp, var), g in df.groupby(["experiment_id", "variant_label"]):
        years = sorted(g["year"].unique())
        gaps = [y for y in range(years[0], years[-1] + 1) if y not in set(years)]
        note = f"  GAPS: {gaps[:5]}{'...' if len(gaps) > 5 else ''}" if gaps else ""
        print(f"  {exp:15s} {var:10s} {years[0]}-{years[-1]}  ({len(years)} yr){note}")


def fallbacks(frames: list[pd.DataFrame]) -> None:
    """Report any reduction that fell back to cos-latitude weights."""
    fell = [f for f in frames if f.attrs.get("cos_latitude_fallback")]
    if fell:
        for f in fell:
            print(f"  COS-LATITUDE FALLBACK: {f['experiment_id'].iloc[0]} {f['variant_label'].iloc[0]}")
    else:
        print("\nWeighting: areacella used throughout (no cos-latitude fallback)")


def value_at(df: pd.DataFrame, year: int, experiment: str | None = None) -> pd.Series:
    """Values in a given year, indexed by member."""
    sub = df[df["year"] == year]
    if experiment:
        sub = sub[sub["experiment_id"] == experiment]
    return sub.set_index("variant_label")["value"]


def mean_over(df: pd.DataFrame, y0: int, y1: int, experiment: str | None = None) -> pd.Series:
    """Per-member mean over a year window."""
    sub = df[df["year"].between(y0, y1)]
    if experiment:
        sub = sub[sub["experiment_id"] == experiment]
    return sub.groupby("variant_label")["value"].mean()


def sanity_panel(df: pd.DataFrame, name: str, ylabel: str, title: str = "") -> Path:
    """One quick line panel per product, written to figures/checks/."""
    CHECK_FIGURES.mkdir(parents=True, exist_ok=True)
    fig, ax = plt.subplots(figsize=(7, 4))
    for (exp, var), g in df.groupby(["experiment_id", "variant_label"]):
        g = g.sort_values("year")
        ax.plot(g["year"], g["value"], linewidth=1, label=f"{exp} {var}")
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title or name, fontsize=10, loc="left")
    ax.legend(fontsize=6, frameon=False, ncol=2)
    ax.grid(color="#e4e3df", linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    fig.tight_layout()
    path = CHECK_FIGURES / f"{name}.png"
    fig.savefig(path, dpi=120)
    plt.close(fig)
    print(f"Sanity panel: {path}")
    return path
