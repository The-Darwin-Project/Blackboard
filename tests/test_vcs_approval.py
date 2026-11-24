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

import json
import shutil
import subprocess
from pathlib import Path
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
        assert sha is None
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
        assert sha is None
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
        assert sha is None

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
        assert sha is None
        mock_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_missing_project_id_skips_network_call(self):
        gl_ctx = {"mr_iid": "7", "head_sha": "stale-sha"}
        mock_client_cls = _mock_client(get_return=_resp(200, {"sha": "x"}))
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls):
            mr_id, sha = await _resolve_gitlab_head(gl_ctx)
        assert mr_id == "7"
        assert sha is None
        mock_client_cls.assert_not_called()

    @pytest.mark.asyncio
    async def test_resolve_gitlab_head_url_encodes_namespaced_project_id(self):
        """T-8: Given project_id with slashes, API URL path encodes with quote(safe='')."""
        gl_ctx = {
            "mr_iid": "7",
            "project_id": "openshift-virtualization/downstream-configuration",
            "head_sha": "stale-sha",
        }
        resp = _resp(200, {"sha": "live-sha-encoded"})
        mock_client_cls = _mock_client(get_return=resp)
        with (
            patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls),
            patch.dict("os.environ", {"GITLAB_HOST": "gitlab.example.com", "GITLAB_TOKEN": "tok"}),
            patch("src.utils.gitlab_token.get_gitlab_auth", return_value=None),
        ):
            mr_id, sha = await _resolve_gitlab_head(gl_ctx)

        assert mr_id == "7"
        assert sha == "live-sha-encoded"
        call_args = mock_client_cls.return_value.__aenter__.return_value.get.call_args
        requested_url = call_args[0][0]
        assert "openshift-virtualization%2Fdownstream-configuration" in requested_url

    @pytest.mark.asyncio
    async def test_resolve_gitlab_head_http_500_fails_closed_returns_mr_iid_none(self, caplog):
        """T-10b: Given GitLab API returns HTTP 500, return (mr_iid, None) fail-closed."""
        gl_ctx = {"mr_iid": "25", "project_id": "123", "head_sha": "stale-sha"}
        resp = _resp(500)
        with (
            patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)),
            patch.dict("os.environ", {"GITLAB_HOST": "gitlab.example.com", "GITLAB_TOKEN": "tok"}),
            patch("src.utils.gitlab_token.get_gitlab_auth", return_value=None),
            caplog.at_level("WARNING"),
        ):
            mr_id, sha = await _resolve_gitlab_head(gl_ctx)
        assert mr_id == "25"
        assert sha is None


class TestResolveGithubHead:
    """Dedicated unit coverage for _resolve_github_head's live-query + fail-closed branches (F8)."""

    @pytest.mark.asyncio
    async def test_success_returns_live_sha(self):
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        resp = _resp(200, {"head": {"sha": "live-sha-xyz"}})
        with patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert pr_number == "265"
        assert sha == "live-sha-xyz"

    @pytest.mark.asyncio
    async def test_non_2xx_response_fails_closed_and_logs(self, caplog):
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        resp = _resp(404)  # renamed/deleted PR
        with (
            patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)),
            caplog.at_level("WARNING"),
        ):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert pr_number == "265"
        assert sha is None, "stale cached head_sha must never be substituted for a live SHA"
        assert any("404" in r.message or "HTTP" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_broad_exception_fails_closed_and_logs(self, caplog):
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
        assert sha is None
        assert any("Failed live GitHub" in r.message for r in caplog.records)

    @pytest.mark.asyncio
    async def test_malformed_json_body_fails_closed(self):
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        resp = _resp(200, json_side_effect=ValueError("not json"))
        with patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert pr_number == "265"
        assert sha is None

    @pytest.mark.asyncio
    async def test_success_without_head_sha_fails_closed(self):
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        resp = _resp(200, {"head": {}})
        with patch("src.utils.vcs_approval.httpx.AsyncClient", _mock_client(get_return=resp)):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert (pr_number, sha) == ("265", None)

    @pytest.mark.asyncio
    async def test_insecure_gitlab_ssl_verify_fails_closed_without_network(self, monkeypatch):
        """resolve_ca_bundle() raising ValueError (GITLAB_SSL_VERIFY=false) is caught: no live SHA, no client."""
        monkeypatch.setenv("GITLAB_SSL_VERIFY", "false")
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        mock_client_cls = _mock_client(get_return=_resp(200, {"head": {"sha": "live"}}))
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert (pr_number, sha) == ("265", None)
        mock_client_cls.assert_not_called()

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
    async def test_live_sha_client_uses_ca_bundle_verify(self, monkeypatch, tmp_path, env_name):
        """GitHub live-SHA call passes the configured CA bundle as verify= and never False."""
        ca_file = tmp_path / "ca-bundle.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\nx\n-----END CERTIFICATE-----\n")
        monkeypatch.delenv("GITLAB_SSL_VERIFY", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.setenv(env_name, str(ca_file))
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        mock_client_cls = _mock_client(get_return=_resp(200, {"head": {"sha": "live-sha-xyz"}}))
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls):
            _, sha = await _resolve_github_head(gh_ctx)
        assert sha == "live-sha-xyz"
        kwargs = mock_client_cls.call_args.kwargs
        assert kwargs["verify"] == str(ca_file)
        assert kwargs["verify"] is not False

    @pytest.mark.asyncio
    async def test_live_sha_client_defaults_to_system_trust_when_no_bundle(self, monkeypatch):
        """No CA env configured and no standard bundle on disk: verify=True, never disabled."""
        monkeypatch.delenv("GITLAB_SSL_VERIFY", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale-sha"}
        mock_client_cls = _mock_client(get_return=_resp(200, {"head": {"sha": "live-sha-xyz"}}))
        with (
            patch("src.utils.tls._usable_ca_file", return_value=False),
            patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls),
        ):
            await _resolve_github_head(gh_ctx)
        assert mock_client_cls.call_args.kwargs["verify"] is True

    @pytest.mark.asyncio
    async def test_missing_pr_number_skips_network_call(self):
        gh_ctx = {"owner": "o", "repo": "r", "head_sha": "stale-sha"}
        mock_client_cls = _mock_client(get_return=_resp(200, {}))
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_client_cls):
            pr_number, sha = await _resolve_github_head(gh_ctx)
        assert pr_number is None
        assert sha is None
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
    async def test_kargo_verification_failure_ignores_mr_url_in_head_sha_and_vcs_backed(self):
        """T-19: resolve_live_head_sha and _is_vcs_backed_event ignore kargo_context['mr_url']
        when failure_type == 'verification'."""
        from src.utils.vcs_approval import _is_vcs_backed_event

        event = MagicMock()
        event.event.evidence.gitlab_context = None
        event.event.evidence.github_context = None
        event.event.evidence.kargo_context = {
            "project": "v4-22",
            "stage": "verify-release-chart",
            "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/42",
            "failure_type": "verification",
        }
        assert _is_vcs_backed_event(event) is False
        with patch("src.utils.vcs_approval._resolve_gitlab_head", AsyncMock()) as mock_gl:
            result = await resolve_live_head_sha(event)
        assert result == (None, None)
        mock_gl.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_kargo_verification_stale_mirror_populated_gitlab_context_not_resolved(self):
        """H2 / M1: Populated gitlab_context matching verification kargo_context.mr_url (by URL or project/iid)
        is skipped by resolve_live_head_sha (including tail), _is_vcs_backed_event, and extract_context_head_sha."""
        from src.utils.vcs_approval import (
            _is_vcs_backed_event,
            extract_context_head_sha,
            is_stale_verification_gitlab_mirror,
        )

        # Case 1: target_url equals kc.mr_url
        ev_url = MagicMock()
        ev_url.event.evidence.github_context = None
        ev_url.event.evidence.gitlab_context = {
            "target_url": "https://gitlab.example.com/org/repo/-/merge_requests/42",
            "project_id": "org/repo",
            "mr_iid": 42,
            "head_sha": "stale-promo-sha",
        }
        ev_url.event.evidence.kargo_context = {
            "project": "v4-22",
            "stage": "verify-release-chart",
            "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/42",
            "failure_type": "verification",
            "head_sha": "stale-promo-sha",
        }
        assert is_stale_verification_gitlab_mirror(ev_url) is True
        assert _is_vcs_backed_event(ev_url) is False
        assert extract_context_head_sha(ev_url) is None
        with patch("src.utils.vcs_approval._resolve_gitlab_head", AsyncMock()) as mock_gl:
            assert await resolve_live_head_sha(ev_url) == (None, None)
        mock_gl.assert_not_awaited()

        # Case 2: target_url absent, matched via project_id + mr_iid parsed from kc.mr_url
        ev_pid = MagicMock()
        ev_pid.event.evidence.github_context = None
        ev_pid.event.evidence.gitlab_context = {
            "project_id": "org/repo",
            "mr_iid": 42,
            "head_sha": "stale-sha-pid",
        }
        ev_pid.event.evidence.kargo_context = {
            "project": "v4-22",
            "stage": "verify-release-chart",
            "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/42",
            "failure_type": "verification",
        }
        assert is_stale_verification_gitlab_mirror(ev_pid) is True
        assert _is_vcs_backed_event(ev_pid) is False
        assert extract_context_head_sha(ev_pid) is None
        with patch("src.utils.vcs_approval._resolve_gitlab_head", AsyncMock()) as mock_gl:
            assert await resolve_live_head_sha(ev_pid) == (None, None)
        mock_gl.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_kargo_verification_mirrored_provenance_survives_mr_url_flip(self):
        """M2: A superseded promotion mirror tagged mirrored_from_kargo=True stays stale even if kc.mr_url flips to mr/11."""
        from src.utils.vcs_approval import _is_vcs_backed_event, is_stale_verification_gitlab_mirror

        event = MagicMock()
        event.event.evidence.github_context = None
        event.event.evidence.gitlab_context = {
            "target_url": "https://gitlab.example.com/org/repo/-/merge_requests/10",
            "project_id": "org/repo",
            "mr_iid": 10,
            "mirrored_from_kargo": True,
        }
        event.event.evidence.kargo_context = {
            "project": "v4-22",
            "stage": "verify-release-chart",
            "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/11",
            "failure_type": "verification",
        }
        assert is_stale_verification_gitlab_mirror(event) is True
        assert _is_vcs_backed_event(event) is False
        with patch("src.utils.vcs_approval._resolve_gitlab_head", AsyncMock()) as mock_gl:
            assert await resolve_live_head_sha(event) == (None, None)
        mock_gl.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_kargo_verification_distinct_fix_mr_is_not_stale_mirror(self):
        """H2 / M11: Distinct fix MR attached via gitlab_context resolves live SHA and stays VCS-backed."""
        from src.utils.vcs_approval import (
            _is_vcs_backed_event,
            extract_context_head_sha,
            is_stale_verification_gitlab_mirror,
        )

        event = MagicMock()
        event.event.evidence.github_context = None
        event.event.evidence.gitlab_context = {
            "target_url": "https://gitlab.example.com/org/repo/-/merge_requests/99",
            "project_id": "org/repo",
            "mr_iid": 99,
            "head_sha": "fix-head-sha",
            "mirrored_from_kargo": False,
        }
        event.event.evidence.kargo_context = {
            "project": "v4-22",
            "stage": "verify-release-chart",
            "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/42",
            "failure_type": "verification",
        }
        assert is_stale_verification_gitlab_mirror(event) is False
        assert _is_vcs_backed_event(event) is True
        assert extract_context_head_sha(event) == "fix-head-sha"
        with patch(
            "src.utils.vcs_approval._resolve_gitlab_head",
            AsyncMock(return_value=("99", "live-fix-sha")),
        ) as mock_gl:
            assert await resolve_live_head_sha(event) == ("99", "live-fix-sha")
        mock_gl.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_kargo_promotion_failure_preserves_mr_url_resolution_and_vcs_backed(self):
        """T-19: Promotion-failure kargo_context with mr_url remains VCS-backed and resolves live SHA."""
        from src.utils.vcs_approval import _is_vcs_backed_event

        event = MagicMock()
        event.event.evidence.gitlab_context = None
        event.event.evidence.github_context = None
        event.event.evidence.kargo_context = {
            "project": "v4-22",
            "stage": "promote-stage",
            "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/42",
            "failure_type": "promotion",
        }
        assert _is_vcs_backed_event(event) is True
        with patch(
            "src.utils.vcs_approval._resolve_gitlab_head",
            AsyncMock(return_value=("42", "live-sha-kargo")),
        ) as mock_gl:
            result = await resolve_live_head_sha(event)
        assert result == ("42", "live-sha-kargo")
        mock_gl.assert_awaited_once_with({"project_id": "org/repo", "mr_iid": 42})

    @pytest.mark.asyncio
    async def test_resolve_live_head_sha_tls_verify_ca_bundle(self, monkeypatch):
        """T-11 / Step 5: resolve_live_head_sha passes CA bundle path and never verify=False."""
        from src.utils.vcs_approval import _resolve_gitlab_head
        monkeypatch.setenv("GITLAB_HOST", "gitlab.corp.redhat.com")
        monkeypatch.setenv("GITLAB_TOKEN", "gl-token-123")
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/etc/pki/tls/certs/ca-bundle.crt")

        gl_ctx = {"mr_iid": "42", "project_id": "100", "head_sha": "fallback_sha"}
        with (
            # Host-independent: _usable_ca_file is the only filesystem probe, so patch it rather than
            # relying on /etc/pki existing (RHEL) -- ubuntu-latest only ships /etc/ssl/certs.
            patch(
                "src.utils.tls._usable_ca_file",
                side_effect=lambda p: p == "/etc/pki/tls/certs/ca-bundle.crt",
            ),
            patch("httpx.AsyncClient") as mock_client_cls,
        ):
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

    @pytest.mark.asyncio
    async def test_kargo_context_mr_url_fallback(self):
        """T-10: Given missing gitlab_context but valid kargo_context.mr_url, resolves live HEAD."""
        event = MagicMock()
        event.event.evidence.gitlab_context = None
        event.event.evidence.github_context = None
        event.event.evidence.kargo_context = {
            "mr_url": "https://gitlab.example.com/openshift-virtualization/downstream-configuration/-/merge_requests/25"
        }
        with patch(
            "src.utils.vcs_approval._resolve_gitlab_head",
            AsyncMock(return_value=("25", "d461a00c1234567890abcdef")),
        ) as mock_gl:
            result = await resolve_live_head_sha(event)

        mock_gl.assert_awaited_once_with({
            "project_id": "openshift-virtualization/downstream-configuration",
            "mr_iid": 25,
        })
        assert result == ("25", "d461a00c1234567890abcdef")

    @pytest.mark.asyncio
    async def test_kargo_fallback_when_gitlab_context_has_no_project_id(self):
        """R4-03: When gitlab_context has mr_iid but lacks project_id, falls through to kargo_context.mr_url."""
        event = MagicMock()
        event.event.evidence.gitlab_context = {"mr_iid": "25"}  # missing project_id
        event.event.evidence.github_context = None
        event.event.evidence.kargo_context = {
            "mr_url": "https://gitlab.example.com/openshift-virtualization/downstream-configuration/-/merge_requests/25"
        }
        with patch(
            "src.utils.vcs_approval._resolve_gitlab_head",
            AsyncMock(return_value=("25", "live-sha-999")),
        ) as mock_gl:
            result = await resolve_live_head_sha(event)

        mock_gl.assert_awaited_once_with({
            "project_id": "openshift-virtualization/downstream-configuration",
            "mr_iid": 25,
        })
        assert result == ("25", "live-sha-999")


class TestResolveCaBundle:
    """T-9: Tests for resolve_ca_bundle (and its _resolve_ca_bundle alias) TLS trust evaluation."""

    def test_insecure_verify_env_raises_value_error(self, monkeypatch):
        """T-9: GITLAB_SSL_VERIFY='0' or 'false' raises ValueError -- verify=False is forbidden."""
        import src.utils.vcs_approval as vcs_mod
        resolve_ca = getattr(vcs_mod, "resolve_ca_bundle", None)
        assert callable(resolve_ca), "resolve_ca_bundle must be public in src.utils.vcs_approval"

        for val in ("0", "false", "no", "FALSE"):
            monkeypatch.setenv("GITLAB_SSL_VERIFY", val)
            with pytest.raises(ValueError, match="Insecure TLS verification"):
                resolve_ca("gitlab.cee.redhat.com")

    def test_ca_bundle_returns_path_or_true_never_false(self, monkeypatch, tmp_path):
        """T-9: _resolve_ca_bundle detects corporate CA path or falls back to True, NEVER False."""
        import src.utils.vcs_approval as vcs_mod
        resolve_ca = getattr(vcs_mod, "resolve_ca_bundle", None)
        assert callable(resolve_ca), "resolve_ca_bundle must be public in src.utils.vcs_approval"

        # When file exists
        ca_file = tmp_path / "custom-ca.pem"
        ca_file.write_text("cert")
        monkeypatch.setenv("GITLAB_SSL_VERIFY", str(ca_file))
        res = resolve_ca("gitlab.cee.redhat.com")
        assert res == str(ca_file)

        # When no env set and no standard paths exist, fallback is True
        monkeypatch.delenv("GITLAB_SSL_VERIFY", raising=False)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        with patch("os.path.isfile", return_value=False):
            fallback_res = resolve_ca("gitlab.cee.redhat.com")
            assert fallback_res is True
            assert fallback_res is not False

    @pytest.mark.parametrize("val", ["1", "true", "yes", "TRUE", "True", "YES"])
    def test_boolean_strings_fall_through_to_true_not_string(self, monkeypatch, val):
        """C6-06 / C12-02: Truthy boolean strings in GITLAB_SSL_VERIFY fall through to True, not string 'true'."""
        import src.utils.vcs_approval as vcs_mod
        resolve_ca = vcs_mod.resolve_ca_bundle
        monkeypatch.setenv("GITLAB_SSL_VERIFY", val)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.delenv("REQUESTS_CA_BUNDLE", raising=False)
        with patch("os.path.isfile", return_value=False):
            res = resolve_ca("gitlab.example.com")
            assert res is True
            assert not isinstance(res, str)

    def test_non_existent_path_falls_back_with_warning(self, monkeypatch, caplog):
        """C6-06: Non-existent custom CA path in REQUESTS_CA_BUNDLE warns and falls back to True or std path."""
        import src.utils.vcs_approval as vcs_mod
        resolve_ca = vcs_mod.resolve_ca_bundle
        monkeypatch.delenv("GITLAB_SSL_VERIFY", raising=False)
        monkeypatch.delenv("SSL_CERT_FILE", raising=False)
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", "/non/existent/path/ca.crt")
        with patch("os.path.isfile", return_value=False), caplog.at_level("WARNING"):
            res = resolve_ca("gitlab.example.com")
            assert res is True
            assert any("does not exist" in r.message for r in caplog.records)


class TestResolveCaBundleHardening:
    """F3/F9/F10: public resolver, empty/dir bundles rejected, generalized insecure-TLS message."""

    @staticmethod
    def _clean_env(monkeypatch):
        for k in ("GITLAB_SSL_VERIFY", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
            monkeypatch.delenv(k, raising=False)

    def test_underscore_alias_is_the_public_function(self):
        import src.utils.vcs_approval as vcs_mod
        assert vcs_mod._resolve_ca_bundle is vcs_mod.resolve_ca_bundle

    def test_insecure_message_is_not_scoped_to_approval_calls(self, monkeypatch):
        import src.utils.vcs_approval as vcs_mod
        monkeypatch.setenv("GITLAB_SSL_VERIFY", "false")
        with pytest.raises(ValueError) as exc:
            vcs_mod.resolve_ca_bundle("gitlab.example.com")
        assert "GITLAB_SSL_VERIFY=false" in str(exc.value)
        assert "approval" not in str(exc.value).lower()

    @pytest.mark.parametrize("env_name", ["GITLAB_SSL_VERIFY", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"])
    def test_empty_bundle_file_is_rejected(self, monkeypatch, tmp_path, caplog, env_name):
        import src.utils.vcs_approval as vcs_mod
        self._clean_env(monkeypatch)
        empty = tmp_path / "empty.pem"
        empty.write_text("")
        monkeypatch.setenv(env_name, str(empty))
        with caplog.at_level("WARNING"):
            res = vcs_mod.resolve_ca_bundle("gitlab.example.com")
        assert res != str(empty)
        assert any("non-empty file" in r.message for r in caplog.records)

    @pytest.mark.parametrize("env_name", ["GITLAB_SSL_VERIFY", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"])
    def test_directory_bundle_is_rejected(self, monkeypatch, tmp_path, env_name):
        import src.utils.vcs_approval as vcs_mod
        self._clean_env(monkeypatch)
        monkeypatch.setenv(env_name, str(tmp_path))  # exists, but is a directory
        res = vcs_mod.resolve_ca_bundle("gitlab.example.com")
        assert res != str(tmp_path)

    def test_empty_bundle_falls_back_to_true_when_no_standard_bundle(self, monkeypatch, tmp_path):
        import src.utils.vcs_approval as vcs_mod
        self._clean_env(monkeypatch)
        empty = tmp_path / "empty.pem"
        empty.write_text("")
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(empty))
        with patch("src.utils.vcs_approval.os.path.isfile", side_effect=lambda p: p == str(empty)):
            assert vcs_mod.resolve_ca_bundle("gitlab.example.com") is True

    def test_non_empty_bundle_file_is_accepted(self, monkeypatch, tmp_path):
        import src.utils.vcs_approval as vcs_mod
        self._clean_env(monkeypatch)
        ca = tmp_path / "ca.pem"
        ca.write_text("cert")
        monkeypatch.setenv("SSL_CERT_FILE", str(ca))
        assert vcs_mod.resolve_ca_bundle("gitlab.example.com") == str(ca)


class TestParseMrUrl:
    """Tests for parse_mr_url extracted helper."""

    def test_standard_gitlab_mr_url(self):
        from src.utils.vcs_approval import parse_mr_url
        res = parse_mr_url("https://gitlab.example.com/org/group/project/-/merge_requests/42")
        assert res == ("org/group/project", 42)

    def test_projects_id_syntax(self):
        from src.utils.vcs_approval import parse_mr_url
        res = parse_mr_url("https://gitlab.example.com/api/v4/projects/123/merge_requests/99")
        assert res == (123, 99)

    def test_invalid_url_returns_none(self):
        from src.utils.vcs_approval import parse_mr_url
        assert parse_mr_url("https://gitlab.example.com/not-an-mr") is None
        assert parse_mr_url("") is None


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


SHA = "a" * 40
OTHER_SHA = "b" * 40


class TestVerifyMergeGuardStrictApproval:
    """`approved` must be the boolean True: truthy non-booleans must not authorize anything (VMER-2271)."""

    @pytest.mark.parametrize("approved", ["false", "true", "yes", 1, 2, {}, [], [False], "x"])
    @pytest.mark.parametrize("category", ["git_merge", "operational", "unknown"])
    def test_truthy_non_boolean_approved_refused(self, approved, category):
        allowed, reason = verify_merge_guard({"approved": approved, "approved_mr_sha": SHA}, SHA, category=category)
        assert allowed is False, f"approved={approved!r} category={category}"
        assert "refused" in reason.lower()

    @pytest.mark.parametrize("record", [None, {}, {"approved": None}, {"approved": False}, {"approved_mr_sha": SHA}, "approved", 1, [], ["approved"]])
    @pytest.mark.parametrize("category", ["git_merge", "operational"])
    def test_missing_or_non_dict_record_refused(self, record, category):
        allowed, _ = verify_merge_guard(record, SHA, category=category)
        assert allowed is False, f"record={record!r} category={category}"

    def test_boolean_true_is_accepted(self):
        assert verify_merge_guard({"approved": True, "approved_mr_sha": SHA}, SHA)[0] is True
        assert verify_merge_guard({"approved": True}, None, category="operational")[0] is True

    def test_operational_none_record_refused_with_operational_wording(self):
        allowed, reason = verify_merge_guard(None, None, category="operational")
        assert allowed is False
        assert reason.startswith("Operational mutation REFUSED")

    def test_git_merge_refusal_keeps_merge_wording(self):
        allowed, reason = verify_merge_guard({"approved": False}, SHA)
        assert allowed is False
        assert reason.startswith("Merge REFUSED")

    def test_operational_ignores_local_head_sha(self):
        for local in (None, "", SHA, OTHER_SHA):
            allowed, _ = verify_merge_guard({"approved": True, "approved_mr_sha": SHA}, local, category="operational")
            assert allowed is True, f"local_head_sha={local!r}"

    @pytest.mark.parametrize("category", ["OPERATIONAL", "Operational", " operational", "operational ", "", None, "ops"])
    def test_only_exact_operational_relaxes_sha_rule(self, category):
        allowed, reason = verify_merge_guard({"approved": True, "approved_mr_sha": None}, None, category=category)
        assert allowed is False
        assert "differs" in reason.lower()

    def test_git_merge_sha_binding_edge_cases(self):
        assert verify_merge_guard({"approved": True, "approved_mr_sha": SHA}, OTHER_SHA)[0] is False
        assert verify_merge_guard({"approved": True, "approved_mr_sha": SHA}, "")[0] is False
        assert verify_merge_guard({"approved": True, "approved_mr_sha": SHA}, None)[0] is False
        assert verify_merge_guard({"approved": True, "approved_mr_sha": ""}, "")[0] is False


MERGE_GUARD_JS = Path(__file__).resolve().parents[1] / "gemini-sidecar" / "hooks" / "merge-guard.js"


@pytest.mark.skipif(shutil.which("node") is None, reason="node not available")
class TestJsPythonVerdictParity:
    """The Python verdict is the reference copy of gemini-sidecar/hooks/merge-guard.js approvalVerdict (the enforcing
    implementation). Drive both with ONE fixture matrix so they cannot drift apart silently."""

    RECORDS = [
        None, {}, {"approved": False}, {"approved": None}, {"approved": "false"}, {"approved": "true"}, {"approved": 1},
        {"approved": True}, {"approved": True, "approved_mr_sha": None}, {"approved": True, "approved_mr_sha": ""},
        {"approved": True, "approved_mr_sha": SHA}, {"approved": True, "approved_mr_sha": OTHER_SHA}, [], "approved",
    ]
    LOCALS = ["", SHA, OTHER_SHA]
    CATEGORIES = ["git_merge", "operational", "OPERATIONAL", "bogus"]

    @staticmethod
    def _js(record, local, category):
        out = subprocess.run(
            ["node", str(MERGE_GUARD_JS), "--verdict", "--", json.dumps(record), local, category],
            capture_output=True, text=True, timeout=20, check=True,
        ).stdout
        return out.split("|||", 1)[0] == "ALLOW"

    def test_allow_decisions_match_across_the_matrix(self):
        mismatches = []
        for record in self.RECORDS:
            for local in self.LOCALS:
                for category in self.CATEGORIES:
                    py = verify_merge_guard(record, local or None, category=category)[0]
                    js = self._js(record, local, category)
                    if py != js:
                        mismatches.append((record, local, category, py, js))
        assert not mismatches, f"JS/Python verdict drift: {mismatches}"


# =========================================================================
# Batch 1 ATDD (Step 5 / T-9): GitHub App installation token resolution in
# _resolve_github_head(), eager missing-.pem vs lazy corrupt-.pem fallback,
# CA bundle preservation
# =========================================================================


@pytest.fixture(autouse=True)
def _reset_shared_github_manager_vcs():
    """Teardown guard ensuring shared manager singleton never leaks across vcs_approval tests."""
    from src.utils.github_app import reset_installation_manager

    reset_installation_manager()
    yield
    reset_installation_manager()


class TestATDDT9VcsApprovalGitHubAppAuth:
    """Layer 1-4 ATDD scenarios for T-9 in src/utils/vcs_approval.py."""

    @pytest.mark.asyncio
    async def test_private_repo_authenticates_with_github_app_token_and_ca_bundle(self, monkeypatch, tmp_path):
        """Given a private GitHub App-only repo (GITHUB_TOKEN='', GITHUB_APP_ID set)
        When _resolve_github_head() runs
        Then get_installation_manager() unpacks (inst_id, client), sends
        Authorization: Bearer <app_token>, and uses resolve_ca_bundle() verify=."""
        ca_file = tmp_path / "ca.crt"
        ca_file.write_text("-----BEGIN CERTIFICATE-----\nx\n-----END CERTIFICATE-----\n")
        monkeypatch.setenv("GITHUB_TOKEN", "")
        monkeypatch.setenv("REQUESTS_CA_BUNDLE", str(ca_file))
        monkeypatch.delenv("GITLAB_SSL_VERIFY", raising=False)

        mock_gh_client = AsyncMock()
        mock_gh_client.get_token = AsyncMock(return_value="ghs_app_installation_token_xyz")
        mock_mgr = MagicMock()
        mock_mgr.get_client_for_repo = AsyncMock(return_value=("inst-123", mock_gh_client))

        mock_http_cls = _mock_client(get_return=_resp(200, {"head": {"sha": "live-app-sha-999"}}))
        gh_ctx = {"pr_number": "314", "owner": "private-org", "repo": "secret-repo", "head_sha": "stale"}

        with (
            patch("src.utils.vcs_approval.get_installation_manager", return_value=mock_mgr) as mock_get_mgr,
            patch("src.utils.vcs_approval.httpx.AsyncClient", mock_http_cls),
        ):
            pr_number, sha = await _resolve_github_head(gh_ctx)

        assert mock_get_mgr.called, "_resolve_github_head must consult get_installation_manager()"
        assert (pr_number, sha) == ("314", "live-app-sha-999")
        mock_mgr.get_client_for_repo.assert_awaited_once_with("private-org", "secret-repo")
        mock_gh_client.get_token.assert_awaited_once()
        assert mock_http_cls.call_args.kwargs["verify"] == str(ca_file)
        _, get_kwargs = mock_http_cls.return_value.__aenter__.return_value.get.call_args
        assert get_kwargs["headers"]["Authorization"] == "Bearer ghs_app_installation_token_xyz"

    @pytest.mark.asyncio
    async def test_corrupt_pem_lazy_get_token_failure_falls_back_to_pat_without_raising(self, monkeypatch, tmp_path):
        """Run #5 C-5a Path B: Given a present-but-corrupt .pem file (passes _find_pem_file
        in __init__ so get_installation_manager() returns a live manager, then fails lazily in
        _load_private_key/_create_jwt during get_token/discovery) and GITHUB_TOKEN is set
        When _resolve_github_head() runs
        Then lazy failure is caught without raising and falls back to GITHUB_TOKEN PAT."""
        from src.utils.github_app import get_installation_manager

        corrupt_pem = tmp_path / "corrupt.pem"
        corrupt_pem.write_text("NOT-A-VALID-RSA-PRIVATE-KEY")
        monkeypatch.setenv("GITHUB_APP_ID", "123456")
        monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(corrupt_pem))
        monkeypatch.delenv("GITHUB_INSTALLATION_ID", raising=False)
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_pat_fallback_token")

        mgr = get_installation_manager()
        assert mgr is not None

        mock_http_cls = _mock_client(get_return=_resp(200, {"head": {"sha": "pat-fallback-sha"}}))
        gh_ctx = {"pr_number": "42", "owner": "org", "repo": "repo", "head_sha": "stale"}
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_http_cls):
            pr_number, sha = await _resolve_github_head(gh_ctx)

        assert (pr_number, sha) == ("42", "pat-fallback-sha")
        _, get_kwargs = mock_http_cls.return_value.__aenter__.return_value.get.call_args
        assert get_kwargs["headers"]["Authorization"] == "Bearer ghp_pat_fallback_token"

    @pytest.mark.asyncio
    async def test_corrupt_pem_with_empty_pat_fails_closed_on_private_404_without_raising(self, monkeypatch, tmp_path):
        """Run #5 C-5a Path B (no PAT): Given corrupt .pem and GITHUB_TOKEN=''
        When _resolve_github_head() queries a private repo returning 404
        Then lazy App error is swallowed and returns (pr_number, None) fail-closed."""
        from src.utils.github_app import get_installation_manager

        corrupt_pem = tmp_path / "corrupt.pem"
        corrupt_pem.write_text("NOT-A-VALID-KEY")
        monkeypatch.setenv("GITHUB_APP_ID", "123456")
        monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(corrupt_pem))
        monkeypatch.setenv("GITHUB_TOKEN", "")

        assert get_installation_manager() is not None

        mock_http_cls = _mock_client(get_return=_resp(404))
        gh_ctx = {"pr_number": "42", "owner": "org", "repo": "private", "head_sha": "stale"}
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_http_cls):
            pr_number, sha = await _resolve_github_head(gh_ctx)

        assert (pr_number, sha) == ("42", None)
        _, get_kwargs = mock_http_cls.return_value.__aenter__.return_value.get.call_args
        assert "Authorization" not in get_kwargs.get("headers", {})

    @pytest.mark.asyncio
    async def test_missing_pem_path_with_app_id_set_still_queries_without_auth_header(self, monkeypatch, tmp_path):
        """Run #5 C-5a Path A end-to-end: Given GITHUB_APP_ID set with missing .pem path
        and GITHUB_TOKEN=''
        When _resolve_github_head() runs
        Then get_installation_manager() returns None cleanly and public query succeeds without
        Authorization header."""
        from src.utils.github_app import get_installation_manager

        monkeypatch.setenv("GITHUB_APP_ID", "123456")
        monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(tmp_path / "missing-dir"))
        monkeypatch.setenv("GITHUB_TOKEN", "")

        assert get_installation_manager() is None

        mock_http_cls = _mock_client(get_return=_resp(200, {"head": {"sha": "public-sha"}}))
        gh_ctx = {"pr_number": "265", "owner": "o", "repo": "r", "head_sha": "stale"}
        with patch("src.utils.vcs_approval.httpx.AsyncClient", mock_http_cls):
            pr_number, sha = await _resolve_github_head(gh_ctx)

        assert (pr_number, sha) == ("265", "public-sha")
        _, get_kwargs = mock_http_cls.return_value.__aenter__.return_value.get.call_args
        assert "Authorization" not in get_kwargs.get("headers", {})

    @pytest.mark.asyncio
    async def test_repo_cache_miss_logs_warning_and_falls_back_to_pat(self, monkeypatch, caplog):
        """F-14/F-23: Given get_client_for_repo() returns None (repo cache miss)
        When _resolve_github_head() runs
        Then an explicit warning is logged and GITHUB_TOKEN PAT is used."""
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_cache_miss_pat")
        mock_mgr = MagicMock()
        mock_mgr.get_client_for_repo = AsyncMock(return_value=None)
        mock_http_cls = _mock_client(get_return=_resp(200, {"head": {"sha": "pat-miss-sha"}}))
        gh_ctx = {"pr_number": "88", "owner": "uninstalled-org", "repo": "repo", "head_sha": "stale"}

        with (
            patch("src.utils.vcs_approval.get_installation_manager", return_value=mock_mgr),
            patch("src.utils.vcs_approval.httpx.AsyncClient", mock_http_cls),
            caplog.at_level("WARNING"),
        ):
            pr_number, sha = await _resolve_github_head(gh_ctx)

        assert (pr_number, sha) == ("88", "pat-miss-sha")
        assert any("missed repo" in r.message for r in caplog.records)
        _, get_kwargs = mock_http_cls.return_value.__aenter__.return_value.get.call_args
        assert get_kwargs["headers"]["Authorization"] == "Bearer ghp_cache_miss_pat"

    @pytest.mark.asyncio
    async def test_app_token_lookup_timeout_falls_back_to_pat(self, monkeypatch, caplog):
        """F-14: Given App token resolution exceeds the 10s wait_for timeout
        When _resolve_github_head() runs
        Then TimeoutError is caught, logged by exception type, and falls back to GITHUB_TOKEN."""
        import asyncio as _asyncio

        monkeypatch.setenv("GITHUB_TOKEN", "ghp_timeout_pat")
        mock_mgr = MagicMock()

        async def _hang(*a, **k):
            await _asyncio.sleep(30)

        mock_mgr.get_client_for_repo = AsyncMock(side_effect=_hang)
        mock_http_cls = _mock_client(get_return=_resp(200, {"head": {"sha": "timeout-fallback-sha"}}))
        gh_ctx = {"pr_number": "91", "owner": "slow-org", "repo": "repo", "head_sha": "stale"}

        async def _instant_timeout(coro, timeout=None):
            coro.close()
            raise _asyncio.TimeoutError()

        with (
            patch("src.utils.vcs_approval.get_installation_manager", return_value=mock_mgr),
            patch("src.utils.vcs_approval.asyncio.wait_for", side_effect=_instant_timeout) as mock_wait_for,
            patch("src.utils.vcs_approval.httpx.AsyncClient", mock_http_cls),
            caplog.at_level("WARNING"),
        ):
            pr_number, sha = await _resolve_github_head(gh_ctx)

        assert (pr_number, sha) == ("91", "timeout-fallback-sha")
        assert mock_wait_for.call_args.kwargs.get("timeout") == 10
        assert any("TimeoutError" in r.message for r in caplog.records)
        _, get_kwargs = mock_http_cls.return_value.__aenter__.return_value.get.call_args
        assert get_kwargs["headers"]["Authorization"] == "Bearer ghp_timeout_pat"


def test_t21_extract_context_head_sha_skips_verification_kargo_context():
    from src.utils.vcs_approval import extract_context_head_sha
    from unittest.mock import MagicMock
    event = MagicMock()
    event.event.evidence.gitlab_context = None
    event.event.evidence.github_context = None
    event.event.evidence.kargo_context = {"head_sha": "sha123", "failure_type": "verification"}
    assert extract_context_head_sha(event) is None
    
    event.event.evidence.kargo_context = {"head_sha": "sha123", "failure_type": "promotion"}
    assert extract_context_head_sha(event) == "sha123"

def test_t21_stale_gitlab_context_mirror_ignored():
    from src.utils.vcs_approval import extract_context_head_sha, _is_vcs_backed_event
    from unittest.mock import MagicMock
    event = MagicMock()
    event.event.evidence.kargo_context = {"mr_url": "url1", "failure_type": "verification"}
    event.event.evidence.gitlab_context = {"target_url": "url1", "head_sha": "sha123", "mr_iid": "1"}
    event.event.evidence.github_context = None
    
    assert extract_context_head_sha(event) is None
    assert _is_vcs_backed_event(event) is False
