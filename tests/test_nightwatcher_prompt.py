# tests/test_nightwatcher_prompt.py
# @ai-rules:
# 1. [Pattern]: Tests prompt generation functions in isolation -- no LLM calls.
# 2. [Constraint]: Validate manifest table structure and system prompt content.
# 3. [Pattern]: Tag structural test validates XML open/close pairs via regex.
# 4. [Pattern]: Summary is NOT truncated in manifest table -- Pydantic model enforces 200 char max.
"""Unit tests for Nightwatcher prompt builder."""
from __future__ import annotations

import re

from src.models import StagedEscalation
from src.observers.nightwatcher_prompt import (
    build_manifest_table, build_system_prompt, build_report_iteration_prompt,
    build_summary_prompt, extract_event_links, extract_full_links,
)


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

    def test_summary_not_truncated(self):
        long_summary = "x" * 200
        table = build_manifest_table([_make_escalation(summary=long_summary)])
        for line in table.split("\n")[2:]:
            if "evt-1" in line:
                summary_in_table = line.split("|")[-2].strip()
                assert len(summary_in_table) == 200

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

    def test_report_phase_describes_clustering(self):
        prompt = build_system_prompt([_make_escalation()], "s", "e")
        assert "grouping events by shared root cause" in prompt
        assert "create_issue" not in prompt


# =========================================================================
# build_manifest_table -- Staged (hrs ago) column
# =========================================================================

class TestManifestTableStagedHoursAgo:
    def test_staged_hours_ago_column_present(self):
        """Manifest table includes Staged (hrs ago) header and computed value."""
        import time as _time
        esc = StagedEscalation(
            event_id="evt-test", service="svc-1", source="aligner",
            reason="test", summary="test summary",
            staged_at=_time.time() - 7200,
        )
        table = build_manifest_table([esc])
        assert "Staged (hrs ago)" in table
        assert "2.0h" in table


# =========================================================================
# build_report_iteration_prompt
# =========================================================================

class TestBuildReportIterationPrompt:
    def test_carries_cluster_context_and_receipts(self):
        cluster = {"events": ["evt-1"], "platform": "Konflux", "root_cause": "CDN 404", "services": ["svc-a"]}
        completed = [{"index": 1, "summary": "Auth fail", "priority": "Critical", "platform": "Kargo", "affected_events": ["evt-2"]}]
        prompt = build_report_iteration_prompt(cluster, 2, 3, completed)
        assert "Report 2 of 3" in prompt
        assert "CDN 404" in prompt
        assert "evt-1" in prompt
        assert "Auth fail" in prompt


# =========================================================================
# build_summary_prompt
# =========================================================================

class TestBuildSummaryPrompt:
    def test_includes_metrics_and_report_list(self):
        reports = [{"index": 1, "summary": "CDN 404", "priority": "Critical", "status": "New", "platform": "Konflux", "affected_events": ["evt-1"]}]
        metrics = {"escalation_count": 5, "incident_count": 1, "noise_reduction_pct": 80.0}
        prompt = build_summary_prompt(reports, metrics)
        assert "5" in prompt
        assert "80.0%" in prompt
        assert "CDN 404" in prompt


# =========================================================================
# XML tag structural integrity
# =========================================================================

class TestNightwatcherTagStructure:
    def test_nightwatcher_tag_pairs_structural(self):
        mock_esc = StagedEscalation(
            event_id="evt-test", service="test-svc", source="headhunter",
            reason="test", summary="test summary",
        )
        prompt = build_system_prompt([mock_esc], "2026-01-01T00:00", "2026-01-01T12:00")
        opens = re.findall(r'<((?:rule|mode|protocol|context))\s+id="([^"]+)">', prompt)
        closes = re.findall(r'</((?:rule|mode|protocol|context))>', prompt)
        assert len(opens) == len(closes), f"Tag mismatch: {len(opens)} opens vs {len(closes)} closes"
        for (o_type, _), c_type in zip(opens, closes):
            assert o_type == c_type, f"Tag type mismatch: <{o_type}> closed by </{c_type}>"

    def test_required_tag_ids_present(self):
        from src.observers.nightwatcher_prompt import _REQUIRED_TAG_IDS
        mock_esc = StagedEscalation(
            event_id="evt-test", service="test-svc", source="headhunter",
            reason="test", summary="test summary",
        )
        prompt = build_system_prompt([mock_esc], "2026-01-01T00:00", "2026-01-01T12:00")
        found_ids = {m.group(1) for m in re.finditer(r'id="([^"]+)"', prompt)}
        missing = _REQUIRED_TAG_IDS - found_ids
        assert not missing, f"Missing required tag IDs: {missing}"


# =========================================================================
# extract_event_links
# =========================================================================

class TestExtractEventLinks:
    def test_headhunter_with_all_links(self):
        esc = StagedEscalation(
            event_id="evt-test", service="test", source="headhunter",
            reason="test", summary="test",
            evidence_snapshot={
                "gitlab_context": {"target_url": "https://gitlab/mr/1", "mr_iid": 42, "pipeline_id": 123, "project_path": "org/repo"},
            },
            slack_thread_url="https://slack.com/archives/C123/p456",
        )
        result = extract_event_links(esc)
        assert "MR !42" in result
        assert "Pipe #123" in result
        assert "Slack" in result

    def test_aligner_no_links(self):
        esc = StagedEscalation(
            event_id="evt-test", service="test", source="aligner",
            reason="test", summary="test",
            evidence_snapshot={"source_type": "aligner", "metrics": {"cpu": 0.9}},
        )
        assert extract_event_links(esc) == "\u2014"


# =========================================================================
# extract_full_links
# =========================================================================

class TestExtractFullLinks:
    def test_empty_gitlab_host_fallback(self, monkeypatch):
        monkeypatch.delenv("GITLAB_HOST", raising=False)
        esc = StagedEscalation(
            event_id="evt-test", service="test", source="headhunter",
            reason="test", summary="test",
            evidence_snapshot={"gitlab_context": {"pipeline_id": 99, "project_path": "org/repo"}},
        )
        result = extract_full_links(esc)
        assert "Pipeline ID: 99" in result
        assert "https://" not in result

    def test_gitlab_host_with_scheme_normalization(self, monkeypatch):
        monkeypatch.setenv("GITLAB_HOST", "https://gitlab.example.com/")
        esc = StagedEscalation(
            event_id="evt-test", service="test", source="headhunter",
            reason="test", summary="test",
            evidence_snapshot={
                "gitlab_context": {
                    "target_url": "https://gitlab.example.com/org/repo/-/merge_requests/1",
                    "pipeline_id": 55,
                    "project_path": "org/repo",
                },
            },
        )
        result = extract_full_links(esc)
        assert "https://gitlab.example.com/org/repo/-/pipelines/55" in result
        assert "https://https://" not in result

    def test_mixed_sources(self):
        esc = StagedEscalation(
            event_id="evt-test", service="test", source="headhunter",
            reason="test", summary="test",
            evidence_snapshot={
                "gitlab_context": {"target_url": "https://gitlab/mr/1"},
                "kargo_context": {"mr_url": "https://gitlab/mr/2"},
            },
            slack_thread_url="https://slack/thread",
        )
        result = extract_full_links(esc)
        assert "MR:" in result
        assert "Kargo MR:" in result
        assert "Slack:" in result


# =========================================================================
# build_report_iteration_prompt with cluster_links
# =========================================================================

class TestReportIterationPromptLinks:
    def test_with_cluster_links(self):
        cluster = {"root_cause": "test", "platform": "Konflux", "services": ["svc"], "events": ["evt-1"]}
        links = ["**evt-1**:\n- MR: https://gitlab/mr/1\n- Slack: https://slack/thread"]
        prompt = build_report_iteration_prompt(cluster, 1, 1, [], cluster_links=links)
        assert "### Related Links" in prompt
        assert "evt-1" in prompt
        assert "https://gitlab/mr/1" in prompt

    def test_without_links(self):
        cluster = {"root_cause": "test", "platform": "Konflux", "services": ["svc"], "events": ["evt-1"]}
        prompt = build_report_iteration_prompt(cluster, 1, 1, [])
        assert "### Related Links" not in prompt
