"""Assemble, validate and write the single result JSON that the report is rendered from."""

import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime
from importlib import metadata, resources
from pathlib import Path

import jsonschema

from . import __version__
from .config import BAND_PERCENTILES, TRAINING_AGE_RANGE, TRAINING_FS_VERSIONS, UPSTREAM_COMMIT, UPSTREAM_REPO
from .measures import MeasureSpec
from .scoring import SEX_NAME, _NORMAL

SCHEMA_VERSION = 1
BAND_Z = tuple(round(_NORMAL.inv_cdf(p / 100.0), 4) for p in BAND_PERCENTILES)
_PACKAGES = ("pandas", "numpy", "openpyxl", "matplotlib", "jinja2", "weasyprint", "jsonschema")


def result_filename(spec: MeasureSpec) -> str:
    return f"centilebrain-{spec.name}.json"


def flag_for(percentile: float) -> str:
    low, _, high = BAND_PERCENTILES
    if percentile < low:
        return "low"
    if percentile > high:
        return "high"
    return "within"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _r_version() -> str:
    try:
        out = subprocess.run(["Rscript", "-e", "cat(R.version.string)"], capture_output=True, text=True, check=True)
        return out.stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def _package_versions() -> dict:
    versions = {}
    for name in _PACKAGES:
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            pass
    return versions


def provenance(cli_args: dict) -> dict:
    return {
        "tool": "fs-centilebrain",
        "tool_version": __version__,
        "tool_git_sha": os.environ.get("FS_CENTILEBRAIN_GIT_SHA"),
        "container_image": os.environ.get("FS_CENTILEBRAIN_IMAGE"),
        "run_timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "cli_args": cli_args,
        "python_version": platform.python_version(),
        "python_executable": sys.executable,
        "r_version": _r_version(),
        "packages": _package_versions(),
    }


def model_block(spec: MeasureSpec, sex: str, model_file: Path, offsets) -> dict:
    return {
        "family": "MFP",
        "description": "CentileBrain fractional-polynomial model: region ~ fp(age) + ICV, Gaussian residuals with constant SD",
        "upstream_repo": UPSTREAM_REPO,
        "upstream_commit": UPSTREAM_COMMIT,
        "model_file": model_file.name,
        "model_sha256": _sha256(model_file),
        "offsets_source": str(offsets["source"].iloc[0]),
        "offsets_exact": bool((offsets["max_abs_dev"] < 1e-6).all()),
        "training_age_range": list(TRAINING_AGE_RANGE[SEX_NAME[sex]]),
        "training_fs_versions": list(TRAINING_FS_VERSIONS),
        "percentile_method": "gaussian",
        "band_percentiles": list(BAND_PERCENTILES),
        "band_z": list(BAND_Z),
    }


def region_entries(spec: MeasureSpec, row: dict, scored) -> list:
    """Per-region results for the single subject (scored rows with row == 0)."""
    z_low, _, z_high = BAND_Z
    entries = []
    for region in spec.regions:
        s = scored[(scored.row == 0) & (scored.region == region.column)].iloc[0]
        predicted = float(s.predicted)
        rmse = float(s.rmse)
        percentile = float(s.percentile)
        entries.append({
            "region": region.column,
            "hemi": region.hemi,
            "structure": region.structure,
            "label": region.label,
            "volume_mm3": float(row[region.column]),
            "predicted_mm3": predicted,
            "p10_mm3": predicted + z_low * rmse,
            "p50_mm3": predicted,
            "p90_mm3": predicted + z_high * rmse,
            "rmse_mm3": rmse,
            "z": float(s.z),
            "percentile": percentile,
            "percentile_empirical": float(s.percentile_empirical),
            "flag": flag_for(percentile),
        })
    return entries


def build_result(spec: MeasureSpec, subject: dict, model: dict, regions: list, warnings: list,
                 prov: dict) -> dict:
    n_regions = len(regions)
    low, _, high = BAND_PERCENTILES
    return {
        "schema_version": SCHEMA_VERSION,
        "measure": spec.name,
        "subject": subject,
        "model": model,
        "regions": regions,
        "curve_settings": None,          # filled in Step 4
        "warnings": warnings,
        "notes": {
            "expected_flags_healthy": round(n_regions * (low + (100 - high)) / 100.0, 2),
            "research_use_only": True,
        },
        "provenance": prov,
    }


def validate_result(result: dict) -> None:
    schema = json.loads(resources.files("fs_centilebrain").joinpath("schema", "result-v1.json").read_text())
    jsonschema.validate(result, schema)


def write_result(result: dict, path: Path) -> None:
    validate_result(result)
    with open(path, "w") as fh:
        json.dump(result, fh, indent=2)
        fh.write("\n")


def read_result(path: Path) -> dict:
    with open(path) as fh:
        result = json.load(fh)
    validate_result(result)
    return result
