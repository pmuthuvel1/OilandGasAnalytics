"""LangChain agents for Oil & Gas Analytics."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .config import AGENT_CONFIGS, get_config
from .tools import TOOLS

logger = logging.getLogger(__name__)


class AgentState(BaseModel):
    """State for multi-agent workflow."""

    messages: List[Dict[str, Any]] = Field(default_factory=list)
    analysis_results: Dict[str, Any] = Field(default_factory=dict)
    current_agent: str = ""
    completed_agents: List[str] = Field(default_factory=list)
    user_input: Dict[str, Any] = Field(default_factory=dict)
    final_report: Dict[str, Any] = Field(default_factory=dict)


class ToolInput(BaseModel):
    """Generic input schema for registry-backed domain tools."""

    data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Oil and gas analysis payload for this tool.",
    )


AGENT_INSTRUCTIONS = {
    "seismic_analyzer": """You are an expert seismic interpreter for oil and gas exploration.
Use the seismic tools to identify amplitude anomalies, likely discontinuities, and
horizon candidates. Tie every interpretation to numeric tool outputs, call out data
limitations, and avoid overclaiming hydrocarbon presence.""",
    "well_log_interpreter": """You are an expert petrophysicist. Use the well log tools to
classify lithology, identify likely fluids, and assess reservoir quality. Explain
which log responses support each conclusion and flag uncertainty in sparse data.""",
    "reservoir_characterizer": """You are an expert reservoir engineer. Use the reservoir
tools to estimate permeability, saturation, and pressure. Integrate prior seismic
and petrophysical findings into a producibility view with clear assumptions.""",
    "exploration_risk_assessor": """You are an exploration manager. Use the trap, volume,
and seal tools to evaluate commercial and subsurface risk. Separate technical
confidence from business recommendation and include clear risk mitigations.""",
    "report_generator": """You are a senior technical report writer. Synthesize all prior
agent outputs into a concise executive summary, technical findings, visual
recommendations, and next actions. Preserve caveats and uncertainty.""",
}


SEISMIC_TOOLS = {
    "analyze_seismic_amplitude",
    "detect_faults",
    "pick_horizons",
}
WELL_LOG_TOOLS = {
    "classify_lithology",
    "identify_fluids",
    "estimate_porosity",
    "estimate_permeability",
    "analyze_saturation",
    "predict_pressure",
}
REPORT_LIST_TOOLS = {
    "synthesize_analysis",
    "format_recommendations",
}


def _is_real_api_key(api_key: str) -> bool:
    """Return True when the configured API key looks intentional."""

    return bool(api_key and api_key.strip() and api_key.strip().upper() not in {"NA", "N/A", "NONE", "CHANGEME"})


def _json_default(value: Any) -> str:
    """JSON fallback for objects returned by third-party libraries."""

    return str(value)


def _create_structured_tool(tool_name: str) -> StructuredTool:
    """Create a LangChain structured tool from the local tool registry."""

    tool_func = TOOLS[tool_name]

    def invoke_tool(data: Dict[str, Any]) -> str:
        result = tool_func(data)
        return json.dumps(result, default=_json_default)

    invoke_tool.__name__ = tool_name
    return StructuredTool.from_function(
        func=invoke_tool,
        name=tool_name,
        description=tool_func.__doc__ or f"Run {tool_name}.",
        args_schema=ToolInput,
    )


def create_tool_functions(tool_names: Optional[List[str]] = None) -> List[StructuredTool]:
    """Create LangChain tools for the selected registry entries."""

    selected_tools = tool_names or list(TOOLS.keys())
    return [_create_structured_tool(name) for name in selected_tools]


def _create_llm(temperature: float = 0.2) -> Optional[Any]:
    """Create the configured chat model when an API key is available."""

    config = get_config()
    if not _is_real_api_key(config.OPENAI_API_KEY):
        logger.warning("OPENAI_API_KEY is not configured; agents will use deterministic tool results only.")
        return None

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        logger.warning(
            "langchain-openai is not installed; agents will use deterministic tool results only."
        )
        return None

    llm_params: Dict[str, Any] = {
        "api_key": config.OPENAI_API_KEY,
        "model": config.OPENAI_MODEL,
        "temperature": temperature,
    }
    if config.OPENAI_BASE_URL:
        llm_params["base_url"] = config.OPENAI_BASE_URL

    return ChatOpenAI(**llm_params)


def _create_agent_executor(agent_name: str, temperature: float = 0.2) -> Optional[Any]:
    """Create one configured LangChain function-calling agent."""

    llm = _create_llm(temperature=temperature)
    if llm is None:
        return None

    try:
        from langchain.agents import AgentExecutor, create_openai_functions_agent
    except ImportError:
        logger.warning(
            "Installed LangChain does not expose the legacy function-agent API; "
            "agents will use deterministic tool results only."
        )
        return None

    agent_config = AGENT_CONFIGS[agent_name]
    tools = create_tool_functions(agent_config["tools"])
    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", AGENT_INSTRUCTIONS[agent_name]),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )
    agent = create_openai_functions_agent(llm, tools, prompt)
    config = get_config()

    return AgentExecutor.from_agent_and_tools(
        agent=agent,
        tools=tools,
        verbose=False,
        max_iterations=config.MAX_ITERATIONS,
        max_execution_time=config.AGENT_TIMEOUT,
        handle_parsing_errors=True,
    )


def create_seismic_analyzer_agent() -> Optional[Any]:
    """Create SeismicAnalyzer agent."""

    return _create_agent_executor("seismic_analyzer", temperature=0.2)


def create_well_log_interpreter_agent() -> Optional[Any]:
    """Create WellLogInterpreter agent."""

    return _create_agent_executor("well_log_interpreter", temperature=0.2)


def create_reservoir_characterizer_agent() -> Optional[Any]:
    """Create ReservoirCharacterizer agent."""

    return _create_agent_executor("reservoir_characterizer", temperature=0.2)


def create_exploration_risk_agent() -> Optional[Any]:
    """Create ExplorationRiskAssessor agent."""

    return _create_agent_executor("exploration_risk_assessor", temperature=0.2)


def create_report_generator_agent() -> Optional[Any]:
    """Create ReportGenerator agent."""

    return _create_agent_executor("report_generator", temperature=0.3)


def _analysis_payload_for_tool(tool_name: str, context: Dict[str, Any]) -> Any:
    """Select the most relevant payload shape for each tool family."""

    if tool_name in SEISMIC_TOOLS:
        return context.get("seismic_data") or context
    if tool_name in WELL_LOG_TOOLS:
        return context.get("well_log_data") or context
    if tool_name in REPORT_LIST_TOOLS:
        return context.get("all_analyses") or []
    return context


class AgentExecutorManager:
    """Manages deterministic tool execution plus optional LLM interpretation."""

    def __init__(self):
        self.config = get_config()
        self.agents = {
            "seismic_analyzer": create_seismic_analyzer_agent(),
            "well_log_interpreter": create_well_log_interpreter_agent(),
            "reservoir_characterizer": create_reservoir_characterizer_agent(),
            "exploration_risk_assessor": create_exploration_risk_agent(),
            "report_generator": create_report_generator_agent(),
        }

    def _run_configured_tools(self, agent_name: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """Run an agent's required tools before LLM synthesis."""

        tool_results: Dict[str, Any] = {}
        for tool_name in AGENT_CONFIGS[agent_name]["tools"]:
            try:
                payload = _analysis_payload_for_tool(tool_name, context)
                tool_results[tool_name] = TOOLS[tool_name](payload)
            except Exception as exc:
                logger.exception("Tool %s failed for agent %s", tool_name, agent_name)
                tool_results[tool_name] = {"error": str(exc)}
        return tool_results

    def execute_agent(
        self, agent_name: str, task_description: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single agent with reliable tool-first behavior."""

        if agent_name not in AGENT_CONFIGS:
            return {"status": "error", "error": f"Agent {agent_name} not found"}

        tool_results = self._run_configured_tools(agent_name, context)
        agent = self.agents.get(agent_name)
        base_result = {
            "agent": agent_name,
            "agent_name": AGENT_CONFIGS[agent_name]["name"],
            "description": AGENT_CONFIGS[agent_name]["description"],
            "tool_results": tool_results,
            "timestamp": datetime.now().isoformat(),
        }

        if agent is None:
            return {
                "status": "success",
                **base_result,
                "result": {
                    "mode": "tool_only",
                    "summary": "LLM synthesis skipped because OPENAI_API_KEY is not configured.",
                    "tool_results": tool_results,
                },
            }

        try:
            input_text = (
                f"{task_description}\n\n"
                f"Context JSON:\n{json.dumps(context, default=_json_default)}\n\n"
                f"Precomputed tool results JSON:\n{json.dumps(tool_results, default=_json_default)}\n\n"
                "Use the precomputed tool results as the source of truth. Call additional tools only if needed."
            )
            llm_result = agent.invoke({"input": input_text, "chat_history": []})
            return {
                "status": "success",
                **base_result,
                "result": llm_result,
            }
        except Exception as exc:
            logger.exception("Error executing LLM synthesis for agent %s", agent_name)
            return {
                "status": "success",
                **base_result,
                "result": {
                    "mode": "tool_only_after_llm_error",
                    "summary": "LLM synthesis failed; returning deterministic tool results.",
                    "llm_error": str(exc),
                    "tool_results": tool_results,
                },
            }

    def execute_workflow(
        self, workflow_config: Dict[str, Any], data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a complete workflow with multiple agents."""

        results = {
            "workflow_id": datetime.now().isoformat(),
            "status": "in_progress",
            "agents_executed": [],
            "findings": {},
            "errors": [],
        }

        for agent_name in workflow_config.get("agent_sequence", []):
            task = workflow_config.get(f"{agent_name}_task", "Analyze provided data")
            result = self.execute_agent(agent_name, task, data)
            results["agents_executed"].append(agent_name)

            if result["status"] == "success":
                results["findings"][agent_name] = result
            else:
                results["errors"].append(
                    {"agent": agent_name, "error": result.get("error", "Unknown error")}
                )

        results["status"] = "completed" if not results["errors"] else "partial"
        return results


def create_agent_executor(agent_name: str) -> Optional[Any]:
    """Compatibility factory for package-level imports."""

    return _create_agent_executor(agent_name)
