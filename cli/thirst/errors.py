"""Plain-words errors for the CLI. Each carries the process exit code (plan 04.0)."""

from __future__ import annotations

EXIT_OK = 0
EXIT_BAD_ARGS = 2
EXIT_CONFIG = 3
EXIT_API = 4
EXIT_GPU = 5
EXIT_INTERRUPTED = 130


class CliError(Exception):
    """An expected failure. ``message`` is safe to show to the user (never holds a secret)."""

    exit_code = EXIT_BAD_ARGS

    def __init__(self, message: str, exit_code: int | None = None) -> None:
        super().__init__(message)
        self.message = message
        if exit_code is not None:
            self.exit_code = exit_code


class ConfigError(CliError):
    """The config file is missing, unreadable or invalid."""

    exit_code = EXIT_CONFIG


class ApiError(CliError):
    """The server refused a request, or could not be reached.

    ``code`` is the server's error code (for example ``duplicate_job``), or a local code such as
    ``network_error``. ``status`` is the HTTP status, or 0 when there was no response.
    """

    exit_code = EXIT_API

    def __init__(self, message: str, code: str = "api_error", status: int = 0) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


class GpuError(CliError):
    """No usable NVIDIA GPU or driver, or a GPU call failed."""

    exit_code = EXIT_GPU
