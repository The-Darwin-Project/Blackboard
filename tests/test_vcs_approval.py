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
