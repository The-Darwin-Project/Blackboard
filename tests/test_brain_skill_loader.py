# BlackBoard/tests/test_brain_skill_loader.py
# @ai-rules:
# 1. [Constraint]: Tests use temp directories only -- no dependency on actual brain_skills/ content.
# 2. [Pattern]: Each test creates its own fixture via _make_skills helper.
"""Unit tests for BrainSkillLoader: discovery, frontmatter, dependencies, tags, reload."""
from __future__ import annotations

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


class TestDependencyResolutionWithPaths:
    def test_transitive_returns_paths_and_bodies(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "a": {"skill-a.md": "---\nrequires:\n  - b/skill-b.md\n---\n# A"},
            "b": {"skill-b.md": "---\nrequires:\n  - c/skill-c.md\n---\n# B"},
            "c": {"skill-c.md": "# C"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        result = loader.resolve_dependencies_with_paths(["a/skill-a.md"])
        assert len(result) == 3
        assert all(isinstance(item, tuple) and len(item) == 2 for item in result)
        assert result[0][0] == "a/skill-a.md"
        assert "# A" in result[0][1]
        assert result[1][0] == "b/skill-b.md"
        assert "# B" in result[1][1]
        assert result[2][0] == "c/skill-c.md"
        assert "# C" in result[2][1]

    def test_cycle_safety_with_paths(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "a": {"skill-a.md": "---\nrequires:\n  - b/skill-b.md\n---\n# A"},
            "b": {"skill-b.md": "---\nrequires:\n  - a/skill-a.md\n---\n# B"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        result = loader.resolve_dependencies_with_paths(["a/skill-a.md"])
        assert len(result) == 2
        assert all(isinstance(item, tuple) for item in result)

    def test_dynamic_template_vars_with_paths(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "post": {"close.md": "---\nrequires:\n  - source/{event.source}.md\n---\n# Close"},
            "source": {"slack.md": "# Slack rules"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        result = loader.resolve_dependencies_with_paths(
            ["post/close.md"], template_vars={"event.source": "slack"},
        )
        assert len(result) == 2
        assert result[1][0] == "source/slack.md"
        assert "# Slack rules" in result[1][1]

    def test_equivalence_with_resolve_dependencies(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "a": {"skill-a.md": "---\nrequires:\n  - b/skill-b.md\n---\n# A"},
            "b": {"skill-b.md": "---\nrequires:\n  - c/skill-c.md\n---\n# B"},
            "c": {"skill-c.md": "# C"},
            "post": {"close.md": "---\nrequires:\n  - source/{event.source}.md\n---\n# Close"},
            "source": {"slack.md": "# Slack rules"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        tv = {"event.source": "slack"}
        paths = ["a/skill-a.md", "post/close.md"]
        with_paths = loader.resolve_dependencies_with_paths(paths, template_vars=tv)
        without_paths = loader.resolve_dependencies(paths, template_vars=tv)
        assert [body for _, body in with_paths] == without_paths

    def test_empty_input_returns_empty(self, tmp_path: Path):
        _make_skills(tmp_path, {"a": {"s1.md": "# A"}})
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.resolve_dependencies([]) == []
        assert loader.resolve_dependencies_with_paths([]) == []


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


class TestGetTagType:
    def test_folder_defaults(self, tmp_path: Path):
        _make_skills(tmp_path, {
            "always": {"rule.md": "# Rule"},
            "source": {"slack.md": "# Slack"},
            "context": {"env.md": "# Env"},
            "dispatch": {"exec.md": "# Exec"},
            "triage": {"assess.md": "# Assess"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.get_tag_type("always/rule.md") == "rule"
        assert loader.get_tag_type("source/slack.md") == "rule"
        assert loader.get_tag_type("context/env.md") == "context"
        assert loader.get_tag_type("dispatch/exec.md") == "skill"
        assert loader.get_tag_type("triage/assess.md") == "skill"

    def test_frontmatter_override(self, tmp_path: Path):
        content = "---\ntag_type: protocol\n---\n# Protocol"
        _make_skills(tmp_path, {"always": {"lifecycle.md": content}})
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.get_tag_type("always/lifecycle.md") == "protocol"

    def test_invalid_frontmatter_ignored(self, tmp_path: Path):
        content = "---\ntag_type: bogus\n---\n# Invalid"
        _make_skills(tmp_path, {"always": {"invalid.md": content}})
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.get_tag_type("always/invalid.md") == "rule"

    def test_unknown_folder_defaults_to_skill(self, tmp_path: Path):
        _make_skills(tmp_path, {"custom": {"file.md": "# Custom"}})
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.get_tag_type("custom/file.md") == "skill"

    def test_unknown_path_defaults_to_skill(self, tmp_path: Path):
        _make_skills(tmp_path, {"a": {"s1.md": "# A"}})
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.get_tag_type("nonexistent/missing.md") == "skill"

    def test_valid_tag_types_allowlist(self):
        from src.agents.brain_skill_loader import _VALID_TAG_TYPES
        expected = {"rule", "skill", "protocol", "context"}
        assert _VALID_TAG_TYPES == expected
