# tests/test_formatter.py
# @ai-rules:
# 1. [Constraint]: Pure function tests only -- no mocks, no I/O. Tests formatter.py Block Kit output.
# 2. [Pattern]: Each test constructs a ConversationTurn and asserts on format_turn() / get_turn_attachment_color() output.
"""Tests for Slack Block Kit formatter -- Unified Message Cards (B+)."""
from __future__ import annotations

import pytest

from src.channels.formatter import (
    AGENT_SHORTCODE,
    build_event_report_md,
    format_turn,
    get_turn_attachment_color,
)
from src.models import ConversationTurn, EventDocument, EventInput


def _make_turn(**kwargs) -> ConversationTurn:
    defaults = {"turn": 1, "actor": "brain", "action": "think"}
    defaults.update(kwargs)
    return ConversationTurn(**defaults)


# ── Test 1: KV happy path ──────────────────────────────────────────────

def test_brain_think_kv_happy_path():
    """brain.think with KV lines renders as compact context block (no KV formatting in Slack)."""
    thoughts = "MR State: opened\nPipeline: running\nMerge Blocked: ci_still_running\nSeverity: info"
    turn = _make_turn(thoughts=thoughts)
    blocks = format_turn(turn)
    ctx = [b for b in blocks if b.get("type") == "context" and "AI-generated" not in str(b)]
    assert ctx, "brain.think should produce a context block"
    text = ctx[0]["elements"][0]["text"]
    assert ":female-technologist:" in text
    assert "MR State" in text


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
    """brain.think with mixed KV/prose renders as compact context block (no KV formatting in Slack)."""
    thoughts = (
        "Summary: overview of the situation\n"
        "Some prose here\n"
        "MR State: opened\n"
        "Pipeline: running\n"
        "Merge Blocked: ci_still_running"
    )
    turn = _make_turn(thoughts=thoughts)
    blocks = format_turn(turn)
    ctx = [b for b in blocks if b.get("type") == "context" and "AI-generated" not in str(b)]
    assert ctx, "brain.think should produce a context block"
    text = ctx[0]["elements"][0]["text"]
    assert ":female-technologist:" in text
    assert "Summary: overview" in text, "Raw content should be preserved"


# ── Test 12: brain.notify renders as context block with bell ──────────

def test_brain_notify_context_block():
    """brain.notify renders as context block with bell emoji, no disclaimer."""
    turn = _make_turn(action="notify", thoughts="Slack DM sent to user@co.com.")
    blocks = format_turn(turn)
    ctx = [b for b in blocks if b.get("type") == "context"]
    assert ctx
    assert ":bell:" in ctx[0]["elements"][0]["text"]
    disclaimer = [b for b in blocks if "AI-generated" in str(b)]
    assert not disclaimer


# ── Test 13: brain.thoughts renders as context block ────────────────

def test_brain_thoughts_context_block():
    """brain.thoughts renders as context block (internal reasoning, grey)."""
    turn = _make_turn(action="thoughts", thoughts="Reasoning about options")
    blocks = format_turn(turn)
    ctx = [b for b in blocks if b.get("type") == "context"
           and "AI-generated" not in str(b)]
    assert ctx, "brain.thoughts should produce a context block"
    text = ctx[0]["elements"][0]["text"]
    assert ":female-technologist:" in text
    assert "Reasoning about options" in text


# ── Test 14: brain.response renders as section block ────────────────

def test_brain_response_section_block():
    """brain.response renders as section block (visible reply to user)."""
    turn = _make_turn(action="response", thoughts="Here is your answer")
    blocks = format_turn(turn)
    sections = [b for b in blocks if b.get("type") == "section"]
    assert sections, "brain.response should produce a section block"
    text = sections[0]["text"]["text"]
    assert ":female-technologist:" in text
    assert "Here is your answer" in text


# ── build_event_report_md: actor-aware labels ────────────────────────

def _make_event_doc(*turns: ConversationTurn) -> EventDocument:
    return EventDocument(
        source="chat",
        service="test-service",
        event=EventInput(reason="test", evidence="test evidence"),
        conversation=list(turns),
    )


def test_report_md_user_turn_message_label():
    """User turn in build_event_report_md renders **Message:** label."""
    turn = _make_turn(actor="user", action="message", thoughts="Hello from user")
    md = build_event_report_md(_make_event_doc(turn))
    assert "**Message:** Hello from user" in md
    assert "**Thoughts:**" not in md


def test_report_md_tool_result_evidence_label():
    """tool_result turn in build_event_report_md renders **Evidence:** from evidence field."""
    turn = _make_turn(actor="brain", action="tool_result", result=None, evidence="service healthy")
    md = build_event_report_md(_make_event_doc(turn))
    assert "**Evidence:** service healthy" in md


def test_report_md_brain_think_internal_label():
    """Legacy brain.think renders **Internal:** label in report."""
    turn = _make_turn(actor="brain", action="think", thoughts="Analyzing")
    md = build_event_report_md(_make_event_doc(turn))
    assert "**Internal:** Analyzing" in md
    assert "**Message:**" not in md


def test_report_md_brain_thoughts_internal_label():
    """brain.thoughts renders **Internal:** label in report."""
    turn = _make_turn(actor="brain", action="thoughts", thoughts="Reasoning")
    md = build_event_report_md(_make_event_doc(turn))
    assert "**Internal:** Reasoning" in md


def test_report_md_brain_response_friday_label():
    """brain.response renders **FRIDAY:** label in report."""
    turn = _make_turn(actor="brain", action="response", thoughts="Here is the answer")
    md = build_event_report_md(_make_event_doc(turn))
    assert "**FRIDAY:** Here is the answer" in md


# ── Block Kit Table Formatting & Fallback Code Block ───────────────────

class TestSlackTableFormatting:
    """Tests for Block Kit table normalization, rectangular padding, and ASCII code block fallback."""

    def test_ragged_row_padding(self):
        """A table where rows have varying number of cells gets padded with '-' so all rows have col_count cells."""
        from src.channels.formatter import extract_tables

        md = (
            "| Col1 | Col2 | Col3 | Col4 |\n"
            "|---|---|---|---|\n"
            "| A | B |\n"
            "| C | D | E | F |\n"
        )
        cleaned, tables = extract_tables(md)
        assert len(tables) == 1
        table = tables[0]
        assert table.get("type") == "table"
        rows = table.get("rows", [])
        assert len(rows) == 3  # header + 2 data rows
        for row in rows:
            assert len(row) == 4
        # Check row 1 (A, B) was padded with "-"
        row1_texts = [cell["text"] for cell in rows[1]]
        assert row1_texts == ["A", "B", "-", "-"]

    def test_empty_cell_sanitization(self):
        """Empty string '', whitespace '  ', or None in cells are normalized to '-'."""
        from src.channels.formatter import extract_tables

        md = (
            "| H1 | H2 | H3 |\n"
            "|---|---|---|\n"
            "| A | | C |\n"
            "|   | E | |\n"
        )
        cleaned, tables = extract_tables(md)
        assert len(tables) == 1
        rows = tables[0].get("rows", [])
        assert len(rows) == 3
        # Check row 1
        row1_texts = [cell["text"] for cell in rows[1]]
        assert row1_texts == ["A", "-", "C"]
        # Check row 2
        row2_texts = [cell["text"] for cell in rows[2]]
        assert row2_texts == ["-", "E", "-"]
        for row in rows:
            for cell in row:
                assert cell["text"] != ""
                assert cell["text"].strip() != ""

    def test_column_cap_at_10_columns(self):
        """A table with 15 columns is capped at 10 columns (_MAX_TABLE_COLS)."""
        from src.channels.formatter import _MAX_TABLE_COLS, extract_tables

        assert _MAX_TABLE_COLS == 10
        headers = " | ".join(f"Col{i}" for i in range(1, 16))
        seps = " | ".join("---" for _ in range(15))
        values = " | ".join(f"Val{i}" for i in range(1, 16))
        md = f"| {headers} |\n| {seps} |\n| {values} |\n"
        cleaned, tables = extract_tables(md)
        assert len(tables) == 1
        rows = tables[0].get("rows", [])
        for row in rows:
            assert len(row) == 10
        row0_texts = [c["text"] for c in rows[0]]
        assert row0_texts == [f"Col{i}" for i in range(1, 11)]

    def test_secondary_table_preservation(self):
        """extract_tables(text, max_tables=1) extracts only 1 table block and leaves remaining tables in markdown text."""
        from src.channels.formatter import extract_tables

        table1 = (
            "| H1 | H2 |\n"
            "|---|---|\n"
            "| A | B |\n"
        )
        table2 = (
            "| H3 | H4 |\n"
            "|---|---|\n"
            "| C | D |\n"
        )
        text = f"First table:\n{table1}\nSecond table:\n{table2}\nDone."
        cleaned, tables = extract_tables(text, max_tables=1)
        assert len(tables) == 1
        # First table was extracted
        assert "| H1 | H2 |" not in cleaned
        # Second table is preserved in cleaned text
        assert "| H3 | H4 |" in cleaned
        assert "| C | D |" in cleaned

    def test_table_block_to_code_block_ascii_format(self):
        """Converts a table block dict into an ASCII aligned table in ``` code block."""
        from src.channels.formatter import table_block_to_code_block

        table_block = {
            "type": "table",
            "rows": [
                [{"type": "raw_text", "text": "Service"}, {"type": "raw_text", "text": "Status"}],
                [{"type": "raw_text", "text": "auth"}, {"type": "raw_text", "text": "healthy"}],
                [{"type": "raw_text", "text": "payment"}, {"type": "raw_text", "text": "degraded"}],
            ],
        }
        code_block = table_block_to_code_block(table_block)
        assert code_block.startswith("```")
        assert code_block.endswith("```")
        assert "Service" in code_block
        assert "Status" in code_block
        assert "auth" in code_block
        assert "healthy" in code_block
        assert "payment" in code_block
        assert "degraded" in code_block

    def test_table_block_to_code_block_row_truncation(self):
        """If rows exceed 25, truncates and appends '... [N more rows truncated]'."""
        from src.channels.formatter import table_block_to_code_block

        rows = [[{"type": "raw_text", "text": f"Row{i}"}] for i in range(30)]
        table_block = {
            "type": "table",
            "rows": rows,
        }
        code_block = table_block_to_code_block(table_block)
        assert code_block.startswith("```")
        assert code_block.endswith("```")
        assert "... [5 more rows truncated]" in code_block

    def test_formatter_exports_and_cell_sanitization(self):
        """Verifies public exports and safe cell sanitization (None text, raw types)."""
        from src.channels.formatter import (
            truncate_text, MAX_SECTION_TEXT, table_block_to_code_block, _md_table_to_block_kit
        )

        assert MAX_SECTION_TEXT == 2900
        assert truncate_text("short") == "short"

        # Safe handling of None in dict text and non-dict cells
        table_block = {
            "type": "table",
            "rows": [
                [{"type": "raw_text", "text": None}, "plain_cell"],
                [None, 123],
            ],
        }
        cb = table_block_to_code_block(table_block)
        assert "plain_cell" in cb
        assert "123" in cb
        assert "None" not in cb  # Empty/None text converted to empty or space, never literal "None"

        # Col count clamp
        block = _md_table_to_block_kit([["h1"], ["c1"]])
        assert block is not None
        assert len(block["rows"][0]) == 1
