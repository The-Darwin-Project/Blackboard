# BlackBoard/tests/test_prefix_cache_stability.py
# @ai-rules:
# 1. [Constraint]: Executable 4-layer ATDD fitness & seam suite for VMER-2450 Step 9 Probe & Step 11 (T-37 + Section 6c).
# 2. [Pattern]: Layer 1 (Domain Intent) -> Layer 2 (DSL replay/wire-diff helpers) -> Layer 3 (Protocol drivers:
#    fakeredis BlackboardState, real BrainSkillLoader, real GeminiAdapter._convert_tools/_convert_structured) -> Layer 4 (SUT).
# 3. [Boundary]: Pure in-process wire serialization probe -- zero live Vertex AI / network calls.
# 4. [Invariant]: Asserts 100% byte-equality of wire tools, Global Core SI, thinking_level='high', Turn-0 anchor
#    across mutations and Brain pod restart L1 cache clears, and within-epoch wire history across a 25-turn replay
#    with exactly ONE controlled prefix mutation at the conv_len==21 K=10 decay epoch snap.
"""Within-epoch Gemini wire prefix byte-equality fitness suite and hexagonal seam guards (VMER-2450).

Spec IDs: T-37, Step 9 25-turn Complex Probe, Section 6c Fitness & Seam Guards.
"""
from __future__ import annotations

import ast
import asyncio
import json
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import AsyncMock

import fakeredis.aioredis
import pytest

from src.agents.brain import Brain
from src.agents.brain_skill_loader import BrainSkillLoader
from src.agents.llm.gemini_client import GeminiAdapter, _SYNTHETIC_BRIDGE_TEXT
from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
from src.agents.prefix_builder import build_global_core_si, canonical_wire_tools
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)
from src.state.blackboard import BlackboardState

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SKILLS_DIR = _REPO_ROOT / "src" / "agents" / "brain_skills"


# ---------------------------------------------------------------------------
# Layer 2 & 3: DSL Helpers & In-Memory Wire Serialization Driver
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _WireTurnSnapshot:
    step: int
    label: str
    conv_len: int
    phase: str
    domain: str
    tools_bytes: str
    si_bytes: bytes
    thinking_level: str
    max_output_tokens: int
    anchor_part0_bytes: str
    history_msgs: tuple[str, ...]
    overlay_texts: tuple[str, ...]
    decayed_count: int
    tail_text: str


def _serialize_part(part) -> str:
    return json.dumps(part.model_dump(mode="json", exclude_none=True), sort_keys=True, separators=(",", ":"))


def _serialize_content(content) -> str:
    return json.dumps(content.model_dump(mode="json", exclude_none=True), sort_keys=True, separators=(",", ":"))


def _flatten_wire_parts(history_msgs: tuple[str, ...]) -> list[tuple[str, str]]:
    """Flatten serialized wire Content messages into an ordered (role, canonical_part_json) stream."""
    out: list[tuple[str, str]] = []
    for m_json in history_msgs:
        msg = json.loads(m_json)
        role = msg["role"]
        for part in msg.get("parts", []):
            out.append((role, json.dumps(part, sort_keys=True, separators=(",", ":"))))
    return out


def _is_fr_part(part) -> bool:
    return getattr(part, "function_response", None) is not None


def _extract_wire_history_prefix(wire_contents: list) -> tuple[tuple[str, ...], str]:
    """Strip ONLY the volatile trailing <event_state> part (and any volatile bridge preceding it).

    Returns (canonical_json_messages, tail_text) so consecutive turns can be compared for exact
    byte-equality of wire_contents[0..k-1] without false diffs from the volatile tail.
    """
    assert wire_contents, "wire_contents must be non-empty"
    last = wire_contents[-1]
    assert last.role == "user", f"wire_contents must end with role='user', got {last.role!r}"
    assert last.parts, "final user Content must contain parts"
    tail_text = str(getattr(last.parts[-1], "text", "") or "")
    assert tail_text.lstrip().startswith("<event_state>"), (
        f"Expected trailing volatile <event_state> part, got: {tail_text[:120]!r}"
    )

    if len(last.parts) > 1:
        trimmed_last = last.model_copy(update={"parts": list(last.parts[:-1])})
        history_contents = list(wire_contents[:-1]) + [trimmed_last]
    else:
        history_contents = list(wire_contents[:-1])
        # When trailing <event_state> immediately followed a functionResponse user turn,
        # GeminiAdapter._append_user_turn inserted a volatile synthetic model bridge strictly
        # before <event_state>. Strip that volatile bridge so prefix comparison measures history.
        if (
            len(history_contents) >= 2
            and history_contents[-1].role == "model"
            and len(history_contents[-1].parts or []) == 1
            and getattr(history_contents[-1].parts[0], "text", None) == _SYNTHETIC_BRIDGE_TEXT
            and history_contents[-2].role == "user"
            and any(_is_fr_part(p) for p in (history_contents[-2].parts or []))
        ):
            history_contents = history_contents[:-1]

    return tuple(_serialize_content(c) for c in history_contents), tail_text


def _assert_gemini_wire_alternation(wire_contents: list, label: str) -> None:
    """Verify strict Gemini wire protocol invariants on every serialized turn."""
    for idx in range(len(wire_contents)):
        msg = wire_contents[idx]
        if idx > 0:
            assert msg.role != wire_contents[idx - 1].role, (
                f"[{label}] Adjacent same-role wire messages at index {idx}: {msg.role!r}"
            )
        if msg.role == "user":
            has_fr = any(_is_fr_part(p) for p in (msg.parts or []))
            has_non_fr = any(not _is_fr_part(p) for p in (msg.parts or []))
            assert not (has_fr and has_non_fr), (
                f"[{label}] User wire message at index {idx} mixes functionResponse and non-FR parts"
            )


def _make_fc_turn(
    turn_num: int,
    *,
    tool_name: str,
    args: dict,
    action: str = "tool_result",
    result_text: str = "ok",
    thoughts: str | None = None,
    batch_size: int | None = None,
    batch_index: int | None = None,
    extra_fcs: list[dict] | None = None,
) -> ConversationTurn:
    fc_parts = [{"functionCall": {"name": tool_name, "args": args}}]
    if extra_fcs:
        fc_parts.extend(extra_fcs)
    return ConversationTurn(
        turn=turn_num,
        actor="brain",
        action=action,
        waitingFor=tool_name,
        thoughts=thoughts if thoughts is not None else result_text,
        result=result_text,
        response_parts=fc_parts if batch_index is None else None,
        batch_size=batch_size,
        batch_index=batch_index,
    )


def _make_agent_result_turn(turn_num: int, *, actor: str = "sysadmin", payload: str) -> ConversationTurn:
    return ConversationTurn(
        turn=turn_num,
        actor=actor,
        action="result",
        result=payload,
    )


def _make_probe_brain() -> tuple[Brain, BlackboardState, fakeredis.aioredis.FakeRedis, GeminiAdapter]:
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    bb = BlackboardState(redis)
    brain = Brain(blackboard=bb, agents={})
    brain.provider = "gemini"
    brain.model_name = "gemini-4-neon"
    brain.max_output_tokens = 65536
    brain._skill_loader = BrainSkillLoader(str(_SKILLS_DIR), include_generated_map=True)
    brain._progressive_skills = True
    brain._skills_version = "probe-v1"
    brain._skills_reload_lock = asyncio.Lock()
    brain._get_journal_cached = AsyncMock(return_value=[])

    adapter = GeminiAdapter.__new__(GeminiAdapter)
    adapter._model_name = "gemini-4-neon"
    adapter._tracker = None
    return brain, bb, redis, adapter


def _make_multiphase_event() -> EventDocument:
    ev = EventEvidence(
        display_text="MR !42 pipeline failed on unit-tests in payments-api",
        source_type="headhunter",
        domain="disorder",
        severity="warning",
        gitlab_context={
            "mr_title": "Bump payments-api dependency to 2.4.1",
            "source_branch": "feat/payments-bump",
            "pipeline_id": 10042,
            "pipeline_status": "failed",
            "maintainer": {"emails": ["alice@redhat.com"]},
        },
    )
    return EventDocument(
        id="evt-wire-probe-25",
        source="headhunter",
        service="payments-api",
        subject_type="service",
        status=EventStatus.ACTIVE,
        brain_phase="triage",
        event=EventInput(
            reason="Headhunter detected failing MR !42",
            evidence=ev,
            timeDate="2026-11-23T10:00:00Z",
        ),
        conversation=[],
    )


async def _capture_wire_snapshot(
    step: int,
    label: str,
    brain: Brain,
    event: EventDocument,
    adapter: GeminiAdapter,
    *,
    brain_has_classified: bool,
    domain: str,
) -> _WireTurnSnapshot:
    context_flags = {
        "turn_count": len(event.conversation),
        "source": event.source,
        "service": event.service,
        "is_waiting": False,
        "has_agent_result": any(t.action == "result" and t.actor != "brain" for t in event.conversation),
        "last_is_user": False,
        "has_related": False,
        "has_recent_closed": False,
        "has_graph_edges": False,
        "has_aligner_turns": False,
        "brain_has_classified": brain_has_classified,
        "event_domain": domain,
        "domain_confidence": "explicit" if brain_has_classified else "default",
        "has_slack_participant": False,
        "is_intermediate": False,
        "has_pending_huddle": False,
    }
    active_phases = brain._match_phases(event, context_flags)
    si = await brain._build_system_prompt(event, active_phases, context_flags)
    thinking_level, _temp, max_tokens = brain._resolve_llm_params(active_phases, domain=domain)
    wire_tools = canonical_wire_tools(BRAIN_TOOL_SCHEMAS)
    raw_contents = await brain._build_contents(
        event,
        context_cache=dict(context_flags),
        terminal_prompt="Proceed with the current operational phase.",
    )

    sdk_tool = adapter._convert_tools(wire_tools)
    tools_bytes = json.dumps(sdk_tool.model_dump(mode="json", exclude_none=True), sort_keys=True, separators=(",", ":"))
    wire_contents = adapter._convert_structured(raw_contents)
    _assert_gemini_wire_alternation(wire_contents, label)

    anchor_part0_bytes = _serialize_part(wire_contents[0].parts[0])
    history_msgs, tail_text = _extract_wire_history_prefix(wire_contents)
    overlay_texts = tuple(
        str(p.get("text", ""))
        for msg in raw_contents[:-1]
        for p in msg.get("parts", [])
        if isinstance(p, dict) and str(p.get("text", "")).lstrip().startswith("<skill_overlay>")
    )
    decayed_count = sum(m.count("<blackboard_evidence_reference") for m in history_msgs)

    return _WireTurnSnapshot(
        step=step,
        label=label,
        conv_len=len(event.conversation),
        phase=event.brain_phase or "triage",
        domain=domain,
        tools_bytes=tools_bytes,
        si_bytes=si.encode("utf-8"),
        thinking_level=thinking_level,
        max_output_tokens=max_tokens,
        anchor_part0_bytes=anchor_part0_bytes,
        history_msgs=history_msgs,
        overlay_texts=overlay_texts,
        decayed_count=decayed_count,
        tail_text=tail_text,
    )


def _assert_no_forbidden_imports(file_path: Path, forbidden_prefixes: tuple[str, ...]) -> None:
    """AST import guard: fails if any runtime import (outside TYPE_CHECKING) hits forbidden prefixes."""
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.If):
            test = node.test
            if (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
                isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
            ):
                continue
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    for prefix in forbidden_prefixes:
                        assert not (alias.name == prefix or alias.name.startswith(f"{prefix}.")), (
                            f"{file_path.name} imports forbidden module {alias.name!r}"
                        )
            elif isinstance(child, ast.ImportFrom):
                mod = child.module or ""
                for prefix in forbidden_prefixes:
                    assert not (mod == prefix or mod.startswith(f"{prefix}.")), (
                        f"{file_path.name} imports from forbidden module {mod!r}"
                    )


# ---------------------------------------------------------------------------
# Layer 1: T-37 & Step 9 25-Turn Multi-Phase Wire Byte-Equality Probe
# ---------------------------------------------------------------------------

class TestT37WithinEpochWirePrefixStability:
    """T-37 + Step 9 Complex Probe: 25-turn multi-phase wire byte-equality audit."""

    @pytest.mark.asyncio
    async def test_t37_25_turn_multiphase_wire_byte_equality_and_single_epoch_snap(self, monkeypatch):
        """Given a 25-turn multi-phase event (triage -> dispatch -> verify -> close) crossing
        conv_len == 21 first K=10 decay snap, with batch classify_event, refresh_gitlab_context
        live evidence mutation, sticky note addition, rejected [GATE] transition, and simulated
        Brain pod restart clearing L1 _frozen_anchors while backed by fakeredis BlackboardState,
        When serialized through GeminiAdapter._convert_tools and _convert_structured at every turn,
        Then wire tools, Global Core SI, thinking_level='high', and Turn-0 anchor are 100%
        byte-identical across all 25 turns, historical wire prefix wire_contents[0..k-1] shifts
        ONLY ONCE at conv_len == 21 (zero diffs within epochs 0..20 and 21..25), and post-FR
        <skill_overlay> anchors append cleanly without mutating earlier messages."""
        monkeypatch.delenv("BRAIN_DECAY_EPOCH_SIZE", raising=False)
        monkeypatch.setattr("src.agents.brain._THOUGHT_SIG_V2", True)
        brain, bb, redis, adapter = _make_probe_brain()
        event = _make_multiphase_event()
        await bb.redis.set(f"darwin:event:{event.id}", event.model_dump_json())

        snaps: list[_WireTurnSnapshot] = []
        classified = False
        domain = "disorder"
        next_turn_num = 1

        async def _record(label: str) -> _WireTurnSnapshot:
            snap = await _capture_wire_snapshot(
                len(snaps),
                label,
                brain,
                event,
                adapter,
                brain_has_classified=classified,
                domain=domain,
            )
            snaps.append(snap)
            return snap

        # Turn 0 (conv_len=0): initial triage anchor persisted to fakeredis SSOT
        await _record("turn0-triage-init")
        assert await redis.exists(f"darwin:event:{event.id}:anchor") == 1

        # Turn 1 (conv_len=2): 2-FC parallel batch [classify_event(complicated), lookup_service]
        t1 = _make_fc_turn(
            next_turn_num,
            tool_name="classify_event",
            args={"domain": "complicated", "reasoning": "deterministic CI test failure"},
            action="triage",
            result_text="Classified as complicated",
            batch_size=2,
            extra_fcs=[{"functionCall": {"name": "lookup_service", "args": {"service_name": "payments-api"}}}],
        )
        t2 = _make_fc_turn(
            next_turn_num + 1,
            tool_name="lookup_service",
            args={"service_name": "payments-api"},
            action="tool_result",
            result_text="EARLY_DECAY_CANDIDATE_T2 " + ("svc-topology-detail " * 35),
            batch_index=1,
        )
        next_turn_num += 2
        event.conversation.extend([t1, t2])
        event.event.evidence.brain_domain = "complicated"
        classified = True
        domain = "complicated"
        await _record("turn1-batch-classify-and-lookup")

        # Turn 2 (conv_len=3): accepted set_phase("dispatch") -> anchors dispatch/ overlay post-FR
        event.conversation.append(
            _make_fc_turn(
                next_turn_num,
                tool_name="set_phase",
                args={"phase": "dispatch", "reasoning": "dispatch sysadmin to inspect MR"},
                action="phase",
                result_text="Phase transitioned to dispatch",
            )
        )
        next_turn_num += 1
        event.brain_phase = "dispatch"
        await _record("turn2-phase-dispatch")

        # Turn 3 (conv_len=4): select_agent dispatch
        event.conversation.append(
            _make_fc_turn(
                next_turn_num,
                tool_name="select_agent",
                args={"agent": "sysadmin", "task": "Inspect failing CI logs on MR !42"},
                action="route",
                result_text="Dispatched sysadmin",
            )
        )
        next_turn_num += 1
        await _record("turn3-select-agent")

        # Turn 4 (conv_len=5): heavy agent result (>400 chars -> decays at conv_len==21)
        event.conversation.append(
            _make_agent_result_turn(
                next_turn_num,
                actor="sysadmin",
                payload="EARLY_DECAY_CANDIDATE_T5 " + ("ci-log-trace-line " * 45),
            )
        )
        next_turn_num += 1
        await _record("turn4-agent-result")

        # Turn 5 (conv_len=6): refresh_gitlab_context live mutation + sticky note + pod restart L1 clear!
        event.event.evidence.gitlab_context["mr_title"] = "MUTATED_AFTER_REFRESH_TITLE"
        event.event.evidence.gitlab_context["pipeline_status"] = "running"
        event.event.evidence.gitlab_context["pipeline_id"] = 99999
        event.sticky_notes.append({
            "timestamp": "2026-11-23T10:05:00Z",
            "content": "Operator note: watch for flaky integration runner",
            "read": False,
        })
        brain._frozen_anchors.clear()  # Simulate Brain pod restart wiping L1 anchor cache
        event.conversation.append(
            _make_fc_turn(
                next_turn_num,
                tool_name="lookup_journal",
                args={"service": "payments-api"},
                action="tool_result",
                result_text="Journal entry: runner-4 restarted 2h ago",
            )
        )
        next_turn_num += 1
        await _record("turn5-after-refresh-sticky-and-restart")

        # Turn 6 (conv_len=7): accepted set_phase("verify")
        event.conversation.append(
            _make_fc_turn(
                next_turn_num,
                tool_name="set_phase",
                args={"phase": "verify", "reasoning": "verify fix against live CI"},
                action="phase",
                result_text="Phase transitioned to verify",
            )
        )
        next_turn_num += 1
        event.brain_phase = "verify"
        await _record("turn6-phase-verify")

        # Turns 7..19 (conv_len=8..20): steady verify work crossing old sliding boundary (11..20)
        # Includes a second L1 restart clear (conv_len=15), a rejected [GATE] close attempt (conv_len=16),
        # and >400-char payloads in indices 10..19 that MUST stay raw after conv_len==21.
        post_epoch_sentinel = "POST_EPOCH_RAW_TURN_12 " + ("verify-check-output " * 35)
        for conv_target in range(8, 21):
            if conv_target in (8, 17):
                event.conversation.append(
                    _make_fc_turn(
                        next_turn_num,
                        tool_name="select_agent",
                        args={"agent": "qe", "task": f"Run verification pass {conv_target}"},
                        action="route",
                        result_text=f"Dispatched qe for pass {conv_target}",
                    )
                )
            elif conv_target in (9, 18):
                event.conversation.append(
                    _make_agent_result_turn(
                        next_turn_num,
                        actor="qe",
                        payload=f"Verification pass {conv_target}: 14/14 checks green",
                    )
                )
            elif conv_target == 12:
                event.conversation.append(
                    _make_fc_turn(
                        next_turn_num,
                        tool_name="lookup_service",
                        args={"service_name": "payments-api"},
                        action="tool_result",
                        result_text=post_epoch_sentinel,
                    )
                )
            elif conv_target == 15:
                brain._frozen_anchors.clear()  # Second simulated pod restart mid-event
                event.conversation.append(
                    _make_fc_turn(
                        next_turn_num,
                        tool_name="lookup_journal",
                        args={"service": "payments-api"},
                        action="tool_result",
                        result_text="Post-restart journal check clean",
                    )
                )
            elif conv_target == 16:
                # Rejected close transition (action="tool_result" + [GATE]) must NOT anchor close/ overlay
                event.conversation.append(
                    _make_fc_turn(
                        next_turn_num,
                        tool_name="set_phase",
                        args={"phase": "close", "reasoning": "premature close"},
                        action="tool_result",
                        thoughts="[GATE] Close blocked: verification pending",
                        result_text="[GATE] Close blocked: verification pending",
                    )
                )
            else:
                event.conversation.append(
                    _make_fc_turn(
                        next_turn_num,
                        tool_name="lookup_service",
                        args={"service_name": "payments-api"},
                        action="tool_result",
                        result_text=f"Service health check {conv_target}: synced & healthy",
                    )
                )
            next_turn_num += 1
            await _record(f"turn-conv{conv_target}-verify")

        # Turn 20 (conv_len=21): FIRST K=10 EPOCH SNAP (cutoff transitions 0 -> 10)
        event.conversation.append(
            _make_fc_turn(
                next_turn_num,
                tool_name="lookup_service",
                args={"service_name": "payments-api"},
                action="tool_result",
                result_text="Final verification check: pipeline green",
            )
        )
        next_turn_num += 1
        await _record("turn-conv21-epoch-snap")

        # Turn 21 (conv_len=22): accepted set_phase("close") -> anchors close/ overlay post-FR
        event.conversation.append(
            _make_fc_turn(
                next_turn_num,
                tool_name="set_phase",
                args={"phase": "close", "reasoning": "all checks verified"},
                action="phase",
                result_text="Phase transitioned to close",
            )
        )
        next_turn_num += 1
        event.brain_phase = "close"
        await _record("turn-conv22-phase-close")

        # Turns 22..24 (conv_len=23..25): within-epoch close turns (ZERO diffs expected)
        for conv_target in range(23, 26):
            event.conversation.append(
                _make_fc_turn(
                    next_turn_num,
                    tool_name="lookup_journal",
                    args={"service": "payments-api"},
                    action="tool_result",
                    result_text=f"Close checklist step {conv_target}: documented",
                )
            )
            next_turn_num += 1
            await _record(f"turn-conv{conv_target}-close")

        assert len(snaps) == 25
        assert snaps[-1].conv_len == 25

        # 1. Static preamble invariants: 100% byte-identical tools & SI across ALL 25 snapshots
        assert len({s.tools_bytes for s in snaps}) == 1, "Wire tools drifted across turns"
        assert len({s.si_bytes for s in snaps}) == 1, "Global Core SI drifted across turns"

        # 2. thinking_level invariant: 'high' across all operational phases (triage/dispatch/verify/close)
        phases_seen = {s.phase for s in snaps}
        assert phases_seen == {"triage", "dispatch", "verify", "close"}
        for s in snaps:
            assert s.thinking_level == "high", (
                f"[{s.label}] expected thinking_level='high' in phase={s.phase!r}, got {s.thinking_level!r}"
            )
            assert s.max_output_tokens == 65536

        # 3. Turn-0 anchor invariant: 100% byte-identical across Turn 0 -> refresh -> sticky -> restart -> Turn 25
        assert len({s.anchor_part0_bytes for s in snaps}) == 1, "wire_contents[0].parts[0] drifted"
        assert len({s.history_msgs[0] for s in snaps}) == 1, "Turn-0 anchor Content drifted"
        assert "MUTATED_AFTER_REFRESH_TITLE" not in snaps[-1].history_msgs[0]
        assert "Bump payments-api dependency to 2.4.1" in snaps[-1].history_msgs[0]

        # 4. Consecutive turn-pair wire prefix byte-equality audit (both message-level and part-stream level)
        mutated_labels: list[str] = []
        part_mutated_labels: list[str] = []
        for idx in range(1, len(snaps)):
            prev_s = snaps[idx - 1]
            curr_s = snaps[idx]
            prev_len = len(prev_s.history_msgs)
            assert len(curr_s.history_msgs) >= prev_len, (
                f"[{curr_s.label}] history shrank unexpectedly from {prev_len} to {len(curr_s.history_msgs)}"
            )
            if curr_s.history_msgs[:prev_len] != prev_s.history_msgs:
                mutated_labels.append(curr_s.label)
            prev_parts = _flatten_wire_parts(prev_s.history_msgs)
            curr_parts = _flatten_wire_parts(curr_s.history_msgs)
            if curr_parts[: len(prev_parts)] != prev_parts:
                part_mutated_labels.append(curr_s.label)

        assert mutated_labels == ["turn-conv21-epoch-snap"], (
            f"Expected message-level prefix mutation ONLY at conv_len==21; got {mutated_labels}"
        )
        assert part_mutated_labels == ["turn-conv21-epoch-snap"], (
            f"Expected part-stream prefix mutation ONLY at conv_len==21; got {part_mutated_labels}"
        )

        # 5. Verify conv_len==21 decay snap genuinely decayed turns 0..9 while preserving turns 10..20 raw
        snap_20 = next(s for s in snaps if s.conv_len == 20)
        snap_21 = next(s for s in snaps if s.conv_len == 21)
        snap_25 = next(s for s in snaps if s.conv_len == 25)
        assert snap_20.decayed_count == 0, "Zero turns may decay before conv_len==21 (K=10)"
        assert snap_21.decayed_count >= 2, (
            f"Expected >=2 heavy turns in 0..9 to decay at conv_len==21, got {snap_21.decayed_count}"
        )
        assert snap_25.decayed_count == snap_21.decayed_count, "Decayed count must not drift within epoch 21..25"
        joined_25 = "\n".join(snap_25.history_msgs)
        assert "EARLY_DECAY_CANDIDATE_T2" not in joined_25
        assert "EARLY_DECAY_CANDIDATE_T5" not in joined_25
        assert "POST_EPOCH_RAW_TURN_12" in joined_25, "Turns 10..20 must stay raw across conv_len 21..25"

        # 6. Verify within-epoch Turn 21 -> Turn 25 has ZERO byte diffs across wire_contents[0..k-1]
        epoch2_snaps = [s for s in snaps if s.conv_len >= 21]
        assert [s.conv_len for s in epoch2_snaps] == [21, 22, 23, 24, 25]
        for idx in range(1, len(epoch2_snaps)):
            prev_s = epoch2_snaps[idx - 1]
            curr_s = epoch2_snaps[idx]
            assert curr_s.history_msgs[: len(prev_s.history_msgs)] == prev_s.history_msgs, (
                f"Unexpected within-epoch wire diff at conv_len={curr_s.conv_len} ({curr_s.label})"
            )

        # 7. Verify post-FR overlays anchored deterministically on distinct domain/phases & skipped rejected [GATE]
        snap_before_gate = next(s for s in snaps if s.conv_len == 15)
        snap_after_gate = next(s for s in snaps if s.conv_len == 16)
        assert snap_after_gate.overlay_texts == snap_before_gate.overlay_texts, (
            "Rejected [GATE] set_phase('close') must NOT anchor close/ overlay"
        )
        assert len(snap_25.overlay_texts) >= 2, (
            f"Expected domain/phase <skill_overlay> anchors in replay, got {len(snap_25.overlay_texts)}"
        )
        assert any("domain/complicated.md" in ov for ov in snap_25.overlay_texts)
        assert any("close/" in ov for ov in snap_25.overlay_texts)
        assert not any("close/" in ov for ov in snap_after_gate.overlay_texts)


# ---------------------------------------------------------------------------
# Section 6c: Static Preamble Token Ceiling & Hexagonal Seam Guards
# ---------------------------------------------------------------------------

class TestSection6cFitnessAndSeamGuards:
    """Section 6c fitness & architectural boundary invariants for VMER-2450. [T-38]"""

    def test_section6c_static_preamble_estimated_tokens_within_45k_ceiling(self):
        """[T-38] Given canonical wire_tools and Global Core SI built from live brain_skills/,
        When estimated tokens are computed as (len(json(wire_tools)) + len(global_core_si)) / 4,
        Then the static preamble stays strictly <= 45,000 tokens (QuotaTracker burst headroom)."""
        loader = BrainSkillLoader(str(_SKILLS_DIR), include_generated_map=True)
        wire_tools = canonical_wire_tools(BRAIN_TOOL_SCHEMAS)
        global_core_si = build_global_core_si(loader)

        tools_json = json.dumps(wire_tools, sort_keys=True, separators=(",", ":"))
        est_tokens = (len(tools_json) + len(global_core_si)) / 4
        assert 0 < est_tokens <= 45_000, (
            f"Static preamble exceeded 45,000 est. tokens ceiling: {est_tokens:.1f} "
            f"(tools={len(tools_json) / 4:.1f}, si={len(global_core_si) / 4:.1f})"
        )

        # Also check SDK-converted wire tools representation stays within ceiling
        sdk_tool = GeminiAdapter._convert_tools(wire_tools)
        sdk_tools_json = json.dumps(sdk_tool.model_dump(mode="json", exclude_none=True), sort_keys=True)
        sdk_est_tokens = (len(sdk_tools_json) + len(global_core_si)) / 4
        assert sdk_est_tokens <= 45_000, (
            f"SDK-serialized static preamble exceeded 45,000 est. tokens ceiling: {sdk_est_tokens:.1f}"
        )

    def test_section6c_hexagonal_seam_and_modularity_guards(self):
        """Verify <=100-line budget on prefix_builder.py & event_state_tail.py, zero Redis/LLM/Brain
        imports in those pure helpers, and zero runtime src.agents imports in turn_decay.py & maintainers.py."""
        prefix_builder_path = _REPO_ROOT / "src" / "agents" / "prefix_builder.py"
        event_state_tail_path = _REPO_ROOT / "src" / "agents" / "event_state_tail.py"
        turn_decay_path = _REPO_ROOT / "src" / "utils" / "turn_decay.py"
        maintainers_path = _REPO_ROOT / "src" / "utils" / "maintainers.py"

        for pure_path in (prefix_builder_path, event_state_tail_path):
            line_count = len(pure_path.read_text(encoding="utf-8").splitlines())
            assert line_count <= 100, f"{pure_path.name} has {line_count} lines (ceiling: 100)"
            _assert_no_forbidden_imports(
                pure_path,
                (
                    "redis",
                    "src.state",
                    "src.agents.brain",
                    "src.agents.llm",
                    "google",
                    "anthropic",
                ),
            )

        for util_path in (turn_decay_path, maintainers_path):
            _assert_no_forbidden_imports(util_path, ("src.agents",))
