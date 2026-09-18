"""Command-line interface.

Two forms are accepted:

    fs-centilebrain -sd DIR -s SUBJECT (--male|--female) -a AGE [-v VENDOR]   # full run
    fs-centilebrain report RESULT.json                                         # re-render the PDF

The first form is the default; ``run`` may be given explicitly.
"""

import argparse
import logging
import sys
from pathlib import Path

from . import __version__
from .cli_errors import CliError
from .config import DEFAULT_MEASURE, DEFAULT_VENDOR, MEASURES, MODEL_DIR, VENDORS

SUBCOMMANDS = ("run", "report")

# Exit codes: 0 success, 1 unexpected error (traceback in the log), 2 usage/input error.
EXIT_UNEXPECTED = 1
EXIT_USAGE = 2


def _positive_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"age must be a number, got {text!r}") from exc
    if value <= 0:
        raise argparse.ArgumentTypeError(f"age must be positive, got {value}")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="fs-centilebrain",
        description="Apply CentileBrain normative models to one FreeSurfer subject.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="{run,report}")

    run = sub.add_parser("run", help="extract inputs, score the model, plot and write the report (default)")
    run.add_argument("-sd", "--subject-dir", required=True, type=Path, metavar="DIR",
                     help="FreeSurfer SUBJECTS_DIR")
    run.add_argument("-s", "--subject", required=True, metavar="NAME", help="FreeSurfer subject name")
    sex = run.add_mutually_exclusive_group(required=True)
    sex.add_argument("-m", "--male", action="store_const", const="M", dest="sex", help="subject is male")
    sex.add_argument("-f", "--female", action="store_const", const="F", dest="sex", help="subject is female")
    run.add_argument("-a", "--age", required=True, type=_positive_float, metavar="YEARS",
                     help="age of the subject at scan time, in years")
    run.add_argument("-v", "--vendor", default=DEFAULT_VENDOR, choices=VENDORS,
                     help=f"MR scanner vendor (default: {DEFAULT_VENDOR})")
    run.add_argument("--measure", default=DEFAULT_MEASURE, choices=MEASURES,
                     help=f"morphometric measure to score (default: {DEFAULT_MEASURE})")
    run.add_argument("--model-dir", type=Path, default=MODEL_DIR, metavar="DIR",
                     help=f"directory holding the CentileBrain .rds files (default: {MODEL_DIR})")

    report = sub.add_parser("report", help="re-render the PDF report from an existing result JSON")
    report.add_argument("result_json", type=Path, metavar="RESULT.json")
    report.add_argument("-o", "--output", type=Path, metavar="PDF",
                        help="where to write the PDF (default: next to the JSON, as normative-neuromorphometry-report--subject-<id>.pdf)")
    return parser


def parse_args(argv=None) -> argparse.Namespace:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Make "run" the default subcommand so the documented flag-only form works.
    if not argv or argv[0] not in SUBCOMMANDS and argv[0] not in ("-h", "--help", "--version"):
        argv.insert(0, "run")
    return build_parser().parse_args(argv)


def validate_run_args(args: argparse.Namespace) -> None:
    """Check that the inputs a run needs actually exist."""
    if not args.subject_dir.is_dir():
        raise CliError(f"subject dir not found: {args.subject_dir}")
    subject_path = args.subject_dir / args.subject
    if not subject_path.is_dir():
        raise CliError(f"subject not found: {subject_path}")
    aseg = subject_path / "stats" / "aseg.stats"
    if not aseg.is_file():
        raise CliError(f"missing {aseg}; has recon-all completed?")
    if not args.model_dir.is_dir():
        raise CliError(f"model dir not found: {args.model_dir}")


def main(argv=None) -> int:
    args = parse_args(argv)
    log = logging.getLogger("fs_centilebrain")
    try:
        if args.command == "report":
            if not args.result_json.is_file():
                raise CliError(f"result JSON not found: {args.result_json}")
            from .report import render_report
            logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
            render_report(args.result_json, args.output)
            return 0
        validate_run_args(args)
        from .freesurfer import FreeSurferError
        from .pipeline import run_pipeline
        from .scoring import ScoringError
        try:
            return run_pipeline(args)
        except (FreeSurferError, ScoringError) as exc:
            # Problems with the subject's files or the model inputs: report as an input error.
            log.error("%s", exc)
            raise CliError(str(exc)) from exc
    except CliError as exc:
        print(f"fs-centilebrain: error: {exc}", file=sys.stderr)
        return EXIT_USAGE
    except Exception as exc:  # noqa: BLE001 - last resort: traceback to the log, one line to the user
        log.exception("unexpected error")
        print(f"fs-centilebrain: unexpected error: {exc!r} (see centilebrain.log for the traceback)", file=sys.stderr)
        return EXIT_UNEXPECTED


if __name__ == "__main__":
    sys.exit(main())
