# tests/test_health.py
# @ai-rules:
# 1. [Gotcha]: Patches lifespan to avoid full Redis/agent initialization in unit tests.
# 2. [Constraint]: Tests the 503 degradation path. The 200 path requires a running Redis -- use integration tests for that.
# 3. [Pattern]: Uses httpx AsyncClient + ASGITransport for in-process ASGI testing.
import pytest
from httpx import AsyncClient, ASGITransport
from unittest.mock import patch, AsyncMock


@pytest.mark.asyncio
async def test_health_returns_503_without_redis():
    """Health endpoint returns 503 when Blackboard is not initialized."""
    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()

        from src.main import app
        from src import dependencies
        original = dependencies._blackboard
        dependencies._blackboard = None
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/health")
                assert resp.status_code == 503
        finally:
            dependencies._blackboard = original
