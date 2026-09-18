import json

import pytest

from fs_centilebrain.plots import render_plots
from fs_centilebrain.report import build_context, render_html
from fs_centilebrain.results import write_result

from test_plots import _result_with_curves

weasyprint = pytest.importorskip("weasyprint")


def _write_full_result(tmp_path):
    """A result JSON with plots rendered next to it, like the pipeline leaves behind."""
    out = tmp_path / "output"
    out.mkdir()
    result = _result_with_curves()
    result["warnings"] = [{"code": "FS_VERSION_UNKNOWN", "message": "could not determine the FreeSurfer version"}]
    render_plots(result, out)
    path = out / "centilebrain-subcortical.json"
    write_result(result, path)
    return path


def test_html_contains_table_values_and_flags():
    result = _result_with_curves()
    html = render_html(result)
    assert "8,000" in html and "6,500" in html            # volumes
    assert "0.79" in html and "0.03" in html               # percentiles as decimals
    assert "Neuromorphometry report" in html and "not been approved by the FDA" in html
    assert 'class="side-l low"' in html and "↓" in html    # right thalamus flagged low
    assert "1 of 2 regions flagged" in html
    assert "+20.7" in html                                 # AI = 200*(8000-6500)/(14500)
    ctx = build_context(result)
    assert [s["label"] for s in ctx["structures"]] == ["Thalamus"]
    assert ctx["structures"][0]["L"]["region"] == "Lthal" and ctx["structures"][0]["R"]["region"] == "Rthal"


def test_render_report_from_json_only(tmp_path):
    from fs_centilebrain.report import render_report

    json_path = _write_full_result(tmp_path)
    pdf = render_report(json_path)
    assert pdf == tmp_path / "centilebrain-report.pdf"
    assert pdf.read_bytes()[:5] == b"%PDF-"
    assert pdf.stat().st_size > 50_000                      # includes the embedded PNGs
    html = (tmp_path / "output" / "centilebrain-report.html").read_text()
    assert 'src="plots/thalamus-left.png"' in html and 'src="plots/legend.png"' in html
    assert "FS_VERSION_UNKNOWN" in html


def test_report_subcommand(tmp_path):
    from fs_centilebrain.cli import main

    json_path = _write_full_result(tmp_path)
    target = tmp_path / "custom.pdf"
    assert main(["report", str(json_path), "-o", str(target)]) == 0
    assert target.read_bytes()[:5] == b"%PDF-"
    assert main(["report", str(tmp_path / "missing.json")]) == 2
