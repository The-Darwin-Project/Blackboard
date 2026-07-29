# tests/test_aligner_deterministic_escalation.py
# @ai-rules:
# 1. [Constraint]: No real LLM calls, no real Redis. All external deps are AsyncMock.
# 2. [Pattern]: Exercises _drain_once() and _trigger_architect() directly -- the
#    poll-driven pending queue escalation path (replaces old handle_health_change/handle_sync_drift).
# 3. [Pattern]: ZSET-based dwell replaces in-memory _sync_drift_first_seen dict.
"""Unit tests for Aligner's poll-driven health/sync escalation (ZSET pending queue)."""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.models import Service


# =========================================================================
# Helpers
# =========================================================================

def _mock_blackboard():
    from src.state.blackboard import BlackboardState
    bb = AsyncMock(spec=BlackboardState)
    bb.get_active_events.return_value = []
    bb.get_event.return_value = None
    bb.get_service.return_value = None
    bb.get_escalation_flag.return_value = None
    bb.create_event.return_value = "evt-new"
    bb.drain_aligner_pending.return_value = []
    bb.count_aligner_pending.return_value = 0
    bb.commit_aligner_signal.return_value = None
    bb.restage_aligner_signal.return_value = None
    bb.stage_aligner_signal.return_value = None
    bb.remove_aligner_pending.return_value = None
    bb.clear_escalation_flag.return_value = 1
    bb.redis = AsyncMock()
    bb.redis.get.return_value = None
    bb.redis.hget.return_value = None
    return bb


def _make_aligner(bb=None):
    from src.agents.aligner import Aligner
    aligner = Aligner(bb or _mock_blackboard())
    aligner._llm_enabled = False
    return aligner


def _health_meta(service="svc-a", severity="critical"):
    return {
        "anomaly_type": "argocd_health_degraded",
        "display_text": f"ArgoCD health: Healthy -> Degraded (service={service})",
        "severity": severity,
        "domain": "complicated",
        "argocd_app": "argocd/test-app",
        "namespace": "test-ns",
        "subject_type": "service",
    }


def _sync_meta(app_key="argocd/test-app"):
    return {
        "anomaly_type": "argocd_sync_drift",
        "display_text": f"ArgoCD sync: Synced -> OutOfSync for {app_key}",
        "severity": "warning",
        "domain": "clear",
        "argocd_app": app_key,
        "namespace": "argocd",
        "subject_type": "system",
    }


# =========================================================================
# Health escalation via _drain_once (was handle_health_change)
# =========================================================================

@pytest.mark.asyncio
async def test_degraded_creates_event_via_drain():
    """Pending health anomaly for service with Degraded status → event created."""
    bb = _mock_blackboard()
    meta = _health_meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Degraded")
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_called_once()
    kwargs = bb.create_event.call_args.kwargs
    assert kwargs["service"] == "svc-a"
    assert kwargs["evidence"].severity == "critical"
    assert kwargs["evidence"].metrics is None


@pytest.mark.asyncio
async def test_missing_creates_event_via_drain():
    """Pending health anomaly with Missing status → event created with warning severity."""
    bb = _mock_blackboard()
    meta = _health_meta(severity="warning")
    meta["anomaly_type"] = "argocd_health_missing"
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Missing")
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_called_once()
    assert bb.create_event.call_args.kwargs["evidence"].severity == "warning"


@pytest.mark.asyncio
async def test_progressing_does_not_create_event():
    """Progressing is a normal deploy transient -- self-resolved on drain."""
    bb = _mock_blackboard()
    meta = _health_meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Progressing")
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_not_called()
    bb.commit_aligner_signal.assert_called_once_with("svc-a|health")


@pytest.mark.asyncio
async def test_healthy_self_resolves_on_drain():
    """Service now Healthy -- pending item committed (self-resolved)."""
    bb = _mock_blackboard()
    meta = _health_meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Healthy")
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_not_called()
    bb.commit_aligner_signal.assert_called_once_with("svc-a|health")


@pytest.mark.asyncio
async def test_active_event_dedup_commits_without_create():
    """Active event exists (Layer 1) → _trigger_architect returns 'suppressed_active' → commit."""
    from src.models import EventDocument, EventInput, EventEvidence, EventStatus
    bb = _mock_blackboard()
    meta = _health_meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Degraded")

    active_event = EventDocument(
        id="evt-existing", source="aligner", status=EventStatus.ACTIVE, service="svc-a",
        event=EventInput(reason="test", evidence=EventEvidence(display_text="test", source_type="aligner")),
    )
    bb.get_active_events.return_value = ["evt-existing"]
    bb.get_event.return_value = active_event
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_not_called()
    bb.commit_aligner_signal.assert_called_once_with("svc-a|health")


@pytest.mark.asyncio
async def test_cooldown_prevents_rapid_event_churn():
    """Cooldown active → _trigger_architect returns 'suppressed_cooldown' → restage."""
    bb = _mock_blackboard()
    meta = _health_meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Degraded")
    bb.count_aligner_pending.return_value = 1

    aligner = _make_aligner(bb)
    # Simulate cooldown by setting a recent creation time
    aligner._last_event_creation["svc-a"] = time.time() - 10  # only 10s ago

    await aligner._drain_once()

    bb.create_event.assert_not_called()
    bb.restage_aligner_signal.assert_called_once_with("svc-a|health", meta)


# =========================================================================
# Sync escalation via ZSET (replaces _sync_drift_first_seen in-memory dwell)
# =========================================================================

@pytest.mark.asyncio
async def test_sync_drift_creates_event_when_still_out_of_sync():
    """ZSET dwell expired + app still OutOfSync → event created."""
    bb = _mock_blackboard()
    meta = _sync_meta()
    bb.drain_aligner_pending.return_value = ["argocd/test-app|sync"]
    bb.redis.hget.side_effect = lambda key, field=None: (
        json.dumps(meta) if key == "darwin:aligner:pending:meta"
        else "OutOfSync" if "darwin:argocd_app_sync:" in key
        else None
    )
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_called_once()
    kwargs = bb.create_event.call_args.kwargs
    assert kwargs["service"] == "argocd/test-app"
    assert kwargs["evidence"].domain == "clear"
    assert kwargs["subject_type"] == "system"


@pytest.mark.asyncio
async def test_sync_self_resolves_when_synced():
    """App now Synced → pending item committed (self-resolved)."""
    bb = _mock_blackboard()
    meta = _sync_meta()
    bb.drain_aligner_pending.return_value = ["argocd/test-app|sync"]
    bb.redis.hget.side_effect = lambda key, field=None: (
        json.dumps(meta) if key == "darwin:aligner:pending:meta"
        else "Synced" if "darwin:argocd_app_sync:" in key
        else None
    )
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_not_called()
    bb.commit_aligner_signal.assert_called_once_with("argocd/test-app|sync")


@pytest.mark.asyncio
async def test_sync_hash_none_treated_as_resolved():
    """No app sync hash entry (deleted app?) → committed as resolved."""
    bb = _mock_blackboard()
    meta = _sync_meta()
    bb.drain_aligner_pending.return_value = ["argocd/test-app|sync"]
    bb.redis.hget.side_effect = lambda key, field=None: (
        json.dumps(meta) if key == "darwin:aligner:pending:meta"
        else None  # no sync hash entry
    )
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_not_called()
    bb.commit_aligner_signal.assert_called_once_with("argocd/test-app|sync")


# =========================================================================
# check_state() — unchanged, regression test
# =========================================================================

@pytest.mark.asyncio
async def test_check_state_returns_health_sync_fields():
    """check_state() (consumed by handlers_verification.py) returns ArgoCD fields, not cpu/memory."""
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
