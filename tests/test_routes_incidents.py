# tests/test_routes_incidents.py
# @ai-rules:
# 1. [Pattern]: Tests the /incidents/list route with mocked app.state.incident_adapter.
# 2. [Constraint]: No live Jira calls -- adapter mocked.
"""Route tests for /incidents/list."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.routes.incidents import list_incidents


@pytest.mark.asyncio
async def test_list_returns_empty_when_no_adapter():
    """Graceful degradation: returns [] when adapter is None."""
    request = MagicMock()
    request.app.state.incident_adapter = None
    result = await list_incidents(request)
    assert result == []


@pytest.mark.asyncio
async def test_list_returns_incidents():
    """Returns Jira incidents from adapter."""
    mock_adapter = AsyncMock()
    mock_adapter.list_incidents.return_value = [
        {"issue_key": "VMER-1", "summary": "test", "status": "New"},
    ]
    request = MagicMock()
    request.app.state.incident_adapter = mock_adapter
    with patch.dict("os.environ", {"JIRA_INCIDENT_LABEL_FILTER": "darwin-auto"}):
        result = await list_incidents(request)
    assert len(result) == 1
    assert result[0]["issue_key"] == "VMER-1"
    mock_adapter.list_incidents.assert_called_once_with(label_filter="darwin-auto")


@pytest.mark.asyncio
async def test_list_handles_adapter_error():
    """Returns [] on adapter exception."""
    mock_adapter = AsyncMock()
    mock_adapter.list_incidents.side_effect = RuntimeError("Jira down")
    request = MagicMock()
    request.app.state.incident_adapter = mock_adapter
    result = await list_incidents(request)
    assert result == []
