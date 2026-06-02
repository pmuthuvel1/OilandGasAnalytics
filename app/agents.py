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
    agent_logs: List[Dict[str, Any]] = Field(default_factory=list)
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

# Canonical sequential execution order after collaboration + critique.
SEQUENTIAL_EXECUTION_ORDER = [
    "seismic_analyzer",
    "well_log_interpreter",
    "reservoir_characterizer",
    "exploration_risk_assessor",
]

UPSTREAM_DEPENDENCIES = {
    "seismic_analyzer": [],
    "well_log_interpreter": [],
    "reservoir_characterizer": ["seismic_analyzer", "well_log_interpreter"],
    "exploration_risk_assessor": [
        "seismic_analyzer",
        "well_log_interpreter",
        "reservoir_characterizer",
    ],
    "report_generator": [
        "seismic_analyzer",
        "well_log_interpreter",
        "reservoir_characterizer",
        "exploration_risk_assessor",
    ],
}


def _is_real_api_key(api_key: str) -> bool:
    """Return True when the configured API key looks intentional."""

    return bool(api_key and api_key.strip() and api_key.strip().upper() not in {"NA", "N/A", "NONE", "CHANGEME"})


def _json_default(value: Any) -> str:
    """JSON fallback for objects returned by third-party libraries."""

    return str(value)


def _utc_timestamp_z() -> str:
    """Return an ISO-8601 UTC timestamp with Z suffix."""

    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


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


def _create_llm(temperature: float = 0.2, model: Optional[str] = None) -> Optional[Any]:
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
        "model": model or config.OPENAI_PRIMARY_MODEL,
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

    llm = _create_llm(temperature=temperature, model=get_config().OPENAI_PRIMARY_MODEL)
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
        self.reasoning_llm = _create_llm(
            temperature=0.15,
            model=self.config.OPENAI_REASONING_MODEL,
        )

    def _log(
        self,
        state: AgentState,
        agent: str,
        action: str,
        details: Dict[str, Any],
    ) -> None:
        """Append both legacy and normalized collaboration logs."""

        status = details.get("status", "success")
        confidence = details.get("confidence")
        if not isinstance(confidence, (int, float)):
            confidence = 0.79 if status == "success" else 0.39

        target_agent = details.get("target_agent")
        if not target_agent:
            delegated = details.get("agents")
            if isinstance(delegated, list) and delegated:
                target_agent = delegated[0]
            elif agent == "planner":
                target_agent = "research_agent"
            elif agent == "evaluator":
                retry_agents = details.get("retry_agents", [])
                target_agent = retry_agents[0] if retry_agents else "planner"
            elif agent in {"seismic_analyzer", "well_log_interpreter"}:
                target_agent = "reservoir_characterizer"
            elif agent == "reservoir_characterizer":
                target_agent = "exploration_risk_assessor"
            elif agent == "exploration_risk_assessor":
                target_agent = "report_generator"
            else:
                target_agent = ""

        input_summary = details.get("input_summary")
        if not input_summary:
            input_keys = details.get("input_keys", [])
            if input_keys:
                input_summary = f"Input keys: {', '.join(input_keys[:6])}"
            else:
                input_summary = f"Executed {action} in collaboration workflow"

        output_summary = details.get("output_summary")
        if not output_summary:
            tools = details.get("tools", [])
            if tools:
                output_summary = f"Executed tools: {', '.join(tools)}"
            else:
                output_summary = f"Completed action: {action}"

        normalized_entry = {
            "timestamp": _utc_timestamp_z(),
            "agent_name": AGENT_CONFIGS.get(agent, {}).get("name", agent),
            "action": action,
            "input_summary": str(input_summary),
            "output_summary": str(output_summary),
            "target_agent": str(target_agent),
            "confidence": round(float(confidence), 2),
            "retry_count": max(0, state.iteration - 1),
            "status": str(status),
        }
        state.agent_logs.append(normalized_entry)

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

        latest_evaluation = state.shared_memory.get("latest_evaluation", {})
        retry_agents = latest_evaluation.get("retry_agents", [])
        if retry_agents:
            # Put weak agents first on retry cycles so evaluator feedback has teeth.
            selected = retry_agents + selected

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
            {
                "agents": delegated,
                "llm_plan": llm_plan,
                "input_summary": f"Planner reviewed keys: {', '.join(sorted(user_input.keys())[:8])}",
                "output_summary": f"Delegated agents: {', '.join(delegated)}",
                "target_agent": delegated[0] if delegated else "",
                "status": "success",
            },
        )
        return delegated

    def _summarize_tool_health(self, tool_results: Dict[str, Any]) -> Dict[str, Any]:
        """Build compact tool-health summary for collaboration handoffs."""

        failed_tools = []
        for tool_name, output in tool_results.items():
            if isinstance(output, dict) and output.get("error"):
                failed_tools.append(tool_name)
        return {
            "tools_run": list(tool_results.keys()),
            "failed_tools": failed_tools,
            "healthy": not failed_tools and bool(tool_results),
        }

    def _order_agents_sequential(self, agent_names: List[str]) -> List[str]:
        """Return agents in canonical subsurface workflow order."""

        order_index = {name: index for index, name in enumerate(SEQUENTIAL_EXECUTION_ORDER)}
        return sorted(agent_names, key=lambda name: order_index.get(name, 999))

    def _next_agent_in_chain(self, agent_name: str, delegated_agents: List[str]) -> str:
        """Resolve the next specialist in the sequential chain."""

        ordered = self._order_agents_sequential(delegated_agents)
        if agent_name not in ordered:
            return "report_generator"
        position = ordered.index(agent_name)
        if position + 1 < len(ordered):
            return ordered[position + 1]
        return "report_generator"

    def _build_collaboration_packet(self, state: AgentState, agent_name: str) -> Dict[str, Any]:
        """Create focused cross-agent context instead of passing raw state only."""

        upstream_agents = UPSTREAM_DEPENDENCIES.get(agent_name, [])
        upstream_notes: List[Dict[str, Any]] = []
        for upstream in upstream_agents:
            upstream_result = state.analysis_results.get(upstream, {})
            if not upstream_result:
                continue
            tool_results = upstream_result.get("tool_results", {})
            upstream_notes.append(
                {
                    "agent": upstream,
                    "status": upstream_result.get("status", "unknown"),
                    "tool_health": self._summarize_tool_health(tool_results),
                    "llm_mode": upstream_result.get("result", {}).get("mode")
                    if isinstance(upstream_result.get("result"), dict)
                    else "llm",
                }
            )

        latest_evaluation = state.shared_memory.get("latest_evaluation", {})
        return {
            "target_agent": agent_name,
            "upstream_required": upstream_agents,
            "upstream_notes": upstream_notes,
            "latest_critique": {
                "missing_evidence": latest_evaluation.get("missing_evidence", []),
                "weak_outputs": latest_evaluation.get("weak_outputs", []),
                "cross_agent_contradictions": latest_evaluation.get(
                    "cross_agent_contradictions", []
                ),
            },
            "user_goal": state.shared_memory.get("workflow_goal", ""),
            "collaboration_briefs": state.shared_memory.get("collaboration_briefs", {}),
            "pre_execution_critique": state.shared_memory.get("pre_execution_critique", {}),
        }

    def _run_collaboration_phase(
        self, state: AgentState, delegated_agents: List[str]
    ) -> Dict[str, Any]:
        """Collaboration round: each agent states needs and handoffs before execution."""

        ordered_agents = self._order_agents_sequential(delegated_agents)
        briefs: Dict[str, Any] = {}
        prior_summaries: List[str] = []

        for agent_name in ordered_agents:
            role_key = agent_name if agent_name in AGENT_INSTRUCTIONS else "planner"
            target_agent = self._next_agent_in_chain(agent_name, delegated_agents)
            collaboration_payload = {
                "phase": "pre_execution_collaboration",
                "agent": agent_name,
                "planned_upstream": UPSTREAM_DEPENDENCIES.get(agent_name, []),
                "available_evidence": sorted(state.user_input.keys()),
                "data_sources": state.user_input.get("data_sources", []),
                "prior_agent_briefs": prior_summaries,
                "pre_execution_critique": state.shared_memory.get("pre_execution_critique", {}),
            }
            brief = self._invoke_reasoning_llm(
                role_key,
                (
                    "Collaboration only (no fabricated tool outputs). State: "
                    "1) evidence you require, 2) deliverables for downstream agents, "
                    "3) risks/uncertainties to flag before execution."
                ),
                collaboration_payload,
            )
            briefs[agent_name] = brief
            brief_text = (
                brief.get("content", "")
                if isinstance(brief, dict) and brief.get("mode") == "llm"
                else json.dumps(brief, default=_json_default)
            )
            prior_summaries.append(f"{AGENT_CONFIGS[agent_name]['name']}: {brief_text}")
            self._log(
                state,
                agent_name,
                "collaboration_brief",
                {
                    "status": "success",
                    "target_agent": target_agent,
                    "input_summary": (
                        f"Reviewed evidence keys: {', '.join(sorted(state.user_input.keys())[:8])}"
                    ),
                    "output_summary": (
                        "Published collaboration brief for sequential execution chain"
                    ),
                    "brief": brief,
                },
            )

        state.shared_memory["collaboration_briefs"] = briefs
        return {"agent_briefs": briefs, "execution_order": ordered_agents}

    def _assess_evidence_gaps(
        self, state: AgentState, delegated_agents: List[str]
    ) -> Dict[str, List[str]]:
        """Deterministic evidence gap checks used in critique phases."""

        missing: List[str] = []
        if "seismic_analyzer" in delegated_agents and not state.user_input.get("seismic_data"):
            missing.append("seismic_data")
        if "well_log_interpreter" in delegated_agents and not state.user_input.get("well_log_data"):
            missing.append("well_log_data")
        return {"missing_evidence": missing}

    def _run_pre_execution_critique(
        self, state: AgentState, delegated_agents: List[str]
    ) -> Dict[str, Any]:
        """Critique collaboration plan and evidence readiness before any specialist runs."""

        gaps = self._assess_evidence_gaps(state, delegated_agents)
        missing = gaps["missing_evidence"]
        collaboration_briefs = state.shared_memory.get("collaboration_briefs", {})

        llm_critique = self._invoke_reasoning_llm(
            "evaluator",
            (
                "Pre-execution critique only. Review collaboration briefs and evidence. "
                "Return approve_to_execute or request_revision with concrete gaps."
            ),
            {
                "phase": "pre_execution",
                "delegated_agents": delegated_agents,
                "execution_order": self._order_agents_sequential(delegated_agents),
                "missing_evidence": missing,
                "collaboration_briefs": collaboration_briefs,
                "data_sources": state.user_input.get("data_sources", []),
            },
        )

        ready_to_execute = not missing
        critique = {
            "phase": "pre_execution",
            "ready_to_execute": ready_to_execute,
            "missing_evidence": missing,
            "collaboration_reviewed": list(collaboration_briefs.keys()),
            "execution_order": self._order_agents_sequential(delegated_agents),
            "llm_critique": llm_critique,
            "critique_summary": {
                "status": "approved_for_execution" if ready_to_execute else "needs_revision",
                "total_gaps": len(missing),
            },
        }
        state.shared_memory["pre_execution_critique"] = critique
        self._log(
            state,
            "evaluator",
            "pre_execution_critique",
            {
                **critique,
                "status": "success" if ready_to_execute else "needs_revision",
                "target_agent": delegated_agents[0] if delegated_agents else "planner",
                "input_summary": "Reviewed collaboration briefs and available evidence",
                "output_summary": (
                    "Approved sequential execution"
                    if ready_to_execute
                    else f"Blocked pending evidence: {', '.join(missing)}"
                ),
                "confidence": 0.85 if ready_to_execute else 0.45,
            },
        )
        return critique

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
                "input_summary": "Enriched user input with local/reference datasets",
                "output_summary": f"Added keys: {', '.join([key for key in after if key not in before]) or 'none'}",
                "target_agent": "planner",
                "status": "success",
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

    def _build_agent_context(self, state: AgentState) -> Dict[str, Any]:
        """Build a shared context payload for specialist agents."""

        return {
            **state.user_input,
            "shared_memory": state.shared_memory,
            "prior_findings": state.analysis_results,
            "seismic_interpretation": state.analysis_results.get("seismic_analyzer", {}),
            "petrophysics": state.analysis_results.get("well_log_interpreter", {}),
            "reservoir_properties": state.analysis_results.get("reservoir_characterizer", {}),
            "evidence_register": state.evidence_register,
        }

    def _execute_agents_sequential(
        self, state: AgentState, agent_names: List[str]
    ) -> Dict[str, Dict[str, Any]]:
        """Execute specialists one-by-one in subsurface dependency order."""

        ordered_results: Dict[str, Dict[str, Any]] = {}
        for agent_name in self._order_agents_sequential(agent_names):
            task = AGENT_CONFIGS[agent_name]["description"]
            context = self._build_agent_context(state)
            context["collaboration_packet"] = self._build_collaboration_packet(
                state, agent_name
            )
            context["execution_mode"] = "sequential"
            result = self.execute_agent(agent_name, task, context)
            ordered_results[agent_name] = result
            state.analysis_results[agent_name] = result
            state.completed_agents.append(agent_name)
            state.shared_memory["handoff_notes"][agent_name] = {
                "iteration": state.iteration,
                "tool_health": self._summarize_tool_health(result.get("tool_results", {})),
                "status": result.get("status"),
            }
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
                    "input_summary": (
                        f"Sequential execution step for {agent_name} "
                        f"(after collaboration and pre-execution critique)"
                    ),
                    "output_summary": (
                        f"Produced {len(result.get('tool_results', {}))} tool outputs; "
                        f"handoff to {self._next_agent_in_chain(agent_name, agent_names)}"
                    ),
                    "target_agent": self._next_agent_in_chain(agent_name, agent_names),
                    "confidence": 0.82 if result.get("status") == "success" else 0.4,
                },
            )
        return ordered_results

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
        missing = self._assess_evidence_gaps(state, delegated_agents)["missing_evidence"]
        weak: List[str] = []

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
            elif not tool_results:
                weak.append(f"{agent_name}: no tool outputs were produced")

        contradictions: List[str] = []
        risk_tool_results = (
            findings.get("exploration_risk_assessor", {})
            .get("tool_results", {})
        )
        trap_score = risk_tool_results.get("evaluate_trap", {}).get("trap_score")
        permeability = (
            findings.get("reservoir_characterizer", {})
            .get("tool_results", {})
            .get("estimate_permeability", {})
            .get("estimated_permeability_md")
        )
        if (
            isinstance(trap_score, (int, float))
            and isinstance(permeability, (int, float))
            and trap_score < 0.35
            and permeability > 100
        ):
            contradictions.append(
                "High permeability with poor trap quality: validate seal and trap mapping before recommendation."
            )

        approved = not missing and not weak
        llm_critique = self._invoke_reasoning_llm(
            "evaluator",
            "Post-execution critique. State approve/request_revision and evidence gaps.",
            {
                "phase": "post_execution",
                "delegated_agents": delegated_agents,
                "missing": missing,
                "weak": weak,
                "contradictions": contradictions,
                "findings": findings,
                "collaboration_briefs": state.shared_memory.get("collaboration_briefs", {}),
                "pre_execution_critique": state.shared_memory.get("pre_execution_critique", {}),
            },
        )
        evaluation = {
            "phase": "post_execution",
            "approved": approved,
            "missing_evidence": missing,
            "weak_outputs": weak,
            "cross_agent_contradictions": contradictions,
            "llm_critique": llm_critique,
            "critique_summary": {
                "status": "needs_revision" if (missing or weak or contradictions) else "approved",
                "total_gaps": len(missing) + len(weak) + len(contradictions),
            },
            "retry_agents": [],
        }

        retry_agents = []
        for weakness in weak:
            retry_agents.append(weakness.split(":", 1)[0].strip())
        if missing:
            if "seismic_data" in missing:
                retry_agents.append("seismic_analyzer")
            if "well_log_data" in missing:
                retry_agents.append("well_log_interpreter")
        if contradictions:
            retry_agents.extend(["reservoir_characterizer", "exploration_risk_assessor"])
        evaluation["retry_agents"] = list(dict.fromkeys(retry_agents))

        self._log(
            state,
            "evaluator",
            "post_execution_critique",
            {
                **evaluation,
                "status": "success" if approved else "needs_revision",
                "target_agent": "planner",
                "input_summary": "Reviewed sequential execution outputs and tool evidence",
                "output_summary": evaluation["critique_summary"]["status"],
                "confidence": 0.88 if approved else 0.5,
            },
        )
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
            {
                "status": report.get("status"),
                "llm_mode": final_llm.get("mode"),
                "input_summary": "Compiled approved findings and evaluator critique",
                "output_summary": "Generated final synthesis and report payload",
                "target_agent": "api_response",
            },
        )
        return report

    def execute_collaborative_workflow(
        self, user_input: Dict[str, Any], quick: bool = False, max_review_cycles: int = 2
    ) -> Dict[str, Any]:
        """Run collaborate -> critique -> sequential execution -> post-critique -> report."""

        state = AgentState(
            user_input=dict(user_input),
            shared_memory={
                "workflow_goal": "Evidence-grounded oil and gas prospect analysis",
                "llm_configured": self.reasoning_llm is not None,
                "execution_mode": "sequential",
                "handoff_notes": {},
                "collaboration_briefs": {},
                "pre_execution_critique": {},
                "latest_evaluation": {},
                "evaluation_history": [],
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

            # Phase 1: collaboration (no tools)
            collaboration = self._run_collaboration_phase(state, delegated_agents)

            # Phase 2: pre-execution critique
            pre_critique = self._run_pre_execution_critique(state, delegated_agents)
            if not pre_critique.get("ready_to_execute"):
                self._log(
                    state,
                    "planner",
                    "revision_requested",
                    {
                        "phase": "pre_execution",
                        "missing_evidence": pre_critique.get("missing_evidence", []),
                        "next_action": "research_agent_reload_then_retry",
                    },
                )
                self._research_missing_context(state)
                delegated_agents = self._planner_delegate(state, quick=quick)
                collaboration = self._run_collaboration_phase(state, delegated_agents)
                pre_critique = self._run_pre_execution_critique(state, delegated_agents)

            # Phase 3: sequential specialist execution (tools + optional LLM)
            self._execute_agents_sequential(state, delegated_agents)

            evaluation = self._evaluate_iteration(state, delegated_agents)
            state.shared_memory["latest_evaluation"] = evaluation
            state.shared_memory["evaluation_history"].append(evaluation)
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
            "execution_mode": "sequential",
            "workflow_phases": [
                "research",
                "planner_delegation",
                "collaboration",
                "pre_execution_critique",
                "sequential_execution",
                "post_execution_critique",
                "report",
            ],
            "collaboration": state.shared_memory.get("collaboration_briefs", {}),
            "pre_execution_critique": state.shared_memory.get("pre_execution_critique", {}),
            "planner_delegation": delegated_agents,
            "sequential_execution_order": self._order_agents_sequential(delegated_agents),
            "shared_memory": state.shared_memory,
            "evidence_register": state.evidence_register,
            "collaboration_log": state.collaboration_log,
            "agent_logs": state.agent_logs,
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
