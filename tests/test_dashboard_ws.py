from fastapi.testclient import TestClient
from src.main import app
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

def test_dashboard_ws_rejects_anonymous_with_4001(monkeypatch):
    """When auth is enabled and caller is anonymous, WS closes with 4001."""
    monkeypatch.setattr("src.auth.DEX_ENABLED", True)
    monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)
    
    with TestClient(app) as client:
        from fastapi import WebSocketDisconnect
        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect("/ws") as ws:
                ws.receive_text()
        assert exc_info.value.code == 4001

def test_dashboard_ws_handle_user_message_unowned_event(monkeypatch):
    """An authenticated operator replying to an unowned event succeeds."""
    monkeypatch.setattr("src.auth.DEX_ENABLED", True)
    monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)
    
    monkeypatch.setattr("src.auth.decode_jwt", lambda token: {"email": "operator@example.com", "name": "Op"})
    
    from src.models import EventDocument, EventInput
    mock_event = EventDocument(
        event_id="evt-123",
        source="jenkins",
        service="test",
        event=EventInput(reason="test"),
        created_by_email=None,
        status="active"
    )
    
    mock_blackboard = MagicMock()
    mock_blackboard.get_event = AsyncMock(return_value=mock_event)
    mock_blackboard.append_turn = AsyncMock()
    
    app.state.dashboard_adapter._blackboard = mock_blackboard
    
    with TestClient(app) as client:
        with client.websocket_connect("/ws?token=valid-jwt") as ws:
            ws.send_json({
                "type": "user_message",
                "event_id": "evt-123",
                "message": "I will handle this"
            })
            import time
            time.sleep(0.1)
            mock_blackboard.append_turn.assert_awaited()
            
def test_dashboard_ws_handle_user_message_mismatched_owner(monkeypatch):
    """An operator replying to an event owned by someone else is denied."""
    monkeypatch.setattr("src.auth.DEX_ENABLED", True)
    monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)
    
    monkeypatch.setattr("src.auth.decode_jwt", lambda token: {"email": "operator@example.com", "name": "Op"})
    
    from src.models import EventDocument, EventInput
    mock_event = EventDocument(
        event_id="evt-123",
        source="chat",
        service="test",
        event=EventInput(reason="test"),
        created_by_email="other@example.com",
        status="active"
    )
    
    mock_blackboard = MagicMock()
    mock_blackboard.get_event = AsyncMock(return_value=mock_event)
    app.state.dashboard_adapter._blackboard = mock_blackboard
    
    with TestClient(app) as client:
        with client.websocket_connect("/ws?token=valid-jwt") as ws:
            ws.send_json({
                "type": "user_message",
                "event_id": "evt-123",
                "message": "Let me hijack this"
            })
            
            resp = ws.receive_json()
            assert resp["type"] == "error"
            assert resp["kind"] == "auth_rejected"
            assert resp["event_id"] == "evt-123"
            assert "message" in resp

def test_dashboard_ws_handle_approve_ignores_ownership(monkeypatch):
    """_handle_approve has no ownership check today and must NOT gain one."""
    monkeypatch.setattr("src.auth.DEX_ENABLED", True)
    monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)
    monkeypatch.setattr("src.auth.decode_jwt", lambda token: {"email": "other@example.com", "name": "Op"})
    
    from src.models import EventDocument, EventInput
    mock_event = EventDocument(
        event_id="evt-123",
        source="chat",
        service="test",
        event=EventInput(reason="test"),
        created_by_email="owner@example.com",
        status="waiting_approval"
    )
    
    mock_blackboard = MagicMock()
    mock_blackboard.get_event = AsyncMock(return_value=mock_event)
    mock_blackboard.append_turn = AsyncMock()
    
    mock_brain = MagicMock()
    mock_brain.resume_if_parked = AsyncMock(return_value=True)
    mock_brain.enqueue_for_processing = MagicMock()
    
    app.state.dashboard_adapter._blackboard = mock_blackboard
    app.state.dashboard_adapter._brain = mock_brain
    
    with TestClient(app) as client:
        with client.websocket_connect("/ws?token=valid-jwt") as ws:
            ws.send_json({
                "type": "approve",
                "event_id": "evt-123"
            })
            import time
            time.sleep(0.1)
            mock_blackboard.append_turn.assert_awaited()

def test_dashboard_ws_handle_emergency_stop_ignores_ownership(monkeypatch):
    """_handle_emergency_stop has no ownership check today and must NOT gain one."""
    monkeypatch.setattr("src.auth.DEX_ENABLED", True)
    monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)
    monkeypatch.setattr("src.auth.decode_jwt", lambda token: {"email": "other@example.com", "name": "Op"})
    
    from src.models import EventDocument, EventInput
    mock_event = EventDocument(
        event_id="evt-123",
        source="chat",
        service="test",
        event=EventInput(reason="test"),
        created_by_email="owner@example.com",
        status="active"
    )
    
    mock_blackboard = MagicMock()
    mock_blackboard.get_event = AsyncMock(return_value=mock_event)
    mock_blackboard.append_turn = AsyncMock()
    
    mock_brain = MagicMock()
    mock_brain.cancel_event_tasks = AsyncMock(return_value=1)
    
    app.state.dashboard_adapter._blackboard = mock_blackboard
    app.state.dashboard_adapter._brain = mock_brain
    
    with TestClient(app) as client:
        with client.websocket_connect("/ws?token=valid-jwt") as ws:
            ws.send_json({
                "type": "emergency_stop",
                "event_id": "evt-123"
            })
            import time
            time.sleep(0.1)
            mock_brain.cancel_event_tasks.assert_awaited()
