# tests/test_nightwatcher_sweep.py
# @ai-rules:
# 1. [Pattern]: Tests the NightwatcherObserver._sweep method with fully mocked dependencies.
# 2. [Constraint]: No real LLM calls, no real Redis. LLM adapter returns controlled responses.
# 3. [Pattern]: Covers: empty sweep, below-min sweep, no-adapter error path, tool-calling loop,
#    orphan re-injection, phase transitions, and commit/persist ordering.
"""Unit tests for Nightwatcher sweep orchestration."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import ShiftIncident, ShiftReport, StagedEscalation
from src.observers.nightwatcher import NightwatcherObserver


# =========================================================================
# Fixtures
# =========================================================================

def _make_escalation(event_id="evt-1", service="svc-a", staged_at=1000.0):
    return StagedEscalation(
        event_id=event_id, service=service, source="aligner",
        reason="cpu", summary="High CPU", staged_at=staged_at,
    )


def _make_observer(**overrides) -> NightwatcherObserver:
    defaults = dict(
        blackboard=AsyncMock(),
        registry=AsyncMock(),
        bridge=AsyncMock(),
        provisioner=AsyncMock(),
        smartsheet_adapter=AsyncMock(),
        archivist=AsyncMock(),
        slack_notify=AsyncMock(),
    )
    defaults.update(overrides)
    return NightwatcherObserver(**defaults)


class MockFunctionCall:
    def __init__(self, name: str, args: dict):
        self.name = name
        self.args = args


class MockResponse:
    """Mock LLM generate() response."""
    def __init__(self, function_call=None, text=None, raw_parts=None):
        self.function_call = function_call
        self.text = text or ""
        self.raw_parts = raw_parts


# =========================================================================
# Empty / below-min sweep
# =========================================================================

class TestEmptySweep:
    @pytest.mark.asyncio
    async def test_zero_pending_persists_empty_report(self):
        obs = _make_observer()
        obs.blackboard.lease_pending_escalations = AsyncMock(return_value=([], []))
        obs.blackboard.persist_shift_report = AsyncMock()

        await obs._sweep()

        obs.blackboard.persist_shift_report.assert_awaited_once()
        report = obs.blackboard.persist_shift_report.call_args[0][0]
        assert report.status == "empty"

    @pytest.mark.asyncio
    async def test_below_min_requeues_and_persists_empty(self):
        obs = _make_observer()
        esc = _make_escalation()
        json_str = esc.model_dump_json()
        obs.blackboard.lease_pending_escalations = AsyncMock(
            return_value=([esc], [json_str]),
        )
        obs.blackboard.requeue_inflight = AsyncMock()
        obs.blackboard.persist_shift_report = AsyncMock()

        with patch.dict("os.environ", {"NIGHTWATCHER_MIN_PENDING": "5"}):
            await obs._sweep()

        obs.blackboard.requeue_inflight.assert_awaited_once()
        report = obs.blackboard.persist_shift_report.call_args[0][0]
        assert report.status == "empty"


# =========================================================================
# No LLM adapter
# =========================================================================

class TestNoAdapter:
    @pytest.mark.asyncio
    async def test_requeues_when_no_adapter(self):
        obs = _make_observer()
        esc = _make_escalation()
        obs.blackboard.lease_pending_escalations = AsyncMock(
            return_value=([esc], [esc.model_dump_json()]),
        )
        obs.blackboard.requeue_inflight = AsyncMock()
        obs._get_adapter = AsyncMock(return_value=None)

        await obs._sweep()

        obs.blackboard.requeue_inflight.assert_awaited_once()


# =========================================================================
# Full sweep with tool-calling loop
# =========================================================================

class TestFullSweep:
    @pytest.mark.asyncio
    async def test_happy_path_single_incident(self):
        """LLM does: set_phase(investigate) -> set_phase(report) -> create_incident -> text done."""
        obs = _make_observer()
        esc1 = _make_escalation("evt-1", "svc-a")
        esc2 = _make_escalation("evt-2", "svc-a")
        json_members = [esc1.model_dump_json(), esc2.model_dump_json()]
        obs.blackboard.lease_pending_escalations = AsyncMock(
            return_value=([esc1, esc2], json_members),
        )
        obs.blackboard.commit_inflight = AsyncMock()
        obs.blackboard.persist_shift_report = AsyncMock()

        call_sequence = [
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "investigate"})),
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "report"})),
            MockResponse(function_call=MockFunctionCall("create_issue", {
                "platform": "Konflux", "summary": "Shared root cause",
                "affected_events": ["evt-1", "evt-2"],
            })),
            MockResponse(function_call=MockFunctionCall("post_shift_summary", {
                "summary": "1 incident from 2 escalations.",
            })),
            MockResponse(text="Sweep complete."),
        ]
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(side_effect=call_sequence)
        obs._get_adapter = AsyncMock(return_value=mock_adapter)

        obs._smartsheet = AsyncMock()
        obs._smartsheet.create_incident = AsyncMock(
            return_value={"row_id": 100, "sheet_url": "https://ss.com/100"},
        )

        await obs._sweep()

        obs.blackboard.commit_inflight.assert_awaited_once_with(json_members)
        obs.blackboard.persist_shift_report.assert_awaited_once()
        report = obs.blackboard.persist_shift_report.call_args[0][0]
        assert report.status == "completed"
        assert len(report.incidents) == 1
        assert set(report.incidents[0].affected_events) == {"evt-1", "evt-2"}
        assert report.metrics["noise_reduction_pct"] == 50.0


# =========================================================================
# Orphan re-injection
# =========================================================================

class TestOrphanReinjection:
    @pytest.mark.asyncio
    async def test_orphan_detected_and_reinjected(self):
        """LLM creates incident for evt-1 but misses evt-2. Re-injection fires."""
        obs = _make_observer()
        esc1 = _make_escalation("evt-1", "svc-a")
        esc2 = _make_escalation("evt-2", "svc-b")
        json_members = [esc1.model_dump_json(), esc2.model_dump_json()]
        obs.blackboard.lease_pending_escalations = AsyncMock(
            return_value=([esc1, esc2], json_members),
        )
        obs.blackboard.commit_inflight = AsyncMock()
        obs.blackboard.persist_shift_report = AsyncMock()

        first_incident = MockResponse(function_call=MockFunctionCall("create_issue", {
            "platform": "K", "summary": "S", "affected_events": ["evt-1"],
        }))
        text_done = MockResponse(text="Done.")
        second_incident = MockResponse(function_call=MockFunctionCall("create_issue", {
            "platform": "K", "summary": "S2", "affected_events": ["evt-2"],
        }))
        final_done = MockResponse(text="All done.")

        call_sequence = [
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "report"})),
            first_incident,
            text_done,
            second_incident,
            final_done,
        ]
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(side_effect=call_sequence)
        obs._get_adapter = AsyncMock(return_value=mock_adapter)
        obs._smartsheet = AsyncMock()
        obs._smartsheet.create_incident = AsyncMock(
            return_value={"row_id": 1, "sheet_url": ""},
        )

        await obs._sweep()

        report = obs.blackboard.persist_shift_report.call_args[0][0]
        assert len(report.incidents) == 2


# =========================================================================
# Phase transition
# =========================================================================

class TestPhaseTransitions:
    @pytest.mark.asyncio
    async def test_backward_transition_ignored(self):
        """set_phase('review') while in investigate should not go backwards."""
        obs = _make_observer()
        esc = _make_escalation("evt-1")
        obs.blackboard.lease_pending_escalations = AsyncMock(
            return_value=([esc], [esc.model_dump_json()]),
        )
        obs.blackboard.commit_inflight = AsyncMock()
        obs.blackboard.persist_shift_report = AsyncMock()

        call_sequence = [
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "investigate"})),
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "review"})),
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "report"})),
            MockResponse(function_call=MockFunctionCall("create_issue", {
                "platform": "K", "summary": "S", "affected_events": ["evt-1"],
            })),
            MockResponse(text="Done."),
        ]
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(side_effect=call_sequence)
        obs._get_adapter = AsyncMock(return_value=mock_adapter)
        obs._smartsheet = AsyncMock()
        obs._smartsheet.create_incident = AsyncMock(
            return_value={"row_id": 1, "sheet_url": ""},
        )

        await obs._sweep()

        report = obs.blackboard.persist_shift_report.call_args[0][0]
        assert report.status == "completed"


# =========================================================================
# Start / stop lifecycle
# =========================================================================

class TestLifecycle:
    @pytest.mark.asyncio
    async def test_start_calls_requeue(self):
        obs = _make_observer()
        obs.blackboard.requeue_inflight = AsyncMock(return_value=3)
        await obs.start()
        obs.blackboard.requeue_inflight.assert_awaited_once()
        assert obs._running is True
        await obs.stop()
        assert obs._running is False

    @pytest.mark.asyncio
    async def test_double_start_noop(self):
        obs = _make_observer()
        obs.blackboard.requeue_inflight = AsyncMock(return_value=0)
        await obs.start()
        await obs.start()
        assert obs.blackboard.requeue_inflight.await_count == 1
        await obs.stop()
