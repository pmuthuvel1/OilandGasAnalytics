"""Generate `output_examples/*.json` deterministically from `input_examples/`.

Designed to be invoked either by hand (``python scripts/generate_outputs.py``)
or by CI (``python scripts/generate_outputs.py --check``).

When ``--check`` is passed, the script *does not* overwrite anything. It
exits non-zero if any output would change. This is what the CI workflow uses
to make sure the bundled examples stay in sync with the deterministic
SAMPLE_MODE execution of the multi-agent stack.

The generator forces ``SAMPLE_MODE=true`` so we don't need an API key, and so
the output is reproducible (no LLM-generated text). To regenerate with live
LLM synthesis, run the CLI directly: ``python cli.py analyze --input <file>``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Output sanitization — strip volatile fields so the bundled examples are
# diff-friendly and stable across runs.
# ---------------------------------------------------------------------------
_VOLATILE_KEYS = {
    "timestamp",
    "workflow_id",
    "trace_id",
    "trace_file",
    "synthesis_timestamp",
}
# Keys whose entire value we replace with a placeholder. These are runtime-
# only fields that either grow over runs (prior_memory persisted to disk) or
# embed wall-clock timestamps into free-form strings (messages list).
_REDACTED_KEYS = {"prior_memory", "messages"}


def _normalize(value: Any) -> Any:
    if isinstance(value, dict):
        cleaned: Dict[str, Any] = {}
        for k, v in value.items():
            if k in _VOLATILE_KEYS:
                cleaned[k] = "<redacted-for-snapshot>"
                continue
            if k in _REDACTED_KEYS:
                cleaned[k] = "<redacted-for-snapshot>"
                continue
            cleaned[k] = _normalize(v)
        return cleaned
    if isinstance(value, list):
        return [_normalize(item) for item in value]
    return value


def _is_quick(raw: Dict[str, Any]) -> bool:
    return str(raw.get("analysis_type", "")).strip().lower() == "quick"


def _build_user_input(raw: Dict[str, Any]) -> Dict[str, Any]:
    # Local import keeps the CLI command lightweight.
    from cli import _normalize_input

    return _normalize_input(raw)


def _run_one(raw: Dict[str, Any]) -> Dict[str, Any]:
    from app.workflows import WorkflowOrchestrator

    orchestrator = WorkflowOrchestrator()
    user_input = _build_user_input(raw)
    if _is_quick(raw):
        return orchestrator.execute_quick_analysis(user_input)
    return orchestrator.execute_full_analysis(user_input)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------
def regenerate(
    root: Path,
    check: bool = False,
    only: Optional[Iterable[str]] = None,
) -> List[Tuple[str, str]]:
    """Regenerate every `<stem>_output.json` for each `input_examples/<stem>.json`.

    Returns a list of ``(input_name, status)`` pairs for entries that changed.
    ``status`` is one of ``"new"``, ``"updated"``, ``"unchanged"``, or ``"would-change"``
    (the last only when ``check=True``).
    """
    # Force deterministic execution.
    os.environ["SAMPLE_MODE"] = "true"
    # Isolate stateful files in a temp dir so the bundled snapshots are
    # reproducible (without this, ``prior_memory`` grows on each run as
    # ``app/memory.py`` persists summaries to disk).
    tmp_state = tempfile.mkdtemp(prefix="oga-genoutputs-")
    os.environ["PERSISTENT_MEMORY_FILE"] = str(Path(tmp_state) / "memory.json")
    os.environ["RAG_INDEX_FILE"] = str(Path(tmp_state) / "rag_index.json")
    os.environ["OBS_EVENT_FILE"] = str(Path(tmp_state) / "events.jsonl")
    # The config module caches via lru_cache — wipe so the env takes effect.
    from app.config import get_config

    get_config.cache_clear()  # type: ignore[attr-defined]

    inputs_dir = root / "input_examples"
    outputs_dir = root / "output_examples"
    outputs_dir.mkdir(parents=True, exist_ok=True)
    only_set = {s for s in (only or [])} or None

    inputs = sorted(inputs_dir.glob("*.json"))
    if not inputs:
        print("No input examples found under", inputs_dir, file=sys.stderr)
        return []

    diffs: List[Tuple[str, str]] = []
    for in_path in inputs:
        if only_set and in_path.stem not in only_set:
            continue
        raw = json.loads(in_path.read_text(encoding="utf-8"))
        result = _normalize(_run_one(raw))
        out_path = outputs_dir / f"{in_path.stem}_output.json"
        new_text = json.dumps(result, indent=2, default=str) + "\n"

        if out_path.exists():
            old_text = out_path.read_text(encoding="utf-8")
            if old_text == new_text:
                print(f"  unchanged : {out_path.name}")
                continue
            status = "would-change" if check else "updated"
        else:
            status = "would-change" if check else "new"

        if check:
            print(f"  WOULD CHANGE: {out_path.name}")
            diffs.append((in_path.name, status))
            continue

        out_path.write_text(new_text, encoding="utf-8")
        print(f"  {status:9s} : {out_path.name}")
        diffs.append((in_path.name, status))
    return diffs


def main(argv: Optional[Iterable[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Do not write files; exit non-zero if any output would change.",
    )
    parser.add_argument(
        "--only",
        nargs="*",
        default=None,
        help="Restrict to specific input file stems (without .json).",
    )
    args = parser.parse_args(list(argv) if argv is not None else None)

    # Be sure `app/` is importable when run as a script.
    repo_root = Path(__file__).resolve().parent.parent
    if str(repo_root) not in sys.path:
        sys.path.insert(0, str(repo_root))

    diffs = regenerate(repo_root, check=args.check, only=args.only)
    if args.check and diffs:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

