# BlackBoard/src/observers/nightwatcher_tools.py
# @ai-rules:
# 1. [Pattern]: Stateless tool handlers. All state lives in NightwatcherContext dataclass.
# 2. [Constraint]: write_incident merges LLM judgment (args) + code-prefilled (cluster dict). Never mix.
# 3. [Constraint]: validate_cluster_plan is a pure function -- no side effects, no async.
# 4. [Pattern]: build_report_tool() and build_summary_tool() generate dynamic tool dicts per iteration.
# 5. [Pattern]: get_phase_tools() filters static schemas. Dynamic tools are built separately by the cart loop.
# 6. [Pattern]: on_progress callback wired to ctx.broadcast for UI stream visibility of ephemeral oncall agents.
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
from typing import TYPE_CHECKING, Any, Awaitable, Callable

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
    "report": {"declare_clusters"},
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
    broadcast: Callable[[dict], Awaitable[None]] | None = None
    manifest_services: set[str] = field(default_factory=set)
    manifest_ids: set[str] = field(default_factory=set)
    dispatch_count: int = 0
    dispatch_cap: int = 3
    created_incidents: list[ShiftIncident] = field(default_factory=list)
    investigations: list[ShiftInvestigation] = field(default_factory=list)
    declared_clusters: list[dict] = field(default_factory=list)
    failed_cluster_events: list[str] = field(default_factory=list)
    _summary_text: str = ""


def get_phase_tools(phase: str) -> list[dict]:
    """Return tool schemas filtered by current phase."""
    from ..agents.llm.types import NIGHTWATCHER_TOOL_SCHEMAS, NIGHTWATCHER_DECLARE_CLUSTERS_SCHEMA
    allowed = _PHASE_TOOLS.get(phase, set())
    all_schemas = NIGHTWATCHER_TOOL_SCHEMAS + NIGHTWATCHER_DECLARE_CLUSTERS_SCHEMA
    return [t for t in all_schemas if t["name"] in allowed]


from ..agents.llm.types import VALID_PLATFORMS, VALID_STATUSES, VALID_PRIORITIES


def validate_cluster_plan(clusters: list[dict], manifest_ids: set[str]) -> tuple[bool, str]:
    """Validate that clusters cover the full manifest with no overlaps or unknowns."""
    if not clusters:
        return False, "No clusters declared. You must create at least one cluster."
    all_assigned: set[str] = set()
    for i, c in enumerate(clusters):
        events = c.get("events", [])
        if not events:
            return False, f"Cluster {i + 1} has no events. Every cluster must contain at least one event."
        platform = c.get("platform", "")
        if VALID_PLATFORMS and platform not in VALID_PLATFORMS:
            return False, f"Cluster {i + 1} has invalid platform '{platform}'. Must be one of: {', '.join(sorted(VALID_PLATFORMS))}"
        for eid in events:
            if eid in all_assigned:
                return False, f"Event {eid} appears in multiple clusters. Each event must be in exactly one cluster."
            if eid not in manifest_ids:
                return False, f"Event {eid} is not in the manifest. Only manifest events can be assigned."
            all_assigned.add(eid)
    missing = manifest_ids - all_assigned
    if missing:
        return False, f"Events not assigned to any cluster: {', '.join(sorted(missing))}"
    return True, ""


_MAX_TOOL_DESC_CHARS = 4000


def build_report_tool(cluster: dict, index: int, total: int, completed_reports: list[dict]) -> list[dict]:
    """Generate a dynamic write_incident tool with contract-only description."""
    receipt_lines = []
    for r in completed_reports:
        receipt_lines.append(f"  [{r['index']}] {r['summary'][:60]} -- {r['priority']} -- {len(r['affected_events'])} events")
    receipt = "\n".join(receipt_lines) if receipt_lines else "  (none yet)"

    desc = (
        f"Cluster {index} of {total}: {cluster.get('root_cause', '?')}\n"
        f"Platform and affected_events are pre-filled from your cluster plan.\n"
    )
    if completed_reports:
        desc += f"\nCompleted reports:\n{receipt}\n"
    remaining = total - index
    if remaining > 0:
        desc += f"\nAfter this report, {remaining} cluster(s) remain."
    else:
        desc += "\nThis is the final report."

    if len(desc) > _MAX_TOOL_DESC_CHARS:
        short_receipt = "\n".join(
            f"  [{r['index']}] {r['priority']} -- {len(r['affected_events'])} events"
            for r in completed_reports
        )
        desc = (
            f"Cluster {index} of {total}: {cluster.get('root_cause', '?')}\n"
            f"Platform and affected_events are pre-filled.\n"
            f"\nCompleted reports:\n{short_receipt}\n"
            f"\n{'This is the final report.' if remaining == 0 else f'{remaining} cluster(s) remain.'}"
        )

    from ..agents.llm.types import NIGHTWATCHER_TOOL_SCHEMAS
    base_schema = next(t for t in NIGHTWATCHER_TOOL_SCHEMAS if t["name"] == "write_incident")
    tool = {
        "name": "write_incident",
        "description": desc,
        "input_schema": base_schema["input_schema"],
    }
    return [tool]


def build_summary_tool(completed_reports: list[dict], metrics: dict) -> list[dict]:
    """Generate a dynamic post_shift_summary tool with full receipt."""
    receipt_lines = []
    for r in completed_reports:
        receipt_lines.append(
            f"  [{r['index']}] [{r['priority']}] {r.get('platform', '?')} -- {r['summary'][:80]} "
            f"({len(r['affected_events'])} events)"
        )
    receipt = "\n".join(receipt_lines) if receipt_lines else "  (no incidents created)"

    desc = (
        f"Post the end-of-shift summary to Slack.\n\n"
        f"Sweep metrics:\n"
        f"  Escalations: {metrics.get('escalation_count', '?')}\n"
        f"  Incidents: {metrics.get('incident_count', '?')}\n"
        f"  Noise reduction: {metrics.get('noise_reduction_pct', '?')}%\n\n"
        f"Incident reports:\n{receipt}"
    )
    from ..agents.llm.types import NIGHTWATCHER_TOOL_SCHEMAS
    base_schema = next(t for t in NIGHTWATCHER_TOOL_SCHEMAS if t["name"] == "post_shift_summary")
    return [{
        "name": "post_shift_summary",
        "description": desc,
        "input_schema": base_schema["input_schema"],
    }]


async def execute_tool(name: str, args: dict, ctx: NightwatcherContext) -> str:
    """Route a tool call to its handler. Returns result text for the LLM."""
    handlers = {
        "get_event_report": _handle_get_event_report,
        "search_journal": _handle_search_journal,
        "consult_deep_memory": _handle_consult_deep_memory,
        "dispatch_investigation": _handle_dispatch_investigation,
        "declare_clusters": _handle_declare_clusters,
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
    from ..memory.pulse import PulseContext
    pulse_ctx = PulseContext(event_id=None, turn=None, event_elapsed_s=0)
    results = await ctx.archivist.search(query, limit=5, context=pulse_ctx)
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

    async def on_progress(progress_data: dict) -> None:
        if ctx.broadcast:
            await ctx.broadcast({
                "type": "progress",
                "event_id": sweep_event_id,
                "actor": progress_data.get("actor", "sysadmin"),
                "message": progress_data.get("message", ""),
                "event_source": "nightwatcher",
            })

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
            on_progress=on_progress,
        )
    except Exception as e:
        result_text = f"Investigation dispatch failed: {e}"
    finally:
        try:
            await ctx.provisioner.terminate_agent(sweep_event_id)
        except Exception:
            logger.debug("Nightwatcher: failed to terminate sweep agent %s (may already be gone)", sweep_event_id)
    duration = round(time.time() - start, 1)
    ctx.dispatch_count += 1
    ctx.investigations.append(ShiftInvestigation(
        task=task_prompt, service=service,
        agent_result=result_text[:3000], duration_seconds=duration,
    ))
    logger.info("Nightwatcher investigation %d/%d: %s (%.1fs)", ctx.dispatch_count, ctx.dispatch_cap, service, duration)
    return result_text[:3000]


async def _handle_declare_clusters(args: dict, ctx: NightwatcherContext) -> str:
    clusters = args.get("clusters", [])
    ok, error = validate_cluster_plan(clusters, ctx.manifest_ids)
    if not ok:
        return f"Cluster plan validation failed: {error}"
    ctx.declared_clusters = clusters
    cluster_summary = "; ".join(
        f"[{i+1}] {c.get('root_cause', '?')} ({len(c.get('events', []))} events)"
        for i, c in enumerate(clusters)
    )
    logger.info("Nightwatcher cluster plan accepted: %d clusters", len(clusters))
    return f"Cluster plan accepted. {len(clusters)} clusters: {cluster_summary}"


async def _handle_write_incident(args: dict, ctx: NightwatcherContext, cluster: dict) -> str:
    """Write a single incident, merging LLM judgment with code-prefilled cluster fields."""
    if not ctx.smartsheet_adapter:
        return "Smartsheet adapter not configured. Incident not created."
    platform = cluster.get("platform", "")
    affected_events = cluster.get("events", [])
    summary = args.get("summary", "")[:200]
    status = args.get("status", "New")
    if VALID_STATUSES and status not in VALID_STATUSES:
        fallback_status = VALID_STATUSES[0] if VALID_STATUSES else "New"
        logger.warning("Nightwatcher: LLM provided invalid status '%s', defaulting to '%s'", status, fallback_status)
        status = fallback_status
    priority = args.get("priority", "Normal")
    if VALID_PRIORITIES and priority not in VALID_PRIORITIES:
        fallback_priority = VALID_PRIORITIES[0] if VALID_PRIORITIES else "Normal"
        logger.warning("Nightwatcher: LLM provided invalid priority '%s', defaulting to '%s'", priority, fallback_priority)
        priority = fallback_priority
    logger.info("Nightwatcher write_incident: cluster=%s, events=%d", cluster.get("root_cause", "?")[:50], len(affected_events))
    fields = {
        "Reporter e-mail": os.environ.get("SMARTSHEET_INCIDENT_REPORTER", ""),
        "Reporter Display Name": os.environ.get("SMARTSHEET_INCIDENT_REPORTER_NAME", "Darwin Nightwatcher"),
        "Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "Status": status,
        "Issue Type": os.environ.get("SMARTSHEET_INCIDENT_ISSUE_TYPE", "Task"),
        "Labels": os.environ.get("SMARTSHEET_INCIDENT_LABELS", ""),
        "Components": os.environ.get("SMARTSHEET_INCIDENT_COMPONENTS", ""),
        "Platform": platform,
        "Summary": summary,
        "Reason": args.get("description", ""),
        "Priority": priority,
    }
    try:
        result = await ctx.smartsheet_adapter.create_incident(fields)
        incident = ShiftIncident(
            platform=platform,
            summary=summary,
            description=args.get("description", ""),
            priority=priority,
            status=status,
            affected_events=affected_events,
            smartsheet_row_id=str(result.get("row_id", "")),
            smartsheet_url=result.get("sheet_url", ""),
        )
        ctx.created_incidents.append(incident)
        covered = {eid for inc in ctx.created_incidents for eid in inc.affected_events}
        remaining = ctx.manifest_ids - covered
        return (
            f"Incident created (row {result.get('row_id', '?')}). "
            f"{len(affected_events)} events consolidated. "
            f"Manifest coverage: {len(covered)}/{len(ctx.manifest_ids)}."
        )
    except Exception as e:
        ctx.failed_cluster_events.extend(affected_events)
        return f"Failed to create incident: {e}. Events will be restaged for next sweep."


async def _handle_post_shift_summary(args: dict, ctx: NightwatcherContext) -> str:
    summary = args.get("summary", "")
    if not summary.strip():
        return "Error: summary is empty. Provide the shift report text including escalation count, incident count, and key findings."
    ctx._summary_text = summary
    logger.info("Nightwatcher post_shift_summary: %d chars", len(summary))
    if ctx.slack_notify:
        try:
            await ctx.slack_notify(summary)
            return "Shift summary posted to Slack."
        except Exception as e:
            return f"Slack notification failed: {e}"
    return "Shift summary recorded (Slack not configured)."
