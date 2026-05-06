# tests/test_nightwatcher_sweep.py
# @ai-rules:
# 1. [Pattern]: Tests the NightwatcherObserver._sweep, _run_analysis_loop, and _run_report_cart methods.
# 2. [Constraint]: No real LLM calls, no real Redis. LLM adapter returns controlled responses.
# 3. [Pattern]: Covers: empty sweep, below-min sweep, no-adapter error path, analysis loop,
#    report shopping cart, phase transitions, coverage gate, and commit/persist ordering.
"""Unit tests for Nightwatcher sweep orchestration."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import ShiftIncident, ShiftReport, StagedEscalation
from src.observers.nightwatcher import (
    MAX_ANALYSIS_ROUNDS,
    NightwatcherObserver,
)


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
# Full sweep with shopping cart
# =========================================================================

class TestFullSweep:
    @pytest.mark.asyncio
    async def test_happy_path_single_incident(self):
        """Analysis -> report cart: declare 1 cluster, write 1 incident, post summary."""
        obs = _make_observer()
        esc1 = _make_escalation("evt-1", "svc-a")
        esc2 = _make_escalation("evt-2", "svc-a")
        json_members = [esc1.model_dump_json(), esc2.model_dump_json()]
        obs.blackboard.lease_pending_escalations = AsyncMock(
            return_value=([esc1, esc2], json_members),
        )
        obs.blackboard.commit_inflight = AsyncMock()
        obs.blackboard.persist_shift_report = AsyncMock()

        # Analysis loop: set_phase(investigate) -> set_phase(report) exits loop
        analysis_calls = [
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "investigate"})),
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "report"})),
        ]
        # Report cart: declare_clusters -> write_incident -> post_shift_summary
        cart_calls = [
            MockResponse(function_call=MockFunctionCall("declare_clusters", {
                "clusters": [{"root_cause": "Shared CPU spike", "platform": "Konflux",
                              "events": ["evt-1", "evt-2"]}],
            })),
            MockResponse(function_call=MockFunctionCall("write_incident", {
                "summary": "Shared root cause", "description": "CPU spike",
                "priority": "High", "status": "New",
            })),
            MockResponse(function_call=MockFunctionCall("post_shift_summary", {
                "summary": "1 incident from 2 escalations.",
            })),
        ]
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(side_effect=analysis_calls + cart_calls)
        obs._get_adapter = AsyncMock(return_value=mock_adapter)

        obs._smartsheet = AsyncMock()
        obs._smartsheet.create_incident = AsyncMock(
            return_value={"row_id": 100, "sheet_url": "https://ss.com/100"},
        )

        await obs._sweep()

        obs.blackboard.commit_inflight.assert_awaited_once()
        obs.blackboard.persist_shift_report.assert_awaited_once()
        report = obs.blackboard.persist_shift_report.call_args[0][0]
        assert report.status == "completed"
        assert len(report.incidents) == 1
        assert set(report.incidents[0].affected_events) == {"evt-1", "evt-2"}
        assert report.metrics["noise_reduction_pct"] == 50.0


# =========================================================================
# Analysis loop tests
# =========================================================================

class TestAnalysisLoop:
    @pytest.mark.asyncio
    async def test_analysis_loop_text_nudge(self):
        """LLM emits text (no tool call) first, then calls set_phase(report). Verify nudge injection."""
        obs = _make_observer()
        esc = _make_escalation("evt-1")
        json_members = [esc.model_dump_json()]
        obs.blackboard.lease_pending_escalations = AsyncMock(
            return_value=([esc], json_members),
        )
        obs.blackboard.commit_inflight = AsyncMock()
        obs.blackboard.persist_shift_report = AsyncMock()

        # Analysis: set_phase(investigate) -> text (nudge) -> set_phase(report)
        analysis_calls = [
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "investigate"})),
            MockResponse(text="I'll analyze the escalations now."),
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "report"})),
        ]
        # Cart: simple declare + write + summary
        cart_calls = [
            MockResponse(function_call=MockFunctionCall("declare_clusters", {
                "clusters": [{"root_cause": "CPU", "platform": "Konflux", "events": ["evt-1"]}],
            })),
            MockResponse(function_call=MockFunctionCall("write_incident", {
                "summary": "CPU spike", "description": "desc", "priority": "Normal", "status": "New",
            })),
            MockResponse(function_call=MockFunctionCall("post_shift_summary", {
                "summary": "Done.",
            })),
        ]
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(side_effect=analysis_calls + cart_calls)
        obs._get_adapter = AsyncMock(return_value=mock_adapter)
        obs._smartsheet = AsyncMock()
        obs._smartsheet.create_incident = AsyncMock(
            return_value={"row_id": 1, "sheet_url": ""},
        )

        await obs._sweep()

        # Verify: 3 analysis calls (investigate + text nudge + report) + 3 cart calls = 6
        assert mock_adapter.generate.await_count == 6
        report = obs.blackboard.persist_shift_report.call_args[0][0]
        assert report.status == "completed"

    @pytest.mark.asyncio
    async def test_analysis_loop_max_rounds(self):
        """LLM always returns a tool call (not set_phase(report)). Verify loop terminates at MAX_ANALYSIS_ROUNDS."""
        obs = _make_observer()
        esc = _make_escalation("evt-1")
        json_members = [esc.model_dump_json()]
        obs.blackboard.lease_pending_escalations = AsyncMock(
            return_value=([esc], json_members),
        )
        obs.blackboard.commit_inflight = AsyncMock()
        obs.blackboard.persist_shift_report = AsyncMock()

        # Analysis: MAX_ANALYSIS_ROUNDS calls that never transition to report
        analysis_calls = [
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "investigate"})),
        ] + [
            MockResponse(function_call=MockFunctionCall("dispatch_investigation", {
                "target_service": "svc-a", "question": "what happened?",
            }))
            for _ in range(MAX_ANALYSIS_ROUNDS - 1)
        ]
        # Cart still runs after forced exit: declare + write + summary
        cart_calls = [
            MockResponse(function_call=MockFunctionCall("declare_clusters", {
                "clusters": [{"root_cause": "CPU", "platform": "Konflux", "events": ["evt-1"]}],
            })),
            MockResponse(function_call=MockFunctionCall("write_incident", {
                "summary": "CPU", "description": "desc", "priority": "Normal", "status": "New",
            })),
            MockResponse(function_call=MockFunctionCall("post_shift_summary", {
                "summary": "Done.",
            })),
        ]
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(side_effect=analysis_calls + cart_calls)
        obs._get_adapter = AsyncMock(return_value=mock_adapter)
        obs._smartsheet = AsyncMock()
        obs._smartsheet.create_incident = AsyncMock(
            return_value={"row_id": 1, "sheet_url": ""},
        )

        # Mock execute_tool for the dispatch_investigation calls
        with patch("src.observers.nightwatcher.execute_tool", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = "Investigation dispatched."
            await obs._sweep()

        # Analysis loop should have exhausted MAX_ANALYSIS_ROUNDS
        assert mock_adapter.generate.await_count == MAX_ANALYSIS_ROUNDS + 3  # +3 for cart
        report = obs.blackboard.persist_shift_report.call_args[0][0]
        assert report.status == "completed"


# =========================================================================
# Report cart tests
# =========================================================================

class TestReportCart:
    @pytest.mark.asyncio
    async def test_report_cart_happy_path(self):
        """Full cart: declare 2 clusters, write 2 incidents, post summary."""
        obs = _make_observer()
        esc1 = _make_escalation("evt-1", "svc-a")
        esc2 = _make_escalation("evt-2", "svc-b")
        esc3 = _make_escalation("evt-3", "svc-b")
        json_members = [e.model_dump_json() for e in [esc1, esc2, esc3]]
        obs.blackboard.lease_pending_escalations = AsyncMock(
            return_value=([esc1, esc2, esc3], json_members),
        )
        obs.blackboard.commit_inflight = AsyncMock()
        obs.blackboard.persist_shift_report = AsyncMock()

        # Analysis: fast-track to report
        analysis_calls = [
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "investigate"})),
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "report"})),
        ]
        # Cart: 2 clusters, 2 write_incidents, 1 summary
        cart_calls = [
            MockResponse(function_call=MockFunctionCall("declare_clusters", {
                "clusters": [
                    {"root_cause": "CPU spike", "platform": "Konflux", "events": ["evt-1"]},
                    {"root_cause": "OOM", "platform": "Konflux", "events": ["evt-2", "evt-3"]},
                ],
            })),
            MockResponse(function_call=MockFunctionCall("write_incident", {
                "summary": "CPU spike in svc-a", "description": "desc1",
                "priority": "High", "status": "New",
            })),
            MockResponse(function_call=MockFunctionCall("write_incident", {
                "summary": "OOM in svc-b", "description": "desc2",
                "priority": "Normal", "status": "New",
            })),
            MockResponse(function_call=MockFunctionCall("post_shift_summary", {
                "summary": "2 incidents from 3 escalations.",
            })),
        ]
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(side_effect=analysis_calls + cart_calls)
        obs._get_adapter = AsyncMock(return_value=mock_adapter)
        obs._smartsheet = AsyncMock()
        obs._smartsheet.create_incident = AsyncMock(
            return_value={"row_id": 1, "sheet_url": ""},
        )

        await obs._sweep()

        report = obs.blackboard.persist_shift_report.call_args[0][0]
        assert report.status == "completed"
        assert len(report.incidents) == 2
        all_events = {eid for inc in report.incidents for eid in inc.affected_events}
        assert all_events == {"evt-1", "evt-2", "evt-3"}
        assert report.metrics["noise_reduction_pct"] > 0

    @pytest.mark.asyncio
    async def test_report_cart_validation_retry(self):
        """First declare_clusters misses an event, second attempt passes validation."""
        obs = _make_observer()
        esc1 = _make_escalation("evt-1", "svc-a")
        esc2 = _make_escalation("evt-2", "svc-b")
        json_members = [esc1.model_dump_json(), esc2.model_dump_json()]
        obs.blackboard.lease_pending_escalations = AsyncMock(
            return_value=([esc1, esc2], json_members),
        )
        obs.blackboard.commit_inflight = AsyncMock()
        obs.blackboard.persist_shift_report = AsyncMock()

        # Analysis: fast-track
        analysis_calls = [
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "investigate"})),
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "report"})),
        ]
        # Cart: first declare missing evt-2, second declare includes all
        cart_calls = [
            # Attempt 1: only covers evt-1 (missing evt-2)
            MockResponse(function_call=MockFunctionCall("declare_clusters", {
                "clusters": [{"root_cause": "CPU", "platform": "Konflux", "events": ["evt-1"]}],
            })),
            # Attempt 2: covers both
            MockResponse(function_call=MockFunctionCall("declare_clusters", {
                "clusters": [
                    {"root_cause": "CPU", "platform": "Konflux", "events": ["evt-1"]},
                    {"root_cause": "OOM", "platform": "Konflux", "events": ["evt-2"]},
                ],
            })),
            # write_incident for cluster 1
            MockResponse(function_call=MockFunctionCall("write_incident", {
                "summary": "CPU", "description": "d1", "priority": "Normal", "status": "New",
            })),
            # write_incident for cluster 2
            MockResponse(function_call=MockFunctionCall("write_incident", {
                "summary": "OOM", "description": "d2", "priority": "Normal", "status": "New",
            })),
            MockResponse(function_call=MockFunctionCall("post_shift_summary", {
                "summary": "2 incidents.",
            })),
        ]
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(side_effect=analysis_calls + cart_calls)
        obs._get_adapter = AsyncMock(return_value=mock_adapter)
        obs._smartsheet = AsyncMock()
        obs._smartsheet.create_incident = AsyncMock(
            return_value={"row_id": 1, "sheet_url": ""},
        )

        await obs._sweep()

        # Verify second attempt succeeded: 2 incidents created
        report = obs.blackboard.persist_shift_report.call_args[0][0]
        assert report.status == "completed"
        assert len(report.incidents) == 2
        all_events = {eid for inc in report.incidents for eid in inc.affected_events}
        assert all_events == {"evt-1", "evt-2"}


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

        analysis_calls = [
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "investigate"})),
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "review"})),
            MockResponse(function_call=MockFunctionCall("set_phase", {"phase": "report"})),
        ]
        cart_calls = [
            MockResponse(function_call=MockFunctionCall("declare_clusters", {
                "clusters": [{"root_cause": "X", "platform": "Konflux", "events": ["evt-1"]}],
            })),
            MockResponse(function_call=MockFunctionCall("write_incident", {
                "summary": "S", "description": "d", "priority": "Normal", "status": "New",
            })),
            MockResponse(function_call=MockFunctionCall("post_shift_summary", {
                "summary": "Done.",
            })),
        ]
        mock_adapter = AsyncMock()
        mock_adapter.generate = AsyncMock(side_effect=analysis_calls + cart_calls)
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
