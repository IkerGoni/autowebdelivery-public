"""R1-03 — idempotency/resume of the pipeline orchestrator (run_state_db flag).

All phase modules are replaced with counting fakes that write the minimal
artifacts the orchestrator itself consumes (result.json envelopes and
``03_scoring/selected_for_preview.json``), following the monkeypatch style of
``tests/test_run_pipeline.py``.
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from packages.pipeline import run_pipeline
from packages.pipeline.result_envelope import ResultEnvelope
from packages.pipeline.run_pipeline import lead_fingerprint, run_full_pipeline
from packages.pipeline.state_db import StateDB

RUN_ID = "run_r103_fixed"

LEAD = {
    "record_id": "lead_001",
    "business_name": "Test Detailing",
    "business_slug": "test-detailing",
    "address": "123 Main St",
    "maps_url": "https://maps.google.com/?cid=123",
}

# Phase key -> (orchestrator symbol, run-directory name)
_PHASES = {
    "01": ("run_phase_01", "01_input"),
    "02": ("run_phase_02", "02_discovery"),
    "02.1": ("run_phase_02_1", "02_1_website_filter"),
    "03": ("run_phase_03", "03_scoring"),
    "04": ("run_phase_04", "04_briefs"),
    "04.5": ("run_phase_04_5", "04_5_enrichment"),
    "05": ("run_phase_05_unified", "05_sites"),
    "06": ("run_strict_phase_06", "06_quality"),
    "07": ("run_phase_07", "07_deployments"),
    "08": ("run_phase_08", "08_outreach"),
    "09": ("run_phase_09", "09_review"),
}


def _envelope(phase: str, status: str = "done") -> dict:
    if status == "done":
        return ResultEnvelope.done(
            phase=phase, run_id=RUN_ID, inputs_used=[], outputs_created=[],
            records_processed=1, records_created=1,
        ).to_dict()
    return {"status": status, "errors": [f"{phase} forced failure"]}


def _install_fakes(monkeypatch, workspace: Path, *, fail_phase: str | None = None) -> dict[str, int]:
    """Replace every phase with a counting fake; returns per-phase call counts."""
    counts: dict[str, int] = {key: 0 for key in _PHASES}

    def make_fake(key: str, dir_name: str):
        def fake(run_id=RUN_ID, workspace=workspace, *args, **kwargs):
            counts[key] += 1
            phase_dir = Path(workspace) / "runs" / run_id / dir_name
            phase_dir.mkdir(parents=True, exist_ok=True)
            if key == "03":
                from packages.pipeline.json_io import write_json
                write_json(str(phase_dir / "selected_for_preview.json"), [LEAD])
            status = "failed" if key == fail_phase else "done"
            res = _envelope(f"phase_{key}", status)
            from packages.pipeline.json_io import write_json
            write_json(str(phase_dir / "result.json"), res)
            if key == "06":
                res["decisions"] = [
                    "Strict quality checked 1 sites",
                    "Approved: 1, Needs edit: 0, Rejected: 0",
                ]
            return res

        return fake

    for key, (symbol, dir_name) in _PHASES.items():
        monkeypatch.setattr(run_pipeline, symbol, make_fake(key, dir_name))
    return counts


def _run(workspace: Path, **overrides):
    kwargs: dict = {
        "niche": "auto detailing",
        "area": "Frisco TX",
        "workspace": str(workspace),
        "generation_mode": "template",
        "deploy_provider": "local_only",
        "max_preview_sites": 1,
        "dry_run": True,
    }
    kwargs.update(overrides)
    return run_full_pipeline(**kwargs)


def test_full_run_records_run_and_phase_rows(tmp_path, monkeypatch):
    """(a) A full flagged run records the run row, all phase rows and artifacts."""
    _install_fakes(monkeypatch, tmp_path)
    summary = _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID, dry_run=False)

    assert summary["errors"] == []
    db_path = tmp_path / "runs" / "state.db"
    assert db_path.exists()

    db = StateDB(tmp_path)
    try:
        assert db.is_run_complete(RUN_ID)
        latest = db.latest_run()
        assert latest["run_id"] == RUN_ID
        assert latest["status"] == "done"
        assert latest["summary_json"] is not None
        for key in (*_PHASES, "05.5"):
            row = db.get_phase_execution(RUN_ID, key)
            assert row is not None, f"missing phase_executions row for {key}"
            assert row["status"] == "done"
            if key != "05.5":
                assert row["duration_ms"] is not None
                assert row["result_path"].endswith("result.json")
    finally:
        db.close()

    # result.json artifacts recorded (05.5 has no directory of its own)
    with sqlite3.connect(db_path) as conn:
        artifact_count = conn.execute(
            "SELECT COUNT(*) FROM artifacts WHERE run_id = ? AND artifact_type = 'outputs'", (RUN_ID,)
        ).fetchone()[0]
    assert artifact_count == len(_PHASES)


def test_rerun_same_run_id_skips_completed_phases(tmp_path, monkeypatch):
    """(b) Re-running with the same run_id invokes zero phase fakes."""
    _install_fakes(monkeypatch, tmp_path)
    first = _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)
    assert first["phases_completed"]

    counts = _install_fakes(monkeypatch, tmp_path)
    second = _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)

    assert all(c == 0 for c in counts.values()), counts
    assert second["errors"] == []
    assert sorted(second["phases_completed"]) == sorted(first["phases_completed"])


def test_failed_phase_dir_cleaned_and_rerun(tmp_path, monkeypatch):
    """(c) A failed phase's partial artifacts are removed before the re-run."""
    _install_fakes(monkeypatch, tmp_path, fail_phase="04")
    failed = _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)
    assert any("Phase 04 failed" in e for e in failed["errors"])
    partial = tmp_path / "runs" / RUN_ID / "04_briefs" / "stale_partial.txt"
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_text("partial artifact from the failed attempt")

    counts = _install_fakes(monkeypatch, tmp_path)
    retried = _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)

    # Phase 04 re-ran; everything before it was skipped as complete.
    assert counts["04"] == 1
    assert all(counts[k] == 0 for k in ("01", "02", "02.1", "03")), counts
    assert not partial.exists(), "partial artifacts of the failed phase must be cleaned"
    assert retried["errors"] == []
    assert "04" in retried["phases_completed"]

    db = StateDB(tmp_path)
    try:
        latest = db.latest_run()
        assert latest["status"] == "done"
    finally:
        db.close()


def test_lead_fingerprint_dedupe_skips_repeat_leads(tmp_path, monkeypatch):
    """(d) A lead already fingerprinted in a previous run is skipped."""
    counts1 = _install_fakes(monkeypatch, tmp_path)
    _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)
    assert counts1["03"] == 1

    # A second, distinct run discovers the same lead again.
    counts2 = _install_fakes(monkeypatch, tmp_path)
    second = _run(tmp_path, vnext_flags={"run_state_db": True}, run_id="run_r103_second")

    assert counts2["03"] == 1  # phase ran fresh, dedupe applies to its output
    assert second["leads_selected"] == 0, "repeat lead must be deduped out"
    assert "04" not in second["phases_completed"]


def test_flag_off_no_db_and_phases_always_run(tmp_path, monkeypatch):
    """(e) Flag off: no state.db is created and every phase runs again."""
    _install_fakes(monkeypatch, tmp_path)
    monkeypatch.delenv("RUN_STATE_DB", raising=False)
    first = _run(tmp_path, dry_run=False)
    assert first["errors"] == []
    assert not (tmp_path / "runs" / "state.db").exists()

    counts = _install_fakes(monkeypatch, tmp_path)
    _run(tmp_path, dry_run=False, run_id=RUN_ID)
    assert all(c == 1 for c in counts.values()), counts


def test_env_var_enables_flag_without_config(tmp_path, monkeypatch):
    """RUN_STATE_DB=1 overrides the (False) config flag; =0 forces it off."""
    _install_fakes(monkeypatch, tmp_path)
    monkeypatch.setenv("RUN_STATE_DB", "1")
    _run(tmp_path)
    assert (tmp_path / "runs" / "state.db").exists()

    workspace2 = tmp_path / "second"
    workspace2.mkdir()
    _install_fakes(monkeypatch, workspace2)
    monkeypatch.setenv("RUN_STATE_DB", "0")
    _run(workspace2, vnext_flags={"run_state_db": True})
    assert not (workspace2 / "runs" / "state.db").exists()


def test_run_state_db_flag_defaults_false():
    from packages.pipeline.vnext_integration import _VNEXT_FLAG_DEFAULTS, get_vnext_flags

    assert _VNEXT_FLAG_DEFAULTS["run_state_db"] is False
    assert get_vnext_flags({})["run_state_db"] is False


def test_flag_on_does_not_trip_vnext_any_gating(tmp_path, monkeypatch):
    """run_state_db=True must not enable any() vNext post-phase integrations."""
    calls: list[str] = []
    monkeypatch.setattr(
        run_pipeline, "run_vnext_post_phase_03",
        lambda *a, **k: calls.append("post_03"),
    )
    _install_fakes(monkeypatch, tmp_path)
    _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)
    assert calls == []


class TestLeadFingerprint:
    def test_stable_across_key_order_and_case(self):
        a = lead_fingerprint({"business_name": "Test Detailing", "address": "123 Main St"})
        b = lead_fingerprint({"address": "123 MAIN ST", "business_name": "test detailing"})
        assert a == b

    def test_different_address_changes_fingerprint(self):
        a = lead_fingerprint({"business_name": "Test Detailing", "address": "123 Main St"})
        b = lead_fingerprint({"business_name": "Test Detailing", "address": "9 Oak Ave"})
        assert a != b

    def test_place_id_takes_precedence_over_maps_url(self):
        a = lead_fingerprint({"business_name": "X", "address": "Y", "place_id": "p1"})
        b = lead_fingerprint({"business_name": "X", "address": "Y", "maps_url": "u1"})
        assert a != b


def test_resume_accepts_needs_review_for_phase_02(tmp_path):
    """Phases 02/02.1 treat a recorded needs_review execution as complete."""
    db = StateDB(tmp_path)
    try:
        db.record_phase_execution(RUN_ID, "02", "needs_review", result={"status": "needs_review"})
        row = db.get_phase_execution(RUN_ID, "02")
        assert row["status"] in run_pipeline._phase_success_statuses("02")
        assert row["status"] not in run_pipeline._phase_success_statuses("03")
    finally:
        db.close()


def test_unhandled_phase_exception_records_failed_run(tmp_path, monkeypatch):
    """A phase raising mid-run still records run finish (status=failed) and closes the DB."""
    counts = _install_fakes(monkeypatch, tmp_path)

    def boom(run_id, workspace):
        raise RuntimeError("phase 03 exploded")

    monkeypatch.setattr(run_pipeline, "run_phase_03", boom)
    with pytest.raises(RuntimeError):
        _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)
    assert counts["03"] == 0  # the patched boom replaced the fake

    db = StateDB(tmp_path)
    try:
        assert db.latest_run()["status"] == "failed"
    finally:
        db.close()


def test_recorded_result_json_round_trips(tmp_path, monkeypatch):
    """The recorded phase result_json deserializes back to the envelope dict."""
    _install_fakes(monkeypatch, tmp_path)
    _run(tmp_path, vnext_flags={"run_state_db": True}, run_id=RUN_ID)
    db = StateDB(tmp_path)
    try:
        row = db.get_phase_execution(RUN_ID, "02")
        assert json.loads(row["result_json"])["status"] == "done"
    finally:
        db.close()


def test_hard_killed_phase_stale_dir_cleaned_on_fresh_run(tmp_path):
    """A SIGKILLed phase leaves stale artifacts but no DB row — cleanup must still fire."""
    db = StateDB(tmp_path)
    try:
        stale_dir = tmp_path / "runs" / RUN_ID / "05_sites"
        stale_dir.mkdir(parents=True)
        (stale_dir / "partial.html").write_text("half-written", encoding="utf-8")
        assert db.get_phase_execution(RUN_ID, "05") is None

        result = run_pipeline._resumable_execution(db, RUN_ID, "05", str(tmp_path))
        assert result is None
        assert not stale_dir.exists()
    finally:
        db.close()


class TestResumeLeadFilter:
    def test_leads_from_other_runs_filtered(self, tmp_path):
        """On resume, leads fingerprinted by a previous run are dropped."""
        db = StateDB(tmp_path)
        try:
            other = {"business_name": "Old Lead", "address": "1 Main St", "place_id": "p-old"}
            assert db.record_lead_fingerprint(run_pipeline.lead_fingerprint(other), "run_other", "03")
            kept = run_pipeline._filter_leads_on_resume(
                db, RUN_ID, [other, {"business_name": "This Run", "address": "2 Oak St", "place_id": "p-new"}]
            )
            assert [lead["business_name"] for lead in kept] == ["This Run"]
        finally:
            db.close()

    def test_own_run_fingerprints_survive_resume(self, tmp_path):
        """Leads recorded by THIS run must not be filtered out on its own resume."""
        db = StateDB(tmp_path)
        try:
            mine = {"business_name": "Mine", "address": "3 Elm St", "place_id": "p-mine"}
            assert db.record_lead_fingerprint(run_pipeline.lead_fingerprint(mine), RUN_ID, "03")
            kept = run_pipeline._filter_leads_on_resume(db, RUN_ID, [mine])
            assert [lead["business_name"] for lead in kept] == ["Mine"]
        finally:
            db.close()
