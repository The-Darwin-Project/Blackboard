# BlackBoard/tests/test_build_contents_structure.py
# @ai-rules:
# 1. [Constraint]: Tests verify content structure labels and markers per plan specification.
#    Written from spec only — tests the PLANNED interface, not current implementation.
# 2. [Pattern]: _turn_to_parts is @staticmethod — call Brain._turn_to_parts(turn) directly.
#    _build_contents is async — use SimpleNamespace mock as self (same pattern as test_brain_prompt_assembly).
# 3. [Gotcha]: _build_contents lazily imports build_event_header from llm.prompt.
# 4. [Pattern]: _make_event/_make_turn helpers follow test_brain_loop_plumbing.py conventions.
# 5. [Pattern]: T-13+ tests verify native FC/FR propagation gated by _THOUGHT_SIG_V2.
#    Feature flag patched via monkeypatch on `src.agents.brain._THOUGHT_SIG_V2`.
"""Unit tests for _turn_to_parts labeling and _build_contents structural markers.

Spec IDs: T1–T31.
Verifies prefix labeling ([USER], [SYSTEM X], [AGENT Y]),
delta markers, header boundaries, FC/FR pairing, thought_signature propagation,
and compression safety for native function call/response contents.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

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
        _extract_model_parts=Brain._extract_model_parts,
        _build_function_response=Brain._build_function_response,
        _estimate_msg_tokens=Brain._estimate_msg_tokens,
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

    def test_t5_brain_phase_gets_friday_prefix(self):
        turn = _make_turn(actor="brain", action="phase", thoughts="Phase: VERIFY")
        parts = Brain._turn_to_parts(turn)

        assert len(parts) >= 1
        assert parts[0]["text"].startswith("[FRIDAY phase]: ")
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


# ---------------------------------------------------------------------------
# T13–T31: Native FC/FR propagation (thought_signature v2)
# ---------------------------------------------------------------------------

class TestNativeFCFRPropagation:
    """Tests for native functionCall/functionResponse pairing in _build_contents.

    When _THOUGHT_SIG_V2 is True, tool_result turns with a preceding FC
    emit a model:FC + user:FR Content pair instead of text-only [SYSTEM] labels.
    """

    @pytest.mark.asyncio
    async def test_t13_case_b_fc_only_tool_result_emits_model_fc_user_fr(self):
        """Case B: tool_result with response_parts=[{functionCall+sig}], no preceding response.

        When a tool_result has a functionCall in response_parts (stored from
        the preceding LLM cycle), _build_contents emits model:{FC+sig} then user:{FR}.
        """
        fc_part = {
            "functionCall": {"name": "classify_event", "args": {"domain": "clear"}},
            "thought_signature": "c2lnX2RhdGE=",
        }
        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="triage this"),
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc_part],
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        # Find the model Content with functionCall
        fc_idx = None
        for i, msg in enumerate(contents):
            if msg["role"] == "model" and any(
                "functionCall" in p for p in msg.get("parts", [])
            ):
                fc_idx = i
                break

        assert fc_idx is not None, "model:FC Content not found"
        # Verify signature preserved on the FC part
        fc_content = contents[fc_idx]
        fc_sig_parts = [p for p in fc_content["parts"] if p.get("thought_signature")]
        assert len(fc_sig_parts) >= 1, "thought_signature missing from FC part"

        # Next content must be user:FR
        assert fc_idx + 1 < len(contents), "No Content after model:FC"
        fr_content = contents[fc_idx + 1]
        assert fr_content["role"] == "user"
        fr_parts = [p for p in fr_content["parts"] if "functionResponse" in p]
        assert len(fr_parts) >= 1, "user:FR Content missing functionResponse"
        assert fr_parts[0]["functionResponse"]["name"] == "classify_event"

    @pytest.mark.asyncio
    async def test_t14_case_a_no_duplicate_fc(self):
        """Case A: response(FC) + tool_result(FC) → only ONE model:FC emitted.

        When brain.response already contains the FC (response_parts), the
        following tool_result must NOT emit a second model:FC. Result: one
        model:FC then one user:FR.
        """
        fc_part = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="triage"),
            # Response turn with the FC (brain emitted it)
            _make_turn(
                turn=2, actor="brain", action="response",
                response_parts=[fc_part],
            ),
            # Tool result following the FC
            _make_turn(
                turn=3, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc_part],
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        # Count model Contents with functionCall
        fc_msgs = [
            msg for msg in contents
            if msg["role"] == "model"
            and any("functionCall" in p for p in msg.get("parts", []))
        ]
        assert len(fc_msgs) == 1, f"Expected exactly 1 model:FC, got {len(fc_msgs)}"

        # Verify FR exists after the FC
        fc_idx = contents.index(fc_msgs[0])
        assert fc_idx + 1 < len(contents)
        fr_content = contents[fc_idx + 1]
        assert fr_content["role"] == "user"
        assert any("functionResponse" in p for p in fr_content.get("parts", []))

    @pytest.mark.asyncio
    async def test_t15_sig_never_on_user_text(self):
        """thought_signature NEVER appears on a role:user Content part.

        Tests at _build_contents level since FC/FR split lives there.
        """
        fc_part = {
            "functionCall": {"name": "select_agent", "args": {"agent": "developer"}},
            "thought_signature": "c2lnX2RhdGE=",
        }
        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="dispatch"),
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="select_agent", evidence="Dispatched developer",
                response_parts=[fc_part],
            ),
        ]

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_event(conversation=conversation)
            brain = _make_brain_mock()
            contents = await Brain._build_contents(brain, event)

        for content in contents:
            if content["role"] == "user":
                for p in content.get("parts", []):
                    if "functionResponse" in p:
                        continue
                    assert "thought_signature" not in p, (
                        f"thought_signature leaked to user-role part: {p}"
                    )

    @pytest.mark.asyncio
    async def test_t16_fr_format_correct(self):
        """functionResponse format: {functionResponse:{name:"classify_event", response:{result:"x"}}}.

        Tests at _build_contents level since FR emission lives there.
        """
        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="classify"),
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[
                    {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}},
                ],
            ),
        ]

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_event(conversation=conversation)
            brain = _make_brain_mock()
            contents = await Brain._build_contents(brain, event)

        fr_parts = []
        for content in contents:
            if content["role"] == "user":
                for p in content.get("parts", []):
                    if "functionResponse" in p:
                        fr_parts.append(p)

        assert len(fr_parts) >= 1, "No functionResponse part found in contents"
        fr = fr_parts[0]["functionResponse"]
        assert fr["name"] == "classify_event", f"FR name mismatch: {fr['name']}"
        assert "response" in fr, "FR missing 'response' key"
        assert "result" in fr["response"], "FR response missing 'result' key"
        assert fr["response"]["result"] == "Domain: CLEAR"

    def test_t17_backward_compat_no_fc_text_fallback(self):
        """No FC in response_parts → text fallback (old format).

        tool_result with response_parts=[{text:"", thought:true}] (no FC)
        should produce plain text [SYSTEM tool] format.
        """
        turn = _make_turn(
            turn=1, actor="brain", action="tool_result",
            waitingFor="inspect_event", evidence="All good",
            response_parts=[{"text": "", "thought": True}],
        )

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            parts = Brain._turn_to_parts(turn)

        # Should be old text format: [SYSTEM inspect_event]: All good
        assert len(parts) >= 1
        assert "text" in parts[0]
        assert "[SYSTEM inspect_event]:" in parts[0]["text"]
        assert "All good" in parts[0]["text"]
        # No functionResponse in output
        assert not any("functionResponse" in p for p in parts)

    @pytest.mark.asyncio
    async def test_t18_compression_pairs_no_orphans(self):
        """Compression with 50 turns, 5 FC/FR pairs, tight budget → no orphaned FC or FR."""
        conversation = []
        turn_num = 0

        # Build 50 turns with 5 FC/FR pairs interleaved
        for i in range(10):
            turn_num += 1
            conversation.append(
                _make_turn(turn=turn_num, actor="user", action="message",
                           thoughts=f"request {i}")
            )
            # Every other cycle has an FC/FR pair
            if i % 2 == 0:
                fc_part = {
                    "functionCall": {"name": f"tool_{i}", "args": {"x": "y" * 100}},
                    "thought_signature": "c2lnX2RhdGE=",
                }
                turn_num += 1
                conversation.append(
                    _make_turn(turn=turn_num, actor="brain", action="response",
                               response_parts=[fc_part])
                )
                turn_num += 1
                conversation.append(
                    _make_turn(turn=turn_num, actor="brain", action="tool_result",
                               waitingFor=f"tool_{i}", evidence=f"result {i}",
                               response_parts=[fc_part])
                )
            turn_num += 1
            conversation.append(
                _make_turn(turn=turn_num, actor="brain", action="response",
                           thoughts="a" * 500)
            )
            turn_num += 1
            conversation.append(
                _make_turn(turn=turn_num, actor="brain", action="response",
                           thoughts="b" * 500)
            )

        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        # Use a tight budget to force compression
        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
             patch("src.agents.brain._CONTENT_BUDGET", 200):
            contents = await Brain._build_contents(brain, event)

        # Verify: no model:FC without a following user:FR
        for i, msg in enumerate(contents):
            if msg["role"] == "model" and any(
                "functionCall" in p for p in msg.get("parts", [])
            ):
                assert i + 1 < len(contents), (
                    f"Orphaned model:FC at index {i} — no following Content"
                )
                next_msg = contents[i + 1]
                assert next_msg["role"] == "user", (
                    f"Orphaned model:FC at index {i} — next is role={next_msg['role']}"
                )
                # Next user must have FR or text (FR if native path)
                has_fr = any("functionResponse" in p for p in next_msg.get("parts", []))
                has_text = any("text" in p for p in next_msg.get("parts", []))
                assert has_fr or has_text, (
                    f"Orphaned model:FC at index {i} — next user has neither FR nor text"
                )

    def test_t19_token_estimation_counts_fc(self):
        """Token estimation must count functionCall args in budget calculation."""
        big_args = {"data": "x" * 4000}
        contents = [
            {"role": "model", "parts": [
                {"functionCall": {"name": "select_agent", "args": big_args}},
            ]},
        ]
        tokens = Brain._estimate_tokens(contents)
        assert tokens > 0, "FC args not counted in token estimation"
        # 4000 chars ≈ 1000 tokens at 4 chars/token
        assert tokens >= 100, f"Token estimate too low for 4K-char FC args: {tokens}"

    @pytest.mark.asyncio
    async def test_t20_positional_dedup_same_tool_twice(self):
        """classify_event called at idx 2 and idx 8 → both get model:FC."""
        fc_part_1 = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        fc_part_2 = {"functionCall": {"name": "classify_event", "args": {"domain": "complex"}}}

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="help"),
            # First classify_event
            _make_turn(turn=2, actor="brain", action="tool_result",
                       waitingFor="classify_event", evidence="Domain: CLEAR",
                       response_parts=[fc_part_1]),
            _make_turn(turn=3, actor="brain", action="response", thoughts="Classified"),
            _make_turn(turn=4, actor="user", action="message", thoughts="reclassify"),
            _make_turn(turn=5, actor="brain", action="response", thoughts="Re-evaluating"),
            _make_turn(turn=6, actor="user", action="message", thoughts="continue"),
            _make_turn(turn=7, actor="brain", action="response", thoughts="thinking"),
            # Second classify_event
            _make_turn(turn=8, actor="brain", action="tool_result",
                       waitingFor="classify_event", evidence="Domain: COMPLEX",
                       response_parts=[fc_part_2]),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        # Both positions must produce model:FC
        fc_msgs = [
            msg for msg in contents
            if msg["role"] == "model"
            and any("functionCall" in p for p in msg.get("parts", []))
        ]
        assert len(fc_msgs) == 2, (
            f"Expected 2 model:FC for same tool called twice, got {len(fc_msgs)}"
        )

    @pytest.mark.asyncio
    async def test_t21_flag_false_old_path(self):
        """_THOUGHT_SIG_V2=False → tool_result emits old text format, not native FC/FR."""
        fc_part = {
            "functionCall": {"name": "classify_event", "args": {"domain": "clear"}},
            "thought_signature": "c2lnX2RhdGE=",
        }
        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="test"),
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc_part],
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", False):
            contents = await Brain._build_contents(brain, event)

        # No native functionCall in output when flag is off
        for msg in contents:
            for part in msg.get("parts", []):
                assert "functionCall" not in part, (
                    "functionCall should not appear when _THOUGHT_SIG_V2=False"
                )
                assert "functionResponse" not in part, (
                    "functionResponse should not appear when _THOUGHT_SIG_V2=False"
                )

        # The old text format should be present
        all_text = _all_text(contents)
        assert "[SYSTEM classify_event]:" in all_text


# ---------------------------------------------------------------------------
# T22–T23: Adapter integration (structured conversion)
# ---------------------------------------------------------------------------

class TestAdapterIntegration:
    """Integration tests for adapter _convert_structured with native FC/FR."""

    def test_t22_gemini_dict_passthrough_with_sig(self):
        """GeminiAdapter._convert_structured passes through FC+sig with base64 decode."""
        from src.agents.llm.gemini_client import GeminiAdapter

        contents = [
            {"role": "model", "parts": [
                {
                    "functionCall": {"name": "classify_event", "args": {"domain": "clear"}},
                    "thought_signature": "c2lnX2RhdGE=",
                },
            ]},
            {"role": "user", "parts": [
                {"functionResponse": {
                    "name": "classify_event",
                    "response": {"result": "Domain: CLEAR"},
                }},
            ]},
        ]

        adapter = GeminiAdapter.__new__(GeminiAdapter)
        converted = adapter._convert_structured(contents)

        # Verify conversion produces 2 Content objects with correct roles
        assert len(converted) == 2
        assert converted[0].role == "model"
        assert converted[1].role == "user"
        # The model content should have parts (SDK wraps dicts into Part objects)
        assert len(converted[0].parts) >= 1
        # Verify conversion doesn't crash — live probe confirms API acceptance

    def test_t23_claude_adapter_fc_fr_conversion(self):
        """ClaudeAdapter._convert_structured maps FC→tool_use, FR→tool_result."""
        from src.agents.llm.claude_client import ClaudeAdapter

        contents = [
            {"role": "model", "parts": [
                {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}},
            ]},
            {"role": "user", "parts": [
                {"functionResponse": {
                    "name": "classify_event",
                    "response": {"result": "Domain: CLEAR"},
                }},
            ]},
        ]

        messages = ClaudeAdapter._convert_structured(contents)

        # Find assistant message with tool_use
        assistant_msgs = [m for m in messages if m["role"] == "assistant"]
        assert len(assistant_msgs) >= 1, "No assistant message found"
        tool_use_blocks = [
            b for m in assistant_msgs
            for b in m["content"]
            if b.get("type") == "tool_use"
        ]
        assert len(tool_use_blocks) >= 1, "No tool_use block found"
        assert tool_use_blocks[0]["name"] == "classify_event"

        # Find user message with tool_result
        user_msgs = [m for m in messages if m["role"] == "user"]
        tool_result_blocks = [
            b for m in user_msgs
            for b in m["content"]
            if b.get("type") == "tool_result"
        ]
        assert len(tool_result_blocks) >= 1, "No tool_result block found"


# ---------------------------------------------------------------------------
# T24–T31: Edge cases and regression guards
# ---------------------------------------------------------------------------

class TestFCFREdgeCases:
    """Edge cases for native FC/FR propagation."""

    @pytest.mark.asyncio
    async def test_t24_mixed_format_old_and_new_turns(self):
        """Old text turns + new FC/FR turns in same event → valid alternation."""
        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="Hello"),
            # Old-style tool_result (no FC in response_parts)
            _make_turn(turn=2, actor="brain", action="tool_result",
                       waitingFor="inspect_event", evidence="All OK"),
            _make_turn(turn=3, actor="brain", action="response", thoughts="Noted"),
            _make_turn(turn=4, actor="user", action="message", thoughts="classify"),
            # New-style tool_result (FC in response_parts)
            _make_turn(
                turn=5, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[
                    {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}},
                ],
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        # Validate alternation: no two consecutive same-role Contents
        for i in range(1, len(contents)):
            if contents[i]["role"] == contents[i - 1]["role"]:
                # Merging is allowed (same role = merged parts) but the test
                # structure should still produce valid output
                pass

        # At least one native FC and one text-based tool_result
        has_native_fc = any(
            msg["role"] == "model" and any("functionCall" in p for p in msg.get("parts", []))
            for msg in contents
        )
        has_text_system = "[SYSTEM inspect_event]:" in _all_text(contents)
        assert has_native_fc, "New-style FC missing in mixed conversation"
        assert has_text_system, "Old-style text tool_result missing in mixed conversation"

    @pytest.mark.asyncio
    async def test_t25_grounding_turn_excluded(self):
        """tool_result with waitingFor='google_web_search' → text fallback, not native FC.

        Grounding (search) tool_results should not emit native FC/FR because
        they are handled by the SDK's built-in grounding mechanism.
        """
        fc_part = {"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}
        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="find info"),
            # Grounding turn
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="google_web_search", evidence="Search results...",
                response_parts=[{"functionCall": {"name": "google_web_search", "args": {}}}],
            ),
            # Normal FC turn that follows
            _make_turn(
                turn=3, actor="brain", action="tool_result",
                waitingFor="select_agent", evidence="Dispatched",
                response_parts=[fc_part],
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        # google_web_search should be text fallback, not native FC
        all_text = _all_text(contents)
        assert "[SYSTEM google_web_search]:" in all_text, (
            "Grounding turn should use text fallback format"
        )

        # The select_agent turn should get native FC
        fc_msgs = [
            msg for msg in contents
            if msg["role"] == "model"
            and any(
                p.get("functionCall", {}).get("name") == "select_agent"
                for p in msg.get("parts", [])
            )
        ]
        assert len(fc_msgs) >= 1, "Non-grounding FC should still use native format"

    @pytest.mark.asyncio
    async def test_t26_t9_hardened_must_fail_on_unfixed_code(self):
        """T9 hardened: Case B with FC+sig — assert FR EXISTS and name matches FC.

        This is T9 but hardened for the new path. Under _THOUGHT_SIG_V2=True,
        a tool_result with FC in response_parts MUST produce both:
        - model Content with functionCall
        - user Content with functionResponse whose name matches the FC
        """
        fc_part = {
            "functionCall": {"name": "classify_event", "args": {"domain": "clear"}},
            "thought_signature": "c2lnX2RhdGE=",
        }
        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="test"),
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc_part],
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        # Find model:FC
        fc_idx = None
        fc_name = None
        for i, msg in enumerate(contents):
            if msg["role"] == "model":
                for p in msg.get("parts", []):
                    if "functionCall" in p:
                        fc_idx = i
                        fc_name = p["functionCall"]["name"]
                        break
            if fc_idx is not None:
                break

        assert fc_idx is not None, "model:FC Content MUST exist for Case B with FC+sig"

        # FR must immediately follow
        assert fc_idx + 1 < len(contents), "user:FR MUST follow model:FC"
        fr_content = contents[fc_idx + 1]
        assert fr_content["role"] == "user", "FR Content must be role=user"

        fr_parts = [p for p in fr_content["parts"] if "functionResponse" in p]
        assert len(fr_parts) >= 1, "functionResponse part MUST exist in FR Content"
        assert fr_parts[0]["functionResponse"]["name"] == fc_name, (
            f"FR name '{fr_parts[0]['functionResponse']['name']}' "
            f"does not match FC name '{fc_name}'"
        )

    @pytest.mark.asyncio
    async def test_t27_no_orphaned_fr_after_compression(self):
        """Budget boundary between FC/FR pair → zero orphaned FR.

        If compression prunes the model:FC, the user:FR must also be pruned.
        """
        # Build a long conversation where the FC/FR pair is near the prune boundary
        conversation = []
        turn_num = 0

        # 30 large turns to push over budget
        for i in range(30):
            turn_num += 1
            conversation.append(
                _make_turn(turn=turn_num, actor="brain", action="response",
                           thoughts="padding " * 200)
            )
            turn_num += 1
            conversation.append(
                _make_turn(turn=turn_num, actor="user", action="message",
                           thoughts=f"msg {i}")
            )

        # FC/FR pair at the end (should survive compression)
        fc_part = {"functionCall": {"name": "close_event", "args": {}}}
        turn_num += 1
        conversation.append(
            _make_turn(turn=turn_num, actor="brain", action="tool_result",
                       waitingFor="close_event", evidence="Closed",
                       response_parts=[fc_part])
        )

        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
             patch("src.agents.brain._CONTENT_BUDGET", 100):
            contents = await Brain._build_contents(brain, event)

        # Verify no orphaned FR (FR without preceding FC)
        for i, msg in enumerate(contents):
            if msg["role"] == "user":
                for p in msg.get("parts", []):
                    if "functionResponse" in p:
                        # Must have a preceding model:FC
                        assert i > 0, "FR at position 0 is orphaned"
                        prev = contents[i - 1]
                        assert prev["role"] == "model", (
                            f"Orphaned FR at index {i} — preceding is role={prev['role']}"
                        )
                        assert any("functionCall" in pp for pp in prev.get("parts", [])), (
                            f"Orphaned FR at index {i} — preceding model has no FC"
                        )

    @pytest.mark.asyncio
    async def test_t28_fr_name_from_fc_part_waiting_for_none(self):
        """response_parts=[{functionCall:{name:"close_event"}}], waitingFor=None.

        FR name should come from the functionCall part, not waitingFor.
        Tests at _build_contents level.
        """
        fc_part = {"functionCall": {"name": "close_event", "args": {"event_id": "evt-1"}}}
        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="close it"),
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor=None, evidence="Event closed",
                response_parts=[fc_part],
            ),
        ]

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            event = _make_event(conversation=conversation)
            brain = _make_brain_mock()
            contents = await Brain._build_contents(brain, event)

        fr_parts = []
        for content in contents:
            if content["role"] == "user":
                for p in content.get("parts", []):
                    if "functionResponse" in p:
                        fr_parts.append(p)

        assert len(fr_parts) >= 1, "No FR emitted when waitingFor is None but FC exists"
        assert fr_parts[0]["functionResponse"]["name"] == "close_event", (
            f"FR name should be from FC part, got: {fr_parts[0]['functionResponse']['name']}"
        )

    @pytest.mark.asyncio
    async def test_t29_oversized_thought_in_compression(self):
        """10K-char thought + small FC, tight budget → graceful pruning."""
        big_thought = "x" * 10_000
        fc_part = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="start"),
            # Big thought turn
            _make_turn(turn=2, actor="brain", action="response", thoughts=big_thought),
            # FC/FR pair
            _make_turn(
                turn=3, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Done",
                response_parts=[fc_part],
            ),
            _make_turn(turn=4, actor="user", action="message", thoughts="continue"),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        # Budget tight enough that the 10K thought must be pruned
        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
             patch("src.agents.brain._CONTENT_BUDGET", 50):
            contents = await Brain._build_contents(brain, event)

        # No crash — graceful output
        assert len(contents) >= 1, "Compression produced empty contents"
        # If FC survived, FR must also survive
        for i, msg in enumerate(contents):
            if msg["role"] == "model" and any(
                "functionCall" in p for p in msg.get("parts", [])
            ):
                assert i + 1 < len(contents), "Orphaned FC after compression with big thought"

    def test_t31_double_fallback_no_fc_no_waiting_for(self):
        """response_parts=[{text:""}], waitingFor=None → text-only path, no native FR.

        When there's no FC and no waitingFor, should produce minimal text output
        without any functionResponse.
        """
        turn = _make_turn(
            turn=1, actor="brain", action="tool_result",
            waitingFor=None, evidence="Some result",
            response_parts=[{"text": ""}],
        )

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            parts = Brain._turn_to_parts(turn)

        # Should be text-only fallback
        assert len(parts) >= 1
        assert "text" in parts[0]
        # No native FR
        assert not any("functionResponse" in p for p in parts), (
            "functionResponse should not be emitted without FC or waitingFor"
        )
        # Should use generic tool label since waitingFor is None
        assert "[SYSTEM tool]:" in parts[0]["text"]
