# BlackBoard/src/agents/handlers_cross_event.py
# @ai-rules:
# 1. [Pattern]: Cross-event inspection and sticky note handlers.
# 2. [Constraint]: No Brain import. All state access via ToolContext protocol.
# 3. [Pattern]: Every handler returns bool (True = re-invoke LLM, False = stop).
# 4. [Constraint]: Called within per-event asyncio.Lock — MUST NOT re-acquire.
# 5. [Security]: recall_pruned_turns sanitizes in THIS order via _sanitize_recalled: pre-cap raw text (bounds the
#    regex work on the event loop) -> strip_xml_fences (looped) -> redact_pii -> defang [!call: -> final truncate.
#    Strip MUST precede redaction: a fence tag spliced inside a secret/email otherwise survives redact_pii and
#    rejoins after the strip. Single turn returns up to 30k chars; range returns up to 3k chars per turn.
# 6. [Pattern]: inspect_event omits raw dumps for recalled turns to prevent secondary context inflation.
# 7. [Pattern]: The recall result is stored ONCE (in `thoughts`; Brain replay reads `evidence or thoughts`), and
#    Brain exempts waitingFor="recall_pruned_turns" turns from evidence decay (no recall/decay ping-pong).
"""Cross-event inspection and sticky note tool handlers."""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..models import ConversationTurn, _resolve_phase
from ..utils.pii_redaction import redact_pii
from ..utils.prompt_sanitize import strip_xml_fences

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


_RECALL_SINGLE_TURN_MAX_CHARS = 30000
_RECALL_RANGE_TURN_MAX_CHARS = 3000
_RECALL_MAX_RANGE_TURNS = 20
# Raw text is cut to this multiple of the output cap BEFORE any regex runs (headroom for stripped tags).
_RECALL_RAW_CEILING_FACTOR = 2


def _parse_turn_int(val: object) -> int | None:
    """Strict int coercion for a turn bound; None when ``val`` is not a usable finite number."""
    if val is None or isinstance(val, bool):
        return None
    try:
        f = float(val)
        if not (-1_000_000 <= f <= 1_000_000):
            return None
        return int(f)
    except (ValueError, TypeError, OverflowError):
        return None


def _coerce_turn_int(val: object, default: int) -> int:
    parsed = _parse_turn_int(val)
    return default if parsed is None else parsed


def _sanitize_recalled(raw: str, max_chars: int, marker: str) -> str:
    """Sanitize one recalled turn payload for re-injection into the prompt.

    Order is load-bearing: pre-cap -> strip fences (looped) -> redact PII -> defang -> truncate.
    """
    text = raw or ""
    ceiling = max_chars * _RECALL_RAW_CEILING_FACTOR
    if len(text) > ceiling:
        text = text[:ceiling]
    text = strip_xml_fences(text)
    text = redact_pii(text)
    text = text.replace("[!call:", "[call:")
    if len(text) > max_chars:
        text = text[:max_chars] + marker
    return text


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

    for key in ("from_turn", "to_turn"):
        supplied = args.get(key)
        if supplied is not None and _parse_turn_int(supplied) is None:
            turn = ConversationTurn(
                turn=(await ctx.next_turn_number(event_id)),
                actor="brain", action="tool_result",
                thoughts=(
                    f"Error: {key} must be an integer turn number between 1 and "
                    f"{len(event.conversation)}; nothing was recalled."
                ),
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
    if to_turn - from_turn >= _RECALL_MAX_RANGE_TURNS:
        to_turn = from_turn + _RECALL_MAX_RANGE_TURNS - 1

    turns = [t for t in event.conversation if from_turn <= t.turn <= to_turn]
    blocks = []
    for t in turns:
        if is_single_turn:
            content = _sanitize_recalled(
                t.evidence or t.result or t.thoughts or "",
                _RECALL_SINGLE_TURN_MAX_CHARS, "\n...(truncated)",
            )
        else:
            content = _sanitize_recalled(
                t.thoughts or t.evidence or t.result or "",
                _RECALL_RANGE_TURN_MAX_CHARS, "...(truncated)",
            )
        blocks.append(f"[T{t.turn} {t.actor}.{t.action}]: {content}")

    result_text = "\n\n".join(blocks) if blocks else "(no turns in range)"
    turn = ConversationTurn(
        turn=(await ctx.next_turn_number(event_id)),
        actor="brain", action="tool_result",
        thoughts=result_text,
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
