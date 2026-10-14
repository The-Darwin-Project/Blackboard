# tests/test_adapter_token_extraction.py
"""Direct tests for GeminiAdapter._record_usage() and ClaudeAdapter._extract_usage()."""
from types import SimpleNamespace

from src.agents.llm.types import TokenUsage


class TestGeminiRecordUsage:
    """Test GeminiAdapter._record_usage() token extraction logic."""

    def _make_adapter(self):
        from src.agents.llm.gemini_client import GeminiAdapter
        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-3-pro"
        adapter._tracker = None
        return adapter

    def test_full_usage_metadata(self):
        adapter = self._make_adapter()
        meta = SimpleNamespace(
            prompt_token_count=100,
            candidates_token_count=50,
            cached_content_token_count=20,
            thoughts_token_count=30,
            tool_use_prompt_token_count=10,
            total_token_count=210,
        )
        usage = adapter._record_usage(meta, estimate=200)
        assert isinstance(usage, TokenUsage)
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.cached_tokens == 20
        assert usage.thinking_tokens == 30
        assert usage.tool_use_tokens == 10
        assert usage.total_tokens == 210
        assert usage.model_version == "gemini-3-pro"

    def test_streaming_fallback_candidates_none(self):
        """When candidates_token_count is None (streaming final chunk), derive from total.
        cached_t and tool_use_t are sub-breakdowns of prompt_token_count — not subtracted."""
        adapter = self._make_adapter()
        meta = SimpleNamespace(
            prompt_token_count=100,
            candidates_token_count=None,
            cached_content_token_count=20,
            thoughts_token_count=30,
            tool_use_prompt_token_count=10,
            total_token_count=180,
        )
        usage = adapter._record_usage(meta, estimate=150)
        assert usage.output_tokens == 50  # 180 - 100(prompt) - 30(thinking)
        assert usage.cached_tokens == 20
        assert usage.tool_use_tokens == 10

    def test_none_usage_metadata(self):
        adapter = self._make_adapter()
        assert adapter._record_usage(None, estimate=100) is None

    def test_missing_fields_default_zero(self):
        adapter = self._make_adapter()
        meta = SimpleNamespace(
            prompt_token_count=100,
            total_token_count=100,
        )
        usage = adapter._record_usage(meta, estimate=100)
        assert usage.thinking_tokens == 0
        assert usage.cached_tokens == 0
        assert usage.tool_use_tokens == 0

    def test_quota_tracker_still_called(self):
        from unittest.mock import MagicMock
        adapter = self._make_adapter()
        adapter._tracker = MagicMock()
        meta = SimpleNamespace(
            prompt_token_count=50,
            candidates_token_count=50,
            total_token_count=100,
        )
        adapter._record_usage(meta, estimate=90)
        adapter._tracker.record.assert_called_once_with(100, 90)


class TestClaudeExtractUsage:
    """Test ClaudeAdapter._extract_usage() token extraction logic."""

    def _make_adapter(self):
        from src.agents.llm.claude_client import ClaudeAdapter
        adapter = ClaudeAdapter.__new__(ClaudeAdapter)
        adapter._model_name = "claude-sonnet-4.6"
        return adapter

    def test_full_usage(self):
        adapter = self._make_adapter()
        msg = SimpleNamespace(usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=50,
            cache_read_input_tokens=20,
            cache_creation_input_tokens=10,
        ))
        usage = adapter._extract_usage(msg)
        assert isinstance(usage, TokenUsage)
        assert usage.input_tokens == 130  # 100 + 20 cache_read + 10 cache_create
        assert usage.output_tokens == 50
        assert usage.cached_tokens == 30  # 20 read + 10 create
        assert usage.total_tokens == 180  # 130 + 50
        assert usage.model_version == "claude-sonnet-4.6"

    def test_no_cache_fields(self):
        adapter = self._make_adapter()
        msg = SimpleNamespace(usage=SimpleNamespace(
            input_tokens=80,
            output_tokens=40,
        ))
        usage = adapter._extract_usage(msg)
        assert usage.input_tokens == 80
        assert usage.cached_tokens == 0
        assert usage.total_tokens == 120

    def test_cache_creation_included(self):
        """cache_creation_input_tokens must contribute to input_tokens and cached_tokens."""
        adapter = self._make_adapter()
        msg = SimpleNamespace(usage=SimpleNamespace(
            input_tokens=50,
            output_tokens=30,
            cache_read_input_tokens=0,
            cache_creation_input_tokens=25,
        ))
        usage = adapter._extract_usage(msg)
        assert usage.input_tokens == 75  # 50 + 0 + 25
        assert usage.cached_tokens == 25  # 0 + 25
        assert usage.total_tokens == 105  # 75 + 30

    def test_none_usage(self):
        adapter = self._make_adapter()
        msg = SimpleNamespace(usage=None)
        assert adapter._extract_usage(msg) is None

    def test_no_usage_attr(self):
        adapter = self._make_adapter()
        msg = SimpleNamespace()
        assert adapter._extract_usage(msg) is None


class TestGeminiGenerateStreamUsageDrain:
    """Test that GeminiAdapter.generate_stream drains remaining chunks on function_calls."""

    def test_function_call_drains_stream_for_usage(self):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from src.agents.llm.gemini_client import GeminiAdapter
        from src.agents.llm.types import FunctionCall

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-argon"
        adapter._tracker = None
        adapter._is_thought_part = lambda part: getattr(part, "thought", False)
        adapter._estimate_tokens = lambda contents: 50
        adapter._convert_contents = lambda contents: contents
        adapter._build_config = MagicMock(return_value=None)

        chunk1 = SimpleNamespace(
            candidates=[SimpleNamespace(content=SimpleNamespace(parts=[SimpleNamespace(text=None, thought=False)]))],
            text=None,
            function_calls=[SimpleNamespace(name="classify_event", args={"domain": "complicated"})],
            usage_metadata=None,
        )
        chunk2 = SimpleNamespace(
            candidates=[],
            text=None,
            function_calls=[],
            usage_metadata=SimpleNamespace(
                prompt_token_count=100,
                candidates_token_count=20,
                thoughts_token_count=15,
                total_token_count=135,
            ),
        )

        async def mock_stream_iter():
            yield chunk1
            yield chunk2

        mock_client = MagicMock()
        mock_client.aio.models.generate_content_stream = AsyncMock(return_value=mock_stream_iter())
        adapter._client = mock_client

        async def run_test():
            chunks = []
            async for c in adapter.generate_stream("sys", "prompt", tools=[{"name": "classify_event"}]):
                chunks.append(c)
            return chunks

        chunks = asyncio.run(run_test())

        assert len(chunks) == 1
        fc_chunk = chunks[0]
        assert fc_chunk.function_call == FunctionCall(name="classify_event", args={"domain": "complicated"})
        assert fc_chunk.done is True
        assert fc_chunk.usage is not None
        assert fc_chunk.usage.total_tokens == 135
        assert fc_chunk.usage.thinking_tokens == 15
        assert fc_chunk.usage.output_tokens == 20
        assert fc_chunk.usage.input_tokens == 100

