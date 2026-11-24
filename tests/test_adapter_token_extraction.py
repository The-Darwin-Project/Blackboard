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
        adapter._model_name = "gemini-4-carbon"
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
        adapter._model_name = "gemini-4-carbon"
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
        tracker.acquire.assert_awaited_once()
        assert tracker.acquire.await_args.args[0] == 50
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




class TestGeminiStreamReservationPaths:
    """H1: both tracker contracts in generate_stream.

    - Real QuotaTracker -> acquire() returns a Reservation -> record(..., reservation=) finalizes it.
    - Legacy/mock tracker whose acquire() returns a non-Reservation -> record(actual, estimate) fallback, no rollback.
    """

    @staticmethod
    def _adapter(stream_factory, tracker):
        from unittest.mock import AsyncMock, MagicMock
        from src.agents.llm.gemini_client import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-carbon"
        adapter._tracker = tracker
        adapter._estimate_tokens = lambda contents: 50
        adapter._convert_contents = lambda contents: contents
        adapter._build_config = MagicMock(return_value=None)
        client = MagicMock()
        client.aio.models.generate_content_stream = AsyncMock(side_effect=lambda **kw: stream_factory())
        adapter._client = client
        return adapter

    @staticmethod
    def _collect(adapter):
        import asyncio

        async def run():
            return [c async for c in adapter.generate_stream("sys", "prompt")]

        return asyncio.run(run())

    def test_real_reservation_path_finalizes_via_reservation_kwarg(self):
        from src.agents.llm.quota_tracker import QuotaTracker, Reservation

        tracker = QuotaTracker(tpm_limit=100000)
        recorded = []
        orig = tracker.record

        def spy(actual, estimated=0, reservation=None):
            recorded.append((actual, estimated, reservation))
            return orig(actual, estimated, reservation=reservation)

        tracker.record = spy

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])
            yield _chunk(usage=_usage(total=135))

        chunks = self._collect(self._adapter(stream, tracker))

        assert chunks[-1].usage.total_tokens == 135
        assert len(recorded) == 1
        actual, estimate, reservation = recorded[0]
        assert (actual, estimate) == (135, 50)
        assert isinstance(reservation, Reservation)
        stats = tracker.get_stats()
        assert stats["active_reservations"] == 0
        assert stats["tokens_used_60s"] == 135

    def test_real_reservation_without_usage_is_rolled_back_not_recorded(self):
        from src.agents.llm.quota_tracker import QuotaTracker

        tracker = QuotaTracker(tpm_limit=100000)

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])

        chunks = self._collect(self._adapter(stream, tracker))

        assert chunks[-1].usage is None
        stats = tracker.get_stats()
        assert stats["active_reservations"] == 0
        assert stats["tokens_used_60s"] == 0

    def test_legacy_non_reservation_fallback_records_without_reservation(self):
        tracker = TestGeminiGenerateStreamDrainHardening._tracker()  # acquire() -> AsyncMock default, not a Reservation

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])
            yield _chunk(usage=_usage(total=135))

        self._collect(self._adapter(stream, tracker))

        tracker.record.assert_called_once_with(135, 50)  # no reservation kwarg on the legacy path
        tracker.rollback.assert_not_called()

    def test_legacy_non_reservation_without_usage_does_not_rollback(self):
        tracker = TestGeminiGenerateStreamDrainHardening._tracker()

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])

        self._collect(self._adapter(stream, tracker))

        tracker.record.assert_not_called()
        tracker.rollback.assert_not_called()  # rollback is Reservation-only


class TestGemini4DrainAndTrailingThoughtSignature:
    """T-1: Gemini 4 drain & trailing empty-carrier thoughtSignature reassembly onto raw_parts."""

    @staticmethod
    def _stream_and_collect_parts(chunks_list):
        import asyncio
        from unittest.mock import AsyncMock, MagicMock
        from src.agents.llm.gemini_client import GeminiAdapter

        async def _sdk_stream():
            for ch in chunks_list:
                yield ch

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-carbon"
        adapter._tracker = None
        adapter._estimate_tokens = lambda contents: 50
        adapter._convert_contents = lambda contents: contents
        adapter._build_config = MagicMock(return_value=None)
        client = MagicMock()
        client.aio.models.generate_content_stream = AsyncMock(side_effect=lambda **kw: _sdk_stream())
        adapter._client = client

        async def _run():
            return [c async for c in adapter.generate_stream("sys", "prompt", tools=[{"name": "classify_event"}])]

        return asyncio.run(_run())

    @staticmethod
    def _has_empty_carrier(parts) -> bool:
        for p in parts:
            text = p.get("text") if isinstance(p, dict) else getattr(p, "text", None)
            fc = p.get("functionCall") if isinstance(p, dict) else getattr(p, "function_call", None)
            thought = bool(p.get("thought")) if isinstance(p, dict) else (getattr(p, "thought", None) is True)
            if not text and fc is None and not thought:
                return True
        return False

    def test_t1_single_fc_drain_signature_attaches_to_fc_and_strips_empty_carrier(self):
        from google.genai import types
        from src.agents.context_parts import normalize_response_parts

        fc = types.FunctionCall(name="classify_event", args={"domain": "complicated"})
        fc_part = types.Part(function_call=fc, thought_signature=None)
        drain_carrier = types.Part(text="", thought_signature=b"xyz")

        chunks = self._stream_and_collect_parts([
            _chunk(parts=[fc_part], function_calls=[fc]),
            _chunk(parts=[drain_carrier], usage=_usage(total=135)),
        ])

        done_chunk = chunks[-1]
        assert done_chunk.done is True
        assert done_chunk.function_call is not None
        assert done_chunk.function_call.name == "classify_event"
        assert fc_part.thought_signature is None, "original SDK Part must be cloned, not mutated in place"
        assert done_chunk.raw_parts is not None and len(done_chunk.raw_parts) == 1
        assert not self._has_empty_carrier(done_chunk.raw_parts)
        assert done_chunk.raw_parts[-1].function_call.name == "classify_event"
        assert done_chunk.raw_parts[-1].thought_signature == b"xyz"

        normalized = normalize_response_parts(done_chunk.raw_parts)
        assert normalized[-1]["functionCall"]["name"] == "classify_event"
        assert normalized[-1]["thought_signature"] == "eHl6"

    def test_t1_text_only_trailing_carrier_preserves_text_and_attaches_signature(self):
        from google.genai import types
        from src.agents.context_parts import normalize_response_parts

        hello_part = types.Part(text="hello")
        trailing_carrier = types.Part(text="", thought_signature=b"xyz")

        chunks = self._stream_and_collect_parts([
            _chunk(parts=[hello_part], text="hello"),
            _chunk(parts=[trailing_carrier], text="", usage=_usage(total=60)),
        ])

        done_chunk = chunks[-1]
        assert done_chunk.done is True
        assert hello_part.thought_signature is None
        assert done_chunk.raw_parts is not None and len(done_chunk.raw_parts) == 1
        assert not self._has_empty_carrier(done_chunk.raw_parts)
        assert done_chunk.raw_parts[0].text == "hello"
        assert done_chunk.raw_parts[0].thought_signature == b"xyz"

        normalized = normalize_response_parts(done_chunk.raw_parts)
        assert normalized == [{"text": "hello", "thought_signature": "eHl6"}]

    def test_t1_thought_only_stream_with_trailing_carrier_and_dict_is_thought_part(self):
        from google.genai import types
        from src.agents.context_parts import normalize_response_parts
        from src.agents.llm.gemini_client import GeminiAdapter

        assert GeminiAdapter._is_thought_part({"thought": True, "text": "..."}) is True
        assert GeminiAdapter._is_thought_part({"thought": False, "text": "..."}) is False
        assert GeminiAdapter._is_thought_part({"text": "..."}) is False

        thought_part = types.Part(thought=True, text="thinking")
        trailing_carrier = types.Part(text="", thought_signature=b"xyz")

        chunks = self._stream_and_collect_parts([
            _chunk(parts=[thought_part]),
            _chunk(parts=[trailing_carrier], usage=_usage(total=50)),
        ])

        done_chunk = chunks[-1]
        assert done_chunk.done is True
        assert done_chunk.raw_parts is not None and len(done_chunk.raw_parts) >= 1
        assert not self._has_empty_carrier(done_chunk.raw_parts)
        assert done_chunk.raw_parts[-1].thought_signature == b"xyz"

        normalized = normalize_response_parts(done_chunk.raw_parts)
        assert normalized[-1]["thought_signature"] == "eHl6"

    def test_cr04_text_followed_by_empty_thought_signature_carrier_preserves_hello_part(self):
        from google.genai import types
        from src.agents.context_parts import normalize_response_parts

        hello_part = types.Part(text="Hello")
        thought_sig_carrier = types.Part(thought=True, text="", thought_signature=b"sig")

        chunks = self._stream_and_collect_parts([
            _chunk(parts=[hello_part], text="Hello"),
            _chunk(parts=[thought_sig_carrier], text="", usage=_usage(total=45)),
        ])

        done_chunk = chunks[-1]
        assert done_chunk.done is True
        non_thought = [p for p in (done_chunk.raw_parts or []) if not getattr(p, "thought", False)]
        assert len(non_thought) == 1
        assert non_thought[0].text == "Hello"
        assert non_thought[0].thought_signature == b"sig"

        normalized = normalize_response_parts(done_chunk.raw_parts)
        assert any(p.get("text") == "Hello" and p.get("thought_signature") == "c2ln" for p in normalized)

    def test_cr14_dict_thought_yields_and_sig_v2_parallel_fc_suppresses_dropped_warning(self, monkeypatch, caplog):
        from google.genai import types
        from src.agents.llm.gemini_client import GeminiAdapter

        # 1. __new__ GeminiAdapter without _model_name/_tracker coerces model_version="" safely
        bare_ad = GeminiAdapter.__new__(GeminiAdapter)
        usage = bare_ad._record_usage(_usage(total=40, prompt=20, candidates=20), estimate=20)
        assert usage is not None and usage.model_version == ""

        # 2. Dict thought part yields LLMChunk(text=..., is_thought=True)
        chunks_dict = self._stream_and_collect_parts([
            _chunk(parts=[{"thought": True, "text": "dict thought step"}, {"text": "done"}], text="done"),
        ])
        thought_chunks = [c for c in chunks_dict if c.is_thought]
        assert len(thought_chunks) == 1 and thought_chunks[0].text == "dict thought step"

        # 3. BRAIN_THOUGHT_SIG_V2=true suppresses warning on single-chunk parallel FCs, warns on drain FC
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        fc1 = types.FunctionCall(name="tool_1", args={})
        fc2 = types.FunctionCall(name="tool_2", args={})
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            self._stream_and_collect_parts([
                _chunk(parts=[types.Part(function_call=fc1), types.Part(function_call=fc2)], function_calls=[fc1, fc2]),
            ])
        assert "additional function_call" not in caplog.text

        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="src.agents.llm.gemini_client"):
            self._stream_and_collect_parts([
                _chunk(parts=[types.Part(function_call=fc1)], function_calls=[fc1]),
                _chunk(parts=[types.Part(function_call=fc2)], function_calls=[fc2]),
            ])
        assert "1 additional function_call" in caplog.text


# ---------------------------------------------------------------------------
# VMER-2450 Step 10 (4-Layer ATDD): T-35, T-36 & Helm BRAIN_DECAY_EPOCH_SIZE
# ---------------------------------------------------------------------------

def _record_has_structured_field(record: logging.LogRecord, key: str, value: str) -> bool:
    """Layer 2 DSL helper: verify structured log field in message or LogRecord extra."""
    import re

    msg = record.getMessage()
    pattern = rf"\b{re.escape(key)}[=:]\s*['\"]?{re.escape(value)}(?:%|['\"]|\b|$)"
    if re.search(pattern, msg):
        return True
    extra_val = getattr(record, key, None)
    return extra_val is not None and str(extra_val) == value


class _RecordingLogHandler(logging.Handler):
    """Layer 3 driver: captures emitted LogRecords and invocation order."""

    def __init__(self, order_events: list[str]):
        super().__init__(level=logging.DEBUG)
        self.records: list[logging.LogRecord] = []
        self._order_events = order_events

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
        self._order_events.append(f"log:{record.levelname}")


class TestT35CallerAwareCacheLogging:
    """T-35: Caller-aware structured cache logging in src/agents/llm/__init__.py:record_token_usage."""

    @staticmethod
    def _invoke_record_token_usage(
        monkeypatch,
        *,
        caller: str,
        usage: TokenUsage,
        event_id: str | None,
    ) -> tuple[list[str], list[tuple], list[logging.LogRecord]]:
        import src.agents.llm as llm_pkg

        order_events: list[str] = []
        meter_calls: list[tuple] = []

        class _FakeMeter:
            def record(self, c, model, u, eid=None):
                order_events.append("record")
                meter_calls.append((c, model, u, eid))

        monkeypatch.setattr(llm_pkg, "get_token_meter", lambda: _FakeMeter())

        target_logger = logging.getLogger("src.agents.llm")
        prev_level = target_logger.level
        handler = _RecordingLogHandler(order_events)
        target_logger.setLevel(logging.DEBUG)
        target_logger.addHandler(handler)
        try:
            llm_pkg.record_token_usage(caller, usage, event_id)
        finally:
            target_logger.removeHandler(handler)
            target_logger.setLevel(prev_level)
        return order_events, meter_calls, handler.records

    def test_t35_brain_caller_records_meter_before_info_log_and_gemini_stays_debug_only(
        self, monkeypatch, caplog
    ):
        """Given brain caller with 27k/30k cached tokens and 50 thinking tokens,
        When GeminiAdapter._record_usage extracts usage and record_token_usage runs,
        Then TokenMeter.record fires BEFORE the 1-line INFO log carrying all 7 fields,
        and GeminiAdapter._record_usage emits ZERO INFO logs (no duplicate INFO)."""
        from unittest.mock import MagicMock
        from src.agents.llm.gemini_client import GeminiAdapter

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        adapter._model_name = "gemini-4-neon"
        adapter._tracker = MagicMock()
        adapter._tracker.get_stats.return_value = {"utilization_pct": 12}

        meta = SimpleNamespace(
            prompt_token_count=30000,
            candidates_token_count=120,
            cached_content_token_count=27000,
            thoughts_token_count=50,
            tool_use_prompt_token_count=0,
            total_token_count=30170,
        )
        with caplog.at_level(logging.DEBUG, logger="src.agents.llm.gemini_client"):
            usage = adapter._record_usage(meta, estimate=29000)

        assert usage is not None
        gemini_info_records = [
            r for r in caplog.records
            if r.name == "src.agents.llm.gemini_client" and r.levelno >= logging.INFO
        ]
        assert gemini_info_records == [], "GeminiAdapter._record_usage must stay debug-only"

        order_events, meter_calls, records = self._invoke_record_token_usage(
            monkeypatch, caller="brain", usage=usage, event_id="evt-1"
        )

        assert meter_calls == [("brain", "gemini-4-neon", usage, "evt-1")]
        assert order_events == ["record", "log:INFO"], (
            f"TokenMeter.record must run strictly before INFO log; got {order_events}"
        )
        info_records = [r for r in records if r.levelno == logging.INFO]
        assert len(info_records) == 1
        rec = info_records[0]
        assert "\n" not in rec.getMessage(), "Brain INFO log must be concise single-line"
        for key, expected in (
            ("caller", "brain"),
            ("event_id", "evt-1"),
            ("input_tokens", "30000"),
            ("cached_tokens", "27000"),
            ("cache_hit_pct", "90.0"),
            ("thinking_tokens", "50"),
            ("output_tokens", "120"),
        ):
            assert _record_has_structured_field(rec, key, expected), (
                f"Missing structured field {key}={expected!r} in log: {rec.getMessage()!r}"
            )

    def test_t35_non_brain_callers_record_first_and_log_at_debug_only(self, monkeypatch):
        """Given non-brain callers ('aligner', 'headhunter'),
        When record_token_usage runs,
        Then TokenMeter.record fires first and structured cache log emits at DEBUG (never INFO)."""
        usage = TokenUsage(
            input_tokens=10000,
            output_tokens=200,
            cached_tokens=5000,
            thinking_tokens=25,
            total_tokens=10225,
            model_version="gemini-4-argon",
        )
        for caller, event_id in (("aligner", "evt-align-1"), ("headhunter", "evt-hh-2")):
            order_events, meter_calls, records = self._invoke_record_token_usage(
                monkeypatch, caller=caller, usage=usage, event_id=event_id
            )
            assert meter_calls == [(caller, "gemini-4-argon", usage, event_id)]
            assert order_events == ["record", "log:DEBUG"], (
                f"Expected record then DEBUG log for {caller}; got {order_events}"
            )
            assert [r for r in records if r.levelno >= logging.INFO] == [], (
                f"Non-brain caller {caller!r} must NOT emit INFO+ log"
            )
            debug_records = [r for r in records if r.levelno == logging.DEBUG]
            assert len(debug_records) == 1
            rec = debug_records[0]
            for key, expected in (
                ("caller", caller),
                ("event_id", event_id),
                ("input_tokens", "10000"),
                ("cached_tokens", "5000"),
                ("cache_hit_pct", "50.0"),
                ("thinking_tokens", "25"),
                ("output_tokens", "200"),
            ):
                assert _record_has_structured_field(rec, key, expected), (
                    f"Missing structured field {key}={expected!r} in DEBUG log: {rec.getMessage()!r}"
                )

    def test_t35_zero_input_tokens_logs_zero_cache_hit_pct_safely(self, monkeypatch):
        """Given TokenUsage with input_tokens=0,
        When record_token_usage('brain', ...) runs,
        Then no ZeroDivisionError occurs, meter updates first, and INFO log reports cache_hit_pct=0.0."""
        usage = TokenUsage(
            input_tokens=0,
            output_tokens=0,
            cached_tokens=0,
            thinking_tokens=0,
            total_tokens=0,
            model_version="gemini-4-neon",
        )
        order_events, meter_calls, records = self._invoke_record_token_usage(
            monkeypatch, caller="brain", usage=usage, event_id="evt-zero"
        )
        assert meter_calls == [("brain", "gemini-4-neon", usage, "evt-zero")]
        assert order_events == ["record", "log:INFO"]
        info_records = [r for r in records if r.levelno == logging.INFO]
        assert len(info_records) == 1
        rec = info_records[0]
        assert _record_has_structured_field(rec, "input_tokens", "0")
        assert _record_has_structured_field(rec, "cached_tokens", "0")
        assert _record_has_structured_field(rec, "cache_hit_pct", "0.0")


class TestT36ClaudeStructuredMultiFCAndEventStateParity:
    """T-36: ClaudeAdapter._convert_structured FIFO pending_tool_ids & <event_state> parity."""

    @staticmethod
    def _shape_claude_wire(contents: list[dict]) -> list[dict]:
        from src.agents.llm.claude_client import ClaudeAdapter

        return ClaudeAdapter._convert_structured(contents)

    def test_t36_single_fc_colocated_fr_and_event_state_orders_tool_result_before_other_blocks(self):
        """Given single-FC model turn followed by user turn with co-located [FR_1, text(<event_state>)]
        (and also reversed [text, FR_1, image]),
        When ClaudeAdapter._convert_structured runs,
        Then tool_result maps to exact tool_use ID 'call_1' and is emitted strictly BEFORE text/image blocks."""
        contents = [
            {"role": "user", "parts": [{"text": "Initial anchor"}]},
            {
                "role": "model",
                "parts": [
                    {"functionCall": {"name": "lookup_service", "args": {"service_name": "payments"}}}
                ],
            },
            {
                "role": "user",
                "parts": [
                    {"functionResponse": {"name": "lookup_service", "response": {"result": "healthy"}}},
                    {"text": "<event_state>\nStatus: active\n</event_state>"},
                ],
            },
        ]
        messages = self._shape_claude_wire(contents)
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        assert messages[1]["content"] == [
            {
                "type": "tool_use",
                "id": "call_1",
                "name": "lookup_service",
                "input": {"service_name": "payments"},
            }
        ]
        user_blocks = messages[2]["content"]
        assert len(user_blocks) == 2
        assert user_blocks[0]["type"] == "tool_result"
        assert user_blocks[0]["tool_use_id"] == "call_1"
        assert "healthy" in user_blocks[0]["content"]
        assert user_blocks[1] == {"type": "text", "text": "<event_state>\nStatus: active\n</event_state>"}

        # Reversed input order [text, FR_1, image]: tool_result MUST still precede text and image.
        reversed_contents = [
            {"role": "user", "parts": [{"text": "Initial anchor"}]},
            {
                "role": "model",
                "parts": [{"functionCall": {"name": "lookup_service", "args": {}}}],
            },
            {
                "role": "user",
                "parts": [
                    {"text": "<event_state>\nStatus: active\n</event_state>"},
                    {"functionResponse": {"name": "lookup_service", "response": {"result": "healthy"}}},
                    {"bytes": b"\x89PNG", "mime_type": "image/png"},
                ],
            },
        ]
        rev_messages = self._shape_claude_wire(reversed_contents)
        rev_blocks = rev_messages[2]["content"]
        assert [b["type"] for b in rev_blocks] == ["tool_result", "text", "image"]
        assert rev_blocks[0]["tool_use_id"] == "call_1"
        assert "healthy" in rev_blocks[0]["content"]

    def test_t36_parallel_2fc_batch_fifo_pads_unconsumed_and_coalesces_trailing_event_state(self):
        """Given 2-FC parallel batch model([FC_1, FC_2]) -> user([FR_1]) -> trailing user(<event_state>),
        When ClaudeAdapter._convert_structured runs,
        Then FIFO assigns call_1/call_2, FR_1 pops call_1, unconsumed call_2 is padded inside the FR
        user turn BEFORE text/image blocks, and trailing <event_state> coalesces cleanly without double user."""
        # Case A: partial FR_1 + separate trailing user(<event_state>)
        contents = [
            {"role": "user", "parts": [{"text": "Initial anchor"}]},
            {
                "role": "model",
                "parts": [
                    {"functionCall": {"name": "lookup_service", "args": {"service_name": "payments"}}},
                    {"functionCall": {"name": "lookup_journal", "args": {"service": "payments"}}},
                ],
            },
            {
                "role": "user",
                "parts": [
                    {"functionResponse": {"name": "lookup_service", "response": {"result": "svc-ok"}}},
                ],
            },
            {
                "role": "user",
                "parts": [{"text": "<event_state>\nPhase: dispatch\n</event_state>"}],
            },
        ]
        messages = self._shape_claude_wire(contents)
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        assert [(b["id"], b["name"]) for b in messages[1]["content"]] == [
            ("call_1", "lookup_service"),
            ("call_2", "lookup_journal"),
        ]
        user_blocks = messages[2]["content"]
        assert [b["type"] for b in user_blocks] == ["tool_result", "tool_result", "text"]
        assert user_blocks[0]["tool_use_id"] == "call_1"
        assert "svc-ok" in user_blocks[0]["content"]
        assert user_blocks[1]["tool_use_id"] == "call_2"
        assert user_blocks[1]["content"]  # non-empty padded result
        assert user_blocks[2] == {"type": "text", "text": "<event_state>\nPhase: dispatch\n</event_state>"}

        # Case B: partial FR_1 + co-located text + image -> padded call_2 precedes co-located other_blocks
        colocated = [
            {"role": "user", "parts": [{"text": "Initial anchor"}]},
            {
                "role": "model",
                "parts": [
                    {"functionCall": {"name": "lookup_service", "args": {}}},
                    {"functionCall": {"name": "lookup_journal", "args": {}}},
                ],
            },
            {
                "role": "user",
                "parts": [
                    {"functionResponse": {"name": "lookup_service", "response": {"result": "svc-ok"}}},
                    {"text": "<skill_overlay>\ndispatch\n</skill_overlay>"},
                    {"bytes": b"img", "mime_type": "image/png"},
                ],
            },
        ]
        col_messages = self._shape_claude_wire(colocated)
        col_blocks = col_messages[2]["content"]
        assert [b["type"] for b in col_blocks] == ["tool_result", "tool_result", "text", "image"]
        assert [b["tool_use_id"] for b in col_blocks[:2]] == ["call_1", "call_2"]
        assert "svc-ok" in col_blocks[0]["content"]

        # Case C: full 2-FC [FR_1, FR_2] + trailing separate user(<event_state>)
        full_batch = [
            {"role": "user", "parts": [{"text": "Initial anchor"}]},
            {
                "role": "model",
                "parts": [
                    {"functionCall": {"name": "lookup_service", "args": {}}},
                    {"functionCall": {"name": "lookup_journal", "args": {}}},
                ],
            },
            {
                "role": "user",
                "parts": [
                    {"functionResponse": {"name": "lookup_service", "response": {"result": "svc-ok"}}},
                    {"functionResponse": {"name": "lookup_journal", "response": {"result": "journal-ok"}}},
                ],
            },
            {
                "role": "user",
                "parts": [{"text": "<event_state>\nPhase: verify\n</event_state>"}],
            },
        ]
        full_messages = self._shape_claude_wire(full_batch)
        assert [m["role"] for m in full_messages] == ["user", "assistant", "user"]
        full_blocks = full_messages[2]["content"]
        assert [b["type"] for b in full_blocks] == ["tool_result", "tool_result", "text"]
        assert full_blocks[0]["tool_use_id"] == "call_1" and "svc-ok" in full_blocks[0]["content"]
        assert full_blocks[1]["tool_use_id"] == "call_2" and "journal-ok" in full_blocks[1]["content"]
        assert full_blocks[2]["text"] == "<event_state>\nPhase: verify\n</event_state>"

    def test_t36_consecutive_coalesced_model_turns_preserve_pending_tool_ids(self):
        """Given consecutive model([FC_1]) followed immediately by model([FC_2]),
        When ClaudeAdapter._convert_structured runs,
        Then pending_tool_ids is NOT reset across coalesced assistant turns and maps call_1/call_2 FIFO."""
        contents = [
            {"role": "user", "parts": [{"text": "Start"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "tool_a", "args": {"x": 1}}}]},
            {"role": "model", "parts": [{"functionCall": {"name": "tool_b", "args": {"y": 2}}}]},
            {
                "role": "user",
                "parts": [
                    {"functionResponse": {"name": "tool_a", "response": {"result": "res-a"}}},
                    {"functionResponse": {"name": "tool_b", "response": {"result": "res-b"}}},
                ],
            },
        ]
        messages = self._shape_claude_wire(contents)
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        assert [(b["id"], b["name"]) for b in messages[1]["content"]] == [
            ("call_1", "tool_a"),
            ("call_2", "tool_b"),
        ]
        user_blocks = messages[2]["content"]
        assert [b["type"] for b in user_blocks] == ["tool_result", "tool_result"]
        assert user_blocks[0]["tool_use_id"] == "call_1" and "res-a" in user_blocks[0]["content"]
        assert user_blocks[1]["tool_use_id"] == "call_2" and "res-b" in user_blocks[1]["content"]

    def test_t36_user_turn_without_fr_wraps_text_for_all_pending_ids_and_clears_queue(self):
        """Given pending_tool_ids=[call_1, call_2] and a user turn with NO functionResponse parts,
        When ClaudeAdapter._convert_structured runs,
        Then text is wrapped into tool_result blocks for EACH pending ID, pending_tool_ids is cleared,
        and a subsequent trailing user(<event_state>) coalesces as a text block (not tool_result)."""
        contents = [
            {"role": "user", "parts": [{"text": "Start"}]},
            {
                "role": "model",
                "parts": [
                    {"functionCall": {"name": "tool_a", "args": {}}},
                    {"functionCall": {"name": "tool_b", "args": {}}},
                ],
            },
            {"role": "user", "parts": [{"text": "Human interrupted before tool output"}]},
            {"role": "user", "parts": [{"text": "<event_state>\nStatus: active\n</event_state>"}]},
        ]
        messages = self._shape_claude_wire(contents)
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        user_blocks = messages[2]["content"]
        assert [b["type"] for b in user_blocks] == ["tool_result", "tool_result", "text"]
        assert [b["tool_use_id"] for b in user_blocks[:2]] == ["call_1", "call_2"]
        assert "Human interrupted before tool output" in user_blocks[0]["content"]
        assert "Human interrupted before tool output" in user_blocks[1]["content"]
        assert user_blocks[2] == {"type": "text", "text": "<event_state>\nStatus: active\n</event_state>"}

    def test_t36_extra_fr_with_empty_pending_tool_ids_falls_back_safely(self):
        """Given extra functionResponse when pending_tool_ids is empty (or orphan FR),
        When ClaudeAdapter._convert_structured runs,
        Then it falls back cleanly to synthetic call_{counter} without raising IndexError."""
        contents = [
            {"role": "user", "parts": [{"text": "Start"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "tool_a", "args": {}}}]},
            {
                "role": "user",
                "parts": [
                    {"functionResponse": {"name": "tool_a", "response": {"result": "res-a"}}},
                    {"functionResponse": {"name": "extra_tool", "response": {"result": "res-extra"}}},
                ],
            },
        ]
        messages = self._shape_claude_wire(contents)
        assert [m["role"] for m in messages] == ["user", "assistant", "user"]
        user_blocks = messages[2]["content"]
        assert len(user_blocks) == 2
        assert user_blocks[0]["type"] == "tool_result"
        assert user_blocks[0]["tool_use_id"] == "call_1"
        assert "res-a" in user_blocks[0]["content"]
        assert user_blocks[1]["type"] == "tool_result"
        assert user_blocks[1]["tool_use_id"].startswith("call_")
        assert "res-extra" in user_blocks[1]["content"]

        # Orphan FR with zero preceding model FCs
        orphan = self._shape_claude_wire([
            {"role": "user", "parts": [{"functionResponse": {"name": "orphan", "response": {"result": "orphan-res"}}}]}
        ])
        assert len(orphan) == 1
        assert orphan[0]["content"][0]["type"] == "tool_result"
        assert orphan[0]["content"][0]["tool_use_id"].startswith("call_")
        assert "orphan-res" in orphan[0]["content"][0]["content"]


class TestStep10HelmDecayEpochSizeWiring:
    """Step 10 Helm env wiring: brain.decayEpochSize defaults to '10' and wires BRAIN_DECAY_EPOCH_SIZE."""

    def test_step10_helm_decay_epoch_size_wired_in_values_and_deployment(self):
        """Given helm/values.yaml and helm/templates/deployment.yaml,
        When parsed (and rendered via helm template if available),
        Then brain.decayEpochSize defaults to '10' and BRAIN_DECAY_EPOCH_SIZE is wired from it."""
        from pathlib import Path
        import shutil
        import subprocess
        import yaml

        repo_root = Path(__file__).resolve().parent.parent
        values = yaml.safe_load((repo_root / "helm" / "values.yaml").read_text(encoding="utf-8"))
        assert isinstance(values.get("brain"), dict)
        assert values["brain"].get("decayEpochSize") == "10", (
            f"Expected helm/values.yaml brain.decayEpochSize='10', got {values['brain'].get('decayEpochSize')!r}"
        )

        deploy_lines = (repo_root / "helm" / "templates" / "deployment.yaml").read_text(encoding="utf-8").splitlines()
        env_idx = next(
            (i for i, line in enumerate(deploy_lines) if "- name: BRAIN_DECAY_EPOCH_SIZE" in line),
            None,
        )
        assert env_idx is not None, "BRAIN_DECAY_EPOCH_SIZE env entry missing from helm/templates/deployment.yaml"
        value_line = deploy_lines[env_idx + 1] if env_idx + 1 < len(deploy_lines) else ""
        assert ".Values.brain.decayEpochSize" in value_line, (
            f"BRAIN_DECAY_EPOCH_SIZE must be wired from .Values.brain.decayEpochSize, got: {value_line!r}"
        )

        if shutil.which("helm"):
            proc = subprocess.run(
                ["helm", "template", "darwin", "helm"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            assert proc.returncode == 0, f"helm template failed: {proc.stderr}"
            docs = [d for d in yaml.safe_load_all(proc.stdout) if isinstance(d, dict)]
            dep = next(d for d in docs if d.get("kind") == "Deployment")
            brain_container = next(
                c for c in dep["spec"]["template"]["spec"]["containers"]
                if any(e.get("name") == "BRAIN_CONTENT_BUDGET_TOKENS" for e in c.get("env", []))
            )
            env_map = {e["name"]: e.get("value") for e in brain_container.get("env", [])}
            assert env_map.get("BRAIN_DECAY_EPOCH_SIZE") == "10"



class TestR1L5AdapterTokenExtraction:
    def test_r1_l5_convert_structured_coalesces_user_tool_results_first(self):
        """[R1-L5] _convert_structured groups tool_result blocks strictly before text blocks when 
        coalescing multiple user messages (e.g. text message followed by FR-bearing message)."""
        from src.agents.llm.claude_client import ClaudeAdapter
        
        contents = [
            {
                "role": "user",
                "parts": [{"text": "Hello text 1"}]
            },
            {
                "role": "user",
                "parts": [
                    {"functionResponse": {"name": "tool1", "response": {"res": "ok"}}},
                    {"text": "Hello text 2"}
                ]
            }
        ]
        
        wire = ClaudeAdapter._convert_structured(contents)
        
        assert len(wire) == 1
        msg = wire[0]
        assert msg["role"] == "user"
        
        # Verify order: tool_results must come before text
        # ClaudeAdapter parts is a list of blocks.
        seen_text = False
        for part in msg["content"]:
            if part.get("type") if isinstance(part, dict) else getattr(part, "type", part.__class__.__name__) == "tool_result":
                assert not seen_text, "tool_result block found after a text block"
            elif part.get("type") if isinstance(part, dict) else getattr(part, "type", part.__class__.__name__) == "text":
                seen_text = True
