# tests/test_task_lifecycle_ordering.py
# @ai-rules:
# 1. [Constraint]: No Redis -- MagicMock blackboard only.
# 2. [Pattern]: Follows test_brain_orphan.py structure: Brain(blackboard=mock, agents={}).
# 3. [Invariant]: _release_task_state MUST run before any bookkeeping await after turn delivery.
# 4. [Gotcha]: _active_tasks is set by the dispatcher, not inside _run_agent_task. Pre-set in tests.
# 5. [Gotcha]: Error path mocks must NOT swallow exceptions -- agent.process raises, except block catches.
"""Verify _release_task_state runs before bookkeeping awaits (TOCTOU prevention).

Production evidence: evt-8758be1b, 68.3s delay, 4 GATE rejections caused by
_active_tasks persisting through bookkeeping awaits in _run_agent_task.

Tests cover all 4 tail paths:
- Success: normal agent completion
- Error: agent.process raises exception
- Wake: handle_wake_task normal completion
- Message-mode: no-deliverable early return
"""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.brain import Brain
from src.models import EventDocument, EventEvidence, EventInput


def _make_event(event_id: str = "evt-test", source: str = "chat") -> EventDocument:
    evidence = EventEvidence(
        display_text="test", source_type=source, domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id, source=source, service="test-svc", brain_phase="dispatch",
        event=EventInput(reason="test", evidence=evidence),
        conversation=[],
    )


def _make_brain() -> Brain:
    bb = MagicMock()
    bb.get_event = AsyncMock(return_value=_make_event())
    bb.append_turn = AsyncMock(return_value=1)
    bb.mark_turn_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.get_active_events = AsyncMock(return_value=[])
    bb.get_recent_closed_for_service = AsyncMock(return_value=[])
    bb.generate_mermaid = AsyncMock(return_value="")
    brain = Brain(blackboard=bb, agents={})
    brain._broadcast = AsyncMock()
    brain._broadcast_turn = AsyncMock()
    brain._broadcast_status_update = AsyncMock()
    brain._dispatch_semaphore = None
    brain._ws_mode = "legacy"
    return brain


def _instrument(brain: Brain) -> list[str]:
    """Wrap target methods with call-order recording. Returns the shared call log."""
    call_log: list[str] = []

    original_release = brain._release_task_state

    def release_wrapper(event_id: str) -> None:
        call_log.append("release_task_state")
        original_release(event_id)

    brain._release_task_state = release_wrapper  # type: ignore[assignment]
    brain._append_and_broadcast = AsyncMock(
        side_effect=lambda *a, **kw: call_log.append("append_and_broadcast"),
    )
    brain.blackboard.mark_turn_status = AsyncMock(
        side_effect=lambda *a, **kw: call_log.append("mark_turn_status"),
    )
    brain._broadcast_status_update = AsyncMock(
        side_effect=lambda *a, **kw: call_log.append("broadcast_status_update"),
    )
    brain.blackboard.stamp_event = AsyncMock(
        side_effect=lambda *a, **kw: call_log.append("stamp_event"),
    )
    return call_log


def _assert_release_before_bookkeeping(call_log: list[str]) -> None:
    """Assert _release_task_state precedes ALL bookkeeping calls (not just first occurrence)."""
    assert "release_task_state" in call_log, f"release_task_state missing: {call_log}"
    release_idx = call_log.index("release_task_state")
    for i, entry in enumerate(call_log):
        if entry in ("mark_turn_status", "broadcast_status_update", "stamp_event"):
            assert release_idx < i, (
                f"release_task_state (idx={release_idx}) must precede "
                f"{entry} (idx={i}), got: {call_log}"
            )


class TestTaskLifecycleOrdering:
    """TOCTOU prevention: _release_task_state MUST run before bookkeeping awaits."""

    @pytest.mark.asyncio
    async def test_success_path(self):
        """Normal completion: release before mark_turn_status + stamp_event."""
        brain = _make_brain()
        call_log = _instrument(brain)

        mock_agent = MagicMock()
        mock_agent.process = AsyncMock(
            return_value=("Agent completed the task successfully", None),
        )

        brain._active_tasks["evt-test"] = asyncio.current_task()
        brain._active_agent_for_event["evt-test"] = "sysadmin"

        await brain._run_agent_task(
            event_id="evt-test",
            agent_name="sysadmin",
            agent=mock_agent,
            task="Investigate pod logs",
            event_md_path="/tmp/event.md",
            routing_turn_num=5,
        )

        _assert_release_before_bookkeeping(call_log)
        assert "append_and_broadcast" in call_log, "Result turn must be written"

    @pytest.mark.asyncio
    async def test_error_path(self):
        """Agent crash: release before mark_turn_status in except block."""
        brain = _make_brain()
        call_log = _instrument(brain)

        mock_agent = MagicMock()
        mock_agent.process = AsyncMock(side_effect=RuntimeError("sidecar OOM"))

        brain._active_tasks["evt-test"] = asyncio.current_task()
        brain._active_agent_for_event["evt-test"] = "sysadmin"

        await brain._run_agent_task(
            event_id="evt-test",
            agent_name="sysadmin",
            agent=mock_agent,
            task="Investigate pod logs",
            event_md_path="/tmp/event.md",
            routing_turn_num=5,
        )

        _assert_release_before_bookkeeping(call_log)
        assert "append_and_broadcast" in call_log, "Error turn must be written"

    @pytest.mark.asyncio
    async def test_wake_path(self):
        """Wake task: release before stamp_event."""
        brain = _make_brain()
        call_log = _instrument(brain)

        mock_registry = MagicMock()
        mock_registry.mark_idle = AsyncMock()
        mock_bridge = MagicMock()

        with patch(
            "src.dependencies.get_registry_and_bridge",
            return_value=(mock_registry, mock_bridge),
        ), patch(
            "src.agents.dispatch.consume_wake_task",
            new_callable=AsyncMock,
            return_value=("Wake result with enough content to pass threshold", None),
        ):
            await brain.handle_wake_task(
                data={
                    "event_id": "evt-test",
                    "role": "sysadmin",
                    "task_id": "task-1",
                    "mode": "implement",
                },
                agent_id="sysadmin-1",
            )

        _assert_release_before_bookkeeping(call_log)
        assert "append_and_broadcast" in call_log, "Result turn must be written"

    @pytest.mark.asyncio
    async def test_message_mode_no_deliverable(self):
        """Message-mode early return: release before mark_turn_status + stamp_event.

        brain.py gates no-deliverable on: len(result_str) <= 100 AND not
        result_str.startswith("---"). "short" (5 chars) hits the no-deliverable path.
        """
        brain = _make_brain()
        call_log = _instrument(brain)

        mock_agent = MagicMock()
        mock_agent.process = AsyncMock(return_value=("short", None))

        brain._active_tasks["evt-test"] = asyncio.current_task()
        brain._active_agent_for_event["evt-test"] = "developer"

        await brain._run_agent_task(
            event_id="evt-test",
            agent_name="developer",
            agent=mock_agent,
            task="Send the teammate a message",
            event_md_path="/tmp/event.md",
            routing_turn_num=5,
            mode="message",
        )

        _assert_release_before_bookkeeping(call_log)
        assert "append_and_broadcast" not in call_log, (
            "Message-mode no-deliverable path must NOT write a result turn"
        )
