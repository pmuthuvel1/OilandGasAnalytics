"""Integration tests for the FastAPI surface."""

from __future__ import annotations

from typing import Any, Dict

import pytest
from fastapi.testclient import TestClient

# Importing run pulls in the orchestrator -> agents -> heavy LangChain deps.
# We import lazily inside the fixture so failures show up as test errors
# rather than collection errors.


@pytest.fixture(scope="module")
def client() -> TestClient:
    from run import app

    return TestClient(app)


def test_health(client: TestClient) -> None:
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "healthy"
    assert body["version"]
    # X-Request-ID is set by the middleware.
    assert resp.headers.get("X-Request-ID")


def test_info_endpoint_redacts_secrets(client: TestClient) -> None:
    resp = client.get("/info")
    assert resp.status_code == 200
    body = resp.json()
    assert "config" in body
    # In SAMPLE_MODE, the redacted API key is an empty string.
    assert body["config"]["openai_api_key"] in {"", "***"}


def test_tools_endpoint_lists_tools(client: TestClient) -> None:
    resp = client.get("/tools")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_tools"] >= 10
    assert "analyze_seismic_amplitude" in body["tools"]


def test_open_sources_endpoint(client: TestClient) -> None:
    resp = client.get("/data/open-sources")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["sources"], "SEG open-data list should be non-empty"


def test_analyze_quick_mode(client: TestClient, sample_user_input: Dict[str, Any]) -> None:
    body = {
        "well_name": sample_user_input["well_name"],
        "analysis_type": "quick",
        "seismic_data": sample_user_input["seismic_data"],
        "well_log_data": sample_user_input["well_log_data"],
        "user_notes": sample_user_input["user_notes"],
    }
    resp = client.post("/analyze", json=body)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in {"success", "partial", "blocked"}
    assert "results" in data
    assert "agents_executed" in data["results"]


def test_tool_invocation_through_endpoint(client: TestClient, sample_seismic_data: Dict[str, Any]) -> None:
    resp = client.post("/tools/analyze_seismic_amplitude", json=sample_seismic_data)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "success"
    assert body["tool"] == "analyze_seismic_amplitude"
    assert body["result"]["mean_amplitude"] > 0

