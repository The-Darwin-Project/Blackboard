# BlackBoard/tests/test_qe_mutant_gaps.py
# @ai-rules:
# 1. [Constraint]: QE-owned regression tests added after line-anchored mutation testing of VMER-2341 (PR #333).
#    Each test pins a behavior whose single-point mutant previously SURVIVED the whole suite.
# 2. [Pattern]: Notice counts are parsed with this file's OWN regex, never the SUT's prune_notice_count.
# 3. [Gotcha]: The orphan-FR case needs BRAIN_THOUGHT_SIG_V2=true (unequal FC/FR counts => no pair_buddy).
"""Mutation-gap tests (QE): recall range bounds + field precedence, recall-gate predicate, decay-predicate parity with
_build_contents, decay flag/size boundaries per branch, prune-notice counts, fence pass cap, briefing caps, single-turn quota."""
from __future__ import annotations

import re
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.context_parts import (
    compress_contents,
    contents_have_pruned_or_decayed,
    format_evidence_decay_reference,
    format_prune_notice,
    turn_to_parts,
)
from src.agents.handlers_cross_event import handle_recall_pruned_turns
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)

_NOTICE_RE = re.compile(r"(\d+) earlier conversation entries pruned")


def _notice_counts(contents: list[dict]) -> list[int]:
    return [
        int(m.group(1))
        for msg in contents
        for p in msg.get("parts", [])
        for m in [_NOTICE_RE.search(str(p.get("text", "")))]
        if m
    ]


def _event(turns: list[ConversationTurn]) -> EventDocument:
    ev = EventEvidence(display_text="t", source_type="chat", domain="complicated", severity="info")
    return EventDocument(
        id="evt-qe-gap", source="chat", status=EventStatus("active"), service="svc",
        event=EventInput(reason="r", evidence=ev, timeDate="2026-01-01T00:00:00Z"), conversation=turns,
    )


async def _recall(event: EventDocument, args: dict) -> str:
    ctx = MagicMock()
    bb = AsyncMock()
    bb.get_event = AsyncMock(return_value=event)
    ctx.get_blackboard.return_value = bb
    ctx.next_turn_number = AsyncMock(return_value=len(event.conversation) + 1)
    ctx.append_and_broadcast = AsyncMock()
    assert await handle_recall_pruned_turns(ctx, event.id, args, None) is True
    return ctx.append_and_broadcast.call_args[0][1].thoughts


def _users(n: int) -> list[ConversationTurn]:
    return [ConversationTurn(turn=i, actor="user", action="message", thoughts=f"body{i}") for i in range(1, n + 1)]


def _recalled_turn_numbers(text: str) -> list[int]:
    return [int(m) for m in re.findall(r"\[T(\d+) user\.message\]", text)]


# ---------------------------------------------------------------------------
# Recall range bounds: the 20-turn cap must be a pure width check (to - from), not position-dependent
# ---------------------------------------------------------------------------

class TestRecallRangeBounds:
    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "from_turn,to_turn,expected",
        [
            (20, 22, list(range(20, 23))),          # high start, narrow range: must NOT be widened
            (1, 9, list(range(1, 10))),             # narrow range from the start: must NOT gain a turn
            (5, 7, [5, 6, 7]),
            (1, 20, list(range(1, 21))),            # exactly the cap
            (1, 21, list(range(1, 21))),            # one over the cap -> clamped to 20 turns
            (5, 40, list(range(5, 25))),            # wide range from the middle -> 20 turns
        ],
    )
    async def test_range_returns_exactly_requested_window_capped_at_20(self, from_turn, to_turn, expected):
        text = await _recall(_event(_users(40)), {"from_turn": from_turn, "to_turn": to_turn})
        assert _recalled_turn_numbers(text) == expected


# ---------------------------------------------------------------------------
# Recall payload field precedence per mode
# ---------------------------------------------------------------------------

class TestRecallPayloadFieldPrecedence:
    @staticmethod
    def _tool_turn(**kw) -> ConversationTurn:
        return ConversationTurn(turn=3, actor="brain", action="tool_result", waitingFor="run_bash", **kw)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "fields,expected",
        [
            ({"evidence": "EVID"}, "EVID"),                                   # evidence only (thoughts/result empty)
            ({"result": "RES"}, "RES"),                                       # result only
            ({"thoughts": "THO"}, "THO"),
            ({"thoughts": "THO", "evidence": "EVID"}, "THO"),                 # range mode prefers thoughts
            ({"evidence": "EVID", "result": "RES"}, "EVID"),                  # evidence over result
        ],
    )
    async def test_range_mode_precedence_thoughts_evidence_result(self, fields, expected):
        turns = _users(2) + [self._tool_turn(**fields)]
        text = await _recall(_event(turns), {"from_turn": 1, "to_turn": 3})
        assert f"[T3 brain.tool_result]: {expected}" in text

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "fields,expected",
        [
            ({"evidence": "EVID", "thoughts": "THO", "result": "RES"}, "EVID"),   # single turn prefers evidence
            ({"result": "RES", "thoughts": "THO"}, "RES"),
            ({"thoughts": "THO"}, "THO"),
        ],
    )
    async def test_single_turn_precedence_evidence_result_thoughts(self, fields, expected):
        turns = _users(2) + [self._tool_turn(**fields)]
        text = await _recall(_event(turns), {"from_turn": 3, "to_turn": 3})
        assert f"[T3 brain.tool_result]: {expected}" in text


# ---------------------------------------------------------------------------
# contents_have_pruned_or_decayed: the single predicate that un-gates recall_pruned_turns
# ---------------------------------------------------------------------------

_REF = format_evidence_decay_reference(7, "run_bash", 5000)


class TestRecallGatePredicate:
    def test_empty_contents_is_false(self):
        assert contents_have_pruned_or_decayed([]) is False

    def test_plain_function_response_without_decay_tag_is_false(self):
        contents = [
            {"role": "user", "parts": [{"text": "header"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "run_bash", "args": {}}}]},
            {"role": "user", "parts": [{"functionResponse": {"name": "run_bash", "response": {"result": "ok"}}}]},
        ]
        assert contents_have_pruned_or_decayed(contents) is False

    def test_function_response_with_non_dict_response_is_false(self):
        contents = [
            {"role": "user", "parts": [{"text": "header"}]},
            {"role": "user", "parts": [{"functionResponse": {"name": "x", "response": "plain string"}}]},
        ]
        assert contents_have_pruned_or_decayed(contents) is False

    def test_decayed_function_response_as_first_part_of_later_message_is_true(self):
        contents = [
            {"role": "user", "parts": [{"text": "header"}]},
            {"role": "model", "parts": [{"functionCall": {"name": "run_bash", "args": {}}}]},
            {"role": "user", "parts": [{"functionResponse": {"name": "run_bash", "response": {"result": _REF}}}]},
        ]
        assert contents_have_pruned_or_decayed(contents) is True

    def test_decayed_text_part_as_first_part_of_later_message_is_true(self):
        contents = [
            {"role": "user", "parts": [{"text": "header"}]},
            {"role": "user", "parts": [{"text": f"[SYSTEM run_bash]: {_REF}"}]},
        ]
        assert contents_have_pruned_or_decayed(contents) is True

    def test_decay_tag_only_in_event_header_part_is_ignored(self):
        contents = [{"role": "user", "parts": [{"text": f"header embeds {_REF}"}]}]
        assert contents_have_pruned_or_decayed(contents) is False

    def test_decay_tag_in_later_part_of_message_zero_is_detected(self):
        contents = [{"role": "user", "parts": [{"text": "header"}, {"text": f"[SYSTEM x]: {_REF}"}]}]
        assert contents_have_pruned_or_decayed(contents) is True

    def test_prune_notice_in_message_zero_is_detected(self):
        contents = [{"role": "user", "parts": [{"text": "header"}, format_prune_notice(3)]}]
        assert contents_have_pruned_or_decayed(contents) is True


# ---------------------------------------------------------------------------
# Decay boundary on the AGENT branch (every other branch already has a 399/400/401 test)
# ---------------------------------------------------------------------------

class TestAgentDecayBoundary:
    @pytest.mark.parametrize("n,decays", [(399, False), (400, False), (401, True)])
    def test_agent_turn_payload_boundary(self, n, decays):
        turn = ConversationTurn(turn=4, actor="developer", action="result", result="r" * n)
        text = turn_to_parts(turn, decay_evidence=True, turn_index=4)[0]["text"]
        assert ("blackboard_evidence_reference" in text) is decays


# ---------------------------------------------------------------------------
# Prune-notice counts
# ---------------------------------------------------------------------------

def _single_message_contents(n_conv: int) -> list[dict]:
    parts = [{"text": "HEADER"}, {"text": "--- CONVERSATION ---"}]
    parts += [{"text": f"C{i:02d}:" + "x" * 2000} for i in range(n_conv)]
    parts.append({"text": "ACTION"})
    return [{"role": "user", "parts": parts}]


class TestSingleMessageCompression:
    def test_notice_count_equals_pruned_parts_and_newest_part_survives(self):
        out = compress_contents(_single_message_contents(10), max_tokens=2000, tail_budget=1000)
        assert len(out) == 1
        texts = [str(p.get("text", "")) for p in out[0]["parts"]]
        kept = [t for t in texts if re.match(r"C\d\d:", t)]
        assert kept, "at least the newest conversation part must survive"
        assert kept[-1].startswith("C09:"), "newest conversation part must never be the one dropped"
        assert _notice_counts(out) == [10 - len(kept)]
        assert texts[0] == "HEADER" and texts[-1] == "ACTION"

    def test_second_pass_merges_counts_instead_of_stacking(self):
        once = compress_contents(_single_message_contents(10), max_tokens=2000, tail_budget=1000)
        n_first = _notice_counts(once)[0]
        twice = compress_contents(once, max_tokens=100, tail_budget=50)
        counts = _notice_counts(twice)
        assert len(counts) == 1
        kept_after = [p for p in twice[0]["parts"] if re.match(r"C\d\d:", str(p.get("text", "")))]
        assert counts[0] == 10 - len(kept_after) >= n_first


class TestOrphanFunctionResponseCount:
    def test_dropped_orphan_fr_message_is_counted_in_notice(self, monkeypatch):
        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        fc = lambda n: {"functionCall": {"name": n, "args": {}}}  # noqa: E731
        fr = lambda n: {"functionResponse": {"name": n, "response": {"result": "ok"}}}  # noqa: E731
        conv = [
            {"role": "model", "parts": [{"text": "OLD" + "o" * 6000}, fc("a"), fc("b")]},  # 2 FC ...
            {"role": "user", "parts": [fr("a")]},                                         # ... 1 FR: not paired
            {"role": "model", "parts": [{"text": "M1" + "m" * 200}]},
            {"role": "user", "parts": [{"text": "U1" + "u" * 200}]},
            {"role": "model", "parts": [{"text": "M2"}]},
            {"role": "user", "parts": [{"text": "ASK"}]},
        ]
        contents = [{"role": "user", "parts": [{"text": "HEADER"}]}] + conv
        out = compress_contents(contents, max_tokens=1000, tail_budget=600)
        flat = "\n".join(str(p) for m in out for p in m["parts"])
        assert "functionResponse" not in flat, "orphan FR must be dropped, not left at the cut boundary"
        assert "OLD" not in flat and "M1" in flat and "U1" in flat and "M2" in flat
        # OLD (budget-pruned) + the FR message dropped at the cut boundary = 2 entries
        assert _notice_counts(out) == [2]
        assert [m["role"] for m in out] == ["user", "model", "user", "model", "user"]


# ---------------------------------------------------------------------------
# strip_xml_fences pass cap: converge exactly at the cap, fall back (strip every '<') one nesting level deeper
# ---------------------------------------------------------------------------

from src.utils.prompt_sanitize import strip_xml_fences  # noqa: E402


def _nested_context_tag(depth: int) -> str:
    """``<context>`` split ``depth`` times: each pass removes exactly one inner tag layer."""
    s = "<context>"
    for _ in range(depth):
        s = "<context" + s + ">"
    return s


class TestFencePassCap:
    def test_depth_converging_within_cap_keeps_surrounding_text_and_lt(self):
        # depth 6 needs 7 changing passes + 1 confirming pass == the 8 allowed: converges, unrelated '<' survives.
        out = strip_xml_fences("a < b " + _nested_context_tag(6) + " z")
        assert out == "a < b  z"

    def test_depth_exceeding_cap_falls_back_to_removing_all_lt(self):
        # depth 7 does not converge in 8 passes -> fallback deletes every '<' (and so cannot leave a fence tag).
        out = strip_xml_fences("a < b " + _nested_context_tag(7) + " z")
        assert "<" not in out

    @pytest.mark.parametrize("depth", [0, 3, 7, 8, 9, 20, 200])
    def test_never_emits_a_fence_tag_at_any_nesting_depth(self, depth):
        out = strip_xml_fences(_nested_context_tag(depth))
        for tag in ("<context>", "</context>", "<functionCall>", "--- CONVERSATION ---"):
            assert tag not in out


# ---------------------------------------------------------------------------
# tool_gates._decay_payload_len / conversation_has_decayed_turns: must mirror context_parts' decay branches
# ---------------------------------------------------------------------------

import random  # noqa: E402
from unittest.mock import patch  # noqa: E402

from src.agents.tool_gates import (  # noqa: E402
    DECAY_MIN_CHARS,
    DEFAULT_TURN_DECAY_DISTANCE,
    _decay_payload_len,
    conversation_has_decayed_turns,
)


def _t(actor="brain", action="tool_result", waitingFor=None, **fields) -> ConversationTurn:
    return ConversationTurn(turn=1, actor=actor, action=action, waitingFor=waitingFor, **fields)


class TestDecayPayloadLen:
    @pytest.mark.parametrize("actor", ["user", "jarvis", "dispatcher"])
    def test_human_and_dispatcher_text_never_decays(self, actor):
        assert _decay_payload_len(_t(actor=actor, action="message", thoughts="x" * 5000, evidence="y" * 5000)) == 0

    @pytest.mark.parametrize("fields", [{"evidence": "e" * 5000}, {"thoughts": "t" * 5000}])
    def test_recall_result_is_exempt_for_both_storage_fields(self, fields):
        assert _decay_payload_len(_t(waitingFor="recall_pruned_turns", **fields)) == 0

    def test_brain_tool_result_decays_evidence_else_thoughts(self):
        assert _decay_payload_len(_t(waitingFor="run_bash", evidence="e" * 500)) == 500
        assert _decay_payload_len(_t(waitingFor="run_bash", thoughts="t" * 600)) == 600
        assert _decay_payload_len(_t(waitingFor="run_bash", evidence="e" * 500, thoughts="t" * 900)) == 500
        assert _decay_payload_len(_t(waitingFor="run_bash")) == 0

    def test_other_brain_turns_decay_evidence_only(self):
        assert _decay_payload_len(_t(action="route", waitingFor="select_agent", evidence="e" * 700)) == 700
        assert _decay_payload_len(_t(action="route", waitingFor="select_agent", thoughts="t" * 900)) == 0

    def test_agent_turn_precedence_evidence_result_thoughts(self):
        a = dict(actor="developer", action="result")
        assert _decay_payload_len(_t(**a, evidence="e" * 11, result="r" * 22, thoughts="t" * 33)) == 11
        assert _decay_payload_len(_t(**a, result="r" * 22, thoughts="t" * 33)) == 22
        assert _decay_payload_len(_t(**a, thoughts="t" * 33)) == 33
        assert _decay_payload_len(_t(**a)) == 0


class TestConversationHasDecayedTurns:
    @staticmethod
    def _conv(big_idx: int, size: int, n: int = 12) -> list[ConversationTurn]:
        turns = [_t(actor="user", action="message", thoughts="hi") for _ in range(n)]
        turns[big_idx] = _t(waitingFor="run_bash", evidence="e" * size)
        return turns

    def test_distance_boundary(self):
        assert DEFAULT_TURN_DECAY_DISTANCE == 10
        assert conversation_has_decayed_turns(self._conv(0, 500)) is True    # distance 11 > 10
        assert conversation_has_decayed_turns(self._conv(1, 500)) is False   # distance 10 is still raw

    @pytest.mark.parametrize("size,expected", [(399, False), (400, False), (401, True)])
    def test_size_boundary(self, size, expected):
        assert DECAY_MIN_CHARS == 400
        assert conversation_has_decayed_turns(self._conv(0, size)) is expected

    def test_custom_distance_and_empty_inputs(self):
        assert conversation_has_decayed_turns(self._conv(8, 500), decay_distance=2) is True
        assert conversation_has_decayed_turns([]) is False
        assert conversation_has_decayed_turns(None) is False  # type: ignore[arg-type]

    def test_far_big_user_message_is_not_a_decay_signal(self):
        turns = [_t(actor="user", action="message", thoughts="u" * 5000)] + [
            _t(actor="user", action="message", thoughts="hi") for _ in range(12)
        ]
        assert conversation_has_decayed_turns(turns) is False


_KINDS = [  # (actor, action, waitingFor, field) -- every kind that really decays, plus the exempt/never-decay ones
    ("user", "message", None, "thoughts"), ("jarvis", "message", None, "thoughts"),
    ("dispatcher", "acknowledge", None, "thoughts"),
    ("brain", "tool_result", "run_bash", "evidence"), ("brain", "tool_result", "run_bash", "thoughts"),
    ("brain", "tool_result", "recall_pruned_turns", "thoughts"), ("brain", "tool_result", "recall_pruned_turns", "evidence"),
    ("brain", "route", "select_agent", "evidence"), ("brain", "phase", "set_phase", "evidence"),
    ("developer", "result", None, "result"), ("developer", "progress", None, "evidence"),
    ("qe", "result", None, "thoughts"), ("architect", "message", None, "result"),
]
_LENS = [0, 10, 399, 400, 401, 1500]


@pytest.mark.asyncio
async def test_gate_fallback_predicate_matches_what_build_contents_actually_decays():
    """Seeded property test: conversation_has_decayed_turns() == "the built prompt carries a decay reference"."""
    from tests.test_build_contents_structure import _make_brain_mock, _make_event, _make_turn, _all_text
    from src.agents.brain import Brain

    rng = random.Random(20260113)
    seen = set()
    for _ in range(400):
        conv = []
        for i in range(rng.randint(11, 22)):
            actor, action, wf, field = rng.choice(_KINDS)
            n = rng.choice(_LENS)
            conv.append(_make_turn(turn=i + 1, actor=actor, action=action, waitingFor=wf, **({field: "z" * n} if n else {})))
        with patch("src.agents.brain._CONTENT_BUDGET", 10**9), patch("src.agents.brain._TAIL_BUDGET", 10**9):
            built = await Brain._build_contents(_make_brain_mock(), _make_event(conversation=conv))
        actual = "blackboard_evidence_reference" in _all_text(built)
        predicted = conversation_has_decayed_turns(conv)
        assert predicted == actual, [(t.actor, t.action, t.waitingFor, len(t.evidence or ""), len(t.thoughts or ""), len(t.result or "")) for t in conv]
        seen.add(actual)
    assert seen == {True, False}, "generator must exercise both outcomes"


# ---------------------------------------------------------------------------
# Operational briefing: untrusted-line pre-cap and label cap
# ---------------------------------------------------------------------------

from src.agents.llm.prompt import build_operational_briefing  # noqa: E402


class TestBriefingUntrustedLineCaps:
    @staticmethod
    def _briefing(**note) -> str:
        from tests.test_operational_briefing import _make_briefing_event

        return build_operational_briefing(_make_briefing_event(sticky_notes=[note]))

    @pytest.mark.parametrize("label_len,shown", [(63, 63), (64, 64), (65, 64), (200, 64)])
    def test_author_label_is_capped_at_64_chars(self, label_len, shown):
        out = self._briefing(content="n", author="L" * label_len)
        m = re.search(r"  \* \[(L+)\] n", out)
        assert m and len(m.group(1)) == shown

    def test_note_is_precapped_before_stripping_then_hard_capped_last(self):
        # 120 stripped tags (1080 chars) + 400 'A': only the first 4*300=1200 raw chars are examined, so 120 'A' survive.
        out = self._briefing(content="<context>" * 120 + "A" * 400, timestamp="t")
        assert "  * [t] " + "A" * 120 + "\n" in out + "\n"
        assert "A" * 121 not in out
        # A note that is clean but long is hard-capped to exactly 300 chars.
        out2 = self._briefing(content="B" * 1000, timestamp="t")
        assert "B" * 300 in out2 and "B" * 301 not in out2


# ---------------------------------------------------------------------------
# turn_to_parts: decay requires BOTH the flag and the size, on every branch (brain tool_result / brain evidence / agent)
# ---------------------------------------------------------------------------

_BRANCH_TURNS = {
    "tool_result": lambda n: ConversationTurn(turn=4, actor="brain", action="tool_result", waitingFor="run_bash", evidence="e" * n),
    "brain_evidence": lambda n: ConversationTurn(turn=4, actor="brain", action="route", waitingFor="select_agent", evidence="e" * n),
    "agent": lambda n: ConversationTurn(turn=4, actor="developer", action="result", result="e" * n),
}


class TestTurnToPartsDecayFlagAndSize:
    @pytest.mark.parametrize("branch", sorted(_BRANCH_TURNS))
    @pytest.mark.parametrize("n,decays", [(399, False), (400, False), (401, True), (5000, True)])
    def test_size_boundary_with_flag(self, branch, n, decays):
        text = turn_to_parts(_BRANCH_TURNS[branch](n), decay_evidence=True, turn_index=4)[0]["text"]
        assert ("blackboard_evidence_reference" in text) is decays

    @pytest.mark.parametrize("branch", sorted(_BRANCH_TURNS))
    def test_flag_off_never_decays_even_when_huge(self, branch):
        text = turn_to_parts(_BRANCH_TURNS[branch](5000), decay_evidence=False, turn_index=4)[0]["text"]
        assert "blackboard_evidence_reference" not in text and "e" * 5000 in text



# ---------------------------------------------------------------------------
# Single-turn events: nothing to shed. Burst errors fail fast; plain quota errors take the generic backoff.
# ---------------------------------------------------------------------------

def _single_turn_event() -> EventDocument:
    turn = ConversationTurn(turn=1, actor="user", action="message", thoughts="only message " + "u" * 20000)
    return _event([turn]).model_copy(update={"id": "evt-shed-test", "brain_phase": "dispatch"})


class TestSingleTurnQuotaHandling:
    @staticmethod
    def _run(errors):
        from tests.test_quota_shedding import _fc_success_stream, _make_brain_for_shedding, _scripted_factory

        seq = [*errors, _fc_success_stream()]
        brain, bb = _make_brain_for_shedding(_scripted_factory(seq))
        return brain, bb

    @pytest.mark.asyncio
    async def test_burst_error_on_single_turn_event_fails_fast_without_retry_or_sleep(self, monkeypatch):
        from src.agents.llm.quota_tracker import RequestExceedsBurstError

        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            brain, bb = self._run([RequestExceedsBurstError(180_000, 100_000)])
            with patch("asyncio.sleep", new_callable=AsyncMock) as sleep:
                assert await brain._process_with_llm("evt-shed-test", _single_turn_event()) is False
        assert brain._adapter.generate_stream.call_count == 1
        sleep.assert_not_awaited()
        assert brain._append_and_broadcast.call_args[0][1].action == "error"

    @pytest.mark.asyncio
    async def test_local_quota_error_on_single_turn_event_sheds_nothing_and_backs_off_30s(self, monkeypatch):
        from src.agents.llm.quota_tracker import QuotaExhaustedError
        from tests.test_quota_shedding import _incr_keys

        monkeypatch.setenv("BRAIN_THOUGHT_SIG_V2", "true")
        with patch("src.agents.brain._THOUGHT_SIG_V2", True):
            brain, bb = self._run([QuotaExhaustedError("q0")])
            with (
                patch("src.agents.brain.random.random", return_value=0.0),
                patch("asyncio.sleep", new_callable=AsyncMock) as sleep,
            ):
                assert await brain._process_with_llm("evt-shed-test", _single_turn_event()) is True
        calls = brain._adapter.generate_stream.call_args_list
        assert len(calls) == 2
        assert calls[1].kwargs["contents"] == calls[0].kwargs["contents"], "a single turn cannot be shrunk"
        assert not [k for k in _incr_keys(bb) if "quota_shed" in k]
        assert [c.args[0] for c in sleep.await_args_list] == [30.0], "generic rate-limit backoff, not the zero-sleep shed path"
