"""Main API server for Oil & Gas Analytics Multi-Agent System - Runs on port 8000"""

import os
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, File, UploadFile, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Import application components
from app.config import get_config
from app.data_sources import SEG_OPEN_DATA_SOURCES
from app.workflows import WorkflowOrchestrator
from app.tools import TOOLS

config = get_config()

# Create logs directory if it doesn't exist
os.makedirs("logs", exist_ok=True)
os.makedirs("data/uploads", exist_ok=True)

# Initialize workflow orchestrator
orchestrator = WorkflowOrchestrator()


# Request/Response Models
class AnalysisRequest(BaseModel):
    """Request for analysis"""

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
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health and Info Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat(),
        "agents_available": 5,
    }


@app.get("/info")
async def get_info():
    """Get system information"""
    return {
        "system_name": "Oil & Gas Analytics Multi-Agent System",
        "version": "1.0.0",
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
        "api_port": config.API_PORT,
        "ui_port": config.UI_PORT,
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
@app.post("/analyze", response_model=AnalysisResponse)
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
        logger.info(f"Received analysis request for {request.well_name}")

        # Prepare input data
        user_input = {
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

        # Log to file
        background_tasks.add_task(
            log_analysis_result, result, request.well_name
        )

        return {
            "workflow_id": result.get("workflow_id"),
            "status": result.get("status"),
            "results": result,
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Analysis failed: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/analyze/batch")
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
@app.post("/upload/seismic")
async def upload_seismic_data(file: UploadFile = File(...)):
    """Upload seismic data file (CSV)"""
    try:
        contents = await file.read()
        filename = f"seismic_{datetime.now().timestamp()}.csv"
        filepath = os.path.join("data/uploads", filename)

        with open(filepath, "wb") as f:
            f.write(contents)

        return {
            "status": "success",
            "filename": filename,
            "size": len(contents),
            "path": filepath,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/upload/well-log")
async def upload_well_log_data(file: UploadFile = File(...)):
    """Upload well log data file (LAS or CSV)"""
    try:
        contents = await file.read()
        filename = f"welllog_{datetime.now().timestamp()}_{file.filename}"
        filepath = os.path.join("data/uploads", filename)

        with open(filepath, "wb") as f:
            f.write(contents)

        return {
            "status": "success",
            "filename": filename,
            "size": len(contents),
            "path": filepath,
        }
    except Exception as e:
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


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API documentation"""
    return {
        "message": "Oil & Gas Analytics Multi-Agent System",
        "version": "1.0.0",
        "documentation": "/docs",
        "quick_start": {
            "1_check_health": "/health",
            "2_view_info": "/info",
            "3_submit_analysis": "POST /analyze",
            "4_view_history": "/workflows/history",
        },
        "api_port": config.API_PORT,
        "ui_port": config.UI_PORT,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=config.HOST,
        port=config.API_PORT,
        log_level=config.LOG_LEVEL.lower(),
    )
