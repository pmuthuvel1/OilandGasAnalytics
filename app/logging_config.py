"""Structured (JSON) logging setup for the Oil & Gas Analytics system.

Use :func:`configure_logging` once at process start (``run.py`` / ``run_ui.py``
/ ``cli.py``). All subsequent ``logging.getLogger(__name__)`` calls inherit the
configuration. When ``JSON_LOGS=true`` (or ``APP_ENV=production``), the
formatter emits one JSON object per line — easy to ingest into Datadog,
Splunk, Loki, ELK, etc. Otherwise we render the classic human-readable form.

The :class:`ContextFilter` injects a per-request ``request_id`` and per-run
``trace_id`` when the calling code sets them via :func:`set_context`.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import threading
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional

# ---------------------------------------------------------------------------
# Context (thread-local) so log records can carry request/trace correlation
# ---------------------------------------------------------------------------
_CTX = threading.local()


def set_context(**fields: Any) -> None:
    """Attach key/value pairs to the calling thread's log context."""
    current: Dict[str, Any] = getattr(_CTX, "fields", {}) or {}
    current.update({k: v for k, v in fields.items() if v is not None})
    _CTX.fields = current


def clear_context(*keys: str) -> None:
    """Remove keys (or the whole context if no keys given) from the thread."""
    if not hasattr(_CTX, "fields"):
        return
    if not keys:
        _CTX.fields = {}
        return
    for key in keys:
        _CTX.fields.pop(key, None)


def get_context() -> Dict[str, Any]:
    """Return a copy of the current thread-local context."""
    return dict(getattr(_CTX, "fields", {}) or {})


class ContextFilter(logging.Filter):
    """Inject thread-local context into every record."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: D401
        for key, value in get_context().items():
            setattr(record, key, value)
        return True


# ---------------------------------------------------------------------------
# Formatters
# ---------------------------------------------------------------------------
_RESERVED_RECORD_KEYS: frozenset = frozenset(
    {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime",
    }
)


class JSONFormatter(logging.Formatter):
    """One-line JSON log records. Safe under multi-threaded async servers."""

    def __init__(self, extra_static: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self._extra_static = extra_static or {}

    def format(self, record: logging.LogRecord) -> str:
        payload: Dict[str, Any] = {
            "ts": datetime.fromtimestamp(record.created, tz=timezone.utc)
            .isoformat(timespec="milliseconds")
            .replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack_info"] = record.stack_info
        for key, value in record.__dict__.items():
            if key in _RESERVED_RECORD_KEYS or key.startswith("_"):
                continue
            try:
                json.dumps(value, default=str)
                payload[key] = value
            except (TypeError, ValueError):
                payload[key] = str(value)
        payload.update(self._extra_static)
        try:
            return json.dumps(payload, default=str, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            return json.dumps({"level": record.levelname, "message": str(record.msg)})


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def _to_bool(value: Optional[str], default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def configure_logging(
    level: Optional[str] = None,
    json_logs: Optional[bool] = None,
    quiet_loggers: Iterable[str] = ("httpx", "urllib3", "asyncio"),
    service: str = "oil-gas-analytics",
) -> None:
    """Configure root logging exactly once. Idempotent and safe to re-call."""
    level_name = (level or os.getenv("LOG_LEVEL", "INFO")).upper()
    log_level = getattr(logging, level_name, logging.INFO)

    if json_logs is None:
        json_logs = _to_bool(
            os.getenv("JSON_LOGS"),
            default=os.getenv("APP_ENV", "").lower() == "production",
        )

    handler = logging.StreamHandler(stream=sys.stdout)
    handler.addFilter(ContextFilter())
    if json_logs:
        handler.setFormatter(JSONFormatter(extra_static={"service": service}))
    else:
        handler.setFormatter(
            logging.Formatter(
                fmt="%(asctime)s %(levelname)s %(name)s %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        )

    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(log_level)

    for noisy in quiet_loggers:
        logging.getLogger(noisy).setLevel(max(log_level, logging.WARNING))


def get_logger(name: str) -> logging.Logger:
    """Convenience wrapper around :func:`logging.getLogger`."""
    return logging.getLogger(name)

