# tests/test_aligner_deterministic_escalation.py
# @ai-rules:
# 1. [Constraint]: No real LLM calls, no real Redis. All external deps are AsyncMock.
# 2. [Pattern]: Exercises handle_health_change/handle_sync_drift directly -- the
#    deterministic ArgoCD event-driven escalation path (no Flash in the loop).
"""Unit tests for Aligner's deterministic health/sync escalation (ArgoCD platform replacement)."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock

import pytest

from src.agents.aligner import Aligner, SYNC_DRIFT_DWELL_SECONDS


def _mock_blackboard():
    bb = AsyncMock()
    bb.get_active_events.return_value = []
    bb.get_event.return_value = None
    bb.get_service.return_value = None
    bb.get_escalation_flag.return_value = None
    bb.create_event.return_value = "evt-new"
    bb.redis = AsyncMock()
    bb.redis.get.return_value = None
    return bb


def _make_aligner(bb=None) -> Aligner:
    aligner = Aligner(bb or _mock_blackboard())
    aligner._llm_enabled = False
    return aligner


# =========================================================================
# handle_health_change: escalation rules
# =========================================================================

@pytest.mark.asyncio
async def test_degraded_creates_event():
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)

    await aligner.handle_health_change("svc-a", "Healthy", "Degraded", {"argocd_app": "ns/app"})

    bb.create_event.assert_called_once()
    kwargs = bb.create_event.call_args.kwargs
    assert kwargs["service"] == "svc-a"
    assert kwargs["evidence"].severity == "critical"
    assert kwargs["evidence"].metrics is None


@pytest.mark.asyncio
async def test_missing_creates_event():
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)

    await aligner.handle_health_change("svc-a", "Healthy", "Missing", {"argocd_app": "ns/app"})

    bb.create_event.assert_called_once()
    assert bb.create_event.call_args.kwargs["evidence"].severity == "warning"


@pytest.mark.asyncio
async def test_progressing_does_not_create_event():
    """Progressing is a normal deploy transient -- never escalates."""
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)

    await aligner.handle_health_change("svc-a", "Healthy", "Progressing", {"argocd_app": "ns/app"})

    bb.create_event.assert_not_called()


@pytest.mark.asyncio
async def test_healthy_from_healthy_does_not_create_event():
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)

    await aligner.handle_health_change("svc-a", "Healthy", "Healthy", {"argocd_app": "ns/app"})

    bb.create_event.assert_not_called()


@pytest.mark.asyncio
async def test_degraded_to_degraded_does_not_duplicate_active_event():
    """Same-state repeat is blocked by the active-event dedup gate (Layer 1)."""
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)

    await aligner.handle_health_change("svc-a", "Healthy", "Degraded", {"argocd_app": "ns/app"})
    assert bb.create_event.call_count == 1

    # Simulate the created event now being active -- Layer 1 gate kicks in
    from src.models import EventDocument, EventInput, EventEvidence, EventStatus
    active_event = EventDocument(
        id="evt-new", source="aligner", status=EventStatus.ACTIVE, service="svc-a",
        event=EventInput(reason="test", evidence=EventEvidence(display_text="test", source_type="aligner")),
    )
    bb.get_active_events.return_value = ["evt-new"]
    bb.get_event.return_value = active_event

    await aligner.handle_health_change("svc-a", "Degraded", "Degraded", {"argocd_app": "ns/app"})
    assert bb.create_event.call_count == 1


@pytest.mark.asyncio
async def test_cooldown_prevents_rapid_event_churn_on_flapping_health():
    """Rapid Healthy<->Degraded flapping is throttled by the 5-minute cooldown."""
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)

    await aligner.handle_health_change("svc-a", "Healthy", "Degraded", {"argocd_app": "ns/app"})
    assert bb.create_event.call_count == 1

    # Event closed quickly, flapped back to Degraded moments later -- cooldown blocks re-fire
    await aligner.handle_health_change("svc-a", "Healthy", "Degraded", {"argocd_app": "ns/app"})
    assert bb.create_event.call_count == 1


# =========================================================================
# handle_sync_drift: dwell-time debounce
# =========================================================================

@pytest.mark.asyncio
async def test_out_of_sync_first_seen_does_not_escalate():
    """First OutOfSync sighting records the dwell timer but does not escalate yet."""
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)

    await aligner.handle_sync_drift("ns/app", "Synced", "OutOfSync")

    bb.create_event.assert_not_called()
    assert "ns/app" in aligner._sync_drift_first_seen


@pytest.mark.asyncio
async def test_out_of_sync_under_dwell_time_does_not_escalate():
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)
    aligner._sync_drift_first_seen["ns/app"] = time.time() - (SYNC_DRIFT_DWELL_SECONDS - 5)

    await aligner.handle_sync_drift("ns/app", "OutOfSync", "OutOfSync")

    bb.create_event.assert_not_called()


@pytest.mark.asyncio
async def test_out_of_sync_past_dwell_time_escalates():
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)
    aligner._sync_drift_first_seen["ns/app"] = time.time() - (SYNC_DRIFT_DWELL_SECONDS + 5)

    await aligner.handle_sync_drift("ns/app", "OutOfSync", "OutOfSync")

    bb.create_event.assert_called_once()
    kwargs = bb.create_event.call_args.kwargs
    assert kwargs["service"] == "ns/app"
    assert kwargs["evidence"].domain == "clear"


@pytest.mark.asyncio
async def test_synced_clears_dwell_timer():
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)
    aligner._sync_drift_first_seen["ns/app"] = time.time() - (SYNC_DRIFT_DWELL_SECONDS + 5)

    await aligner.handle_sync_drift("ns/app", "OutOfSync", "Synced")

    bb.create_event.assert_not_called()
    assert "ns/app" not in aligner._sync_drift_first_seen


@pytest.mark.asyncio
async def test_check_state_returns_health_sync_fields():
    """check_state() (consumed by handlers_verification.py) returns ArgoCD fields, not cpu/memory."""
    from src.models import Service
    bb = _mock_blackboard()
    bb.get_service.return_value = Service(
        name="svc-a", version="1.0.0",
        health_status="Degraded", sync_status="Synced", argocd_app="ns/app",
        replicas_ready=1, replicas_desired=2,
    )
    aligner = _make_aligner(bb)

    state = await aligner.check_state("svc-a")

    assert state == {
        "service": "svc-a",
        "health_status": "Degraded",
        "sync_status": "Synced",
        "argocd_app": "ns/app",
        "replicas_ready": 1,
        "replicas_desired": 2,
        "version": "1.0.0",
    }
