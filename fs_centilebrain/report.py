"""Render the PDF report from the result JSON (and nothing else)."""

import logging
from datetime import datetime
from importlib import resources
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from .results import read_result

log = logging.getLogger("fs_centilebrain")

REPORT_BASENAME = "centilebrain-report"


def _ordinal(value: float) -> str:
    n = int(round(value))
    suffix = "th" if 10 <= n % 100 <= 20 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _fmt_int(value: float) -> str:
    return f"{value:,.0f}"


def _fmt_date(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return iso
    zone = dt.strftime("%Z")
    return f"{dt:%Y-%m-%d %H:%M} ({zone})" if zone else f"{dt:%Y-%m-%d %H:%M}"


def _structures(result: dict) -> list:
    """Group regions into one row per structure with 'L' and 'R' entries."""
    rows = {}
    for entry in result["regions"]:
        rows.setdefault(entry["structure"], {"label": entry["label"], "structure": entry["structure"], "ai": None})
        rows[entry["structure"]][entry["hemi"]] = entry
    for a in result.get("asymmetry", []):
        if a["structure"] in rows:
            rows[a["structure"]]["ai"] = a["ai_percent"]
    return list(rows.values())


def build_context(result: dict) -> dict:
    band = result["model"]["band_percentiles"]
    flagged = [r for r in result["regions"] if r["flag"] != "within"]
    return {
        "r": result,
        "subject": result["subject"],
        "model": result["model"],
        "band": {"low": band[0], "mid": band[1], "high": band[2]},
        "structures": _structures(result),
        "flagged": flagged,
        "n_regions": len(result["regions"]),
        "warnings": result["warnings"],
        "notes": result["notes"],
        "prov": result["provenance"],
        "curve_settings": result["curve_settings"],
        "legend_plot": result.get("legend_plot"),
        "sex_word": {"M": "male", "F": "female"}[result["subject"]["sex"]],
        "run_date": _fmt_date(result["provenance"]["run_timestamp"]),
    }


def render_html(result: dict) -> str:
    templates_dir = Path(resources.files("fs_centilebrain").joinpath("templates"))
    env = Environment(loader=FileSystemLoader(str(templates_dir)), autoescape=select_autoescape(["html"]))
    env.filters["ordinal"] = _ordinal
    env.filters["int"] = _fmt_int
    template = env.get_template("report.html.j2")
    return template.render(**build_context(result))


def render_report(result_path: Path, pdf_path: Path = None) -> Path:
    """Read the result JSON, write <output_dir>/centilebrain-report.html and the PDF.

    Plot paths in the JSON are relative to the JSON's directory, which is used as the
    base URL for both the HTML and the PDF.
    """
    from weasyprint import HTML  # imported lazily: slow, and not needed by the rest of the package
    logging.getLogger("fontTools").setLevel(logging.WARNING)   # "name pruned" chatter during font subsetting
    logging.getLogger("weasyprint").setLevel(logging.ERROR)    # HarfBuzz-Subset deprecation notice on Ubuntu 22.04

    result_path = Path(result_path)
    result = read_result(result_path)
    output_dir = result_path.parent
    if pdf_path is None:
        pdf_path = output_dir.parent / f"{REPORT_BASENAME}.pdf"

    html = render_html(result)
    html_path = output_dir / f"{REPORT_BASENAME}.html"
    html_path.write_text(html)
    log.info("wrote %s", html_path)

    HTML(string=html, base_url=str(output_dir) + "/").write_pdf(str(pdf_path))
    log.info("wrote %s", pdf_path)
    return pdf_path
