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
        }
        defaults.update(overrides)
        return defaults

    def test_new_event_triage(self):
        ctx = self._make_ctx(turn_count=0)
        active = [p for p, cond in PHASE_CONDITIONS.items() if cond(None, ctx)]
        assert "always" in active
        assert "triage" in active
        assert "dispatch" in active
        assert "source" in active
        assert "post-agent" not in active

    def test_post_agent_excludes_triage_dispatch(self):
        ctx = self._make_ctx(turn_count=1, has_agent_result=True)
        active = [p for p, cond in PHASE_CONDITIONS.items() if cond(None, ctx)]
        assert "post-agent" in active
        assert "triage" in active
        assert "dispatch" in active

        excluded: set[str] = set()
        for phase in active:
            excluded.update(PHASE_EXCLUSIONS.get(phase, []))
        final = [p for p in active if p not in excluded]
        assert "post-agent" in final
        assert "triage" not in final
        assert "dispatch" not in final
        assert "source" in final

    def test_waiting_excludes_triage_dispatch_postagent(self):
        ctx = self._make_ctx(turn_count=5, is_waiting=True, has_agent_result=True)
        active = [p for p, cond in PHASE_CONDITIONS.items() if cond(None, ctx)]

        excluded: set[str] = set()
        for phase in active:
            excluded.update(PHASE_EXCLUSIONS.get(phase, []))
        final = [p for p in active if p not in excluded]
        assert "waiting" in final
        assert "always" in final
        assert "source" in final
        assert "triage" not in final
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
