"""Oil & Gas Analytics — production multi-agent system package."""

from __future__ import annotations

__version__ = "1.1.0"

from .config import Config, get_config

# Heavy imports (LangChain / LangGraph) are lazy so simple things like
# ``from app import __version__`` stay cheap and side-effect free.
__all__ = [
    "__version__",
    "Config",
    "get_config",
    "AgentExecutorManager",
    "WorkflowOrchestrator",
    "create_agent_executor",
    "create_workflow",
]


def __getattr__(name: str):  # pragma: no cover - thin lazy loader
    if name in {"AgentExecutorManager", "create_agent_executor"}:
        from . import agents as _agents

        return getattr(_agents, name)
    if name == "WorkflowOrchestrator":
        from .workflows import WorkflowOrchestrator

        return WorkflowOrchestrator
    if name == "create_workflow":
        from .workflows import create_analysis_workflow

        return create_analysis_workflow
    raise AttributeError(f"module 'app' has no attribute {name!r}")

