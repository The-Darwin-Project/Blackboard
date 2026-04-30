# tests/test_nightwatcher_tools.py
# @ai-rules:
# 1. [Pattern]: All infrastructure mocked via AsyncMock -- no Redis, no Smartsheet, no LLM calls.
# 2. [Pattern]: NightwatcherContext constructed per test with controlled mocks.
# 3. [Constraint]: Tests verify tool routing, phase gating, dispatch cap enforcement, and field population.
"""Unit tests for Nightwatcher tool execution and phase gating."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, patch

from src.models import ShiftIncident, ShiftInvestigation
from src.observers.nightwatcher_tools import (
    NightwatcherContext,
    execute_tool,
    get_phase_tools,
    _PHASE_TOOLS,
)


# =========================================================================
# Fixtures
# =========================================================================

def _make_ctx(**overrides) -> NightwatcherContext:
    defaults = dict(
        blackboard=AsyncMock(),
        archivist=AsyncMock(),
        provisioner=AsyncMock(),
        registry=AsyncMock(),
        bridge=AsyncMock(),
        smartsheet_adapter=AsyncMock(),
        slack_notify=AsyncMock(),
        manifest_services={"svc-a", "svc-b"},
        manifest_ids={"evt-1", "evt-2"},
        dispatch_count=0,
        dispatch_cap=3,
        created_incidents=[],
        investigations=[],
    )
    defaults.update(overrides)
    return NightwatcherContext(**defaults)


# =========================================================================
# Phase gating
# =========================================================================

class TestPhaseGating:
    def test_review_phase_tools(self):
        tools = get_phase_tools("review")
        names = {t["name"] for t in tools}
        assert "set_phase" in names
        assert "get_event_report" in names
        assert "consult_deep_memory" in names
        assert "search_journal" in names
        assert "dispatch_investigation" not in names
        assert "create_issue" not in names

    def test_investigate_phase_adds_dispatch(self):
        tools = get_phase_tools("investigate")
        names = {t["name"] for t in tools}
        assert "dispatch_investigation" in names
        assert "get_event_report" in names
        assert "create_issue" not in names

    def test_report_phase_write_only(self):
        tools = get_phase_tools("report")
        names = {t["name"] for t in tools}
        assert "create_issue" in names
        assert "post_shift_summary" in names
        assert "get_event_report" not in names
        assert "dispatch_investigation" not in names
        assert "set_phase" not in names

    def test_unknown_phase_returns_empty(self):
        tools = get_phase_tools("nonexistent")
        assert tools == []

    def test_phase_tool_sets_match_constant(self):
        assert "review" in _PHASE_TOOLS
        assert "investigate" in _PHASE_TOOLS
        assert "report" in _PHASE_TOOLS


# =========================================================================
# Tool routing
# =========================================================================

class TestExecuteTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        ctx = _make_ctx()
        result = await execute_tool("nonexistent_tool", {}, ctx)
        assert "Unknown tool" in result

    @pytest.mark.asyncio
    async def test_handler_exception_returns_error(self):
        ctx = _make_ctx()
        ctx.blackboard.get_report = AsyncMock(side_effect=RuntimeError("boom"))
        result = await execute_tool("get_event_report", {"event_id": "evt-1"}, ctx)
        assert "Tool error" in result
        assert "boom" in result


# =========================================================================
# get_event_report
# =========================================================================

class TestGetEventReport:
    @pytest.mark.asyncio
    async def test_returns_markdown_content(self):
        ctx = _make_ctx()
        ctx.blackboard.get_report = AsyncMock(return_value={"markdown": "# Report\nCPU spike."})
        result = await execute_tool("get_event_report", {"event_id": "evt-1"}, ctx)
        assert "Report" in result
        assert "CPU spike" in result

    @pytest.mark.asyncio
    async def test_missing_report(self):
        ctx = _make_ctx()
        ctx.blackboard.get_report = AsyncMock(return_value=None)
        result = await execute_tool("get_event_report", {"event_id": "evt-missing"}, ctx)
        assert "No report found" in result


# =========================================================================
# search_journal
# =========================================================================

class TestSearchJournal:
    @pytest.mark.asyncio
    async def test_returns_entries(self):
        ctx = _make_ctx()
        ctx.blackboard.get_journal = AsyncMock(return_value=["entry-1", "entry-2"])
        result = await execute_tool("search_journal", {"service": "svc-a"}, ctx)
        assert "entry-1" in result
        assert "entry-2" in result

    @pytest.mark.asyncio
    async def test_no_entries(self):
        ctx = _make_ctx()
        ctx.blackboard.get_journal = AsyncMock(return_value=[])
        result = await execute_tool("search_journal", {"service": "svc-x"}, ctx)
        assert "No journal entries" in result


# =========================================================================
# consult_deep_memory
# =========================================================================

class TestConsultDeepMemory:
    @pytest.mark.asyncio
    async def test_returns_formatted_results(self):
        ctx = _make_ctx()
        ctx.archivist.search = AsyncMock(return_value=[
            {"score": 0.92, "payload": {
                "symptom": "OOM", "root_cause": "memory leak",
                "fix_action": "increase limits", "service": "svc-a",
                "outcome": "resolved",
            }},
        ])
        result = await execute_tool("consult_deep_memory", {"query": "memory"}, ctx)
        assert "0.92" in result
        assert "OOM" in result
        assert "memory leak" in result

    @pytest.mark.asyncio
    async def test_no_results(self):
        ctx = _make_ctx()
        ctx.archivist.search = AsyncMock(return_value=[])
        result = await execute_tool("consult_deep_memory", {"query": "xyz"}, ctx)
        assert "No matching events" in result


# =========================================================================
# dispatch_investigation
# =========================================================================

class TestDispatchInvestigation:
    @pytest.mark.asyncio
    async def test_service_not_in_manifest(self):
        ctx = _make_ctx()
        result = await execute_tool(
            "dispatch_investigation", {"service": "unknown-svc"}, ctx,
        )
        assert "not in the manifest" in result
        assert ctx.dispatch_count == 0

    @pytest.mark.asyncio
    async def test_dispatch_cap_reached(self):
        ctx = _make_ctx(dispatch_count=3, dispatch_cap=3)
        result = await execute_tool(
            "dispatch_investigation", {"service": "svc-a"}, ctx,
        )
        assert "Dispatch cap reached" in result
        assert ctx.dispatch_count == 3

    @pytest.mark.asyncio
    async def test_no_provisioner(self):
        ctx = _make_ctx(provisioner=None)
        result = await execute_tool(
            "dispatch_investigation", {"service": "svc-a"}, ctx,
        )
        assert "provisioner not available" in result

    @pytest.mark.asyncio
    async def test_successful_dispatch(self):
        ctx = _make_ctx()
        mock_agent = AsyncMock()
        mock_agent.agent_id = "agent-123"
        ctx.provisioner.ensure_agent = AsyncMock(return_value=mock_agent)

        with patch("src.agents.dispatch.dispatch_to_agent",
                   new_callable=AsyncMock, return_value=("Pipeline healthy.", None)):
            result = await execute_tool(
                "dispatch_investigation", {"service": "svc-a"}, ctx,
            )
        assert ctx.dispatch_count == 1
        assert len(ctx.investigations) == 1
        inv = ctx.investigations[0]
        assert inv.service == "svc-a"
        assert "Check current status of svc-a" in inv.task

    @pytest.mark.asyncio
    async def test_dispatch_increments_counter(self):
        ctx = _make_ctx(dispatch_count=1, dispatch_cap=3)
        mock_agent = AsyncMock()
        mock_agent.agent_id = "agent-1"
        ctx.provisioner.ensure_agent = AsyncMock(return_value=mock_agent)

        with patch("src.agents.dispatch.dispatch_to_agent",
                   new_callable=AsyncMock, return_value=("ok", None)):
            await execute_tool("dispatch_investigation", {"service": "svc-a"}, ctx)
        assert ctx.dispatch_count == 2


# =========================================================================
# create_issue
# =========================================================================

class TestCreateIncident:
    @pytest.mark.asyncio
    async def test_no_smartsheet_adapter(self):
        ctx = _make_ctx(smartsheet_adapter=None)
        result = await execute_tool("create_issue", {
            "platform": "Konflux", "summary": "test",
            "affected_events": ["evt-1"],
        }, ctx)
        assert "not configured" in result
        assert len(ctx.created_incidents) == 0

    @pytest.mark.asyncio
    async def test_successful_creation(self):
        ctx = _make_ctx()
        ctx.smartsheet_adapter.create_incident = AsyncMock(
            return_value={"row_id": 12345, "sheet_url": "https://ss.com/row/12345"},
        )
        result = await execute_tool("create_issue", {
            "platform": "Konflux", "summary": "Pipeline failures",
            "description": "All s390x pipelines failing",
            "priority": "Critical", "status": "New",
            "affected_events": ["evt-1", "evt-2"],
        }, ctx)
        assert "Incident created" in result
        assert "12345" in result
        assert len(ctx.created_incidents) == 1
        inc = ctx.created_incidents[0]
        assert inc.platform == "Konflux"
        assert inc.affected_events == ["evt-1", "evt-2"]
        assert inc.smartsheet_row_id == "12345"

    @pytest.mark.asyncio
    async def test_system_fields_populated(self):
        """create_incident must add Labels, Components, Reporter from env."""
        ctx = _make_ctx()
        captured_fields = {}

        async def capture_fields(fields):
            captured_fields.update(fields)
            return {"row_id": 1, "sheet_url": ""}

        ctx.smartsheet_adapter.create_incident = capture_fields
        await execute_tool("create_issue", {
            "platform": "P", "summary": "S", "affected_events": ["e"],
        }, ctx)
        assert captured_fields["Labels"] == "darwin-auto, release-incident"
        assert captured_fields["Components"] == "CNV CI and Release"
        assert captured_fields["Issue Type"] == "Task"

    @pytest.mark.asyncio
    async def test_smartsheet_error_handled(self):
        ctx = _make_ctx()
        ctx.smartsheet_adapter.create_incident = AsyncMock(
            side_effect=RuntimeError("API 500"),
        )
        result = await execute_tool("create_issue", {
            "platform": "P", "summary": "S", "affected_events": [],
        }, ctx)
        assert "Failed to create incident" in result
        assert len(ctx.created_incidents) == 0


# =========================================================================
# post_shift_summary
# =========================================================================

class TestPostShiftSummary:
    @pytest.mark.asyncio
    async def test_slack_configured(self):
        ctx = _make_ctx()
        ctx.slack_notify = AsyncMock()
        result = await execute_tool(
            "post_shift_summary", {"summary": "Shift done. 1 incident."}, ctx,
        )
        assert "posted to Slack" in result
        ctx.slack_notify.assert_awaited_once_with("Shift done. 1 incident.")
        assert ctx._summary_text == "Shift done. 1 incident."

    @pytest.mark.asyncio
    async def test_slack_not_configured(self):
        ctx = _make_ctx(slack_notify=None)
        result = await execute_tool(
            "post_shift_summary", {"summary": "text"}, ctx,
        )
        assert "not configured" in result
        assert ctx._summary_text == "text"

    @pytest.mark.asyncio
    async def test_slack_error_handled(self):
        ctx = _make_ctx()
        ctx.slack_notify = AsyncMock(side_effect=RuntimeError("Slack down"))
        result = await execute_tool(
            "post_shift_summary", {"summary": "text"}, ctx,
        )
        assert "failed" in result
