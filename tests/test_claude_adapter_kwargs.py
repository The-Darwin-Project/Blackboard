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


class TestClaudeModelMaxTokensCeilings:
    """T-4 & CR-06: ClaudeAdapter._build_kwargs clamps max_tokens per exact Anthropic model family ceiling."""

    @pytest.mark.parametrize(
        "model_name",
        [
            "claude-3-haiku-20240307",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
            "claude-3.0-sonnet",
        ],
    )
    def test_cr06_claude_3_0_clamps_to_4096(self, model_name: str) -> None:
        adapter = _make_adapter(model_name)
        kwargs = adapter._build_kwargs(
            system_prompt="sys",
            contents="hello",
            tools=None,
            temperature=0.5,
            max_output_tokens=65536,
        )
        assert kwargs["max_tokens"] == 4096

        below = adapter._build_kwargs(
            system_prompt="sys",
            contents="hello",
            tools=None,
            temperature=0.5,
            max_output_tokens=2048,
        )
        assert below["max_tokens"] == 2048

    @pytest.mark.parametrize(
        "model_name",
        [
            "claude-3-5-sonnet-20241022",
            "claude-3.5-sonnet",
            "claude-3-5-haiku",
            "Claude-3.5-Sonnet",
        ],
    )
    def test_t4_claude_35_clamps_65536_to_8192(self, model_name: str) -> None:
        adapter = _make_adapter(model_name)
        kwargs = adapter._build_kwargs(
            system_prompt="sys",
            contents="hello",
            tools=None,
            temperature=0.5,
            max_output_tokens=65536,
        )
        assert kwargs["max_tokens"] == 8192

        below = adapter._build_kwargs(
            system_prompt="sys",
            contents="hello",
            tools=None,
            temperature=0.5,
            max_output_tokens=4096,
        )
        assert below["max_tokens"] == 4096

    @pytest.mark.parametrize(
        "model_name",
        [
            "claude-opus-4",
            "claude-opus-4-0",
            "claude-opus-4.0",
            "claude-opus-4-1",
            "claude-opus-4.1",
            "claude-opus-4@20250514",
            "claude-opus-4-20250514",
        ],
    )
    def test_cr06_claude_opus_4_and_41_clamp_to_32000(self, model_name: str) -> None:
        adapter = _make_adapter(model_name)
        kwargs = adapter._build_kwargs(
            system_prompt="sys",
            contents="hello",
            tools=None,
            temperature=0.5,
            max_output_tokens=65536,
        )
        assert kwargs["max_tokens"] == 32000

        below = adapter._build_kwargs(
            system_prompt="sys",
            contents="hello",
            tools=None,
            temperature=0.5,
            max_output_tokens=16384,
        )
        assert below["max_tokens"] == 16384

    @pytest.mark.parametrize(
        "model_name",
        [
            "claude-sonnet-4-5",
            "claude-opus-4-5",
            "claude-opus-4.5",
            "claude-opus-4-6",
            "claude-opus-4.6",
            "claude-3-7-sonnet",
            "claude-3.7-sonnet",
            "claude-haiku-4-5",
            "claude-4-sonnet",
            "Claude-Sonnet-4-5",
        ],
    )
    def test_t4_claude_37_sonnet4_and_opus45_clamp_65536_to_64000(self, model_name: str) -> None:
        adapter = _make_adapter(model_name)
        kwargs = adapter._build_kwargs(
            system_prompt="sys",
            contents="hello",
            tools=None,
            temperature=0.5,
            max_output_tokens=65536,
        )
        assert kwargs["max_tokens"] == 64000

        below = adapter._build_kwargs(
            system_prompt="sys",
            contents="hello",
            tools=None,
            temperature=0.5,
            max_output_tokens=16384,
        )
        assert below["max_tokens"] == 16384

    @pytest.mark.parametrize(
        "model_name",
        [
            "claude-sonnet-5-5",
            "claude-opus-5-5",
            "claude-5-sonnet",
        ],
    )
    def test_t4_claude_5_passes_65536_through_unclamped(self, model_name: str) -> None:
        adapter = _make_adapter(model_name)
        kwargs = adapter._build_kwargs(
            system_prompt="sys",
            contents="hello",
            tools=None,
            temperature=0.5,
            max_output_tokens=65536,
        )
        assert kwargs["max_tokens"] == 65536

    @pytest.mark.parametrize("bad_tokens", [None, True, False, 0, -10, "65536", 1.5])
    def test_cr06_invalid_max_output_tokens_defaults_safely(self, bad_tokens) -> None:
        adapter_5 = _make_adapter("claude-sonnet-5-5")
        kwargs_5 = adapter_5._build_kwargs("sys", "hello", None, 0.5, bad_tokens)  # type: ignore[arg-type]
        assert kwargs_5["max_tokens"] == 65000

        adapter_opus4 = _make_adapter("claude-opus-4-1")
        kwargs_opus4 = adapter_opus4._build_kwargs("sys", "hello", None, 0.5, bad_tokens)  # type: ignore[arg-type]
        assert kwargs_opus4["max_tokens"] == 32000


class TestClaudeAdapterStreamParityAndSafety:
    """CR-05, CR-06, CR-07: Sync generate_stream delegator, SSE liveness chunks, unary 21333 cap, and thought filtering."""

    def test_cr05_generate_stream_is_sync_delegator(self) -> None:
        import inspect

        assert inspect.iscoroutinefunction(ClaudeAdapter.generate_stream) is False
        assert inspect.isasyncgenfunction(ClaudeAdapter.generate_stream) is False

    @pytest.mark.asyncio
    async def test_cr05_raw_sse_events_emit_thinking_and_tool_json_liveness_chunks(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        adapter = _make_adapter("claude-sonnet-4-5")
        adapter._client = MagicMock()

        raw_events = [
            SimpleNamespace(type="message_start"),
            SimpleNamespace(type="content_block_start"),
            SimpleNamespace(
                type="content_block_delta",
                delta=SimpleNamespace(type="thinking_delta", thinking="step 1"),
            ),
            SimpleNamespace(type="thinking", thinking="step 1"),  # high-level helper event (must not duplicate)
            SimpleNamespace(
                type="content_block_delta",
                delta=SimpleNamespace(type="text_delta", text="Answer"),
            ),
            SimpleNamespace(type="text", text="Answer"),  # high-level helper event (must not duplicate)
            SimpleNamespace(
                type="content_block_delta",
                delta=SimpleNamespace(type="input_json_delta", partial_json='{"k":'),
            ),
        ]

        class RawSSEStream:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                return None

            def __aiter__(self):
                async def _gen():
                    for ev in raw_events:
                        yield ev

                return _gen()

            async def get_final_message(self):
                return SimpleNamespace(
                    content=[SimpleNamespace(type="tool_use", name="inspect_event", input={"k": 1})],
                    usage=SimpleNamespace(input_tokens=20, output_tokens=10),
                )

        adapter._client.messages.stream = MagicMock(return_value=RawSSEStream())
        gen = adapter.generate_stream("sys", "hello")
        assert hasattr(gen, "aclose")
        chunks = [c async for c in gen]

        visible = [c.text for c in chunks if c.text and not c.is_thought]
        thoughts = [c.text for c in chunks if c.is_thought]
        heartbeats = [c for c in chunks if c.text is None and not c.done]
        assert visible == ["Answer"], "text_delta must emit once without duplicating TextEvent"
        assert thoughts == ["step 1"]
        assert len(heartbeats) == 3, "message_start, content_block_start, and input_json_delta must emit liveness chunks"
        assert chunks[-1].done is True
        assert chunks[-1].function_call is not None and chunks[-1].function_call.name == "inspect_event"

    @pytest.mark.asyncio
    async def test_cr06_unary_generate_clamps_nonstreaming_max_tokens_to_21333(self) -> None:
        from types import SimpleNamespace
        from unittest.mock import AsyncMock, MagicMock

        adapter = _make_adapter("claude-sonnet-4-5")
        adapter._client = MagicMock()
        adapter._client.messages.create = AsyncMock(
            return_value=SimpleNamespace(
                content=[SimpleNamespace(type="text", text="ok")],
                usage=SimpleNamespace(input_tokens=10, output_tokens=5),
            )
        )

        await adapter.generate("sys", "hello", max_output_tokens=65000)
        assert adapter._client.messages.create.call_args.kwargs["max_tokens"] == 21333

        await adapter.generate("sys", "hello", max_output_tokens=16384)
        assert adapter._client.messages.create.call_args.kwargs["max_tokens"] == 16384

    def test_cr07_convert_structured_filters_thought_and_empty_carrier_dicts(self) -> None:
        contents = [
            {"role": "user", "parts": [{"text": "hi"}]},
            {
                "role": "model",
                "parts": [
                    {"thought": True, "text": "secret internal chain of thought"},
                    {"text": "", "thoughtSignature": "eHl6"},
                    {"text": "Public answer"},
                ],
            },
        ]
        messages = ClaudeAdapter._convert_structured(contents)
        assert len(messages) == 2
        assert messages[1] == {"role": "assistant", "content": [{"type": "text", "text": "Public answer"}]}

