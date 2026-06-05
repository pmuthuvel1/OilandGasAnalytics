"""Lightweight JSONL trace logging utility for agent activity.

Each trace record is appended as one JSON object per line to a per-run
trace file under ``logs/`` and also echoed to stdout for evaluator
visibility.

Record schema (one line of JSONL)::

    {
      "timestamp":      "2026-05-24T10:15:31.420Z",
      "trace_id":       "run_abc123",        # stable for the whole workflow run
      "span_id":        "span_4f8c1a9b",     # unique per individual action/event
      "agent_name":     "PlannerAgent",
      "action":         "decompose_question",
      "input_summary":  "...",               # truncated to 500 chars
      "output_summary": "...",               # truncated to 800 chars
      "target_agent":   "PaperRetrieverAgent",
      "confidence":     0.87,
      "retry_count":    0,
      "status":         "success",
      "extra":          {}
    }
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)


def utc_now() -> str:
    """Return current UTC time as ISO-8601 with millisecond precision and ``Z`` suffix.

    Example: ``2026-05-24T10:15:31.420Z``
    """
    now = datetime.now(timezone.utc)
    # millisecond precision, trailing 'Z' instead of '+00:00'
    return now.strftime("%Y-%m-%dT%H:%M:%S.") + f"{now.microsecond // 1000:03d}Z"


def new_trace_id() -> str:
    """Generate a short unique trace/run identifier (e.g. ``run_abc12345``)."""
    return f"run_{uuid.uuid4().hex[:8]}"


def new_span_id() -> str:
    """Generate a short unique span/event identifier (e.g. ``span_4f8c1a9b``).

    A span represents a single agent action within a larger trace (run).
    """
    return f"span_{uuid.uuid4().hex[:8]}"


def new_trace_file(trace_id: Optional[str] = None) -> Tuple[str, str]:
    """Create a new trace file path for the current run.

    Returns a tuple of ``(trace_file_path, trace_id)``. If ``trace_id`` is not
    supplied, a new one is generated.
    """
    if not trace_id:
        trace_id = new_trace_id()
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = LOG_DIR / f"agent_trace_{timestamp}_{trace_id}.jsonl"
    return str(path), trace_id


def write_trace(
    trace_file: str,
    agent_name: str,
    action: str,
    input_summary: str,
    output_summary: str,
    trace_id: Optional[str] = None,
    span_id: Optional[str] = None,
    target_agent: Optional[str] = None,
    confidence: Optional[float] = None,
    retry_count: int = 0,
    status: str = "success",
    extra: Optional[Dict[str, Any]] = None,
) -> None:
    """Append a single trace record to ``trace_file`` and echo to stdout.

    ``trace_id`` should be stable for an entire workflow run, while
    ``span_id`` identifies this individual action/event. If ``span_id`` is not
    provided, a fresh one is generated for the record.
    """
    record: Dict[str, Any] = {
        "timestamp": utc_now(),
        "trace_id": trace_id,
        "span_id": span_id or new_span_id(),
        "agent_name": agent_name,
        "action": action,
        "input_summary": (input_summary or "")[:500],
        "output_summary": (output_summary or "")[:800],
        "target_agent": target_agent,
        "confidence": confidence,
        "retry_count": retry_count,
        "status": status,
        "extra": extra or {},
    }

    try:
        with open(trace_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError:
        # Never let logging break the agent pipeline.
        pass

    # Also print to stdout for evaluator visibility.
    print(json.dumps(record, ensure_ascii=False))

