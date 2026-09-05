"""Structured logging configuration (R1-01).

Stdlib-only logging setup for the pipeline: a JSON formatter that emits one
JSON object per record (``ts``, ``level``, ``logger``, ``message`` plus the
ambient ``run_id``/``phase`` context) and a ``setup_logging`` entry point that
configures the ROOT logger — human-readable console output by default, one-line
JSON when requested (CLI: ``--json-logs``).

Ambient context (``run_id``, ``phase``) is carried in ``contextvars`` and set
by pipeline code via :func:`set_log_context`, so every log line emitted during
a phase automatically carries that phase's context without threading extra
arguments through call sites.

Note on ``structlog``: it remains an *optional* extra for richer structured
logging — it is NOT a dependency of this project and nothing here requires it
(acceptance criterion for R1-01). The stdlib implementation is intentionally
dependency-free.
"""

from __future__ import annotations

import datetime as _dt
import json
import logging
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

__all__ = [
    "JsonLogFormatter",
    "get_log_phase",
    "get_log_run_id",
    "set_log_context",
    "setup_logging",
]

# Module-private ambient context (defaults: no run/phase context attached).
_run_id_var: ContextVar[str | None] = ContextVar("awd_log_run_id", default=None)
_phase_var: ContextVar[str | None] = ContextVar("awd_log_phase", default=None)

_HUMAN_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
_HANDLER_TAG = "_autowebdelivery_handler"


def get_log_run_id() -> str | None:
    """Return the ambient ``run_id`` for logging, or ``None`` if unset."""
    return _run_id_var.get()


def get_log_phase() -> str | None:
    """Return the ambient ``phase`` for logging, or ``None`` if unset."""
    return _phase_var.get()


@contextmanager
def set_log_context(run_id: str | None = None, phase: str | None = None) -> Iterator[None]:
    """Set ambient logging context for the duration of the ``with`` block.

    Both fields are optional; passing ``None`` clears that field for the
    duration. Previous values are always restored on exit (including on
    exception).
    """
    run_token = _run_id_var.set(run_id)
    phase_token = _phase_var.set(phase)
    try:
        yield
    finally:
        _run_id_var.reset(run_token)
        _phase_var.reset(phase_token)


class JsonLogFormatter(logging.Formatter):
    """One-JSON-object-per-record formatter.

    Always emits ``ts`` (ISO 8601 UTC), ``level``, ``logger`` and ``message``;
    includes ``run_id``/``phase`` only when ambient context is set. Never
    raises: records that cannot be formatted fall back to a minimal JSON error
    line rather than breaking logging.
    """

    def format(self, record: logging.LogRecord) -> str:
        try:
            entry: dict[str, Any] = {
                "ts": _dt.datetime.fromtimestamp(
                    record.created, tz=_dt.timezone.utc
                ).isoformat(timespec="milliseconds"),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            run_id = _run_id_var.get()
            phase = _phase_var.get()
            if run_id is not None:
                entry["run_id"] = run_id
            if phase is not None:
                entry["phase"] = phase
            if record.exc_info:
                entry["exc_info"] = self.formatException(record.exc_info)
            return json.dumps(entry, ensure_ascii=False, default=str)
        except Exception:  # noqa: BLE001 - defensive boundary: logging must never raise (R1-01)
            try:
                return json.dumps(
                    {
                        "ts": _dt.datetime.now(_dt.timezone.utc).isoformat(
                            timespec="milliseconds"
                        ),
                        "level": "ERROR",
                        "logger": "logging",
                        "message": "unformattable log record",
                    },
                    ensure_ascii=False,
                )
            except Exception:  # noqa: BLE001 - absolute last resort: return static line
                return '{"level": "ERROR", "logger": "logging", "message": "unformattable log record"}'


def setup_logging(*, json_logs: bool = False, verbose: bool = False) -> None:
    """Configure the ROOT logger for pipeline runs.

    Human-readable console output by default (matches the previous
    ``logging.basicConfig`` behaviour); one-line JSON when ``json_logs=True``.
    Idempotent: only handlers created by this function are managed, so calling
    twice never duplicates them and foreign handlers (e.g. test harnesses) are
    left untouched.
    """
    root = logging.getLogger()
    level = logging.DEBUG if verbose else logging.INFO
    root.setLevel(level)

    # Replace only our own previous handler (tagged below) — keeps repeated
    # calls idempotent without clobbering handlers installed by others.
    for handler in list(root.handlers):
        if getattr(handler, _HANDLER_TAG, False):
            root.removeHandler(handler)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonLogFormatter() if json_logs else logging.Formatter(_HUMAN_FORMAT))
    setattr(handler, _HANDLER_TAG, True)
    root.addHandler(handler)
