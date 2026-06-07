"""Main API server for Oil & Gas Analytics Multi-Agent System."""

import os
import json
import time
import uuid
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks, Request
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

# Import application components
from app import __version__
from app.config import get_config
from app.data_sources import SEG_OPEN_DATA_SOURCES
from app.logging_config import clear_context, configure_logging, get_logger, set_context
from app.workflows import WorkflowOrchestrator
from app.tools import TOOLS
from app import rag as rag_module
from app import memory as memory_module

config = get_config()

# Structured logging (JSON in production, human-readable otherwise).
configure_logging(level=config.LOG_LEVEL, json_logs=config.JSON_LOGS)
logger = get_logger("oilgas.api")


def _api_key_status(value: str) -> str:
    """Return ``configured`` / ``not configured`` — never the secret itself."""
    return "configured" if value and value.strip() else "not configured"


# Log the active LLM configuration so it's obvious in the logs that
# OPENAI_API_KEY and OPENAI_BASE_URL were sourced strictly from the
# environment (with https://api.core42.ai/v1 as the documented fallback
# for OPENAI_BASE_URL). The API key itself is NEVER printed (not even
# masked) — only its presence status and source are logged.
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

# Validate critical settings (fails fast in production)
config.validate()

# Ensure required directories exist
os.makedirs(os.path.dirname(config.LOG_FILE) or "logs", exist_ok=True)
os.makedirs("data/uploads", exist_ok=True)

# Initialize workflow orchestrator (singleton)
orchestrator = WorkflowOrchestrator()


# Request/Response Models
class AnalysisRequest(BaseModel):
    """Request for analysis"""

    use_case_id: Optional[int] = None  # client-supplied tracking ID echoed back in the response
    well_name: str
    analysis_type: str = "full"  # 'full' or 'quick'
    seismic_data: Optional[Dict[str, Any]] = None
    well_log_data: Optional[Dict[str, Any]] = None
    seismic_csv_path: Optional[str] = None
    well_log_csv_path: Optional[str] = None
    seam_well_number: Optional[int] = 1
    user_notes: Optional[str] = None


class AnalysisResponse(BaseModel):
    """Response for analysis"""

    use_case_id: Optional[int] = None  # echoed back from the request for tracking
    workflow_id: str
    status: str
    results: Dict[str, Any]
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response"""

    status: str
    version: str
    timestamp: str
    agents_available: int


class WorkflowHistoryResponse(BaseModel):
    """Workflow history response"""

    total_executions: int
    recent_workflows: list


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management"""
    logger.info("Oil & Gas Analytics System starting...")
    logger.info(f"API running on port {config.API_PORT}")
    logger.info(f"UI running on port {config.UI_PORT}")
    yield
    logger.info("Oil & Gas Analytics System shutting down...")


# Create FastAPI application
app = FastAPI(
    title="Oil & Gas Analytics Multi-Agent System",
    description="Production-ready multi-agent AI system for oil & gas exploration and analysis",
    version=__version__,
    lifespan=lifespan,
    docs_url="/docs" if config.DEBUG else None,
    redoc_url="/redoc" if config.DEBUG else None,
)

# CORS - explicit allow-list from environment (CORS_ORIGINS)
allow_origins = config.CORS_ORIGINS or ["*"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allow_origins,
    allow_credentials=allow_origins != ["*"],
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Attach a request ID and basic access log to every response."""
    request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex)
    set_context(request_id=request_id, path=request.url.path, method=request.method)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled error rid=%s path=%s", request_id, request.url.path)
        clear_context("request_id", "path", "method")
        return JSONResponse(
            status_code=500,
            content={"error": "internal_server_error", "request_id": request_id},
        )
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Response-Time-ms"] = str(duration_ms)
    logger.info(
        "request_completed",
        extra={
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    clear_context("request_id", "path", "method")
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )


# Health and Info Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Liveness probe - process is up."""
    return {
        "status": "healthy",
        "version": __version__,
        "timestamp": datetime.now().isoformat(),
        "agents_available": len(orchestrator.manager.agents) if hasattr(orchestrator, "manager") else 5,
    }


@app.get("/readyz")
async def readiness_check():
    """Readiness probe - validates downstream dependencies."""
    ready = config.llm_enabled
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "ready": ready,
            "llm_enabled": config.llm_enabled,
            "timestamp": datetime.now().isoformat(),
        },
    )


@app.get("/info")
async def get_info():
    """Get system information (secrets redacted)."""
    return {
        "system_name": "Oil & Gas Analytics Multi-Agent System",
        "version": __version__,
        "config": config.safe_dict(),
        "agents": {
            "planner": "Dynamically delegates specialists and revision cycles",
            "research_agent": "Loads local evidence and recommends SEG/SEAM open data",
            "seismic_analyzer": "Analyzes seismic data for structures",
            "well_log_interpreter": "Interprets well logs",
            "reservoir_characterizer": "Characterizes reservoir properties",
            "exploration_risk_assessor": "Assesses exploration risks",
            "evaluator": "Critiques outputs and requests retries when evidence is weak",
            "report_generator": "Generates comprehensive reports",
        },
        "capabilities": [
            "Seismic interpretation",
            "Well log analysis",
            "Reservoir characterization",
            "Risk assessment",
            "Volumetric calculation",
            "Report generation",
            "Planner-executor-evaluator retry loops",
            "Shared memory and collaboration logs",
            "Local CSV evidence loading and SEG open-data guidance",
        ],
    }


# Analysis Endpoints
# ``/run`` is the canonical path (preferred by CLI and run_ui.py).
# ``/analyze`` is kept as a deprecated alias for backward compatibility.
@app.post("/run", response_model=AnalysisResponse, tags=["analysis"])
@app.post(
    "/analyze",
    response_model=AnalysisResponse,
    tags=["analysis"],
    deprecated=True,
)
async def analyze(request: AnalysisRequest, background_tasks: BackgroundTasks):
    """
    Execute multi-agent analysis on provided data

    Args:
        request: Analysis request with well data
        background_tasks: Background task manager

    Returns:
        Analysis results with workflow ID
    """
    try:
        logger.info(
            "Received analysis request for %s (use_case_id=%s)",
            request.well_name,
            request.use_case_id,
        )

        # Prepare input data
        user_input = {
            "use_case_id": request.use_case_id,
            "well_name": request.well_name,
            "seismic_data": request.seismic_data or {},
            "well_log_data": request.well_log_data or {},
            "seismic_csv_path": request.seismic_csv_path,
            "well_log_csv_path": request.well_log_csv_path,
            "seam_well_number": request.seam_well_number,
            "user_notes": request.user_notes or "",
        }

        # Execute appropriate workflow
        if request.analysis_type == "quick":
            result = orchestrator.execute_quick_analysis(user_input)
        else:
            result = orchestrator.execute_full_analysis(user_input)

        # Make sure the workflow result also carries the use_case_id so the
        # nested ``results`` block matches the saved output_examples/*.json
        # snapshots ("use_case_id" appears at the top of those files too).
        if isinstance(result, dict) and request.use_case_id is not None:
            result.setdefault("use_case_id", request.use_case_id)

        # Log to file
        background_tasks.add_task(
            log_analysis_result, result, request.well_name
        )

        return {
            "use_case_id": request.use_case_id,
            "workflow_id": result.get("workflow_id"),
            "status": result.get("status"),
            "results": result,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/run/batch", tags=["analysis"])
@app.post("/analyze/batch", tags=["analysis"], deprecated=True)
async def analyze_batch(wells_data: list[Dict[str, Any]]):
    """
    Execute analysis on multiple wells

    Args:
        wells_data: List of well data objects

    Returns:
        Batch analysis results
    """
    try:
        results = []
        for well_data in wells_data:
            result = orchestrator.execute_full_analysis(well_data)
            results.append(result)

        return {
            "status": "success",
            "batch_size": len(wells_data),
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/workflows/history", response_model=WorkflowHistoryResponse)
async def get_workflow_history(limit: int = 10):
    """
    Get recent workflow execution history

    Args:
        limit: Number of recent workflows to return

    Returns:
        Workflow history
    """
    history = orchestrator.get_execution_history()
    return {
        "total_executions": len(history),
        "recent_workflows": history[-limit:],
    }


@app.delete("/workflows/history")
async def clear_workflow_history():
    """Clear workflow execution history"""
    orchestrator.clear_history()
    return {"status": "success", "message": "History cleared"}


# Tool Endpoints
@app.get("/tools")
async def list_tools():
    """List available analysis tools"""
    return {
        "total_tools": len(TOOLS),
        "tools": list(TOOLS.keys()),
        "categories": {
            "seismic": [
                "analyze_seismic_amplitude",
                "detect_faults",
                "pick_horizons",
            ],
            "well_logs": [
                "classify_lithology",
                "identify_fluids",
                "estimate_porosity",
            ],
            "reservoir": [
                "estimate_permeability",
                "analyze_saturation",
                "predict_pressure",
            ],
            "exploration": [
                "evaluate_trap",
                "calculate_volumes",
                "assess_seal_integrity",
            ],
            "reporting": [
                "synthesize_analysis",
                "create_visualizations",
                "format_recommendations",
            ],
        },
    }


@app.get("/data/open-sources")
async def list_open_data_sources():
    """List public data sources suitable for larger seismic validation."""
    return {
        "status": "success",
        "sources": SEG_OPEN_DATA_SOURCES,
        "note": (
            "Large SEG/SEAM files are not auto-downloaded by the API. Download them "
            "into the data directory, then pass seismic_csv_path/well_log_csv_path "
            "for normalized CSV extracts or uploaded local files."
        ),
    }


@app.post("/tools/{tool_name}")
async def execute_tool(tool_name: str, data: Dict[str, Any]):
    """
    Execute a specific analysis tool directly

    Args:
        tool_name: Name of the tool to execute
        data: Input data for the tool

    Returns:
        Tool execution result
    """
    try:
        if tool_name not in TOOLS:
            raise HTTPException(
                status_code=404, detail=f"Tool {tool_name} not found"
            )

        tool_func = TOOLS[tool_name]
        result = tool_func(data)

        return {
            "tool": tool_name,
            "status": "success",
            "result": result,
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"Tool execution failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# Data Upload Endpoints
def _safe_filename(name: str) -> str:
    base = os.path.basename(name or "")
    return "".join(c for c in base if c.isalnum() or c in (".", "_", "-"))[:200] or "upload"


async def _read_capped(file: UploadFile) -> bytes:
    contents = await file.read()
    if len(contents) > config.MAX_REQUEST_BYTES:
        raise HTTPException(status_code=413, detail="File too large")
    return contents


@app.post("/upload/seismic")
async def upload_seismic_data(file: UploadFile = File(...)):
    """Upload seismic data file (CSV)"""
    try:
        contents = await _read_capped(file)
        filename = f"seismic_{int(datetime.now().timestamp())}_{_safe_filename(file.filename or '')}.csv"
        filepath = os.path.join("data/uploads", filename)

        with open(filepath, "wb") as f:
            f.write(contents)

        return {
            "status": "success",
            "filename": filename,
            "size": len(contents),
            "path": filepath,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Seismic upload failed")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/well-log")
async def upload_well_log_data(file: UploadFile = File(...)):
    """Upload well log data file (LAS or CSV)"""
    try:
        contents = await _read_capped(file)
        filename = f"welllog_{int(datetime.now().timestamp())}_{_safe_filename(file.filename or '')}"
        filepath = os.path.join("data/uploads", filename)

        with open(filepath, "wb") as f:
            f.write(contents)

        return {
            "status": "success",
            "filename": filename,
            "size": len(contents),
            "path": filepath,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Well-log upload failed")
        raise HTTPException(status_code=500, detail=str(e))


# Helper Functions
def log_analysis_result(result: Dict[str, Any], well_name: str):
    """Log analysis result to file"""
    try:
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "well_name": well_name,
            "workflow_id": result.get("workflow_id"),
            "status": result.get("status"),
            "summary": {
                "seismic": result.get("seismic_analysis", {}).get("status"),
                "well_logs": result.get("well_log_analysis", {}).get("status"),
                "reservoir": result.get("reservoir_analysis", {}).get("status"),
                "risk": result.get("risk_assessment", {}).get("status"),
            },
            "collaboration": {
                "agents_executed": result.get("agents_executed", []),
                "planner_delegation": result.get("planner_delegation", []),
                "evaluation": result.get("evaluation", {}),
            },
        }

        with open(config.LOG_FILE, "a") as f:
            f.write(json.dumps(log_entry) + "\n")
    except Exception as e:
        logger.error(f"Failed to log analysis result: {str(e)}")


@app.get("/logs/download")
async def download_logs():
    """Download analysis logs"""
    if not os.path.exists(config.LOG_FILE):
        raise HTTPException(status_code=404, detail="Logs not found")

    return FileResponse(
        config.LOG_FILE,
        media_type="application/json",
        filename="agent_logs.json",
    )


# ---------------------------------------------------------------------------
# RAG, persistent memory and observability endpoints
# ---------------------------------------------------------------------------
@app.get("/rag/status")
async def rag_status():
    """Return current RAG index status."""
    return rag_module.status()


@app.post("/rag/build")
async def rag_build(force: bool = False):
    """Build/rebuild the RAG index. Requires OPENAI_API_KEY for embeddings."""
    try:
        chunks = rag_module.build_index(force=force)
        return {"status": "ok", "chunks": chunks, **rag_module.status()}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/rag/search")
async def rag_search(q: str, k: int = 4):
    """Search the RAG index for relevant chunks."""
    if not q.strip():
        raise HTTPException(status_code=400, detail="Query 'q' must not be empty")
    return {"query": q, "results": rag_module.retrieve(q, k=k)}


@app.get("/memory/{key}")
async def get_memory(key: str, limit: int = 5):
    """Return persisted prior-run memory for a well/asset key."""
    entries = memory_module.recall({"well_name": key}, limit=limit)
    return {"key": key, "entries": entries, "count": len(entries)}


@app.get("/events/tail")
async def events_tail(n: int = 50):
    """Tail the structured observability event log (JSONL)."""
    path = os.getenv("OBS_EVENT_FILE", "logs/events.jsonl")
    if not os.path.exists(path):
        return {"events": [], "file": path}
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-max(1, min(n, 1000)) :]
        events = []
        for line in lines:
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError:
                continue
        return {"events": events, "file": path, "count": len(events)}
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=str(exc))


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API documentation"""
    return {
        "message": "Oil & Gas Analytics Multi-Agent System",
        "version": __version__,
        "documentation": "/docs",
        "quick_start": {
            "1_check_health": "/health",
            "2_view_info": "/info",
            "3_submit_analysis": "POST /run (alias: POST /analyze, deprecated)",
            "4_view_history": "/workflows/history",
        },
        "api_port": config.API_PORT,
        "ui_port": config.UI_PORT,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "run:app",
        host=config.HOST,
        port=config.API_PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=config.DEBUG and not config.is_production,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )
