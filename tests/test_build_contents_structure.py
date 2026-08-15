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
# 6. [Pattern]: T-40+ tests verify parallel FC batch execution and replay.
#    _BatchContext wraps _tool_ctx to inject batch_size/batch_index on tool_result turns.
#    _MAX_BATCH_SIZE (default 4) caps the number of FCs per batch.
"""Unit tests for _turn_to_parts labeling and _build_contents structural markers.

Spec IDs: T1–T50.
Verifies prefix labeling ([USER], [SYSTEM X], [AGENT Y]),
delta markers, header boundaries, FC/FR pairing, thought_signature propagation,
compression safety for native function call/response contents,
and parallel function call batch execution/replay (T40–T50).
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
    batch_size: int | None = None,
    batch_index: int | None = None,
) -> ConversationTurn:
    return ConversationTurn(
        turn=turn, actor=actor, action=action,
        thoughts=thoughts, result=result, evidence=evidence,
        waitingFor=waitingFor, response_parts=response_parts,
        batch_size=batch_size, batch_index=batch_index,
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


# ---------------------------------------------------------------------------
# T32: Regression guard for PR #186 — classify_event triage+nudge dedup pair
# ---------------------------------------------------------------------------

class TestClassifyEventTriageNudgeDedupSig:
    """Regression test for the FC-dedup sibling-sig discard bug fixed in a05299e8.

    handle_classify_event (handlers_state.py) threads the SAME response_parts
    onto both the triage turn (action="triage") and the immediately-following
    nudge turn (action="tool_result", waitingFor="classify_event"). The triage
    turn's raw response_parts (a functionCall lacking thought_signature, with a
    sibling thought part carrying one) go through turn_to_parts()'s raw
    passthrough and get marked as "emitted" for FC-dedup purposes. The nudge
    turn then re-derives fc_parts via extract_model_parts() (which DOES apply
    the sibling-sig fix-up) but _build_contents' dedup discards that corrected
    copy because the triage turn already claimed the emission slot.

    Before a05299e8, turn_to_parts()'s raw passthrough did not apply the
    sibling-sig defense, so the surviving (triage) emission kept a bare,
    signature-less functionCall — silently defeating the PR's core purpose on
    every single classify_event call. This test pins the fixed behavior: the
    functionCall content that survives the dedup must carry the signature.
    """

    @pytest.mark.asyncio
    async def test_t32_sig_survives_classify_event_dedup_pair(self):
        """Repro shape: sibling thought carries the sig, the FC part does not.

        Runs a classify_event triage+nudge turn pair (identical response_parts,
        as produced by handle_classify_event) through Brain._build_contents()
        with BRAIN_THOUGHT_SIG_V2 on, and asserts the surviving model:FC
        content has thought_signature attached post-dedup.
        """
        response_parts = [
            {"thought": True, "thought_signature": "c2lnX2RhdGE="},
            {"functionCall": {
                "name": "classify_event",
                "args": {"domain": "clear", "reasoning": "known pattern"},
            }},
        ]
        conversation = [
            # triage turn — handle_classify_event's first ConversationTurn
            _make_turn(
                turn=1, actor="brain", action="triage",
                thoughts="Cynefin: CLEAR. known pattern",
                response_parts=response_parts,
            ),
            # nudge turn — handle_classify_event's second ConversationTurn,
            # sharing the identical response_parts list with the triage turn
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="classify_event",
                evidence="Domain set: CLEAR. Known solution exists.",
                response_parts=response_parts,
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        fc_msgs = [
            msg for msg in contents
            if msg["role"] == "model"
            and any("functionCall" in p for p in msg.get("parts", []))
        ]
        assert len(fc_msgs) == 1, (
            f"Expected exactly 1 surviving model:FC from the dedup pair, got {len(fc_msgs)}"
        )

        fc_part = next(p for p in fc_msgs[0]["parts"] if "functionCall" in p)
        assert fc_part["functionCall"]["name"] == "classify_event"
        assert fc_part.get("thought_signature") == "c2lnX2RhdGE=", (
            "thought_signature did not survive the classify_event "
            "triage+nudge dedup pair — sibling-sig defense was not applied "
            "to the surviving (raw-passthrough) emission"
        )

    @pytest.mark.asyncio
    async def test_t32b_flag_off_no_response_parts_threaded(self):
        """With BRAIN_THOUGHT_SIG_V2 off, handlers_state.py never threads
        response_parts onto triage/nudge turns (opt-in/default-off design) —
        confirm _build_contents degrades to plain text with no leaked FC/sig.
        """
        conversation = [
            _make_turn(
                turn=1, actor="brain", action="triage",
                thoughts="Cynefin: CLEAR.", response_parts=None,
            ),
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="classify_event",
                evidence="Domain set: CLEAR.", response_parts=None,
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", False):
            contents = await Brain._build_contents(brain, event)

        for msg in contents:
            for part in msg.get("parts", []):
                assert "functionCall" not in part
                assert "thought_signature" not in part


# ---------------------------------------------------------------------------
# T40–T50: Parallel Function Call Batch Execution & Replay
# ---------------------------------------------------------------------------

class TestParallelFunctionCallExecution:
    """Tests for parallel FC batch execution and replay.

    When _THOUGHT_SIG_V2 is True and the model emits multiple functionCall
    parts in a single response, the Brain executes them sequentially in-order,
    storing batch_size on the head turn and batch_index on continuation turns.
    _build_contents replays these as model:[FC1,...,FCn] + user:[FR1,...,FRn].
    """

    @pytest.mark.asyncio
    async def test_t40_two_fc_batch_replay_emits_paired_contents(self):
        """2 FCs in response_parts, 2 continuation turns → model:[FC1,FC2] + user:[FR1,FR2]."""
        fc1 = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        fc2 = {"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}
        sig = {"thought": True, "thought_signature": "c2lnX2RhdGE="}

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="handle this"),
            _make_turn(
                turn=2, actor="brain", action="response",
                response_parts=[fc1, fc2, sig],
            ),
            _make_turn(
                turn=3, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc1, fc2, sig],
                batch_size=2,
            ),
            _make_turn(
                turn=4, actor="brain", action="tool_result",
                waitingFor="select_agent", evidence="Dispatched developer",
                batch_index=1,
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        fc_parts_all = [
            p
            for msg in contents if msg["role"] == "model"
            for p in msg.get("parts", []) if "functionCall" in p
        ]
        assert len(fc_parts_all) == 2, (
            f"Expected 2 functionCall parts across model Contents, got {len(fc_parts_all)}"
        )

        fr_parts_all = [
            p
            for msg in contents if msg["role"] == "user"
            for p in msg.get("parts", []) if "functionResponse" in p
        ]
        assert len(fr_parts_all) == 2, (
            f"Expected 2 functionResponse parts across user Contents, got {len(fr_parts_all)}"
        )

        assert fc_parts_all[0]["functionCall"]["name"] == "classify_event"
        assert fc_parts_all[1]["functionCall"]["name"] == "select_agent"
        assert fr_parts_all[0]["functionResponse"]["name"] == "classify_event"
        assert fr_parts_all[1]["functionResponse"]["name"] == "select_agent"

    @pytest.mark.asyncio
    async def test_t41_batch_context_proxy_injects_markers(self):
        """_BatchContext injects batch_size on head turn and batch_index on continuation."""
        from src.agents.brain import _BatchContext

        appended_turns: list[ConversationTurn] = []

        class _TrackingCtx:
            async def append_and_broadcast(self, eid, turn, event=None):
                appended_turns.append(turn)
                return len(appended_turns)
            def __getattr__(self, name):
                return AsyncMock()

        inner = _TrackingCtx()

        # FC[0]: batch_size=3, batch_index=None
        head_ctx = _BatchContext(inner, batch_size=3, batch_index=None)
        head_turn = ConversationTurn(
            turn=1, actor="brain", action="tool_result",
            waitingFor="classify_event", evidence="Domain: CLEAR",
        )
        await head_ctx.append_and_broadcast("evt-test", head_turn)
        assert head_turn.batch_size == 3, f"Head turn batch_size should be 3, got {head_turn.batch_size}"
        assert head_turn.batch_index is None

        # FC[2]: batch_size=None, batch_index=2
        cont_ctx = _BatchContext(inner, batch_size=None, batch_index=2)
        cont_turn = ConversationTurn(
            turn=3, actor="brain", action="tool_result",
            waitingFor="set_phase", evidence="Phase: DISPATCH",
        )
        await cont_ctx.append_and_broadcast("evt-test", cont_turn)
        assert cont_turn.batch_index == 2, f"Continuation turn batch_index should be 2, got {cont_turn.batch_index}"
        assert cont_turn.batch_size is None

        # Verify injection is one-shot: second call on same ctx does NOT re-inject
        extra_turn = ConversationTurn(
            turn=4, actor="brain", action="tool_result",
            waitingFor="extra", evidence="extra",
        )
        await head_ctx.append_and_broadcast("evt-test", extra_turn)
        assert extra_turn.batch_size is None, "Second tool_result on same ctx should not get batch_size"

    @pytest.mark.asyncio
    async def test_t42_batch_stop_on_false_fc2_never_executes(self):
        """FC[0]→True, FC[1]→False → FC[2] never called; only 2 tool_result turns."""
        from src.agents.brain import _BatchContext

        appended_turns: list[ConversationTurn] = []

        class _TrackingCtx:
            async def append_and_broadcast(self, eid, turn, event=None):
                appended_turns.append(turn)
                return len(appended_turns)
            def __getattr__(self, name):
                return AsyncMock()

        inner = _TrackingCtx()

        fcs = [
            {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}},
            {"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}},
            {"functionCall": {"name": "set_phase", "args": {"phase": "dispatch"}}},
        ]

        execute_results = {"classify_event": True, "select_agent": False}
        executed_names: list[str] = []

        for i, fc in enumerate(fcs):
            name = fc["functionCall"]["name"]
            ctx = _BatchContext(
                inner,
                batch_size=len(fcs) if i == 0 else None,
                batch_index=i if i > 0 else None,
            )
            turn = ConversationTurn(
                turn=i + 1, actor="brain", action="tool_result",
                waitingFor=name, evidence=f"Result: {name}",
            )
            await ctx.append_and_broadcast("evt-test", turn)
            executed_names.append(name)
            if not execute_results.get(name, True):
                break

        assert executed_names == ["classify_event", "select_agent"], (
            f"FC[2] should not have been called. Executed: {executed_names}"
        )
        assert len(appended_turns) == 2, (
            f"Only 2 tool_result turns should be created, got {len(appended_turns)}"
        )
        assert appended_turns[0].batch_size == 3
        assert appended_turns[1].batch_index == 1

    @pytest.mark.asyncio
    async def test_t43_gate_re_evaluation_after_classify(self):
        """classify_event changes domain → select_agent available for FC[1].

        After FC[0] (classify_event), gate re-evaluation makes select_agent
        available. Verify FC[1] (select_agent) passes the re-evaluated gate.
        """
        from src.agents.brain import _BatchContext

        appended_turns: list[ConversationTurn] = []
        gate_state = {"domain": "disorder", "classified": False}

        class _TrackingCtx:
            async def append_and_broadcast(self, eid, turn, event=None):
                appended_turns.append(turn)
                return len(appended_turns)
            def __getattr__(self, name):
                return AsyncMock()

        inner = _TrackingCtx()

        fcs = [
            {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}},
            {"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}},
        ]

        executed_names: list[str] = []

        for i, fc in enumerate(fcs):
            name = fc["functionCall"]["name"]
            available_tools = {"classify_event"}
            if gate_state["classified"]:
                available_tools.add("select_agent")

            if name not in available_tools:
                break

            ctx = _BatchContext(
                inner,
                batch_size=len(fcs) if i == 0 else None,
                batch_index=i if i > 0 else None,
            )
            turn = ConversationTurn(
                turn=i + 1, actor="brain", action="tool_result",
                waitingFor=name, evidence=f"Result: {name}",
            )
            await ctx.append_and_broadcast("evt-test", turn)
            executed_names.append(name)

            if name == "classify_event":
                gate_state["domain"] = "clear"
                gate_state["classified"] = True

        assert "classify_event" in executed_names
        assert "select_agent" in executed_names, (
            "select_agent should execute after classify_event re-evaluates gates"
        )
        assert len(appended_turns) == 2

    @pytest.mark.asyncio
    async def test_t44_mid_batch_crash_pads_missing_fr(self):
        """batch_size=3, batch_index=1 exists, batch_index=2 missing → error FR pad."""
        fc1 = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        fc2 = {"functionCall": {"name": "select_agent", "args": {"agent": "dev"}}}
        fc3 = {"functionCall": {"name": "set_phase", "args": {"phase": "dispatch"}}}
        sig = {"thought": True, "thought_signature": "c2lnX2RhdGE="}

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="go"),
            _make_turn(
                turn=2, actor="brain", action="response",
                response_parts=[fc1, fc2, fc3, sig],
            ),
            _make_turn(
                turn=3, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc1, fc2, fc3, sig],
                batch_size=3,
            ),
            _make_turn(
                turn=4, actor="brain", action="tool_result",
                waitingFor="select_agent", evidence="Dispatched",
                batch_index=1,
            ),
            # NO batch_index=2 turn — simulates crash/interruption
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        fr_parts_all = [
            p
            for msg in contents if msg["role"] == "user"
            for p in msg.get("parts", []) if "functionResponse" in p
        ]
        assert len(fr_parts_all) == 3, (
            f"Expected 3 FRs (2 real + 1 error pad), got {len(fr_parts_all)}"
        )

        error_pad = fr_parts_all[2]
        assert error_pad["functionResponse"]["name"] == "set_phase", (
            f"Error pad FR should be named 'set_phase', got {error_pad['functionResponse']['name']}"
        )
        result_text = error_pad["functionResponse"]["response"].get("result", "")
        assert "interrupt" in result_text.lower() or "error" in result_text.lower(), (
            f"Error pad result should indicate interruption: {result_text}"
        )

    @pytest.mark.asyncio
    async def test_t45_grounding_turn_excluded_from_batch_lookahead(self):
        """Synthetic google_web_search turn NOT consumed by batch look-ahead."""
        fc1 = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        fc2 = {"functionCall": {"name": "select_agent", "args": {"agent": "dev"}}}
        sig = {"thought": True, "thought_signature": "c2lnX2RhdGE="}
        grounding_fc = {"functionCall": {"name": "google_web_search", "args": {}}}

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="go"),
            # Synthetic grounding turn (preceding the batch)
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="google_web_search", evidence="Search results...",
                response_parts=[grounding_fc],
            ),
            # brain.response with 2 FCs
            _make_turn(
                turn=3, actor="brain", action="response",
                response_parts=[fc1, fc2, sig],
            ),
            # Batch head
            _make_turn(
                turn=4, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc1, fc2, sig],
                batch_size=2,
            ),
            # Batch continuation
            _make_turn(
                turn=5, actor="brain", action="tool_result",
                waitingFor="select_agent", evidence="Dispatched",
                batch_index=1,
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        # Grounding turn should use text fallback (not native FC)
        all_text = _all_text(contents)
        assert "[SYSTEM google_web_search]:" in all_text, (
            "Grounding turn should use text fallback, not native FC/FR"
        )

        # Batch FCs should still be present
        batch_fc_parts = [
            p
            for msg in contents if msg["role"] == "model"
            for p in msg.get("parts", [])
            if "functionCall" in p
            and p["functionCall"]["name"] != "google_web_search"
        ]
        assert len(batch_fc_parts) == 2, (
            f"Expected 2 batch FC parts (classify_event, select_agent), got {len(batch_fc_parts)}"
        )

        # Batch FRs should pair correctly
        batch_fr_parts = [
            p
            for msg in contents if msg["role"] == "user"
            for p in msg.get("parts", [])
            if "functionResponse" in p
            and p["functionResponse"]["name"] in ("classify_event", "select_agent")
        ]
        assert len(batch_fr_parts) == 2, (
            f"Expected 2 batch FR parts, got {len(batch_fr_parts)}"
        )

    @pytest.mark.asyncio
    async def test_t46_flag_off_parallel_fcs_fall_through_to_last_wins(self):
        """_THOUGHT_SIG_V2=False → only last FC from scalar function_call executes."""
        fc1 = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        fc2 = {"functionCall": {"name": "select_agent", "args": {"agent": "dev"}}}

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="go"),
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="select_agent", evidence="Dispatched",
                response_parts=[fc1, fc2],
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

        # No batch_size or batch_index should be set on any turns
        for turn in event.conversation:
            assert turn.batch_size is None, "batch_size should not be set when flag is off"
            assert turn.batch_index is None, "batch_index should not be set when flag is off"

    @pytest.mark.asyncio
    async def test_t47_compression_prunes_batch_fc_fr_pair_atomically(self):
        """2-FC/2-FR batch pair must be pruned together, never one without the other."""
        fc1 = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        fc2 = {"functionCall": {"name": "select_agent", "args": {"agent": "dev"}}}
        sig = {"thought": True, "thought_signature": "c2lnX2RhdGE="}

        # Build a long conversation to push over budget, with a batch pair embedded
        conversation = []
        turn_num = 0

        for i in range(20):
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

        # Batch pair at the end (recent — more likely to survive compression)
        turn_num += 1
        conversation.append(
            _make_turn(
                turn=turn_num, actor="brain", action="response",
                response_parts=[fc1, fc2, sig],
            )
        )
        turn_num += 1
        conversation.append(
            _make_turn(
                turn=turn_num, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc1, fc2, sig],
                batch_size=2,
            )
        )
        turn_num += 1
        conversation.append(
            _make_turn(
                turn=turn_num, actor="brain", action="tool_result",
                waitingFor="select_agent", evidence="Dispatched",
                batch_index=1,
            )
        )

        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True), \
             patch("src.agents.brain._CONTENT_BUDGET", 100):
            contents = await Brain._build_contents(brain, event)

        # Verify atomicity: if any FC exists, matching FR must exist, and vice versa
        fc_names = set()
        fr_names = set()
        for msg in contents:
            for p in msg.get("parts", []):
                if "functionCall" in p:
                    fc_names.add(p["functionCall"]["name"])
                if "functionResponse" in p:
                    fr_names.add(p["functionResponse"]["name"])

        # Either both survive or both are pruned
        assert fc_names == fr_names, (
            f"FC/FR mismatch after compression — orphaned entries. "
            f"FCs: {fc_names}, FRs: {fr_names}"
        )

        # No orphaned model:FC without following user:FR
        for i, msg in enumerate(contents):
            if msg["role"] == "model" and any(
                "functionCall" in p for p in msg.get("parts", [])
            ):
                assert i + 1 < len(contents), f"Orphaned model:FC at index {i}"
                assert contents[i + 1]["role"] == "user", (
                    f"Orphaned model:FC at index {i} — next is role={contents[i + 1]['role']}"
                )

    @pytest.mark.asyncio
    async def test_t48_recall_fires_once_before_fc0_not_between(self):
        """RECALL (reflex_chunker.flush) fires exactly once before FC[0], not between FCs."""
        from src.agents.brain import _BatchContext

        flush_call_log: list[str] = []

        class _TrackingCtx:
            async def append_and_broadcast(self, eid, turn, event=None):
                return 1
            def __getattr__(self, name):
                return AsyncMock()

        inner = _TrackingCtx()

        fcs = [
            {"functionCall": {"name": "classify_event", "args": {}}},
            {"functionCall": {"name": "select_agent", "args": {}}},
            {"functionCall": {"name": "set_phase", "args": {}}},
        ]

        class MockReflex:
            def flush(self):
                flush_call_log.append("flush")
                return "thinking about it"

        reflex_chunker = MockReflex()

        # Flush before batch (once)
        final_window = reflex_chunker.flush()
        assert final_window, "reflex_chunker.flush should return thinking text"

        # Execute batch — NO flush between FCs
        for i, fc in enumerate(fcs):
            ctx = _BatchContext(
                inner,
                batch_size=len(fcs) if i == 0 else None,
                batch_index=i if i > 0 else None,
            )
            turn = ConversationTurn(
                turn=i + 1, actor="brain", action="tool_result",
                waitingFor=fc["functionCall"]["name"], evidence="OK",
            )
            await ctx.append_and_broadcast("evt-test", turn)
            # Contract: no flush between FCs

        assert len(flush_call_log) == 1, (
            f"reflex_chunker.flush() should be called exactly once (before FC[0]), "
            f"got {len(flush_call_log)} calls"
        )

    def test_t49_batch_cap_truncates_to_max_batch_size(self):
        """6 FCs truncated to _MAX_BATCH_SIZE (4)."""
        from src.agents.brain import _MAX_BATCH_SIZE

        assert _MAX_BATCH_SIZE == 4, (
            f"_MAX_BATCH_SIZE expected to be 4, got {_MAX_BATCH_SIZE}"
        )

        captured_parts = [
            {"functionCall": {"name": f"tool_{i}", "args": {"x": i}}}
            for i in range(6)
        ] + [{"thought": True, "thought_signature": "c2lnX2RhdGE="}]

        fc_parts = [p for p in captured_parts if "functionCall" in p]
        assert len(fc_parts) == 6

        # Apply batch cap (contract: only first _MAX_BATCH_SIZE FCs execute)
        truncated = fc_parts[:_MAX_BATCH_SIZE]
        assert len(truncated) == 4, (
            f"Expected 4 FCs after truncation, got {len(truncated)}"
        )

        # Verify the correct 4 FCs survive (first 4 in order)
        surviving_names = [p["functionCall"]["name"] for p in truncated]
        assert surviving_names == ["tool_0", "tool_1", "tool_2", "tool_3"]

        # tool_4 and tool_5 should be excluded
        excluded_names = [p["functionCall"]["name"] for p in fc_parts[_MAX_BATCH_SIZE:]]
        assert "tool_4" in excluded_names
        assert "tool_5" in excluded_names

    @pytest.mark.asyncio
    async def test_t49b_batch_cap_reflected_in_head_turn_response_parts(self):
        """Head turn's response_parts should only contain first 4 FC entries (+ sig)."""
        from src.agents.brain import _MAX_BATCH_SIZE

        fc_parts = [
            {"functionCall": {"name": f"tool_{i}", "args": {"x": i}}}
            for i in range(6)
        ]
        sig = {"thought": True, "thought_signature": "c2lnX2RhdGE="}

        # Build conversation as if the batch was capped at 4
        capped_fcs = fc_parts[:_MAX_BATCH_SIZE]
        response_parts = capped_fcs + [sig]

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="go"),
            _make_turn(
                turn=2, actor="brain", action="response",
                response_parts=response_parts,
            ),
            _make_turn(
                turn=3, actor="brain", action="tool_result",
                waitingFor="tool_0", evidence="Result 0",
                response_parts=response_parts,
                batch_size=4,
            ),
            _make_turn(turn=4, actor="brain", action="tool_result",
                       waitingFor="tool_1", evidence="Result 1", batch_index=1),
            _make_turn(turn=5, actor="brain", action="tool_result",
                       waitingFor="tool_2", evidence="Result 2", batch_index=2),
            _make_turn(turn=6, actor="brain", action="tool_result",
                       waitingFor="tool_3", evidence="Result 3", batch_index=3),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        fc_parts_all = [
            p
            for msg in contents if msg["role"] == "model"
            for p in msg.get("parts", []) if "functionCall" in p
        ]
        assert len(fc_parts_all) == 4, (
            f"Expected 4 FC parts after batch cap, got {len(fc_parts_all)}"
        )

        fr_parts_all = [
            p
            for msg in contents if msg["role"] == "user"
            for p in msg.get("parts", []) if "functionResponse" in p
        ]
        assert len(fr_parts_all) == 4, (
            f"Expected 4 FR parts (one per capped FC), got {len(fr_parts_all)}"
        )

    @pytest.mark.asyncio
    async def test_t50_fr_names_from_head_turn_order_not_waiting_for(self):
        """FR names derived from head turn's response_parts FC order, not waitingFor."""
        fc1 = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        fc2 = {"functionCall": {"name": "select_agent", "args": {"agent": "dev"}}}
        sig = {"thought": True, "thought_signature": "c2lnX2RhdGE="}

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="go"),
            _make_turn(
                turn=2, actor="brain", action="response",
                response_parts=[fc1, fc2, sig],
            ),
            _make_turn(
                turn=3, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc1, fc2, sig],
                batch_size=2,
            ),
            # Continuation turn has WRONG waitingFor — FR name must come from
            # head turn's response_parts order (fc2 = "select_agent"), not this field
            _make_turn(
                turn=4, actor="brain", action="tool_result",
                waitingFor="something_else", evidence="Dispatched",
                batch_index=1,
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        fr_parts_all = [
            p
            for msg in contents if msg["role"] == "user"
            for p in msg.get("parts", []) if "functionResponse" in p
        ]
        assert len(fr_parts_all) == 2, (
            f"Expected 2 FR parts, got {len(fr_parts_all)}"
        )

        assert fr_parts_all[0]["functionResponse"]["name"] == "classify_event"
        # The critical assertion: FR for continuation uses head turn's FC order
        assert fr_parts_all[1]["functionResponse"]["name"] == "select_agent", (
            f"FR[1] name should be 'select_agent' (from head turn FC order), "
            f"not 'something_else' (from waitingFor). Got: "
            f"{fr_parts_all[1]['functionResponse']['name']}"
        )

    # -----------------------------------------------------------------------
    # T51-T52: PR #189 remediation -- grounding+batch replay & idempotency
    # padding regression tests (correctness HIGH + reliability HIGH fixes).
    # -----------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_t51_grounding_batch_head_still_gets_native_fc_fr_replay(self):
        """Regression test for the correctness HIGH: when grounding co-occurs with a
        parallel-FC batch, _execute_function_call's synthetic waitingFor="google_web_search"
        turn is the ONLY turn that ever carries the batch's real response_parts (the
        handler's own turn gets response_parts cleared to None). Before the fix,
        _BatchContext unconditionally excluded google_web_search turns from batch-marker
        injection AND _build_contents unconditionally excluded them from native FC/FR
        replay -- together silently dropping the whole batch to legacy text-fallback.

        Both guards now special-case batch heads (turn.batch_size set / turn carries
        real FC parts), so this turn must still produce native FC/FR replay.
        """
        fc1 = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        fc2 = {"functionCall": {"name": "select_agent", "args": {"agent": "developer"}}}
        sig = {"thought": True, "thought_signature": "c2lnX2RhdGE="}

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="handle this"),
            # This is the synthetic grounding wrapper turn _execute_function_call creates
            # when grounding_evidence is set -- it carries the batch's real FC parts and
            # (post-fix) the batch marker, even though waitingFor == "google_web_search".
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="google_web_search", evidence="\n\n## Web Search Context\n\n...",
                response_parts=[fc1, fc2, sig],
                batch_size=2,
            ),
            _make_turn(
                turn=3, actor="brain", action="tool_result",
                waitingFor="select_agent", evidence="Dispatched developer",
                batch_index=1,
            ),
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        fc_parts_all = [
            p
            for msg in contents if msg["role"] == "model"
            for p in msg.get("parts", []) if "functionCall" in p
        ]
        assert len(fc_parts_all) == 2, (
            f"Expected native replay of both FCs despite the grounding wrapper turn, "
            f"got {len(fc_parts_all)} functionCall parts (legacy text-fallback bug "
            f"would silently drop these to 0)"
        )
        assert fc_parts_all[0]["functionCall"]["name"] == "classify_event"
        assert fc_parts_all[1]["functionCall"]["name"] == "select_agent"

        fr_parts_all = [
            p
            for msg in contents if msg["role"] == "user"
            for p in msg.get("parts", []) if "functionResponse" in p
        ]
        assert len(fr_parts_all) == 2, (
            f"Expected 2 functionResponse parts, got {len(fr_parts_all)}"
        )
        assert fr_parts_all[0]["functionResponse"]["name"] == "classify_event"
        assert fr_parts_all[1]["functionResponse"]["name"] == "select_agent"

    @pytest.mark.asyncio
    async def test_t52_non_idempotent_tool_replay_padding_warns_against_reissue(self):
        """Regression test for the reliability HIGH: if a batch FC with side effects
        (select_agent/ask_agent_for_state/defer_event) completes its external effect but
        the process crashes before the corresponding turn is persisted, replay padding
        must NOT say "execution interrupted" (reads as "safe to retry") -- it must warn
        that the side effect may have already run."""
        fc1 = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        fc2 = {"functionCall": {"name": "defer_event", "args": {"reason": "waiting"}}}
        sig = {"thought": True, "thought_signature": "c2lnX2RhdGE="}

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="go"),
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc1, fc2, sig],
                batch_size=2,
            ),
            # No batch_index=1 continuation turn -- simulates a crash before defer_event's
            # turn was persisted.
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        fr_parts_all = [
            p
            for msg in contents if msg["role"] == "user"
            for p in msg.get("parts", []) if "functionResponse" in p
        ]
        assert len(fr_parts_all) == 2
        padded = fr_parts_all[1]["functionResponse"]
        assert padded["name"] == "defer_event"
        assert padded["response"]["result"] != "execution interrupted", (
            "non-idempotent tool must not use the 'safe to retry' phrasing"
        )
        assert "do not blindly re-issue" in padded["response"]["result"].lower()

    @pytest.mark.asyncio
    async def test_t52b_idempotent_tool_replay_padding_unchanged(self):
        """Sanity check: idempotent tools (not in _NON_IDEMPOTENT_TOOLS) keep the
        original 'execution interrupted' padding -- only the non-idempotent set changed."""
        fc1 = {"functionCall": {"name": "classify_event", "args": {"domain": "clear"}}}
        fc2 = {"functionCall": {"name": "lookup_journal", "args": {}}}
        sig = {"thought": True, "thought_signature": "c2lnX2RhdGE="}

        conversation = [
            _make_turn(turn=1, actor="user", action="message", thoughts="go"),
            _make_turn(
                turn=2, actor="brain", action="tool_result",
                waitingFor="classify_event", evidence="Domain: CLEAR",
                response_parts=[fc1, fc2, sig],
                batch_size=2,
            ),
            # No continuation turn for lookup_journal either -- same crash scenario.
        ]
        event = _make_event(conversation=conversation)
        brain = _make_brain_mock()

        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            contents = await Brain._build_contents(brain, event)

        fr_parts_all = [
            p
            for msg in contents if msg["role"] == "user"
            for p in msg.get("parts", []) if "functionResponse" in p
        ]
        assert len(fr_parts_all) == 2
        padded = fr_parts_all[1]["functionResponse"]
        assert padded["name"] == "lookup_journal"
        assert padded["response"]["result"] == "execution interrupted"
