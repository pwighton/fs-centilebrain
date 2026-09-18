"""The per-subject pipeline: extract inputs, score, curves, plots, report.

Stages are added step by step; see 20260917-fs-centilebrains-implementation.md.
"""

import argparse
import logging
import os
import re

import pandas as pd

from . import __version__
from .cli_errors import CliError
from .config import OUTPUT_DIRNAME, TRAINING_AGE_RANGE, TRAINING_FS_VERSIONS
from .curves import compute_curves
from .freesurfer import freesurfer_version, parse_aseg_stats, read_build_stamp, recon_all_done
from .inputs import build_input_row, write_input_files
from .measures import MEASURE_SPECS
from .plots import render_plots
from .report import render_report
from .results import (build_result, model_block, provenance, region_entries, result_filename,
                      write_result)
from .scoring import (SEX_NAME, load_offsets, model_path, score_cases, verify_model_checksum,
                      write_website_format)

log = logging.getLogger("fs_centilebrain")


def _warn(warnings: list, code: str, message: str) -> None:
    warnings.append({"code": code, "message": message})
    log.warning("%s: %s", code, message)


def input_warnings(subject_path, fs_version: str, sex: str, age: float) -> list:
    warnings = []
    if not recon_all_done(subject_path):
        _warn(warnings, "RECON_ALL_NOT_DONE",
              "scripts/recon-all.done not found; recon-all may not have completed")
    major_minor = re.match(r"^(\d+\.\d+)", fs_version)
    if major_minor is None:
        _warn(warnings, "FS_VERSION_UNKNOWN",
              f"could not determine the FreeSurfer version ({fs_version!r}); the norms were built from versions "
              f"{', '.join(TRAINING_FS_VERSIONS)}")
    elif major_minor.group(1) not in TRAINING_FS_VERSIONS:
        _warn(warnings, "FS_VERSION_NOT_IN_TRAINING",
              f"FreeSurfer {fs_version} is not among the versions the norms were built from "
              f"({', '.join(TRAINING_FS_VERSIONS)}); systematic offsets are possible")
    lo, hi = TRAINING_AGE_RANGE[SEX_NAME[sex]]
    if not lo <= age <= hi:
        _warn(warnings, "AGE_OUT_OF_RANGE",
              f"age {age:g} is outside the training age range {lo:g}-{hi:g} years; results are an extrapolation")
    return warnings


def prepare_output_dirs(subject_path):
    """Create <subject>/centilebrain/{input,output}; returns (out_root, input_dir, output_dir, existed)."""
    out_root = subject_path / OUTPUT_DIRNAME
    existed = out_root.exists()
    input_dir = out_root / "input"
    output_dir = out_root / "output"
    try:
        for d in (out_root, input_dir, output_dir):
            d.mkdir(exist_ok=True)
        probe = output_dir / ".write-test"
        probe.touch()
        probe.unlink()
    except PermissionError as exc:
        raise CliError(f"cannot write to {out_root} (running as uid {os.getuid()}): {exc}") from exc
    return out_root, input_dir, output_dir, existed


def configure_logging(log_file) -> None:
    """Console + per-run log file (truncated, so it describes only this run)."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)
        handler.close()
    root.setLevel(logging.INFO)
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    for handler in (logging.StreamHandler(), logging.FileHandler(log_file, mode="w")):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    quiet_third_party_loggers()


def quiet_third_party_loggers() -> None:
    logging.getLogger("fontTools").setLevel(logging.WARNING)      # "name pruned" chatter during font subsetting
    logging.getLogger("weasyprint").setLevel(logging.ERROR)       # HarfBuzz-Subset deprecation notice on Ubuntu 22.04


def run_pipeline(args: argparse.Namespace) -> int:
    subject_path = args.subject_dir / args.subject
    out_root, input_dir, output_dir, existed = prepare_output_dirs(subject_path)
    configure_logging(output_dir / "centilebrain.log")

    log.info("fs-centilebrain %s run: subject=%s sex=%s age=%.2f vendor=%s measure=%s",
             __version__, args.subject, args.sex, args.age, args.vendor, args.measure)
    log.info("subject dir: %s", subject_path)
    log.info("model dir:   %s", args.model_dir)
    log.info("output dir:  %s", out_root)
    if existed:
        log.info("%s already exists; its contents will be overwritten", out_root)

    spec = MEASURE_SPECS[args.measure]

    # --- Step 2: input extraction -------------------------------------------------
    stamp = read_build_stamp(subject_path)
    fs_version = freesurfer_version(stamp)
    log.info("FreeSurfer build stamp: %s -> version %s", stamp, fs_version)
    warnings = input_warnings(subject_path, fs_version, args.sex, args.age)

    aseg = parse_aseg_stats(subject_path / "stats" / "aseg.stats")
    row = build_input_row(spec, args.subject, args.sex, args.age, args.vendor, fs_version, aseg)
    csv_path, xlsx_path = write_input_files(row, spec, input_dir)
    log.info("%s = %.1f mm3", spec.global_column, row[spec.global_column])
    for region in spec.regions:
        log.info("%-8s %10.1f mm3  (%s)", region.column, row[region.column], region.aseg_names[0])
    log.info("wrote %s and %s", csv_path, xlsx_path)

    # --- Step 3: model scoring ----------------------------------------------------
    offsets = load_offsets(spec, args.sex)
    model_file = model_path(spec, args.sex, args.model_dir)
    checksum_problem = verify_model_checksum(model_file)
    if checksum_problem:
        _warn(warnings, "MODEL_CHECKSUM_MISMATCH", checksum_problem)
    cases = pd.DataFrame([row])
    scored = score_cases(cases, spec, args.sex, args.model_dir)
    pred_path, z_path = write_website_format(cases, scored, spec, args.sex, output_dir)
    log.info("scored with %s; wrote %s and %s", model_file.name, pred_path.name, z_path.name)

    regions = region_entries(spec, row, scored)
    for entry in regions:
        log.info("%-8s z=%+6.2f  percentile=%5.1f  (%s)", entry["region"], entry["z"], entry["percentile"], entry["flag"])

    subject = {
        "id": args.subject,
        "sex": args.sex,
        "age": args.age,
        "icv_mm3": float(row[spec.global_column]),
        "vendor": args.vendor,
        "freesurfer_version": fs_version,
        "freesurfer_build_stamp": stamp,
        "subject_dir": str(subject_path),
        "recon_all_done": recon_all_done(subject_path),
    }
    cli_args = {k: (str(v) if not isinstance(v, (int, float, str, type(None))) else v)
                for k, v in vars(args).items()}
    result = build_result(spec, subject, model_block(spec, args.sex, model_file, offsets), regions,
                          warnings, provenance(cli_args))
    for a in result["asymmetry"]:
        log.info("%-12s asymmetry index %+5.1f %%", a["label"], a["ai_percent"])

    # --- Step 4: age curves -------------------------------------------------------
    curves, settings = compute_curves(spec, args.sex, args.age, subject["icv_mm3"], args.model_dir)
    for entry in result["regions"]:
        entry["curve"] = curves[entry["region"]]
    result["curve_settings"] = settings
    if settings["age_window_used"] != settings["age_window_requested"]:
        _warn(warnings, "CURVE_WINDOW_CLIPPED",
              "the +/-{:g} year curve window was clipped to the training age range ({:g}-{:g} years)".format(
                  (settings["age_window_requested"][1] - settings["age_window_requested"][0]) / 2,
                  *settings["age_window_used"]))

    # --- Step 5: plots ------------------------------------------------------------
    render_plots(result, output_dir)

    result_path = output_dir / result_filename(spec)
    write_result(result, result_path)
    log.info("wrote %s", result_path)

    # --- Step 6: PDF report (from the JSON only) ------------------------------------
    pdf_path = render_report(result_path)
    log.info("done: %s", pdf_path)
    return 0
