"""LangChain agents for Oil & Gas Analytics."""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

from .config import AGENT_CONFIGS, get_config
from .data_sources import SEG_OPEN_DATA_SOURCES, enrich_with_reference_data
from .tools import TOOLS

logger = logging.getLogger(__name__)


class AgentState(BaseModel):
    """State for multi-agent workflow."""

    messages: List[Dict[str, Any]] = Field(default_factory=list)
    shared_memory: Dict[str, Any] = Field(default_factory=dict)
    evidence_register: List[Dict[str, Any]] = Field(default_factory=list)
    collaboration_log: List[Dict[str, Any]] = Field(default_factory=list)
    iteration: int = 0
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
    "planner": """You are the workflow planner. Choose the next specialist agents
based on available seismic, well-log, reservoir, and risk evidence. Delegate only
work that can be grounded in data, and request research/data loading when evidence
is missing.""",
    "evaluator": """You are the independent evaluator. Critique the previous agent
outputs for missing data, weak evidence, tool failures, unsupported claims, and
cross-agent contradictions. Approve only when findings cite usable evidence.""",
    "research_agent": """You are the data research agent. Retrieve and normalize
local uploaded data first, then recommend suitable SEG/SEAM open data sources for
larger validation datasets. Never pretend that a remote dataset was downloaded.""",
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


def _extract_llm_text(result: Any) -> str:
    """Extract display text from LangChain messages and executor outputs."""

    if isinstance(result, dict):
        if "output" in result:
            return str(result["output"])
        if "content" in result:
            return str(result["content"])
        return json.dumps(result, default=_json_default)
    return str(getattr(result, "content", result))


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
    """Manages dynamic agent collaboration plus optional LLM interpretation."""

    def __init__(self):
        self.config = get_config()
        self.agents = {
            "seismic_analyzer": create_seismic_analyzer_agent(),
            "well_log_interpreter": create_well_log_interpreter_agent(),
            "reservoir_characterizer": create_reservoir_characterizer_agent(),
            "exploration_risk_assessor": create_exploration_risk_agent(),
            "report_generator": create_report_generator_agent(),
        }
        self.reasoning_llm = _create_llm(temperature=0.15)

    def _log(
        self,
        state: AgentState,
        agent: str,
        action: str,
        details: Dict[str, Any],
    ) -> None:
        """Append a compact collaboration event to shared memory."""

        state.collaboration_log.append(
            {
                "timestamp": datetime.now().isoformat(),
                "iteration": state.iteration,
                "agent": agent,
                "action": action,
                "details": details,
            }
        )

    def _invoke_reasoning_llm(
        self, role: str, prompt: str, payload: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Make a direct LLM call when configured and report when skipped."""

        if self.reasoning_llm is None:
            return {
                "mode": "llm_skipped",
                "reason": "OPENAI_API_KEY is not configured or langchain-openai is unavailable.",
            }
        try:
            messages = [
                ("system", AGENT_INSTRUCTIONS.get(role, AGENT_INSTRUCTIONS["report_generator"])),
                (
                    "human",
                    f"{prompt}\n\nShared context JSON:\n{json.dumps(payload, default=_json_default)}",
                ),
            ]
            result = self.reasoning_llm.invoke(messages)
            return {"mode": "llm", "content": _extract_llm_text(result)}
        except Exception as exc:
            logger.exception("LLM call failed for %s", role)
            return {"mode": "llm_error", "error": str(exc)}

    def _planner_delegate(self, state: AgentState, quick: bool = False) -> List[str]:
        """Select agents dynamically from available data and current evidence gaps."""

        user_input = state.user_input
        selected: List[str] = []
        if user_input.get("seismic_data"):
            selected.append("seismic_analyzer")
        if user_input.get("well_log_data"):
            selected.append("well_log_interpreter")
        if user_input.get("well_log_data") or state.analysis_results.get("well_log_interpreter"):
            selected.append("reservoir_characterizer")
        selected.append("exploration_risk_assessor")
        if quick:
            selected = [agent for agent in selected if agent != "seismic_analyzer"]

        # Keep order stable while avoiding duplicates.
        delegated = list(dict.fromkeys(selected))
        llm_plan = self._invoke_reasoning_llm(
            "planner",
            "Create a concise execution plan. Return useful critique, not hidden reasoning.",
            {
                "quick": quick,
                "available_keys": sorted(user_input.keys()),
                "delegated_agents": delegated,
                "data_sources": user_input.get("data_sources", []),
            },
        )
        self._log(
            state,
            "planner",
            "delegated",
            {"agents": delegated, "llm_plan": llm_plan},
        )
        return delegated

    def _research_missing_context(self, state: AgentState) -> None:
        """Load local reference data and add open-data recommendations."""

        before = sorted(state.user_input.keys())
        state.user_input = enrich_with_reference_data(state.user_input)
        after = sorted(state.user_input.keys())
        data_sources = state.user_input.get("data_sources", [])
        state.evidence_register.extend(data_sources)
        self._log(
            state,
            "research_agent",
            "loaded_context",
            {
                "keys_added": [key for key in after if key not in before],
                "local_sources": data_sources,
                "open_data_recommendations": SEG_OPEN_DATA_SOURCES,
            },
        )

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

    def _evaluate_iteration(self, state: AgentState, delegated_agents: List[str]) -> Dict[str, Any]:
        """Critique outputs and request retries when evidence is missing."""

        findings = state.analysis_results
        missing: List[str] = []
        weak: List[str] = []
        if "seismic_analyzer" in delegated_agents and not state.user_input.get("seismic_data"):
            missing.append("seismic_data")
        if "well_log_interpreter" in delegated_agents and not state.user_input.get("well_log_data"):
            missing.append("well_log_data")

        for agent_name in delegated_agents:
            result = findings.get(agent_name, {})
            tool_results = result.get("tool_results", {})
            errors = [
                tool_name
                for tool_name, tool_result in tool_results.items()
                if isinstance(tool_result, dict) and tool_result.get("error")
            ]
            if errors:
                weak.append(f"{agent_name}: tool errors in {', '.join(errors)}")

        approved = not missing and not weak
        llm_critique = self._invoke_reasoning_llm(
            "evaluator",
            "Critique the iteration. State approve/request_revision and evidence gaps.",
            {
                "delegated_agents": delegated_agents,
                "missing": missing,
                "weak": weak,
                "findings": findings,
            },
        )
        evaluation = {
            "approved": approved,
            "missing_evidence": missing,
            "weak_outputs": weak,
            "llm_critique": llm_critique,
        }
        self._log(state, "evaluator", "evaluated", evaluation)
        return evaluation

    def _finalize_report(self, state: AgentState, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """Run report agent after approval or final retry."""

        all_analyses = list(state.analysis_results.values())
        context = {
            "all_analyses": all_analyses,
            "evaluation": evaluation,
            "shared_memory": state.shared_memory,
            "evidence_register": state.evidence_register,
            "collaboration_log": state.collaboration_log,
        }
        report = self.execute_agent(
            "report_generator",
            "Produce a final answer grounded in the approved agent outputs and evaluator critique.",
            context,
        )
        final_llm = self._invoke_reasoning_llm(
            "report_generator",
            "Write the final executive and technical synthesis using only cited tool outputs and evidence.",
            context,
        )
        report["final_synthesis"] = final_llm
        self._log(
            state,
            "final_agent",
            "produced_answer",
            {"status": report.get("status"), "llm_mode": final_llm.get("mode")},
        )
        return report

    def execute_collaborative_workflow(
        self, user_input: Dict[str, Any], quick: bool = False, max_review_cycles: int = 2
    ) -> Dict[str, Any]:
        """Run Planner -> Research -> Executor -> Evaluator retry loop -> Final."""

        state = AgentState(
            user_input=dict(user_input),
            shared_memory={
                "workflow_goal": "Evidence-grounded oil and gas prospect analysis",
                "llm_configured": self.reasoning_llm is not None,
            },
        )
        workflow_id = datetime.now().isoformat()
        self._log(state, "planner", "started", {"workflow_id": workflow_id, "quick": quick})
        self._research_missing_context(state)

        evaluation: Dict[str, Any] = {"approved": False}
        delegated_agents: List[str] = []
        for iteration in range(1, max_review_cycles + 1):
            state.iteration = iteration
            delegated_agents = self._planner_delegate(state, quick=quick)
            for agent_name in delegated_agents:
                task = AGENT_CONFIGS[agent_name]["description"]
                context = {
                    **state.user_input,
                    "shared_memory": state.shared_memory,
                    "prior_findings": state.analysis_results,
                    "seismic_interpretation": state.analysis_results.get("seismic_analyzer", {}),
                    "petrophysics": state.analysis_results.get("well_log_interpreter", {}),
                    "reservoir_properties": state.analysis_results.get("reservoir_characterizer", {}),
                    "evidence_register": state.evidence_register,
                }
                result = self.execute_agent(agent_name, task, context)
                state.analysis_results[agent_name] = result
                state.completed_agents.append(agent_name)
                self._log(
                    state,
                    agent_name,
                    "executed",
                    {
                        "status": result.get("status"),
                        "tools": list(result.get("tool_results", {}).keys()),
                        "llm_mode": result.get("result", {}).get("mode")
                        if isinstance(result.get("result"), dict)
                        else "llm",
                    },
                )

            evaluation = self._evaluate_iteration(state, delegated_agents)
            if evaluation["approved"]:
                break
            self._log(
                state,
                "planner",
                "revision_requested",
                {
                    "next_action": "research_agent_reload_then_retry",
                    "missing_evidence": evaluation["missing_evidence"],
                    "weak_outputs": evaluation["weak_outputs"],
                },
            )
            self._research_missing_context(state)

        final_report = self._finalize_report(state, evaluation)
        state.final_report = final_report

        return {
            "workflow_id": workflow_id,
            "status": "success" if evaluation.get("approved") else "partial",
            "planner_delegation": delegated_agents,
            "shared_memory": state.shared_memory,
            "evidence_register": state.evidence_register,
            "collaboration_log": state.collaboration_log,
            "evaluation": evaluation,
            "agents_executed": state.completed_agents,
            "findings": state.analysis_results,
            "seismic_analysis": state.analysis_results.get("seismic_analyzer", {}),
            "well_log_analysis": state.analysis_results.get("well_log_interpreter", {}),
            "reservoir_analysis": state.analysis_results.get("reservoir_characterizer", {}),
            "risk_assessment": state.analysis_results.get("exploration_risk_assessor", {}),
            "final_report": final_report,
            "messages": [
                f"{event['agent']} {event['action']} at {event['timestamp']}"
                for event in state.collaboration_log
            ],
            "open_data_recommendations": SEG_OPEN_DATA_SOURCES,
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
