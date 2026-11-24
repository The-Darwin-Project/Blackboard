# tests/test_kargo_observer.py
# @ai-rules:
# 1. [Constraint]: No real K8s API calls. All K8s interactions mocked.
# 2. [Pattern]: Tests exercise _process_stage directly with dict fixtures from real CRDs.
# 3. [Pattern]: Async tests use pytest-asyncio. Callbacks are AsyncMock.
"""Unit tests for KargoObserver -- promotion failure detection + recovery."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.observers.kargo import KargoObserver, FAILED_PHASES


def _make_stage(
    namespace: str = "kargo-test-project",
    name: str = "test-stage",
    promo_name: str = "test-stage.01abc.freight1",
    phase: str = "Errored",
    message: str = 'step "wait-for-merge" timed out after 3h0m0s',
    freight_name: str = "freight123",
    failed_step_alias: str = "wait-for-merge",
    mr_url: str = "",
    started_at: str = "2026-04-12T10:00:00Z",
    finished_at: str = "2026-04-12T13:00:00Z",
) -> dict:
    step_meta = [
        {"alias": "pipeline-payload", "status": "Succeeded"},
        {"alias": "trigger-pipeline", "status": "Succeeded"},
        {"alias": failed_step_alias, "status": "Errored", "message": message},
    ]
    state = {}
    if mr_url:
        state["open-mr"] = {"pr": {"id": 10, "url": mr_url}}

    return {
        "metadata": {"namespace": namespace, "name": name, "resourceVersion": "12345"},
        "status": {
            "lastPromotion": {
                "name": promo_name,
                "finishedAt": finished_at,
                "freight": {"name": freight_name},
                "status": {
                    "phase": phase,
                    "message": message,
                    "startedAt": started_at,
                    "finishedAt": finished_at,
                    "stepExecutionMetadata": step_meta,
                    "state": state,
                },
            },
        },
    }


def _make_observer(failure_cb=None, recovery_cb=None) -> KargoObserver:
    bb = AsyncMock()
    obs = KargoObserver(
        blackboard=bb,
        failure_callback=failure_cb or AsyncMock(),
        recovery_callback=recovery_cb or AsyncMock(),
    )
    return obs


# =========================================================================
# Test 1: Failed promotion detected
# =========================================================================

@pytest.mark.asyncio
async def test_failed_promotion_fires_callback():
    """MODIFIED event with Errored phase fires failure_callback with correct kargo_context."""
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)

    stage = _make_stage(
        namespace="kargo-cnv-must-gather-v4-13",
        name="must-gather-v4.13",
        promo_name="must-gather-v4.13.01kp0mc.36cd9f0",
        phase="Errored",
        message='step "wait-for-merge" timed out after 3h0m0s',
        freight_name="36cd9f0851536af6",
        failed_step_alias="wait-for-merge",
        mr_url="https://gitlab.example.com/merge_requests/10",
    )

    await obs._process_stage(stage)

    failure_cb.assert_called_once()
    kwargs = failure_cb.call_args.kwargs
    assert kwargs["service"] == "must-gather-v4.13@kargo-cnv-must-gather-v4-13"
    assert kwargs["project"] == "kargo-cnv-must-gather-v4-13"
    assert kwargs["stage"] == "must-gather-v4.13"
    assert kwargs["promotion"] == "must-gather-v4.13.01kp0mc.36cd9f0"
    assert kwargs["freight"] == "36cd9f0851536af6"
    assert kwargs["phase"] == "Errored"
    assert kwargs["failed_step"] == "wait-for-merge"
    assert kwargs["mr_url"] == "https://gitlab.example.com/merge_requests/10"


@pytest.mark.asyncio
async def test_failed_phase_variants():
    """Both 'Errored' and 'Failed' phases trigger the callback."""
    for phase in FAILED_PHASES:
        failure_cb = AsyncMock()
        obs = _make_observer(failure_cb=failure_cb)
        stage = _make_stage(phase=phase, promo_name=f"promo-{phase}")
        await obs._process_stage(stage)
        assert failure_cb.called, f"phase={phase} did not trigger callback"


# =========================================================================
# Test 2: Dedup prevents duplicate events
# =========================================================================

@pytest.mark.asyncio
async def test_dedup_same_promotion_fires_once():
    """Same promotion name on same stage fires callback only once."""
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)

    stage = _make_stage(promo_name="promo-abc")
    await obs._process_stage(stage)
    await obs._process_stage(stage)
    await obs._process_stage(stage)

    assert failure_cb.call_count == 1


@pytest.mark.asyncio
async def test_dedup_new_promotion_fires_again():
    """Different promotion name on same stage fires a new callback."""
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)

    stage1 = _make_stage(promo_name="promo-v1")
    stage2 = _make_stage(promo_name="promo-v2")

    await obs._process_stage(stage1)
    await obs._process_stage(stage2)

    assert failure_cb.call_count == 2


@pytest.mark.asyncio
async def test_dedup_different_stages_independent():
    """Different stages track independently."""
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)

    stage_a = _make_stage(namespace="proj-a", name="stage-a", promo_name="promo-1")
    stage_b = _make_stage(namespace="proj-b", name="stage-b", promo_name="promo-1")

    await obs._process_stage(stage_a)
    await obs._process_stage(stage_b)

    assert failure_cb.call_count == 2


# =========================================================================
# Test 3: Recovery detection
# =========================================================================

@pytest.mark.asyncio
async def test_recovery_fires_on_newer_succeeded_promotion():
    """When a watched stage gets a newer Succeeded promotion, recovery_callback fires."""
    failure_cb = AsyncMock()
    recovery_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb, recovery_cb=recovery_cb)

    errored = _make_stage(promo_name="promo-v1", phase="Errored")
    await obs._process_stage(errored)
    assert failure_cb.call_count == 1
    assert "kargo-test-project/test-stage" in obs._active_watches

    succeeded = _make_stage(promo_name="promo-v2", phase="Succeeded")
    await obs._process_stage(succeeded)

    recovery_cb.assert_called_once()
    kwargs = recovery_cb.call_args.kwargs
    assert kwargs["service"] == "test-stage@kargo-test-project"
    assert kwargs["promotion"] == "promo-v2"

    assert "kargo-test-project/test-stage" not in obs._active_watches
    assert "kargo-test-project/test-stage" not in obs._reported_failures


@pytest.mark.asyncio
async def test_recovery_ignores_same_promotion_succeeded():
    """Succeeded with same promotion name as the failure does NOT trigger recovery."""
    failure_cb = AsyncMock()
    recovery_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb, recovery_cb=recovery_cb)

    errored = _make_stage(promo_name="promo-v1", phase="Errored")
    await obs._process_stage(errored)

    same_succeeded = _make_stage(promo_name="promo-v1", phase="Succeeded")
    await obs._process_stage(same_succeeded)

    recovery_cb.assert_not_called()


@pytest.mark.asyncio
async def test_recovery_only_for_watched_stages():
    """Succeeded on a stage that's NOT in _active_watches doesn't fire recovery."""
    recovery_cb = AsyncMock()
    obs = _make_observer(recovery_cb=recovery_cb)

    succeeded = _make_stage(promo_name="promo-v1", phase="Succeeded")
    await obs._process_stage(succeeded)

    recovery_cb.assert_not_called()


# =========================================================================
# Test 4: Initial sync suppresses callbacks
# =========================================================================

@pytest.mark.asyncio
async def test_initial_sync_records_without_callbacks():
    """suppress_callbacks=True records failures but does NOT fire callbacks."""
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)

    stage = _make_stage(promo_name="promo-old", phase="Errored")
    await obs._process_stage(stage, suppress_callbacks=True)

    failure_cb.assert_not_called()
    assert obs._reported_failures.get("kargo-test-project/test-stage") == "promo-old"


@pytest.mark.asyncio
async def test_initial_sync_prevents_duplicate_on_watch():
    """After initial sync records a failure, watch event for same promo doesn't re-fire."""
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)

    stage = _make_stage(promo_name="promo-old", phase="Errored")
    await obs._process_stage(stage, suppress_callbacks=True)
    await obs._process_stage(stage, suppress_callbacks=False)

    failure_cb.assert_not_called()


# =========================================================================
# Test 5: Skip conditions
# =========================================================================

@pytest.mark.asyncio
async def test_skip_stage_without_last_promotion():
    """Stages with no lastPromotion are silently skipped."""
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)

    stage = {"metadata": {"namespace": "ns", "name": "empty"}, "status": {}}
    await obs._process_stage(stage)
    failure_cb.assert_not_called()


@pytest.mark.asyncio
async def test_skip_running_promotion():
    """Promotions with phase=Running are not treated as failures."""
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)

    stage = _make_stage(phase="Running")
    await obs._process_stage(stage)
    failure_cb.assert_not_called()


@pytest.mark.asyncio
async def test_skip_succeeded_without_active_watch():
    """Succeeded promotions without active watches are silently skipped."""
    failure_cb = AsyncMock()
    recovery_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb, recovery_cb=recovery_cb)

    stage = _make_stage(phase="Succeeded")
    await obs._process_stage(stage)
    failure_cb.assert_not_called()
    recovery_cb.assert_not_called()


# =========================================================================
# Test 6: Helper extraction
# =========================================================================

def test_extract_failed_step():
    """_extract_failed_step returns the alias of the first Errored step."""
    promo_status = {
        "stepExecutionMetadata": [
            {"alias": "git-clone", "status": "Succeeded"},
            {"alias": "wait-for-merge", "status": "Errored", "message": "timed out"},
            {"alias": "notify", "status": "Skipped"},
        ],
    }
    assert KargoObserver._extract_failed_step(promo_status) == "wait-for-merge"


def test_extract_failed_step_empty():
    """_extract_failed_step returns empty string when no step errored."""
    assert KargoObserver._extract_failed_step({}) == ""
    assert KargoObserver._extract_failed_step({"stepExecutionMetadata": []}) == ""


def test_extract_mr_url_open_mr():
    """_extract_mr_url finds URL from open-mr step state."""
    promo_status = {
        "state": {
            "open-mr": {"pr": {"id": 10, "url": "https://gitlab.example.com/mr/10"}},
        },
    }
    assert KargoObserver._extract_mr_url(promo_status) == "https://gitlab.example.com/mr/10"


def test_extract_mr_url_underscore_key():
    """_extract_mr_url also checks open_mr (underscore variant)."""
    promo_status = {
        "state": {
            "open_mr": {"pr": {"id": 5, "url": "https://gitlab.example.com/mr/5"}},
        },
    }
    assert KargoObserver._extract_mr_url(promo_status) == "https://gitlab.example.com/mr/5"


def test_extract_mr_url_missing():
    """_extract_mr_url returns empty string when no MR step exists."""
    assert KargoObserver._extract_mr_url({}) == ""
    assert KargoObserver._extract_mr_url({"state": {}}) == ""


# =========================================================================
# Test 7: get_stage_status (on-demand read)
# =========================================================================

@pytest.mark.asyncio
async def test_get_stage_status_returns_structured_data():
    """get_stage_status returns promotion details from K8s GET."""
    obs = _make_observer()
    obs._k8s_available = True
    obs._custom_api = MagicMock()

    stage_cr = _make_stage(
        namespace="proj", name="prod",
        promo_name="prod.01abc.freight1",
        phase="Errored", message="timed out",
        failed_step_alias="wait-for-merge",
    )
    obs._custom_api.get_namespaced_custom_object = MagicMock(return_value=stage_cr)

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=stage_cr)
        result = await obs.get_stage_status("proj", "prod")

    assert result["project"] == "proj"
    assert result["stage"] == "prod"
    assert result["phase"] == "Errored"
    assert result["failed_step"] == "wait-for-merge"
    assert result["promotion"] == "prod.01abc.freight1"


@pytest.mark.asyncio
async def test_get_stage_status_returns_error_on_failure():
    """get_stage_status returns error dict when K8s API fails."""
    obs = _make_observer()
    obs._k8s_available = True
    obs._custom_api = MagicMock()

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(side_effect=Exception("API timeout"))
        result = await obs.get_stage_status("proj", "prod")

    assert "error" in result
    assert "API timeout" in result["error"]


@pytest.mark.asyncio
async def test_get_stage_status_k8s_unavailable():
    """get_stage_status returns error when K8s client not initialized."""
    obs = _make_observer()
    obs._k8s_available = False

    result = await obs.get_stage_status("proj", "prod")
    assert "error" in result


# =========================================================================
# Test 8: Model backward compatibility
# =========================================================================

def test_event_document_subject_type_default():
    """EventDocument defaults subject_type to 'service' for backward compat."""
    from src.models import EventDocument, EventInput, EventEvidence
    doc = EventDocument(
        source="aligner",
        service="darwin-store",
        event=EventInput(reason="test", evidence=EventEvidence(display_text="test")),
    )
    assert doc.subject_type == "service"


def test_event_document_kargo_stage():
    """EventDocument accepts subject_type='kargo_stage'."""
    from src.models import EventDocument, EventInput, EventEvidence
    doc = EventDocument(
        source="aligner",
        service="test-stage@kargo-test",
        subject_type="kargo_stage",
        event=EventInput(
            reason="kargo promotion failed",
            evidence=EventEvidence(
                display_text="test",
                kargo_context={"project": "kargo-test", "stage": "test-stage"},
            ),
        ),
    )
    assert doc.subject_type == "kargo_stage"
    assert doc.event.evidence.kargo_context["project"] == "kargo-test"


def test_event_evidence_kargo_context_default_none():
    """EventEvidence.kargo_context defaults to None."""
    from src.models import EventEvidence
    ev = EventEvidence(display_text="cpu spike")
    assert ev.kargo_context is None


def test_event_document_deserialize_without_subject_type():
    """Old EventDocument JSON without subject_type deserializes with default."""
    from src.models import EventDocument
    old_json = {
        "id": "evt-abc123",
        "source": "aligner",
        "status": "new",
        "service": "darwin-store",
        "event": {"reason": "high cpu", "evidence": "cpu at 95%", "timeDate": "2026-01-01T00:00:00Z"},
        "conversation": [],
    }
    doc = EventDocument.model_validate(old_json)
    assert doc.subject_type == "service"


# =========================================================================
# Helpers for verification failure tests (T-1 .. T-11)
# =========================================================================

def _make_verif_stage(
    namespace: str = "v4-22",
    name: str = "verify-release-chart",
    promo_name: str = "verify-release-chart.01m83xf2.dae4bb2",
    promo_phase: str = "Succeeded",
    promo_fc_id: str = "dae4bb27ec6bad98e8f2fbee9ed5f6a39d7b1091",
    promo_started_at: str = "2026-11-23T09:58:15Z",
    promo_finished_at: str = "2026-11-23T09:58:15Z",
    fh_id: str = "dae4bb27ec6bad98e8f2fbee9ed5f6a39d7b1091",
    verif_id: str = "1605daa6-92cb-4050-addd-89465a90f331",
    verif_phase: str = "Failed",
    verif_message: str = 'Metric "check-chart-exists" assessed Failed',
    verif_start: str = "2026-11-23T09:58:15Z",
    verif_finish: str = "2026-11-23T11:30:21Z",
    analysis_run: str | None = "verify-release-chart.01m83xf2jcgzpb7323tcajppsx.3aa0ebb",
    include_last_promo: bool = True,
    include_verif: bool = True,
    has_spec_verification: bool = False,
    mr_url: str = "",
) -> dict:
    status: dict = {"freightSummary": fh_id}
    if include_last_promo:
        promo_status: dict = {
            "phase": promo_phase,
            "startedAt": promo_started_at,
            "finishedAt": promo_finished_at,
            "freightCollection": {"id": promo_fc_id},
        }
        if mr_url:
            promo_status["state"] = {"open-mr": {"pr": {"id": 42, "url": mr_url}}}
        status["lastPromotion"] = {
            "name": promo_name,
            "finishedAt": promo_finished_at,
            "status": promo_status,
        }
    if include_verif:
        vh0: dict = {
            "id": verif_id,
            "phase": verif_phase,
            "startTime": verif_start,
            "finishTime": verif_finish,
            "message": verif_message,
        }
        if analysis_run is not None:
            vh0["analysisRun"] = {"name": analysis_run, "namespace": namespace, "phase": verif_phase}
        status["freightHistory"] = [{"id": fh_id, "verificationHistory": [vh0]}]
    else:
        status["freightHistory"] = []

    stage: dict = {
        "metadata": {"namespace": namespace, "name": name, "resourceVersion": "999"},
        "status": status,
    }
    if has_spec_verification:
        stage["spec"] = {"verification": {"analysisTemplates": [{"name": "check-chart-exists"}]}}
    return stage


# =========================================================================
# T-1: Verification Failed / Error (no analysisRun) / Inconclusive
# =========================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("verif_phase", "analysis_run"),
    [
        ("Failed", "verify-release-chart.ar-1"),
        ("Error", None),
        ("Inconclusive", "verify-release-chart.ar-2"),
    ],
)
async def test_t1_verification_failure_phases_fire_callback_and_populate_snapshot(verif_phase, analysis_run):
    """T-1: Failed, Error (absent analysisRun), and Inconclusive fire verification failure_callback."""
    failure_cb = AsyncMock()
    broadcast_cb = AsyncMock()
    obs = KargoObserver(blackboard=AsyncMock(), failure_callback=failure_cb, broadcast_callback=broadcast_cb)

    stage = _make_verif_stage(
        verif_phase=verif_phase,
        verif_message=f"verification {verif_phase} detail",
        analysis_run=analysis_run,
        mr_url="https://gitlab.example.com/org/repo/-/merge_requests/99",
    )
    await obs._process_stage(stage)

    failure_cb.assert_awaited_once()
    kw = failure_cb.call_args.kwargs
    assert kw["failure_type"] == "verification"
    assert kw["phase"] == verif_phase
    assert kw["message"] == f"verification {verif_phase} detail"
    assert kw["failed_step"] == ""
    assert kw["verification_id"] == "1605daa6-92cb-4050-addd-89465a90f331"
    assert kw["analysis_run"] == (analysis_run or "")
    assert kw["started_at"] == "2026-11-23T09:58:15Z"
    assert kw["finished_at"] == "2026-11-23T11:30:21Z"
    assert kw["freight"] == "dae4bb27ec6bad98e8f2fbee9ed5f6a39d7b1091"
    assert kw["mr_url"] == "https://gitlab.example.com/org/repo/-/merge_requests/99"

    snaps = obs.get_failed_stages()
    assert len(snaps) == 1
    assert snaps[0]["failure_type"] == "verification"
    assert snaps[0]["phase"] == verif_phase
    assert snaps[0]["verification_id"] == "1605daa6-92cb-4050-addd-89465a90f331"
    assert snaps[0]["analysis_run"] == (analysis_run or "")
    broadcast_cb.assert_awaited_once()


# =========================================================================
# T-2: Verification Aborted neither fails nor recovers
# =========================================================================

@pytest.mark.asyncio
async def test_t2_verification_aborted_ignored_and_holds_active_watch():
    """T-2: Aborted verification neither fires failure_callback nor clears active watches."""
    failure_cb = AsyncMock()
    recovery_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb, recovery_cb=recovery_cb)

    aborted = _make_verif_stage(verif_phase="Aborted", verif_id="uuid-aborted")
    await obs._process_stage(aborted)
    failure_cb.assert_not_called()
    recovery_cb.assert_not_called()
    assert obs.get_failed_stages() == []

    # Active watch from a prior verification failure must remain intact on Aborted
    failed = _make_verif_stage(verif_phase="Failed", verif_id="uuid-fail-1")
    await obs._process_stage(failed)
    assert "v4-22/verify-release-chart" in obs._active_watches

    aborted_next = _make_verif_stage(verif_phase="Aborted", verif_id="uuid-aborted-2")
    await obs._process_stage(aborted_next)
    recovery_cb.assert_not_called()
    assert "v4-22/verify-release-chart" in obs._active_watches
    assert failure_cb.call_count == 1


# =========================================================================
# T-3: Re-verification UUID dedup on same promotion/freight
# =========================================================================

@pytest.mark.asyncio
async def test_t3_reverification_same_promo_new_uuid_fires_duplicate_deduped():
    """T-3: Duplicate verification id is deduplicated; new id on same promotion fires again."""
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)

    v1 = _make_verif_stage(verif_id="uuid-1", verif_phase="Failed")
    await obs._process_stage(v1)
    await obs._process_stage(v1)
    assert failure_cb.call_count == 1

    v2 = _make_verif_stage(verif_id="uuid-2", verif_phase="Failed")
    await obs._process_stage(v2)
    assert failure_cb.call_count == 2
    assert obs._reported_failures["v4-22/verify-release-chart"] == "verification:uuid-2"


# =========================================================================
# T-4: Manual re-verify after Aborted promotion / absent lastPromotion / RFC3339 fractional ordering
# =========================================================================

@pytest.mark.asyncio
async def test_t4_manual_reverify_after_aborted_and_absent_last_promo():
    """T-4: Post-abort manual re-verify fires; stale pre-abort blocked; fractional RFC3339 accurate."""
    from src.observers.kargo_helpers import is_verification_stale

    # 1. kargo-demo-alraj/test1 pattern: Aborted promo (June 30) + later manual re-verify Error (July 9)
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)
    later_reverify = _make_verif_stage(
        namespace="kargo-demo-alraj", name="test1",
        promo_name="test1.01k", promo_phase="Aborted",
        promo_fc_id="0946cd5d", promo_started_at="2026-06-30T09:55:00Z", promo_finished_at="2026-06-30T10:00:00Z",
        fh_id="ad03b0c3", verif_id="b7c1", verif_phase="Error",
        verif_start="2026-07-09T12:00:00Z", verif_finish="2026-07-09T12:00:01Z",
        analysis_run=None,
    )
    await obs._process_stage(later_reverify)
    failure_cb.assert_awaited_once()
    assert failure_cb.call_args.kwargs["failure_type"] == "verification"
    assert failure_cb.call_args.kwargs["phase"] == "Error"
    assert failure_cb.call_args.kwargs["analysis_run"] == ""

    # 2. Absent lastPromotion still triggers verification failure
    failure_cb2 = AsyncMock()
    obs2 = _make_observer(failure_cb=failure_cb2)
    no_promo = _make_verif_stage(include_last_promo=False, verif_id="uuid-nopromo", verif_phase="Failed")
    await obs2._process_stage(no_promo)
    failure_cb2.assert_awaited_once()
    assert failure_cb2.call_args.kwargs["promotion"] == ""
    assert failure_cb2.call_args.kwargs["failure_type"] == "verification"

    # 3. Stale pre-abort verification (verif_ts < promo_ts) must NOT re-fire
    failure_cb3 = AsyncMock()
    obs3 = _make_observer(failure_cb=failure_cb3)
    stale_pre_abort = _make_verif_stage(
        promo_phase="Aborted", promo_finished_at="2026-07-09T12:00:00Z",
        verif_phase="Failed", verif_start="2026-07-08T12:00:00Z", verif_finish="2026-07-08T12:05:00Z",
    )
    await obs3._process_stage(stale_pre_abort)
    failure_cb3.assert_not_called()

    # 4. Fractional-second RFC3339 ordering: .500Z > whole-second Z (lexical compare would fail: '.' < 'Z')
    promo_whole = {"status": {"phase": "Aborted", "finishedAt": "2026-07-09T12:00:00Z"}}
    verif_frac_after = {"phase": "Error", "start_time": "2026-07-09T12:00:00.500Z", "finish_time": ""}
    assert is_verification_stale(promo_whole, verif_frac_after) is False

    promo_frac = {"status": {"phase": "Aborted", "finishedAt": "2026-07-09T12:00:00.500Z"}}
    verif_whole_before = {"phase": "Error", "start_time": "2026-07-09T12:00:00Z", "finish_time": ""}
    assert is_verification_stale(promo_frac, verif_whole_before) is True


# =========================================================================
# T-5: False-recovery guard
# =========================================================================

@pytest.mark.asyncio
@pytest.mark.parametrize("verif_phase", ["Running", "Pending", "Failed"])
async def test_t5_false_recovery_blocked_while_verification_not_successful(verif_phase):
    """T-5: Errored -> Succeeded promotion does NOT recover while verification is Running/Pending/Failed."""
    failure_cb = AsyncMock()
    recovery_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb, recovery_cb=recovery_cb)

    errored = _make_stage(namespace="v4-22", name="verify-release-chart", promo_name="p1", phase="Errored")
    await obs._process_stage(errored)
    assert "v4-22/verify-release-chart" in obs._active_watches

    next_stage = _make_verif_stage(promo_name="p2", promo_phase="Succeeded", verif_phase=verif_phase)
    await obs._process_stage(next_stage)
    recovery_cb.assert_not_called()


@pytest.mark.asyncio
async def test_t5_false_recovery_blocked_empty_freight_history_with_spec_verification():
    """T-5: Empty freightHistory on a stage with spec.verification blocks premature recovery."""
    failure_cb = AsyncMock()
    recovery_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb, recovery_cb=recovery_cb)

    errored = _make_stage(namespace="v4-22", name="verify-release-chart", promo_name="p1", phase="Errored")
    await obs._process_stage(errored)

    succeeded_no_vh = _make_verif_stage(
        promo_name="p2", promo_phase="Succeeded", include_verif=False, has_spec_verification=True,
    )
    await obs._process_stage(succeeded_no_vh)
    recovery_cb.assert_not_called()
    assert "v4-22/verify-release-chart" in obs._active_watches


# =========================================================================
# T-6: Stale freightHistory[0] guard
# =========================================================================

@pytest.mark.asyncio
async def test_t6_stale_freight_history_guard():
    """T-6: (a) failed promo + stale Successful verif reports promo failure; (b) Succeeded fc_id mismatch ignored."""
    # (a) Failed promotion + stale Successful verification -> reports promotion failure
    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)
    failed_promo = _make_verif_stage(
        promo_name="p-fail", promo_phase="Errored", promo_fc_id="fc-new",
        fh_id="fc-old", verif_phase="Successful",
    )
    await obs._process_stage(failed_promo)
    failure_cb.assert_awaited_once()
    assert failure_cb.call_args.kwargs["failure_type"] == "promotion"
    assert failure_cb.call_args.kwargs["promotion"] == "p-fail"

    # (b) Succeeded promotion with freightCollection.id != freightHistory[0].id ignores stale verif failure & recovery
    failure_cb2 = AsyncMock()
    recovery_cb2 = AsyncMock()
    obs2 = _make_observer(failure_cb=failure_cb2, recovery_cb=recovery_cb2)
    obs2._active_watches["v4-22/verify-release-chart"] = "verify-release-chart@v4-22"
    obs2._reported_failures["v4-22/verify-release-chart"] = "p-old"

    stale_verif_fail = _make_verif_stage(
        promo_name="p-new", promo_phase="Succeeded", promo_fc_id="fc-new",
        fh_id="fc-old", verif_phase="Failed", verif_id="uuid-stale-fail",
    )
    await obs2._process_stage(stale_verif_fail)
    failure_cb2.assert_not_called()
    recovery_cb2.assert_not_called()

    stale_verif_ok = _make_verif_stage(
        promo_name="p-new", promo_phase="Succeeded", promo_fc_id="fc-new",
        fh_id="fc-old", verif_phase="Successful", verif_id="uuid-stale-ok",
    )
    await obs2._process_stage(stale_verif_ok)
    recovery_cb2.assert_not_called()
    assert "v4-22/verify-release-chart" in obs2._active_watches


# =========================================================================
# T-7: Verification recovery (Failed -> Successful on new UUID, same promotion)
# =========================================================================

@pytest.mark.asyncio
async def test_t7_verification_recovery_same_promo_new_uuid():
    """T-7: Failed -> Successful verification on new UUID with unchanged promo fires recovery and clears state."""
    failure_cb = AsyncMock()
    recovery_cb = AsyncMock()
    broadcast_cb = AsyncMock()
    obs = KargoObserver(
        blackboard=AsyncMock(), failure_callback=failure_cb,
        recovery_callback=recovery_cb, broadcast_callback=broadcast_cb,
    )

    failed = _make_verif_stage(promo_name="same-promo", verif_id="uuid-fail", verif_phase="Failed")
    await obs._process_stage(failed)
    assert "v4-22/verify-release-chart" in obs._active_watches
    assert obs._reported_failures["v4-22/verify-release-chart"] == "verification:uuid-fail"

    succeeded = _make_verif_stage(promo_name="same-promo", verif_id="uuid-pass", verif_phase="Successful")
    await obs._process_stage(succeeded)

    recovery_cb.assert_awaited_once()
    kw = recovery_cb.call_args.kwargs
    assert kw["service"] == "verify-release-chart@v4-22"
    assert kw["project"] == "v4-22"
    assert kw["stage"] == "verify-release-chart"
    assert kw["promotion"] == "same-promo"
    assert kw["failure_type"] == "verification"
    assert kw["verification_id"] == "uuid-pass"
    assert "v4-22/verify-release-chart" not in obs._failure_details
    assert "v4-22/verify-release-chart" not in obs._reported_failures
    assert "v4-22/verify-release-chart" not in obs._active_watches
    assert broadcast_cb.call_count == 2


# =========================================================================
# T-8: Initial sync suppression + callback exception safety
# =========================================================================

@pytest.mark.asyncio
async def test_t8_initial_sync_verification_and_callback_exception_safety():
    """T-8: suppress_callbacks=True records failure without watch/broadcast; later recovery clears quietly; callback error safe."""
    failure_cb = AsyncMock()
    recovery_cb = AsyncMock()
    broadcast_cb = AsyncMock()
    obs = KargoObserver(
        blackboard=AsyncMock(), failure_callback=failure_cb,
        recovery_callback=recovery_cb, broadcast_callback=broadcast_cb,
    )

    failed = _make_verif_stage(verif_id="uuid-init", verif_phase="Failed")
    await obs._process_stage(failed, suppress_callbacks=True)

    failure_cb.assert_not_called()
    broadcast_cb.assert_not_called()
    assert obs._reported_failures["v4-22/verify-release-chart"] == "verification:uuid-init"
    assert "v4-22/verify-release-chart" in obs._failure_details
    assert "v4-22/verify-release-chart" not in obs._active_watches

    # Later watch recovery clears _failure_details & broadcasts without calling recovery_callback
    recovered = _make_verif_stage(verif_id="uuid-ok", verif_phase="Successful")
    await obs._process_stage(recovered, suppress_callbacks=False)
    recovery_cb.assert_not_called()
    assert "v4-22/verify-release-chart" not in obs._failure_details
    assert "v4-22/verify-release-chart" not in obs._reported_failures
    broadcast_cb.assert_awaited_once()

    # failure_callback raising must not crash _process_stage or set _active_watches
    boom_cb = AsyncMock(side_effect=RuntimeError("aligner down"))
    obs_err = _make_observer(failure_cb=boom_cb)
    await obs_err._process_stage(_make_verif_stage(verif_id="uuid-boom", verif_phase="Failed"))
    assert "v4-22/verify-release-chart" not in obs_err._active_watches

    # Same for promotion failure callback exception
    boom_promo_cb = AsyncMock(side_effect=RuntimeError("boom"))
    obs_err2 = _make_observer(failure_cb=boom_promo_cb)
    await obs_err2._process_stage(_make_stage(promo_name="p-boom", phase="Errored"))
    assert "kargo-test-project/test-stage" not in obs_err2._active_watches


# =========================================================================
# T-9: get_stage_status() <-> Aligner.handle_failed_promotion 1:1 key contract & _extract_failed_step
# =========================================================================

@pytest.mark.asyncio
async def test_t9_get_stage_status_matches_aligner_signature_and_failed_step_phases():
    """T-9: Non-_ keys + 'service' strictly match Aligner.handle_failed_promotion params; _extract_failed_step handles Failed."""
    import inspect
    from src.agents.aligner import Aligner

    expected_params = set(inspect.signature(Aligner.handle_failed_promotion).parameters) - {"self"}

    obs = _make_observer()
    obs._k8s_available = True
    obs._custom_api = MagicMock()

    # 1. Promotion failure stage
    promo_cr = _make_stage(namespace="proj", name="prod", phase="Errored")
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=promo_cr)
        res_promo = await obs.get_stage_status("proj", "prod")
    non_private_promo = {k for k in res_promo if not k.startswith("_")} | {"service"}
    assert non_private_promo == expected_params
    assert res_promo["failure_type"] == "promotion"
    assert res_promo["_promotion_phase"] == "Errored"

    # 2. Verification failure stage
    verif_cr = _make_verif_stage(verif_phase="Failed")
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=verif_cr)
        res_verif = await obs.get_stage_status("v4-22", "verify-release-chart")
    non_private_verif = {k for k in res_verif if not k.startswith("_")} | {"service"}
    assert non_private_verif == expected_params
    assert res_verif["failure_type"] == "verification"
    assert res_verif["phase"] == "Failed"
    assert res_verif["_promotion_phase"] == "Succeeded"
    assert res_verif["_verification"]["id"] == "1605daa6-92cb-4050-addd-89465a90f331"

    # 3. Direct promotion_id branch
    direct_promo = {"spec": {"freight": {"name": "f1"}}, "status": {"phase": "Failed", "message": "boom"}}
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=direct_promo)
        res_direct = await obs.get_stage_status("proj", "prod", promotion_id="p-1")
    non_private_direct = {k for k in res_direct if not k.startswith("_")} | {"service"}
    assert non_private_direct == expected_params
    assert res_direct["failure_type"] == "promotion"

    # 4. _extract_failed_step matches both Errored and Failed
    assert KargoObserver._extract_failed_step(
        {"stepExecutionMetadata": [{"alias": "step-a", "status": "Failed"}]}
    ) == "step-a"
    assert KargoObserver._extract_failed_step(
        {"stepExecutionMetadata": [{"alias": "step-b", "status": "Errored"}]}
    ) == "step-b"


# =========================================================================
# T-10 (observer part): extract_kargo_state_key & poll_kargo_stage_status parity
# =========================================================================

@pytest.mark.asyncio
async def test_t10_poll_and_get_stage_status_share_projection_and_state_key():
    """T-10: extract_kargo_state_key preserves 2 keys without verif; adds 2 keys with verif; poll matches get_stage_status."""
    ps = {"phase": "Succeeded", "stepExecutionMetadata": []}
    assert KargoObserver.extract_kargo_state_key(ps) == {"phase": "Succeeded", "failed_step": ""}
    assert KargoObserver.extract_kargo_state_key(ps, verification=None) == {"phase": "Succeeded", "failed_step": ""}
    assert KargoObserver.extract_kargo_state_key(ps, verification={}) == {"phase": "Succeeded", "failed_step": ""}
    assert KargoObserver.extract_kargo_state_key(
        ps, verification={"phase": "Failed", "id": "uuid-9"},
    ) == {"phase": "Succeeded", "failed_step": "", "verification_phase": "Failed", "verification_id": "uuid-9"}

    obs = _make_observer()
    obs._k8s_available = True
    obs._custom_api = MagicMock()

    # Active verification on Succeeded promotion: get_stage_status and poll_kargo_stage_status produce identical state_key
    stage_cr = _make_verif_stage(verif_phase="Running", verif_id="uuid-run")
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=stage_cr)
        status_res = await obs.get_stage_status("v4-22", "verify-release-chart")
        poll_res = await obs.poll_kargo_stage_status("v4-22", "verify-release-chart")
    reg_key = KargoObserver.extract_kargo_state_key(
        status_res["_promo_status"], verification=status_res["_verification"] or None,
    )
    assert reg_key == poll_res == {
        "phase": "Succeeded", "failed_step": "",
        "verification_phase": "Running", "verification_id": "uuid-run",
    }

    # Active currentPromotion drops stale prior verification in both get_stage_status and poll_kargo_stage_status
    stage_cr["status"]["currentPromotion"] = {"name": "promo-live", "status": {"phase": "Running"}}
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value=stage_cr)
        status_cur = await obs.get_stage_status("v4-22", "verify-release-chart")
        poll_cur = await obs.poll_kargo_stage_status("v4-22", "verify-release-chart")
    assert status_cur["_verification"] == {}
    assert poll_cur == {"phase": "Running", "failed_step": ""}


# =========================================================================
# T-11: Null/malformed CRD JSON resilience
# =========================================================================

@pytest.mark.asyncio
async def test_t11_null_and_malformed_crd_json_resilience():
    """T-11: Null/malformed metadata, status, lastPromotion, message, analysisRun, freight never raise."""
    from src.observers.kargo_helpers import (
        _parse_ts,
        build_verification_dedup_key,
        extract_latest_verification,
    )

    failure_cb = AsyncMock()
    obs = _make_observer(failure_cb=failure_cb)

    malformed_stages = [
        None,
        {},
        {"metadata": None, "status": None},
        {"metadata": {"namespace": "", "name": "s1"}, "status": {}},
        {"metadata": {"namespace": "ns", "name": None}, "status": {}},
        {"metadata": {"namespace": "ns", "name": "s1"}, "status": {"lastPromotion": None}},
        {
            "metadata": {"namespace": "ns", "name": "s2"},
            "status": {
                "lastPromotion": {
                    "name": "p1",
                    "freight": "string-ref",
                    "status": {
                        "phase": "Errored",
                        "message": None,
                        "startedAt": None,
                        "finishedAt": None,
                        "stepExecutionMetadata": [None, {"alias": None, "status": "Errored"}],
                        "state": None,
                    },
                },
            },
        },
        {
            "metadata": {"namespace": "ns", "name": "s3"},
            "status": {
                "lastPromotion": {"name": "p2", "status": {"phase": "Succeeded"}},
                "freightHistory": [
                    {
                        "id": None,
                        "verificationHistory": [
                            {
                                "id": None,
                                "phase": "Failed",
                                "message": None,
                                "startTime": None,
                                "finishTime": None,
                                "analysisRun": "bad-type",
                            },
                        ],
                    },
                ],
            },
        },
        {
            "metadata": {"namespace": "ns", "name": "s4"},
            "status": {
                "lastPromotion": {"name": "p3", "status": {"phase": "Succeeded"}},
                "freightHistory": [
                    {
                        "id": "fh-1",
                        "verificationHistory": [
                            {"id": "v-null-ar", "phase": "Error", "message": None, "analysisRun": None},
                        ],
                    },
                ],
            },
        },
    ]

    for stage in malformed_stages:
        await obs._process_stage(stage)

    # s2 (promotion), s3 (verification without id -> fallback key), s4 (verification with analysisRun=None) all fired safely
    assert failure_cb.call_count == 3
    assert obs._failure_details["ns/s2"]["failed_step"] == "unknown"
    assert obs._failure_details["ns/s2"]["message"] == ""
    assert obs._failure_details["ns/s3"]["analysis_run"] == ""
    assert obs._reported_failures["ns/s3"] == "verification:p2:Failed"
    assert obs._failure_details["ns/s4"]["analysis_run"] == ""

    # Pure helper edge cases
    assert _parse_ts("") is None
    assert _parse_ts("not-a-date") is None
    assert _parse_ts("2026-07-09T12:00:00") is not None  # naive normalized to UTC
    assert extract_latest_verification(None) == {}  # type: ignore[arg-type]
    assert build_verification_dedup_key({"phase": "Failed"}, "p-x") == "verification:p-x:Failed"
    assert KargoObserver._extract_failed_step(None) == ""  # type: ignore[arg-type]
    assert KargoObserver._extract_mr_url(None) == ""  # type: ignore[arg-type]

@pytest.mark.asyncio
async def test_t21_kargo_deleted_event_clears_state():
    from src.observers.kargo import KargoObserver
    from unittest.mock import MagicMock, AsyncMock
    obs = KargoObserver(blackboard=MagicMock())
    obs.broadcast_callback = AsyncMock()
    obs._reported_failures["ns/name"] = "dedup"
    obs._failure_details["ns/name"] = {"phase": "Failed"}
    obs._active_watches["ns/name"] = 123
    
    await obs._handle_deleted_stage({"metadata": {"namespace": "ns", "name": "name"}})
    assert "ns/name" not in obs._reported_failures
    assert "ns/name" not in obs._failure_details
    assert "ns/name" not in obs._active_watches
    obs.broadcast_callback.assert_awaited_once()

@pytest.mark.asyncio
async def test_t21_initial_sync_restores_state_on_exception():
    from src.observers.kargo import KargoObserver
    from unittest.mock import MagicMock
    obs = KargoObserver(blackboard=MagicMock())
    obs._reported_failures["old"] = "old"
    obs._failure_details["old"] = {}
    obs._active_watches["old"] = 123
    obs._k8s_available = True
    obs._custom_api = MagicMock()
    obs._custom_api.list_cluster_custom_object = MagicMock(side_effect=Exception("boom"))
    
    await obs._initial_sync()
    
    assert "old" in obs._reported_failures
    assert "old" in obs._active_watches

@pytest.mark.asyncio
async def test_t21_watch_loop_invokes_stop_in_finally():
    from src.observers.kargo import KargoObserver
    from unittest.mock import MagicMock, patch
    import asyncio
    obs = KargoObserver(blackboard=MagicMock())
    obs._k8s_available = True
    obs._running = True
    mock_watch = MagicMock()
    obs._current_watch = mock_watch
    
    async def mock_run_in_executor(*args, **kwargs):
        raise asyncio.CancelledError()
        
    with patch("kubernetes.watch.Watch", return_value=mock_watch):
        with patch("asyncio.get_running_loop") as mock_loop:
            mock_loop_instance = MagicMock()
            mock_loop_instance.run_in_executor = mock_run_in_executor
            mock_loop.return_value = mock_loop_instance
            await obs._watch_loop()
        
    mock_watch.stop.assert_called_once()
    assert obs._current_watch is None


@pytest.mark.asyncio
async def test_t21_failure_callback_exception_pops_reported_failures():
    from src.observers.kargo import KargoObserver
    from unittest.mock import MagicMock, AsyncMock
    obs = KargoObserver(blackboard=MagicMock())
    obs.failure_callback = AsyncMock(side_effect=Exception("cb_boom"))
    obs._reported_failures["ns/name"] = "dedup"
    obs._failure_details["ns/name"] = {"phase": "Failed", "stage": "stg", "project": "prj", "promotion": "p", "freight": "f", "message": "m", "failed_step": "s", "mr_url": "u"}
    
    try:
        await obs._record_failure(stage_key="ns/name", dedup_key="dedup", details=obs._failure_details["ns/name"], suppress_callbacks=False)
    except Exception:
        pass
    assert "ns/name" not in obs._reported_failures
    assert "ns/name" in obs._failure_details

def test_t21_is_verification_stale_freight_fallback():
    from src.observers import kargo_helpers
    promo = {"status": {"phase": "Succeeded", "freightCollection": {}}, "freight": {"name": "p_name"}}
    verif = {"freight_id": "v_name"}
    assert kargo_helpers.is_verification_stale(promo, verif)

def test_t21_parse_ts_rejects_long_string():
    from src.observers import kargo_helpers
    assert kargo_helpers._parse_ts("a" * 65) is None

def test_t21_resolve_stage_freight_prefers_verif_id():
    from src.observers import kargo_helpers
    assert kargo_helpers.resolve_stage_freight({"freightSummary": "prose"}, {}, {"freight_id": "v_id"}) == "v_id"

def test_t21_build_verification_dedup_key_fallback():
    from src.observers import kargo_helpers
    assert kargo_helpers.build_verification_dedup_key({"start_time": "st"}, "promo") == "verification:promo:st"
