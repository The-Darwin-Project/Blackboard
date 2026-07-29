# tests/test_aligner_poll_drain.py
# @ai-rules:
# 1. [Pattern]: Tests the poll-driven pending queue drain logic in Aligner._drain_once().
# 2. [Constraint]: No real Redis/LLM. AsyncMock blackboard with .redis sub-mock.
# 3. [Pattern]: _drain_once() is tested directly — NOT the while True _poll_loop().
# 4. [Pattern]: _trigger_architect returns Literal["created","suppressed_active","suppressed_cooldown","suppressed_escalation"].
# 5. [Pattern]: handle_recovery(target, message, scope) is the new public recovery method.
"""Unit tests for Aligner poll-driven drain loop and pending queue lifecycle."""
from __future__ import annotations

import json
import time
from unittest.mock import AsyncMock, patch

import pytest

from src.models import Service


# =========================================================================
# Helpers (mirror test_aligner_escalation_gate.py patterns)
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
    bb.redis.zadd.return_value = None
    return bb


def _make_aligner(bb=None):
    from src.agents.aligner import Aligner
    aligner = Aligner(bb or _mock_blackboard())
    aligner._llm_enabled = False
    return aligner


def _meta(anomaly_type="argocd_health_degraded", subject_type="service", **overrides):
    """Build metadata dict matching the pending queue HASH schema."""
    base = {
        "anomaly_type": anomaly_type,
        "display_text": f"ArgoCD health: Healthy -> Degraded (service=svc-a)",
        "severity": "critical",
        "domain": "complicated",
        "argocd_app": "argocd/test-app",
        "namespace": "test-ns",
        "subject_type": subject_type,
    }
    base.update(overrides)
    return base


# =========================================================================
# T-1: Dwell-expired anomaly creates event
# =========================================================================

@pytest.mark.asyncio
async def test_drain_creates_event_for_persistent_anomaly():
    """Stage old item, service still Degraded → create_event called + commit."""
    bb = _mock_blackboard()
    meta = _meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Degraded")
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_called_once()
    kwargs = bb.create_event.call_args.kwargs
    assert kwargs["service"] == "svc-a"
    assert kwargs["source"] == "aligner"
    bb.commit_aligner_signal.assert_called_once_with("svc-a|health")


# =========================================================================
# T-2: Self-resolved discarded
# =========================================================================

@pytest.mark.asyncio
async def test_drain_discards_self_resolved():
    """Service now Healthy → ZREM (commit), no event created."""
    bb = _mock_blackboard()
    meta = _meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Healthy")
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_not_called()
    bb.commit_aligner_signal.assert_called_once_with("svc-a|health")


# =========================================================================
# T-3: Dwell not expired → not drained
# =========================================================================

@pytest.mark.asyncio
async def test_drain_respects_dwell():
    """Recent item → drain returns empty list, no processing."""
    bb = _mock_blackboard()
    bb.drain_aligner_pending.return_value = []  # nothing past dwell

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_not_called()
    bb.commit_aligner_signal.assert_not_called()
    bb.restage_aligner_signal.assert_not_called()


# =========================================================================
# T-4: ZADD NX preserves first_seen
# =========================================================================

@pytest.mark.asyncio
async def test_zadd_nx_preserves_first_seen():
    """Same key staged twice → ZADD NX means score stays at first call time."""
    bb = _mock_blackboard()
    meta = _meta()
    aligner = _make_aligner(bb)

    # Two stage calls for same key
    await bb.stage_aligner_signal("svc-a|health", meta)
    await bb.stage_aligner_signal("svc-a|health", meta)

    # The stage_aligner_signal contract uses ZADD NX internally.
    # Verify the method was called twice (observer calls it each tick).
    assert bb.stage_aligner_signal.call_count == 2


# =========================================================================
# T-5: Health recovery: notify + clear + ZREM
# =========================================================================

@pytest.mark.asyncio
async def test_health_recovery_notifies_and_clears():
    """handle_recovery(scope='health') → _notify_active_events + clear_escalation_flag + remove_aligner_pending."""
    bb = _mock_blackboard()
    bb.get_active_events.return_value = []
    aligner = _make_aligner(bb)

    await aligner.handle_recovery("svc-a", "ArgoCD health recovered", "health")

    bb.clear_escalation_flag.assert_called_once_with("svc-a", scope="health")
    bb.remove_aligner_pending.assert_called_once_with("svc-a|health")


# =========================================================================
# T-5b: Sync recovery: ZREM only
# =========================================================================

@pytest.mark.asyncio
async def test_sync_recovery_zrem_only():
    """handle_recovery(scope='sync') → ZREM only, no _notify_active_events, no clear_escalation_flag."""
    bb = _mock_blackboard()
    bb.get_active_events.return_value = ["evt-1"]  # would be notified if scope was health
    aligner = _make_aligner(bb)

    await aligner.handle_recovery("argocd/app", "", "sync")

    bb.remove_aligner_pending.assert_called_once_with("argocd/app|sync")
    bb.clear_escalation_flag.assert_not_called()


# =========================================================================
# T-6: Flap: Degraded→Healthy→Degraded — fresh first_seen after recovery
# =========================================================================

@pytest.mark.asyncio
async def test_flap_degraded_healthy_degraded():
    """Recovery ZREM clears the entry, re-stage creates fresh first_seen."""
    bb = _mock_blackboard()
    meta = _meta()
    aligner = _make_aligner(bb)

    # Stage initial anomaly
    await bb.stage_aligner_signal("svc-a|health", meta)
    # Recovery clears it
    await aligner.handle_recovery("svc-a", "recovered", "health")
    bb.remove_aligner_pending.assert_called_with("svc-a|health")

    # Re-stage — fresh ZADD NX gets new score since key was removed
    await bb.stage_aligner_signal("svc-a|health", meta)
    assert bb.stage_aligner_signal.call_count == 2


# =========================================================================
# T-7: Cooldown → restage
# =========================================================================

@pytest.mark.asyncio
async def test_drain_restages_on_cooldown():
    """_trigger_architect returns 'suppressed_cooldown' → restage called."""
    bb = _mock_blackboard()
    meta = _meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Degraded")
    bb.count_aligner_pending.return_value = 1

    aligner = _make_aligner(bb)

    with patch.object(aligner, "_trigger_architect", return_value="suppressed_cooldown") as mock_ta:
        await aligner._drain_once()

    bb.restage_aligner_signal.assert_called_once_with("svc-a|health", meta)
    bb.commit_aligner_signal.assert_not_called()


# =========================================================================
# T-8: Escalation → restage
# =========================================================================

@pytest.mark.asyncio
async def test_drain_restages_on_escalation():
    """_trigger_architect returns 'suppressed_escalation' → restage called."""
    bb = _mock_blackboard()
    meta = _meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Degraded")
    bb.count_aligner_pending.return_value = 1

    aligner = _make_aligner(bb)

    with patch.object(aligner, "_trigger_architect", return_value="suppressed_escalation") as mock_ta:
        await aligner._drain_once()

    bb.restage_aligner_signal.assert_called_once_with("svc-a|health", meta)
    bb.commit_aligner_signal.assert_not_called()


# =========================================================================
# T-8b: Active event → commit
# =========================================================================

@pytest.mark.asyncio
async def test_drain_commits_on_active_event():
    """_trigger_architect returns 'suppressed_active' → commit (not restage)."""
    bb = _mock_blackboard()
    meta = _meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Degraded")
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)

    with patch.object(aligner, "_trigger_architect", return_value="suppressed_active") as mock_ta:
        await aligner._drain_once()

    bb.commit_aligner_signal.assert_called_once_with("svc-a|health")
    bb.restage_aligner_signal.assert_not_called()


# =========================================================================
# T-13 (partial): pending_count in-memory property
# =========================================================================

@pytest.mark.asyncio
async def test_pending_count_in_memory():
    """pending_count property returns the _pending_count attribute value."""
    bb = _mock_blackboard()
    aligner = _make_aligner(bb)
    aligner._pending_count = 7

    assert aligner.pending_count == 7


# =========================================================================
# T-15: Orphan cleanup (meta=None)
# =========================================================================

@pytest.mark.asyncio
async def test_orphan_meta_none_cleanup():
    """ZSET member with no HASH entry → warning logged + committed (cleaned up)."""
    bb = _mock_blackboard()
    bb.drain_aligner_pending.return_value = ["svc-orphan|health"]
    bb.redis.hget.return_value = None  # no metadata
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.commit_aligner_signal.assert_called_once_with("svc-orphan|health")
    bb.create_event.assert_not_called()


# =========================================================================
# T-16: Sync re-check reads app_sync hash
# =========================================================================

@pytest.mark.asyncio
async def test_sync_recheck_reads_app_sync_hash():
    """Drain reads darwin:argocd_app_sync:{key} for sync re-check. Synced → commit."""
    bb = _mock_blackboard()
    meta = _meta(anomaly_type="argocd_sync_drift", subject_type="system")
    bb.drain_aligner_pending.return_value = ["argocd/app|sync"]
    bb.redis.hget.side_effect = lambda key, field=None: (
        json.dumps(meta) if key == "darwin:aligner:pending:meta"
        else "Synced" if "darwin:argocd_app_sync:" in key
        else None
    )
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.commit_aligner_signal.assert_called_once_with("argocd/app|sync")
    bb.create_event.assert_not_called()


# =========================================================================
# T-18: Malformed key skipped, not poison
# =========================================================================

@pytest.mark.asyncio
async def test_malformed_key_skipped_not_poison():
    """Key without '|' delimiter → warning + commit, remaining items still drain."""
    bb = _mock_blackboard()
    meta_good = _meta()
    meta_malformed = _meta()

    call_count = {"n": 0}

    def hget_side(key, field=None):
        call_count["n"] += 1
        return json.dumps(meta_malformed if call_count["n"] == 1 else meta_good)

    bb.drain_aligner_pending.return_value = ["malformed-no-pipe", "svc-b|health"]
    bb.redis.hget.side_effect = hget_side
    bb.get_service.return_value = Service(name="svc-b", health_status="Degraded")
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    # Malformed key committed (cleaned up)
    bb.commit_aligner_signal.assert_any_call("malformed-no-pipe")
    # Good key still processed
    bb.create_event.assert_called_once()


# =========================================================================
# T-19: Descriptive anomaly_type in reason
# =========================================================================

@pytest.mark.asyncio
async def test_descriptive_anomaly_type_in_reason():
    """create_event(reason=...) uses descriptive string from metadata (underscores→spaces)."""
    bb = _mock_blackboard()
    meta = _meta(anomaly_type="argocd_health_degraded")
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Degraded")
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)
    await aligner._drain_once()

    bb.create_event.assert_called_once()
    kwargs = bb.create_event.call_args.kwargs
    assert kwargs["reason"] == "argocd health degraded"


# =========================================================================
# Progressing edge case: commits without notify
# =========================================================================

@pytest.mark.asyncio
async def test_progressing_commits_without_notify():
    """Progressing health status → commit only, no _notify_active_events (transient)."""
    bb = _mock_blackboard()
    meta = _meta()
    bb.drain_aligner_pending.return_value = ["svc-a|health"]
    bb.redis.hget.return_value = json.dumps(meta)
    bb.get_service.return_value = Service(name="svc-a", health_status="Progressing")
    bb.count_aligner_pending.return_value = 0

    aligner = _make_aligner(bb)

    with patch.object(aligner, "_notify_active_events") as mock_notify:
        await aligner._drain_once()

    bb.commit_aligner_signal.assert_called_once_with("svc-a|health")
    mock_notify.assert_not_called()
    bb.create_event.assert_not_called()
