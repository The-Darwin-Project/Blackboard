# tests/test_ephemeral_provisioner.py
# @ai-rules:
# 1. [Pattern]: Local probe — validates EphemeralProvisioner health-aware spawn mechanics.
# 2. [Constraint]: No cluster, no Redis, no Tekton — pure asyncio + mocks.
# 3. [Pattern]: AsyncMock for SpawnHealthPort, httpx calls, and AgentRegistry.
"""
Probe tests for health-aware EphemeralProvisioner.
Validates: fast-fail, stall detection, deadline, degradation, race safety,
circuit breaker, MISSING grace, UNKNOWN flapping, multi-pod, adapter errors.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from src.observers.k8s_constants import SpawnStatus, SpawnPollResult
from src.agents.ephemeral_provisioner import (
    EphemeralProvisioner,
    SpawnFailed,
    INFRA_SENTINEL,
)


@dataclass
class FakeAgent:
    ephemeral: bool = True
    event_id: str = "evt-test001"
    ws: MagicMock = None

    def __post_init__(self):
        if self.ws is None:
            self.ws = MagicMock()


def _make_provisioner(
    health_port=None,
    deadline_sec: float = 5,
    poll_interval_sec: float = 0.1,
    stall_timeout_sec: float = 1,
) -> tuple[EphemeralProvisioner, AsyncMock]:
    """Create provisioner with mocked registry and httpx."""
    registry = AsyncMock()
    registry.get_ephemeral = AsyncMock(return_value=None)
    prov = EphemeralProvisioner(
        registry=registry,
        event_listener_url="http://fake:8080",
        health_port=health_port,
        deadline_sec=deadline_sec,
        poll_interval_sec=poll_interval_sec,
        stall_timeout_sec=stall_timeout_sec,
    )
    return prov, registry


class TestHealthAwareFastFail:
    @pytest.mark.asyncio
    async def test_fast_fail_on_pod_terminal(self):
        """FAILED status after 2 polls → SpawnFailed, elapsed << deadline."""
        call_count = 0

        async def poll_status(event_id: str) -> SpawnPollResult:
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                return SpawnPollResult(
                    SpawnStatus.FAILED, "ImagePullBackOff: bad-image", "pod-x",
                )
            return SpawnPollResult(SpawnStatus.PENDING, pod_name="pod-x")

        hp = AsyncMock()
        hp.poll_spawn_status = poll_status
        prov, _ = _make_provisioner(health_port=hp, deadline_sec=60)

        start = time.monotonic()
        with pytest.raises(SpawnFailed, match="ImagePullBackOff"):
            await prov._wait_for_registration("evt-test001", 60, 0.05, 10)
        elapsed = time.monotonic() - start
        assert elapsed < 5, f"Fast-fail took {elapsed:.1f}s — should be << 60s"


class TestHealthAwareSuccess:
    @pytest.mark.asyncio
    async def test_registration_after_pending(self):
        """PENDING → RUNNING, then registration fires → agent returned."""
        call_count = 0

        async def poll_status(event_id: str) -> SpawnPollResult:
            nonlocal call_count
            call_count += 1
            return SpawnPollResult(
                SpawnStatus.RUNNING if call_count > 1 else SpawnStatus.PENDING,
                pod_name="pod-x",
            )

        hp = AsyncMock()
        hp.poll_spawn_status = poll_status
        prov, registry = _make_provisioner(health_port=hp)

        agent = FakeAgent()

        async def simulate_registration():
            await asyncio.sleep(0.25)
            prov.on_ephemeral_registered("evt-test001")
            registry.get_ephemeral.return_value = agent

        task = asyncio.create_task(simulate_registration())
        result = await prov._wait_for_registration("evt-test001", 5, 0.1, 10)
        await task
        assert result is agent


class TestStallDetection:
    @pytest.mark.asyncio
    async def test_stall_after_pending_then_missing(self):
        """PENDING once → MISSING after → stall timer fires."""
        call_count = 0

        async def poll_status(event_id: str) -> SpawnPollResult:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return SpawnPollResult(SpawnStatus.PENDING, pod_name="pod-x")
            return SpawnPollResult(SpawnStatus.MISSING)

        hp = AsyncMock()
        hp.poll_spawn_status = poll_status
        prov, _ = _make_provisioner(health_port=hp, stall_timeout_sec=0.3)

        with pytest.raises(asyncio.TimeoutError, match="No spawn progress"):
            await prov._wait_for_registration("evt-test001", 30, 0.05, 0.3)


class TestDeadlineExceeded:
    @pytest.mark.asyncio
    async def test_pending_forever_hits_deadline(self):
        """PENDING continuously → deadline fires."""
        async def poll_status(event_id: str) -> SpawnPollResult:
            return SpawnPollResult(SpawnStatus.PENDING, pod_name="pod-x")

        hp = AsyncMock()
        hp.poll_spawn_status = poll_status
        prov, _ = _make_provisioner(health_port=hp, deadline_sec=0.5, stall_timeout_sec=60)

        with pytest.raises(asyncio.TimeoutError, match="deadline exceeded"):
            await prov._wait_for_registration("evt-test001", 0.5, 0.05, 60)


class TestGracefulDegradation:
    @pytest.mark.asyncio
    async def test_no_health_port_blind_wait(self):
        """No health_port → falls back to blind wait, times out at deadline."""
        prov, _ = _make_provisioner(health_port=None, deadline_sec=0.3)

        with pytest.raises(asyncio.TimeoutError, match="deadline exceeded"):
            await prov._wait_for_registration("evt-test001", 0.3, 0.05, 60)


class TestRegistrationDuringPoll:
    @pytest.mark.asyncio
    async def test_race_safe_registration(self):
        """Registration fires during health poll → agent returned."""
        async def slow_poll(event_id: str) -> SpawnPollResult:
            await asyncio.sleep(0.1)
            return SpawnPollResult(SpawnStatus.PENDING, pod_name="pod-x")

        hp = AsyncMock()
        hp.poll_spawn_status = slow_poll
        prov, registry = _make_provisioner(health_port=hp)
        agent = FakeAgent()

        async def fire_registration():
            await asyncio.sleep(0.15)
            prov.on_ephemeral_registered("evt-test001")
            registry.get_ephemeral.return_value = agent

        task = asyncio.create_task(fire_registration())
        result = await prov._wait_for_registration("evt-test001", 5, 0.05, 10)
        await task
        assert result is agent


class TestCircuitBreaker:
    @pytest.mark.asyncio
    async def test_spawn_failed_increments_once(self):
        """SpawnFailed on both attempts → _infra_failures incremented once."""
        async def poll_fail(event_id: str) -> SpawnPollResult:
            return SpawnPollResult(SpawnStatus.FAILED, "CrashLoopBackOff", "pod-x")

        hp = AsyncMock()
        hp.poll_spawn_status = poll_fail
        hp.clear_event = MagicMock()
        prov, registry = _make_provisioner(
            health_port=hp, deadline_sec=2, poll_interval_sec=0.05,
        )

        with patch.object(prov, "_trigger_taskrun", new_callable=AsyncMock):
            with patch.object(prov, "_cancel_taskrun", new_callable=AsyncMock):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await prov.ensure_agent("evt-test001")

        assert result == INFRA_SENTINEL
        assert prov._infra_failures.get("evt-test001") == 1
        assert hp.clear_event.call_count == 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_on_third_call(self):
        """After 2 failed cycles, third call returns None (circuit breaker)."""
        async def poll_fail(event_id: str) -> SpawnPollResult:
            return SpawnPollResult(SpawnStatus.FAILED, "ImagePullBackOff", "pod-x")

        hp = AsyncMock()
        hp.poll_spawn_status = poll_fail
        hp.clear_event = MagicMock()
        prov, _ = _make_provisioner(
            health_port=hp, deadline_sec=1, poll_interval_sec=0.05,
        )

        with patch.object(prov, "_trigger_taskrun", new_callable=AsyncMock):
            with patch.object(prov, "_cancel_taskrun", new_callable=AsyncMock):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    r1 = await prov.ensure_agent("evt-trip")
                    assert r1 == INFRA_SENTINEL
                    assert prov._infra_failures.get("evt-trip") == 1

                    r2 = await prov.ensure_agent("evt-trip")
                    assert r2 == INFRA_SENTINEL
                    assert prov._infra_failures.get("evt-trip") == 2

                    r3 = await prov.ensure_agent("evt-trip")
                    assert r3 is None
                    assert "evt-trip" not in prov._infra_failures


class TestMissingNoStall:
    @pytest.mark.asyncio
    async def test_missing_only_hits_deadline(self):
        """MISSING continuously → stall timer never starts, only deadline fires."""
        async def poll_status(event_id: str) -> SpawnPollResult:
            return SpawnPollResult(SpawnStatus.MISSING)

        hp = AsyncMock()
        hp.poll_spawn_status = poll_status
        prov, _ = _make_provisioner(
            health_port=hp, deadline_sec=0.4, stall_timeout_sec=0.1,
        )

        with pytest.raises(asyncio.TimeoutError, match="deadline exceeded"):
            await prov._wait_for_registration("evt-test001", 0.4, 0.05, 0.1)


class TestUnknownFlapping:
    @pytest.mark.asyncio
    async def test_unknown_pending_alternation(self):
        """UNKNOWN/PENDING alternating → stall resets on PENDING, not on UNKNOWN."""
        call_count = 0

        async def poll_status(event_id: str) -> SpawnPollResult:
            nonlocal call_count
            call_count += 1
            if call_count % 2 == 0:
                return SpawnPollResult(SpawnStatus.PENDING, pod_name="pod-x")
            return SpawnPollResult(SpawnStatus.UNKNOWN, reason="transient")

        hp = AsyncMock()
        hp.poll_spawn_status = poll_status
        prov, _ = _make_provisioner(
            health_port=hp, deadline_sec=0.6, stall_timeout_sec=60,
        )

        with pytest.raises(asyncio.TimeoutError, match="deadline exceeded"):
            await prov._wait_for_registration("evt-test001", 0.6, 0.05, 60)


class TestMultiplePods:
    @patch("src.adapters.spawn_health.httpx.get")
    def test_newest_pod_selected(self, mock_httpx_get):
        """Adapter selects newest pod when N>1 share the same event-id label."""
        from datetime import datetime, timezone
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        mock_httpx_get.return_value = MagicMock(status_code=200)
        adapter = KubernetesSpawnHealthAdapter(namespace="test")

        old_pod = MagicMock()
        old_pod.metadata.name = "pod-old"
        old_pod.metadata.creation_timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

        new_pod = MagicMock()
        new_pod.metadata.name = "pod-new"
        new_pod.metadata.uid = "uid-new"
        new_pod.metadata.creation_timestamp = datetime(2026, 7, 1, tzinfo=timezone.utc)
        new_pod.status.phase = "Running"
        new_pod.status.pod_ip = "10.0.0.1"
        new_pod.status.container_statuses = []
        new_pod.status.init_container_statuses = []

        pods_response = MagicMock()
        pods_response.items = [old_pod, new_pod]

        adapter._initialized = True
        adapter._core_api = MagicMock()
        adapter._core_api.list_namespaced_pod.return_value = pods_response

        result = adapter._poll_sync("evt-test001")
        assert result.pod_name == "pod-new"


class TestTaskRunFallback:
    @patch("src.adapters.spawn_health.httpx.get")
    def test_label_miss_taskrun_hit(self, mock_httpx_get):
        """Label returns 0 pods → fallback to TaskRun → podName → read pod → classify."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        mock_httpx_get.return_value = MagicMock(status_code=200)
        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()
        adapter._custom_api = MagicMock()

        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[])

        pod_mock = MagicMock()
        pod_mock.metadata.name = "darwin-oncall-abc"
        pod_mock.metadata.uid = "uid-abc"
        pod_mock.status.phase = "Running"
        pod_mock.status.pod_ip = "10.0.0.2"
        pod_mock.status.container_statuses = [
            MagicMock(state=MagicMock(waiting=None, terminated=None, running=MagicMock()), started=True),
        ]
        pod_mock.status.init_container_statuses = []
        adapter._core_api.read_namespaced_pod.return_value = pod_mock

        adapter._custom_api.list_namespaced_custom_object.return_value = {
            "items": [{"metadata": {"creationTimestamp": "2026-07-03T00:00:00Z"}, "status": {"podName": "darwin-oncall-abc"}}],
        }

        result = adapter._poll_sync("evt-test001")
        assert result.status == SpawnStatus.RUNNING
        assert result.pod_name == "darwin-oncall-abc"
        adapter._core_api.read_namespaced_pod.assert_called_once()


class TestUnknownOnlyDeadline:
    @pytest.mark.asyncio
    async def test_unknown_only_hits_deadline(self):
        """UNKNOWN every poll → stall never starts, absolute deadline fires."""
        async def poll_status(event_id: str) -> SpawnPollResult:
            return SpawnPollResult(SpawnStatus.UNKNOWN, reason="API flap")

        hp = AsyncMock()
        hp.poll_spawn_status = poll_status
        prov, _ = _make_provisioner(
            health_port=hp, deadline_sec=0.4, stall_timeout_sec=0.1,
        )

        with pytest.raises(asyncio.TimeoutError, match="deadline exceeded"):
            await prov._wait_for_registration("evt-test001", 0.4, 0.05, 0.1)


class TestAdapterExceptionMapping:
    def test_api_exception_returns_unknown(self):
        """K8s ApiException → SpawnPollResult(UNKNOWN, reason=...)."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()
        adapter._core_api.list_namespaced_pod.side_effect = Exception("403 Forbidden")
        adapter._custom_api = MagicMock()
        adapter._custom_api.list_namespaced_custom_object.side_effect = Exception("403 Forbidden")

        result = adapter._poll_sync("evt-test001")
        assert result.status == SpawnStatus.UNKNOWN
        assert "403" in result.reason

    @pytest.mark.asyncio
    async def test_poll_spawn_status_catches_thread_exception(self):
        """Generic exception in thread → UNKNOWN with reason string."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()
        adapter._core_api.list_namespaced_pod.side_effect = RuntimeError("network down")
        adapter._custom_api = MagicMock()
        adapter._custom_api.list_namespaced_custom_object.side_effect = RuntimeError("network down")

        result = await adapter.poll_spawn_status("evt-test001")
        assert result.status == SpawnStatus.UNKNOWN
        assert "network down" in result.reason


class TestRegisteredButMissing:
    @pytest.mark.asyncio
    async def test_registered_but_not_in_registry(self):
        """evt.set() fires but get_ephemeral returns None → TimeoutError."""
        prov, registry = _make_provisioner(health_port=None, deadline_sec=1)
        registry.get_ephemeral = AsyncMock(return_value=None)

        async def fire_registration():
            await asyncio.sleep(0.05)
            prov.on_ephemeral_registered("evt-ghost")

        task = asyncio.create_task(fire_registration())
        with pytest.raises(asyncio.TimeoutError, match="not in registry"):
            await prov._wait_for_registration("evt-ghost", 1, 0.05, 60)
        await task


class TestImportFailDegradation:
    @pytest.mark.asyncio
    async def test_none_health_port_no_polls(self):
        """health_port=None → no health polls, TimeoutError on deadline."""
        prov, _ = _make_provisioner(health_port=None, deadline_sec=0.3)

        with pytest.raises(asyncio.TimeoutError, match="deadline exceeded"):
            await prov._wait_for_registration("evt-test001", 0.3, 0.05, 60)

        assert "evt-test001" not in prov._pending


# ===== Phase 2: Sidecar /health Probe Tests =====


class TestHealthProbeSuccess:
    @patch("src.adapters.spawn_health.httpx.get")
    def test_health_probe_success(self, mock_httpx_get):
        """200 from /health → reason=sidecar_healthy, status=RUNNING."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        mock_httpx_get.return_value = MagicMock(status_code=200)
        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()

        pod = MagicMock()
        pod.metadata.name = "pod-health"
        pod.metadata.uid = "uid-001"
        pod.status.phase = "Running"
        pod.status.pod_ip = "10.0.0.5"
        pod.status.container_statuses = [
            MagicMock(state=MagicMock(waiting=None, terminated=None, running=MagicMock()), started=True),
        ]
        pod.status.init_container_statuses = []
        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[pod])

        result = adapter._poll_sync("evt-health")
        assert result.status == SpawnStatus.RUNNING
        assert result.reason == "sidecar_healthy"
        mock_httpx_get.assert_called_once_with("http://10.0.0.5:9090/health", timeout=2.0)


class TestHealthProbeNotReady:
    @patch("src.adapters.spawn_health.httpx.get")
    def test_health_probe_not_ready(self, mock_httpx_get):
        """Health timeout, not previously healthy → reason=sidecar_not_ready, RUNNING."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        mock_httpx_get.side_effect = httpx.TimeoutException("timeout")
        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()

        pod = MagicMock()
        pod.metadata.name = "pod-boot"
        pod.metadata.uid = "uid-002"
        pod.status.phase = "Running"
        pod.status.pod_ip = "10.0.0.6"
        pod.status.container_statuses = [
            MagicMock(state=MagicMock(waiting=None, terminated=None, running=MagicMock()), started=True),
        ]
        pod.status.init_container_statuses = []
        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[pod])

        result = adapter._poll_sync("evt-boot")
        assert result.status == SpawnStatus.RUNNING
        assert result.reason == "sidecar_not_ready"


class TestHealthProbeCrashDetection:
    @patch("src.adapters.spawn_health.httpx.get")
    def test_health_probe_crash_detection(self, mock_httpx_get):
        """Healthy → 2 consecutive failures → FAILED sidecar_crashed."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()

        pod = MagicMock()
        pod.metadata.name = "pod-crash"
        pod.metadata.uid = "uid-003"
        pod.status.phase = "Running"
        pod.status.pod_ip = "10.0.0.7"
        pod.status.container_statuses = [
            MagicMock(state=MagicMock(waiting=None, terminated=None, running=MagicMock()), started=True),
        ]
        pod.status.init_container_statuses = []
        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[pod])

        # First poll: healthy
        mock_httpx_get.return_value = MagicMock(status_code=200)
        r1 = adapter._poll_sync("evt-crash")
        assert r1.reason == "sidecar_healthy"

        # Second poll: failure #1
        mock_httpx_get.side_effect = ConnectionError("refused")
        r2 = adapter._poll_sync("evt-crash")
        assert r2.status == SpawnStatus.RUNNING
        assert r2.reason == "sidecar_suspect"

        # Third poll: failure #2 → FAILED
        r3 = adapter._poll_sync("evt-crash")
        assert r3.status == SpawnStatus.FAILED
        assert "sidecar_crashed" in r3.reason


class TestSingleMissNotFatal:
    @patch("src.adapters.spawn_health.httpx.get")
    def test_single_miss_after_healthy_not_fatal(self, mock_httpx_get):
        """Healthy then ONE failure → RUNNING sidecar_suspect (not FAILED)."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()

        pod = MagicMock()
        pod.metadata.name = "pod-flap"
        pod.metadata.uid = "uid-004"
        pod.status.phase = "Running"
        pod.status.pod_ip = "10.0.0.8"
        pod.status.container_statuses = [
            MagicMock(state=MagicMock(waiting=None, terminated=None, running=MagicMock()), started=True),
        ]
        pod.status.init_container_statuses = []
        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[pod])

        # Healthy first
        mock_httpx_get.return_value = MagicMock(status_code=200)
        adapter._poll_sync("evt-flap")

        # Single failure
        mock_httpx_get.side_effect = ConnectionError("blip")
        result = adapter._poll_sync("evt-flap")
        assert result.status == SpawnStatus.RUNNING
        assert result.reason == "sidecar_suspect"


class TestRetryResetsHealthState:
    @patch("src.adapters.spawn_health.httpx.get")
    def test_retry_resets_health_state(self, mock_httpx_get):
        """New pod UID on retry → state resets, first failure on new pod = RUNNING."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()

        # Old pod was healthy
        old_pod = MagicMock()
        old_pod.metadata.name = "pod-old"
        old_pod.metadata.uid = "uid-old"
        old_pod.status.phase = "Running"
        old_pod.status.pod_ip = "10.0.0.9"
        old_pod.status.container_statuses = [
            MagicMock(state=MagicMock(waiting=None, terminated=None, running=MagicMock()), started=True),
        ]
        old_pod.status.init_container_statuses = []
        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[old_pod])

        mock_httpx_get.return_value = MagicMock(status_code=200)
        adapter._poll_sync("evt-retry")

        # New pod (different UID) — first probe fails
        new_pod = MagicMock()
        new_pod.metadata.name = "pod-new"
        new_pod.metadata.uid = "uid-new"
        new_pod.status.phase = "Running"
        new_pod.status.pod_ip = "10.0.0.10"
        new_pod.status.container_statuses = [
            MagicMock(state=MagicMock(waiting=None, terminated=None, running=MagicMock()), started=True),
        ]
        new_pod.status.init_container_statuses = []
        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[new_pod])

        mock_httpx_get.side_effect = ConnectionError("refused")
        result = adapter._poll_sync("evt-retry")
        assert result.status == SpawnStatus.RUNNING
        assert result.reason == "sidecar_not_ready"


class TestNoPodIpSkipsProbe:
    @patch("src.adapters.spawn_health.httpx.get")
    def test_no_pod_ip_skips_probe(self, mock_httpx_get):
        """pod_ip=None → RUNNING, no HTTP call attempted."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()

        pod = MagicMock()
        pod.metadata.name = "pod-noip"
        pod.metadata.uid = "uid-noip"
        pod.status.phase = "Running"
        pod.status.pod_ip = None
        pod.status.container_statuses = [
            MagicMock(state=MagicMock(waiting=None, terminated=None, running=MagicMock()), started=True),
        ]
        pod.status.init_container_statuses = []
        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[pod])

        result = adapter._poll_sync("evt-noip")
        assert result.status == SpawnStatus.RUNNING
        mock_httpx_get.assert_not_called()


class TestClearEventRemovesState:
    def test_clear_event_removes_state(self):
        """clear_event removes health state for given event."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter, _PodHealthState

        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._health_state["evt-clear"] = _PodHealthState(
            pod_uid="uid-x", was_healthy=True,
            consecutive_misses=0, boot_first_seen=0.0,
        )

        adapter.clear_event("evt-clear")
        assert "evt-clear" not in adapter._health_state

    def test_clear_event_noop_on_missing(self):
        """clear_event on unknown event_id is a no-op."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter.clear_event("evt-nonexistent")


class TestBootTimeout:
    @patch("src.adapters.spawn_health.time.monotonic")
    @patch("src.adapters.spawn_health.httpx.get")
    def test_boot_timeout_never_healthy(self, mock_httpx_get, mock_monotonic):
        """Never healthy + 120s+ elapsed → FAILED sidecar_boot_timeout."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        mock_httpx_get.side_effect = ConnectionError("refused")
        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()

        pod = MagicMock()
        pod.metadata.name = "pod-stuck"
        pod.metadata.uid = "uid-stuck"
        pod.status.phase = "Running"
        pod.status.pod_ip = "10.0.0.11"
        pod.status.container_statuses = [
            MagicMock(state=MagicMock(waiting=None, terminated=None, running=MagicMock()), started=True),
        ]
        pod.status.init_container_statuses = []
        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[pod])

        # First poll at t=100 — establishes boot_first_seen
        mock_monotonic.return_value = 100.0
        r1 = adapter._poll_sync("evt-stuck")
        assert r1.status == SpawnStatus.RUNNING
        assert r1.reason == "sidecar_not_ready"

        # Second poll at t=221 — exceeds 120s boot timeout
        mock_monotonic.return_value = 221.0
        r2 = adapter._poll_sync("evt-stuck")
        assert r2.status == SpawnStatus.FAILED
        assert "sidecar_boot_timeout" in r2.reason


class TestEvaluateHealthWiring:
    @patch("src.adapters.spawn_health.httpx.get")
    def test_evaluate_health_called_only_for_running(self, mock_httpx_get):
        """_poll_sync calls _evaluate_health ONLY when _classify_pod returns RUNNING."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()

        # FAILED pod — _evaluate_health should NOT be called
        pod_failed = MagicMock()
        pod_failed.metadata.name = "pod-fail"
        pod_failed.metadata.uid = "uid-fail"
        pod_failed.status.phase = "Failed"
        pod_failed.status.pod_ip = "10.0.0.12"
        pod_failed.status.container_statuses = []
        pod_failed.status.init_container_statuses = []
        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[pod_failed])

        result = adapter._poll_sync("evt-wire-fail")
        assert result.status == SpawnStatus.FAILED
        mock_httpx_get.assert_not_called()

        # RUNNING pod — _evaluate_health IS called
        pod_running = MagicMock()
        pod_running.metadata.name = "pod-run"
        pod_running.metadata.uid = "uid-run"
        pod_running.status.phase = "Running"
        pod_running.status.pod_ip = "10.0.0.13"
        pod_running.status.container_statuses = [
            MagicMock(state=MagicMock(waiting=None, terminated=None, running=MagicMock()), started=True),
        ]
        pod_running.status.init_container_statuses = []
        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[pod_running])
        mock_httpx_get.return_value = MagicMock(status_code=200)

        result = adapter._poll_sync("evt-wire-run")
        assert result.status == SpawnStatus.RUNNING
        assert result.reason == "sidecar_healthy"
        mock_httpx_get.assert_called_once()


class TestInstallationIdPropagation:
    """(p)/(q): ensure_agent forwards installation_id to the TaskRun POST body."""

    @pytest.mark.asyncio
    async def test_ensure_agent_with_installation_id_includes_it_in_post_body(self):
        """(p) ensure_agent(event_id, "123") -> POST body includes installation_id."""
        prov, registry = _make_provisioner()
        registry.get_ephemeral = AsyncMock(return_value=None)

        captured = {}

        class _FakeResponse:
            status_code = 202
            def raise_for_status(self):
                pass

        class _FakeAsyncClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *exc):
                return False
            async def post(self, url, json):
                captured["json"] = json
                return _FakeResponse()

        with patch("httpx.AsyncClient", return_value=_FakeAsyncClient()):
            with patch.object(prov, "_wait_for_registration", new_callable=AsyncMock) as mock_wait:
                mock_wait.return_value = MagicMock()
                await prov.ensure_agent("evt-install001", "123")

        assert captured["json"]["installation_id"] == "123"
        assert captured["json"]["event_id"] == "evt-install001"

    @pytest.mark.asyncio
    async def test_ensure_agent_without_installation_id_sends_empty_string(self):
        """(q) ensure_agent(event_id) -> sends installation_id="" (default, backward compat)."""
        prov, registry = _make_provisioner()
        registry.get_ephemeral = AsyncMock(return_value=None)

        captured = {}

        class _FakeResponse:
            status_code = 202
            def raise_for_status(self):
                pass

        class _FakeAsyncClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *exc):
                return False
            async def post(self, url, json):
                captured["json"] = json
                return _FakeResponse()

        with patch("httpx.AsyncClient", return_value=_FakeAsyncClient()):
            with patch.object(prov, "_wait_for_registration", new_callable=AsyncMock) as mock_wait:
                mock_wait.return_value = MagicMock()
                await prov.ensure_agent("evt-install002")

        assert captured["json"]["installation_id"] == ""


class TestModelPropagation:
    """ensure_agent forwards `model` to the TaskRun POST body -- conditionally.

    An empty string must NOT be sent: it would override the TriggerTemplate's
    Helm-configured default (see ephemeral-model-routing plan, Step 6).
    """

    @staticmethod
    def _fake_client(captured: dict):
        class _FakeResponse:
            status_code = 202
            def raise_for_status(self):
                pass

        class _FakeAsyncClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *exc):
                return False
            async def post(self, url, json):
                captured["json"] = json
                return _FakeResponse()

        return _FakeAsyncClient()

    @pytest.mark.asyncio
    async def test_model_included_when_non_empty(self):
        """(a) ensure_agent(event_id, model="claude-opus-4-6[1m]") -> POST body includes model."""
        prov, registry = _make_provisioner()
        registry.get_ephemeral = AsyncMock(return_value=None)
        captured = {}

        with patch("httpx.AsyncClient", return_value=self._fake_client(captured)):
            with patch.object(prov, "_wait_for_registration", new_callable=AsyncMock) as mock_wait:
                mock_wait.return_value = MagicMock()
                await prov.ensure_agent("evt-model001", model="claude-opus-4-6[1m]")

        assert captured["json"]["model"] == "claude-opus-4-6[1m]"

    @pytest.mark.asyncio
    async def test_model_omitted_when_empty(self):
        """(b) ensure_agent(event_id) with no model -> "model" key absent from POST body
        (so the TriggerTemplate's Helm default takes effect instead of an empty override)."""
        prov, registry = _make_provisioner()
        registry.get_ephemeral = AsyncMock(return_value=None)
        captured = {}

        with patch("httpx.AsyncClient", return_value=self._fake_client(captured)):
            with patch.object(prov, "_wait_for_registration", new_callable=AsyncMock) as mock_wait:
                mock_wait.return_value = MagicMock()
                await prov.ensure_agent("evt-model002")

        assert "model" not in captured["json"]

    @pytest.mark.asyncio
    async def test_retry_path_passes_model(self):
        """(c) retry after a transient failure still forwards model to the second POST."""
        prov, registry = _make_provisioner()
        registry.get_ephemeral = AsyncMock(return_value=None)

        call_count = 0
        captured_calls = []

        async def flaky_trigger(event_id, installation_id="", model=""):
            nonlocal call_count
            call_count += 1
            captured_calls.append(model)
            if call_count == 1:
                raise httpx.HTTPError("transient")

        with patch.object(prov, "_trigger_taskrun", side_effect=flaky_trigger):
            with patch.object(prov, "_cancel_taskrun", new_callable=AsyncMock):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    with patch.object(prov, "_wait_for_registration", new_callable=AsyncMock) as mock_wait:
                        mock_wait.return_value = MagicMock()
                        await prov.ensure_agent("evt-model003", model="claude-sonnet-5")

        assert captured_calls == ["claude-sonnet-5", "claude-sonnet-5"]
