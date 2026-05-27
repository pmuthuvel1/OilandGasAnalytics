"""Oil & Gas Analytics Multi-Agent System using LangGraph"""

__version__ = "1.0.0"
__author__ = "LangGraph Analytics Team"

from .config import get_config
from .agents import create_agent_executor
from .workflows import create_workflow

__all__ = ["get_config", "create_agent_executor", "create_workflow"]
