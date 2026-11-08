# tests/test_nightwatcher_tools.py
# @ai-rules:
# 1. [Pattern]: All infrastructure mocked via AsyncMock -- no Redis, no Jira, no LLM calls.
# 2. [Pattern]: NightwatcherContext constructed per test with controlled mocks.
# 3. [Constraint]: Tests verify tool routing, phase gating, dispatch cap enforcement, and field population.
"""Unit tests for Nightwatcher tool execution and phase gating."""
from __future__ import annotations

import copy
import os
import pytest
from unittest.mock import AsyncMock, patch

from src.models import ShiftIncident, ShiftInvestigation
from src.observers.nightwatcher_tools import (
    NightwatcherContext,
    execute_tool,
    get_phase_tools,
    validate_cluster_plan,
    reconcile_cluster_plan,
    build_report_tool,
    build_summary_tool,
    _handle_declare_clusters,
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
        ctx.archivist.get_memory = AsyncMock(return_value=None)
        ctx.blackboard.get_report = AsyncMock(side_effect=RuntimeError("boom"))
        result = await execute_tool("get_event_report", {"event_id": "evt-1"}, ctx)
        assert "Tool error" in result
        assert "boom" in result


# =========================================================================
# get_event_report
# =========================================================================

class TestGetEventReport:
    @pytest.mark.asyncio
    async def test_returns_digest_when_archive_exists(self):
        ctx = _make_ctx()
        ctx.archivist.get_memory = AsyncMock(return_value={
            "id": "point-1",
            "payload": {
                "service": "release-console",
                "symptom": "CPU spike",
                "root_cause": "runaway loop",
                "fix_action": "restarted pod",
                "outcome": "resolved",
                "domain": "complicated",
                "duration_seconds": 120,
                "turns": 5,
                "procedures": ["checked logs", "restarted pod"],
            },
        })
        result = await execute_tool("get_event_report", {"event_id": "evt-1"}, ctx)
        assert "CPU spike" in result
        assert "runaway loop" in result
        assert "resolved" in result
        assert "checked logs" in result
        ctx.blackboard.get_report.assert_not_called()

    @pytest.mark.asyncio
    async def test_digest_handles_procedures_as_string(self):
        """_archive_event_fallback sets procedures='unknown' (string, not list)."""
        ctx = _make_ctx()
        ctx.archivist.get_memory = AsyncMock(return_value={
            "id": "point-1",
            "payload": {
                "service": "test-svc", "symptom": "crash",
                "root_cause": "?", "fix_action": "?",
                "outcome": "escalated", "domain": "complex",
                "duration_seconds": 60, "turns": 2,
                "procedures": "unknown",
            },
        })
        result = await execute_tool("get_event_report", {"event_id": "evt-1"}, ctx)
        assert "Procedures: unknown" in result
        assert "u; n; k" not in result

    @pytest.mark.asyncio
    async def test_falls_back_to_markdown_when_archive_missing(self):
        ctx = _make_ctx()
        ctx.archivist.get_memory = AsyncMock(return_value=None)
        ctx.blackboard.get_report = AsyncMock(return_value={"markdown": "# Report\nCPU spike."})
        result = await execute_tool("get_event_report", {"event_id": "evt-1"}, ctx)
        assert "CPU spike" in result

    @pytest.mark.asyncio
    async def test_fallback_returns_tail_for_long_reports(self):
        ctx = _make_ctx()
        ctx.archivist.get_memory = AsyncMock(return_value=None)
        body = "x" * 20000 + "TAIL_MARKER"
        ctx.blackboard.get_report = AsyncMock(return_value={"markdown": body})
        result = await execute_tool("get_event_report", {"event_id": "evt-1"}, ctx)
        assert "TAIL_MARKER" in result
        assert len(result) <= 10011

    @pytest.mark.asyncio
    async def test_falls_back_when_digest_payload_malformed(self):
        """Malformed Qdrant payload triggers formatting error -> logged, falls back to markdown."""
        ctx = _make_ctx()
        ctx.archivist.get_memory = AsyncMock(return_value={"payload": "not-a-dict"})
        ctx.blackboard.get_report = AsyncMock(return_value={"markdown": "# Report\nCPU spike."})
        result = await execute_tool("get_event_report", {"event_id": "evt-1"}, ctx)
        assert "Report" in result
        assert "CPU spike" in result

    @pytest.mark.asyncio
    async def test_missing_report(self):
        ctx = _make_ctx()
        ctx.archivist.get_memory = AsyncMock(return_value=None)
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
    def test_empty_clusters_with_auto_reconcile_succeeds(self):
        """VMER-2272-V1: empty clusters list is permitted when auto_reconcile=True."""
        ok, error = validate_cluster_plan([], {"evt-1", "evt-2"}, auto_reconcile=True)
        assert ok is True
        assert error == ""

    def test_empty_clusters_without_auto_reconcile_fails(self):
        """VMER-2272-V2: empty clusters list is rejected when auto_reconcile=False."""
        ok, error = validate_cluster_plan([], {"evt-1", "evt-2"}, auto_reconcile=False)
        assert ok is False
        assert error == "No clusters declared. You must create at least one cluster."

    def test_happy_path(self):
        """All events covered, no overlaps."""
        clusters = [
            {"events": ["evt-1", "evt-2"], "root_cause": "CDN 404", "platform": "Konflux", "services": ["svc-a"]},
            {"events": ["evt-3"], "root_cause": "auth failure", "platform": "Kargo", "services": ["svc-b"]},
        ]
        ok, error = validate_cluster_plan(clusters, {"evt-1", "evt-2", "evt-3"})
        assert ok is True
        assert error == ""

    def test_missing_events_without_auto_reconcile(self):
        """Returns specific error listing missing event IDs when auto_reconcile=False."""
        clusters = [
            {"events": ["evt-1"], "root_cause": "CDN 404", "platform": "Konflux", "services": ["svc-a"]},
        ]
        ok, error = validate_cluster_plan(clusters, {"evt-1", "evt-2", "evt-3"}, auto_reconcile=False)
        assert ok is False
        assert "evt-2" in error
        assert "evt-3" in error

    def test_auto_reconcile_defaults_to_false(self):
        """M6: omitting auto_reconcile must reject unassigned events (no silent fabrication)."""
        clusters = [
            {"events": ["evt-1"], "root_cause": "CDN 404", "platform": "Konflux", "services": ["svc-a"]},
        ]
        ok, error = validate_cluster_plan(clusters, {"evt-1", "evt-2"})
        assert ok is False
        assert "evt-2" in error

    def test_validate_never_mutates_clusters_even_with_auto_reconcile(self):
        """M6: validate_cluster_plan is pure -- the caller's list is untouched."""
        clusters = [
            {"events": ["evt-1"], "root_cause": "CDN 404", "platform": "Konflux", "services": ["svc-a"]},
        ]
        snapshot = copy.deepcopy(clusters)
        ok, error = validate_cluster_plan(clusters, {"evt-1", "evt-2", "evt-3"}, auto_reconcile=True)
        assert ok is True
        assert error == ""
        assert clusters == snapshot

    def test_auto_reconcile_still_rejects_unknown_and_duplicate_ids(self):
        """auto_reconcile only tolerates MISSING ids; unknown/duplicate stay fatal."""
        unknown = [{"events": ["evt-1", "evt-x"], "root_cause": "r", "platform": "Konflux", "services": []}]
        assert validate_cluster_plan(unknown, {"evt-1", "evt-2"}, auto_reconcile=True)[0] is False
        dup = [
            {"events": ["evt-1"], "root_cause": "r", "platform": "Konflux", "services": []},
            {"events": ["evt-1"], "root_cause": "r", "platform": "Konflux", "services": []},
        ]
        assert validate_cluster_plan(dup, {"evt-1", "evt-2"}, auto_reconcile=True)[0] is False

    def test_reconcile_returns_new_list_with_flagged_fallback(self):
        """M6: fallback cluster has root_cause/services (so report builders don't render '?')."""
        clusters = [
            {"events": ["evt-1"], "root_cause": "CDN 404", "platform": "Konflux", "services": ["svc-a"]},
        ]
        snapshot = copy.deepcopy(clusters)
        result = reconcile_cluster_plan(clusters, {"evt-1", "evt-2", "evt-3"})
        assert clusters == snapshot, "caller's list must not be mutated"
        assert result is not clusters
        assert len(result) == 2
        fallback = result[1]
        assert set(fallback["events"]) == {"evt-2", "evt-3"}
        assert fallback["events"] == sorted(fallback["events"])
        assert fallback["auto_reconciled"] is True
        assert fallback["root_cause"] and "NOT a shared root cause" in fallback["root_cause"]
        assert isinstance(fallback["services"], list)
        assert "platform" in fallback

    def test_reconcile_noop_when_nothing_missing(self):
        clusters = [{"events": ["evt-1"], "root_cause": "r", "platform": "Konflux", "services": []}]
        result = reconcile_cluster_plan(clusters, {"evt-1"})
        assert result == clusters
        assert result is not clusters

    def test_reconcile_platform_is_deterministic_from_missing_events(self):
        """Platform comes from the unassigned events themselves (majority, alphabetical tie-break)."""
        from src.agents.llm.types import VALID_PLATFORMS
        from src.models import StagedEscalation
        old = list(VALID_PLATFORMS)
        VALID_PLATFORMS.clear()
        VALID_PLATFORMS.extend(["Konflux", "Kargo", "General"])
        try:
            def esc(eid, platform, service="svc"):
                return StagedEscalation(event_id=eid, service=service, source="aligner",
                                        reason="r", summary="s", platform=platform)
            by_id = {
                "evt-1": esc("evt-1", "Konflux"),
                "evt-2": esc("evt-2", "Kargo", "svc-b"),
                "evt-3": esc("evt-3", "Kargo", "svc-a"),
                "evt-4": esc("evt-4", "Bogus"),
            }
            clusters = [{"events": ["evt-1"], "root_cause": "r", "platform": "Konflux", "services": []}]
            ids = set(by_id)
            runs = [reconcile_cluster_plan(clusters, ids, by_id)[-1] for _ in range(5)]
            assert {r["platform"] for r in runs} == {"Kargo"}  # majority of missing events
            assert runs[0]["services"] == ["svc", "svc-a", "svc-b"]
            # no usable per-event platform -> falls back to declared clusters
            no_info = reconcile_cluster_plan(clusters, {"evt-1", "evt-9"}, None)[-1]
            assert no_info["platform"] == "Konflux"
            # nothing at all -> first SORTED valid platform, independent of list order
            VALID_PLATFORMS[:] = ["Kargo", "General", "Konflux"]
            empty_clusters = [{"events": ["evt-1"], "root_cause": "r", "platform": "", "services": []}]
            assert reconcile_cluster_plan(empty_clusters, {"evt-1", "evt-2"}, None)[-1]["platform"] == "General"
        finally:
            VALID_PLATFORMS.clear()
            VALID_PLATFORMS.extend(old)

    @pytest.mark.asyncio
    async def test_handle_declare_clusters_reconciles_without_mutating_args(self):
        """The handler stores reconciled clusters on ctx but leaves the LLM args list intact."""
        ctx = _make_ctx(manifest_ids={"evt-1", "evt-2"})
        args = {"clusters": [{"events": ["evt-1"], "root_cause": "r", "platform": "Konflux", "services": []}]}
        snapshot = copy.deepcopy(args)
        result = await _handle_declare_clusters(args, ctx, auto_reconcile=True)
        assert "accepted" in result
        assert args == snapshot
        assert len(ctx.declared_clusters) == 2
        assert ctx.declared_clusters[1]["events"] == ["evt-2"]
        # default (no reconcile) rejects and stores nothing
        ctx2 = _make_ctx(manifest_ids={"evt-1", "evt-2"})
        rejected = await _handle_declare_clusters(args, ctx2)
        assert "validation failed" in rejected
        assert ctx2.declared_clusters == []

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


# =========================================================================
# VMER-2272: guard branches (malformed LLM payloads) + salvage_cluster_plan
# =========================================================================

class TestVmer2272ClusterPlanGuards:
    IDS = {"evt-1", "evt-2"}

    @pytest.mark.parametrize("clusters,needle", [
        ("not-a-list", "must be a list"),
        ([None], "not a valid object"),
        (["str"], "not a valid object"),
        ([{"events": "evt-1"}], "no events"),
        ([{"events": None}], "no events"),
        ([{"events": [123]}], "non-string event ID"),
    ])
    def test_validate_rejects_malformed_payloads(self, clusters, needle):
        ok, err = validate_cluster_plan(clusters, self.IDS)
        assert ok is False and needle in err

    def test_validate_none_clusters_is_treated_as_empty(self):
        assert validate_cluster_plan(None, self.IDS)[0] is False
        assert validate_cluster_plan(None, self.IDS, auto_reconcile=True) == (True, "")

    def test_reconcile_none_clusters_materialises_single_fallback_cluster(self):
        plan = reconcile_cluster_plan(None, self.IDS)
        assert len(plan) == 1 and plan[0]["auto_reconciled"] is True
        assert plan[0]["events"] == ["evt-1", "evt-2"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("args", [{"clusters": "oops"}, {"clusters": {"events": ["evt-1"]}}])
    async def test_handle_declare_clusters_rejects_non_list(self, args):
        ctx = NightwatcherContext(blackboard=AsyncMock(), archivist=AsyncMock(), provisioner=AsyncMock(),
                                  registry=AsyncMock(), bridge=AsyncMock(), incident_adapter=AsyncMock(),
                                  slack_notify=AsyncMock(), manifest_ids=set(self.IDS))
        out = await _handle_declare_clusters(args, ctx, auto_reconcile=True)
        assert "must be a list" in out and ctx.declared_clusters == []

    @pytest.mark.asyncio
    async def test_handle_declare_clusters_none_clusters_with_auto_reconcile_builds_fallback(self):
        ctx = NightwatcherContext(blackboard=AsyncMock(), archivist=AsyncMock(), provisioner=AsyncMock(),
                                  registry=AsyncMock(), bridge=AsyncMock(), incident_adapter=AsyncMock(),
                                  slack_notify=AsyncMock(), manifest_ids=set(self.IDS))
        out = await _handle_declare_clusters({"clusters": None}, ctx, auto_reconcile=True)
        assert out.startswith("Cluster plan accepted")
        assert ctx.declared_clusters[0]["auto_reconciled"] is True


class TestVmer2272SalvageClusterPlan:
    IDS = {"evt-1", "evt-2", "evt-3"}

    def test_non_list_and_none_yield_empty(self):
        from src.observers.nightwatcher_tools import salvage_cluster_plan
        assert salvage_cluster_plan(None, self.IDS) == []
        assert salvage_cluster_plan("x", self.IDS) == []
        assert salvage_cluster_plan({"events": ["evt-1"]}, self.IDS) == []

    def test_drops_unusable_clusters_and_strips_bad_ids_first_claim_wins(self):
        from src.observers.nightwatcher_tools import salvage_cluster_plan
        src = [
            "junk",
            {"events": "evt-1"},
            {"events": ["evt-1", 7, "evt-ghost"], "root_cause": "a", "extends_issue_key": "VMER-1"},
            {"events": ["evt-1", "evt-2"], "root_cause": "b"},
            {"events": ["evt-ghost"], "root_cause": "c"},
        ]
        snapshot = copy.deepcopy(src)
        out = salvage_cluster_plan(src, self.IDS)
        assert [(c["root_cause"], c["events"]) for c in out] == [("a", ["evt-1"]), ("b", ["evt-2"])]
        assert out[0]["extends_issue_key"] == "VMER-1"
        assert src == snapshot                               # pure: input untouched
        out[0]["events"].append("zzz")
        assert src == snapshot                               # no aliasing

    def test_invalid_platform_is_coerced_only_when_platforms_are_configured(self, monkeypatch):
        from src.observers import nightwatcher_tools as nt
        from src.observers.nightwatcher_tools import salvage_cluster_plan
        clusters = [{"events": ["evt-1"], "platform": "bogus"}]
        monkeypatch.setattr(nt, "VALID_PLATFORMS", [])
        assert salvage_cluster_plan(clusters, self.IDS)[0]["platform"] == "bogus"      # no allow-list -> untouched
        monkeypatch.setattr(nt, "VALID_PLATFORMS", ["gitlab", "kargo"])
        assert salvage_cluster_plan(clusters, self.IDS)[0]["platform"] == "gitlab"     # deterministic fallback
