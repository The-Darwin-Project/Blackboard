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
from pathlib import Path

import pytest

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
