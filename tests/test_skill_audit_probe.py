# tests/test_skill_audit_probe.py
# @ai-rules:
# 1. [Pattern]: Loads REAL skill files via BrainSkillLoader filesystem mode — no mocks.
# 2. [Purpose]: Probe gate for HOW/WHY skill audit. Validates principles survive rewrites.
# 3. [Constraint]: Tests run against current skill files on disk. Update assertions after each rewrite phase.
"""
Probe gate tests for the HOW/WHY skill audit.

Phase 2.5a: After rewriting always/06, asserts key principles PRESENT + prescriptive content ABSENT.
Phase 3.5:  After deduplication, asserts no duplicate content + gated/ metadata correct.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

import pytest
import yaml

from tests.test_skill_ci_gating_probes import _TOOL_NAMES, _strip_frontmatter

SKILLS_DIR = Path(__file__).parent.parent / "src" / "agents" / "brain_skills"


@pytest.fixture(scope="module")
def loader():
    from src.agents.brain_skill_loader import BrainSkillLoader
    return BrainSkillLoader(str(SKILLS_DIR))


@pytest.fixture(scope="module")
def skill_06_body(loader):
    result = loader.get_with_meta("always/06-decision-guidelines.md")
    assert result is not None, "always/06-decision-guidelines.md not found"
    body, _ = result
    return body


class TestBaseline:
    """Run BEFORE any rewrites to establish what currently exists."""

    def test_loader_discovers_skills(self, loader):
        phases = list(loader._corpus.cache.keys())
        assert "always" in phases
        assert "domain" in phases
        assert "source" in phases

    def test_skill_06_exists(self, skill_06_body):
        assert len(skill_06_body) > 100

    def test_prescriptive_content_removed_post_rewrite(self, skill_06_body):
        """Post-rewrite: prescriptive content should be gone."""
        assert "1 minute = 60" not in skill_06_body
        assert "1 hour = 3600" not in skill_06_body
        assert "MintMaker" not in skill_06_body
        assert "Renovate" not in skill_06_body

    def test_current_principles_present(self, skill_06_body):
        """These principles MUST survive the rewrite."""
        assert "self-answer" in skill_06_body.lower() or "Self-Answer" in skill_06_body
        assert "calibrat" in skill_06_body.lower()  # calibrate/calibration
        assert "recurring" in skill_06_body.lower() or "Recurring" in skill_06_body


class TestPhase2_5a:
    """Phase 2.5a probe: run AFTER rewriting always/06."""

    def test_principles_survived(self, skill_06_body):
        body_lower = skill_06_body.lower()
        assert "self-answer" in body_lower or "blackboard" in body_lower, \
            "Self-Answer First principle missing after rewrite"
        assert "calibrat" in body_lower, \
            "Deferral calibration principle missing after rewrite"
        assert "recurring" in body_lower or "pattern" in body_lower, \
            "Recurring Failure Recognition missing after rewrite"
        assert "scope" in body_lower, \
            "Scope Awareness missing after rewrite"

    def test_prescriptive_content_removed(self, skill_06_body):
        assert "1 minute = 60" not in skill_06_body, \
            "Seconds conversion table still present"
        assert "1 hour = 3600" not in skill_06_body, \
            "Seconds conversion table still present"
        assert "MintMaker" not in skill_06_body, \
            "Environmental tool name still present"
        assert "Renovate" not in skill_06_body, \
            "Environmental tool name still present"
        assert "1800s" not in skill_06_body, \
            "Hardcoded clarification timeout still present"

    def test_hardcoded_thresholds_removed(self, skill_06_body):
        assert "multi-arch/arm64/s390x" not in skill_06_body, \
            "Architecture-specific variant still present"
        assert "2-3 hours as the floor" not in skill_06_body, \
            "Hardcoded cron floor still present"

    def test_flange_reframed(self, skill_06_body):
        body_lower = skill_06_body.lower()
        has_stall = "stall" in body_lower or "repeated" in body_lower
        has_flange = "flange" in body_lower or "runaway" in body_lower or "ceiling" in body_lower
        assert has_stall or has_flange, \
            "Structural bounds not reframed as stall detection / emergency flange"

    def test_seconds_verification_principle(self, skill_06_body):
        body_lower = skill_06_body.lower()
        has_verify = "ensure" in body_lower and "seconds" in body_lower
        has_agree = "agree" in body_lower and ("duration" in body_lower or "seconds" in body_lower)
        assert has_verify or has_agree, \
            "Seconds verification principle not present (replacement for conversion table)"

    def test_heading_reference_fixed(self, skill_06_body):
        assert "State Change Subscriptions" not in skill_06_body, \
            "Broken heading reference 'State Change Subscriptions' still present (should be 'Subscription Over Blind Waits')"


class TestPhase3_5:
    """Phase 3.5 probe: run AFTER progressive tier deduplication."""

    def test_no_duplicate_subscribe_rule(self, loader):
        """Subscribe-before-defer should appear once (always/08), not in progressive tiers."""
        always_08 = loader.get_with_meta("always/08-flow-engineering.md")
        assert always_08 is not None
        body_08, _ = always_08

        assert "subscription" in body_08.lower() or "subscribe" in body_08.lower(), \
            "always/08 must contain subscription principle"

        complicated = loader.get_with_meta("domain/complicated.md")
        if complicated:
            body_comp, _ = complicated
            assert "subscribe before defer" not in body_comp.lower(), \
                "domain/complicated.md still restates subscribe-before-defer (should bridge to always/08)"

    def test_no_duplicate_route_vs_message(self, loader):
        """Route vs Message should live in always/01, not in coordination-triage."""
        coord = loader.get_with_meta("dispatch/coordination-triage.md")
        if coord:
            body_coord, _ = coord
            assert "select_agent" not in body_coord or "message_agent" not in body_coord, \
                "coordination-triage.md still duplicates Route vs Message table from always/01"

    def test_gated_kargo_has_context_tag_type(self, loader):
        """After move to gated/, kargo must have explicit tag_type: context."""
        result = loader.get_with_meta("gated/kargo-environment.md")
        if result is None:
            pytest.skip("gated/kargo-environment.md not yet moved")
        _, meta = result
        assert meta.get("tag_type") == "context", \
            "gated/kargo-environment.md missing tag_type: context (lost folder default after move)"

    def test_gitlab_stays_in_context(self, loader):
        """gitlab-environment.md must remain in context/ (no double-load, no move needed)."""
        result = loader.get_with_meta("context/gitlab-environment.md")
        assert result is not None, \
            "gitlab-environment.md missing from context/ — should NOT have been moved to gated/"

    def test_gated_kargo_discoverable_by_tag(self, loader):
        """find_paths_by_tag('kargo') should find the gated/ file after move."""
        kargo_paths = loader.find_paths_by_tag("kargo")
        if any("gated/" in p for p in kargo_paths):
            return  # Moved and discoverable
        if any("context/" in p for p in kargo_paths):
            pytest.skip("kargo still in context/ — not yet moved to gated/")
        pytest.fail("kargo-environment.md not discoverable by 'kargo' tag")

    def test_no_kargo_double_load(self, loader):
        """kargo-environment.md should NOT appear in context/ phase after move."""
        context_paths = loader.get_all_paths_for_phase("context") or []
        kargo_in_context = [p for p in context_paths if "kargo" in p]
        assert len(kargo_in_context) == 0, \
            f"kargo still in context/ phase after gated/ move: {kargo_in_context}"

    def test_stall_detection_references_trajectories(self, skill_06_body):
        """Stall detection must reference live observation trajectories for ceiling."""
        start = skill_06_body.index("### Stall Detection")
        next_heading = skill_06_body.find("## ", start + len("### Stall Detection"))
        stall_section = skill_06_body[start:next_heading if next_heading != -1 else None]
        section_lower = " ".join(stall_section.lower().split())

        assert "trajectory" in section_lower, (
            "Stall Detection section must reference observation trajectories"
            " for ceiling calibration"
        )

        assert "takes precedence" in section_lower and "tighter" in section_lower, (
            "Stall Detection must state that a tighter live range takes"
            " precedence over the deep-memory baseline"
        )

        assert "single data point is not a trajectory" in section_lower, (
            "Stall Detection must guard against treating a single observation"
            " as a trajectory"
        )

        assert (
            "no live observations" in section_lower
            and "sparse" in section_lower
            and "deep memory is the sole source" in section_lower
        ), (
            "Stall Detection must fall back to deep memory when live"
            " observations are absent or too sparse to form a range"
        )

    def test_list_observations_mapped_to_decision_guidelines(self, loader):
        """list_observations tool must resolve back to always/06 via the reverse map."""
        skills = loader.get_tool_skills("list_observations")
        assert "always/06-decision-guidelines.md" in skills, (
            "list_observations not associated with"
            " always/06-decision-guidelines.md in the tool->skill map"
        )


# ---------------------------------------------------------------------------
# Content-contract tests for prompt files.
#
# Skill files are prompts, so there is no runtime behavior to execute here. What CAN be pinned
# without being tautological: (a) the loader wiring (tool -> skill, frontmatter), and (b) that
# each load-bearing statement lives inside the SECTION that owns it -- a bare "phrase in file"
# check still passes when the phrase sits in an unrelated or contradictory paragraph, and an
# `a or b or c` chain passes on almost any governance text. Every assertion below is
# section-scoped and names one specific statement; there are no `or` fallbacks.
# ---------------------------------------------------------------------------

def _section(body: str, heading: str) -> str:
    """Return whitespace-normalised text of the section starting at `heading` (exact line match).

    Runs to the next heading of the same or higher level, so sub-sections are included.
    Raises AssertionError (not ValueError) so a renamed heading fails with a clear message.
    """
    lines = body.splitlines()
    level = len(heading) - len(heading.lstrip("#"))
    try:
        start = next(i for i, ln in enumerate(lines) if ln.strip() == heading)
    except StopIteration:
        raise AssertionError(f"heading {heading!r} not found")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        ln = lines[i]
        if ln.startswith("#") and (len(ln) - len(ln.lstrip("#"))) <= level and ln.lstrip("#").startswith(" "):
            end = i
            break
    return " ".join(" ".join(lines[start:end]).split())


def _skill(loader, path: str) -> str:
    result = loader.get_with_meta(path)
    assert result is not None, f"{path} not found"
    return result[0]


class TestSectionScopedHelper:
    """The helper is the instrument for every test below -- prove it can actually fail."""

    BODY = "# T\n## A\nalpha\n### A1\nnested\n## B\nbeta\n"

    def test_includes_subsections_and_stops_at_peer_heading(self):
        sec = _section(self.BODY, "## A")
        assert "alpha" in sec and "nested" in sec
        assert "beta" not in sec

    def test_missing_heading_fails_loudly(self):
        with pytest.raises(AssertionError, match="not found"):
            _section(self.BODY, "## Missing")


class TestStallDetectionContract:
    def test_both_stall_triggers_and_escalation_live_in_stall_section(self, skill_06_body):
        sec = _section(skill_06_body, "### Stall Detection (Emergency Flange)").lower()
        assert "repeated same-reason deferrals" in sec
        assert "elapsed ceiling" in sec
        assert "mandatory escalation" in sec
        assert "never defer on stale state" in sec

    def test_unbounded_waiting_is_framed_as_missing_circuit_breaker(self, loader):
        sec = _section(_skill(loader, "always/08-flow-engineering.md"), "## Two Kinds of Deferral").lower()
        assert "missing circuit breaker" in sec

    def test_stall_section_is_not_duplicated_in_other_always_skills(self, loader):
        """The rule has one owner (always/06); a second copy would drift."""
        owners = [
            p for p in (loader.get_all_paths_for_phase("always") or [])
            if "### Stall Detection" in _skill(loader, p)
        ]
        assert owners == ["always/06-decision-guidelines.md"]


class TestDeflectionClosureGateProbe:
    PATH = "close/when-to-close.md"

    def test_close_event_tool_loads_this_skill(self, loader):
        assert self.PATH in loader.get_tool_skills("close_event")

    def test_gate_states_resolution_standard_and_both_source_rules(self, loader):
        sec = _section(_skill(loader, self.PATH), "## Deflection Closure Gate").lower()
        assert "requires verified resolution, an active external tracking link, or explicit user consensus" in sec
        assert "user-facing conversations (chat / slack)" in sec
        assert "automated events (aligner / pr / ci)" in sec
        assert "never terminate an automated event without recording verified root cause evidence" in sec

    def test_gate_precedes_domain_gated_criteria(self, loader):
        body = _skill(loader, self.PATH)
        assert body.index("## Deflection Closure Gate") < body.index("## Domain-Gated Close Criteria")

    def test_chaotic_and_casual_cannot_close_directly(self, loader):
        sec = _section(_skill(loader, self.PATH), "## Domain-Gated Close Criteria")
        assert "**CHAOTIC**: NEVER close from CHAOTIC" in sec
        assert "**CASUAL**: NEVER close from CASUAL directly" in sec

    @pytest.mark.parametrize("bad_phrase", ["feel free to ask", "someone else's problem", "out of scope, closing"])
    def test_no_negative_production_phrasing(self, loader, bad_phrase):
        # AGENTS.md rule: positive-only guidance, never quote bad output in a skill.
        assert bad_phrase not in _skill(loader, self.PATH).lower()


class TestWorkerHandoffBalanceProbe:
    REC = "post-agent/agent-recommendations.md"

    def test_handoff_section_requires_follow_or_recorded_override(self, loader):
        sec = _section(_skill(loader, self.REC), "## Worker Handoff and Agent POV Balance").lower()
        assert "follow the recommended handoff" in sec
        assert "explicitly record the governing blackboard rule that overrides it" in sec
        assert "never silently drop or bypass a concrete worker handoff recommendation" in sec

    def test_handoff_override_rules_include_unapproved_source_mutations(self, loader):
        """The override list is what keeps a worker handoff from outranking the approval gate."""
        sec = _section(_skill(loader, self.REC), "## Worker Handoff and Agent POV Balance").lower()
        assert "unapproved source mutations" in sec

    def test_decision_routing_ties_recommendations_to_approval_gates(self, loader):
        body = _skill(loader, "dispatch/decision-routing.md")
        assert "not what you should do" not in body.lower()
        # Both statements must be in ONE passage: recommendations are sensor input AND are
        # evaluated against approval gates -- not merely both mentioned somewhere in the file.
        flat = " ".join(body.split())
        i = flat.index("sensor inputs for you to evaluate against")
        assert "approval gates" in flat[i:i + 160]


def test_agent_dispatch_defer_rules_alignment(loader):
    """VMER-2187: Verify intermediate deferral rules harmonization across skills.

    Tests T-1 through T-6 from Test Specification & Code Review findings:
    - Tool-to-skill indexing: always/01 in loader.get_tool_skills("defer_event")
    - T-1: Blanket deferral ban removed from always/01-function-rules.md
    - T-2: Intermediate deferral permitted on active wake in always/01-function-rules.md
    - T-3: External async distinction and single wait discipline in always/09-phase-lifecycle.md
    - T-4: defer_event present in intermediate/_phase.yaml and intermediate/awareness.md
    - T-6: Timekeeper context loader compatibility
    """
    assert "always/01-function-rules.md" in loader.get_tool_skills("defer_event")

    skill_01 = _skill(loader, "always/01-function-rules.md")
    skill_09 = _skill(loader, "always/09-phase-lifecycle.md")

    # T-1 & T-2: Section-scoped checks in always/01
    sec_01 = _section(skill_01, "## Agent Progress vs Completed Work")
    assert "close, defer, or transition phases" not in sec_01
    assert "do not defer" not in sec_01.lower()
    assert "defer the event (`defer_event`)" in sec_01

    # T-3: Section-scoped checks in always/09
    sec_09_cap = _section(skill_09, "## Capabilities Per Phase")
    assert "external async result" in sec_09_cap
    assert "call wait_for_agent ONCE to park" in sec_09_cap
    assert "valid only for capacity gating" not in sec_09_cap
    assert "in-flight agent is actively progressing" in sec_09_cap
    assert "Do not transition to VERIFY while an agent dispatch is still running" in sec_09_cap

    # T-4: Intermediate phase configuration and awareness
    phase_yaml = yaml.safe_load((SKILLS_DIR / "intermediate" / "_phase.yaml").read_text())
    assert "defer_event" in phase_yaml["description"]

    skill_intermediate_awareness = _skill(loader, "intermediate/awareness.md")
    assert "defer_event" in skill_intermediate_awareness

    # T-6: Timekeeper context loader compatibility
    from src.routes.timekeeper import _load_brain_context
    ctx = _load_brain_context()
    assert len(ctx) > 0
    assert "Agent Progress vs Completed Work" in ctx


class TestWaitingApprovalDedupRepollProbe:
    """VMER-2216: Content contract and modularity probes for waiting_approval dedup re-poll.

    T-1: deep-memory-fixes.md pre-parking note protocol.
    T-2: 05-cynefin.md cross-issue correlation superseded re-poll protocol.
    T-4: Modularity ceiling (<= 100 lines) for both modified skill files.
    """

    DEEP_FIXES = "dispatch/deep-memory-fixes.md"
    CYNEFIN = "always/05-cynefin.md"

    def test_t1_deep_memory_fixes_instructs_note_before_parking(self, loader):
        """T-1: Section # Deep Memory Fix Proposals (Propose and Prompt) in deep-memory-fixes.md

        Asserts exact heading contains 'take_note', 'cross-event', and 'waiting_approval'.
        """
        sec = _section(
            _skill(loader, self.DEEP_FIXES),
            "# Deep Memory Fix Proposals (Propose and Prompt)",
        )
        assert "take_note" in sec
        assert "cross-event" in sec
        assert "waiting_approval" in sec

    def test_t2_cynefin_cross_issue_correlation_waiting_approval_closure(self, loader):
        """T-2: Section ## Cross-Issue Correlation (before classifying) in 05-cynefin.md

        Asserts exact heading contains 'waiting_approval', 'superseded re-poll', and 'set_phase'.
        """
        sec = _section(
            _skill(loader, self.CYNEFIN),
            "## Cross-Issue Correlation (before classifying)",
        )
        assert "waiting_approval" in sec
        assert "superseded re-poll" in sec
        assert "set_phase" in sec

    def test_t4_modularity_file_line_limits(self):
        """T-4: Modularity check ensuring deep-memory-fixes.md and 05-cynefin.md <= 100 lines."""
        for path in (self.DEEP_FIXES, self.CYNEFIN):
            full_path = SKILLS_DIR / path
            lines = full_path.read_text().splitlines()
            assert len(lines) <= 100, f"{path} exceeded modularity ceiling: {len(lines)} lines"


class TestGemini4PhaseBudgetsAndSelfAuditSkillsProbe:
    """Gemini 4 phase YAML budgets and section-scoped self-audit skill probes (#322, #323, #324).

    T-10: All 12 _phase.yaml budgets are 65536 and intermediate/_phase.yaml description updated.
    T-11: Section-scoped after-escalation and field-note conciseness contracts + hygiene checks.
    T-12: Cross-source BrainSkillLoader hygiene + JARVIS incremental inspection & passive sticky notes.
    """

    _TOOL_RE = re.compile(
        r"\b(" + "|".join(sorted(map(re.escape, _TOOL_NAMES), key=len, reverse=True)) + r")\b"
    )

    def test_all_12_phase_yaml_budgets_are_65536(self, loader):
        """T-10: Every _phase.yaml sets max_output_tokens == 65536 and intermediate description aligns."""
        phase_yamls = sorted(SKILLS_DIR.glob("*/_phase.yaml"))
        assert len(phase_yamls) == 12

        for yaml_path in phase_yamls:
            phase = yaml_path.parent.name
            meta = loader.get_phase_meta(phase)
            assert meta["max_output_tokens"] == 65536, (
                f"{phase}/_phase.yaml expected max_output_tokens=65536, got {meta.get('max_output_tokens')}"
            )

        intermediate_desc = loader.get_phase_meta("intermediate")["description"]
        assert "Normalized token limit: 65536." in intermediate_desc
        assert "defer_event" in intermediate_desc

    def test_after_escalation_and_field_note_conciseness_contracts(self, loader):
        """T-11: Section-scoped contracts for always/09-phase-lifecycle.md and always/10-observations.md."""
        tool_re = self._TOOL_RE

        esc_sec = _section(_skill(loader, "always/09-phase-lifecycle.md"), "## After Escalation")
        esc_lower = esc_sec.lower()
        assert "single-delivery" in esc_lower
        assert "automated check-in" in esc_lower
        assert "live repository or promotion state" in esc_lower
        assert set(tool_re.findall(esc_sec)) == set()

        obs_sec = _section(_skill(loader, "always/10-observations.md"), "### Note vs Other Tools")
        obs_lower = obs_sec.lower()
        assert "triage context" in obs_lower
        assert "compact, self-contained insight" in obs_lower
        assert "shared token capacity" in obs_lower
        assert set(tool_re.findall(obs_sec)) - {"record_observation", "take_note"} == set()

        added_obs = obs_sec.split("Sticky notes bridge two specific consecutive events.", 1)[1]
        assert added_obs.strip() != ""
        assert set(tool_re.findall(added_obs)) == set()

        for md_path in sorted(SKILLS_DIR.rglob("*.md")):
            text = md_path.read_text(encoding="utf-8")
            assert "32768" not in text, f"Hardcoded 32768 literal in {md_path.relative_to(SKILLS_DIR)}"
            assert "defers=0" not in text, f"Internal defers=0 syntax in {md_path.relative_to(SKILLS_DIR)}"

    def test_jarvis_incremental_inspection_and_passive_sticky_notes(self, loader):
        """T-12: Cross-source tool-map hygiene and section-scoped contracts for source/jarvis.md."""
        tool_re = self._TOOL_RE

        assert loader.get_tool_skills("post_sticky_note") == ["source/jarvis.md"]
        assert loader.get_tool_skills("wait_for_jarvis") == ["source/jarvis.md"]
        assert "source/jarvis.md" not in loader.get_tool_skills("inspect_event")
        assert "source/jarvis.md" not in loader.get_tool_skills("lookup_journal")
        assert '<skill id="source/jarvis.md" />' in loader.build_skill_refs(
            "inspect_event", event_source="jarvis"
        )
        assert '<skill id="source/jarvis.md" />' in loader.build_skill_refs(
            "lookup_journal", event_source="jarvis"
        )
        assert "source/jarvis.md" not in loader.build_skill_refs(
            "lookup_journal", event_source="headhunter"
        )

        jarvis_body = _skill(loader, "source/jarvis.md")
        proto_sec = _section(jarvis_body, "## Protocol")
        sticky_sec = _section(jarvis_body, "## Sticky Notes")

        proto_lower = proto_sec.lower()
        assert "ops journal" in proto_lower
        assert "incrementally" in proto_lower
        assert "prior diagnosis" in proto_lower

        sticky_lower = sticky_sec.lower()
        assert "passive" in sticky_lower
        assert "unscheduled stalled event" in sticky_lower
        assert "zero active deferrals" in sticky_lower

        assert set(tool_re.findall(jarvis_body)) - {"wait_for_jarvis", "hold_watch"} == set()
        proto_steps_1_to_4 = proto_sec.split("5. **Send your assessment to JARVIS.**", 1)[0]
        assert set(tool_re.findall(proto_steps_1_to_4)) == set()

        added_sticky = sticky_sec.split("that event.", 1)[1]
        assert added_sticky.strip() != ""
        assert set(tool_re.findall(added_sticky)) == set()


def _skill_text(*parts: str) -> str:
    return (SKILLS_DIR.joinpath(*parts)).read_text(encoding="utf-8")


def _md_section(text: str, heading: str) -> str:
    """Body of the markdown section whose heading line starts with ``heading`` (up to the next heading of any level)."""
    lines = text.splitlines()
    start = next((n for n, line in enumerate(lines) if line.startswith(heading)), None)
    assert start is not None, f"heading {heading!r} not found"
    end = next((n for n in range(start + 1, len(lines)) if lines[n].startswith("#")), len(lines))
    return "\n".join(lines[start + 1:end])


def _headings_outside_fences(text: str) -> list[tuple[int, str]]:
    out, fenced = [], False
    for n, line in enumerate(text.splitlines()):
        if line.lstrip().startswith("```"):
            fenced = not fenced
        elif not fenced and re.match(r"#{1,6} ", line):
            out.append((n, line))
    return out


class TestVmer2383NotificationPolicyAndSkillHardening:
    def test_notify_user_slack_schema_description_describes_capability_only(self):
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS

        schema = next(t for t in BRAIN_TOOL_SCHEMAS if t["name"] == "notify_user_slack")
        desc = schema["description"]
        assert "Slack DM" in desc
        assert desc.count("(") == desc.count(")"), f"unbalanced parentheses: {desc!r}"
        assert "Option B" not in desc
        assert not re.search(r"\bP[1-4]\b", desc), "priority policy belongs in brain_skills, not the tool schema"
        assert "report_incident" not in desc and "Nightwatcher" not in desc
        assert "pipeline failure notification, escalation" not in desc
        assert desc.rstrip().endswith(".")
        assert set(schema["input_schema"]["properties"]) >= {"user_email", "message"}

    def test_p1_chaotic_notification_policy_is_consistent_across_skills(self):
        rules = _md_section(_skill_text("always", "01-function-rules.md"), "## Notification Authority")
        bullet = next(line for line in rules.splitlines() if line.startswith("- Notifications (`notify_user_slack`)"))
        for token in ("P1", "CHAOTIC", "report_incident", "P2/P3/P4"):
            assert token in bullet, f"01-function-rules bullet missing {token}"

        close = _skill_text("close", "when-to-close.md")
        step = next(line for line in close.splitlines() if line.startswith("5. `notify_user_slack`"))
        assert "CHAOTIC" in step and "P1" in step and "skip" in step.lower()

        incident = _skill_text("escalate", "incident-tracking.md")
        body = _md_section(incident, "### Maintainer Notification (P1 and CHAOTIC Only)")
        for token in ("P1", "CHAOTIC", "notify_user_slack", "report_incident", "Nightwatcher", "P2", "P3/P4"):
            assert token in body, f"incident-tracking notification section missing {token}"
        assert "MUST ping the maintainers with `notify_user_slack`" in body
        # The contradictory legacy rule ("P1 or P2 -> MUST ping") must be gone everywhere.
        assert "Critical/Blocker (P1) or Major (P2), you MUST" not in incident
        assert "P1/P2 Incidents" not in incident

    def test_touched_notification_skill_headings_are_well_formed(self):
        for rel in (("escalate", "incident-tracking.md"), ("close", "when-to-close.md"),
                    ("always", "01-function-rules.md")):
            for n, heading in _headings_outside_fences(_skill_text(*rel)):
                assert len(heading) <= 80, f"{rel[-1]}:{n + 1} heading looks garbled: {heading!r}"
                assert heading.count("`") % 2 == 0, f"{rel[-1]}:{n + 1} unbalanced code span in heading"

    def test_mr_lifecycle_notifies_only_for_human_merge_block(self):
        text = _skill_text("dispatch", "mr-lifecycle.md")
        conflicts = _md_section(text, "## Bot MR Merge Conflicts")
        assert conflicts.strip()
        assert "notify maintainers via notify_user_slack" not in conflicts
        exception = text.split("**Exception — Agent-authored commits**:")[1].split("\n## ")[0]
        assert "`notify_user_slack`" in exception and "mandatory human merge" in exception
        assert "\n\n## Post-Approval Merge Dispatch" in text, "heading must be preceded by a blank line"

    def test_t17_phase_lifecycle_escalate_recovery_edges_and_tool_free_after_escalation(self):
        phase_lf = _skill_text("always", "09-phase-lifecycle.md")
        assert re.search(r'POST_ESC\s*-->\|"transient[^"]*work unexecuted"\|\s*DISPATCH', phase_lf)
        assert re.search(r'POST_ESC\s*-->\|"transient[^"]*verify pending"\|\s*VERIFY', phase_lf)

        after_esc = _md_section(phase_lf, "## After Escalation")
        assert after_esc.strip(), "After Escalation section must not be empty"
        tool_re = re.compile(r"\b(" + "|".join(re.escape(t) for t in _TOOL_NAMES) + r")\b")
        assert tool_re.findall(after_esc) == []

        actor_res = _skill_text("always", "12-actor-responses.md")
        bullet = next(line for line in actor_res.splitlines() if line.startswith("- **Stabilization wake**"))
        assert "[STABILIZATION WAKE]" in bullet and "agent.result" in bullet and "defer_wake" in bullet

    def test_t18_deep_memory_fixes_and_decision_routing(self):
        decision_routing = _skill_text("dispatch", "decision-routing.md")
        deep_memory_fixes = _skill_text("dispatch", "deep-memory-fixes.md")
        observations = _skill_text("always", "10-observations.md")

        assert "delta probes on follow-ups" in decision_routing
        assert decision_routing.rstrip().splitlines()[-1].startswith("**Follow-up checks:**")

        idx1 = decision_routing.find("sensor inputs for you to evaluate against")
        idx2 = decision_routing.find("approval gates")
        assert idx1 != -1 and idx2 != -1
        assert abs(idx1 - idx2) <= 160

        assert len(deep_memory_fixes.splitlines()) <= 100
        step3 = next(line for line in deep_memory_fixes.splitlines() if line.startswith("3. "))
        assert step3.count("`") % 2 == 0, f"unbalanced inline code span: {step3!r}"
        assert "`review_notes`" in step3 and '`take_note(category="cross-event")`' in step3
        assert "check review_notes before take_note" not in deep_memory_fixes

        review = _md_section(observations, "### Review Before Decisions")
        assert "`review_notes`" in review and "take_note" in review
        assert not observations.split("### Review Before Decisions")[1].startswith(
            "\nUse review_notes"
        ), "stray unformatted sentence under the heading"
        note_vs_other = _md_section(observations, "### Note vs Other Tools")
        tool_re = re.compile(r"\b(" + "|".join(re.escape(t) for t in _TOOL_NAMES) + r")\b")
        found_tools = set(tool_re.findall(note_vs_other))
        assert {"record_observation", "take_note"} <= found_tools
        assert found_tools <= {"record_observation", "take_note"}

    def test_touched_skill_headings_have_leading_blank_line(self):
        for rel in (("dispatch", "mr-lifecycle.md"), ("always", "10-observations.md"),
                    ("always", "12-actor-responses.md"), ("dispatch", "decision-routing.md")):
            lines = _skill_text(*rel).splitlines()
            for n, heading in _headings_outside_fences("\n".join(lines)):
                assert n == 0 or lines[n - 1].strip() in ("", "---"), f"{rel[-1]}:{n + 1} heading lacks a blank line before: {heading!r}"


class TestVmer2391CasualTriageWaitAndCloseReplyProbe:
    """T-8: Probe gate for VMER-2391 casual triage wait_for_user and close-reply alignment."""

    def test_casual_skill_omits_exit_triage_detour(self, loader):
        casual_body = _skill(loader, "domain/casual.md")
        assert "ExitTriage" not in casual_body
        assert "exit the initial observation phase" not in casual_body.lower()
        assert 'Greet["Read the room, respond conversationally"] --> Park["Park: wait for user"]' in casual_body

    def test_phase_lifecycle_close_constraint_reclassifies_casual_and_scopes_user_park(self, loader):
        sec = _section(_skill(loader, "always/09-phase-lifecycle.md"), "## Close Phase Constraint")
        sec_lower = sec.lower()
        assert "close immediately after your final message" not in sec_lower
        assert "for casual events" in sec_lower and "reclassify to clear" in sec_lower
        assert "for user-facing events (chat/slack), never emit a final reply as a standalone text-only turn before entering close" in sec_lower

    def test_when_to_close_closure_reason_turn_avoids_set_phase_and_keeps_gitlab_note(self, loader):
        sec = _section(_skill(loader, "close/when-to-close.md"), "## Closure Reason Turn")
        sec_lower = sec.lower()
        assert "set_phase" not in sec
        assert "emitted as text alongside entering the close phase or finalizing closure in the same processing cycle" in sec_lower
        assert "never send this final reply as a standalone text-only turn before entering close" in sec_lower
        assert "notify_gitlab_result" in sec

    def test_tool_schemas_align_close_and_wait_for_user_reply_timing(self):
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS

        schemas_by_name = {t["name"]: t for t in BRAIN_TOOL_SCHEMAS}
        set_phase_phase_desc = (
            schemas_by_name["set_phase"]["input_schema"]["properties"]["phase"]["description"]
        )
        assert "Enter ONLY after you have replied to the user" not in set_phase_phase_desc
        assert "Enter ONLY after you have replied to the user" not in schemas_by_name["set_phase"]["description"]
        assert "alongside" in set_phase_phase_desc
        assert "standalone text-only turn" in set_phase_phase_desc
        assert "emit your final user reply alongside set_phase(phase='close') or close_event" in set_phase_phase_desc

        close_desc = schemas_by_name["close_event"]["description"]
        assert "you MUST have sent a visible reply to the user before calling this" not in close_desc
        assert "either generated as text alongside this close_event call or emitted earlier in the current cycle alongside set_phase(phase='close')" in close_desc

        wait_desc = schemas_by_name["wait_for_user"]["description"]
        assert "BEFORE or alongside calling this tool" in wait_desc


class TestVmer2409KargoSystemicConsolidationAndTsGuardProbe:
    """T-VMER-2409: Probe gate for Kargo systemic consolidation and pre-failed pipeline Ts guard."""

    def test_flow_engineering_systemic_consolidation_fast_path(self):
        text = _skill_text("always", "08-flow-engineering.md")
        sec = _md_section(text, "### Cross-Service Systemic Blocker Fast-Path")
        assert 'step "auto-merge" timed out' in sec
        assert "leaf error" in sec.lower()
        assert "O(1)" in sec
        reclass_sec = _md_section(text, "### Transient → Systemic Reclassification")
        assert "on the same service" not in reclass_sec

    def test_deep_memory_fast_path_bypass_for_active_systemic_blockers(self):
        text = _skill_text("always", "04-deep-memory.md")
        sec = _md_section(text, "## Mandatory Consultation (TRIAGE phase)")
        assert "Exception — Active Systemic Blocker" in sec
        assert "systemic" in sec.lower() and "optional" in sec.lower()

    def test_incident_tracking_forbids_individual_staging_for_systemic_waves(self):
        text = _skill_text("escalate", "incident-tracking.md")
        flat = " ".join(text.split())
        assert (
            "Stage each incident individually via the normal escalation path -- the Nightwatcher daemon clusters related escalations during its sweep cycle"
            not in flat
        )
        sec = _md_section(text, "### Recurring Failures Across Events")
        assert "consolidated incident" in sec.lower()

    def test_incident_tracking_post_resolution_promotion_guard(self):
        text = _skill_text("escalate", "incident-tracking.md")
        sec = _md_section(text, "### Post-Escalation Behavior")
        assert "Post-Resolution Promotion Boundary Guard" in sec or "post-resolution" in sec.lower()
        assert "60 second" in sec or "60s" in sec or "60-second" in sec
        assert "creationTimestamp > incident.resolved_at" in sec
        assert "currentPromotion" in sec and "lastPromotion" in sec
        assert "verify recovery and transition to close" in sec.lower()
        assert "same leaf error signature" in sec.lower()

    def test_kargo_environment_inspects_current_promotion_before_last_promotion(self):
        text = _skill_text("gated", "kargo-environment.md")
        err_sec = _md_section(text, "## Error Natures")
        assert "Auto-Merge Timeout" in err_sec
        assert 'step "auto-merge" timed out' in err_sec
        concepts_sec = _md_section(text, "## Kargo Concepts")
        assert "currentPromotion" in concepts_sec and "lastPromotion" in concepts_sec
        idx_curr = concepts_sec.find("currentPromotion")
        idx_last = concepts_sec.find("lastPromotion")
        assert idx_curr != -1 and idx_last != -1
        assert "currentPromotion" in concepts_sec.split("lastPromotion")[0] or idx_curr < idx_last

    def test_complicated_ts_pre_failed_and_frozen_admission_guards(self):
        text = _skill_text("domain", "complicated.md")
        sec = _md_section(text, "## Ts Calibration Railway")
        assert "terminal failed state" in sec.lower() or "pre-failed" in sec.lower()
        assert "zero-deferral" in sec.lower() or "zero delay" in sec.lower() or "bypassing deferral" in sec.lower()
        assert "frozen" in sec.lower() or "suspended" in sec.lower()
        assert len(text.splitlines()) <= 100, f"domain/complicated.md exceeded modularity limit: {len(text.splitlines())} lines"

    def test_phase_lifecycle_post_esc_supports_verify_deferral(self):
        phase_lf = _skill_text("always", "09-phase-lifecycle.md")
        assert 'POST_ESC -->|"automated in-progress/queued: incident staged, await resolution"| VERIFY' in phase_lf
        assert 'POST_ESC -->|"automated terminal: incident staged"| CLOSE' in phase_lf
        assert 'POST_ESC -->|"need human input"| WAIT_HUMAN["request_user_approval"]' in phase_lf
        assert 'POST_ESC -->|"CHAOTIC stabilized"| RECLASS' in phase_lf
        assert re.search(r'POST_ESC\s*-->\|"transient[^"]*work unexecuted"\|\s*DISPATCH', phase_lf)
        assert re.search(r'POST_ESC\s*-->\|"transient[^"]*verify pending"\|\s*VERIFY', phase_lf)
        after_esc = _md_section(phase_lf, "## After Escalation")
        assert "re-enter verify to defer on the resolution timeline" in after_esc.lower()

    def test_phase_lifecycle_budget_exhaustion_direct_verify_evaluation(self):
        phase_lf = _skill_text("always", "09-phase-lifecycle.md")
        budget_sec = _md_section(phase_lf, "## Refresh Budget")
        assert "directly in verify" in budget_sec.lower() or "evaluate" in budget_sec.lower()
        assert "1 fallback measurement" in budget_sec.lower() or "maximum 1" in budget_sec.lower()

    def test_vmer_2409_touched_skills_tool_free_and_heading_hygiene(self):
        tool_re = re.compile(
            r"\b(" + "|".join(sorted(map(re.escape, _TOOL_NAMES), key=len, reverse=True)) + r")\b"
        )
        touched_files = [
            ("always", "08-flow-engineering.md"),
            ("always", "04-deep-memory.md"),
            ("escalate", "incident-tracking.md"),
            ("gated", "kargo-environment.md"),
            ("domain", "complicated.md"),
            ("always", "09-phase-lifecycle.md"),
            ("source", "aligner.md"),
        ]

        # 1. Heading formatting check for all 7 touched files
        for rel in touched_files:
            text = _skill_text(*rel)
            lines = text.splitlines()
            for n, heading in _headings_outside_fences(text):
                assert len(heading) <= 80, f"{rel[-1]}:{n + 1} heading > 80 chars: {heading!r}"
                assert heading.count("`") % 2 == 0, f"{rel[-1]}:{n + 1} unbalanced code ticks: {heading!r}"
                assert n == 0 or lines[n - 1].strip() in ("", "---"), (
                    f"{rel[-1]}:{n + 1} heading lacks leading blank line: {heading!r}"
                )

        # 2. Tool-free checks
        assert tool_re.findall(_strip_frontmatter(_skill_text("always", "08-flow-engineering.md"))) == []
        assert tool_re.findall(_strip_frontmatter(_skill_text("source", "aligner.md"))) == []

        sec_04 = _md_section(_skill_text("always", "04-deep-memory.md"), "## Mandatory Consultation (TRIAGE phase)")
        exc_04 = sec_04.split("Exception — Active Systemic Blocker")[-1]
        assert tool_re.findall(exc_04) == []

        sec_inc_recur = _md_section(_skill_text("escalate", "incident-tracking.md"), "### Recurring Failures Across Events")
        sec_inc_post = _md_section(_skill_text("escalate", "incident-tracking.md"), "### Post-Escalation Behavior")
        assert tool_re.findall(sec_inc_recur) == []
        assert tool_re.findall(sec_inc_post) == []

        sec_kargo_err = _md_section(_skill_text("gated", "kargo-environment.md"), "## Error Natures")
        sec_kargo_con = _md_section(_skill_text("gated", "kargo-environment.md"), "## Kargo Concepts")
        assert tool_re.findall(sec_kargo_err) == []
        assert tool_re.findall(sec_kargo_con) == []

        sec_comp = _md_section(_skill_text("domain", "complicated.md"), "## Ts Calibration Railway")
        assert tool_re.findall(sec_comp) == []

        sec_lf_esc = _md_section(_skill_text("always", "09-phase-lifecycle.md"), "## After Escalation")
        sec_lf_bud = _md_section(_skill_text("always", "09-phase-lifecycle.md"), "## Refresh Budget")
        assert tool_re.findall(sec_lf_esc) == []
        assert tool_re.findall(sec_lf_bud) == []

        # 3. Source reference contracts
        aligner_text = _skill_text("source", "aligner.md")
        assert "always/08-flow-engineering.md" in aligner_text
        assert "gated/kargo-environment.md" in aligner_text
