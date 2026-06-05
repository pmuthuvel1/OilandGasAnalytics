"""Shared pytest fixtures for the Oil & Gas Analytics test suite.

We always run tests in SAMPLE_MODE so they don't need an API key and are
fully deterministic. The fixtures also point logs/memory/RAG files at a
temporary directory so test runs don't pollute the repo.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Generator

import pytest

# Force SAMPLE_MODE before the app package gets imported.
os.environ.setdefault("SAMPLE_MODE", "true")
os.environ.setdefault("APP_ENV", "development")
os.environ.setdefault("LOG_LEVEL", "WARNING")
os.environ.setdefault("JSON_LOGS", "false")
os.environ.setdefault("CORS_ORIGINS", "*")
# Disable any real API key that may leak in from the shell during tests.
os.environ.pop("OPENAI_API_KEY", None)

REPO_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session", autouse=True)
def _isolate_log_paths(tmp_path_factory: pytest.TempPathFactory) -> Generator[Path, None, None]:
    """Redirect log / memory / index files to a temp dir for the whole session."""
    tmp_logs = tmp_path_factory.mktemp("oga-logs")
    os.environ["PERSISTENT_MEMORY_FILE"] = str(tmp_logs / "persistent_memory.json")
    os.environ["OBS_EVENT_FILE"] = str(tmp_logs / "events.jsonl")
    os.environ["RAG_INDEX_FILE"] = str(tmp_logs / "rag_index.json")
    os.environ["LOG_FILE"] = str(tmp_logs / "agent_logs.json")

    # Reset the cached config so the new env vars are picked up.
    from app.config import get_config

    get_config.cache_clear()  # type: ignore[attr-defined]
    yield tmp_logs


@pytest.fixture()
def sample_seismic_data() -> Dict[str, Any]:
    return {
        "well_name": "TestWell-001",
        "depth_values": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700],
        "amplitude_values": [0.5, 1.2, 2.3, 1.8, 3.2, 2.8, 1.5, 0.7],
        "frequency_content": {
            "low_freq_10_20Hz": 0.25,
            "mid_freq_20_50Hz": 0.5,
            "high_freq_50_100Hz": 0.25,
        },
    }


@pytest.fixture()
def sample_well_log_data() -> Dict[str, Any]:
    return {
        "well_name": "TestWell-001",
        "depth_values": [2000, 2100, 2200, 2300, 2400, 2500],
        "gamma_ray": [85, 78, 125, 105, 92, 72],
        "resistivity": [45, 135, 28, 160, 48, 125],
        "porosity": [16, 24, 6, 28, 14, 22],
        "depth_unit": "feet",
    }


@pytest.fixture()
def sample_user_input(
    sample_seismic_data: Dict[str, Any],
    sample_well_log_data: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "well_name": "TestWell-001",
        "seismic_data": sample_seismic_data,
        "well_log_data": sample_well_log_data,
        "user_notes": "Pytest synthetic well used in CI.",
        "quality_threshold": 0.3,
    }


@pytest.fixture()
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture()
def first_input_example(repo_root: Path) -> Dict[str, Any]:
    path = repo_root / "input_examples" / "example_1_northfield.json"
    return json.loads(path.read_text(encoding="utf-8"))

