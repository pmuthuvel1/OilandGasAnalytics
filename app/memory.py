"""Persistent cross-session memory keyed by well/asset name.

Stores compact workflow summaries in ``logs/persistent_memory.json`` so future
runs can recall prior findings for the same well. Pure JSON, no external
dependency. Thread/process-safe enough for single-host deployments.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_MEMORY_FILE = Path(os.getenv("PERSISTENT_MEMORY_FILE", "logs/persistent_memory.json"))
_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
_MAX_PER_KEY = int(os.getenv("PERSISTENT_MEMORY_MAX_PER_KEY", "10"))
_LOCK = threading.Lock()


def _load() -> Dict[str, List[Dict[str, Any]]]:
    if not _MEMORY_FILE.exists():
        return {}
    try:
        return json.loads(_MEMORY_FILE.read_text(encoding="utf-8") or "{}")
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to load persistent memory (%s); starting fresh.", exc)
        return {}


def _save(store: Dict[str, List[Dict[str, Any]]]) -> None:
    tmp = _MEMORY_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(store, indent=2, default=str), encoding="utf-8")
    tmp.replace(_MEMORY_FILE)


def _normalize_key(user_input: Dict[str, Any]) -> str:
    return str(
        user_input.get("well_name")
        or user_input.get("asset")
        or user_input.get("project")
        or "default"
    ).strip().lower() or "default"


def recall(user_input: Dict[str, Any], limit: int = 3) -> List[Dict[str, Any]]:
    """Return up to ``limit`` previous memory entries for this well/asset."""
    with _LOCK:
        store = _load()
    key = _normalize_key(user_input)
    return list(store.get(key, []))[-limit:]


def remember(user_input: Dict[str, Any], summary: Dict[str, Any]) -> None:
    """Persist a compact workflow summary for later recall."""
    key = _normalize_key(user_input)
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "workflow_id": summary.get("workflow_id"),
        "status": summary.get("status"),
        "agents_executed": summary.get("agents_executed", []),
        "evaluation": {
            "approved": (summary.get("evaluation") or {}).get("approved"),
            "missing_evidence": (summary.get("evaluation") or {}).get("missing_evidence"),
            "weak_outputs": (summary.get("evaluation") or {}).get("weak_outputs"),
        },
        "headline_findings": _headline_findings(summary),
    }
    with _LOCK:
        store = _load()
        bucket = store.setdefault(key, [])
        bucket.append(entry)
        if len(bucket) > _MAX_PER_KEY:
            del bucket[: len(bucket) - _MAX_PER_KEY]
        try:
            _save(store)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to persist memory: %s", exc)


def _headline_findings(summary: Dict[str, Any]) -> Dict[str, Any]:
    findings = summary.get("findings") or {}
    headlines: Dict[str, Any] = {}
    for agent, result in findings.items():
        tool_results = (result or {}).get("tool_results") or {}
        # Take a small subset to keep memory compact.
        compact = {}
        for tool, payload in list(tool_results.items())[:3]:
            if isinstance(payload, dict):
                compact[tool] = {
                    k: v for k, v in list(payload.items())[:6] if not isinstance(v, (list, dict))
                }
        headlines[agent] = compact
    return headlines

