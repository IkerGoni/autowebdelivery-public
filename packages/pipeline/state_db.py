"""SQLite-backed run state store (Story R1-02).

A minimal, stdlib-only (``sqlite3``) write-through mirror of pipeline run
state. The DB is derived state: it records what the filesystem already
contains (result envelopes, artifact paths, dead letters) so a later story
(R1-03) can add idempotency/resume behind a ``RUN_STATE_DB`` flag without
changing the filesystem contract. Legacy filesystem consumers keep working —
nothing reads from this DB in the current pipeline.

Connection handling: a single connection is shared across operations, guarded
by a ``threading.Lock`` and opened with ``check_same_thread=False`` so the
store is safe to use from multiple threads. Callers may use the instance as a
context manager or call :meth:`close` explicitly; every public method
commits before returning so data survives an unclean shutdown.

Schema evolution: a ``schema_version`` table records the applied schema
version (:data:`SCHEMA_VERSION`). :meth:`StateDB._migrate` is idempotent and
safe to call on an existing DB — it creates missing tables and stamps the
version only when upgrading.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Self

from packages.pipeline.failure_semantics import FailureClass

SCHEMA_VERSION = 1

_SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS runs (
        run_id TEXT PRIMARY KEY,
        started_at TEXT,  -- NULL when finish-only was recorded before any start
        finished_at TEXT,
        status TEXT NOT NULL DEFAULT 'running',
        summary_json TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS phase_executions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        phase TEXT NOT NULL,
        status TEXT NOT NULL,
        started_at TEXT,
        finished_at TEXT,
        duration_ms INTEGER,
        result_path TEXT,
        result_json TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_phase_executions_run_phase ON phase_executions(run_id, phase)",
    """
    CREATE TABLE IF NOT EXISTS artifacts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        phase TEXT NOT NULL,
        artifact_type TEXT NOT NULL,
        path TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS dead_letters (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT NOT NULL REFERENCES runs(run_id) ON DELETE CASCADE,
        phase TEXT NOT NULL,
        record_json TEXT NOT NULL,
        failure_class TEXT NOT NULL,
        detail TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS lead_fingerprints (
        fingerprint TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        phase TEXT NOT NULL,
        created_at TEXT NOT NULL
    )
    """,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _dump_json(payload: Any) -> str | None:
    """Serialize ``payload`` to JSON, never raising.

    Unserializable values fall back to ``repr`` via ``default``; if even that
    fails (exotic objects raising inside ``repr``), the whole payload degrades
    to its ``repr`` string.
    """
    if payload is None:
        return None
    try:
        return json.dumps(payload, default=repr, sort_keys=True)
    except Exception:  # noqa: BLE001 - deliberate: serialization must never raise (R1-02 spec)
        return repr(payload)


class StateDB:
    """Write-through SQLite mirror of pipeline run state.

    Args:
        workspace: Pipeline workspace root. The DB defaults to
            ``<workspace>/runs/state.db`` (auto-created).
        db_path: Explicit DB file path overriding the workspace-derived
            default. Parent directories are created as needed.
    """

    def __init__(self, workspace: str | Path, *, db_path: str | Path | None = None) -> None:
        resolved = Path(db_path) if db_path is not None else Path(workspace) / "runs" / "state.db"
        resolved.parent.mkdir(parents=True, exist_ok=True)
        self.path = resolved
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(resolved), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._migrate()

    # -- lifecycle ---------------------------------------------------------

    def _migrate(self) -> None:
        """Create missing tables and stamp the schema version (idempotent)."""
        with self._lock, self._conn:
            self._conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_version "
                "(version INTEGER NOT NULL, applied_at TEXT NOT NULL)"
            )
            row = self._conn.execute("SELECT MAX(version) FROM schema_version").fetchone()
            current = int(row[0]) if row and row[0] is not None else 0
            for statement in _SCHEMA_STATEMENTS:
                self._conn.execute(statement)
            if current < SCHEMA_VERSION:
                self._conn.execute(
                    "INSERT INTO schema_version(version, applied_at) VALUES (?, ?)",
                    (SCHEMA_VERSION, _now()),
                )

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    # -- runs ----------------------------------------------------------------

    def _ensure_run(self, run_id: str) -> None:
        """Best-effort parent-row creation so child FKs never block recording.

        Only valid inside an open transaction on ``self._conn`` (callers hold
        ``self._lock``). A run row created here stays ``running`` until
        :meth:`record_run_finish` (or :meth:`record_run_start` for an explicit
        start) updates it.
        """
        self._conn.execute(
            "INSERT OR IGNORE INTO runs(run_id, started_at, status) VALUES (?, ?, 'running')",
            (run_id, _now()),
        )

    def record_run_start(self, run_id: str, *, started_at: str | None = None, summary: dict | None = None) -> None:
        """Insert (or reset) a run row in ``running`` state."""
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO runs(run_id, started_at, status, summary_json) VALUES (?, ?, 'running', ?) "
                "ON CONFLICT(run_id) DO UPDATE SET started_at=excluded.started_at, "
                "finished_at=NULL, status='running', summary_json=excluded.summary_json",
                (run_id, started_at or _now(), _dump_json(summary)),
            )

    def record_run_finish(
        self, run_id: str, *, status: str = "done", finished_at: str | None = None, summary: dict | None = None
    ) -> None:
        """Mark a run finished; creates the row if the start was never recorded.

        When the start was never recorded the row is created with a NULL
        ``started_at`` — inventing one would make resume logic (R1-03) read a
        fake run duration.
        """
        with self._lock, self._conn:
            self._conn.execute(
                "INSERT INTO runs(run_id, started_at, finished_at, status, summary_json) "
                "VALUES (?, NULL, ?, ?, ?) "
                "ON CONFLICT(run_id) DO UPDATE SET finished_at=excluded.finished_at, "
                "status=excluded.status, summary_json=excluded.summary_json",
                (run_id, finished_at or _now(), status, _dump_json(summary)),
            )

    def latest_run(self) -> dict | None:
        """Return the most recently started run as a dict, or ``None``."""
        with self._lock:
            row = self._conn.execute("SELECT * FROM runs ORDER BY started_at DESC LIMIT 1").fetchone()
        return dict(row) if row else None

    def is_run_complete(self, run_id: str) -> bool:
        """Heuristic: a run is complete when it has recorded phases and all are ``done``."""
        with self._lock:
            row = self._conn.execute(
                "SELECT COUNT(*) AS total, "
                "SUM(CASE WHEN status = 'done' THEN 1 ELSE 0 END) AS done_count "
                "FROM phase_executions WHERE run_id = ?",
                (run_id,),
            ).fetchone()
        return bool(row and row["total"] and row["total"] == row["done_count"])

    # -- phase executions ----------------------------------------------------

    def record_phase_execution(
        self,
        run_id: str,
        phase: str,
        status: str,
        *,
        result: dict | None = None,
        result_path: str | None = None,
        started_at: str | None = None,
        finished_at: str | None = None,
        duration_ms: int | None = None,
    ) -> None:
        """Record one phase execution (write-through mirror of its result envelope).

        ``result`` is serialized defensively: unserializable values never raise.
        If ``started_at``/``finished_at`` are both given and ``duration_ms`` is
        omitted, the duration is derived from the ISO timestamps.
        """
        if duration_ms is None and started_at and finished_at:
            try:
                delta = datetime.fromisoformat(finished_at) - datetime.fromisoformat(started_at)
                duration_ms = max(0, round(delta.total_seconds() * 1000))
            except ValueError:
                duration_ms = None
        with self._lock, self._conn:
            self._ensure_run(run_id)
            self._conn.execute(
                "INSERT INTO phase_executions(run_id, phase, status, started_at, finished_at, "
                "duration_ms, result_path, result_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    run_id,
                    phase,
                    status,
                    started_at,
                    finished_at,
                    duration_ms,
                    result_path,
                    _dump_json(result),
                ),
            )

    def get_phase_execution(self, run_id: str, phase: str) -> dict | None:
        """Return the most recent execution of ``phase`` in ``run_id``, or ``None``."""
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM phase_executions WHERE run_id = ? AND phase = ? "
                "ORDER BY id DESC LIMIT 1",
                (run_id, phase),
            ).fetchone()
        return dict(row) if row else None

    # -- artifacts / dead letters / fingerprints ------------------------------

    def record_artifact(
        self, run_id: str, phase: str, artifact_type: str, path: str, *, created_at: str | None = None
    ) -> bool:
        """Record an artifact path; ``path`` is unique so duplicates are ignored.

        Returns ``True`` when a new row was inserted, ``False`` when the path
        was already recorded.
        """
        with self._lock, self._conn:
            self._ensure_run(run_id)
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO artifacts(run_id, phase, artifact_type, path, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (run_id, phase, artifact_type, path, created_at or _now()),
            )
        return cursor.rowcount > 0

    def has_fingerprint(self, fingerprint: str, *, exclude_run_id: str | None = None) -> bool:
        """Read-only check whether a fingerprint was recorded before.

        With ``exclude_run_id`` the lookup ignores rows recorded by that run —
        used on resume, where the current run's own fingerprints must not
        filter out the leads it already kept.
        """
        with self._lock:
            if exclude_run_id is None:
                row = self._conn.execute(
                    "SELECT 1 FROM lead_fingerprints WHERE fingerprint = ? LIMIT 1",
                    (fingerprint,),
                ).fetchone()
            else:
                row = self._conn.execute(
                    "SELECT 1 FROM lead_fingerprints WHERE fingerprint = ? AND run_id != ? LIMIT 1",
                    (fingerprint, exclude_run_id),
                ).fetchone()
        return row is not None

    def record_dead_letter(
        self,
        run_id: str,
        phase: str,
        record: dict,
        failure_class: FailureClass | str,
        *,
        detail: str = "",
        created_at: str | None = None,
    ) -> None:
        """Record a dead letter using the canonical :class:`FailureClass` taxonomy."""
        class_value = failure_class.value if isinstance(failure_class, FailureClass) else str(failure_class)
        with self._lock, self._conn:
            self._ensure_run(run_id)
            self._conn.execute(
                "INSERT INTO dead_letters(run_id, phase, record_json, failure_class, detail, created_at) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (run_id, phase, _dump_json(record) or "{}", class_value, detail, created_at or _now()),
            )

    def list_dead_letters(self, run_id: str | None = None, limit: int = 100) -> list[dict]:
        """Return recorded dead letters, newest first (R1-05 read helper).

        Args:
            run_id: Filter to one run when given; ``None`` returns all runs.
            limit: Maximum number of rows to return.
        """
        with self._lock:
            if run_id is None:
                rows = self._conn.execute(
                    "SELECT * FROM dead_letters ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
            else:
                rows = self._conn.execute(
                    "SELECT * FROM dead_letters WHERE run_id = ? ORDER BY id DESC LIMIT ?",
                    (run_id, limit),
                ).fetchall()
        return [dict(row) for row in rows]

    def phase_metrics(self, run_id: str) -> list[dict]:
        """Return one metrics row per recorded phase of ``run_id`` (R1-06).

        Each row carries ``phase``, ``status``, ``duration_ms`` and ``counts``
        (the counts stored in the recorded result payload). Rows recorded
        without a counts block fall back to status-derived counts.
        """
        with self._lock:
            rows = self._conn.execute(
                "SELECT phase, status, duration_ms, result_json FROM phase_executions "
                "WHERE run_id = ? ORDER BY id",
                (run_id,),
            ).fetchall()
        metrics: list[dict] = []
        for row in rows:
            counts: dict = {}
            if row["result_json"]:
                try:
                    payload = json.loads(row["result_json"])
                except ValueError:
                    payload = None
                if isinstance(payload, dict) and isinstance(payload.get("counts"), dict):
                    counts = payload["counts"]
            if not counts:
                counts = (
                    {"records_succeeded": 1} if row["status"] in ("done", "needs_review") else {"records_failed": 1}
                )
            metrics.append(
                {
                    "phase": row["phase"],
                    "status": row["status"],
                    "duration_ms": row["duration_ms"],
                    "counts": counts,
                }
            )
        return metrics

    def record_lead_fingerprint(
        self, fingerprint: str, run_id: str, phase: str, *, created_at: str | None = None
    ) -> bool:
        """Record a lead fingerprint; returns ``False`` if it was already seen (dedupe)."""
        with self._lock, self._conn:
            cursor = self._conn.execute(
                "INSERT OR IGNORE INTO lead_fingerprints(fingerprint, run_id, phase, created_at) "
                "VALUES (?, ?, ?, ?)",
                (fingerprint, run_id, phase, created_at or _now()),
            )
        return cursor.rowcount > 0
