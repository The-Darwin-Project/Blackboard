# tests/test_nightwatcher_prompt.py
# @ai-rules:
# 1. [Pattern]: Tests prompt generation functions in isolation -- no LLM calls.
# 2. [Constraint]: Validate manifest table structure and system prompt content.
"""Unit tests for Nightwatcher prompt builder."""
from __future__ import annotations

from src.models import StagedEscalation
from src.observers.nightwatcher_prompt import build_manifest_table, build_system_prompt


def _make_escalation(event_id="evt-1", service="svc-a", **kw):
    defaults = dict(
        source="aligner", reason="cpu", summary="High CPU",
        platform="Konflux", priority="Normal", staged_at=1000.0,
    )
    defaults.update(kw)
    return StagedEscalation(event_id=event_id, service=service, **defaults)


# =========================================================================
# build_manifest_table
# =========================================================================

class TestBuildManifestTable:
    def test_single_escalation(self):
        table = build_manifest_table([_make_escalation()])
        assert "| 1 |" in table
        assert "evt-1" in table
        assert "svc-a" in table
        assert "Konflux" in table

    def test_multiple_escalations(self):
        escs = [
            _make_escalation("evt-1", "svc-a"),
            _make_escalation("evt-2", "svc-b", platform="Kargo"),
            _make_escalation("evt-3", "svc-c", priority="Critical"),
        ]
        table = build_manifest_table(escs)
        assert "| 1 |" in table
        assert "| 2 |" in table
        assert "| 3 |" in table
        assert "svc-b" in table
        assert "Kargo" in table
        assert "Critical" in table

    def test_has_header_row(self):
        table = build_manifest_table([_make_escalation()])
        lines = table.split("\n")
        assert "Event ID" in lines[0]
        assert "Service" in lines[0]
        assert "Platform" in lines[0]
        assert "---" in lines[1]

    def test_summary_truncated(self):
        long_summary = "x" * 200
        table = build_manifest_table([_make_escalation(summary=long_summary)])
        for line in table.split("\n")[2:]:
            if "evt-1" in line:
                summary_in_table = line.split("|")[-2].strip()
                assert len(summary_in_table) <= 80

    def test_empty_list(self):
        table = build_manifest_table([])
        lines = table.split("\n")
        assert len(lines) == 2

    def test_missing_platform_shows_question_mark(self):
        table = build_manifest_table([_make_escalation(platform="")])
        assert "?" in table


# =========================================================================
# build_system_prompt
# =========================================================================

class TestBuildSystemPrompt:
    def test_contains_identity(self):
        prompt = build_system_prompt(
            [_make_escalation()], "2026-04-29T06:00Z", "2026-04-29T12:00Z",
        )
        assert "Nightwatcher" in prompt

    def test_contains_phase_lifecycle(self):
        prompt = build_system_prompt(
            [_make_escalation()], "2026-04-29T06:00Z", "2026-04-29T12:00Z",
        )
        assert "REVIEW Phase" in prompt
        assert "INVESTIGATE Phase" in prompt
        assert "REPORT Phase" in prompt

    def test_contains_manifest(self):
        escs = [
            _make_escalation("evt-1", "svc-a"),
            _make_escalation("evt-2", "svc-b"),
        ]
        prompt = build_system_prompt(escs, "start", "end")
        assert "evt-1" in prompt
        assert "evt-2" in prompt
        assert "svc-a" in prompt
        assert "svc-b" in prompt

    def test_contains_window_times(self):
        prompt = build_system_prompt(
            [_make_escalation()], "2026-04-29T06:00Z", "2026-04-29T12:00Z",
        )
        assert "2026-04-29T06:00Z" in prompt
        assert "2026-04-29T12:00Z" in prompt

    def test_contains_escalation_count(self):
        escs = [_make_escalation(f"evt-{i}") for i in range(5)]
        prompt = build_system_prompt(escs, "s", "e")
        assert "5 escalations" in prompt

    def test_contains_consolidation_rules(self):
        prompt = build_system_prompt([_make_escalation()], "s", "e")
        assert "Consolidation Rules" in prompt

    def test_contains_cynefin_awareness(self):
        prompt = build_system_prompt([_make_escalation()], "s", "e")
        assert "Cynefin" in prompt
        assert "CLEAR" in prompt
        assert "COMPLICATED" in prompt
        assert "CHAOTIC" in prompt
