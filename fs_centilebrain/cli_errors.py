"""Exception type shared by the CLI and the pipeline (kept separate to avoid import cycles)."""


class CliError(Exception):
    """A usage or input error that should be reported without a traceback (exit code 2)."""
