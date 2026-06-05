"""Tests for the project metadata module (app/__init__.py)."""

import re

import app


def test_version_string_is_semver() -> None:
    assert re.match(r"^\d+\.\d+\.\d+$", app.__version__), app.__version__


def test_lazy_attribute_access_returns_classes() -> None:
    assert callable(app.WorkflowOrchestrator)
    assert callable(app.AgentExecutorManager)


def test_unknown_attribute_raises() -> None:
    import pytest

    with pytest.raises(AttributeError):
        _ = app.does_not_exist  # type: ignore[attr-defined]

