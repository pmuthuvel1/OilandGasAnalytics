"""Configuration management for the Oil & Gas Analytics system.

All settings are loaded from environment variables (with optional `.env` for
local development). In production, set `APP_ENV=production` so that the
process fails fast when critical secrets (e.g. ``OPENAI_API_KEY``) are missing.
"""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from typing import List, Optional

from dotenv import dotenv_values

# Load .env only for local/dev convenience; container deployments should
# inject real environment variables instead of relying on the file.
#
# IMPORTANT: we deliberately do NOT use ``load_dotenv()`` because it writes
# empty values (e.g. ``OPENAI_API_KEY=``) straight into ``os.environ``,
# which then masks a real shell ``export`` and makes the app behave as if
# the secret were unset. Instead, only copy non-empty keys that aren't
# already defined in the real environment.
for _k, _v in dotenv_values().items():
    if _v is None or _v.strip() == "":
        continue
    os.environ.setdefault(_k, _v)

logger = logging.getLogger(__name__)

_PLACEHOLDER_SECRETS = {"", "NA", "N/A", "NONE", "CHANGEME", "YOUR-API-KEY"}

# Default LLM gateway when ``OPENAI_BASE_URL`` is not provided in the
# environment. Project-wide we standardize on Core42 / Compass, with the
# public OpenAI endpoint reachable by setting the env var explicitly.
DEFAULT_OPENAI_BASE_URL = "https://api.core42.ai/v1"


def _env_str(name: str, default: str = "") -> str:
    return (os.getenv(name) or default).strip()


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw)
    except ValueError:
        logger.warning("Invalid integer for %s=%r; using default %s", name, raw, default)
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _env_list(name: str, default: Optional[List[str]] = None) -> List[str]:
    raw = os.getenv(name)
    if not raw:
        return list(default or [])
    return [item.strip() for item in raw.split(",") if item.strip()]


def _is_real_secret(value: str) -> bool:
    return bool(value) and value.strip().upper() not in _PLACEHOLDER_SECRETS


def _mask_secret(value: str) -> str:
    """Render an API key as ``abcd...wxyz (len=N)`` so it's safe to log."""
    if not value:
        return "<not set>"
    if not _is_real_secret(value):
        return "<placeholder>"
    if len(value) <= 8:
        return f"{'*' * len(value)} (len={len(value)})"
    return f"{value[:4]}...{value[-4:]} (len={len(value)})"


class Config:
    """Immutable application configuration loaded from the environment."""

    def __init__(self) -> None:
        # Runtime environment
        self.APP_ENV: str = _env_str("APP_ENV", "development").lower()
        self.DEBUG: bool = _env_bool("DEBUG", self.APP_ENV != "production")

        # API / UI
        self.API_PORT: int = _env_int("API_PORT", 8000)
        self.UI_PORT: int = _env_int("UI_PORT", 8001)
        self.HOST: str = _env_str("HOST", "0.0.0.0")
        self.API_BASE_URL: str = _env_str(
            "API_BASE_URL", f"http://localhost:{self.API_PORT}"
        )

        # LLM / OpenAI-compatible provider — STRICTLY env-driven, never
        # hard-coded in source. ``OPENAI_API_KEY`` is read only from the
        # process environment (or a local ``.env`` for dev convenience).
        # ``OPENAI_BASE_URL`` falls back to ``DEFAULT_OPENAI_BASE_URL``
        # (Core42 / Compass at https://api.core42.ai/v1) when the env
        # var is missing. Both values, along with their source ("env" vs
        # "default-fallback" / "missing"), are logged at startup so
        # operators can confirm the active gateway.
        raw_api_key = _env_str("OPENAI_API_KEY")
        self.OPENAI_API_KEY: str = raw_api_key
        self.OPENAI_API_KEY_SOURCE: str = (
            "env" if _is_real_secret(raw_api_key) else "missing"
        )
        env_base_url = _env_str("OPENAI_BASE_URL")
        self.OPENAI_BASE_URL: str = env_base_url or DEFAULT_OPENAI_BASE_URL
        self.OPENAI_BASE_URL_SOURCE: str = "env" if env_base_url else "default-fallback"
        self.OPENAI_MODEL: str = _env_str("OPENAI_MODEL", "gpt-4.1")
        self.OPENAI_REQUEST_TIMEOUT: int = _env_int("OPENAI_REQUEST_TIMEOUT", 60)
        self.OPENAI_MAX_RETRIES: int = _env_int("OPENAI_MAX_RETRIES", 2)

        logger.info(
            "LLM provider configured: base_url=%s (source=%s) api_key=%s (source=%s)",
            self.OPENAI_BASE_URL,
            self.OPENAI_BASE_URL_SOURCE,
            _mask_secret(self.OPENAI_API_KEY),
            self.OPENAI_API_KEY_SOURCE,
        )

        # COMPASS model aliases (specialized models per task).
        # Default to OPENAI_MODEL so existing deployments keep working.
        self.COMPASS_CHAT_MODEL: str = _env_str("COMPASS_CHAT_MODEL", self.OPENAI_MODEL)
        self.COMPASS_REASONING_MODEL: str = _env_str(
            "COMPASS_REASONING_MODEL", self.COMPASS_CHAT_MODEL
        )
        self.COMPASS_EMBEDDING_MODEL: str = _env_str(
            "COMPASS_EMBEDDING_MODEL", "text-embedding-3-large"
        )
        self.COMPASS_WHISPER_MODEL: str = _env_str("COMPASS_WHISPER_MODEL", "whisper-1")

        # Sample mode forces deterministic tool-only execution (no LLM calls),
        # useful for demos/CI without an API key.
        self.SAMPLE_MODE: bool = _env_bool("SAMPLE_MODE", False)

        # Logging
        self.LOG_LEVEL: str = _env_str("LOG_LEVEL", "INFO").upper()
        self.LOG_FILE: str = _env_str("LOG_FILE", "logs/agent_logs.json")
        self.JSON_LOGS: bool = _env_bool("JSON_LOGS", self.APP_ENV == "production")

        # Agent runtime
        self.MAX_ITERATIONS: int = _env_int("MAX_ITERATIONS", 10)
        self.AGENT_TIMEOUT: int = _env_int("AGENT_TIMEOUT", 300)
        self.MAX_CONTEXT_CHARS: int = _env_int("MAX_CONTEXT_CHARS", 24_000)

        # Data
        self.DATA_PATH: str = _env_str("DATA_PATH", "data/")
        self.MAX_FILE_SIZE: int = _env_int("MAX_FILE_SIZE", 500_000_000)

        # HTTP security
        self.CORS_ORIGINS: List[str] = _env_list(
            "CORS_ORIGINS",
            default=["*"] if self.APP_ENV != "production" else [],
        )
        self.MAX_REQUEST_BYTES: int = _env_int("MAX_REQUEST_BYTES", 10_000_000)

    # ------------------------------------------------------------------ #
    # Helpers
    # ------------------------------------------------------------------ #
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def llm_enabled(self) -> bool:
        """True only when an actual (non-placeholder) API key is configured
        and SAMPLE_MODE is not active."""
        if self.SAMPLE_MODE:
            return False
        return _is_real_secret(self.OPENAI_API_KEY)

    def validate(self) -> None:
        """Validate critical settings; raise in production when invalid."""
        errors: List[str] = []
        warnings: List[str] = []

        if not self.llm_enabled:
            if self.SAMPLE_MODE:
                warnings.append(
                    "SAMPLE_MODE is enabled; LLM calls are disabled and tools "
                    "will return deterministic sample results only."
                )
            else:
                msg = "OPENAI_API_KEY is not set or is a placeholder."
                (errors if self.is_production else warnings).append(msg)

        if self.is_production and "*" in self.CORS_ORIGINS:
            errors.append(
                "CORS_ORIGINS must not be '*' in production. "
                "Set CORS_ORIGINS to a comma-separated allow-list."
            )

        for w in warnings:
            logger.warning("Config warning: %s", w)

        if errors:
            joined = "; ".join(errors)
            logger.error("Invalid configuration: %s", joined)
            raise RuntimeError(f"Invalid configuration: {joined}")

    def safe_dict(self) -> dict:
        """Return config as dict with secrets redacted (safe for /info)."""
        masked_key = "***" if self.llm_enabled else ""
        return {
            "app_env": self.APP_ENV,
            "debug": self.DEBUG,
            "api_port": self.API_PORT,
            "ui_port": self.UI_PORT,
            "host": self.HOST,
            "openai_model": self.OPENAI_MODEL,
            "openai_base_url": self.OPENAI_BASE_URL,
            "openai_base_url_source": self.OPENAI_BASE_URL_SOURCE,
            "openai_api_key": masked_key,
            "openai_api_key_present": bool(_is_real_secret(self.OPENAI_API_KEY)),
            "openai_api_key_source": self.OPENAI_API_KEY_SOURCE,
            "compass_chat_model": self.COMPASS_CHAT_MODEL,
            "compass_reasoning_model": self.COMPASS_REASONING_MODEL,
            "compass_embedding_model": self.COMPASS_EMBEDDING_MODEL,
            "compass_whisper_model": self.COMPASS_WHISPER_MODEL,
            "sample_mode": self.SAMPLE_MODE,
            "llm_enabled": self.llm_enabled,
            "log_level": self.LOG_LEVEL,
            "max_iterations": self.MAX_ITERATIONS,
            "agent_timeout": self.AGENT_TIMEOUT,
            "cors_origins": self.CORS_ORIGINS,
        }


@lru_cache(maxsize=1)
def get_config() -> Config:
    """Return a cached, process-wide configuration instance."""
    return Config()


# Agent configurations (static; unrelated to environment)
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
