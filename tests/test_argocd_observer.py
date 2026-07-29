# tests/test_argocd_observer.py
# @ai-rules:
# 1. [Constraint]: No real K8s API calls. All K8s interactions mocked.
# 2. [Pattern]: Tests exercise _process_application/_process_deleted directly with dict fixtures.
# 3. [Pattern]: Async tests use pytest-asyncio. Callbacks and blackboard are AsyncMock.
# 4. [Pattern]: Observer uses anomaly_callback(target, anomaly_type, metadata) and
#    recovery_callback(target, message, scope) — NOT health_change_callback/sync_change_callback.
"""Unit tests for ArgoCDObserver -- N:1 Application-to-service extraction, anomaly/recovery callbacks."""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from src.observers.argocd import ArgoCDObserver


def _deployment_resource(
    name: str = "my-service",
    namespace: str = "test-namespace",
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
    namespace: str = "argocd",
    name: str = "test-app",
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


def _make_observer(anomaly_cb=None, recovery_cb=None) -> ArgoCDObserver:
    bb = AsyncMock()
    obs = ArgoCDObserver(
        blackboard=bb,
        anomaly_callback=anomaly_cb or AsyncMock(),
        recovery_callback=recovery_cb or AsyncMock(),
    )
    return obs


# =========================================================================
# Test 1: Null/empty status guard
# =========================================================================

@pytest.mark.asyncio
async def test_null_health_guard_skips_processing():
    """Application with no status.health is skipped (freshly-created / ApplicationSet child)."""
    anomaly_cb = AsyncMock()
    obs = _make_observer(anomaly_cb=anomaly_cb)
    app = {"metadata": {"namespace": "argocd", "name": "new-app"}, "status": {}}

    await obs._process_application(app)

    anomaly_cb.assert_not_called()
    assert "argocd/new-app" not in obs._application_states


@pytest.mark.asyncio
async def test_null_sync_guard_skips_processing():
    """Application with health but no sync status is skipped."""
    app = _make_application()
    app["status"]["sync"] = {}

    obs = _make_observer()
    await obs._process_application(app)

    assert "argocd/test-app" not in obs._application_states


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
    app = _make_application(resources=[_deployment_resource(name="my-service")])

    await obs._process_application(app, suppress_callbacks=True)

    obs.blackboard.add_service.assert_called_once_with("test-namespace/my-service")
    obs.blackboard.update_service_argocd_status.assert_called_once()
    kwargs = obs.blackboard.update_service_argocd_status.call_args.kwargs
    assert kwargs["name"] == "test-namespace/my-service"
    assert kwargs["health_status"] == "Healthy"
    assert kwargs["sync_status"] == "Synced"
    assert kwargs["argocd_app"] == "argocd/test-app"
    assert kwargs["namespace"] == "test-namespace"
    assert len(kwargs["last_operations"]) == 3  # 1 current + 2 history


@pytest.mark.asyncio
async def test_initial_sync_suppresses_anomaly_callback():
    """suppress_callbacks=True records state but does NOT fire anomaly_callback."""
    anomaly_cb = AsyncMock()
    obs = _make_observer(anomaly_cb=anomaly_cb)
    app = _make_application()

    await obs._process_application(app, suppress_callbacks=True)

    anomaly_cb.assert_not_called()
    assert obs._application_states["argocd/test-app"]["resource_health"] == {
        "test-namespace/my-service": "Healthy",
    }


# =========================================================================
# Test 3: Health transition fires anomaly_callback (T-9)
# =========================================================================

@pytest.mark.asyncio
async def test_health_transition_fires_anomaly_callback():
    """T-9: Healthy→Degraded fires anomaly_callback with subject_type='service'."""
    anomaly_cb = AsyncMock()
    obs = _make_observer(anomaly_cb=anomaly_cb)

    healthy_app = _make_application(resources=[_deployment_resource(health_status="Healthy")], resource_version="1")
    await obs._process_application(healthy_app, suppress_callbacks=True)

    degraded_app = _make_application(
        app_health="Degraded",
        resources=[_deployment_resource(health_status="Degraded")],
        resource_version="2",
    )
    await obs._process_application(degraded_app)

    anomaly_cb.assert_called_once()
    args = anomaly_cb.call_args
    assert args[0][0] == "test-namespace/my-service"  # target
    assert args[0][1] == "argocd_health_degraded"  # anomaly_type
    metadata = args[0][2]
    assert metadata["subject_type"] == "service"
    assert metadata["severity"] == "critical"
    assert metadata["argocd_app"] == "argocd/test-app"


@pytest.mark.asyncio
async def test_health_recovery_fires_recovery_callback():
    """T-10: Degraded→Healthy fires recovery_callback with scope='health'."""
    recovery_cb = AsyncMock()
    obs = _make_observer(recovery_cb=recovery_cb)

    degraded_app = _make_application(
        app_health="Degraded",
        resources=[_deployment_resource(health_status="Degraded")],
        resource_version="1",
    )
    await obs._process_application(degraded_app, suppress_callbacks=True)

    healthy_app = _make_application(
        app_health="Healthy",
        resources=[_deployment_resource(health_status="Healthy")],
        resource_version="2",
    )
    await obs._process_application(healthy_app)

    recovery_cb.assert_called_once()
    args = recovery_cb.call_args
    assert args[0][0] == "test-namespace/my-service"  # target
    assert "recovered" in args[0][1].lower() or "Healthy" in args[0][1]  # message
    assert args[0][2] == "health"  # scope


@pytest.mark.asyncio
async def test_new_service_first_sighting_does_not_fire_callback():
    """A brand-new Deployment appearing in an already-tracked app does not fire on first sight."""
    anomaly_cb = AsyncMock()
    obs = _make_observer(anomaly_cb=anomaly_cb)

    app_v1 = _make_application(resources=[_deployment_resource(name="svc-a")], resource_version="1")
    await obs._process_application(app_v1, suppress_callbacks=True)

    app_v2 = _make_application(
        resources=[_deployment_resource(name="svc-a"), _deployment_resource(name="svc-b")],
        resource_version="2",
    )
    await obs._process_application(app_v2)

    anomaly_cb.assert_not_called()


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
    # last_seen touch + app-level sync persistence = 2 hset calls
    assert obs.blackboard.redis.hset.await_count == 2
    hset_calls = obs.blackboard.redis.hset.call_args_list
    hset_keys = [c.args[0] for c in hset_calls]
    assert "darwin:service:test-namespace/my-service" in hset_keys
    assert any(k.startswith("darwin:argocd_app_sync:") for k in hset_keys)


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
# Test 5: N:1 sync-once -- anomaly_callback fires once per Application, not per service (T-11)
# =========================================================================

@pytest.mark.asyncio
async def test_sync_drift_fires_anomaly_callback_for_multi_service_app():
    """T-11: OutOfSync fires anomaly_callback once with subject_type='system'."""
    anomaly_cb = AsyncMock()
    obs = _make_observer(anomaly_cb=anomaly_cb)

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

    anomaly_cb.assert_called_once()
    args = anomaly_cb.call_args
    assert args[0][0] == "argocd/test-app"  # target = app_key
    assert args[0][1] == "argocd_sync_drift"  # anomaly_type
    metadata = args[0][2]
    assert metadata["subject_type"] == "system"
    assert metadata["severity"] == "warning"


@pytest.mark.asyncio
async def test_sync_callback_gated_on_automated_key():
    """No spec.syncPolicy.automated key -- anomaly_callback never fires even on drift."""
    anomaly_cb = AsyncMock()
    obs = _make_observer(anomaly_cb=anomaly_cb)

    app = _make_application(app_sync="Synced", automated=None, resource_version="1")
    await obs._process_application(app, suppress_callbacks=True)

    drifted = _make_application(app_sync="OutOfSync", automated=None, resource_version="2")
    await obs._process_application(drifted)

    anomaly_cb.assert_not_called()


@pytest.mark.asyncio
async def test_sync_anomaly_fires_on_every_tick_while_out_of_sync():
    """anomaly_callback fires every tick while OutOfSync (level-triggered).
    ZADD NX at the Redis layer prevents dwell-timer reset — the observer
    must re-supply so that committed entries can be re-armed."""
    anomaly_cb = AsyncMock()
    obs = _make_observer(anomaly_cb=anomaly_cb)

    app_v1 = _make_application(app_sync="Synced", automated={}, resource_version="1")
    await obs._process_application(app_v1, suppress_callbacks=True)

    app_v2 = _make_application(app_sync="OutOfSync", automated={}, resource_version="2")
    await obs._process_application(app_v2)
    assert anomaly_cb.call_count == 1

    app_v3 = _make_application(app_sync="OutOfSync", automated={}, resource_version="3")
    await obs._process_application(app_v3)
    assert anomaly_cb.call_count == 2  # re-fires — level-triggered, not edge-triggered


@pytest.mark.asyncio
async def test_sync_recovery_fires_recovery_callback():
    """Synced after OutOfSync → recovery_callback with scope='sync'."""
    recovery_cb = AsyncMock()
    anomaly_cb = AsyncMock()
    obs = _make_observer(anomaly_cb=anomaly_cb, recovery_cb=recovery_cb)

    oos_app = _make_application(app_sync="OutOfSync", automated={}, resource_version="1")
    await obs._process_application(oos_app, suppress_callbacks=True)

    synced_app = _make_application(app_sync="Synced", automated={}, resource_version="2")
    await obs._process_application(synced_app)

    recovery_cb.assert_called_once()
    args = recovery_cb.call_args
    assert args[0][0] == "argocd/test-app"  # target
    assert args[0][2] == "sync"  # scope


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
    obs.blackboard.remove_service.assert_any_call("test-namespace/svc-a")
    obs.blackboard.remove_service.assert_any_call("test-namespace/svc-b")
    assert "argocd/test-app" not in obs._application_states


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
    monkeypatch.setenv("ARGOCD_NAME_MAPPING", _json.dumps({"raw-deploy-name": "mapped-name"}))

    obs = ArgoCDObserver(blackboard=AsyncMock())
    app = _make_application(resources=[_deployment_resource(name="raw-deploy-name")])

    await obs._process_application(app, suppress_callbacks=True)

    obs.blackboard.add_service.assert_called_once_with("test-namespace/mapped-name")


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
# Test 10: GitOps repo/path + version extraction (Step 6)
# =========================================================================

@pytest.mark.asyncio
async def test_extracts_gitops_source_and_version():
    obs = _make_observer()
    app = _make_application(resources=[_deployment_resource(name="my-service")])
    app["spec"]["source"] = {"repoURL": "https://github.com/org/repo.git", "path": "helm"}
    app["status"]["summary"] = {"images": ["quay.io/org/image:1784816083-29211b5"]}

    await obs._process_application(app, suppress_callbacks=True)

    obs.blackboard.update_service_discovery.assert_called_once_with(
        name="test-namespace/my-service",
        version="1784816083-29211b5",
        gitops_repo_url="https://github.com/org/repo.git",
        gitops_config_path="helm",
    )


@pytest.mark.asyncio
async def test_gitops_source_missing_defaults_to_unknown_version():
    """No spec.source or status.summary -- version falls back to 'unknown', repo/path stay None."""
    obs = _make_observer()
    app = _make_application(resources=[_deployment_resource(name="my-service")])

    await obs._process_application(app, suppress_callbacks=True)

    obs.blackboard.update_service_discovery.assert_called_once_with(
        name="test-namespace/my-service",
        version="unknown",
        gitops_repo_url=None,
        gitops_config_path=None,
    )


@pytest.mark.asyncio
async def test_gitops_fields_skipped_when_fingerprint_unchanged():
    obs = _make_observer()
    app = _make_application(resource_version="1")
    await obs._process_application(app, suppress_callbacks=True)
    obs.blackboard.update_service_discovery.reset_mock()

    same_app = _make_application(resource_version="2")  # only resourceVersion differs
    await obs._process_application(same_app)

    obs.blackboard.update_service_discovery.assert_not_called()


@pytest.mark.parametrize(
    "images,expected",
    [
        ([], "unknown"),
        (["quay.io/org/image:1784816083-29211b5"], "1784816083-29211b5"),
        (["registry:5000/org/image:v1.2.3"], "v1.2.3"),
        (["quay.io/org/image@sha256:abcdef123456"], "sha256:abcdef123456"),
        (["quay.io/org/image"], "quay.io/org/image"),
    ],
)
def test_first_image_tag(images, expected):
    assert ArgoCDObserver._first_image_tag(images) == expected


# =========================================================================
# Test 9: Non-Deployment resources are ignored
# =========================================================================

@pytest.mark.asyncio
async def test_non_deployment_resources_ignored():
    obs = _make_observer()
    resources = [
        _deployment_resource(name="my-service"),
        {"version": "v1", "kind": "Service", "namespace": "test-namespace", "name": "other-svc", "status": "Synced", "health": {"status": "Healthy"}},
        {"version": "v1", "kind": "ConfigMap", "namespace": "test-namespace", "name": "other-config", "status": "Synced"},
    ]
    app = _make_application(resources=resources)

    await obs._process_application(app, suppress_callbacks=True)

    obs.blackboard.add_service.assert_called_once_with("test-namespace/my-service")


# =========================================================================
# Test 10: Zero-workload app registered as config-only
# =========================================================================

@pytest.mark.asyncio
async def test_zero_workload_app_registered_to_redis():
    """Application with 0 workloads is registered in darwin:argocd_apps SET."""
    obs = _make_observer()
    resources = [
        {"version": "v1", "kind": "ConfigMap", "namespace": "argocd", "name": "my-config", "status": "Synced"},
    ]
    app = _make_application(name="config-app", resources=resources)

    await obs._process_application(app, suppress_callbacks=True)

    obs.blackboard.redis.sadd.assert_any_call("darwin:argocd_apps", "argocd/config-app")


# =========================================================================
# Test 11: Config-only to workload transition
# =========================================================================

@pytest.mark.asyncio
async def test_config_only_to_workload_transition():
    """App that gains workloads is deregistered from darwin:argocd_apps."""
    obs = _make_observer()
    resources_none = [{"version": "v1", "kind": "ConfigMap", "namespace": "argocd", "name": "cfg", "status": "Synced"}]
    app_config = _make_application(name="transitioning-app", resources=resources_none)
    await obs._process_application(app_config, suppress_callbacks=True)

    app_with_workload = _make_application(name="transitioning-app", resources=[_deployment_resource(name="my-svc")])
    await obs._process_application(app_with_workload, suppress_callbacks=True)

    obs.blackboard.redis.srem.assert_any_call("darwin:argocd_apps", "argocd/transitioning-app")
    obs.blackboard.redis.delete.assert_any_call("darwin:argocd_app:argocd/transitioning-app")


# =========================================================================
# Test 12: Config-only app last_seen refreshed on unchanged tick (precision #10)
# =========================================================================

@pytest.mark.asyncio
async def test_config_only_app_last_seen_refreshed_on_unchanged_tick():
    """Two _process_application() calls with identical zero-workload payload both write last_seen."""
    obs = _make_observer()
    resources_none = [{"version": "v1", "kind": "ConfigMap", "namespace": "ns", "name": "c", "status": "Synced"}]
    app = _make_application(name="stable-config-app", resources=resources_none)

    await obs._process_application(app, suppress_callbacks=True)
    first_hset_count = obs.blackboard.redis.hset.call_count

    await obs._process_application(app, suppress_callbacks=True)
    second_hset_count = obs.blackboard.redis.hset.call_count

    assert second_hset_count > first_hset_count


# =========================================================================
# Test 13: App-level sync_status persisted for ALL apps (T-17)
# =========================================================================

@pytest.mark.asyncio
async def test_app_sync_status_persisted_every_tick():
    """T-17: _process_application writes HSET darwin:argocd_app_sync:{app_key} when not suppressed."""
    obs = _make_observer()
    app_init = _make_application(app_sync="Synced", resource_version="1")
    await obs._process_application(app_init, suppress_callbacks=True)
    obs.blackboard.redis.hset.reset_mock()

    app = _make_application(app_sync="OutOfSync", automated={}, resource_version="2")
    await obs._process_application(app)

    obs.blackboard.redis.hset.assert_any_call(
        "darwin:argocd_app_sync:argocd/test-app", "sync_status", "OutOfSync"
    )


@pytest.mark.asyncio
async def test_app_sync_persisted_for_synced_app():
    """Synced apps also persist their sync_status (uniform read path)."""
    obs = _make_observer()
    app_init = _make_application(app_sync="OutOfSync", resource_version="1")
    await obs._process_application(app_init, suppress_callbacks=True)
    obs.blackboard.redis.hset.reset_mock()

    app = _make_application(app_sync="Synced", resource_version="2")
    await obs._process_application(app)

    obs.blackboard.redis.hset.assert_any_call(
        "darwin:argocd_app_sync:argocd/test-app", "sync_status", "Synced"
    )


# =========================================================================
# Test 14: _process_deleted cleans pending entries
# =========================================================================

@pytest.mark.asyncio
async def test_deleted_cleans_pending_entries():
    """_process_deleted removes aligner pending entries for services AND app sync."""
    obs = _make_observer()
    app = _make_application(
        resources=[_deployment_resource(name="svc-a"), _deployment_resource(name="svc-b")],
        automated={},
    )
    await obs._process_application(app, suppress_callbacks=True)

    await obs._process_deleted(app)

    # Service removal (which internally cleans pending health entries)
    obs.blackboard.remove_service.assert_any_call("test-namespace/svc-a")
    obs.blackboard.remove_service.assert_any_call("test-namespace/svc-b")
    # App sync pending entry cleaned explicitly (not covered by remove_service)
    obs.blackboard.remove_aligner_pending.assert_any_call("argocd/test-app|sync")
    # App sync hash deleted
    obs.blackboard.redis.delete.assert_any_call("darwin:argocd_app_sync:argocd/test-app")
