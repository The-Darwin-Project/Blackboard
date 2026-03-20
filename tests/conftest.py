# tests/conftest.py
# @ai-rules:
# 1. [Pattern]: Shared pytest fixtures. All test files import fixtures from here.
# 2. [Constraint]: mock_redis uses AsyncMock -- matches the async Redis client in state/redis_client.py.
# 3. [Pattern]: Add new fixtures here as test coverage expands. Keep fixture scope minimal (function default).
import pytest
from unittest.mock import AsyncMock


@pytest.fixture
def mock_redis():
    """Mock Redis client for unit tests."""
    redis = AsyncMock()
    redis.ping.return_value = True
    redis.hget.return_value = None
    redis.hgetall.return_value = {}
    redis.llen.return_value = 0
    return redis
