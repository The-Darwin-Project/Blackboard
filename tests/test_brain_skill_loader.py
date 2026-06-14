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
        expected = {"rule", "skill", "protocol", "context", "navigation"}
        assert _VALID_TAG_TYPES == expected

    def test_unhashable_frontmatter_ignored(self, tmp_path: Path):
        """Non-string tag_type (list/dict) falls back to folder default, no crash."""
        content = "---\ntag_type: [protocol]\n---\n# List value"
        _make_skills(tmp_path, {"always": {"bad.md": content}})
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.get_tag_type("always/bad.md") == "rule"


class TestIntegrationTagWrapping:
    """Integration test: real BrainSkillLoader + _wrap_section produce correct tags."""

    @pytest.mark.asyncio
    async def test_real_loader_produces_correct_semantic_tags(self, tmp_path: Path):
        from src.agents.brain import _wrap_section

        _make_skills(tmp_path, {
            "always": {"identity.md": "# Identity rules"},
            "context": {"env.md": "# Environment"},
            "dispatch": {"exec.md": "---\ntag_type: protocol\n---\n# Execution protocol"},
            "triage": {"assess.md": "# Assessment"},
        })
        loader = BrainSkillLoader(str(tmp_path))

        initial_paths: list[str] = []
        for phase in loader.available_phases():
            initial_paths.extend(loader.get_all_paths_for_phase(phase))

        resolved_pairs = loader.resolve_dependencies_with_paths(initial_paths)
        results = [
            _wrap_section(path, body, loader.get_tag_type(path))
            for path, body in resolved_pairs
        ]

        joined = "\n".join(results)
        assert '<rule id="always/identity.md">' in joined
        assert '</rule>' in joined
        assert '<context id="context/env.md">' in joined
        assert '</context>' in joined
        assert '<protocol id="dispatch/exec.md">' in joined
        assert '</protocol>' in joined
        assert '<skill id="triage/assess.md">' in joined
        assert '</skill>' in joined


class TestDomainSkillLoading:
    """T1+T2: Domain skills must resolve via _path_index and produce navigation tags."""

    def test_domain_phase_returns_empty_from_get_all_paths(self, tmp_path: Path):
        """get_all_paths_for_phase('domain/clear') returns [] because cache keys by folder."""
        _make_skills(tmp_path, {
            "domain": {"clear.md": "# CLEAR loop"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.get_all_paths_for_phase("domain/clear") == []
        assert loader.get_all_paths_for_phase("domain") == ["domain/clear.md"]

    def test_domain_file_accessible_via_path_index(self, tmp_path: Path):
        """Domain files are reachable via get_with_meta (the H1 fix path)."""
        _make_skills(tmp_path, {
            "domain": {"clear.md": "# CLEAR control loop"},
        })
        loader = BrainSkillLoader(str(tmp_path))
        result = loader.get_with_meta("domain/clear.md")
        assert result is not None
        body, _ = result
        assert "CLEAR control loop" in body

    def test_domain_files_get_navigation_tag_type(self, tmp_path: Path):
        """domain/ folder default resolves to 'navigation' tag type."""
        _make_skills(tmp_path, {
            "domain": {
                "clear.md": "# CLEAR",
                "complicated.md": "# COMPLICATED",
            },
        })
        loader = BrainSkillLoader(str(tmp_path))
        assert loader.get_tag_type("domain/clear.md") == "navigation"
        assert loader.get_tag_type("domain/complicated.md") == "navigation"

    @pytest.mark.asyncio
    async def test_domain_skill_in_system_prompt(self, tmp_path: Path):
        """H1 integration: domain/clear in active_phases produces <navigation> tag in prompt."""
        from src.agents.brain import _wrap_section

        _make_skills(tmp_path, {
            "domain": {"clear.md": "# CLEAR: Categorize then Act"},
        })
        loader = BrainSkillLoader(str(tmp_path))

        active_phases = ["domain/clear"]
        initial_paths: list[str] = []
        for phase in active_phases:
            if phase.startswith("domain/"):
                domain_file = f"{phase}.md"
                if loader.get_with_meta(domain_file):
                    initial_paths.append(domain_file)

        assert initial_paths == ["domain/clear.md"]

        resolved_pairs = loader.resolve_dependencies_with_paths(initial_paths)
        results = [
            _wrap_section(path, body, loader.get_tag_type(path))
            for path, body in resolved_pairs
        ]

        joined = "\n".join(results)
        assert '<navigation id="domain/clear.md">' in joined
        assert "CLEAR: Categorize then Act" in joined
        assert "</navigation>" in joined

    def test_all_five_domains_resolvable(self, tmp_path: Path):
        """All five domain files resolve via the H1 fix path."""
        _make_skills(tmp_path, {
            "domain": {
                "clear.md": "# CLEAR",
                "complicated.md": "# COMPLICATED",
                "complex.md": "# COMPLEX",
                "chaotic.md": "# CHAOTIC",
                "casual.md": "# CASUAL",
            },
        })
        loader = BrainSkillLoader(str(tmp_path))
        for domain in ("clear", "complicated", "complex", "chaotic", "casual"):
            result = loader.get_with_meta(f"domain/{domain}.md")
            assert result is not None, f"domain/{domain}.md not found in path_index"


class TestIdleTimeoutConversation:
    """T4: Idle timeout schedule with conversation-length override."""

    @pytest.mark.asyncio
    async def test_schedule_with_warning_override(self):
        from src.scheduling.idle_timeout import IdleTimeoutManager

        warned = []
        closed = []

        async def warn_cb(eid: str) -> None:
            warned.append(eid)

        async def close_cb(eid: str) -> None:
            closed.append(eid)

        mgr = IdleTimeoutManager(warn_callback=warn_cb, close_callback=close_cb)
        mgr.schedule("evt-1", warning_sec=3600)
        assert mgr.has_timer("evt-1")
        mgr.cancel("evt-1")
        assert not mgr.has_timer("evt-1")

    @pytest.mark.asyncio
    async def test_schedule_without_override_uses_default(self):
        from src.scheduling.idle_timeout import IdleTimeoutManager

        async def noop(eid: str) -> None:
            pass

        mgr = IdleTimeoutManager(warn_callback=noop, close_callback=noop)
        mgr.schedule("evt-2")
        assert mgr.has_timer("evt-2")
        mgr.cancel_all()


class TestUserMessageBypass:
    """T3: DELIVERED user turn clears _waiting_for_user in scan logic."""

    def test_user_delivered_turn_detected_in_recent_window(self):
        """Verify the scan pattern: actor=='user' + status=='delivered' in last 10 turns."""
        from collections import namedtuple
        Status = namedtuple("Status", ["value"])
        Turn = namedtuple("Turn", ["actor", "status", "action"])

        old_brain_turn = Turn(actor="brain", status=Status("evaluated"), action="response")
        old_user_turn = Turn(actor="user", status=Status("evaluated"), action="message")
        new_user_turn = Turn(actor="user", status=Status("delivered"), action="message")
        conversation = [old_brain_turn, old_user_turn] + [old_brain_turn] * 15 + [new_user_turn]

        has_unread = any(t.status.value == "delivered" for t in conversation)
        has_user_unread = has_unread and any(
            t.status.value == "delivered" and t.actor == "user"
            for t in conversation[-10:]
        )
        assert has_user_unread is True

    def test_stale_user_turns_not_matched(self):
        """Old delivered user turns beyond the 10-turn window are not matched."""
        from collections import namedtuple
        Status = namedtuple("Status", ["value"])
        Turn = namedtuple("Turn", ["actor", "status", "action"])

        stale_user = Turn(actor="user", status=Status("delivered"), action="message")
        brain_turn = Turn(actor="brain", status=Status("evaluated"), action="response")
        conversation = [stale_user] + [brain_turn] * 15

        has_unread = any(t.status.value == "delivered" for t in conversation)
        has_user_unread = has_unread and any(
            t.status.value == "delivered" and t.actor == "user"
            for t in conversation[-10:]
        )
        assert has_user_unread is False
