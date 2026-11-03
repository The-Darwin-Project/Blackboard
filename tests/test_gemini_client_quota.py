# BlackBoard/tests/test_gemini_client_quota.py
# @ai-rules:
# 1. [Constraint]: Unit tests for GeminiAdapter quota acquisition budget (30s), _record_usage chokepoint, and stream rollback.
# 2. [Pattern]: Validates T-1 and T-2 using mocks for LLM client and QuotaTracker.
"""Unit tests for GeminiAdapter quota decoupling and stream error rollback."""
import asyncio
from unittest.mock import AsyncMock, MagicMock
import pytest

from src.agents.llm.gemini_client import GeminiAdapter
from src.agents.llm.quota_tracker import QuotaExhaustedError, QuotaTracker, Reservation


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
