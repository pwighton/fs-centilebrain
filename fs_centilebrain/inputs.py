"""Build the one-row CentileBrain input table for a subject and write it as csv + xlsx."""

from pathlib import Path

import pandas as pd

from .freesurfer import AsegStats
from .measures import MeasureSpec

SITE = "site1"


def build_input_row(spec: MeasureSpec, subject: str, sex: str, age: float, vendor: str,
                    fs_version: str, aseg: AsegStats) -> dict:
    """One record with exactly the template's columns, in template order."""
    row = {
        "SITE": SITE,
        "SubjectID": subject,
        "Vendor": vendor,
        "FreeSurfer_Version": fs_version,
        "age": age,
        "sex": sex,
        spec.global_column: aseg.measure(spec.aseg_global_measure),
    }
    for region in spec.regions:
        row[region.column] = aseg.volume(*region.aseg_names)
    assert tuple(row) == spec.columns
    return row


def input_basename(spec: MeasureSpec) -> str:
    return f"centilebrain-input-{spec.name}"


def write_input_files(row: dict, spec: MeasureSpec, input_dir: Path) -> tuple:
    """Write the row as csv and xlsx; returns (csv_path, xlsx_path)."""
    frame = pd.DataFrame([row], columns=list(spec.columns))
    csv_path = input_dir / f"{input_basename(spec)}.csv"
    xlsx_path = input_dir / f"{input_basename(spec)}.xlsx"
    frame.to_csv(csv_path, index=False)
    frame.to_excel(xlsx_path, index=False)
    return csv_path, xlsx_path


def read_input_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)
