# BlackBoard/src/observers/nightwatcher.py
# @ai-rules:
# 1. [Pattern]: Follows TimeKeeperObserver lifecycle -- in-process daemon with start/stop/cron loop.
# 2. [Pattern]: Analysis loop (review/investigate) is LLM-driven multi-turn. Report phase is code-driven shopping cart.
# 3. [Pattern]: Shopping cart: declare_clusters -> validate -> code-driven N iterations -> coverage gate -> summary.
# 4. [Constraint]: requeue_inflight() called on start() to recover from prior crash.
# 5. [Constraint]: MAX_ANALYSIS_ROUNDS caps the analysis loop. Report loop bounded by N declared clusters.
# 6. [Pattern]: Partial commit: successful events committed, failed cluster events restaged.
# 7. [Pattern]: Cart loop hydrates cluster links via extract_full_links from escalations_by_id before each iteration.
# 8. [Pattern]: Cart loop routes write_incident (new) vs extend_incident (existing) per cluster.extends_issue_key.
# 9. [Constraint]: extends_issue_key validation is fail-closed (search_succeeded flag). Invalid keys convert to new incidents.
# 10. [Constraint]: _sweep drains the backlog in bounded batches (NIGHTWATCHER_BATCH_SIZE x NIGHTWATCHER_MAX_BATCHES).
#     One ShiftReport per sweep: batches are merged cumulatively into the same date:window key.
# 11. [Constraint]: On quota/generic failure, events already in ctx.created_incidents are COMMITTED (Jira write is not
#     idempotent); only the uncommitted remainder is restaged. Never restage a member whose incident exists.
# 12. [Constraint]: auto_reconcile is enabled ONLY on the final declare_clusters attempt (_run_clustering_agent).
# 13. [Constraint]: The cart commits each cluster's members to Jira-done IMMEDIATELY after its incident is created (not at the end),
#     so a crash/SIGTERM/CancelledError later in the sweep cannot make requeue_inflight() re-file an existing incident.
# 14. [Gotcha]: INFLIGHT_TTL EXPIREs (deletes) the inflight SET after 1h -- it never requeues. Anything stranded there is lost unless
#     requeue_inflight() runs first (on start() or the failure-path fallback in _settle_failed_batch).
# 15. [Gotcha]: self._batch_ctx is per-sweep mutable state; safe only because _sweep() runs strictly sequentially (single poll loop).
"""
Nightwatcher Observer -- end-of-shift incident consolidation agent.

Cron-triggered (default 06:00/18:00 UTC). Leases pending escalations,
runs a phase-gated Gemini Flash tool-calling session to cluster and
consolidate, writes deduplicated incidents to Jira, posts a
shift summary to Slack, and persists a ShiftReport for the Shifts UI.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING, Awaitable, Callable, Optional

if TYPE_CHECKING:
    from ..adapters.jira_incident import JiraIncidentAdapter
    from ..agents.agent_registry import AgentRegistry
    from ..agents.archivist import Archivist
    from ..agents.ephemeral_provisioner import EphemeralProvisioner
    from ..agents.task_bridge import TaskBridge
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

MAX_ANALYSIS_ROUNDS = 30
MAX_DECLARE_RETRIES = 2
MAX_CART_RETRIES = 2
NIGHTWATCHER_SWEEP_CRON = os.getenv("NIGHTWATCHER_SWEEP_CRON", "0 6,18 * * *")
DEFAULT_BATCH_SIZE = 25
DEFAULT_MAX_BATCHES = 10
DEFAULT_BATCH_COOLDOWN_S = 30.0
DEFAULT_BATCH_TIMEOUT_S = 1800.0
SUMMARY_PROMPT_CHARS = 140


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    """Read an int env var.

    Unset/empty/non-numeric -> `default`. Numeric but below `minimum` -> clamped to `minimum`
    (NOT to `default`). Docs (helm values, deployment.md, 13-nightwatcher.mdc) and test T-1 mirror this.
    """
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Nightwatcher: invalid %s=%r, using default %d", name, raw, default)
        return default
    if value < minimum:
        logger.warning("Nightwatcher: %s=%d below minimum, clamping to %d", name, value, minimum)
        return minimum
    return value


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    raw = os.getenv(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError:
        logger.warning("Nightwatcher: invalid %s=%r, using default %s", name, raw, default)
        return default
    return max(minimum, value)

from .nightwatcher_tools import NightwatcherContext, execute_tool, get_phase_tools, validate_cluster_plan, build_report_tool, build_extend_tool, build_summary_tool, _handle_write_incident, _handle_extend_incident
from .nightwatcher_prompt import build_system_prompt, build_report_iteration_prompt, build_summary_prompt, extract_full_links


class NightwatcherObserver:
    """End-of-shift incident consolidation agent (Agent 6)."""

    def __init__(
        self,
        blackboard: "BlackboardState",
        registry: "AgentRegistry",
        bridge: "TaskBridge",
        provisioner: "Optional[EphemeralProvisioner]",
        incident_adapter: "Optional[JiraIncidentAdapter]",
        archivist: "Archivist",
        slack_notify=None,
        broadcast: "Callable[[dict], Awaitable[None]] | None" = None,
    ):
        self.blackboard = blackboard
        self._registry = registry
        self._bridge = bridge
        self._provisioner = provisioner
        self._incident_adapter = incident_adapter
        self._archivist = archivist
        self._slack_notify = slack_notify
        self._broadcast: "Callable[[dict], Awaitable[None]] | None" = broadcast
        self._adapter = None
        self._task: Optional[asyncio.Task] = None
        self._running = False
        self._batch_ctx: Optional[NightwatcherContext] = None

    async def start(self) -> None:
        if self._running:
            logger.warning("NightwatcherObserver already running")
            return
        requeued = await self.blackboard.requeue_inflight()
        if requeued:
            logger.warning("Nightwatcher: recovered %d inflight items on startup", requeued)
        self._running = True
        self._task = asyncio.create_task(self._poll_loop())
        logger.info("NightwatcherObserver started (cron=%s)", NIGHTWATCHER_SWEEP_CRON)

    async def stop(self) -> None:
        self._running = False
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("NightwatcherObserver stopped")

    async def _get_adapter(self):
        """Lazy-load LLM adapter (Gemini Flash for Nightwatcher)."""
        if self._adapter is None:
            try:
                from ..agents.llm import create_adapter
                project = os.getenv("GCP_PROJECT", "")
                location = os.getenv("GCP_LOCATION", "global")
                model = os.getenv("LLM_MODEL_NIGHTWATCHER", "gemini-3.7-flash")
                self._adapter = create_adapter("gemini", project, location, model)
                logger.info("Nightwatcher LLM adapter: gemini/%s", model)
            except Exception as e:
                logger.warning("Nightwatcher LLM adapter failed: %s", e)
        return self._adapter

    async def _poll_loop(self) -> None:
        from croniter import croniter
        cron = croniter(NIGHTWATCHER_SWEEP_CRON, time.time())
        while self._running:
            try:
                next_fire = cron.get_next(float)
                delay = max(0, next_fire - time.time())
                logger.info("Nightwatcher: next sweep at %s (in %.0fs)",
                            time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime(next_fire)), delay)
                await asyncio.sleep(delay)
                if not self._running:
                    break
                await self._sweep()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Nightwatcher sweep error")
                await asyncio.sleep(60)

    async def _sweep(self) -> None:
        from ..models import ShiftReport
        from datetime import datetime, timedelta, timezone

        sweep_start = time.time()
        now_utc = datetime.now(timezone.utc)
        shift_date = now_utc.strftime("%Y-%m-%d")
        window = "morning" if now_utc.hour < 12 else "evening"
        if window == "morning":
            ws = (now_utc - timedelta(days=1)).replace(hour=18, minute=0, second=0, microsecond=0)
        else:
            ws = now_utc.replace(hour=6, minute=0, second=0, microsecond=0)
        window_start = ws.isoformat()
        window_end = now_utc.isoformat()

        try:
            await self._archivist.digest_field_notes(self.blackboard)
        except Exception:
            logger.warning("Field notes digest failed (non-fatal)", exc_info=True)

        batch_size = _env_int("NIGHTWATCHER_BATCH_SIZE", DEFAULT_BATCH_SIZE)
        configured_min = _env_int("NIGHTWATCHER_MIN_PENDING", 1)
        min_pending = min(configured_min, batch_size)
        if min_pending != configured_min:
            logger.warning(
                "Nightwatcher: NIGHTWATCHER_MIN_PENDING=%d exceeds batch size %d, using %d",
                configured_min, batch_size, min_pending,
            )
        max_batches = _env_int("NIGHTWATCHER_MAX_BATCHES", DEFAULT_MAX_BATCHES)
        cooldown_s = _env_float("NIGHTWATCHER_BATCH_COOLDOWN_SECONDS", DEFAULT_BATCH_COOLDOWN_S)
        batch_timeout_s = _env_float("NIGHTWATCHER_BATCH_TIMEOUT_SECONDS", DEFAULT_BATCH_TIMEOUT_S, minimum=0.01)

        from ..agents.llm.quota_tracker import QuotaExhaustedError, RequestExceedsBurstError
        cumulative: "Optional[ShiftReport]" = None
        dispatch_cap = int(os.getenv("NIGHTWATCHER_DISPATCH_CAP", "3"))
        sweep_dispatch_count = 0

        for batch_no in range(1, max_batches + 1):
            escalations, json_members = await self.blackboard.lease_pending_escalations(
                time.time(), limit=batch_size
            )
            pending_count = len(escalations)
            logger.info("Nightwatcher sweep batch %d/%d: %d pending escalations",
                        batch_no, max_batches, pending_count)

            if pending_count == 0 or pending_count < min_pending:
                if json_members:
                    await self.blackboard.requeue_inflight()
                if cumulative is None:
                    report = ShiftReport(
                        shift_date=shift_date, window=window,
                        window_start=window_start, window_end=window_end,
                        status="empty", started_at=sweep_start, completed_at=time.time(),
                    )
                    await self.blackboard.persist_shift_report(report)
                return

            adapter = await self._get_adapter()
            if not adapter:
                logger.error("Nightwatcher: no LLM adapter, requeueing %d escalations", pending_count)
                await self.blackboard.requeue_inflight()
                return

            system_prompt = build_system_prompt(escalations, window_start, window_end)
            self._batch_ctx = None
            try:
                # Refresh inflight TTL at the start of each batch so multi-batch sweeps do not expire
                if hasattr(self.blackboard, "refresh_inflight_ttl"):
                    await self.blackboard.refresh_inflight_ttl()

                async with asyncio.timeout(batch_timeout_s):
                    contents, ctx = await self._run_analysis_loop(
                        escalations, json_members, system_prompt,
                        window_start, window_end, shift_date, window,
                        sweep_start, pending_count,
                        dispatch_count=sweep_dispatch_count, dispatch_cap=dispatch_cap,
                    )
                    sweep_dispatch_count = ctx.dispatch_count
                    if hasattr(self.blackboard, "refresh_inflight_ttl"):
                        await self.blackboard.refresh_inflight_ttl()
                    cumulative = await self._run_report_cart(
                        ctx, contents, json_members, escalations, system_prompt,
                        shift_date, window, window_start, window_end,
                        sweep_start, pending_count, prior_report=cumulative,
                    )
            except TimeoutError:
                logger.error("Nightwatcher batch %d timed out after %.1fs (circuit breaker triggered)", batch_no, batch_timeout_s)
                await self._notify_ops(
                    f":warning: Nightwatcher batch {batch_no} timed out after {batch_timeout_s:.0f}s. "
                    f"Settling batch and restaging non-committed events before inflight TTL expiration."
                )
                await self._settle_failed_batch(
                    "failed", json_members, escalations, cumulative,
                    shift_date, window, window_start, window_end, sweep_start, requeue_all=False,
                )
                return
            except RequestExceedsBurstError as be:
                # PERMANENT for this batch: the prompt alone exceeds the whole TPM bucket, so every future sweep that
                # leases the same oldest items fails identically. Surface it loudly instead of looking like a transient quota blip.
                logger.error(
                    "Nightwatcher batch %d prompt exceeds the TPM burst limit (batch_size=%d): %s -- "
                    "lower NIGHTWATCHER_BATCH_SIZE; the batch is restaged and will fail again until then",
                    batch_no, batch_size, be,
                )
                await self._notify_ops(
                    f":rotating_light: Nightwatcher batch {batch_no} (batch_size={batch_size}) exceeds the LLM token burst "
                    f"limit and cannot be processed. It was restaged and will fail every sweep until "
                    f"NIGHTWATCHER_BATCH_SIZE is lowered. Detail: {be}"
                )
                await self._settle_failed_batch(
                    "failed", json_members, escalations, cumulative,
                    shift_date, window, window_start, window_end, sweep_start, requeue_all=False,
                )
                return
            except QuotaExhaustedError as qe:
                logger.warning("Nightwatcher sweep paused due to quota exhaustion on batch %d: %s", batch_no, qe)
                await self._settle_failed_batch(
                    "quota_exhausted", json_members, escalations, cumulative,
                    shift_date, window, window_start, window_end, sweep_start, requeue_all=False,
                )
                return
            except Exception:
                logger.exception("Nightwatcher sweep failed, settling batch and persisting failed report")
                await self._settle_failed_batch(
                    "failed", json_members, escalations, cumulative,
                    shift_date, window, window_start, window_end, sweep_start, requeue_all=True,
                )
                return

            # Decide whether to drain another batch within this sweep.
            ctx = self._batch_ctx
            if not (ctx and ctx.created_incidents):
                logger.warning("Nightwatcher: batch %d produced no incidents, stopping drain to avoid re-leasing the same items", batch_no)
                return
            if batch_no >= max_batches:
                logger.info("Nightwatcher: reached NIGHTWATCHER_MAX_BATCHES=%d, remaining backlog drains next sweep", max_batches)
                return
            remaining = await self.blackboard.count_pending_escalations()
            if not isinstance(remaining, int) or remaining < min_pending:
                return
            logger.info("Nightwatcher: %d escalations still pending, cooling down %.0fs before next batch",
                        remaining, cooldown_s)
            if cooldown_s > 0:
                await asyncio.sleep(cooldown_s)

    @staticmethod
    def _incidented_ids(ctx) -> set[str]:
        """Event IDs that already have a Jira incident/extension (pure, no I/O)."""
        return {eid for inc in ctx.created_incidents for eid in inc.affected_events} if ctx else set()

    async def _notify_ops(self, text: str) -> None:
        """Best-effort ops notification (never raises)."""
        if not self._slack_notify:
            return
        try:
            await self._slack_notify(text)
        except Exception:
            logger.warning("Nightwatcher: ops notification failed (non-fatal)", exc_info=True)

    async def _commit_processed(self, ctx, json_members, escalations) -> set[str]:
        """Commit events whose Jira incident already exists; clear their escalation flags.

        Idempotent and incremental: only events not yet in ctx.committed_event_ids are sent to
        Redis, and an event is marked committed only after commit_inflight succeeded (a failed
        call is retried by the next invocation). Returns ALL incidented event IDs.
        """
        done_ids = self._incidented_ids(ctx)
        if not ctx:
            return done_ids
        fresh = done_ids - ctx.committed_event_ids
        if not fresh:
            return done_ids
        fresh_jsons = [jm for jm, e in zip(json_members, escalations) if e.event_id in fresh]
        if fresh_jsons:
            await self.blackboard.commit_inflight(fresh_jsons)
        ctx.committed_event_ids |= fresh

        # Clear escalation flags for newly committed services (best-effort:
        # if clear fails, recovery or next escalation cycle will reset the flag)
        for eid in fresh:
            esc = ctx.escalations_by_id.get(eid)
            if esc and esc.service:
                try:
                    await self.blackboard.clear_escalation_flag(
                        esc.service, scope=esc.scope or "health",
                        expected_event_id=eid,
                    )
                except Exception:
                    logger.warning(
                        f"Failed to clear escalation flag for {esc.service} "
                        f"(eid={eid}), best-effort — recovery or next escalation will reset"
                    )
        return done_ids

    async def _settle_failed_batch(self, status, json_members, escalations, prior,
                                   shift_date, window, window_start, window_end,
                                   sweep_start, requeue_all: bool) -> None:
        """Failure path: commit already-incidented events, restage only the remainder, persist report.

        Jira writes are not idempotent, so a member whose incident exists must never go back to
        pending (the next sweep would file a duplicate). Persisting the report is attempted even
        if settling raised, so the Shifts UI always reflects the outage.
        """
        from ..models import ShiftReport
        ctx = getattr(self, "_batch_ctx", None)
        # Independent of Redis: which events already have a Jira incident.
        done_ids = self._incidented_ids(ctx)

        # Step A: commit incidented events. Isolated so a failure here can never skip the restage below.
        commit_ok = True
        try:
            await self._commit_processed(ctx, json_members, escalations)
        except Exception:
            commit_ok = False
            logger.exception("Nightwatcher: failed to commit %d incidented events during %s settle", len(done_ids), status)

        # Step B: give every NON-incidented member back to pending.
        rest = [jm for jm, e in zip(json_members, escalations) if e.event_id not in done_ids]
        if rest:
            try:
                if requeue_all and not done_ids:
                    await self.blackboard.requeue_inflight()
                else:
                    await self.blackboard.restage_orphans(rest)
            except Exception:
                logger.exception("Nightwatcher: failed to restage %d members during %s settle", len(rest), status)
                # Fallback: requeue_inflight() moves EVERYTHING still in inflight back to pending. That is only
                # safe when no incidented event can still be sitting in inflight (commit succeeded or none exist);
                # otherwise it would re-file existing Jira incidents.
                if commit_ok:
                    try:
                        await self.blackboard.requeue_inflight()
                    except Exception:
                        logger.exception(
                            "Nightwatcher: requeue fallback failed -- %d members remain in inflight and are LOST when "
                            "INFLIGHT_TTL expires (the TTL deletes the set, it does not requeue) unless the pod restarts first",
                            len(rest))
                        stranded_ids = [e.event_id for e in escalations if e.event_id not in done_ids]
                        await self._notify_ops(
                            f":rotating_light: *Nightwatcher double-fault*: requeue fallback failed during {status} settle. "
                            f"{len(rest)} escalations stranded in inflight: {', '.join(stranded_ids[:10])}"
                        )
                else:
                    logger.error(
                        "Nightwatcher: commit AND restage failed -- NOT calling requeue_inflight() (would duplicate Jira "
                        "incidents for %d incidented events). Manual recovery required.", len(done_ids))
                    stranded_ids = [e.event_id for e in escalations]
                    await self._notify_ops(
                        f":rotating_light: *Nightwatcher double-fault*: commit AND restage failed during {status} settle. "
                        f"Manual recovery required for {len(stranded_ids)} escalations: {', '.join(stranded_ids[:10])}"
                    )

        created = list(ctx.created_incidents) if ctx else []
        batch_report = ShiftReport(
            shift_date=shift_date, window=window,
            window_start=window_start, window_end=window_end,
            status=status,
            manifest=[e for e in escalations if e.event_id in done_ids],
            incidents=created,
            investigations=list(ctx.investigations) if ctx else [],
            metrics={"escalation_count": len(done_ids), "incident_count": len(created),
                     "investigation_count": len(ctx.investigations) if ctx else 0,
                     "failed_cluster_count": 0},
            started_at=sweep_start, completed_at=time.time(),
        )
        report = self._merge_reports(prior, batch_report, status=status)
        await self.blackboard.persist_shift_report(report)

    @staticmethod
    def _merge_reports(prior, new, status: str | None = None):
        """Merge a batch's report into the sweep's cumulative report (same date:window key)."""
        if prior is None:
            return new
        metrics = dict(prior.metrics)
        for key in ("escalation_count", "incident_count", "investigation_count", "failed_cluster_count"):
            metrics[key] = (prior.metrics.get(key) or 0) + (new.metrics.get(key) or 0)
        esc_total = metrics.get("escalation_count") or 0
        metrics["noise_reduction_pct"] = (
            round((1 - metrics["incident_count"] / esc_total) * 100, 1)
            if metrics.get("incident_count") and esc_total else 0
        )
        started = prior.started_at or new.started_at
        completed = new.completed_at
        metrics["sweep_duration_s"] = round((completed or time.time()) - (started or time.time()), 1)
        return prior.model_copy(update={
            "status": status or new.status,
            "manifest": prior.manifest + new.manifest,
            "incidents": prior.incidents + new.incidents,
            "investigations": prior.investigations + new.investigations,
            "summary_text": "\n\n".join(t for t in (prior.summary_text, new.summary_text) if t),
            "metrics": metrics,
            "started_at": started,
            "completed_at": completed,
        })

    async def _run_analysis_loop(self, escalations, json_members, system_prompt,
                                 window_start, window_end, shift_date, window,
                                 sweep_start, pending_count,
                                 dispatch_count: int = 0, dispatch_cap: int | None = None):
        """LLM-driven analysis loop: review + investigate phases."""
        adapter = await self._get_adapter()
        escalation_text = "\n".join(
            f"- **{e.event_id}** | {e.service} | {e.platform} | {(e.summary or '')[:SUMMARY_PROMPT_CHARS]}"
            for e in escalations
        )
        contents = [{"role": "user", "parts": [{"text": escalation_text}]}]
        current_phase = "review"
        if dispatch_cap is None:
            dispatch_cap = int(os.getenv("NIGHTWATCHER_DISPATCH_CAP", "3"))

        ctx = NightwatcherContext(
            blackboard=self.blackboard, archivist=self._archivist,
            provisioner=self._provisioner, registry=self._registry,
            bridge=self._bridge, incident_adapter=self._incident_adapter,
            broadcast=self._broadcast,
            slack_notify=self._slack_notify,
            manifest_services={e.service for e in escalations},
            manifest_ids={e.event_id for e in escalations},
            escalations_by_id={e.event_id: e for e in escalations},
            dispatch_count=dispatch_count, dispatch_cap=dispatch_cap,
            created_incidents=[], investigations=[],
        )
        self._batch_ctx = ctx  # lets _sweep's failure path see incidents created before an error

        temperature = float(os.getenv("LLM_TEMPERATURE_NIGHTWATCHER", "0.3"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS_NIGHTWATCHER", "8192"))
        analysis_max_tokens = int(os.getenv("LLM_MAX_TOKENS_NIGHTWATCHER_ANALYSIS", "16384"))
        thinking = os.getenv("LLM_THINKING_NIGHTWATCHER", "high")
        text_nudge_count = 0

        for _ in range(MAX_ANALYSIS_ROUNDS):
            tools = get_phase_tools(current_phase)
            response = await adapter.generate(
                system_prompt=system_prompt, contents=contents,
                tools=tools, temperature=temperature,
                max_output_tokens=analysis_max_tokens, thinking_level=thinking,
            )
            from src.agents.llm import record_token_usage
            record_token_usage("nightwatcher", response.usage)
            if response.function_call:
                name = response.function_call.name
                args = response.function_call.args
                if name == "set_phase":
                    new_phase = args.get("phase", "")
                    phases = ["review", "investigate", "report"]
                    cur_idx = phases.index(current_phase) if current_phase in phases else 0
                    new_idx = phases.index(new_phase) if new_phase in phases else -1
                    if new_idx == cur_idx + 1:
                        current_phase = new_phase
                        logger.info("Nightwatcher phase: %s -> %s (%s)", phases[cur_idx], new_phase, args.get("reasoning", ""))
                        if new_phase == "report":
                            return contents, ctx
                        tool_result = f"Phase: {current_phase.upper()}"
                    else:
                        tool_result = (
                            f"Invalid phase transition: {current_phase} -> {new_phase}. "
                            f"Advance one step at a time (review -> investigate -> report)."
                        )
                else:
                    tool_result = await execute_tool(name, args, ctx)
                    logger.info("Nightwatcher tool %s: %s", name, tool_result[:200])
                contents.append({"role": "model", "parts": response.raw_parts or [{"text": response.text or ""}]})
                contents.append({"role": "user", "parts": [{"text": tool_result}]})
                text_nudge_count = 0
            else:
                text_nudge_count += 1
                if text_nudge_count <= 2:
                    logger.info("Nightwatcher analysis nudge %d/2: LLM emitted text without tool call", text_nudge_count)
                    contents.append({"role": "model", "parts": response.raw_parts or [{"text": response.text or ""}]})
                    contents.append({"role": "user", "parts": [{"text":
                        "You have finished your analysis. Call set_phase('report') to proceed to the report phase."}]})
                else:
                    logger.warning("Nightwatcher: forcing transition to report phase after %d nudges", text_nudge_count)
                    return contents, ctx

        logger.warning("Nightwatcher: MAX_ANALYSIS_ROUNDS exhausted, forcing transition to report phase")
        return contents, ctx

    async def _run_clustering_agent(self, adapter, ctx, system_prompt, contents,
                                    temperature, max_tokens, thinking) -> None:
        """Step 1 of the cart: have the LLM declare clusters, with bounded retries.

        Validation errors are fed back to the model. auto_reconcile (code-built fallback
        cluster for unassigned events) is enabled ONLY on the final attempt, so the model
        always gets MAX_DECLARE_RETRIES chances to produce a complete plan itself.
        Raises RuntimeError if no plan is accepted.
        """
        from ..agents.llm.types import NIGHTWATCHER_DECLARE_CLUSTERS_SCHEMA
        from .nightwatcher_tools import _handle_declare_clusters
        from src.agents.llm import record_token_usage
        for attempt in range(MAX_DECLARE_RETRIES + 1):
            response = await adapter.generate(
                system_prompt=system_prompt, contents=contents,
                tools=NIGHTWATCHER_DECLARE_CLUSTERS_SCHEMA, temperature=temperature,
                max_output_tokens=max_tokens, thinking_level=thinking,
            )
            record_token_usage("nightwatcher", response.usage)
            if response.function_call and response.function_call.name == "declare_clusters":
                result = await _handle_declare_clusters(
                    response.function_call.args, ctx,
                    auto_reconcile=(attempt == MAX_DECLARE_RETRIES),
                )
                contents.append({"role": "model", "parts": response.raw_parts or [{"text": response.text or ""}]})
                contents.append({"role": "user", "parts": [{"text": result}]})
                if ctx.declared_clusters:
                    logger.info("Nightwatcher: cluster plan accepted on attempt %d", attempt + 1)
                    return
                logger.warning("Nightwatcher: cluster plan rejected on attempt %d: %s", attempt + 1, result[:200])
            else:
                contents.append({"role": "model", "parts": response.raw_parts or [{"text": response.text or ""}]})
                contents.append({"role": "user", "parts": [{"text":
                    "You must call declare_clusters with your cluster plan. Every manifest event must be assigned."}]})
        raise RuntimeError("Nightwatcher: cluster declaration failed after max retries")

    async def _run_report_cart(self, ctx, contents, json_members, escalations,
                               system_prompt, shift_date, window, window_start,
                               window_end, sweep_start, pending_count, prior_report=None):
        """Code-driven shopping cart: declare clusters, then N isolated report iterations.

        Returns the persisted ShiftReport (cumulative with prior_report when draining
        multiple batches in one sweep).
        """
        from ..models import ShiftReport
        adapter = await self._get_adapter()
        temperature = float(os.getenv("LLM_TEMPERATURE_NIGHTWATCHER", "0.3"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS_NIGHTWATCHER", "8192"))
        thinking = os.getenv("LLM_THINKING_NIGHTWATCHER", "high")

        # Step 1: Declare clusters
        await self._run_clustering_agent(
            adapter, ctx, system_prompt, contents, temperature, max_tokens, thinking,
        )

        # Step 2: Validate extends_issue_key values against open incidents (fail-closed)
        open_keys: set[str] = set()
        search_succeeded = False
        if any(c.get("extends_issue_key") for c in ctx.declared_clusters):
            try:
                if ctx.incident_adapter:
                    open_incidents = await ctx.incident_adapter.search_open_incidents()
                    open_keys = {inc.get("key", "") for inc in open_incidents}
                    search_succeeded = True
            except Exception as e:
                logger.warning("Nightwatcher: failed to validate extends_issue_key set: %s", e)

        for cluster in ctx.declared_clusters:
            ext_key = cluster.get("extends_issue_key")
            if ext_key:
                if not search_succeeded or ext_key not in open_keys:
                    logger.warning("Nightwatcher: extends_issue_key %s invalid (search_ok=%s, in_set=%s), converting to new incident",
                                   ext_key, search_succeeded, ext_key in open_keys if search_succeeded else "N/A")
                    del cluster["extends_issue_key"]

        # Step 3: Code-driven report loop (write or extend)
        completed_reports: list[dict] = []
        for i, cluster in enumerate(ctx.declared_clusters, 1):
            is_extend = bool(cluster.get("extends_issue_key"))
            cluster_links: list[str] = []
            for eid in cluster.get("events", []):
                esc = ctx.escalations_by_id.get(eid)
                if esc:
                    links_text = extract_full_links(esc)
                    if links_text:
                        cluster_links.append(f"**{eid}**:\n{links_text}")
            report_prompt = build_report_iteration_prompt(
                cluster, i, len(ctx.declared_clusters), completed_reports,
                cluster_links=cluster_links or None,
            )

            if is_extend:
                report_tools = build_extend_tool(cluster, i, len(ctx.declared_clusters), completed_reports)
                expected_tool = "extend_incident"
            else:
                report_tools = build_report_tool(cluster, i, len(ctx.declared_clusters), completed_reports)
                expected_tool = "write_incident"

            for retry in range(MAX_CART_RETRIES + 1):
                response = await adapter.generate(
                    system_prompt=system_prompt,
                    contents=[{"role": "user", "parts": [{"text": report_prompt}]}],
                    tools=report_tools, temperature=temperature,
                    max_output_tokens=max_tokens, thinking_level=thinking,
                )
                from src.agents.llm import record_token_usage
                record_token_usage("nightwatcher", response.usage)
                if response.function_call and response.function_call.name == expected_tool:
                    if is_extend:
                        result = await _handle_extend_incident(response.function_call.args, ctx, cluster)
                    else:
                        result = await _handle_write_incident(response.function_call.args, ctx, cluster)
                    logger.info("Nightwatcher report %d/%d: %s", i, len(ctx.declared_clusters), result[:200])
                    report_record = {
                        "index": i,
                        "platform": cluster.get("platform", ""),
                        "summary": (response.function_call.args.get("summary") or "")[:200],
                        "priority": response.function_call.args.get("priority", "Normal"),
                        "status": response.function_call.args.get("status", "New"),
                        "affected_events": cluster.get("events", []),
                    }
                    completed_reports.append(report_record)
                    # Jira write is not idempotent: take this cluster's members out of inflight NOW so a
                    # later crash / SIGTERM / CancelledError cannot requeue them and file a duplicate.
                    await self._commit_processed(ctx, json_members, escalations)
                    break
                else:
                    if retry < MAX_CART_RETRIES:
                        logger.warning("Nightwatcher: report %d/%d retry %d (no tool call)", i, len(ctx.declared_clusters), retry + 1)
                    else:
                        logger.error("Nightwatcher: report %d/%d failed after %d retries, marking cluster as failed", i, len(ctx.declared_clusters), MAX_CART_RETRIES + 1)
                        ctx.failed_cluster_events.extend(cluster.get("events", []))

        # Step 3: Coverage gate
        if ctx.failed_cluster_events:
            failed_jsons = [jm for jm, e in zip(json_members, escalations) if e.event_id in set(ctx.failed_cluster_events)]
            if failed_jsons:
                await self.blackboard.restage_orphans(failed_jsons)
                logger.warning("Nightwatcher: restaged %d failed cluster events", len(ctx.failed_cluster_events))

        # Step 4: Summary
        noise_pct = round((1 - len(ctx.created_incidents) / max(pending_count, 1)) * 100, 1) if ctx.created_incidents else 0
        metrics = {
            "escalation_count": pending_count,
            "incident_count": len(ctx.created_incidents),
            "noise_reduction_pct": noise_pct,
            "investigation_count": len(ctx.investigations),
            "failed_cluster_count": len([c for c in ctx.declared_clusters if any(eid in ctx.failed_cluster_events for eid in c.get("events", []))]),
            "sweep_duration_s": round(time.time() - sweep_start, 1),
        }
        summary_prompt = build_summary_prompt(completed_reports, metrics)
        summary_tools = build_summary_tool(completed_reports, metrics)
        response = await adapter.generate(
            system_prompt=system_prompt,
            contents=[{"role": "user", "parts": [{"text": summary_prompt}]}],
            tools=summary_tools, temperature=temperature,
            max_output_tokens=max_tokens, thinking_level=thinking,
        )
        from src.agents.llm import record_token_usage
        record_token_usage("nightwatcher", response.usage)
        if response.function_call and response.function_call.name == "post_shift_summary":
            from .nightwatcher_tools import _handle_post_shift_summary
            await _handle_post_shift_summary(response.function_call.args, ctx)
        else:
            logger.warning("Nightwatcher: summary LLM call did not produce post_shift_summary tool call")

        # Step 5: Safety net -- per-cluster commits above already removed incidented events; this is a no-op
        # unless an earlier commit failed (it is retried here).
        await self._commit_processed(ctx, json_members, escalations)

        report = ShiftReport(
            shift_date=shift_date, window=window,
            window_start=window_start, window_end=window_end,
            status="completed", manifest=escalations,
            incidents=ctx.created_incidents, investigations=ctx.investigations,
            summary_text=getattr(ctx, "_summary_text", ""),
            metrics=metrics,
            started_at=sweep_start, completed_at=time.time(),
        )
        report = self._merge_reports(prior_report, report)
        await self.blackboard.persist_shift_report(report)
        logger.info("Nightwatcher sweep complete: %d escalations -> %d incidents (%.0f%% reduction, %.1fs)",
                     pending_count, len(ctx.created_incidents), noise_pct, time.time() - sweep_start)
        return report
