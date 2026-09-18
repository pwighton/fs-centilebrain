"""The per-subject pipeline: extract inputs, score, curves, plots, report.

Stages are added step by step; see 20260917-fs-centilebrains-implementation.md.
"""

import argparse
import logging

from .config import OUTPUT_DIRNAME
from .freesurfer import freesurfer_version, parse_aseg_stats, read_build_stamp, recon_all_done
from .inputs import build_input_row, write_input_files
from .measures import MEASURE_SPECS

log = logging.getLogger("fs_centilebrain")


def run_pipeline(args: argparse.Namespace) -> int:
    subject_path = args.subject_dir / args.subject
    out_root = subject_path / OUTPUT_DIRNAME
    input_dir = out_root / "input"
    output_dir = out_root / "output"
    for d in (out_root, input_dir, output_dir):
        d.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(output_dir / "centilebrain.log")],
    )
    log.info("fs-centilebrain run: subject=%s sex=%s age=%.2f vendor=%s measure=%s",
             args.subject, args.sex, args.age, args.vendor, args.measure)
    log.info("subject dir: %s", subject_path)
    log.info("model dir:   %s", args.model_dir)
    log.info("output dir:  %s", out_root)

    spec = MEASURE_SPECS[args.measure]

    # --- Step 2: input extraction -------------------------------------------------
    if not recon_all_done(subject_path):
        log.warning("scripts/recon-all.done not found; recon-all may not have completed")
    stamp = read_build_stamp(subject_path)
    fs_version = freesurfer_version(stamp)
    log.info("FreeSurfer build stamp: %s -> version %s", stamp, fs_version)

    aseg = parse_aseg_stats(subject_path / "stats" / "aseg.stats")
    row = build_input_row(spec, args.subject, args.sex, args.age, args.vendor, fs_version, aseg)
    csv_path, xlsx_path = write_input_files(row, spec, input_dir)
    log.info("%s = %.1f mm3", spec.global_column, row[spec.global_column])
    for region in spec.regions:
        log.info("%-8s %10.1f mm3  (%s)", region.column, row[region.column], region.aseg_names[0])
    log.info("wrote %s and %s", csv_path, xlsx_path)

    log.error("model scoring is not implemented yet (Step 3)")
    return 3
