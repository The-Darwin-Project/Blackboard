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
                model = os.getenv("LLM_MODEL_NIGHTWATCHER", "gemini-3-flash-preview")
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

        escalations, json_members = await self.blackboard.lease_pending_escalations(time.time())
        pending_count = len(escalations)
        logger.info("Nightwatcher sweep: %d pending escalations", pending_count)

        min_pending = int(os.getenv("NIGHTWATCHER_MIN_PENDING", "1"))
        if pending_count == 0 or pending_count < min_pending:
            if json_members:
                await self.blackboard.requeue_inflight()
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
        try:
            contents, ctx = await self._run_analysis_loop(
                escalations, json_members, system_prompt,
                window_start, window_end, shift_date, window,
                sweep_start, pending_count,
            )
            await self._run_report_cart(
                ctx, contents, json_members, escalations, system_prompt,
                shift_date, window, window_start, window_end,
                sweep_start, pending_count,
            )
        except Exception:
            logger.exception("Nightwatcher sweep failed, requeueing and persisting failed report")
            await self.blackboard.requeue_inflight()
            failed_report = ShiftReport(
                shift_date=shift_date, window=window,
                window_start=window_start, window_end=window_end,
                status="failed", started_at=sweep_start, completed_at=time.time(),
            )
            await self.blackboard.persist_shift_report(failed_report)

    async def _run_analysis_loop(self, escalations, json_members, system_prompt,
                                 window_start, window_end, shift_date, window,
                                 sweep_start, pending_count):
        """LLM-driven analysis loop: review + investigate phases."""
        adapter = await self._get_adapter()
        escalation_text = "\n\n".join(
            f"**{e.event_id}** | {e.service} | {e.platform} | {e.summary}\n{e.description[:300]}"
            for e in escalations
        )
        contents = [{"role": "user", "parts": [{"text": escalation_text}]}]
        current_phase = "review"
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
            dispatch_count=0, dispatch_cap=dispatch_cap,
            created_incidents=[], investigations=[],
        )

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

    async def _run_report_cart(self, ctx, contents, json_members, escalations,
                               system_prompt, shift_date, window, window_start,
                               window_end, sweep_start, pending_count):
        """Code-driven shopping cart: declare clusters, then N isolated report iterations."""
        from ..models import ShiftReport
        from ..agents.llm.types import NIGHTWATCHER_DECLARE_CLUSTERS_SCHEMA
        adapter = await self._get_adapter()
        temperature = float(os.getenv("LLM_TEMPERATURE_NIGHTWATCHER", "0.3"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS_NIGHTWATCHER", "8192"))
        thinking = os.getenv("LLM_THINKING_NIGHTWATCHER", "high")

        # Step 1: Declare clusters
        for attempt in range(MAX_DECLARE_RETRIES + 1):
            response = await adapter.generate(
                system_prompt=system_prompt, contents=contents,
                tools=NIGHTWATCHER_DECLARE_CLUSTERS_SCHEMA, temperature=temperature,
                max_output_tokens=max_tokens, thinking_level=thinking,
            )
            from src.agents.llm import record_token_usage
            record_token_usage("nightwatcher", response.usage)
            if response.function_call and response.function_call.name == "declare_clusters":
                from .nightwatcher_tools import _handle_declare_clusters
                result = await _handle_declare_clusters(response.function_call.args, ctx)
                if ctx.declared_clusters:
                    logger.info("Nightwatcher: cluster plan accepted on attempt %d", attempt + 1)
                    contents.append({"role": "model", "parts": response.raw_parts or [{"text": response.text or ""}]})
                    contents.append({"role": "user", "parts": [{"text": result}]})
                    break
                contents.append({"role": "model", "parts": response.raw_parts or [{"text": response.text or ""}]})
                contents.append({"role": "user", "parts": [{"text": result}]})
                logger.warning("Nightwatcher: cluster plan rejected on attempt %d: %s", attempt + 1, result[:200])
            else:
                contents.append({"role": "model", "parts": response.raw_parts or [{"text": response.text or ""}]})
                contents.append({"role": "user", "parts": [{"text":
                    "You must call declare_clusters with your cluster plan. Every manifest event must be assigned."}]})
        else:
            raise RuntimeError("Nightwatcher: cluster declaration failed after max retries")

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
                        "summary": response.function_call.args.get("summary", "")[:200],
                        "priority": response.function_call.args.get("priority", "Normal"),
                        "status": response.function_call.args.get("status", "New"),
                        "affected_events": cluster.get("events", []),
                    }
                    completed_reports.append(report_record)
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

        # Step 5: Commit / restage
        successful_event_ids = {eid for inc in ctx.created_incidents for eid in inc.affected_events}
        successful_jsons = [jm for jm, e in zip(json_members, escalations) if e.event_id in successful_event_ids]
        if successful_jsons:
            await self.blackboard.commit_inflight(successful_jsons)

        # Clear escalation flags for successfully committed services (best-effort:
        # if clear fails, recovery or next escalation cycle will reset the flag)
        for eid in successful_event_ids:
            esc = ctx.escalations_by_id.get(eid)
            if esc and esc.service:
                try:
                    await self.blackboard.clear_escalation_flag(
                        esc.service, expected_event_id=eid,
                    )
                except Exception:
                    logger.warning(
                        f"Failed to clear escalation flag for {esc.service} "
                        f"(eid={eid}), best-effort — recovery or next escalation will reset"
                    )

        report = ShiftReport(
            shift_date=shift_date, window=window,
            window_start=window_start, window_end=window_end,
            status="completed", manifest=escalations,
            incidents=ctx.created_incidents, investigations=ctx.investigations,
            summary_text=getattr(ctx, "_summary_text", ""),
            metrics=metrics,
            started_at=sweep_start, completed_at=time.time(),
        )
        await self.blackboard.persist_shift_report(report)
        logger.info("Nightwatcher sweep complete: %d escalations -> %d incidents (%.0f%% reduction, %.1fs)",
                     pending_count, len(ctx.created_incidents), noise_pct, time.time() - sweep_start)
