import numpy as np

from fs_centilebrain.plots import render_plots
from fs_centilebrain.results import validate_result

from test_results import _minimal_result


def _result_with_curves():
    result = _minimal_result()
    ages = list(np.round(np.arange(30.0, 50.25, 0.25), 6))
    p50 = [8000.0 - 10.0 * (a - 30.0) for a in ages]
    left = result["regions"][0]
    left["curve"] = {"age": ages, "p10": [v - 800 for v in p50], "p50": p50, "p90": [v + 800 for v in p50]}
    right = dict(left, region="Rthal", hemi="R", volume_mm3=6500.0, z=-1.9, percentile=2.9, flag="low",
                 curve=dict(left["curve"]))
    result["regions"].append(right)
    result["curve_settings"] = {"age_window_requested": [30.0, 50.0], "age_window_used": [30.0, 50.0],
                                "step_years": 0.25, "icv_fixed_mm3": 1.5e6}
    return result


def test_render_plots_from_json_only(tmp_path):
    result = _result_with_curves()
    paths = render_plots(result, tmp_path)
    assert paths == {"Lthal": "plots/thalamus.png", "Rthal": "plots/thalamus.png"}
    png = tmp_path / "plots" / "thalamus.png"
    assert png.is_file() and png.stat().st_size > 10_000
    assert result["regions"][0]["plot"] == "plots/thalamus.png"
    validate_result(result)     # the added "plot" key is allowed by the schema
