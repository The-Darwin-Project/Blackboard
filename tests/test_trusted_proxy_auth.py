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

        # ASGI fix: accept() is called FIRST so close(4001) transmits a real
        # WS Close Frame (pre-accept close = HTTP 403 / code 1006, never 4001).
        ws.accept.assert_called_once()
        ws.close.assert_called_once_with(code=4001)

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

class TestAuthPredicates:
    """Tests for pure auth predicates can_append_message and can_override_domain."""

    def test_can_append_message_owned_matching(self):
        assert auth.can_append_message("user@example.com", "user@example.com") is True

    def test_can_append_message_owned_mismatched(self):
        assert auth.can_append_message("owner@example.com", "other@example.com") is False

    def test_can_append_message_owned_no_user(self):
        assert auth.can_append_message("owner@example.com", None) is False

    def test_can_append_message_unowned_auth_enabled_with_user(self):
        assert auth.can_append_message(None, "user@example.com", auth_enabled=True) is True

    def test_can_append_message_unowned_auth_enabled_no_user(self):
        assert auth.can_append_message(None, None, auth_enabled=True) is False
        assert auth.can_append_message(None, "", auth_enabled=True) is False

    def test_can_append_message_unowned_auth_disabled(self):
        assert auth.can_append_message(None, "user@example.com", auth_enabled=False) is True
        assert auth.can_append_message(None, None, auth_enabled=False) is True

    def test_can_append_message_auth_enabled_fallback(self, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", True)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
        assert auth.can_append_message(None, "user@example.com", auth_enabled=None) is True

        monkeypatch.setattr(auth, "DEX_ENABLED", False)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", True)
        assert auth.can_append_message(None, "user@example.com", auth_enabled=None) is True

        monkeypatch.setattr(auth, "DEX_ENABLED", False)
        monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
        # auth disabled -> True even with no user
        assert auth.can_append_message(None, None, auth_enabled=None) is True

    def test_can_append_message_no_side_effects(self, caplog):
        import logging
        with caplog.at_level(logging.DEBUG):
            auth.can_append_message(None, "user@example.com", auth_enabled=True)
            auth.can_append_message("owner@example.com", "other@example.com", auth_enabled=True)
        assert len(caplog.records) == 0

    def test_can_override_domain_owned_matching(self):
        assert auth.can_override_domain("user@example.com", "user@example.com") is True

    def test_can_override_domain_owned_mismatched(self):
        assert auth.can_override_domain("owner@example.com", "other@example.com") is False

    def test_can_override_domain_unowned_always_false(self):
        assert auth.can_override_domain(None, "user@example.com") is False
        assert auth.can_override_domain(None, None) is False


class TestNormalizeEmail:
    """Tests for auth._normalize_email -- case-folding and whitespace-stripping.

    Existing can_append_message/can_override_domain tests above only ever pass
    already-lowercased, unpadded emails, so they never actually exercise
    _normalize_email's transformation behavior (only its None/empty short-circuits
    indirectly). These tests hit the function directly with mixed-case and
    padded input, matching what a real OIDC `email` claim or user-typed address
    can look like.
    """

    def test_lowercases_mixed_case_email(self):
        assert auth._normalize_email("User@Example.COM") == "user@example.com"

    def test_strips_surrounding_whitespace(self):
        assert auth._normalize_email("  user@example.com  ") == "user@example.com"

    def test_strips_and_lowercases_together(self):
        assert auth._normalize_email("  User@Example.COM\n") == "user@example.com"

    def test_none_returns_none(self):
        assert auth._normalize_email(None) is None

    def test_empty_string_returns_none(self):
        assert auth._normalize_email("") is None

    def test_whitespace_only_returns_none(self):
        assert auth._normalize_email("   ") is None

    def test_non_string_input_returns_none(self):
        assert auth._normalize_email(12345) is None  # type: ignore[arg-type]

    def test_can_override_domain_matches_despite_case_and_whitespace_differences(self):
        """End-to-end: a predicate consumer must not require pre-normalized input --
        an owner email stored as-typed and a caller email from a JWT claim with
        different case/whitespace must still be treated as the same identity."""
        assert auth.can_override_domain("Dev@RedHat.com", "  dev@redhat.com  ") is True

    def test_can_append_message_matches_despite_case_and_whitespace_differences(self):
        assert auth.can_append_message(" Dev@RedHat.com ", "dev@redhat.com") is True
