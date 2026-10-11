"""Receipts waiting to be posted (plan 04.2 tests 4 and 5, `thirst sync`).

A receipt is written to ``~/.thirst/outbox/<job_id>.json`` BEFORE the first network attempt (the
body only; the old timestamp is never reused, ``sync`` signs again) and removed once the server
has it, so hours of measurement survive a Ctrl-C, a dropped SSH session or a power cut during the
post. The job id makes posting idempotent: a 409 ``duplicate_job`` means the server already has
it, which counts as done.

A receipt stays queued when the network is down, the server is busy, or the server answers 401
(wrong clock or token: the user can fix that and ``thirst sync`` again). Only a 400, 413 or 422
moves it to ``outbox/rejected/``, because the server will never accept that body.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from . import config
from .client import ReceiptPost
from .errors import ApiError
from .ids import JOB_ID

logger = logging.getLogger(__name__)

MAX_FILE_BYTES = 256 * 1024
_UNREADABLE = "The saved receipt is not valid JSON for this job."
_UNAUTHORISED = (
    "The server did not accept this computer's signature (HTTP 401). "
    "Check that the computer's clock is right (`thirst doctor`) and that the token in "
    "config.toml is current, then run `thirst sync`."
)
_UNSAVED = (
    "The receipt could not be saved to the outbox ({reason}), so `thirst sync` cannot retry it. "
    "Free some disk space or check permissions on ~/.thirst."
)

__all__ = ["JOB_ID", "MAX_FILE_BYTES", "PostOutcome", "SyncResult", "post_or_queue", "sync"]


class ReceiptSender(Protocol):
    def post_receipt(self, payload: dict[str, Any]) -> ReceiptPost: ...


@dataclass(frozen=True)
class PostOutcome:
    """``status``: posted, duplicate, queued (kept for `thirst sync`), rejected by the server, or
    unsaved (could not reach the server and could not write the outbox either)."""

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
    try:
        _path(job_id).unlink(missing_ok=True)
    except OSError:
        logger.warning("could not remove %s from the outbox", job_id)


def _reject(job_id: str) -> None:
    """Move an item the server will never accept out of the way (it would fail on every sync)."""
    source = _path(job_id)
    target_dir = config.outbox_dir() / "rejected"
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        if source.exists():
            source.replace(target_dir / source.name)
    except OSError:
        logger.warning("could not move %s to the rejected folder", job_id)


def _keep_queued(err: ApiError) -> bool:
    """Errors the user or time can fix: no connection, server trouble, rate limit, or a 401."""
    return err.status == 0 or err.status >= 500 or err.status == 401 or err.code == "rate_limited"


def _message(err: ApiError) -> str:
    return _UNAUTHORISED if err.status == 401 else err.message


def _try_enqueue(body: dict[str, Any]) -> str | None:
    """None when the receipt is in the outbox, else the reason it could not be written."""
    try:
        enqueue(body)
    except OSError as exc:
        logger.warning("could not write the receipt to the outbox: %s", exc)
        return exc.strerror or "write error"
    except ValueError:
        return "invalid job id"
    return None


def post_or_queue(client: ReceiptSender, body: dict[str, Any]) -> PostOutcome:
    """Persist the receipt, then post it. It leaves the outbox only when the server has it."""
    failure = _try_enqueue(body)
    job_id = str(body.get("job_id"))
    try:
        sent = client.post_receipt(body)
    except ApiError as err:
        if not _keep_queued(err):
            if failure is None:
                _reject(job_id)
            return PostOutcome("rejected", None, err.message)
        if failure is not None:
            failure = _try_enqueue(body)  # one more try now that time has passed
        if failure is not None:
            return PostOutcome(
                "unsaved", None, f"{_message(err)} " + _UNSAVED.format(reason=failure)
            )
        return PostOutcome("queued", None, _message(err))
    if failure is None:
        _remove(job_id)
    if sent.duplicate:
        return PostOutcome("duplicate", None, "This receipt was already recorded.")
    return PostOutcome("posted", sent.response, "")


def _load(job_id: str) -> dict[str, Any] | None:
    """The saved body, ``None`` if it can never be valid; ``OSError`` if it cannot be read now."""
    path = _path(job_id)
    if path.stat().st_size > MAX_FILE_BYTES:
        return None
    try:
        data = json.loads(path.read_bytes().decode("utf-8"))
    except (ValueError, RecursionError):
        return None
    if not isinstance(data, dict) or data.get("job_id") != job_id:
        return None
    return data


def sync(client: ReceiptSender) -> SyncResult:
    """Post every queued receipt again (fresh timestamp and signature each time)."""
    sent: list[str] = []
    duplicates: list[str] = []
    rejected: list[tuple[str, str]] = []
    skipped: list[str] = []
    queue = pending()
    for index, job_id in enumerate(queue):
        try:
            body = _load(job_id)
        except OSError:
            skipped.append(job_id)  # a transient read problem: leave it for the next sync
            continue
        if body is None:
            _reject(job_id)
            rejected.append((job_id, _UNREADABLE))
            continue
        try:
            result = client.post_receipt(body)
        except ApiError as err:
            if _keep_queued(err):
                left = (*skipped, *queue[index:])
                return SyncResult(
                    tuple(sent), tuple(duplicates), tuple(rejected), left, _message(err)
                )
            _reject(job_id)
            rejected.append((job_id, err.message))
            continue
        _remove(job_id)
        (duplicates if result.duplicate else sent).append(job_id)
    return SyncResult(tuple(sent), tuple(duplicates), tuple(rejected), tuple(skipped), None)
