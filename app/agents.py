"""LangGraph agents for Oil & Gas Analytics"""

import json
import logging
from typing import Any, Dict, List, Callable
from datetime import datetime
from langchain.agents import create_openai_functions_agent, AgentExecutor
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.graph.graph import CompiledGraph
from pydantic import BaseModel

from .config import get_config, AGENT_CONFIGS
from .tools import TOOLS

logger = logging.getLogger(__name__)


class AgentState(BaseModel):
    """State for multi-agent workflow"""

    messages: List[Dict[str, Any]] = []
    analysis_results: Dict[str, Any] = {}
    current_agent: str = ""
    completed_agents: List[str] = []
    user_input: Dict[str, Any] = {}
    final_report: Dict[str, Any] = {}


def create_tool_functions():
    """Create callable tool functions for LangChain"""
    tool_functions = {}

    for tool_name, tool_func in TOOLS.items():
        @tool
        def dynamic_tool(data: Dict[str, Any], func=tool_func, name=tool_name) -> str:
            """Dynamic tool wrapper"""
            result = func(data)
            return json.dumps(result)

        tool_functions[tool_name] = dynamic_tool

    return list(tool_functions.values())


def create_seismic_analyzer_agent():
    """Create SeismicAnalyzer agent"""
    config = get_config()
    llm = ChatOpenAI(
        api_key=config.OPENAI_API_KEY, model=config.OPENAI_MODEL, temperature=0.2
    )

    tools = [
        tool(TOOLS["analyze_seismic_amplitude"])(
            lambda x: TOOLS["analyze_seismic_amplitude"](x)
        ),
        tool(TOOLS["detect_faults"])(lambda x: TOOLS["detect_faults"](x)),
        tool(TOOLS["pick_horizons"])(lambda x: TOOLS["pick_horizons"](x)),
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert Seismic Analyst for oil and gas exploration.
                Your role is to analyze seismic data for subsurface structures, faults, 
                and hydrocarbon indicators. Use the available tools to:
                1. Analyze seismic amplitude data for anomalies
                2. Detect fault structures
                3. Pick key seismic horizons
                
                Provide clear, technical interpretations suitable for exploration teams.""",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)


def create_well_log_interpreter_agent():
    """Create WellLogInterpreter agent"""
    config = get_config()
    llm = ChatOpenAI(
        api_key=config.OPENAI_API_KEY, model=config.OPENAI_MODEL, temperature=0.2
    )

    tools = [
        tool(TOOLS["classify_lithology"])(lambda x: TOOLS["classify_lithology"](x)),
        tool(TOOLS["identify_fluids"])(lambda x: TOOLS["identify_fluids"](x)),
        tool(TOOLS["estimate_porosity"])(lambda x: TOOLS["estimate_porosity"](x)),
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert Well Log Interpreter for oil and gas exploration.
                Your role is to interpret well log data for lithology classification,
                fluid identification, and reservoir quality assessment. Use the available tools to:
                1. Classify rock types from gamma ray and resistivity logs
                2. Identify fluid types based on log signatures
                3. Estimate porosity and flow characteristics
                
                Provide detailed petrophysical interpretations.""",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)


def create_reservoir_characterizer_agent():
    """Create ReservoirCharacterizer agent"""
    config = get_config()
    llm = ChatOpenAI(
        api_key=config.OPENAI_API_KEY, model=config.OPENAI_MODEL, temperature=0.2
    )

    tools = [
        tool(TOOLS["estimate_permeability"])(
            lambda x: TOOLS["estimate_permeability"](x)
        ),
        tool(TOOLS["analyze_saturation"])(lambda x: TOOLS["analyze_saturation"](x)),
        tool(TOOLS["predict_pressure"])(lambda x: TOOLS["predict_pressure"](x)),
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert Reservoir Engineer for oil and gas exploration.
                Your role is to characterize reservoir properties and predict production potential.
                Use the available tools to:
                1. Estimate formation permeability
                2. Analyze fluid saturation distribution
                3. Predict formation pressures
                
                Integrate analysis to assess reservoir quality and producibility.""",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)


def create_exploration_risk_agent():
    """Create ExplorationRiskAssessor agent"""
    config = get_config()
    llm = ChatOpenAI(
        api_key=config.OPENAI_API_KEY, model=config.OPENAI_MODEL, temperature=0.2
    )

    tools = [
        tool(TOOLS["evaluate_trap"])(lambda x: TOOLS["evaluate_trap"](x)),
        tool(TOOLS["calculate_volumes"])(lambda x: TOOLS["calculate_volumes"](x)),
        tool(TOOLS["assess_seal_integrity"])(lambda x: TOOLS["assess_seal_integrity"](x)),
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert Exploration Manager for oil and gas companies.
                Your role is to assess exploration opportunities and risks. Use tools to:
                1. Evaluate trap geometry and seal integrity
                2. Calculate volumetric estimates
                3. Assess risk factors
                
                Provide business-focused recommendations on drilling decisions.""",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)


def create_report_generator_agent():
    """Create ReportGenerator agent"""
    config = get_config()
    llm = ChatOpenAI(
        api_key=config.OPENAI_API_KEY, model=config.OPENAI_MODEL, temperature=0.3
    )

    tools = [
        tool(TOOLS["synthesize_analysis"])(
            lambda x: TOOLS["synthesize_analysis"](x)
        ),
        tool(TOOLS["create_visualizations"])(
            lambda x: TOOLS["create_visualizations"](x)
        ),
        tool(TOOLS["format_recommendations"])(
            lambda x: TOOLS["format_recommendations"](x)
        ),
    ]

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """You are an expert Technical Report Writer for oil and gas exploration.
                Your role is to synthesize findings from all analysis agents into
                comprehensive, actionable reports. Use tools to:
                1. Summarize and synthesize all analyses
                2. Create visualization specifications
                3. Generate final recommendations
                
                Create reports suitable for executive and technical audiences.""",
            ),
            MessagesPlaceholder(variable_name="chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad"),
        ]
    )

    agent = create_openai_functions_agent(llm, tools, prompt)
    return AgentExecutor.from_agent_and_tools(agent=agent, tools=tools, verbose=True)


class AgentExecutorManager:
    """Manages multi-agent execution"""

    def __init__(self):
        self.agents = {
            "seismic_analyzer": create_seismic_analyzer_agent(),
            "well_log_interpreter": create_well_log_interpreter_agent(),
            "reservoir_characterizer": create_reservoir_characterizer_agent(),
            "exploration_risk_assessor": create_exploration_risk_agent(),
            "report_generator": create_report_generator_agent(),
        }
        self.config = get_config()

    def execute_agent(
        self, agent_name: str, task_description: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single agent"""
        try:
            if agent_name not in self.agents:
                return {
                    "status": "error",
                    "error": f"Agent {agent_name} not found",
                }

            agent = self.agents[agent_name]
            input_text = f"{task_description}\nContext: {json.dumps(context)}"

            result = agent.invoke(
                {
                    "input": input_text,
                    "chat_history": [],
                    "agent_scratchpad": "",
                }
            )

            return {
                "status": "success",
                "agent": agent_name,
                "result": result,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            logger.error(f"Error executing agent {agent_name}: {str(e)}")
            return {
                "status": "error",
                "agent": agent_name,
                "error": str(e),
            }

    def execute_workflow(
        self, workflow_config: Dict[str, Any], data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a complete workflow with multiple agents"""
        results = {
            "workflow_id": datetime.now().isoformat(),
            "status": "in_progress",
            "agents_executed": [],
            "findings": {},
            "errors": [],
        }

        agent_sequence = workflow_config.get("agent_sequence", [])

        for agent_name in agent_sequence:
            task = workflow_config.get(f"{agent_name}_task", "Analyze provided data")
            result = self.execute_agent(agent_name, task, data)

            results["agents_executed"].append(agent_name)

            if result["status"] == "success":
                results["findings"][agent_name] = result["result"]
            else:
                results["errors"].append(
                    {
                        "agent": agent_name,
                        "error": result.get("error", "Unknown error"),
                    }
                )

        results["status"] = "completed" if not results["errors"] else "partial"
        return results
