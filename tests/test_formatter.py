# tests/test_formatter.py
# @ai-rules:
# 1. [Constraint]: Pure function tests only -- no mocks, no I/O. Tests formatter.py Block Kit output.
# 2. [Pattern]: Each test constructs a ConversationTurn and asserts on format_turn() / get_turn_attachment_color() output.
"""Tests for Slack Block Kit formatter -- Unified Message Cards (B+)."""
from __future__ import annotations

import pytest

from src.channels.formatter import (
    AGENT_SHORTCODE,
    format_turn,
    get_turn_attachment_color,
)
from src.models import ConversationTurn


def _make_turn(**kwargs) -> ConversationTurn:
    defaults = {"turn": 1, "actor": "brain", "action": "think"}
    defaults.update(kwargs)
    return ConversationTurn(**defaults)


# ── Test 1: KV happy path ──────────────────────────────────────────────

def test_brain_think_kv_happy_path():
    """3+ Key: Value lines render as a bulleted mrkdwn list."""
    thoughts = "MR State: opened\nPipeline: running\nMerge Blocked: ci_still_running\nSeverity: info"
    turn = _make_turn(thoughts=thoughts)
    blocks = format_turn(turn)
    section_blocks = [b for b in blocks if b.get("type") == "section"]
    assert section_blocks
    text = section_blocks[0]["text"]["text"]
    assert "- *MR State:*" in text
    assert "- *Pipeline:*" in text
    assert "- *Merge Blocked:*" in text


# ── Test 2: KV false positive ──────────────────────────────────────────

def test_brain_think_kv_false_positive():
    """2 prose lines starting with 'X: ...' must NOT render as KV bullets."""
    thoughts = "Note: this is an important observation\nSummary: the pipeline looks healthy"
    turn = _make_turn(thoughts=thoughts)
    blocks = format_turn(turn)
    text_blocks = [b for b in blocks if b.get("type") in ("section", "context")]
    assert text_blocks
    block = text_blocks[0]
    if block["type"] == "context":
        text = block["elements"][0]["text"]
    else:
        text = block["text"]["text"]
    assert "- *Note:*" not in text


# ── Test 3: Short think → context block ────────────────────────────────

def test_brain_think_short_context_block():
    """brain.think under 200 chars without KV renders as context block, not section."""
    turn = _make_turn(thoughts="Checking pipeline status")
    blocks = format_turn(turn)
    non_disclaimer = [b for b in blocks if b.get("type") == "context"
                      and "AI-generated" not in str(b)]
    assert non_disclaimer, "Short think should produce a context block"
    assert non_disclaimer[0]["type"] == "context"


# ── Test 4: Disclaimer count ──────────────────────────────────────────

def test_disclaimer_count_in_typical_thread():
    """A 10-turn thread should produce only 2-3 disclaimers, not 9."""
    turns = [
        _make_turn(actor="brain", action="triage", thoughts="Analyzing..."),
        _make_turn(actor="brain", action="route", thoughts="Routing to developer: check MR",
                   selectedAgents=["developer"]),
        _make_turn(actor="developer", action="message", thoughts="Starting task"),
        _make_turn(actor="brain", action="think", thoughts="Pipeline status ok"),
        _make_turn(actor="developer", action="execute", result="MR merged successfully"),
        _make_turn(actor="brain", action="wait", thoughts="Waiting for verification",
                   waitingFor="agent"),
        _make_turn(actor="brain", action="defer", thoughts="Pipeline still running"),
        _make_turn(actor="brain", action="think", thoughts="Rechecking after defer"),
        _make_turn(actor="brain", action="close", thoughts="Event resolved"),
        _make_turn(actor="user", action="message", thoughts="Thanks!", source="slack"),
    ]
    disclaimer_count = 0
    for t in turns:
        blocks = format_turn(t)
        for b in blocks:
            if b.get("type") == "context" and "AI-generated" in str(b):
                disclaimer_count += 1
    assert disclaimer_count == 2, f"Expected exactly 2 disclaimers (execute + close), got {disclaimer_count}"


# ── Test 5: Defer/wait shape ──────────────────────────────────────────

@pytest.mark.parametrize("action,emoji_fragment", [
    ("defer", ":double_vertical_bar:"),
    ("wait", ":hourglass_flowing_sand:"),
])
def test_defer_wait_single_section(action, emoji_fragment):
    """brain.defer and brain.wait each produce exactly 1 section block with bold verb."""
    kwargs = {"actor": "brain", "action": action, "thoughts": "Pipeline running"}
    if action == "wait":
        kwargs["waitingFor"] = "agent"
    turn = _make_turn(**kwargs)
    blocks = format_turn(turn)
    sections = [b for b in blocks if b.get("type") == "section"]
    assert len(sections) == 1, f"Expected 1 section, got {len(sections)}"
    text = sections[0]["text"]["text"]
    assert emoji_fragment in text
    assert "*" in text


# ── Test 6: Agent message header ──────────────────────────────────────

def test_agent_message_has_emoji_header():
    """developer.message section text contains agent shortcode emoji + bold name."""
    turn = _make_turn(actor="developer", action="message", thoughts="Starting task")
    blocks = format_turn(turn)
    sections = [b for b in blocks if b.get("type") == "section"]
    assert sections
    text = sections[0]["text"]["text"]
    assert AGENT_SHORTCODE["developer"] in text
    assert "*developer*" in text


# ── Test 7: Execute color bar ─────────────────────────────────────────

def test_execute_color_bar():
    """get_turn_attachment_color for developer.execute returns the developer color."""
    turn = _make_turn(actor="developer", action="execute", result="Done")
    color = get_turn_attachment_color(turn)
    assert color == "#10b981"


# ── Test 8: Fallback card ─────────────────────────────────────────────

def test_fallback_card_has_bold_header():
    """Unrecognized actor.action produces emoji + bold header, not italic raw dump."""
    turn = _make_turn(actor="timekeeper", action="tick", thoughts="Heartbeat")
    blocks = format_turn(turn)
    sections = [b for b in blocks if b.get("type") == "section"]
    assert sections
    text = sections[0]["text"]["text"]
    assert "*timekeeper*" in text
    assert "(tick)" in text
    assert text.startswith("_") is False


# ── Test 9: Non-consecutive KV lines must NOT trigger bullet rendering ─

def test_brain_think_kv_non_consecutive():
    """KV lines separated by prose must not render as KV bullets."""
    thoughts = (
        "MR State: opened\n"
        "Some prose explanation here\n"
        "Pipeline: running\n"
        "More text between the lines\n"
        "Severity: info"
    )
    turn = _make_turn(thoughts=thoughts)
    blocks = format_turn(turn)
    text_blocks = [b for b in blocks if b.get("type") in ("section", "context")]
    assert text_blocks
    block = text_blocks[0]
    if block["type"] == "context":
        text = block["elements"][0]["text"]
    else:
        text = block["text"]["text"]
    assert "- *MR State:*" not in text


# ── Test 10: Cancel has no disclaimer and no color bar ─────────────────

def test_cancel_no_disclaimer_no_color():
    """agent.cancel should not get a disclaimer or a color bar."""
    turn = _make_turn(actor="developer", action="cancel")
    blocks = format_turn(turn)
    disclaimer_blocks = [b for b in blocks if b.get("type") == "context"
                         and "AI-generated" in str(b)]
    assert len(disclaimer_blocks) == 0, "Cancel should not have a disclaimer"
    color = get_turn_attachment_color(turn)
    assert color is None, "Cancel should not have a color bar"


# ── Test 11: Isolated KV before a qualifying streak stays plain text ───

def test_brain_think_kv_isolated_before_streak():
    """Isolated KV line before a 3+ consecutive streak must NOT be bulleted."""
    thoughts = (
        "Summary: overview of the situation\n"
        "Some prose here\n"
        "MR State: opened\n"
        "Pipeline: running\n"
        "Merge Blocked: ci_still_running"
    )
    turn = _make_turn(thoughts=thoughts)
    blocks = format_turn(turn)
    section_blocks = [b for b in blocks if b.get("type") == "section"]
    assert section_blocks
    text = section_blocks[0]["text"]["text"]
    assert "- *MR State:*" in text, "Streak KV lines should be bulleted"
    assert "- *Summary:*" not in text, "Isolated KV line before streak should NOT be bulleted"
    assert "Summary: overview" in text, "Isolated line should remain as plain text"
