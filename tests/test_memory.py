"""Tests for cross-run persistent memory (app/memory.py)."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from app import memory as memory_module


@pytest.fixture()
def reset_memory(tmp_path, monkeypatch: pytest.MonkeyPatch):
    mem_file = tmp_path / "memory.json"
    monkeypatch.setattr(memory_module, "_MEMORY_FILE", mem_file)
    yield mem_file


def _make_summary(workflow_id: str) -> Dict[str, Any]:
    return {
        "workflow_id": workflow_id,
        "status": "success",
        "agents_executed": ["seismic_analyzer", "well_log_interpreter"],
        "evaluation": {"approved": True, "missing_evidence": [], "weak_outputs": []},
        "findings": {
            "seismic_analyzer": {
                "tool_results": {"analyze_seismic_amplitude": {"mean_amplitude": 1.5}}
            }
        },
    }


def test_remember_then_recall(reset_memory) -> None:
    payload = {"well_name": "Memory Well"}
    memory_module.remember(payload, _make_summary("wf-1"))
    memory_module.remember(payload, _make_summary("wf-2"))
    entries = memory_module.recall(payload, limit=5)
    assert len(entries) == 2
    assert {e["workflow_id"] for e in entries} == {"wf-1", "wf-2"}


def test_recall_keys_are_case_insensitive(reset_memory) -> None:
    memory_module.remember({"well_name": "Mixed Case"}, _make_summary("wf-3"))
    assert memory_module.recall({"well_name": "MIXED case"}, limit=1)

