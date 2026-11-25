# BlackBoard/src/observers/flow_collector.py
# @ai-rules:
# 1. [Constraint]: Lives in src/observers/ because it writes to Redis (forbidden in src/scheduling/).
# 2. [Pattern]: External observer — reads scheduler.metrics (pull-only public API) + blackboard state.
# 3. [Gotcha]: Must survive Redis errors — try/except per cycle, log + continue.
# 4. [Pattern]: Maintains _prev_* counters for delta computation across snapshots.
# 5. [Constraint]: No Brain logic. No LLM. Pure data collection + persistence. TokenMeter / QuotaTracker via DI is permitted (counters, not LLM code).
# 6. [Pattern]: aligner.pending_count is a sync property (in-memory counter) read unawaited — mirrors headhunter.pending_count pattern.
# 7. [Pattern]: quota_tracker / quota_registry support either an instance or lazy getter callable so FlowCollector sees QuotaTracker / QuotaPoolRegistry once initialized.
"""FlowCollector: periodic snapshot of system flow health, persisted to Redis."""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from ..agents.agent_registry import AgentRegistry
    from ..agents.aligner import Aligner
    from ..agents.ephemeral_provisioner import EphemeralProvisioner
    from ..agents.headhunter import Headhunter
    from ..agents.jenkins_observer import JenkinsObserver
    from ..agents.llm.quota_registry import QuotaPoolRegistry
    from ..agents.llm.quota_tracker import QuotaTracker
    from ..agents.llm.token_meter import TokenMeter
    from ..scheduling.reconciler import ReconcileScheduler
    from ..state.blackboard import BlackboardState

from ..models import (
    FLOW_QUOTA_SHED_TIER1_KEY,
    FLOW_QUOTA_SHED_TIER2_KEY,
    FlowSnapshot,
)
from ..state.wip_meta import count_interactive_sessions, fetch_active_events_meta, is_automated_wip_event

logger = logging.getLogger(__name__)


class FlowCollector:
    """Collects flow health snapshots every interval and persists to Redis."""

    def __init__(
        self,
        scheduler: "ReconcileScheduler",
        blackboard: "BlackboardState",
        registry: "AgentRegistry | None" = None,
        headhunter: "Headhunter | None" = None,
        aligner: "Aligner | None" = None,
        jenkins_observer: "JenkinsObserver | None" = None,
        provisioner: "EphemeralProvisioner | None" = None,
        token_meter: "TokenMeter | None" = None,
        quota_tracker: "QuotaTracker | Callable[[], QuotaTracker | None] | None" = None,
        quota_registry: "QuotaPoolRegistry | Callable[[], QuotaPoolRegistry | None] | None" = None,
        interval: float = 60.0,
    ):
        self._scheduler = scheduler
        self._blackboard = blackboard
        self._registry = registry
        self._headhunter = headhunter
        self._aligner = aligner
        self._jenkins_observer = jenkins_observer
        self._provisioner = provisioner
        self._token_meter = token_meter
        self._quota_tracker = quota_tracker
        self._quota_registry = quota_registry
        self._interval = interval
        self._task: asyncio.Task | None = None
        self._running = False
        self._prev_reconcile_count = 0
        self._prev_error_count = 0
        self._prev_quota_throttles = 0

    async def start(self) -> None:
        if self._task is not None:
            return
        self._running = True
        self._task = asyncio.create_task(self._collect_loop(), name="flow-collector")
        logger.info("FlowCollector started (interval=%ds)", int(self._interval))

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("FlowCollector stopped")

    async def _collect_loop(self) -> None:
        while self._running:
            try:
                snapshot = await self._build_snapshot()
                await self._blackboard.persist_flow_snapshot(snapshot)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                logger.warning("FlowCollector: snapshot failed, skipping: %s", e)
            await asyncio.sleep(self._interval)

    async def _build_snapshot(self) -> FlowSnapshot:
        metrics = self._scheduler.metrics
        now = time.time()

        # Delta computation (guard against counter reset producing negative deltas)
        current_reconcile = metrics.get("reconcile_count", 0)
        current_errors = metrics.get("error_count", 0)
        if current_reconcile < self._prev_reconcile_count:
            self._prev_reconcile_count = 0
        if current_errors < self._prev_error_count:
            self._prev_error_count = 0
        reconcile_delta = current_reconcile - self._prev_reconcile_count
        error_delta = current_errors - self._prev_error_count
        self._prev_reconcile_count = current_reconcile
        self._prev_error_count = current_errors

        # Queue depth + active event count from blackboard (O(1) Redis ops)
        flow = await self._blackboard.get_flow_metrics()

        # Event status + age + WIP computation (single 2-RTT pipeline metadata, zero get_event fan-out)
        meta_map = await fetch_active_events_meta(self._blackboard)
        deferred_count = sum(1 for m in meta_map.values() if m.status == "deferred")
        wip_used_raw = sum(1 for m in meta_map.values() if is_automated_wip_event(m, include_new=False))
        active_user_sessions = count_interactive_sessions(meta_map)
        wip_cap = int(os.getenv("MAX_ACTIVE_EVENTS", "20"))

        ages = [now - m.queued_at for m in meta_map.values() if m.queued_at is not None]
        cycles = [m.atdd_cycle_sec for m in meta_map.values() if m.atdd_cycle_sec is not None]

        avg_age = sum(ages) / len(ages) if ages else 0.0
        avg_cycle = sum(cycles) / len(cycles) if cycles else None

        tampering_strikes = 0
        try:
            val = await self._blackboard.redis.get("darwin:flow:tampering_strikes")
            if val:
                tampering_strikes = int(val)
        except Exception:
            pass

        # Agent stats from registry
        busy = 0
        idle = 0
        try:
            if self._registry:
                agents = await self._registry.list_agents()
                for a in agents:
                    if a.get("busy"):
                        busy += 1
                    else:
                        idle += 1
        except Exception as e:
            logger.debug("FlowCollector: agent stats unavailable: %s", e)

        # Subscription count from state watcher (if available via blackboard)
        active_subs = 0
        try:
            active_subs = metrics.get("active_subscriptions", 0)
        except Exception:
            pass

        hh_pending = 0
        hh_gitlab_pending = 0
        hh_github_pending = 0
        hh_gitlab_breaker = "closed"
        hh_github_breaker = "closed"
        try:
            if self._headhunter:
                hh_pending = self._headhunter.pending_count
                hh_gitlab_pending = self._headhunter.gitlab_pending_count
                hh_github_pending = self._headhunter.github_pending_count
                hh_gitlab_breaker = self._headhunter.gitlab_breaker_state
                hh_github_breaker = self._headhunter.github_breaker_state
        except Exception:
            pass

        aligner_pending = 0
        try:
            if self._aligner:
                aligner_pending = self._aligner.pending_count
        except Exception:
            pass

        jenkins_pending = 0
        jenkins_breaker_open = False
        jenkins_view_unhealthy = False
        try:
            if self._jenkins_observer:
                jenkins_pending = self._jenkins_observer.pending_count
                jenkins_breaker_open = self._jenkins_observer.breaker_open
                jenkins_view_unhealthy = self._jenkins_observer.view_unhealthy
        except Exception:
            pass

        dispatch_total = 0
        dispatch_success_rate_pct = 100.0
        dispatch_infra_fails = 0
        dispatch_circuit_breaks = 0
        avg_spawn_latency_sec = 0.0
        try:
            if self._provisioner:
                dm = self._provisioner.dispatch_metrics
                dispatch_total = dm.total
                dispatch_success_rate_pct = dm.success_rate_pct
                dispatch_infra_fails = dm.infra_fail
                dispatch_circuit_breaks = dm.circuit_break
                avg_spawn_latency_sec = dm.avg_spawn_latency_sec
        except Exception:
            pass

        q_stats = self._collect_quota_stats()
        (
            tpm_used, tpm_limit, tpm_util, quota_throttle_delta,
            peak_pool_util, gem_used, gem_lim, claude_used, claude_lim, enmaas_used, enmaas_lim,
        ) = q_stats

        # Quota shedding telemetry counters
        quota_shed_tier1 = 0
        quota_shed_tier2 = 0
        try:
            if hasattr(self._blackboard, "redis") and self._blackboard.redis:
                r = self._blackboard.redis
                if hasattr(r, "mget"):
                    vals = await r.mget([FLOW_QUOTA_SHED_TIER1_KEY, FLOW_QUOTA_SHED_TIER2_KEY])
                    if isinstance(vals, (list, tuple)) and len(vals) == 2:
                        if vals[0]:
                            quota_shed_tier1 = int(vals[0])
                        if vals[1]:
                            quota_shed_tier2 = int(vals[1])
                    else:
                        r1 = await r.get(FLOW_QUOTA_SHED_TIER1_KEY)
                        if r1:
                            quota_shed_tier1 = int(r1)
                        r2 = await r.get(FLOW_QUOTA_SHED_TIER2_KEY)
                        if r2:
                            quota_shed_tier2 = int(r2)
                else:
                    r1 = await r.get(FLOW_QUOTA_SHED_TIER1_KEY)
                    if r1:
                        quota_shed_tier1 = int(r1)
                    r2 = await r.get(FLOW_QUOTA_SHED_TIER2_KEY)
                    if r2:
                        quota_shed_tier2 = int(r2)
        except Exception:
            pass

        # Token meter: snapshot_with_callers() atomically drains aggregate + per-caller intervals
        if self._token_meter:
            token_snap, by_caller = self._token_meter.snapshot_with_callers()
            platform_totals = self._token_meter.get_platform_totals()
            by_provider = (
                self._token_meter.last_interval_by_provider()
                if hasattr(self._token_meter, "last_interval_by_provider")
                else {}
            )
        else:
            token_snap, by_caller, platform_totals, by_provider = {}, {}, {}, {}
        brain_snap = by_caller.get("brain", {})
        if by_provider:
            claude_token_total_delta = (
                int(by_provider.get("vertex_claude", {}).get("total_tokens", 0) or 0)
                + int(by_provider.get("enmaas", {}).get("total_tokens", 0) or 0)
            )
        else:
            claude_token_total_delta = sum(
                int(v.get("total_tokens", 0) or 0)
                for k, v in by_caller.items()
                if k in ("archivist", "headhunter_jira", "sidecar:claude")
            )
        sidecar_token_total_delta = sum(
            int(v.get("total_tokens", 0) or 0)
            for k, v in by_caller.items()
            if k.startswith("sidecar:")
        )

        return FlowSnapshot(
            timestamp=now,
            queue_depth=flow["queue_depth"],
            active_events=len(meta_map),
            deferred_events=deferred_count,
            waiting_approval_events=flow.get("waiting_approval_events", 0),
            headhunter_pending=hh_pending,
            headhunter_gitlab_pending=hh_gitlab_pending,
            headhunter_github_pending=hh_github_pending,
            headhunter_gitlab_breaker=hh_gitlab_breaker,
            headhunter_github_breaker=hh_github_breaker,
            aligner_pending=aligner_pending,
            jenkins_pending=jenkins_pending,
            jenkins_breaker_open=jenkins_breaker_open,
            jenkins_view_unhealthy=jenkins_view_unhealthy,
            wip_used=wip_used_raw,
            wip_cap=wip_cap,
            wip_utilization_pct=round(wip_used_raw / wip_cap * 100, 1) if wip_cap > 0 else 0.0,
            wip_available=max(0, wip_cap - wip_used_raw),
            busy_agents=busy,
            idle_agents=idle,
            active_subscriptions=active_subs,
            avg_event_age_sec=round(avg_age, 1),
            avg_reconcile_ms=metrics.get("avg_reconcile_ms", 0.0),
            reconcile_count_delta=reconcile_delta,
            error_count_delta=error_delta,
            dispatch_total=dispatch_total,
            dispatch_success_rate_pct=dispatch_success_rate_pct,
            dispatch_infra_fails=dispatch_infra_fails,
            dispatch_circuit_breaks=dispatch_circuit_breaks,
            avg_spawn_latency_sec=avg_spawn_latency_sec,
            token_input_delta=token_snap.get("input_tokens", 0),
            token_output_delta=token_snap.get("output_tokens", 0),
            token_thinking_delta=token_snap.get("thinking_tokens", 0),
            token_cached_delta=token_snap.get("cached_tokens", 0),
            token_tool_use_delta=token_snap.get("tool_use_tokens", 0),
            token_total_delta=token_snap.get("total_tokens", 0),
            token_calls_delta=token_snap.get("calls", 0),
            token_total_cumulative=platform_totals.get("total_tokens", 0),
            brain_token_input_delta=brain_snap.get("input_tokens", 0),
            brain_token_cached_delta=brain_snap.get("cached_tokens", 0),
            tpm_used=tpm_used,
            tpm_limit=tpm_limit,
            tpm_utilization_pct=tpm_util,
            quota_throttle_delta=quota_throttle_delta,
            tampering_strikes=tampering_strikes,
            quota_shed_tier1_total=quota_shed_tier1,
            quota_shed_tier2_total=quota_shed_tier2,
            atdd_cycle_sec=avg_cycle,
            active_user_sessions=active_user_sessions,
            peak_pool_utilization_pct=peak_pool_util,
            gemini_tpm_used=gem_used,
            gemini_tpm_limit=gem_lim,
            claude_tpm_used=claude_used,
            claude_tpm_limit=claude_lim,
            enmaas_tpm_used=enmaas_used,
            enmaas_tpm_limit=enmaas_lim,
            claude_token_total_delta=claude_token_total_delta,
            sidecar_token_total_delta=sidecar_token_total_delta,
        )

    def _collect_quota_stats(self) -> tuple[int, int, float, int, float, int, int, int, int, int, int]:
        """Read QuotaPoolRegistry (or legacy QuotaTracker) rolling 60s usage, limits, and throttles."""
        zero = (0, 0, 0.0, 0, 0.0, 0, 0, 0, 0, 0, 0)
        try:
            reg = None
            if self._quota_registry is not None:
                reg = (
                    self._quota_registry
                    if hasattr(self._quota_registry, "get_all_stats")
                    else (self._quota_registry() if callable(self._quota_registry) else None)
                )
            if reg is not None:
                all_stats = reg.get_all_stats()
                g = all_stats["global"]
                pools = all_stats["pools"]
                enmaas_active = bool(all_stats.get("enmaas_active", False))
                gem = pools.get("vertex_gemini", {})
                cld = pools.get("vertex_claude", {})
                enm = pools.get("enmaas", {})
                current_throttles = int(g.get("throttle_events", 0) or 0)
                if current_throttles < self._prev_quota_throttles:
                    self._prev_quota_throttles = 0
                throttle_delta = current_throttles - self._prev_quota_throttles
                self._prev_quota_throttles = current_throttles
                return (
                    int(g.get("tokens_used_60s", 0) or 0),
                    int(g.get("tpm_limit", 0) or 0),
                    float(g.get("utilization_pct", 0.0) or 0.0),
                    throttle_delta,
                    float(g.get("peak_pool_utilization_pct", 0.0) or 0.0),
                    int(gem.get("tokens_used_60s", 0) or 0),
                    int(gem.get("tpm_limit", 0) or 0),
                    int(cld.get("tokens_used_60s", 0) or 0),
                    int(cld.get("tpm_limit", 0) or 0),
                    int(enm.get("tokens_used_60s", 0) or 0),
                    int(enm.get("tpm_limit", 0) or 0) if enmaas_active else 0,
                )

            if self._quota_tracker is None:
                return zero
            tracker = (
                self._quota_tracker
                if hasattr(self._quota_tracker, "get_stats")
                else (self._quota_tracker() if callable(self._quota_tracker) else None)
            )
            if tracker is None:
                return zero
            stats = tracker.get_stats()
            if not isinstance(stats, dict):
                return zero
            tokens_used = int(stats.get("tokens_used_60s", 0) or 0)
            tpm_limit = int(stats.get("tpm_limit", 0) or 0)
            utilization_pct = float(stats.get("utilization_pct", 0.0) or 0.0)
            current_throttles = int(stats.get("throttle_events", 0) or 0)
            if current_throttles < self._prev_quota_throttles:
                self._prev_quota_throttles = 0
            throttle_delta = current_throttles - self._prev_quota_throttles
            self._prev_quota_throttles = current_throttles
            return (tokens_used, tpm_limit, utilization_pct, throttle_delta, utilization_pct, tokens_used, tpm_limit, 0, 0, 0, 0)
        except Exception as e:
            logger.debug("FlowCollector: quota stats unavailable: %s", e)
            return zero
