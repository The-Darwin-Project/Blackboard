# BlackBoard/src/agents/handlers_observations.py
# @ai-rules:
# 1. [Pattern]: Observation + field notes handlers. Minimal ToolContext surface.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
# 5. [Pattern]: handle_take_note prefixes the thoughts turn with `[{category}]` (e.g. "Noted [correction]").
#    Archivist's archive_event() reads this text to detect field-note corrections during archival.
"""Observation and field notes tool handlers."""
from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import ConversationTurn

if TYPE_CHECKING:
    from .tool_router import ToolContext


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


async def handle_list_observations(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    bb = ctx.get_blackboard()
    result = await bb.list_observations()
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

    ev = await bb.get_event(event_id)
    if ev and ev.source in ("chat", "slack"):
        last_user = next(
            (t for t in reversed(ev.conversation) if t.actor == "user"), None
        )
        if last_user:
            user_text = last_user.evidence or last_user.thoughts or ""
            if user_text:
                summary_text += f"\n\n---\nRespond to the user: {user_text}"

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
        thoughts=f"Noted [{category}] ({result['note_id'][:8]}): {content}",
        waitingFor="take_note",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


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
# Registry registration
# ---------------------------------------------------------------------------
from .tool_router import HANDLER_REGISTRY

HANDLER_REGISTRY["record_observation"] = handle_record_observation
HANDLER_REGISTRY["list_observations"] = handle_list_observations
HANDLER_REGISTRY["take_note"] = handle_take_note
HANDLER_REGISTRY["review_notes"] = handle_review_notes
