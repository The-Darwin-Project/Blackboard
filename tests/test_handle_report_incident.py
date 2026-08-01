# tests/test_handle_report_incident.py
# @ai-rules:
# 1. [Constraint]: Pure unit tests -- mock ToolContext + BlackboardState, no real Redis, no Jira.
# 2. [Pattern]: Mirrors test_handle_close_event.py's ToolContext-mock convention.
# 3. [Gotcha]: handle_report_incident is async -- pytest.ini sets asyncio_mode=auto.
"""Tests for handle_report_incident's incident_references persistence (T-11/T-12,
plan: terminal-state-close-gate, Step 2) -- the prerequisite for GitHub #155's
open-incident close-gate."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.handlers_dispatch import handle_report_incident
from src.models import EventEvidence, EventInput


def _event_doc(source: str = "aligner", conversation=None):
    return SimpleNamespace(
        id="evt-1",
        source=source,
        service="test-svc",
        subject_type="service",
        slack_thread_ts=None,
        slack_channel_id=None,
        conversation=conversation or [],
        event=EventInput(
            reason="anomaly",
            evidence=EventEvidence(display_text="test", source_type=source, severity="warning"),
        ),
    )


def _mock_ctx(event=None):
    bb = AsyncMock()
    bb.get_event = AsyncMock(return_value=event)
    bb.stage_escalation = AsyncMock()
    bb.add_incident_reference = AsyncMock()
    bb.set_escalation_flag = AsyncMock()
    ctx = AsyncMock()
    ctx.get_blackboard = MagicMock(return_value=bb)
    ctx.has_incident_been_created = MagicMock(return_value=False)
    ctx.mark_incident_created = MagicMock()
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock(return_value=1)
    ctx.get_incident_adapter = MagicMock(return_value=None)
    return ctx, bb


class TestNightwatcherStagedIncidentReference:
    """T-12: the Nightwatcher-staged branch persists a placeholder incident
    reference in "nightwatcher-staged:{staged_at}" format."""

    @pytest.mark.asyncio
    async def test_staged_branch_calls_add_incident_reference_with_placeholder(self, monkeypatch):
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "true")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)

        result = await handle_report_incident(
            ctx, "evt-1", {"summary": "anomaly detected", "description": "details"}, None,
        )

        assert result is True
        bb.add_incident_reference.assert_awaited_once()
        call_args = bb.add_incident_reference.call_args
        assert call_args.args[0] == "evt-1"
        ref = call_args.args[1]
        assert ref.startswith("nightwatcher-staged:")
        # The suffix must be the StagedEscalation's own staged_at timestamp --
        # parseable as a float, not a placeholder string.
        float(ref.removeprefix("nightwatcher-staged:"))

    @pytest.mark.asyncio
    async def test_staged_branch_marks_incident_created(self, monkeypatch):
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "true")
        event = _event_doc(source="headhunter")
        ctx, bb = _mock_ctx(event)

        await handle_report_incident(ctx, "evt-1", {"summary": "s"}, None)

        ctx.mark_incident_created.assert_called_once_with("evt-1")

    @pytest.mark.asyncio
    async def test_non_automated_source_does_not_stage_or_persist_reference(self, monkeypatch):
        """report_incident is only available for automated sources -- chat/slack
        must neither stage an escalation nor add an incident_reference."""
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "true")
        event = _event_doc(source="chat")
        ctx, bb = _mock_ctx(event)

        result = await handle_report_incident(ctx, "evt-1", {"summary": "s"}, None)

        assert result is True
        bb.stage_escalation.assert_not_awaited()
        bb.add_incident_reference.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_duplicate_incident_skips_staging_and_reference(self, monkeypatch):
        """has_incident_been_created=True short-circuits before staging/reference logic."""
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "true")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        ctx.has_incident_been_created = MagicMock(return_value=True)

        result = await handle_report_incident(ctx, "evt-1", {"summary": "s"}, None)

        assert result is True
        bb.stage_escalation.assert_not_awaited()
        bb.add_incident_reference.assert_not_awaited()


class TestIncidentCreatedOrderingRelativeToReferencePersist:
    """HIGH finding fix: mark_incident_created must fire strictly before
    add_incident_reference is attempted, in both branches. The external
    incident/escalation already exists at that point, so has_incident_been_created's
    dedup check must catch a retry even if add_incident_reference then fails --
    otherwise a persistence hiccup would let a retry create a duplicate incident."""

    @pytest.mark.asyncio
    async def test_staged_branch_marks_incident_created_before_reference_persist(self, monkeypatch):
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "true")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        call_order = []
        bb.add_incident_reference = AsyncMock(side_effect=lambda *a, **k: call_order.append("add_incident_reference"))
        ctx.mark_incident_created = MagicMock(side_effect=lambda *a, **k: call_order.append("mark_incident_created"))

        await handle_report_incident(ctx, "evt-1", {"summary": "s"}, None)

        assert call_order == ["mark_incident_created", "add_incident_reference"]

    @pytest.mark.asyncio
    async def test_direct_jira_branch_marks_incident_created_before_reference_persist(self, monkeypatch):
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "false")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        adapter = AsyncMock()
        adapter.create_incident = AsyncMock(
            return_value={"issue_key": "VMER-1234", "issue_url": "https://example/browse/VMER-1234"},
        )
        ctx.get_incident_adapter = MagicMock(return_value=adapter)
        call_order = []
        bb.add_incident_reference = AsyncMock(side_effect=lambda *a, **k: call_order.append("add_incident_reference"))
        ctx.mark_incident_created = MagicMock(side_effect=lambda *a, **k: call_order.append("mark_incident_created"))

        await handle_report_incident(
            ctx, "evt-1", {"summary": "anomaly detected", "description": "details"}, None,
        )

        assert call_order == ["mark_incident_created", "add_incident_reference"]


class TestStageEscalationFailureStillSkipsMarkIncidentCreated:
    """If stage_escalation itself fails, no escalation exists yet, so
    mark_incident_created must NOT fire -- only a successful create/stage should
    ever mark the incident as created (the whole point of the duplicate-prevention
    fix is to mark right after the external side effect succeeds, not before)."""

    @pytest.mark.asyncio
    async def test_stage_escalation_failure_does_not_mark_incident_created(self, monkeypatch):
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "true")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        bb.stage_escalation = AsyncMock(side_effect=RuntimeError("blackboard down"))

        result = await handle_report_incident(ctx, "evt-1", {"summary": "s"}, None)

        assert result is True
        ctx.mark_incident_created.assert_not_called()
        bb.add_incident_reference.assert_not_awaited()
        turn_arg = ctx.append_and_broadcast.call_args[0][1]
        assert "Failed to stage escalation" in turn_arg.thoughts

    @pytest.mark.asyncio
    async def test_create_incident_failure_does_not_mark_incident_created(self, monkeypatch):
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "false")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        adapter = AsyncMock()
        adapter.create_incident = AsyncMock(side_effect=RuntimeError("jira down"))
        ctx.get_incident_adapter = MagicMock(return_value=adapter)

        result = await handle_report_incident(
            ctx, "evt-1", {"summary": "anomaly detected", "description": "details"}, None,
        )

        assert result is True
        ctx.mark_incident_created.assert_not_called()
        bb.add_incident_reference.assert_not_awaited()
        turn_arg = ctx.append_and_broadcast.call_args[0][1]
        assert "Failed to create incident" in turn_arg.thoughts


class TestNightwatcherStagedIncidentReferenceFailureIsNonFatal:
    """HIGH finding fix: add_incident_reference failures after a successful
    stage_escalation must not be treated as if the escalation itself failed --
    the escalation already exists, so mark_incident_created still fires (to
    prevent a retry from duplicating it) and the reference-persistence failure
    is surfaced as a degraded-but-created result instead of a bare failure."""

    @pytest.mark.asyncio
    async def test_add_incident_reference_failure_is_reported_as_degraded_success(self, monkeypatch):
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "true")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        bb.add_incident_reference = AsyncMock(side_effect=RuntimeError("redis unavailable"))

        result = await handle_report_incident(ctx, "evt-1", {"summary": "s"}, None)

        assert result is True
        turn_arg = ctx.append_and_broadcast.call_args[0][1]
        assert "Escalation staged" in turn_arg.thoughts
        assert "redis unavailable" in turn_arg.thoughts
        assert "Failed to stage escalation" not in turn_arg.thoughts

    @pytest.mark.asyncio
    async def test_add_incident_reference_failure_skips_set_escalation_flag(self, monkeypatch):
        # add_incident_reference's failure short-circuits the success branch, so
        # set_escalation_flag (which only runs after the reference persists) must
        # never be reached.
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "true")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        bb.add_incident_reference = AsyncMock(side_effect=RuntimeError("redis unavailable"))

        await handle_report_incident(ctx, "evt-1", {"summary": "s"}, None)

        bb.set_escalation_flag.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_add_incident_reference_failure_still_marks_incident_created(self, monkeypatch):
        # HIGH finding fix: mark_incident_created must fire once the escalation is
        # staged, regardless of whether add_incident_reference then succeeds,
        # otherwise a retry after a transient persistence failure would stage a
        # duplicate escalation.
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "true")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        bb.add_incident_reference = AsyncMock(side_effect=RuntimeError("redis unavailable"))

        await handle_report_incident(ctx, "evt-1", {"summary": "s"}, None)

        ctx.mark_incident_created.assert_called_once_with("evt-1")


class TestDirectJiraIncidentReference:
    """Direct-Jira branch (NIGHTWATCHER_ENABLED=false): create_incident's
    issue_key is persisted via add_incident_reference, mirroring the
    Nightwatcher-staged branch's placeholder-reference coverage above."""

    @pytest.mark.asyncio
    async def test_direct_jira_branch_calls_add_incident_reference_with_issue_key(self, monkeypatch):
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "false")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        adapter = AsyncMock()
        adapter.create_incident = AsyncMock(
            return_value={"issue_key": "VMER-1234", "issue_url": "https://example/browse/VMER-1234"},
        )
        ctx.get_incident_adapter = MagicMock(return_value=adapter)

        result = await handle_report_incident(
            ctx, "evt-1", {"summary": "anomaly detected", "description": "details"}, None,
        )

        assert result is True
        adapter.create_incident.assert_awaited_once()
        bb.add_incident_reference.assert_awaited_once_with("evt-1", "VMER-1234")
        ctx.mark_incident_created.assert_called_once_with("evt-1")


class TestDirectJiraIncidentReferenceFailureIsNonFatal:
    """HIGH finding fix: mirrors the Nightwatcher-staged branch -- once
    create_incident succeeds, the Jira issue already exists, so
    add_incident_reference failing afterward must not be reported as if
    incident creation itself failed, and must not skip mark_incident_created
    (which would let a retry create a duplicate Jira issue)."""

    @pytest.mark.asyncio
    async def test_add_incident_reference_failure_is_reported_as_degraded_success(self, monkeypatch):
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "false")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        adapter = AsyncMock()
        adapter.create_incident = AsyncMock(
            return_value={"issue_key": "VMER-1234", "issue_url": "https://example/browse/VMER-1234"},
        )
        ctx.get_incident_adapter = MagicMock(return_value=adapter)
        bb.add_incident_reference = AsyncMock(side_effect=RuntimeError("redis unavailable"))

        result = await handle_report_incident(
            ctx, "evt-1", {"summary": "anomaly detected", "description": "details"}, None,
        )

        assert result is True
        turn_arg = ctx.append_and_broadcast.call_args[0][1]
        assert "Incident created in Jira" in turn_arg.thoughts
        assert "VMER-1234" in turn_arg.thoughts
        assert "redis unavailable" in turn_arg.thoughts
        assert "Failed to create incident" not in turn_arg.thoughts

    @pytest.mark.asyncio
    async def test_add_incident_reference_failure_skips_set_escalation_flag(self, monkeypatch):
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "false")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        adapter = AsyncMock()
        adapter.create_incident = AsyncMock(
            return_value={"issue_key": "VMER-1234", "issue_url": "https://example/browse/VMER-1234"},
        )
        ctx.get_incident_adapter = MagicMock(return_value=adapter)
        bb.add_incident_reference = AsyncMock(side_effect=RuntimeError("redis unavailable"))

        await handle_report_incident(
            ctx, "evt-1", {"summary": "anomaly detected", "description": "details"}, None,
        )

        bb.set_escalation_flag.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_add_incident_reference_failure_still_marks_incident_created(self, monkeypatch):
        # HIGH finding fix, mirrored for the direct-Jira branch: mark_incident_created
        # must fire once the Jira issue is created, regardless of whether
        # add_incident_reference then succeeds, to prevent a retry from creating a
        # duplicate Jira issue.
        monkeypatch.setenv("NIGHTWATCHER_ENABLED", "false")
        event = _event_doc(source="aligner")
        ctx, bb = _mock_ctx(event)
        adapter = AsyncMock()
        adapter.create_incident = AsyncMock(
            return_value={"issue_key": "VMER-1234", "issue_url": "https://example/browse/VMER-1234"},
        )
        ctx.get_incident_adapter = MagicMock(return_value=adapter)
        bb.add_incident_reference = AsyncMock(side_effect=RuntimeError("redis unavailable"))

        await handle_report_incident(
            ctx, "evt-1", {"summary": "anomaly detected", "description": "details"}, None,
        )

        ctx.mark_incident_created.assert_called_once_with("evt-1")
