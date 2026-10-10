"""Engine errors. Codes match the API error table in plan 08 §4."""

from __future__ import annotations


class EngineError(Exception):
    """A problem the caller can fix, with a stable machine code and a plain-words message."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
