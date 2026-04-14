# BlackBoard/tests/test_brain_progressive.py
# @ai-rules:
# 1. [Constraint]: Tests Brain static/class methods only -- no Redis, no async, no adapter.
# 2. [Pattern]: Uses minimal ConversationTurn/EventDocument stubs for isolation.
"""Unit tests for Brain progressive skill methods: recommendation extraction, phase matching."""
from __future__ import annotations

import pytest

from src.agents.brain import Brain, PHASE_CONDITIONS, PHASE_EXCLUSIONS


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

    def test_max_tokens_cap(self):
        long_rec = "## Recommendation\n" + "x" * 2000
        result = Brain._extract_recommendation(long_rec, max_tokens=100)
        assert result is not None
        assert len(result) <= 400  # 100 tokens * 4 chars


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
        }
        defaults.update(overrides)
        return defaults

    def test_new_event_dispatch_gated_before_classify(self):
        ctx = self._make_ctx(turn_count=0)
        active = [p for p, cond in PHASE_CONDITIONS.items() if cond(None, ctx)]
        assert "always" in active
        assert "dispatch" not in active, "dispatch must be gated until brain classifies"
        assert "source" in active
        assert "post-agent" not in active

    def test_new_event_dispatch_unlocked_after_classify(self):
        ctx = self._make_ctx(turn_count=1, brain_has_classified=True)
        active = [p for p, cond in PHASE_CONDITIONS.items() if cond(None, ctx)]
        assert "dispatch" in active, "dispatch available after classify_event"

    def test_post_agent_excludes_dispatch(self):
        ctx = self._make_ctx(turn_count=1, has_agent_result=True, brain_has_classified=True)
        active = [p for p, cond in PHASE_CONDITIONS.items() if cond(None, ctx)]
        assert "post-agent" in active
        assert "dispatch" in active

        excluded: set[str] = set()
        for phase in active:
            excluded.update(PHASE_EXCLUSIONS.get(phase, []))
        final = [p for p in active if p not in excluded]
        assert "post-agent" in final
        assert "dispatch" not in final
        assert "source" in final

    def test_waiting_excludes_dispatch_postagent(self):
        ctx = self._make_ctx(turn_count=5, is_waiting=True, has_agent_result=True)
        active = [p for p, cond in PHASE_CONDITIONS.items() if cond(None, ctx)]

        excluded: set[str] = set()
        for phase in active:
            excluded.update(PHASE_EXCLUSIONS.get(phase, []))
        final = [p for p in active if p not in excluded]
        assert "waiting" in final
        assert "always" in final
        assert "source" in final
        assert "dispatch" not in final
        assert "post-agent" not in final

    def test_context_phase_activates_on_related(self):
        ctx = self._make_ctx(turn_count=1, has_related=True)
        active = [p for p, cond in PHASE_CONDITIONS.items() if cond(None, ctx)]
        assert "context" in active

    def test_context_phase_inactive_when_no_context(self):
        ctx = self._make_ctx(turn_count=1)
        active = [p for p, cond in PHASE_CONDITIONS.items() if cond(None, ctx)]
        assert "context" not in active


class TestSurfaceAgentRecommendation:
    @staticmethod
    def _make_event_stub(agent_result: str | None = None):
        """Minimal stub with just enough for _surface_agent_recommendation."""
        from unittest.mock import MagicMock
        event = MagicMock()
        if agent_result is not None:
            turn = MagicMock()
            turn.actor = "sysadmin"
            turn.result = agent_result
            turn.thoughts = None
            turn.taskForAgent = None
            event.conversation = [turn]
        else:
            event.conversation = []
        return event

    def test_with_recommendation_header(self):
        event = self._make_event_stub("Analysis done.\n\n## Recommendation\nScale to 3.")
        result = Brain._surface_agent_recommendation(event)
        assert result is not None
        assert "LATEST AGENT RECOMMENDATION" in result
        assert "Scale to 3" in result

    def test_without_recommendation_returns_ask_directive(self):
        event = self._make_event_stub("")
        result = Brain._surface_agent_recommendation(event)
        assert result is not None
        assert "AGENT RESULT WITHOUT RECOMMENDATION" in result
        assert "route back to the SAME agent" in result

    def test_fallback_last_paragraph_as_recommendation(self):
        event = self._make_event_stub("Raw data dump with no next step.")
        result = Brain._surface_agent_recommendation(event)
        assert result is not None
        assert "LATEST AGENT RECOMMENDATION" in result

    def test_no_agent_turns_returns_none(self):
        event = self._make_event_stub(None)
        result = Brain._surface_agent_recommendation(event)
        assert result is None

    @staticmethod
    def _make_event_stub_with_reasoning(reasoning: str, result_body: str = "Evidence here."):
        """Stub with explicit taskForAgent.reasoning (structured frontmatter path)."""
        from unittest.mock import MagicMock
        event = MagicMock()
        turn = MagicMock()
        turn.actor = "developer"
        turn.result = result_body
        turn.thoughts = None
        turn.taskForAgent = {"reasoning": reasoning}
        event.conversation = [turn]
        return event

    def test_reasoning_promoted_as_rca(self):
        event = self._make_event_stub_with_reasoning("PaC controller not processing events")
        result = Brain._surface_agent_recommendation(event)
        assert result is not None
        assert "ROOT CAUSE ANALYSIS" in result
        assert "PaC controller not processing events" in result

    def test_reasoning_with_steps_still_promotes_rca(self):
        from unittest.mock import MagicMock
        event = MagicMock()
        turn = MagicMock()
        turn.actor = "sysadmin"
        turn.result = "Investigation complete."
        turn.thoughts = None
        turn.taskForAgent = {
            "reasoning": "OOMKilled exit code 137",
            "steps": [{"id": "1", "agent": "developer", "summary": "Fix memory leak"}],
            "source": "sysadmin",
        }
        event.conversation = [turn]
        result = Brain._surface_agent_recommendation(event)
        assert "ROOT CAUSE ANALYSIS" in result
        assert "OOMKilled" in result

    def test_no_reasoning_falls_through_to_legacy(self):
        """Agent without taskForAgent.reasoning uses legacy regex path."""
        from unittest.mock import MagicMock
        event = MagicMock()
        turn = MagicMock()
        turn.actor = "developer"
        turn.result = "Done.\n\n## Recommendation\nMerge the PR."
        turn.thoughts = None
        turn.taskForAgent = None
        event.conversation = [turn]
        result = Brain._surface_agent_recommendation(event)
        assert "LATEST AGENT RECOMMENDATION" in result
        assert "Merge the PR" in result

    def test_empty_reasoning_falls_through_to_legacy(self):
        from unittest.mock import MagicMock
        event = MagicMock()
        turn = MagicMock()
        turn.actor = "developer"
        turn.result = "No findings."
        turn.thoughts = None
        turn.taskForAgent = {"reasoning": ""}
        event.conversation = [turn]
        result = Brain._surface_agent_recommendation(event)
        assert "ROOT CAUSE ANALYSIS" not in result


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
