# BlackBoard/src/observers/nightwatcher_tools.py
# @ai-rules:
# 1. [Pattern]: Stateless tool handlers. All state lives in NightwatcherContext dataclass.
# 2. [Constraint]: dispatch_investigation uses a FIXED server-side template. Service must be in manifest.
# 3. [Constraint]: create_incident populates system fields (Labels, Components, Reporter) from env -- same contract as Brain.
# 4. [Pattern]: get_phase_tools() returns filtered NIGHTWATCHER_TOOL_SCHEMAS by current_phase.
"""
Nightwatcher tool execution router and phase-gated tool filtering.

Each handler is a thin wrapper around existing infrastructure
(blackboard, archivist, dispatch, smartsheet, slack).
"""
from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..adapters.smartsheet_incident import SmartsheetIncidentAdapter
    from ..agents.agent_registry import AgentRegistry
    from ..agents.archivist import Archivist
    from ..agents.ephemeral_provisioner import EphemeralProvisioner
    from ..agents.task_bridge import TaskBridge
    from ..state.blackboard import BlackboardState

from ..models import ShiftIncident, ShiftInvestigation

logger = logging.getLogger(__name__)

INVESTIGATION_TEMPLATE = (
    "Check current status of {service}. Report: "
    "(1) pipeline health, (2) current errors, (3) manual intervention needed."
)

_PHASE_TOOLS: dict[str, set[str]] = {
    "review": {"set_phase", "get_event_report", "search_journal", "consult_deep_memory"},
    "investigate": {"set_phase", "get_event_report", "search_journal", "consult_deep_memory", "dispatch_investigation"},
    "report": {"create_incident", "post_shift_summary"},
}


@dataclass
class NightwatcherContext:
    """Mutable sweep context passed through all tool handlers."""
    blackboard: Any
    archivist: Any
    provisioner: Any
    registry: Any
    bridge: Any
    smartsheet_adapter: Any
    slack_notify: Any
    manifest_services: set[str] = field(default_factory=set)
    manifest_ids: set[str] = field(default_factory=set)
    dispatch_count: int = 0
    dispatch_cap: int = 3
    created_incidents: list[ShiftIncident] = field(default_factory=list)
    investigations: list[ShiftInvestigation] = field(default_factory=list)
    _summary_text: str = ""


def get_phase_tools(phase: str) -> list[dict]:
    """Return NIGHTWATCHER_TOOL_SCHEMAS filtered by current phase."""
    from ..agents.llm.types import NIGHTWATCHER_TOOL_SCHEMAS
    allowed = _PHASE_TOOLS.get(phase, set())
    return [t for t in NIGHTWATCHER_TOOL_SCHEMAS if t["name"] in allowed]


async def execute_tool(name: str, args: dict, ctx: NightwatcherContext) -> str:
    """Route a tool call to its handler. Returns result text for the LLM."""
    handlers = {
        "get_event_report": _handle_get_event_report,
        "search_journal": _handle_search_journal,
        "consult_deep_memory": _handle_consult_deep_memory,
        "dispatch_investigation": _handle_dispatch_investigation,
        "create_incident": _handle_create_incident,
        "post_shift_summary": _handle_post_shift_summary,
    }
    handler = handlers.get(name)
    if not handler:
        return f"Unknown tool: {name}"
    try:
        return await handler(args, ctx)
    except Exception as e:
        logger.warning("Nightwatcher tool %s failed: %s", name, e)
        return f"Tool error ({name}): {e}"


async def _handle_get_event_report(args: dict, ctx: NightwatcherContext) -> str:
    event_id = args.get("event_id", "")
    report = await ctx.blackboard.get_report(event_id)
    if not report:
        return f"No report found for {event_id}"
    content = report.get("markdown", report.get("content", ""))
    return content[:8000] if content else f"Report for {event_id} is empty"


async def _handle_search_journal(args: dict, ctx: NightwatcherContext) -> str:
    service = args.get("service", "")
    entries = await ctx.blackboard.get_journal(service)
    if not entries:
        return f"No journal entries for {service}"
    return "\n".join(entries[-20:])


async def _handle_consult_deep_memory(args: dict, ctx: NightwatcherContext) -> str:
    query = args.get("query", "")
    results = await ctx.archivist.search(query, limit=5)
    if not results:
        return "No matching events in deep memory."
    lines = []
    for r in results:
        p = r.get("payload", {})
        lines.append(
            f"- score={r.get('score', 0):.2f} | {p.get('symptom', '?')} | "
            f"root_cause={p.get('root_cause', '?')} | fix={p.get('fix_action', '?')} | "
            f"service={p.get('service', '?')} | outcome={p.get('outcome', '?')}"
        )
    return "\n".join(lines)


async def _handle_dispatch_investigation(args: dict, ctx: NightwatcherContext) -> str:
    service = args.get("service", "")
    if service not in ctx.manifest_services:
        return f"Service '{service}' is not in the manifest. Only manifest services can be investigated."
    if ctx.dispatch_count >= ctx.dispatch_cap:
        return f"Dispatch cap reached ({ctx.dispatch_cap}/{ctx.dispatch_cap}). No more investigations this sweep."
    if not ctx.provisioner:
        return "Ephemeral provisioner not available. Cannot dispatch investigation."

    task_prompt = INVESTIGATION_TEMPLATE.format(service=service)
    sweep_event_id = f"nw-sweep-{int(time.time())}"
    start = time.time()
    try:
        from ..agents.ephemeral_provisioner import INFRA_SENTINEL
        from ..agents.dispatch import dispatch_to_agent
        agent = await ctx.provisioner.ensure_agent(sweep_event_id)
        if agent == INFRA_SENTINEL:
            return f"Ephemeral agent unavailable (Tekton infra). Skipping investigation for {service}."
        if not agent:
            return "No ephemeral agent available. Skipping investigation."
        result_text, _ = await dispatch_to_agent(
            ctx.registry, ctx.bridge, "sysadmin", sweep_event_id,
            task_prompt, agent_id=agent.agent_id, mode="investigate",
        )
    except Exception as e:
        result_text = f"Investigation dispatch failed: {e}"
    duration = round(time.time() - start, 1)
    ctx.dispatch_count += 1
    ctx.investigations.append(ShiftInvestigation(
        task=task_prompt, service=service,
        agent_result=result_text[:3000], duration_seconds=duration,
    ))
    logger.info("Nightwatcher investigation %d/%d: %s (%.1fs)", ctx.dispatch_count, ctx.dispatch_cap, service, duration)
    return result_text[:3000]


async def _handle_create_incident(args: dict, ctx: NightwatcherContext) -> str:
    if not ctx.smartsheet_adapter:
        return "Smartsheet adapter not configured. Incident not created."
    logger.info("Nightwatcher create_incident args: %s", {k: (v[:80] if isinstance(v, str) else v) for k, v in args.items()})
    fields = {
        "Reporter e-mail": os.environ.get("SMARTSHEET_INCIDENT_REPORTER", ""),
        "Reporter Display Name": os.environ.get("SMARTSHEET_INCIDENT_REPORTER_NAME", "Darwin Nightwatcher"),
        "Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "Status": args.get("status", "New"),
        "Issue Type": "Task",
        "Labels": "darwin-auto, release-incident",
        "Components": "CNV CI and Release",
        "Platform": args.get("platform", ""),
        "Summary": args.get("summary", "")[:200],
        "Reason": args.get("description", ""),
        "Priority": args.get("priority", "Normal"),
    }
    try:
        result = await ctx.smartsheet_adapter.create_incident(fields)
        incident = ShiftIncident(
            platform=args.get("platform", ""),
            summary=args.get("summary", "")[:200],
            description=args.get("description", ""),
            priority=args.get("priority", "Normal"),
            status=args.get("status", "New"),
            affected_events=args.get("affected_events", []),
            smartsheet_row_id=str(result.get("row_id", "")),
            smartsheet_url=result.get("sheet_url", ""),
        )
        ctx.created_incidents.append(incident)
        return f"Incident created (row {result.get('row_id', '?')}). {len(incident.affected_events)} events consolidated."
    except Exception as e:
        return f"Failed to create incident: {e}"


async def _handle_post_shift_summary(args: dict, ctx: NightwatcherContext) -> str:
    summary = args.get("summary", "")
    ctx._summary_text = summary
    if ctx.slack_notify:
        try:
            await ctx.slack_notify(summary)
            return "Shift summary posted to Slack."
        except Exception as e:
            return f"Slack notification failed: {e}"
    return "Shift summary recorded (Slack not configured)."
