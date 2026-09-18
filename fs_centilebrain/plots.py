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

    ax.fill_between(ages, p10, p90, color=BAND_FILL, linewidth=0, zorder=1)   # grid (1.5) shows through
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

    ax.axvline(subject_age, color=GRID, linewidth=0.8, zorder=1.4)
    ax.set_title(f"{'Left' if entry['hemi'] == 'L' else 'Right'} {entry['label'].lower()}", loc="left")
    ax.set_xlabel("Age (years)")
    if show_ylabel:
        ax.set_ylabel("Volume (mm³)")
    ax.grid(True, axis="y", color=GRID, linewidth=0.6)
    ax.set_axisbelow("line")   # gridlines at zorder 1.5: above the band fill, below the curves
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    ax.set_xlim(ages[0], ages[-1])
    ax.margins(x=0)
    ax.xaxis.set_major_locator(matplotlib.ticker.MaxNLocator(nbins=6, integer=True))
    ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))


def _legend_handles(band: tuple) -> list:
    low, mid, high = band
    return [
        Patch(facecolor=BAND_FILL, edgecolor=BAND_EDGE, linestyle=(0, (3, 2)), linewidth=0.8,
              label=f"{low:g}th–{high:g}th percentile"),
        Line2D([], [], color=MEDIAN, linewidth=1.6, label=f"{mid:g}th percentile"),
        Line2D([], [], marker="o", color=INK, linestyle="none", markersize=6, label="This subject"),
        Line2D([], [], marker="^", color=FLAG, linestyle="none", markersize=6,
               label=f"Outside {low:g}th–{high:g}th (▲ above, ▼ below)"),
    ]


def render_legend(band: tuple, path: Path) -> None:
    """A stand-alone legend image, shown once in the report rather than on every plot."""
    fig = plt.figure(figsize=(7.2, 0.4))
    fig.legend(handles=_legend_handles(band), loc="center", ncol=4, frameon=False, fontsize=7.5,
               handlelength=1.6, columnspacing=1.6)
    fig.savefig(path, dpi=DPI)
    plt.close(fig)


def _ylim_for(entries: list) -> tuple:
    """Common y-limits for the left/right pair of a structure, with headroom for labels."""
    lo = min(min(e["curve"]["p10"]) for e in entries)
    hi = max(max(e["curve"]["p90"]) for e in entries)
    lo = min(lo, *(e["volume_mm3"] for e in entries))
    hi = max(hi, *(e["volume_mm3"] for e in entries))
    pad = 0.12 * (hi - lo)
    return lo - pad, hi + pad


def render_plots(result: dict, output_dir: Path) -> dict:
    """Write one PNG per region to output_dir/plots (plus legend.png).

    Left and right plots of the same structure share y-limits so they can be compared.
    Returns {region column: relative path}; records it under each region's "plot" key and
    the legend under result["legend_plot"].
    """
    plots_dir = output_dir / PLOTS_DIRNAME
    plots_dir.mkdir(exist_ok=True)
    band = tuple(result["model"]["band_percentiles"])
    subject_age = result["subject"]["age"]
    by_structure = {}
    for entry in result["regions"]:
        by_structure.setdefault(entry["structure"], []).append(entry)

    paths = {}
    for structure, entries in by_structure.items():
        ylim = _ylim_for(entries)
        for entry in entries:
            fig, ax = plt.subplots(figsize=(3.6, 2.8))
            _draw_panel(ax, entry, band, subject_age, show_ylabel=True)
            ax.set_ylim(*ylim)
            fig.subplots_adjust(left=0.20, right=0.88, top=0.90, bottom=0.17)
            side = "left" if entry["hemi"] == "L" else "right"
            path = plots_dir / f"{structure}-{side}.png"
            fig.savefig(path, dpi=DPI)
            plt.close(fig)
            rel = f"{PLOTS_DIRNAME}/{path.name}"
            entry["plot"] = rel
            paths[entry["region"]] = rel
            log.info("wrote %s", path)

    legend_path = plots_dir / "legend.png"
    render_legend(band, legend_path)
    result["legend_plot"] = f"{PLOTS_DIRNAME}/{legend_path.name}"
    log.info("wrote %s", legend_path)
    return paths
