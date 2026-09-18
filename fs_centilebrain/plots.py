"""Per-structure plots (left and right side by side) rendered from the result JSON only."""

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402

log = logging.getLogger("fs_centilebrain")

PLOTS_DIRNAME = "plots"
DPI = 200

# Colors: one sequential hue (blue) for the normative band and median, neutral ink for the
# subject, a reserved status color for out-of-band values (always paired with a marker shape
# so the flag survives grayscale printing).
BAND_FILL = "#cde2fb"
BAND_EDGE = "#5598e7"
MEDIAN = "#2a78d6"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
GRID = "#e6e5e1"
FLAG = "#d03b3b"
MARKER = {"within": "o", "low": "v", "high": "^"}

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 8,
    "axes.titlesize": 9,
    "axes.labelsize": 8,
    "axes.edgecolor": INK_SECONDARY,
    "axes.linewidth": 0.6,
    "xtick.color": INK_SECONDARY,
    "ytick.color": INK_SECONDARY,
    "axes.labelcolor": INK,
    "axes.titlecolor": INK,
})


def _ordinal(p: float) -> str:
    n = int(round(p))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _draw_panel(ax, entry: dict, band: tuple, subject_age: float, show_ylabel: bool) -> None:
    low, mid, high = band
    curve = entry["curve"]
    ages, p10, p50, p90 = curve["age"], curve["p10"], curve["p50"], curve["p90"]

    ax.fill_between(ages, p10, p90, color=BAND_FILL, linewidth=0, zorder=1)
    ax.plot(ages, p10, color=BAND_EDGE, linewidth=0.8, linestyle=(0, (3, 2)), zorder=2)
    ax.plot(ages, p90, color=BAND_EDGE, linewidth=0.8, linestyle=(0, (3, 2)), zorder=2)
    ax.plot(ages, p50, color=MEDIAN, linewidth=1.6, zorder=3)

    # Direct labels on the curves at the right edge
    for values, text in ((p10, f"{low:g}th"), (p50, f"{mid:g}th"), (p90, f"{high:g}th")):
        ax.annotate(text, (ages[-1], values[-1]), xytext=(3, 0), textcoords="offset points",
                    ha="left", va="center", fontsize=7, color=INK_SECONDARY)

    flag = entry["flag"]
    color = FLAG if flag != "within" else INK
    ax.plot([subject_age], [entry["volume_mm3"]], marker=MARKER[flag], markersize=7, color=color,
            markeredgecolor="white", markeredgewidth=1.0, linestyle="none", zorder=5)
    label = f"{entry['volume_mm3']:,.0f} mm³\n{_ordinal(entry['percentile'])} percentile"
    # Label beside the point, on whichever side has more room
    left_half = subject_age <= (ages[0] + ages[-1]) / 2
    ax.annotate(label, (subject_age, entry["volume_mm3"]), xytext=(8 if left_half else -8, 0),
                textcoords="offset points", ha="left" if left_half else "right", va="center",
                fontsize=7.5, color=INK, fontweight="bold" if flag != "within" else "normal")

    ax.axvline(subject_age, color=GRID, linewidth=0.8, zorder=0)
    ax.set_title(f"{'Left' if entry['hemi'] == 'L' else 'Right'} {entry['label'].lower()}", loc="left")
    ax.set_xlabel("Age (years)")
    if show_ylabel:
        ax.set_ylabel("Volume (mm³)")
    ax.grid(True, axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_xlim(ages[0], ages[-1])
    ax.margins(x=0)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=6, integer=True))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))


def _legend(fig, band: tuple) -> None:
    low, mid, high = band
    handles = [
        Patch(facecolor=BAND_FILL, edgecolor=BAND_EDGE, linestyle=(0, (3, 2)), linewidth=0.8,
              label=f"{low:g}th–{high:g}th percentile"),
        Line2D([], [], color=MEDIAN, linewidth=1.6, label=f"{mid:g}th percentile"),
        Line2D([], [], marker="o", color=INK, linestyle="none", markersize=6, label="This subject"),
        Line2D([], [], marker="^", color=FLAG, linestyle="none", markersize=6,
               label=f"Outside {low:g}th–{high:g}th (▲ above, ▼ below)"),
    ]
    fig.legend(handles=handles, loc="lower center", ncol=4, frameon=False, fontsize=7,
               bbox_to_anchor=(0.5, 0.0), handlelength=1.6, columnspacing=1.4)


def render_plots(result: dict, output_dir: Path) -> dict:
    """Write one PNG per structure (L and R side by side) to output_dir/plots.

    Returns {region column: relative path} and records it under each region's "plot" key.
    """
    plots_dir = output_dir / PLOTS_DIRNAME
    plots_dir.mkdir(exist_ok=True)
    band = tuple(result["model"]["band_percentiles"])
    subject_age = result["subject"]["age"]
    by_structure = {}
    for entry in result["regions"]:
        by_structure.setdefault(entry["structure"], {})[entry["hemi"]] = entry

    paths = {}
    for structure, sides in by_structure.items():
        entries = [sides[h] for h in ("L", "R") if h in sides]
        fig, axes = plt.subplots(1, len(entries), figsize=(7.2, 2.9), sharey=True, squeeze=False)
        for ax, entry, first in zip(axes[0], entries, (True, False)):
            _draw_panel(ax, entry, band, subject_age, show_ylabel=first)
        # Common y-limits with headroom for the labels
        lo = min(min(e["curve"]["p10"]) for e in entries + [])
        hi = max(max(e["curve"]["p90"]) for e in entries + [])
        lo = min(lo, *(e["volume_mm3"] for e in entries))
        hi = max(hi, *(e["volume_mm3"] for e in entries))
        pad = 0.12 * (hi - lo)
        axes[0][0].set_ylim(lo - pad, hi + pad)
        fig.suptitle(entries[0]["label"], x=0.01, ha="left", fontsize=10, fontweight="bold", color=INK)
        _legend(fig, band)
        fig.subplots_adjust(left=0.10, right=0.95, top=0.82, bottom=0.30, wspace=0.18)
        path = plots_dir / f"{structure}.png"
        fig.savefig(path, dpi=DPI)
        plt.close(fig)
        rel = f"{PLOTS_DIRNAME}/{path.name}"
        for entry in entries:
            entry["plot"] = rel
            paths[entry["region"]] = rel
        log.info("wrote %s", path)
    return paths
