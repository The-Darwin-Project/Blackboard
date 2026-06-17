# tests/test_state_watcher_probe.py
# @ai-rules:
# 1. [Pattern]: Local probe -- validates core StateWatcher mechanics against mocks.
# 2. [Constraint]: No cluster, no Redis, no GitLab API -- pure asyncio + mocks.
"""
Local probe for StateWatcher: validates register, poll, state change detection,
hook firing, cancel, duplicate replace, backoff, max cap, deferred gate, lifecycle.
"""
import asyncio
import time
import pytest
from unittest.mock import AsyncMock

from src.scheduling.state_watcher import (
    StateWatcher, SubscriptionSpec, GitLabMrRef, KargoStageRef,
    StateKey, MAX_SUBSCRIPTIONS,
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
        poll_fn = AsyncMock(return_value=state_key or {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"})
    if state_key is None:
        state_key = {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"}
    ref = GitLabMrRef(project_id=123, mr_iid=42) if resource_type == "gitlab_mr" else KargoStageRef(project="test", stage="dev")
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


class TestRegister:
    def test_register_returns_true(self, watcher):
        spec = _make_spec()
        assert watcher.register(spec) is True
        assert watcher.active_count == 1

    def test_duplicate_replaces(self, watcher):
        spec1 = _make_spec(cycle_id="c1")
        spec2 = _make_spec(cycle_id="c2")
        watcher.register(spec1)
        watcher.register(spec2)
        assert watcher.active_count == 1

    def test_cap_rejects(self, watcher):
        for i in range(MAX_SUBSCRIPTIONS):
            assert watcher.register(_make_spec(event_id=f"evt-{i}")) is True
        assert watcher.register(_make_spec(event_id="evt-overflow")) is False
        assert watcher.active_count == MAX_SUBSCRIPTIONS


class TestCancel:
    def test_cancel_existing(self, watcher):
        watcher.register(_make_spec())
        assert watcher.cancel("evt-test-001") is True
        assert watcher.active_count == 0

    def test_cancel_nonexistent(self, watcher):
        assert watcher.cancel("evt-nope") is False

    def test_cancel_if_different_cycle(self, watcher):
        watcher.register(_make_spec(cycle_id="old"))
        assert watcher.cancel_if_different_cycle("evt-test-001", "new") is True
        assert watcher.active_count == 0

    def test_cancel_preserves_same_cycle(self, watcher):
        watcher.register(_make_spec(cycle_id="same"))
        assert watcher.cancel_if_different_cycle("evt-test-001", "same") is False
        assert watcher.active_count == 1

    def test_cancel_all(self, watcher):
        for i in range(5):
            watcher.register(_make_spec(event_id=f"evt-{i}"))
        count = watcher.cancel_all()
        assert count == 5
        assert watcher.active_count == 0


class TestStateChangeDetection:
    @pytest.mark.asyncio
    async def test_detects_change_and_fires_hook(self, watcher, on_change, is_deferred):
        old_state = {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"}
        new_state = {"mr_state": "opened", "pipeline_status": "success", "merge_status": "can_be_merged"}
        poll_fn = AsyncMock(return_value=new_state)
        spec = _make_spec(poll_fn=poll_fn, state_key=old_state, interval=1)

        watcher.register(spec)
        await watcher.start()
        await asyncio.sleep(2.5)
        await watcher.stop()

        on_change.assert_called_once()
        args = on_change.call_args[0]
        assert args[0] == "evt-test-001"
        assert args[1] == old_state
        assert args[2] == new_state
        assert watcher.active_count == 0

    @pytest.mark.asyncio
    async def test_no_change_no_hook(self, watcher, on_change, is_deferred):
        same_state = {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"}
        poll_fn = AsyncMock(return_value=same_state)
        spec = _make_spec(poll_fn=poll_fn, state_key=same_state, interval=1)

        watcher.register(spec)
        await watcher.start()
        await asyncio.sleep(2.5)
        await watcher.stop()

        on_change.assert_not_called()
        assert poll_fn.call_count >= 1


class TestDeferredGate:
    @pytest.mark.asyncio
    async def test_skips_non_deferred(self, watcher, on_change):
        is_not_deferred = AsyncMock(return_value=False)
        watcher._is_deferred = is_not_deferred

        new_state = {"mr_state": "merged", "pipeline_status": "success", "merge_status": "merged"}
        poll_fn = AsyncMock(return_value=new_state)
        old_state = {"mr_state": "opened", "pipeline_status": "running", "merge_status": "unchecked"}
        spec = _make_spec(poll_fn=poll_fn, state_key=old_state, interval=1)

        watcher.register(spec)
        await watcher.start()
        await asyncio.sleep(2.5)

        poll_fn.assert_not_called()
        on_change.assert_not_called()
        assert watcher.active_count == 1

        await watcher.stop()


class TestBackoff:
    @pytest.mark.asyncio
    async def test_backoff_on_poll_error(self, watcher, on_change, is_deferred):
        poll_fn = AsyncMock(side_effect=ConnectionError("GitLab 429"))
        spec = _make_spec(poll_fn=poll_fn, interval=1)

        watcher.register(spec)
        await watcher.start()
        await asyncio.sleep(4.0)
        await watcher.stop()

        assert poll_fn.call_count >= 2
        on_change.assert_not_called()

    @pytest.mark.asyncio
    async def test_max_failures_cancels(self, watcher, on_change, is_deferred):
        poll_fn = AsyncMock(side_effect=ConnectionError("down"))
        spec = _make_spec(poll_fn=poll_fn, interval=0)

        watcher.register(spec)
        await watcher.start()
        await asyncio.sleep(3.0)
        await watcher.stop()

        assert watcher.active_count == 0
        on_change.assert_not_called()


class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_stop(self, watcher):
        await watcher.start()
        assert watcher._running is True
        await watcher.stop()
        assert watcher._running is False
        assert watcher._task is None

    @pytest.mark.asyncio
    async def test_double_start_is_noop(self, watcher):
        await watcher.start()
        task1 = watcher._task
        await watcher.start()
        assert watcher._task is task1
        await watcher.stop()


class TestKargoResource:
    @pytest.mark.asyncio
    async def test_kargo_poll(self, watcher, on_change, is_deferred):
        old_state = {"phase": "Running", "failed_step": None}
        new_state = {"phase": "Succeeded", "failed_step": None}
        poll_fn = AsyncMock(return_value=new_state)

        spec = _make_spec(
            event_id="evt-kargo-001",
            poll_fn=poll_fn,
            state_key=old_state,
            interval=1,
            resource_type="kargo_stage",
        )

        watcher.register(spec)
        await watcher.start()
        await asyncio.sleep(2.5)
        await watcher.stop()

        on_change.assert_called_once()
        assert on_change.call_args[0][2] == new_state
