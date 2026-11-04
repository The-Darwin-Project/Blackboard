# BlackBoard/tests/test_gemini_client_quota.py
# @ai-rules:
# 1. [Constraint]: Unit tests for GeminiAdapter quota acquisition budget (30s), _record_usage chokepoint, and stream rollback.
# 2. [Pattern]: Validates T-1 and T-2 using mocks for LLM client and QuotaTracker.
# 3. [Pattern]: TestBrainPriorityDerivation calls the production derive_llm_priority (llm/types.py, used by Brain._process_with_llm;
#    PRIORITY_HIGH=0, PRIORITY_NORMAL=1). Never copy the heuristic into the test.
"""Unit tests for GeminiAdapter quota decoupling and stream error rollback."""
import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.agents.llm.gemini_client import GeminiAdapter
from src.agents.llm.quota_tracker import QuotaExhaustedError, QuotaTracker, Reservation
from src.agents.llm.types import PRIORITY_HIGH, PRIORITY_NORMAL, derive_llm_priority


@pytest.fixture
def adapter():
    ad = GeminiAdapter.__new__(GeminiAdapter)
    ad._model_name = "gemini-2.5-flash"
    ad._project = "test-proj"
    ad._location = "us-central1"
    ad._tracker = MagicMock(spec=QuotaTracker)
    ad._client = MagicMock()
    return ad


class TestGeminiClientQuotaDecoupling:
    @pytest.mark.asyncio
    async def test_record_usage_rolls_back_on_none_or_zero_tokens(self, adapter):
        """_record_usage rolls back reservation when metadata is None or total_token_count is 0."""
        res = Reservation(id="res-1", tokens=2000, timestamp=100.0)

        # None metadata -> rollback
        adapter._record_usage(None, estimate=2000, reservation=res)
        adapter._tracker.rollback.assert_called_once_with(res)

        adapter._tracker.reset_mock()

        # Zero total tokens -> rollback
        zero_meta = MagicMock(total_token_count=0)
        adapter._record_usage(zero_meta, estimate=2000, reservation=res)
        adapter._tracker.rollback.assert_called_once_with(res)

    @pytest.mark.asyncio
    async def test_record_usage_records_when_total_tokens_positive(self, adapter):
        """_record_usage calls tracker.record with reservation when total_token_count > 0."""
        res = Reservation(id="res-2", tokens=2000, timestamp=100.0)
        meta = MagicMock(
            total_token_count=2500,
            prompt_token_count=1800,
            candidates_token_count=700,
            thoughts_token_count=0,
            cached_content_token_count=0,
            tool_use_prompt_token_count=0,
        )

        usage = adapter._record_usage(meta, estimate=2000, reservation=res)
        assert usage is not None
        assert usage.total_tokens == 2500
        adapter._tracker.record.assert_called_once_with(2500, 2000, reservation=res)
        adapter._tracker.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_generate_stream_timeout_rolls_back_reservation(self, adapter):
        """T-1: When stream iteration raises TimeoutError, finally block rolls back reservation."""
        res = Reservation(id="res-timeout", tokens=3000, timestamp=100.0)
        adapter._tracker.acquire = AsyncMock(return_value=res)

        async def mock_stream(*args, **kwargs):
            async def failing_stream():
                raise asyncio.TimeoutError("Stream timed out waiting for first chunk")
                yield  # pragma: no cover
            return failing_stream()

        adapter._client.aio.models.generate_content_stream = MagicMock(side_effect=mock_stream)

        with pytest.raises(asyncio.TimeoutError):
            async for _ in adapter.generate_stream(system_prompt="sys", contents="hello"):
                pass

        adapter._tracker.rollback.assert_called_with(res)

    @pytest.mark.asyncio
    async def test_acquire_budget_raises_quota_exhausted_error_on_timeout(self, adapter):
        """T-2: When tracker.acquire exceeds max_wait_seconds, QuotaExhaustedError is propagated."""
        adapter._tracker.acquire = AsyncMock(side_effect=QuotaExhaustedError("Quota wait exceeded 30s"))

        with pytest.raises(QuotaExhaustedError) as exc_info:
            async for _ in adapter.generate_stream(system_prompt="sys", contents="hello"):
                pass

        assert "Quota wait exceeded" in str(exc_info.value)
        adapter._tracker.acquire.assert_called_once()
        # Verify acquire was called with 30s timeout budget
        _, kwargs = adapter._tracker.acquire.call_args
        assert kwargs.get("max_wait_seconds") == 30.0


# ---------------------------------------------------------------------------
# H1: reservation lifecycle with a REAL QuotaTracker (no tracker mocks).
# Reservation is a frozen handle; "finalized" == no longer in _active_reservations.
# ---------------------------------------------------------------------------
from types import SimpleNamespace  # noqa: E402

ESTIMATE = 50


def _usage(total=135, prompt=100, candidates=20, thoughts=15):
    return SimpleNamespace(
        prompt_token_count=prompt,
        candidates_token_count=candidates,
        thoughts_token_count=thoughts,
        total_token_count=total,
    )


def _part(text=None):
    return SimpleNamespace(text=text, thought=False, function_call=None)


def _chunk(parts=None, text=None, function_calls=None, usage=None):
    candidates = []
    if parts is not None:
        candidates = [SimpleNamespace(content=SimpleNamespace(parts=parts), grounding_metadata=None)]
    return SimpleNamespace(
        candidates=candidates, text=text, function_calls=function_calls or [], usage_metadata=usage,
    )


def _fc(name="classify_event"):
    return SimpleNamespace(name=name, args={"domain": "complicated"})


def _response(usage=None, text="ok"):
    return SimpleNamespace(
        candidates=[SimpleNamespace(content=SimpleNamespace(parts=[_part(text)]))],
        function_calls=[],
        text=text,
        usage_metadata=usage,
    )


@pytest.fixture
def real_tracker():
    return QuotaTracker(tpm_limit=100000)


@pytest.fixture
def real_adapter(real_tracker):
    ad = GeminiAdapter.__new__(GeminiAdapter)
    ad._model_name = "gemini-2.5-flash"
    ad._tracker = real_tracker
    ad._estimate_tokens = lambda contents: ESTIMATE
    ad._convert_contents = lambda contents: contents
    ad._build_config = MagicMock(return_value=None)
    ad._client = MagicMock()
    return ad


def _set_stream(adapter, stream_factory):
    adapter._client.aio.models.generate_content_stream = AsyncMock(side_effect=lambda **kw: stream_factory())


def _assert_released(tracker):
    """Reservation finalized and fully rolled back: nothing active, window nets to zero."""
    stats = tracker.get_stats()
    assert stats["active_reservations"] == 0
    assert stats["tokens_used_60s"] == 0
    assert stats["total_tokens"] == 0


def _assert_recorded(tracker, actual):
    """Reservation finalized and window corrected from the estimate to the actual usage."""
    stats = tracker.get_stats()
    assert stats["active_reservations"] == 0
    assert stats["tokens_used_60s"] == actual
    assert stats["total_tokens"] == actual


class TestGenerateReservationLifecycle:
    @pytest.mark.asyncio
    async def test_acquire_called_with_30s_budget(self, real_adapter, real_tracker):
        real_tracker.acquire = AsyncMock(wraps=real_tracker.acquire)
        real_adapter._client.aio.models.generate_content = AsyncMock(return_value=_response(_usage()))

        await real_adapter.generate("sys", "hello")

        real_tracker.acquire.assert_awaited_once_with(ESTIMATE, max_wait_seconds=30.0, priority=PRIORITY_NORMAL)

    @pytest.mark.asyncio
    async def test_success_records_actual_and_clears_reservation(self, real_adapter, real_tracker):
        real_adapter._client.aio.models.generate_content = AsyncMock(return_value=_response(_usage(total=135)))

        resp = await real_adapter.generate("sys", "hello")

        assert resp.usage.total_tokens == 135
        _assert_recorded(real_tracker, 135)

    @pytest.mark.asyncio
    async def test_error_rolls_back_reservation(self, real_adapter, real_tracker):
        real_adapter._client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("boom"))

        with pytest.raises(RuntimeError, match="boom"):
            await real_adapter.generate("sys", "hello")

        _assert_released(real_tracker)

    @pytest.mark.asyncio
    async def test_missing_usage_metadata_rolls_back_reservation(self, real_adapter, real_tracker):
        real_adapter._client.aio.models.generate_content = AsyncMock(return_value=_response(usage=None))

        resp = await real_adapter.generate("sys", "hello")

        assert resp.usage is None
        _assert_released(real_tracker)

    @pytest.mark.asyncio
    async def test_quota_exhausted_propagates_and_leaves_no_reservation(self, real_adapter, real_tracker):
        real_tracker.acquire = AsyncMock(side_effect=QuotaExhaustedError("full"))
        real_adapter._client.aio.models.generate_content = AsyncMock()

        with pytest.raises(QuotaExhaustedError):
            await real_adapter.generate("sys", "hello")

        real_adapter._client.aio.models.generate_content.assert_not_awaited()
        assert real_tracker.get_stats()["active_reservations"] == 0


class TestGenerateStreamReservationLifecycle:
    @pytest.mark.asyncio
    async def test_acquire_called_with_30s_budget(self, real_adapter, real_tracker):
        real_tracker.acquire = AsyncMock(wraps=real_tracker.acquire)

        async def stream():
            yield _chunk(parts=[_part("hi")], text="hi", usage=_usage(total=90))

        _set_stream(real_adapter, stream)
        _ = [c async for c in real_adapter.generate_stream("sys", "hello")]

        real_tracker.acquire.assert_awaited_once_with(ESTIMATE, max_wait_seconds=30.0, priority=PRIORITY_NORMAL)

    @pytest.mark.asyncio
    async def test_success_takes_reservation_branch_and_corrects_window(self, real_adapter, real_tracker):
        """Real Reservation -> isinstance branch -> record(..., reservation=) pops it and corrects estimate->actual."""
        seen = []
        orig_record = real_tracker.record

        def spy(actual, estimated=0, reservation=None):
            seen.append(reservation)
            return orig_record(actual, estimated, reservation=reservation)

        real_tracker.record = spy

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])
            yield _chunk(usage=_usage(total=135))

        _set_stream(real_adapter, stream)
        chunks = [c async for c in real_adapter.generate_stream("sys", "hello")]

        assert chunks[-1].usage.total_tokens == 135
        assert len(seen) == 1 and isinstance(seen[0], Reservation)
        assert seen[0].tokens == ESTIMATE
        assert seen[0].id not in real_tracker._active_reservations  # finalized
        _assert_recorded(real_tracker, 135)

    @pytest.mark.asyncio
    async def test_success_window_shrinks_when_actual_below_estimate(self, real_adapter, real_tracker):
        async def stream():
            yield _chunk(parts=[_part("x")], text="x", usage=_usage(total=20))

        _set_stream(real_adapter, stream)
        _ = [c async for c in real_adapter.generate_stream("sys", "hello")]

        _assert_recorded(real_tracker, 20)

    @pytest.mark.asyncio
    async def test_early_aclose_before_usage_rolls_back(self, real_adapter, real_tracker):
        async def stream():
            yield _chunk(parts=[_part("partial")], text="partial")
            yield _chunk(parts=[_part("more")], text="more", usage=_usage(total=77))

        _set_stream(real_adapter, stream)
        gen = real_adapter.generate_stream("sys", "hello")
        first = await gen.__anext__()
        assert real_tracker.get_stats()["active_reservations"] == 1  # held mid-stream
        await gen.aclose()  # GeneratorExit at the yield, before usage metadata arrived

        assert first.text == "partial"
        _assert_released(real_tracker)

    @pytest.mark.asyncio
    async def test_early_aclose_after_usage_records_actual(self, real_adapter, real_tracker):
        async def stream():
            yield _chunk(parts=[_part("partial")], text="partial", usage=_usage(total=77))
            yield _chunk(parts=[_part("more")], text="more")

        _set_stream(real_adapter, stream)
        gen = real_adapter.generate_stream("sys", "hello")
        await gen.__anext__()
        await gen.aclose()

        _assert_recorded(real_tracker, 77)

    @pytest.mark.asyncio
    async def test_cancelled_error_mid_stream_rolls_back(self, real_adapter, real_tracker):
        started = asyncio.Event()

        async def stream():
            yield _chunk(parts=[_part("partial")], text="partial")
            started.set()
            await asyncio.Event().wait()  # hang until cancelled
            yield _chunk(parts=[_part("never")], text="never")  # pragma: no cover

        _set_stream(real_adapter, stream)

        async def consume():
            async for _ in real_adapter.generate_stream("sys", "hello"):
                pass

        task = asyncio.create_task(consume())
        await asyncio.wait_for(started.wait(), timeout=2.0)
        assert real_tracker.get_stats()["active_reservations"] == 1
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        _assert_released(real_tracker)

    @pytest.mark.asyncio
    async def test_failure_before_stream_created_rolls_back(self, real_adapter, real_tracker):
        real_adapter._client.aio.models.generate_content_stream = AsyncMock(side_effect=ConnectionError("no stream"))

        with pytest.raises(ConnectionError):
            async for _ in real_adapter.generate_stream("sys", "hello"):
                pass

        _assert_released(real_tracker)

    @pytest.mark.asyncio
    async def test_exception_during_consumption_rolls_back(self, real_adapter, real_tracker):
        async def stream():
            yield _chunk(parts=[_part("hello")], text="hello")
            raise ConnectionError("stream reset")

        _set_stream(real_adapter, stream)

        with pytest.raises(ConnectionError):
            async for _ in real_adapter.generate_stream("sys", "hello"):
                pass

        _assert_released(real_tracker)

    @pytest.mark.asyncio
    async def test_drain_abort_without_usage_rolls_back(self, real_adapter, real_tracker):
        """Function call held, tail chunk fails: call is still emitted, but no usage -> reservation rolled back."""
        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])
            raise ConnectionError("tail failure")

        _set_stream(real_adapter, stream)
        chunks = [c async for c in real_adapter.generate_stream("sys", "hello")]

        assert chunks[-1].function_call.name == "classify_event"
        assert chunks[-1].usage is None
        _assert_released(real_tracker)

    @pytest.mark.asyncio
    async def test_drain_timeout_without_usage_rolls_back(self, real_adapter, real_tracker, monkeypatch):
        monkeypatch.setenv("LLM_STREAM_DRAIN_TIMEOUT_SEC", "0.05")

        async def stream():
            yield _chunk(parts=[_part()], function_calls=[_fc()])
            await asyncio.sleep(5)  # trailing metadata never arrives within the drain budget
            yield _chunk(usage=_usage())  # pragma: no cover

        _set_stream(real_adapter, stream)
        chunks = [c async for c in real_adapter.generate_stream("sys", "hello")]

        assert chunks[-1].function_call is not None
        assert chunks[-1].usage is None
        _assert_released(real_tracker)

    @pytest.mark.asyncio
    async def test_close_stream_raising_still_releases_reservation(self, real_adapter, real_tracker):
        """_close_stream blowing up in the outer finally must not leak the reservation (finalized before it runs)."""
        async def stream():
            yield _chunk(parts=[_part("hello")], text="hello")
            raise ConnectionError("stream reset")

        _set_stream(real_adapter, stream)
        real_adapter._close_stream = AsyncMock(side_effect=RuntimeError("close exploded"))

        with pytest.raises(RuntimeError, match="close exploded"):
            async for _ in real_adapter.generate_stream("sys", "hello"):
                pass

        real_adapter._close_stream.assert_awaited_once()
        _assert_released(real_tracker)

    @pytest.mark.asyncio
    async def test_close_stream_raising_after_success_keeps_recorded_usage(self, real_adapter, real_tracker):
        async def stream():
            yield _chunk(parts=[_part("hi")], text="hi", usage=_usage(total=90))

        _set_stream(real_adapter, stream)
        real_adapter._close_stream = AsyncMock(side_effect=RuntimeError("close exploded"))

        with pytest.raises(RuntimeError, match="close exploded"):
            _ = [c async for c in real_adapter.generate_stream("sys", "hello")]

        _assert_recorded(real_tracker, 90)

    @pytest.mark.asyncio
    async def test_real_close_stream_swallows_aclose_failure(self, real_adapter, real_tracker):
        """Real _close_stream: an aclose() failure is logged, the stream result and accounting are unaffected."""
        class BadCloseStream:
            def __init__(self):
                self._chunks = [_chunk(parts=[_part("hi")], text="hi", usage=_usage(total=90))]

            def __aiter__(self):
                return self

            async def __anext__(self):
                if not self._chunks:
                    raise StopAsyncIteration
                return self._chunks.pop(0)

            async def aclose(self):
                raise RuntimeError("aclose failed")

        _set_stream(real_adapter, BadCloseStream)
        chunks = [c async for c in real_adapter.generate_stream("sys", "hello")]

        assert chunks[-1].done is True
        _assert_recorded(real_tracker, 90)


# ---------------------------------------------------------------------------
# Priority-aware token reservation forwarding and Claude conformance (Step 6)
# ---------------------------------------------------------------------------
from src.agents.llm.claude_client import ClaudeAdapter  # noqa: E402


class TestGeminiAndClaudePriorityForwarding:
    """Dave Farley ATDD Layer for Adapter Priority Forwarding and Conformance."""

    @pytest.mark.asyncio
    async def test_gemini_adapter_generate_forwards_priority(self, real_adapter, real_tracker):
        """GeminiAdapter.generate forwards priority argument to tracker.acquire."""
        real_tracker.acquire = AsyncMock(wraps=real_tracker.acquire)
        real_adapter._client.aio.models.generate_content = AsyncMock(return_value=_response(_usage()))

        await real_adapter.generate("sys", "hello", priority=0)

        real_tracker.acquire.assert_awaited_once_with(ESTIMATE, max_wait_seconds=30.0, priority=0)

    @pytest.mark.asyncio
    async def test_gemini_adapter_generate_stream_forwards_priority(self, real_adapter, real_tracker):
        """GeminiAdapter.generate_stream forwards priority argument to tracker.acquire."""
        real_tracker.acquire = AsyncMock(wraps=real_tracker.acquire)

        async def stream():
            yield _chunk(parts=[_part("hi")], text="hi", usage=_usage(total=90))

        _set_stream(real_adapter, stream)
        _ = [c async for c in real_adapter.generate_stream("sys", "hello", priority=0)]

        real_tracker.acquire.assert_awaited_once_with(ESTIMATE, max_wait_seconds=30.0, priority=0)

    @pytest.mark.asyncio
    async def test_claude_adapter_generate_accepts_priority(self):
        """ClaudeAdapter.generate accepts priority argument without error."""
        claude = ClaudeAdapter.__new__(ClaudeAdapter)
        claude._model_name = "claude-3-5-sonnet-v2@20241022"
        claude._client = MagicMock()

        # Mock messages.create response
        mock_msg = SimpleNamespace(
            content=[SimpleNamespace(type="text", text="hello from claude")],
            usage=SimpleNamespace(input_tokens=10, output_tokens=5),
        )
        claude._client.messages.create = AsyncMock(return_value=mock_msg)

        resp = await claude.generate("sys", "hello", priority=0)
        assert resp.text == "hello from claude"

    @pytest.mark.asyncio
    async def test_claude_adapter_generate_stream_accepts_priority(self):
        """ClaudeAdapter.generate_stream accepts priority argument without error."""
        claude = ClaudeAdapter.__new__(ClaudeAdapter)
        claude._model_name = "claude-3-5-sonnet-v2@20241022"
        claude._client = MagicMock()

        # Mock messages.stream context manager
        class MockClaudeStream:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc_val, exc_tb):
                pass

            @property
            def text_stream(self):
                async def text_gen():
                    yield "chunk1"
                return text_gen()

            async def get_final_message(self):
                return SimpleNamespace(
                    content=[SimpleNamespace(type="text", text="chunk1")],
                    usage=SimpleNamespace(input_tokens=10, output_tokens=5),
                )

        claude._client.messages.stream = MagicMock(return_value=MockClaudeStream())

        chunks = [c async for c in claude.generate_stream("sys", "hello", priority=0)]
        assert len(chunks) == 2
        assert chunks[0].text == "chunk1"
        assert chunks[1].done is True


class TestBrainPriorityDerivation:
    """Tests derive_llm_priority, the production helper called by Brain._process_with_llm.

    Brain computes priority once before its retry loop (PRIORITY_HIGH = 0, PRIORITY_NORMAL = 1). The tests call the
    real helper rather than a copy of the heuristic so they cannot drift from production.
    """

    @staticmethod
    def _event(source="headhunter", approved_by=None, conversation=None):
        return SimpleNamespace(source=source, approved_by=approved_by, conversation=conversation or [])

    def test_constants_match_documented_values(self):
        assert PRIORITY_HIGH == 0
        assert PRIORITY_NORMAL == 1

    @pytest.mark.parametrize("source", ["chat", "slack", "jarvis"])
    def test_interactive_sources_yield_priority_high(self, source):
        assert derive_llm_priority(self._event(source=source)) == PRIORITY_HIGH

    def test_approved_by_admin_yields_priority_high(self):
        assert derive_llm_priority(self._event(approved_by="admin")) == PRIORITY_HIGH

    @pytest.mark.parametrize("action", ["approve", "reject", "message"])
    def test_recent_user_action_yields_priority_high(self, action):
        """user approve / reject / message in the last 3 turns -> HIGH (message included for non-chat events)."""
        event = self._event(conversation=[SimpleNamespace(actor="user", action=action)])
        assert derive_llm_priority(event) == PRIORITY_HIGH

    @pytest.mark.parametrize("action", ["approve", "reject", "message"])
    def test_user_action_in_last_three_turns_yields_priority_high(self, action):
        turns = [
            SimpleNamespace(actor="headhunter", action="evidence"),
            SimpleNamespace(actor="user", action=action),
            SimpleNamespace(actor="brain", action="reply"),
        ]
        assert derive_llm_priority(self._event(conversation=turns)) == PRIORITY_HIGH

    def test_user_action_older_than_three_turns_does_not_boost_priority(self):
        """User turn at index -4 (outside the [-3:] window) does not elevate background priority."""
        turns = [
            SimpleNamespace(actor="user", action="approve"),
            SimpleNamespace(actor="brain", action="think"),
            SimpleNamespace(actor="brain", action="triage"),
            SimpleNamespace(actor="brain", action="reply"),
        ]
        assert derive_llm_priority(self._event(conversation=turns)) == PRIORITY_NORMAL

    def test_user_action_at_window_boundary_still_boosts(self):
        """User turn at index -3 is the oldest turn inside the window."""
        turns = [
            SimpleNamespace(actor="user", action="reject"),
            SimpleNamespace(actor="brain", action="think"),
            SimpleNamespace(actor="brain", action="reply"),
        ]
        assert derive_llm_priority(self._event(conversation=turns)) == PRIORITY_HIGH

    def test_dict_turns_are_supported(self):
        turns = [{"actor": "user", "action": "message"}]
        assert derive_llm_priority(self._event(conversation=turns)) == PRIORITY_HIGH

    @pytest.mark.parametrize("source", ["headhunter", "aligner", "timekeeper"])
    def test_background_events_without_user_activity_yield_priority_normal(self, source):
        assert derive_llm_priority(self._event(source=source)) == PRIORITY_NORMAL

    def test_non_user_actor_does_not_boost(self):
        turns = [SimpleNamespace(actor="brain", action="approve")]
        assert derive_llm_priority(self._event(conversation=turns)) == PRIORITY_NORMAL

    def test_missing_conversation_attribute_is_normal(self):
        event = SimpleNamespace(source="headhunter", approved_by=None, conversation=None)
        assert derive_llm_priority(event) == PRIORITY_NORMAL


class TestGeminiCallSyntaxFallback:
    """Tests regex fallback parsing for hallucinated [!call:name:{args}!] tool calls."""

    @pytest.mark.asyncio
    async def test_generate_parses_call_syntax_and_cleans_text(self):
        from src.agents.llm.gemini_client import GeminiAdapter
        from unittest.mock import AsyncMock, MagicMock

        adapter = GeminiAdapter(model_name="test-gemini", project="p", location="l")
        mock_response = MagicMock()
        mock_response.function_calls = []
        mock_response.text = 'Closing now! [!call:set_phase:{"phase": "close", "reasoning": "done"}!]'
        mock_response.candidates = []
        mock_response.usage_metadata = None

        adapter._client = MagicMock()
        adapter._client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        res = await adapter.generate(
            system_prompt="sys",
            contents="user prompt",
        )

        assert res.function_call is not None
        assert res.function_call.name == "set_phase"
        assert res.function_call.args == {"phase": "close", "reasoning": "done"}
        assert res.text == "Closing now!"

    @pytest.mark.asyncio
    async def test_generate_stream_parses_call_syntax_and_strips_chunks(self):
        from src.agents.llm.gemini_client import GeminiAdapter
        from unittest.mock import AsyncMock, MagicMock

        adapter = GeminiAdapter(model_name="test-gemini", project="p", location="l")

        chunk1 = MagicMock()
        chunk1.text = "All resolved. "
        chunk1.candidates = []
        chunk1.function_calls = []
        chunk1.usage_metadata = None

        chunk2 = MagicMock()
        chunk2.text = '[!call:close_event:{"summary": "All fixed"}!]'
        chunk2.candidates = []
        chunk2.function_calls = []
        chunk2.usage_metadata = None

        async def fake_stream():
            yield chunk1
            yield chunk2

        stream_mock = MagicMock()
        stream_mock.__aiter__ = lambda self: fake_stream()

        adapter._client = MagicMock()
        adapter._client.aio.models.generate_content_stream = AsyncMock(return_value=stream_mock)

        received_chunks = []
        async for chunk in adapter.generate_stream(
            system_prompt="sys",
            contents="user prompt",
        ):
            received_chunks.append(chunk)

        assert received_chunks[0].text == "All resolved. "
        terminal = received_chunks[-1]
        assert terminal.done is True
        assert terminal.function_call is not None
        assert terminal.function_call.name == "close_event"
        assert terminal.function_call.args == {"summary": "All fixed"}

