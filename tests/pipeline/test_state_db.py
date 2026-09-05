"""Tests for the SQLite run-state store (Story R1-02, write-through mirror)."""

from __future__ import annotations

import json
import sqlite3

from packages.pipeline.failure_semantics import FailureClass
from packages.pipeline.state_db import SCHEMA_VERSION, StateDB

RUN_ID = "run_1700000000_abcdef01"


class TestInit:
    def test_auto_creates_db_file(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            assert db.path == tmp_path / "runs" / "state.db"
            assert db.path.exists()
        finally:
            db.close()

    def test_schema_version_row_stamped(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            conn = sqlite3.connect(db.path)
            version = conn.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
            conn.close()
            assert version == SCHEMA_VERSION
        finally:
            db.close()

    def test_migrate_is_idempotent(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            db._migrate()
            db._migrate()
            conn = sqlite3.connect(db.path)
            versions = conn.execute("SELECT version FROM schema_version").fetchall()
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
            conn.close()
            assert versions == [(SCHEMA_VERSION,)]
            assert {"runs", "phase_executions", "artifacts", "dead_letters", "lead_fingerprints"} <= tables
        finally:
            db.close()


class TestPersistence:
    def test_data_survives_close_and_reopen(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        db.record_run_start(RUN_ID)
        db.record_phase_execution(RUN_ID, "phase_02", "done", result_path="runs/x/outputs/r.json")
        db.close()

        reopened = StateDB(tmp_path)
        try:
            row = reopened.get_phase_execution(RUN_ID, "phase_02")
            assert row is not None
            assert row["status"] == "done"
            assert row["result_path"] == "runs/x/outputs/r.json"
            assert reopened.latest_run()["run_id"] == RUN_ID
        finally:
            reopened.close()

    def test_custom_db_path_respected(self, tmp_path) -> None:
        custom = tmp_path / "elsewhere" / "custom.db"
        db = StateDB(tmp_path, db_path=custom)
        try:
            assert db.path == custom
            assert custom.exists()
        finally:
            db.close()


class TestRunLifecycle:
    def test_start_then_finish_updates_status(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            db.record_run_start(RUN_ID, summary={"leads": 10})
            assert db.latest_run()["status"] == "running"

            db.record_run_finish(RUN_ID, status="done", summary={"leads": 12})
            run = db.latest_run()
            assert run["status"] == "done"
            assert run["finished_at"] is not None
            assert json.loads(run["summary_json"]) == {"leads": 12}
        finally:
            db.close()

    def test_finish_without_start_creates_row(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            db.record_run_finish(RUN_ID, status="failed")
            assert db.latest_run()["status"] == "failed"
        finally:
            db.close()

    def test_is_run_complete_requires_all_done(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            db.record_phase_execution(RUN_ID, "phase_02", "done")
            db.record_phase_execution(RUN_ID, "phase_03", "done")
            assert db.is_run_complete(RUN_ID)

            db.record_phase_execution(RUN_ID, "phase_04", "failed")
            assert not db.is_run_complete(RUN_ID)
        finally:
            db.close()

    def test_is_run_complete_false_without_phases(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            assert not db.is_run_complete("run_unknown")
        finally:
            db.close()


class TestPhaseExecution:
    def test_roundtrip_with_result_json(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            db.record_phase_execution(
                RUN_ID,
                "phase_02",
                "done",
                result={"phase": "phase_02", "status": "done", "risks": []},
                result_path="runs/x/phase_02/outputs/result.json",
                started_at="2026-01-01T00:00:00+00:00",
                finished_at="2026-01-01T00:00:05+00:00",
            )
            row = db.get_phase_execution(RUN_ID, "phase_02")
            assert row is not None
            assert json.loads(row["result_json"])["phase"] == "phase_02"
            assert row["duration_ms"] == 5000
        finally:
            db.close()

    def test_unserializable_result_falls_back_to_repr(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            db.record_phase_execution(RUN_ID, "phase_03", "done", result={"obj": object()})
            row = db.get_phase_execution(RUN_ID, "phase_03")
            assert row is not None
            assert "<object object at" in row["result_json"]
        finally:
            db.close()

    def test_get_phase_execution_unknown_run_returns_none(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            assert db.get_phase_execution("run_nope", "phase_02") is None
        finally:
            db.close()

    def test_latest_execution_wins_for_repeated_phase(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            db.record_phase_execution(RUN_ID, "phase_02", "failed")
            db.record_phase_execution(RUN_ID, "phase_02", "done")
            assert db.get_phase_execution(RUN_ID, "phase_02")["status"] == "done"
        finally:
            db.close()


class TestArtifacts:
    def test_duplicate_path_ignored(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            path = "runs/x/phase_02/outputs/leads.csv"
            assert db.record_artifact(RUN_ID, "phase_02", "csv", path)
            assert not db.record_artifact(RUN_ID, "phase_02", "csv", path)
            conn = sqlite3.connect(db.path)
            count = conn.execute("SELECT COUNT(*) FROM artifacts WHERE path = ?", (path,)).fetchone()[0]
            conn.close()
            assert count == 1
        finally:
            db.close()


class TestDeadLetters:
    def test_roundtrip_with_failure_class(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            db.record_dead_letter(
                RUN_ID,
                "phase_02",
                {"lead": "Joe's Plumbing", "reason": "missing phone"},
                FailureClass.HARD_FAILURE,
                detail="invalid contact data",
            )
            conn = sqlite3.connect(db.path)
            row = conn.execute(
                "SELECT record_json, failure_class, detail FROM dead_letters WHERE run_id = ?",
                (RUN_ID,),
            ).fetchone()
            conn.close()
            assert json.loads(row[0])["lead"] == "Joe's Plumbing"
            assert row[1] == "hard_failure"
            assert row[2] == "invalid contact data"
        finally:
            db.close()

    def test_accepts_plain_string_failure_class(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            db.record_dead_letter(RUN_ID, "phase_03", {"x": 1}, "retryable")
            conn = sqlite3.connect(db.path)
            value = conn.execute("SELECT failure_class FROM dead_letters").fetchone()[0]
            conn.close()
            assert value == "retryable"
        finally:
            db.close()


class TestLeadFingerprints:
    def test_dedupe_returns_true_then_false(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            assert db.record_lead_fingerprint("fp-123", RUN_ID, "phase_02")
            assert not db.record_lead_fingerprint("fp-123", RUN_ID, "phase_02")
        finally:
            db.close()

    def test_distinct_fingerprints_independent(self, tmp_path) -> None:
        db = StateDB(tmp_path)
        try:
            assert db.record_lead_fingerprint("fp-a", RUN_ID, "phase_02")
            assert db.record_lead_fingerprint("fp-b", RUN_ID, "phase_02")
            assert not db.record_lead_fingerprint("fp-a", RUN_ID, "phase_03")
        finally:
            db.close()
