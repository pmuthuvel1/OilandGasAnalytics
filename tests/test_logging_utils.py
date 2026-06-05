"""Tests for the deterministic per-run trace logging utility."""

from __future__ import annotations

import json
from pathlib import Path

from app.logging_utils import new_trace_file, new_trace_id, utc_now, write_trace


def test_utc_now_format() -> None:
    ts = utc_now()
    assert ts.endswith("Z")
    assert "T" in ts


def test_new_trace_id_is_unique() -> None:
    a = new_trace_id()
    b = new_trace_id()
    assert a != b
    assert a.startswith("run_")


def test_write_trace_appends_jsonl(tmp_path: Path) -> None:
    trace_file = str(tmp_path / "trace.jsonl")
    trace_id = "run_xyz"

    write_trace(
        trace_file,
        agent_name="PlannerAgent",
        action="delegate",
        input_summary="some input",
        output_summary="some output",
        trace_id=trace_id,
        target_agent="EvaluatorAgent",
        confidence=0.91,
        retry_count=0,
        status="success",
        extra={"iteration": 1},
    )
    write_trace(
        trace_file,
        agent_name="EvaluatorAgent",
        action="evaluate",
        input_summary="critique",
        output_summary="approved",
        trace_id=trace_id,
        status="approved",
    )

    lines = Path(trace_file).read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2

    first = json.loads(lines[0])
    assert first["trace_id"] == trace_id
    assert first["agent_name"] == "PlannerAgent"
    assert first["action"] == "delegate"
    assert first["target_agent"] == "EvaluatorAgent"
    assert first["confidence"] == 0.91
    assert first["status"] == "success"
    assert first["extra"] == {"iteration": 1}
    assert first["timestamp"].endswith("Z")


def test_new_trace_file_returns_tuple(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path, trace_id = new_trace_file()
    assert trace_id.startswith("run_")
    assert path.endswith(".jsonl")
    assert "agent_trace_" in path

