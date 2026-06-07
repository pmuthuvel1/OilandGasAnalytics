"""Primary UI Server for Oil & Gas Analytics — runs on port 8001.

This is the main dashboard (was previously ``run_ui2.py``). It adds a
Sample-Test-Data dropdown covering both **success** and **failure**
scenarios, an agent-collaboration trace table, a matplotlib drilling
decision dashboard, and a final-verdict card.

Behaviour:
    * Success samples are loaded from ``input_examples/*.json`` at startup
      (the same files shipped with the project).
    * Failure samples are crafted inline to exercise validation errors,
      escalation, weak-evidence critique loops, and CSV-loader failures.
    * All other logic (CORS, logging, backend proxy, API target) mirrors
      the legacy ``run_ui_old.py``.

Run with:
    python run_ui.py
or:
    UI_PORT=8001 python run_ui.py
"""

from __future__ import annotations

import base64
import io
import json
import math
import os
import socket
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Matplotlib in headless mode — must be set BEFORE importing pyplot.
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from app import __version__
from app.config import get_config
from app.logging_config import configure_logging, get_logger

# --------------------------------------------------------------------------- #
# Bootstrap (mirrors run_ui_old.py)                                           #
# --------------------------------------------------------------------------- #
config = get_config()
configure_logging(level=config.LOG_LEVEL, json_logs=config.JSON_LOGS)
logger = get_logger("run_ui")


def _api_key_status(value: str) -> str:
    """Return ``configured`` / ``not configured`` — never the secret itself."""
    return "configured" if value and value.strip() else "not configured"


# The API key itself is NEVER printed (not even masked) — only its
# presence status and source are logged.
logger.info(
    "OPENAI_API_KEY: %s (source=%s)",
    _api_key_status(config.OPENAI_API_KEY),
    config.OPENAI_API_KEY_SOURCE,
)
logger.info(
    "LLM config: base_url=%s (source=%s) chat=%s reasoning=%s llm_enabled=%s",
    config.OPENAI_BASE_URL,
    config.OPENAI_BASE_URL_SOURCE,
    config.COMPASS_CHAT_MODEL,
    config.COMPASS_REASONING_MODEL,
    config.llm_enabled,
)

API_BASE_URL = config.API_BASE_URL
# UI_PORT lets ops override the default 8001 without touching code. We
# fall back to ``config.UI_PORT`` (which itself defaults to 8001) so the
# rest of the codebase stays consistent.
UI_PORT = int(os.getenv("UI_PORT", str(config.UI_PORT or 8001)))
# When UI_PORT_AUTO=true (default) we hop to the next free port if the
# requested one is taken — avoids the macOS "Address already in use" loop
# when a previous instance is still bound.
UI_PORT_AUTO = os.getenv("UI_PORT_AUTO", "true").strip().lower() in {"1", "true", "yes", "on"}
UI_PORT_RANGE = int(os.getenv("UI_PORT_RANGE", "20"))


def _port_is_free(host: str, port: int) -> bool:
    """Return True iff ``host:port`` can be bound right now."""
    # We bind both IPv4 and (best-effort) check by trying to bind on the
    # requested host. SO_REUSEADDR mimics what uvicorn does so the check
    # is representative.
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind((host if host not in {"", "0.0.0.0"} else "0.0.0.0", port))
        except OSError:
            return False
        return True
    finally:
        sock.close()


def _pick_port(host: str, preferred: int, span: int) -> Optional[int]:
    """Return ``preferred`` if free, otherwise scan forward up to ``span``."""
    if _port_is_free(host, preferred):
        return preferred
    for candidate in range(preferred + 1, preferred + 1 + span):
        if _port_is_free(host, candidate):
            return candidate
    return None


# --------------------------------------------------------------------------- #
# Sample-test-data catalogue                                                  #
# --------------------------------------------------------------------------- #
INPUT_EXAMPLES_DIR = Path(__file__).parent / "input_examples"


# Friendly labels & descriptions for the bundled success examples.
# Keys match the file stem inside ``input_examples/``.
SUCCESS_META: Dict[str, Dict[str, str]] = {
    "example_1_northfield": {
        "label": "1. North Field — Bright-spot exploration",
        "description": "Full analysis. Shallow sand target with seismic bright spot at ~2300 ft. Expects standard end-to-end run.",
    },
    "example_2_central_basin": {
        "label": "2. Central Basin — Multi-sand targets",
        "description": "Full analysis. Stacked pay zones with good seal. Demonstrates multi-horizon picking and reservoir characterization.",
    },
    "example_3_eastern": {
        "label": "3. Eastern Prospect — Quick farmout look",
        "description": "Quick analysis path. Shallow water, lightweight workflow for screening / farmout decks.",
    },
    "example_4_deepwater_gulf": {
        "label": "4. Deepwater Gulf — Subsalt Class-III AVO",
        "description": "Full analysis with quality_threshold=0.65. Subsalt turbidite with strong amplitude anomaly; high capex — gates the report on quality.",
    },
    "example_5_permian_mature": {
        "label": "5. Permian Mature — Carbonate infill",
        "description": "Full analysis. Mature pressure-depleted carbonate; looks for bypassed pay. Moderate quality gate (0.55).",
    },
    "example_6_heavy_oil_shallow": {
        "label": "6. Heavy Oil Shallow — Bitumen / SAGD",
        "description": "Full analysis. Unconsolidated shallow heavy-oil sand; thin cap rock. Tests soft-sand reservoir branch.",
    },
    "example_7_tight_gas_appalachia": {
        "label": "7. Tight Gas Appalachia — Strat trap",
        "description": "Full analysis. Sub-6% porosity gas-saturated sand; productivity depends on completion design. Lower quality gate (0.45).",
    },
    "example_8_faulted_high_risk": {
        "label": "8. Faulted High Risk — Compartmentalized",
        "description": "Full analysis with quality_threshold=0.7. Heavily faulted seal-integrity risk; intended to trigger evaluator critique cycles.",
    },
    "example_9_csv_loader": {
        "label": "9. CSV Loader — On-disk seismic + log",
        "description": "Full analysis. No inline arrays; ResearchAgent pulls sample_seismic.csv & sample_welllog.csv from data/.",
    },
    "example_10_quick_triage": {
        "label": "10. Quick Triage — Logs only",
        "description": "Quick analysis. Well-log only (no seismic). Demonstrates the non-linear branch that skips the seismic specialist.",
    },
}


# Failure / edge-case scenarios — crafted to exercise validation, retry,
# escalation, and weak-evidence critique paths.
FAILURE_SAMPLES: List[Dict[str, Any]] = [
    {
        "id": "fail_missing_well_name",
        "label": "F1. Missing well_name (validation 422)",
        "description": "well_name is required by the API contract. Expect HTTP 422 / 500 from /run.",
        "expected": "error",
        "payload": {
            "well_name": "",
            "analysis_type": "full",
            "seismic_data": {"depth_values": [1000, 1100], "amplitude_values": [1.0, 1.2]},
            "well_log_data": None,
            "user_notes": "Intentionally blank well name to trigger backend validation.",
        },
    },
    {
        "id": "fail_malformed_seismic_json",
        "label": "F2. Malformed seismic JSON (client parse fail)",
        "description": "Seismic textarea contains invalid JSON. Expect a client-side parse error before submit.",
        "expected": "client-error",
        "payload": {
            "well_name": "Malformed-JSON-Demo",
            "analysis_type": "full",
            # Raw text injected verbatim into the textarea (intentionally invalid JSON).
            "seismic_data_raw": '{"depth_values": [1000, 1100, 1200], "amplitude_values": [0.5, 1.2,, 2.3]}',
            "well_log_data": None,
            "user_notes": "Trailing/extra comma in amplitude_values to break JSON.parse.",
        },
    },
    {
        "id": "fail_mismatched_arrays",
        "label": "F3. Mismatched depth vs amplitude lengths",
        "description": "depth_values has 10 entries, amplitude_values has 3. Specialists should flag weak / inconsistent evidence and the evaluator should request a revision.",
        "expected": "weak-evidence",
        "payload": {
            "well_name": "Mismatched-Arrays-Demo",
            "analysis_type": "full",
            "seismic_data": {
                "depth_values": [1000, 1100, 1200, 1300, 1400, 1500, 1600, 1700, 1800, 1900],
                "amplitude_values": [0.5, 1.2, 2.3],
                "frequency_content": {"low_freq_10_20Hz": 0.3, "mid_freq_20_50Hz": 0.5, "high_freq_50_100Hz": 0.2},
            },
            "well_log_data": {
                "depth_values": [2000, 2100],
                "gamma_ray": [80, 90],
                "resistivity": [50, 60],
                "porosity": [18, 20],
                "depth_unit": "feet",
            },
            "user_notes": "Mismatched array lengths to stress the evaluator critique loop.",
        },
    },
    {
        "id": "fail_all_shale_weak",
        "label": "F4. All-shale zone (weak reservoir evidence)",
        "description": "Very high gamma-ray, near-zero porosity, low resistivity. No reservoir present — evaluator should mark evidence as weak and gate the report.",
        "expected": "weak-evidence",
        "payload": {
            "well_name": "All-Shale-Weak-Evidence",
            "analysis_type": "full",
            "trap_type": "stratigraphic",
            "closure_area": 6.0,
            "spill_depth": 4000,
            "grv": 12.0,
            "quality_threshold": 0.7,
            "seismic_data": {
                "depth_values": [3800, 3900, 4000, 4100, 4200, 4300],
                "amplitude_values": [0.2, 0.25, 0.22, 0.21, 0.24, 0.23],
                "frequency_content": {"low_freq_10_20Hz": 0.4, "mid_freq_20_50Hz": 0.5, "high_freq_50_100Hz": 0.1},
            },
            "well_log_data": {
                "depth_values": [3900, 4000, 4100, 4200, 4300],
                "gamma_ray": [150, 160, 155, 165, 158],
                "resistivity": [4, 5, 3, 4, 4],
                "porosity": [2, 1, 2, 1, 2],
                "depth_unit": "feet",
            },
            "user_notes": "Pure shale package — should trigger weak-evidence critique and a revision cycle with quality_threshold=0.7.",
        },
    },
    {
        "id": "fail_negative_values",
        "label": "F5. Negative & out-of-range physical values",
        "description": "Negative resistivity, porosity > 100%, negative depths. Petrophysics tools should clamp/flag these and surface errors.",
        "expected": "error",
        "payload": {
            "well_name": "Out-Of-Range-Values",
            "analysis_type": "full",
            "seismic_data": {
                "depth_values": [-500, -400, -300],
                "amplitude_values": [1.0, 1.5, 2.0],
                "frequency_content": {"low_freq_10_20Hz": 0.3, "mid_freq_20_50Hz": 0.5, "high_freq_50_100Hz": 0.2},
            },
            "well_log_data": {
                "depth_values": [1000, 1100, 1200],
                "gamma_ray": [80, 90, 85],
                "resistivity": [-50, -30, -10],
                "porosity": [120, 150, 200],
                "depth_unit": "feet",
            },
            "user_notes": "Negative depths/resistivity and porosity > 100% to stress physical-bounds checks.",
        },
    },
    {
        "id": "fail_missing_csv",
        "label": "F6. Missing CSV file (loader failure)",
        "description": "seismic_csv_path points to a file that does not exist. ResearchAgent should log a load failure and the workflow should degrade gracefully.",
        "expected": "error",
        "payload": {
            "well_name": "Missing-CSV-Demo",
            "analysis_type": "full",
            "trap_type": "structural",
            "closure_area": 10.0,
            "spill_depth": 2500,
            "grv": 40.0,
            "quality_threshold": 0.5,
            "seismic_csv_path": "this_file_does_not_exist.csv",
            "well_log_csv_path": "also_missing.csv",
            "user_notes": "Both CSVs intentionally point to non-existent files in data/.",
        },
    },
    {
        "id": "fail_empty_arrays",
        "label": "F7. Empty arrays (no signal to analyze)",
        "description": "All input arrays are empty. Tools should return zero / NaN stats; evaluator should flag insufficient data.",
        "expected": "weak-evidence",
        "payload": {
            "well_name": "Empty-Arrays-Demo",
            "analysis_type": "full",
            "seismic_data": {
                "depth_values": [],
                "amplitude_values": [],
                "frequency_content": {"low_freq_10_20Hz": 0, "mid_freq_20_50Hz": 0, "high_freq_50_100Hz": 0},
            },
            "well_log_data": {
                "depth_values": [],
                "gamma_ray": [],
                "resistivity": [],
                "porosity": [],
                "depth_unit": "feet",
            },
            "user_notes": "Empty payload — tests divide-by-zero / NaN guards across the tools layer.",
        },
    },
    {
        "id": "fail_single_sample",
        "label": "F8. Single sample point (insufficient stats)",
        "description": "Only one depth point provided. Anomaly / horizon detection needs N>=3; expect downgraded confidence and a critique.",
        "expected": "weak-evidence",
        "payload": {
            "well_name": "Single-Sample-Demo",
            "analysis_type": "quick",
            "seismic_data": {
                "depth_values": [2000],
                "amplitude_values": [1.5],
                "frequency_content": {"low_freq_10_20Hz": 0.3, "mid_freq_20_50Hz": 0.5, "high_freq_50_100Hz": 0.2},
            },
            "well_log_data": {
                "depth_values": [2000],
                "gamma_ray": [80],
                "resistivity": [50],
                "porosity": [18],
                "depth_unit": "feet",
            },
            "user_notes": "One sample per array — too few to compute meaningful stats / horizons.",
        },
    },
    {
        "id": "fail_bogus_analysis_type",
        "label": "F9. Unknown analysis_type='bogus'",
        "description": "analysis_type is neither 'full' nor 'quick'. Backend should reject or default — useful to verify the contract.",
        "expected": "error",
        "payload": {
            "well_name": "Bogus-Type-Demo",
            "analysis_type": "bogus",
            "seismic_data": {
                "depth_values": [1000, 1100, 1200],
                "amplitude_values": [0.5, 1.2, 2.3],
                "frequency_content": {"low_freq_10_20Hz": 0.3, "mid_freq_20_50Hz": 0.5, "high_freq_50_100Hz": 0.2},
            },
            "well_log_data": None,
            "user_notes": "Invalid analysis_type enum.",
        },
    },
    {
        "id": "fail_strings_for_numbers",
        "label": "F10. Numbers passed as strings",
        "description": "depth/amplitude arrays contain quoted strings instead of numbers. Petrophysics math should fail or coerce; evaluator should notice.",
        "expected": "error",
        "payload": {
            "well_name": "Stringly-Typed-Demo",
            "analysis_type": "full",
            "seismic_data": {
                "depth_values": ["1000", "1100", "1200"],
                "amplitude_values": ["0.5", "1.2", "2.3"],
                "frequency_content": {"low_freq_10_20Hz": "0.3", "mid_freq_20_50Hz": "0.5", "high_freq_50_100Hz": "0.2"},
            },
            "well_log_data": {
                "depth_values": ["2000", "2100"],
                "gamma_ray": ["80", "90"],
                "resistivity": ["50", "60"],
                "porosity": ["18", "20"],
                "depth_unit": "feet",
            },
            "user_notes": "All numeric values wrapped in strings — tests type coercion / validation.",
        },
    },
]


def _load_success_samples() -> List[Dict[str, Any]]:
    """Scan ``input_examples/`` and pair each file with its label metadata."""
    samples: List[Dict[str, Any]] = []
    if not INPUT_EXAMPLES_DIR.is_dir():
        logger.warning("input_examples directory not found at %s", INPUT_EXAMPLES_DIR)
        return samples

    for json_path in sorted(INPUT_EXAMPLES_DIR.glob("*.json")):
        stem = json_path.stem
        try:
            payload = json.loads(json_path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - defensive
            logger.error("Failed to parse %s: %s", json_path, exc)
            continue

        meta = SUCCESS_META.get(stem, {})
        samples.append(
            {
                "id": f"success_{stem}",
                "label": meta.get("label", stem.replace("_", " ").title()),
                "description": meta.get(
                    "description",
                    "Bundled input example from input_examples/.",
                ),
                "expected": "success",
                "payload": payload,
            }
        )
    return samples


SUCCESS_SAMPLES = _load_success_samples()
logger.info(
    "run_ui loaded %d success samples and %d failure samples",
    len(SUCCESS_SAMPLES),
    len(FAILURE_SAMPLES),
)

ALL_SAMPLES = SUCCESS_SAMPLES + FAILURE_SAMPLES


# --------------------------------------------------------------------------- #
# FastAPI app                                                                  #
# --------------------------------------------------------------------------- #
app = FastAPI(title="Oil & Gas Analytics UI (Sample Selector)")

allow_origins = config.CORS_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_origins != ["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# The samples catalogue is injected directly into the HTML so the page works
# offline (no extra round trip). It is also exposed via /samples for tooling.
_SAMPLES_JSON_LITERAL = json.dumps(ALL_SAMPLES, ensure_ascii=False)


DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang=\"en\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>Oil & Gas Analytics — Sample Selector</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0f1a2e 0%, #142447 100%);
            color: #e6edf3; min-height: 100vh;
        }
        header {
            background: rgba(0,0,0,0.35); padding: 18px 24px;
            border-bottom: 2px solid #6ee7ff;
            box-shadow: 0 2px 10px rgba(0,0,0,0.3);
        }
        .header-content {
            max-width: 1400px; margin: 0 auto;
            display: flex; justify-content: space-between; align-items: center;
        }
        h1 { color: #6ee7ff; font-size: 26px; font-weight: 600; }
        h1 small { color: #9aa9bd; font-size: 13px; font-weight: 400; margin-left: 8px; }
        .status { display: flex; gap: 12px; align-items: center; }
        .status-badge {
            background: #6ee7ff; color: #0f1a2e;
            padding: 6px 14px; border-radius: 18px;
            font-size: 12px; font-weight: 600;
        }
        .container { max-width: 1400px; margin: 28px auto; padding: 0 20px; }
        .card {
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(110,231,255,0.2);
            border-radius: 10px; padding: 22px; margin-bottom: 22px;
            backdrop-filter: blur(10px);
        }
        .card h2 {
            color: #6ee7ff; font-size: 19px; margin-bottom: 14px;
            border-bottom: 1px solid rgba(110,231,255,0.25); padding-bottom: 10px;
        }
        .input-group { margin-bottom: 14px; }
        label { display: block; margin-bottom: 5px; color: #6ee7ff; font-weight: 500; font-size: 13px; }
        input, textarea, select {
            width: 100%; padding: 10px;
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(110,231,255,0.3);
            border-radius: 4px; color: #e6edf3; font-family: inherit; font-size: 13px;
        }
        textarea { min-height: 110px; font-family: 'Courier New', monospace; }
        input:focus, textarea:focus, select:focus {
            outline: none; border-color: #6ee7ff; background: rgba(110,231,255,0.08);
        }
        button {
            background: linear-gradient(135deg, #6ee7ff 0%, #2a93b8 100%);
            color: #0f1a2e; border: none; padding: 11px 24px;
            border-radius: 4px; cursor: pointer; font-weight: 600; font-size: 13px;
            transition: all 0.2s ease;
        }
        button.secondary {
            background: rgba(110,231,255,0.18); color: #e6edf3;
            border: 1px solid rgba(110,231,255,0.4);
        }
        button.danger {
            background: linear-gradient(135deg, #ff8c8c 0%, #c64646 100%);
            color: #0f1a2e;
        }
        button:hover { transform: translateY(-1px); box-shadow: 0 4px 14px rgba(110,231,255,0.25); }
        .button-group { display: flex; gap: 10px; margin-top: 18px; flex-wrap: wrap; }
        .sample-meta {
            display: flex; gap: 14px; align-items: center;
            background: rgba(0,0,0,0.25); border: 1px dashed rgba(110,231,255,0.3);
            border-radius: 6px; padding: 12px 14px; margin-top: 10px; font-size: 13px;
        }
        .sample-meta .pill {
            font-size: 11px; padding: 3px 10px; border-radius: 12px;
            font-weight: 700; letter-spacing: 0.4px;
        }
        .pill.success { background: #2ed27a; color: #0f1a2e; }
        .pill.error { background: #ff7373; color: #0f1a2e; }
        .pill.weak { background: #ffb347; color: #0f1a2e; }
        .pill.client-error { background: #c084fc; color: #0f1a2e; }
        .sample-meta .desc { color: #c9d4e3; flex: 1; }
        .loading { display: none; text-align: center; padding: 18px; }
        .spinner {
            border: 3px solid rgba(110,231,255,0.2);
            border-top: 3px solid #6ee7ff;
            border-radius: 50%; width: 36px; height: 36px;
            animation: spin 1s linear infinite; margin: 0 auto;
        }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        .alert {
            padding: 12px 14px; border-radius: 5px; margin-bottom: 14px; font-size: 13px;
        }
        .alert.error { background: rgba(255,100,100,0.12); border: 1px solid rgba(255,100,100,0.5); color: #ff8c8c; }
        .alert.success { background: rgba(100,255,150,0.10); border: 1px solid rgba(100,255,150,0.5); color: #7ee5a3; }
        pre {
            background: rgba(0,0,0,0.55); padding: 14px; border-radius: 4px;
            overflow-x: auto; border: 1px solid rgba(110,231,255,0.2);
            margin-top: 10px; font-size: 12px; max-height: 520px;
        }
        code { background: rgba(0,0,0,0.35); padding: 2px 6px; border-radius: 3px; font-family: 'Courier New', monospace; }
        footer { text-align: center; padding: 18px; color: #6f7d92; font-size: 12px; margin-top: 40px; }
        .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
        @media (max-width: 900px) { .grid-2 { grid-template-columns: 1fr; } }
        /* --- Verdict / chart styling ----------------------------------- */
        .verdict-card { display: grid; grid-template-columns: 240px 1fr; gap: 18px; align-items: stretch; }
        @media (max-width: 800px) { .verdict-card { grid-template-columns: 1fr; } }
        .verdict-badge {
            border-radius: 10px; padding: 18px; text-align: center;
            color: #0f1a2e; font-weight: 700;
            box-shadow: 0 4px 16px rgba(0,0,0,0.3);
        }
        .verdict-badge .label { font-size: 12px; letter-spacing: 1.5px; opacity: 0.85; }
        .verdict-badge .decision { font-size: 26px; margin: 8px 0; }
        .verdict-badge .score { font-size: 40px; font-weight: 800; line-height: 1; }
        .verdict-badge .score-label { font-size: 10px; letter-spacing: 1px; opacity: 0.8; }
        .verdict-body { display: flex; flex-direction: column; gap: 10px; }
        .verdict-headline { font-size: 15px; color: #e6edf3; }
        .score-row { display: flex; gap: 10px; flex-wrap: wrap; }
        .score-chip {
            background: rgba(0,0,0,0.3); border: 1px solid rgba(110,231,255,0.3);
            border-radius: 18px; padding: 5px 12px; font-size: 12px; color: #c9d4e3;
        }
        .score-chip b { color: #e6edf3; margin-left: 6px; }
        .driver-list { margin: 0; padding-left: 20px; color: #c9d4e3; font-size: 13px; }
        .driver-list li { margin-bottom: 4px; }
        .chart-wrap {
            background: #0f1a2e; border: 1px solid rgba(110,231,255,0.2);
            border-radius: 8px; padding: 10px; margin-top: 12px; overflow-x: auto;
        }
        .chart-wrap img { width: 100%; height: auto; display: block; }
        .final-result-pre {
            background: rgba(0,0,0,0.55); border: 1px solid rgba(110,231,255,0.2);
            border-radius: 6px; padding: 12px; font-size: 12px; color: #c9d4e3;
            max-height: 320px; overflow: auto; margin-top: 8px;
        }
        /* --- Agent trace table ----------------------------------------- */
        .trace-table-wrap { overflow-x: auto; margin-top: 6px; }
        table.trace-table {
            width: 100%; border-collapse: collapse; font-size: 12px;
            background: rgba(0,0,0,0.30); color: #e6edf3;
        }
        table.trace-table th, table.trace-table td {
            border: 1px solid rgba(110,231,255,0.22);
            padding: 6px 9px; text-align: left; vertical-align: top;
        }
        table.trace-table th {
            background: rgba(110,231,255,0.12); color: #6ee7ff;
            font-weight: 600; letter-spacing: 0.3px; white-space: nowrap;
        }
        table.trace-table td.col-step { text-align: right; color: #9aa9bd; width: 36px; }
        table.trace-table td.col-agent { font-weight: 600; color: #6ee7ff; white-space: nowrap; }
        table.trace-table td.col-action { white-space: nowrap; color: #ffd28c; }
        table.trace-table td.col-target { white-space: nowrap; color: #c084fc; }
        table.trace-table td.col-result { color: #c9d4e3; max-width: 520px; }
        table.trace-table tbody tr:nth-child(odd) { background: rgba(255,255,255,0.02); }
        table.trace-table .pill-status {
            display: inline-block; padding: 1px 8px; border-radius: 10px;
            font-size: 10px; font-weight: 700;
        }
        table.trace-table .pill-status.success { background: #2ed27a; color: #0f1a2e; }
        table.trace-table .pill-status.error { background: #ff7373; color: #0f1a2e; }
        table.trace-table .pill-status.skipped { background: #9aa9bd; color: #0f1a2e; }
        table.trace-table .pill-status.partial { background: #ffb347; color: #0f1a2e; }
    </style>
</head>
<body>
    <header>
        <div class=\"header-content\">
            <h1>🛢️ Oil &amp; Gas Analytics <small>Sample Selector Dashboard</small></h1>
            <div class=\"status\">
                <span class=\"status-badge\">Port __UI_PORT__</span>
                <span id=\"api-status\" class=\"status-badge\">API: checking…</span>
            </div>
        </div>
    </header>

    <div class=\"container\">
        <div class=\"card\">
            <h2>1. Pick a Sample Test Case</h2>
            <div class=\"input-group\">
                <label for=\"sampleSelect\">Sample Catalogue</label>
                <select id=\"sampleSelect\" onchange=\"onSampleChange()\">
                    <option value=\"\">— Select a sample —</option>
                    <optgroup id=\"successGroup\" label=\"✅ Success Cases (from input_examples/)\"></optgroup>
                    <optgroup id=\"failureGroup\" label=\"⚠️ Failure / Edge Cases\"></optgroup>
                </select>
            </div>
            <div id=\"sampleMeta\" class=\"sample-meta\" style=\"display:none;\">
                <span id=\"sampleBadge\" class=\"pill success\">SUCCESS</span>
                <span id=\"sampleDesc\" class=\"desc\"></span>
            </div>
            <div class=\"button-group\">
                <button onclick=\"applySample()\">Load Into Form</button>
                <button class=\"secondary\" onclick=\"runSelectedSample()\">Run Sample Now</button>
                <button class=\"secondary\" onclick=\"resetForm()\">Reset Form</button>
            </div>
        </div>

        <div class=\"card\">
            <h2>2. Review / Edit Request</h2>
            <div id=\"message\"></div>

            <div class=\"grid-2\">
                <div class=\"input-group\">
                    <label>Well Name *</label>
                    <input type=\"text\" id=\"wellName\" placeholder=\"e.g., Well-001\">
                </div>
                <div class=\"input-group\">
                    <label>Analysis Type</label>
                    <select id=\"analysisType\">
                        <option value=\"full\">Full Analysis (all agents)</option>
                        <option value=\"quick\">Quick Analysis (risk only)</option>
                        <option value=\"bogus\">bogus (invalid — for F9)</option>
                    </select>
                </div>
            </div>

            <div class=\"grid-2\">
                <div class=\"input-group\">
                    <label>Seismic CSV Path (optional)</label>
                    <input type=\"text\" id=\"seismicCsvPath\" placeholder=\"e.g., sample_seismic.csv\">
                </div>
                <div class=\"input-group\">
                    <label>Well Log CSV Path (optional)</label>
                    <input type=\"text\" id=\"wellLogCsvPath\" placeholder=\"e.g., sample_welllog.csv\">
                </div>
            </div>

            <div class=\"input-group\">
                <label>Seismic Data (JSON)</label>
                <textarea id=\"seismicData\" placeholder='{\"amplitude_values\": [...], \"depth_values\": [...]}'></textarea>
            </div>

            <div class=\"input-group\">
                <label>Well Log Data (JSON)</label>
                <textarea id=\"wellLogData\" placeholder='{\"gamma_ray\": [...], \"resistivity\": [...], \"porosity\": [...]}'></textarea>
            </div>

            <div class=\"input-group\">
                <label>Extra Fields (JSON, optional — trap_type, closure_area, spill_depth, grv, quality_threshold, ...)</label>
                <textarea id=\"extraFields\" placeholder='{\"trap_type\": \"structural\", \"quality_threshold\": 0.6}'></textarea>
            </div>

            <div class=\"input-group\">
                <label>User Notes</label>
                <textarea id=\"userNotes\" placeholder=\"Add any relevant notes…\"></textarea>
            </div>

            <div class=\"button-group\">
                <button onclick=\"submitAnalysis()\">Submit Analysis</button>
                <button class=\"secondary\" onclick=\"copyRequestJson()\">Copy Request JSON</button>
            </div>

            <div class=\"loading\" id=\"loading\">
                <div class=\"spinner\"></div>
                <p style=\"margin-top:12px;color:#6ee7ff;\">Running multi-agent workflow…</p>
            </div>
        </div>

        <div id=\"resultsContainer\"></div>
    </div>

    <footer>
        <p>Oil &amp; Gas Analytics Multi-Agent System · UI on port __UI_PORT__ · Backend: <code>__API_BASE_URL__</code></p>
    </footer>

    <script>
        const API_URL = '__API_BASE_URL__';
        const SAMPLES = __SAMPLES_JSON__;
        const SAMPLE_BY_ID = Object.fromEntries(SAMPLES.map(s => [s.id, s]));

        function populateSelect() {
            const sel = document.getElementById('sampleSelect');
            const successGroup = document.getElementById('successGroup');
            const failureGroup = document.getElementById('failureGroup');
            SAMPLES.forEach(s => {
                const opt = document.createElement('option');
                opt.value = s.id;
                opt.textContent = s.label;
                if (s.expected === 'success') {
                    successGroup.appendChild(opt);
                } else {
                    failureGroup.appendChild(opt);
                }
            });
        }

        function onSampleChange() {
            const id = document.getElementById('sampleSelect').value;
            const meta = document.getElementById('sampleMeta');
            if (!id) { meta.style.display = 'none'; return; }
            const s = SAMPLE_BY_ID[id];
            const badge = document.getElementById('sampleBadge');
            const desc = document.getElementById('sampleDesc');
            badge.className = 'pill ' + (s.expected || 'success');
            badge.textContent = (s.expected || 'success').toUpperCase();
            desc.textContent = s.description || '';
            meta.style.display = 'flex';
        }

        function applySample() {
            const id = document.getElementById('sampleSelect').value;
            if (!id) { showMessage('Pick a sample from the dropdown first.', 'error'); return; }
            const s = SAMPLE_BY_ID[id];
            const p = s.payload || {};

            document.getElementById('wellName').value = p.well_name || '';
            // Analysis type — handle the invalid 'bogus' value too.
            const at = document.getElementById('analysisType');
            const requested = p.analysis_type || 'full';
            if ([...at.options].some(o => o.value === requested)) {
                at.value = requested;
            } else {
                // Add an option on the fly so what the user picked is preserved.
                const opt = document.createElement('option');
                opt.value = requested; opt.textContent = requested + ' (custom)';
                at.appendChild(opt); at.value = requested;
            }

            document.getElementById('seismicCsvPath').value = p.seismic_csv_path || '';
            document.getElementById('wellLogCsvPath').value = p.well_log_csv_path || '';

            // Seismic textarea — supports a raw-string escape hatch (F2).
            if (p.seismic_data_raw !== undefined) {
                document.getElementById('seismicData').value = p.seismic_data_raw;
            } else if (p.seismic_data !== undefined && p.seismic_data !== null) {
                document.getElementById('seismicData').value = JSON.stringify(p.seismic_data, null, 2);
            } else {
                document.getElementById('seismicData').value = '';
            }

            // Well-log textarea.
            if (p.well_log_data !== undefined && p.well_log_data !== null) {
                document.getElementById('wellLogData').value = JSON.stringify(p.well_log_data, null, 2);
            } else {
                document.getElementById('wellLogData').value = '';
            }

            // Extras — everything that isn't a top-level recognized key.
            const known = new Set([
                'well_name', 'analysis_type', 'seismic_data', 'seismic_data_raw',
                'well_log_data', 'seismic_csv_path', 'well_log_csv_path',
                'user_notes',
            ]);
            const extras = {};
            Object.keys(p).forEach(k => { if (!known.has(k)) extras[k] = p[k]; });
            document.getElementById('extraFields').value =
                Object.keys(extras).length ? JSON.stringify(extras, null, 2) : '';

            document.getElementById('userNotes').value = p.user_notes || '';

            showMessage('Sample <b>' + s.label + '</b> loaded into the form.', 'success');
        }

        function resetForm() {
            ['wellName','seismicData','wellLogData','userNotes','seismicCsvPath','wellLogCsvPath','extraFields']
                .forEach(id => { document.getElementById(id).value = ''; });
            document.getElementById('analysisType').value = 'full';
            document.getElementById('sampleSelect').value = '';
            document.getElementById('sampleMeta').style.display = 'none';
            document.getElementById('resultsContainer').innerHTML = '';
            showMessage('Form reset.', 'success');
        }

        function buildRequestBody() {
            const wellName = document.getElementById('wellName').value;
            const analysisType = document.getElementById('analysisType').value;
            const seismicTxt = document.getElementById('seismicData').value.trim();
            const wellLogTxt = document.getElementById('wellLogData').value.trim();
            const extrasTxt = document.getElementById('extraFields').value.trim();
            const seismicCsv = document.getElementById('seismicCsvPath').value.trim();
            const wellLogCsv = document.getElementById('wellLogCsvPath').value.trim();
            const notes = document.getElementById('userNotes').value;

            const body = {
                well_name: wellName,
                analysis_type: analysisType,
                seismic_data: seismicTxt ? JSON.parse(seismicTxt) : null,
                well_log_data: wellLogTxt ? JSON.parse(wellLogTxt) : null,
                user_notes: notes,
            };
            if (seismicCsv) body.seismic_csv_path = seismicCsv;
            if (wellLogCsv) body.well_log_csv_path = wellLogCsv;
            if (extrasTxt) {
                const extras = JSON.parse(extrasTxt);
                Object.assign(body, extras);
            }
            return body;
        }

        async function submitAnalysis() {
            let body;
            try {
                body = buildRequestBody();
            } catch (e) {
                showMessage('Failed to parse JSON input: ' + e.message, 'error');
                return;
            }
            if (!body.well_name) {
                // Still send it through so the user can see the backend's 4xx response.
                showMessage('well_name is empty — sending anyway so you can see the backend response.', 'error');
            }
            showLoading(true);
            const t0 = performance.now();
            let result, response, ms;
            try {
                response = await fetch(API_URL + '/run', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(body),
                });
                const text = await response.text();
                try { result = JSON.parse(text); } catch { result = { raw: text }; }
                ms = Math.round(performance.now() - t0);
                if (response.ok) {
                    showMessage('Analysis OK in ' + ms + ' ms · workflow_id=' + (result.workflow_id || 'n/a'), 'success');
                } else {
                    showMessage('Backend returned HTTP ' + response.status + ' in ' + ms + ' ms', 'error');
                }
            } catch (e) {
                showMessage('Network error: ' + e.message, 'error');
                displayResults({ error: e.message, request: body }, null);
                showLoading(false);
                return;
            }

            // Render the raw response first so the user sees something immediately.
            displayResults({ http_status: response.status, duration_ms: ms, request: body, response: result }, null);

            // Then ask our own UI server to compute the verdict + matplotlib chart.
            // We call this even on backend errors so failures still get a clear
            // "INCONCLUSIVE" verdict card instead of a silent dead-end.
            try {
                const vizResp = await fetch('/visualize', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ request: body, response: result || {} }),
                });
                if (vizResp.ok) {
                    const viz = await vizResp.json();
                    displayResults({ http_status: response.status, duration_ms: ms, request: body, response: result }, viz);
                } else {
                    console.error('visualize endpoint returned HTTP', vizResp.status);
                }
            } catch (e) {
                console.error('Visualize call failed:', e);
            } finally {
                showLoading(false);
            }
        }

        function runSelectedSample() {
            const id = document.getElementById('sampleSelect').value;
            if (!id) { showMessage('Pick a sample from the dropdown first.', 'error'); return; }
            applySample();
            // Defer to next tick so the form is populated before submit.
            setTimeout(submitAnalysis, 50);
        }

        function copyRequestJson() {
            let body;
            try { body = buildRequestBody(); } catch (e) {
                showMessage('Cannot copy — JSON parse failed: ' + e.message, 'error'); return;
            }
            navigator.clipboard.writeText(JSON.stringify(body, null, 2)).then(
                () => showMessage('Request JSON copied to clipboard.', 'success'),
                () => showMessage('Clipboard write failed.', 'error'),
            );
        }

        function displayResults(payload, viz) {
            const container = document.getElementById('resultsContainer');
            let verdictHtml = '';
            let chartHtml = '';
            let finalResultHtml = '';
            let traceTableHtml = '';

            if (viz && viz.verdict) {
                const v = viz.verdict;
                const sc = v.scores || {};
                const overallTxt = (sc.overall === null || sc.overall === undefined) ? 'n/a' : sc.overall.toFixed(0);
                const chip = (label, val) => '<span class="score-chip">' + label
                    + '<b>' + ((val === null || val === undefined) ? 'n/a' : val.toFixed(0)) + '</b></span>';
                const drivers = (v.drivers || []).slice(0, 8)
                    .map(d => '<li>' + escapeHtml(d) + '</li>').join('') || '<li>No structured drivers extracted.</li>';
                verdictHtml = ''
                    + '<div class="verdict-card">'
                    +   '<div class="verdict-badge" style="background:' + v.color + ';">'
                    +     '<div class="label">DRILLING DECISION</div>'
                    +     '<div class="decision">' + escapeHtml((v.decision || '').replace(/_/g, ' ')) + '</div>'
                    +     '<div class="score">' + overallTxt + '</div>'
                    +     '<div class="score-label">OVERALL / 100</div>'
                    +   '</div>'
                    +   '<div class="verdict-body">'
                    +     '<div class="verdict-headline"><b>' + escapeHtml(v.well_name || '') + '</b> — ' + escapeHtml(v.headline || '') + '</div>'
                    +     '<div class="score-row">'
                    +       chip('Reservoir', sc.reservoir)
                    +       chip('Economic', sc.economic)
                    +       chip('Risk Safety', sc.risk_safety)
                    +       chip('Overall', sc.overall)
                    +     '</div>'
                    +     '<div><b style="color:#6ee7ff;font-size:13px;">Key drivers</b><ul class="driver-list">'
                    +       drivers + '</ul></div>'
                    +   '</div>'
                    + '</div>';
                if (viz.chart_png_b64) {
                    chartHtml = '<div class="chart-wrap"><img alt="Drilling decision chart" '
                        + 'src="data:image/png;base64,' + viz.chart_png_b64 + '"></div>';
                }
                // Extracted numeric/categorical metrics rendered as the "final result".
                finalResultHtml = '<div style="margin-top:14px;"><b style="color:#6ee7ff;font-size:13px;">'
                    + 'Final Result (extracted metrics)</b>'
                    + '<pre class="final-result-pre">'
                    + escapeHtml(JSON.stringify({
                        verdict: viz.verdict,
                        metrics: viz.metrics,
                    }, null, 2))
                    + '</pre></div>';
                traceTableHtml = buildTraceTableHtml(viz.trace_table || [], viz.trace_file);
            } else if (viz === null) {
                verdictHtml = '<div class="verdict-headline" style="color:#9aa9bd;">'
                    + 'Computing final verdict & chart…</div>';
            }

            container.innerHTML = ''
                + (traceTableHtml
                    ? ('<div class="card"><h2>3. Agent Collaboration Trace</h2>' + traceTableHtml + '</div>')
                    : '')
                + '<div class="card"><h2>' + (traceTableHtml ? '4' : '3') + '. Final Drilling Verdict</h2>'
                +     (verdictHtml || '<p style="color:#9aa9bd;">Submit a request to see the verdict.</p>')
                +     chartHtml
                +     finalResultHtml
                + '</div>'
                + '<div class="card"><h2>' + (traceTableHtml ? '5' : '4') + '. Raw API Response</h2><pre>'
                +     escapeHtml(JSON.stringify(payload, null, 2)) + '</pre></div>';
        }

        function buildTraceTableHtml(rows, tracePath) {
            if (!rows || !rows.length) {
                return '<p style="color:#9aa9bd;font-size:13px;">'
                    + 'No agent trace records were found for this run.</p>';
            }
            const head = '<thead><tr>'
                + '<th>#</th><th>Agent Name</th><th>Action</th>'
                + '<th>Target Agent</th><th>Result</th><th>Status</th>'
                + '</tr></thead>';
            const body = rows.map(r => {
                const status = (r.status || '').toLowerCase();
                const statusClass = ['success','error','skipped','partial'].includes(status) ? status : 'success';
                const conf = (r.confidence === null || r.confidence === undefined)
                    ? '' : ' <span style="color:#9aa9bd;">(' + Number(r.confidence).toFixed(2) + ')</span>';
                return '<tr>'
                    + '<td class="col-step">' + (r.step || '') + '</td>'
                    + '<td class="col-agent">' + escapeHtml(r.agent_name || '') + '</td>'
                    + '<td class="col-action">' + escapeHtml(r.action || '') + '</td>'
                    + '<td class="col-target">' + escapeHtml(r.target_agent || '-') + '</td>'
                    + '<td class="col-result">' + escapeHtml(r.result || '') + '</td>'
                    + '<td><span class="pill-status ' + statusClass + '">'
                        + escapeHtml((r.status || 'success').toUpperCase()) + '</span>' + conf + '</td>'
                    + '</tr>';
            }).join('');
            const footer = tracePath
                ? '<p style="color:#9aa9bd;font-size:11px;margin-top:6px;">'
                    + 'Source: <code>' + escapeHtml(tracePath) + '</code> · '
                    + rows.length + ' rows shown</p>'
                : '';
            return '<div class="trace-table-wrap"><table class="trace-table">'
                + head + '<tbody>' + body + '</tbody></table></div>' + footer;
        }

        function escapeHtml(s) {
            return s.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
        }

        function showMessage(html, type) {
            const m = document.getElementById('message');
            m.innerHTML = '<div class=\"alert ' + type + '\">' + html + '</div>';
            setTimeout(() => { m.innerHTML = ''; }, 7000);
        }

        function showLoading(on) {
            document.getElementById('loading').style.display = on ? 'block' : 'none';
        }

        async function checkAPIHealth() {
            const badge = document.getElementById('api-status');
            try {
                const r = await fetch(API_URL + '/health');
                if (r.ok) {
                    badge.textContent = '✓ API online';
                    badge.style.background = '#2ed27a';
                } else {
                    badge.textContent = '! API ' + r.status;
                    badge.style.background = '#ffb347';
                }
            } catch {
                badge.textContent = '✗ API offline';
                badge.style.background = '#ff7373';
            }
        }

        populateSelect();
        checkAPIHealth();
        setInterval(checkAPIHealth, 30000);
    </script>
</body>
</html>
"""

DASHBOARD_HTML = (
    DASHBOARD_HTML
    .replace("__SAMPLES_JSON__", _SAMPLES_JSON_LITERAL)
    .replace("__API_BASE_URL__", API_BASE_URL)
    .replace("__UI_PORT__", str(UI_PORT))
)


# --------------------------------------------------------------------------- #
# Endpoints                                                                    #
# --------------------------------------------------------------------------- #
@app.get("/", response_class=HTMLResponse)
async def get_dashboard() -> str:
    """Serve the sample-selector dashboard."""
    return DASHBOARD_HTML


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """Liveness for the UI + downstream API status."""
    out: Dict[str, Any] = {
        "status": "healthy",
        "ui": "run_ui",
        "port": UI_PORT,
        "version": __version__,
        "samples": {
            "success": len(SUCCESS_SAMPLES),
            "failure": len(FAILURE_SAMPLES),
            "total": len(ALL_SAMPLES),
        },
    }
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE_URL}/health", timeout=5.0)
            out["api"] = r.json()
    except Exception as exc:
        out["api"] = {"status": "unreachable", "error": str(exc)}
    return out


@app.get("/samples")
async def list_samples() -> JSONResponse:
    """Return the full sample catalogue (success + failure) for tooling/tests."""
    return JSONResponse(
        {
            "success_samples": SUCCESS_SAMPLES,
            "failure_samples": FAILURE_SAMPLES,
            "total": len(ALL_SAMPLES),
        }
    )


@app.get("/samples/{sample_id}")
async def get_sample(sample_id: str) -> Dict[str, Any]:
    """Return a single sample by id."""
    for s in ALL_SAMPLES:
        if s["id"] == sample_id:
            return s
    raise HTTPException(status_code=404, detail=f"Sample '{sample_id}' not found")


@app.get("/api/proxy/{path:path}")
async def proxy_api(path: str) -> Dict[str, Any]:
    """Optional CORS-safe passthrough to the backend API (mirrors run_ui.py)."""
    try:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{API_BASE_URL}/{path}")
            return r.json()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# --------------------------------------------------------------------------- #
# Verdict + chart rendering                                                   #
# --------------------------------------------------------------------------- #
# Substring matchers used to scrape known reservoir/economic/risk metrics out
# of an arbitrary tool-results blob. Keys are normalized output names; values
# are the substrings to look for inside any nested dict key.
NUMERIC_KEY_MATCHERS: Dict[str, Tuple[str, ...]] = {
    "porosity": ("avg_porosity", "mean_porosity", "porosity_avg", "porosity"),
    "permeability_md": ("estimated_permeability_md", "permeability_md", "perm_md"),
    "water_saturation": ("water_saturation", "sw_avg", "avg_sw"),
    "hydrocarbon_saturation": ("hydrocarbon_saturation", "hc_saturation", "sh"),
    "net_pay_ft": ("net_pay", "net_to_gross", "ntg"),
    "ooip_mmbbl": ("ooip", "stoiip"),
    "ogip_bcf": ("ogip", "gas_in_place"),
    "npv_musd": ("npv", "net_present_value"),
    "fault_count": ("fault_count",),
    "fault_severity": ("fault_severity",),
    "bright_spot_count": ("bright_spot_count",),
    "anomaly_ratio": ("anomaly_ratio",),
    "closure_area": ("closure_area",),
    "grv": ("grv", "gross_rock_volume"),
    "quality_score": ("quality_score", "evidence_quality", "confidence"),
}

CATEGORICAL_KEY_MATCHERS: Dict[str, Tuple[str, ...]] = {
    "risk_level": ("risk_level",),
    "permeability_class": ("permeability_class",),
    "reservoir_class": ("reservoir_class", "reservoir_quality_class"),
    "trap_type": ("trap_type",),
}


def _walk(obj: Any, path: str = "") -> Iterable[Tuple[str, str, Any]]:
    """Recursively yield (full_path, leaf_key, value) for every leaf in ``obj``."""
    if isinstance(obj, dict):
        for k, v in obj.items():
            sub = f"{path}.{k}" if path else str(k)
            if isinstance(v, (dict, list)):
                yield from _walk(v, sub)
            else:
                yield sub, str(k), v
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            sub = f"{path}[{i}]"
            if isinstance(v, (dict, list)):
                yield from _walk(v, sub)
            else:
                yield sub, "", v


def _coerce_float(v: Any) -> Optional[float]:
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)) and not (isinstance(v, float) and math.isnan(v)):
        return float(v)
    if isinstance(v, str):
        try:
            return float(v)
        except (TypeError, ValueError):
            return None
    return None


def _extract_metrics(response: Dict[str, Any]) -> Dict[str, Any]:
    """Best-effort extraction of named metrics from a /run response.

    Returns ``{"numeric": {...}, "categorical": {...}, "evidence_paths": {...}}``.
    """
    numeric: Dict[str, float] = {}
    categorical: Dict[str, str] = {}
    evidence: Dict[str, str] = {}

    for path, leaf, value in _walk(response):
        leaf_lower = leaf.lower()
        # Numeric matchers — first hit wins (keeps the outermost / most
        # canonical match).
        for out_key, needles in NUMERIC_KEY_MATCHERS.items():
            if out_key in numeric:
                continue
            if any(n in leaf_lower for n in needles):
                f = _coerce_float(value)
                if f is not None:
                    numeric[out_key] = f
                    evidence[out_key] = path
                    break
        # Categorical matchers.
        for out_key, needles in CATEGORICAL_KEY_MATCHERS.items():
            if out_key in categorical:
                continue
            if any(n in leaf_lower for n in needles) and isinstance(value, str):
                categorical[out_key] = value
                evidence[out_key] = path

    return {"numeric": numeric, "categorical": categorical, "evidence_paths": evidence}


def _clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def _norm_porosity(pct: float) -> float:
    """Porosity in % → 0–100 score (linear, capped)."""
    if pct > 1.0:
        # already in %
        return _clip(pct / 0.30, 0.0, 1.0) * 100.0
    # 0–1 fraction; treat 0.30 as best-in-class
    return _clip(pct / 0.30, 0.0, 1.0) * 100.0


def _norm_permeability(md: float) -> float:
    """Permeability in mD → 0–100 score (log scale: 0.001 mD→0, 10000 mD→100)."""
    if md <= 0:
        return 0.0
    lo, hi = -3.0, 4.0
    score = (math.log10(md) - lo) / (hi - lo)
    return _clip(score, 0.0, 1.0) * 100.0


def _norm_saturation(sat: float) -> float:
    if sat > 1.0:
        sat = sat / 100.0
    return _clip(sat, 0.0, 1.0) * 100.0


def _norm_closure(area: float) -> float:
    # 0 km² → 0, 50 km² → 100 (linear cap)
    return _clip(area / 50.0, 0.0, 1.0) * 100.0


def _norm_grv(grv: float) -> float:
    # 0 → 0, 300 → 100 (linear cap)
    return _clip(grv / 300.0, 0.0, 1.0) * 100.0


def _norm_fault_count(n: float) -> float:
    # 0 faults → 100, 5+ → 0
    return _clip(1.0 - (n / 5.0), 0.0, 1.0) * 100.0


def _norm_fault_severity(sev: float) -> float:
    # 0 → 100, 1 → 0
    return _clip(1.0 - sev, 0.0, 1.0) * 100.0


def _risk_level_score(level: str) -> Optional[float]:
    mapping = {"LOW": 90.0, "MEDIUM": 60.0, "MODERATE": 60.0, "HIGH": 25.0, "VERY_HIGH": 10.0}
    return mapping.get((level or "").strip().upper())


def _compute_verdict(metrics: Dict[str, Any], request: Dict[str, Any]) -> Dict[str, Any]:
    """Combine metrics + the original request into a drilling decision."""
    num = dict(metrics.get("numeric", {}))
    cat = dict(metrics.get("categorical", {}))

    # Fall back to user-provided economic inputs when tools didn't surface them.
    for k in ("closure_area", "grv"):
        if k not in num and isinstance(request.get(k), (int, float)):
            num[k] = float(request[k])

    drivers: List[str] = []

    # ---- Reservoir score -------------------------------------------------- #
    reservoir_parts: List[float] = []
    if "porosity" in num:
        s = _norm_porosity(num["porosity"])
        reservoir_parts.append(s)
        drivers.append(f"Porosity {num['porosity']:.2f} → score {s:.0f}/100")
    if "permeability_md" in num:
        s = _norm_permeability(num["permeability_md"])
        reservoir_parts.append(s)
        drivers.append(f"Permeability {num['permeability_md']:.1f} mD → score {s:.0f}/100")
    if "hydrocarbon_saturation" in num:
        s = _norm_saturation(num["hydrocarbon_saturation"])
        reservoir_parts.append(s)
        drivers.append(f"HC saturation {num['hydrocarbon_saturation']:.2f} → score {s:.0f}/100")
    elif "water_saturation" in num:
        s = 100.0 - _norm_saturation(num["water_saturation"])
        reservoir_parts.append(s)
        drivers.append(f"Water sat {num['water_saturation']:.2f} → (1-Sw) score {s:.0f}/100")
    perm_class = cat.get("permeability_class", "").lower()
    if perm_class and not reservoir_parts:
        # Fallback if no numeric perm but class is present.
        reservoir_parts.append({"low": 25, "moderate": 55, "medium": 55, "high": 85, "excellent": 95}.get(perm_class, 50))
        drivers.append(f"Permeability class={perm_class}")

    reservoir_score = float(np.mean(reservoir_parts)) if reservoir_parts else float("nan")

    # ---- Economic score --------------------------------------------------- #
    economic_parts: List[float] = []
    if "closure_area" in num:
        s = _norm_closure(num["closure_area"])
        economic_parts.append(s)
        drivers.append(f"Closure area {num['closure_area']:.1f} → score {s:.0f}/100")
    if "grv" in num:
        s = _norm_grv(num["grv"])
        economic_parts.append(s)
        drivers.append(f"GRV {num['grv']:.1f} → score {s:.0f}/100")
    if "ooip_mmbbl" in num:
        s = _clip(num["ooip_mmbbl"] / 200.0, 0.0, 1.0) * 100.0
        economic_parts.append(s)
        drivers.append(f"OOIP {num['ooip_mmbbl']:.1f} MMbbl → score {s:.0f}/100")
    if "npv_musd" in num:
        s = _clip(num["npv_musd"] / 500.0, 0.0, 1.0) * 100.0
        economic_parts.append(s)
        drivers.append(f"NPV {num['npv_musd']:.1f} M$ → score {s:.0f}/100")
    economic_score = float(np.mean(economic_parts)) if economic_parts else float("nan")

    # ---- Risk score (higher = safer) ------------------------------------- #
    risk_parts: List[float] = []
    rl = _risk_level_score(cat.get("risk_level", ""))
    if rl is not None:
        risk_parts.append(rl)
        drivers.append(f"Risk level={cat['risk_level']} → score {rl:.0f}/100")
    if "fault_count" in num:
        s = _norm_fault_count(num["fault_count"])
        risk_parts.append(s)
        drivers.append(f"Fault count {num['fault_count']:.0f} → score {s:.0f}/100")
    if "fault_severity" in num:
        s = _norm_fault_severity(num["fault_severity"])
        risk_parts.append(s)
        drivers.append(f"Fault severity {num['fault_severity']:.2f} → score {s:.0f}/100")
    risk_score = float(np.mean(risk_parts)) if risk_parts else float("nan")

    # ---- Overall ---------------------------------------------------------- #
    weighted_parts: List[Tuple[float, float]] = []
    if not math.isnan(reservoir_score):
        weighted_parts.append((reservoir_score, 0.50))
    if not math.isnan(economic_score):
        weighted_parts.append((economic_score, 0.25))
    if not math.isnan(risk_score):
        weighted_parts.append((risk_score, 0.25))

    if weighted_parts:
        wsum = sum(w for _, w in weighted_parts)
        overall = sum(s * w for s, w in weighted_parts) / wsum
    else:
        overall = float("nan")

    # ---- Decision --------------------------------------------------------- #
    if math.isnan(overall):
        decision = "INCONCLUSIVE"
        color = "#9aa9bd"
        headline = "Insufficient evidence — cannot make a drilling recommendation."
    elif overall >= 65 and (math.isnan(reservoir_score) or reservoir_score >= 55):
        decision = "DRILL"
        color = "#2ed27a"
        headline = "Suitable & profitable — recommend proceeding to drill."
    elif overall >= 45:
        decision = "MARGINAL"
        color = "#ffb347"
        headline = "Marginal — drillable but economics/risk need mitigation."
    else:
        decision = "DO_NOT_DRILL"
        color = "#ff7373"
        headline = "Not suitable — recommend deferring or abandoning the prospect."

    return {
        "decision": decision,
        "headline": headline,
        "color": color,
        "scores": {
            "reservoir": None if math.isnan(reservoir_score) else round(reservoir_score, 1),
            "economic": None if math.isnan(economic_score) else round(economic_score, 1),
            "risk_safety": None if math.isnan(risk_score) else round(risk_score, 1),
            "overall": None if math.isnan(overall) else round(overall, 1),
        },
        "drivers": drivers,
        "well_name": request.get("well_name", "Unknown Well"),
    }


def _render_chart(metrics: Dict[str, Any], verdict: Dict[str, Any]) -> str:
    """Render a 2×2 matplotlib dashboard summarising the verdict. Returns base64 PNG."""
    plt.rcParams.update(
        {
            "figure.facecolor": "#0f1a2e",
            "axes.facecolor": "#142447",
            "axes.edgecolor": "#6ee7ff",
            "axes.labelcolor": "#e6edf3",
            "axes.titlecolor": "#6ee7ff",
            "xtick.color": "#c9d4e3",
            "ytick.color": "#c9d4e3",
            "text.color": "#e6edf3",
            "font.size": 10,
            "font.family": "DejaVu Sans",
        }
    )

    fig, axes = plt.subplots(2, 2, figsize=(11.5, 7.5))
    fig.suptitle(
        f"Drilling Decision Dashboard — {verdict['well_name']}",
        fontsize=15, fontweight="bold", color="#6ee7ff",
    )

    # ---- 1. Score bar chart ---------------------------------------------- #
    ax = axes[0, 0]
    score_labels = ["Reservoir", "Economic", "Risk Safety", "Overall"]
    score_keys = ["reservoir", "economic", "risk_safety", "overall"]
    scores = [verdict["scores"].get(k) or 0 for k in score_keys]
    bar_colors = []
    for s in scores:
        if s >= 65:
            bar_colors.append("#2ed27a")
        elif s >= 45:
            bar_colors.append("#ffb347")
        else:
            bar_colors.append("#ff7373")
    bars = ax.barh(score_labels, scores, color=bar_colors, edgecolor="#6ee7ff", height=0.55)
    for bar, raw, key in zip(bars, scores, score_keys):
        present = verdict["scores"].get(key) is not None
        label = f"{raw:.0f}" if present else "n/a"
        ax.text(min(raw + 2, 102), bar.get_y() + bar.get_height() / 2,
                label, va="center", fontsize=10, color="#e6edf3")
    ax.set_xlim(0, 110)
    ax.axvline(45, color="#ffb347", linestyle="--", alpha=0.5, linewidth=1)
    ax.axvline(65, color="#2ed27a", linestyle="--", alpha=0.5, linewidth=1)
    ax.set_title("Drill Readiness Scores (0–100)")
    ax.invert_yaxis()
    ax.grid(axis="x", color="#1f3357", alpha=0.4)

    # ---- 2. Reservoir property bars (normalized) ------------------------- #
    ax = axes[0, 1]
    num = metrics.get("numeric", {})
    prop_specs = [
        ("Porosity (%)", num.get("porosity"), lambda v: v * 100 if v is not None and v <= 1 else v, 35.0),
        ("log10(Perm mD)", num.get("permeability_md"), lambda v: math.log10(v) if v and v > 0 else None, 4.0),
        ("HC Sat (%)", num.get("hydrocarbon_saturation"), lambda v: v * 100 if v is not None and v <= 1 else v, 100.0),
        ("Net Pay (ft)", num.get("net_pay_ft"), lambda v: v, 200.0),
        ("Closure (km²)", num.get("closure_area"), lambda v: v, 50.0),
        ("GRV", num.get("grv"), lambda v: v, 300.0),
    ]
    names, values, ceilings = [], [], []
    for name, raw, transform, ceiling in prop_specs:
        if raw is None:
            continue
        try:
            v = transform(raw)
        except Exception:
            v = None
        if v is None:
            continue
        names.append(name)
        values.append(v)
        ceilings.append(ceiling)

    if names:
        norm = [v / c * 100 for v, c in zip(values, ceilings)]
        bars = ax.barh(names, norm, color="#6ee7ff", edgecolor="#0f1a2e", height=0.55)
        for bar, raw_v in zip(bars, values):
            ax.text(min(bar.get_width() + 2, 102), bar.get_y() + bar.get_height() / 2,
                    f"{raw_v:.2f}", va="center", fontsize=9, color="#e6edf3")
        ax.set_xlim(0, 110)
        ax.set_title("Reservoir & Economic Inputs (normalized %)")
        ax.invert_yaxis()
        ax.grid(axis="x", color="#1f3357", alpha=0.4)
    else:
        ax.set_title("Reservoir & Economic Inputs")
        ax.text(0.5, 0.5, "No numeric metrics extracted",
                ha="center", va="center", transform=ax.transAxes,
                color="#9aa9bd", fontsize=11, style="italic")
        ax.set_xticks([]); ax.set_yticks([])

    # ---- 3. Overall gauge (semi-donut) ----------------------------------- #
    ax = axes[1, 0]
    overall = verdict["scores"].get("overall")
    if overall is None:
        overall = 0.0
        gauge_color = "#9aa9bd"
    else:
        gauge_color = verdict["color"]

    ax.set_xlim(-1.15, 1.15); ax.set_ylim(-0.2, 1.25)
    ax.set_aspect("equal"); ax.axis("off")

    def _arc(start_pct: float, end_pct: float, color: str, r_in: float = 0.72, r_out: float = 1.0):
        t = np.linspace(np.pi * (1 - start_pct / 100.0), np.pi * (1 - end_pct / 100.0), 80)
        x_out = r_out * np.cos(t); y_out = r_out * np.sin(t)
        x_in = r_in * np.cos(t[::-1]); y_in = r_in * np.sin(t[::-1])
        ax.fill(np.concatenate([x_out, x_in]),
                np.concatenate([y_out, y_in]),
                color=color, edgecolor="none")

    # Tri-band background: red 0-45, amber 45-65, green 65-100.
    _arc(0, 45, "#3a1a1a"); _arc(45, 65, "#3b2c12"); _arc(65, 100, "#143a26")
    _arc(0, overall, gauge_color)
    ax.text(0, 0.30, f"{overall:.0f}", ha="center", va="center",
            fontsize=34, fontweight="bold", color=gauge_color)
    ax.text(0, 0.05, "OVERALL SCORE", ha="center", va="center",
            fontsize=10, color="#c9d4e3")
    ax.text(-1.0, -0.10, "0", color="#9aa9bd", fontsize=9)
    ax.text(1.0, -0.10, "100", color="#9aa9bd", fontsize=9, ha="right")
    ax.set_title("Overall Drill-Readiness Gauge", color="#6ee7ff", pad=10)

    # ---- 4. Verdict text panel ------------------------------------------- #
    ax = axes[1, 1]
    ax.axis("off")
    decision = verdict["decision"]
    color = verdict["color"]
    # Big decision badge.
    ax.add_patch(plt.Rectangle((0.02, 0.78), 0.96, 0.18,
                               transform=ax.transAxes,
                               facecolor=color, edgecolor="none", alpha=0.95))
    ax.text(0.5, 0.87, decision.replace("_", " "),
            transform=ax.transAxes, ha="center", va="center",
            fontsize=24, fontweight="bold", color="#0f1a2e")
    ax.text(0.02, 0.69, verdict["headline"],
            transform=ax.transAxes, ha="left", va="center",
            fontsize=11, color="#e6edf3", wrap=True)

    # Top 6 drivers as bullet lines.
    drivers = verdict.get("drivers") or ["No structured drivers extracted."]
    y = 0.58
    ax.text(0.02, y, "Key drivers:", transform=ax.transAxes,
            ha="left", fontsize=11, color="#6ee7ff", fontweight="bold")
    y -= 0.07
    for line in drivers[:6]:
        ax.text(0.04, y, f"• {line}", transform=ax.transAxes,
                ha="left", va="top", fontsize=9.5, color="#c9d4e3", wrap=True)
        y -= 0.08
    ax.set_title("Final Verdict", color="#6ee7ff", pad=10)

    fig.tight_layout(rect=(0, 0, 1, 0.95))
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, facecolor=fig.get_facecolor())
    plt.close(fig)
    buf.seek(0)
    return base64.b64encode(buf.read()).decode("ascii")


class VisualizeRequest(BaseModel):
    request: Dict[str, Any] = {}
    response: Dict[str, Any] = {}


# --------------------------------------------------------------------------- #
# Agent-trace table (read the JSONL trace file produced by the workflow)      #
# --------------------------------------------------------------------------- #
LOGS_DIR = Path(__file__).parent / "logs"

# Hide internal bookkeeping rows from the user-facing table by default.
_TRACE_TABLE_HIDDEN_ACTIONS = {"llm_config_resolved"}


def _find_trace_file(response: Dict[str, Any]) -> Optional[Path]:
    """Try to locate this run's JSONL trace file.

    Preference order:
      1. ``response.results.trace_file`` (set by the workflow)
      2. ``response.trace_file``
      3. ``response.results.trace_id`` → newest matching ``agent_trace_*_<trace_id>.jsonl``
      4. Most recently modified ``agent_trace_*.jsonl`` in ``logs/``
    """
    candidates: List[Any] = []
    results = response.get("results") if isinstance(response, dict) else None
    if isinstance(results, dict):
        candidates.append(results.get("trace_file"))
        candidates.append(results.get("trace_id"))
    candidates.append(response.get("trace_file") if isinstance(response, dict) else None)
    candidates.append(response.get("trace_id") if isinstance(response, dict) else None)

    for cand in candidates:
        if not cand or not isinstance(cand, str):
            continue
        # Direct path?
        p = Path(cand)
        if p.is_file():
            return p
        # Relative to project root?
        p2 = Path(__file__).parent / cand
        if p2.is_file():
            return p2
        # Looks like a trace_id (e.g. "run_abc12345") — find by suffix.
        if cand.startswith("run_") and LOGS_DIR.is_dir():
            matches = sorted(LOGS_DIR.glob(f"agent_trace_*_{cand}.jsonl"),
                             key=lambda p: p.stat().st_mtime, reverse=True)
            if matches:
                return matches[0]

    # Final fallback: newest JSONL in logs/.
    if LOGS_DIR.is_dir():
        matches = sorted(LOGS_DIR.glob("agent_trace_*.jsonl"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if matches:
            return matches[0]
    return None


def _load_trace_records(trace_path: Optional[Path]) -> List[Dict[str, Any]]:
    """Parse a JSONL trace file into a list of records (one per line)."""
    if not trace_path or not trace_path.is_file():
        return []
    records: List[Dict[str, Any]] = []
    try:
        with trace_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    except OSError as exc:
        logger.warning("Failed to read trace file %s: %s", trace_path, exc)
    return records


def _stringify_result(value: Any, max_len: int = 220) -> str:
    """Render an arbitrary value as a single-line, length-capped string."""
    if value is None:
        return ""
    if isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, ensure_ascii=False, default=str)
        except Exception:
            text = str(value)
    text = " ".join(text.split())  # collapse whitespace/newlines
    if len(text) > max_len:
        text = text[: max_len - 1] + "…"
    return text


def _build_trace_table(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Project trace records to the 4-column table the user asked for."""
    rows: List[Dict[str, Any]] = []
    for idx, rec in enumerate(records, start=1):
        action = rec.get("action", "")
        if action in _TRACE_TABLE_HIDDEN_ACTIONS:
            continue
        rows.append(
            {
                "step": idx,
                "timestamp": rec.get("timestamp", ""),
                "agent_name": rec.get("agent_name", ""),
                "action": action,
                "target_agent": rec.get("target_agent") or "-",
                "result": _stringify_result(rec.get("output_summary", "")),
                "status": rec.get("status", ""),
                "confidence": rec.get("confidence"),
            }
        )
    return rows


def _print_trace_table(rows: List[Dict[str, Any]], well_name: str) -> None:
    """Pretty-print the agent-trace table to stdout (terminal)."""
    if not rows:
        print(f"\n[Agent Trace] No trace records found for well={well_name}.\n", flush=True)
        return

    cols = [
        ("step", "#", 4),
        ("agent_name", "Agent Name", 26),
        ("action", "Action", 28),
        ("target_agent", "Target Agent", 22),
        ("result", "Result", 70),
    ]
    sep_line = "+" + "+".join("-" * (w + 2) for _, _, w in cols) + "+"

    def fmt_row(values: List[str]) -> str:
        cells = []
        for (key, _, width), val in zip(cols, values):
            text = (val or "")
            if len(text) > width:
                text = text[: width - 1] + "…"
            cells.append(" " + text.ljust(width) + " ")
        return "+" + "+".join(cells) + "+"

    print(f"\n=============== AGENT TRACE — {well_name} ===============", flush=True)
    print(sep_line, flush=True)
    print(fmt_row([h for _, h, _ in cols]), flush=True)
    print(sep_line, flush=True)
    for row in rows:
        print(fmt_row([str(row.get(k, "")) for k, _, _ in cols]), flush=True)
    print(sep_line, flush=True)
    print(f"{len(rows)} trace events.\n", flush=True)


@app.post("/visualize")
async def visualize(payload: VisualizeRequest) -> Dict[str, Any]:
    """Render the final drilling verdict + a matplotlib dashboard PNG."""
    try:
        metrics = _extract_metrics(payload.response)
    except Exception as exc:
        logger.exception("Metric extraction failed: %s", exc)
        metrics = {"numeric": {}, "categorical": {}, "evidence_paths": {}}

    try:
        verdict = _compute_verdict(metrics, payload.request)
    except Exception as exc:
        logger.exception("Verdict computation failed: %s", exc)
        verdict = {
            "decision": "INCONCLUSIVE",
            "headline": f"Verdict computation failed: {exc}",
            "color": "#9aa9bd",
            "scores": {"reservoir": None, "economic": None, "risk_safety": None, "overall": None},
            "drivers": [],
            "well_name": payload.request.get("well_name", "Unknown Well"),
        }

    try:
        png_b64 = _render_chart(metrics, verdict)
    except Exception as exc:
        logger.exception("Chart rendering failed: %s", exc)
        png_b64 = ""

    # --- Agent-trace table -------------------------------------------------
    trace_path: Optional[Path] = None
    trace_rows: List[Dict[str, Any]] = []
    try:
        trace_path = _find_trace_file(payload.response or {})
        trace_records = _load_trace_records(trace_path)
        trace_rows = _build_trace_table(trace_records)
    except Exception as exc:
        logger.exception("Failed to assemble trace table: %s", exc)

    # Print the trace table to the terminal so it is visible alongside the
    # final verdict (user request).
    _print_trace_table(trace_rows, verdict.get("well_name", "Unknown Well"))

    # Also print the final result to the server log so it is visible from
    # the terminal (matches the user request: "print the final result").
    logger.info(
        "FINAL_VERDICT well=%s decision=%s scores=%s drivers=%s",
        verdict.get("well_name"),
        verdict.get("decision"),
        verdict.get("scores"),
        verdict.get("drivers"),
    )
    print(
        "\n=============== DRILLING DECISION =================\n"
        f" Well     : {verdict.get('well_name')}\n"
        f" Decision : {verdict.get('decision')}\n"
        f" Headline : {verdict.get('headline')}\n"
        f" Scores   : {verdict.get('scores')}\n"
        f" Drivers  : {chr(10).join('   • ' + d for d in verdict.get('drivers', []))}\n"
        "===================================================\n",
        flush=True,
    )

    return {
        "verdict": verdict,
        "metrics": metrics,
        "chart_png_b64": png_b64,
        "trace_table": trace_rows,
        "trace_file": str(trace_path) if trace_path else None,
    }


# --------------------------------------------------------------------------- #
# Entrypoint                                                                   #
# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import sys
    import uvicorn

    reload = os.getenv("UVICORN_RELOAD", "false").strip().lower() in {"1", "true", "yes", "on"}
    workers_env = os.getenv("WEB_CONCURRENCY", "1").strip()
    try:
        workers = max(1, int(workers_env))
    except ValueError:
        workers = 1
    if reload:
        workers = 1

    # Resolve the actual port to bind. Falls back if the preferred one is
    # taken (common on macOS when a previous run is still bound).
    bind_port = UI_PORT
    if not _port_is_free(config.HOST, UI_PORT):
        if UI_PORT_AUTO:
            picked = _pick_port(config.HOST, UI_PORT, UI_PORT_RANGE)
            if picked is None:
                logger.error(
                    "Port %d is busy and no free port was found in %d..%d. "
                    "Free the port and retry, e.g.:\n"
                    "    lsof -nP -iTCP:%d -sTCP:LISTEN\n"
                    "    kill -9 <PID>\n"
                    "or set UI_PORT=<free port> / UI_PORT_RANGE=<n>.",
                    UI_PORT,
                    UI_PORT + 1,
                    UI_PORT + UI_PORT_RANGE,
                    UI_PORT,
                )
                sys.exit(1)
            logger.warning(
                "Port %d already in use — auto-falling back to %d. "
                "(Set UI_PORT_AUTO=false to disable this behaviour.)",
                UI_PORT,
                picked,
            )
            bind_port = picked
        else:
            logger.error(
                "Port %d is already in use and UI_PORT_AUTO is disabled. "
                "Free it with:\n    lsof -nP -iTCP:%d -sTCP:LISTEN\n"
                "    kill -9 <PID>\n"
                "or rerun with UI_PORT=<free port>.",
                UI_PORT,
                UI_PORT,
            )
            sys.exit(1)

    # If we ended up on a different port, regenerate the cached HTML so the
    # footer / status badge reflect reality.
    if bind_port != UI_PORT:
        DASHBOARD_HTML = DASHBOARD_HTML.replace(  # noqa: F841 (re-bound module global)
            f"Port {UI_PORT}", f"Port {bind_port}"
        ).replace(
            f"port {UI_PORT}", f"port {bind_port}"
        )
        globals()["DASHBOARD_HTML"] = DASHBOARD_HTML
        globals()["UI_PORT"] = bind_port

    logger.info(
        "Starting run_ui on %s:%d (backend=%s, samples=%d)",
        config.HOST,
        bind_port,
        API_BASE_URL,
        len(ALL_SAMPLES),
    )

    uvicorn.run(
        "run_ui:app",
        host=config.HOST,
        port=bind_port,
        log_level=config.LOG_LEVEL.lower(),
        reload=reload,
        workers=workers,
    )


