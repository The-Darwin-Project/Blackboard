# BlackBoard/tests/test_build_contents_structure.py
# @ai-rules:
# 1. [Constraint]: Tests verify content structure labels and markers per plan specification.
#    Written from spec only — tests the PLANNED interface, not current implementation.
# 2. [Pattern]: _turn_to_parts is @staticmethod — call Brain._turn_to_parts(turn) directly.
#    _build_contents is async — use SimpleNamespace mock as self (same pattern as test_brain_prompt_assembly).
# 3. [Gotcha]: _build_contents lazily imports build_event_header from llm.prompt.
# 4. [Pattern]: _make_event/_make_turn helpers follow test_brain_loop_plumbing.py conventions.
"""Unit tests for _turn_to_parts labeling and _build_contents structural markers.

Spec IDs: T1–T12.
Verifies prefix labeling ([USER], [SYSTEM X], [AGENT Y]),
delta markers, header boundaries, and FC/FR pairing in the contents array.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.agents.brain import Brain
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_turn(
    turn: int = 1,
    actor: str = "brain",
    action: str = "response",
    thoughts: str | None = None,
    result: str | None = None,
    evidence: str | None = None,
    waitingFor: str | None = None,
    response_parts: list[dict] | None = None,
) -> ConversationTurn:
    return ConversationTurn(
        turn=turn, actor=actor, action=action,
        thoughts=thoughts, result=result, evidence=evidence,
        waitingFor=waitingFor, response_parts=response_parts,
    )


def _make_event(
    event_id: str = "evt-test",
    source: str = "chat",
    service: str = "test-svc",
    conversation: list[ConversationTurn] | None = None,
    brain_phase: str | None = "triage",
) -> EventDocument:
    evidence = EventEvidence(
        display_text="test", source_type=source,
        domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id,
        source=source,
        status=EventStatus("active"),
        brain_phase=brain_phase,
        service=service,
        event=EventInput(
            reason="test event", evidence=evidence,
            timeDate="2026-01-01T00:00:00Z",
        ),
        conversation=conversation or [],
    )


def _make_brain_mock():
    """Minimal Brain-like object for _build_contents (unbound call)."""
    bb = AsyncMock()
    bb.get_service.return_value = None
    bb.get_active_events.return_value = []
    bb.get_event.return_value = None
    bb.get_recent_closed_for_service.return_value = []

    return SimpleNamespace(
        blackboard=bb,
        _get_journal_cached=AsyncMock(return_value=[]),
        _skill_loader=None,
        _turn_to_parts=Brain._turn_to_parts,
        _compress_contents=Brain._compress_contents,
    )


def _all_text(contents: list[dict]) -> str:
    """Concatenate all text parts across all contents for substring search."""
    return "\n".join(
        part.get("text", "")
        for msg in contents
        for part in msg.get("parts", [])
    )


# ---------------------------------------------------------------------------
# T1–T5, T11, T12: _turn_to_parts labeling (static, no async)
# ---------------------------------------------------------------------------

class TestTurnToPartsLabeling:
    """Brain._turn_to_parts prefix labels."""

    def test_t1_user_message_gets_user_prefix(self):
        turn = _make_turn(actor="user", action="message", thoughts="hello")
        parts = Brain._turn_to_parts(turn)

        assert len(parts) >= 1
        assert parts[0]["text"].startswith("[USER]: ")
        assert "hello" in parts[0]["text"]

    def test_t2_tool_result_gets_system_prefix(self):
        turn = _make_turn(
            actor="brain", action="tool_result",
            waitingFor="classify_event", evidence="Domain: CLEAR",
        )
        parts = Brain._turn_to_parts(turn)

        assert len(parts) >= 1
        assert parts[0]["text"].startswith("[SYSTEM classify_event]: ")
        assert "Domain: CLEAR" in parts[0]["text"]

    def test_t3_agent_turn_gets_agent_prefix(self):
        turn = _make_turn(actor="developer", action="execute", result="Done")
        parts = Brain._turn_to_parts(turn)

        assert len(parts) >= 1
        assert parts[0]["text"].startswith("[AGENT developer]: ")
        assert "Done" in parts[0]["text"]

    def test_t4_brain_response_with_response_parts_raw(self):
        rp = [{"text": "hi"}]
        turn = _make_turn(actor="brain", action="response", response_parts=rp)
        parts = Brain._turn_to_parts(turn)

        assert parts == rp

    def test_t5_brain_phase_gets_system_phase_prefix(self):
        turn = _make_turn(actor="brain", action="phase", thoughts="Phase: VERIFY")
        parts = Brain._turn_to_parts(turn)

        assert len(parts) >= 1
        assert parts[0]["text"].startswith("[SYSTEM phase]: ")
        assert "Phase: VERIFY" in parts[0]["text"]

    def test_t11_brain_response_no_response_parts_no_prefix(self):
        turn = _make_turn(actor="brain", action="response", thoughts="Hey!")
        parts = Brain._turn_to_parts(turn)

        assert len(parts) >= 1
        assert parts[0]["text"] == "Hey!"

    def test_t12_jarvis_message_gets_agent_jarvis_prefix(self):
        turn = _make_turn(actor="jarvis", action="message", thoughts="Pattern detected")
        parts = Brain._turn_to_parts(turn)

        assert len(parts) >= 1
        assert parts[0]["text"].startswith("[AGENT jarvis]: ")


# ---------------------------------------------------------------------------
# T6–T10: _build_contents structural markers (async)
# ---------------------------------------------------------------------------

class TestBuildContentsStructure:
    """Brain._build_contents delta markers, boundaries, and merging."""

    @pytest.mark.asyncio
    async def test_t6_delta_marker_before_last_non_brain_turn(self):
        """5-turn conversation ending with user.message → delta marker present."""
        conversation = [
            _make_turn(turn=1, actor="brain", action="response", thoughts="Noted"),
            _make_turn(turn=2, actor="user", action="message", thoughts="check status"),
            _make_turn(turn=3, actor="brain", action="response", thoughts="On it"),
            _make_turn(turn=4, actor="brain", action="tool_result",
                       waitingFor="inspect_event", evidence="All OK"),
            _make_turn(turn=5, actor="user", action="message", thoughts="what now?"),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        contents = await Brain._build_contents(brain, event)

        assert "--- RESPOND TO THIS ---" in _all_text(contents)

    @pytest.mark.asyncio
    async def test_t7_no_delta_marker_empty_conversation(self):
        """Empty conversation (header only) → no delta marker."""
        event = _make_event(conversation=[])
        brain = _make_brain_mock()

        contents = await Brain._build_contents(brain, event)

        assert "RESPOND TO THIS" not in _all_text(contents)

    @pytest.mark.asyncio
    async def test_t8_header_boundary_when_first_turn_merges(self):
        """First turn is user.message (role=user, same as header) → boundary separator."""
        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="Hello FRIDAY"),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        contents = await Brain._build_contents(brain, event)

        assert "--- CONVERSATION ---" in _all_text(contents)

    @pytest.mark.asyncio
    async def test_t9_fc_fr_pairing_unchanged(self):
        """functionCall Content is role=model, tool_result Content is role=user."""
        fc_parts = [{"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}]
        conversation = [
            _make_turn(turn=1, actor="brain", action="response",
                       response_parts=fc_parts),
            _make_turn(turn=2, actor="brain", action="tool_result",
                       waitingFor="classify_event", evidence="Domain: CLEAR"),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        contents = await Brain._build_contents(brain, event)

        fc_idx = None
        for i, msg in enumerate(contents):
            if any("functionCall" in p for p in msg.get("parts", [])):
                fc_idx = i
                break

        assert fc_idx is not None, "functionCall Content not found in contents"
        assert contents[fc_idx]["role"] == "model"
        assert fc_idx + 1 < len(contents), "No Content after functionCall"
        assert contents[fc_idx + 1]["role"] == "user"

    @pytest.mark.asyncio
    async def test_t10_merged_content_preserves_labels(self):
        """user.message + brain.tool_result (both role=user) merge; both labels visible."""
        conversation = [
            # model turn to break the user chain from the header
            _make_turn(turn=1, actor="brain", action="response", thoughts="Processing"),
            # user turn (role=user)
            _make_turn(turn=2, actor="user", action="message", thoughts="status?"),
            # tool_result (role=user) — should merge with previous user content
            _make_turn(turn=3, actor="brain", action="tool_result",
                       waitingFor="inspect_event", evidence="Active"),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        contents = await Brain._build_contents(brain, event)

        merged_found = False
        for msg in contents:
            texts = [p.get("text", "") for p in msg.get("parts", [])]
            has_user_label = any("[USER]" in t for t in texts)
            has_system_label = any("[SYSTEM" in t for t in texts)
            if has_user_label and has_system_label:
                merged_found = True
                break

        assert merged_found, (
            "No Content found with both [USER] and [SYSTEM] labels in merged parts"
        )
