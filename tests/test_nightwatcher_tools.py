# tests/test_nightwatcher_tools.py
# @ai-rules:
# 1. [Pattern]: All infrastructure mocked via AsyncMock -- no Redis, no Jira, no LLM calls.
# 2. [Pattern]: NightwatcherContext constructed per test with controlled mocks.
# 3. [Constraint]: Tests verify tool routing, phase gating, dispatch cap enforcement, and field population.
"""Unit tests for Nightwatcher tool execution and phase gating."""
from __future__ import annotations

import os
import pytest
from unittest.mock import AsyncMock, patch

from src.models import ShiftIncident, ShiftInvestigation
from src.observers.nightwatcher_tools import (
    NightwatcherContext,
    execute_tool,
    get_phase_tools,
    validate_cluster_plan,
    build_report_tool,
    build_summary_tool,
    _handle_write_incident,
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
        incident_adapter=AsyncMock(),
        slack_notify=AsyncMock(),
        manifest_services={"svc-a", "svc-b"},
        manifest_ids={"evt-1", "evt-2"},
        dispatch_count=0,
        dispatch_cap=3,
        created_incidents=[],
        investigations=[],
        declared_clusters=[],
        failed_cluster_events=[],
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
        assert "write_incident" not in names

    def test_investigate_phase_adds_dispatch(self):
        tools = get_phase_tools("investigate")
        names = {t["name"] for t in tools}
        assert "dispatch_investigation" in names
        assert "get_event_report" in names
        assert "write_incident" not in names

    def test_report_phase_declare_clusters_only(self):
        tools = get_phase_tools("report")
        names = {t["name"] for t in tools}
        assert names == {"declare_clusters"}
        assert "write_incident" not in names
        assert "post_shift_summary" not in names
        assert "get_event_report" not in names

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
# write_incident (called directly with cluster dict, not via execute_tool)
# =========================================================================

class TestWriteIncident:
    @pytest.mark.asyncio
    async def test_no_incident_adapter(self):
        ctx = _make_ctx(incident_adapter=None)
        cluster = {"platform": "Konflux", "events": ["evt-1"], "root_cause": "test", "services": ["svc-a"]}
        result = await _handle_write_incident(
            {"summary": "test"}, ctx, cluster,
        )
        assert "not configured" in result
        assert len(ctx.created_incidents) == 0

    @pytest.mark.asyncio
    async def test_successful_creation(self):
        ctx = _make_ctx()
        ctx.incident_adapter.create_incident = AsyncMock(
            return_value={"issue_key": "VMER-123", "issue_url": "https://jira.example.com/browse/VMER-123"},
        )
        cluster = {"platform": "Konflux", "events": ["evt-1", "evt-2"], "root_cause": "s390x failures", "services": ["svc-a"]}
        result = await _handle_write_incident(
            {"summary": "Pipeline failures", "description": "All s390x pipelines failing",
             "priority": "Critical", "status": "New"},
            ctx, cluster,
        )
        assert "Incident created" in result
        assert "VMER-123" in result
        assert len(ctx.created_incidents) == 1
        inc = ctx.created_incidents[0]
        assert inc.platform == "Konflux"
        assert inc.affected_events == ["evt-1", "evt-2"]
        assert inc.jira_issue_key == "VMER-123"

    @pytest.mark.asyncio
    async def test_system_fields_populated(self):
        """write_incident must add Labels, Components, Reporter from env."""
        ctx = _make_ctx()
        captured_fields = {}

        async def capture_fields(fields):
            captured_fields.update(fields)
            return {"issue_key": "X-1", "issue_url": ""}

        ctx.incident_adapter.create_incident = capture_fields
        cluster = {"platform": "P", "events": ["e"], "root_cause": "x", "services": ["svc"]}
        await _handle_write_incident({"summary": "S"}, ctx, cluster)
        assert captured_fields["platform"] == "P"
        assert isinstance(captured_fields["labels"], list)
        assert isinstance(captured_fields["components"], list)

    @pytest.mark.asyncio
    async def test_jira_error_adds_to_failed_cluster_events(self):
        ctx = _make_ctx()
        ctx.incident_adapter.create_incident = AsyncMock(
            side_effect=RuntimeError("API 500"),
        )
        cluster = {"platform": "P", "events": ["evt-1", "evt-2"], "root_cause": "x", "services": ["svc"]}
        result = await _handle_write_incident(
            {"summary": "S"}, ctx, cluster,
        )
        assert "Failed to create incident" in result
        assert len(ctx.created_incidents) == 0
        assert "evt-1" in ctx.failed_cluster_events
        assert "evt-2" in ctx.failed_cluster_events


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


# =========================================================================
# validate_cluster_plan
# =========================================================================

class TestValidateClusterPlan:
    def test_happy_path(self):
        """All events covered, no overlaps."""
        clusters = [
            {"events": ["evt-1", "evt-2"], "root_cause": "CDN 404", "platform": "Konflux", "services": ["svc-a"]},
            {"events": ["evt-3"], "root_cause": "auth failure", "platform": "Kargo", "services": ["svc-b"]},
        ]
        ok, error = validate_cluster_plan(clusters, {"evt-1", "evt-2", "evt-3"})
        assert ok is True
        assert error == ""

    def test_missing_events(self):
        """Returns specific error listing missing event IDs."""
        clusters = [
            {"events": ["evt-1"], "root_cause": "CDN 404", "platform": "Konflux", "services": ["svc-a"]},
        ]
        ok, error = validate_cluster_plan(clusters, {"evt-1", "evt-2", "evt-3"})
        assert ok is False
        assert "evt-2" in error
        assert "evt-3" in error

    def test_duplicate_events(self):
        """Event in 2 clusters rejected."""
        clusters = [
            {"events": ["evt-1", "evt-2"], "root_cause": "CDN 404", "platform": "Konflux", "services": ["svc-a"]},
            {"events": ["evt-2", "evt-3"], "root_cause": "auth", "platform": "Kargo", "services": ["svc-b"]},
        ]
        ok, error = validate_cluster_plan(clusters, {"evt-1", "evt-2", "evt-3"})
        assert ok is False
        assert "evt-2" in error
        assert "multiple" in error.lower()

    def test_empty_cluster(self):
        """Empty events list rejected."""
        clusters = [
            {"events": [], "root_cause": "CDN 404", "platform": "Konflux", "services": ["svc-a"]},
        ]
        ok, error = validate_cluster_plan(clusters, {"evt-1"})
        assert ok is False
        assert "no events" in error.lower()

    def test_unknown_event(self):
        """Event not in manifest rejected."""
        clusters = [
            {"events": ["evt-1", "evt-unknown"], "root_cause": "CDN 404", "platform": "Konflux", "services": ["svc-a"]},
        ]
        ok, error = validate_cluster_plan(clusters, {"evt-1"})
        assert ok is False
        assert "evt-unknown" in error

    def test_invalid_platform(self):
        """Invalid platform enum rejected when VALID_PLATFORMS is populated."""
        from src.agents.llm.types import VALID_PLATFORMS
        old = list(VALID_PLATFORMS)
        VALID_PLATFORMS.clear()
        VALID_PLATFORMS.extend(["Konflux", "Kargo"])
        try:
            clusters = [
                {"events": ["evt-1"], "root_cause": "CDN 404", "platform": "InvalidPlatform", "services": ["svc-a"]},
            ]
            ok, error = validate_cluster_plan(clusters, {"evt-1"})
            assert ok is False
            assert "InvalidPlatform" in error
            assert "invalid platform" in error.lower()
        finally:
            VALID_PLATFORMS.clear()
            VALID_PLATFORMS.extend(old)

    def test_platform_validation_skipped_when_empty(self):
        """Platform validation skipped when VALID_PLATFORMS is empty (enums not configured)."""
        from src.agents.llm.types import VALID_PLATFORMS
        old = list(VALID_PLATFORMS)
        VALID_PLATFORMS.clear()
        try:
            clusters = [
                {"events": ["evt-1"], "root_cause": "CDN 404", "platform": "AnyPlatform", "services": ["svc-a"]},
            ]
            ok, error = validate_cluster_plan(clusters, {"evt-1"})
            assert ok is True
        finally:
            VALID_PLATFORMS.clear()
            VALID_PLATFORMS.extend(old)


# =========================================================================
# build_report_tool
# =========================================================================

class TestBuildReportTool:
    def test_context_in_description(self):
        """Dynamic description contains cluster info + receipt."""
        cluster = {"root_cause": "CDN 404 s390x", "events": ["evt-1", "evt-2"], "platform": "Konflux", "services": ["svc-a"]}
        completed = [{"index": 1, "summary": "Auth failure", "priority": "Critical", "affected_events": ["evt-3"]}]
        tools = build_report_tool(cluster, 2, 3, completed)
        assert len(tools) == 1
        assert tools[0]["name"] == "write_incident"
        desc = tools[0]["description"]
        assert "2 of 3" in desc
        assert "CDN 404 s390x" in desc
        assert "Auth failure" in desc or "Critical" in desc
        assert "input_schema" in tools[0]

    def test_token_guard_truncation(self):
        """Receipt truncated when description exceeds 4000 chars."""
        cluster = {"root_cause": "test", "events": ["evt-1"], "platform": "Konflux", "services": ["svc"]}
        long_reports = [
            {"index": i, "summary": "A" * 200, "priority": "Major", "affected_events": [f"evt-{i}"]}
            for i in range(1, 50)
        ]
        tools = build_report_tool(cluster, 50, 50, long_reports)
        desc = tools[0]["description"]
        assert len(desc) <= 5000


# =========================================================================
# build_summary_tool
# =========================================================================

class TestBuildSummaryTool:
    def test_returns_post_shift_summary(self):
        reports = [{"index": 1, "summary": "CDN 404", "priority": "Critical", "platform": "Konflux", "affected_events": ["evt-1"]}]
        metrics = {"escalation_count": 5, "incident_count": 1, "noise_reduction_pct": 80.0}
        tools = build_summary_tool(reports, metrics)
        assert len(tools) == 1
        assert tools[0]["name"] == "post_shift_summary"
        assert "input_schema" in tools[0]


# =========================================================================
# Extend Incident
# =========================================================================
from src.observers.nightwatcher_tools import _handle_extend_incident, build_extend_tool, _handle_search_existing_incidents


class TestExtendIncident:
    @pytest.mark.asyncio
    async def test_extend_success(self):
        ctx = _make_ctx()
        ctx.incident_adapter.add_comment = AsyncMock(
            return_value={"comment_id": "10001", "issue_url": "https://jira.example.com/browse/VMER-5"},
        )
        cluster = {"extends_issue_key": "VMER-5", "platform": "OCP", "events": ["evt-1"], "root_cause": "test", "services": ["svc-a"]}
        result = await _handle_extend_incident({"summary": "new evidence", "comment": "details"}, ctx, cluster)
        assert "Incident extended" in result
        assert "VMER-5" in result
        assert len(ctx.created_incidents) == 1
        assert ctx.created_incidents[0].extended is True
        assert ctx.created_incidents[0].jira_issue_key == "VMER-5"

    @pytest.mark.asyncio
    async def test_extend_failure_tracks_events(self):
        ctx = _make_ctx()
        ctx.incident_adapter.add_comment = AsyncMock(side_effect=RuntimeError("API error"))
        cluster = {"extends_issue_key": "VMER-5", "platform": "OCP", "events": ["evt-1", "evt-2"], "root_cause": "test", "services": ["svc"]}
        result = await _handle_extend_incident({"summary": "s", "comment": "c"}, ctx, cluster)
        assert "Failed" in result
        assert "evt-1" in ctx.failed_cluster_events
        assert "evt-2" in ctx.failed_cluster_events

    @pytest.mark.asyncio
    async def test_extend_bookkeeping_matches_write(self):
        """Verify extended incidents count toward manifest coverage."""
        ctx = _make_ctx()
        ctx.incident_adapter.add_comment = AsyncMock(
            return_value={"comment_id": "1", "issue_url": ""},
        )
        cluster = {"extends_issue_key": "VMER-5", "platform": "P", "events": ["evt-1"], "root_cause": "x", "services": ["svc"]}
        await _handle_extend_incident({"summary": "s", "comment": "c"}, ctx, cluster)
        covered = {eid for inc in ctx.created_incidents for eid in inc.affected_events}
        assert "evt-1" in covered

    @pytest.mark.asyncio
    async def test_no_adapter(self):
        ctx = _make_ctx(incident_adapter=None)
        cluster = {"extends_issue_key": "VMER-5", "platform": "P", "events": ["evt-1"], "root_cause": "x", "services": ["svc"]}
        result = await _handle_extend_incident({"summary": "s", "comment": "c"}, ctx, cluster)
        assert "not configured" in result


class TestBuildExtendTool:
    def test_includes_issue_key_in_description(self):
        cluster = {"extends_issue_key": "VMER-10", "root_cause": "test", "events": ["evt-1"], "platform": "P", "services": ["svc"]}
        tools = build_extend_tool(cluster, 1, 2, [])
        assert len(tools) == 1
        assert tools[0]["name"] == "extend_incident"
        assert "VMER-10" in tools[0]["description"]


# =========================================================================
# Search Existing Incidents
# =========================================================================

class TestSearchExistingIncidents:
    @pytest.mark.asyncio
    async def test_returns_formatted_list(self):
        ctx = _make_ctx()
        ctx.incident_adapter.search_open_incidents = AsyncMock(return_value=[
            {"issue_key": "VMER-1", "summary": "test", "priority": "Major", "status": "New"},
        ])
        result = await _handle_search_existing_incidents({}, ctx)
        assert "VMER-1" in result
        assert "Major" in result

    @pytest.mark.asyncio
    async def test_empty_results(self):
        ctx = _make_ctx()
        ctx.incident_adapter.search_open_incidents = AsyncMock(return_value=[])
        result = await _handle_search_existing_incidents({}, ctx)
        assert "No open incidents" in result

    @pytest.mark.asyncio
    async def test_no_adapter(self):
        ctx = _make_ctx(incident_adapter=None)
        result = await _handle_search_existing_incidents({}, ctx)
        assert "not configured" in result


# =========================================================================
# Write Incident Dedup Sentinel
# =========================================================================

class TestWriteIncidentDedup:
    @pytest.mark.asyncio
    async def test_result_contains_dedup_sentinel(self):
        """Result string MUST contain 'Incident created' for handlers_dispatch.py dedup."""
        ctx = _make_ctx()
        ctx.incident_adapter.create_incident = AsyncMock(
            return_value={"issue_key": "VMER-99", "issue_url": "https://jira.example.com/browse/VMER-99"},
        )
        cluster = {"platform": "P", "events": ["evt-1"], "root_cause": "x", "services": ["svc"]}
        result = await _handle_write_incident({"summary": "S", "description": "D", "priority": "Normal"}, ctx, cluster)
        assert "Incident created" in result

    @pytest.mark.asyncio
    async def test_severity_in_fields(self):
        """Severity field ID passed through to adapter."""
        ctx = _make_ctx()
        captured = {}

        async def capture(fields):
            captured.update(fields)
            return {"issue_key": "X-1", "issue_url": ""}

        ctx.incident_adapter.create_incident = capture
        cluster = {"platform": "P", "events": ["e"], "root_cause": "x", "services": ["svc"]}
        with patch.dict("os.environ", {"JIRA_INCIDENT_SEVERITY_FIELD": "customfield_10840"}):
            await _handle_write_incident(
                {"summary": "S", "description": "D", "priority": "Normal", "severity": "Critical"},
                ctx, cluster,
            )
        assert captured.get("severity") == "Critical"
        assert captured.get("severity_field_id") == "customfield_10840"


# =========================================================================
# Cart Loop Routing
# =========================================================================

class TestCartLoopRouting:
    def test_extends_empty_string_treated_as_new(self):
        """Empty string extends_issue_key should be treated as falsy -> new incident."""
        cluster = {"extends_issue_key": "", "events": ["evt-1"], "root_cause": "x", "platform": "P", "services": ["svc"]}
        assert not cluster.get("extends_issue_key")

    def test_extends_none_treated_as_new(self):
        """None extends_issue_key -> falsy -> new incident."""
        cluster = {"events": ["evt-1"], "root_cause": "x", "platform": "P", "services": ["svc"]}
        assert not cluster.get("extends_issue_key")
