# BlackBoard/src/channels/formatter.py
# @ai-rules:
# 1. [Constraint]: Pure functions only -- no I/O, no Slack API calls (debug-level logging excepted). Returns Block Kit dicts or slack-sdk model objects.
# 2. [Pattern]: format_turn dispatches on actor.action key into 4 card families:
#    - System Card (brain.triage/thoughts/intermediate/think/defer/wait/close/tool_result, aligner.confirm) -- low visual weight
#    - Action Card (brain.route, brain.request_approval) -- bold, state-changing
#    - Response Card (brain.response, brain.respond_jarvis) -- full section, user-facing FRIDAY output
#    - Agent Card (agent.message/execute) -- color bar + emoji header via AGENT_SHORTCODE
#    - User Card (user.message/approve/reject) -- speech balloon
# 3. [Gotcha]: Slack Block Kit text limit is 3000 chars per section. Truncate long results.
# 4. [Pattern]: create_feedback_block uses slack-sdk model objects (ContextActionsBlock, FeedbackButtonsElement).
# 5. [Contract]: AI disclaimer only on _DISCLAIMER_ACTIONS (execute, request_approval, close). Not on operational status turns.
# 6. [Contract]: get_turn_attachment_color fires for action in ("message", "execute") on agent actors.
# 7. [Pattern]: brain.think/thoughts/intermediate render as compact _context_line (small grey text).
#    brain.response renders as full _section (user-facing). brain.thoughts is suppressed in slack.py
#    legacy handler (never posted to thread -- thinking animation persists until brain.response).
#    brain.notify renders as :bell: context block. brain.respond_jarvis as full section.
# 8. [Pattern]: agent.cancel uses :stop_button: (System Card style, not Agent Card identity). No color bar.
"""Convert ConversationTurn objects to Slack Block Kit payloads."""
from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..models import ConversationTurn, EventDocument

logger = logging.getLogger("darwin.formatter")

# Slack section text limit (Block Kit)
_MAX_TEXT = 2900

AGENT_COLORS: dict[str, str] = {
    "architect": "#3b82f6",
    "sysadmin": "#f59e0b",
    "developer": "#10b981",
    "qe": "#fb7185",
    "security_analyst": "#ef4444",
}

AGENT_EMOJI: dict[str, str] = {
    "architect": "\U0001f4d0",
    "sysadmin": "\U0001f527",
    "developer": "\U0001f4bb",
    "qe": "\U0001f9ea",
    "security_analyst": "\U0001f6e1",
}

# Slack shortcodes for Block Kit output (distinct from AGENT_EMOJI Unicode for push text)
AGENT_SHORTCODE: dict[str, str] = {
    "architect": ":triangular_ruler:",
    "sysadmin": ":wrench:",
    "developer": ":computer:",
    "qe": ":test_tube:",
    "security_analyst": ":shield:",
}

_DISCLAIMER_ACTIONS = frozenset({"execute", "request_approval", "close"})


def _context_line(text: str) -> dict[str, Any]:
    """Return a context block (small grey font) for low-weight system messages."""
    return {
        "type": "context",
        "elements": [{"type": "mrkdwn", "text": _truncate(text)}],
    }


def _parse_md_table(text: str) -> list[list[str]]:
    """Parse markdown pipe table into list of rows (list of cell strings).
    Skips separator rows (---|---). Returns empty list if not a valid table.
    """
    rows: list[list[str]] = []
    for line in text.strip().splitlines():
        if not line.strip():
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if cells and all(re.match(r"^[-:]+$", c) for c in cells):
            continue
        rows.append(cells)
    return rows


def _md_table_to_text(match: re.Match) -> str:
    """Convert a markdown pipe table to padded plain-text columns (code block)."""
    rows = _parse_md_table(match.group(0))
    if not rows:
        return match.group(0)
    col_count = max(len(r) for r in rows)
    widths = [0] * col_count
    for row in rows:
        for i, cell in enumerate(row):
            if i < col_count:
                widths[i] = max(widths[i], len(cell))
    out: list[str] = []
    for idx, row in enumerate(rows):
        padded = [row[i].ljust(widths[i]) if i < len(row) else " " * widths[i] for i in range(col_count)]
        out.append("  ".join(padded))
        if idx == 0:
            out.append("  ".join("-" * w for w in widths))
    return "```\n" + "\n".join(out) + "\n```"


_MAX_TABLE_ROWS = 100
_MAX_TABLE_COLS = 20


def _md_table_to_block_kit(table_text: str) -> dict | None:
    """Convert markdown pipe table to a Block Kit table block dict.

    Enforces Slack limits: 100 rows, 20 columns. Truncates with a footer on overflow.
    """
    rows = _parse_md_table(table_text)
    if len(rows) < 2:
        return None
    overflow = len(rows) > _MAX_TABLE_ROWS
    col_count = min(max((len(r) for r in rows), default=1), _MAX_TABLE_COLS)
    truncated = [row[:col_count] for row in rows[:_MAX_TABLE_ROWS]]
    if overflow:
        footer = [f"... ({len(rows) - _MAX_TABLE_ROWS} more rows)"] + [""] * (col_count - 1)
        truncated.append(footer)
    return {
        "type": "table",
        "rows": [[{"type": "raw_text", "text": cell} for cell in row] for row in truncated],
    }


_TABLE_RE = re.compile(r"(?:^\|.+\|$\n?)+", re.MULTILINE)


def extract_tables(text: str) -> tuple[str, list[dict]]:
    """Extract markdown tables from text, returning cleaned text + Block Kit table blocks.
    Tables are stripped from the text so they don't double-render as code blocks in _md_to_mrkdwn.
    """
    tables: list[dict] = []

    def _replace(match: re.Match) -> str:
        block = _md_table_to_block_kit(match.group(0))
        if block:
            tables.append(block)
            return ""
        return match.group(0)

    cleaned = _TABLE_RE.sub(_replace, text).strip()
    return cleaned, tables


def _md_to_mrkdwn(text: str) -> str:
    """Convert standard Markdown to Slack mrkdwn format.

    Slack uses *bold*, _italic_, ~strike~, and ```code``` but NOT **bold** or ### headings.
    Markdown tables are converted to monospaced code blocks with aligned columns.
    """
    text = re.sub(r"(?:^\|.+\|$\n?)+", _md_table_to_text, text, flags=re.MULTILINE)
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
    display_name = {"brain": "FRIDAY", "jarvis": "JARVIS"}.get(turn.actor, turn.actor)
    logger.debug("format_turn: %s", key)
    blocks: list[dict] = []

    if key == "brain.triage":
        thoughts = turn.thoughts or "Analyzing event..."
        blocks.append(_section(f"_:female-technologist: {thoughts}_"))

    elif key == "brain.route":
        agents = ", ".join(turn.selectedAgents or [])
        header = f"*:arrow_right: Routing to {agents}*"
        if turn.thoughts:
            task = turn.thoughts
            for agent in (turn.selectedAgents or []):
                task = task.removeprefix(f"Routing to {agent}: ").removeprefix(f"Routing to {agent}. ").removeprefix(f"Routing to {agent}")
            task = task.strip()
            if task:
                header += f"\n{task}"
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
        waiting = turn.waitingFor or "user input"
        reason = _md_to_mrkdwn(turn.thoughts) if turn.thoughts else ""
        separator = f" -- {reason}" if reason else ""
        blocks.append(_section(f":hourglass_flowing_sand: *Waiting for {waiting}*{separator}"))

    elif key == "brain.defer":
        reason = _md_to_mrkdwn(turn.thoughts) if turn.thoughts else "Deferred"
        blocks.append(_section(f":double_vertical_bar: *Event paused* -- {reason}"))

    elif key == "brain.thoughts":
        raw = turn.thoughts or ""
        if raw:
            blocks.append(_context_line(f":female-technologist: {raw}"))

    elif key == "brain.intermediate":
        raw = turn.thoughts or ""
        if raw:
            blocks.append(_context_line(f":female-technologist: {raw}"))

    elif key == "brain.think":
        raw = turn.thoughts or turn.evidence or ""
        if raw:
            blocks.append(_context_line(f":female-technologist: {raw}"))

    elif key == "brain.response":
        raw = _md_to_mrkdwn(turn.thoughts) if turn.thoughts else ""
        if raw:
            blocks.append(_section(f":female-technologist: {raw}"))

    elif key == "brain.tool_result":
        tool_name = turn.waitingFor or "tool"
        text = turn.evidence or turn.thoughts or ""
        if len(text) > 2500:
            text = text[:2500] + "..."
        blocks.append(_section(f":mag: *{tool_name}*\n{text}"))

    elif key == "brain.close":
        blocks.append(_section(f":white_check_mark: *Event closed:* {turn.thoughts or ''}"))

    elif key == "brain.notify":
        blocks.append(_context_line(f":bell: {turn.thoughts or 'Notification sent.'}"))

    elif key == "brain.phase":
        reason = _md_to_mrkdwn(turn.thoughts) if turn.thoughts else "Phase transition"
        blocks.append(_section(f":female-technologist: {reason}"))

    elif key == "brain.respond_jarvis":
        text = _md_to_mrkdwn(turn.thoughts) if turn.thoughts else ""
        if text:
            blocks.append(_section(f":female-technologist: {text}"))

    elif turn.action == "message" and turn.actor in AGENT_COLORS:
        emoji = AGENT_SHORTCODE.get(turn.actor, ":robot_face:")
        text = turn.thoughts or ""
        blocks.append(_section(f"{emoji} *{turn.actor}*\n{text}"))

    elif turn.action == "cancel" and turn.actor in ("architect", "sysadmin", "developer", "qe", "security_analyst"):
        blocks.append(_section(f":stop_button: *{turn.actor}* task cancelled"))

    elif turn.actor in ("architect", "sysadmin", "developer", "qe", "security_analyst") and turn.result:
        emoji = AGENT_SHORTCODE.get(turn.actor, ":gear:")
        result = _md_to_mrkdwn(_truncate(turn.result))
        blocks.append(_section(f"{emoji} *{turn.actor}* ({turn.action}):\n{result}"))

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
        emoji = AGENT_SHORTCODE.get(turn.actor, ":gear:")
        text = _md_to_mrkdwn(turn.thoughts or turn.result or f"{display_name}.{turn.action}")
        blocks.append(_section(f"{emoji} *{display_name}* ({turn.action}):\n{text}"))

    if turn.actor != "user" and turn.action in _DISCLAIMER_ACTIONS:
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
    display_name = {"brain": "FRIDAY", "jarvis": "JARVIS"}.get(turn.actor, turn.actor)
    return f"{emoji} {display_name}"


def get_turn_attachment_color(turn: "ConversationTurn") -> str | None:
    """Return a color hex for turns that should use the Slack attachment color bar.

    Agent progress messages get a per-agent color strip for visual distinction.
    Returns None for turns that use standard block formatting.
    """
    if turn.actor in AGENT_COLORS and turn.action in ("message", "execute"):
        return AGENT_COLORS[turn.actor]
    return None


def build_event_report_md(event_doc: "EventDocument") -> str:
    """Build a Markdown report of the event conversation for Slack file attachment."""
    subj_label = SUBJECT_LABEL.get(getattr(event_doc, "subject_type", "service"), "Service")
    lines = [
        f"# Event: {event_doc.id}",
        f"- **Source:** {event_doc.source}",
        f"- **{subj_label}:** {event_doc.service}",
        f"- **Status:** {event_doc.status}",
        f"- **Reason:** {event_doc.event.reason}",
        "",
        "## Conversation",
    ]
    for t in event_doc.conversation:
        name = t.user_name or {"brain": "FRIDAY", "jarvis": "JARVIS"}.get(t.actor, t.actor)
        if t.actor == "user" and t.source == "automated":
            name = "System"
        lines.append(f"### Turn {t.turn} - {name} ({t.action})")
        if t.actor == "user" and t.source == "automated":
            text = (t.thoughts or "")[:300]
            if text:
                lines.append(f"**System Nudge:** {text}")
        elif t.actor == "user":
            text = (t.thoughts or t.result or t.action or "")[:300]
            lines.append(f"**Message:** {text}")
        elif t.action in ("think", "thoughts"):
            text = (t.thoughts or "")[:300]
            if text:
                lines.append(f"**Internal:** {text}")
        elif t.action == "response":
            text = (t.thoughts or "")[:300]
            if text:
                lines.append(f"**FRIDAY:** {text}")
        elif t.action == "respond_jarvis":
            text = (t.thoughts or "")[:300]
            if text:
                lines.append(f"**Message to JARVIS:** {text}")
        elif t.action == "tool_result":
            text = (t.result or t.evidence or t.thoughts or t.action or "")[:300]
            lines.append(f"**Evidence:** {text}")
        else:
            text = (t.thoughts or t.result or t.action or "")[:300]
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

    subj_label = SUBJECT_LABEL.get(getattr(event_doc, "subject_type", "service"), "Service")
    subj_icon = SUBJECT_EMOJI.get(getattr(event_doc, "subject_type", "service"), "")
    prefix = f"{subj_icon} " if subj_icon else ""
    blocks = [
        _section(
            f"{prefix}*Event `{event_doc.id}` created*\n"
            f">*{subj_label}:* {event_doc.service}\n"
            f">*Reason:* {reason}\n"
            + (f">*Evidence:* {_truncate(evidence, 500)}" if evidence else "")
        ),
    ]
    return blocks


# =========================================================================
# Streaming / Assistant formatting helpers
# =========================================================================

_TASK_STATUS_ICON = {
    "in_progress": ":arrows_counterclockwise:",
    "complete": ":white_check_mark:",
    "error": ":warning:",
}


def format_task_card(turn: "ConversationTurn", status: str = "in_progress") -> str:
    """Return mrkdwn string for a task card (used in streaming append).

    Maps agent dispatch/completion to a compact status line.
    """
    icon = _TASK_STATUS_ICON.get(status, ":gear:")
    agents = ", ".join(turn.selectedAgents or [turn.actor])
    emoji = AGENT_EMOJI.get(agents.split(",")[0].strip(), "\U0001f916")
    reason = _truncate(turn.thoughts or "", 200)
    return f"{icon} {emoji} *{agents}* {reason}"


def format_plan_block(event_id: str, tasks: list[dict[str, str]]) -> list[dict]:
    """Return Block Kit blocks for a task plan (non-streaming fallback).

    Each task dict has 'agent', 'status', and optional 'text'.
    """
    lines = [f"*Plan for `{event_id}`*"]
    for t in tasks:
        icon = _TASK_STATUS_ICON.get(t.get("status", "in_progress"), ":gear:")
        lines.append(f"{icon} *{t['agent']}*: {t.get('text', '')}")
    return [_section("\n".join(lines))]


SOURCE_EMOJI: dict[str, str] = {
    "chat": ":speech_balloon:",
    "slack": ":slack:",
    "aligner": ":chart_with_upwards_trend:",
    "headhunter": ":gitlab:",
}

STATUS_EMOJI: dict[str, str] = {
    "new": ":new:",
    "active": ":zap:",
    "deferred": ":double_vertical_bar:",
    "closed": ":white_check_mark:",
}

SUBJECT_EMOJI: dict[str, str] = {
    "service": "",
    "kargo_stage": ":kargo:",
    "system": ":female-technologist:",
}

SUBJECT_LABEL: dict[str, str] = {
    "service": "Service",
    "kargo_stage": "Stage",
    "system": "System",
}


def build_access_denied_home_view() -> dict:
    """Build a limited Home tab view for users not authorized by the access gate.

    Pure function -- no I/O, no Slack API calls.
    Returns a complete views.publish payload with the same shape as build_home_tab_view.
    """
    return {
        "type": "home",
        "blocks": [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "Darwin - AI Operations Agent"},
            },
            {"type": "divider"},
            _section(
                ":lock: *Access Required*\n\n"
                "You don't have access to Darwin yet. "
                "Contact the app maintainer to be added to the Darwin users group."
            ),
            {"type": "divider"},
        ],
    }


def build_home_tab_view(
    active_events: list[dict],
    recent_closed: list[dict],
    agents: list[dict],
    dashboard_url: str = "",
) -> dict:
    """Build a Slack Home tab view with active events, closures, agent status, and actions.

    All arguments are plain dicts -- no model imports at call time.
    Returns a complete views.publish view payload.
    """
    blocks: list[dict] = []

    blocks.append({
        "type": "header",
        "text": {"type": "plain_text", "text": "Darwin Operations Center"},
    })
    blocks.append({"type": "divider"})

    # --- Active Events ---
    blocks.append(_section(":zap: *Active Events*"))
    if active_events:
        for evt in active_events[:10]:
            subj_type = evt.get("subject_type", "service")
            if subj_type == "service" and "@kargo-" in evt.get("service", ""):
                subj_type = "kargo_stage"
            src_icon = SUBJECT_EMOJI.get(subj_type) or SOURCE_EMOJI.get(evt.get("source", ""), ":gear:")
            status_icon = STATUS_EMOJI.get(evt.get("status", ""), ":gear:")
            reason = _truncate(evt.get("reason", ""), 120)
            evt_id = evt.get("id", "?")
            svc = evt.get("service", "general")
            label = SUBJECT_LABEL.get(subj_type, "Service")
            turns = evt.get("turns", 0)
            line = f"{status_icon} `{evt_id}` {src_icon} *{label}: {svc}* -- {reason} _({turns} turns)_"
            blocks.append(_section(line))
    else:
        blocks.append(_section("_No active events. All systems nominal._"))

    blocks.append({"type": "divider"})

    # --- Recent Closures ---
    blocks.append(_section(":white_check_mark: *Recently Closed* (last 24h)"))
    if recent_closed:
        lines = []
        for evt in recent_closed[:8]:
            evt_id = evt.get("id", "?")
            svc = evt.get("service", "general")
            summary = _truncate(evt.get("summary", ""), 100)
            lines.append(f"- `{evt_id}` *{svc}* -- {summary}")
        blocks.append(_section("\n".join(lines)))
    else:
        blocks.append(_section("_No events closed in the last 24 hours._"))

    blocks.append({"type": "divider"})

    # --- Agent Status ---
    blocks.append(_section(":robot_face: *Connected Agents*"))
    if agents:
        lines = []
        for a in agents:
            role = a.get("role", "unknown")
            emoji = AGENT_EMOJI.get(role, ":gear:")
            busy = ":red_circle:" if a.get("busy") else ":large_green_circle:"
            evt_id = a.get("current_event_id", "")
            status = f"working on `{evt_id}`" if evt_id else "idle"
            lines.append(f"{busy} {emoji} *{role}* -- {status}")
        blocks.append(_section("\n".join(lines)))
    else:
        blocks.append(_section("_No agents connected._"))

    blocks.append({"type": "divider"})

    # --- Quick Actions ---
    action_elements: list[dict] = [
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Create Event"},
            "style": "primary",
            "action_id": "darwin_home_create_event",
        },
    ]
    if dashboard_url:
        action_elements.append({
            "type": "button",
            "text": {"type": "plain_text", "text": "Open Dashboard"},
            "url": dashboard_url,
            "action_id": "darwin_home_open_dashboard",
        })
    blocks.append({"type": "actions", "elements": action_elements})

    return {"type": "home", "blocks": blocks}


def create_feedback_block() -> list:
    """Return ContextActionsBlock with feedback thumbs up/down buttons."""
    from slack_sdk.models.blocks import (
        ContextActionsBlock, FeedbackButtonsElement, FeedbackButtonObject,
    )
    return [ContextActionsBlock(elements=[
        FeedbackButtonsElement(
            action_id="darwin_feedback",
            positive_button=FeedbackButtonObject(
                text="Helpful", value="positive",
                accessibility_label="Submit positive feedback",
            ),
            negative_button=FeedbackButtonObject(
                text="Not helpful", value="negative",
                accessibility_label="Submit negative feedback",
            ),
        ),
    ])]
