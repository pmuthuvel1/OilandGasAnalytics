"""Smoke tests for the deterministic analysis tools."""

from __future__ import annotations

from typing import Any, Dict

from app.tools import TOOLS


def test_tool_registry_contains_expected_tools() -> None:
    expected = {
        "analyze_seismic_amplitude",
        "detect_faults",
        "pick_horizons",
        "classify_lithology",
        "identify_fluids",
        "estimate_porosity",
        "estimate_permeability",
        "analyze_saturation",
        "predict_pressure",
        "evaluate_trap",
        "calculate_volumes",
        "assess_seal_integrity",
        "synthesize_analysis",
        "create_visualizations",
        "format_recommendations",
    }
    assert expected.issubset(set(TOOLS.keys()))


def test_seismic_amplitude_with_data(sample_seismic_data: Dict[str, Any]) -> None:
    result = TOOLS["analyze_seismic_amplitude"](sample_seismic_data)
    assert "error" not in result
    assert result["mean_amplitude"] > 0
    assert result["max_amplitude"] >= result["mean_amplitude"]


def test_seismic_amplitude_handles_empty_payload() -> None:
    result = TOOLS["analyze_seismic_amplitude"]({"amplitude_values": []})
    assert "error" in result


def test_detect_faults_returns_risk_level(sample_seismic_data: Dict[str, Any]) -> None:
    result = TOOLS["detect_faults"](sample_seismic_data)
    assert result["risk_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert isinstance(result["fault_depths"], list)


def test_pick_horizons_reports_coverage(sample_seismic_data: Dict[str, Any]) -> None:
    result = TOOLS["pick_horizons"](sample_seismic_data)
    assert 0 <= result["coverage"] <= 100
    assert isinstance(result["top_horizons"], list)


def test_classify_lithology(sample_well_log_data: Dict[str, Any]) -> None:
    result = TOOLS["classify_lithology"](sample_well_log_data)
    assert "primary_lithology" in result
    assert result["primary_lithology"]


def test_identify_fluids(sample_well_log_data: Dict[str, Any]) -> None:
    result = TOOLS["identify_fluids"](sample_well_log_data)
    assert result["primary_fluid"] in {"Oil bearing", "Gas bearing", "Water bearing"}
    assert 0 <= result["confidence"] <= 1


def test_estimate_porosity_class(sample_well_log_data: Dict[str, Any]) -> None:
    result = TOOLS["estimate_porosity"](sample_well_log_data)
    assert result["porosity_quality"] in {"Good", "Fair", "Poor"}


def test_estimate_permeability_classes(sample_well_log_data: Dict[str, Any]) -> None:
    result = TOOLS["estimate_permeability"](sample_well_log_data)
    assert result["permeability_class"] in {"Low", "Moderate", "High"}


def test_calculate_volumes_keys() -> None:
    result = TOOLS["calculate_volumes"]({"grv": 75.0, "porosity_fraction": 0.18})
    for key in (
        "gross_rock_volume_mmbbl",
        "stock_tank_volume_mmbbl",
        "recoverable_reserves_mmbbl",
    ):
        assert key in result


def test_synthesize_analysis_aggregates() -> None:
    payload = [
        {"agent_name": "A", "confidence": 0.8},
        {"agent_name": "B", "confidence": 0.6},
    ]
    result = TOOLS["synthesize_analysis"](payload)
    assert result["total_analyses"] == 2
    assert "B" in result["agents_involved"]
    assert 0 < result["overall_confidence"] <= 1

