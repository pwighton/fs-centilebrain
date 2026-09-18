from pathlib import Path

import pandas as pd
import pytest

from fs_centilebrain.freesurfer import (FreeSurferError, freesurfer_version, parse_aseg_stats,
                                        read_build_stamp, recon_all_done)
from fs_centilebrain.inputs import build_input_row, write_input_files
from fs_centilebrain.measures import SUBCORTICAL

FIXTURES = Path(__file__).parent / "fixtures"
REPO = Path(__file__).resolve().parents[1]
BERT_ASEG = FIXTURES / "bert-7.3.2-aseg.stats"

# Hand-checked against tests/fixtures/bert-7.3.2-aseg.stats
BERT_VALUES = {
    "ICV": 1518348.145089,
    "Lthal": 8109.9, "Rthal": 8330.0,
    "Lcaud": 2993.9, "Rcaud": 2932.2,
    "Lput": 5106.9, "Rput": 5256.3,
    "Lpal": 2175.3, "Rpal": 2188.6,
    "Lhippo": 4438.1, "Rhippo": 4652.9,
    "Lamyg": 1588.9, "Ramyg": 1558.6,
    "Laccumb": 491.5, "Raccumb": 649.9,
}


def test_parse_aseg_values():
    aseg = parse_aseg_stats(BERT_ASEG)
    assert aseg.measure("EstimatedTotalIntraCranialVol") == BERT_VALUES["ICV"]
    assert aseg.measure("eTIV") == BERT_VALUES["ICV"]          # short name also works
    assert aseg.volume("Left-Thalamus") == 8109.9
    assert aseg.volume("Right-Accumbens-area") == 649.9
    with pytest.raises(FreeSurferError):
        aseg.volume("Left-Thalamus-Proper")
    with pytest.raises(FreeSurferError):
        aseg.measure("NoSuchMeasure")


def test_thalamus_proper_naming(tmp_path):
    """FreeSurfer <= 7.1 calls the thalamus 'Thalamus-Proper'; both spellings must work."""
    old = BERT_ASEG.read_text().replace("Left-Thalamus ", "Left-Thalamus-Proper ").replace("Right-Thalamus ", "Right-Thalamus-Proper ")
    path = tmp_path / "aseg.stats"
    path.write_text(old)
    aseg = parse_aseg_stats(path)
    assert "Left-Thalamus-Proper" in aseg.volumes and "Left-Thalamus" not in aseg.volumes
    row = build_input_row(SUBCORTICAL, "s", "M", 40, "Siemens", "7.1.1", aseg)
    assert row["Lthal"] == 8109.9 and row["Rthal"] == 8330.0


def test_missing_structure_is_an_error(tmp_path):
    path = tmp_path / "aseg.stats"
    path.write_text("\n".join(l for l in BERT_ASEG.read_text().splitlines() if "Left-Amygdala" not in l) + "\n")
    with pytest.raises(FreeSurferError, match="Left-Amygdala"):
        build_input_row(SUBCORTICAL, "s", "M", 40, "Siemens", "7.3.2", parse_aseg_stats(path))


def test_input_row_matches_template_columns():
    row = build_input_row(SUBCORTICAL, "bert", "M", 40.0, "Siemens", "7.3.2", parse_aseg_stats(BERT_ASEG))
    for sex in ("male", "female"):
        template = (REPO / "reference" / "templates" / f"subcortical-volume-{sex}-columns.txt").read_text().split()
        assert list(row) == template
    assert row["SITE"] == "site1" and row["SubjectID"] == "bert" and row["sex"] == "M"
    assert row["Vendor"] == "Siemens" and row["FreeSurfer_Version"] == "7.3.2" and row["age"] == 40.0
    for col, value in BERT_VALUES.items():
        assert row[col] == value


def test_write_csv_and_xlsx_roundtrip(tmp_path):
    row = build_input_row(SUBCORTICAL, "bert", "F", 33.5, "GE", "7.3.2", parse_aseg_stats(BERT_ASEG))
    csv_path, xlsx_path = write_input_files(row, SUBCORTICAL, tmp_path)
    assert csv_path.name == "centilebrain-input-subcortical.csv"
    assert xlsx_path.name == "centilebrain-input-subcortical.xlsx"
    for frame in (pd.read_csv(csv_path), pd.read_excel(xlsx_path)):
        assert list(frame.columns) == list(SUBCORTICAL.columns)
        assert len(frame) == 1
        rec = frame.iloc[0]
        assert rec["sex"] == "F" and rec["Vendor"] == "GE" and rec["age"] == 33.5
        for col, value in BERT_VALUES.items():
            assert rec[col] == pytest.approx(value, abs=1e-6)


@pytest.mark.parametrize("stamp,expected", [
    ("freesurfer-linux-ubuntu20_x86_64-7.3.2-20220804-6354275", "7.3.2"),
    ("freesurfer-linux-centos7_x86_64-7.1.1-20200723-8b40551", "7.1.1"),
    ("freesurfer-Linux-centos6_x86_64-stable-pub-v5.3.0", "5.3.0"),
    ("freesurfer-linux-ubuntu22_x86_64-8.2.0-20250901-abcdef0", "8.2.0"),
    ("freesurfer-linux-centos7_x86_64-dev-20220617-ed5d67f", "freesurfer-linux-centos7_x86_64-dev-20220617-ed5d67f"),
    (None, "unknown"),
    ("", "unknown"),
])
def test_freesurfer_version(stamp, expected):
    assert freesurfer_version(stamp) == expected


def test_build_stamp_and_done_flag(tmp_path):
    subj = tmp_path / "s"
    (subj / "scripts").mkdir(parents=True)
    assert read_build_stamp(subj) is None and not recon_all_done(subj)
    (subj / "scripts" / "build-stamp.txt").write_text("freesurfer-linux-ubuntu20_x86_64-7.3.2-20220804-6354275\n")
    (subj / "scripts" / "recon-all.done").write_text("done\n")
    assert freesurfer_version(read_build_stamp(subj)) == "7.3.2" and recon_all_done(subj)
