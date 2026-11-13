# BlackBoard/src/agents/handlers_cross_event.py
# @ai-rules:
# 1. [Pattern]: Cross-event inspection and sticky note handlers.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
# 5. [Security]: recall_pruned_turns applies PII redaction, XML fence stripping, and defangs [!call: to prevent prompt injection. Single turn returns up to 30k chars of raw evidence; range returns up to 3k chars.
# 6. [Pattern]: inspect_event omits raw dumps for recalled turns to prevent secondary context inflation.
"""Cross-event inspection and sticky note tool handlers."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..models import ConversationTurn, _resolve_phase
from ..utils.pii_redaction import redact_pii
from .context_parts import _strip_xml_fences

if TYPE_CHECKING:
    from .tool_router import ToolContext

logger = logging.getLogger("darwin.brain")


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
        if getattr(t, "waitingFor", None) == "recall_pruned_turns":
            dump_len = len(t.thoughts or t.evidence or t.result or "")
            lines.append(f"[{t.action}] (recalled pruned turns — {dump_len} chars omitted)")
        else:
            content = t.thoughts or t.result or ""
            lines.append(f"[{t.action}] {content}")
    result_text = header + "\n".join(lines)
    result_text = result_text[:int(os.getenv("AGENT_RESULT_MAX_CHARS", "100000"))]
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


def _coerce_turn_int(val: object, default: int) -> int:
    if val is None or isinstance(val, bool):
        return default
    try:
        f = float(val)
        if not (-1_000_000 <= f <= 1_000_000):
            return default
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return default


async def handle_recall_pruned_turns(
    ctx: ToolContext, event_id: str, args: dict, response_parts: list[dict] | None,
) -> bool:
    """Read turns from the current event that were pruned from context."""
    bb = ctx.get_blackboard()
    event = await bb.get_event(event_id)
    if not event or not event.conversation:
        turn = ConversationTurn(
            turn=(await ctx.next_turn_number(event_id)),
            actor="brain", action="tool_result",
            thoughts="No conversation found.",
            waitingFor="recall_pruned_turns",
            response_parts=response_parts,
        )
        await ctx.append_and_broadcast(event_id, turn)
        return True

    raw_from = _coerce_turn_int(args.get("from_turn"), 1)
    raw_to_arg = args.get("to_turn")
    raw_to = raw_from if ("from_turn" in args and raw_to_arg is None) else _coerce_turn_int(raw_to_arg, 10)
    is_single_turn = (raw_from == raw_to)

    from_turn = max(1, raw_from)
    to_turn = min(len(event.conversation), raw_to)
    if to_turn - from_turn >= 20:
        to_turn = from_turn + 19

    turns = [t for t in event.conversation if from_turn <= t.turn <= to_turn]
    blocks = []
    for t in turns:
        if is_single_turn:
            content = t.evidence or t.result or t.thoughts or ""
            content = redact_pii(content)
            content = _strip_xml_fences(content)
            content = content.replace("[!call:", "[call:")
            if len(content) > 30000:
                content = content[:30000] + "\n...(truncated)"
        else:
            content = t.thoughts or t.evidence or t.result or ""
            content = redact_pii(content)
            content = _strip_xml_fences(content)
            content = content.replace("[!call:", "[call:")
            if len(content) > 3000:
                content = content[:3000] + "...(truncated)"
        blocks.append(f"[T{t.turn} {t.actor}.{t.action}]: {content}")

    result_text = "\n\n".join(blocks) if blocks else "(no turns in range)"
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain", action="tool_result",
        thoughts=result_text,
        evidence=result_text,
        waitingFor="recall_pruned_turns",
        response_parts=response_parts,
    )
    await ctx.append_and_broadcast(event_id, turn)
    return True


# ---------------------------------------------------------------------------
# Registry registration
# ---------------------------------------------------------------------------
from .tool_router import HANDLER_REGISTRY

HANDLER_REGISTRY["inspect_event"] = handle_inspect_event
HANDLER_REGISTRY["post_sticky_note"] = handle_post_sticky_note
HANDLER_REGISTRY["read_sticky_notes"] = handle_read_sticky_notes
HANDLER_REGISTRY["recall_pruned_turns"] = handle_recall_pruned_turns
