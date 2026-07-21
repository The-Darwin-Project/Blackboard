# BlackBoard/tests/test_brain_prompt_assembly.py
# @ai-rules:
# 1. [Constraint]: Tests mock _skill_loader -- no dependency on actual skill files or Brain init.
# 2. [Pattern]: Minimal EventDocument stubs via SimpleNamespace. Only fields _build_system_prompt reads.
# 3. [Gotcha]: _build_system_prompt is async -- all tests must be async.
"""Unit tests for _build_system_prompt wrapping logic in Brain."""
from __future__ import annotations

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest


def _make_event_stub(
    source: str = "chat",
    service: str = "test-svc",
    brain_phase: str = "triage",
    subject_type: str = "service",
    kargo_context: object | None = None,
):
    """Minimal EventDocument-like stub for _build_system_prompt."""
    evidence = SimpleNamespace(kargo_context=kargo_context)
    inner_event = SimpleNamespace(evidence=evidence)
    return SimpleNamespace(
        id="evt-test",
        source=source,
        service=service,
        brain_phase=brain_phase,
        subject_type=subject_type,
        event=inner_event,
        conversation=[],
        active_plan=None,
    )


def _make_brain_stub(resolved_pairs, kargo_paths=None, kargo_bodies=None):
    """Build a Brain-like object with mocked _skill_loader and helper methods."""
    loader = MagicMock()
    loader.resolve_dependencies_with_paths.return_value = resolved_pairs
    loader.get_all_paths_for_phase.return_value = []
    loader.find_paths_by_tag.return_value = kargo_paths or []
    loader.get_tag_type.side_effect = lambda p: {
        "always": "rule", "source": "rule", "context": "context"
    }.get(p.split("/")[0], "skill")

    if kargo_bodies is not None:
        loader.get_with_meta.side_effect = lambda p: kargo_bodies.get(p)
    else:
        loader.get_with_meta.return_value = None

    brain = SimpleNamespace(
        _skill_loader=loader,
        _build_event_state_header=lambda event, ctx: "## EVENT STATE HEADER",
        _post_agent_recall=lambda event: None,
        _format_recall_block=lambda event: None,
    )
    return brain


class TestWrappingFormat:
    @pytest.mark.asyncio
    async def test_skills_wrapped_with_semantic_tags(self):
        pairs = [
            ("phase/file-a.md", "# Skill A content"),
            ("dispatch/exec.md", "# Execution rules"),
        ]
        brain = _make_brain_stub(pairs)

        from src.agents.brain import Brain
        prompt = await Brain._build_system_prompt(
            brain, _make_event_stub(), ["triage"], context_flags=None
        )

        assert '<skill id="phase/file-a.md">' in prompt
        assert "# Skill A content" in prompt
        assert '<skill id="dispatch/exec.md">' in prompt
        assert "# Execution rules" in prompt
        assert "</skill>" in prompt

    @pytest.mark.asyncio
    async def test_empty_resolved_list_no_crash(self):
        brain = _make_brain_stub([])

        from src.agents.brain import Brain
        prompt = await Brain._build_system_prompt(
            brain, _make_event_stub(), ["triage"], context_flags=None
        )

        assert "## EVENT STATE HEADER" in prompt
        assert "<skill" not in prompt

    @pytest.mark.asyncio
    async def test_kargo_none_guard(self, caplog):
        brain = _make_brain_stub(
            resolved_pairs=[],
            kargo_paths=["context/kargo-environment.md"],
            kargo_bodies={},
        )

        event = _make_event_stub(kargo_context=SimpleNamespace(promotion_id="p1"))

        from src.agents.brain import Brain
        with caplog.at_level(logging.DEBUG):
            prompt = await Brain._build_system_prompt(
                brain, event, ["triage"], context_flags=None
            )

        assert "kargo-environment.md" not in prompt
        assert "resolved to None" in caplog.text

    @pytest.mark.asyncio
    async def test_kargo_positive_wrapping(self):
        brain = _make_brain_stub(
            resolved_pairs=[("always/identity.md", "# Identity")],
            kargo_paths=["context/kargo-environment.md"],
            kargo_bodies={"context/kargo-environment.md": ("# Kargo Promotion Environment", {})},
        )

        event = _make_event_stub(kargo_context=SimpleNamespace(promotion_id="p1"))

        from src.agents.brain import Brain
        prompt = await Brain._build_system_prompt(
            brain, event, ["triage"], context_flags=None
        )

        assert '<context id="context/kargo-environment.md">' in prompt
        assert "# Kargo Promotion Environment" in prompt
        assert "</context>" in prompt

    @pytest.mark.asyncio
    async def test_mixed_wrapped_unwrapped_join(self):
        pairs = [("always/identity.md", "# Identity")]
        brain = _make_brain_stub(pairs)

        event = _make_event_stub()
        context_flags = {"consecutive_agent_waits": 3}

        from src.agents.brain import Brain
        prompt = await Brain._build_system_prompt(
            brain, event, ["triage"], context_flags=context_flags
        )

        assert "\n\n---\n\n" in prompt
        assert '<rule id="always/identity.md">' in prompt
        assert "WAIT LOOP DETECTED" in prompt

    @pytest.mark.asyncio
    async def test_semantic_tag_type_selection(self):
        """Verify each folder maps to its correct semantic tag type."""
        pairs = [
            ("always/rules.md", "# Rules"),
            ("source/slack.md", "# Slack"),
            ("context/env.md", "# Env"),
            ("dispatch/exec.md", "# Exec"),
            ("triage/assess.md", "# Assess"),
        ]
        brain = _make_brain_stub(pairs)

        from src.agents.brain import Brain
        prompt = await Brain._build_system_prompt(
            brain, _make_event_stub(), ["triage"], context_flags=None
        )

        assert '<rule id="always/rules.md">' in prompt
        assert '</rule>' in prompt
        assert '<rule id="source/slack.md">' in prompt
        assert '<context id="context/env.md">' in prompt
        assert '</context>' in prompt
        assert '<skill id="dispatch/exec.md">' in prompt
        assert '<skill id="triage/assess.md">' in prompt


class TestFailClosed:
    @pytest.mark.asyncio
    async def test_build_system_prompt_raises_when_no_loader(self):
        """_build_system_prompt raises RuntimeError when skill loader has no phases."""
        loader = MagicMock()
        loader.available_phases.return_value = []

        brain = SimpleNamespace(_skill_loader=loader)

        from src.agents.brain import Brain
        with pytest.raises(RuntimeError, match="no available phases"):
            await Brain._build_system_prompt(
                brain, _make_event_stub(), ["triage"], context_flags=None
            )

    @pytest.mark.asyncio
    async def test_build_system_prompt_raises_when_loader_is_none(self):
        """_build_system_prompt raises RuntimeError when _skill_loader is None."""
        brain = SimpleNamespace(_skill_loader=None)

        from src.agents.brain import Brain
        with pytest.raises(RuntimeError, match="no available phases"):
            await Brain._build_system_prompt(
                brain, _make_event_stub(), ["triage"], context_flags=None
            )
