# BlackBoard/src/observers/nightwatcher.py
# @ai-rules:
# 1. [Pattern]: Follows TimeKeeperObserver lifecycle -- in-process daemon with start/stop/cron loop.
# 2. [Pattern]: Flash tool-calling loop matches Brain.process_event -- multi-turn structured contents.
# 3. [Pattern]: Phase gating: review -> investigate -> report. Tools filtered by current_phase.
# 4. [Pattern]: Orphan re-injection: code detects missing events, re-injects into Flash session (LLM decides).
# 5. [Constraint]: requeue_inflight() called on start() to recover from prior crash.
# 6. [Constraint]: Max 50 tool rounds per sweep as safety cap. Max 2 orphan re-injections.
"""
Nightwatcher Observer -- end-of-shift incident consolidation agent.

Cron-triggered (default 06:00/18:00 UTC). Leases pending escalations,
runs a phase-gated Gemini Flash tool-calling session to cluster and
consolidate, writes deduplicated incidents to Smartsheet, posts a
shift summary to Slack, and persists a ShiftReport for the Shifts UI.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..adapters.smartsheet_incident import SmartsheetIncidentAdapter
    from ..agents.agent_registry import AgentRegistry
    from ..agents.archivist import Archivist
    from ..agents.ephemeral_provisioner import EphemeralProvisioner
    from ..agents.task_bridge import TaskBridge
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 50
MAX_ORPHAN_REINJECTIONS = 2
NIGHTWATCHER_SWEEP_CRON = os.getenv("NIGHTWATCHER_SWEEP_CRON", "0 6,18 * * *")

from .nightwatcher_tools import NightwatcherContext, execute_tool, get_phase_tools
from .nightwatcher_prompt import build_system_prompt


class NightwatcherObserver:
    """End-of-shift incident consolidation agent (Agent 6)."""

    def __init__(
        self,
        blackboard: "BlackboardState",
        registry: "AgentRegistry",
        bridge: "TaskBridge",
        provisioner: "Optional[EphemeralProvisioner]",
        smartsheet_adapter: "Optional[SmartsheetIncidentAdapter]",
        archivist: "Archivist",
        slack_notify=None,
    ):
        self.blackboard = blackboard
        self._registry = registry
        self._bridge = bridge
        self._provisioner = provisioner
        self._smartsheet = smartsheet_adapter
        self._archivist = archivist
        self._slack_notify = slack_notify
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
            await self._run_flash_loop(escalations, json_members, system_prompt,
                                       window_start, window_end, shift_date, window,
                                       sweep_start, pending_count)
        except Exception:
            logger.exception("Nightwatcher sweep failed, requeueing and persisting failed report")
            await self.blackboard.requeue_inflight()
            failed_report = ShiftReport(
                shift_date=shift_date, window=window,
                window_start=window_start, window_end=window_end,
                status="failed", started_at=sweep_start, completed_at=time.time(),
            )
            await self.blackboard.persist_shift_report(failed_report)

    async def _run_flash_loop(self, escalations, json_members, system_prompt,
                              window_start, window_end, shift_date, window,
                              sweep_start, pending_count):
        """Flash tool-calling loop with phase gating and orphan re-injection."""
        from ..models import ShiftReport
        adapter = await self._get_adapter()
        escalation_text = "\n\n".join(
            f"**{e.event_id}** | {e.service} | {e.platform} | {e.summary}\n{e.description[:300]}"
            for e in escalations
        )
        contents = [{"role": "user", "parts": [{"text": escalation_text}]}]
        current_phase = "review"
        manifest_ids = {e.event_id for e in escalations}
        dispatch_cap = int(os.getenv("NIGHTWATCHER_DISPATCH_CAP", "3"))

        ctx = NightwatcherContext(
            blackboard=self.blackboard, archivist=self._archivist,
            provisioner=self._provisioner, registry=self._registry,
            bridge=self._bridge, smartsheet_adapter=self._smartsheet,
            slack_notify=self._slack_notify,
            manifest_services={e.service for e in escalations},
            manifest_ids=manifest_ids, dispatch_count=0, dispatch_cap=dispatch_cap,
            created_incidents=[], investigations=[],
        )

        temperature = float(os.getenv("LLM_TEMPERATURE_NIGHTWATCHER", "0.3"))
        max_tokens = int(os.getenv("LLM_MAX_TOKENS_NIGHTWATCHER", "8192"))
        thinking = os.getenv("LLM_THINKING_NIGHTWATCHER", "high")
        reinjection_count = 0

        for _ in range(MAX_TOOL_ROUNDS):
            tools = get_phase_tools(current_phase)
            response = await adapter.generate(
                system_prompt=system_prompt, contents=contents,
                tools=tools, temperature=temperature,
                max_output_tokens=max_tokens, thinking_level=thinking,
            )
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
            else:
                covered = set()
                for inc in ctx.created_incidents:
                    covered.update(inc.affected_events)
                orphans = manifest_ids - covered
                if orphans and reinjection_count < MAX_ORPHAN_REINJECTIONS:
                    reinjection_count += 1
                    orphan_list = ", ".join(sorted(orphans))
                    logger.warning("Nightwatcher orphan re-injection #%d: %s", reinjection_count, orphan_list)
                    contents.append({"role": "user", "parts": [{"text":
                        f"You have not accounted for these events: [{orphan_list}]. "
                        f"Every event in the manifest must appear in a create_incident call. "
                        f"Create incidents for the remaining events now."}]})
                    continue
                if orphans:
                    logger.warning("Nightwatcher: %d orphans after %d re-injections, re-staging", len(orphans), reinjection_count)
                    orphan_jsons = [jm for jm, e in zip(json_members, escalations) if e.event_id in orphans]
                    await self.blackboard.restage_orphans(orphan_jsons)
                break

        await self.blackboard.commit_inflight(json_members)
        noise_pct = round((1 - len(ctx.created_incidents) / max(pending_count, 1)) * 100, 1) if ctx.created_incidents else 0
        report = ShiftReport(
            shift_date=shift_date, window=window,
            window_start=window_start, window_end=window_end,
            status="completed", manifest=escalations,
            incidents=ctx.created_incidents, investigations=ctx.investigations,
            summary_text=getattr(ctx, "_summary_text", ""),
            metrics={"escalation_count": pending_count, "incident_count": len(ctx.created_incidents),
                     "noise_reduction_pct": noise_pct, "investigation_count": len(ctx.investigations),
                     "orphan_count": len(manifest_ids - {eid for inc in ctx.created_incidents for eid in inc.affected_events}),
                     "sweep_duration_s": round(time.time() - sweep_start, 1)},
            started_at=sweep_start, completed_at=time.time(),
        )
        await self.blackboard.persist_shift_report(report)
        logger.info("Nightwatcher sweep complete: %d escalations -> %d incidents (%.0f%% reduction, %.1fs)",
                     pending_count, len(ctx.created_incidents), noise_pct, time.time() - sweep_start)
