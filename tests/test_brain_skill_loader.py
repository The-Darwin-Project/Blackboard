# BlackBoard/tests/test_brain_skill_loader.py
# @ai-rules:
# 1. [Constraint]: Tests use temp directories only -- no dependency on actual brain_skills/ content.
# 2. [Pattern]: Each test creates its own fixture via _make_skills helper.
"""Unit tests for BrainSkillLoader: discovery, frontmatter, dependencies, tags, reload."""
from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from src.agents.brain_skill_loader import BrainSkillLoader


def _make_skills(base: Path, structure: dict[str, dict[str, str]]) -> None:
    """Create skill directory structure from a nested dict.

    structure: {phase_name: {filename: content, ...}, ...}
    """
    for phase, files in structure.items():
        phase_dir = base / phase
        phase_dir.mkdir(parents=True, exist_ok=True)
        for filename, content in files.items():
            (phase_dir / filename).write_text(content)


class TestPhaseDiscovery:
    def test_discovers_phases_and_files(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "always": {"00-identity.md": "# Identity", "01-rules.md": "# Rules"},
            "triage": {"cynefin.md": "# Cynefin"},
            "dispatch": {"exec.md": "# Exec"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        assert sorted(loader.available_phases()) == ["always", "dispatch", "triage"]
        assert len(loader.get_phase("always")) == 2
        assert len(loader.get_phase("triage")) == 1
        assert len(loader.get_phase("dispatch")) == 1

    def test_empty_dir_returns_no_phases(self, tmp_path: Path):
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.available_phases() == []

    def test_nonexistent_dir_returns_no_phases(self, tmp_path: Path):
        loader = BrainSkillLoader(str(tmp_path / "missing"))
        assert loader.available_phases() == []


class TestFrontmatterParsing:
    def test_parses_full_frontmatter(self, tmp_path: Path):
        content = (
            "---\n"
            "description: \"Test skill\"\n"
            "requires:\n"
            "  - other/file.md\n"
            "tags: [a, b]\n"
            "---\n"
            "# Body content\nSome text."
        )
        _make_skills(tmp_path, {"phase": {"skill.md": content}})
        loader = BrainSkillLoader(str(tmp_path))
        result = loader.get_with_meta("phase/skill.md")
        assert result is not None
        body, meta = result
        assert "# Body content" in body
        assert meta["description"] == "Test skill"
        assert meta["requires"] == ["other/file.md"]
        assert meta["tags"] == ["a", "b"]

    def test_no_frontmatter_returns_full_body(self, tmp_path: Path):
        _make_skills(tmp_path, {"phase": {"plain.md": "# Just a body\nNo frontmatter."}})
        loader = BrainSkillLoader(str(tmp_path))
        result = loader.get_with_meta("phase/plain.md")
        assert result is not None
        body, meta = result
        assert "# Just a body" in body
        assert meta == {}


class TestDependencyResolution:
    def test_transitive_resolution(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "a": {"skill-a.md": "---\nrequires:\n  - b/skill-b.md\n---\n# A"},
            "b": {"skill-b.md": "---\nrequires:\n  - c/skill-c.md\n---\n# B"},
            "c": {"skill-c.md": "# C"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        resolved = loader.resolve_dependencies(["a/skill-a.md"])
        assert len(resolved) == 3
        assert "# A" in resolved[0]
        assert "# B" in resolved[1]
        assert "# C" in resolved[2]

    def test_cycle_safety(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "a": {"skill-a.md": "---\nrequires:\n  - b/skill-b.md\n---\n# A"},
            "b": {"skill-b.md": "---\nrequires:\n  - a/skill-a.md\n---\n# B"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        resolved = loader.resolve_dependencies(["a/skill-a.md"])
        assert len(resolved) == 2
        assert "# A" in resolved[0]
        assert "# B" in resolved[1]

    def test_deduplication(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "a": {"s1.md": "---\nrequires:\n  - c/shared.md\n---\n# A1"},
            "b": {"s2.md": "---\nrequires:\n  - c/shared.md\n---\n# B1"},
            "c": {"shared.md": "# Shared"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        resolved = loader.resolve_dependencies(["a/s1.md", "b/s2.md"])
        shared_count = sum(1 for r in resolved if "# Shared" in r)
        assert shared_count == 1

    def test_dynamic_template_vars(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "post": {"close.md": "---\nrequires:\n  - source/{event.source}.md\n---\n# Close"},
            "source": {"slack.md": "# Slack rules"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        resolved = loader.resolve_dependencies(
            ["post/close.md"], template_vars={"event.source": "slack"},
        )
        assert len(resolved) == 2
        assert "# Slack rules" in resolved[1]

    def test_missing_dependency_skipped(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "a": {"skill.md": "---\nrequires:\n  - missing/nope.md\n---\n# A"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        resolved = loader.resolve_dependencies(["a/skill.md"])
        assert len(resolved) == 1
        assert "# A" in resolved[0]


class TestTagIndex:
    def test_find_by_tag(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "a": {"s1.md": "---\ntags: [infra, gitops]\n---\n# S1"},
            "b": {"s2.md": "---\ntags: [infra]\n---\n# S2"},
            "c": {"s3.md": "---\ntags: [other]\n---\n# S3"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        infra = loader.find_by_tag("infra")
        assert len(infra) == 2
        assert loader.find_by_tag("other") == ["# S3"]
        assert loader.find_by_tag("nonexistent") == []

    def test_find_paths_by_tag(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "a": {"s1.md": "---\ntags: [x]\n---\n# S1"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.find_paths_by_tag("x") == ["a/s1.md"]


class TestPhaseMetadata:
    def test_reads_phase_yaml(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "triage": {
                "_phase.yaml": "thinking_level: low\ntemperature: 0.3\npriority: 20\n",
                "skill.md": "# Skill",
            },
        })
        loader = BrainSkillLoader(str(tmp_path))
        meta = loader.get_phase_meta("triage")
        assert meta["thinking_level"] == "low"
        assert meta["temperature"] == 0.3
        assert meta["priority"] == 20

    def test_missing_phase_yaml_returns_empty(self, tmp_path: Path):
        _make_skills(tmp_path, {"bare": {"skill.md": "# Skill"}})
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.get_phase_meta("bare") == {}


class TestReload:
    def test_reload_picks_up_new_files(self, tmp_path: Path):
        _make_skills(tmp_path, {"a": {"s1.md": "# Original"}})
        loader = BrainSkillLoader(str(tmp_path))
        assert len(loader.get_phase("a")) == 1

        (tmp_path / "a" / "s2.md").write_text("# New file")
        loader.reload()
        assert len(loader.get_phase("a")) == 2

    def test_reload_picks_up_content_changes(self, tmp_path: Path):
        _make_skills(tmp_path, {"a": {"s1.md": "# V1"}})
        loader = BrainSkillLoader(str(tmp_path))
        assert "# V1" in loader.get_phase("a")[0]

        (tmp_path / "a" / "s1.md").write_text("# V2")
        loader.reload()
        assert "# V2" in loader.get_phase("a")[0]
