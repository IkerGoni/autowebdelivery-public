"""R1-04 / R1-05 / R1-06 — failure contexts, dead-letter queue and phase metrics.

FailureContext/classify_failure unit tests plus focused orchestrator tests that
reuse the counting-fake harness from ``test_run_idempotency``.
"""

from __future__ import annotations

import json
import sqlite3

from packages.pipeline.failure_semantics import (
    FailureClass,
    FailureContext,
    classify_failure,
)
from packages.pipeline.run_pipeline import _join_errors, _phase_counts
from packages.pipeline.state_db import StateDB

# Reuse the R1-03 fake-phase harness (counting fakes + minimal envelopes).
from tests.pipeline.test_run_idempotency import RUN_ID, _install_fakes, _run


class TestFailureContext:
    def test_to_dict_is_json_serializable(self):
        ctx = FailureContext(
            phase="04", error="boom", run_id="run_x", artifact="runs/run_x/04_briefs/result.json",
            retryable=True, category=FailureClass.RETRYABLE,
        )
        assert json.loads(json.dumps(ctx.to_dict())) == {
            "phase": "04",
            "run_id": "run_x",
            "artifact": "runs/run_x/04_briefs/result.json",
            "error": "boom",
            "retryable": True,
            "category": "retryable",
        }

    def test_category_defaults_to_hard_failure(self):
        assert FailureContext(phase="04", error="boom").category is FailureClass.HARD_FAILURE

    def test_classify_failure_from_envelope_status(self):
        ctx = classify_failure("04", status="failed", error="site generation blew up")
        assert ctx.category is FailureClass.HARD_FAILURE
        assert ctx.retryable is False
        assert ctx.error == "site generation blew up"

    def test_classify_failure_blocked_is_not_retryable(self):
        ctx = classify_failure("02", status="blocked", error="missing input")
        assert ctx.category is FailureClass.BLOCKED
        assert ctx.retryable is False

    def test_classify_failure_skipped_is_optional_retryable(self):
        ctx = classify_failure("05", status="skipped")
        assert ctx.category is FailureClass.OPTIONAL
        assert ctx.retryable is True

    def test_classify_failure_unknown_status_is_hard(self):
        ctx = classify_failure("09", status="wat")
        assert ctx.category is FailureClass.HARD_FAILURE
        assert "unknown phase status" in ctx.error

    def test_classify_failure_without_status_defaults_hard(self):
        ctx = classify_failure("pipeline", status=None, error="unhandled exception")
        assert ctx.category is FailureClass.HARD_FAILURE
        assert ctx.error == "unhandled exception"

    def test_classify_failure_error_falls_back_to_semantics_detail(self):
        ctx = classify_failure("06", status="needs_review")
        assert ctx.error == "phase status 'needs_review'"


class TestPhaseCounts:
    def test_mirrors_envelope_count_keys(self):
        counts = _phase_counts({"records_processed": 3, "records_created": 2}, success=True)
        assert counts == {"records_processed": 3, "records_created": 2, "records_succeeded": 1}

    def test_status_derived_fallback(self):
        assert _phase_counts({"status": "failed", "errors": ["x"]}, success=False) == {"records_failed": 1}

    def test_join_errors(self):
        assert _join_errors(["a", "b"]) == "a; b"
        assert _join_errors(None) == ""
        assert _join_errors("solo") == "solo"


def test_failed_phase_writes_dead_letter_and_summary_failures(tmp_path, monkeypatch):
    """R1-04/R1-05: a failed phase produces a summary failure + a DB dead letter."""
    _install_fakes(monkeypatch, tmp_path, fail_phase="04")
    summary = _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)

    assert [f["phase"] for f in summary["failures"]] == ["04"]
    assert summary["failures"][0]["category"] == "hard_failure"
    assert "forced failure" in summary["failures"][0]["error"]

    db = StateDB(tmp_path)
    try:
        letters = db.list_dead_letters(RUN_ID)
        assert len(letters) == 1
        letter = letters[0]
        assert letter["phase"] == "04"
        assert letter["failure_class"] == "hard_failure"
        assert "forced failure" in letter["detail"]
        record = json.loads(letter["record_json"])
        assert record["status"] == "failed"
    finally:
        db.close()


def test_dead_letters_survive_restart(tmp_path, monkeypatch):
    """Dead letters are in sqlite and readable from a fresh StateDB instance."""
    _install_fakes(monkeypatch, tmp_path, fail_phase="03")
    _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)

    with sqlite3.connect(tmp_path / "runs" / "state.db") as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT phase, failure_class FROM dead_letters WHERE run_id = ?", (RUN_ID,)
        ).fetchall()
    assert [row["phase"] for row in rows] == ["03"]
    assert rows[0]["failure_class"] == "hard_failure"


def test_failed_phase_result_payload_carries_failure_and_counts(tmp_path, monkeypatch):
    """R1-04/R1-06: the recorded payload serializes the failure context + counts."""
    _install_fakes(monkeypatch, tmp_path, fail_phase="05")
    _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)

    db = StateDB(tmp_path)
    try:
        row = db.get_phase_execution(RUN_ID, "05")
        payload = json.loads(row["result_json"])
        assert payload["failure"]["phase"] == "05"
        assert payload["failure"]["category"] == "hard_failure"
        assert payload["counts"] == {"records_failed": 1}
        # Succeeded phases get status-derived counts too.
        ok_payload = json.loads(db.get_phase_execution(RUN_ID, "01")["result_json"])
        assert ok_payload["counts"]["records_succeeded"] == 1
        assert "failure" not in ok_payload
    finally:
        db.close()


def test_flag_off_no_db_but_summary_still_has_failures(tmp_path, monkeypatch):
    """Legacy path: no DB artifacts, but the summary still classifies failures."""
    monkeypatch.delenv("RUN_STATE_DB", raising=False)
    _install_fakes(monkeypatch, tmp_path, fail_phase="02")
    summary = _run(tmp_path, run_id=RUN_ID)

    assert not (tmp_path / "runs" / "state.db").exists()
    assert [f["phase"] for f in summary["failures"]] == ["02"]
    assert "phase_metrics" not in summary


def test_phase_metrics_rows_per_recorded_phase(tmp_path, monkeypatch):
    """R1-06: one metrics row per recorded phase with counts and duration."""
    _install_fakes(monkeypatch, tmp_path)
    summary = _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)

    metrics = summary["phase_metrics"]
    phases = [m["phase"] for m in metrics]
    assert "01" in phases and "05.5" in phases and "06" in phases
    assert len(phases) == len(set(phases)), "one row per phase"
    for m in metrics:
        assert m["status"] in ("done", "needs_review")
        assert m["counts"].get("records_succeeded") == 1
        assert "records_failed" not in m["counts"]

    db = StateDB(tmp_path)
    try:
        assert db.phase_metrics(RUN_ID) == metrics
        assert db.phase_metrics("run_unknown") == []
    finally:
        db.close()


def test_phase_metrics_include_failed_counts(tmp_path, monkeypatch):
    """A failed phase's metrics row carries records_failed=1."""
    _install_fakes(monkeypatch, tmp_path, fail_phase="04")
    summary = _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)

    row = next(m for m in summary["phase_metrics"] if m["phase"] == "04")
    assert row["status"] == "failed"
    assert row["counts"] == {"records_failed": 1}


def test_phase_metrics_falls_back_to_status_derived_counts(tmp_path):
    """Rows recorded without a counts block derive counts from their status."""
    db = StateDB(tmp_path)
    try:
        db.record_phase_execution(RUN_ID, "01", "done", result=None)
        db.record_phase_execution(RUN_ID, "02", "failed", result=None)
        metrics = {m["phase"]: m for m in db.phase_metrics(RUN_ID)}
        assert metrics["01"]["counts"] == {"records_succeeded": 1}
        assert metrics["02"]["counts"] == {"records_failed": 1}
        assert metrics["01"]["duration_ms"] is None
    finally:
        db.close()


def test_list_dead_letters_filters_by_run_and_limit(tmp_path):
    """list_dead_letters: run filter, newest-first ordering and limit."""
    db = StateDB(tmp_path)
    try:
        for i in range(3):
            db.record_dead_letter("run_a", "04", {"i": i}, FailureClass.HARD_FAILURE, detail=f"a{i}")
        db.record_dead_letter("run_b", "05", {"i": 9}, FailureClass.OPTIONAL, detail="b")

        assert len(db.list_dead_letters()) == 4
        a_letters = db.list_dead_letters("run_a")
        assert [letter["detail"] for letter in a_letters] == ["a2", "a1", "a0"]
        assert db.list_dead_letters("run_a", limit=1)[0]["detail"] == "a2"
        assert db.list_dead_letters("run_b")[0]["failure_class"] == "optional"
        assert db.list_dead_letters("run_missing") == []
    finally:
        db.close()


def test_dead_letter_written_for_per_item_failure_lists(tmp_path):
    """When an envelope carries a failed-item list, one dead letter is written per item."""
    db = StateDB(tmp_path)
    try:
        result = {
            "status": "failed",
            "errors": ["2 records failed"],
            "failed_records": [
                {"record_id": "lead_1", "error": "missing address"},
                {"record_id": "lead_2", "error": "geocode failed"},
            ],
        }
        ctx = classify_failure("04", status="failed", error=_join_errors(result["errors"]))
        from packages.pipeline.run_pipeline import _record_dead_letters

        _record_dead_letters(db, RUN_ID, "04", result, ctx.to_dict())
        letters = db.list_dead_letters(RUN_ID)
        assert len(letters) == 2
        # list_dead_letters is newest-first, so items come back in reverse order.
        assert [json.loads(letter["record_json"])["record_id"] for letter in letters] == ["lead_2", "lead_1"]
        assert letters[0]["detail"] == "geocode failed"
        assert letters[1]["detail"] == "missing address"
    finally:
        db.close()
