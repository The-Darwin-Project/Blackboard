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
        "claude-haiku-5",
        "claude-haiku-5-5",
        "claude-sonnet-5@20250219",
        "claude-5-sonnet",
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


@pytest.mark.parametrize("temp_value", [0.0, 0.5, 1.0])
def test_claude_5_omits_temperature_regardless_of_value(temp_value: float) -> None:
    """Ensure temperature is omitted on 5.x models across boundary float values."""
    adapter = _make_adapter("claude-sonnet-5-5")
    kwargs = adapter._build_kwargs(
        system_prompt="",
        contents="hello",
        tools=None,
        temperature=temp_value,
        max_output_tokens=1024,
    )
    assert "temperature" not in kwargs


@pytest.mark.parametrize(
    "model_name",
    [
        "claude-opus-4-6",
        "claude-sonnet-4-6",
        "claude-3-5-sonnet",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku",
        "claude-haiku-4-5",
        "claude-sonnet-4-5",
        "claude-opus-4-5",
    ],
)
def test_legacy_claude_models_include_temperature(model_name: str) -> None:
    """Pre-5 Claude models require normalized temperature in kwargs even if their version string contains '-5'."""
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
