"""Tests for packages.shared.logging_config (R1-01: structured logging)."""

from __future__ import annotations

import io
import json
import logging
import sys
from datetime import datetime

import pytest

from packages.shared.logging_config import (
    JsonLogFormatter,
    get_log_phase,
    get_log_run_id,
    set_log_context,
    setup_logging,
)


@pytest.fixture(autouse=True)
def _restore_root_logger():
    """Snapshot the root logger so setup_logging tests cannot leak state."""
    root = logging.getLogger()
    saved_handlers = root.handlers[:]
    saved_level = root.level
    yield
    root.handlers[:] = saved_handlers
    root.setLevel(saved_level)


def _make_record(msg: str = "hello", *args: object) -> logging.LogRecord:
    return logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=args or None,
        exc_info=None,
    )


def _own_handlers() -> list[logging.Handler]:
    return [h for h in logging.getLogger().handlers if getattr(h, "_autowebdelivery_handler", False)]


def test_context_defaults_are_none() -> None:
    assert get_log_run_id() is None
    assert get_log_phase() is None


def test_set_log_context_sets_and_restores() -> None:
    assert get_log_run_id() is None
    with set_log_context(run_id="run_1", phase="01"):
        assert get_log_run_id() == "run_1"
        assert get_log_phase() == "01"
        with set_log_context(run_id="run_2", phase="02"):
            assert get_log_run_id() == "run_2"
            assert get_log_phase() == "02"
        assert get_log_run_id() == "run_1"
        assert get_log_phase() == "01"
    assert get_log_run_id() is None
    assert get_log_phase() is None


def test_set_log_context_restores_on_exception() -> None:
    with pytest.raises(RuntimeError), set_log_context(run_id="run_x", phase="05"):
        raise RuntimeError("boom")
    assert get_log_run_id() is None
    assert get_log_phase() is None


def test_json_output_is_valid_json_with_required_fields() -> None:
    with set_log_context(run_id="run_abc", phase="03"):
        line = JsonLogFormatter().format(_make_record("processed %s items", 5))
    entry = json.loads(line)
    assert entry["run_id"] == "run_abc"
    assert entry["phase"] == "03"
    assert entry["message"] == "processed 5 items"
    assert entry["level"] == "INFO"
    assert entry["logger"] == "test.logger"
    # ts is ISO 8601 UTC and parseable
    parsed_ts = datetime.fromisoformat(entry["ts"])
    assert parsed_ts.tzinfo is not None


def test_json_output_omits_context_when_unset() -> None:
    entry = json.loads(JsonLogFormatter().format(_make_record("plain message")))
    assert "run_id" not in entry
    assert "phase" not in entry
    assert entry["message"] == "plain message"
    assert {"ts", "level", "logger", "message"} <= set(entry)


def test_json_formatter_survives_odd_records() -> None:
    formatter = JsonLogFormatter()
    # %-style message with missing args would raise on getMessage()
    odd = _make_record("value: %d")
    line = formatter.format(odd)
    assert json.loads(line)["message"]  # valid JSON, never raises
    # Record with a lazily-broken exc_info still formats
    rec = _make_record("with exc")
    rec.exc_info = (ValueError, ValueError("x"), None)
    entry = json.loads(formatter.format(rec))
    assert "ValueError" in entry["exc_info"]


def test_setup_logging_human_format_is_default() -> None:
    setup_logging()
    handlers = _own_handlers()
    assert len(handlers) == 1
    assert not isinstance(handlers[0].formatter, JsonLogFormatter)
    assert logging.getLogger().level == logging.INFO


def test_setup_logging_json_mode_and_verbose_level() -> None:
    setup_logging(json_logs=True, verbose=True)
    handlers = _own_handlers()
    assert len(handlers) == 1
    assert isinstance(handlers[0].formatter, JsonLogFormatter)
    assert logging.getLogger().level == logging.DEBUG


def test_setup_logging_is_idempotent() -> None:
    setup_logging()
    setup_logging(json_logs=True)
    handlers = _own_handlers()
    assert len(handlers) == 1
    assert isinstance(handlers[0].formatter, JsonLogFormatter)


def test_end_to_end_json_lines_carry_run_id_phase_ts(monkeypatch: pytest.MonkeyPatch) -> None:
    buf = io.StringIO()
    monkeypatch.setattr(sys, "stdout", buf)
    setup_logging(json_logs=True)
    logger = logging.getLogger("e2e.test")
    logger.warning("outside context")
    with set_log_context(run_id="run_e2e", phase="07"):
        logger.warning("inside context")
    lines = [l for l in buf.getvalue().splitlines() if l.strip()]
    assert len(lines) == 2
    outside = json.loads(lines[0])
    inside = json.loads(lines[1])
    assert "run_id" not in outside and "phase" not in outside
    assert inside["run_id"] == "run_e2e"
    assert inside["phase"] == "07"
    assert inside["message"] == "inside context"
    assert "ts" in inside and "ts" in outside
