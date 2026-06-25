# BlackBoard/src/agents/handlers_data.py
# @ai-rules:
# 1. [Pattern]: Group A "pure data" handlers. Minimal ToolContext surface.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
"""Group A: 16 pure data tool handlers (low Brain coupling)."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..models import ConversationTurn, _resolve_domain, _resolve_phase

if TYPE_CHECKING:
    from .tool_router import ToolContext

logger = logging.getLogger("darwin.brain")


def _safe_int(val, *, default: int | None = None) -> int | None:
    if val is None or isinstance(val, bool):
        return default
    try:
        result = int(val)
        return result if result > 0 else default
    except (ValueError, TypeError, OverflowError):
        return default


# ---------------------------------------------------------------------------
# record_observation
# ---------------------------------------------------------------------------
async def handle_record_observation(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    name = args.get("name", "")
    value = args.get("value", 0)
    unit = args.get("unit", "")
    result = await ctx.get_blackboard().record_observation(event_id, name, value, unit)
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        thoughts=(
            f"Recorded observation '{name}' = {value}"
            f"{(' ' + unit) if unit else ''}"
            f" (point #{result['count']}, event age {result['event_age_minutes']}m)"
        ),
        waitingFor="record_observation",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# list_observations
# ---------------------------------------------------------------------------
async def handle_list_observations(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    result = await ctx.get_blackboard().list_observations()
    if not result["observations"]:
        summary_text = "No observations recorded yet."
    else:
        lines = [f"{len(result['observations'])} observation series (global, last 7 days):"]
        for s in result["observations"]:
            events_in_series = {p.get("event_id", "") for p in s["points"] if p.get("event_id")}
            lines.append(
                f"  • {s['name']}: {s['count']} pts, "
                f"range [{s['min']}–{s['max']}] {s['unit']}, "
                f"latest={s['latest_value']}, trend={s['trend']}, "
                f"span={s['span_minutes']}m, "
                f"events={len(events_in_series)}"
            )
        summary_text = "\n".join(lines)
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        thoughts=summary_text,
        waitingFor="list_observations",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# take_note
# ---------------------------------------------------------------------------
async def handle_take_note(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    content = args.get("content", "")
    category = args.get("category", "convention")
    bb = ctx.get_blackboard()
    if category not in bb.VALID_CATEGORIES:
        category = "convention"
    result = await bb.take_note(event_id, content, category)
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        thoughts=f"Noted ({result['note_id'][:8]}): {content[:80]}",
        waitingFor="take_note",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# review_notes
# ---------------------------------------------------------------------------
async def handle_review_notes(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    notes = await ctx.get_blackboard().get_notes()
    if not notes:
        summary_text = "No field notes recorded yet."
    else:
        lines = [f"{len(notes)} field notes in notebook:"]
        for n in notes:
            lines.append(
                f"  • [{n.get('category', '?')}] {n.get('content', '')[:120]}"
                f" (evt:{n.get('event_id', '?')[:8]}, {n.get('timestamp', '?')})"
            )
        summary_text = "\n".join(lines)
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        thoughts=summary_text,
        waitingFor="review_notes",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# lookup_service
# ---------------------------------------------------------------------------
async def handle_lookup_service(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    service_name = args.get("service_name", "")
    bb = ctx.get_blackboard()

    event_doc = await bb.get_event(event_id)
    subject_type = getattr(event_doc, "subject_type", "service") if event_doc else "service"
    if subject_type != "service":
        context_label = {
            "kargo_stage": "kargo_context",
            "jira": "jira_context",
            "system": "system-level context",
        }.get(subject_type, subject_type)
        result_text = (
            f"## lookup_service: Not applicable\n\n"
            f"This event's subject is a {subject_type}, not a monitored K8s deployment.\n"
            f"The relevant context ({context_label}) is already in your prompt."
        )
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            waitingFor="lookup_service",
            evidence=result_text,
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False

    svc = await bb.get_service(service_name)
    if svc:
        rows = [f"| Version | {svc.version} |"]
        if svc.gitops_repo:
            rows.append(f"| GitOps Repo | {svc.gitops_repo} |")
        if svc.gitops_repo_url:
            rows.append(f"| Repo URL | {svc.gitops_repo_url} |")
        if svc.gitops_config_path:
            rows.append(f"| Config Path | {svc.gitops_config_path} |")
        if svc.replicas_ready is not None:
            rows.append(f"| Replicas | {svc.replicas_ready}/{svc.replicas_desired} |")
        rows.append(f"| CPU | {svc.metrics.cpu:.1f}% |")
        rows.append(f"| Memory | {svc.metrics.memory:.1f}% |")
        if svc.escalation_flag:
            rows.append(f"| Escalation | {svc.escalation_flag} |")
        result_text = f"## Service: {service_name}\n\n| Field | Value |\n|---|---|\n" + "\n".join(rows)
    else:
        known = await bb.get_services()
        result_text = f"## Service: {service_name}\n\nNot found. Known services: {', '.join(sorted(known)) if known else 'none'}"

    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="lookup_service",
        evidence=result_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# consult_deep_memory
# ---------------------------------------------------------------------------
async def handle_consult_deep_memory(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    query = args.get("query", "")
    time_range = _safe_int(args.get("time_range_hours"))
    min_dur = _safe_int(args.get("min_duration_minutes"))
    svc = str(args.get("service") or "").strip() or None
    bb = ctx.get_blackboard()

    conditions: list[dict] = []
    if time_range:
        cutoff = time.time() - (time_range * 3600)
        conditions.append({"key": "closed_at", "range": {"gte": cutoff}})
    if min_dur:
        conditions.append({"key": "duration_seconds", "range": {"gte": min_dur * 60}})
    if svc:
        conditions.append({"key": "service", "match": {"value": svc}})
    qdrant_filter = {"must": conditions} if conditions else None
    if qdrant_filter:
        logger.debug(
            "Deep memory filters applied: %s for event %s",
            [f for f in ['time_range' if time_range else '', 'min_dur' if min_dur else '', 'svc' if svc else ''] if f],
            event_id,
        )

    ev = await bb.get_event(event_id)
    safe_query = query.replace('"', '\\"')
    filter_parts: list[str] = []
    if time_range:
        filter_parts.append(f"time={time_range}h")
    if min_dur:
        filter_parts.append(f"dur>={min_dur}m")
    if svc:
        filter_parts.append(f"svc={svc}")
    filter_tag = f" [{','.join(filter_parts)}]" if filter_parts else " [unfiltered]"
    query_marker = f'Deep Memory: "{safe_query}"{filter_tag}'
    already_consulted = any(
        t.action in ("think", "thoughts", "intermediate", "response", "tool_result")
        and t.evidence and query_marker in (t.evidence or "")
        for t in (ev.conversation if ev else [])
    )
    if already_consulted:
        logger.info(f"Deep memory already consulted for {event_id} query={query!r} -- returning cached results")
        cached_evidence = next(
            (t.evidence for t in (ev.conversation if ev else [])
             if t.action in ("think", "thoughts", "intermediate", "response", "tool_result")
             and t.evidence and query_marker in t.evidence),
            "Deep memory was already consulted (no cached results).",
        )
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            waitingFor="consult_deep_memory",
            evidence=f"[Already consulted] {cached_evidence}",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        if "No historical patterns" in cached_evidence or "No results" in cached_evidence or "No events match" in cached_evidence:
            return False
        return True

    archivist = ctx.get_agent_instance("_archivist_memory")
    has_results = False

    from ..memory.pulse import PulseContext
    ev_for_ctx = ev or await bb.get_event(event_id)
    pulse_ctx = PulseContext(
        event_id=event_id,
        turn=len(ev_for_ctx.conversation) if ev_for_ctx else 0,
        event_elapsed_s=int(time.time() - ev_for_ctx.conversation[0].timestamp) if ev_for_ctx and ev_for_ctx.conversation else 0,
        event_source=ev_for_ctx.source if ev_for_ctx else None,
    )

    memory_text = f"# Deep Memory: \"{safe_query}\"{filter_tag}\n\n"

    query_vector = None
    if archivist and hasattr(archivist, "embed_query"):
        try:
            query_vector = await archivist.embed_query(query)
        except Exception as e:
            logger.debug(f"embed_query failed, each search will embed individually: {e}")

    if archivist and hasattr(archivist, "search_knowledge"):
        try:
            knowledge = await archivist.search_knowledge(query, limit=3, context=pulse_ctx, vector=query_vector)
        except Exception as e:
            logger.warning(f"Deep memory knowledge search failed: {e}")
            knowledge = None
        if knowledge:
            has_results = True
            memory_text += "### Reference Facts\n"
            for i, r in enumerate(knowledge, 1):
                p = r.get("payload", {})
                stale_tag = " [STALE - verify before acting]" if r.get("stale") else ""
                fact_text = p.get("fact", "?")[:200]
                memory_text += (
                    f"{i}. **{p.get('topic', '?')}** ({p.get('scope', '?')}, confidence: {p.get('confidence', '?')}){stale_tag}\n"
                    f"   - {fact_text}\n"
                    f"   - Source: {p.get('source', '?')}\n"
                )
            memory_text += "\n"

    if archivist and hasattr(archivist, "search_lessons"):
        try:
            lessons = await archivist.search_lessons(query, limit=3, context=pulse_ctx, vector=query_vector)
        except Exception as e:
            logger.warning(f"Deep memory lesson search failed: {e}")
            lessons = None
        if lessons:
            has_results = True
            memory_text += "### Lessons Learned\n"
            for i, r in enumerate(lessons, 1):
                p = r.get("payload", {})
                memory_text += (
                    f"{i}. **{p.get('title', '?')}** (score: {r.get('score', 0):.2f})\n"
                    f"   - Pattern: {p.get('pattern', '?')}\n"
                )
                if p.get("anti_pattern"):
                    memory_text += f"   - Anti-pattern: {p['anti_pattern']}\n"
            memory_text += "\n"

    if archivist and hasattr(archivist, "search"):
        try:
            results = await archivist.search(query, limit=5, context=pulse_ctx, vector=query_vector, filter=qdrant_filter)
        except Exception as e:
            logger.warning(f"Deep memory event search failed: {e}")
            results = None
        if results:
            has_results = True
            memory_text += "### Past Events\n"
            for i, r in enumerate(results, 1):
                p = r.get("payload", {})
                dur = p.get("duration_seconds", 0)
                dur_m = f"{dur // 60}m" if dur else "?"
                defers = p.get("defer_patterns", [])
                total_defer = sum(d.get("duration_seconds", 0) for d in defers if isinstance(d, dict))
                defer_m = f"{total_defer // 60}m" if total_defer else "0m"
                timings = p.get("operational_timings", [])
                timing_str = ", ".join(
                    f"{t.get('process', '?')}={t.get('duration_seconds', 0) // 60}m"
                    for t in timings if isinstance(t, dict)
                ) or "none"
                domain_str = p.get("brain_domain", p.get("domain", "?"))
                corrected = " [CORRECTED]" if p.get("corrected") else ""
                memory_text += (
                    f"{i}. domain: {domain_str} | score: {r.get('score', 0):.2f}{corrected}\n"
                    f"   - Pattern: {p.get('symptom', '?')}\n"
                    f"   - Root cause: {p.get('root_cause', '?')}\n"
                    f"   - Fix: {p.get('fix_action', '?')}\n"
                    f"   - Service: {p.get('service', '?')} | Duration: {dur_m}, defers: {defer_m}, timings: [{timing_str}], outcome: {p.get('outcome', '?')}\n"
                )

    if not has_results:
        if qdrant_filter:
            filter_desc = ", ".join(filter_parts) if filter_parts else "active filters"
            memory_text += (
                f"No events match the applied filters ({filter_desc}). "
                "Consider widening the time range, removing duration or service constraints, "
                "or searching with different keywords."
            )
        else:
            memory_text += (
                "No historical patterns match this query. "
                "Consider whether the event classification is accurate, "
                "or try searching with different keywords that describe the symptom or root cause. "
                "The ops journal for this service may also have relevant entries."
            )

    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="consult_deep_memory",
        evidence=memory_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# lookup_journal
# ---------------------------------------------------------------------------
async def handle_lookup_journal(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    service_name = args.get("service_name", "")
    bb = ctx.get_blackboard()
    if service_name:
        entries = await ctx.get_cached_journal(service_name)
        if entries:
            header = f"## Ops Journal: {service_name}\n\n{len(entries)} entries:\n\n"
            journal_text = header + "\n".join(f"- {e}" for e in entries)
        else:
            journal_text = f"## Ops Journal: {service_name}\n\nNo entries found."
    else:
        entries = await bb.get_recent_journal_entries()
        if entries:
            header = f"## Ops Journal: all services\n\n{len(entries)} entries:\n\n"
            journal_text = header + "\n".join(f"- {e}" for e in entries)
        else:
            journal_text = "## Ops Journal\n\nNo entries found across any service."
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="lookup_journal",
        evidence=journal_text,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# create_plan
# ---------------------------------------------------------------------------
async def handle_create_plan(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    steps = args.get("steps", [])
    reasoning = args.get("reasoning", "")
    if not steps:
        logger.warning(f"create_plan called with no steps for {event_id}")
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Plan creation needs at least one step with an assigned participant and objective. "
                     "Review the conversation to identify which agents should act and on what.",
            waitingFor="create_plan",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    plan_lines = [f"## Plan\n\n{reasoning}\n"]
    for s in steps:
        plan_lines.append(f"{s.get('id', '?')}. **{s.get('agent', '?')}**: {s.get('summary', '')}")
    plan_md = "\n".join(plan_lines)
    step_map = [{"id": str(s.get("id", "")), "agent": s.get("agent", ""), "summary": s.get("summary", "")} for s in steps]
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="plan",
        plan=plan_md,
        thoughts=f"Plan created: {len(steps)} steps. {reasoning}",
        taskForAgent={"steps": step_map, "source": "brain"},
        waitingFor="create_plan",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    logger.info(f"Brain chalked plan for {event_id}: {len(steps)} steps")
    return True


# ---------------------------------------------------------------------------
# get_plan_progress
# ---------------------------------------------------------------------------
async def handle_get_plan_progress(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    bb = ctx.get_blackboard()
    event_doc = await bb.get_event(event_id)
    if not event_doc:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Event data is temporarily unavailable. "
                     "Wait for the next update from the conversation.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    plan_turn = None
    for t in reversed(event_doc.conversation):
        if t.action == "plan" and t.taskForAgent and "steps" in t.taskForAgent:
            plan_turn = t
            break
    if not plan_turn:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain", action="tool_result",
            waitingFor="get_plan_progress",
            evidence="## Plan Progress\n\nNo plan has been created for this event yet. "
                     "If a plan is needed, create one first with the appropriate agents and steps.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    steps = {s["id"]: {**s, "status": "pending"} for s in plan_turn.taskForAgent["steps"]}
    for t in event_doc.conversation:
        if t.action == "plan_step" and t.taskForAgent and "step_id" in t.taskForAgent:
            sid = t.taskForAgent["step_id"]
            if sid in steps:
                steps[sid]["status"] = t.taskForAgent.get("status", "completed")
    progress = list(steps.values())
    done = sum(1 for s in progress if s["status"] == "completed")
    summary = f"## Plan Progress\n\n{done}/{len(progress)} steps completed:\n\n"
    for s in progress:
        icon = {"completed": "- [x]", "in_progress": "- [~]", "blocked": "- [!]"}.get(s["status"], "- [ ]")
        summary += f"{icon} Step {s['id']}: {s.get('summary', '')} ({s.get('agent', '?')}) -- {s['status']}\n"
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain", action="tool_result",
        waitingFor="get_plan_progress",
        evidence=summary.strip(),
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# inspect_event
# ---------------------------------------------------------------------------
async def handle_inspect_event(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    target_id = args.get("event_id", "").strip()
    bb = ctx.get_blackboard()
    if not target_id:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Error: event_id is required.",
            waitingFor="inspect_event",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    target_event = await bb.get_event(target_id)
    if not target_event:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts=f"Event {target_id} not found in active storage.",
            waitingFor="inspect_event",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    age_seconds = time.time() - (target_event.queued_at or target_event.processing_started_at or time.time())
    age_h = int(age_seconds // 3600)
    age_m = int((age_seconds % 3600) // 60)
    age_str = f"{age_h}h {age_m}m"
    header = (
        f"## Event: {target_id}\n"
        f"Phase: {_resolve_phase(target_event.brain_phase)} | "
        f"Status: {target_event.status.value if target_event.status else 'unknown'} | "
        f"Age: {age_str}\n"
        f"Source: {target_event.source or 'unknown'} | "
        f"Service: {target_event.service or '?'}\n"
    )
    evidence = target_event.event.evidence if target_event.event else None
    if evidence and hasattr(evidence, 'display_text') and evidence.display_text:
        header += f"\n## Original Request\n{evidence.display_text}\n"
    my_turns = [t for t in target_event.conversation if t.actor == "brain"]
    lines = [f"\n## My Actions ({len(my_turns)} turns)"]
    for t in my_turns:
        content = t.thoughts or t.result or ""
        lines.append(f"[{t.action}] {content}")
    result_text = header + "\n".join(lines)
    result_text = result_text[:15000]
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        thoughts=result_text,
        waitingFor="inspect_event",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# post_sticky_note
# ---------------------------------------------------------------------------
async def handle_post_sticky_note(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    target_id = args.get("event_id", "").strip()
    content = args.get("content", "").strip()
    bb = ctx.get_blackboard()
    if not target_id or not content:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Error: event_id and content are required.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    target_event = await bb.get_event(target_id)
    if not target_event:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts=f"Event {target_id} not found — cannot post note.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    notes = list(getattr(target_event, "sticky_notes", None) or [])
    notes.append({
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "content": content,
        "read": False,
    })
    new_unread = (getattr(target_event, "unread_notes", 0) or 0) + 1
    await bb.update_event_sticky_notes(target_id, notes, new_unread)
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="post_sticky_note",
        thoughts=f"Sticky note sent to {target_id}.",
        result=f"Sticky note sent to {target_id} -- proceed with next action.",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    logger.info(f"Sticky note posted from {event_id} to {target_id}")
    return True


# ---------------------------------------------------------------------------
# read_sticky_notes
# ---------------------------------------------------------------------------
async def handle_read_sticky_notes(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    target_id = args.get("event_id", "").strip()
    bb = ctx.get_blackboard()
    if not target_id:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Error: event_id is required.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    target_event = await bb.get_event(target_id)
    if not target_event:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts=f"Event {target_id} not found.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    notes = list(getattr(target_event, "sticky_notes", None) or [])
    unread_notes = [n for n in notes if not n.get("read", False)]
    if not unread_notes:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="No unread notes on this event.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    lines = [f"## {len(unread_notes)} Unread Note(s)\n"]
    for n in unread_notes:
        lines.append(f"**{n.get('timestamp', '?')}**: {n.get('content', '')}")
        n["read"] = True
    await bb.update_event_sticky_notes(target_id, notes, 0)
    formatted = "\n".join(lines)
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="tool_result",
        waitingFor="read_sticky_notes",
        thoughts=formatted,
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    logger.info(f"Read {len(unread_notes)} sticky notes on {target_id}")
    return True


# ---------------------------------------------------------------------------
# set_phase
# ---------------------------------------------------------------------------
async def handle_set_phase(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    phase = _resolve_phase(args.get("phase", "triage"))
    reasoning = args.get("reasoning", "")
    bb = ctx.get_blackboard()
    event_doc = await bb.get_event(event_id)
    current_phase = _resolve_phase(event_doc.brain_phase) if event_doc else None
    if current_phase is not None and phase == current_phase:
        logger.debug(f"set_phase: confirmed {phase} for {event_id}")
        if event_doc and event_doc.brain_phase != phase:
            await bb.update_event_phase(event_id, phase)
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="phase",
            thoughts=f"Phase: {phase.upper()} (confirmed). {reasoning}",
            waitingFor="set_phase",
            response_parts=response_parts,
            timestamp=time.time(),
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True
    await bb.update_event_phase(event_id, phase)
    thoughts = f"Phase: {phase.upper()}. {reasoning}"
    logger.info(f"Phase transition: {current_phase} -> {phase} for {event_id} ({reasoning})")
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="phase",
        thoughts=thoughts,
        waitingFor="set_phase",
        response_parts=response_parts,
        timestamp=time.time(),
    )
    await ctx.append_and_broadcast(event_id, turn)
    await ctx.broadcast({
        "type": "phase_updated",
        "event_id": event_id,
        "phase": phase,
    })
    await ctx.emit_pulse(event_id, [(f"phase:{phase}", "phase")])
    return True


# ---------------------------------------------------------------------------
# re_trigger_aligner
# ---------------------------------------------------------------------------
async def handle_re_trigger_aligner(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    service = args.get("service", "")
    condition = args.get("check_condition", "")
    aligner = ctx.get_agent_instance("_aligner")
    if not aligner or not service:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Service health data is not available for this event. "
                     "Consider checking the ops journal for recent entries, "
                     "or dispatching an agent to investigate directly.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    try:
        state = await aligner.check_state(service)
    except Exception as e:
        logger.warning(f"re_trigger_aligner check_state failed for {service}: {e}")
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Service health check failed. "
                     "Consider deferring briefly and retrying, "
                     "or dispatching an agent to investigate directly.",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return False
    verify_turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="verify",
        thoughts=f"Re-triggering Aligner to check: {condition}",
        evidence=f"target_service:{service}",
    )
    await ctx.append_and_broadcast(event_id, verify_turn)
    confirm_turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="aligner",
        action="confirm",
        evidence=(
            f"Service: {state['service']}, "
            f"CPU: {state.get('cpu', 0):.1f}%, "
            f"Memory: {state.get('memory', 0):.1f}%, "
            f"Replicas: {state.get('replicas_ready', '?')}/{state.get('replicas_desired', '?')}"
        ),
    )
    await ctx.append_and_broadcast(event_id, confirm_turn)
    return False


# ---------------------------------------------------------------------------
# wait_for_verification
# ---------------------------------------------------------------------------
async def handle_wait_for_verification(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    condition = args.get("condition", "")
    bb = ctx.get_blackboard()
    event = await bb.get_event(event_id)
    target_service = event.service if event else ""
    aligner = ctx.get_agent_instance("_aligner")
    if aligner and target_service:
        state = await aligner.check_state(target_service)
        verify_turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="verify",
            thoughts=f"Waiting for verification: {condition}",
            evidence=f"target_service:{target_service}",
            waitingFor="wait_for_verification",
        )
        await ctx.append_and_broadcast(event_id, verify_turn)
        confirm_turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="aligner",
            action="confirm",
            evidence=(
                f"Service: {state['service']}, "
                f"CPU: {state.get('cpu', 0):.1f}%, "
                f"Memory: {state.get('memory', 0):.1f}%, "
                f"Replicas: {state.get('replicas_ready', '?')}/{state.get('replicas_desired', '?')}"
            ),
            waitingFor="wait_for_verification",
        )
        await ctx.append_and_broadcast(event_id, confirm_turn)
    else:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain",
            action="tool_result",
            thoughts="Verification data is not available for this service right now. "
                     "Consider what other tools or participants in the conversation "
                     "might confirm whether the situation has changed since the last check.",
            waitingFor="wait_for_verification",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# notify_gitlab_result
# ---------------------------------------------------------------------------
async def handle_notify_gitlab_result(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    bb = ctx.get_blackboard()
    event_doc = await bb.get_event(event_id)
    gl_ctx = None
    if event_doc and event_doc.event.evidence:
        ev = event_doc.event.evidence
        gl_ctx = getattr(ev, "gitlab_context", None) if hasattr(ev, "gitlab_context") else None
    if not gl_ctx:
        result_text = "Cannot notify GitLab: no gitlab_context in event evidence. This tool is for headhunter-sourced events only."
        await ctx.emit_pulse(event_id, [("tool:notify_gitlab_result", "tool", 0.3)])
    else:
        project_id = args.get("project_id", gl_ctx.get("project_id"))
        mr_iid = args.get("mr_iid", gl_ctx.get("mr_iid"))
        result_type = args.get("result", "success")
        summary = args.get("summary", "")
        reassign = args.get("reassign_reviewer", False)
        result_text = (
            f"GitLab notification queued: {result_type} on !{mr_iid} (project {project_id}). "
            f"Summary: {summary[:200]}. Reassign reviewer: {reassign}. "
            f"Feedback will be posted by Headhunter feedback loop on event close."
        )
        logger.info(f"notify_gitlab_result: event={event_id} project={project_id} mr=!{mr_iid} result={result_type}")
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain",
        action="notify",
        thoughts=result_text,
        waitingFor="notify_gitlab_result",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# Registry registration
# ---------------------------------------------------------------------------
from .tool_router import HANDLER_REGISTRY

HANDLER_REGISTRY["record_observation"] = handle_record_observation
HANDLER_REGISTRY["list_observations"] = handle_list_observations
HANDLER_REGISTRY["take_note"] = handle_take_note
HANDLER_REGISTRY["review_notes"] = handle_review_notes
HANDLER_REGISTRY["lookup_service"] = handle_lookup_service
HANDLER_REGISTRY["consult_deep_memory"] = handle_consult_deep_memory
HANDLER_REGISTRY["lookup_journal"] = handle_lookup_journal
HANDLER_REGISTRY["create_plan"] = handle_create_plan
HANDLER_REGISTRY["get_plan_progress"] = handle_get_plan_progress
HANDLER_REGISTRY["inspect_event"] = handle_inspect_event
HANDLER_REGISTRY["post_sticky_note"] = handle_post_sticky_note
HANDLER_REGISTRY["read_sticky_notes"] = handle_read_sticky_notes
HANDLER_REGISTRY["set_phase"] = handle_set_phase
HANDLER_REGISTRY["re_trigger_aligner"] = handle_re_trigger_aligner
HANDLER_REGISTRY["wait_for_verification"] = handle_wait_for_verification
HANDLER_REGISTRY["notify_gitlab_result"] = handle_notify_gitlab_result
