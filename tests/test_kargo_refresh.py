# BlackBoard/tests/test_kargo_refresh.py
# @ai-rules:
# 1. [Constraint]: Pure unit tests for handle_refresh_kargo_context (no K8s, no Redis).
# 2. [Pattern]: Mocks ToolContext, Blackboard, KargoObserver, and StateWatcher directly.
"""Unit tests for handle_refresh_kargo_context verification rendering, mirror guards, and StateWatcher parity (T-13)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.handlers_integration import handle_refresh_kargo_context


MR_URL = "https://gitlab.example.com/org/repo/-/merge_requests/42"


def _make_ctx(
    *,
    kc: dict | None = None,
    stage_state: dict | None = None,
    poll_return: dict | None = None,
    poll_side_effect: Exception | None = None,
    with_watcher: bool = False,
):
    bb = MagicMock()
    event = MagicMock()
    evidence = MagicMock()
    evidence.kargo_context = kc if kc is not None else {}
    event.event.evidence = evidence
    bb.get_event = AsyncMock(return_value=event)
    bb.update_event_kargo_context = AsyncMock()
    bb.update_event_gitlab_context = AsyncMock(return_value=True)

    observer = MagicMock()
    observer.get_stage_status = AsyncMock(return_value=stage_state or {})
    if poll_side_effect is not None:
        observer.poll_kargo_stage_status = AsyncMock(side_effect=poll_side_effect)
    else:
        observer.poll_kargo_stage_status = AsyncMock(return_value=poll_return or {})

    watcher = MagicMock() if with_watcher else None
    if watcher is not None:
        watcher.register = MagicMock(return_value=True)

    ctx = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.get_agent_instance.side_effect = lambda name: observer if name == "_kargo_observer" else None
    ctx.next_turn_number = AsyncMock(return_value=3)
    ctx.append_and_broadcast = AsyncMock()
    ctx.broadcast = AsyncMock()
    ctx.get_state_watcher.return_value = watcher
    ctx.get_cycle_id.return_value = "cycle-1"
    return ctx, bb, observer, watcher


@pytest.mark.asyncio
async def test_verification_failure_renders_without_duplicate_phase_and_skips_gitlab_mirror():
    """Verification failure renders Failure Type / Promotion Phase / Verification ID / AnalysisRun / Failed Step: N/A
    without duplicating Verification Phase, and skips update_event_gitlab_context."""
    ctx, bb, _, _ = _make_ctx(
        kc={"project": "v4-22", "stage": "verify-release-chart"},
        stage_state={
            "project": "v4-22",
            "stage": "verify-release-chart",
            "promotion": "verify-release-chart.01abc",
            "phase": "Failed",
            "failed_step": "",
            "message": 'Metric "check-chart-exists" assessed Failed',
            "mr_url": MR_URL,
            "failure_type": "verification",
            "verification_id": "1605daa6-92cb-4050-addd-89465a90f331",
            "analysis_run": "verify-release-chart.01m83xf2.3aa0ebb",
            "_promotion_phase": "Succeeded",
            "_promo_status": {"phase": "Succeeded"},
            "_verification": {
                "id": "1605daa6-92cb-4050-addd-89465a90f331",
                "phase": "Failed",
                "message": 'Metric "check-chart-exists" assessed Failed',
                "analysis_run": "verify-release-chart.01m83xf2.3aa0ebb",
            },
        },
    )

    ok = await handle_refresh_kargo_context(ctx, "evt-v1", {"check_condition": "check status"}, None)

    assert ok is True
    bb.update_event_kargo_context.assert_awaited_once_with(
        "evt-v1",
        {"mr_url": MR_URL, "failure_type": "verification"},
    )
    bb.update_event_gitlab_context.assert_not_awaited()

    turn = ctx.append_and_broadcast.call_args[0][1]
    ev = turn.evidence
    assert "Kargo Stage: verify-release-chart@v4-22" in ev
    assert "Promotion: verify-release-chart.01abc" in ev
    assert "Phase: Failed" in ev
    assert "Failed Step: N/A" in ev
    assert "Failure Type: verification" in ev
    assert "Promotion Phase: Succeeded" in ev
    assert "Verification ID: 1605daa6-92cb-4050-addd-89465a90f331" in ev
    assert "AnalysisRun: verify-release-chart.01m83xf2.3aa0ebb" in ev
    assert "Verification Phase:" not in ev


@pytest.mark.asyncio
async def test_running_and_successful_verification_renders_verification_phase_block():
    """When promotion is Succeeded and verification is Running/Successful, render Verification Phase lines."""
    ctx, bb, _, _ = _make_ctx(
        kc={"project": "v4-22", "stage": "verify-release-chart", "failure_type": "verification"},
        stage_state={
            "project": "v4-22",
            "stage": "verify-release-chart",
            "promotion": "verify-release-chart.01abc",
            "phase": "Succeeded",
            "failed_step": "",
            "message": "",
            "mr_url": MR_URL,
            "failure_type": "promotion",
            "_promotion_phase": "Succeeded",
            "_promo_status": {"phase": "Succeeded"},
            "_verification": {
                "id": "new-verif-uuid",
                "phase": "Running",
                "message": "AnalysisRun in progress",
                "analysis_run": "verify-release-chart.run-2",
            },
        },
    )

    await handle_refresh_kargo_context(ctx, "evt-v2", {}, None)

    bb.update_event_gitlab_context.assert_not_awaited()
    ev = ctx.append_and_broadcast.call_args[0][1].evidence
    assert "Phase: Succeeded" in ev
    assert "Failed Step: N/A" in ev
    assert "Verification Phase: Running" in ev
    assert "Verification ID: new-verif-uuid" in ev
    assert "AnalysisRun: verify-release-chart.run-2" in ev
    assert "Verification Message: AnalysisRun in progress" in ev
    assert "Failure Type: verification" not in ev


@pytest.mark.asyncio
async def test_gitlab_mirror_skipped_when_promotion_succeeded_or_kc_is_verification():
    """Secondary gitlab_context mirror must be skipped when _promotion_phase == 'Succeeded'
    or when existing kargo_context already has failure_type == 'verification'."""
    # Case A: _promotion_phase == "Succeeded" on a non-verification kc
    ctx_a, bb_a, _, _ = _make_ctx(
        kc={"project": "v4-22", "stage": "verify-release-chart"},
        stage_state={
            "promotion": "promo-1",
            "phase": "Succeeded",
            "failed_step": "",
            "mr_url": MR_URL,
            "failure_type": "promotion",
            "_promotion_phase": "Succeeded",
        },
    )
    await handle_refresh_kargo_context(ctx_a, "evt-a", {}, None)
    bb_a.update_event_kargo_context.assert_awaited_once_with("evt-a", {"mr_url": MR_URL})
    bb_a.update_event_gitlab_context.assert_not_awaited()

    # Case B: kc already has failure_type == "verification" even if _promotion_phase is Running
    ctx_b, bb_b, _, _ = _make_ctx(
        kc={"project": "v4-22", "stage": "verify-release-chart", "failure_type": "verification"},
        stage_state={
            "promotion": "promo-2",
            "phase": "Running",
            "failed_step": "",
            "mr_url": MR_URL,
            "failure_type": "promotion",
            "_promotion_phase": "Running",
        },
    )
    await handle_refresh_kargo_context(ctx_b, "evt-b", {}, None)
    bb_b.update_event_kargo_context.assert_awaited_once_with("evt-b", {"mr_url": MR_URL})
    bb_b.update_event_gitlab_context.assert_not_awaited()


@pytest.mark.asyncio
async def test_chat_hydration_persists_verification_marker_even_without_mr_url():
    """Chat/Slack hydration on a verification stage persists failure_type='verification' even if mr_url is empty."""
    ctx, bb, _, _ = _make_ctx(
        kc={},
        stage_state={
            "promotion": "promo-1",
            "phase": "Error",
            "failed_step": "",
            "message": "error building AnalysisRun",
            "mr_url": "",
            "failure_type": "verification",
            "verification_id": "b7c1-uuid",
            "analysis_run": "",
            "_promotion_phase": "Aborted",
            "_verification": {"id": "b7c1-uuid", "phase": "Error", "analysis_run": ""},
        },
    )

    await handle_refresh_kargo_context(
        ctx,
        "evt-chat",
        {"kargo_project": "kargo-demo-alraj", "kargo_stage": "test1"},
        None,
    )

    assert bb.update_event_kargo_context.await_count == 2
    bb.update_event_kargo_context.assert_any_await("evt-chat", {"project": "kargo-demo-alraj", "stage": "test1"})
    bb.update_event_kargo_context.assert_any_await("evt-chat", {"failure_type": "verification"})
    bb.update_event_gitlab_context.assert_not_awaited()


@pytest.mark.asyncio
async def test_subscribe_registers_verification_aware_state_key():
    """subscribe=True without promotion_id passes _verification to extract_kargo_state_key."""
    ctx, _, _, watcher = _make_ctx(
        kc={"project": "v4-22", "stage": "verify-release-chart"},
        stage_state={
            "promotion": "promo-1",
            "phase": "Failed",
            "failed_step": "",
            "failure_type": "verification",
            "_promotion_phase": "Succeeded",
            "_promo_status": {"phase": "Succeeded"},
            "_verification": {"phase": "Failed", "id": "verif-123"},
        },
        with_watcher=True,
    )

    await handle_refresh_kargo_context(ctx, "evt-sub", {"subscribe": True, "poll_interval": 45}, None)

    watcher.register.assert_called_once()
    spec = watcher.register.call_args[0][0]
    assert spec.state_key == {
        "phase": "Succeeded",
        "failed_step": "",
        "verification_phase": "Failed",
        "verification_id": "verif-123",
    }
    assert spec.interval == 45
    assert "subscription_active: true" in ctx.append_and_broadcast.call_args[0][1].evidence


@pytest.mark.asyncio
async def test_subscribe_with_promotion_id_delegates_state_key_to_poll_kargo_stage_status():
    """When promotion_id AND subscribe=True are passed, state_key is derived via poll_kargo_stage_status."""
    polled_key = {
        "phase": "Succeeded",
        "failed_step": "",
        "verification_phase": "Running",
        "verification_id": "verif-live-99",
    }
    ctx, _, observer, watcher = _make_ctx(
        kc={"project": "v4-22", "stage": "verify-release-chart"},
        stage_state={
            "promotion": "promo-explicit",
            "phase": "Succeeded",
            "failed_step": "",
            "failure_type": "promotion",
            "_promo_status": {"phase": "Succeeded"},
            "_verification": {},
        },
        poll_return=polled_key,
        with_watcher=True,
    )

    await handle_refresh_kargo_context(
        ctx,
        "evt-promo-sub",
        {"promotion_id": "promo-explicit", "subscribe": True},
        None,
    )

    observer.poll_kargo_stage_status.assert_awaited_once_with("v4-22", "verify-release-chart")
    spec = watcher.register.call_args[0][0]
    assert spec.state_key == polled_key


@pytest.mark.asyncio
async def test_subscribe_with_promotion_id_falls_back_when_poll_raises():
    """If poll_kargo_stage_status raises during promotion_id+subscribe, fall back to extract_kargo_state_key."""
    ctx, _, observer, watcher = _make_ctx(
        kc={"project": "v4-22", "stage": "verify-release-chart"},
        stage_state={
            "promotion": "promo-explicit",
            "phase": "Running",
            "failed_step": "",
            "_promo_status": {"phase": "Running"},
            "_verification": {},
        },
        poll_side_effect=RuntimeError("transient K8s timeout"),
        with_watcher=True,
    )

    await handle_refresh_kargo_context(
        ctx,
        "evt-promo-fallback",
        {"promotion_id": "promo-explicit", "subscribe": True},
        None,
    )

    observer.poll_kargo_stage_status.assert_awaited_once_with("v4-22", "verify-release-chart")
    spec = watcher.register.call_args[0][0]
    assert spec.state_key == {"phase": "Running", "failed_step": ""}


@pytest.mark.asyncio
async def test_subscribe_bare_fallback_coerces_empty_phase_and_failed_step():
    """When neither _promo_status nor _verification exists, bare fallback coerces phase='unknown' and failed_step=''."""
    ctx, _, _, watcher = _make_ctx(
        kc={"project": "v4-22", "stage": "verify-release-chart"},
        stage_state={"promotion": "promo-1", "phase": "", "failed_step": None},
        with_watcher=True,
    )

    await handle_refresh_kargo_context(ctx, "evt-bare", {"subscribe": True}, None)

    spec = watcher.register.call_args[0][0]
    assert spec.state_key == {"phase": "unknown", "failed_step": ""}


@pytest.mark.asyncio
async def test_t21_verification_to_promotion_transition():
    from src.agents.handlers_integration import handle_refresh_kargo_context
    from unittest.mock import MagicMock, AsyncMock
    bb = AsyncMock()
    evt = MagicMock()
    evt.event.evidence.kargo_context = {"project": "p", "stage": "s", "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/42", "failure_type": "verification"}
    bb.get_event.return_value = evt
    kargo_obs = MagicMock()
    kargo_obs.get_stage_status = AsyncMock(return_value={"promotion": "promo", "phase": "Failed", "_promotion_phase": "Failed", "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/42"})
    
    ctx = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.get_agent_instance.return_value = kargo_obs
    ctx.get_state_watcher.return_value = None
    ctx.next_turn_number = AsyncMock(return_value=2)
    ctx.append_and_broadcast = AsyncMock()
    
    await handle_refresh_kargo_context(ctx, "evt-1", {"kargo_project": "p", "kargo_stage": "s"}, [])
    
    bb.update_event_kargo_context.assert_called_with("evt-1", {"failure_type": "promotion"})
    bb.update_event_gitlab_context.assert_called_once()


@pytest.mark.asyncio
async def test_m2_legacy_mirror_tagged_on_verification_mr_url_flip():
    """M2: When verification refreshes to a newer kc.mr_url, an untagged legacy gitlab_context
    matching the old kc.mr_url is stamped with mirrored_from_kargo=True before overwriting mr_url."""
    old_url = "https://gitlab.example.com/org/repo/-/merge_requests/10"
    new_url = "https://gitlab.example.com/org/repo/-/merge_requests/11"
    ctx, bb, _, _ = _make_ctx(
        kc={"project": "v4-22", "stage": "verify-release-chart", "mr_url": old_url, "failure_type": "verification"},
        stage_state={
            "project": "v4-22",
            "stage": "verify-release-chart",
            "promotion": "promo-2",
            "phase": "Failed",
            "failure_type": "verification",
            "mr_url": new_url,
            "verification_id": "v-2",
            "analysis_run": "ar-2",
            "_promo_status": {"phase": "Succeeded"},
            "_verification": {"id": "v-2", "phase": "Failed", "analysis_run": "ar-2"},
            "_promotion_phase": "Succeeded",
        },
    )
    ev = bb.get_event.return_value
    ev.event.evidence.gitlab_context = {
        "target_url": old_url,
        "project_id": "org/repo",
        "mr_iid": 10,
    }

    await handle_refresh_kargo_context(ctx, "evt-m2", {}, None)

    bb.update_event_gitlab_context.assert_awaited_once_with("evt-m2", {"mirrored_from_kargo": True})
    bb.update_event_kargo_context.assert_awaited_once_with("evt-m2", {"mr_url": new_url, "failure_type": "verification"})


@pytest.mark.asyncio
async def test_t21_prompt_injection_fences_stripped():
    from src.agents.handlers_integration import handle_refresh_kargo_context
    from unittest.mock import MagicMock, AsyncMock
    bb = AsyncMock()
    evt = MagicMock()
    evt.event.evidence.kargo_context = None
    bb.get_event.return_value = evt
    kargo_obs = MagicMock()
    kargo_obs.get_stage_status = AsyncMock(return_value={"promotion": "promo", "phase": "Failed", "message": "<context>hack</context>", "mr_url": "url1"})
    
    ctx = MagicMock()
    ctx.get_blackboard.return_value = bb
    ctx.get_agent_instance.return_value = kargo_obs
    ctx.get_state_watcher.return_value = None
    ctx.next_turn_number = AsyncMock(return_value=2)
    ctx.append_and_broadcast = AsyncMock()
    
    await handle_refresh_kargo_context(ctx, "evt-1", {"kargo_project": "p", "kargo_stage": "s"}, [])
    
    turn = ctx.append_and_broadcast.call_args[0][1]
    assert "<context>" not in turn.evidence

