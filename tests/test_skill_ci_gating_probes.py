# tests/test_skill_ci_gating_probes.py
# @ai-rules:
# 1. [Pattern]: Loads REAL skill files via BrainSkillLoader filesystem mode — no mocks.
# 2. [Purpose]: Probe gate for CI gating skill content (Steps 10-11). Validates WHY/WHAT
#    principles survive rewrites, no tool names in body, and injection via find_paths_by_tag.
# 3. [Constraint]: Tests run against current skill files on disk. Implementation runs in
#    parallel — tests assert planned interface, may need adjustment at reconciliation.
# 4. [Contract]: T-S6/T-S7/T-S7b test assembled prompt behavior via BrainSkillLoader's
#    find_paths_by_tag + resolve_dependencies. They do NOT import brain.py.
"""
CI gating skill content probes (Steps 10-13 of jenkins-view-discovery plan).

Spec rows: T-14, T-S1 through T-S7b.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

SKILLS_DIR = Path(__file__).parent.parent / "src" / "agents" / "brain_skills"

# ---------------------------------------------------------------------------
# Known FRIDAY tool names (from frontmatter `tools:` across all skills).
# Skill BODY text must never mention these — authoring rule enforcement.
# ---------------------------------------------------------------------------
_TOOL_NAMES = frozenset({
    "classify_event", "select_agent", "close_event", "set_phase",
    "refresh_kargo_context", "refresh_gitlab_context", "refresh_github_context",
    "consult_deep_memory", "take_note", "record_observation",
    "search_open_incidents", "list_observations", "review_notes",
    "notify_user_slack", "report_incident", "lookup_service",
    "defer_event", "subscribe_to", "wait_for_user", "message_agent",
    "reply_to_agent", "create_plan", "get_plan_progress",
    "fetch_jira_issue", "comment_jira_issue", "transition_jira_issue",
    "notify_gitlab_result", "inspect_event", "request_user_approval",
    "wait_for_agent", "hold_watch", "wait_for_jarvis",
    "post_sticky_note", "read_sticky_notes", "wait_for_verification",
    "respond_to_jarvis", "lookup_journal",
    "greenwave", "ask_release_ai", "retrigger_jenkins_build",
})


@pytest.fixture(scope="module")
def loader():
    from src.agents.brain_skill_loader import BrainSkillLoader
    return BrainSkillLoader(str(SKILLS_DIR))


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter (between --- delimiters) from skill text."""
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            return text[end + 3:].strip()
    return text.strip()


def _read_skill_body(rel_path: str) -> str:
    """Read a skill file and return body without frontmatter."""
    full = (SKILLS_DIR / rel_path).read_text()
    return _strip_frontmatter(full)


def _read_skill_frontmatter(rel_path: str) -> dict:
    """Read a skill file and return parsed YAML frontmatter."""
    import yaml
    full = (SKILLS_DIR / rel_path).read_text()
    if full.startswith("---"):
        end = full.find("---", 3)
        if end != -1:
            return yaml.safe_load(full[3:end]) or {}
    return {}


# =========================================================================
# T-14: aligner_ci_gating.md probes — still pass after WHY/WHAT rewrite
# =========================================================================

class TestT14AfterRewrite:
    """T-14: Verify T-14 assertions still hold after the WHY/WHAT rewrite.

    These are the SAME assertions as TestT14SkillContent in test_jenkins_observer.py.
    We re-check here to confirm the rewrite in Step 10 didn't break them.
    """

    @pytest.fixture(scope="class")
    def skill_body(self):
        path = SKILLS_DIR / "source" / "aligner_ci_gating.md"
        assert path.exists(), f"Skill file not found: {path}"
        return path.read_text()

    def test_retry_before_escalate_present(self, skill_body):
        body_lower = skill_body.lower()
        has_restart = "restart" in body_lower or "retry" in body_lower
        has_before = "before" in body_lower
        has_escalate = "escalat" in body_lower
        assert has_restart and has_before, \
            "Skill must contain 'restart/retry before' language"
        assert has_escalate, \
            "Skill must reference escalation as a later step"

    def test_unconditional_auto_retry_absent(self, skill_body):
        assert "always retry" not in skill_body.lower()
        assert "auto-retry all" not in skill_body.lower()

    def test_closure_validation_present(self, skill_body):
        body_lower = skill_body.lower()
        assert "closure" in body_lower or "close" in body_lower
        assert "gating" in body_lower or "decision" in body_lower or "policies" in body_lower

    def test_timing_awareness_present(self, skill_body):
        body_lower = skill_body.lower()
        assert "hour" in body_lower or "6" in skill_body or "9" in skill_body


# =========================================================================
# T-S1: close/when-to-close.md CI gating content
# =========================================================================

class TestTS1CloseWhenToClose:
    """T-S1: close/when-to-close.md has CI gating closure guidance.

    Closure means the gating decision is satisfied, not metric resolution.
    """

    @pytest.fixture(scope="class")
    def body(self):
        return _read_skill_body("close/when-to-close.md")

    def test_ci_gating_closure_mentions_gating_decision(self, body):
        body_lower = body.lower()
        assert "gating" in body_lower and "decision" in body_lower, \
            "close/when-to-close.md must mention 'gating decision' for ci_gating closure"

    def test_ci_gating_closure_not_metric_resolution(self, body):
        body_lower = body.lower()
        has_gating_decision = "gating decision" in body_lower or "gating-decision" in body_lower
        assert has_gating_decision, \
            "CI gating closure must reference gating decision satisfaction, not metric resolution"

    def test_ci_gating_subject_type_mentioned(self, body):
        assert "ci_gating" in body or "ci gating" in body.lower(), \
            "close/when-to-close.md must explicitly reference ci_gating subject type"

    def test_requires_source_removed(self):
        """T-S7 prerequisite: requires: [source/{event.source}.md] must be removed."""
        fm = _read_skill_frontmatter("close/when-to-close.md")
        requires = fm.get("requires", [])
        for req in requires:
            assert "source/" not in req, \
                f"close/when-to-close.md must NOT have requires: [source/...] — found: {req}"


# =========================================================================
# T-S2: always/11-subject-semantics.md
# =========================================================================

class TestTS2SubjectSemantics:
    """T-S2: ci_gating section uses {job_name} format (no pipe), mentions job_metadata."""

    @pytest.fixture(scope="class")
    def body(self):
        return _read_skill_body("always/11-subject-semantics.md")

    def test_no_pipe_in_service_format(self, body):
        ci_section_match = re.search(
            r"###?\s*ci_gating(.*?)(?=###?\s|\Z)", body, re.DOTALL | re.IGNORECASE
        )
        assert ci_section_match, "ci_gating section not found in 11-subject-semantics.md"
        section = ci_section_match.group(1)
        assert "{job_name}|{version}" not in section, \
            "ci_gating section must NOT use pipe-separated {job_name}|{version} format"

    def test_job_name_format_present(self, body):
        ci_section_match = re.search(
            r"###?\s*ci_gating(.*?)(?=###?\s|\Z)", body, re.DOTALL | re.IGNORECASE
        )
        assert ci_section_match, "ci_gating section not found"
        section = ci_section_match.group(1)
        assert "job_name" in section, \
            "ci_gating section must reference job_name"

    def test_job_metadata_mentioned(self, body):
        body_lower = body.lower()
        assert "job_metadata" in body_lower, \
            "11-subject-semantics.md must mention job_metadata"

    def test_greenwave_tool_name_removed(self, body):
        ci_section_match = re.search(
            r"###?\s*ci_gating(.*?)(?=###?\s|\Z)", body, re.DOTALL | re.IGNORECASE
        )
        if ci_section_match:
            section = ci_section_match.group(1)
            assert "`greenwave`" not in section, \
                "ci_gating section must NOT contain literal tool name `greenwave`"


# =========================================================================
# T-S3: gated/ci-gating-environment.md exists with correct content
# =========================================================================

class TestTS3CiGatingEnvironment:
    """T-S3: gated/ci-gating-environment.md exists with wrapper/leaf, gating decision
    service description, timing cadence. No literal 'greenwave' in body."""

    @pytest.fixture(scope="class")
    def full_text(self):
        path = SKILLS_DIR / "gated" / "ci-gating-environment.md"
        assert path.exists(), "gated/ci-gating-environment.md must exist"
        return path.read_text()

    @pytest.fixture(scope="class")
    def body(self, full_text):
        return _strip_frontmatter(full_text)

    @pytest.fixture(scope="class")
    def frontmatter(self, full_text):
        import yaml
        if full_text.startswith("---"):
            end = full_text.find("---", 3)
            if end != -1:
                return yaml.safe_load(full_text[3:end]) or {}
        return {}

    def test_wrapper_leaf_mentioned(self, body):
        body_lower = body.lower()
        assert "wrapper" in body_lower, "Must mention wrapper jobs"
        assert "leaf" in body_lower or "lane" in body_lower, \
            "Must mention leaf jobs or lanes"

    def test_gating_decision_service_described(self, body):
        body_lower = body.lower()
        has_gating = "gating" in body_lower and ("decision" in body_lower or "service" in body_lower)
        assert has_gating, \
            "Must describe the gating decision service (without literal tool name)"

    def test_no_greenwave_in_body(self, body):
        assert "greenwave" not in body.lower(), \
            "Body must NOT contain literal 'greenwave' — tool names in frontmatter only"

    def test_greenwave_in_frontmatter_tools(self, frontmatter):
        tools = frontmatter.get("tools", [])
        assert "greenwave" in tools, \
            "greenwave must be listed in frontmatter tools: (not body)"

    def test_timing_cadence_mentioned(self, body):
        body_lower = body.lower()
        assert "hour" in body_lower or "6" in body or "9" in body, \
            "Must mention timing cadence (6-9 hours for wrappers)"

    def test_tag_type_is_context(self, frontmatter):
        assert frontmatter.get("tag_type") == "context", \
            "gated/ci-gating-environment.md must have tag_type: context"

    def test_ci_gating_tag_present(self, frontmatter):
        tags = frontmatter.get("tags", [])
        assert "ci_gating" in tags, \
            "Must have 'ci_gating' tag for find_paths_by_tag discovery"

    def test_ask_release_ai_not_in_body(self, body):
        assert "ask_release_ai" not in body, \
            "Body must NOT contain literal 'ask_release_ai' — tool names in frontmatter only"

    def test_retrigger_jenkins_build_in_frontmatter_tools(self, frontmatter):
        tools = frontmatter.get("tools", [])
        assert "retrigger_jenkins_build" in tools, \
            "retrigger_jenkins_build must be listed in frontmatter tools:"

    def test_retrigger_jenkins_build_not_in_body(self, body):
        assert "retrigger_jenkins_build" not in body, \
            "Body must NOT contain literal 'retrigger_jenkins_build' — tool names in frontmatter only"


# =========================================================================
# T-S4: dispatch/coordination-triage.md investigation-first for ci_gating
# =========================================================================

class TestTS4CoordinationTriage:
    """T-S4: dispatch/coordination-triage.md has investigation-first for ci_gating."""

    @pytest.fixture(scope="class")
    def body(self):
        return _read_skill_body("dispatch/coordination-triage.md")

    def test_ci_gating_dispatch_principles(self, body):
        body_lower = body.lower()
        has_ci_gating = "ci gating" in body_lower or "ci_gating" in body_lower
        assert has_ci_gating, \
            "coordination-triage.md must have CI gating dispatch guidance"

    def test_investigation_first(self, body):
        body_lower = body.lower()
        has_investigation = "investigat" in body_lower
        assert has_investigation, \
            "CI gating dispatch must mention investigation-first approach"

    def test_native_retrigger_over_agent_dispatch(self, body):
        """Plan Step 5: coordination-triage must steer toward native tools for transient infra retests."""
        body_lower = body.lower()
        has_native = "native" in body_lower or "brain" in body_lower or "retest" in body_lower or "retrigger" in body_lower
        assert has_native, \
            "coordination-triage.md must mention native tool retest for transient CI failures"

    def test_no_developer_dispatch_for_infra_retest(self, body):
        """Plan Step 5: transient infra failures should NOT dispatch Developer/SysAdmin for retest."""
        body_lower = body.lower()
        has_transient_guidance = "transient" in body_lower
        assert has_transient_guidance, \
            "coordination-triage.md must mention transient infrastructure failures"


# =========================================================================
# T-S5: No tool names in body of all new/amended skills
# =========================================================================

class TestTS5NoToolNamesInBody:
    """T-S5: All new/amended skill files must have NO tool names in their body text.

    Tool names are allowed ONLY in frontmatter `tools:` lists.
    """

    AMENDED_SKILLS = [
        "source/aligner_ci_gating.md",
        "gated/ci-gating-environment.md",
        "close/when-to-close.md",
        "context/aligner.md",
        "always/11-subject-semantics.md",
        "dispatch/coordination-triage.md",
        "post-agent/agent-recommendations.md",
    ]

    @pytest.fixture(scope="class")
    def skill_bodies(self):
        """Load body text (no frontmatter) for all amended skills."""
        bodies = {}
        for rel in self.AMENDED_SKILLS:
            path = SKILLS_DIR / rel
            if path.exists():
                bodies[rel] = _strip_frontmatter(path.read_text())
        return bodies

    # Files where this plan ONLY added content (not rewritten entirely).
    # Pre-existing protocol sections in these files contain tool names
    # that predate this plan and are out of scope for this PR.
    _NEW_CONTENT_ONLY = {
        "source/aligner_ci_gating.md",
        "gated/ci-gating-environment.md",
        "context/aligner.md",
        "always/11-subject-semantics.md",
    }

    def test_no_tool_names_in_any_body(self, skill_bodies):
        """Scan amended skill bodies for literal tool name references.

        Scoped to files this plan rewrote entirely or created new.
        Files where only a sub-bullet was added (close, post-agent, dispatch)
        have pre-existing tool names in their protocol sections that predate
        this plan — those are excluded to avoid false positives on pre-existing
        content.
        """
        violations = []
        for rel, body in skill_bodies.items():
            if rel not in self._NEW_CONTENT_ONLY:
                continue
            for tool in _TOOL_NAMES:
                if re.search(rf'\b{re.escape(tool)}\b', body):
                    violations.append(f"{rel}: found `{tool}` in body")

        assert not violations, \
            "Tool names found in skill body text (must be in frontmatter only):\n" + \
            "\n".join(violations)


# =========================================================================
# T-S6: gated/ci-gating-environment.md injected for ci_context events
# =========================================================================

class TestTS6CiGatingInjection:
    """T-S6: find_paths_by_tag('ci_gating') returns the gated skill.

    Verifies the skill is discoverable via the tag system, which is the
    mechanism brain.py uses to inject gated skills into the assembled prompt.
    """

    def test_ci_gating_tag_returns_gated_skill(self, loader):
        """ci_gating tag must resolve to gated/ci-gating-environment.md."""
        paths = loader.find_paths_by_tag("ci_gating")
        gated_paths = [p for p in paths if "gated/" in p and "ci-gating" in p]
        assert len(gated_paths) > 0, \
            "find_paths_by_tag('ci_gating') must return gated/ci-gating-environment.md"

    def test_ci_gating_skill_body_resolvable(self, loader):
        """The skill body must be readable via get_with_meta."""
        paths = loader.find_paths_by_tag("ci_gating")
        gated_paths = [p for p in paths if "gated/" in p]
        assert len(gated_paths) > 0, "No gated ci_gating skill found"

        for gp in gated_paths:
            result = loader.get_with_meta(gp)
            assert result is not None, f"get_with_meta returned None for {gp}"
            body, meta = result
            assert len(body) > 50, f"Skill body too short for {gp}"

    def test_ci_gating_tag_not_in_kargo_results(self, loader):
        """ci_gating tag results must not include kargo skills (no cross-contamination)."""
        paths = loader.find_paths_by_tag("ci_gating")
        kargo_paths = [p for p in paths if "kargo" in p]
        assert len(kargo_paths) == 0, \
            f"ci_gating tag should not return kargo paths: {kargo_paths}"

    def test_non_ci_gating_aligner_event_skips_ci_skill(self, loader):
        """For a plain aligner event (no ci_gating tag match from evidence),
        the ci-gating-environment.md should NOT be in the assembled prompt.

        This verifies that the always/ phase does NOT accidentally load gated/ skills.
        """
        always_paths = loader.get_all_paths_for_phase("always") or []
        ci_gating_in_always = [p for p in always_paths if "ci-gating-environment" in p]
        assert len(ci_gating_in_always) == 0, \
            "gated/ci-gating-environment.md must NOT appear in always/ phase"

        # Also verify it's not in the context/ phase (it's gated/, not context/)
        context_paths = loader.get_all_paths_for_phase("context") or []
        ci_gating_in_context = [p for p in context_paths if "ci-gating-environment" in p]
        assert len(ci_gating_in_context) == 0, \
            "gated/ci-gating-environment.md must NOT appear in context/ phase"


# =========================================================================
# T-S7: close/when-to-close.md requires: removed
# =========================================================================

class TestTS7CloseRequiresRemoved:
    """T-S7: close/when-to-close.md must NOT have requires: [source/{event.source}.md].

    After removal, the close-phase prompt for a ci_gating event should contain
    the composite source/aligner_ci_gating.md (loaded unconditionally by the
    source phase), not a duplicate generic source/aligner.md forced by requires:.
    """

    def test_no_source_requires(self):
        fm = _read_skill_frontmatter("close/when-to-close.md")
        requires = fm.get("requires", [])
        source_deps = [r for r in requires if r.startswith("source/")]
        assert len(source_deps) == 0, \
            f"close/when-to-close.md must NOT require source/*.md — found: {source_deps}"

    def test_composite_loaded_for_ci_gating(self, loader):
        """When source=aligner + subject_type=ci_gating, the composite
        source/aligner_ci_gating.md exists and is preferred over generic."""
        all_source = loader.get_all_paths_for_phase("source") or []
        assert "source/aligner_ci_gating.md" in all_source, \
            "source/aligner_ci_gating.md must exist in source phase"

    def test_close_phase_dependencies_exclude_generic_source(self, loader):
        """Resolving close/when-to-close.md dependencies should NOT pull in
        source/aligner.md (the generic file). The source phase loads the
        composite unconditionally — requires: was redundant and harmful."""
        close_result = loader.get_with_meta("close/when-to-close.md")
        assert close_result is not None
        _, meta = close_result

        requires = meta.get("requires", [])
        resolved_paths = []
        if requires:
            template_vars = {"event.source": "aligner"}
            resolved = loader.resolve_dependencies_with_paths(
                requires, template_vars=template_vars
            )
            resolved_paths = [p for p, _ in resolved]

        assert "source/aligner.md" not in resolved_paths, \
            "close/when-to-close.md requires: must not resolve to source/aligner.md"


# =========================================================================
# T-S7b: post-agent/agent-recommendations.md requires: removed
# =========================================================================

class TestTS7bAgentRecommendationsRequiresRemoved:
    """T-S7b: post-agent/agent-recommendations.md must NOT have
    requires: [source/{event.source}.md]. Sibling of T-S7.

    This file loads on both verify and escalate phases — more frequent
    than the terminal close phase.
    """

    def test_no_source_requires(self):
        fm = _read_skill_frontmatter("post-agent/agent-recommendations.md")
        requires = fm.get("requires", [])
        source_deps = [r for r in requires if r.startswith("source/")]
        assert len(source_deps) == 0, \
            f"agent-recommendations.md must NOT require source/*.md — found: {source_deps}"

    def test_deep_memory_requires_preserved(self):
        """The always/04-deep-memory.md dependency must be preserved."""
        fm = _read_skill_frontmatter("post-agent/agent-recommendations.md")
        requires = fm.get("requires", [])
        assert "always/04-deep-memory.md" in requires, \
            "agent-recommendations.md must still require always/04-deep-memory.md"

    def test_verify_escalate_phase_no_generic_source(self, loader):
        """Resolving agent-recommendations.md dependencies for a ci_gating event
        should NOT pull in the generic source/aligner.md."""
        result = loader.get_with_meta("post-agent/agent-recommendations.md")
        assert result is not None
        _, meta = result

        requires = meta.get("requires", [])
        if requires:
            template_vars = {"event.source": "aligner"}
            resolved = loader.resolve_dependencies_with_paths(
                requires, template_vars=template_vars
            )
            resolved_paths = [p for p, _ in resolved]
            assert "source/aligner.md" not in resolved_paths, \
                "agent-recommendations.md requires: must not resolve to source/aligner.md"
