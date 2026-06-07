"""Tests for app/config.py."""

import logging

import pytest

from app.config import (
    DEFAULT_OPENAI_BASE_URL,
    Config,
    _secret_status,
    get_config,
)


def test_sample_mode_disables_llm() -> None:
    cfg = get_config()
    assert cfg.SAMPLE_MODE is True
    assert cfg.llm_enabled is False
    # validate() must not raise in SAMPLE_MODE.
    cfg.validate()


def test_safe_dict_does_not_leak_api_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "sk-super-secret-12345")
    monkeypatch.setenv("SAMPLE_MODE", "false")
    get_config.cache_clear()  # type: ignore[attr-defined]
    try:
        cfg = get_config()
        snapshot = cfg.safe_dict()
        assert snapshot["openai_api_key"] in {"***", ""}
        assert snapshot["openai_api_key_present"] is True
        assert "sk-super-secret" not in str(snapshot)
    finally:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.setenv("SAMPLE_MODE", "true")
        get_config.cache_clear()  # type: ignore[attr-defined]


def test_production_requires_cors_allowlist(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("CORS_ORIGINS", "*")
    monkeypatch.setenv("SAMPLE_MODE", "true")  # avoid OPENAI_API_KEY requirement
    get_config.cache_clear()  # type: ignore[attr-defined]
    try:
        cfg = get_config()
        with pytest.raises(RuntimeError, match="CORS_ORIGINS"):
            cfg.validate()
    finally:
        monkeypatch.setenv("APP_ENV", "development")
        monkeypatch.setenv("CORS_ORIGINS", "*")
        get_config.cache_clear()  # type: ignore[attr-defined]


def test_env_int_falls_back_on_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("API_PORT", "not-a-number")
    get_config.cache_clear()  # type: ignore[attr-defined]
    try:
        cfg = Config()
        assert cfg.API_PORT == 8000  # default
    finally:
        monkeypatch.delenv("API_PORT", raising=False)
        get_config.cache_clear()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# OPENAI_API_KEY / OPENAI_BASE_URL: env-driven + Core42 fallback
# ---------------------------------------------------------------------------
def test_default_base_url_constant_is_core42() -> None:
    assert DEFAULT_OPENAI_BASE_URL == "https://api.core42.ai/v1"


def test_base_url_falls_back_to_core42(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    get_config.cache_clear()  # type: ignore[attr-defined]
    try:
        cfg = Config()
        assert cfg.OPENAI_BASE_URL == DEFAULT_OPENAI_BASE_URL
        assert cfg.OPENAI_BASE_URL_SOURCE == "default-fallback"
    finally:
        get_config.cache_clear()  # type: ignore[attr-defined]


def test_base_url_env_override_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    get_config.cache_clear()  # type: ignore[attr-defined]
    try:
        cfg = Config()
        assert cfg.OPENAI_BASE_URL == "https://api.openai.com/v1"
        assert cfg.OPENAI_BASE_URL_SOURCE == "env"
    finally:
        monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
        get_config.cache_clear()  # type: ignore[attr-defined]


def test_api_key_only_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # No source-level default — the field reflects only the env value.
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    get_config.cache_clear()  # type: ignore[attr-defined]
    try:
        cfg = Config()
        assert cfg.OPENAI_API_KEY == ""
        assert cfg.llm_enabled is False  # SAMPLE_MODE still on from conftest
    finally:
        get_config.cache_clear()  # type: ignore[attr-defined]


def test_config_init_logs_provider_setup(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    get_config.cache_clear()  # type: ignore[attr-defined]
    try:
        with caplog.at_level(logging.INFO, logger="app.config"):
            Config()
        messages = [r.getMessage() for r in caplog.records if "LLM provider" in r.getMessage()]
        assert messages, "expected an LLM-provider log line on Config init"
        line = messages[-1]
        assert "base_url=https://api.core42.ai/v1" in line
        assert "source=default-fallback" in line
        assert "api_key_status=missing" in line
        # The raw key (or any portion of it) must never appear in logs.
        assert "OPENAI_API_KEY=" not in line
    finally:
        get_config.cache_clear()  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# _secret_status: log-safe presence reporting (NEVER returns the value)
# ---------------------------------------------------------------------------
def test_secret_status_missing_for_empty() -> None:
    assert _secret_status("") == "missing"


def test_secret_status_placeholder_for_dummy_values() -> None:
    assert _secret_status("NA") == "placeholder"
    assert _secret_status("CHANGEME") == "placeholder"


def test_secret_status_present_for_real_key_without_leaking() -> None:
    secret = "sk-abcdefghij1234567890wxyz"
    rendered = _secret_status(secret)
    assert rendered == "present"
    # The helper must NEVER echo the value (full, masked, or length).
    assert secret not in rendered
    assert "sk-" not in rendered
    assert "wxyz" not in rendered
    assert str(len(secret)) not in rendered


