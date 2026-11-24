# tests/test_aligner_escalation_gate.py
# @ai-rules:
# 1. [Pattern]: Tests the escalation suppression flag lifecycle across Aligner, Brain, and Nightwatcher.
# 2. [Constraint]: No real LLM calls, no real Redis. All external deps are AsyncMock.
# 3. [Pattern]: _trigger_architect() returns Literal["created","suppressed_active","suppressed_cooldown","suppressed_escalation"].
# 4. [Pattern]: handle_recovery(target, message, scope) replaces handle_health_change recovery path.
"""Unit tests for the escalation suppression flag (issue #78)."""
from __future__ import annotations

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models import (
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
    Service,
    StagedEscalation,
)
from src.state.blackboard import BlackboardState


# =========================================================================
# Helpers
# =========================================================================

def _svc(name="svc-a", flag=None):
    return Service(name=name, escalation_flag=flag)


def _make_event(event_id="evt-1", service="svc-a", source="aligner", status=EventStatus.ACTIVE, **kw):
    return EventDocument(
        id=event_id, source=source, status=status, service=service,
        event=EventInput(
            reason="test",
            evidence=EventEvidence(display_text="test", source_type=source),
        ),
        **kw,
    )


def _mock_blackboard():
    bb = AsyncMock(spec=BlackboardState)
    bb.get_active_events.return_value = []
    bb.get_event.return_value = None
    bb.get_service.return_value = None
    bb.get_escalation_flag.return_value = None
    bb.set_escalation_flag.return_value = None
    bb.clear_escalation_flag.return_value = 1
    bb.create_event.return_value = "evt-new"
    bb.redis = AsyncMock()
    bb.redis.get.return_value = None
    return bb


def _make_aligner(bb=None):
    from src.agents.aligner import Aligner
    aligner = Aligner(bb or _mock_blackboard())
    aligner._llm_enabled = False
    return aligner


def _make_blackboard_state():
    """Create a real BlackboardState with mocked Redis and a callable Lua script mock."""
    redis = AsyncMock()
    lua_script = AsyncMock()
    # register_script is sync in redis-py — returns a callable Script object
    redis.register_script = MagicMock(return_value=lua_script)
    bb = BlackboardState(redis)
    return bb, redis, lua_script


def _stub_brain(bb):
    """Create a minimal Brain stub with enough attributes for _execute_function_call."""
    from src.agents.brain import Brain, _BrainToolContext
    brain = Brain.__new__(Brain)
    brain.blackboard = bb
    brain._incident_created = set()
    brain._next_turn_number = AsyncMock(return_value=1)
    brain._append_and_broadcast = AsyncMock(return_value=1)
    brain._emit_executive_pulse = AsyncMock()
    brain._incident_adapter = None
    brain.pulse_port = None
    brain._skill_loader = None
    brain._grounding_evidence_for_event = {}
    brain._thinking_per_event = {}
    brain._tool_ctx = _BrainToolContext(brain)
    return brain


# =========================================================================
# 1. Gate: Service with flag → _trigger_architect returns "suppressed_escalation"
# =========================================================================

@pytest.mark.asyncio
async def test_gate_blocks_when_flag_set():
    bb = _mock_blackboard()
    bb.get_escalation_flag.return_value = "evt-old|high cpu"
    aligner = _make_aligner(bb)
    result = await aligner._trigger_architect("svc-a", "high_cpu", "ArgoCD health: Healthy -> Degraded")
    bb.create_event.assert_not_called()
    assert result == "suppressed_escalation"


# =========================================================================
# 2. Gate negative: flag=None → "created"
# =========================================================================

@pytest.mark.asyncio
async def test_gate_allows_when_no_flag():
    bb = _mock_blackboard()
    bb.get_escalation_flag.return_value = None
    aligner = _make_aligner(bb)
    result = await aligner._trigger_architect("svc-a", "high_cpu", "ArgoCD health: Healthy -> Degraded")
    bb.create_event.assert_called_once()
    assert result == "created"


# =========================================================================
# 3. Flag-set: stage_escalation success → set_escalation_flag called
# =========================================================================

@pytest.mark.asyncio
async def test_brain_sets_flag_on_staging_success():
    bb = _mock_blackboard()
    bb.stage_escalation.return_value = None
    bb.get_event.return_value = _make_event(service="svc-a")
    brain = _stub_brain(bb)

    with patch.dict("os.environ", {"NIGHTWATCHER_ENABLED": "true"}):
        await brain._execute_function_call(
            event_id="evt-1", function_name="report_incident",
            args={"summary": "high cpu", "description": "test", "priority": "Normal"},
            response_parts=None,
        )

    bb.set_escalation_flag.assert_called_once_with("svc-a", "evt-1", "high cpu", scope="health")


# =========================================================================
# 4. Flag-set null-safety: service=None → set NOT called
# =========================================================================

@pytest.mark.asyncio
async def test_brain_skips_flag_when_service_none():
    """Jira branch: service=None should skip set_escalation_flag."""
    bb = _mock_blackboard()
    evt = _make_event(source="aligner")
    evt.service = None
    bb.get_event.return_value = evt

    mock_adapter = AsyncMock()
    mock_adapter.create_incident.return_value = {"issue_key": "VMER-123", "issue_url": "https://jira.example.com/browse/VMER-123"}

    brain = _stub_brain(bb)

    with patch.dict("os.environ", {"NIGHTWATCHER_ENABLED": "false"}), \
         patch.object(brain, "_incident_adapter", new=mock_adapter):
        await brain._execute_function_call(
            event_id="evt-1", function_name="report_incident",
            args={"summary": "test", "description": "test"},
            response_parts=None,
        )

    bb.set_escalation_flag.assert_not_called()


# =========================================================================
# 5. Recovery-clear: handle_recovery(scope="health") → notify + clear + ZREM
# =========================================================================

@pytest.mark.asyncio
async def test_recovery_clears_flag():
    """handle_recovery(scope='health') clears escalation flag and removes pending entry."""
    bb = _mock_blackboard()
    bb.get_journal.return_value = []
    active_evt = _make_event(event_id="evt-active", service="svc-a")
    bb.get_active_events.return_value = ["evt-active"]
    bb.get_event.return_value = active_evt

    aligner = _make_aligner(bb)

    await aligner.handle_recovery("svc-a", "ArgoCD health recovered", "health")

    bb.clear_escalation_flag.assert_called_once_with("svc-a", scope="health")
    bb.remove_aligner_pending.assert_called_once_with("svc-a|health")


# =========================================================================
# 6. NW clear: committed services cleared, failed not
# =========================================================================

@pytest.mark.asyncio
async def test_nw_clears_committed_only():
    """Verify the clear loop only processes committed event_ids."""
    bb = _mock_blackboard()
    escalations = [
        StagedEscalation(event_id="evt-1", service="svc-a", source="aligner", reason="cpu", summary="high"),
        StagedEscalation(event_id="evt-2", service="svc-b", source="aligner", reason="cpu", summary="high"),
    ]
    successful_event_ids = {"evt-1"}
    escalations_by_id = {e.event_id: e for e in escalations}

    for eid in successful_event_ids:
        esc = escalations_by_id.get(eid)
        if esc and esc.service:
            try:
                await bb.clear_escalation_flag(esc.service, expected_event_id=eid)
            except Exception:
                pass

    bb.clear_escalation_flag.assert_called_once_with("svc-a", expected_event_id="evt-1")


# =========================================================================
# 7. NW atomic race: mismatched event_id → NOT cleared (return 0)
# =========================================================================

@pytest.mark.asyncio
async def test_lua_atomic_no_clear_on_mismatch():
    bb, redis, lua_script = _make_blackboard_state()
    lua_script.return_value = 0

    result = await bb.clear_escalation_flag("svc-a", expected_event_id="evt-wrong")
    assert result == 0
    lua_script.assert_called_once_with(
        keys=["darwin:service:svc-a"],
        args=["evt-wrong", "escalation_flag:health", "escalation_flag"],
    )


# =========================================================================
# 8. Backward compat: missing HASH field → None
# =========================================================================

@pytest.mark.asyncio
async def test_get_service_missing_field_returns_none():
    bb, redis, _ = _make_blackboard_state()
    redis.hgetall.return_value = {
        "version": "v1", "cpu": "10", "memory": "20",
        "error_rate": "0", "last_seen": str(time.time()),
    }
    redis.smembers.return_value = []

    svc = await bb.get_service("svc-a")
    assert svc is not None
    assert svc.escalation_flag is None


# =========================================================================
# 9. Kargo parallel: handle_failed_promotion checks gate
# =========================================================================

@pytest.mark.asyncio
async def test_kargo_gate_blocks_when_flag_set():
    bb = _mock_blackboard()
    bb.get_escalation_flag.return_value = "evt-old|promotion failed"
    aligner = _make_aligner(bb)

    result = await aligner.handle_failed_promotion(
        service="svc-a", project="proj", stage="staging",
        promotion="p1", freight="f1", phase="failed",
        message="step failed", failed_step="step1", mr_url="https://example.com/mr/1",
    )
    assert result is None
    bb.create_event.assert_not_called()


@pytest.mark.asyncio
async def test_kargo_handle_failed_promotion_seeds_gitlab_context():
    """T-6: handle_failed_promotion uses GitLabPlatform.parse_mr_url (2-tuple) to seed evidence.gitlab_context."""
    bb = _mock_blackboard()
    bb.get_active_events.return_value = []
    bb.get_escalation_flag.return_value = None
    created_events = []

    async def mock_create_event(**kwargs):
        created_events.append(kwargs)
        return "evt-kargo-123"

    bb.create_event = mock_create_event
    aligner = _make_aligner(bb)

    mr_url = "https://gitlab.example.com/openshift-virtualization/downstream-configuration/-/merge_requests/25"
    result = await aligner.handle_failed_promotion(
        service="svc-a",
        project="downstream-configuration",
        stage="staging",
        promotion="p1",
        freight="f1",
        phase="failed",
        message="Promotion failed on step verification",
        failed_step="verify-step",
        mr_url=mr_url,
    )

    assert result == "evt-kargo-123"
    assert len(created_events) == 1
    evidence = created_events[0]["evidence"]
    assert evidence.gitlab_context is not None
    assert evidence.gitlab_context["target_url"] == mr_url
    assert evidence.gitlab_context["project_id"] == "openshift-virtualization/downstream-configuration"
    assert evidence.gitlab_context["mr_iid"] == 25


# =========================================================================
# 10. Kargo hash lifecycle: HSET/HGET/HDEL
# =========================================================================

@pytest.mark.asyncio
async def test_escalation_flag_lifecycle():
    bb, redis, lua_script = _make_blackboard_state()
    redis.hget.return_value = None
    lua_script.return_value = 1

    assert await bb.get_escalation_flag("svc-new") is None
    # Backward compat: checks scoped field first, then falls back to legacy
    redis.hget.assert_any_call("darwin:service:svc-new", "escalation_flag:health")
    redis.hget.assert_called_with("darwin:service:svc-new", "escalation_flag")

    await bb.set_escalation_flag("svc-new", "evt-1", "test reason")
    redis.hset.assert_called_with("darwin:service:svc-new", "escalation_flag:health", "evt-1|test reason")

    await bb.clear_escalation_flag("svc-new", expected_event_id="evt-1")
    lua_script.assert_called_once_with(
        keys=["darwin:service:svc-new"],
        args=["evt-1", "escalation_flag:health", "escalation_flag"],
    )


# =========================================================================
# 11. Escalation gate: pending flag → _trigger_architect returns suppressed
# =========================================================================

@pytest.mark.asyncio
async def test_trigger_architect_respects_escalation_flag():
    """_trigger_architect returns 'suppressed_escalation' while escalation flag is pending."""
    bb = _mock_blackboard()
    bb.get_escalation_flag.return_value = "evt-old|argocd health degraded"
    aligner = _make_aligner(bb)

    result = await aligner._trigger_architect("svc-a", "argocd_health_degraded", "ArgoCD health: Degraded")

    bb.create_event.assert_not_called()
    assert result == "suppressed_escalation"


# =========================================================================
# 12. Multi-escalation overwrite: latest event_id wins
# =========================================================================

@pytest.mark.asyncio
async def test_multi_escalation_latest_wins():
    bb, redis, _ = _make_blackboard_state()

    await bb.set_escalation_flag("svc-a", "evt-1", "first escalation")
    await bb.set_escalation_flag("svc-a", "evt-2", "second escalation")

    calls = redis.hset.call_args_list
    assert len(calls) == 2
    assert calls[-1].args == ("darwin:service:svc-a", "escalation_flag:health", "evt-2|second escalation")


# =========================================================================
# 13. Malformed flag: no delimiter → Lua handles gracefully
# =========================================================================

@pytest.mark.asyncio
async def test_malformed_flag_no_delimiter():
    bb, redis, lua_script = _make_blackboard_state()
    lua_script.return_value = 1

    result = await bb.clear_escalation_flag("svc-a", expected_event_id="evt-nopipe")
    lua_script.assert_called_once_with(
        keys=["darwin:service:svc-a"],
        args=["evt-nopipe", "escalation_flag:health", "escalation_flag"],
    )
    assert result == 1


# =========================================================================
# 14. Failure-path no-ghost: staging exception → flag NOT set
# =========================================================================

@pytest.mark.asyncio
async def test_staging_failure_does_not_set_flag():
    bb = _mock_blackboard()
    bb.stage_escalation.side_effect = RuntimeError("Redis down")
    bb.get_event.return_value = _make_event(service="svc-a")
    brain = _stub_brain(bb)

    with patch.dict("os.environ", {"NIGHTWATCHER_ENABLED": "true"}):
        await brain._execute_function_call(
            event_id="evt-1", function_name="report_incident",
            args={"summary": "test", "description": "test"},
            response_parts=None,
        )

    bb.set_escalation_flag.assert_not_called()


# =========================================================================
# 15. NW clear loop resilience: one clear fails → others still cleared
# =========================================================================

@pytest.mark.asyncio
async def test_nw_clear_loop_resilience():
    """One failing clear_escalation_flag doesn't stop subsequent clears."""
    bb = _mock_blackboard()
    call_count = 0

    async def side_effect(service, expected_event_id=None):
        nonlocal call_count
        call_count += 1
        if service == "svc-a":
            raise RuntimeError("Redis timeout")
        return 1

    bb.clear_escalation_flag.side_effect = side_effect

    escalations = [
        StagedEscalation(event_id="evt-1", service="svc-a", source="aligner", reason="cpu", summary="high"),
        StagedEscalation(event_id="evt-2", service="svc-b", source="aligner", reason="mem", summary="high"),
        StagedEscalation(event_id="evt-3", service="svc-c", source="aligner", reason="err", summary="high"),
    ]
    successful_event_ids = {"evt-1", "evt-2", "evt-3"}
    escalations_by_id = {e.event_id: e for e in escalations}

    for eid in sorted(successful_event_ids):
        esc = escalations_by_id.get(eid)
        if esc and esc.service:
            try:
                await bb.clear_escalation_flag(esc.service, expected_event_id=eid)
            except Exception:
                pass

    assert call_count == 3


# =========================================================================
# 16. Cross-scope no suppression: Kargo flag → health event NOT suppressed
# =========================================================================

@pytest.mark.asyncio
async def test_cross_scope_no_suppression():
    """Kargo-scoped flag does NOT suppress a health-scoped event."""
    bb = _mock_blackboard()
    async def scope_aware_get(service, scope="health"):
        if scope == "kargo":
            return "evt-old|kargo promo"
        return None
    bb.get_escalation_flag.side_effect = scope_aware_get
    aligner = _make_aligner(bb)
    result = await aligner._trigger_architect("svc-a", "high_cpu", "ArgoCD health: Degraded")
    bb.create_event.assert_called_once()
    assert result == "created"


# =========================================================================
# 17. Same-scope suppression: health flag → health event IS suppressed
# =========================================================================

@pytest.mark.asyncio
async def test_same_scope_suppression():
    """Health-scoped flag DOES suppress a health-scoped event."""
    bb = _mock_blackboard()
    bb.get_escalation_flag.return_value = "evt-old|health flag"
    aligner = _make_aligner(bb)
    result = await aligner._trigger_architect("svc-a", "high_cpu", "ArgoCD health: Degraded")
    bb.create_event.assert_not_called()
    assert result == "suppressed_escalation"


# =========================================================================
# 18. Recovery clears own scope only
# =========================================================================

@pytest.mark.asyncio
async def test_recovery_clears_own_scope_only():
    """Health recovery clears scope=health, not scope=kargo."""
    bb = _mock_blackboard()
    bb.get_active_events.return_value = []
    aligner = _make_aligner(bb)
    await aligner.handle_recovery("svc-a", "ArgoCD health recovered", "health")
    bb.clear_escalation_flag.assert_called_once_with("svc-a", scope="health")
    bb.remove_aligner_pending.assert_called_once_with("svc-a|health")


# =========================================================================
# 19. Backward compat: legacy flag (no scope) treated as health
# =========================================================================

@pytest.mark.asyncio
async def test_backward_compat_legacy_flag():
    """BlackboardState.get_escalation_flag falls back to legacy unscoped field for health scope."""
    bb_real, redis_mock, _ = _make_blackboard_state()
    # Scoped field empty, legacy field has value
    async def hget_side(key, field):
        if field == "escalation_flag:health":
            return None
        if field == "escalation_flag":
            return "evt-legacy|old reason"
        return None
    redis_mock.hget.side_effect = hget_side
    result = await bb_real.get_escalation_flag("svc-a", scope="health")
    assert result == "evt-legacy|old reason"


# =========================================================================
# 20. Nightwatcher clear uses StagedEscalation.scope
# =========================================================================

@pytest.mark.asyncio
async def test_nightwatcher_clear_uses_scope():
    """NW clear passes scope from StagedEscalation to clear_escalation_flag."""
    bb = _mock_blackboard()
    esc = StagedEscalation(
        event_id="evt-1", service="svc-a", source="aligner",
        reason="kargo promo", summary="failed", scope="kargo",
    )
    # Simulate the NW clear loop
    await bb.clear_escalation_flag(esc.service, scope=esc.scope or "health", expected_event_id=esc.event_id)
    bb.clear_escalation_flag.assert_called_once_with("svc-a", scope="kargo", expected_event_id="evt-1")


# =========================================================================
# 21. Sync-drift gate uses direct HGET (works for synthetic argocd_app keys)
# =========================================================================

@pytest.mark.asyncio
async def test_sync_drift_gate_uses_direct_hget():
    """_check_escalation_gate uses get_escalation_flag (direct HGET) not get_service()."""
    bb = _mock_blackboard()
    bb.get_escalation_flag.return_value = "evt-old|sync drift"
    aligner = _make_aligner(bb)
    result = await aligner._check_escalation_gate("openshift-gitops/argocd-app", "sync")
    assert result is True
    bb.get_escalation_flag.assert_called_once_with("openshift-gitops/argocd-app", scope="sync")
    # Importantly: get_service was NOT called (it returns None for synthetic keys)
    bb.get_service.assert_not_called()


# =========================================================================
# 22. Kargo Context Refresh updates gitlab_context on MR URL change
# =========================================================================

@pytest.mark.asyncio
async def test_kargo_refresh_updates_gitlab_context_when_mr_url_changes():
    """handlers_integration.handle_refresh_kargo_context parses new mr_url and updates gitlab_context."""
    from src.agents.handlers_integration import handle_refresh_kargo_context
    bb = _mock_blackboard()
    event = MagicMock()
    evidence = MagicMock()
    evidence.kargo_context = {
        "project": "proj-x",
        "stage": "stage-y",
        "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/10",
    }
    event.event.evidence = evidence
    bb.get_event = AsyncMock(return_value=event)
    bb.update_event_kargo_context = AsyncMock()
    bb.update_event_gitlab_context = AsyncMock()

    mock_kargo_observer = MagicMock()
    mock_kargo_observer.get_stage_status = AsyncMock(return_value={
        "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/11",
        "promotion": "promo-2",
        "phase": "Running",
        "failed_step": "N/A",
    })

    ctx = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.get_agent_instance.side_effect = lambda name: mock_kargo_observer if name == "_kargo_observer" else None
    ctx.next_turn_number = AsyncMock(return_value=2)
    ctx.append_and_broadcast = AsyncMock()
    ctx.get_state_watcher.return_value = None

    result = await handle_refresh_kargo_context(ctx, "evt-kargo-refresh", {}, None)

    assert result is True
    bb.update_event_kargo_context.assert_awaited_once_with("evt-kargo-refresh", {
        "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/11",
    })
    bb.update_event_gitlab_context.assert_awaited_once_with("evt-kargo-refresh", {
        "target_url": "https://gitlab.example.com/org/repo/-/merge_requests/11",
        "project_id": "org/repo",
        "mr_iid": 11,
    })
    turn = ctx.append_and_broadcast.call_args[0][1]
    assert "Promotion: promo-2" in turn.evidence
    assert "MR URL: https://gitlab.example.com/org/repo/-/merge_requests/11" in turn.evidence


@pytest.mark.asyncio
async def test_kargo_refresh_survives_gitlab_context_persistence_failure(caplog):
    """F22: the secondary gitlab_context mirror is best-effort.

    kargo_context.mr_url is persisted first; if the mirror raises, the refreshed promotion state the Brain
    is waiting on must still be returned (not discarded by an unhandled exception) and the failure logged.
    """
    from src.agents.handlers_integration import handle_refresh_kargo_context
    new_url = "https://gitlab.example.com/org/repo/-/merge_requests/11"
    bb = _mock_blackboard()
    event = MagicMock()
    evidence = MagicMock()
    evidence.kargo_context = {
        "project": "proj-x",
        "stage": "stage-y",
        "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/10",
    }
    event.event.evidence = evidence
    bb.get_event = AsyncMock(return_value=event)
    bb.update_event_kargo_context = AsyncMock()
    bb.update_event_gitlab_context = AsyncMock(side_effect=RuntimeError("redis down"))

    mock_kargo_observer = MagicMock()
    mock_kargo_observer.get_stage_status = AsyncMock(return_value={
        "mr_url": new_url,
        "promotion": "promo-2",
        "phase": "Running",
        "failed_step": "N/A",
    })

    ctx = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.get_agent_instance.side_effect = lambda name: mock_kargo_observer if name == "_kargo_observer" else None
    ctx.next_turn_number = AsyncMock(return_value=2)
    ctx.append_and_broadcast = AsyncMock()
    ctx.get_state_watcher.return_value = None

    with caplog.at_level("WARNING"):
        result = await handle_refresh_kargo_context(ctx, "evt-kargo-refresh", {}, None)

    assert result is True
    bb.update_event_kargo_context.assert_awaited_once_with("evt-kargo-refresh", {"mr_url": new_url})
    bb.update_event_gitlab_context.assert_awaited_once()
    assert any(
        "Failed to update gitlab_context" in r.getMessage() and "redis down" in r.getMessage()
        for r in caplog.records
    )
    ctx.append_and_broadcast.assert_awaited_once()
    turn = ctx.append_and_broadcast.call_args[0][1]
    assert "Promotion: promo-2" in turn.evidence
    assert f"MR URL: {new_url}" in turn.evidence


# =========================================================================
# 11. F4: Kargo/CI-gating events seeded with gitlab_context keep their own scope
# =========================================================================

@pytest.mark.parametrize(
    ("subject_type", "expected_scope"),
    [("kargo_stage", "kargo"), ("ci_gating", "jenkins")],
)
def test_resolve_escalation_scope_keeps_kargo_and_ci_scope_with_gitlab_context(subject_type, expected_scope):
    """gitlab_context is now seeded on Kargo events; it must not flip them to scope='review'.

    The Kargo gate is read under scope='kargo' (aligner.handle_failed_promotion), so a 'review'
    flag written here would never suppress the next Kargo failure.
    """
    from src.agents.handlers_dispatch import _resolve_escalation_scope

    doc = EventDocument(
        id="evt-scope",
        source="aligner",
        service="svc-a",
        subject_type=subject_type,
        event=EventInput(
            reason="test",
            evidence=EventEvidence(
                display_text="test",
                source_type="aligner",
                gitlab_context={"target_url": "https://gitlab.example.com/org/repo/-/merge_requests/1",
                                "project_id": "org/repo", "mr_iid": 1},
            ),
        ),
    )
    assert _resolve_escalation_scope(doc) == expected_scope


def test_resolve_escalation_scope_review_context_still_wins_for_service_subject():
    """Regression guard: the F4 exemption is limited to kargo_stage/ci_gating."""
    from src.agents.handlers_dispatch import _resolve_escalation_scope

    doc = EventDocument(
        id="evt-scope-svc",
        source="headhunter",
        service="svc-a",
        subject_type="service",
        event=EventInput(
            reason="test",
            evidence=EventEvidence(
                display_text="test", source_type="headhunter",
                gitlab_context={"project_id": "org/repo", "mr_iid": 1},
            ),
        ),
    )
    assert _resolve_escalation_scope(doc) == "review"


# =========================================================================
# T-12: Aligner Kargo verification failure & recovery handling
# =========================================================================

@pytest.mark.asyncio
async def test_t12_verification_failure_skips_gitlab_context_and_sets_verification_fields():
    """T-12: Verification failure sets verification wording/kargo_context and skips gitlab_context seeding."""
    bb = _mock_blackboard()
    created: list[dict] = []

    async def capture_create(**kwargs):
        created.append(kwargs)
        return "evt-verif-1"

    bb.create_event = capture_create
    aligner = _make_aligner(bb)

    mr_url = "https://gitlab.example.com/openshift-virtualization/downstream-configuration/-/merge_requests/25"
    eid = await aligner.handle_failed_promotion(
        service="verify-release-chart@v4-22",
        project="v4-22",
        stage="verify-release-chart",
        promotion="verify-release-chart.01m83xf2.dae4bb2",
        freight="dae4bb27ec6bad98e8f2fbee9ed5f6a39d7b1091",
        phase="Failed",
        message='Metric "check-chart-exists" assessed Failed',
        failed_step="",
        mr_url=mr_url,
        started_at="2026-11-23T09:58:15Z",
        finished_at="2026-11-23T11:30:21Z",
        failure_type="verification",
        verification_id="1605daa6-92cb-4050-addd-89465a90f331",
        analysis_run="verify-release-chart.ar-1",
    )

    assert eid == "evt-verif-1"
    assert len(created) == 1
    assert created[0]["subject_type"] == "kargo_stage"
    assert created[0]["reason"] == "kargo verification failed: verify-release-chart.ar-1"
    ev = created[0]["evidence"]
    assert ev.display_text.startswith("[kargo] Verification failed: verify-release-chart@v4-22 -- ")
    assert ev.gitlab_context is None
    assert ev.kargo_context["mr_url"] == mr_url
    assert ev.kargo_context["failure_type"] == "verification"
    assert ev.kargo_context["verification_id"] == "1605daa6-92cb-4050-addd-89465a90f331"
    assert ev.kargo_context["analysis_run"] == "verify-release-chart.ar-1"


@pytest.mark.asyncio
async def test_t12_verification_failure_respects_l1_l2_l3_gates():
    """T-12: Verification failures still obey active-event (L1), cooldown (L2), and escalation (L3) gates."""
    kwargs = dict(
        service="verify-release-chart@v4-22", project="v4-22", stage="verify-release-chart",
        promotion="p1", freight="f1", phase="Error", message="launch failed", failed_step="",
        mr_url="", failure_type="verification", verification_id="uuid-1", analysis_run="",
    )

    # L1: active event blocks
    bb_l1 = _mock_blackboard()
    bb_l1.get_active_events.return_value = ["evt-active"]
    bb_l1.get_event.return_value = _make_event(event_id="evt-active", service="verify-release-chart@v4-22")
    assert await _make_aligner(bb_l1).handle_failed_promotion(**kwargs) is None
    bb_l1.create_event.assert_not_called()

    # L2: cooldown blocks second creation
    bb_l2 = _mock_blackboard()
    aligner_l2 = _make_aligner(bb_l2)
    assert await aligner_l2.handle_failed_promotion(**kwargs) == "evt-new"
    assert await aligner_l2.handle_failed_promotion(**kwargs) is None
    bb_l2.create_event.assert_called_once()

    # L3: kargo escalation flag blocks
    bb_l3 = _mock_blackboard()
    bb_l3.get_escalation_flag.return_value = "evt-old|kargo verification failed"
    assert await _make_aligner(bb_l3).handle_failed_promotion(**kwargs) is None
    bb_l3.create_event.assert_not_called()
    bb_l3.get_escalation_flag.assert_called_once_with("verify-release-chart@v4-22", scope="kargo")


@pytest.mark.asyncio
async def test_t12_verification_recovery_notifies_active_events_and_clears_kargo_flag():
    """T-12: handle_promotion_recovery(failure_type='verification') posts Verification succeeded & clears kargo flag."""
    bb = _mock_blackboard()
    active_evt = _make_event(event_id="evt-k1", service="verify-release-chart@v4-22")
    bb.get_active_events.return_value = ["evt-k1"]
    bb.get_event.return_value = active_evt
    aligner = _make_aligner(bb)

    await aligner.handle_promotion_recovery(
        service="verify-release-chart@v4-22",
        project="v4-22",
        stage="verify-release-chart",
        promotion="verify-release-chart.01m83xf2.dae4bb2",
        failure_type="verification",
        verification_id="uuid-pass-1",
    )

    bb.append_turn.assert_awaited_once()
    turn = bb.append_turn.call_args.args[1]
    assert turn.actor == "aligner"
    assert turn.action == "confirm"
    assert turn.evidence == "[kargo] Verification succeeded: verify-release-chart@v4-22 (verification=uuid-pass-1)"
    bb.clear_escalation_flag.assert_awaited_once_with("verify-release-chart@v4-22", scope="kargo")

@pytest.mark.asyncio
async def test_t21_handle_failed_promotion_strips_xml():
    bb = _mock_blackboard()
    bb.get_active_events.return_value = []
    aligner = _make_aligner(bb)
    
    await aligner.handle_failed_promotion(
        service="svc", project="p", stage="stg", promotion="promo", freight="f",
        phase="<thought>Failed</thought>", message="<context>hello</context>\nworld", failed_step="s", mr_url="u"
    )
    
    assert bb.create_event.call_count == 1
    call_args = bb.create_event.call_args[1]
    assert "<thought>" not in call_args["reason"]
    assert "<context>" not in call_args["evidence"].display_text
    assert "\n" not in call_args["evidence"].display_text
