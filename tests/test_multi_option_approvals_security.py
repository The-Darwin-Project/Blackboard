"""Security and integrity tests for Multi-Option User Approvals (VMER-2501 Round 3)."""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import fakeredis.aioredis
import pytest
from redis.exceptions import WatchError

from src.adapters.dashboard_ws import DashboardWSAdapter
from src.agents.handlers_state import handle_request_user_approval
from src.auth import UserContext
from src.models import (
    ApprovalOption,
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
    PendingApproval,
    WRITE_IN_OPTION_ID,
)
from src.routes.approval_decision import execute_approval_decision
from src.routes.approval_decision_helpers import DecisionRequest
from src.state.blackboard import BlackboardState


@pytest.fixture
def fake_redis():
    return fakeredis.aioredis.FakeRedis(decode_responses=True)


@pytest.fixture
def blackboard(fake_redis):
    return BlackboardState(fake_redis)


@pytest.fixture
def mock_brain():
    brain = AsyncMock()
    brain.complete_approval_resume = AsyncMock()
    brain.clear_waiting = MagicMock()
    brain.resume_if_parked = AsyncMock(return_value=True)
    brain.enqueue_for_processing = MagicMock()
    return brain


def _make_waiting_event(
    event_id: str,
    *,
    approval_id: str = "apv-current",
    options: list[ApprovalOption] | None = None,
    requested_sha: str | None = None,
    created_by_email: str | None = "owner@redhat.com",
    source: str = "chat",
    github_context: dict | None = None,
) -> EventDocument:
    opts = options if options is not None else [
        ApprovalOption(id="o1", label="Approve", effect="approve"),
        ApprovalOption(id="o2", label="Reject", effect="reject"),
    ]
    req_turn = ConversationTurn(
        turn=1,
        actor="brain",
        action="request_approval",
        thoughts="Proceed?",
        pendingApproval=True,
        approval_id=approval_id,
        approval_options=opts,
    )
    return EventDocument(
        id=event_id,
        source=source,
        status=EventStatus.WAITING_APPROVAL,
        service="test-svc",
        created_by_email=created_by_email,
        event=EventInput(
            reason="test",
            evidence=EventEvidence(
                display_text="test",
                source_type="chat",
                domain="complicated",
                severity="info",
                github_context=github_context,
            ),
        ),
        conversation=[req_turn],
        approval_requested_sha=requested_sha,
        pending_approval=PendingApproval(
            approval_id=approval_id,
            summary="Proceed?",
            options=opts,
            requested_sha=requested_sha,
        ),
    )


async def _seed_event(blackboard: BlackboardState, evt: EventDocument) -> None:
    await blackboard.redis.set(f"{blackboard.EVENT_PREFIX}{evt.id}", evt.model_dump_json())
    await blackboard.redis.sadd(blackboard.EVENT_ACTIVE, evt.id)
    if evt.status == EventStatus.WAITING_APPROVAL:
        await blackboard.redis.sadd(blackboard.EVENT_WAITING_APPROVAL, evt.id)


@pytest.mark.asyncio
async def test_stale_approval_id_rejected_in_cas_and_execute(blackboard, mock_brain):
    evt = _make_waiting_event("evt-sec-stale", approval_id="apv-current")
    await _seed_event(blackboard, evt)

    cas_res = await blackboard.resolve_approval_decision(
        "evt-sec-stale",
        approval_id="apv-old",
        effect="approve",
        approved_by="owner@redhat.com",
    )
    assert cas_res.code == "stale_approval"

    user = UserContext(user_id="u1", email="owner@redhat.com", display_name="Owner")
    outcome = await execute_approval_decision(
        blackboard=blackboard,
        brain=mock_brain,
        event_id="evt-sec-stale",
        user=user,
        auth_enabled=False,
        req=DecisionRequest(approval_id="apv-old", option_id="o1"),
    )
    assert outcome.kind == "stale_approval"
    mock_brain.complete_approval_resume.assert_not_awaited()

    persisted = await blackboard.get_event("evt-sec-stale")
    assert persisted.status == EventStatus.WAITING_APPROVAL
    assert persisted.approved_mr_sha is None
    assert persisted.pending_approval.approval_id == "apv-current"


@pytest.mark.asyncio
async def test_unauthorized_user_rejected_and_logged(blackboard, mock_brain, caplog):
    evt = _make_waiting_event("evt-sec-auth", created_by_email="owner@redhat.com", source="chat")
    await _seed_event(blackboard, evt)
    raw_before = await blackboard.redis.get(f"{blackboard.EVENT_PREFIX}evt-sec-auth")

    stranger = UserContext(user_id="u-stranger", email="stranger@redhat.com", display_name="Stranger", roles=[])
    with caplog.at_level(logging.WARNING, logger="src.routes.approval_decision"):
        outcome = await execute_approval_decision(
            blackboard=blackboard,
            brain=mock_brain,
            event_id="evt-sec-auth",
            user=stranger,
            auth_enabled=True,
            req=DecisionRequest(approval_id="apv-current", option_id="o1"),
            source="dashboard",
        )

    assert outcome.kind == "auth_rejected"
    assert any(
        "Forbidden approval decision attempt" in rec.message and "stranger@redhat.com" in rec.message
        for rec in caplog.records
    )
    assert await blackboard.redis.get(f"{blackboard.EVENT_PREFIX}evt-sec-auth") == raw_before
    mock_brain.complete_approval_resume.assert_not_awaited()


@pytest.mark.asyncio
async def test_sha_conflict_in_cas_and_execute_drift(blackboard, mock_brain):
    evt = _make_waiting_event(
        "evt-sec-sha",
        requested_sha="1111111111111111",
        github_context={"pr_number": 42, "repo": "org/repo", "head_sha": "1111111111111111"},
    )
    await _seed_event(blackboard, evt)

    cas_res = await blackboard.resolve_approval_decision(
        "evt-sec-sha",
        approval_id="apv-current",
        effect="approve",
        expected_sha="1111111111111111",
        approved_by="owner@redhat.com",
        approved_mr_id="42",
        approved_mr_sha="2222222222222222",
    )
    assert cas_res.code == "sha_conflict"

    async def fake_resolver(_event):
        return ("42", "2222222222222222")

    user = UserContext(user_id="u1", email="owner@redhat.com", display_name="Owner")
    outcome = await execute_approval_decision(
        blackboard=blackboard,
        brain=mock_brain,
        event_id="evt-sec-sha",
        user=user,
        auth_enabled=False,
        req=DecisionRequest(approval_id="apv-current", option_id="o1", expected_sha="1111111111111111"),
        head_sha_resolver=fake_resolver,
    )
    assert outcome.kind == "sha_drift"
    assert outcome.expected_sha == "1111111111111111"
    assert outcome.actual_sha == "2222222222222222"

    persisted = await blackboard.get_event("evt-sec-sha")
    assert persisted.status == EventStatus.WAITING_APPROVAL
    assert persisted.approved_mr_sha is None


@pytest.mark.asyncio
async def test_watch_error_exhaustion_returns_stale_approval(blackboard, mock_brain):
    evt = _make_waiting_event("evt-sec-watch")
    await _seed_event(blackboard, evt)
    raw_before = await blackboard.redis.get(f"{blackboard.EVENT_PREFIX}evt-sec-watch")

    user = UserContext(user_id="u1", email="owner@redhat.com", display_name="Owner")
    with patch.object(blackboard, "resolve_approval_decision", side_effect=WatchError("CAS exhausted")):
        outcome = await execute_approval_decision(
            blackboard=blackboard,
            brain=mock_brain,
            event_id="evt-sec-watch",
            user=user,
            auth_enabled=False,
            req=DecisionRequest(approval_id="apv-current", option_id="o1"),
        )

    assert outcome.kind == "stale_approval"
    assert await blackboard.redis.get(f"{blackboard.EVENT_PREFIX}evt-sec-watch") == raw_before
    mock_brain.complete_approval_resume.assert_not_awaited()


@pytest.mark.asyncio
async def test_empty_writein_rejected(blackboard, mock_brain):
    evt = _make_waiting_event("evt-sec-writein")
    await _seed_event(blackboard, evt)
    user = UserContext(user_id="u1", email="owner@redhat.com", display_name="Owner")

    outcome = await execute_approval_decision(
        blackboard=blackboard,
        brain=mock_brain,
        event_id="evt-sec-writein",
        user=user,
        auth_enabled=False,
        req=DecisionRequest(approval_id="apv-current", option_id=WRITE_IN_OPTION_ID, message="   ", image=None),
    )
    assert outcome.kind == "invalid_option"
    persisted = await blackboard.get_event("evt-sec-writein")
    assert persisted.status == EventStatus.WAITING_APPROVAL


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "options",
    [
        [ApprovalOption(id="o1", label="Only one", effect="approve").model_dump()],
        [ApprovalOption(id=f"o{i}", label=f"Opt {i}", effect="steer").model_dump() for i in range(6)],
        [
            ApprovalOption(id="dup", label="First", effect="approve").model_dump(),
            ApprovalOption(id="dup", label="Second", effect="reject").model_dump(),
        ],
        [
            ApprovalOption(id=WRITE_IN_OPTION_ID, label="Reserved", effect="steer").model_dump(),
            ApprovalOption(id="o2", label="Reject", effect="reject").model_dump(),
        ],
    ],
)
async def test_request_user_approval_option_validation_bounds(blackboard, options):
    evt = EventDocument(
        id="evt-sec-bounds",
        source="chat",
        status=EventStatus.ACTIVE,
        service="test-svc",
        event=EventInput(
            reason="test",
            evidence=EventEvidence(display_text="t", source_type="chat", domain="complicated", severity="info"),
        ),
    )
    await _seed_event(blackboard, evt)

    ctx = MagicMock()
    ctx.get_blackboard = MagicMock(return_value=blackboard)
    ctx.append_and_broadcast = AsyncMock()
    ctx.broadcast = AsyncMock()

    res = await handle_request_user_approval(ctx, "evt-sec-bounds", {"plan_summary": "Plan", "options": options}, None)
    assert res is True

    persisted = await blackboard.get_event("evt-sec-bounds")
    assert persisted.status == EventStatus.ACTIVE
    assert persisted.pending_approval is None
    ctx.append_and_broadcast.assert_awaited_once()
    assert ctx.append_and_broadcast.call_args.args[1].action == "tool_result"


@pytest.mark.asyncio
async def test_ws_legacy_approve_and_decision_with_pending_approval(blackboard, mock_brain):
    steer_reject_opts = [
        ApprovalOption(id="steer1", label="Steer", effect="steer"),
        ApprovalOption(id="rej1", label="Reject", effect="reject"),
    ]
    evt = _make_waiting_event("evt-sec-ws1", options=steer_reject_opts)
    await _seed_event(blackboard, evt)

    adapter = DashboardWSAdapter(brain=mock_brain, blackboard=blackboard, auth_enabled=False)
    ws = AsyncMock()
    user = UserContext(user_id="u1", email="owner@redhat.com", display_name="Owner")

    # Legacy approve on steer/reject-only PendingApproval rejects without unparking or sweeping Auto closed
    await adapter._handle_approve(ws, {"event_id": "evt-sec-ws1"}, user)
    ws.send_json.assert_awaited_once()
    err_payload = ws.send_json.await_args.args[0]
    assert err_payload["type"] == "error"
    assert err_payload["kind"] == "invalid_option"

    still_parked = await blackboard.get_event("evt-sec-ws1")
    assert still_parked.status == EventStatus.WAITING_APPROVAL
    assert still_parked.conversation[0].pendingApproval is True
    assert still_parked.conversation[0].approval_resolution is None

    # Decision on the steer option works via _handle_approval_decision
    ws.send_json.reset_mock()
    await adapter._handle_approval_decision(
        ws, {"event_id": "evt-sec-ws1", "approval_id": "apv-current", "option_id": "steer1"}, user
    )
    ws.send_json.assert_awaited_once()
    assert ws.send_json.await_args.args[0]["type"] == "turn"
    steered = await blackboard.get_event("evt-sec-ws1")
    assert steered.status == EventStatus.ACTIVE
    assert steered.conversation[0].approval_resolution.option_id == "steer1"

    # Legacy approve succeeds via CAS when a single approve option exists
    evt2 = _make_waiting_event("evt-sec-ws2")
    await _seed_event(blackboard, evt2)
    ws2 = AsyncMock()
    await adapter._handle_approve(ws2, {"event_id": "evt-sec-ws2"}, user)
    ws2.send_json.assert_awaited_once()
    assert ws2.send_json.await_args.args[0]["type"] == "turn"
    approved = await blackboard.get_event("evt-sec-ws2")
    assert approved.status == EventStatus.ACTIVE
    assert approved.approved_by == "owner@redhat.com"
    assert approved.conversation[0].approval_resolution.option_id == "o1"
