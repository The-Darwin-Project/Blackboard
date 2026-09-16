import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from src.adapters.dashboard_ws import DashboardWSAdapter
from src.models import EventDocument, EventInput, EventEvidence
from src import auth

@pytest.mark.asyncio
async def test_dashboard_ws_rejects_anonymous_with_4001(monkeypatch):
    """When auth is enabled and caller is anonymous, WS closes with 4001."""
    monkeypatch.setattr(auth, "DEX_ENABLED", True)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
    
    mock_brain = MagicMock()
    mock_blackboard = MagicMock()
    adapter = DashboardWSAdapter(brain=mock_brain, blackboard=mock_blackboard, auth_enabled=True)
    
    ws = AsyncMock()
    ws.headers = {}
    ws.query_params = {}
    
    await adapter.websocket_handler(ws)
    
    ws.close.assert_called_once_with(code=4001)

@pytest.mark.asyncio
async def test_dashboard_ws_handle_user_message_unowned_event(monkeypatch):
    """An authenticated operator replying to an unowned event succeeds."""
    monkeypatch.setattr(auth, "DEX_ENABLED", True)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
    monkeypatch.setattr(auth, "_validate_jwt", lambda token: {"sub": "u1", "email": "operator@example.com", "name": "Op"})
    
    mock_event = EventDocument(
        event_id="evt-123",
        source="headhunter",
        service="test",
        event=EventInput(reason="test", evidence=EventEvidence(display_text="test", source_type="chat", domain="disorder", severity="info")),
        created_by_email=None,
        status="active"
    )
    
    mock_blackboard = MagicMock()
    mock_blackboard.get_event = AsyncMock(return_value=mock_event)
    mock_blackboard.append_turn = AsyncMock()
    
    mock_brain = MagicMock()
    
    adapter = DashboardWSAdapter(brain=mock_brain, blackboard=mock_blackboard, auth_enabled=True)
    
    # Simulate connection
    ws = AsyncMock()
    ws.headers = {}
    ws.query_params = {"token": "valid-jwt"}
    
    # We need to simulate receive_json yielding our message, then raising disconnect
    ws.receive_json = AsyncMock(side_effect=[
        {
            "type": "user_message",
            "event_id": "evt-123",
            "message": "I will handle this"
        },
        Exception("disconnect")
    ])
    
    await adapter.websocket_handler(ws)
    
    mock_blackboard.append_turn.assert_awaited()

@pytest.mark.asyncio
async def test_dashboard_ws_handle_user_message_mismatched_owner(monkeypatch):
    """An operator replying to an event owned by someone else is denied."""
    monkeypatch.setattr(auth, "DEX_ENABLED", True)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
    monkeypatch.setattr(auth, "_validate_jwt", lambda token: {"sub": "u1", "email": "operator@example.com", "name": "Op"})
    
    mock_event = EventDocument(
        event_id="evt-123",
        source="chat",
        service="test",
        event=EventInput(reason="test", evidence=EventEvidence(display_text="test", source_type="chat", domain="disorder", severity="info")),
        created_by_email="other@example.com",
        status="active"
    )
    
    mock_blackboard = MagicMock()
    mock_blackboard.get_event = AsyncMock(return_value=mock_event)
    
    mock_brain = MagicMock()
    
    adapter = DashboardWSAdapter(brain=mock_brain, blackboard=mock_blackboard, auth_enabled=True)
    
    ws = AsyncMock()
    ws.headers = {}
    ws.query_params = {"token": "valid-jwt"}
    
    ws.receive_json = AsyncMock(side_effect=[
        {
            "type": "user_message",
            "event_id": "evt-123",
            "message": "Let me hijack this"
        },
        Exception("disconnect")
    ])
    
    await adapter.websocket_handler(ws)
    
    # Assert error was sent
    ws.send_json.assert_any_call({
        "type": "error",
        "kind": "auth_rejected",
        "event_id": "evt-123",
        "message": "Not authorized to post to this event"
    })

@pytest.mark.asyncio
async def test_dashboard_ws_handle_approve_ignores_ownership(monkeypatch):
    """_handle_approve has no ownership check today and must NOT gain one."""
    monkeypatch.setattr(auth, "DEX_ENABLED", True)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
    monkeypatch.setattr(auth, "_validate_jwt", lambda token: {"sub": "u1", "email": "other@example.com", "name": "Op"})
    
    mock_event = EventDocument(
        event_id="evt-123",
        source="chat",
        service="test",
        event=EventInput(reason="test", evidence=EventEvidence(display_text="test", source_type="chat", domain="disorder", severity="info")),
        created_by_email="owner@example.com",
        status="waiting_approval"
    )
    
    mock_blackboard = MagicMock()
    mock_blackboard.get_event = AsyncMock(return_value=mock_event)
    mock_blackboard.append_turn = AsyncMock()
    
    mock_brain = MagicMock()
    mock_brain.resume_if_parked = AsyncMock(return_value=True)
    mock_brain.enqueue_for_processing = MagicMock()
    
    adapter = DashboardWSAdapter(brain=mock_brain, blackboard=mock_blackboard, auth_enabled=True)
    
    ws = AsyncMock()
    ws.headers = {}
    ws.query_params = {"token": "valid-jwt"}
    
    ws.receive_json = AsyncMock(side_effect=[
        {
            "type": "approve",
            "event_id": "evt-123"
        },
        Exception("disconnect")
    ])
    
    await adapter.websocket_handler(ws)
    
    mock_blackboard.append_turn.assert_awaited()

@pytest.mark.asyncio
async def test_dashboard_ws_handle_emergency_stop_ignores_ownership(monkeypatch):
    """_handle_emergency_stop has no ownership check today and must NOT gain one."""
    monkeypatch.setattr(auth, "DEX_ENABLED", True)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
    monkeypatch.setattr(auth, "_validate_jwt", lambda token: {"sub": "u1", "email": "other@example.com", "name": "Op"})
    
    mock_event = EventDocument(
        event_id="evt-123",
        source="chat",
        service="test",
        event=EventInput(reason="test", evidence=EventEvidence(display_text="test", source_type="chat", domain="disorder", severity="info")),
        created_by_email="owner@example.com",
        status="active"
    )
    
    mock_blackboard = MagicMock()
    mock_blackboard.get_event = AsyncMock(return_value=mock_event)
    mock_blackboard.append_turn = AsyncMock()
    
    mock_brain = MagicMock()
    mock_brain.emergency_stop = AsyncMock(return_value=1)
    
    adapter = DashboardWSAdapter(brain=mock_brain, blackboard=mock_blackboard, auth_enabled=True)
    
    ws = AsyncMock()
    ws.headers = {}
    ws.query_params = {"token": "valid-jwt"}
    
    ws.receive_json = AsyncMock(side_effect=[
        {
            "type": "emergency_stop",
            "event_id": "evt-123"
        },
        Exception("disconnect")
    ])
    
    await adapter.websocket_handler(ws)
    
    mock_brain.emergency_stop.assert_awaited()
