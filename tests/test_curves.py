import numpy as np
import pandas as pd
import pytest

from fs_centilebrain.config import MODEL_DIR, TRAINING_AGE_RANGE
from fs_centilebrain.curves import age_grid, compute_curves
from fs_centilebrain.freesurfer import parse_aseg_stats
from fs_centilebrain.inputs import build_input_row
from fs_centilebrain.measures import SUBCORTICAL
from fs_centilebrain.results import BAND_Z
from fs_centilebrain.scoring import score_cases

from conftest import REPO, requires_r


def test_age_grid_centered_and_unclipped():
    ages, requested, used = age_grid(40.0, "M")
    assert len(ages) == 81
    assert ages[0] == 30.0 and ages[-1] == 50.0 and 40.0 in ages
    assert np.allclose(np.diff(ages), 0.25)
    assert requested == (30.0, 50.0) and used == (30.0, 50.0)


@pytest.mark.parametrize("age,sex", [(5.0, "M"), (5.0, "F"), (88.0, "M"), (88.0, "F")])
def test_age_grid_clipped_to_training_range(age, sex):
    lo, hi = TRAINING_AGE_RANGE[{"M": "male", "F": "female"}[sex]]
    ages, requested, used = age_grid(age, sex)
    assert age in ages
    assert ages.min() >= lo and ages.max() <= hi
    assert used != requested
    assert len(ages) < 81


@requires_r
def test_curves_pass_through_subject_prediction():
    aseg = parse_aseg_stats(REPO / "tests" / "fixtures" / "bert-7.3.2-aseg.stats")
    row = build_input_row(SUBCORTICAL, "bert", "M", 40.0, "Siemens", "dev", aseg)
    scored = score_cases(pd.DataFrame([row]), SUBCORTICAL, "M", MODEL_DIR)
    curves, settings = compute_curves(SUBCORTICAL, "M", 40.0, row["ICV"], MODEL_DIR)
    assert settings["icv_fixed_mm3"] == row["ICV"] and settings["step_years"] == 0.25
    z_low, _, z_high = BAND_Z
    for region in SUBCORTICAL.region_columns:
        c = curves[region]
        i = c["age"].index(40.0)
        s = scored[scored.region == region].iloc[0]
        assert c["p50"][i] == pytest.approx(s.predicted, abs=1e-9)
        assert c["p10"][i] == pytest.approx(s.predicted + z_low * s.rmse, abs=1e-9)
        assert c["p90"][i] == pytest.approx(s.predicted + z_high * s.rmse, abs=1e-9)
        # constant-SD model: band width is the same at every age
        width = np.array(c["p90"]) - np.array(c["p10"])
        assert np.allclose(width, width[0])
        assert len(c["age"]) == len(c["p10"]) == len(c["p50"]) == len(c["p90"]) == 81


@requires_r
def test_curves_are_smooth_and_icv_sensitive():
    curves_a, _ = compute_curves(SUBCORTICAL, "F", 30.0, 1.4e6, MODEL_DIR)
    curves_b, _ = compute_curves(SUBCORTICAL, "F", 30.0, 1.6e6, MODEL_DIR)
    for region in SUBCORTICAL.region_columns:
        p50_a, p50_b = np.array(curves_a[region]["p50"]), np.array(curves_b[region]["p50"])
        assert (p50_b > p50_a).all()                   # larger ICV -> larger predicted volume
        assert np.abs(np.diff(p50_a)).max() < 0.02 * p50_a.mean()   # no jumps between 0.25 y steps
