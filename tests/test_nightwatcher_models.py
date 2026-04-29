# tests/test_nightwatcher_models.py
# @ai-rules:
# 1. [Pattern]: Pydantic model validation tests for Nightwatcher data models.
# 2. [Constraint]: Tests construction, defaults, validation constraints, and round-trip JSON.
# 3. [Pattern]: Each model gets: valid construction, defaults, field constraints, serialization.
"""Unit tests for Nightwatcher Pydantic models."""
from __future__ import annotations

import time

import pytest

from src.models import (
    ShiftIncident,
    ShiftInvestigation,
    ShiftReport,
    StagedEscalation,
)


# =========================================================================
# StagedEscalation
# =========================================================================

class TestStagedEscalation:
    def test_valid_construction(self):
        e = StagedEscalation(
            event_id="evt-abc123", service="release-console",
            source="aligner", reason="CPU > 90%",
            summary="High CPU on release-console",
        )
        assert e.event_id == "evt-abc123"
        assert e.service == "release-console"
        assert e.source == "aligner"
        assert e.priority == "Normal"
        assert e.platform == ""
        assert e.evidence_snapshot == {}
        assert e.staged_at > 0

    def test_defaults(self):
        e = StagedEscalation(
            event_id="evt-1", service="svc", source="headhunter",
            reason="todo", summary="MR review",
        )
        assert e.platform == ""
        assert e.priority == "Normal"
        assert e.description == ""
        assert e.conversation_summary == ""
        assert e.slack_thread_url == ""

    def test_summary_max_length(self):
        with pytest.raises(Exception):
            StagedEscalation(
                event_id="evt-1", service="svc", source="aligner",
                reason="r", summary="x" * 201,
            )

    def test_staged_at_auto_populated(self):
        before = time.time()
        e = StagedEscalation(
            event_id="evt-1", service="svc", source="aligner",
            reason="r", summary="s",
        )
        assert e.staged_at >= before
        assert e.staged_at <= time.time()

    def test_json_round_trip(self):
        e = StagedEscalation(
            event_id="evt-rt", service="payload-viewer",
            source="aligner", reason="memory spike",
            summary="OOM on payload-viewer", platform="Konflux",
            priority="Critical", description="Pods restarting",
            evidence_snapshot={"severity": "critical"},
            conversation_summary="[brain.triage] High memory",
            slack_thread_url="https://slack.com/archives/C1/p123",
            staged_at=1000.0,
        )
        raw = e.model_dump_json()
        restored = StagedEscalation.model_validate_json(raw)
        assert restored.event_id == e.event_id
        assert restored.evidence_snapshot == e.evidence_snapshot
        assert restored.staged_at == 1000.0


# =========================================================================
# ShiftInvestigation
# =========================================================================

class TestShiftInvestigation:
    def test_valid_construction(self):
        inv = ShiftInvestigation(
            task="Check current status of svc-a.",
            service="svc-a", agent_result="Pipeline green.",
            duration_seconds=12.5,
        )
        assert inv.service == "svc-a"
        assert inv.duration_seconds == 12.5

    def test_defaults(self):
        inv = ShiftInvestigation(task="check svc")
        assert inv.service == ""
        assert inv.agent_result == ""
        assert inv.duration_seconds == 0.0
        assert inv.cluster_id == ""


# =========================================================================
# ShiftIncident
# =========================================================================

class TestShiftIncident:
    def test_valid_construction(self):
        inc = ShiftIncident(
            platform="Konflux", summary="s390x pipeline failures",
            affected_events=["evt-1", "evt-2", "evt-3"],
        )
        assert len(inc.affected_events) == 3
        assert inc.status == "New"
        assert inc.priority == "Normal"

    def test_self_resolved_status(self):
        inc = ShiftIncident(
            platform="Kargo", summary="Timeout resolved",
            status="Self-Resolved",
        )
        assert inc.status == "Self-Resolved"

    def test_empty_affected_events_default(self):
        inc = ShiftIncident(platform="p", summary="s")
        assert inc.affected_events == []

    def test_smartsheet_fields_default_empty(self):
        inc = ShiftIncident(platform="p", summary="s")
        assert inc.smartsheet_row_id == ""
        assert inc.smartsheet_url == ""


# =========================================================================
# ShiftReport
# =========================================================================

class TestShiftReport:
    def _make_report(self, **overrides):
        defaults = dict(
            shift_date="2026-04-29", window="morning",
            window_start="2026-04-29T06:00:00+00:00",
            window_end="2026-04-29T12:00:00+00:00",
            status="completed",
        )
        defaults.update(overrides)
        return ShiftReport(**defaults)

    def test_valid_construction(self):
        r = self._make_report()
        assert r.shift_date == "2026-04-29"
        assert r.window == "morning"
        assert r.status == "completed"
        assert r.manifest == []
        assert r.incidents == []
        assert r.investigations == []

    def test_empty_status(self):
        r = self._make_report(status="empty")
        assert r.status == "empty"

    def test_invalid_window_rejected(self):
        with pytest.raises(Exception):
            self._make_report(window="afternoon")

    def test_invalid_status_rejected(self):
        with pytest.raises(Exception):
            self._make_report(status="cancelled")

    def test_metrics_dict(self):
        r = self._make_report(metrics={
            "escalation_count": 5, "incident_count": 1,
            "noise_reduction_pct": 80.0,
        })
        assert r.metrics["noise_reduction_pct"] == 80.0

    def test_json_round_trip_with_nested(self):
        esc = StagedEscalation(
            event_id="evt-1", service="svc", source="aligner",
            reason="cpu", summary="high cpu", staged_at=100.0,
        )
        inc = ShiftIncident(
            platform="Konflux", summary="Pipeline failures",
            affected_events=["evt-1"],
        )
        r = self._make_report(manifest=[esc], incidents=[inc])
        raw = r.model_dump_json()
        restored = ShiftReport.model_validate_json(raw)
        assert len(restored.manifest) == 1
        assert restored.manifest[0].event_id == "evt-1"
        assert len(restored.incidents) == 1
        assert restored.incidents[0].affected_events == ["evt-1"]

    def test_schema_has_expected_fields(self):
        schema = ShiftReport.model_json_schema()
        props = schema["properties"]
        for field in ("shift_date", "window", "status", "manifest",
                      "incidents", "investigations", "metrics"):
            assert field in props, f"Missing field: {field}"
