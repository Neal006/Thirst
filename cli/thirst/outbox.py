"""Receipts waiting to be posted (plan 04.2 tests 4 and 5, `thirst sync`).

A receipt that could not be posted is stored as ``~/.thirst/outbox/<job_id>.json`` (the body only;
the old timestamp is never reused, ``sync`` signs again). The job id makes posting idempotent: a
409 ``duplicate_job`` means the server already has it, which counts as done.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from . import config
from .client import ReceiptPost
from .errors import ApiError

JOB_ID = re.compile(r"j_[a-z2-7]{12}")
_UNREADABLE = "The saved receipt is not valid JSON for this job."


class ReceiptSender(Protocol):
    def post_receipt(self, payload: dict[str, Any]) -> ReceiptPost: ...


@dataclass(frozen=True)
class PostOutcome:
    """``status``: posted, duplicate, queued (kept for `thirst sync`) or rejected by the server."""

    status: str
    response: dict[str, Any] | None
    message: str


@dataclass(frozen=True)
class SyncResult:
    sent: tuple[str, ...]
    duplicates: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    still_queued: tuple[str, ...]
    error: str | None


def _path(job_id: str) -> Path:
    if not JOB_ID.fullmatch(job_id):
        raise ValueError(f"job_id {job_id!r} is not a valid job id")
    return config.outbox_dir() / f"{job_id}.json"


def enqueue(body: dict[str, Any]) -> Path:
    """Store a receipt body for later. Raises ``ValueError`` on a bad job id."""
    job_id = body.get("job_id")
    path = _path(job_id if isinstance(job_id, str) else "")
    config.write_private(path, json.dumps(body, sort_keys=True, allow_nan=False))
    return path


def pending() -> list[str]:
    folder = config.outbox_dir()
    if not folder.is_dir():
        return []
    ids = (p.stem for p in folder.glob("*.json"))
    return sorted(job for job in ids if JOB_ID.fullmatch(job))


def _remove(job_id: str) -> None:
    _path(job_id).unlink(missing_ok=True)


def _reject(job_id: str) -> None:
    """Move an item the server will never accept out of the way (it would fail on every sync)."""
    source = _path(job_id)
    target_dir = config.outbox_dir() / "rejected"
    target_dir.mkdir(parents=True, exist_ok=True)
    if source.exists():
        source.replace(target_dir / source.name)


def _is_retryable(err: ApiError) -> bool:
    return err.status == 0 or err.status >= 500 or err.code == "rate_limited"


def post_or_queue(client: ReceiptSender, body: dict[str, Any]) -> PostOutcome:
    """Post a receipt; if the server can't be reached or is busy, queue it for ``sync``."""
    try:
        sent = client.post_receipt(body)
    except ApiError as err:
        if _is_retryable(err):
            enqueue(body)
            return PostOutcome("queued", None, err.message)
        return PostOutcome("rejected", None, err.message)
    if sent.duplicate:
        return PostOutcome("duplicate", None, "This receipt was already recorded.")
    return PostOutcome("posted", sent.response, "")


def _load(job_id: str) -> dict[str, Any] | None:
    try:
        data = json.loads(_path(job_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or data.get("job_id") != job_id:
        return None
    return data


def sync(client: ReceiptSender) -> SyncResult:
    """Post every queued receipt again (fresh timestamp and signature each time)."""
    sent: list[str] = []
    duplicates: list[str] = []
    rejected: list[tuple[str, str]] = []
    queue = pending()
    for index, job_id in enumerate(queue):
        body = _load(job_id)
        if body is None:
            _reject(job_id)
            rejected.append((job_id, _UNREADABLE))
            continue
        try:
            result = client.post_receipt(body)
        except ApiError as err:
            if _is_retryable(err):
                left = tuple(queue[index:])
                return SyncResult(
                    tuple(sent), tuple(duplicates), tuple(rejected), left, err.message
                )
            _reject(job_id)
            rejected.append((job_id, err.message))
            continue
        _remove(job_id)
        (duplicates if result.duplicate else sent).append(job_id)
    return SyncResult(tuple(sent), tuple(duplicates), tuple(rejected), (), None)
