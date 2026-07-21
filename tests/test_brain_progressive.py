# BlackBoard/tests/test_brain_progressive.py
# @ai-rules:
# 1. [Constraint]: Tests Brain static/class methods only -- no Redis, no async, no adapter.
# 2. [Pattern]: Uses minimal ConversationTurn/EventDocument stubs for isolation.
"""Unit tests for Brain progressive skill methods: recommendation extraction, phase matching."""
from __future__ import annotations

import pytest

from src.agents.brain import Brain, BRAIN_PHASE_SKILLS


class TestExtractRecommendation:
    def test_header_match_h2(self):
        text = "Some analysis here.\n\n## Recommendation\nScale to 3 replicas via GitOps."
        result = Brain._extract_recommendation(text)
        assert result is not None
        assert "Scale to 3 replicas" in result

    def test_header_match_h3_next_step(self):
        text = "Findings.\n\n### Next Step\nRerun the pipeline with --no-cache flag."
        result = Brain._extract_recommendation(text)
        assert result is not None
        assert "Rerun the pipeline" in result

    def test_bold_match(self):
        text = "Investigation complete.\n\n**Recommendation**: Merge MR !42 and deploy."
        result = Brain._extract_recommendation(text)
        assert result is not None
        assert "Merge MR !42" in result

    def test_fallback_last_paragraph(self):
        text = "First paragraph with analysis.\n\nSecond paragraph.\n\nThe service should be scaled down to 1 replica."
        result = Brain._extract_recommendation(text)
        assert result is not None
        assert "scaled down to 1 replica" in result

    def test_empty_text_returns_none(self):
        assert Brain._extract_recommendation("") is None

    def test_no_length_cap(self):
        # Input text is already bounded upstream by AGENT_RESULT_MAX_CHARS at
        # write time -- _extract_recommendation must not re-truncate it.
        long_rec = "## Recommendation\n" + "x" * 2000
        result = Brain._extract_recommendation(long_rec)
        assert result is not None
        assert len(result) == 2000


class TestMatchPhases:
    @staticmethod
    def _make_ctx(**overrides) -> dict:
        defaults = {
            "turn_count": 0,
            "source": "chat",
            "service": "test-svc",
            "is_waiting": False,
            "has_agent_result": False,
            "last_is_user": False,
            "has_related": False,
            "has_recent_closed": False,
            "has_graph_edges": False,
            "has_aligner_turns": False,
            "brain_has_classified": False,
            "event_domain": "complicated",
            "domain_confidence": "default",
            "has_slack_participant": False,
            "is_intermediate": False,
            "has_pending_huddle": False,
        }
        defaults.update(overrides)
        return defaults

    @staticmethod
    def _make_event_stub(brain_phase=None):
        from unittest.mock import MagicMock
        event = MagicMock()
        event.brain_phase = brain_phase
        return event

    def test_triage_default_loads_always_source(self):
        ctx = self._make_ctx()
        event = self._make_event_stub(brain_phase=None)
        active = Brain._match_phases(None, event, ctx)
        assert "always" in active
        assert "source" in active
        assert "dispatch" not in active

    def test_dispatch_loads_dispatch_and_coordination(self):
        ctx = self._make_ctx()
        event = self._make_event_stub(brain_phase="dispatch")
        active = Brain._match_phases(None, event, ctx)
        assert "dispatch" in active
        assert "coordination" in active
        assert "post-agent" not in active

    def test_legacy_investigate_alias_resolves_to_dispatch(self):
        ctx = self._make_ctx()
        event = self._make_event_stub(brain_phase="investigate")
        active = Brain._match_phases(None, event, ctx)
        assert "dispatch" in active
        assert "coordination" in active

    def test_legacy_execute_alias_resolves_to_dispatch(self):
        ctx = self._make_ctx()
        event = self._make_event_stub(brain_phase="execute")
        active = Brain._match_phases(None, event, ctx)
        assert "dispatch" in active
        assert "coordination" in active

    def test_verify_loads_post_agent_and_defer_wake(self):
        ctx = self._make_ctx()
        event = self._make_event_stub(brain_phase="verify")
        active = Brain._match_phases(None, event, ctx)
        assert "post-agent" in active
        assert "defer-wake" in active
        assert "dispatch" not in active

    def test_escalate_loads_post_agent(self):
        ctx = self._make_ctx()
        event = self._make_event_stub(brain_phase="escalate")
        active = Brain._match_phases(None, event, ctx)
        assert "post-agent" in active
        assert "dispatch" not in active

    def test_intermediate_preempts_brain_phase(self):
        ctx = self._make_ctx(is_intermediate=True)
        event = self._make_event_stub(brain_phase="dispatch")
        active = Brain._match_phases(None, event, ctx)
        assert "intermediate" in active
        assert "dispatch" not in active
        assert "post-agent" not in active

    def test_waiting_preempts_brain_phase(self):
        ctx = self._make_ctx(is_waiting=True)
        event = self._make_event_stub(brain_phase="verify")
        active = Brain._match_phases(None, event, ctx)
        assert "waiting" in active
        assert "always" in active
        assert "source" in active
        assert "post-agent" not in active
        assert "dispatch" not in active

    def test_context_phase_activates_on_related(self):
        ctx = self._make_ctx(has_related=True)
        event = self._make_event_stub(brain_phase="triage")
        active = Brain._match_phases(None, event, ctx)
        assert "context" in active

    def test_context_phase_inactive_when_no_context(self):
        ctx = self._make_ctx()
        event = self._make_event_stub(brain_phase="triage")
        active = Brain._match_phases(None, event, ctx)
        assert "context" not in active

    def test_in_flight_migration_loads_verify_skills(self):
        ctx = self._make_ctx(has_agent_result=True)
        event = self._make_event_stub(brain_phase=None)
        active = Brain._match_phases(None, event, ctx)
        assert "post-agent" in active
        assert "defer-wake" in active

    def test_brain_phase_skills_mapping_complete(self):
        expected_phases = {"triage", "dispatch", "verify", "escalate", "close"}
        assert set(BRAIN_PHASE_SKILLS.keys()) == expected_phases

    def test_intermediate_with_huddle_includes_coordination(self):
        ctx = self._make_ctx(is_intermediate=True, has_pending_huddle=True)
        event = self._make_event_stub(brain_phase="dispatch")
        active = Brain._match_phases(None, event, ctx)
        assert "intermediate" in active
        assert "coordination" in active
        assert "dispatch" not in active


class TestActionLanguageGate:
    """Validate _ACTION_PATTERN gate for post-agent recall."""

    def test_escalation_triggers_gate(self):
        from src.agents.brain import _ACTION_PATTERN
        assert _ACTION_PATTERN.search("Hard stall. Escalation recommended.")

    def test_failure_triggers_gate(self):
        from src.agents.brain import _ACTION_PATTERN
        assert _ACTION_PATTERN.search("Pipeline failed with exit code 1.")

    def test_timeout_triggers_gate(self):
        from src.agents.brain import _ACTION_PATTERN
        assert _ACTION_PATTERN.search("Exceeded 2-hour timeout threshold.")

    def test_close_triggers_gate(self):
        from src.agents.brain import _ACTION_PATTERN
        assert _ACTION_PATTERN.search("Recommend closing the MR.")

    def test_oom_triggers_gate(self):
        from src.agents.brain import _ACTION_PATTERN
        assert _ACTION_PATTERN.search("Pod OOMKilled during build.")

    def test_routine_success_blocked(self):
        from src.agents.brain import _ACTION_PATTERN
        assert not _ACTION_PATTERN.search("Pipeline passed. MR ready to merge. No issues found.")

    def test_merged_blocked(self):
        from src.agents.brain import _ACTION_PATTERN
        assert not _ACTION_PATTERN.search("MR merged successfully after pipeline completion.")

    def test_no_issues_blocked(self):
        from src.agents.brain import _ACTION_PATTERN
        assert not _ACTION_PATTERN.search("All checks green. Branch is clean. Ready for merge.")


class TestQueryExtractionPriority:
    """Validate assessment > reasoning > legacy extraction priority."""

    def test_assessment_preferred_over_reasoning(self):
        taskForAgent = {"assessment": "Pipeline stalled in Kueue", "reasoning": "root cause"}
        query = taskForAgent.get("assessment", "") or taskForAgent.get("reasoning", "")
        assert query == "Pipeline stalled in Kueue"

    def test_reasoning_fallback_when_no_assessment(self):
        taskForAgent = {"reasoning": "PaC controller not processing"}
        query = taskForAgent.get("assessment", "") or taskForAgent.get("reasoning", "")
        assert query == "PaC controller not processing"

    def test_legacy_extraction_when_no_frontmatter(self):
        text = "Analysis done.\n\n## Recommendation\nScale to 3 replicas."
        rec = Brain._extract_recommendation(text)
        assert rec is not None
        assert "Scale to 3 replicas" in rec


class TestParsePlanFrontmatter:
    def test_with_reasoning_and_steps(self):
        raw = '---\nreasoning: "PaC issue"\nsteps:\n  - id: "1"\n    agent: sysadmin\n    summary: Check controller\n---\nBody text.'
        body, steps, fm = Brain._parse_plan_frontmatter(raw)
        assert body == "Body text."
        assert steps is not None
        assert len(steps) == 1
        assert fm.get("reasoning") == "PaC issue"

    def test_reasoning_only_no_steps(self):
        raw = '---\nreasoning: "Pipeline passed, MR merged"\n---\nAll good.'
        body, steps, fm = Brain._parse_plan_frontmatter(raw)
        assert body == "All good."
        assert steps is None
        assert fm.get("reasoning") == "Pipeline passed, MR merged"

    def test_no_frontmatter(self):
        raw = "Just a plain result with no frontmatter."
        body, steps, fm = Brain._parse_plan_frontmatter(raw)
        assert body is None
        assert steps is None
        assert fm == {}

    def test_malformed_yaml(self):
        raw = "---\n: bad yaml [[\n---\nBody."
        body, steps, fm = Brain._parse_plan_frontmatter(raw)
        assert body == "Body."
        assert steps is None
        assert fm == {}

    def test_leading_whitespace(self):
        raw = '\n  ---\nreasoning: "with leading spaces"\nsteps:\n  - id: "1"\n    agent: developer\n    summary: Fix it\n---\nBody.'
        body, steps, fm = Brain._parse_plan_frontmatter(raw)
        assert body == "Body."
        assert steps is not None
        assert fm.get("reasoning") == "with leading spaces"

    def test_empty_string(self):
        body, steps, fm = Brain._parse_plan_frontmatter("")
        assert body is None
        assert steps is None
        assert fm == {}

    def test_non_string_reasoning(self):
        raw = '---\nreasoning: 42\n---\nBody.'
        body, steps, fm = Brain._parse_plan_frontmatter(raw)
        assert fm.get("reasoning") == 42
        assert body == "Body."


class TestResolvePhase:
    """Unit tests for _resolve_phase normalization."""

    def test_investigate_resolves_to_dispatch(self):
        from src.models import _resolve_phase
        assert _resolve_phase("investigate") == "dispatch"

    def test_execute_resolves_to_dispatch(self):
        from src.models import _resolve_phase
        assert _resolve_phase("execute") == "dispatch"

    def test_canonical_phases_pass_through(self):
        from src.models import _resolve_phase
        for phase in ("triage", "dispatch", "verify", "escalate", "close"):
            assert _resolve_phase(phase) == phase

    def test_none_defaults_to_triage(self):
        from src.models import _resolve_phase
        assert _resolve_phase(None) == "triage"

    def test_unknown_value_defaults_to_triage(self):
        from src.models import _resolve_phase
        assert _resolve_phase("garbage") == "triage"
        assert _resolve_phase("TRIAGE") == "triage"
        assert _resolve_phase("escalate ") == "triage"

    def test_field_validator_normalizes_investigate(self):
        from src.models import EventDocument
        assert EventDocument._normalize_phase("investigate") == "dispatch"

    def test_field_validator_normalizes_execute(self):
        from src.models import EventDocument
        assert EventDocument._normalize_phase("execute") == "dispatch"

    def test_field_validator_preserves_none(self):
        from src.models import EventDocument
        assert EventDocument._normalize_phase(None) is None

    def test_field_validator_passes_canonical(self):
        from src.models import EventDocument
        assert EventDocument._normalize_phase("dispatch") == "dispatch"
        assert EventDocument._normalize_phase("triage") == "triage"


class TestRefreshBudget:
    """Tests for the conversation-turn-based refresh budget."""

    def _make_turn(self, actor="brain", action="phase", waiting_for=None):
        from src.models import ConversationTurn
        return ConversationTurn(
            turn=1, actor=actor, action=action,
            waitingFor=waiting_for,
        )

    def _compute_budget(self, turns):
        refresh_tools_budgeted = {"refresh_gitlab_context", "refresh_kargo_context"}
        refresh_count = sum(
            1 for t in turns
            if t.actor == "brain" and t.waitingFor in refresh_tools_budgeted
        )
        agent_completions = sum(
            1 for t in turns
            if t.actor not in ("brain", "user", "aligner", "headhunter", "jarvis")
            and t.action in ("execute", "plan")
        )
        return min(3 + agent_completions, 10) - refresh_count

    def test_new_event_has_budget_3(self):
        assert self._compute_budget([]) == 3

    def test_three_refreshes_exhausts_budget(self):
        turns = [
            self._make_turn(waiting_for="refresh_gitlab_context"),
            self._make_turn(waiting_for="refresh_kargo_context"),
            self._make_turn(waiting_for="refresh_gitlab_context"),
        ]
        assert self._compute_budget(turns) == 0

    def test_fourth_refresh_goes_negative(self):
        turns = [self._make_turn(waiting_for="refresh_gitlab_context") for _ in range(4)]
        assert self._compute_budget(turns) < 0

    def test_agent_completion_refills(self):
        turns = [
            self._make_turn(waiting_for="refresh_gitlab_context"),
            self._make_turn(waiting_for="refresh_gitlab_context"),
            self._make_turn(waiting_for="refresh_gitlab_context"),
            self._make_turn(actor="sysadmin", action="execute"),
        ]
        assert self._compute_budget(turns) == 1

    def test_cancel_does_not_refill(self):
        turns = [
            self._make_turn(waiting_for="refresh_gitlab_context"),
            self._make_turn(waiting_for="refresh_gitlab_context"),
            self._make_turn(waiting_for="refresh_gitlab_context"),
            self._make_turn(actor="sysadmin", action="cancel"),
        ]
        assert self._compute_budget(turns) == 0

    def test_huddle_does_not_refill(self):
        turns = [
            self._make_turn(waiting_for="refresh_gitlab_context"),
            self._make_turn(waiting_for="refresh_gitlab_context"),
            self._make_turn(waiting_for="refresh_gitlab_context"),
            self._make_turn(actor="developer", action="huddle"),
        ]
        assert self._compute_budget(turns) == 0

    def test_budget_capped_at_10(self):
        turns = [self._make_turn(actor="sysadmin", action="execute") for _ in range(20)]
        assert self._compute_budget(turns) == 10

    def test_aligner_excluded_from_refill(self):
        turns = [self._make_turn(actor="aligner", action="execute")]
        assert self._compute_budget(turns) == 3
