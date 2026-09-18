import pytest

from fs_centilebrain.cli import CliError, main, parse_args, validate_run_args


def _subject(tmp_path, name="sub01", with_aseg=True):
    sd = tmp_path / "subjects"
    (sd / name / "stats").mkdir(parents=True)
    if with_aseg:
        (sd / name / "stats" / "aseg.stats").write_text("# aseg\n")
    return sd


def test_flag_only_form_defaults_to_run():
    args = parse_args(["-sd", "/x", "-s", "bert", "--male", "-a", "40"])
    assert args.command == "run"
    assert args.sex == "M"
    assert args.age == 40.0
    assert args.vendor == "Siemens"
    assert args.measure == "subcortical"


def test_explicit_run_and_long_flags():
    args = parse_args(["run", "--subject-dir", "/x", "--subject", "bert", "--female", "--age", "12.5", "--vendor", "GE"])
    assert args.sex == "F" and args.age == 12.5 and args.vendor == "GE"


@pytest.mark.parametrize("argv", [
    ["-sd", "/x", "-s", "bert", "-a", "40"],                      # no sex
    ["-sd", "/x", "-s", "bert", "--male", "--female", "-a", "40"],  # both sexes
    ["-sd", "/x", "-s", "bert", "--male", "-a", "forty"],         # non-numeric age
    ["-sd", "/x", "-s", "bert", "--male", "-a", "-3"],            # non-positive age
    ["-sd", "/x", "-s", "bert", "--male", "-a", "40", "-v", "Phillips"],  # bad vendor
    ["-sd", "/x", "--male", "-a", "40"],                          # missing subject
])
def test_bad_arguments_exit_2(argv):
    with pytest.raises(SystemExit) as exc:
        parse_args(argv)
    assert exc.value.code == 2


def test_validate_missing_subject(tmp_path):
    sd = _subject(tmp_path)
    args = parse_args(["-sd", str(sd), "-s", "nope", "--male", "-a", "40", "--model-dir", str(tmp_path)])
    with pytest.raises(CliError, match="subject not found"):
        validate_run_args(args)


def test_validate_missing_aseg(tmp_path):
    sd = _subject(tmp_path, with_aseg=False)
    args = parse_args(["-sd", str(sd), "-s", "sub01", "--male", "-a", "40", "--model-dir", str(tmp_path)])
    with pytest.raises(CliError, match="aseg.stats"):
        validate_run_args(args)


def test_main_reports_cli_errors_without_traceback(tmp_path, capsys):
    rc = main(["-sd", str(tmp_path), "-s", "nope", "--male", "-a", "40", "--model-dir", str(tmp_path)])
    assert rc == 2
    assert "subject not found" in capsys.readouterr().err


def test_report_subcommand_parses(tmp_path):
    args = parse_args(["report", str(tmp_path / "r.json")])
    assert args.command == "report"
