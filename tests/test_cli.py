"""Tests for the CLI surface (cli.py)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

import pytest

import cli


def test_normalize_input_defaults() -> None:
    user_input = cli._normalize_input({"well_name": "X-1"})
    assert user_input["well_name"] == "X-1"
    assert user_input["seismic_data"] == {}
    assert user_input["well_log_data"] == {}
    assert user_input["seismic_csv_path"] is None
    assert user_input["seam_well_number"] == 1


def test_normalize_input_preserves_optional_fields() -> None:
    raw: Dict[str, Any] = {
        "well_name": "X-2",
        "trap_type": "stratigraphic",
        "closure_area": 12.0,
        "grv": 80.0,
        "quality_threshold": 0.55,
    }
    user_input = cli._normalize_input(raw)
    assert user_input["trap_type"] == "stratigraphic"
    assert user_input["closure_area"] == 12.0
    assert user_input["grv"] == 80.0
    assert user_input["quality_threshold"] == 0.55


def test_cli_info(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["info"])
    captured = capsys.readouterr().out
    assert rc == 0
    body = json.loads(captured)
    assert body["version"]
    assert "config" in body


def test_cli_tools(capsys: pytest.CaptureFixture[str]) -> None:
    rc = cli.main(["tools"])
    captured = capsys.readouterr().out
    assert rc == 0
    body = json.loads(captured)
    assert body["total_tools"] >= 10
    assert "analyze_seismic_amplitude" in body["tools"]


def test_cli_examples_lists_files(capsys: pytest.CaptureFixture[str], repo_root: Path) -> None:
    rc = cli.main(["examples"])
    captured = capsys.readouterr().out
    assert rc == 0
    body = json.loads(captured)
    assert len(body["inputs"]) >= 3


def test_cli_analyze_writes_output(
    tmp_path: Path, repo_root: Path, first_input_example: Dict[str, Any]
) -> None:
    input_path = tmp_path / "input.json"
    input_path.write_text(json.dumps(first_input_example), encoding="utf-8")
    out_path = tmp_path / "out.json"

    rc = cli.main(["analyze", "--input", str(input_path), "--output", str(out_path), "--quick"])
    assert rc == 0
    body = json.loads(out_path.read_text(encoding="utf-8"))
    assert body["status"] in {"success", "partial", "blocked"}
    assert "agents_executed" in body

