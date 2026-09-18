"""Golden tests: local scoring must reproduce centilebrain.org's output files."""

import numpy as np
import pandas as pd
import pytest

from fs_centilebrain.config import MODEL_DIR
from fs_centilebrain.freesurfer import parse_aseg_stats
from fs_centilebrain.inputs import build_input_row
from fs_centilebrain.measures import SUBCORTICAL
from fs_centilebrain.results import BAND_Z, flag_for
from fs_centilebrain.scoring import gaussian_percentile, load_offsets, score_cases, write_website_format

from conftest import REPO, WEB_RESULTS, requires_r

REGIONS = list(SUBCORTICAL.region_columns)

# (input file, sex flag, website result folder). The website ignores the sex column of the
# input, so the same 30-subject file serves both sexes.
SINGLE_SITE_RUNS = [
    ("input_single-site_demo.xlsx", "M", "single-site_male_2026-09-18-15-02-11"),
    ("input_single-site_demo.xlsx", "F", "single-site_female_2026-09-17-22-31-48"),
]


def _web(folder: str, kind: str, sex: str) -> pd.DataFrame:
    name = {"M": "male", "F": "female"}[sex]
    return pd.read_csv(WEB_RESULTS / folder / f"{kind}_SubcorticalVolume_{name}.csv")


@requires_r
@pytest.mark.parametrize("input_file,sex,folder", SINGLE_SITE_RUNS)
def test_demo_subjects_match_website(input_file, sex, folder, tmp_path):
    cases = pd.read_excel(WEB_RESULTS / input_file)
    scored = score_cases(cases, SUBCORTICAL, sex, MODEL_DIR)
    assert len(scored) == 30 * 14
    pred_path, z_path = write_website_format(cases, scored, SUBCORTICAL, sex, tmp_path)

    web_pred, web_z = _web(folder, "prediction", sex), _web(folder, "zscore", sex)
    ours_pred, ours_z = pd.read_csv(pred_path), pd.read_csv(z_path)
    assert list(ours_pred.columns) == list(web_pred.columns)
    assert list(ours_z.columns) == list(web_z.columns)
    assert (ours_pred.SubjectID == web_pred.SubjectID).all()
    np.testing.assert_allclose(ours_pred[REGIONS].to_numpy(), web_pred[REGIONS].to_numpy(), rtol=0, atol=1e-6)
    np.testing.assert_allclose(ours_z[REGIONS].to_numpy(), web_z[REGIONS].to_numpy(), rtol=0, atol=1e-6)


@requires_r
def test_bert_matches_website():
    """End-to-end on a real aseg.stats: bert (male, age 40) uploaded to centilebrain.org."""
    aseg = parse_aseg_stats(REPO / "tests" / "fixtures" / "bert-7.3.2-aseg.stats")
    row = build_input_row(SUBCORTICAL, "bert", "M", 40.0, "Siemens", "dev", aseg)
    scored = score_cases(pd.DataFrame([row]), SUBCORTICAL, "M", MODEL_DIR)
    web_z = _web("bert_male_age40_2026-09-18-15-04-41", "zscore", "M").iloc[0]
    web_pred = _web("bert_male_age40_2026-09-18-15-04-41", "prediction", "M").iloc[0]
    for region in REGIONS:
        s = scored[scored.region == region].iloc[0]
        assert s.z == pytest.approx(web_z[region], abs=1e-6)
        assert s.predicted == pytest.approx(web_pred[region], abs=1e-6)


@requires_r
def test_scoring_without_volumes_gives_predictions_only():
    cases = pd.DataFrame({"age": [20.0, 60.0], "ICV": [1.5e6, 1.5e6]})
    scored = score_cases(cases, SUBCORTICAL, "F", MODEL_DIR)
    assert len(scored) == 2 * 14
    assert scored.predicted.notna().all() and scored.z.isna().all() and scored.percentile.isna().all()


@requires_r
def test_empirical_percentile_is_plausible():
    cases = pd.read_excel(WEB_RESULTS / "input_single-site_demo.xlsx")
    scored = score_cases(cases, SUBCORTICAL, "F", MODEL_DIR)
    # Empirical and Gaussian percentiles agree to within a few points across the demo subjects.
    assert (scored.percentile - scored.percentile_empirical).abs().max() < 8
    assert scored.percentile_empirical.between(0, 100).all()


def test_offsets_are_exact_and_complete():
    for sex in ("M", "F"):
        offsets = load_offsets(SUBCORTICAL, sex)
        assert list(offsets.region) == REGIONS
        assert (offsets.max_abs_dev < 1e-9).all()
        assert offsets.source.str.startswith("single-site_").all()


def test_gaussian_percentile_and_flags():
    assert gaussian_percentile(0.0) == pytest.approx(50.0)
    assert gaussian_percentile(BAND_Z[0]) == pytest.approx(10.0, abs=0.01)
    assert gaussian_percentile(BAND_Z[2]) == pytest.approx(90.0, abs=0.01)
    assert BAND_Z[0] == pytest.approx(-1.2816, abs=1e-4) and BAND_Z[1] == 0
    assert flag_for(9.99) == "low" and flag_for(10.0) == "within" and flag_for(90.0) == "within" and flag_for(90.01) == "high"
