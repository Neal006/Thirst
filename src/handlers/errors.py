"""ApiError and engine-error to HTTP mapping (plan 05.5.e, contract 08 §4)."""

from __future__ import annotations

from typing import Any

from engine.errors import EngineError

# Engine codes that are the caller's fault, with their HTTP status.
_ENGINE_STATUS: dict[str, int] = {
    "invalid_field": 400,
    "unknown_city": 400,
    "unknown_gpu": 400,
    "deadline_too_soon": 422,
    "implausible_energy": 422,
    "slot_out_of_range": 422,
}

TRY_AGAIN = "Something went wrong on our side. Please try again."


class ApiError(Exception):
    """An error with a status, a stable code and plain words. Never carries a stack trace."""

    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


def from_engine(err: EngineError) -> ApiError:
    """Map an engine error. An unknown code is our bug, so say 'try again' and leak nothing."""
    status = _ENGINE_STATUS.get(err.code)
    if status is None:
        return ApiError(503, "try_again", TRY_AGAIN)
    return ApiError(status, err.code, err.message)


def error_body(code: str, message: str) -> dict[str, Any]:
    return {"error": code, "message": message}
