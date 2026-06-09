# BlackBoard/tests/test_event_source_consistency.py
# @ai-rules:
# 1. [Constraint]: This test anchors cross-language EventSource consistency.
# 2. [Pattern]: Uses typing.get_args() for Python, regex for TS named export,
#    comment anchor for SI taxonomy. All three must agree.
# 3. [Gotcha]: nightwatcher is a WS dispatcher label, NOT an EventSource member.
"""
CI guard: ensures EventSource stays consistent across Python types, TypeScript
types, and the JARVIS SYSTEM_INSTRUCTION taxonomy prose.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest

from src.agents.jarvis_instructions import SYSTEM_INSTRUCTION
from src.event_types import EventSource

UI_TYPES_PATH = Path(__file__).parent.parent / "ui" / "src" / "api" / "types.ts"


def _parse_ts_event_source() -> set[str]:
    """Extract values from `export type EventSource = ...` in types.ts."""
    content = UI_TYPES_PATH.read_text()
    match = re.search(
        r"export\s+type\s+EventSource\s*=\s*(.+?);", content, re.DOTALL
    )
    assert match, "Could not find 'export type EventSource' in api/types.ts"
    raw = match.group(1)
    return set(re.findall(r"['\"]([^'\"]+)['\"]", raw))


def _parse_si_taxonomy() -> set[str]:
    """Extract source names from the SI taxonomy section (after comment anchor)."""
    anchor = "<!-- EventSource taxonomy -->"
    idx = SYSTEM_INSTRUCTION.find(anchor)
    assert idx != -1, "Missing '<!-- EventSource taxonomy -->' anchor in SYSTEM_INSTRUCTION"
    tail = SYSTEM_INSTRUCTION[idx:]
    section_end = tail.find("\n\n", len(anchor))
    section = tail[:section_end] if section_end != -1 else tail
    expected = set(get_args(EventSource))
    pattern = re.compile(r"\b(" + "|".join(re.escape(s) for s in expected) + r")\b")
    return set(pattern.findall(section))


class TestEventSourceConsistency:
    """Anchor test: Python Literal, TS type, and SI taxonomy must agree."""

    def test_python_event_source_values(self):
        values = set(get_args(EventSource))
        assert "aligner" in values
        assert "nightwatcher" not in values, "nightwatcher is a dispatcher label, not EventSource"

    def test_ts_matches_python(self):
        py_values = set(get_args(EventSource))
        ts_values = _parse_ts_event_source()
        assert ts_values == py_values, (
            f"TS/Python mismatch.\n  TS-only: {ts_values - py_values}\n  Python-only: {py_values - ts_values}"
        )

    def test_si_taxonomy_matches_python(self):
        py_values = set(get_args(EventSource))
        si_values = _parse_si_taxonomy()
        assert si_values == py_values, (
            f"SI taxonomy/Python mismatch.\n  SI-only: {si_values - py_values}\n  Python-only: {py_values - si_values}"
        )

    def test_nightwatcher_explicitly_excluded(self):
        """nightwatcher is a WS progress dispatcher label, not an EventDocument.source."""
        py_values = set(get_args(EventSource))
        assert "nightwatcher" not in py_values

    def test_jarvis_tag_pairs_structural(self):
        """Every opening <jarvis_*> tag must have a matching closing tag."""
        opening_pattern = re.compile(r"<(jarvis_(?:rule|mode|protocol|context))\s+id=\"([^\"]+)\">")
        closing_pattern = re.compile(r"</(jarvis_(?:rule|mode|protocol|context))>")

        openings = opening_pattern.findall(SYSTEM_INSTRUCTION)
        closings = closing_pattern.findall(SYSTEM_INSTRUCTION)

        assert len(openings) == len(closings), (
            f"Tag count mismatch: {len(openings)} opening vs {len(closings)} closing"
        )

        opening_types = [tag_type for tag_type, _ in openings]
        closing_types = list(closings)

        for i, (o_type, o_id) in enumerate(openings):
            assert o_type == closing_types[i], (
                f"Tag pair mismatch at position {i}: "
                f"opening <{o_type} id=\"{o_id}\"> but closing </{closing_types[i]}>"
            )
