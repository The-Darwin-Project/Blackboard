# tests/test_routes_chat.py
# @ai-rules:
# 1. [Pattern]: ASGITransport + httpx.AsyncClient with dependencies._blackboard/_brain overridden,
#    mirroring tests/test_queue.py's _post_with_mocked_deps helper.
# 2. [Constraint]: Covers the evt-dc56392b UI bug -- REST /chat/ must append to an existing event
#    (mirroring the WS user_message handler) instead of always creating a new one.
"""Route tests for POST /chat/."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient


def _make_event_document(event_id: str, conversation=None):
    from src.models import EventDocument, EventEvidence, EventInput
    doc = EventDocument(
        id=event_id,
        source="chat",
        service="general",
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
    if conversation:
        doc.conversation = conversation
    return doc


async def _post_chat(json_body, mock_bb, mock_brain=None):
    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        from src import dependencies
        from src.main import app

        original_bb = dependencies._blackboard
        original_brain = dependencies._brain
        dependencies._blackboard = mock_bb
        dependencies._brain = mock_brain
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post("/chat/", json=json_body)
        finally:
            dependencies._blackboard = original_bb
            dependencies._brain = original_brain


@pytest.mark.asyncio
async def test_chat_without_event_id_creates_new_event():
    """No event_id -> preserves existing create-new-event behavior."""
    mock_bb = AsyncMock()
    mock_bb.create_event = AsyncMock(return_value="evt-new00001")
    mock_bb.append_turn = AsyncMock(return_value=1)

    resp = await _post_chat({"message": "hello"}, mock_bb)

    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == "evt-new00001"
    assert data["status"] == "created"
    mock_bb.create_event.assert_awaited_once()
    mock_bb.get_event.assert_not_called()


@pytest.mark.asyncio
async def test_chat_with_event_id_appends_to_existing_event():
    """event_id for an active event -> appends a turn instead of creating a new event (evt-dc56392b)."""
    event = _make_event_document("evt-active01")

    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.append_turn = AsyncMock(return_value=1)
    mock_bb.create_event = AsyncMock(side_effect=AssertionError("should not create a new event"))

    mock_brain = MagicMock()
    mock_brain.clear_waiting = MagicMock()
    mock_brain.resume_if_parked = AsyncMock(return_value=True)
    mock_brain.enqueue_for_processing = MagicMock(return_value=True)

    resp = await _post_chat(
        {"message": "reply here", "event_id": "evt-active01"}, mock_bb, mock_brain
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == "evt-active01"
    assert data["status"] == "appended"
    mock_bb.create_event.assert_not_called()
    mock_bb.append_turn.assert_awaited_once()
    appended_event_id, appended_turn = mock_bb.append_turn.await_args.args
    assert appended_event_id == "evt-active01"
    assert appended_turn.actor == "user"
    assert appended_turn.thoughts == "reply here"
    mock_brain.clear_waiting.assert_called_once_with("evt-active01")
    mock_brain.resume_if_parked.assert_awaited_once_with("evt-active01")
    mock_brain.enqueue_for_processing.assert_called_once_with("evt-active01")


@pytest.mark.asyncio
async def test_chat_with_unknown_event_id_falls_back_to_new_event():
    """event_id that no longer exists (e.g. closed/archived) -> falls back to creating a new event."""
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=None)
    mock_bb.create_event = AsyncMock(return_value="evt-new00002")
    mock_bb.append_turn = AsyncMock(return_value=1)

    resp = await _post_chat(
        {"message": "hello again", "event_id": "evt-gone0001"}, mock_bb
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["event_id"] == "evt-new00002"
    assert data["status"] == "created"
    mock_bb.create_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_chat_append_survives_brain_not_initialized():
    """RuntimeError from get_brain() (Brain not initialized) must not fail the request."""
    event = _make_event_document("evt-active02")

    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.append_turn = AsyncMock(return_value=1)

    resp = await _post_chat(
        {"message": "reply", "event_id": "evt-active02"}, mock_bb, mock_brain=None
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "appended"
