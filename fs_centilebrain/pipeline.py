"""The per-subject pipeline: extract inputs, score, curves, plots, report.

Stages are added step by step; see 20260917-fs-centilebrains-implementation.md.
"""

import argparse
import logging

from .config import OUTPUT_DIRNAME

log = logging.getLogger("fs_centilebrain")


def run_pipeline(args: argparse.Namespace) -> int:
    subject_path = args.subject_dir / args.subject
    out_root = subject_path / OUTPUT_DIRNAME
    out_root.mkdir(exist_ok=True)
    (out_root / "input").mkdir(exist_ok=True)
    (out_root / "output").mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(out_root / "output" / "centilebrain.log")],
    )
    log.info("fs-centilebrain run: subject=%s sex=%s age=%.2f vendor=%s measure=%s",
             args.subject, args.sex, args.age, args.vendor, args.measure)
    log.info("subject dir: %s", subject_path)
    log.info("model dir:   %s", args.model_dir)
    log.info("output dir:  %s", out_root)

    log.error("pipeline stages are not implemented yet (input extraction arrives in Step 2)")
    return 3
