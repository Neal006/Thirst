"""Plan 04.2 tests 4 and 5: the receipt outbox and `thirst sync`."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from thirst import outbox
from thirst.client import ReceiptPost
from thirst.errors import ApiError

JOB = "j_aaaaaaaaaaaa"
JOB2 = "j_bbbbbbbbbbbb"


@pytest.fixture(autouse=True)
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    target = tmp_path / ".thirst"
    monkeypatch.setenv("THIRST_HOME", str(target))
    return target


def body(job: str = JOB) -> dict[str, object]:
    return {"job_id": job, "site_id": "s_abcdefghij", "start_ts": "2026-10-10T01:00:00+05:30"}


class FakeClient:
    """Plays scripted outcomes for post_receipt, in order; an Exception is raised."""

    def __init__(self, *outcomes: ReceiptPost | BaseException) -> None:
        self.outcomes = list(outcomes)
        self.sent: list[dict[str, object]] = []

    def post_receipt(self, payload: dict[str, object]) -> ReceiptPost:
        self.sent.append(payload)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


OK = ReceiptPost(response={"capture": 0.9}, duplicate=False)
DUP = ReceiptPost(response=None, duplicate=True)


def net_down() -> ApiError:
    return ApiError("Could not reach the Thirst server.", code="network_error")


def test_enqueue_writes_only_the_body(home: Path) -> None:
    path = outbox.enqueue(body())

    assert path == home / "outbox" / f"{JOB}.json"
    assert json.loads(path.read_text(encoding="utf-8")) == body()


def test_enqueue_refuses_a_job_id_that_could_escape_the_folder() -> None:
    with pytest.raises(ValueError, match="job_id"):
        outbox.enqueue({**body(), "job_id": "../../evil"})


def test_pending_lists_valid_job_ids_sorted(home: Path) -> None:
    outbox.enqueue(body(JOB2))
    outbox.enqueue(body(JOB))
    (home / "outbox" / "notes.txt").write_text("x", encoding="utf-8")

    assert outbox.pending() == [JOB, JOB2]


def test_pending_is_empty_without_a_folder() -> None:
    assert outbox.pending() == []


def test_post_or_queue_posts_when_the_server_answers() -> None:
    client = FakeClient(OK)

    outcome = outbox.post_or_queue(client, body())

    assert outcome.status == "posted"
    assert outcome.response == {"capture": 0.9}
    assert outbox.pending() == []


def test_post_or_queue_queues_on_network_failure() -> None:
    client = FakeClient(net_down())

    outcome = outbox.post_or_queue(client, body())

    assert outcome.status == "queued"
    assert outcome.message == "Could not reach the Thirst server."
    assert outbox.pending() == [JOB]


def test_post_or_queue_queues_on_server_error_and_rate_limit() -> None:
    server_down = ApiError("try later", code="try_again", status=503)
    limited = ApiError("slow down", code="rate_limited", status=429)

    assert outbox.post_or_queue(FakeClient(server_down), body(JOB)).status == "queued"
    assert outbox.post_or_queue(FakeClient(limited), body(JOB2)).status == "queued"


def test_post_or_queue_treats_a_duplicate_as_done() -> None:
    outcome = outbox.post_or_queue(FakeClient(DUP), body())

    assert outcome.status == "duplicate"
    assert outbox.pending() == []


def test_post_or_queue_reports_a_rejection_without_queueing() -> None:
    bad = ApiError("This energy is more than your GPUs can draw.", "implausible_energy", 422)

    outcome = outbox.post_or_queue(FakeClient(bad), body())

    assert outcome.status == "rejected"
    assert "more than your GPUs" in outcome.message
    assert outbox.pending() == []


def test_sync_posts_and_removes_each_item() -> None:
    outbox.enqueue(body(JOB))
    outbox.enqueue(body(JOB2))
    client = FakeClient(OK, OK)

    result = outbox.sync(client)

    assert result.sent == (JOB, JOB2)
    assert outbox.pending() == []
    assert [sent["job_id"] for sent in client.sent] == [JOB, JOB2]


def test_sync_counts_a_409_duplicate_as_success_and_removes_it() -> None:
    outbox.enqueue(body())

    result = outbox.sync(FakeClient(DUP))

    assert result.duplicates == (JOB,)
    assert result.sent == ()
    assert outbox.pending() == []


def test_sync_stops_at_the_first_network_failure_and_keeps_the_rest() -> None:
    outbox.enqueue(body(JOB))
    outbox.enqueue(body(JOB2))
    client = FakeClient(net_down())

    result = outbox.sync(client)

    assert result.still_queued == (JOB, JOB2)
    assert result.error is not None
    assert len(client.sent) == 1
    assert outbox.pending() == [JOB, JOB2]


def test_sync_moves_a_rejected_receipt_aside_and_continues(home: Path) -> None:
    outbox.enqueue(body(JOB))
    outbox.enqueue(body(JOB2))
    bad = ApiError("end_ts: more than 30 days old.", "invalid_field", 400)

    result = outbox.sync(FakeClient(bad, OK))

    assert result.rejected == ((JOB, "end_ts: more than 30 days old."),)
    assert result.sent == (JOB2,)
    assert outbox.pending() == []
    assert (home / "outbox" / "rejected" / f"{JOB}.json").is_file()


def test_sync_skips_a_corrupt_file_with_a_note(home: Path) -> None:
    (home / "outbox").mkdir(parents=True)
    (home / "outbox" / f"{JOB}.json").write_text("{not json", encoding="utf-8")

    result = outbox.sync(FakeClient())

    assert [job for job, _ in result.rejected] == [JOB]
    assert "valid" in result.rejected[0][1]
    assert outbox.pending() == []


def test_sync_rejects_a_file_whose_job_id_does_not_match_its_name(home: Path) -> None:
    (home / "outbox").mkdir(parents=True)
    (home / "outbox" / f"{JOB}.json").write_text(json.dumps(body(JOB2)), encoding="utf-8")

    result = outbox.sync(FakeClient())

    assert [job for job, _ in result.rejected] == [JOB]


def test_sync_with_an_empty_outbox_does_nothing() -> None:
    result = outbox.sync(FakeClient())

    assert result == outbox.SyncResult((), (), (), (), None)


# ------------------------------------------------------------ M1 / H4: a receipt is never lost


def unauthorised(code: str = "stale_timestamp") -> ApiError:
    return ApiError("The request is too old.", code=code, status=401)


@pytest.mark.parametrize("code", ["stale_timestamp", "bad_signature", "missing_signature"])
def test_post_or_queue_keeps_a_401_queued_and_explains_it(code: str) -> None:
    outcome = outbox.post_or_queue(FakeClient(unauthorised(code)), body())

    assert outcome.status == "queued"
    assert "clock" in outcome.message
    assert "token" in outcome.message
    assert outbox.pending() == [JOB]


def test_sync_stops_on_a_401_and_keeps_every_receipt_queued(home: Path) -> None:
    outbox.enqueue(body(JOB))
    outbox.enqueue(body(JOB2))
    client = FakeClient(unauthorised())

    result = outbox.sync(client)

    assert result.still_queued == (JOB, JOB2)
    assert result.rejected == ()
    assert result.error is not None
    assert "clock" in result.error
    assert len(client.sent) == 1
    assert outbox.pending() == [JOB, JOB2]
    assert not (home / "outbox" / "rejected").exists()


def test_the_receipt_is_in_the_outbox_before_the_first_network_attempt() -> None:
    seen: list[list[str]] = []

    class Spy(FakeClient):
        def post_receipt(self, payload: dict[str, object]) -> ReceiptPost:
            seen.append(outbox.pending())
            return super().post_receipt(payload)

    outbox.post_or_queue(Spy(OK), body())

    assert seen == [[JOB]]
    assert outbox.pending() == []  # removed again after the server accepted it


def test_an_interrupt_during_the_post_leaves_the_receipt_queued() -> None:
    with pytest.raises(KeyboardInterrupt):
        outbox.post_or_queue(FakeClient(KeyboardInterrupt()), body())

    assert outbox.pending() == [JOB]


def test_a_failing_outbox_write_does_not_stop_the_post(monkeypatch: pytest.MonkeyPatch) -> None:
    def broken(_: dict[str, object]) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(outbox, "enqueue", broken)

    outcome = outbox.post_or_queue(FakeClient(OK), body())

    assert outcome.status == "posted"


def test_a_failing_outbox_write_with_the_server_down_is_reported_not_hidden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def broken(_: dict[str, object]) -> Path:
        raise OSError("disk full")

    monkeypatch.setattr(outbox, "enqueue", broken)

    outcome = outbox.post_or_queue(FakeClient(net_down()), body())

    assert outcome.status == "unsaved"
    assert "could not be saved" in outcome.message


def test_a_rejected_receipt_is_moved_to_rejected_not_deleted(home: Path) -> None:
    bad = ApiError("Too much energy.", "implausible_energy", 422)

    outbox.post_or_queue(FakeClient(bad), body())

    assert outbox.pending() == []
    assert (home / "outbox" / "rejected" / f"{JOB}.json").is_file()


def test_sync_keeps_a_receipt_it_could_not_read_for_now(
    home: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    outbox.enqueue(body(JOB))

    def flaky(self: Path, *args: object, **kwargs: object) -> str:
        raise PermissionError("busy")

    monkeypatch.setattr(Path, "read_bytes", flaky)

    result = outbox.sync(FakeClient())

    assert result.rejected == ()
    assert result.still_queued == (JOB,)
    assert (home / "outbox" / f"{JOB}.json").is_file()


def test_sync_rejects_an_oversized_file(home: Path) -> None:
    (home / "outbox").mkdir(parents=True)
    huge = json.dumps({**body(), "pad": "x" * (outbox.MAX_FILE_BYTES + 1)})
    (home / "outbox" / f"{JOB}.json").write_text(huge, encoding="utf-8")

    result = outbox.sync(FakeClient())

    assert [job for job, _ in result.rejected] == [JOB]
