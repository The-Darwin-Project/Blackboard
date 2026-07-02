# BlackBoard/src/adapters/spawn_health.py
# @ai-rules:
# 1. [Pattern]: Hexagonal driven adapter — implements SpawnHealthPort Protocol.
# 2. [Constraint]: All K8s API calls via asyncio.to_thread() — sync kubernetes client.
# 3. [Pattern]: Pod lookup by label darwin.io/event-id; take newest if N>1.
# 4. [Constraint]: No Brain logic, no Redis, no LLM — pure infrastructure.
# 5. [Gotcha]: BearerToken workaround required for kubernetes client v36+ (see kubernetes.py:169-177).
# 6. [Gotcha]: _request_timeout=(5, 10) on all K8s API calls to prevent thread pool starvation.
"""
Kubernetes-backed spawn health adapter.

Polls pod status for ephemeral agents during spawn to enable fast-fail
on terminal pod states (ImagePullBackOff, CrashLoopBackOff, etc.)
instead of waiting the full 180s blind timeout.
"""
from __future__ import annotations

import asyncio
import logging

from src.observers.k8s_constants import UNHEALTHY_STATES, SpawnStatus, SpawnPollResult

logger = logging.getLogger(__name__)


class KubernetesSpawnHealthAdapter:
    """Polls K8s pod status for ephemeral agent spawn tracking.

    Two-tier lookup:
    1. Primary: list_namespaced_pod by label ``darwin.io/event-id``
    2. Fallback: list TaskRuns by label → read ``status.podName`` → read pod
    """

    def __init__(self, namespace: str) -> None:
        self._namespace = namespace
        self._core_api = None
        self._custom_api = None
        self._initialized = False

    async def poll_spawn_status(self, event_id: str) -> SpawnPollResult:
        """Poll pod status for an ephemeral agent spawn."""
        try:
            return await asyncio.to_thread(self._poll_sync, event_id)
        except Exception as exc:
            reason = f"{type(exc).__name__}: {getattr(exc, 'status', '')}"
            self._consecutive_errors = getattr(self, "_consecutive_errors", 0) + 1
            lvl = logging.WARNING if self._consecutive_errors >= 3 else logging.DEBUG
            logger.log(lvl, "Spawn health poll error for %s: %s", event_id, reason)
            return SpawnPollResult(status=SpawnStatus.UNKNOWN, reason=reason)

    def _poll_sync(self, event_id: str) -> SpawnPollResult:
        """Synchronous poll — runs in thread pool."""
        if not self._initialized:
            self._init_k8s_client()
        self._consecutive_errors = 0

        label_err: Exception | None = None
        tr_err: Exception | None = None

        pod = None
        try:
            pod = self._find_pod_by_label(event_id)
        except Exception as exc:
            label_err = exc

        if pod is None:
            try:
                pod = self._find_pod_via_taskrun(event_id)
            except Exception as exc:
                tr_err = exc

        if pod is None:
            if label_err or tr_err:
                reason = str(label_err or tr_err)
                return SpawnPollResult(status=SpawnStatus.UNKNOWN, reason=reason)
            return SpawnPollResult(status=SpawnStatus.MISSING)

        return self._classify_pod(pod)

    def _find_pod_by_label(self, event_id: str):
        """Primary lookup: pods labeled with darwin.io/event-id.

        Raises on API errors — caller distinguishes "not found" from "API down".
        """
        pods = self._core_api.list_namespaced_pod(
            self._namespace,
            label_selector=f"darwin.io/event-id={event_id}",
            _request_timeout=(5, 10),
        )
        if not pods.items:
            return None
        if len(pods.items) == 1:
            return pods.items[0]
        return max(pods.items, key=lambda p: p.metadata.creation_timestamp)

    def _find_pod_via_taskrun(self, event_id: str):
        """Fallback: find TaskRun by label → read status.podName → read pod.

        Raises on API errors — caller distinguishes "not found" from "API down".
        """
        taskruns = self._custom_api.list_namespaced_custom_object(
            group="tekton.dev",
            version="v1",
            namespace=self._namespace,
            plural="taskruns",
            label_selector=f"darwin.io/event-id={event_id}",
            _request_timeout=(5, 10),
        )
        items = taskruns.get("items", [])
        if not items:
            return None
        items.sort(key=lambda x: x.get("metadata", {}).get("creationTimestamp", ""))
        tr = items[-1]
        pod_name = (tr.get("status") or {}).get("podName")
        if not pod_name:
            return None
        return self._core_api.read_namespaced_pod(
            pod_name, self._namespace, _request_timeout=(5, 10),
        )

    def _classify_pod(self, pod) -> SpawnPollResult:
        """Map pod phase + container states to SpawnPollResult."""
        pod_name = pod.metadata.name or ""
        phase = (pod.status.phase or "") if pod.status else ""

        # Succeeded is terminal for spawn: the TaskRun step exited 0 before WS
        # registration — the agent process ended without connecting to the Brain.
        if phase in ("Failed", "Succeeded"):
            return SpawnPollResult(
                status=SpawnStatus.FAILED,
                reason=f"Pod phase: {phase}",
                pod_name=pod_name,
            )

        all_statuses = []
        if pod.status:
            all_statuses = list(pod.status.container_statuses or []) + \
                           list(pod.status.init_container_statuses or [])

        for cs in all_statuses:
            if cs.state and cs.state.waiting:
                reason = cs.state.waiting.reason or ""
                if reason in UNHEALTHY_STATES:
                    return SpawnPollResult(
                        status=SpawnStatus.FAILED,
                        reason=f"{reason}: {cs.state.waiting.message or cs.name}",
                        pod_name=pod_name,
                    )
            if cs.state and cs.state.terminated:
                reason = cs.state.terminated.reason or ""
                if reason in UNHEALTHY_STATES:
                    return SpawnPollResult(
                        status=SpawnStatus.FAILED,
                        reason=f"{reason}: exit_code={cs.state.terminated.exit_code}",
                        pod_name=pod_name,
                    )

        if phase == "Running" and all(
            getattr(cs, "started", False) or (cs.state and cs.state.running)
            for cs in (pod.status.container_statuses or [])
            if pod.status and pod.status.container_statuses
        ):
            return SpawnPollResult(
                status=SpawnStatus.RUNNING, pod_name=pod_name,
            )

        if phase == "Pending":
            return SpawnPollResult(
                status=SpawnStatus.PENDING, pod_name=pod_name,
            )

        return SpawnPollResult(
            status=SpawnStatus.UNKNOWN,
            reason=f"Unclassified phase: {phase}",
            pod_name=pod_name,
        )

    def _init_k8s_client(self) -> None:
        """Lazy K8s client init with BearerToken workaround."""
        from kubernetes import client, config

        try:
            config.load_incluster_config()
        except config.ConfigException:
            config.load_kube_config()

        cfg = client.Configuration._default
        if cfg and "authorization" in cfg.api_key and "BearerToken" not in cfg.api_key:
            token = cfg.api_key["authorization"]
            if isinstance(token, str) and token.lower().startswith("bearer "):
                token = token[len("Bearer "):]
            cfg.api_key["BearerToken"] = token
            if "authorization" in cfg.api_key_prefix and "BearerToken" not in cfg.api_key_prefix:
                cfg.api_key_prefix["BearerToken"] = cfg.api_key_prefix["authorization"]

        self._core_api = client.CoreV1Api()
        self._custom_api = client.CustomObjectsApi()
        self._initialized = True
