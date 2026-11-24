# BlackBoard/src/observers/kargo.py
# @ai-rules:
# 1. [Pattern]: K8s Watch with exponential backoff (1s-30s). Matches KargoWatchAdapter in payloads service.
# 2. [Pattern]: Initial sync on start() records promotion & verification failures into _reported_failures WITHOUT callbacks.
# 3. [Pattern]: 410 Gone triggers full re-list with fresh resource_version.
#    _initial_sync() clears-then-repopulates ONLY on success. Failed K8s API call preserves previous state.
# 4. [Constraint]: Callbacks are async -- never raise into the watch loop. Wrap in try/except; set _active_watches inside try.
# 5. [Pattern]: _process_stage() detects promotion failures (dedup: promo_name) and post-promotion verification failures
#    (Failed/Error/Inconclusive, dedup: verification:<id>; Aborted/Pending/Running held); recovery is verification-gated.
# 6. [Pattern]: _process_stage() evaluates terminal lastPromotion + freightHistory[0] (keeping failed stages in Ops sidebar during retries), while get_stage_status() and poll_kargo_stage_status() share project_stage_status() preferring active currentPromotion.
"""
Kargo Stage Observer -- watches promotion and verification state via K8s Watch API.

Detects failed promotions and post-promotion verification failures, reporting them to Aligner.
Detects verification-gated recovery and notifies active events.
Provides on-demand stage status reads and StateWatcher polls for Brain verification.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING, Any, Callable, Awaitable, Optional

from .kargo_helpers import (
    PROMOTION_FAILED_PHASES,
    VERIFICATION_FAILED_PHASES,
    VERIFICATION_HOLD_PHASES,
    _s,
    build_verification_dedup_key,
    extract_latest_verification,
    is_verification_stale,
    project_stage_status,
    resolve_stage_freight,
)

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

KARGO_OBSERVER_ENABLED = os.getenv("KARGO_OBSERVER_ENABLED", "false").lower() == "true"
KARGO_GROUP = "kargo.akuity.io"
KARGO_VERSION = "v1alpha1"
KARGO_PLURAL = "stages"
FAILED_PHASES = PROMOTION_FAILED_PHASES


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
            logger.error(f"Failed to initialize K8s client for Kargo: {e}")
            return False

    async def _initial_sync(self) -> None:
        """List all stages, record currently Errored ones without firing callbacks.

        Builds new state in temporary dicts and swaps on success. A failed K8s API
        call preserves the previous state instead of leaving _failure_details empty.
        """
        prev_failures = self._reported_failures.copy()
        prev_details = self._failure_details.copy()
        prev_watches = self._active_watches.copy()
        try:
            result = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._custom_api.list_cluster_custom_object(
                    group=KARGO_GROUP, version=KARGO_VERSION, plural=KARGO_PLURAL,
                ),
            )
            new_rv = result.get("metadata", {}).get("resourceVersion", "")
            self._reported_failures.clear()
            self._failure_details.clear()
            for stage in result.get("items", []):
                await self._process_stage(stage, suppress_callbacks=True)
            for sk in list(self._active_watches):
                if sk not in self._reported_failures:
                    self._active_watches.pop(sk, None)
            self._resource_version = new_rv
            logger.info(
                f"KargoObserver initial sync: rv={self._resource_version}, "
                f"errored={len(self._reported_failures)}"
            )
        except Exception as e:
            self._reported_failures.clear()
            self._reported_failures.update(prev_failures)
            self._failure_details.clear()
            self._failure_details.update(prev_details)
            self._active_watches.clear()
            self._active_watches.update(prev_watches)
            logger.error(f"KargoObserver initial sync failed (previous state preserved): {e}")

    async def _watch_loop(self) -> None:
        from kubernetes import watch
        from kubernetes.client.exceptions import ApiException
        import queue as _queue

        def _put_bounded(q: _queue.Queue, item: Any) -> None:
            try:
                q.put_nowait(item)
            except _queue.Full:
                try:
                    q.get_nowait()
                except _queue.Empty:
                    pass
                try:
                    q.put_nowait(item)
                except _queue.Full:
                    pass

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

                event_q: _queue.Queue = _queue.Queue(maxsize=1000)

                def _run_watch() -> None:
                    try:
                        for event in w.stream(
                            self._custom_api.list_cluster_custom_object, **kwargs,
                        ):
                            _put_bounded(event_q, event)
                    except Exception as e:
                        _put_bounded(event_q, e)
                    finally:
                        _put_bounded(event_q, None)

                loop = asyncio.get_running_loop()
                loop.run_in_executor(None, _run_watch)
                retry_delay = 1

                try:
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
                        try:
                            if event_type in ("ADDED", "MODIFIED"):
                                await self._process_stage(obj)
                            elif event_type == "DELETED":
                                await self._handle_deleted_stage(obj)
                        except Exception as e:
                            logger.error(f"KargoObserver event dispatch error: {e}")
                finally:
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

    async def _handle_deleted_stage(self, stage: dict) -> None:
        if not isinstance(stage, dict):
            return
        meta = stage.get("metadata") if isinstance(stage.get("metadata"), dict) else {}
        ns, name = _s(meta.get("namespace")), _s(meta.get("name"))
        if not ns or not name:
            return
        stage_key = f"{ns}/{name}"
        self._reported_failures.pop(stage_key, None)
        self._active_watches.pop(stage_key, None)
        removed = self._failure_details.pop(stage_key, None)
        if removed is not None:
            await self._fire_broadcast()

    async def _record_failure(self, *, stage_key: str, dedup_key: str, details: dict, suppress_callbacks: bool) -> None:
        self._failure_details[stage_key] = details
        if not suppress_callbacks and self.failure_callback:
            try:
                await self.failure_callback(**details)
                self._reported_failures[stage_key] = dedup_key
                self._active_watches[stage_key] = details["service"]
            except Exception as e:
                self._reported_failures.pop(stage_key, None)
                logger.error(f"KargoObserver failure_callback error for {stage_key}: {e}")
        else:
            self._reported_failures[stage_key] = dedup_key
        if not suppress_callbacks:
            await self._fire_broadcast()

    async def _process_stage(self, stage: dict, suppress_callbacks: bool = False) -> None:
        if not isinstance(stage, dict):
            return
        meta = stage.get("metadata") if isinstance(stage.get("metadata"), dict) else {}
        ns = _s(meta.get("namespace"))
        name = _s(meta.get("name"))
        if not ns or not name:
            return

        status = stage.get("status") if isinstance(stage.get("status"), dict) else {}
        last_promo = status.get("lastPromotion") if isinstance(status.get("lastPromotion"), dict) else {}
        promo_status = last_promo.get("status") if isinstance(last_promo.get("status"), dict) else {}
        promo_phase = _s(promo_status.get("phase"))
        promo_name = _s(last_promo.get("name"))
        stage_key = f"{ns}/{name}"
        service = f"{name}@{ns}"

        # Priority 1: Promotion failure (dedup on unprefixed promo_name)
        if promo_name and promo_phase in FAILED_PHASES:
            if self._reported_failures.get(stage_key) != promo_name:
                failed_step = self._extract_failed_step(promo_status)
                mr_url = self._extract_mr_url(promo_status)
                freight_name = resolve_stage_freight(status, last_promo, {})
                message = _s(promo_status.get("message"))
                started = _s(promo_status.get("startedAt"))
                finished = _s(promo_status.get("finishedAt"))
                details = {
                    "project": ns, "stage": name, "promotion": promo_name,
                    "freight": freight_name, "phase": promo_phase, "message": message,
                    "failed_step": failed_step, "mr_url": mr_url,
                    "service": service, "started_at": started, "finished_at": finished,
                    "failure_type": "promotion", "verification_id": "", "analysis_run": "",
                }
                await self._record_failure(stage_key=stage_key, dedup_key=promo_name, details=details, suppress_callbacks=suppress_callbacks)
            return

        # Extract latest verification & stale-freight guard
        verif = extract_latest_verification(status)
        if is_verification_stale(last_promo, verif):
            return

        verif_phase = verif.get("phase", "")

        # Priority 2: Verification failure (Failed/Error/Inconclusive; dedup on verification:<id>)
        if verif_phase in VERIFICATION_FAILED_PHASES:
            dedup_key = build_verification_dedup_key(verif, promo_name)
            if self._reported_failures.get(stage_key) != dedup_key:
                freight_name = resolve_stage_freight(status, last_promo, verif)
                mr_url = self._extract_mr_url(promo_status)
                verif_msg = verif["message"]
                verif_id = verif["id"]
                analysis_run = verif["analysis_run"]
                started = verif["start_time"]
                finished = verif["finish_time"]
                details = {
                    "project": ns, "stage": name, "promotion": promo_name,
                    "freight": freight_name, "phase": verif_phase, "message": verif_msg,
                    "failed_step": "", "mr_url": mr_url,
                    "service": service, "started_at": started, "finished_at": finished,
                    "failure_type": "verification", "verification_id": verif_id,
                    "analysis_run": analysis_run,
                }
                await self._record_failure(stage_key=stage_key, dedup_key=dedup_key, details=details, suppress_callbacks=suppress_callbacks)
            return

        # Priority 3: Hold on non-terminal or ignored verification phases (Pending/Running/Aborted)
        if verif_phase in VERIFICATION_HOLD_PHASES:
            return

        # Priority 4: Verification-gated recovery
        if stage_key in self._active_watches or stage_key in self._reported_failures:
            prev_key = self._reported_failures.get(stage_key, "")
            was_verification = prev_key.startswith("verification:")
            if was_verification:
                recovered = (
                    verif_phase == "Successful"
                    and build_verification_dedup_key(verif, promo_name) != prev_key
                )
            else:
                spec = stage.get("spec") if isinstance(stage.get("spec"), dict) else {}
                verif_ok = (verif_phase == "Successful") if verif else (not spec.get("verification"))
                recovered = (
                    promo_phase == "Succeeded"
                    and bool(promo_name)
                    and promo_name != prev_key
                    and verif_ok
                )
            if recovered:
                if stage_key in self._active_watches and not suppress_callbacks and self.recovery_callback:
                    try:
                        await self.recovery_callback(
                            service=self._active_watches[stage_key],
                            project=ns, stage=name, promotion=promo_name,
                            failure_type=("verification" if was_verification else "promotion"),
                            verification_id=verif.get("id", ""),
                        )
                    except Exception as e:
                        logger.error(f"KargoObserver recovery_callback error for {stage_key}: {e}")
                self._reported_failures.pop(stage_key, None)
                self._failure_details.pop(stage_key, None)
                self._active_watches.pop(stage_key, None)
                if not suppress_callbacks:
                    await self._fire_broadcast()

    async def get_stage_status(self, project: str, stage: str, promotion_id: str = "") -> dict:
        """On-demand read for Brain's refresh_kargo_context tool.

        When promotion_id is supplied, fetches that specific Promotion directly
        instead of reading lastPromotion from the Stage status. Otherwise,
        projects currentPromotion (active) over lastPromotion (completed) plus verification.
        """
        if not self._k8s_available:
            return {"error": "K8s client not available"}
        try:
            if promotion_id:
                promo_result = await asyncio.get_running_loop().run_in_executor(
                    None,
                    lambda: self._custom_api.get_namespaced_custom_object(
                        group=KARGO_GROUP, version=KARGO_VERSION,
                        namespace=project, plural="promotions", name=promotion_id,
                    ),
                )
                pr = promo_result if isinstance(promo_result, dict) else {}
                promo_status = pr.get("status") if isinstance(pr.get("status"), dict) else {}
                spec = pr.get("spec") if isinstance(pr.get("spec"), dict) else {}
                freight = spec.get("freight")
                promo_phase = _s(promo_status.get("phase"))
                return {
                    "project": project,
                    "stage": stage,
                    "promotion": promotion_id,
                    "freight": _s(freight.get("name")) if isinstance(freight, dict) else "",
                    "phase": promo_phase,
                    "message": _s(promo_status.get("message")),
                    "failed_step": self._extract_failed_step(promo_status),
                    "started_at": _s(promo_status.get("startedAt")),
                    "finished_at": _s(promo_status.get("finishedAt")),
                    "mr_url": self._extract_mr_url(promo_status),
                    "failure_type": "promotion",
                    "verification_id": "",
                    "analysis_run": "",
                    "_promo_status": promo_status,
                    "_verification": {},
                    "_promotion_phase": promo_phase,
                }

            result = await asyncio.get_running_loop().run_in_executor(
                None,
                lambda: self._custom_api.get_namespaced_custom_object(
                    group=KARGO_GROUP, version=KARGO_VERSION,
                    namespace=project, plural=KARGO_PLURAL, name=stage,
                ),
            )
            res = result if isinstance(result, dict) else {}
            status = res.get("status") if isinstance(res.get("status"), dict) else {}
            promo_is_current, promo, promo_status, active_verif = project_stage_status(status)
            promo_phase = _s(promo_status.get("phase"))
            is_verif_failure = (
                not promo_is_current
                and promo_phase not in FAILED_PHASES
                and active_verif.get("phase") in VERIFICATION_FAILED_PHASES
            )
            base = {
                "project": project,
                "stage": stage,
                "promotion": _s(promo.get("name")),
                "freight": resolve_stage_freight(status, promo, active_verif),
                "mr_url": self._extract_mr_url(promo_status),
                "verification_id": active_verif.get("id", ""),
                "analysis_run": active_verif.get("analysis_run", ""),
                "_promo_status": promo_status,
                "_verification": active_verif,
                "_promotion_phase": promo_phase,
            }
            if is_verif_failure:
                return {
                    **base,
                    "phase": active_verif["phase"],
                    "message": active_verif["message"],
                    "failed_step": "",
                    "started_at": active_verif["start_time"],
                    "finished_at": active_verif["finish_time"],
                    "failure_type": "verification",
                }
            return {
                **base,
                "phase": promo_phase,
                "message": _s(promo_status.get("message")),
                "failed_step": self._extract_failed_step(promo_status),
                "started_at": _s(promo_status.get("startedAt")),
                "finished_at": _s(promo_status.get("finishedAt")),
                "failure_type": "promotion",
            }
        except Exception as e:
            logger.error(f"KargoObserver get_stage_status failed for {project}/{stage}: {e}")
            return {"error": str(e), "project": project, "stage": stage}

    async def poll_kargo_stage_status(self, project: str, stage: str) -> dict:
        """Lightweight read-only poll. Returns only state_key fields.
        Does NOT fire callbacks. Used by StateWatcher.
        Raises on K8s errors so StateWatcher backoff engages."""
        if not self._k8s_available:
            raise RuntimeError("K8s client not available")
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: self._custom_api.get_namespaced_custom_object(
                group=KARGO_GROUP, version=KARGO_VERSION,
                namespace=project, plural=KARGO_PLURAL, name=stage,
            ),
        )
        res = result if isinstance(result, dict) else {}
        status = res.get("status") if isinstance(res.get("status"), dict) else {}
        _, _, promo_status, active_verif = project_stage_status(status)
        return self.extract_kargo_state_key(promo_status, verification=active_verif or None)

    @staticmethod
    def extract_kargo_state_key(promo_status: dict, verification: dict | None = None) -> dict:
        """Canonical state_key builder for Kargo subscriptions.
        Single source of truth -- used by both Brain (register) and poll adapter."""
        ps = promo_status if isinstance(promo_status, dict) else {}
        key = {
            "phase": _s(ps.get("phase")) or "unknown",
            "failed_step": KargoObserver._extract_failed_step(ps),
        }
        if isinstance(verification, dict) and _s(verification.get("phase")):
            key["verification_phase"] = _s(verification.get("phase"))
            key["verification_id"] = _s(verification.get("id"))
        return key

    @staticmethod
    def _extract_failed_step(promo_status: dict) -> str:
        if not isinstance(promo_status, dict):
            return ""
        steps = promo_status.get("stepExecutionMetadata")
        if not isinstance(steps, list):
            return ""
        for step in steps:
            if isinstance(step, dict) and step.get("status") in FAILED_PHASES:
                return _s(step.get("alias")) or "unknown"
        return ""

    @staticmethod
    def _extract_mr_url(promo_status: dict) -> str:
        if not isinstance(promo_status, dict):
            return ""
        state = promo_status.get("state")
        if not isinstance(state, dict):
            return ""
        for key in ("open-mr", "open_mr"):
            pr_data = state.get(key)
            if isinstance(pr_data, dict):
                pr = pr_data.get("pr")
                if isinstance(pr, dict) and isinstance(pr.get("url"), str) and pr["url"]:
                    return pr["url"]
        return ""
