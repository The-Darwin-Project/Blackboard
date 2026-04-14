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
