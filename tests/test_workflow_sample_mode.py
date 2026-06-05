"""End-to-end test of the collaborative workflow in SAMPLE_MODE."""

from __future__ import annotations

from typing import Any, Dict

import pytest

from app.workflows import WorkflowOrchestrator


@pytest.fixture()
def orchestrator() -> WorkflowOrchestrator:
    return WorkflowOrchestrator()


def test_full_analysis_returns_expected_keys(
    orchestrator: WorkflowOrchestrator, sample_user_input: Dict[str, Any]
) -> None:
    result = orchestrator.execute_full_analysis(sample_user_input)
    for key in (
        "workflow_id",
        "trace_id",
        "trace_file",
        "status",
        "planner_delegation",
        "agents_executed",
        "findings",
        "seismic_analysis",
        "well_log_analysis",
        "reservoir_analysis",
        "risk_assessment",
        "final_report",
        "evaluation",
        "collaboration_log",
        "shared_memory",
        "evidence_register",
        "open_data_recommendations",
        "escalation",
    ):
        assert key in result, f"missing key {key}"
    assert result["status"] in {"success", "partial", "blocked"}
    assert isinstance(result["agents_executed"], list)
    assert result["agents_executed"], "no agents ran"


def test_quick_analysis_skips_seismic(
    orchestrator: WorkflowOrchestrator, sample_user_input: Dict[str, Any]
) -> None:
    result = orchestrator.execute_quick_analysis(sample_user_input)
    assert result["status"] in {"success", "partial", "blocked"}
    # Quick mode should not invoke the seismic analyzer.
    assert "seismic_analyzer" not in result["agents_executed"]


def test_collaboration_log_contains_planner_and_evaluator(
    orchestrator: WorkflowOrchestrator, sample_user_input: Dict[str, Any]
) -> None:
    result = orchestrator.execute_full_analysis(sample_user_input)
    agents = {entry["agent"] for entry in result["collaboration_log"]}
    assert "planner" in agents
    assert "evaluator" in agents


def test_evaluation_block_exposes_quality_score(
    orchestrator: WorkflowOrchestrator, sample_user_input: Dict[str, Any]
) -> None:
    result = orchestrator.execute_full_analysis(sample_user_input)
    evaluation = result["evaluation"]
    assert "quality_score" in evaluation
    assert 0.0 <= float(evaluation["quality_score"]) <= 1.0
    assert "report_gate" in evaluation


def test_execution_history_grows(
    orchestrator: WorkflowOrchestrator, sample_user_input: Dict[str, Any]
) -> None:
    orchestrator.clear_history()
    orchestrator.execute_quick_analysis(sample_user_input)
    orchestrator.execute_quick_analysis(sample_user_input)
    assert len(orchestrator.get_execution_history()) == 2

