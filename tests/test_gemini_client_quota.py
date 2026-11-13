# BlackBoard/tests/test_gemini_client_quota.py
# @ai-rules:
# 1. [Constraint]: Unit tests for GeminiAdapter quota acquisition budget (30s), _record_usage chokepoint, and stream rollback.
# 2. [Pattern]: Validates T-1 and T-2 using mocks for LLM client and QuotaTracker.
# 3. [Pattern]: TestBrainPriorityDerivation calls the production derive_llm_priority (llm/types.py, used by Brain._process_with_llm;
#    PRIORITY_HIGH=0, PRIORITY_NORMAL=1). Never copy the heuristic into the test.
# 4. [Pattern]: TestCallSyntaxLinearTime / TestHoldbackOverflowNeverLeaks / TestFallbackAllowlist / TestCallSyntaxLogHygiene guard PR #309:
#    linear-time [!call: scanning, discard-not-flush on holdback overflow, fail-closed tool allowlist, no raw model text in logs.
# 5. [Pattern]: TestUnaryMaxOutputTokensCeiling spies on real_adapter._build_config (5th positional arg) to pin the unary 32768 clamp +
#    warning vs the unclamped 65000 stream path. TestBrainDefaultModelMatchesHelm parses brain.py/helm values (no Brain import) so the
#    default model cannot drift. TestGemini4UnaryStreamAndAssemble pins CR-02/CR-03/CR-04/CR-09/CR-14 unary stream-and-assemble contracts.
"""Unit tests for GeminiAdapter quota decoupling and stream error rollback."""
import asyncio
import shutil
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

    @pytest.mark.asyncio
    async def test_generate_parses_nested_json_call_syntax(self):
        """Exercises nested objects and arrays in call syntax (guards against non-greedy regex truncation)."""
        from src.agents.llm.gemini_client import GeminiAdapter
        from unittest.mock import AsyncMock, MagicMock

        adapter = GeminiAdapter(model_name="test-gemini", project="p", location="l")
        mock_response = MagicMock()
        mock_response.function_calls = []
        mock_response.text = (
            'Creating plan now: [!call:create_plan:{"title": "Deploy Service", '
            '"steps": [{"id": 1, "cmd": "apply"}, {"id": 2, "cmd": "rollout"}], '
            '"meta": {"author": "darwin"}}!] Please wait.'
        )
        mock_response.candidates = []
        mock_response.usage_metadata = None

        adapter._client = MagicMock()
        adapter._client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        res = await adapter.generate(
            system_prompt="sys",
            contents="user prompt",
        )

        assert res.function_call is not None
        assert res.function_call.name == "create_plan"
        assert res.function_call.args == {
            "title": "Deploy Service",
            "steps": [{"id": 1, "cmd": "apply"}, {"id": 2, "cmd": "rollout"}],
            "meta": {"author": "darwin"},
        }
        assert res.text == "Creating plan now:  Please wait."

    @pytest.mark.asyncio
    async def test_generate_stream_handles_split_tag_across_chunks(self):
        """Verifies partial call syntax split across provider chunks is not leaked to live stream."""
        from src.agents.llm.gemini_client import GeminiAdapter
        from unittest.mock import AsyncMock, MagicMock

        adapter = GeminiAdapter(model_name="test-gemini", project="p", location="l")

        chunk1 = MagicMock()
        chunk1.text = "Wrapping up work now. [!call:set_"
        chunk1.candidates = []
        chunk1.function_calls = []
        chunk1.usage_metadata = None

        chunk2 = MagicMock()
        chunk2.text = 'phase:{"phase": "close", "reasoning": "all tasks done"}!] Have a good day!'
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

        # Non-terminal text chunks must NEVER contain [!call: or tag fragments
        text_chunks = [c.text for c in received_chunks if c.text]
        assert "[!call:" not in "".join(text_chunks)
        assert "phase:{" not in "".join(text_chunks)
        assert "".join(text_chunks).strip() == "Wrapping up work now.  Have a good day!"

        terminal = received_chunks[-1]
        assert terminal.done is True
        assert terminal.function_call is not None
        assert terminal.function_call.name == "set_phase"
        assert terminal.function_call.args == {"phase": "close", "reasoning": "all tasks done"}

    @pytest.mark.asyncio
    async def test_generate_unparseable_call_syntax_does_not_reemit_raw_syntax(self):
        """When call syntax fails JSON decode, clean_text is None and raw syntax is never re-emitted."""
        from src.agents.llm.gemini_client import GeminiAdapter
        from unittest.mock import AsyncMock, MagicMock

        adapter = GeminiAdapter(model_name="test-gemini", project="p", location="l")
        mock_response = MagicMock()
        mock_response.function_calls = []
        # Entire text is an invalid call block (not valid JSON args)
        mock_response.text = '[!call:broken_tool:{not valid json}!] '
        mock_response.candidates = []
        mock_response.usage_metadata = None

        adapter._client = MagicMock()
        adapter._client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        res = await adapter.generate(
            system_prompt="sys",
            contents="user prompt",
        )

        assert res.function_call is None
        # Must NOT fall back to response.text containing the raw [!call:...] block
        assert res.text is None

    def test_process_stream_call_syntax_buffer_unit(self):
        """Unit test for process_stream_call_syntax_buffer logic."""
        from src.agents.llm.types import process_stream_call_syntax_buffer

        # Normal text yields immediately
        to_yield, buf = process_stream_call_syntax_buffer("Hello world!")
        assert to_yield == "Hello world!"
        assert buf == ""

        # Trailing bracket held back
        to_yield, buf = process_stream_call_syntax_buffer("Click here: [")
        assert to_yield == "Click here: "
        assert buf == "["

        # Incomplete tag held back
        to_yield, buf = process_stream_call_syntax_buffer("Closing now: [!call:set_phase:{")
        assert to_yield == "Closing now: "
        assert buf == "[!call:set_phase:{"

        # Complete tag stripped
        to_yield, buf = process_stream_call_syntax_buffer(buf + '"phase": "close"}!] Done.')
        assert to_yield == " Done."
        assert buf == ""

    def test_sanitize_call_syntax_strips_unterminated_fragment(self):
        """Unclosed [!call: tag at end of string (e.g. truncated response) is stripped."""
        from src.agents.llm.types import sanitize_call_syntax

        # Completed tag stripped
        assert sanitize_call_syntax('Clean text [!call:tool:{"a": 1}!]') == "Clean text"

        # Trailing unterminated tag stripped
        assert sanitize_call_syntax('Output before truncated [!call:set_phase:{"phase":') == "Output before truncated"
        assert sanitize_call_syntax('[!call:set_phase:') is None
        assert sanitize_call_syntax('[!call:') is None

    def test_extract_call_syntax_validates_tools_whitelist(self):
        """_extract_call_syntax rejects tool calls not present in declared tools."""
        from src.agents.llm.gemini_client import _extract_call_syntax

        declared_tools = [
            {"name": "set_phase", "description": "Set phase", "input_schema": {}},
            {"name": "close_event", "description": "Close", "input_schema": {}},
        ]

        # Valid tool name in whitelist is parsed
        fc, text = _extract_call_syntax(
            'Closing: [!call:set_phase:{"phase": "close"}!]',
            tools=declared_tools,
        )
        assert fc is not None
        assert fc.name == "set_phase"
        assert text == "Closing:"

        # Unknown tool name is rejected
        fc_unknown, text_unknown = _extract_call_syntax(
            'Injected: [!call:evil_tool:{"cmd": "rm"}!]',
            tools=declared_tools,
        )
        assert fc_unknown is None
        assert text_unknown == "Injected:"

        # Unterminated tag in text is cleanly stripped even when no valid call exists
        fc_trunc, text_trunc = _extract_call_syntax(
            'Truncated response [!call:set_phase:{"phase":',
            tools=declared_tools,
        )
        assert fc_trunc is None
        assert text_trunc == "Truncated response"


# =============================================================================
# PR #309 remediation: ReDoS, holdback overflow, fail-closed allowlist, log hygiene
# =============================================================================

_DECLARED_TOOLS = [
    {"name": "set_phase", "description": "Set phase", "input_schema": {"type": "object", "properties": {}}},
    {"name": "close_event", "description": "Close", "input_schema": {"type": "object", "properties": {}}},
]


def _text_chunk(text):
    c = MagicMock()
    c.text = text
    c.candidates = []
    c.function_calls = []
    c.usage_metadata = None
    return c


def _stream_adapter(texts):
    ad = GeminiAdapter(model_name="test-gemini", project="p", location="l")

    async def fake_stream():
        for t in texts:
            yield _text_chunk(t)

    stream_mock = MagicMock()
    stream_mock.__aiter__ = lambda self: fake_stream()
    ad._client = MagicMock()
    ad._client.aio.models.generate_content_stream = AsyncMock(return_value=stream_mock)
    return ad


async def _drain(ad, **kwargs):
    return [c async for c in ad.generate_stream(system_prompt="sys", contents="user prompt", **kwargs)]


def _generate_adapter(text):
    ad = GeminiAdapter(model_name="test-gemini", project="p", location="l")
    resp = MagicMock()
    resp.function_calls = []
    resp.text = text
    resp.candidates = []
    resp.usage_metadata = None
    ad._client = MagicMock()
    ad._client.aio.models.generate_content = AsyncMock(return_value=resp)
    return ad


class TestCallSyntaxLinearTime:
    """HIGH #1: unterminated [!call: input must be stripped in linear time (no regex backtracking)."""

    @pytest.mark.parametrize(
        "payload",
        [
            "[!call:a:" + " " * 50000,
            "[!call:a:" + " \n\t" * 20000,
            "[!call:a:" + "!" * 50000,
            "[!call:a:" * 6000,
            "[!call:" * 8000,
            "ok [!call:abc" + "d" * 50000,
        ],
    )
    def test_unterminated_input_is_linear(self, payload):
        import time
        from src.agents.llm.gemini_client import _extract_call_syntax
        from src.agents.llm.types import (
            process_stream_call_syntax_buffer,
            sanitize_call_syntax,
            scan_call_syntax,
        )

        start = time.perf_counter()
        cleaned = sanitize_call_syntax(payload)
        fc, text = _extract_call_syntax(payload, tools=_DECLARED_TOOLS)
        process_stream_call_syntax_buffer(payload)
        scan_call_syntax(payload)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.5, f"call-syntax handling took {elapsed:.2f}s (superlinear?)"
        assert fc is None
        for out in (cleaned, text):
            assert out is None or "[!call:" not in out

    def test_many_complete_tags_are_linear(self):
        import time
        from src.agents.llm.types import sanitize_call_syntax

        payload = "x[!call:a:{}!]" * 20000
        start = time.perf_counter()
        out = sanitize_call_syntax(payload)
        assert time.perf_counter() - start < 0.5
        assert out == "x" * 20000

    def test_scan_matches_previous_regex_semantics_for_wellformed_tags(self):
        from src.agents.llm.types import scan_call_syntax

        clean, calls, tail = scan_call_syntax('A [!call:set_phase:  {"p": 1}  !] B [!call:x_1:!] C')
        assert clean == "A  B  C"
        assert calls == [("set_phase", '{"p": 1}'), ("x_1", "")]
        assert tail == ""

        # Newlines inside args (DOTALL) and "!" inside JSON that is not "!]"
        clean, calls, _ = scan_call_syntax('[!call:t:{"a": "wow!\nok"}!]')
        assert clean == "" and calls == [("t", '{"a": "wow!\nok"}')]

    @pytest.mark.parametrize("frag", ["[!call:", "[!call:ab", "[!call:a b:{}!] tail", "[!call:!] tail", "[!call:a:{"])
    def test_malformed_or_unterminated_fragment_is_never_in_clean_text(self, frag):
        from src.agents.llm.types import sanitize_call_syntax

        assert sanitize_call_syntax("before " + frag) == "before"


class TestHoldbackOverflowNeverLeaks:
    """HIGH #2: an over-cap unterminated tail is discarded, never flushed to the stream."""

    @pytest.mark.parametrize("tail_len", [16383, 16384, 16385])
    def test_boundary_never_emits_raw_call_syntax(self, tail_len):
        from src.agents.llm.types import (
            MAX_STREAM_CALL_SYNTAX_BUFFER,
            process_stream_call_syntax_buffer,
            split_stream_call_syntax,
        )

        assert MAX_STREAM_CALL_SYNTAX_BUFFER == 16384
        tail = "[!call:" + "x" * (tail_len - len("[!call:"))
        assert len(tail) == tail_len
        buffer = "Safe prefix. " + tail

        safe_output, held, overflowed = split_stream_call_syntax(buffer)
        assert safe_output == "Safe prefix. "
        assert "[!call:" not in safe_output
        if tail_len <= MAX_STREAM_CALL_SYNTAX_BUFFER:
            assert (held, overflowed) == (tail, False)
        else:
            assert (held, overflowed) == ("", True)

        # back-compat wrapper agrees and also never leaks
        to_yield, remaining = process_stream_call_syntax_buffer(buffer)
        assert to_yield == "Safe prefix. "
        assert "[!call:" not in to_yield
        assert remaining == (tail if tail_len <= MAX_STREAM_CALL_SYNTAX_BUFFER else "")

    def test_long_safe_text_does_not_trigger_overflow(self):
        from src.agents.llm.types import split_stream_call_syntax

        safe, held, overflowed = split_stream_call_syntax("y" * 100000)
        assert (len(safe), held, overflowed) == (100000, "", False)

    @pytest.mark.asyncio
    async def test_stream_overflow_discards_fragment_and_does_not_execute_call(self):
        """The oversized tag would be a valid declared call once closed; it must neither stream nor run."""
        pad = "x" * 20000
        texts = [
            "Visible before. [!call:set_phase:",
            '{"phase": "close", "pad": "' + pad[:10000],
            pad[10000:],
            '"}!] visible after closing',
            " and more text",
        ]
        chunks = await _drain(_stream_adapter(texts), tools=_DECLARED_TOOLS)

        streamed = "".join(c.text for c in chunks if c.text and not c.is_thought)
        assert streamed.strip() == "Visible before."
        assert "[!call:" not in streamed and "xxxx" not in streamed and "phase" not in streamed
        terminal = chunks[-1]
        assert terminal.done is True
        assert terminal.function_call is None

    @pytest.mark.asyncio
    async def test_stream_overflow_in_many_small_chunks(self):
        texts = ["Hi [!call:set_phase:"] + ["y" * 100 for _ in range(200)] + ["tail"]
        chunks = await _drain(_stream_adapter(texts), tools=_DECLARED_TOOLS)
        streamed = "".join(c.text for c in chunks if c.text and not c.is_thought)
        assert streamed == "Hi "
        assert chunks[-1].function_call is None

    @pytest.mark.asyncio
    async def test_stream_below_cap_still_executes_valid_split_call(self):
        texts = ['Go [!call:set_phase:{"phase": "', "x" * 5000 + '"}!] done']
        chunks = await _drain(_stream_adapter(texts), tools=_DECLARED_TOOLS)
        streamed = "".join(c.text for c in chunks if c.text and not c.is_thought)
        assert streamed == "Go  done"
        assert chunks[-1].function_call is not None
        assert chunks[-1].function_call.name == "set_phase"


class TestFallbackAllowlist:
    """MEDIUM #4: allowlist is fail-closed when tools is not None; every tag is considered."""

    def test_empty_tools_list_fails_closed(self):
        from src.agents.llm.gemini_client import _extract_call_syntax

        fc, text = _extract_call_syntax('Hi [!call:set_phase:{"phase": "x"}!]', tools=[])
        assert fc is None
        assert text == "Hi"

    def test_tools_without_usable_names_fail_closed(self):
        from src.agents.llm.gemini_client import _extract_call_syntax

        fc, text = _extract_call_syntax('[!call:set_phase:{"a": 1}!]', tools=[{"description": "no name"}, {}])
        assert fc is None and text is None

    def test_tools_none_applies_no_allowlist(self):
        from src.agents.llm.gemini_client import _extract_call_syntax

        fc, _ = _extract_call_syntax('[!call:anything:{"a": 1}!]', tools=None)
        assert fc is not None and fc.name == "anything"

    def test_undeclared_first_tag_does_not_mask_declared_second(self):
        from src.agents.llm.gemini_client import _extract_call_syntax

        text = 'A [!call:evil_tool:{"cmd": "rm"}!] B [!call:close_event:{"summary": "ok"}!] C'
        fc, cleaned = _extract_call_syntax(text, tools=_DECLARED_TOOLS)
        assert fc is not None
        assert (fc.name, fc.args) == ("close_event", {"summary": "ok"})
        assert cleaned == "A  B  C"

    def test_invalid_json_first_tag_does_not_mask_valid_second(self):
        from src.agents.llm.gemini_client import _extract_call_syntax

        text = '[!call:set_phase:{not json}!] [!call:set_phase:["list"]!] [!call:set_phase:{"phase": "p"}!]'
        fc, cleaned = _extract_call_syntax(text, tools=_DECLARED_TOOLS)
        assert fc is not None and fc.args == {"phase": "p"}
        assert cleaned is None

    def test_all_tags_rejected_returns_sanitized_text(self):
        from src.agents.llm.gemini_client import _extract_call_syntax

        fc, cleaned = _extract_call_syntax('x [!call:a:{}!] y [!call:b:{}!] z [!call:set_phase:{', tools=_DECLARED_TOOLS)
        assert fc is None
        assert cleaned == "x  y  z"

    @pytest.mark.asyncio
    async def test_generate_passes_tools_to_allowlist(self):
        text = 'Ok [!call:evil_tool:{"x": 1}!] [!call:set_phase:{"phase": "p"}!]'
        res = await _generate_adapter(text).generate(system_prompt="sys", contents="c", tools=_DECLARED_TOOLS)
        assert res.function_call is not None and res.function_call.name == "set_phase"
        assert res.text == "Ok"

        res = await _generate_adapter('[!call:evil_tool:{"x": 1}!]').generate(
            system_prompt="sys", contents="c", tools=_DECLARED_TOOLS
        )
        assert res.function_call is None and res.text is None

    @pytest.mark.asyncio
    async def test_generate_empty_tools_fails_closed(self):
        res = await _generate_adapter('Hi [!call:set_phase:{"phase": "p"}!]').generate(
            system_prompt="sys", contents="c", tools=[]
        )
        assert res.function_call is None
        assert res.text == "Hi"

    @pytest.mark.asyncio
    async def test_generate_stream_passes_tools_to_allowlist(self):
        texts = ['Ok [!call:evil_tool:{"x": 1}!] ', '[!call:close_event:{"summary": "s"}!]']
        chunks = await _drain(_stream_adapter(texts), tools=_DECLARED_TOOLS)
        assert chunks[-1].function_call is not None and chunks[-1].function_call.name == "close_event"
        assert "".join(c.text for c in chunks if c.text).strip() == "Ok"

        chunks = await _drain(_stream_adapter(['[!call:evil_tool:{"x": 1}!]']), tools=_DECLARED_TOOLS)
        assert chunks[-1].function_call is None

    @pytest.mark.asyncio
    async def test_generate_stream_empty_tools_fails_closed(self):
        chunks = await _drain(_stream_adapter(['Hi [!call:set_phase:{"phase": "p"}!]']), tools=[])
        assert chunks[-1].function_call is None
        assert "".join(c.text for c in chunks if c.text).strip() == "Hi"


class TestCallSyntaxLogHygiene:
    """MEDIUM #3/#8: one warning per stripped fragment, and no raw model text in logs."""

    @staticmethod
    def _unterminated_warnings(caplog):
        return [r for r in caplog.records if "unterminated" in r.getMessage()]

    @pytest.mark.asyncio
    async def test_stream_tail_strip_warns_once_without_raw_text(self, caplog):
        import logging

        secret = "SECRET_ARGS_123"
        texts = ["Hello [!call:set_phase:", '{"phase": "' + secret]
        with caplog.at_level(logging.WARNING):
            chunks = await _drain(_stream_adapter(texts), tools=_DECLARED_TOOLS)

        assert "".join(c.text for c in chunks if c.text) == "Hello "
        assert chunks[-1].function_call is None
        warnings = self._unterminated_warnings(caplog)
        assert len(warnings) == 1
        assert "stream end" in warnings[0].getMessage()
        assert secret not in caplog.text

    @pytest.mark.asyncio
    async def test_generate_unterminated_warns_once(self, caplog):
        import logging

        with caplog.at_level(logging.WARNING):
            res = await _generate_adapter('Truncated [!call:set_phase:{"phase":').generate(
                system_prompt="sys", contents="c", tools=_DECLARED_TOOLS
            )
        assert res.text == "Truncated"
        assert len(self._unterminated_warnings(caplog)) == 1

    def test_sanitize_warn_flag_suppresses_duplicate(self, caplog):
        import logging
        from src.agents.llm.types import sanitize_call_syntax

        with caplog.at_level(logging.WARNING):
            sanitize_call_syntax("a [!call:x:{")
            sanitize_call_syntax("a [!call:x:{", warn=False)
        assert len(self._unterminated_warnings(caplog)) == 1

    def test_non_object_args_log_does_not_include_raw_args(self, caplog):
        import logging
        from src.agents.llm.gemini_client import _extract_call_syntax

        with caplog.at_level(logging.WARNING):
            _extract_call_syntax('[!call:set_phase:["TOPSECRET"]!]', tools=_DECLARED_TOOLS)
        assert "TOPSECRET" not in caplog.text


# ---------------------------------------------------------------------------
# PR #320 (M1/M2/M3): unary max_output_tokens ceiling is explicit and never silent;
# generate_stream() keeps the 65000 ceiling; Brain/Helm default model cannot drift.
# ---------------------------------------------------------------------------
import logging  # noqa: E402
import re  # noqa: E402
from pathlib import Path  # noqa: E402

import yaml  # noqa: E402

from src.agents.llm.gemini_client import _GEMINI_UNARY_MAX_OUTPUT_TOKENS  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CLAMP_LOGGER = "src.agents.llm.gemini_client"


def _clamp_warnings(caplog):
    return [r for r in caplog.records if r.levelno == logging.WARNING and "clamped" in r.getMessage()]


def _passed_max_tokens(adapter):
    """max_output_tokens (5th positional arg) of the single _build_config call."""
    adapter._build_config.assert_called_once()
    return adapter._build_config.call_args.args[4]


class TestUnaryMaxOutputTokensCeiling:
    def test_constant_is_32768(self):
        assert _GEMINI_UNARY_MAX_OUTPUT_TOKENS == 32768

    @pytest.mark.asyncio
    async def test_default_uses_ceiling_without_warning(self, real_adapter, caplog):
        real_adapter._client.aio.models.generate_content = AsyncMock(return_value=_response(_usage()))

        with caplog.at_level(logging.WARNING, logger=_CLAMP_LOGGER):
            await real_adapter.generate("sys", "hello")

        assert _passed_max_tokens(real_adapter) == _GEMINI_UNARY_MAX_OUTPUT_TOKENS == 32768
        assert _clamp_warnings(caplog) == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("requested", [1, 8192, 32768])
    async def test_values_at_or_below_ceiling_pass_through(self, real_adapter, caplog, requested):
        real_adapter._client.aio.models.generate_content = AsyncMock(return_value=_response(_usage()))

        with caplog.at_level(logging.WARNING, logger=_CLAMP_LOGGER):
            await real_adapter.generate("sys", "hello", max_output_tokens=requested)

        assert _passed_max_tokens(real_adapter) == requested
        assert _clamp_warnings(caplog) == []

    @pytest.mark.asyncio
    @pytest.mark.parametrize("requested", [32769, 65000])
    async def test_values_above_ceiling_are_clamped_with_warning(self, real_adapter, caplog, requested):
        real_adapter._client.aio.models.generate_content = AsyncMock(return_value=_response(_usage()))

        with caplog.at_level(logging.WARNING, logger=_CLAMP_LOGGER):
            await real_adapter.generate("sys", "hello", max_output_tokens=requested)

        assert _passed_max_tokens(real_adapter) == 32768
        warnings = _clamp_warnings(caplog)
        assert len(warnings) == 1
        msg = warnings[0].getMessage()
        assert "gemini-2.5-flash" in msg
        assert f"requested={requested}" in msg
        assert "clamped=32768" in msg

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", [None, 0, -1, True, False, 1.5, "100"])
    async def test_invalid_values_fall_back_to_ceiling_with_warning(self, real_adapter, caplog, bad):
        real_adapter._client.aio.models.generate_content = AsyncMock(return_value=_response(_usage()))

        with caplog.at_level(logging.WARNING, logger=_CLAMP_LOGGER):
            await real_adapter.generate("sys", "hello", max_output_tokens=bad)

        assert _passed_max_tokens(real_adapter) == 32768
        assert any("invalid max_output_tokens" in r.getMessage() for r in caplog.records)

    @pytest.mark.asyncio
    async def test_stream_passes_65000_through_unclamped(self, real_adapter, caplog):
        async def stream():
            yield _chunk(parts=[_part("hi")], text="hi", usage=_usage(total=90))

        _set_stream(real_adapter, stream)

        with caplog.at_level(logging.WARNING, logger=_CLAMP_LOGGER):
            _ = [c async for c in real_adapter.generate_stream("sys", "hello", max_output_tokens=65000)]

        assert _passed_max_tokens(real_adapter) == 65000
        assert _clamp_warnings(caplog) == []

    @pytest.mark.asyncio
    async def test_stream_default_is_65000(self, real_adapter):
        async def stream():
            yield _chunk(parts=[_part("hi")], text="hi", usage=_usage(total=90))

        _set_stream(real_adapter, stream)

        _ = [c async for c in real_adapter.generate_stream("sys", "hello")]

        assert _passed_max_tokens(real_adapter) == 65000


class TestBrainDefaultModelMatchesHelm:
    def test_brain_fallback_model_matches_helm_values(self):
        brain_src = (_REPO_ROOT / "src" / "agents" / "brain.py").read_text()
        m = re.search(r'os\.getenv\(\s*"LLM_MODEL_BRAIN"\s*,\s*"([^"]+)"\s*\)', brain_src)
        assert m, "Brain LLM_MODEL_BRAIN fallback not found in src/agents/brain.py"

        values = yaml.safe_load((_REPO_ROOT / "helm" / "values.yaml").read_text())
        helm_model = values["gcp"]["llm"]["brain"]["model"]

        assert m.group(1) == helm_model == "gemini-4-carbon"

    def test_t3_brain_fallback_max_tokens_matches_helm_values(self):
        brain_src = (_REPO_ROOT / "src" / "agents" / "brain.py").read_text()
        m = re.search(r'os\.getenv\(\s*"LLM_MAX_TOKENS_BRAIN"\s*,\s*"([^"]+)"\s*\)', brain_src)
        assert m, "Brain LLM_MAX_TOKENS_BRAIN fallback not found in src/agents/brain.py"

        values = yaml.safe_load((_REPO_ROOT / "helm" / "values.yaml").read_text())
        helm_max_tokens = str(values["gcp"]["llm"]["brain"]["maxOutputTokens"])

        assert m.group(1) == helm_max_tokens == "65536"


class TestPerStreamRetryOptionsAndSyncStreamDelegator:
    """T-6 (Probe 4a): Synchronous generate_stream delegator, per-call HttpRetryOptions(attempts=1),
    __new__ instance safety, and 6 positional args to _build_config.
    """

    def test_t6_generate_stream_is_sync_delegator_on_port_and_adapter(self):
        import inspect
        from src.agents.llm.types import LLMPort

        assert inspect.iscoroutinefunction(GeminiAdapter.generate_stream) is False
        assert inspect.iscoroutinefunction(LLMPort.generate_stream) is False
        assert inspect.signature(GeminiAdapter.generate_stream).parameters["max_output_tokens"].default == 65000

    @pytest.mark.asyncio
    async def test_t6_per_call_http_retry_attempts_one_on_initialized_and_new_instances(self, monkeypatch):
        from unittest.mock import patch

        monkeypatch.delenv("LLM_HTTP_TIMEOUT_SEC", raising=False)
        monkeypatch.delenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", raising=False)

        async def _single_chunk_stream():
            yield _chunk(parts=[_part("ok")], text="ok", usage=_usage(total=42))

        # 1. Initialized GeminiAdapter(...) instance
        with patch("google.genai.Client"):
            init_ad = GeminiAdapter("proj", "global", "gemini-4-carbon")
        init_ad._client = MagicMock()
        init_ad._client.aio.models.generate_content_stream = AsyncMock(side_effect=lambda **kw: _single_chunk_stream())
        init_ad._build_config = MagicMock(wraps=init_ad._build_config)

        gen = init_ad.generate_stream("sys", "hello")
        assert hasattr(gen, "aclose")
        _ = [c async for c in gen]

        assert len(init_ad._build_config.call_args.args) == 6
        assert init_ad._build_config.call_args.args[4] == 65000
        init_cfg = init_ad._client.aio.models.generate_content_stream.call_args.kwargs["config"]
        assert init_cfg.http_options is not None
        assert init_cfg.http_options.timeout == 240000
        assert init_cfg.http_options.retry_options is not None
        assert init_cfg.http_options.retry_options.attempts == 1

        # 2. GeminiAdapter.__new__(GeminiAdapter) fixture (no __init__ attribute setup)
        raw_ad = GeminiAdapter.__new__(GeminiAdapter)
        raw_ad._model_name = "gemini-4-carbon"
        raw_ad._tracker = None
        raw_ad._client = MagicMock()
        raw_ad._client.aio.models.generate_content_stream = AsyncMock(side_effect=lambda **kw: _single_chunk_stream())

        _ = [c async for c in raw_ad.generate_stream("sys", "hello")]
        raw_cfg = raw_ad._client.aio.models.generate_content_stream.call_args.kwargs["config"]
        assert raw_cfg.http_options is not None
        assert raw_cfg.http_options.timeout == 240000
        assert raw_cfg.http_options.retry_options is not None
        assert raw_cfg.http_options.retry_options.attempts == 1


class TestGemini4UnaryStreamAndAssemble:
    """T-8: Gemini 4 generate() streams via _stream_chunks(preserve_sdk_retries=True),
    uses sentinel 65536 default, filters thoughts, sanitizes with warn=False,
    acquires quota once, and rolls back on mid-stream inter-chunk timeout.
    """

    @staticmethod
    def _make_gemini4_spy_adapter(model_name: str = "gemini-4-argon", tracker=None):
        ad = GeminiAdapter.__new__(GeminiAdapter)
        ad._model_name = model_name
        ad._tracker = tracker
        ad._estimate_tokens = lambda contents: ESTIMATE
        ad._convert_contents = lambda contents: contents
        ad._build_config = MagicMock(wraps=ad._build_config)
        ad._client = MagicMock()
        return ad

    @pytest.mark.asyncio
    async def test_t8_gemini4_generate_sentinel_defaults_none_and_clamp_warnings_vs_flash(self, caplog):
        async def _json_stream():
            yield _chunk(parts=[_part('{"ok": true}')], text='{"ok": true}', usage=_usage(total=80))

        # 1. Omitted max_output_tokens on Gemini 4 -> silent 65536 (zero warnings)
        ad_default = self._make_gemini4_spy_adapter("gemini-4-argon")
        _set_stream(ad_default, _json_stream)
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=_CLAMP_LOGGER):
            await ad_default.generate("sys", "hello")
        assert _passed_max_tokens(ad_default) == 65536
        assert caplog.records == []

        # 2. Explicit max_output_tokens=None on Gemini 4 -> warns "invalid max_output_tokens" + resolves 65536
        ad_none = self._make_gemini4_spy_adapter("gemini-4-argon")
        _set_stream(ad_none, _json_stream)
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=_CLAMP_LOGGER):
            await ad_none.generate("sys", "hello", max_output_tokens=None)
        assert _passed_max_tokens(ad_none) == 65536
        assert any("invalid max_output_tokens" in r.getMessage() for r in caplog.records)

        # 3. Above ceiling max_output_tokens=100000 on Gemini 4 -> warns "clamped" + resolves 65536
        ad_clamp = self._make_gemini4_spy_adapter("gemini-4-argon")
        _set_stream(ad_clamp, _json_stream)
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=_CLAMP_LOGGER):
            await ad_clamp.generate("sys", "hello", max_output_tokens=100000)
        assert _passed_max_tokens(ad_clamp) == 65536
        warnings = _clamp_warnings(caplog)
        assert len(warnings) == 1
        msg = warnings[0].getMessage()
        assert "gemini-4-argon" in msg
        assert "requested=100000" in msg
        assert "clamped=65536" in msg

        # 4. gemini-3.8-flash keeps unary generate_content with 32768 default
        flash_ad = self._make_gemini4_spy_adapter("gemini-3.8-flash")
        flash_ad._client.aio.models.generate_content = AsyncMock(return_value=_response(_usage(total=70)))
        flash_ad._client.aio.models.generate_content_stream = AsyncMock()
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger=_CLAMP_LOGGER):
            await flash_ad.generate("sys", "hello")
        assert _passed_max_tokens(flash_ad) == 32768
        flash_ad._client.aio.models.generate_content.assert_awaited_once()
        flash_ad._client.aio.models.generate_content_stream.assert_not_called()

    @pytest.mark.asyncio
    async def test_t8_gemini4_generate_streams_with_sdk_retries_filters_thoughts_single_quota_and_warn_false(
        self, real_tracker
    ):
        import json
        from unittest.mock import patch
        from google.genai import types
        from src.agents.llm.types import sanitize_call_syntax as real_sanitize

        real_tracker.acquire = AsyncMock(wraps=real_tracker.acquire)
        ad = self._make_gemini4_spy_adapter("gemini-4-argon", tracker=real_tracker)
        ad._client.aio.models.generate_content = AsyncMock()

        thought_part = types.Part(thought=True, text="Internal reasoning {not valid json}")
        json_text = '{"decision": "approve", "confidence": 98}'
        visible_part = types.Part(thought=False, text=json_text)

        async def _mixed_stream():
            yield _chunk(parts=[thought_part], text=None)
            yield _chunk(parts=[visible_part], text=json_text, usage=_usage(total=150))

        _set_stream(ad, _mixed_stream)

        with patch("src.agents.llm.gemini_client.sanitize_call_syntax", wraps=real_sanitize) as sanitize_spy:
            resp = await ad.generate("sys", "hello")

        ad._client.aio.models.generate_content.assert_not_called()
        passed_cfg = ad._client.aio.models.generate_content_stream.call_args.kwargs["config"]
        assert passed_cfg.http_options is None, "preserve_sdk_retries=True must leave per-call http_options=None"

        assert resp.text is not None
        assert json.loads(resp.text) == {"decision": "approve", "confidence": 98}
        assert resp.usage is not None and resp.usage.total_tokens == 150
        assert real_tracker.acquire.await_count == 1
        _assert_recorded(real_tracker, 150)
        assert any(call.kwargs.get("warn") is False for call in sanitize_spy.call_args_list)

    @pytest.mark.asyncio
    async def test_t8_gemini4_generate_mid_stream_stall_raises_inter_chunk_closes_and_rolls_back_quota(
        self, monkeypatch, real_tracker
    ):
        from google.genai import types
        from src.agents.llm import LLMStreamInterChunkTimeoutError

        monkeypatch.delenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", raising=False)
        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "0.08")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "0.03")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "0.50")

        real_tracker.acquire = AsyncMock(wraps=real_tracker.acquire)
        ad = self._make_gemini4_spy_adapter("gemini-4-argon", tracker=real_tracker)

        class SpyHangingStream:
            def __init__(self):
                self._idx = 0
                self.aclose_awaited = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx == 0:
                    self._idx += 1
                    return _chunk(parts=[types.Part(thought=True, text="heartbeat")], text=None)
                await asyncio.Event().wait()

            async def aclose(self):
                self.aclose_awaited += 1

        spy_stream = SpyHangingStream()
        ad._client.aio.models.generate_content_stream = AsyncMock(return_value=spy_stream)

        with pytest.raises(LLMStreamInterChunkTimeoutError):
            await asyncio.wait_for(ad.generate("sys", "hello"), timeout=0.6)

        assert spy_stream.aclose_awaited == 1
        assert real_tracker.acquire.await_count == 1
        _assert_released(real_tracker)

    @pytest.mark.asyncio
    async def test_cr02_quota_acquire_delay_and_unset_ttfb_sdk_retry_do_not_trigger_false_ttfb_timeout(
        self, monkeypatch, real_tracker
    ):
        from unittest.mock import patch
        from google.genai import types

        # 1. QuotaTracker.acquire sleeps longer than explicit ttfb_timeout (0.03s), wire TTFB is fast -> succeeds!
        monkeypatch.delenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", raising=False)
        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "0.03")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "0.05")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "0.50")

        orig_acquire = real_tracker.acquire

        async def _slow_acquire(*args, **kwargs):
            await asyncio.sleep(0.06)
            return await orig_acquire(*args, **kwargs)

        real_tracker.acquire = AsyncMock(side_effect=_slow_acquire)
        ad = self._make_gemini4_spy_adapter("gemini-4-argon", tracker=real_tracker)

        async def _fast_wire_stream():
            yield _chunk(parts=[types.Part(text="ok")], text="ok", usage=_usage(total=60))

        _set_stream(ad, _fast_wire_stream)
        resp = await ad.generate("sys", "hello")
        assert resp.text == "ok"
        _assert_recorded(real_tracker, 60)

        # 2. When LLM_STREAM_TTFB_TIMEOUT_SEC & LLM_STREAM_CHUNK_TIMEOUT_SEC are unset, Chunk 0 uses total_timeout
        #    so SDK HttpRetryOptions(attempts=5) 429 retry sleep > 35s is NOT killed at 35s.
        monkeypatch.delenv("LLM_STREAM_TTFB_TIMEOUT_SEC", raising=False)
        monkeypatch.delenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", raising=False)
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "120")

        seen_budgets = []
        real_wait_for = asyncio.wait_for

        async def _spy_wait_for(aw, timeout=None):
            seen_budgets.append(timeout)
            return await real_wait_for(aw, timeout=timeout)

        ad_retry = self._make_gemini4_spy_adapter("gemini-4-argon")
        _set_stream(ad_retry, _fast_wire_stream)
        with patch("src.agents.llm.gemini_client.asyncio.wait_for", _spy_wait_for):
            resp_retry = await ad_retry.generate("sys", "hello")
        assert resp_retry.text == "ok"
        assert seen_budgets[0] == 120.0, f"Expected Chunk-0 budget == total_timeout (120.0s), got {seen_budgets[0]}"

    @pytest.mark.asyncio
    async def test_cr03_cr04_cr09_cr14_gemini4_generate_done_break_multichunk_raw_parts_cancel_and_clamp_msg(
        self, monkeypatch, caplog
    ):
        import time
        from unittest.mock import patch
        from google.genai import types

        monkeypatch.delenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", raising=False)
        monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", "0.20")
        monkeypatch.setenv("LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC", "0.20")
        monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", "1.0")

        # 1. CR-04 + CR-03: Multi-chunk visible text reassembles full text + sig in resp.raw_parts,
        #    and done=True breaks cleanly even if monotonic clock passes total_timeout right as done arrives.
        ad = self._make_gemini4_spy_adapter("gemini-4-argon")
        t_part = types.Part(thought=True, text="plan")
        p1 = types.Part(text="Hello ")
        p2 = types.Part(text="world!", thought_signature=b"sig9")

        real_mono = time.monotonic
        gen_calls = [0]

        def _advancing_mono():
            import sys
            if sys._getframe(1).f_code.co_name == "generate":
                idx = gen_calls[0]
                gen_calls[0] += 1
                # Call 0: stream_start=100.0; Call 1..3 (p1, p2, done=True): 100.3, 100.6, 100.9 (<1.0s);
                # Call 4 (would execute if generate() did not break on done=True): 101.2 (>1.0s).
                return 100.0 + idx * 0.30
            return real_mono()

        async def _multi_text_stream():
            yield _chunk(parts=[t_part], text=None)
            yield _chunk(parts=[p1], text="Hello ")
            yield _chunk(parts=[p2], text="world!", usage=_usage(total=88))

        _set_stream(ad, _multi_text_stream)
        with patch("time.monotonic", _advancing_mono):
            resp = await ad.generate("sys", "hello")

        assert resp.text == "Hello world!"
        assert resp.raw_parts is not None
        non_thought = [p for p in resp.raw_parts if not getattr(p, "thought", False)]
        assert len(non_thought) == 1
        assert non_thought[0].text == "Hello world!"
        assert non_thought[0].thought_signature == b"sig9"

        # 2. CR-09: External task.cancel() during post-FC drain propagates CancelledError
        ad_cancel = self._make_gemini4_spy_adapter("gemini-4-argon")
        fc = types.FunctionCall(name="classify_event", args={"domain": "clear"})
        drain_entered = asyncio.Event()

        class DrainHangStream:
            def __init__(self):
                self._idx = 0

            def __aiter__(self):
                return self

            async def __anext__(self):
                if self._idx == 0:
                    self._idx += 1
                    return _chunk(parts=[types.Part(function_call=fc)], function_calls=[fc])
                drain_entered.set()
                await asyncio.Event().wait()

        ad_cancel._client.aio.models.generate_content_stream = AsyncMock(return_value=DrainHangStream())
        tool_schema = [{"name": "classify_event", "description": "Classify", "input_schema": {"type": "object"}}]
        gen_task = asyncio.create_task(ad_cancel.generate("sys", "hello", tools=tool_schema))
        await asyncio.wait_for(drain_entered.wait(), timeout=0.5)
        gen_task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await gen_task

        # 3. CR-14: Gemini 4 clamp warning omits "use generate_stream()", and SDK stream retry attempts cap at 10
        caplog.clear()
        _set_stream(ad, _multi_text_stream)
        with caplog.at_level(logging.WARNING, logger=_CLAMP_LOGGER):
            await ad.generate("sys", "hello", max_output_tokens=100000)
        assert "use generate_stream()" not in caplog.text

        monkeypatch.setenv("LLM_STREAM_SDK_RETRY_ATTEMPTS", "999")
        ad_stream = self._make_gemini4_spy_adapter("gemini-4-argon")
        _set_stream(ad_stream, _multi_text_stream)
        _ = [c async for c in ad_stream.generate_stream("sys", "hello")]
        cfg = ad_stream._client.aio.models.generate_content_stream.call_args.kwargs["config"]
        assert cfg.http_options.retry_options.attempts == 10


class TestGemini4UnaryStreamTtfbTimeoutAndHelmExposure:
    """ATDD 4-Layer Executable Specification:
    Gemini 4 Unary generate() Chunk-0 Timeout Budget Parity under Helm Defaults,
    Custom TTFB Override Clamping, and Helm Chart Deployment Rendering.
    """

    # -------------------------------------------------------------------------
    # Layer 3: Protocol Drivers & Fixtures
    # -------------------------------------------------------------------------
    @staticmethod
    def _make_gemini4_spy_adapter(model_name: str = "gemini-4-argon", tracker=None):
        ad = GeminiAdapter.__new__(GeminiAdapter)
        ad._model_name = model_name
        ad._tracker = tracker
        ad._estimate_tokens = lambda contents: 50
        ad._convert_contents = lambda contents: contents
        ad._build_config = MagicMock(wraps=ad._build_config)
        ad._client = MagicMock()
        return ad

    @staticmethod
    def render_helm_brain_env(overrides: dict[str, str] | None = None) -> dict[str, str]:
        """Driver invoking `helm template darwin helm` to extract the `brain` container env."""
        import subprocess
        cmd = ["helm", "template", "darwin", "helm"]
        if overrides:
            for k, v in overrides.items():
                cmd.extend(["--set", f"{k}={v}"])
        proc = subprocess.run(
            cmd,
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert proc.returncode == 0, f"helm template failed: {proc.stderr}"
        docs = list(yaml.safe_load_all(proc.stdout))
        deployment_doc = None
        for doc in docs:
            if doc and doc.get("kind") == "Deployment" and doc.get("metadata", {}).get("name") == "darwin-brain":
                deployment_doc = doc
                break
        assert deployment_doc is not None, "Deployment 'darwin-brain' not found in helm template output"
        containers = deployment_doc.get("spec", {}).get("template", {}).get("spec", {}).get("containers", [])
        brain_container = next((c for c in containers if c.get("name") == "brain"), None)
        assert brain_container is not None, "Container 'brain' not found in Deployment spec"
        env_list = brain_container.get("env", [])
        return {item["name"]: str(item.get("value", "")) for item in env_list if "name" in item}

    # -------------------------------------------------------------------------
    # Layer 2: Domain-Specific Language (DSL) & Assertions
    # -------------------------------------------------------------------------
    @classmethod
    async def assert_gemini4_generate_chunk0_budget(
        cls, monkeypatch, *, ttfb_env: str | None, total_env: str | None, expected_budget: float
    ) -> None:
        from unittest.mock import patch
        from google.genai import types

        monkeypatch.delenv("LLM_STREAM_CHUNK_TIMEOUT_SEC", raising=False)
        if ttfb_env is not None:
            monkeypatch.setenv("LLM_STREAM_TTFB_TIMEOUT_SEC", ttfb_env)
        else:
            monkeypatch.delenv("LLM_STREAM_TTFB_TIMEOUT_SEC", raising=False)

        if total_env is not None:
            monkeypatch.setenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", total_env)
        else:
            monkeypatch.delenv("LLM_STREAM_TOTAL_TIMEOUT_SEC", raising=False)

        seen_budgets = []
        real_wait_for = asyncio.wait_for

        async def _spy_wait_for(aw, timeout=None):
            seen_budgets.append(timeout)
            return await real_wait_for(aw, timeout=timeout)

        async def _fast_stream():
            yield _chunk(parts=[types.Part(text="ok")], text="ok", usage=_usage(total=50))

        ad = cls._make_gemini4_spy_adapter("gemini-4-argon")
        _set_stream(ad, _fast_stream)

        with patch("src.agents.llm.gemini_client.asyncio.wait_for", _spy_wait_for):
            resp = await ad.generate("sys", "hello")

        assert resp.text == "ok"
        assert len(seen_budgets) > 0, "asyncio.wait_for was never called"
        assert seen_budgets[0] == expected_budget, (
            f"Chunk-0 timeout budget mismatch: expected {expected_budget}s, got {seen_budgets[0]}s"
        )

    @classmethod
    def assert_helm_deployment_env_vars(
        cls, env: dict[str, str], expected_vars: dict[str, str]
    ) -> None:
        for k, v in expected_vars.items():
            assert k in env, f"Expected env var '{k}' missing from brain container env: {list(env.keys())}"
            assert env[k] == v, f"Expected {k}='{v}', got '{env[k]}'"

    # -------------------------------------------------------------------------
    # Layer 1: Executable Scenarios (T-5, T-6, T-7, T-8)
    # -------------------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_t5_gemini4_generate_helm_default_ttfb_preserves_total_timeout(self, monkeypatch):
        """T-5: Gemini 4 unary GeminiAdapter.generate() with LLM_STREAM_TTFB_TIMEOUT_SEC="35"
        (matching the Helm default) preserves total_timeout (180.0s) for Chunk 0.
        """
        await self.assert_gemini4_generate_chunk0_budget(
            monkeypatch,
            ttfb_env="35",
            total_env="180",
            expected_budget=180.0,
        )

    @pytest.mark.asyncio
    async def test_t6_gemini4_generate_custom_ttfb_override_honors_min_ttfb_and_total(self, monkeypatch):
        """T-6: Gemini 4 unary GeminiAdapter.generate() with custom non-default override (e.g. "45")
        honors min(ttfb_timeout, total_timeout).
        """
        # Case A: explicit ttfb override (45s) < total_timeout (180s) -> 45.0s
        await self.assert_gemini4_generate_chunk0_budget(
            monkeypatch,
            ttfb_env="45",
            total_env="180",
            expected_budget=45.0,
        )

        # Case B: explicit ttfb override (200s) > total_timeout (180s) -> clamps to total_timeout (180.0s)
        await self.assert_gemini4_generate_chunk0_budget(
            monkeypatch,
            ttfb_env="200",
            total_env="180",
            expected_budget=180.0,
        )

    @pytest.mark.skipif(not shutil.which("helm"), reason="helm CLI required")
    def test_t7_helm_default_template_renders_brain_stream_timeout_and_sdk_retry_env(self):
        """T-7: Default helm template darwin helm renders Deployment with LLM_STREAM_TTFB_TIMEOUT_SEC="35",
        LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC="30", LLM_STREAM_TOTAL_TIMEOUT_SEC="180",
        LLM_STREAM_SDK_RETRY_ATTEMPTS="1" in the brain container env.
        """
        env = self.render_helm_brain_env()
        self.assert_helm_deployment_env_vars(
            env,
            {
                "LLM_STREAM_TTFB_TIMEOUT_SEC": "35",
                "LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC": "30",
                "LLM_STREAM_TOTAL_TIMEOUT_SEC": "180",
                "LLM_STREAM_SDK_RETRY_ATTEMPTS": "1",
            },
        )

    @pytest.mark.skipif(not shutil.which("helm"), reason="helm CLI required")
    def test_t8_helm_custom_overrides_reflect_in_brain_env_and_lint_passes(self):
        """T-8: Custom helm --set overrides reflect in rendered Deployment and helm lint passes."""
        import subprocess

        overrides = {
            "brain.streamTtfbTimeoutSec": "45",
            "brain.streamInterChunkTimeoutSec": "40",
            "brain.streamTotalTimeoutSec": "210",
            "brain.streamSdkRetryAttempts": "2",
        }
        env = self.render_helm_brain_env(overrides=overrides)
        self.assert_helm_deployment_env_vars(
            env,
            {
                "LLM_STREAM_TTFB_TIMEOUT_SEC": "45",
                "LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC": "40",
                "LLM_STREAM_TOTAL_TIMEOUT_SEC": "210",
                "LLM_STREAM_SDK_RETRY_ATTEMPTS": "2",
            },
        )

        lint_proc = subprocess.run(
            ["helm", "lint", "helm"],
            cwd=_REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert lint_proc.returncode == 0, f"helm lint failed: {lint_proc.stderr}\n{lint_proc.stdout}"

    @pytest.mark.skipif(not shutil.which("helm"), reason="helm CLI required")
    def test_t12_helm_template_zero_retry_attempts_and_partial_brain_values(self):
        """T-12: Rendering helm template with --set brain.streamSdkRetryAttempts=0 outputs
        LLM_STREAM_SDK_RETRY_ATTEMPTS="0" (not omitted due to Go template falsy 0), and
        helm/values.yaml has descriptive inline '#' comments on all 4 stream* keys.
        """
        env = self.render_helm_brain_env(overrides={"brain.streamSdkRetryAttempts": "0"})
        self.assert_helm_deployment_env_vars(
            env,
            {
                "LLM_STREAM_TTFB_TIMEOUT_SEC": "35",
                "LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC": "30",
                "LLM_STREAM_TOTAL_TIMEOUT_SEC": "180",
                "LLM_STREAM_SDK_RETRY_ATTEMPTS": "0",
            },
        )

        values_text = (_REPO_ROOT / "helm" / "values.yaml").read_text()
        for key in (
            "streamTtfbTimeoutSec",
            "streamInterChunkTimeoutSec",
            "streamTotalTimeoutSec",
            "streamSdkRetryAttempts",
        ):
            matching_lines = [
                line for line in values_text.splitlines() if line.strip().startswith(f"{key}:")
            ]
            assert matching_lines, f"Key '{key}:' not found in helm/values.yaml"
            assert "#" in matching_lines[0], (
                f"Expected descriptive inline '#' comment on '{key}' in helm/values.yaml, got: {matching_lines[0]!r}"
            )



