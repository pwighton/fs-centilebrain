"""Warnings, re-runs, error handling and model integrity."""

import json
import os
import shutil
from pathlib import Path

import pytest

from fs_centilebrain.cli import EXIT_UNEXPECTED, EXIT_USAGE, main
from fs_centilebrain.config import MODEL_DIR
from fs_centilebrain.pipeline import input_warnings, prepare_output_dirs
from fs_centilebrain.scoring import expected_checksums, verify_model_checksum

from conftest import REPO, requires_r

BERT_ASEG = REPO / "tests" / "fixtures" / "bert-7.3.2-aseg.stats"


def _make_subject(root: Path, name="sub", stamp="freesurfer-linux-centos7_x86_64-7.1.1-20200723-8b40551",
                  done=True) -> Path:
    subj = root / name
    (subj / "stats").mkdir(parents=True)
    (subj / "scripts").mkdir()
    shutil.copy(BERT_ASEG, subj / "stats" / "aseg.stats")
    if stamp is not None:
        (subj / "scripts" / "build-stamp.txt").write_text(stamp + "\n")
    if done:
        (subj / "scripts" / "recon-all.done").write_text("done\n")
    return subj


def _codes(warnings):
    return [w["code"] for w in warnings]


def test_no_warnings_for_clean_input(tmp_path):
    subj = _make_subject(tmp_path)
    assert input_warnings(subj, "7.1.1", "M", 40.0) == []


def test_warning_codes(tmp_path):
    subj = _make_subject(tmp_path, done=False)
    assert _codes(input_warnings(subj, "7.1.1", "M", 40.0)) == ["RECON_ALL_NOT_DONE"]
    subj = _make_subject(tmp_path, name="s2")
    assert _codes(input_warnings(subj, "8.2.0", "M", 40.0)) == ["FS_VERSION_NOT_IN_TRAINING"]
    assert _codes(input_warnings(subj, "freesurfer-dev-2022", "M", 40.0)) == ["FS_VERSION_UNKNOWN"]
    assert _codes(input_warnings(subj, "unknown", "M", 40.0)) == ["FS_VERSION_UNKNOWN"]
    assert _codes(input_warnings(subj, "5.3.0", "F", 2.0)) == ["AGE_OUT_OF_RANGE"]
    assert _codes(input_warnings(subj, "5.3.0", "F", 95.0)) == ["AGE_OUT_OF_RANGE"]
    assert _codes(input_warnings(subj, "5.3.0", "F", 90.0)) == []          # inside the female range (3.17-90.06)
    assert _codes(input_warnings(subj, "5.3.0", "M", 90.0)) == []          # inside the male range (3.42-90.0)
    assert set(_codes(input_warnings(_make_subject(tmp_path, name="s3", done=False), "8.2.0", "M", 1.0))) == \
        {"RECON_ALL_NOT_DONE", "FS_VERSION_NOT_IN_TRAINING", "AGE_OUT_OF_RANGE"}


def test_output_dirs_created_and_existing_detected(tmp_path):
    subj = _make_subject(tmp_path)
    out_root, input_dir, output_dir, existed = prepare_output_dirs(subj)
    assert out_root == subj / "centilebrain" and input_dir.is_dir() and output_dir.is_dir() and not existed
    assert prepare_output_dirs(subj)[3] is True


@pytest.mark.skipif(os.getuid() == 0, reason="root can write anywhere")
def test_unwritable_subject_dir_is_a_usage_error(tmp_path):
    subj = _make_subject(tmp_path)
    subj.chmod(0o555)
    try:
        rc = main(["-sd", str(tmp_path), "-s", "sub", "--male", "-a", "40", "--model-dir", str(tmp_path)])
    finally:
        subj.chmod(0o755)
    assert rc == EXIT_USAGE


def test_model_checksums_list_and_verify(tmp_path):
    expected = expected_checksums()
    assert set(expected) == {"MFPmodels_subcorticalvolume_male.rds", "MFPmodels_subcorticalvolume_female.rds"}
    bogus = tmp_path / "MFPmodels_subcorticalvolume_male.rds"
    bogus.write_bytes(b"not a model")
    assert "does not match" in verify_model_checksum(bogus)
    assert "no pinned checksum" in verify_model_checksum(tmp_path / "other.rds")


@requires_r
def test_pinned_models_in_model_dir_verify():
    for name in expected_checksums():
        assert verify_model_checksum(MODEL_DIR / name) is None


@requires_r
def test_full_run_then_rerun_overwrites_and_truncates_log(tmp_path):
    subj = _make_subject(tmp_path, done=False)
    argv = ["-sd", str(tmp_path), "-s", "sub", "--female", "-a", "95", "--model-dir", str(MODEL_DIR)]
    assert main(argv) == 0
    out = subj / "centilebrain"
    assert (out / "normative-neuromorphometry-report--subject-sub.pdf").is_file()
    result = json.loads((out / "output" / "centilebrain-subcortical.json").read_text())
    assert set(_codes(result["warnings"])) == {"RECON_ALL_NOT_DONE", "AGE_OUT_OF_RANGE", "CURVE_WINDOW_CLIPPED"}
    assert result["curve_settings"]["age_window_used"][1] <= 90.06

    first_log = (out / "output" / "centilebrain.log").read_text()
    assert first_log.count("fs-centilebrain 0.1.0 run:") == 1 and "already exists" not in first_log
    # Second run: outputs overwritten, log describes only the second run
    assert main(argv) == 0
    second_log = (out / "output" / "centilebrain.log").read_text()
    assert second_log.count("fs-centilebrain 0.1.0 run:") == 1 and "already exists" in second_log


@requires_r
def test_missing_structure_is_reported_as_input_error(tmp_path, capsys):
    subj = _make_subject(tmp_path)
    aseg = subj / "stats" / "aseg.stats"
    aseg.write_text("\n".join(l for l in aseg.read_text().splitlines() if "Left-Amygdala" not in l) + "\n")
    rc = main(["-sd", str(tmp_path), "-s", "sub", "--male", "-a", "40", "--model-dir", str(MODEL_DIR)])
    assert rc == EXIT_USAGE
    assert "Left-Amygdala" in capsys.readouterr().err


def test_unexpected_exception_exits_1(tmp_path, monkeypatch, capsys):
    subj = _make_subject(tmp_path)
    import fs_centilebrain.pipeline as pipeline

    def boom(*_args, **_kwargs):
        raise RuntimeError("kaboom")

    monkeypatch.setattr(pipeline, "parse_aseg_stats", boom)
    rc = main(["-sd", str(tmp_path), "-s", "sub", "--male", "-a", "40", "--model-dir", str(tmp_path)])
    assert rc == EXIT_UNEXPECTED
    assert "unexpected error" in capsys.readouterr().err
    assert "kaboom" in (subj / "centilebrain" / "output" / "centilebrain.log").read_text()
