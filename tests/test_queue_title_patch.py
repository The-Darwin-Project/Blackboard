# BlackBoard/tests/test_queue_title_patch.py
# @ai-rules:
# 1. [Constraint]: Tests for PATCH /queue/{event_id}/title (T-5, T-SEC-1, T-SEC-2, T-SEC-3, T-SEC-6).
# 2. [Pattern]: ASGITransport + httpx.AsyncClient with mocked dependencies.
# 3. [Security]: Covers 401 unauthenticated, 403 IDOR/unowned, 422 validation, 409 closed state, and idempotency.
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
