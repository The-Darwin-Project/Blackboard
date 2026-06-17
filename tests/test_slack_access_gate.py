# tests/test_slack_access_gate.py
# @ai-rules:
# 1. [Pattern]: Mock K8s client via unittest.mock -- no cluster required.
# 2. [Constraint]: Tests gate logic only (SlackAccessGate). Handler integration tested separately.
# 3. [Pattern]: Uses pytest-asyncio for async lifecycle tests (start/sync).
# 4. [Gotcha]: _init_k8s_client patches kubernetes imports -- mock at module level.
"""Unit tests for SlackAccessGate -- OCP Group-based Slack authorization."""
import asyncio
import logging
from unittest.mock import MagicMock, patch, AsyncMock

import pytest


def _make_gate(**kwargs):
    from src.slack_gate import SlackAccessGate
    defaults = {
        "group_names": ["darwin-users"],
        "maintainer_emails": {"admin@example.com"},
        "email_domain": "",
        "sync_interval": 300,
    }
    defaults.update(kwargs)
    return SlackAccessGate(**defaults)


def _mock_k8s_group(users: list[str]) -> dict:
    return {"apiVersion": "user.openshift.io/v1", "kind": "Group", "users": users}


# =====================================================================
# Gate logic (unit, mock K8s client)
# =====================================================================


class TestGateCheck:

    def test_maintainer_bypasses_gate(self):
        gate = _make_gate()
        gate._healthy = True
        gate._allowed_emails = frozenset()
        assert gate.check("admin@example.com") is True

    def test_group_member_allowed(self):
        gate = _make_gate()
        gate._healthy = True
        gate._allowed_emails = frozenset({"user@example.com"})
        assert gate.check("user@example.com") is True

    def test_unknown_email_rejected(self):
        gate = _make_gate()
        gate._healthy = True
        gate._allowed_emails = frozenset({"user@example.com"})
        assert gate.check("stranger@example.com") is False

    def test_empty_email_rejected(self):
        gate = _make_gate()
        gate._healthy = True
        assert gate.check("") is False

    def test_case_insensitive_matching(self):
        gate = _make_gate(maintainer_emails={"Admin@Example.COM"})
        gate._healthy = True
        gate._allowed_emails = frozenset({"user@example.com"})
        assert gate.check("ADMIN@EXAMPLE.COM") is True
        assert gate.check("USER@EXAMPLE.COM") is True

    @pytest.mark.asyncio
    async def test_gate_disabled_all_pass(self):
        """When access_gate=None in SlackChannel, _gate_check returns True."""
        from src.channels.slack import SlackChannel
        sc = SlackChannel.__new__(SlackChannel)
        sc._access_gate = None
        sc._user_email_cache = {}
        sc._user_name_cache = {}
        sc._USER_CACHE_TTL = 3600
        result = await sc._gate_check(MagicMock(), "U_ANYONE")
        assert result is True

    def test_api_down_maintainer_only(self):
        gate = _make_gate()
        gate._healthy = False
        gate._allowed_emails = frozenset()
        assert gate.check("admin@example.com") is True
        assert gate.check("user@example.com") is False

    def test_api_down_midrun_keeps_stale_set(self):
        gate = _make_gate()
        gate._healthy = True
        gate._allowed_emails = frozenset({"user@example.com"})
        # Simulate mid-run failure: _healthy stays True, stale set kept
        assert gate.check("user@example.com") is True
        assert gate.check("admin@example.com") is True

    def test_domain_suffix_mapping(self):
        gate = _make_gate(email_domain="example.com")
        gate._healthy = True
        mock_api = MagicMock()
        mock_api.get_cluster_custom_object.return_value = _mock_k8s_group(["thason"])
        gate._k8s_api = mock_api
        emails = gate._fetch_group_members()
        assert "thason@example.com" in emails


# =====================================================================
# Handler coverage
# =====================================================================


class TestHandlerPatterns:

    @pytest.mark.asyncio
    async def test_action_handler_gated(self):
        """Unapproved user clicking approve button is silently rejected."""
        gate = _make_gate()
        gate._healthy = True
        gate._allowed_emails = frozenset()
        assert gate.check("unauthorized@example.com") is False

    @pytest.mark.asyncio
    async def test_home_tab_shows_limited_view(self):
        """Access-denied home view has the expected structure."""
        from src.channels.formatter import build_access_denied_home_view
        view = build_access_denied_home_view()
        assert view["type"] == "home"
        texts = [b.get("text", {}).get("text", "") for b in view["blocks"] if b["type"] == "section"]
        assert any("Access Required" in t for t in texts)

    @pytest.mark.asyncio
    async def test_cache_cold_start_resolves_email(self):
        """Gate check resolves email via Slack API when cache is empty."""
        gate = _make_gate()
        gate._healthy = True
        gate._allowed_emails = frozenset({"user@example.com"})

        mock_client = AsyncMock()
        mock_client.users_info.return_value = {
            "user": {
                "profile": {"display_name": "User", "email": "user@example.com"},
                "real_name": "User",
            }
        }
        # Simulate SlackChannel._gate_check flow
        from src.channels.slack import SlackChannel
        sc = SlackChannel.__new__(SlackChannel)
        sc._access_gate = gate
        sc._user_email_cache = {}
        sc._user_name_cache = {}
        sc._USER_CACHE_TTL = 3600
        result = await sc._gate_check(mock_client, "U123")
        assert result is True
        assert sc._user_email_cache.get("U123") == "user@example.com"


# =====================================================================
# Error handling
# =====================================================================


class TestErrorHandling:

    def test_group_404_continues_remaining(self):
        from kubernetes.client.exceptions import ApiException
        gate = _make_gate(group_names=["missing-group", "real-group"])
        mock_api = MagicMock()

        def side_effect(api_group, version, resource_type, name, **kwargs):
            if name == "missing-group":
                raise ApiException(status=404, reason="Not Found")
            return _mock_k8s_group(["user@example.com"])

        mock_api.get_cluster_custom_object.side_effect = side_effect
        gate._k8s_api = mock_api
        emails = gate._fetch_group_members()
        assert "user@example.com" in emails

    def test_unmappable_username_warns(self, caplog):
        gate = _make_gate(email_domain="")
        mock_api = MagicMock()
        mock_api.get_cluster_custom_object.return_value = _mock_k8s_group(
            ["pipeline", "user@example.com"]
        )
        gate._k8s_api = mock_api
        with caplog.at_level(logging.WARNING, logger="darwin.slack_gate"):
            emails = gate._fetch_group_members()
        assert "user@example.com" in emails
        assert "pipeline" not in emails
        assert any("1 usernames could not be mapped" in r.message for r in caplog.records)


# =====================================================================
# Audit logging
# =====================================================================


class TestAuditLogging:

    def test_every_decision_logged(self, caplog):
        gate = _make_gate()
        gate._healthy = True
        gate._allowed_emails = frozenset({"member@example.com"})

        with caplog.at_level(logging.INFO, logger="darwin.slack_gate"):
            gate.check("admin@example.com")      # maintainer
            gate.check("member@example.com")      # group_member
            gate.check("stranger@example.com")   # not_in_group
            gate.check("")                       # no_email

        messages = [r.message for r in caplog.records]
        assert sum("result=allow" in m for m in messages) == 2
        assert sum("result=deny" in m for m in messages) == 2
        assert any("reason=maintainer" in m for m in messages)
        assert any("reason=group_member" in m for m in messages)
        assert any("reason=not_in_group" in m for m in messages)
        assert any("reason=no_email" in m for m in messages)
