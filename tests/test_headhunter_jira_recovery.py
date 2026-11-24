# BlackBoard/tests/test_headhunter_jira_recovery.py
# @ai-rules:
# 1. [Constraint]: No real Jira, Claude, or Redis API calls. All mocked via unittest.mock.
# 2. [Pattern]: Reuses _make_issue and _make_mock_redis helpers from tests/test_headhunter_jira.py.
# 3. [Purpose]: Pin VMER-2483 waiting_approval active-key parity, bounded 1-shot duplicate recovery,
#    per-issue Redis state isolation, and _should_retry_duplicate_event edge cases.
"""Unit tests for HeadhunterJira waiting_approval parity and bounded duplicate-close recovery."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.headhunter_jira import HeadhunterJira
from tests.test_headhunter_jira import _make_issue, _make_mock_redis


@pytest.fixture
def stub_blackboard():
    bb = MagicMock()
    bb.create_event = AsyncMock(return_value="evt-jira-001")
    bb.get_active_events = AsyncMock(return_value=[])
    bb.get_waiting_approval_events = AsyncMock(return_value=[])
    bb.get_active_events_with_status = AsyncMock(return_value={})
    bb.get_event = AsyncMock(return_value=None)
    bb.redis = _make_mock_redis()
    return bb


@pytest.fixture
def jira_head(stub_blackboard, monkeypatch):
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")
    monkeypatch.setenv("JIRA_EMAIL", "bot@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    monkeypatch.setenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "bot-acct-123")
    monkeypatch.setenv("HEADHUNTER_JIRA_LABEL", "darwin")
    return HeadhunterJira(stub_blackboard)


def _make_stub_jira_event(
    *,
    status: str = "active",
    issue_key: str | None = "VMER-2464",
    source: str = "headhunter",
    subject_type: str = "jira",
    close_evidence: str | None = None,
    raw_evidence: object = None,
    use_raw_evidence: bool = False,
    turns: list | None = None,
) -> MagicMock:
    """Build a stub Blackboard EventDocument for HeadhunterJira dedup & recovery tests."""
    ev = MagicMock()
    ev.source = source
    ev.subject_type = subject_type
    ev.status = MagicMock()
    ev.status.value = status
    ev.event = MagicMock()
    if use_raw_evidence:
        ev.event.evidence = raw_evidence
    else:
        ev.event.evidence = MagicMock()
        ev.event.evidence.jira_context = {"issue_key": issue_key}
    if turns is not None:
        ev.conversation = turns
    elif close_evidence is not None:
        triage_turn = MagicMock()
        triage_turn.action = "triage"
        triage_turn.evidence = None
        close_turn = MagicMock()
        close_turn.action = "close"
        close_turn.evidence = close_evidence
        ev.conversation = [triage_turn, close_turn]
    else:
        ev.conversation = []
    return ev


def _make_bot_analysis_comment(comment_id: str = "c-bot", text: str = "Approved mission plan") -> dict:
    return {
        "id": comment_id,
        "author": {"accountId": "bot-acct-123"},
        "body": text,
    }


def _make_turn_stub(action: str, evidence: str | None = None) -> MagicMock:
    turn = MagicMock()
    turn.action = action
    turn.evidence = evidence
    return turn


class TestWaitingApprovalAndDuplicateRecovery:
    """VMER-2483: waiting_approval active-key parity and bounded 1-shot duplicate recovery."""

    @pytest.mark.asyncio
    async def test_get_active_jira_keys_includes_waiting_approval_dedups_ids_and_excludes_none(
        self, jira_head, stub_blackboard
    ):
        """Given active + waiting_approval Jira events with an overlapping ID and an explicit
        issue_key=None entry, _get_active_jira_keys unions and dedups IDs and excludes None."""
        events = {
            "evt-active": _make_stub_jira_event(status="active", issue_key="VMER-2463"),
            "evt-overlap": _make_stub_jira_event(status="waiting_approval", issue_key="VMER-2464"),
            "evt-waiting": _make_stub_jira_event(status="waiting_approval", issue_key="VMER-2465"),
            "evt-none-key": _make_stub_jira_event(status="active", issue_key=None),
        }
        stub_blackboard.get_active_events = AsyncMock(return_value=["evt-active", "evt-overlap", "evt-none-key"])
        stub_blackboard.get_waiting_approval_events = AsyncMock(return_value=["evt-overlap", "evt-waiting"])
        stub_blackboard.get_event = AsyncMock(side_effect=lambda eid: events.get(eid))

        keys = await jira_head._get_active_jira_keys()

        assert keys == {"VMER-2463", "VMER-2464", "VMER-2465"}
        assert None not in keys
        assert stub_blackboard.get_event.await_count == 4

    @pytest.mark.asyncio
    async def test_get_active_jira_keys_handles_dict_and_str_evidence(self, jira_head, stub_blackboard):
        """_get_active_jira_keys normalizes dict-typed evidence keys and safely skips legacy str evidence."""
        events = {
            "evt-dict": _make_stub_jira_event(
                status="active",
                use_raw_evidence=True,
                raw_evidence={"jira_context": {"issue_key": " vmer-2466 "}},
            ),
            "evt-str": _make_stub_jira_event(
                status="active",
                use_raw_evidence=True,
                raw_evidence="legacy string evidence",
            ),
        }
        stub_blackboard.get_active_events = AsyncMock(return_value=["evt-dict", "evt-str"])
        stub_blackboard.get_waiting_approval_events = AsyncMock(return_value=[])
        stub_blackboard.get_event = AsyncMock(side_effect=lambda eid: events.get(eid))

        keys = await jira_head._get_active_jira_keys()

        assert keys == {"VMER-2466"}

    @pytest.mark.asyncio
    async def test_get_active_jira_keys_isolates_poison_pill_value_error_but_propagates_transport_error(
        self, jira_head, stub_blackboard, caplog
    ):
        """Per-event ValueError/decode corruption is logged and skipped; transport errors propagate fail-closed."""
        good_ev = _make_stub_jira_event(status="active", issue_key="VMER-2467")

        async def _poison_get_event(eid: str):
            if eid == "evt-corrupt":
                raise ValueError("Pydantic validation error")
            return good_ev

        stub_blackboard.get_active_events = AsyncMock(return_value=["evt-corrupt", "evt-good"])
        stub_blackboard.get_waiting_approval_events = AsyncMock(return_value=[])
        stub_blackboard.get_event = AsyncMock(side_effect=_poison_get_event)

        with caplog.at_level("WARNING", logger="src.agents.headhunter_jira"):
            keys = await jira_head._get_active_jira_keys()

        assert keys == {"VMER-2467"}
        assert any("evt-corrupt" in r.message for r in caplog.records)

        stub_blackboard.get_event = AsyncMock(side_effect=ConnectionError("Redis unavailable"))
        with pytest.raises(ConnectionError, match="Redis unavailable"):
            await jira_head._get_active_jira_keys()

    @pytest.mark.asyncio
    async def test_poll_phase2_skips_active_key_scan_when_todo_empty(self, jira_head, stub_blackboard):
        """Idle-cycle optimization: when poll_todo returns [], get_active_events is never called."""
        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[]),
        ):
            await jira_head.poll_and_process()

        stub_blackboard.get_active_events.assert_not_called()
        stub_blackboard.get_waiting_approval_events.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_phase2_case_insensitive_active_key_skip(self, jira_head, stub_blackboard):
        """Active Jira event with lowercase 'vmer-2464' prevents duplicate creation for 'VMER-2464'."""
        issue = _make_issue(key="VMER-2464", status="To Do")
        active_ev = _make_stub_jira_event(status="active", issue_key="vmer-2464")
        stub_blackboard.get_active_events = AsyncMock(return_value=["evt-lower"])
        stub_blackboard.get_waiting_approval_events = AsyncMock(return_value=[])
        stub_blackboard.get_event = AsyncMock(side_effect=lambda eid: active_ev if eid == "evt-lower" else None)

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock) as mock_create,
        ):
            await jira_head.poll_and_process()

        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_phase2_skips_ticket_with_parked_waiting_approval_event(
        self, jira_head, stub_blackboard
    ):
        """Given a To Do ticket with no Redis event_created state but a parked waiting_approval event,
        poll_and_process Phase 2 skips it and creates no duplicate event."""
        issue = _make_issue(key="VMER-2464", status="To Do")
        parked = _make_stub_jira_event(status="waiting_approval", issue_key="VMER-2464")
        stub_blackboard.get_active_events = AsyncMock(return_value=[])
        stub_blackboard.get_waiting_approval_events = AsyncMock(return_value=["evt-parked"])
        stub_blackboard.get_event = AsyncMock(side_effect=lambda eid: parked if eid == "evt-parked" else None)

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "_run_claude_analysis", new_callable=AsyncMock, return_value="analysis"),
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, return_value="plan: ok"),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, return_value="evt-unexpected") as mock_create,
        ):
            await jira_head.poll_and_process()

        mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_phase2_retries_once_on_duplicate_closed_event_then_stays_parked(
        self, jira_head, stub_blackboard, caplog
    ):
        """Given phase='event_created' pointing to a closed duplicate event, Phase 2 retries once,
        persists duplicate_retried=True, and skips any subsequent poll even if the retry also closes as duplicate."""
        issue = _make_issue(key="VMER-2464", status="To Do")
        issue["fields"]["comment"]["comments"] = [_make_bot_analysis_comment()]
        await jira_head._set_issue_state("VMER-2464", {"phase": "event_created", "event_id": "evt-dup-1"})

        dup_events = {
            "evt-dup-1": _make_stub_jira_event(status="closed", issue_key="VMER-2464", close_evidence="duplicate"),
            "evt-retry-2": _make_stub_jira_event(status="closed", issue_key="VMER-2464", close_evidence="duplicate"),
        }
        stub_blackboard.get_event = AsyncMock(side_effect=lambda eid: dup_events.get(eid))

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "_run_claude_analysis", new_callable=AsyncMock) as mock_analyze,
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, return_value="plan: ok"),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, return_value="evt-retry-2") as mock_create,
            caplog.at_level("INFO", logger="src.agents.headhunter_jira"),
        ):
            # Poll 1: recovers once from duplicate-closed event
            await jira_head.poll_and_process()

            mock_analyze.assert_not_called()
            mock_create.assert_called_once()
            assert any("recovering from prior duplicate-closed event evt-dup-1" in r.message for r in caplog.records)
            state = await jira_head._get_issue_state("VMER-2464")
            assert state["phase"] == "event_created"
            assert state["event_id"] == "evt-retry-2"
            assert state.get("duplicate_retried") is True

            # Poll 2: even though evt-retry-2 also closed as duplicate, monotonic guard stays parked
            await jira_head.poll_and_process()
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_poll_phase2_flow_gate_closed_mid_cycle_suppresses_recovery_log_and_preserves_state(
        self, jira_head, stub_blackboard, caplog
    ):
        """Given a duplicate-closed event and a flow gate that closes mid-cycle, Phase 2 must NOT
        create an event, must NOT emit the recovery INFO log, and must leave duplicate_retried unset."""
        issue = _make_issue(key="VMER-2464", status="To Do")
        issue["fields"]["comment"]["comments"] = [_make_bot_analysis_comment()]
        await jira_head._set_issue_state("VMER-2464", {"phase": "event_created", "event_id": "evt-dup-1"})
        dup_ev = _make_stub_jira_event(status="closed", issue_key="VMER-2464", close_evidence="duplicate")
        stub_blackboard.get_event = AsyncMock(return_value=dup_ev)

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "check_flow_gate", new_callable=AsyncMock, side_effect=[True, False]) as mock_gate,
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, return_value="evt-unexpected") as mock_create,
            caplog.at_level("INFO", logger="src.agents.headhunter_jira"),
        ):
            await jira_head.poll_and_process()

        assert mock_gate.await_count == 2
        mock_create.assert_not_called()
        assert not any("recovering from prior duplicate-closed event" in r.message for r in caplog.records)
        state = await jira_head._get_issue_state("VMER-2464")
        assert not state.get("duplicate_retried")

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "state_payload,close_evidence",
        [
            ({"phase": "event_created", "event_id": "evt-dup-1", "duplicate_retried": True}, "duplicate"),
            ({"phase": "event_created", "event_id": "evt-res-1"}, "resolved"),
        ],
    )
    async def test_poll_phase2_skips_when_already_retried_or_closed_resolved(
        self, jira_head, stub_blackboard, state_payload, close_evidence
    ):
        """Given duplicate_retried=True OR prior event closed with evidence='resolved',
        Phase 2 skips the issue and creates no new event."""
        issue = _make_issue(key="VMER-2464", status="To Do")
        await jira_head._set_issue_state("VMER-2464", state_payload)
        prior_ev = _make_stub_jira_event(status="closed", issue_key="VMER-2464", close_evidence=close_evidence)
        stub_blackboard.get_event = AsyncMock(return_value=prior_ev)

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, return_value="evt-unexpected") as mock_create,
        ):
            await jira_head.poll_and_process()

        mock_create.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "bad_state,get_event_side_effect,expected_event_id,expect_warning",
        [
            ({"phase": "event_created"}, lambda eid: None, None, False),
            ({"phase": "event_created", "event_id": ""}, lambda eid: None, None, False),
            ({"phase": "event_created", "event_id": "   "}, lambda eid: None, None, False),
            ({"phase": "event_created", "event_id": 123}, lambda eid: None, None, False),
            ({"phase": "event_created", "event_id": "evt-missing"}, lambda eid: None, "evt-missing", False),
            ({"phase": "event_created", "event_id": "evt-boom"}, RuntimeError("Redis timeout"), "evt-boom", True),
        ],
    )
    async def test_poll_phase2_fail_closed_on_missing_none_or_error_and_continues_loop(
        self,
        jira_head,
        stub_blackboard,
        caplog,
        bad_state,
        get_event_side_effect,
        expected_event_id,
        expect_warning,
    ):
        """Given invalid/missing event_id, get_event() returning None, or get_event() raising RuntimeError,
        Phase 2 fails closed for that issue and continues processing subsequent To Do issues."""
        bad_issue = _make_issue(key="VMER-2461", status="To Do")
        healthy_issue = _make_issue(key="VMER-2462", status="To Do")
        healthy_issue["fields"]["comment"]["comments"] = [_make_bot_analysis_comment()]
        await jira_head._set_issue_state("VMER-2461", bad_state)

        stub_blackboard.get_event = AsyncMock(side_effect=get_event_side_effect)

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[bad_issue, healthy_issue]),
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, return_value="plan: ok"),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, return_value="evt-2462") as mock_create,
            caplog.at_level("WARNING", logger="src.agents.headhunter_jira"),
        ):
            await jira_head.poll_and_process()

        mock_create.assert_called_once()
        assert mock_create.call_args[0][0]["key"] == "VMER-2462"
        if expected_event_id is None:
            stub_blackboard.get_event.assert_not_called()
        else:
            stub_blackboard.get_event.assert_awaited_once_with(expected_event_id)
        if expect_warning:
            assert any(expected_event_id in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_bot_comment_recovery_preclaims_budget_when_brain_plan_raises(
        self, jira_head, stub_blackboard
    ):
        """Bot-comment path + _run_brain_plan raising across 3 cycles is bounded to 1 attempt via pre-claim."""
        issue = _make_issue(key="VMER-2464", status="To Do")
        issue["fields"]["comment"]["comments"] = [_make_bot_analysis_comment()]
        await jira_head._set_issue_state("VMER-2464", {"phase": "event_created", "event_id": "evt-dup-1"})
        dup_ev = _make_stub_jira_event(status="closed", issue_key="VMER-2464", close_evidence="duplicate")
        stub_blackboard.get_event = AsyncMock(return_value=dup_ev)

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, side_effect=RuntimeError("LLM down")) as mock_plan,
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock) as mock_create,
        ):
            for _ in range(3):
                await jira_head.poll_and_process()

        assert mock_plan.await_count == 1
        mock_create.assert_not_called()
        state = await jira_head._get_issue_state("VMER-2464")
        assert state["duplicate_retried"] is True

    @pytest.mark.asyncio
    async def test_bot_comment_recovery_bounded_when_create_event_or_post_state_write_raises(
        self, jira_head, stub_blackboard
    ):
        """Bot-comment recovery stays bounded to 1 attempt if create_jira_event raises, AND if
        post-create _set_issue_state raises after creating an event that subsequently closes."""
        # Case A: create_jira_event raises
        issue_a = _make_issue(key="VMER-2464", status="To Do")
        issue_a["fields"]["comment"]["comments"] = [_make_bot_analysis_comment()]
        await jira_head._set_issue_state("VMER-2464", {"phase": "event_created", "event_id": "evt-dup-a"})
        dup_ev = _make_stub_jira_event(status="closed", issue_key="VMER-2464", close_evidence="duplicate")
        stub_blackboard.get_event = AsyncMock(return_value=dup_ev)

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue_a]),
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, return_value="plan: ok"),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, side_effect=RuntimeError("BB write failed")) as mock_create_a,
        ):
            await jira_head.poll_and_process()
            await jira_head.poll_and_process()

        assert mock_create_a.await_count == 1

        # Case B: post-create _set_issue_state raises after pre-claim succeeded
        issue_b = _make_issue(key="VMER-2465", status="To Do")
        issue_b["fields"]["comment"]["comments"] = [_make_bot_analysis_comment()]
        await jira_head._set_issue_state("VMER-2465", {"phase": "event_created", "event_id": "evt-dup-b"})
        dup_ev_b = _make_stub_jira_event(status="closed", issue_key="VMER-2465", close_evidence="duplicate")
        stub_blackboard.get_event = AsyncMock(return_value=dup_ev_b)

        real_set = jira_head._set_issue_state
        call_count = 0

        async def _flaky_set_state(key: str, state: dict) -> None:
            nonlocal call_count
            call_count += 1
            if call_count == 2:
                raise RuntimeError("Redis blip on final save")
            await real_set(key, state)

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue_b]),
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, return_value="plan: ok"),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, return_value="evt-retry-b") as mock_create_b,
            patch.object(jira_head, "_set_issue_state", side_effect=_flaky_set_state),
        ):
            await jira_head.poll_and_process()
            # Next poll: even with retry event already closed, pre-claimed duplicate_retried blocks a 2nd event
            await jira_head.poll_and_process()

        mock_create_b.assert_called_once()
        state_b = await jira_head._get_issue_state("VMER-2465")
        assert state_b["duplicate_retried"] is True

    @pytest.mark.asyncio
    async def test_direct_to_todo_duplicate_retry_preserves_flag_across_record_analysis_failure(
        self, jira_head, stub_blackboard
    ):
        """Direct-to-To-Do retry: when _run_claude_analysis runs and _run_brain_plan raises on cycle 1,
        _record_analysis must persist duplicate_retried=True on phase='analyzed'; cycle 2 creates the event
        preserving duplicate_retried=True; cycle 3 stays parked even if the retry event closes as duplicate."""
        issue = _make_issue(key="VMER-2464", status="To Do")
        await jira_head._set_issue_state("VMER-2464", {"phase": "event_created", "event_id": "evt-dup-1"})

        dup_events = {
            "evt-dup-1": _make_stub_jira_event(status="closed", issue_key="VMER-2464", close_evidence="duplicate"),
            "evt-retry-2": _make_stub_jira_event(status="closed", issue_key="VMER-2464", close_evidence="duplicate"),
        }
        stub_blackboard.get_event = AsyncMock(side_effect=lambda eid: dup_events.get(eid))

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "_resolve_system_prompt", new_callable=AsyncMock, return_value="prompt"),
            patch.object(jira_head, "_run_claude_analysis", new_callable=AsyncMock, return_value="Fresh analysis") as mock_analyze,
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, side_effect=RuntimeError("transient")) as mock_plan,
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, return_value="evt-retry-2") as mock_create,
        ):
            # Cycle 1: analysis runs & caches, then _run_brain_plan raises
            await jira_head.poll_and_process()

            mock_analyze.assert_called_once()
            mock_create.assert_not_called()
            state_after_c1 = await jira_head._get_issue_state("VMER-2464")
            assert state_after_c1["phase"] == "analyzed"
            assert state_after_c1["analysis"] == "Fresh analysis"
            assert state_after_c1.get("duplicate_retried") is True
            assert state_after_c1.get("plan_failures") == 1

            # Cycle 2: _run_brain_plan succeeds, reuses cached analysis, creates event with duplicate_retried=True
            mock_plan.side_effect = None
            mock_plan.return_value = "plan: ok"
            await jira_head.poll_and_process()

            mock_analyze.assert_called_once()
            mock_create.assert_called_once()
            state_after_c2 = await jira_head._get_issue_state("VMER-2464")
            assert state_after_c2["phase"] == "event_created"
            assert state_after_c2["event_id"] == "evt-retry-2"
            assert state_after_c2.get("duplicate_retried") is True

            # Cycle 3: even if evt-retry-2 also closes as duplicate, never >1 created event
            await jira_head.poll_and_process()
            mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_direct_to_todo_persistent_brain_plan_failure_bounded_at_max_retries(
        self, jira_head, stub_blackboard
    ):
        """Direct-to-To-Do recovery with persistent _run_brain_plan errors stops at _MAX_RECOVERY_PLAN_FAILURES (2)."""
        issue = _make_issue(key="VMER-2464", status="To Do")
        await jira_head._set_issue_state("VMER-2464", {"phase": "event_created", "event_id": "evt-dup-1"})
        dup_ev = _make_stub_jira_event(status="closed", issue_key="VMER-2464", close_evidence="duplicate")
        stub_blackboard.get_event = AsyncMock(return_value=dup_ev)

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "_resolve_system_prompt", new_callable=AsyncMock, return_value="prompt"),
            patch.object(jira_head, "_run_claude_analysis", new_callable=AsyncMock, return_value="Fresh analysis") as mock_analyze,
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, side_effect=RuntimeError("persistent")) as mock_plan,
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock) as mock_create,
        ):
            for _ in range(4):
                await jira_head.poll_and_process()

        assert mock_analyze.await_count == 1
        assert mock_plan.await_count == jira_head._MAX_RECOVERY_PLAN_FAILURES
        mock_create.assert_not_called()
        state = await jira_head._get_issue_state("VMER-2464")
        assert state["phase"] == "analyzed"
        assert state["plan_failures"] == jira_head._MAX_RECOVERY_PLAN_FAILURES

    @pytest.mark.asyncio
    @pytest.mark.parametrize("corrupt_payload", ["{bad", "[]"])
    async def test_poll_phase2_isolates_corrupt_redis_state_per_issue(
        self, jira_head, stub_blackboard, caplog, corrupt_payload
    ):
        """Corrupt JSON or non-dict JSON in Redis for VMER-2461 fails closed while VMER-2462 still proceeds."""
        bad_issue = _make_issue(key="VMER-2461", status="To Do")
        healthy_issue = _make_issue(key="VMER-2462", status="To Do")
        healthy_issue["fields"]["comment"]["comments"] = [_make_bot_analysis_comment()]
        stub_blackboard.redis._store[f"{jira_head.REDIS_PREFIX}VMER-2461"] = corrupt_payload

        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[bad_issue, healthy_issue]),
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, return_value="plan: ok"),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, return_value="evt-2462") as mock_create,
            caplog.at_level("WARNING", logger="src.agents.headhunter_jira"),
        ):
            await jira_head.poll_and_process()

        mock_create.assert_called_once()
        assert mock_create.call_args[0][0]["key"] == "VMER-2462"
        assert any("VMER-2461" in r.message for r in caplog.records)


class TestShouldRetryDuplicateEvent:
    """Direct unit tests for HeadhunterJira._should_retry_duplicate_event edge cases."""

    @pytest.mark.asyncio
    async def test_multi_close_turns_uses_latest_close_turn(self, jira_head, stub_blackboard):
        """Reverse scan inspects the most recent close turn."""
        ev_resolved_last = _make_stub_jira_event(
            status="closed",
            turns=[_make_turn_stub("close", "duplicate"), _make_turn_stub("close", "resolved")],
        )
        stub_blackboard.get_event = AsyncMock(return_value=ev_resolved_last)
        assert await jira_head._should_retry_duplicate_event("VMER-2464", {"event_id": "evt-1"}) is False

        ev_dup_last = _make_stub_jira_event(
            status="closed",
            turns=[_make_turn_stub("close", "resolved"), _make_turn_stub("close", "duplicate")],
        )
        stub_blackboard.get_event = AsyncMock(return_value=ev_dup_last)
        assert await jira_head._should_retry_duplicate_event("VMER-2464", {"event_id": "evt-1"}) is True

    @pytest.mark.asyncio
    async def test_closed_event_without_close_turns_returns_false(self, jira_head, stub_blackboard):
        """Closed event with no action='close' turn fails closed (False)."""
        ev = _make_stub_jira_event(status="closed", turns=[_make_turn_stub("triage", None)])
        stub_blackboard.get_event = AsyncMock(return_value=ev)
        assert await jira_head._should_retry_duplicate_event("VMER-2464", {"event_id": "evt-1"}) is False

    @pytest.mark.asyncio
    async def test_active_non_closed_event_returns_false(self, jira_head, stub_blackboard):
        """Non-closed event returns False even if a close turn exists."""
        ev = _make_stub_jira_event(status="active", turns=[_make_turn_stub("close", "duplicate")])
        stub_blackboard.get_event = AsyncMock(return_value=ev)
        assert await jira_head._should_retry_duplicate_event("VMER-2464", {"event_id": "evt-1"}) is False

    @pytest.mark.asyncio
    async def test_dict_shaped_turns_supported(self, jira_head, stub_blackboard):
        """Dict-shaped conversation turns are handled identically to ConversationTurn models."""
        ev = _make_stub_jira_event(
            status="closed",
            turns=[
                {"action": "triage", "evidence": None},
                {"action": "close", "evidence": "duplicate"},
            ],
        )
        stub_blackboard.get_event = AsyncMock(return_value=ev)
        assert await jira_head._should_retry_duplicate_event("VMER-2464", {"event_id": "evt-1"}) is True
