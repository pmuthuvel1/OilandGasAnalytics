"""LangChain agents for Oil & Gas Analytics."""

import asyncio
import json
import logging
from datetime import datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field

# Model name prefixes whose chat-completions endpoint rejects ``temperature``
# (and similar sampling) parameters. Core42 / Azure / OpenAI all enforce this
# for the "reasoning" family of models.
_REASONING_MODEL_PREFIXES = ("o1", "o3", "o4", "gpt-5")


def _is_reasoning_model(model_name: Optional[str]) -> bool:
    if not model_name:
        return False
    name = model_name.lower()
    return any(name.startswith(prefix) for prefix in _REASONING_MODEL_PREFIXES)

from .config import AGENT_CONFIGS, DEFAULT_OPENAI_BASE_URL, get_config
from .data_sources import SEG_OPEN_DATA_SOURCES, enrich_with_reference_data
from .tools import TOOLS
from . import memory as persistent_memory
from . import observability as obs
from . import rag
from .logging_utils import new_trace_file, write_trace


def _summarize(value: Any, limit: int = 400) -> str:
    """Render any value as a short, safe single-line string for trace logs."""
    try:
        if isinstance(value, str):
            text = value
        else:
            text = json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        text = str(value)
    text = " ".join(text.split())
    return text if len(text) <= limit else text[: limit - 1] + "…"

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


def _json_default(value: Any) -> str:
    """JSON fallback for objects returned by third-party libraries."""

    return str(value)


def _truncate_payload(payload: Any, max_chars: int) -> str:
    """Serialize and truncate a payload so prompts stay within token bounds."""

    serialized = json.dumps(payload, default=_json_default)
    if len(serialized) <= max_chars:
        return serialized
    return serialized[:max_chars] + f"... [truncated {len(serialized) - max_chars} chars]"


def _extract_http_error_body(exc: Optional[BaseException]) -> str:
    """Best-effort extraction of an OpenAI/HTTP error response body."""

    if exc is None:
        return ""
    # openai>=1 exposes ``response`` (httpx.Response) and ``body`` on errors.
    body = getattr(exc, "body", None)
    if body:
        try:
            return json.dumps(body, default=_json_default)[:2000]
        except Exception:  # noqa: BLE001
            return str(body)[:2000]
    response = getattr(exc, "response", None)
    if response is not None:
        try:
            text = response.text  # httpx.Response
        except Exception:  # noqa: BLE001
            text = ""
        if text:
            return text[:2000]
    return ""


def _looks_like_retryable_bad_request(exc: BaseException) -> bool:
    """Return True for 400-class errors that may succeed with a smaller payload."""

    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if status != 400:
        return False
    text = (_extract_http_error_body(exc) or str(exc)).lower()
    keywords = (
        "context", "token", "length", "too long", "maximum", "size", "truncat",
    )
    return any(keyword in text for keyword in keywords)


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



@lru_cache(maxsize=8)
def _create_llm(temperature: float = 0.2, model: Optional[str] = None) -> Optional[Any]:
    """Create (and cache) the chat model when an API key is configured.

    OPENAI_API_KEY and OPENAI_BASE_URL are sourced exclusively from the
    process environment via :func:`get_config`. The instance is cached so all
    agents share a single underlying HTTP client per (temperature, model) pair.
    When ``model`` is ``None`` we fall back to ``COMPASS_CHAT_MODEL`` (which
    itself defaults to ``OPENAI_MODEL``).
    """

    config = get_config()
    if not config.llm_enabled:
        if config.SAMPLE_MODE:
            logger.info(
                "SAMPLE_MODE is enabled; skipping LLM initialization and using "
                "deterministic tool results only."
            )
        else:
            logger.warning(
                "OPENAI_API_KEY is not configured; agents will use deterministic tool results only."
            )
        return None

    try:
        from langchain_openai import ChatOpenAI
    except ImportError:
        logger.warning(
            "langchain-openai is not installed; agents will use deterministic tool results only."
        )
        return None

    chosen_model = model or config.COMPASS_CHAT_MODEL or config.OPENAI_MODEL
    llm_params: Dict[str, Any] = {
        "api_key": config.OPENAI_API_KEY,
        "model": chosen_model,
        "timeout": config.OPENAI_REQUEST_TIMEOUT,
        "max_retries": config.OPENAI_MAX_RETRIES,
    }
    # Reasoning-family models (o1/o3/o4/gpt-5) reject ``temperature`` on the
    # chat-completions endpoint and respond with HTTP 400. Only send the
    # sampling parameter for classic chat models.
    if not _is_reasoning_model(chosen_model):
        llm_params["temperature"] = temperature
    if config.OPENAI_BASE_URL:
        llm_params["base_url"] = config.OPENAI_BASE_URL

    logger.info(
        "Initialized LLM model=%s base_url=%s (source=%s) api_key_source=%s timeout=%ss",
        chosen_model,
        config.OPENAI_BASE_URL,
        config.OPENAI_BASE_URL_SOURCE,
        config.OPENAI_API_KEY_SOURCE,
        config.OPENAI_REQUEST_TIMEOUT,
    )
    return ChatOpenAI(**llm_params)


@lru_cache(maxsize=4)
def _create_raw_openai_client(model: Optional[str] = None):
    """Return ``(client, model_name)`` for a minimal OpenAI-compatible call.

    Mirrors the documented Core42 sample::

        client = OpenAI(api_key=..., base_url="https://api.core42.ai/v1")
        client.chat.completions.create(model="gpt-4.1", messages=[...])

    We deliberately avoid LangChain here so the request body contains *only*
    ``model`` and ``messages`` — Core42's gpt-5.1 deployment returns a
    misleading "no quota or access" 400 when extra fields are present.
    """

    config = get_config()
    if not config.llm_enabled:
        return None, None
    try:
        from openai import OpenAI
    except ImportError:
        logger.warning("openai package not installed; raw client unavailable.")
        return None, None

    kwargs: Dict[str, Any] = {
        "api_key": config.OPENAI_API_KEY,
        "timeout": config.OPENAI_REQUEST_TIMEOUT,
        "max_retries": config.OPENAI_MAX_RETRIES,
    }
    if config.OPENAI_BASE_URL:
        kwargs["base_url"] = config.OPENAI_BASE_URL
    client = OpenAI(**kwargs)
    chosen = model or config.COMPASS_REASONING_MODEL or config.OPENAI_MODEL
    logger.info(
        "Initialized raw OpenAI client model=%s base_url=%s (source=%s) api_key_source=%s",
        chosen,
        config.OPENAI_BASE_URL,
        config.OPENAI_BASE_URL_SOURCE,
        config.OPENAI_API_KEY_SOURCE,
    )
    return client, chosen


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

    config = get_config()
    llm = _create_llm(temperature=temperature, model=config.COMPASS_CHAT_MODEL)
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
            temperature=0.15, model=self.config.COMPASS_REASONING_MODEL
        )
        # Raw OpenAI client used for direct reasoning calls. LangChain's
        # ChatOpenAI sends additional fields (penalties, stream_options, etc.)
        # that some Core42 / Azure model deployments reject with a generic
        # HTTP 400 ("You may not have a quota or access to use this model").
        # The raw client mirrors the documented working Core42 sample and
        # sends only ``model`` + ``messages``.
        self.reasoning_client, self.reasoning_model = _create_raw_openai_client(
            self.config.COMPASS_REASONING_MODEL
        )
        # --- Escalation state: switch to deterministic sample mode after
        # repeated live-API failures so downstream agents keep producing
        # answers instead of cascading errors.
        self._llm_failure_streak: int = 0
        self._llm_escalated: bool = False
        self._llm_failure_threshold: int = 3

        # Per-run trace logging state. A new trace file + id is created at the
        # start of each collaborative workflow; standalone agent calls lazily
        # create one on first use so they are still observable.
        self.trace_file: Optional[str] = None
        self.trace_id: Optional[str] = None

    def _ensure_trace(self) -> None:
        """Lazily create a trace file/id if one has not been initialized."""
        if not self.trace_file or not self.trace_id:
            self.trace_file, self.trace_id = new_trace_file()

    def _trace(
        self,
        agent_name: str,
        action: str,
        input_summary: Any = "",
        output_summary: Any = "",
        target_agent: Optional[str] = None,
        confidence: Optional[float] = None,
        retry_count: int = 0,
        status: str = "success",
        extra: Optional[Dict[str, Any]] = None,
        span_id: Optional[str] = None,
    ) -> None:
        """Emit a single agent trace record to the per-run JSONL trace file.

        A fresh ``span_id`` is auto-generated for each record by
        :func:`app.logging_utils.write_trace` unless one is supplied here.
        """
        self._ensure_trace()
        try:
            write_trace(
                self.trace_file,
                agent_name=agent_name,
                action=action,
                input_summary=_summarize(input_summary),
                output_summary=_summarize(output_summary, limit=700),
                trace_id=self.trace_id,
                span_id=span_id,
                target_agent=target_agent,
                confidence=confidence,
                retry_count=retry_count,
                status=status,
                extra=extra or {},
            )
        except Exception:  # noqa: BLE001 - never break the pipeline on logging
            logger.debug("Failed to write trace record", exc_info=True)

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

        if self.reasoning_client is None or self._llm_escalated:
            reason = (
                "Escalated to deterministic sample mode after repeated "
                "LLM failures."
                if self._llm_escalated
                else "OPENAI_API_KEY is not configured or openai package is unavailable."
            )
            self._trace(
                agent_name=role,
                action="llm_call_skipped",
                input_summary=prompt,
                output_summary=reason,
                status="skipped",
                extra={"escalated": self._llm_escalated},
            )
            return {
                "mode": "llm_skipped",
                "reason": reason,
                "escalated": self._llm_escalated,
            }

        system_text = (
            AGENT_INSTRUCTIONS.get(role) or AGENT_INSTRUCTIONS["report_generator"]
        ).strip() or "You are a helpful assistant."
        safe_prompt = (prompt or "Summarize the provided context.").strip()

        # Some providers (Core42 / Azure) return HTTP 400 when the request body
        # is too large for the deployed context window. Retry once with an
        # aggressively shrunk payload before giving up.
        budgets = [
            self.config.MAX_CONTEXT_CHARS,
            max(2_000, self.config.MAX_CONTEXT_CHARS // 4),
        ]
        last_error: Optional[BaseException] = None
        for attempt, budget in enumerate(budgets, start=1):
            payload_text = _truncate_payload(payload or {}, budget) or "{}"
            messages = [
                {"role": "system", "content": system_text},
                {
                    "role": "user",
                    "content": f"{safe_prompt}\n\nShared context JSON:\n{payload_text}",
                },
            ]
            try:
                # IMPORTANT: send only model + messages. Extra fields cause
                # Core42's gpt-5.1 endpoint to respond with HTTP 400
                # ("no quota or access"), even when access is granted.
                logger.info(
                    "Calling LLM role=%s model=%r base_url=%s system_chars=%d user_chars=%d",
                    role,
                    self.reasoning_model,
                    getattr(self.reasoning_client, "base_url", "?"),
                    len(messages[0]["content"]),
                    len(messages[1]["content"]),
                )
                response = self.reasoning_client.chat.completions.create(
                    model=self.reasoning_model,
                    messages=messages,
                )
                content = response.choices[0].message.content if response.choices else ""
                self._llm_failure_streak = 0
                self._trace(
                    agent_name=role,
                    action="llm_call",
                    input_summary=prompt,
                    output_summary=content or "",
                    retry_count=attempt - 1,
                    status="success",
                    extra={"model": self.reasoning_model, "budget_chars": budget},
                )
                return {"mode": "llm", "content": content or ""}
            except Exception as exc:  # noqa: BLE001 - want to inspect provider error
                last_error = exc
                body = _extract_http_error_body(exc)
                logger.warning(
                    "LLM call failed for %s (attempt %d/%d, budget=%d chars): %s%s",
                    role,
                    attempt,
                    len(budgets),
                    budget,
                    exc,
                    f" | response: {body}" if body else "",
                )
                self._trace(
                    agent_name=role,
                    action="llm_call_failed",
                    input_summary=prompt,
                    output_summary=f"{exc} | {body or ''}",
                    retry_count=attempt - 1,
                    status="retry" if attempt < len(budgets) else "error",
                    extra={"model": self.reasoning_model, "budget_chars": budget},
                )
                # Only retry on 4xx that look like payload/size issues.
                if not _looks_like_retryable_bad_request(exc):
                    break

        logger.error(
            "LLM call permanently failed for %s: %s", role, last_error
        )
        self._trace(
            agent_name=role,
            action="llm_call_permanently_failed",
            input_summary=prompt,
            output_summary=str(last_error) if last_error else "unknown error",
            status="error",
        )
        return {
            "mode": "llm_error",
            "error": str(last_error) if last_error else "unknown error",
            "provider_response": _extract_http_error_body(last_error),
        }

    def _planner_delegate(self, state: AgentState, quick: bool = False) -> List[str]:
        """Dynamic delegation: branch on available evidence, RAG coverage, risk."""

        user_input = state.user_input
        shared = state.shared_memory
        prior_eval = shared.get("last_evaluation") or {}
        needs = shared.setdefault("needs", [])
        selected: List[str] = []

        if user_input.get("seismic_data"):
            selected.append("seismic_analyzer")
        elif "seismic_data" not in needs:
            needs.append("seismic_data")

        if user_input.get("well_log_data"):
            selected.append("well_log_interpreter")
        elif "well_log_data" not in needs:
            needs.append("well_log_data")

        if user_input.get("well_log_data") or state.analysis_results.get("well_log_interpreter"):
            selected.append("reservoir_characterizer")

        force_risk = bool(
            prior_eval.get("weak_outputs")
            or prior_eval.get("risk_level") == "HIGH"
            or (prior_eval.get("quality_score", 1.0) < 0.6)
        )
        selected.append("exploration_risk_assessor")
        if quick and not force_risk:
            selected = [a for a in selected if a != "seismic_analyzer"]

        delegated = list(dict.fromkeys(selected))

        # Dynamic retrieval delegation: ask the retriever for MORE context only
        # when current RAG coverage is weak or empty.
        coverage = (shared.get("rag_retrieval") or {}).get("coverage", "empty")
        if coverage in {"weak", "empty"}:
            self._log(
                state,
                "planner",
                "requested_retrieval",
                {"reason": f"rag_coverage={coverage}", "iteration": state.iteration},
            )
            self._broaden_retrieval(state)

        llm_plan = self._invoke_reasoning_llm(
            "planner",
            "Create a concise execution plan. Return useful critique, not hidden reasoning.",
            {
                "quick": quick,
                "available_keys": sorted(user_input.keys()),
                "delegated_agents": delegated,
                "data_sources": user_input.get("data_sources", []),
                "rag_coverage": coverage,
                "force_risk": force_risk,
                "needs": needs,
            },
        )
        self._log(
            state,
            "planner",
            "delegated",
            {
                "agents": delegated,
                "branch_reason": {
                    "force_risk": force_risk,
                    "rag_coverage": coverage,
                    "missing": list(needs),
                },
                "llm_plan_mode": llm_plan.get("mode"),
            },
        )
        self._trace(
            agent_name="PlannerAgent",
            action="delegate",
            input_summary={
                "available_keys": sorted(user_input.keys()),
                "quick": quick,
                "iteration": state.iteration,
            },
            output_summary={
                "delegated": delegated,
                "needs": list(needs),
                "rag_coverage": coverage,
                "force_risk": force_risk,
            },
            target_agent=",".join(delegated) if delegated else None,
            extra={"llm_plan_mode": llm_plan.get("mode")},
        )
        return delegated

    def _broaden_retrieval(self, state: AgentState) -> None:
        """Retriever retry: broaden the query when RAG coverage is weak/empty."""
        query_parts = [
            str(state.user_input.get("well_name") or ""),
            str(state.user_input.get("user_notes") or ""),
            " ".join(state.shared_memory.get("needs", []) or []),
        ]
        query = " ".join(p for p in query_parts if p).strip() or "oil gas reservoir"
        try:
            outcome = rag.retrieve_with_retry(query, k=6)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Broadened retrieval failed: %s", exc)
            outcome = {"hits": [], "attempts": [], "coverage": "empty", "final_query": query}
        state.shared_memory["rag_retrieval"] = {
            "coverage": outcome["coverage"],
            "attempts": outcome["attempts"],
            "final_query": outcome["final_query"],
        }
        if outcome["hits"]:
            state.shared_memory["rag_context"] = outcome["hits"]
            state.evidence_register.extend(
                [
                    {"source": h["source"], "score": h["score"], "chunk_id": h["chunk_id"]}
                    for h in outcome["hits"]
                ]
            )
        self._log(
            state,
            "retriever_agent",
            "broadened_retry",
            {
                "coverage": outcome["coverage"],
                "attempts": len(outcome["attempts"]),
                "hits": len(outcome["hits"]),
            },
        )
        self._trace(
            agent_name="RetrieverAgent",
            action="broaden_retry",
            input_summary={"query": query},
            output_summary={
                "coverage": outcome["coverage"],
                "hits": len(outcome["hits"]),
                "final_query": outcome.get("final_query"),
            },
            retry_count=max(0, len(outcome["attempts"]) - 1),
            status="success" if outcome["hits"] else "empty",
        )

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
        self._trace(
            agent_name="ResearchAgent",
            action="load_context",
            input_summary={"before_keys": before},
            output_summary={
                "keys_added": [key for key in after if key not in before],
                "local_sources_count": len(data_sources),
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
            # The per-agent LangChain function-calling executor is unavailable
            # (newer langchain versions removed ``create_openai_functions_agent``).
            # Fall back to the raw OpenAI client when an API key is configured
            # so we still produce a real LLM synthesis instead of just dumping
            # tool results.
            if self.reasoning_client is not None:
                synthesis = self._invoke_reasoning_llm(
                    agent_name,
                    task_description,
                    {"context": context, "tool_results": tool_results},
                )
                return {
                    "status": "success",
                    **base_result,
                    "result": {
                        "mode": synthesis.get("mode", "llm"),
                        "summary": synthesis.get("content")
                        or synthesis.get("reason")
                        or "",
                        "llm_error": synthesis.get("error"),
                        "provider_response": synthesis.get("provider_response"),
                        "tool_results": tool_results,
                    },
                }
            return {
                "status": "success",
                **base_result,
                "result": {
                    "mode": "tool_only",
                    "summary": (
                        "LLM synthesis skipped: OPENAI_API_KEY is not configured "
                        "(or SAMPLE_MODE is enabled, or the openai package is missing)."
                    ),
                    "tool_results": tool_results,
                },
            }

        try:
            ctx_text = _truncate_payload(context, self.config.MAX_CONTEXT_CHARS)
            tools_text = _truncate_payload(tool_results, self.config.MAX_CONTEXT_CHARS)
            input_text = (
                f"{task_description}\n\n"
                f"Context JSON:\n{ctx_text}\n\n"
                f"Precomputed tool results JSON:\n{tools_text}\n\n"
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
        """Critique outputs, score quality, derive risk, and gate the report writer."""

        findings = state.analysis_results
        missing: List[str] = []
        weak: List[str] = []
        tool_total = 0
        tool_errors = 0
        synth_total = 0
        synth_ok = 0

        if "seismic_analyzer" in delegated_agents and not state.user_input.get("seismic_data"):
            missing.append("seismic_data")
        if "well_log_interpreter" in delegated_agents and not state.user_input.get("well_log_data"):
            missing.append("well_log_data")

        for agent_name in delegated_agents:
            result = findings.get(agent_name, {})
            tool_results = result.get("tool_results", {})
            tool_total += len(tool_results)
            errors = [
                tname for tname, tr in tool_results.items()
                if isinstance(tr, dict) and tr.get("error")
            ]
            tool_errors += len(errors)
            if errors:
                weak.append(f"{agent_name}: tool errors in {', '.join(errors)}")
            res = result.get("result")
            if isinstance(res, dict):
                synth_total += 1
                mode = res.get("mode", "")
                if mode == "llm" and (res.get("summary") or res.get("content")):
                    synth_ok += 1
                if mode in {"llm_error", "tool_only_after_llm_error"}:
                    weak.append(f"{agent_name}: llm synthesis failed")

        # Composite quality score (0..1) used by the gate.
        tool_score = 1.0 - (tool_errors / tool_total) if tool_total else 0.5
        synth_score = (synth_ok / synth_total) if synth_total else 0.5
        evidence_score = min(1.0, len(state.evidence_register) / 5.0)
        rag_cov = (state.shared_memory.get("rag_retrieval") or {}).get("coverage", "empty")
        rag_score = {"ok": 1.0, "weak": 0.5, "empty": 0.1}.get(rag_cov, 0.3)
        missing_penalty = 0.25 * len(missing)
        quality_score = max(
            0.0,
            round(
                0.4 * tool_score + 0.3 * synth_score + 0.15 * evidence_score
                + 0.15 * rag_score - missing_penalty,
                3,
            ),
        )

        # Risk level derived from the risk-assessor tool outputs.
        risk_block = (findings.get("exploration_risk_assessor", {}) or {}).get("tool_results", {})
        risk_level = "UNKNOWN"
        for tr in risk_block.values():
            if isinstance(tr, dict) and tr.get("risk_level"):
                risk_level = str(tr["risk_level"]).upper()
                break

        quality_threshold = float(state.user_input.get("quality_threshold", 0.6))
        approved = (not missing) and (not weak) and (quality_score >= quality_threshold)

        # Role authority: explicit gate the report writer must respect.
        report_gate = {
            "may_publish": approved,
            "threshold": quality_threshold,
            "blocking_reasons": (
                missing + weak
                + ([f"quality_score={quality_score}<{quality_threshold}"]
                   if quality_score < quality_threshold else [])
            ),
        }

        llm_critique = self._invoke_reasoning_llm(
            "evaluator",
            "Critique the iteration. State approve/request_revision and evidence gaps.",
            {
                "delegated_agents": delegated_agents,
                "missing": missing,
                "weak": weak,
                "quality_score": quality_score,
                "risk_level": risk_level,
                "rag_coverage": rag_cov,
            },
        )
        evaluation = {
            "approved": approved,
            "missing_evidence": missing,
            "weak_outputs": weak,
            "quality_score": quality_score,
            "quality_threshold": quality_threshold,
            "risk_level": risk_level,
            "report_gate": report_gate,
            "llm_critique": llm_critique,
        }
        state.shared_memory["last_evaluation"] = evaluation
        self._log(
            state,
            "evaluator",
            "evaluated",
            {k: v for k, v in evaluation.items() if k != "llm_critique"},
        )
        self._trace(
            agent_name="EvaluatorAgent",
            action="evaluate",
            input_summary={
                "delegated_agents": delegated_agents,
                "iteration": state.iteration,
            },
            output_summary={
                "approved": approved,
                "quality_score": quality_score,
                "risk_level": risk_level,
                "missing_evidence": missing,
                "weak_outputs": weak,
            },
            confidence=float(quality_score),
            target_agent="ReportGeneratorAgent",
            status="approved" if approved else "request_revision",
            extra={"report_gate": report_gate},
        )
        return evaluation

    def _finalize_report(self, state: AgentState, evaluation: Dict[str, Any]) -> Dict[str, Any]:
        """Produce the final report — honoring the evaluator's role authority."""

        gate = evaluation.get("report_gate", {}) or {}
        if not gate.get("may_publish", True):
            # Evaluator BLOCKS the report writer until quality is met.
            blocked = {
                "status": "blocked",
                "agent": "report_generator",
                "agent_name": AGENT_CONFIGS["report_generator"]["name"],
                "description": AGENT_CONFIGS["report_generator"]["description"],
                "tool_results": {},
                "timestamp": datetime.now().isoformat(),
                "result": {
                    "mode": "blocked_by_evaluator",
                    "summary": (
                        "Report writer was blocked by the evaluator because the "
                        "quality threshold was not met."
                    ),
                    "blocking_reasons": gate.get("blocking_reasons", []),
                    "quality_score": evaluation.get("quality_score"),
                    "quality_threshold": evaluation.get("quality_threshold"),
                },
            }
            self._log(
                state,
                "evaluator",
                "blocked_report_writer",
                {"reasons": gate.get("blocking_reasons", [])},
            )
            self._trace(
                agent_name="EvaluatorAgent",
                action="block_report_writer",
                input_summary={"quality_score": evaluation.get("quality_score")},
                output_summary={"blocking_reasons": gate.get("blocking_reasons", [])},
                target_agent="ReportGeneratorAgent",
                status="blocked",
            )
            return blocked

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
        self._trace(
            agent_name="ReportGeneratorAgent",
            action="produce_final_answer",
            input_summary={"agents": list(state.analysis_results.keys())},
            output_summary={
                "status": report.get("status"),
                "llm_mode": final_llm.get("mode"),
                "synthesis_preview": (final_llm.get("content") or "")[:300],
            },
            status=str(report.get("status", "success")),
        )
        return report

    # ------------------------------------------------------------------ #
    # RAG + persistent memory helpers
    # ------------------------------------------------------------------ #
    def _augment_with_rag_and_memory(self, state: AgentState) -> None:
        """Recall prior memory and inject RAG snippets into shared_memory."""
        prior = persistent_memory.recall(state.user_input)
        if prior:
            state.shared_memory["prior_memory"] = prior
            self._log(state, "memory_agent", "recalled", {"entries": len(prior)})
            self._trace(
                agent_name="MemoryAgent",
                action="recall",
                input_summary={"keys": sorted(state.user_input.keys())},
                output_summary={"entries": len(prior)},
            )

        query_parts = [
            str(state.user_input.get("well_name") or ""),
            str(state.user_input.get("user_notes") or ""),
            "reservoir seismic well log porosity permeability risk",
        ]
        query = " ".join(p for p in query_parts if p).strip()
        try:
            outcome = (
                rag.retrieve_with_retry(query, k=4)
                if query
                else {"hits": [], "attempts": [], "coverage": "empty", "final_query": ""}
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("RAG retrieval failed: %s", exc)
            outcome = {"hits": [], "attempts": [], "coverage": "empty", "final_query": query}
        hits = outcome["hits"]
        state.shared_memory["rag_retrieval"] = {
            "coverage": outcome["coverage"],
            "attempts": outcome["attempts"],
            "final_query": outcome["final_query"],
        }
        if hits:
            state.shared_memory["rag_context"] = hits
            state.evidence_register.extend(
                [{"source": h["source"], "score": h["score"], "chunk_id": h["chunk_id"]} for h in hits]
            )
            self._log(state, "rag_agent", "retrieved", {
                "hits": len(hits),
                "top_score": hits[0]["score"],
                "coverage": outcome["coverage"],
                "attempts": len(outcome["attempts"]),
            })
            self._trace(
                agent_name="RAGAgent",
                action="retrieve",
                input_summary={"query": query},
                output_summary={
                    "hits": len(hits),
                    "top_score": hits[0]["score"],
                    "coverage": outcome["coverage"],
                },
                confidence=float(hits[0]["score"]) if hits else None,
                retry_count=max(0, len(outcome["attempts"]) - 1),
            )
        else:
            self._log(state, "rag_agent", "no_hits", {
                "coverage": outcome["coverage"],
                "attempts": len(outcome["attempts"]),
            })
            self._trace(
                agent_name="RAGAgent",
                action="retrieve",
                input_summary={"query": query},
                output_summary={"hits": 0, "coverage": outcome["coverage"]},
                status="empty",
                retry_count=max(0, len(outcome["attempts"]) - 1),
            )

    async def _run_agents_parallel(
        self, state: AgentState, delegated_agents: List[str]
    ) -> None:
        """Execute independent agents concurrently; chain dependent ones."""
        # Dependency model: reservoir depends on well_log; risk depends on others.
        independent = [a for a in delegated_agents if a in {"seismic_analyzer", "well_log_interpreter"}]
        dependent_order = [
            a for a in delegated_agents if a in {"reservoir_characterizer", "exploration_risk_assessor"}
        ]
        others = [a for a in delegated_agents if a not in independent and a not in dependent_order]

        async def run_one(agent_name: str) -> None:
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
            with obs.span("agent.execute", agent=agent_name):
                result = await asyncio.to_thread(self.execute_agent, agent_name, task, context)
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
            res = result.get("result") if isinstance(result.get("result"), dict) else {}
            self._trace(
                agent_name=AGENT_CONFIGS[agent_name]["name"],
                action="execute",
                input_summary={"task": task, "iteration": state.iteration},
                output_summary={
                    "status": result.get("status"),
                    "tools": list(result.get("tool_results", {}).keys()),
                    "mode": res.get("mode"),
                    "summary": res.get("summary") or res.get("output") or "",
                },
                status=str(result.get("status", "success")),
                extra={"llm_mode": res.get("mode")},
            )

        if independent:
            await asyncio.gather(*(run_one(a) for a in independent))
        for agent_name in dependent_order + others:
            await run_one(agent_name)

    def execute_collaborative_workflow(
        self,
        user_input: Dict[str, Any],
        quick: bool = False,
        max_review_cycles: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Sync wrapper around the async collaborative workflow.

        ``max_review_cycles`` controls the outer planner→executor→evaluator
        review loop. When ``None`` (the default) it falls back to
        ``config.MAX_AGENT_ITERATIONS`` (env var ``MAX_AGENT_ITERATIONS``,
        default 3).
        """
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(
                self.execute_collaborative_workflow_async(
                    user_input, quick=quick, max_review_cycles=max_review_cycles
                )
            )
        # Already in an event loop (e.g. inside FastAPI) — run in a worker thread.
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(
                lambda: asyncio.run(
                    self.execute_collaborative_workflow_async(
                        user_input, quick=quick, max_review_cycles=max_review_cycles
                    )
                )
            ).result()

    async def execute_collaborative_workflow_async(
        self,
        user_input: Dict[str, Any],
        quick: bool = False,
        max_review_cycles: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Async Planner -> Research -> (parallel) Executor -> Evaluator -> Final.

        Non-linear control flow:
        - Specialist agents run in parallel when independent.
        - If the evaluator's quality_score is below threshold OR risk_level is
          HIGH, the planner re-delegates with broadened retrieval.
        - On repeated LLM failures the manager auto-escalates to deterministic
          sample mode (handled in ``_invoke_reasoning_llm``).
        - The evaluator can block the report writer via ``report_gate``.
        """

        # Resolve the outer review-cycle cap. Explicit caller value wins,
        # otherwise fall back to MAX_AGENT_ITERATIONS from .env (default 3).
        if max_review_cycles is None:
            max_review_cycles = self.config.MAX_AGENT_ITERATIONS
        max_review_cycles = max(1, int(max_review_cycles))

        state = AgentState(
            user_input=dict(user_input),
            shared_memory={
                "workflow_goal": "Evidence-grounded oil and gas prospect analysis",
                "llm_configured": self.reasoning_llm is not None,
                "needs": [],
                "max_agent_iterations": max_review_cycles,
            },
        )
        workflow_id = datetime.now().isoformat()
        # Fresh per-run trace file/id so each workflow has an isolated log.
        self.trace_file, self.trace_id = new_trace_file()
        logger.info(
            "Workflow %s starting with max_agent_iterations=%d (source=%s)",
            workflow_id,
            max_review_cycles,
            "caller" if max_review_cycles != self.config.MAX_AGENT_ITERATIONS else "env/config",
        )

        # Record the resolved LLM configuration as the very first trace event
        # so every run's JSONL log clearly shows where OPENAI_API_KEY and
        # OPENAI_BASE_URL were sourced from (env vs. default fallback) and
        # which Compass models are active. The key itself is never logged.
        cfg = self.config
        api_key_present = bool(cfg.OPENAI_API_KEY) and cfg.OPENAI_API_KEY_SOURCE == "env"
        self._trace(
            agent_name="AgentExecutorManager",
            action="llm_config_resolved",
            input_summary={
                "workflow_id": workflow_id,
                "sample_mode": cfg.SAMPLE_MODE,
            },
            output_summary={
                "llm_enabled": cfg.llm_enabled,
                "openai_api_key_present": api_key_present,
                "openai_api_key_source": cfg.OPENAI_API_KEY_SOURCE,
                "openai_base_url": cfg.OPENAI_BASE_URL,
                "openai_base_url_source": cfg.OPENAI_BASE_URL_SOURCE,
                "compass_chat_model": cfg.COMPASS_CHAT_MODEL,
                "compass_reasoning_model": cfg.COMPASS_REASONING_MODEL,
                "compass_embedding_model": cfg.COMPASS_EMBEDDING_MODEL,
                "reasoning_client_ready": self.reasoning_client is not None,
                "max_iterations": cfg.MAX_ITERATIONS,
                "max_agent_iterations": max_review_cycles,
            },
            status="success" if cfg.llm_enabled else "skipped",
            extra={
                "default_base_url_fallback": DEFAULT_OPENAI_BASE_URL,
                "trace_file": self.trace_file,
            },
        )

        obs.emit_event(
            "workflow.start",
            workflow_id=workflow_id,
            quick=quick,
            well=user_input.get("well_name"),
        )
        self._log(state, "planner", "started", {"workflow_id": workflow_id, "quick": quick})
        self._trace(
            agent_name="PlannerAgent",
            action="workflow_start",
            input_summary={
                "workflow_id": workflow_id,
                "quick": quick,
                "well": user_input.get("well_name"),
                "available_keys": sorted(user_input.keys()),
            },
            output_summary="Workflow initialized",
            extra={"trace_file": self.trace_file},
        )
        with obs.span("workflow.research"):
            self._research_missing_context(state)
            self._augment_with_rag_and_memory(state)

        evaluation: Dict[str, Any] = {"approved": False}
        delegated_agents: List[str] = []
        for iteration in range(1, max_review_cycles + 1):
            state.iteration = iteration
            delegated_agents = self._planner_delegate(state, quick=quick)

            # Parallel non-linear execution (independent agents concurrently;
            # dependent ones chained).
            with obs.span("workflow.execute", iteration=iteration):
                await self._run_agents_parallel(state, delegated_agents)

            evaluation = self._evaluate_iteration(state, delegated_agents)

            # Branch: stop if approved.
            if evaluation["approved"]:
                break

            # Branch: HIGH risk -> always loop to gather more evidence.
            # Low quality -> request research + retry.
            self._log(
                state,
                "planner",
                "revision_requested",
                {
                    "next_action": "broaden_retrieval_and_retry",
                    "quality_score": evaluation.get("quality_score"),
                    "risk_level": evaluation.get("risk_level"),
                    "missing_evidence": evaluation.get("missing_evidence"),
                    "weak_outputs": evaluation.get("weak_outputs"),
                },
            )
            self._trace(
                agent_name="PlannerAgent",
                action="revision_requested",
                input_summary={
                    "iteration": state.iteration,
                    "quality_score": evaluation.get("quality_score"),
                    "risk_level": evaluation.get("risk_level"),
                },
                output_summary={
                    "missing_evidence": evaluation.get("missing_evidence"),
                    "weak_outputs": evaluation.get("weak_outputs"),
                },
                retry_count=state.iteration,
                status="request_revision",
            )
            self._research_missing_context(state)
            self._broaden_retrieval(state)

        # Final synthesis (respects evaluator's report gate).
        final_report = self._finalize_report(state, evaluation)
        state.final_report = final_report

        status_label = (
            "blocked" if final_report.get("status") == "blocked"
            else "success" if evaluation.get("approved") else "partial"
        )

        summary = {
            "workflow_id": workflow_id,
            "trace_id": self.trace_id,
            "trace_file": self.trace_file,
            "status": status_label,
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
            "escalation": {
                "llm_failure_streak": self._llm_failure_streak,
                "escalated_to_sample_mode": self._llm_escalated,
            },
            "messages": [
                f"{event['agent']} {event['action']} at {event['timestamp']}"
                for event in state.collaboration_log
            ],
            "open_data_recommendations": SEG_OPEN_DATA_SOURCES,
        }
        try:
            persistent_memory.remember(state.user_input, summary)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Failed to persist memory: %s", exc)
        obs.emit_event(
            "workflow.end",
            workflow_id=workflow_id,
            status=summary["status"],
            agents=state.completed_agents,
            escalated=self._llm_escalated,
        )
        self._trace(
            agent_name="PlannerAgent",
            action="workflow_end",
            input_summary={"workflow_id": workflow_id},
            output_summary={
                "status": summary["status"],
                "agents_executed": state.completed_agents,
                "quality_score": evaluation.get("quality_score"),
                "risk_level": evaluation.get("risk_level"),
                "escalated": self._llm_escalated,
            },
            confidence=float(evaluation.get("quality_score") or 0.0) or None,
            status=summary["status"],
        )
        return summary

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
