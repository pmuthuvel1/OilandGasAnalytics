"""LangGraph workflows for orchestrating multi-agent analysis"""

import logging
import json
from typing import Any, Dict, List, Optional, TypedDict
from datetime import datetime
from langgraph.graph import StateGraph, END

from .config import get_config
from .agents import AgentExecutorManager

logger = logging.getLogger(__name__)


class AnalysisState(TypedDict, total=False):
    """State definition for analysis workflow"""

    workflow_id: str
    user_input: Dict[str, Any]
    seismic_analysis: Dict[str, Any]
    well_log_analysis: Dict[str, Any]
    reservoir_analysis: Dict[str, Any]
    risk_assessment: Dict[str, Any]
    final_report: Dict[str, Any]
    messages: List[str]
    errors: List[str]


def create_seismic_analysis_node(manager: AgentExecutorManager):
    """Create seismic analysis node"""

    def seismic_analysis(state: AnalysisState) -> AnalysisState:
        logger.info("Executing seismic analysis...")

        task = """Analyze the provided seismic data to:
        1. Identify amplitude anomalies and bright spots
        2. Detect potential fault structures
        3. Pick key seismic horizons for structure mapping
        
        Focus on hydrocarbon indicators and structural traps."""

        result = manager.execute_agent("seismic_analyzer", task, state["user_input"])

        state["seismic_analysis"] = result
        state["messages"].append(f"✓ Seismic analysis completed at {datetime.now()}")

        if result["status"] == "error":
            state["errors"].append(f"Seismic analysis error: {result.get('error')}")

        return state

    return seismic_analysis


def create_well_log_analysis_node(manager: AgentExecutorManager):
    """Create well log analysis node"""

    def well_log_analysis(state: AnalysisState) -> AnalysisState:
        logger.info("Executing well log analysis...")

        task = """Analyze the provided well log data to:
        1. Classify lithology from gamma ray and resistivity
        2. Identify fluid types
        3. Estimate porosity and reservoir quality
        
        Assess which sections are potential pay zones."""

        result = manager.execute_agent("well_log_interpreter", task, state["user_input"])

        state["well_log_analysis"] = result
        state["messages"].append(f"✓ Well log analysis completed at {datetime.now()}")

        if result["status"] == "error":
            state["errors"].append(f"Well log analysis error: {result.get('error')}")

        return state

    return well_log_analysis


def create_reservoir_analysis_node(manager: AgentExecutorManager):
    """Create reservoir characterization node"""

    def reservoir_analysis(state: AnalysisState) -> AnalysisState:
        logger.info("Executing reservoir characterization...")

        # Pass previous analysis results for context
        context = {
            **state["user_input"],
            "seismic_findings": state.get("seismic_analysis", {}),
            "well_log_findings": state.get("well_log_analysis", {}),
        }

        task = """Characterize the reservoir based on seismic and well log data:
        1. Estimate permeability and flow characteristics
        2. Analyze fluid saturation distribution
        3. Predict formation pressures
        
        Assess producibility and recovery potential."""

        result = manager.execute_agent("reservoir_characterizer", task, context)

        state["reservoir_analysis"] = result
        state["messages"].append(
            f"✓ Reservoir characterization completed at {datetime.now()}"
        )

        if result["status"] == "error":
            state["errors"].append(f"Reservoir analysis error: {result.get('error')}")

        return state

    return reservoir_analysis


def create_risk_assessment_node(manager: AgentExecutorManager):
    """Create risk assessment node"""

    def risk_assessment(state: AnalysisState) -> AnalysisState:
        logger.info("Executing risk assessment...")

        # Compile all findings for risk assessment
        context = {
            **state["user_input"],
            "seismic_interpretation": state.get("seismic_analysis", {}),
            "petrophysics": state.get("well_log_analysis", {}),
            "reservoir_properties": state.get("reservoir_analysis", {}),
        }

        task = """Assess exploration risks and opportunities:
        1. Evaluate trap geometry and seal integrity
        2. Calculate volumetric estimates and recoverable reserves
        3. Assess overall exploration risk and confidence
        
        Provide drilling recommendations."""

        result = manager.execute_agent("exploration_risk_assessor", task, context)

        state["risk_assessment"] = result
        state["messages"].append(f"✓ Risk assessment completed at {datetime.now()}")

        if result["status"] == "error":
            state["errors"].append(f"Risk assessment error: {result.get('error')}")

        return state

    return risk_assessment


def create_report_generation_node(manager: AgentExecutorManager):
    """Create final report generation node"""

    def report_generation(state: AnalysisState) -> AnalysisState:
        logger.info("Generating final report...")

        # Compile all analyses
        all_analyses = [
            state.get("seismic_analysis", {}),
            state.get("well_log_analysis", {}),
            state.get("reservoir_analysis", {}),
            state.get("risk_assessment", {}),
        ]

        context = {
            "all_analyses": all_analyses,
            "workflow_id": state["workflow_id"],
            "errors": state.get("errors", []),
        }

        task = """Generate comprehensive technical report:
        1. Synthesize findings from all analysis agents
        2. Create visualization recommendations
        3. Formulate final drilling/investment recommendations
        
        Structure report for executive and technical audiences."""

        result = manager.execute_agent("report_generator", task, context)

        state["final_report"] = result
        state["messages"].append(f"✓ Report generation completed at {datetime.now()}")

        return state

    return report_generation


def create_analysis_workflow() -> Any:
    """Create the complete multi-agent analysis workflow using LangGraph"""

    config = get_config()
    manager = AgentExecutorManager()

    # Create the workflow graph
    workflow = StateGraph(AnalysisState)

    # Add nodes
    workflow.add_node("seismic_analysis", create_seismic_analysis_node(manager))
    workflow.add_node("well_log_analysis", create_well_log_analysis_node(manager))
    workflow.add_node("reservoir_analysis", create_reservoir_analysis_node(manager))
    workflow.add_node("risk_assessment", create_risk_assessment_node(manager))
    workflow.add_node("report_generation", create_report_generation_node(manager))

    # Define edges - agents run in sequence
    workflow.add_edge("seismic_analysis", "well_log_analysis")
    workflow.add_edge("well_log_analysis", "reservoir_analysis")
    workflow.add_edge("reservoir_analysis", "risk_assessment")
    workflow.add_edge("risk_assessment", "report_generation")
    workflow.add_edge("report_generation", END)

    # Set entry point
    workflow.set_entry_point("seismic_analysis")

    # Compile the graph
    return workflow.compile()


def create_quick_analysis_workflow() -> Any:
    """Create a faster workflow that only runs critical agents"""

    config = get_config()
    manager = AgentExecutorManager()

    workflow = StateGraph(AnalysisState)

    workflow.add_node("well_log_analysis", create_well_log_analysis_node(manager))
    workflow.add_node("risk_assessment", create_risk_assessment_node(manager))
    workflow.add_node("report_generation", create_report_generation_node(manager))

    workflow.add_edge("well_log_analysis", "risk_assessment")
    workflow.add_edge("risk_assessment", "report_generation")
    workflow.add_edge("report_generation", END)

    workflow.set_entry_point("well_log_analysis")

    return workflow.compile()


class WorkflowOrchestrator:
    """Orchestrates multi-agent workflows"""

    def __init__(self):
        self.config = get_config()
        self.manager = AgentExecutorManager()
        self.full_workflow = None
        self.quick_workflow = None
        self.execution_history = []

    def execute_full_analysis(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute full multi-agent analysis workflow"""

        logger.info(f"Starting full analysis workflow")

        workflow_id = datetime.now().isoformat()

        try:
            result = self.manager.execute_collaborative_workflow(
                user_input=user_input,
                quick=False,
            )
            self.execution_history.append(result)
            return result
        except Exception as e:
            logger.error(f"Workflow execution failed: {str(e)}")
            return {
                "status": "error",
                "workflow_id": workflow_id,
                "error": str(e),
                "messages": [],
            }

    def execute_quick_analysis(self, user_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute quick analysis workflow"""

        logger.info(f"Starting quick analysis workflow")

        workflow_id = datetime.now().isoformat()

        try:
            result = self.manager.execute_collaborative_workflow(
                user_input=user_input,
                quick=True,
            )
            self.execution_history.append(result)
            return result
        except Exception as e:
            logger.error(f"Quick workflow execution failed: {str(e)}")
            return {
                "status": "error",
                "workflow_id": workflow_id,
                "error": str(e),
                "messages": [],
            }

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """Get workflow execution history"""
        return self.execution_history

    def clear_history(self):
        """Clear execution history"""
        self.execution_history = []
