# BlackBoard/tests/test_vcs_approval.py
# @ai-rules:
# 1. [Constraint]: Unit tests for the live-HEAD-SHA TOCTOU defense (src/utils/vcs_approval.py).
# 2. [Pattern]: Mocks httpx.AsyncClient directly (patch("src.utils.vcs_approval.httpx.AsyncClient"),
#    same convention as test_jenkins_tools.py) rather than mocking resolve_live_head_sha wholesale --
#    this file exists specifically to exercise the internal fallback branches that a wholesale mock hides.
"""Unit tests for src/utils/vcs_approval.py: live HEAD SHA resolution and the Developer merge guard.

Covers the failure modes identified as untested by code review: HTTP timeout, non-2xx
response, malformed JSON body, missing token (fallback path), and the broad-exception
swallow-and-fallback branches for both GitLab and GitHub resolution.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.vcs_approval import (
    _resolve_github_head,
    _resolve_gitlab_head,
    resolve_live_head_sha,
    verify_merge_guard,
)


def _mock_client(get_return=None, get_side_effect=None):
    """Build a mock httpx.AsyncClient context manager yielding a client whose .get() is mocked."""
    mock_client = AsyncMock()
    if get_side_effect is not None:
        mock_client.get = AsyncMock(side_effect=get_side_effect)
    else:
        mock_client.get = AsyncMock(return_value=get_return)
    mock_client_cls = MagicMock()
    mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)
    return mock_client_cls


def _resp(status_code=200, json_data=None, json_side_effect=None):
    resp = MagicMock()
    resp.is_success = 200 <= status_code < 300
    resp.status_code = status_code
    if json_side_effect is not None:
        resp.json = MagicMock(side_effect=json_side_effect)
    else:
        resp.json = MagicMock(return_value=json_data or {})
    return resp


class TestResolveGitlabHead:
    """Dedicated unit coverage for _resolve_gitlab_head's live-query + fallback branches."""

    @pytest.mark.asyncio
    async def test_success_returns_live_sha(self):
        gl_ctx = {"mr_iid": "7", "project_id": "123", "head_sha": "stale-sha"}
        resp = _resp(200, {"sha": "live-sha-abc123"})
        with (
            patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)),
            patch.dict("os.environ", {"GITLAB_HOST": "gitlab.example.com", "GITLAB_TOKEN": "tok"}),
            patch("src.utils.gitlab_token.get_gitlab_auth", return_value=None),
        ):
            mr_id, sha = await _resolve_gitlab_head(gl_ctx)
        assert mr_id == "7"
        assert sha == "live-sha-abc123"

    @pytest.mark.asyncio
    async def test_non_2xx_response_falls_back_and_logs(self, caplog):
        gl_ctx = {"mr_iid": "7", "project_id": "123", "head_sha": "stale-sha"}
        resp = _resp(401)  # expired/invalid token
        with (
            patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)),
            patch.dict("os.environ", {"GITLAB_HOST": "gitlab.example.com", "GITLAB_TOKEN": "tok"}),
            patch("src.utils.gitlab_token.get_gitlab_auth", return_value=None),
            caplog.at_level("WARNING"),
        ):
            mr_id, sha = await _resolve_gitlab_head(gl_ctx)
        assert mr_id == "7"
        assert sha == "stale-sha"
        assert any("401" in r.message or "HTTP" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_timeout_exception_falls_back_and_logs(self, caplog):
        import httpx as httpx_mod
        gl_ctx = {"mr_iid": "7", "project_id": "123", "head_sha": "stale-sha"}
        with (
            patch(
                "src.utils.vcs_approval.httpx.AsyncClient",
                _mock_client(get_side_effect=httpx_mod.TimeoutException("timed out")),
            ),
            patch.dict("os.environ", {"GITLAB_HOST": "gitlab.example.com", "GITLAB_TOKEN": "tok"}),
            patch("src.utils.gitlab_token.get_gitlab_auth", return_value=None),
            caplog.at_level("WARNING"),
        ):
            mr_id, sha = await _resolve_gitlab_head(gl_ctx)
        assert mr_id == "7"
        assert sha == "stale-sha"
        assert any("Failed live GitLab" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_malformed_json_body_falls_back(self, caplog):
        gl_ctx = {"mr_iid": "7", "project_id": "123", "head_sha": "stale-sha"}
        resp = _resp(200, json_side_effect=ValueError("not json"))
        with (
            patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)),
            patch.dict("os.environ", {"GITLAB_HOST": "gitlab.example.com", "GITLAB_TOKEN": "tok"}),
            patch("src.utils.gitlab_token.get_gitlab_auth", return_value=None),
            caplog.at_level("WARNING"),
        ):
            mr_id, sha = await _resolve_gitlab_head(gl_ctx)
        assert mr_id == "7"
        assert sha == "stale-sha"

    @pytest.mark.asyncio
    async def test_missing_token_skips_network_call_and_falls_back(self):
        gl_ctx = {"mr_iid": "7", "project_id": "123", "head_sha": "stale-sha"}
        mock_client_cls = _mock_client(get_return=_resp(200, {"sha": "should-not-be-used"}))
        with (
            patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls),
            patch.dict("os.environ", {"GITLAB_HOST": "gitlab.example.com", "GITLAB_TOKEN": ""}),
            patch("src.utils.gitlab_token.get_gitlab_auth", return_value=None),
        ):
            mr_id, sha = await _resolve_gitlab_head(gl_ctx)
        assert mr_id == "7"
        assert sha == "stale-sha"
        mock_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_project_id_skips_network_call(self):
        gl_ctx = {"mr_iid": "7", "head_sha": "stale-sha"}
        mock_client_cls = _mock_client(get_return=_resp(200, {"sha": "x"}))
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls):
            mr_id, sha = await _resolve_gitlab_head(gl_ctx)
        assert mr_id == "7"
        assert sha == "stale-sha"
        mock_client_cls.assert_not_called()


class TestResolveGithubHead:
    """Dedicated unit coverage for _resolve_github_head's live-query + fallback branches."""

    @pytest.mark.asyncio
    async def test_success_returns_live_sha(self):
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        resp = _resp(200, {"head": {"sha": "live-sha-xyz"}})
        with patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert pr_number == "265"
        assert sha == "live-sha-xyz"

    @pytest.mark.asyncio
    async def test_non_2xx_response_falls_back_and_logs(self, caplog):
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        resp = _resp(404)  # renamed/deleted PR
        with (
            patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)),
            caplog.at_level("WARNING"),
        ):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert pr_number == "265"
        assert sha == "stale-sha"
        assert any("404" in r.message or "HTTP" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_broad_exception_falls_back_and_logs(self, caplog):
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        with (
            patch(
                "src.utils.vcs_approval.httpx.AsyncClient",
                _mock_client(get_side_effect=ConnectionError("connection reset")),
            ),
            caplog.at_level("WARNING"),
        ):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert pr_number == "265"
        assert sha == "stale-sha"
        assert any("Failed live GitHub" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_malformed_json_body_falls_back(self):
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        resp = _resp(200, json_side_effect=ValueError("not json"))
        with patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert pr_number == "265"
        assert sha == "stale-sha"

    @pytest.mark.asyncio
    async def test_missing_token_still_queries_without_auth_header(self):
        """GitHub's public API tolerates unauthenticated calls (rate-limited, not rejected) --
        unlike GitLab, missing token must NOT skip the live query, only the Authorization header."""
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        resp = _resp(200, {"head": {"sha": "live-sha-xyz"}})
        mock_client_cls = _mock_client(get_return=resp)
        with patch.dict("os.environ", {"GITHUB_TOKEN": ""}):
            with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls):
                pr_number, sha = await _resolve_github_head(gh_ctx)
        assert sha == "live-sha-xyz"
        _, call_kwargs = mock_client_cls.return_value.__aenter__.return_value.get.call_args
        assert "Authorization" not in call_kwargs.get("headers", {})

    @pytest.mark.asyncio
    @pytest.mark.parametrize("env_name", ["REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"])
    async def test_live_sha_client_uses_ca_bundle_verify(self, monkeypatch, env_name):
        """GitHub live-SHA call passes the configured CA bundle as verify= and never False."""
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.setenv(env_name, "/etc/pki/tls/certs/ca-bundle.crt")
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        mock_client_cls = _mock_client(get_return=_resp(200, {"head": {"sha": "live-sha-xyz"}}))
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls):
            _, sha = await _resolve_github_head(gh_ctx)
        assert sha == "live-sha-xyz"
        kwargs = mock_client_cls.call_args.kwargs
        assert kwargs["verify"] == "/etc/pki/tls/certs/ca-bundle.crt"
        assert kwargs["verify"] is not False

    @pytest.mark.asyncio
    async def test_live_sha_client_defaults_to_system_trust_when_no_bundle(self, monkeypatch):
        """No CA env configured: verify=True (system trust store), never disabled."""
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        mock_client_cls = _mock_client(get_return=_resp(200, {"head": {"sha": "live-sha-xyz"}}))
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls):
            await _resolve_github_head(gh_ctx)
        assert mock_client_cls.call_args.kwargs["verify"] is True

    @pytest.mark.asyncio
    async def test_missing_pr_number_skips_network_call(self):
        gh_ctx = {"owner": "o", "repo": "r", "head_sha": "stale-sha"}
        mock_client_cls = _mock_client(get_return=_resp(200, {}))
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert sha == "stale-sha"
        mock_client_cls.assert_not_called()


class TestResolveLiveHeadShaDispatcher:
    """resolve_live_head_sha() routes to the correct platform resolver based on event evidence."""

    @pytest.mark.asyncio
    async def test_no_evidence_returns_none_none(self):
        event = MagicMock()
        event.event = None
        mr_id, sha = await resolve_live_head_sha(event)
        assert (mr_id, sha) == (None, None)

    @pytest.mark.asyncio
    async def test_gitlab_context_routes_to_gitlab_resolver(self):
        event = MagicMock()
        event.event.evidence.gitlab_context = {"mr_iid": "7", "head_sha": "x"}
        event.event.evidence.github_context = None
        with patch(
            "src.utils.vcs_approval._resolve_gitlab_head",
            AsyncMock(return_value=("7", "x")),
        ) as mock_gl:
            result = await resolve_live_head_sha(event)
        mock_gl.assert_awaited_once()
        assert result == ("7", "x")

    @pytest.mark.asyncio
    async def test_github_context_routes_to_github_resolver(self):
        event = MagicMock()
        event.event.evidence.gitlab_context = None
        event.event.evidence.github_context = {"pr_number": "265", "head_sha": "y"}
        with patch(
            "src.utils.vcs_approval._resolve_github_head",
            AsyncMock(return_value=("265", "y")),
        ) as mock_gh:
            result = await resolve_live_head_sha(event)
        mock_gh.assert_awaited_once()
        assert result == ("265", "y")

    @pytest.mark.asyncio
    async def test_resolve_live_head_sha_tls_verify_ca_bundle(self, monkeypatch):
        """T-11 / Step 5: resolve_live_head_sha passes CA bundle path and never verify=False."""
        from src.utils.vcs_approval import _resolve_gitlab_head
        monkeypatch.setenv("GITLAB_HOST", "gitlab.corp.redhat.com")
        monkeypatch.setenv("GITLAB_TOKEN", "gl-token-123")
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/etc/pki/tls/certs/ca-bundle.crt")

        gl_ctx = {"mr_iid": "42", "project_id": "100", "head_sha": "fallback_sha"}
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__.return_value = mock_client
            mock_resp = MagicMock()
            mock_resp.is_success = True
            mock_resp.json.return_value = {"sha": "live_sha_123"}
            mock_client.get.return_value = mock_resp

            mr_iid, sha = await _resolve_gitlab_head(gl_ctx)

            assert mock_client_cls.called
            kwargs = mock_client_cls.call_args.kwargs
            assert kwargs.get("verify") == "/etc/pki/tls/certs/ca-bundle.crt"
            assert kwargs.get("verify") is not False
            assert sha == "live_sha_123"



class TestVerifyMergeGuard:
    """verify_merge_guard() is the production Developer merge guard (see test_approval_binding.py
    test_09 for the full prompt-injection/TOCTOU scenario suite)."""

    def test_empty_approval_record_refused(self):
        allowed, reason = verify_merge_guard({}, "sha1")
        assert allowed is False
        assert "not approved" in reason.lower()

    def test_approved_but_missing_sha_refused(self):
        allowed, reason = verify_merge_guard({"approved": True, "approved_mr_sha": None}, "sha1")
        assert allowed is False
        assert "differs" in reason.lower()

    def test_operational_category_approved_without_mr_sha_allowed(self):
        """ATDD: Operational category allows execution on approved events even without approved_mr_sha or localSha."""
        allowed, reason = verify_merge_guard(
            {"approved": True, "approved_mr_sha": None},
            None,
            category="operational",
        )
        assert allowed is True
        assert "operational" in reason.lower()

    def test_operational_category_unapproved_refused(self):
        """ATDD: Operational category still refuses unapproved events."""
        allowed, reason = verify_merge_guard(
            {"approved": False, "approved_mr_sha": None},
            None,
            category="operational",
        )
        assert allowed is False
        assert "not approved" in reason.lower()

    def test_git_merge_category_on_operational_approval_refused(self):
        """ATDD: Git merge category strictly refuses operational approval lacking approved_mr_sha."""
        allowed, reason = verify_merge_guard(
            {"approved": True, "approved_mr_sha": None},
            None,
            category="git_merge",
        )
        assert allowed is False
        assert "differs" in reason.lower()

    def test_invalid_category_fails_closed_to_git_merge(self):
        """ATDD: Unknown category fails closed to git_merge rules requiring matching SHA."""
        allowed, reason = verify_merge_guard(
            {"approved": True, "approved_mr_sha": None},
            None,
            category="unknown_category",
        )
        assert allowed is False
        assert "differs" in reason.lower()

    def test_git_merge_category_matching_sha_authorized(self):
        """ATDD: Git merge category allows execution when approved and SHAs match."""
        allowed, reason = verify_merge_guard(
            {"approved": True, "approved_mr_sha": "abc1234"},
            "abc1234",
            category="git_merge",
        )
        assert allowed is True
        assert "authorized" in reason.lower()
