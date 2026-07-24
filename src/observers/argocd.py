# BlackBoard/src/observers/argocd.py
# @ai-rules:
# 1. [Pattern]: K8s Watch with exponential backoff (1s-30s). Mirrors KargoObserver in kargo.py.
# 2. [Constraint]: AIR GAP -- lives in src/observers/, not src/agents/. No agent-side imports.
# 3. [Pattern]: Fingerprint cache (frozenset of Deployment name/health/sync tuples) skips the
#    full extraction+write pass when nothing changed; last_seen is still touched on every
#    watch event for known services so zombie detection never regresses.
# 4. [Pattern]: sync_change_callback fires once per Application per watch tick (never fanned
#    out per-service). It is gated on spec.syncPolicy.automated existing on the Application --
#    Aligner owns the 60s dwell-time debounce state machine on top of these calls.
# 5. [Constraint]: Callbacks are async -- never raise into the watch loop. Wrap in try/except.
# 6. [Pattern]: DELETED events remove every service tracked under that Application via
#    blackboard.remove_service() -- keeps topology membership in sync with cluster state.
# 7. [Pattern]: get_degraded_applications() is the on-demand read path for dashboard broadcast
#    (mirrors KargoObserver.get_failed_stages()).
# 8. [Pattern]: GitOps repo/path (spec.source.repoURL/.path) and version (first
#    status.summary.images[] tag) are Application-level fields shared by every service
#    exploded from that Application -- written via update_service_discovery() (never
#    overwrites cpu/memory/error_rate). Coarse-grained by design: accepted per probe outcome.
"""
ArgoCD Application Observer -- watches Application CRs via K8s Watch API.

Replaces KubernetesObserver + metrics-based health assessment. ArgoCD Application
status.resources[] is the sole discovery, health, and sync source: each Application
explodes into N Darwin services (its Deployments), and per-resource health/sync
drives Aligner escalation deterministically (no LLM in the loop for this signal).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Optional

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

ARGOCD_OBSERVER_ENABLED = os.getenv("ARGOCD_OBSERVER_ENABLED", "false").lower() == "true"
ARGOCD_GROUP = "argoproj.io"
ARGOCD_VERSION = "v1alpha1"
ARGOCD_PLURAL = "applications"

_WORKLOAD_KINDS = frozenset({"Deployment", "StatefulSet", "DaemonSet", "CronJob", "Job"})


def _load_name_mapping() -> dict[str, str]:
    """Parse ARGOCD_NAME_MAPPING (JSON string) into a raw-resource-name -> service-name dict.

    Reserved for future name mismatches -- existing services match resource.name directly.
    """
    raw = os.getenv("ARGOCD_NAME_MAPPING", "")
    if not raw:
        return {}
    try:
        mapping = json.loads(raw)
        return mapping if isinstance(mapping, dict) else {}
    except (json.JSONDecodeError, TypeError):
        logger.warning("ARGOCD_NAME_MAPPING is not valid JSON -- ignoring")
        return {}


class ArgoCDObserver:
    """Watches ArgoCD Application CRs and fires callbacks on health/sync state changes."""

    def __init__(
        self,
        blackboard: "BlackboardState",
        health_change_callback: Optional[Callable[..., Awaitable[None]]] = None,
        sync_change_callback: Optional[Callable[..., Awaitable[None]]] = None,
        broadcast_callback: Optional[Callable[..., Awaitable[None]]] = None,
    ):
        self.blackboard = blackboard
        self.health_change_callback = health_change_callback
        self.sync_change_callback = sync_change_callback
        self.broadcast_callback = broadcast_callback
        self._name_mapping = _load_name_mapping()

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._k8s_available = False
        self._custom_api: Any = None
        self._resource_version: str = ""
        self._current_watch: Any = None

        # app_key ("namespace/name") -> {fingerprint, resource_health, sync, health, automated, namespace}
        self._application_states: dict[str, dict] = {}

    async def start(self) -> None:
        if self._running:
            logger.warning("ArgoCDObserver already running")
            return
        if not await self._init_k8s_client():
            logger.warning("ArgoCDObserver disabled: K8s client not available")
            return

        await self._initial_sync()
        await self._fire_broadcast()
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info(
            "ArgoCDObserver started: watching applications cluster-wide "
            f"(initial apps={len(self._application_states)})"
        )

    async def stop(self) -> None:
        if not self._running:
            return
        self._running = False
        if self._current_watch:
            self._current_watch.stop()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._current_watch = None
        logger.info("ArgoCDObserver stopped")

    def get_degraded_applications(self) -> list[dict]:
        """Return current non-Healthy application snapshots for dashboard broadcast."""
        return [
            {"argocd_app": key, "namespace": state.get("namespace", ""), "health": state.get("health", "")}
            for key, state in self._application_states.items()
            if state.get("health") not in ("Healthy", None)
        ]

    async def _fire_broadcast(self) -> None:
        if self.broadcast_callback:
            try:
                await self.broadcast_callback()
            except Exception as e:
                logger.error(f"ArgoCDObserver broadcast_callback error: {e}")

    async def _init_k8s_client(self) -> bool:
        try:
            from kubernetes import client, config
            try:
                config.load_incluster_config()
            except config.ConfigException:
                try:
                    config.load_kube_config()
                except config.ConfigException as e:
                    logger.warning(f"No Kubernetes config available: {e}")
                    return False
            # Workaround: kubernetes client v36+ stores token under 'authorization'
            # but auth_settings() reads from 'BearerToken'. Patch the mismatch.
            cfg = client.Configuration._default
            if cfg and 'authorization' in cfg.api_key and 'BearerToken' not in cfg.api_key:
                token_val = cfg.api_key['authorization']
                if token_val.lower().startswith('bearer '):
                    token_val = token_val[7:]
                cfg.api_key['BearerToken'] = token_val
                cfg.api_key_prefix['BearerToken'] = 'Bearer'
            self._custom_api = client.CustomObjectsApi()
            self._k8s_available = True
            return True
        except ImportError:
            logger.warning("kubernetes package not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize K8s client for ArgoCD: {e}")
            return False

    async def _initial_sync(self) -> None:
        """List all Applications, record current state without firing callbacks.

        Builds new state in a temporary dict and swaps on success. A failed K8s API
        call preserves the previous state instead of leaving _application_states empty.
        """
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._custom_api.list_cluster_custom_object(
                    group=ARGOCD_GROUP, version=ARGOCD_VERSION, plural=ARGOCD_PLURAL,
                ),
            )
            new_rv = result.get("metadata", {}).get("resourceVersion", "")
            self._application_states.clear()
            for app in result.get("items", []):
                try:
                    await self._process_application(app, suppress_callbacks=True)
                except Exception as app_err:
                    app_name = app.get("metadata", {}).get("name", "unknown")
                    logger.warning(f"ArgoCDObserver: skipping malformed Application {app_name} during initial sync: {app_err}")
            self._resource_version = new_rv
            logger.info(
                f"ArgoCDObserver initial sync: rv={self._resource_version}, "
                f"apps={len(self._application_states)}"
            )
            # Clean orphan entries without ArgoCD metadata or stale last_seen
            try:
                removed = await self.blackboard.cleanup_stale_services()
                if removed:
                    logger.info(f"ArgoCDObserver initial sync: cleaned {removed} orphan entries")
            except Exception as cleanup_err:
                logger.warning(f"ArgoCDObserver cleanup_stale_services failed: {cleanup_err}")
        except Exception as e:
            logger.error(f"ArgoCDObserver initial sync failed (previous state preserved): {e}")

    async def _watch_loop(self) -> None:
        from kubernetes import watch
        from kubernetes.client.exceptions import ApiException
        import queue as _queue

        retry_delay = 1
        while self._running:
            w: Any = None
            try:
                w = watch.Watch()
                self._current_watch = w
                logger.info(f"ArgoCDObserver watch starting (rv={self._resource_version})")
                kwargs: dict[str, Any] = {
                    "group": ARGOCD_GROUP, "version": ARGOCD_VERSION,
                    "plural": ARGOCD_PLURAL, "timeout_seconds": 300,
                }
                if self._resource_version:
                    kwargs["resource_version"] = self._resource_version

                event_q: _queue.Queue = _queue.Queue()

                def _run_watch() -> None:
                    try:
                        for event in w.stream(
                            self._custom_api.list_cluster_custom_object, **kwargs,
                        ):
                            event_q.put(event)
                    except Exception as e:
                        event_q.put(e)
                    finally:
                        event_q.put(None)

                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, _run_watch)
                retry_delay = 1

                while self._running:
                    try:
                        item = await asyncio.wait_for(
                            loop.run_in_executor(None, event_q.get, True, 5),
                            timeout=10,
                        )
                    except asyncio.CancelledError:
                        raise
                    except (asyncio.TimeoutError, _queue.Empty):
                        continue
                    except Exception as e:
                        logger.warning(f"ArgoCDObserver queue read error: {e}")
                        continue
                    if item is None:
                        break
                    if isinstance(item, Exception):
                        raise item

                    event_type = item.get("type", "")
                    obj = item.get("object", {})
                    rv = obj.get("metadata", {}).get("resourceVersion", "")
                    if rv:
                        self._resource_version = rv
                    if event_type in ("ADDED", "MODIFIED"):
                        await self._process_application(obj)
                    elif event_type == "DELETED":
                        await self._process_deleted(obj)

                w.stop()
                self._current_watch = None
            except ApiException as e:
                if e.status == 410:
                    logger.warning("ArgoCDObserver watch 410 Gone -- re-listing")
                    self._resource_version = ""
                    await self._initial_sync()
                    await self._fire_broadcast()
                    retry_delay = 1
                    continue
                logger.warning(f"ArgoCDObserver watch API error ({e.status}): {e.reason}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"ArgoCDObserver watch error: {e}")

            if not self._running:
                break
            logger.info(f"ArgoCDObserver reconnecting in {retry_delay}s")
            try:
                await asyncio.sleep(retry_delay)
            except asyncio.CancelledError:
                break
            retry_delay = min(retry_delay * 2, 30)

    async def _process_application(self, app: dict, suppress_callbacks: bool = False) -> None:
        """Extract Deployment resources from one Application and update service state.

        Guards early on missing/null status (freshly-created apps, ApplicationSet
        children before first reconcile). Skips the full extraction+write pass when
        the Deployment fingerprint is unchanged, but still touches last_seen for
        every known service so zombie detection stays accurate.
        """
        meta = app.get("metadata") or {}
        app_ns = meta.get("namespace", "")
        app_name = meta.get("name", "")
        if not app_name:
            return
        app_key = f"{app_ns}/{app_name}"

        status = app.get("status") or {}
        health = status.get("health") or {}
        sync = status.get("sync") or {}
        app_health = health.get("status")
        app_sync = sync.get("status")
        if not app_health or not app_sync:
            return

        spec = app.get("spec") or {}
        automated = "automated" in (spec.get("syncPolicy") or {})

        source = spec.get("source") or {}
        gitops_repo_url = source.get("repoURL") or ""
        gitops_config_path = source.get("path") or ""
        images = (status.get("summary") or {}).get("images") or []
        version = self._first_image_tag(images)

        resources = status.get("resources") or []
        workloads = [r for r in resources if r.get("kind") in _WORKLOAD_KINDS]
        fingerprint = frozenset(
            (r.get("name", ""), (r.get("health") or {}).get("status", ""), r.get("status", ""))
            for r in workloads
        )

        prev = self._application_states.get(app_key, {})
        prev_fingerprint = prev.get("fingerprint")
        prev_resource_health: dict[str, str] = prev.get("resource_health", {})
        prev_app_sync = prev.get("sync")
        is_new_app = app_key not in self._application_states

        last_operations = self._extract_last_operations(status)

        # Config-only app registration runs OUTSIDE the fingerprint gate (precision req #1)
        # Ensures last_seen stays fresh every tick — zombie filter needs it.
        now_str = str(time.time())
        if not workloads:
            await self.blackboard.redis.sadd("darwin:argocd_apps", app_key)
            await self.blackboard.redis.hset(f"darwin:argocd_app:{app_key}", mapping={
                "name": app_name,
                "health": app_health,
                "sync_status": app_sync,
                "namespace": app_ns,
                "last_seen": now_str,
            })
            # Transition: app lost its workloads — remove old services
            if prev_resource_health:
                for svc_name in prev_resource_health:
                    try:
                        await self.blackboard.remove_service(svc_name)
                    except Exception as e:
                        logger.warning(f"ArgoCDObserver: failed removing transitioned service {svc_name}: {e}")
        else:
            # Workload-bearing: unconditionally deregister from config-only (no-op if absent)
            await self.blackboard.redis.srem("darwin:argocd_apps", app_key)
            await self.blackboard.redis.delete(f"darwin:argocd_app:{app_key}")

        if is_new_app or fingerprint != prev_fingerprint:
            resource_health = await self._extract_and_update(
                app_key, app_ns, workloads, prev_resource_health,
                last_operations, suppress_callbacks,
                version, gitops_repo_url, gitops_config_path,
            )
            # Clean up services removed from the application (partial workload removal)
            removed_services = set(prev_resource_health.keys()) - set(resource_health.keys())
            for svc_name in removed_services:
                try:
                    await self.blackboard.remove_service(svc_name)
                except Exception as e:
                    logger.warning(f"ArgoCDObserver: failed removing orphaned service {svc_name}: {e}")
        else:
            resource_health = prev_resource_health
            await self._touch_last_seen(resource_health)

        if automated and not suppress_callbacks and self.sync_change_callback:
            try:
                await self.sync_change_callback(app_key, prev_app_sync, app_sync)
            except Exception as e:
                logger.error(f"ArgoCDObserver sync_change_callback error for {app_key}: {e}")

        self._application_states[app_key] = {
            "fingerprint": fingerprint,
            "resource_health": resource_health,
            "sync": app_sync,
            "health": app_health,
            "automated": automated,
            "namespace": app_ns,
        }

        if not suppress_callbacks:
            await self._fire_broadcast()

    async def _extract_and_update(
        self,
        app_key: str,
        app_ns: str,
        deployments: list[dict],
        prev_resource_health: dict[str, str],
        last_operations: list[dict],
        suppress_callbacks: bool,
        version: str,
        gitops_repo_url: str,
        gitops_config_path: str,
    ) -> dict[str, str]:
        """Map Deployment resources to Darwin services, write state, fire per-service health callbacks."""
        resource_health: dict[str, str] = {}
        for resource in deployments:
            raw_name = resource.get("name", "")
            if not raw_name:
                continue
            service_name = self._name_mapping.get(raw_name, raw_name)
            svc_ns = resource.get("namespace") or app_ns
            r_health = (resource.get("health") or {}).get("status") or "Unknown"
            r_sync = resource.get("status") or "Unknown"
            resource_health[service_name] = r_health

            try:
                await self.blackboard.add_service(service_name)
                await self.blackboard.update_service_argocd_status(
                    name=service_name,
                    health_status=r_health,
                    sync_status=r_sync,
                    argocd_app=app_key,
                    namespace=svc_ns,
                    last_operations=last_operations,
                )
                await self.blackboard.update_service_discovery(
                    name=service_name,
                    version=version,
                    gitops_repo_url=gitops_repo_url or None,
                    gitops_config_path=gitops_config_path or None,
                )
            except Exception as e:
                logger.error(f"ArgoCDObserver failed to update service {service_name}: {e}")

            old_health = prev_resource_health.get(service_name)
            if (
                not suppress_callbacks
                and old_health is not None
                and old_health != r_health
                and self.health_change_callback
            ):
                try:
                    await self.health_change_callback(
                        service_name, old_health, r_health,
                        {"argocd_app": app_key, "namespace": svc_ns},
                    )
                except Exception as e:
                    logger.error(f"ArgoCDObserver health_change_callback error for {service_name}: {e}")
        return resource_health

    async def _touch_last_seen(self, resource_health: dict[str, str]) -> None:
        """Cheap last_seen refresh for unchanged Applications -- avoids full re-extraction."""
        now_str = str(time.time())
        for service_name in resource_health:
            try:
                await self.blackboard.redis.hset(f"darwin:service:{service_name}", "last_seen", now_str)
            except Exception as e:
                logger.debug(f"ArgoCDObserver last_seen touch failed for {service_name}: {e}")

    async def _process_deleted(self, app: dict) -> None:
        """Application removed from cluster -- clean up topology and config-only app entries."""
        meta = app.get("metadata") or {}
        app_ns = meta.get("namespace", "")
        app_name = meta.get("name", "")
        app_key = f"{app_ns}/{app_name}"
        prev = self._application_states.pop(app_key, None)
        # Clean config-only app entries regardless of prev state
        await self.blackboard.redis.srem("darwin:argocd_apps", app_key)
        await self.blackboard.redis.delete(f"darwin:argocd_app:{app_key}")
        if not prev:
            return
        for service_name in prev.get("resource_health", {}):
            try:
                await self.blackboard.remove_service(service_name)
            except Exception as e:
                logger.error(f"ArgoCDObserver remove_service failed for {service_name}: {e}")
        logger.info(f"ArgoCDObserver: Application {app_key} deleted, removed {len(prev.get('resource_health', {}))} services")
        await self._fire_broadcast()

    @staticmethod
    def _first_image_tag(images: list[str]) -> str:
        """Extract the tag from the first status.summary.images[] entry.

        Handles 'repo:tag' and 'repo@sha256:digest' forms. One Application can
        explode into N services -- all share this version (accepted per probe
        outcome: graceful degradation over per-Deployment image tracking).
        """
        if not images:
            return "unknown"
        first = images[0]
        if "@" in first:
            return first.rsplit("@", 1)[-1]
        if ":" in first:
            candidate = first.rsplit(":", 1)[-1]
            if "/" not in candidate:
                return candidate
        return first

    @staticmethod
    def _extract_last_operations(status: dict) -> list[dict]:
        """Parse operationState (current) + history[] (last 5) into a compact operation log."""
        ops: list[dict] = []
        op_state = status.get("operationState") or {}
        if op_state:
            sync_result = op_state.get("syncResult") or {}
            ops.append({
                "type": "current",
                "phase": op_state.get("phase", ""),
                "startedAt": op_state.get("startedAt", ""),
                "finishedAt": op_state.get("finishedAt", ""),
                "revision": sync_result.get("revision", ""),
            })
        history = status.get("history") or []
        for entry in history[-5:]:
            ops.append({
                "type": "history",
                "revision": entry.get("revision", ""),
                "deployedAt": entry.get("deployedAt", ""),
            })
        return ops
