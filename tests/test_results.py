import jsonschema
import pytest

from fs_centilebrain.results import build_result, read_result, validate_result, write_result
from fs_centilebrain.measures import SUBCORTICAL


def _minimal_result():
    subject = {"id": "s", "sex": "M", "age": 40.0, "icv_mm3": 1.5e6, "vendor": "Siemens",
               "freesurfer_version": "7.1.1", "freesurfer_build_stamp": "stamp", "subject_dir": "/x/s",
               "recon_all_done": True}
    model = {"family": "MFP", "upstream_repo": "r", "upstream_commit": "a" * 40, "model_file": "m.rds",
             "model_sha256": "b" * 64, "offsets_source": "single-site_x", "offsets_exact": True,
             "training_age_range": [3.42, 90.0], "training_fs_versions": ["7.1"], "percentile_method": "gaussian",
             "band_percentiles": [10, 50, 90], "band_z": [-1.2816, 0, 1.2816]}
    regions = [{"region": "Lthal", "hemi": "L", "structure": "thalamus", "label": "Thalamus", "volume_mm3": 8000.0,
                "predicted_mm3": 7500.0, "p10_mm3": 6700.0, "p50_mm3": 7500.0, "p90_mm3": 8300.0, "rmse_mm3": 626.0,
                "z": 0.8, "percentile": 78.8, "percentile_empirical": 78.0, "flag": "within"}]
    prov = {"tool": "fs-centilebrain", "tool_version": "0.1.0", "tool_git_sha": None, "container_image": None,
            "run_timestamp": "2026-09-18T10:00:00-04:00", "cli_args": {}, "python_version": "3.10",
            "python_executable": "/usr/bin/python3", "r_version": "R 4.3.3", "packages": {}}
    return build_result(SUBCORTICAL, subject, model, regions, [], prov)


def test_asymmetry_index():
    from fs_centilebrain.results import asymmetry_entries, asymmetry_index

    assert asymmetry_index(1000.0, 1000.0) == 0.0
    assert asymmetry_index(1100.0, 900.0) == pytest.approx(20.0)      # 200 * 200 / 2000
    assert asymmetry_index(900.0, 1100.0) == pytest.approx(-20.0)     # negative when right is larger
    regions = _minimal_result()["regions"]
    assert asymmetry_entries(regions) == []                           # left only: no pair
    right = dict(regions[0], region="Rthal", hemi="R", volume_mm3=7600.0)
    (entry,) = asymmetry_entries(regions + [right])
    assert entry["structure"] == "thalamus" and entry["left_region"] == "Lthal" and entry["right_region"] == "Rthal"
    assert entry["ai_percent"] == pytest.approx(200 * (8000 - 7600) / (8000 + 7600))


def test_result_validates_and_roundtrips(tmp_path):
    result = _minimal_result()
    validate_result(result)
    assert result["notes"]["expected_flags_healthy"] == 0.2   # 1 region x 20 %
    path = tmp_path / "r.json"
    write_result(result, path)
    assert read_result(path) == result


def test_schema_rejects_bad_flag_and_missing_keys(tmp_path):
    result = _minimal_result()
    result["regions"][0]["flag"] = "weird"
    with pytest.raises(jsonschema.ValidationError):
        validate_result(result)
    result = _minimal_result()
    del result["provenance"]
    with pytest.raises(jsonschema.ValidationError):
        validate_result(result)
