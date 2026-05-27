"""Configuration management for the Oil & Gas Analytics system"""

import os
from typing import Optional
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration"""

    # API Configuration
    API_PORT: int = int(os.getenv("API_PORT", 8000))
    UI_PORT: int = int(os.getenv("UI_PORT", 8001))
    HOST: str = os.getenv("HOST", "0.0.0.0")

    # LLM Configuration
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "gpt-4")

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    LOG_FILE: str = os.getenv("LOG_FILE", "logs/agent_logs.json")

    # Agent Configuration
    MAX_ITERATIONS: int = int(os.getenv("MAX_ITERATIONS", 10))
    AGENT_TIMEOUT: int = int(os.getenv("AGENT_TIMEOUT", 300))

    # Data Configuration
    DATA_PATH: str = os.getenv("DATA_PATH", "data/")
    MAX_FILE_SIZE: int = int(os.getenv("MAX_FILE_SIZE", 500000000))


def get_config() -> Config:
    """Get application configuration"""
    return Config()


# Agent configurations
AGENT_CONFIGS = {
    "seismic_analyzer": {
        "name": "SeismicAnalyzer",
        "description": "Analyzes seismic data for subsurface structures",
        "tools": ["analyze_seismic_amplitude", "detect_faults", "pick_horizons"],
    },
    "well_log_interpreter": {
        "name": "WellLogInterpreter",
        "description": "Interprets well log data for lithology and fluids",
        "tools": ["classify_lithology", "identify_fluids", "estimate_porosity"],
    },
    "reservoir_characterizer": {
        "name": "ReservoirCharacterizer",
        "description": "Characterizes reservoir properties",
        "tools": ["estimate_permeability", "analyze_saturation", "predict_pressure"],
    },
    "exploration_risk_assessor": {
        "name": "ExplorationRiskAssessor",
        "description": "Assesses exploration risks and opportunities",
        "tools": ["evaluate_trap", "calculate_volumes", "assess_seal_integrity"],
    },
    "report_generator": {
        "name": "ReportGenerator",
        "description": "Generates comprehensive analysis reports",
        "tools": ["synthesize_analysis", "create_visualizations", "format_recommendations"],
    },
}
