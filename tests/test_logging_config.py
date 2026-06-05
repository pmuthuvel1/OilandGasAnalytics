"""Tests for `app/logging_config.py`."""

from __future__ import annotations

import io
import json
import logging

from app.logging_config import (
    JSONFormatter,
    clear_context,
    configure_logging,
    get_context,
    set_context,
)


def _format_record(extra: dict | None = None) -> dict:
    record = logging.LogRecord(
        name="oga.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="hello %s",
        args=("world",),
        exc_info=None,
    )
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    formatter = JSONFormatter(extra_static={"service": "oga"})
    return json.loads(formatter.format(record))


def test_json_formatter_basic_fields() -> None:
    payload = _format_record()
    assert payload["level"] == "INFO"
    assert payload["logger"] == "oga.test"
    assert payload["message"] == "hello world"
    assert payload["service"] == "oga"
    assert "ts" in payload


def test_json_formatter_includes_extra_fields() -> None:
    payload = _format_record(extra={"request_id": "abc123", "duration_ms": 42})
    assert payload["request_id"] == "abc123"
    assert payload["duration_ms"] == 42


def test_context_filter_round_trip() -> None:
    set_context(trace_id="t-1", request_id="r-1")
    try:
        assert get_context()["trace_id"] == "t-1"
    finally:
        clear_context()
    assert get_context() == {}


def test_configure_logging_is_idempotent() -> None:
    # Should not throw and should not stack handlers.
    configure_logging(level="DEBUG", json_logs=True)
    configure_logging(level="DEBUG", json_logs=True)
    assert len(logging.getLogger().handlers) == 1

