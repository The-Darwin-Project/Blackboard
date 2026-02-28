# BlackBoard/src/channels/formatter.py
# @ai-rules:
# 1. [Constraint]: Pure functions only -- no I/O, no Slack API calls. Returns Block Kit dicts.
# 2. [Pattern]: format_turn dispatches on actor.action pattern (e.g., "brain.think", "brain.route").
# 3. [Gotcha]: Slack Block Kit text limit is 3000 chars per section. Truncate long results.
"""Convert ConversationTurn objects to Slack Block Kit payloads."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models import ConversationTurn, EventDocument

# Slack section text limit (Block Kit)
_MAX_TEXT = 2900

AGENT_COLORS: dict[str, str] = {
    "architect": "#3b82f6",
    "sysadmin": "#f59e0b",
    "developer": "#10b981",
    "qe": "#fb7185",
}

AGENT_EMOJI: dict[str, str] = {
    "architect": "\U0001f4d0",
    "sysadmin": "\U0001f527",
    "developer": "\U0001f4bb",
    "qe": "\U0001f9ea",
}


import re


def _md_to_mrkdwn(text: str) -> str:
    """Convert standard Markdown to Slack mrkdwn format.

    Slack uses *bold*, _italic_, ~strike~, and ```code``` but NOT **bold** or ### headings.
    """
    # Headers: ### Heading -> *Heading*
    text = re.sub(r"^#{1,6}\s+(.+)$", r"*\1*", text, flags=re.MULTILINE)
    # Bold: **text** -> *text*
    text = re.sub(r"\*\*(.+?)\*\*", r"*\1*", text)
    # Inline code with backticks stays the same (Slack supports `code`)
    # Fenced code blocks stay the same (Slack supports ```)
    # Links: [text](url) -> <url|text>
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"<\2|\1>", text)
    return text


def _truncate(text: str, limit: int = _MAX_TEXT) -> str:
    """Truncate text for Slack Block Kit section limits."""
    if len(text) <= limit:
        return text
    return text[: limit - 20] + "\n...(truncated)"


def _section(text: str) -> dict[str, Any]:
    """Shorthand for a mrkdwn section block."""
    return {"type": "section", "text": {"type": "mrkdwn", "text": _truncate(text)}}


def format_turn(turn: "ConversationTurn", event_id: str = "") -> list[dict]:
    """Convert a ConversationTurn to Slack Block Kit blocks.

    Returns a list of block dicts ready for chat_postMessage(blocks=...).
    """
    key = f"{turn.actor}.{turn.action}"
    blocks: list[dict] = []

    if key == "brain.triage":
        thoughts = turn.thoughts or "Analyzing event..."
        blocks.append(_section(f"_:brain: {thoughts}_"))

    elif key == "brain.route":
        agents = ", ".join(turn.selectedAgents or [])
        header = f"*:arrow_right: Routing to {agents}*"
        if turn.thoughts:
            header += f"\n{turn.thoughts}"
        blocks.append(_section(header))

    elif key == "brain.request_approval":
        plan_text = _md_to_mrkdwn(turn.plan or turn.thoughts or "Plan ready for review.")
        blocks.append(_section(f"*:clipboard: Plan ready:*\n{_truncate(plan_text)}"))
        blocks.append({
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Approve"},
                    "style": "primary",
                    "action_id": "darwin_approve",
                    "value": event_id,
                },
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Reject"},
                    "style": "danger",
                    "action_id": "darwin_reject",
                    "value": event_id,
                },
            ],
        })

    elif key == "brain.wait":
        if turn.thoughts:
            blocks.append(_section(_md_to_mrkdwn(turn.thoughts)))
        waiting = turn.waitingFor or "user input"
        blocks.append(_section(f":hourglass_flowing_sand: Waiting for {waiting}"))

    elif key == "brain.defer":
        reason = turn.thoughts or "Deferred"
        blocks.append(_section(f":double_vertical_bar: *Event paused:* {reason}"))

    elif key == "brain.think":
        thoughts = turn.thoughts or "Noting progress."
        blocks.append(_section(f":brain: _{thoughts}_"))

    elif key == "brain.close":
        blocks.append(_section(f":white_check_mark: *Event closed:* {turn.thoughts or ''}"))

    elif turn.action == "message" and turn.actor in AGENT_COLORS:
        text = turn.thoughts or ""
        blocks.append(_section(text))

    elif turn.actor in ("architect", "sysadmin", "developer", "qe") and turn.result:
        result = _md_to_mrkdwn(_truncate(turn.result))
        blocks.append(_section(f"*:gear: {turn.actor}* ({turn.action}):\n{result}"))

    elif key == "aligner.confirm":
        blocks.append(_section(f":chart_with_upwards_trend: {turn.thoughts or turn.result or 'Metrics confirmed.'}"))

    elif key in ("user.message", "user.approve", "user.reject"):
        text = turn.thoughts or turn.result or turn.action
        if turn.user_name:
            prefix = f"*{turn.user_name}:* "
        elif turn.source == "slack":
            prefix = "*(via Slack)* "
        else:
            prefix = "*(via Dashboard)* "
        blocks.append(_section(f":speech_balloon: {prefix}{text}"))

    else:
        # Fallback: render whatever we have
        text = turn.thoughts or turn.result or f"{turn.actor}.{turn.action}"
        blocks.append(_section(f"_{turn.actor}:_ {text}"))

    if turn.actor != "user":
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "_This response was AI-generated by Darwin Brain. Review for accuracy before acting._"}],
        })

    return blocks


def get_agent_notification_text(turn: "ConversationTurn") -> str:
    """Short text for attachment messages (mobile push notifications, search).

    Keep this minimal -- Slack renders top-level text ABOVE attachments,
    so anything here appears as a separate visible line before the color bar.
    """
    emoji = AGENT_EMOJI.get(turn.actor, "\U0001f916")
    return f"{emoji} {turn.actor}"


def get_turn_attachment_color(turn: "ConversationTurn") -> str | None:
    """Return a color hex for turns that should use the Slack attachment color bar.

    Agent progress messages get a per-agent color strip for visual distinction.
    Returns None for turns that use standard block formatting.
    """
    if turn.action == "message" and turn.actor in AGENT_COLORS:
        return AGENT_COLORS[turn.actor]
    return None


def build_event_report_md(event_doc: "EventDocument") -> str:
    """Build a Markdown report of the event conversation for Slack file attachment."""
    lines = [
        f"# Event: {event_doc.id}",
        f"- **Source:** {event_doc.source}",
        f"- **Service:** {event_doc.service}",
        f"- **Status:** {event_doc.status}",
        f"- **Reason:** {event_doc.event.reason}",
        "",
        "## Conversation",
    ]
    for t in event_doc.conversation:
        name = t.user_name or t.actor
        text = (t.thoughts or t.result or t.action or "")[:300]
        lines.append(f"### Turn {t.turn} - {name} ({t.action})")
        lines.append(text)
        lines.append("")
    return "\n".join(lines)


def format_event_summary(event_doc: "EventDocument") -> list[dict]:
    """Format the initial thread-parent message for an event."""
    reason = event_doc.event.reason
    evidence = ""
    if hasattr(event_doc.event.evidence, "display_text"):
        evidence = event_doc.event.evidence.display_text
    elif isinstance(event_doc.event.evidence, str):
        evidence = event_doc.event.evidence

    blocks = [
        _section(
            f"*Event `{event_doc.id}` created*\n"
            f">*Service:* {event_doc.service}\n"
            f">*Reason:* {reason}\n"
            + (f">*Evidence:* {_truncate(evidence, 500)}" if evidence else "")
        ),
    ]
    return blocks
