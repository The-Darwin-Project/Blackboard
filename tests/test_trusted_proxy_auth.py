# BlackBoard/tests/test_trusted_proxy_auth.py
# @ai-rules:
# 1. [Constraint]: Patch module constants directly (TRUSTED_PROXY_ENABLED, TRUSTED_PROXY_SECRET, DEX_ENABLED) -- they are computed at import time.
# 2. [Pattern]: Use simple mock objects for websocket headers/query_params -- no FastAPI test client needed for pure auth functions.
# 3. [Gotcha]: hmac.compare_digest with two empty strings returns True -- the guard `if bff_token and forwarded_email` prevents this.
# 4. [Pattern]: Adapter-level tests mock Brain+Blackboard and test websocket_handler rejection directly.
"""Tests for trusted-proxy auth path and fail-closed adapter wiring."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src import auth
from src.auth import UserContext, get_user_from_websocket


def _mock_websocket(headers: dict | None = None, query_params: dict | None = None):
    ws = MagicMock()
    ws.headers = headers or {}
    ws.query_params = query_params or {}
    return ws


class TestTrustedProxyAuth:
    """get_user_from_websocket trusted-proxy path."""

    def test_valid_trusted_proxy(self, monkeypatch):
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", True)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_SECRET", "test-secret-123")

        ws = _mock_websocket(headers={
            "x-bff-token": "test-secret-123",
            "x-forwarded-email": "user@example.com",
        })
        user = get_user_from_websocket(ws)

        assert user.email == "user@example.com"
        assert user.source == "release-console"
        assert user.user_id == "user@example.com"
        assert user.display_name == "user"

    def test_wrong_bff_token_returns_anonymous(self, monkeypatch):
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", True)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_SECRET", "correct-secret")
        monkeypatch.setattr(auth, "DEX_ENABLED", False)

        ws = _mock_websocket(headers={
            "x-bff-token": "wrong-secret",
            "x-forwarded-email": "user@example.com",
        })
        user = get_user_from_websocket(ws)

        assert user.user_id == "anonymous"
        assert user.email is None

    def test_missing_email_header_returns_anonymous(self, monkeypatch):
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", True)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_SECRET", "test-secret")
        monkeypatch.setattr(auth, "DEX_ENABLED", False)

        ws = _mock_websocket(headers={"x-bff-token": "test-secret"})
        user = get_user_from_websocket(ws)

        assert user.user_id == "anonymous"
        assert user.email is None

    def test_empty_secret_does_not_match_empty_token(self, monkeypatch):
        """Both TRUSTED_PROXY_SECRET="" and x-bff-token="" should NOT authenticate."""
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", True)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_SECRET", "")
        monkeypatch.setattr(auth, "DEX_ENABLED", False)

        ws = _mock_websocket(headers={
            "x-bff-token": "",
            "x-forwarded-email": "user@example.com",
        })
        user = get_user_from_websocket(ws)

        assert user.user_id == "anonymous"

    def test_trusted_proxy_disabled_skips_headers(self, monkeypatch):
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
        monkeypatch.setattr(auth, "DEX_ENABLED", False)

        ws = _mock_websocket(headers={
            "x-bff-token": "any-secret",
            "x-forwarded-email": "user@example.com",
        })
        user = get_user_from_websocket(ws)

        assert user.user_id == "anonymous"
        assert user.source == "dashboard"

    def test_trusted_proxy_takes_priority_over_jwt(self, monkeypatch):
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", True)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_SECRET", "bff-secret")
        monkeypatch.setattr(auth, "DEX_ENABLED", True)

        ws = _mock_websocket(
            headers={
                "x-bff-token": "bff-secret",
                "x-forwarded-email": "proxy@example.com",
            },
            query_params={"token": "some-jwt-token"},
        )
        user = get_user_from_websocket(ws)

        assert user.email == "proxy@example.com"
        assert user.source == "release-console"


class TestAdapterFailClosed:
    """DashboardWSAdapter.websocket_handler rejects anonymous when auth_enabled=True."""

    @pytest.mark.asyncio
    async def test_adapter_rejects_anonymous_with_4001(self, monkeypatch):
        """When auth_enabled=True and user resolves to anonymous, adapter closes with 4001."""
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", True)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_SECRET", "real-secret")
        monkeypatch.setattr(auth, "DEX_ENABLED", False)

        from src.adapters.dashboard_ws import DashboardWSAdapter

        mock_brain = MagicMock()
        mock_blackboard = MagicMock()
        adapter = DashboardWSAdapter(brain=mock_brain, blackboard=mock_blackboard, auth_enabled=True)

        ws = AsyncMock()
        ws.headers = {"x-bff-token": "wrong-secret", "x-forwarded-email": "user@test.com"}
        ws.query_params = {}

        await adapter.websocket_handler(ws)

        ws.close.assert_called_once_with(code=4001)
        ws.accept.assert_not_called()

    @pytest.mark.asyncio
    async def test_adapter_accepts_valid_trusted_proxy(self, monkeypatch):
        """When auth_enabled=True and trusted-proxy validates, adapter accepts the connection."""
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", True)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_SECRET", "valid-secret")
        monkeypatch.setattr(auth, "DEX_ENABLED", False)

        from src.adapters.dashboard_ws import DashboardWSAdapter

        mock_brain = MagicMock()
        mock_blackboard = MagicMock()
        adapter = DashboardWSAdapter(brain=mock_brain, blackboard=mock_blackboard, auth_enabled=True)
        adapter._kargo_observer = None

        ws = AsyncMock()
        ws.headers = {"x-bff-token": "valid-secret", "x-forwarded-email": "user@test.com"}
        ws.query_params = {}
        ws.receive_json = AsyncMock(side_effect=Exception("disconnect"))

        await adapter.websocket_handler(ws)

        ws.accept.assert_called_once()
        ws.close.assert_not_called()
