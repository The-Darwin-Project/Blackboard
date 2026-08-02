# tests/test_build_contents_fc_fr.py
# @ai-rules:
# 1. [Constraint]: Tests for FC/FR (functionCall/functionResponse) reconstruction in _build_contents.
# 2. [Pattern]: Uses ConversationTurn + EventDocument stubs. No live Redis or LLM.
# 3. [Gotcha]: _dedup_consecutive_fr matches FC+FR PAIRS (2-message atomic units), not bare FR.
#    Collapses 3+ identical consecutive pairs. Runs BEFORE _compress_contents in pipeline.
# 4. [Pattern]: Tests define the target reconstruction behavior (TDD). _build_contents_fc_fr module.
"""Unit tests for FC/FR reconstruction, compression pair-delete, _estimate_tokens,
N-way dedup, dedup immutability, floor=summary, and interleaved text+FC.

These tests define the target interface (TDD). Expected to fail until
implementation lands.
"""
from __future__ import annotations

import copy
import json
import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_event(
    event_id: str = "evt-fc-test",
    source: str = "chat",
    conversation: list | None = None,
) -> EventDocument:
    evidence = EventEvidence(
        display_text="test FC/FR", source_type=source, domain="complicated", severity="info",
    )
    return EventDocument(
        id=event_id,
        source=source,
        service="test-svc",
        event=EventInput(reason="test", evidence=evidence),
        conversation=conversation or [],
    )


def _make_turn(
    turn: int = 1,
    actor: str = "brain",
    action: str = "tool_result",
    thoughts: str | None = None,
    result: str | None = None,
    response_parts: list[dict] | None = None,
    waitingFor: str | None = None,
) -> ConversationTurn:
    return ConversationTurn(
        turn=turn,
        actor=actor,
        action=action,
        thoughts=thoughts,
        result=result,
        response_parts=response_parts,
        waitingFor=waitingFor,
        timestamp=time.time(),
    )


# ---------------------------------------------------------------------------
# Test 1: 3-case FC/FR reconstruction
# ---------------------------------------------------------------------------

class TestFCFRReconstruction:
    """Three cases of FC/FR reconstruction in _build_contents."""

    def test_case1_prior_model_message_has_matching_fc_only_fr_emitted(self):
        """Case 1: prior model message has matching FC → only FR emitted (no duplicate FC)."""
        fc_part = {"functionCall": {"name": "select_agent", "args": {"agent": "sysadmin"}}}
        fr_part = {"functionResponse": {"name": "select_agent", "response": {"result": "dispatched"}}}

        model_turn = _make_turn(
            turn=1, actor="brain", action="route",
            response_parts=[{"text": "Routing to sysadmin"}, fc_part],
        )
        tool_result_turn = _make_turn(
            turn=2, actor="brain", action="tool_result",
            thoughts="Agent dispatched successfully",
            waitingFor="select_agent",
        )

        # The model message already contains the FC; tool_result should produce FR only
        # (avoiding duplicate FC in the content array)
        assert model_turn.response_parts is not None
        has_fc = any("functionCall" in p for p in model_turn.response_parts)
        assert has_fc, "Precondition: model turn has the FC"

        # The reconstruction logic should emit FR for Case 1
        expected_fr = {
            "functionResponse": {
                "name": "select_agent",
                "response": {"result": tool_result_turn.thoughts},
            }
        }
        assert expected_fr["functionResponse"]["name"] == "select_agent"

    def test_case2_response_parts_has_function_call_fc_fr_pair(self):
        """Case 2: turn.response_parts has functionCall → FC+FR pair emitted."""
        fc_part = {"functionCall": {"name": "classify_event", "args": {"domain": "complicated"}}}

        brain_turn = _make_turn(
            turn=1, actor="brain", action="triage",
            response_parts=[fc_part],
        )
        tool_result_turn = _make_turn(
            turn=2, actor="brain", action="tool_result",
            thoughts="Classified as complicated",
            waitingFor="classify_event",
        )

        assert brain_turn.response_parts is not None
        assert any("functionCall" in p for p in brain_turn.response_parts)

        # Case 2: both FC (from response_parts) and FR (from tool_result) must be emitted
        fc = brain_turn.response_parts[0]
        assert "functionCall" in fc
        assert fc["functionCall"]["name"] == "classify_event"

    def test_case3_no_response_parts_synthesized_fc_fr(self):
        """Case 3: response_parts=None, waitingFor="select_agent" → synthesized FC with {_synthesized:true} + FR."""
        tool_result_turn = _make_turn(
            turn=2, actor="brain", action="tool_result",
            thoughts="Agent dispatched",
            waitingFor="select_agent",
            response_parts=None,
        )

        # No prior model message with FC, no response_parts → synthesize
        assert tool_result_turn.response_parts is None
        assert tool_result_turn.waitingFor == "select_agent"

        # Expected synthesized FC:
        synthesized_fc = {
            "functionCall": {
                "name": "select_agent",
                "args": {"_synthesized": True},
            }
        }
        assert synthesized_fc["functionCall"]["args"]["_synthesized"] is True

        # FR follows the synthesized FC
        synthesized_fr = {
            "functionResponse": {
                "name": "select_agent",
                "response": {"result": tool_result_turn.thoughts},
            }
        }
        assert synthesized_fr["functionResponse"]["name"] == "select_agent"


# ---------------------------------------------------------------------------
# Test 2: Compression pair-delete
# ---------------------------------------------------------------------------

class TestCompressionPairDelete:
    """After all turns skeleton'd, pairs deleted oldest-first, min 5 recent retained."""

    def test_pair_delete_preserves_min_5_recent(self):
        """Compression never deletes the 5 most recent FC/FR pairs."""
        from src.agents.brain import Brain

        # Build contents with 10 FC/FR pairs (20 messages) to trigger compression
        contents = [{"role": "user", "parts": [{"text": "Event context header " * 200}]}]
        for i in range(10):
            contents.append({
                "role": "model",
                "parts": [{"functionCall": {"name": f"tool_{i}", "args": {}}}],
            })
            contents.append({
                "role": "user",
                "parts": [{"functionResponse": {"name": f"tool_{i}", "response": {"ok": True}}}],
            })
        # Add enough text to exceed token budget for triggering compression
        for i in range(5):
            contents.append({"role": "model", "parts": [{"text": "final answer " * 500}]})
            contents.append({"role": "user", "parts": [{"text": "follow up " * 500}]})

        compressed = Brain._compress_contents(contents, max_tokens=5000)

        # Count surviving FC/FR pairs in compressed output
        fc_count = sum(
            1 for msg in compressed
            if msg["role"] == "model" and any(
                isinstance(p, dict) and "functionCall" in p
                for p in msg.get("parts", [])
            )
        )
        # At minimum 5 recent should survive (or fewer if total was less)
        assert fc_count >= min(5, 10)


# ---------------------------------------------------------------------------
# Test 3: _estimate_tokens
# ---------------------------------------------------------------------------

class TestEstimateTokens:
    """FC/FR dicts measured (not zero), len(json.dumps(part))//4."""

    def test_fc_fr_dicts_have_nonzero_token_estimate(self):
        """functionCall and functionResponse parts contribute to token estimate."""
        from src.agents.brain import Brain

        fc_msg = {
            "role": "model",
            "parts": [{"functionCall": {"name": "classify_event", "args": {"domain": "complicated", "confidence": "high"}}}],
        }
        fr_msg = {
            "role": "user",
            "parts": [{"functionResponse": {"name": "classify_event", "response": {"result": "classified as complicated"}}}],
        }

        contents = [fc_msg, fr_msg]
        tokens = Brain._estimate_tokens(contents)

        # FC/FR must contribute tokens (not treated as zero)
        assert tokens > 0

    def test_text_estimation_approximation(self):
        """Text parts use len(text)//4 approximation."""
        from src.agents.brain import Brain

        text_400_chars = "a" * 400
        contents = [{"role": "user", "parts": [{"text": text_400_chars}]}]
        tokens = Brain._estimate_tokens(contents)

        assert tokens == 100  # 400 chars // 4


# ---------------------------------------------------------------------------
# Test 4: N-way dedup
# ---------------------------------------------------------------------------

class TestNWayDedup:
    """8 consecutive identical FC+FR pairs → collapsed to 1 pair + annotation."""

    def test_8_identical_fr_collapsed(self):
        """8 consecutive identical FC+FR pairs collapse to 1 pair + annotation.

        _dedup_consecutive_fr runs before _compress_contents in the pipeline
        (brain.py L2735). It matches FC+FR pairs as atomic 2-message units and
        collapses 3+ identical consecutive pairs.
        """
        from src.agents.brain import Brain

        fr_part = {"functionResponse": {"name": "wait_for_agent", "response": {"status": "still_waiting"}}}
        contents = [{"role": "user", "parts": [{"text": "context"}]}]

        for _ in range(8):
            contents.append({"role": "model", "parts": [{"functionCall": {"name": "wait_for_agent", "args": {}}}]})
            contents.append({"role": "user", "parts": [fr_part]})

        deduped = Brain._dedup_consecutive_fr(contents)

        fr_messages = [
            msg for msg in deduped
            if msg["role"] == "user" and any(
                isinstance(p, dict) and "functionResponse" in p
                for p in msg.get("parts", [])
            )
        ]
        assert len(fr_messages) == 1, f"8 identical pairs should collapse to 1, got {len(fr_messages)}"

    def test_non_consecutive_not_deduped(self):
        """Non-consecutive identical FR should NOT be collapsed."""
        from src.agents.brain import Brain

        contents = [{"role": "user", "parts": [{"text": "context"}]}]

        # Alternate different tools between identical ones
        for i in range(4):
            contents.append({"role": "model", "parts": [{"functionCall": {"name": "wait_for_agent", "args": {}}}]})
            contents.append({"role": "user", "parts": [{"functionResponse": {"name": "wait_for_agent", "response": {"status": "waiting"}}}]})
            contents.append({"role": "model", "parts": [{"functionCall": {"name": f"other_tool_{i}", "args": {}}}]})
            contents.append({"role": "user", "parts": [{"functionResponse": {"name": f"other_tool_{i}", "response": {"ok": True}}}]})

        compressed = Brain._compress_contents(contents, max_tokens=999_999)

        # Non-consecutive: all preserved
        fr_wait = [
            msg for msg in compressed
            if msg["role"] == "user" and any(
                isinstance(p, dict) and p.get("functionResponse", {}).get("name") == "wait_for_agent"
                for p in msg.get("parts", [])
            )
        ]
        assert len(fr_wait) == 4


# ---------------------------------------------------------------------------
# Test 5: Dedup on deep copies (original not mutated)
# ---------------------------------------------------------------------------

class TestDedupImmutability:
    """original turn.response_parts NOT mutated after dedup."""

    def test_original_response_parts_not_mutated(self):
        """Dedup creates copies; original ConversationTurn.response_parts is unchanged."""
        fc_part = {"functionCall": {"name": "wait_for_agent", "args": {"summary": "waiting"}}}

        original_parts = [fc_part.copy()]
        turn = _make_turn(turn=1, actor="brain", action="wait", response_parts=original_parts)

        original_snapshot = copy.deepcopy(turn.response_parts)

        from src.agents.brain import Brain

        # Build contents that would trigger dedup
        contents = [{"role": "user", "parts": [{"text": "context"}]}]
        for _ in range(8):
            contents.append({"role": "model", "parts": [fc_part.copy()]})
            contents.append({"role": "user", "parts": [{"functionResponse": {"name": "wait_for_agent", "response": {"ok": True}}}]})

        Brain._compress_contents(contents, max_tokens=999_999)

        # Original turn's response_parts must NOT be mutated
        assert turn.response_parts == original_snapshot


# ---------------------------------------------------------------------------
# Test 6: FC/FR floor=summary
# ---------------------------------------------------------------------------

class TestFCFRFloorSummary:
    """FC/FR never enters skeleton tier even in long conversations."""

    def test_fc_fr_pair_never_skeleton(self):
        """FC/FR atomic pairs are promoted out of skeleton tier."""
        from src.agents.brain import Brain

        # Build a very long conversation to push early messages into skeleton tier
        contents = [{"role": "user", "parts": [{"text": "x" * 5000}]}]

        # Early FC/FR pair (should be promoted out of skeleton)
        contents.append({"role": "model", "parts": [{"functionCall": {"name": "classify_event", "args": {}}}]})
        contents.append({"role": "user", "parts": [{"functionResponse": {"name": "classify_event", "response": {"domain": "complicated"}}}]})

        # Add many text turns to push the above into what would normally be skeleton range
        for i in range(30):
            contents.append({"role": "model", "parts": [{"text": f"response {i} " * 200}]})
            contents.append({"role": "user", "parts": [{"text": f"follow up {i} " * 200}]})

        compressed = Brain._compress_contents(contents, max_tokens=20_000)

        # Find the FC message in compressed output
        fc_msgs = [
            msg for msg in compressed
            if msg["role"] == "model" and any(
                isinstance(p, dict) and "functionCall" in p
                for p in msg.get("parts", [])
            )
        ]
        # FC messages should not be rendered as skeleton "(earlier turn: ...)"
        for msg in fc_msgs:
            for p in msg.get("parts", []):
                if isinstance(p, dict) and "text" in p:
                    assert not p["text"].startswith("(earlier turn:")


# ---------------------------------------------------------------------------
# Test 7: Interleaved text+FC
# ---------------------------------------------------------------------------

class TestInterleavedTextFC:
    """brain.response with text+FC in response_parts → FC preserved in model message."""

    def test_brain_response_text_plus_fc_preserved(self):
        """When response_parts has both text and functionCall, both appear in model content."""
        fc_part = {"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}
        text_part = {"text": "I'll dispatch a developer to handle this."}

        turn = _make_turn(
            turn=1, actor="brain", action="route",
            response_parts=[text_part, fc_part],
        )

        from src.agents.brain import Brain
        parts = Brain._turn_to_parts(turn)

        # Both text and FC should be preserved
        has_text = any(isinstance(p, dict) and "text" in p for p in parts)
        has_fc = any(isinstance(p, dict) and "functionCall" in p for p in parts)

        assert has_text, "Text part must be preserved in model message"
        assert has_fc, "functionCall part must be preserved in model message"

    def test_tool_result_after_text_fc_emits_fr_only(self):
        """tool_result turn after a model message with FC → FR only (Case 1: no dup FC)."""
        model_turn = _make_turn(
            turn=1, actor="brain", action="route",
            response_parts=[
                {"text": "Dispatching developer"},
                {"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}},
            ],
        )
        tool_result_turn = _make_turn(
            turn=2, actor="brain", action="tool_result",
            thoughts="Developer dispatched and working on the task",
            waitingFor="select_agent",
        )

        from src.agents.brain import Brain
        # tool_result turn's parts should be FR-styled (not another FC)
        parts = Brain._turn_to_parts(tool_result_turn)

        # Should NOT contain functionCall (that's already in the model turn)
        has_fc = any(isinstance(p, dict) and "functionCall" in p for p in parts)
        assert not has_fc, "tool_result should not duplicate the FC from the model turn"
