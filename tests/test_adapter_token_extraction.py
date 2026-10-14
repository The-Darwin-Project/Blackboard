# tests/test_adapter_token_extraction.py
"""Direct tests for GeminiAdapter._record_usage() and ClaudeAdapter._extract_usage()."""
import logging
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



def _usage(total=135, prompt=100, candidates=20, thoughts=15):
    return SimpleNamespace(
        prompt_token_count=prompt,
        candidates_token_count=candidates,
        thoughts_token_count=thoughts,
        total_token_count=total,
    )


def _part(text=None, thought=False, function_call=None):
    return SimpleNamespace(text=text, thought=thought, function_call=function_call)


def _chunk(parts=None, text=None, function_calls=None, usage=None, grounding=None):
    candidates = []
    if parts is not None or grounding is not None:
        candidates = [SimpleNamespace(
            content=SimpleNamespace(parts=parts) if parts is not None else None,
            grounding_metadata=grounding,
        )]
    return SimpleNamespace(
        candidates=candidates, text=text, function_calls=function_calls or [], usage_metadata=usage,
    )


def _fc(name="classify_event", args=None):
    return SimpleNamespace(name=name, args=args if args is not None else {"domain": "complicated"})


class TestGeminiGenerateStreamDrainHardening:
    """Drain behaviour of GeminiAdapter.generate_stream after a function_call chunk.

    Uses the real _is_thought_part / _record_usage; only the SDK client and tracker are faked.
    """

    def _adapter(self, chunks_factory, tracker=None):
        from unittest.mock import AsyncMock, MagicMock
        from src.agents.llm.gemini_client import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-argon"
        adapter._tracker = tracker
        adapter._estimate_tokens = lambda contents: 50
        adapter._convert_contents = lambda contents: contents
        adapter._build_config = MagicMock(return_value=None)
        client = MagicMock()
        client.aio.models.generate_content_stream = AsyncMock(side_effect=lambda **kw: chunks_factory())
        adapter._client = client
        return adapter

    @staticmethod
    def _tracker():
        from unittest.mock import AsyncMock, MagicMock
        tracker = MagicMock()
        tracker.acquire = AsyncMock()
        tracker.get_stats.return_value = {"utilization_pct": 1}
        return tracker

    @staticmethod
    def _collect(adapter):
        import asyncio

        async def run():
            return [c async for c in adapter.generate_stream("sys", "prompt", tools=[{"name": "classify_event"}])]

        return asyncio.run(run())

    def test_drained_thought_parts_are_yielded_and_kept_in_raw_parts(self):
        fc_part = _part(function_call=_fc())
        early_thought = _part("early", thought=True)
        late_thought = _part("late", thought=True)

        async def stream():
            yield _chunk(parts=[early_thought, fc_part], function_calls=[_fc()])
            yield _chunk(parts=[late_thought], usage=_usage())

        chunks = self._collect(self._adapter(stream))

        thoughts = [c for c in chunks if c.is_thought]
        assert [c.text for c in thoughts] == ["early", "late"]
        final = chunks[-1]
        assert final.done is True
        assert final.function_call.name == "classify_event"
        # Thoughts first, then the function-call part: fc part (thought_signature carrier) is not displaced
        assert final.raw_parts == [early_thought, late_thought, fc_part]
        assert final.usage.total_tokens == 135

    def test_mid_drain_exception_still_emits_function_call(self):
        tracker = self._tracker()

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()], usage=_usage(total=120))
            raise ConnectionError("stream reset")

        chunks = self._collect(self._adapter(stream, tracker=tracker))

        assert len(chunks) == 1
        assert chunks[0].function_call.name == "classify_event"
        assert chunks[0].done is True
        # Usage seen before the failure is still reported and recorded
        assert chunks[0].usage.total_tokens == 120
        tracker.record.assert_called_once_with(120, 50)

    def test_stalled_drain_times_out_and_emits_function_call(self):
        import asyncio
        tracker = self._tracker()

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])
            await asyncio.sleep(30)
            yield _chunk(usage=_usage())

        adapter = self._adapter(stream, tracker=tracker)
        adapter.DRAIN_TIMEOUT_S = 0.05

        chunks = asyncio.run(asyncio.wait_for(self._run(adapter), timeout=5))

        assert len(chunks) == 1
        assert chunks[0].function_call.name == "classify_event"
        assert chunks[0].usage is None  # terminal usage never arrived
        tracker.record.assert_not_called()

    @staticmethod
    async def _run(adapter):
        return [c async for c in adapter.generate_stream("sys", "prompt", tools=[{"name": "classify_event"}])]

    def test_exception_before_function_call_propagates(self):
        async def stream():
            yield _chunk(parts=[_part("hello")], text="hello")
            raise ConnectionError("stream reset")

        import pytest
        with pytest.raises(ConnectionError):
            self._collect(self._adapter(stream))

    def test_tracker_records_once_on_clean_function_call_drain(self):
        tracker = self._tracker()

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])
            yield _chunk(usage=_usage(total=135))

        chunks = self._collect(self._adapter(stream, tracker=tracker))

        assert chunks[-1].usage.total_tokens == 135
        tracker.acquire.assert_awaited_once_with(50)
        tracker.record.assert_called_once_with(135, 50)

    def test_tracker_records_when_consumer_closes_early(self):
        import asyncio
        tracker = self._tracker()

        async def stream():
            yield _chunk(parts=[_part("partial")], text="partial", usage=_usage(total=77))
            yield _chunk(parts=[_part("more")], text="more")

        adapter = self._adapter(stream, tracker=tracker)

        async def run():
            gen = adapter.generate_stream("sys", "prompt")
            first = await gen.__anext__()
            await gen.aclose()
            return first

        first = asyncio.run(run())

        assert first.text == "partial"
        tracker.record.assert_called_once_with(77, 50)

    def test_text_only_stream_unchanged(self):
        tracker = self._tracker()
        part1, part2 = _part("Hel"), _part("lo")

        async def stream():
            yield _chunk(parts=[part1], text="Hel")
            yield _chunk(parts=[part2], text="lo", usage=_usage(total=60, prompt=40, candidates=None, thoughts=5))

        chunks = self._collect(self._adapter(stream, tracker=tracker))

        assert [c.text for c in chunks if c.text] == ["Hel", "lo"]
        final = chunks[-1]
        assert final.done is True
        assert final.function_call is None
        assert final.raw_parts == [part2]
        # candidates_token_count None on final chunk -> derived from total (@ai-rules 10)
        assert final.usage.output_tokens == 15
        tracker.record.assert_called_once_with(60, 50)

    def test_function_call_without_terminal_usage_chunk(self):
        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])

        chunks = self._collect(self._adapter(stream))

        assert len(chunks) == 1
        assert chunks[0].function_call.name == "classify_event"
        assert chunks[0].usage is None

    def test_extra_function_calls_and_late_text_are_dropped_and_logged(self, caplog):
        import logging
        first = _fc("first_tool", {"a": 1})
        fc_part = _part(function_call=first)

        async def stream():
            yield _chunk(parts=[fc_part], function_calls=[first, _fc("second_tool")])
            yield _chunk(parts=[_part("late text")], text="late text", function_calls=[_fc("third_tool")], usage=_usage())

        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            chunks = self._collect(self._adapter(stream))

        assert len(chunks) == 1  # late text is not surfaced
        assert chunks[0].function_call.name == "first_tool"
        assert chunks[0].function_call.args == {"a": 1}
        assert chunks[0].raw_parts == [fc_part]  # last_parts frozen at the function-call chunk
        assert "2 additional function_call" in caplog.text

    def test_drained_grounding_is_captured(self):
        gm = SimpleNamespace(
            web_search_queries=["q"],
            grounding_chunks=[SimpleNamespace(web=SimpleNamespace(title="T", uri="http://x"))],
        )

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])
            yield _chunk(grounding=gm, usage=_usage())

        chunks = self._collect(self._adapter(stream))

        assert chunks[-1].grounding_metadata == {"queries": ["q"], "chunks": [{"title": "T", "uri": "http://x"}]}

    # --- Stream close on every exit (@ai-rules 15) ---

    @staticmethod
    def _spy(chunks, *, hang_after=None, raise_after=None, raise_exc=None, aclose_exc=None):
        import asyncio

        class SpyStream:
            """SDK stream stand-in that records whether aclose() was awaited."""

            def __init__(self):
                self.aclose_awaited = 0
                self._i = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if hang_after is not None and self._i >= hang_after:
                    await asyncio.Event().wait()
                if raise_after is not None and self._i >= raise_after:
                    raise raise_exc if raise_exc is not None else ConnectionError("read failed")
                if self._i >= len(chunks):
                    raise StopAsyncIteration
                self._i += 1
                return chunks[self._i - 1]

            async def aclose(self):
                self.aclose_awaited += 1
                if aclose_exc:
                    raise aclose_exc

        return SpyStream()

    def test_consumer_aclose_mid_stream_closes_sdk_stream_and_records_usage(self):
        import asyncio
        tracker = self._tracker()
        spy = self._spy([
            _chunk(parts=[_part("partial")], text="partial", usage=_usage(total=77)),
            _chunk(parts=[_part("more")], text="more"),
        ])
        adapter = self._adapter(lambda: spy, tracker=tracker)

        async def run():
            gen = adapter.generate_stream("sys", "prompt")
            await gen.__anext__()
            await gen.aclose()

        asyncio.run(run())

        assert spy.aclose_awaited == 1
        tracker.record.assert_called_once_with(77, 50)

    def test_brain_style_timeout_while_stalled_closes_sdk_stream_and_records_usage(self):
        import asyncio
        tracker = self._tracker()
        spy = self._spy([_chunk(parts=[_part("hi")], text="hi", usage=_usage(total=64))], hang_after=1)
        adapter = self._adapter(lambda: spy, tracker=tracker)

        async def run():
            gen = adapter.generate_stream("sys", "prompt")
            await asyncio.wait_for(gen.__anext__(), timeout=1)
            with __import__("pytest").raises(asyncio.TimeoutError):
                await asyncio.wait_for(gen.__anext__(), timeout=0.05)  # Brain's per-chunk wait_for

        asyncio.run(run())

        assert spy.aclose_awaited == 1
        tracker.record.assert_called_once_with(64, 50)

    def test_read_error_before_function_call_propagates_and_closes_sdk_stream(self):
        import pytest
        spy = self._spy([_chunk(parts=[_part("hi")], text="hi")], raise_after=1)
        adapter = self._adapter(lambda: spy)

        with pytest.raises(ConnectionError):
            self._collect(adapter)

        assert spy.aclose_awaited == 1

    def test_malformed_trailing_grounding_during_drain_emits_function_call(self):
        tracker = self._tracker()
        bad_grounding = SimpleNamespace(web_search_queries=["q"], grounding_chunks=[SimpleNamespace(web=object())])
        spy = self._spy([
            _chunk(parts=[_part()], function_calls=[_fc()]),
            # web has no .title/.uri -> AttributeError while parsing; terminal usage rides on the same chunk
            _chunk(grounding=bad_grounding, usage=_usage(total=135)),
        ])
        adapter = self._adapter(lambda: spy, tracker=tracker)

        chunks = self._collect(adapter)

        assert len(chunks) == 1
        assert chunks[0].function_call.name == "classify_event"
        assert chunks[0].usage.total_tokens == 135
        tracker.record.assert_called_once_with(135, 50)
        assert spy.aclose_awaited == 1

    def test_aclose_failure_is_logged_not_raised(self, caplog):
        import logging
        spy = self._spy([_chunk(parts=[_part()], function_calls=[_fc()], usage=_usage())],
                        aclose_exc=RuntimeError("boom"))
        adapter = self._adapter(lambda: spy)

        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            chunks = self._collect(adapter)

        assert chunks[-1].function_call.name == "classify_event"
        assert spy.aclose_awaited == 1
        assert "Gemini stream close failed" in caplog.text

    def test_drain_cancellation_emits_pending_function_call(self, caplog):
        """T-1: Mid-drain cancellation preserves captured tool call."""
        import asyncio
        import logging
        tracker = self._tracker()
        spy = self._spy(
            [_chunk(parts=[_part()], function_calls=[_fc()])],
            raise_after=1,
            raise_exc=asyncio.CancelledError(),
        )
        adapter = self._adapter(lambda: spy, tracker=tracker)

        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            chunks = self._collect(adapter)

        assert len(chunks) == 1
        assert chunks[0].function_call.name == "classify_event"
        assert chunks[0].done is True
        assert spy.aclose_awaited == 1
        assert "Gemini stream drain interrupted" in caplog.text
        assert "CancelledError" in caplog.text

    def test_pre_function_call_cancellation_propagates(self):
        """T-2: Pre-tool-call cancellation propagates immediately."""
        import asyncio
        import pytest
        spy = self._spy([], raise_after=0, raise_exc=asyncio.CancelledError())
        adapter = self._adapter(lambda: spy)

        with pytest.raises(asyncio.CancelledError):
            self._collect(adapter)

        assert spy.aclose_awaited == 1

    def test_close_stream_shielded_under_cancellation(self, caplog):
        """T-3a: Stream cleanup shielded under outer task cancellation."""
        import asyncio
        import logging
        from src.agents.llm.gemini_client import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter.ACLOSE_TIMEOUT_S = 0.5

        aclose_completed = False

        class SlowStream:
            async def aclose(self):
                nonlocal aclose_completed
                await asyncio.sleep(0.05)
                aclose_completed = True

        stream = SlowStream()

        async def run():
            task = asyncio.create_task(adapter._close_stream(stream))
            await asyncio.sleep(0.01)
            task.cancel()
            await task
            await asyncio.sleep(0.06)

        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            asyncio.run(run())

        assert aclose_completed is True
        assert "Gemini stream close failed" in caplog.text
        assert "CancelledError" in caplog.text

    def test_close_stream_bounded_on_hang(self, caplog):
        """T-3b: Stream cleanup bounded by ACLOSE_TIMEOUT_S when aclose hangs."""
        import asyncio
        import logging
        from src.agents.llm.gemini_client import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter.ACLOSE_TIMEOUT_S = 0.05

        class HangingStream:
            def __init__(self):
                self.cancelled = False

            async def aclose(self):
                try:
                    await asyncio.Event().wait()
                except asyncio.CancelledError:
                    self.cancelled = True
                    raise

        stream = HangingStream()

        async def run():
            await asyncio.wait_for(adapter._close_stream(stream), timeout=1.0)

        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            asyncio.run(run())

        assert "Gemini stream close failed" in caplog.text
        assert "TimeoutError" in caplog.text
        assert stream.cancelled is True

    def test_drain_timeout_env_var_override(self, monkeypatch):
        """T-4: Drain timeout dynamically configurable via environment variable."""
        import asyncio
        from unittest.mock import patch

        monkeypatch.setenv("LLM_STREAM_DRAIN_TIMEOUT_SEC", "3.0")
        recorded_timeouts = []
        real_wait_for = asyncio.wait_for

        async def spy_wait_for(fut, timeout=None):
            if timeout is not None:
                recorded_timeouts.append(timeout)
            return await real_wait_for(fut, timeout=timeout)

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])
            yield _chunk(usage=_usage(total=100))

        adapter = self._adapter(stream)
        with patch("src.agents.llm.gemini_client.asyncio.wait_for", side_effect=spy_wait_for):
            chunks = self._collect(adapter)

        assert len(chunks) == 1
        assert chunks[0].function_call.name == "classify_event"
        assert len(recorded_timeouts) >= 1
        assert 2.5 <= recorded_timeouts[0] <= 3.0

    def test_clean_stream_eof_does_not_log_drain_interruption(self, caplog):
        """T-6: Clean stream EOF breaks cleanly without logging drain interruption warning."""
        import logging
        tracker = self._tracker()
        spy = self._spy([_chunk(parts=[_part()], function_calls=[_fc()])])
        adapter = self._adapter(lambda: spy, tracker=tracker)

        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            chunks = self._collect(adapter)

        assert len(chunks) == 1
        assert chunks[0].function_call.name == "classify_event"
        assert chunks[0].done is True
        assert spy.aclose_awaited == 1
        assert "Gemini stream drain interrupted" not in caplog.text
        assert "Gemini stream drain timeout expired" not in caplog.text

    def test_parse_drain_timeout_validation(self, caplog):
        """CR-2: _parse_drain_timeout validates input, guards against NaN/Inf/empty/bounds, falls back safely."""
        from src.agents.llm.gemini_client import _parse_drain_timeout

        assert _parse_drain_timeout(None, default=15.0) == 15.0
        assert _parse_drain_timeout("", default=15.0) == 15.0
        assert _parse_drain_timeout("   ", default=15.0) == 15.0
        assert _parse_drain_timeout("10.5", default=15.0) == 10.5
        assert _parse_drain_timeout("300.0", default=15.0) == 300.0

        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            assert _parse_drain_timeout("not-a-number", default=15.0) == 15.0
            assert "Malformed LLM_STREAM_DRAIN_TIMEOUT_SEC" in caplog.text

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            assert _parse_drain_timeout("nan", default=15.0) == 15.0
            assert _parse_drain_timeout("inf", default=15.0) == 15.0
            assert _parse_drain_timeout("-inf", default=15.0) == 15.0
            assert _parse_drain_timeout("-1.0", default=15.0) == 15.0
            assert _parse_drain_timeout("0.0", default=15.0) == 15.0
            assert _parse_drain_timeout("500.0", default=15.0) == 15.0
            assert "Invalid LLM_STREAM_DRAIN_TIMEOUT_SEC" in caplog.text

    def test_drain_timeout_log_formatting_timeout_vs_cancelled(self, caplog):
        """CR-5: TimeoutError logs 'timed out', CancelledError logs 'cancelled'."""
        import asyncio
        tracker = self._tracker()

        # 1. Stalled drain -> TimeoutError logs 'timed out'
        stalled_spy = self._spy([_chunk(parts=[_part()], function_calls=[_fc()])], hang_after=1)
        adapter = self._adapter(lambda: stalled_spy, tracker=tracker)
        adapter.DRAIN_TIMEOUT_S = 0.05

        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            chunks = self._collect(adapter)

        assert len(chunks) == 1
        assert "Gemini stream drain interrupted (TimeoutError: timed out)" in caplog.text or "timed out" in caplog.text
        assert "TimeoutError: cancelled" not in caplog.text

        # 2. CancelledError during drain -> logs 'cancelled'
        caplog.clear()
        cancelled_spy = self._spy(
            [_chunk(parts=[_part()], function_calls=[_fc()])],
            raise_after=1,
            raise_exc=asyncio.CancelledError(),
        )
        adapter2 = self._adapter(lambda: cancelled_spy, tracker=tracker)
        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            chunks2 = self._collect(adapter2)

        assert len(chunks2) == 1
        assert "Gemini stream drain interrupted (CancelledError: cancelled)" in caplog.text

    def test_candidate_parsing_usage_metadata_exception_preserves_function_call(self, caplog):
        """CR-3: Exception during usage_metadata read preserves pending_fc."""
        tracker = self._tracker()

        class FaultyChunk:
            text = None
            function_calls = None

            @property
            def usage_metadata(self):
                raise RuntimeError("Corrupted usage metadata")

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])
            yield FaultyChunk()

        adapter = self._adapter(stream, tracker=tracker)
        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            chunks = self._collect(adapter)

        assert len(chunks) == 1
        assert chunks[0].function_call.name == "classify_event"
        assert chunks[0].done is True
        assert "Gemini stream drain candidate parsing failed" in caplog.text
        assert "RuntimeError" in caplog.text


