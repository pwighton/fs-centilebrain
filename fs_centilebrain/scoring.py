"""Run the R scoring script on a table of cases and return tidy results."""

import csv
import hashlib
import subprocess
import tempfile
from importlib import resources
from pathlib import Path
from statistics import NormalDist

import pandas as pd

from .measures import MeasureSpec

SEX_NAME = {"M": "male", "F": "female"}
_NORMAL = NormalDist()


class ScoringError(Exception):
    pass


def _package_file(*parts) -> Path:
    return Path(resources.files("fs_centilebrain").joinpath(*parts))


def offsets_path(spec: MeasureSpec) -> Path:
    return _package_file("data", f"offsets-{spec.name}.csv")


def load_offsets(spec: MeasureSpec, sex: str) -> pd.DataFrame:
    frame = pd.read_csv(offsets_path(spec))
    frame = frame[(frame.measure == spec.name) & (frame.sex == SEX_NAME[sex])].reset_index(drop=True)
    if list(frame.region) != list(spec.region_columns):
        raise ScoringError(f"offsets file regions do not match the {spec.name} spec")
    return frame


def model_path(spec: MeasureSpec, sex: str, model_dir: Path) -> Path:
    path = model_dir / spec.model_file.format(sex=SEX_NAME[sex])
    if not path.is_file():
        raise ScoringError(f"model file not found: {path}")
    return path


def expected_checksums() -> dict:
    """{file name: sha256} for the upstream model files, from the package's checksum list."""
    out = {}
    for line in _package_file("data", "model-checksums.sha256").read_text().splitlines():
        if line.strip():
            digest, name = line.split()
            out[name] = digest
    return out


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_model_checksum(model_file: Path):
    """None if the file matches the pinned upstream checksum, otherwise a message."""
    expected = expected_checksums().get(model_file.name)
    if expected is None:
        return f"no pinned checksum for {model_file.name}"
    actual = sha256_of(model_file)
    if actual != expected:
        return (f"{model_file.name} does not match the pinned upstream file "
                f"(sha256 {actual[:12]}… vs expected {expected[:12]}…); results may differ from centilebrain.org")
    return None


def gaussian_percentile(z: float) -> float:
    return 100.0 * _NORMAL.cdf(z)


def score_cases(cases: pd.DataFrame, spec: MeasureSpec, sex: str, model_dir: Path) -> pd.DataFrame:
    """Score a table with columns age, ICV and (optionally) region volumes.

    Returns a long-format frame with one row per (case index, region):
    row, region, predicted, rmse, z, percentile, percentile_empirical.
    `z`, `percentile` and `percentile_empirical` are NaN for regions absent from `cases`.
    """
    if not {"age", spec.global_column} <= set(cases.columns):
        raise ScoringError(f"cases must have columns age and {spec.global_column}")
    with tempfile.TemporaryDirectory(prefix="fs-centilebrain-") as tmp:
        tmp = Path(tmp)
        cases.to_csv(tmp / "cases.csv", index=False)
        cmd = ["Rscript", str(_package_file("r", "score_mfp.R")),
               "--model", str(model_path(spec, sex, model_dir)),
               "--offsets", str(offsets_path(spec)),
               "--sex", SEX_NAME[sex],
               "--input", str(tmp / "cases.csv"),
               "--output", str(tmp / "scored.csv")]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise ScoringError(f"R scoring failed (exit {proc.returncode}):\n{proc.stderr.strip()}")
        scored = pd.read_csv(tmp / "scored.csv")
    scored["percentile"] = scored["z"].map(lambda z: gaussian_percentile(z) if pd.notna(z) else float("nan"))
    return scored


def write_website_format(cases: pd.DataFrame, scored: pd.DataFrame, spec: MeasureSpec, sex: str,
                         output_dir: Path) -> tuple:
    """Write prediction_/zscore_ CSVs shaped like centilebrain.org's output files.

    The website drops `sex` and the global measure and keeps the other metadata columns
    in front of the 14 regions.
    """
    meta_cols = [c for c in ("SITE", "SubjectID", "Vendor", "FreeSurfer_Version", "age") if c in cases.columns]
    paths = []
    for kind, column in (("prediction", "predicted"), ("zscore", "z")):
        wide = scored.pivot(index="row", columns="region", values=column)[list(spec.region_columns)]
        frame = pd.concat([cases[meta_cols].reset_index(drop=True), wide.reset_index(drop=True)], axis=1)
        path = output_dir / f"{kind}_{spec.website_name}_{SEX_NAME[sex]}.csv"
        frame.to_csv(path, index=False, quoting=csv.QUOTE_NONNUMERIC)
        paths.append(path)
    return tuple(paths)
