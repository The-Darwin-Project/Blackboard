# tests/test_claude_adapter_kwargs.py
"""Tests for ClaudeAdapter._build_kwargs temperature handling and model argument construction."""
import pytest
from src.agents.llm.claude_client import ClaudeAdapter


def _make_adapter(model_name: str) -> ClaudeAdapter:
    adapter = ClaudeAdapter.__new__(ClaudeAdapter)
    adapter._model_name = model_name
    return adapter


@pytest.mark.parametrize(
    "model_name",
    [
        "claude-sonnet-5-5",
        "claude-opus-5-5",
        "claude-sonnet-5",
        "claude-opus-5",
    ],
)
def test_claude_5_models_omit_temperature(model_name: str) -> None:
    """Claude 5.x models deprecate temperature (returns 400 on Vertex AI); must be omitted."""
    adapter = _make_adapter(model_name)
    kwargs = adapter._build_kwargs(
        system_prompt="system",
        contents="hello",
        tools=None,
        temperature=0.7,
        max_output_tokens=1024,
    )
    assert "temperature" not in kwargs
    assert kwargs["model"] == model_name
    assert kwargs["max_tokens"] == 1024
    assert kwargs["system"] == "system"


@pytest.mark.parametrize(
    "model_name",
    [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
    ],
)
def test_legacy_claude_models_include_temperature(model_name: str) -> None:
    """Pre-5 Claude models require normalized temperature in kwargs."""
    adapter = _make_adapter(model_name)
    kwargs = adapter._build_kwargs(
        system_prompt="",
        contents="hello",
        tools=None,
        temperature=0.5,
        max_output_tokens=2048,
    )
    assert kwargs.get("temperature") == 0.5
    assert kwargs["model"] == model_name
    assert kwargs["max_tokens"] == 2048
    assert "system" not in kwargs
