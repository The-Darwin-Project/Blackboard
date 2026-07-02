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
        prov, registry = _make_provisioner(
            health_port=hp, deadline_sec=2, poll_interval_sec=0.05,
        )

        with patch.object(prov, "_trigger_taskrun", new_callable=AsyncMock):
            with patch.object(prov, "_cancel_taskrun", new_callable=AsyncMock):
                with patch("asyncio.sleep", new_callable=AsyncMock):
                    result = await prov.ensure_agent("evt-test001")

        assert result == INFRA_SENTINEL
        assert prov._infra_failures.get("evt-test001") == 1

    @pytest.mark.asyncio
    async def test_circuit_breaker_trips_on_third_call(self):
        """After 2 failed cycles, third call returns None (circuit breaker)."""
        async def poll_fail(event_id: str) -> SpawnPollResult:
            return SpawnPollResult(SpawnStatus.FAILED, "ImagePullBackOff", "pod-x")

        hp = AsyncMock()
        hp.poll_spawn_status = poll_fail
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
    def test_newest_pod_selected(self):
        """Adapter selects newest pod when N>1 share the same event-id label."""
        from datetime import datetime, timezone
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        adapter = KubernetesSpawnHealthAdapter(namespace="test")

        old_pod = MagicMock()
        old_pod.metadata.name = "pod-old"
        old_pod.metadata.creation_timestamp = datetime(2026, 1, 1, tzinfo=timezone.utc)

        new_pod = MagicMock()
        new_pod.metadata.name = "pod-new"
        new_pod.metadata.creation_timestamp = datetime(2026, 7, 1, tzinfo=timezone.utc)
        new_pod.status.phase = "Running"
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
    def test_label_miss_taskrun_hit(self):
        """Label returns 0 pods → fallback to TaskRun → podName → read pod → classify."""
        from src.adapters.spawn_health import KubernetesSpawnHealthAdapter

        adapter = KubernetesSpawnHealthAdapter(namespace="test")
        adapter._initialized = True
        adapter._core_api = MagicMock()
        adapter._custom_api = MagicMock()

        adapter._core_api.list_namespaced_pod.return_value = MagicMock(items=[])

        pod_mock = MagicMock()
        pod_mock.metadata.name = "darwin-oncall-abc"
        pod_mock.status.phase = "Running"
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
