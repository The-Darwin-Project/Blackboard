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

    def test_when_to_close_closure_reason_turn_avoids_set_phase_and_omits_notify_gitlab_result(self, loader):
        sec = _section(_skill(loader, "close/when-to-close.md"), "## Closure Reason Turn")
        sec_lower = sec.lower()
        assert "set_phase" not in sec
        assert "emitted as text alongside entering the close phase or finalizing closure in the same processing cycle" in sec_lower
        assert "never send this final reply as a standalone text-only turn before entering close" in sec_lower
        assert "notify_gitlab_result" not in sec

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
    """T-VMER-2409: Probe gate for cross-service systemic waves, the post-resolution promotion guard,
    escalation resume precedence, and the pre-failed pipeline Ts guard.

    Every test pairs an assertion on newly authored content with the invariants it must preserve, so
    none of them can pass against a skill set that lacks the VMER-2409 remediation.
    """

    _TIMING_RE = re.compile(r"\b\d+\s*(?:-\s*)?(?:seconds?|secs?|minutes?|mins?|s)\b", re.IGNORECASE)
    _TOOL_RE = re.compile(
        r"\b(" + "|".join(sorted(map(re.escape, _TOOL_NAMES), key=len, reverse=True)) + r")\b"
    )

    @classmethod
    def _assert_no_hardcoded_timing(cls, label: str, text: str) -> None:
        assert cls._TIMING_RE.findall(text) == [], f"{label} embeds a hardcoded duration"

    def test_flow_engineering_wave_requires_verified_cause_and_separates_staging(self, loader):
        body = _skill(loader, "always/08-flow-engineering.md")
        sec = _section(body, "### Cross-Service Systemic Wave")
        low = sec.lower()
        assert "untrusted" in low
        assert "matching text alone does not qualify a wave" in low
        assert "same failing step or component" in low and "same upstream dependency" in low
        assert "invisible to the incident tracker search" in low
        assert "nightwatcher owns cross-event clustering" in low
        assert "skip redundant investigation dispatches" in low
        assert "re-check live resource state" in low
        assert "stall detection ceiling" in low and "escalate rather than waiting indefinitely" in low
        assert "per-event escalation evidence" in low
        # The non-existent canonical title convention and the Kargo/HTTP literals are gone.
        assert "Cross-Service Systemic Blocker Fast-Path" not in body
        for gone in ("[Systemic]", "canonical title", "converge on", 'step "auto-merge"', "502"):
            assert gone not in body, f"08-flow-engineering.md still contains {gone!r}"
        assert self._TOOL_RE.findall(_strip_frontmatter(body)) == []
        self._assert_no_hardcoded_timing("08-flow-engineering wave section", sec)

    def test_reclassification_keeps_service_scope_and_defers_cross_service_to_verified_cause(self, loader):
        sec = _section(_skill(loader, "always/08-flow-engineering.md"), "### Transient → Systemic Reclassification")
        assert "on the same service within one event" in sec
        assert "concurrent events on the same service" in sec
        assert "verified-cause qualification in Cross-Service Systemic Wave" in sec

    def test_deep_memory_stays_mandatory_for_tracked_systemic_incidents(self, loader):
        sec = _section(_skill(loader, "always/04-deep-memory.md"), "## Mandatory Consultation (TRIAGE phase)")
        low = sec.lower()
        assert "deep memory consultation is mandatory during triage" in low
        assert "consultation stays mandatory" in low
        assert "stall detection ceiling" in low
        assert "redundant agent investigation" in low
        assert "optional" not in low
        assert self._TOOL_RE.findall(sec) == []

    def test_incident_tracking_wave_staging_matches_nightwatcher_design(self, loader):
        body = _skill(loader, "escalate/incident-tracking.md")
        sec = _section(body, "### Recurring Failures Across Events")
        assert "`search_open_incidents` queries Jira only" in sec
        assert "invisible to it" in sec
        assert "[evt-XXXXXXX]" in sec
        assert "Nightwatcher clusters the wave on its sweep" in sec
        assert "component, failing step, and error signature" in sec
        for gone in ("[Systemic]", "single consolidated incident", "converge on", "Fast-Path"):
            assert gone not in body, f"incident-tracking.md still contains {gone!r}"
        assert "Cross-Service Systemic Wave" in sec

    def test_incident_tracking_per_event_dedup_alerts_via_notification_not_second_report(self, loader):
        body = _skill(loader, "escalate/incident-tracking.md")
        sec = _section(body, "### Post-Escalation Behavior")
        assert "`report_incident` deduplicates per event" in sec
        assert "skipped as a duplicate" in sec
        assert "`notify_user_slack`" in sec and "`comment_jira_issue`" in sec
        assert "observer opens a clean event" in sec
        assert not re.search(r"re-?escalat", sec, re.IGNORECASE)
        # The generic principle stays here; Kargo specifics live in the gated skill.
        guard_free = sec.lower()
        for gone in ("currentpromotion", "lastpromotion", "resolved_at", "creationtimestamp"):
            assert gone not in guard_free, f"incident-tracking.md still pins {gone!r}"
        assert "Post-resolution verification" in sec
        self._assert_no_hardcoded_timing("incident-tracking post-escalation section", sec)

    def test_kargo_environment_owns_fail_closed_post_resolution_guard(self, loader):
        body = _skill(loader, "gated/kargo-environment.md")
        sec = _section(body, "## Post-Resolution Promotion Guard")
        low = sec.lower()
        assert "compare the reported promotion name, phase, failed step, and message" in low
        assert "a newer promotion succeeded" in low and "close" in low
        assert "per-event duplicate" in low and "incident-tracking.md" in sec
        assert "controller-reconcile interval" in low and "observations and deep memory" in low
        assert "fail closed" in low
        assert "closing is reserved for confirmed recovery" in low
        for gone in ("resolved_at", "creationTimestamp", "currentPromotion", "lastPromotion", "health"):
            assert gone not in body, f"kargo-environment.md still pins unobservable {gone!r}"
        self._assert_no_hardcoded_timing("kargo post-resolution guard", sec)

    def test_kargo_environment_has_single_auto_merge_timeout_subsection(self, loader):
        body = _skill(loader, "gated/kargo-environment.md")
        assert body.count('step "auto-merge" timed out') == 1
        sec = _section(body, "### Auto-Merge Timeout")
        assert "Cross-Service Systemic Wave" in sec
        assert "Auto-merge timeout" not in body
        concepts = _section(body, "## Kargo Concepts")
        assert "compare the reported promotion name" in concepts.lower()

    def test_post_resolution_guard_reachable_in_verify_phase(self, loader):
        import inspect
        from src.agents.brain import BRAIN_PHASE_SKILLS, Brain

        # Verify does not load the escalate folder, so the guard must live in the gated Kargo skill.
        assert "escalate" not in BRAIN_PHASE_SKILLS["verify"]
        ctx = {
            "turn_count": 3, "source": "aligner", "service": "svc", "is_waiting": False,
            "has_agent_result": True, "last_is_user": False, "has_related": False,
            "has_recent_closed": False, "has_graph_edges": False, "has_aligner_turns": False,
            "brain_has_classified": True, "event_domain": "complicated",
            "domain_confidence": "default", "has_slack_participant": False,
            "is_intermediate": False, "has_pending_huddle": False,
        }
        from unittest.mock import MagicMock
        event = MagicMock()
        event.brain_phase = "verify"
        active = Brain._match_phases(None, event, ctx)
        assert "escalate" not in active
        # Kargo evidence injects every skill tagged kargo, independent of the declared phase.
        kargo_paths = loader.find_paths_by_tag("kargo")
        assert "gated/kargo-environment.md" in kargo_paths
        injected = "\n".join(_skill(loader, p) for p in kargo_paths)
        assert "## Post-Resolution Promotion Guard" in injected
        from types import SimpleNamespace
        from src.agents.brain import _build_turn0_anchor
        from src.models import EventDocument, EventEvidence, EventInput

        src = inspect.getsource(_build_turn0_anchor)
        call = src.index('_safe_loader_tag_paths(loader, "kargo")')
        gate = src[max(0, call - 400):call]
        assert "kargo_context" in gate and "brain_phase" not in gate

        verify_event = EventDocument(
            id="evt-kargo-verify",
            source="aligner",
            service="svc",
            brain_phase="verify",
            event=EventInput(
                reason="Kargo promotion failed",
                evidence=EventEvidence(
                    display_text="Stage prod failed",
                    source_type="aligner",
                    domain="complicated",
                    severity="warning",
                    kargo_context={
                        "stage": "prod",
                        "project": "demo",
                        "promotion": "promo-1",
                        "phase": "Errored",
                    },
                ),
            ),
            conversation=[],
        )
        anchor = _build_turn0_anchor(SimpleNamespace(_skill_loader=loader), verify_event)
        assert "gated/kargo-environment.md" in anchor.initial_paths
        assert "## Post-Resolution Promotion Guard" in anchor.text

    def test_phase_lifecycle_escalation_resume_precedence_and_edges(self, loader):
        phase_lf = _skill(loader, "always/09-phase-lifecycle.md")
        edges = re.findall(r'POST_ESC\s*-->\|"([^"]*)"\|\s*(\w+)', phase_lf)
        targets = [t for _, t in edges]
        assert targets.count("VERIFY") == 1, edges
        assert targets.count("CLOSE") == 1, edges
        labels = dict((t, label) for label, t in edges)
        assert "non-terminal" in labels["VERIFY"] and "verify pending" in labels["VERIFY"]
        assert "terminal failure" in labels["CLOSE"]
        assert {"WAIT_HUMAN", "RECLASS", "DISPATCH"} <= set(targets)
        after = _section(phase_lf, "## After Escalation")
        low = after.lower()
        assert "failure terminal: advance directly to close" in low
        assert "work still non-terminal or quota recovery pending: enter verify" in low
        assert "transition to verify first so the live state is refreshed" in low
        assert "same precedence" in low
        self._assert_no_hardcoded_timing("09-phase-lifecycle After Escalation", after)
        assert self._TOOL_RE.findall(after) == []

    def test_phase_lifecycle_budget_fallback_uses_control_loop_principle_not_literals(self, loader):
        sec = _section(_skill(loader, "always/09-phase-lifecycle.md"), "## Refresh Budget")
        low = sec.lower()
        assert "a second measurement dispatch on the same wake adds no information" in low
        assert "honor the stall detection ceiling" in low
        assert "maximum 1" not in low and "fallback measurement dispatch per" not in low
        # The budget section legitimately states the token count and cap; only duration literals are barred.
        self._assert_no_hardcoded_timing("09-phase-lifecycle Refresh Budget", sec)
        assert self._TOOL_RE.findall(sec) == []

    def test_complicated_ts_guards_use_observable_fields_and_keep_gates(self, loader):
        text = _skill(loader, "domain/complicated.md")
        sec = _section(text, "## Ts Calibration Railway")
        assert "`pipeline_status` already reports a terminal failed state" in sec
        assert "head_pipeline" not in text
        assert "skip the initial blind pipeline-completion deferral" in sec
        assert "§ Temporal Drift Check" in sec and "§ Terminal Failure Gate" in sec
        assert "`kueue_pending_count`" in sec and "`pipeline_queue_depth`" in sec
        assert "congestion and drain baselines in deep memory" in sec
        assert "<severity_modulation>\n\n|" in text and "|\n\n</severity_modulation>" in text
        assert len(text.splitlines()) <= 100, f"domain/complicated.md exceeded modularity limit: {len(text.splitlines())} lines"
        assert self._TOOL_RE.findall(sec) == []

    def test_aligner_points_only_to_always_loaded_wave_guidance(self, loader):
        text = _skill(loader, "source/aligner.md")
        assert "`always/08-flow-engineering.md` § Cross-Service Systemic Wave" in text
        assert "gated/kargo-environment.md" not in text
        assert self._TOOL_RE.findall(_strip_frontmatter(text)) == []
        assert "Cross-Service Systemic Wave" in _skill(loader, "always/08-flow-engineering.md")

    def test_touched_skill_headings_are_well_formed(self, loader):
        touched = [
            "always/08-flow-engineering.md", "always/04-deep-memory.md", "escalate/incident-tracking.md",
            "gated/kargo-environment.md", "domain/complicated.md", "always/09-phase-lifecycle.md",
            "source/aligner.md",
        ]
        # Anchor on newly authored headings so a skill set without the remediation fails.
        assert "### Cross-Service Systemic Wave" in _skill(loader, "always/08-flow-engineering.md")
        assert "## Post-Resolution Promotion Guard" in _skill(loader, "gated/kargo-environment.md")
        for rel in touched:
            text = _skill(loader, rel)
            lines = text.splitlines()
            for n, heading in _headings_outside_fences(text):
                assert len(heading) <= 80, f"{rel}:{n + 1} heading > 80 chars: {heading!r}"
                assert heading.count("`") % 2 == 0, f"{rel}:{n + 1} unbalanced code ticks: {heading!r}"
                assert n == 0 or lines[n - 1].strip() in ("", "---"), (
                    f"{rel}:{n + 1} heading lacks leading blank line: {heading!r}"
                )


class TestATDDT12VcsSkillTagRouting:
    """Layer 1-4 ATDD probes (T-12) against real on-disk src/agents/brain_skills/."""

    def test_github_tag_routes_only_to_github_environment_not_headhunter_or_issue(self, loader):
        """Given real brain_skills/ frontmatter
        When loader.find_paths_by_tag('github') runs
        Then gated/github-environment.md is included and source/headhunter.md +
        source/headhunter_github_issue.md are NOT leaked into PR events."""
        gh_paths = loader.find_paths_by_tag("github")
        assert "gated/github-environment.md" in gh_paths
        assert "source/headhunter.md" not in gh_paths
        assert "source/headhunter_github_issue.md" not in gh_paths

    def test_gitlab_tag_routes_to_gitlab_environment_not_headhunter(self, loader):
        """When loader.find_paths_by_tag('gitlab') runs
        Then context/gitlab-environment.md is included and source/headhunter.md is excluded."""
        gl_paths = loader.find_paths_by_tag("gitlab")
        assert "context/gitlab-environment.md" in gl_paths
        assert "source/headhunter.md" not in gl_paths

    def test_headhunter_source_skill_does_not_require_gitlab_environment(self, loader):
        """source/headhunter.md must not unconditionally require context/gitlab-environment.md
        so GitHub PR events are not polluted with GitLab rules."""
        result = loader.get_with_meta("source/headhunter.md")
        assert result is not None
        _, meta = result
        assert "context/gitlab-environment.md" not in (meta.get("requires") or [])

    def test_headhunter_github_issue_skill_uses_github_issue_tag(self, loader):
        result = loader.get_with_meta("source/headhunter_github_issue.md")
        assert result is not None
        _, meta = result
        tags = meta.get("tags") or []
        assert "github_issue" in tags
        assert "github" not in tags

    def test_flow_engineering_includes_refresh_github_context_tool(self, loader):
        """always/08-flow-engineering.md declares refresh_github_context in tools:."""
        result = loader.get_with_meta("always/08-flow-engineering.md")
        assert result is not None
        _, meta = result
        assert "refresh_github_context" in (meta.get("tools") or [])
        assert "always/08-flow-engineering.md" in loader.get_tool_skills("refresh_github_context")


class TestATDDVmer2450ThinkingLevelAndSkillCleanup:
    """VMER-2450 Step 6 ATDD (T-18, T-19, T-20): 2-bucket thinking_level pinning,
    dead template_vars / wait-protocol cleanup, and kargo tag deduplication."""

    @staticmethod
    def _llm_params_stub(loader):
        from types import SimpleNamespace
        from src.agents.brain import Brain

        stub = SimpleNamespace(
            _skill_loader=loader,
            temperature=1.0,
            max_output_tokens=65536,
            provider="gemini",
            model_name="gemini-4-neon",
            _clamp_casual_thinking=Brain._clamp_casual_thinking,
        )
        stub._clamp_model_max_tokens = Brain._clamp_model_max_tokens.__get__(stub, SimpleNamespace)
        stub._resolve_llm_params = Brain._resolve_llm_params.__get__(stub, SimpleNamespace)
        return stub

    def test_t18_all_12_phase_yamls_pin_thinking_level_high_and_65536_tokens(self, loader):
        """T-18: All 12 src/agents/brain_skills/*/_phase.yaml files declare
        thinking_level == 'high' and max_output_tokens == 65536, and Brain._resolve_llm_params
        resolves 'high' for every operational phase."""
        phase_yamls = sorted(SKILLS_DIR.glob("*/_phase.yaml"))
        assert len(phase_yamls) == 12

        stub = self._llm_params_stub(loader)
        for yaml_path in phase_yamls:
            phase = yaml_path.parent.name
            meta = loader.get_phase_meta(phase)
            assert meta is not None, f"Missing phase metadata for {phase}"
            assert meta.get("thinking_level") == "high", (
                f"{phase}/_phase.yaml expected thinking_level='high', got {meta.get('thinking_level')!r}"
            )
            assert meta.get("max_output_tokens") == 65536, (
                f"{phase}/_phase.yaml expected max_output_tokens=65536, got {meta.get('max_output_tokens')!r}"
            )
            thinking, _, tokens = stub._resolve_llm_params(["always", phase], domain="complicated")
            assert thinking == "high", f"Operational phase {phase} resolved thinking_level={thinking!r}"
            assert tokens == 65536

    @pytest.mark.parametrize("domain", ["CASUAL", "casual", " casual "])
    @pytest.mark.parametrize("phases", [["always"], ["always", "close"], ["always", "waiting"], ["always", "coordination"]])
    def test_t19_casual_domain_resolves_thinking_level_low(self, loader, domain, phases):
        """T-19: CASUAL domain clamps thinking_level to 'low' via _resolve_llm_params / _clamp_casual_thinking."""
        from src.agents.brain import Brain

        stub = self._llm_params_stub(loader)
        thinking, _, _ = stub._resolve_llm_params(phases, domain=domain)
        assert thinking == "low"
        assert Brain._clamp_casual_thinking("high", domain) == "low"

    def test_t20_wait_protocol_has_no_mustache_template_and_references_event_state(self, loader):
        """T-20: waiting/wait-protocol.md removes dead {{maintainer_emails}} literal and references <event_state>."""
        raw_text = _skill_text("waiting", "wait-protocol.md")
        body = _skill(loader, "waiting/wait-protocol.md")
        assert "{{maintainer_emails}}" not in raw_text
        assert "{{" not in raw_text, "Dead mustache template literal still present in waiting/wait-protocol.md"
        assert "{{" not in body
        assert "<event_state>" in raw_text

    def test_t20_kargo_tag_deduped_exclusively_to_gated_kargo_environment(self, loader):
        """T-20: find_paths_by_tag('kargo') returns ONLY ['gated/kargo-environment.md']
        (duplicate kargo tag removed from always/11-subject-semantics.md)."""
        assert loader.find_paths_by_tag("kargo") == ["gated/kargo-environment.md"]

        subj = loader.get_with_meta("always/11-subject-semantics.md")
        assert subj is not None
        body, meta = subj
        assert "kargo" not in (meta.get("tags") or [])
        assert "ci_gating" in body

    def test_t20_brain_build_system_prompt_has_no_dead_template_vars(self):
        """T-20: src/agents/brain.py removes dead template_vars dict construction in _build_system_prompt."""
        import inspect
        from src.agents.brain import Brain

        src = inspect.getsource(Brain._build_system_prompt)
        assert "template_vars" not in src, (
            "Dead template_vars construction still present in Brain._build_system_prompt"
        )



class TestPhase4AMultiOptionApprovals:
    """Phase 4A: VMER-2501 Multi-option approvals skill probes (T-14)."""

    def test_wait_protocol_phrasing(self, loader):
        raw_text = _skill_text("waiting", "wait-protocol.md")
        body = _skill(loader, "waiting/wait-protocol.md")
        assert "approval buttons" not in body.lower()
        assert "decision card" in body.lower() or "structured option" in body.lower() or "multi-option" in body.lower()
        assert "<event_state>" in raw_text
        assert "{{" not in raw_text

    @pytest.mark.parametrize("skill_path", [
        "always/12-actor-responses.md",
        "dispatch/mr-lifecycle.md",
        "dispatch/execution-method.md",
        "post-agent/plan-activation.md",
        "dispatch/deep-memory-fixes.md",
        "source/_user-conversational.md",
        "always/00-identity.md"
    ])
    def test_structured_option_semantics(self, loader, skill_path):
        body = _skill(loader, skill_path)
        body_lower = body.lower()
        assert "effect" in body_lower or "write_in" in body_lower or "write-in" in body_lower or "steer" in body_lower

    def test_line_caps(self):
        raw_00 = _skill_text("always", "00-identity.md")
        raw_deep = _skill_text("dispatch", "deep-memory-fixes.md")
        assert len(raw_00.splitlines()) <= 100
        assert len(raw_deep.splitlines()) <= 100
