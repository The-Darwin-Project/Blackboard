# BlackBoard/src/observers/kargo.py
# @ai-rules:
# 1. [Pattern]: K8s Watch with exponential backoff (1s-30s). Matches KargoWatchAdapter in payloads service.
# 2. [Pattern]: Initial sync on start() records Errored stages into _reported_failures WITHOUT callbacks.
# 3. [Pattern]: 410 Gone triggers full re-list with fresh resource_version.
# 4. [Constraint]: Callbacks are async -- never raise into the watch loop. Wrap in try/except.
# 5. [Pattern]: get_stage_status() is the on-demand read path for Brain's refresh_kargo_context tool.
"""
Kargo Stage Observer -- watches promotion state via K8s Watch API.

Detects failed promotions and reports them to the Aligner for event creation.
Detects recovery (newer promotion succeeded) and notifies active events.
Provides on-demand stage status reads for Brain verification.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, Callable, Awaitable, Optional

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

KARGO_OBSERVER_ENABLED = os.getenv("KARGO_OBSERVER_ENABLED", "false").lower() == "true"
KARGO_GROUP = "kargo.akuity.io"
KARGO_VERSION = "v1alpha1"
KARGO_PLURAL = "stages"
FAILED_PHASES = frozenset({"Errored", "Failed"})


class KargoObserver:
    """Watches Kargo Stage CRDs and fires callbacks on promotion state changes."""

    def __init__(
        self,
        blackboard: "BlackboardState",
        failure_callback: Optional[Callable[..., Awaitable[None]]] = None,
        recovery_callback: Optional[Callable[..., Awaitable[None]]] = None,
        broadcast_callback: Optional[Callable[..., Awaitable[None]]] = None,
    ):
        self.blackboard = blackboard
        self.failure_callback = failure_callback
        self.recovery_callback = recovery_callback
        self.broadcast_callback = broadcast_callback

        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._k8s_available = False
        self._custom_api: Any = None
        self._resource_version: str = ""

        self._reported_failures: dict[str, str] = {}
        self._active_watches: dict[str, str] = {}
        self._failure_details: dict[str, dict] = {}
        self._current_watch: Any = None

    async def start(self) -> None:
        if self._running:
            logger.warning("KargoObserver already running")
            return
        if not await self._init_k8s_client():
            logger.warning("KargoObserver disabled: K8s client not available")
            return

        await self._initial_sync()
        await self._fire_broadcast()
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info(
            "KargoObserver started: watching stages cluster-wide "
            f"(initial failures={len(self._reported_failures)})"
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
        logger.info("KargoObserver stopped")

    def register_active_watch(self, stage_key: str, service: str) -> None:
        self._active_watches[stage_key] = service

    def get_failed_stages(self) -> list[dict]:
        """Return current failure snapshots for dashboard broadcast."""
        return list(self._failure_details.values())

    async def _fire_broadcast(self) -> None:
        """Send current failed stages snapshot to dashboard clients."""
        if self.broadcast_callback:
            try:
                await self.broadcast_callback()
            except Exception as e:
                logger.error(f"KargoObserver broadcast_callback error: {e}")

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
            self._custom_api = client.CustomObjectsApi()
            self._k8s_available = True
            return True
        except ImportError:
            logger.warning("kubernetes package not installed")
            return False
        except Exception as e:
            logger.error(f"Failed to initialize K8s client for Kargo: {e}")
            return False

    async def _initial_sync(self) -> None:
        """List all stages, record currently Errored ones without firing callbacks."""
        self._failure_details.clear()
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._custom_api.list_cluster_custom_object(
                    group=KARGO_GROUP, version=KARGO_VERSION, plural=KARGO_PLURAL,
                ),
            )
            self._resource_version = result.get("metadata", {}).get("resourceVersion", "")
            for stage in result.get("items", []):
                await self._process_stage(stage, suppress_callbacks=True)
            logger.info(
                f"KargoObserver initial sync: rv={self._resource_version}, "
                f"errored={len(self._reported_failures)}"
            )
        except Exception as e:
            logger.error(f"KargoObserver initial sync failed: {e}")

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
                logger.info(f"KargoObserver watch starting (rv={self._resource_version})")
                kwargs: dict[str, Any] = {
                    "group": KARGO_GROUP, "version": KARGO_VERSION,
                    "plural": KARGO_PLURAL, "timeout_seconds": 300,
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
                        logger.warning(f"KargoObserver queue read error: {e}")
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
                        await self._process_stage(obj)

                w.stop()
                self._current_watch = None
            except ApiException as e:
                if e.status == 410:
                    logger.warning("KargoObserver watch 410 Gone -- re-listing")
                    self._resource_version = ""
                    await self._initial_sync()
                    await self._fire_broadcast()
                    retry_delay = 1
                    continue
                logger.warning(f"KargoObserver watch API error ({e.status}): {e.reason}")
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning(f"KargoObserver watch error: {e}")

            if not self._running:
                break
            logger.info(f"KargoObserver reconnecting in {retry_delay}s")
            try:
                await asyncio.sleep(retry_delay)
            except asyncio.CancelledError:
                break
            retry_delay = min(retry_delay * 2, 30)

    async def _process_stage(self, stage: dict, suppress_callbacks: bool = False) -> None:
        ns = stage.get("metadata", {}).get("namespace", "")
        name = stage.get("metadata", {}).get("name", "")
        status = stage.get("status", {})
        last_promo = status.get("lastPromotion", {})
        if not last_promo:
            return

        promo_status = last_promo.get("status", {})
        phase = promo_status.get("phase", "")
        promo_name = last_promo.get("name", "")
        if not phase or not promo_name:
            return

        stage_key = f"{ns}/{name}"

        if phase in FAILED_PHASES:
            if self._reported_failures.get(stage_key) != promo_name:
                self._reported_failures[stage_key] = promo_name
                service = f"{name}@{ns}"
                failed_step = self._extract_failed_step(promo_status)
                mr_url = self._extract_mr_url(promo_status)
                freight_name = last_promo.get("freight", {}).get("name", "")
                message = promo_status.get("message", "")
                started = promo_status.get("startedAt", "")
                finished = promo_status.get("finishedAt", "")
                self._failure_details[stage_key] = {
                    "project": ns, "stage": name, "promotion": promo_name,
                    "freight": freight_name, "phase": phase, "message": message,
                    "failed_step": failed_step, "mr_url": mr_url,
                    "service": service, "started_at": started, "finished_at": finished,
                }
                if not suppress_callbacks and self.failure_callback:
                    try:
                        await self.failure_callback(
                            service=service, project=ns, stage=name,
                            promotion=promo_name, freight=freight_name,
                            phase=phase, message=message,
                            failed_step=failed_step, mr_url=mr_url,
                            started_at=started, finished_at=finished,
                        )
                        self._active_watches[stage_key] = service
                    except Exception as e:
                        logger.error(f"KargoObserver failure_callback error for {stage_key}: {e}")
                if not suppress_callbacks:
                    await self._fire_broadcast()

        elif phase == "Succeeded" and stage_key in self._active_watches:
            prev_promo = self._reported_failures.get(stage_key, "")
            if promo_name != prev_promo:
                service = self._active_watches[stage_key]
                if not suppress_callbacks and self.recovery_callback:
                    try:
                        await self.recovery_callback(
                            service=service, project=ns,
                            stage=name, promotion=promo_name,
                        )
                    except Exception as e:
                        logger.error(f"KargoObserver recovery_callback error for {stage_key}: {e}")
                self._reported_failures.pop(stage_key, None)
                self._failure_details.pop(stage_key, None)
                if not suppress_callbacks:
                    await self._fire_broadcast()
                self._active_watches.pop(stage_key, None)

    async def get_stage_status(self, project: str, stage: str) -> dict:
        """On-demand read for Brain's refresh_kargo_context tool."""
        if not self._k8s_available:
            return {"error": "K8s client not available"}
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._custom_api.get_namespaced_custom_object(
                    group=KARGO_GROUP, version=KARGO_VERSION,
                    namespace=project, plural=KARGO_PLURAL, name=stage,
                ),
            )
            status = result.get("status", {})
            last_promo = status.get("lastPromotion", {})
            promo_status = last_promo.get("status", {})
            return {
                "project": project,
                "stage": stage,
                "promotion": last_promo.get("name", ""),
                "freight": last_promo.get("freight", {}).get("name", ""),
                "phase": promo_status.get("phase", ""),
                "message": promo_status.get("message", ""),
                "failed_step": self._extract_failed_step(promo_status),
                "started_at": promo_status.get("startedAt", ""),
                "finished_at": promo_status.get("finishedAt", ""),
                "mr_url": self._extract_mr_url(promo_status),
            }
        except Exception as e:
            logger.error(f"KargoObserver get_stage_status failed for {project}/{stage}: {e}")
            return {"error": str(e), "project": project, "stage": stage}

    @staticmethod
    def _extract_failed_step(promo_status: dict) -> str:
        for step in promo_status.get("stepExecutionMetadata", []):
            if step.get("status") == "Errored":
                return step.get("alias", "unknown")
        return ""

    @staticmethod
    def _extract_mr_url(promo_status: dict) -> str:
        state = promo_status.get("state", {})
        for key in ("open-mr", "open_mr"):
            pr_data = state.get(key, {})
            if isinstance(pr_data, dict):
                pr = pr_data.get("pr", {})
                if isinstance(pr, dict) and pr.get("url"):
                    return pr["url"]
        return ""
