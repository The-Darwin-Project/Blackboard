# BlackBoard/tests/test_queue_title_patch.py
# @ai-rules:
# 1. [Constraint]: Tests for PATCH /queue/{event_id}/title (T-5, T-SEC-1, T-SEC-2, T-SEC-3, T-SEC-6).
# 2. [Pattern]: ASGITransport + httpx.AsyncClient with mocked dependencies.
# 3. [Pattern]: Real-state (fakeredis BlackboardState) tests race PATCH vs generate_event_title; can_rename_event matrix.
# 4. [Security]: Covers 401 unauthenticated, 403 IDOR/unowned, 422 validation, 409 closed state, and idempotency.
"""Route-level tests for PATCH /queue/{event_id}/title endpoint."""
from __future__ import annotations

import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.auth import UserContext
from src.models import EventDocument, EventEvidence, EventInput, EventStatus


def _make_event_doc(
    event_id: str = "evt-title01",
    source: str = "chat",
    created_by_email: str | None = "owner@redhat.com",
    title: str | None = "Original Fallback",
    title_source: str | None = "fallback",
    status: EventStatus = EventStatus.ACTIVE,
) -> EventDocument:
    return EventDocument(
        id=event_id,
        source=source,
        service="general",
        status=status,
        title=title,
        title_source=title_source,
        created_by_email=created_by_email,
        event=EventInput(
            reason="test",
            evidence=EventEvidence(
                display_text="test",
                source_type="chat",
                domain="disorder",
                severity="info",
            ),
        ),
    )


async def _patch_title(
    event_id: str,
    json_body: dict,
    user_context: UserContext,
    mock_bb: AsyncMock,
    mock_brain: AsyncMock,
    dex_enabled: bool = False,
    headers: dict | None = None,
):
    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        from src import auth, dependencies
        from src.main import app

        original_bb = dependencies._blackboard
        original_brain = dependencies._brain
        dependencies._blackboard = mock_bb
        dependencies._brain = mock_brain

        req_headers = dict(headers or {})
        try:
            with patch("src.routes.queue.get_user_from_request", return_value=user_context), \
                 patch.object(auth, "DEX_ENABLED", dex_enabled):
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    return await client.patch(
                        f"/queue/{event_id}/title",
                        json=json_body,
                        headers=req_headers,
                    )
        finally:
            dependencies._blackboard = original_bb
            dependencies._brain = original_brain


@pytest.mark.asyncio
async def test_patch_title_success():
    """T-5: Active event rename by owner succeeds with 200, stamps doc, broadcasts."""
    event = _make_event_doc("evt-001", created_by_email="owner@redhat.com")
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()

    mock_brain = AsyncMock()
    mock_brain.broadcast = AsyncMock()

    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])

    resp = await _patch_title(
        "evt-001",
        {"title": "Fix Redis Cluster OOM"},
        user,
        mock_bb,
        mock_brain,
        dex_enabled=True,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == "evt-001"
    assert data["title"] == "Fix Redis Cluster OOM"
    assert data["title_source"] == "user"

    mock_bb.stamp_event.assert_awaited_once_with(
        "evt-001", title="Fix Redis Cluster OOM", title_source="user"
    )
    mock_brain.broadcast.assert_awaited_once_with(
        {
            "type": "event_title_updated",
            "event_id": "evt-001",
            "title": "Fix Redis Cluster OOM",
            "title_source": "user",
        }
    )


@pytest.mark.asyncio
async def test_patch_title_unauthenticated():
    """Returns 401 when auth is enabled and user is anonymous."""
    event = _make_event_doc("evt-002", created_by_email="owner@redhat.com")
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()
    mock_brain = AsyncMock()

    anonymous_user = UserContext()  # email is "" / None

    resp = await _patch_title(
        "evt-002",
        {"title": "New Title"},
        anonymous_user,
        mock_bb,
        mock_brain,
        dex_enabled=True,
    )

    assert resp.status_code == 401
    assert "Authentication required" in resp.json()["detail"]
    mock_bb.stamp_event.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_idor_blocked(caplog):
    """T-SEC-2: Returns 403 when user is not the owner and not admin; logs audit warning."""
    event = _make_event_doc("evt-003", created_by_email="owner@redhat.com")
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()
    mock_brain = AsyncMock()

    other_user = UserContext(email="other@redhat.com", user_id="u2", roles=[])

    with caplog.at_level(logging.WARNING):
        resp = await _patch_title(
            "evt-003",
            {"title": "Hacked Title"},
            other_user,
            mock_bb,
            mock_brain,
            dex_enabled=True,
        )

    assert resp.status_code == 403
    mock_bb.stamp_event.assert_not_called()
    assert any("[Audit] Denied title rename" in record.message for record in caplog.records)


@pytest.mark.asyncio
async def test_patch_title_unowned_event_blocked():
    """T-SEC-1: Automated/unowned event returns 403 for non-admin user."""
    event = _make_event_doc("evt-004", source="aligner", created_by_email=None)
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()
    mock_brain = AsyncMock()

    user = UserContext(email="dev@redhat.com", user_id="u3", roles=[])

    resp = await _patch_title(
        "evt-004",
        {"title": "Rename Aligner"},
        user,
        mock_bb,
        mock_brain,
        dex_enabled=True,
    )

    assert resp.status_code == 403
    mock_bb.stamp_event.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_whitespace_rejected():
    """T-SEC-3: Whitespace-only title is rejected with 422 Unprocessable Entity."""
    event = _make_event_doc("evt-005", created_by_email="owner@redhat.com")
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()
    mock_brain = AsyncMock()

    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])

    resp = await _patch_title(
        "evt-005",
        {"title": "   \n\t  "},
        user,
        mock_bb,
        mock_brain,
        dex_enabled=False,
    )

    assert resp.status_code == 422
    mock_bb.stamp_event.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_too_long_rejected():
    """Title exceeding 100 characters is rejected with 422."""
    event = _make_event_doc("evt-006", created_by_email="owner@redhat.com")
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()
    mock_brain = AsyncMock()

    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])

    resp = await _patch_title(
        "evt-006",
        {"title": "a" * 101},
        user,
        mock_bb,
        mock_brain,
        dex_enabled=False,
    )

    assert resp.status_code == 422
    mock_bb.stamp_event.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_closed_conflict():
    """T-SEC-6: Closed event returns 409 Conflict."""
    event = _make_event_doc("evt-007", created_by_email="owner@redhat.com", status=EventStatus.CLOSED)
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()
    mock_brain = AsyncMock()

    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])

    resp = await _patch_title(
        "evt-007",
        {"title": "Reopen Name"},
        user,
        mock_bb,
        mock_brain,
        dex_enabled=False,
    )

    assert resp.status_code == 409
    assert "Cannot rename closed event" in resp.json()["detail"]
    mock_bb.stamp_event.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_resolved_conflict():
    """Resolved event returns 409 Conflict."""
    event = _make_event_doc("evt-007b", created_by_email="owner@redhat.com", status=EventStatus.RESOLVED)
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()
    mock_brain = AsyncMock()

    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])

    resp = await _patch_title(
        "evt-007b",
        {"title": "Reopen Resolved"},
        user,
        mock_bb,
        mock_brain,
        dex_enabled=False,
    )

    assert resp.status_code == 409
    assert "Cannot rename closed event" in resp.json()["detail"]
    mock_bb.stamp_event.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_idempotent():
    """Unchanged title returns 200 immediately without writing or broadcasting."""
    event = _make_event_doc(
        "evt-008",
        created_by_email="owner@redhat.com",
        title="Same Title",
        title_source="user",
    )
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()
    mock_brain = AsyncMock()
    mock_brain.broadcast = AsyncMock()

    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])

    resp = await _patch_title(
        "evt-008",
        {"title": "Same Title"},
        user,
        mock_bb,
        mock_brain,
        dex_enabled=False,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Same Title"
    assert data["title_source"] == "user"
    mock_bb.stamp_event.assert_not_called()
    mock_brain.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_idempotent_from_fallback_locks_user():
    """T-IDEMP-FALLBACK: PATCH with identical title to current fallback locks ownership as 'user'."""
    event = _make_event_doc(
        "evt-008b",
        created_by_email="owner@redhat.com",
        title="Same Fallback Title",
        title_source="fallback",
    )
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()
    mock_brain = AsyncMock()
    mock_brain.broadcast = AsyncMock()

    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])

    resp = await _patch_title(
        "evt-008b",
        {"title": "Same Fallback Title"},
        user,
        mock_bb,
        mock_brain,
        dex_enabled=False,
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Same Fallback Title"
    assert data["title_source"] == "user"
    mock_bb.stamp_event.assert_awaited_once_with(
        "evt-008b", title="Same Fallback Title", title_source="user"
    )
    mock_brain.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_not_found():
    """Non-existent event returns 404 Not Found."""
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=None)
    mock_brain = AsyncMock()

    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])

    resp = await _patch_title(
        "evt-missing",
        {"title": "Any Title"},
        user,
        mock_bb,
        mock_brain,
        dex_enabled=False,
    )

    assert resp.status_code == 404
    assert "Event not found" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_patch_title_admin_override():
    """Admin/approver role permits renaming events created by another user."""
    event = _make_event_doc("evt-009", created_by_email="user1@redhat.com")
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.stamp_event = AsyncMock()
    mock_brain = AsyncMock()
    mock_brain.broadcast = AsyncMock()

    admin_user = UserContext(
        email="admin@redhat.com",
        user_id="u_admin",
        roles=["darwin-approvers"],
    )

    from src import auth
    with patch.object(auth, "APPROVER_GROUPS", frozenset({"darwin-approvers"})):
        resp = await _patch_title(
            "evt-009",
            {"title": "Admin Override Title"},
            admin_user,
            mock_bb,
            mock_brain,
            dex_enabled=True,
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["title"] == "Admin Override Title"
    mock_bb.stamp_event.assert_awaited_once_with(
        "evt-009", title="Admin Override Title", title_source="user"
    )


# ---------------------------------------------------------------------------------------------
# M16: can_rename_event unit tests + PATCH authorization / validation edge cases
# ---------------------------------------------------------------------------------------------
from src import auth  # noqa: E402
from src.auth import can_rename_event  # noqa: E402


@pytest.fixture
def groups():
    """Configured approver / obs-admin groups (mixed case on purpose)."""
    with patch.object(auth, "APPROVER_GROUPS", frozenset({"darwin-approvers"})), \
         patch.object(auth, "OBS_ADMIN_GROUPS", frozenset({"Obs-Admins"})):
        yield


@pytest.mark.parametrize(
    "created_by,user_email,source,roles,auth_enabled,expected",
    [
        # owner
        ("owner@redhat.com", "owner@redhat.com", "chat", [], True, True),
        ("Owner@RedHat.com", " owner@redhat.COM ", "slack", [], True, True),  # normalized email
        ("owner@redhat.com", "other@redhat.com", "chat", [], True, False),
        # approver / obs-admin, incl. case-insensitivity on both sides
        ("owner@redhat.com", "x@redhat.com", "chat", ["darwin-approvers"], True, True),
        ("owner@redhat.com", "x@redhat.com", "chat", ["DARWIN-APPROVERS"], True, True),
        ("owner@redhat.com", "x@redhat.com", "slack", ["obs-admins"], True, True),
        ("owner@redhat.com", "x@redhat.com", "slack", [" OBS-ADMINS "], True, True),
        ("owner@redhat.com", "x@redhat.com", "chat", ["unrelated-group"], True, False),
        # automated sources are never renamable, even by approvers/admins/owners/auth-off
        ("owner@redhat.com", "owner@redhat.com", "aligner", [], True, False),
        ("owner@redhat.com", "x@redhat.com", "headhunter", ["darwin-approvers", "obs-admins"], True, False),
        (None, "x@redhat.com", "kargo", ["obs-admins"], True, False),
        (None, None, "aligner", [], False, False),
        # created_by_email=None: only approver/admin may rename
        (None, "x@redhat.com", "chat", [], True, False),
        (None, None, "chat", [], True, False),  # None == None must NOT authorize
        ("", "", "chat", [], True, False),
        (None, "x@redhat.com", "chat", ["darwin-approvers"], True, True),
        # anonymous caller with auth enabled
        ("owner@redhat.com", None, "chat", [], True, False),
        ("owner@redhat.com", "", "chat", [], True, False),
        # auth disabled -> open for user-initiated sources
        (None, None, "chat", [], False, True),
        ("owner@redhat.com", "other@redhat.com", "slack", [], False, True),
    ],
)
def test_can_rename_event_matrix(groups, created_by, user_email, source, roles, auth_enabled, expected):
    assert can_rename_event(created_by, user_email, source, roles, auth_enabled=auth_enabled) is expected


def test_can_rename_event_unset_groups_fail_closed():
    """No approver/admin groups configured -> roles grant nothing (only ownership works)."""
    with patch.object(auth, "APPROVER_GROUPS", frozenset()), patch.object(auth, "OBS_ADMIN_GROUPS", frozenset()):
        assert can_rename_event("o@x.com", "a@x.com", "chat", ["darwin-approvers", ""], auth_enabled=True) is False
        assert can_rename_event("o@x.com", "o@x.com", "chat", [], auth_enabled=True) is True


def test_can_rename_event_auth_enabled_none_derives_from_flags():
    with patch.object(auth, "DEX_ENABLED", False), patch.object(auth, "TRUSTED_PROXY_ENABLED", False):
        assert can_rename_event(None, None, "chat", []) is True
    with patch.object(auth, "DEX_ENABLED", True), patch.object(auth, "TRUSTED_PROXY_ENABLED", False):
        assert can_rename_event(None, None, "chat", []) is False
    with patch.object(auth, "DEX_ENABLED", False), patch.object(auth, "TRUSTED_PROXY_ENABLED", True):
        assert can_rename_event("o@x.com", "o@x.com", "chat", []) is True
        assert can_rename_event("o@x.com", None, "chat", []) is False


def _mock_bb_for(event: EventDocument | None):
    bb = AsyncMock()
    bb.get_event = AsyncMock(return_value=event)
    bb.stamp_event = AsyncMock()
    return bb


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status",
    [EventStatus.NEW, EventStatus.ACTIVE, EventStatus.WAITING_APPROVAL, EventStatus.DEFERRED],
)
async def test_patch_title_allowed_for_open_statuses(status):
    """deferred / waiting_approval / new / active events can be renamed."""
    event = _make_event_doc("evt-st", status=status)
    bb, brain = _mock_bb_for(event), AsyncMock()
    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])
    resp = await _patch_title("evt-st", {"title": "Renamed While Open"}, user, bb, brain, dex_enabled=True)
    assert resp.status_code == 200, resp.text
    bb.stamp_event.assert_awaited_once_with("evt-st", title="Renamed While Open", title_source="user")


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [EventStatus.CLOSED, EventStatus.RESOLVED])
async def test_patch_title_closed_resolved_409_even_for_admin(status, groups):
    event = _make_event_doc("evt-cl", status=status)
    bb, brain = _mock_bb_for(event), AsyncMock()
    admin = UserContext(email="a@redhat.com", user_id="a", roles=["darwin-approvers"])
    resp = await _patch_title("evt-cl", {"title": "Nope"}, admin, bb, brain, dex_enabled=True)
    assert resp.status_code == 409
    bb.stamp_event.assert_not_called()
    brain.broadcast.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_email,roles,expected_status",
    [
        ("owner@redhat.com", [], 200),
        ("OWNER@RedHat.com", [], 200),                 # email case-insensitive
        ("x@redhat.com", ["darwin-approvers"], 200),   # approver
        ("x@redhat.com", ["DARWIN-APPROVERS"], 200),   # approver, case-insensitive
        ("x@redhat.com", ["obs-admins"], 200),         # OBS_ADMIN_GROUPS case-insensitive ("Obs-Admins")
        ("x@redhat.com", ["OBS-ADMINS"], 200),
        ("x@redhat.com", [], 403),
    ],
)
async def test_patch_title_authz_matrix(groups, user_email, roles, expected_status):
    event = _make_event_doc("evt-az", created_by_email="owner@redhat.com")
    bb, brain = _mock_bb_for(event), AsyncMock()
    user = UserContext(email=user_email, user_id="u", roles=roles)
    resp = await _patch_title("evt-az", {"title": "Authz Title"}, user, bb, brain, dex_enabled=True)
    assert resp.status_code == expected_status, resp.text
    assert bb.stamp_event.await_count == (1 if expected_status == 200 else 0)


@pytest.mark.asyncio
@pytest.mark.parametrize("source", ["aligner", "headhunter", "timekeeper", "jarvis"])
async def test_patch_title_automated_source_rejected_even_for_admin(groups, source):
    event = _make_event_doc("evt-auto", source=source, created_by_email=None)
    bb, brain = _mock_bb_for(event), AsyncMock()
    admin = UserContext(email="a@redhat.com", user_id="a", roles=["darwin-approvers", "obs-admins"])
    resp = await _patch_title("evt-auto", {"title": "Rename Automated"}, admin, bb, brain, dex_enabled=True)
    assert resp.status_code == 403
    bb.stamp_event.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_created_by_email_none_non_admin_forbidden(groups):
    event = _make_event_doc("evt-noown", source="chat", created_by_email=None)
    bb, brain = _mock_bb_for(event), AsyncMock()
    user = UserContext(email="dev@redhat.com", user_id="d", roles=[])
    resp = await _patch_title("evt-noown", {"title": "Claim Orphan"}, user, bb, brain, dex_enabled=True)
    assert resp.status_code == 403
    bb.stamp_event.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_slack_event_owner_allowed():
    event = _make_event_doc("evt-slack", source="slack", created_by_email="owner@redhat.com")
    bb, brain = _mock_bb_for(event), AsyncMock()
    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])
    resp = await _patch_title("evt-slack", {"title": "Slack Rename"}, user, bb, brain, dex_enabled=True)
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_patch_title_auth_disabled_allows_anonymous_on_chat_event():
    event = _make_event_doc("evt-open", created_by_email=None)
    bb, brain = _mock_bb_for(event), AsyncMock()
    resp = await _patch_title("evt-open", {"title": "Open Rename"}, UserContext(), bb, brain, dex_enabled=False)
    assert resp.status_code == 200
    bb.stamp_event.assert_awaited_once_with("evt-open", title="Open Rename", title_source="user")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "title,expected_status,expected_title",
    [
        ("x" * 100, 200, "x" * 100),                   # boundary: exactly 100 accepted
        ("x" * 101, 422, None),                        # boundary: 101 rejected
        ("  " + "x" * 100 + "  ", 200, "x" * 100),     # trimmed before the length check
        ("Fix deploy\nrollback", 200, "Fix deploy rollback"),   # newline -> space, NOT "deployrollback"
        ("Fix deploy\r\nrollback", 200, "Fix deploy rollback"),
        ("Fix\tdeploy", 200, "Fix deploy"),
        ("a    b \n\n c", 200, "a b c"),               # whitespace collapse
        ("Zero​Width‮Bidi", 200, "ZeroWidthBidi"),
        ("", 422, None),
        ("   ", 422, None),
        ("\n\t\r", 422, None),
        ("​", 422, None),                         # zero-width only
        ("​‍﻿⁠", 422, None),
        ("‮⁦⁩", 422, None),             # bidi only
        ("\x00\x07\x1f\x7f\x85\x9f", 422, None),       # C0 / DEL / C1 only
    ],
)
async def test_patch_title_validation_edges(title, expected_status, expected_title):
    event = _make_event_doc("evt-val")
    bb, brain = _mock_bb_for(event), AsyncMock()
    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])
    resp = await _patch_title("evt-val", {"title": title}, user, bb, brain, dex_enabled=True)
    assert resp.status_code == expected_status, resp.text
    if expected_title is None:
        bb.stamp_event.assert_not_called()
    else:
        assert resp.json()["title"] == expected_title
        bb.stamp_event.assert_awaited_once_with("evt-val", title=expected_title, title_source="user")


@pytest.mark.asyncio
@pytest.mark.parametrize("body", [{}, {"title": None}, {"title": 123}, {"name": "wrong key"}])
async def test_patch_title_invalid_body_422(body):
    event = _make_event_doc("evt-body")
    bb, brain = _mock_bb_for(event), AsyncMock()
    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])
    resp = await _patch_title("evt-body", body, user, bb, brain, dex_enabled=True)
    assert resp.status_code == 422
    bb.stamp_event.assert_not_called()


# ---------------------------------------------------------------------------------------------
# H2: real BlackboardState (fakeredis) -- PATCH vs. background LLM naming, both interleavings
# ---------------------------------------------------------------------------------------------
import asyncio  # noqa: E402
import json  # noqa: E402

import fakeredis.aioredis  # noqa: E402

from src.agents import event_namer  # noqa: E402
from src.agents.llm.types import LLMResponse  # noqa: E402
from src.state.blackboard import BlackboardState  # noqa: E402


@pytest.fixture
async def real_bb():
    state = BlackboardState.__new__(BlackboardState)
    state.redis = fakeredis.aioredis.FakeRedis()
    state.EVENT_PREFIX = "darwin:event:"
    state.EVENT_QUEUE = "darwin:queue"
    state.EVENT_ACTIVE = "darwin:events:active"
    state.EVENT_WAITING_APPROVAL = "darwin:events:waiting_approval"
    state.EVENT_CLOSED = "darwin:events:closed"
    state.SLACK_THREAD_PREFIX = "darwin:slack:thread:"
    event_namer._adapter_instance = None
    event_namer._namer_semaphore = None
    yield state
    event_namer._adapter_instance = None
    event_namer._namer_semaphore = None
    await state.redis.aclose()


async def _seed_real_event(bb: BlackboardState, event_id: str) -> None:
    doc = _make_event_doc(event_id, title="Fallback Title", title_source="fallback")
    await bb.redis.set(f"darwin:event:{event_id}", json.dumps(doc.model_dump(mode="json")))


@pytest.mark.asyncio
@pytest.mark.parametrize("order", ["patch_lands_first", "llm_lands_first", "llm_completes_mid_patch_window"])
async def test_patch_and_llm_naming_concurrently_user_title_always_wins(real_bb, order):
    """H2: PATCH /queue/{id}/title and generate_event_title raced via asyncio.gather on real state.

    Whatever the interleaving, the stored doc ends with title_source == "user" and the user's
    title, and the LLM never broadcasts a title that was overwritten/blocked by the user.
    """
    event_id = "evt-race-" + order
    await _seed_real_event(real_bb, event_id)

    llm_entered = asyncio.Event()      # LLM stub has been called (is "in flight")
    release_llm = asyncio.Event()      # lets the LLM stub return
    patch_done = asyncio.Event()

    adapter = AsyncMock()

    async def _delayed_generate(*args, **kwargs):
        llm_entered.set()
        if order == "patch_lands_first":
            await release_llm.wait()           # LLM returns only AFTER the user's PATCH committed
        return LLMResponse(text="LLM Suggested Title")

    adapter.generate = _delayed_generate
    llm_brain = AsyncMock()
    patch_brain = AsyncMock()
    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])

    async def _llm():
        with patch("src.agents.event_namer.create_adapter", return_value=adapter):
            await event_namer.generate_event_title(real_bb, llm_brain, event_id, "help me with redis", "chat")
        if order == "llm_lands_first":
            llm_done.set()

    llm_done = asyncio.Event()

    async def _user_patch():
        await llm_entered.wait()                # LLM request is in flight
        if order == "llm_lands_first":
            await llm_done.wait()               # LLM write commits before the user's rename
        resp = await _patch_title(
            event_id, {"title": "User Chosen Title"}, user, real_bb, patch_brain, dex_enabled=True
        )
        patch_done.set()
        release_llm.set()
        return resp

    _, resp = await asyncio.gather(_llm(), _user_patch())

    assert resp.status_code == 200, resp.text
    doc = await real_bb.get_event(event_id)
    assert doc is not None
    assert doc.title == "User Chosen Title"
    assert doc.title_source == "user"

    patch_brain.broadcast.assert_awaited_once()
    assert patch_brain.broadcast.await_args.args[0]["title_source"] == "user"
    if order == "patch_lands_first":
        llm_brain.broadcast.assert_not_called()     # blocked by in-transaction user re-check
    else:
        llm_brain.broadcast.assert_awaited_once()   # LLM legitimately landed first, then user overwrote


@pytest.mark.asyncio
async def test_patch_then_late_llm_does_not_clobber_user_title_real_state(real_bb):
    """Simple ordering guard on real state: user rename committed, a late LLM result is dropped."""
    event_id = "evt-late-llm"
    await _seed_real_event(real_bb, event_id)
    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])
    resp = await _patch_title(event_id, {"title": "Manual Name"}, user, real_bb, AsyncMock(), dex_enabled=True)
    assert resp.status_code == 200

    brain = AsyncMock()
    adapter = AsyncMock()
    adapter.generate = AsyncMock(return_value=LLMResponse(text="Late LLM Name"))
    with patch("src.agents.event_namer.create_adapter", return_value=adapter):
        await event_namer.generate_event_title(real_bb, brain, event_id, "text", "chat")

    doc = await real_bb.get_event(event_id)
    assert (doc.title, doc.title_source) == ("Manual Name", "user")
    brain.broadcast.assert_not_called()


@pytest.mark.asyncio
async def test_patch_title_real_state_sanitizes_newline_title(real_bb):
    """End-to-end on real state: 'Fix deploy\\nrollback' is persisted as 'Fix deploy rollback'."""
    event_id = "evt-nl"
    await _seed_real_event(real_bb, event_id)
    user = UserContext(email="owner@redhat.com", user_id="u1", roles=[])
    resp = await _patch_title(event_id, {"title": "Fix deploy\nrollback"}, user, real_bb, AsyncMock(), dex_enabled=True)
    assert resp.status_code == 200
    doc = await real_bb.get_event(event_id)
    assert doc.title == "Fix deploy rollback"
    assert doc.title_source == "user"
