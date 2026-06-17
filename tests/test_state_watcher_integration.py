# tests/test_state_watcher_integration.py
# @ai-rules:
# 1. [Pattern]: Integration tests beyond the probe -- exercises brain-level wiring scenarios.
# 2. [Constraint]: No cluster, no Redis, no GitLab API -- pure asyncio + mocks.
# 3. [Pattern]: Reuses _make_spec helper from probe for consistency.
# 4. [Pattern]: Tests for code review findings: HTTP errors, heapq tie-breaking, re-queue, force-close cleanup.
"""
Integration tests for StateWatcher subscription lifecycle:
- Transition failure (on_change callback handles already-closed events)
- Cap rejection with feedback in tool result
- Timer-wake defensive cancel
- cycle_id boundary across processing cycles
- Close-path cancel (all 5 paths)
- Slack filter refactor (tuple matching)
- HTTP error handling (raise_for_status routing)
- heapq tie-breaking (same next_poll_at)
- Outer except re-queue (subscription orphan prevention)
- Force-close cleanup (_cycle_id_for_event)
"""
import asyncio
import time
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

from src.scheduling.state_watcher import (
    StateWatcher, SubscriptionSpec, GitLabMrRef, KargoStageRef,
    StateKey, MAX_SUBSCRIPTIONS, _QueueEntry, BACKOFF_BASE,
)


def _make_spec(
    event_id: str = "evt-test-001",
    poll_fn: AsyncMock | None = None,
    interval: int = 1,
    state_key: StateKey | None = None,
    cycle_id: str = "cycle-1",
    resource_type: str = "gitlab_mr",
) -> SubscriptionSpec:
    if poll_fn is None:
        poll_fn = AsyncMock(return_value=state_key or {
            "mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked",
        })
    if state_key is None:
        state_key = {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"}
    ref = (
        GitLabMrRef(project_id=123, mr_iid=42)
        if resource_type == "gitlab_mr"
        else KargoStageRef(project="test", stage="dev")
    )
    return SubscriptionSpec(
        event_id=event_id,
        resource_type=resource_type,
        resource_ref=ref,
        poll_fn=poll_fn,
        interval=interval,
        state_key=state_key,
        registered_at=time.time(),
        cycle_id=cycle_id,
    )


@pytest.fixture
def on_change():
    return AsyncMock()


@pytest.fixture
def is_deferred():
    return AsyncMock(return_value=True)


@pytest.fixture
def watcher(on_change, is_deferred):
    return StateWatcher(on_change=on_change, is_deferred=is_deferred)


class TestTransitionFailure:
    """on_change callback raises -- subscription still cleans up."""

    @pytest.mark.asyncio
    async def test_on_change_exception_cancels_sub(self, is_deferred):
        on_change = AsyncMock(side_effect=RuntimeError("transition failed"))
        w = StateWatcher(on_change=on_change, is_deferred=is_deferred)

        new_state = {"mr_state": "merged", "pipeline_status": "success", "merge_status": "merged"}
        poll_fn = AsyncMock(return_value=new_state)
        old_state = {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"}
        spec = _make_spec(poll_fn=poll_fn, state_key=old_state, interval=1)

        w.register(spec)
        await w.start()
        await asyncio.sleep(2.5)
        await w.stop()

        on_change.assert_called_once()
        assert w.active_count == 0


class TestCapRejectionFeedback:
    """Cap rejection returns False -- Brain can include this in tool result."""

    def test_cap_returns_false(self, watcher):
        for i in range(MAX_SUBSCRIPTIONS):
            assert watcher.register(_make_spec(event_id=f"evt-{i}")) is True
        rejected = watcher.register(_make_spec(event_id="evt-overflow"))
        assert rejected is False

    def test_cap_rejection_preserves_existing(self, watcher):
        for i in range(MAX_SUBSCRIPTIONS):
            watcher.register(_make_spec(event_id=f"evt-{i}"))
        watcher.register(_make_spec(event_id="evt-overflow"))
        assert watcher.active_count == MAX_SUBSCRIPTIONS


class TestTimerWakeCancel:
    """When timer wakes the event, cancel cleans up the watcher."""

    @pytest.mark.asyncio
    async def test_cancel_stops_polling(self, watcher, on_change, is_deferred):
        same_state = {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"}
        poll_fn = AsyncMock(return_value=same_state)
        spec = _make_spec(poll_fn=poll_fn, state_key=same_state, interval=1)

        watcher.register(spec)
        await watcher.start()
        await asyncio.sleep(1.5)

        watcher.cancel("evt-test-001")
        assert watcher.active_count == 0
        call_count_at_cancel = poll_fn.call_count

        await asyncio.sleep(2.0)
        await watcher.stop()

        assert poll_fn.call_count == call_count_at_cancel
        on_change.assert_not_called()


class TestCycleIdBoundary:
    """subscribe -> defer within same cycle preserves; different cycle cancels."""

    def test_same_cycle_preserved(self, watcher):
        spec = _make_spec(cycle_id="cycle-A")
        watcher.register(spec)
        cancelled = watcher.cancel_if_different_cycle("evt-test-001", "cycle-A")
        assert cancelled is False
        assert watcher.active_count == 1

    def test_different_cycle_cancels(self, watcher):
        spec = _make_spec(cycle_id="cycle-A")
        watcher.register(spec)
        cancelled = watcher.cancel_if_different_cycle("evt-test-001", "cycle-B")
        assert cancelled is True
        assert watcher.active_count == 0

    def test_new_cycle_replaces_old_subscription(self, watcher):
        spec1 = _make_spec(cycle_id="cycle-old")
        spec2 = _make_spec(cycle_id="cycle-new")
        watcher.register(spec1)
        watcher.register(spec2)
        assert watcher.active_count == 1
        cancelled = watcher.cancel_if_different_cycle("evt-test-001", "cycle-new")
        assert cancelled is False


class TestClosePathCancel:
    """All 5 cancel paths should clean up subscriptions."""

    def test_direct_cancel(self, watcher):
        watcher.register(_make_spec())
        watcher.cancel("evt-test-001")
        assert watcher.active_count == 0

    def test_cancel_all_on_stop(self, watcher):
        for i in range(3):
            watcher.register(_make_spec(event_id=f"evt-{i}"))
        count = watcher.cancel_all()
        assert count == 3
        assert watcher.active_count == 0

    @pytest.mark.asyncio
    async def test_stop_cancels_all(self, watcher, on_change, is_deferred):
        for i in range(3):
            watcher.register(_make_spec(event_id=f"evt-{i}"))
        await watcher.start()
        await watcher.stop()
        assert watcher.active_count == 0

    def test_cancel_nonexistent_is_safe(self, watcher):
        assert watcher.cancel("evt-ghost") is False

    def test_cancel_if_different_cycle_nonexistent(self, watcher):
        assert watcher.cancel_if_different_cycle("evt-ghost", "cycle-x") is False


class TestInflightRace:
    """Subscription registered, event not yet deferred -- poll waits for deferred gate."""

    @pytest.mark.asyncio
    async def test_poll_waits_for_deferred_gate(self, watcher, on_change):
        gate_open = asyncio.Event()
        call_count = 0

        async def delayed_deferred(event_id: str) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count >= 3:
                gate_open.set()
                return True
            return False

        watcher._is_deferred = delayed_deferred

        new_state = {"mr_state": "merged", "pipeline_status": "success", "merge_status": "merged"}
        poll_fn = AsyncMock(return_value=new_state)
        old_state = {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"}
        spec = _make_spec(poll_fn=poll_fn, state_key=old_state, interval=1)

        watcher.register(spec)
        await watcher.start()
        await asyncio.sleep(5.0)
        await watcher.stop()

        assert gate_open.is_set()
        on_change.assert_called_once()


class TestSlackFilterRefactor:
    """Verify _INTERNAL_TURNS uses (actor, action) tuple matching."""

    def test_internal_turns_structure(self):
        from src.channels.slack import _INTERNAL_TURNS
        assert isinstance(_INTERNAL_TURNS, frozenset)
        assert ("brain", "triage") in _INTERNAL_TURNS
        assert ("system", "notification") in _INTERNAL_TURNS
        assert "triage" not in _INTERNAL_TURNS

    def test_backward_compat_brain_actions(self):
        from src.channels.slack import _INTERNAL_TURNS
        for action in ["triage", "phase", "respond_jarvis", "tool_result",
                       "hold_watch", "intermediate", "hold_watch_wake", "think"]:
            assert ("brain", action) in _INTERNAL_TURNS


class TestHeapqTieBreaking:
    """_QueueEntry with same next_poll_at must not raise TypeError."""

    def test_same_timestamp_no_error(self):
        import heapq
        now = time.time()
        q: list[_QueueEntry] = []
        heapq.heappush(q, _QueueEntry(now, event_id="evt-a"))
        heapq.heappush(q, _QueueEntry(now, event_id="evt-b"))
        heapq.heappush(q, _QueueEntry(now, event_id="evt-c"))
        results = [heapq.heappop(q).event_id for _ in range(3)]
        assert len(results) == 3
        assert set(results) == {"evt-a", "evt-b", "evt-c"}

    def test_ordering_preserved_with_tiebreaker(self):
        import heapq
        q: list[_QueueEntry] = []
        heapq.heappush(q, _QueueEntry(10.0, event_id="evt-late"))
        heapq.heappush(q, _QueueEntry(5.0, event_id="evt-early"))
        heapq.heappush(q, _QueueEntry(5.0, event_id="evt-early2"))
        first = heapq.heappop(q)
        assert first.next_poll_at == 5.0


class TestOuterExceptRequeue:
    """Outer except in _poll_loop re-queues subscription with backoff."""

    @pytest.mark.asyncio
    async def test_is_deferred_failure_requeues(self, on_change):
        call_count = 0
        deferred_error_count = 0

        async def failing_deferred(event_id: str) -> bool:
            nonlocal call_count, deferred_error_count
            call_count += 1
            if call_count <= 2:
                deferred_error_count += 1
                raise RuntimeError("Redis connection lost")
            return True

        new_state = {"mr_state": "merged", "pipeline_status": "success", "merge_status": "merged"}
        poll_fn = AsyncMock(return_value=new_state)
        old_state = {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"}
        spec = _make_spec(poll_fn=poll_fn, state_key=old_state, interval=1)

        w = StateWatcher(on_change=on_change, is_deferred=failing_deferred)
        w.register(spec)
        await w.start()
        await asyncio.sleep(10.0)
        await w.stop()

        assert deferred_error_count == 2
        assert w.active_count == 0
        on_change.assert_called_once()


class TestPollGitlabHttpErrors:
    """poll_gitlab_mr_status raises on non-2xx, triggering backoff."""

    @pytest.mark.asyncio
    async def test_raise_for_status_on_429(self):
        from src.agents.headhunter import Headhunter
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "429 Too Many Requests", request=MagicMock(), response=mock_response,
        )

        async def mock_get(*args, **kwargs):
            return mock_response

        hh = Headhunter.__new__(Headhunter)
        hh._gitlab_host = "https://gitlab.example.com"
        hh._gitlab_token = "test-token"

        with patch("httpx.AsyncClient") as mock_client_cls:
            client_instance = AsyncMock()
            client_instance.get = mock_get
            client_instance.__aenter__ = AsyncMock(return_value=client_instance)
            client_instance.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = client_instance
            with pytest.raises(httpx.HTTPStatusError):
                await hh.poll_gitlab_mr_status(project_id=123, mr_iid=42)


class TestCanonicalStateKeyBuilders:
    """Canonical state-key builders produce consistent output."""

    def test_gitlab_state_key_builder(self):
        from src.agents.headhunter import Headhunter
        state = {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked", "extra": "ignored"}
        key = Headhunter.extract_gitlab_state_key(state)
        assert key == {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"}
        assert "extra" not in key

    def test_gitlab_state_key_defaults(self):
        from src.agents.headhunter import Headhunter
        key = Headhunter.extract_gitlab_state_key({})
        assert key == {"mr_state": "unknown", "pipeline_status": "unknown", "merge_status": "unknown"}

    def test_kargo_state_key_builder(self):
        from src.observers.kargo import KargoObserver
        promo_status = {"phase": "Running", "stepExecutionMetadata": []}
        key = KargoObserver.extract_kargo_state_key(promo_status)
        assert key == {"phase": "Running", "failed_step": ""}

    def test_kargo_state_key_with_failed_step(self):
        from src.observers.kargo import KargoObserver
        promo_status = {
            "phase": "Errored",
            "stepExecutionMetadata": [{"alias": "deploy", "status": "Errored"}],
        }
        key = KargoObserver.extract_kargo_state_key(promo_status)
        assert key == {"phase": "Errored", "failed_step": "deploy"}


class TestPollFnProtocol:
    """PollFn protocol is importable and usable for type checking."""

    def test_protocol_importable(self):
        from src.scheduling.state_watcher import PollFn
        assert hasattr(PollFn, "__call__")
