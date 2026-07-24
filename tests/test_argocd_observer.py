# tests/test_argocd_observer.py
# @ai-rules:
# 1. [Constraint]: No real K8s API calls. All K8s interactions mocked.
# 2. [Pattern]: Tests exercise _process_application/_process_deleted directly with dict fixtures.
# 3. [Pattern]: Async tests use pytest-asyncio. Callbacks and blackboard are AsyncMock.
"""Unit tests for ArgoCDObserver -- N:1 Application-to-service extraction, health/sync callbacks."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.observers.argocd import ArgoCDObserver


def _deployment_resource(
    name: str = "ai-insights",
    namespace: str = "cnv-fbc-konflux",
    health_status: str = "Healthy",
    sync_status: str = "Synced",
) -> dict:
    return {
        "version": "v1",
        "kind": "Deployment",
        "namespace": namespace,
        "name": name,
        "status": sync_status,
        "health": {"status": health_status},
    }


def _make_application(
    namespace: str = "openshift-gitops",
    name: str = "release-app-services",
    app_health: str = "Healthy",
    app_sync: str = "Synced",
    resources: list[dict] | None = None,
    automated: bool | dict | None = None,
    operation_phase: str = "Succeeded",
    resource_version: str = "999",
) -> dict:
    spec: dict = {"source": {}}
    if automated is not None:
        spec["syncPolicy"] = {"automated": automated if isinstance(automated, dict) else {}}
    doc: dict = {
        "metadata": {"namespace": namespace, "name": name, "resourceVersion": resource_version},
        "spec": spec,
        "status": {
            "health": {"status": app_health},
            "sync": {"status": app_sync},
            "resources": resources if resources is not None else [_deployment_resource()],
            "operationState": {
                "phase": operation_phase,
                "startedAt": "2026-07-24T10:00:00Z",
                "finishedAt": "2026-07-24T10:01:00Z",
                "syncResult": {"revision": "abc123"},
            },
            "history": [
                {"revision": "rev1", "deployedAt": "2026-07-23T10:00:00Z"},
                {"revision": "rev2", "deployedAt": "2026-07-24T10:00:00Z"},
            ],
        },
    }
    return doc


def _make_observer(health_cb=None, sync_cb=None) -> ArgoCDObserver:
    bb = AsyncMock()
    obs = ArgoCDObserver(
        blackboard=bb,
        health_change_callback=health_cb or AsyncMock(),
        sync_change_callback=sync_cb or AsyncMock(),
    )
    return obs


# =========================================================================
# Test 1: Null/empty status guard
# =========================================================================

@pytest.mark.asyncio
async def test_null_health_guard_skips_processing():
    """Application with no status.health is skipped (freshly-created / ApplicationSet child)."""
    health_cb = AsyncMock()
    obs = _make_observer(health_cb=health_cb)
    app = {"metadata": {"namespace": "openshift-gitops", "name": "new-app"}, "status": {}}

    await obs._process_application(app)

    health_cb.assert_not_called()
    assert "openshift-gitops/new-app" not in obs._application_states


@pytest.mark.asyncio
async def test_null_sync_guard_skips_processing():
    """Application with health but no sync status is skipped."""
    app = _make_application()
    app["status"]["sync"] = {}

    obs = _make_observer()
    await obs._process_application(app)

    assert "openshift-gitops/release-app-services" not in obs._application_states


@pytest.mark.asyncio
async def test_missing_app_name_skipped():
    """Application with no metadata.name is skipped without raising."""
    obs = _make_observer()
    await obs._process_application({"metadata": {}, "status": {"health": {"status": "Healthy"}, "sync": {"status": "Synced"}}})
    assert obs._application_states == {}


# =========================================================================
# Test 2: Initial extraction registers services and writes ArgoCD status
# =========================================================================

@pytest.mark.asyncio
async def test_initial_extraction_registers_service():
    obs = _make_observer()
    app = _make_application(resources=[_deployment_resource(name="ai-insights")])

    await obs._process_application(app, suppress_callbacks=True)

    obs.blackboard.add_service.assert_called_once_with("ai-insights")
    obs.blackboard.update_service_argocd_status.assert_called_once()
    kwargs = obs.blackboard.update_service_argocd_status.call_args.kwargs
    assert kwargs["name"] == "ai-insights"
    assert kwargs["health_status"] == "Healthy"
    assert kwargs["sync_status"] == "Synced"
    assert kwargs["argocd_app"] == "openshift-gitops/release-app-services"
    assert kwargs["namespace"] == "cnv-fbc-konflux"
    assert len(kwargs["last_operations"]) == 3  # 1 current + 2 history


@pytest.mark.asyncio
async def test_initial_sync_suppresses_health_callback():
    """suppress_callbacks=True records state but does NOT fire health_change_callback."""
    health_cb = AsyncMock()
    obs = _make_observer(health_cb=health_cb)
    app = _make_application()

    await obs._process_application(app, suppress_callbacks=True)

    health_cb.assert_not_called()
    assert obs._application_states["openshift-gitops/release-app-services"]["resource_health"] == {
        "ai-insights": "Healthy",
    }


# =========================================================================
# Test 3: Health transition fires per-service callback
# =========================================================================

@pytest.mark.asyncio
async def test_health_transition_fires_callback():
    health_cb = AsyncMock()
    obs = _make_observer(health_cb=health_cb)

    healthy_app = _make_application(resources=[_deployment_resource(health_status="Healthy")], resource_version="1")
    await obs._process_application(healthy_app, suppress_callbacks=True)

    degraded_app = _make_application(
        app_health="Degraded",
        resources=[_deployment_resource(health_status="Degraded")],
        resource_version="2",
    )
    await obs._process_application(degraded_app)

    health_cb.assert_called_once_with(
        "ai-insights", "Healthy", "Degraded",
        {"argocd_app": "openshift-gitops/release-app-services", "namespace": "cnv-fbc-konflux"},
    )


@pytest.mark.asyncio
async def test_new_service_first_sighting_does_not_fire_callback():
    """A brand-new Deployment appearing in an already-tracked app does not fire on first sight."""
    health_cb = AsyncMock()
    obs = _make_observer(health_cb=health_cb)

    app_v1 = _make_application(resources=[_deployment_resource(name="svc-a")], resource_version="1")
    await obs._process_application(app_v1, suppress_callbacks=True)

    app_v2 = _make_application(
        resources=[_deployment_resource(name="svc-a"), _deployment_resource(name="svc-b")],
        resource_version="2",
    )
    await obs._process_application(app_v2)

    health_cb.assert_not_called()


# =========================================================================
# Test 4: Fingerprint skip -- unchanged resources skip full extraction
# =========================================================================

@pytest.mark.asyncio
async def test_fingerprint_unchanged_skips_extraction():
    obs = _make_observer()
    app = _make_application(resource_version="1")
    await obs._process_application(app, suppress_callbacks=True)
    obs.blackboard.update_service_argocd_status.reset_mock()
    obs.blackboard.add_service.reset_mock()

    same_app = _make_application(resource_version="2")  # only resourceVersion differs
    await obs._process_application(same_app)

    obs.blackboard.update_service_argocd_status.assert_not_called()
    obs.blackboard.add_service.assert_not_called()
    # last_seen is still touched for known services
    assert obs.blackboard.redis.hset.await_count == 1
    call_args = obs.blackboard.redis.hset.call_args
    assert call_args.args[0] == "darwin:service:ai-insights"
    assert call_args.args[1] == "last_seen"


@pytest.mark.asyncio
async def test_fingerprint_changed_triggers_extraction():
    obs = _make_observer()
    app = _make_application(resources=[_deployment_resource(health_status="Healthy")], resource_version="1")
    await obs._process_application(app, suppress_callbacks=True)
    obs.blackboard.update_service_argocd_status.reset_mock()

    changed_app = _make_application(
        app_health="Degraded",
        resources=[_deployment_resource(health_status="Degraded")],
        resource_version="2",
    )
    await obs._process_application(changed_app)

    obs.blackboard.update_service_argocd_status.assert_called_once()


# =========================================================================
# Test 5: N:1 sync-once -- sync callback fires once per Application, not per service
# =========================================================================

@pytest.mark.asyncio
async def test_sync_drift_fires_once_for_multi_service_app():
    sync_cb = AsyncMock()
    obs = _make_observer(sync_cb=sync_cb)

    synced_app = _make_application(
        app_sync="Synced",
        resources=[_deployment_resource(name=f"svc-{i}") for i in range(5)],
        automated={},
        resource_version="1",
    )
    await obs._process_application(synced_app, suppress_callbacks=True)

    out_of_sync_app = _make_application(
        app_sync="OutOfSync",
        resources=[_deployment_resource(name=f"svc-{i}", sync_status="OutOfSync") for i in range(5)],
        automated={},
        resource_version="2",
    )
    await obs._process_application(out_of_sync_app)

    sync_cb.assert_called_once_with(
        "openshift-gitops/release-app-services", "Synced", "OutOfSync",
    )


@pytest.mark.asyncio
async def test_sync_callback_gated_on_automated_key():
    """No spec.syncPolicy.automated key -- sync_change_callback never fires even on drift."""
    sync_cb = AsyncMock()
    obs = _make_observer(sync_cb=sync_cb)

    app = _make_application(app_sync="Synced", automated=None, resource_version="1")
    await obs._process_application(app, suppress_callbacks=True)

    drifted = _make_application(app_sync="OutOfSync", automated=None, resource_version="2")
    await obs._process_application(drifted)

    sync_cb.assert_not_called()


@pytest.mark.asyncio
async def test_sync_callback_fires_on_every_tick_while_automated():
    """Repeated MODIFIED events with automated=True re-invoke the callback each time
    (Aligner owns the dwell-time debounce, not the observer)."""
    sync_cb = AsyncMock()
    obs = _make_observer(sync_cb=sync_cb)

    app_v1 = _make_application(app_sync="OutOfSync", automated={}, resource_version="1")
    await obs._process_application(app_v1, suppress_callbacks=True)

    app_v2 = _make_application(app_sync="OutOfSync", automated={}, resource_version="2")
    await obs._process_application(app_v2)
    app_v3 = _make_application(app_sync="OutOfSync", automated={}, resource_version="3")
    await obs._process_application(app_v3)

    assert sync_cb.call_count == 2


# =========================================================================
# Test 6: DELETED removes services
# =========================================================================

@pytest.mark.asyncio
async def test_deleted_removes_tracked_services():
    obs = _make_observer()
    app = _make_application(resources=[_deployment_resource(name="svc-a"), _deployment_resource(name="svc-b")])
    await obs._process_application(app, suppress_callbacks=True)

    await obs._process_deleted(app)

    assert obs.blackboard.remove_service.await_count == 2
    obs.blackboard.remove_service.assert_any_call("svc-a")
    obs.blackboard.remove_service.assert_any_call("svc-b")
    assert "openshift-gitops/release-app-services" not in obs._application_states


@pytest.mark.asyncio
async def test_deleted_unknown_app_is_noop():
    obs = _make_observer()
    app = _make_application(name="never-seen")
    await obs._process_deleted(app)
    obs.blackboard.remove_service.assert_not_called()


# =========================================================================
# Test 7: Name mapping
# =========================================================================

@pytest.mark.asyncio
async def test_name_mapping_translates_resource_name(monkeypatch):
    import json as _json
    monkeypatch.setenv("ARGOCD_NAME_MAPPING", _json.dumps({"raw-deploy-name": "darwin-service-name"}))

    obs = ArgoCDObserver(blackboard=AsyncMock())
    app = _make_application(resources=[_deployment_resource(name="raw-deploy-name")])

    await obs._process_application(app, suppress_callbacks=True)

    obs.blackboard.add_service.assert_called_once_with("darwin-service-name")


# =========================================================================
# Test 8: Operation history extraction
# =========================================================================

def test_extract_last_operations_current_and_history():
    status = {
        "operationState": {
            "phase": "Succeeded",
            "startedAt": "t1",
            "finishedAt": "t2",
            "syncResult": {"revision": "rev-current"},
        },
        "history": [
            {"revision": "r1", "deployedAt": "d1"},
            {"revision": "r2", "deployedAt": "d2"},
            {"revision": "r3", "deployedAt": "d3"},
            {"revision": "r4", "deployedAt": "d4"},
            {"revision": "r5", "deployedAt": "d5"},
            {"revision": "r6", "deployedAt": "d6"},
        ],
    }
    ops = ArgoCDObserver._extract_last_operations(status)
    assert ops[0]["type"] == "current"
    assert ops[0]["revision"] == "rev-current"
    # Only last 5 history entries kept
    assert len(ops) == 6
    assert ops[1]["revision"] == "r2"
    assert ops[-1]["revision"] == "r6"


def test_extract_last_operations_empty_status():
    assert ArgoCDObserver._extract_last_operations({}) == []


# =========================================================================
# Test 9: Non-Deployment resources are ignored
# =========================================================================

@pytest.mark.asyncio
async def test_non_deployment_resources_ignored():
    obs = _make_observer()
    resources = [
        _deployment_resource(name="ai-insights"),
        {"version": "v1", "kind": "Service", "namespace": "cnv-fbc-konflux", "name": "ai-insights-svc", "status": "Synced", "health": {"status": "Healthy"}},
        {"version": "v1", "kind": "ConfigMap", "namespace": "cnv-fbc-konflux", "name": "ai-insights-config", "status": "Synced"},
    ]
    app = _make_application(resources=resources)

    await obs._process_application(app, suppress_callbacks=True)

    obs.blackboard.add_service.assert_called_once_with("ai-insights")
