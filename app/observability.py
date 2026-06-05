"""Lightweight structured observability for the agent pipeline.

Writes one JSON object per line to ``logs/events.jsonl`` (configurable via
``OBS_EVENT_FILE``) and optionally forwards spans to OpenTelemetry when
``OTEL_ENABLED=true`` and the SDK is installed. Falls back to a no-op when
OTel isn't available so the rest of the app keeps working unchanged.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Iterator

logger = logging.getLogger(__name__)

_EVENT_FILE = Path(os.getenv("OBS_EVENT_FILE", "logs/events.jsonl"))
_EVENT_FILE.parent.mkdir(parents=True, exist_ok=True)
_LOCK = threading.Lock()

_OTEL_ENABLED = os.getenv("OTEL_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}
_tracer = None
if _OTEL_ENABLED:
    try:  # pragma: no cover - optional dependency
        from opentelemetry import trace

        _tracer = trace.get_tracer("oilgas.agents")
    except Exception as exc:  # noqa: BLE001
        logger.warning("OTEL_ENABLED=true but OpenTelemetry import failed: %s", exc)
        _tracer = None


def _json_default(value: Any) -> str:
    return str(value)


def emit_event(event_type: str, **fields: Any) -> None:
    """Append a structured event to the JSONL event log."""
    record = {
        "ts": datetime.utcnow().isoformat(timespec="milliseconds") + "Z",
        "type": event_type,
        **fields,
    }
    try:
        with _LOCK, _EVENT_FILE.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, default=_json_default) + "\n")
    except Exception as exc:  # noqa: BLE001
        logger.debug("Failed to write observability event: %s", exc)


@contextmanager
def span(name: str, **attributes: Any) -> Iterator[Dict[str, Any]]:
    """Context manager: emits start/end events and (optionally) an OTel span."""
    span_id = uuid.uuid4().hex[:12]
    start = time.perf_counter()
    emit_event("span.start", name=name, span_id=span_id, attributes=attributes)
    otel_cm = _tracer.start_as_current_span(name) if _tracer else None
    otel_span = otel_cm.__enter__() if otel_cm else None
    if otel_span is not None:
        for k, v in attributes.items():
            try:
                otel_span.set_attribute(
                    k, v if isinstance(v, (str, int, float, bool)) else str(v)
                )
            except Exception:  # noqa: BLE001
                pass
    status = "ok"
    try:
        yield {"span_id": span_id}
    except Exception as exc:  # noqa: BLE001
        status = "error"
        emit_event("span.error", name=name, span_id=span_id, error=str(exc))
        if otel_span is not None:
            try:
                otel_span.record_exception(exc)
            except Exception:  # noqa: BLE001
                pass
        raise
    finally:
        if otel_cm is not None:
            otel_cm.__exit__(None, None, None)
        emit_event(
            "span.end",
            name=name,
            span_id=span_id,
            duration_ms=round((time.perf_counter() - start) * 1000, 2),
            status=status,
        )

