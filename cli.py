"""Command-line interface for the Oil & Gas Analytics multi-agent system.

Examples
--------
Run a single analysis from an input JSON file::

    python cli.py run --input input_examples/example_1_northfield.json

Force quick analysis and write the result somewhere specific::

    python cli.py run --input input.json --quick --output result.json

Run a batch from a directory of input files::

    python cli.py batch --input-dir input_examples --output-dir runs/$(date +%s)

List available tools / agents::

    python cli.py info
    python cli.py tools

Regenerate the bundled output examples from input examples (deterministic)::

    SAMPLE_MODE=true python cli.py regen-outputs

The legacy subcommand name ``analyze`` is kept as an alias of ``run`` for
backward compatibility, mirroring the new canonical HTTP path ``/run``
exposed by ``run.py`` (``/analyze`` is now a deprecated alias of ``/run``).

All commands honor ``SAMPLE_MODE=true`` for deterministic execution without
an API key, and ``OPENAI_API_KEY`` / ``OPENAI_BASE_URL`` for live runs.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

from app import __version__
from app.config import get_config
from app.logging_config import configure_logging, get_logger

logger = get_logger("oilgas.cli")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise SystemExit(f"Input file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc


def _normalize_input(raw: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize raw input JSON to the dict shape expected by the orchestrator."""
    user_input: Dict[str, Any] = {
        "well_name": raw.get("well_name") or raw.get("name") or "unnamed well",
        "seismic_data": raw.get("seismic_data") or {},
        "well_log_data": raw.get("well_log_data") or {},
        "seismic_csv_path": raw.get("seismic_csv_path"),
        "well_log_csv_path": raw.get("well_log_csv_path"),
        "seam_well_number": raw.get("seam_well_number", 1),
        "user_notes": raw.get("user_notes") or "",
    }
    for optional_key in ("quality_threshold", "trap_type", "closure_area", "spill_depth", "grv"):
        if optional_key in raw:
            user_input[optional_key] = raw[optional_key]
    return user_input


def _write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _run_orchestrator(user_input: Dict[str, Any], quick: bool) -> Dict[str, Any]:
    # Import lazily so simple commands (info/tools) stay fast.
    from app.workflows import WorkflowOrchestrator

    orchestrator = WorkflowOrchestrator()
    if quick:
        return orchestrator.execute_quick_analysis(user_input)
    return orchestrator.execute_full_analysis(user_input)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_run(args: argparse.Namespace) -> int:
    input_path = Path(args.input).resolve()
    raw = _load_json(input_path)
    user_input = _normalize_input(raw)

    quick = args.quick or (str(raw.get("analysis_type", "")).lower() == "quick")
    logger.info(
        "Running analysis",
        extra={
            "input_file": str(input_path),
            "well_name": user_input["well_name"],
            "mode": "quick" if quick else "full",
            "sample_mode": get_config().SAMPLE_MODE,
        },
    )
    result = _run_orchestrator(user_input, quick=quick)

    if args.output:
        out_path = Path(args.output).resolve()
        _write_json(out_path, result)
        logger.info("Wrote analysis result", extra={"output_file": str(out_path)})
    else:
        json.dump(result, sys.stdout, indent=2, default=str)
        sys.stdout.write("\n")
    return 0


# Back-compat alias for older scripts that still invoke ``cmd_analyze``.
cmd_analyze = cmd_run


def cmd_batch(args: argparse.Namespace) -> int:
    input_dir = Path(args.input_dir).resolve()
    if not input_dir.is_dir():
        raise SystemExit(f"--input-dir must be a directory: {input_dir}")
    output_dir = Path(args.output_dir).resolve()
    files = sorted(input_dir.glob("*.json"))
    if not files:
        raise SystemExit(f"No *.json files found under {input_dir}")
    failed: List[str] = []
    for path in files:
        try:
            raw = _load_json(path)
            user_input = _normalize_input(raw)
            quick = args.quick or (str(raw.get("analysis_type", "")).lower() == "quick")
            result = _run_orchestrator(user_input, quick=quick)
            out = output_dir / f"{path.stem}_output.json"
            _write_json(out, result)
            logger.info(
                "Batch item complete",
                extra={"input": path.name, "output": out.name, "status": result.get("status")},
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Batch item failed: %s", path.name)
            failed.append(f"{path.name}: {exc}")
    if failed:
        logger.error("Batch finished with %d failure(s)", len(failed))
        for line in failed:
            sys.stderr.write(f"  - {line}\n")
        return 1
    return 0


def cmd_info(_args: argparse.Namespace) -> int:
    cfg = get_config()
    info = {
        "version": __version__,
        "config": cfg.safe_dict(),
    }
    json.dump(info, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


def cmd_tools(_args: argparse.Namespace) -> int:
    from app.tools import TOOLS

    payload = {
        "total_tools": len(TOOLS),
        "tools": sorted(TOOLS.keys()),
    }
    json.dump(payload, sys.stdout, indent=2, default=str)
    sys.stdout.write("\n")
    return 0


def cmd_examples(_args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parent
    inputs = sorted((root / "input_examples").glob("*.json"))
    outputs = sorted((root / "output_examples").glob("*.json"))
    payload = {
        "inputs": [str(p.relative_to(root)) for p in inputs],
        "outputs": [str(p.relative_to(root)) for p in outputs],
    }
    json.dump(payload, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def cmd_regen_outputs(args: argparse.Namespace) -> int:
    from scripts.generate_outputs import regenerate

    diffs = regenerate(
        Path(__file__).resolve().parent,
        check=args.check,
        only=args.only,
    )
    if args.check and diffs:
        sys.stderr.write(
            "output_examples are out of sync with code; run "
            "`python cli.py regen-outputs` to refresh them.\n"
        )
        return 1
    return 0


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------
def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="oilgas",
        description=(
            "Oil & Gas Analytics CLI — run multi-agent analyses, inspect "
            "configuration, and regenerate bundled sample outputs."
        ),
    )
    parser.add_argument("--version", action="version", version=f"oilgas {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    # ``run`` is the canonical subcommand (mirrors the canonical HTTP path
    # ``/run`` in run.py). ``analyze`` is kept as an alias for backward
    # compatibility with older docs / shell scripts.
    p_run = sub.add_parser(
        "run",
        aliases=["analyze"],
        help="Run a single multi-agent analysis",
    )
    p_run.add_argument("--input", required=True, help="Path to input JSON file")
    p_run.add_argument("--output", help="Optional output JSON path (defaults to stdout)")
    p_run.add_argument("--quick", action="store_true", help="Force quick analysis mode")
    p_run.set_defaults(func=cmd_run)

    p_batch = sub.add_parser("batch", help="Run all *.json inputs in a directory")
    p_batch.add_argument("--input-dir", required=True)
    p_batch.add_argument("--output-dir", required=True)
    p_batch.add_argument("--quick", action="store_true")
    p_batch.set_defaults(func=cmd_batch)

    p_info = sub.add_parser("info", help="Show system + redacted config info")
    p_info.set_defaults(func=cmd_info)

    p_tools = sub.add_parser("tools", help="List registered domain tools")
    p_tools.set_defaults(func=cmd_tools)

    p_examples = sub.add_parser("examples", help="List bundled input / output examples")
    p_examples.set_defaults(func=cmd_examples)

    p_regen = sub.add_parser(
        "regen-outputs",
        help="Regenerate output_examples/ from input_examples/ (SAMPLE_MODE recommended)",
    )
    p_regen.add_argument("--check", action="store_true", help="Fail if outputs would change")
    p_regen.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Restrict to specific input file stems (without .json)",
    )
    p_regen.set_defaults(func=cmd_regen_outputs)
    return parser


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)

    cfg = get_config()
    configure_logging(level=cfg.LOG_LEVEL, json_logs=cfg.JSON_LOGS)

    try:
        return int(args.func(args) or 0)
    except KeyboardInterrupt:
        logger.warning("Interrupted")
        return 130


if __name__ == "__main__":
    raise SystemExit(main())

