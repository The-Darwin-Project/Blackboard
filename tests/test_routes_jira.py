# tests/test_routes_jira.py
# @ai-rules:
# 1. [Pattern]: Tests /jira/missions (list_missions) and POST mutation auth / {key} validation via FastAPI TestClient and direct calls, no live Jira calls.
# 2. [Constraint]: httpx.AsyncClient mocked per test; blackboard dependency overridden with AsyncMock via app.dependency_overrides[get_blackboard].
"""Route and security tests for /jira/missions (list_missions + POST mutation auth and key validation)."""
import logging
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src import auth
from src.auth import UserContext
from src.dependencies import get_blackboard
from src.routes.jira import (
    approve_mission,
    dismiss_mission,
    list_missions,
    reanalyze_mission,
    retry_mission,
    router,
)
from src.state.blackboard import BlackboardState
from src.utils.jira_context import is_valid_jira_key

_ENV = {
    "JIRA_URL": "https://jira.example.com",
    "JIRA_EMAIL": "bot@example.com",
    "JIRA_API_TOKEN": "test-token",
    "HEADHUNTER_JIRA_BOT_ACCOUNT_ID": "bot-acct-123",
    "HEADHUNTER_JIRA_LABEL": "darwin",
}


def _make_issue(key: str = "CNV-1", comment_body=None) -> dict:
    comments = []
    if comment_body is not None:
        comments.append({"author": {"accountId": "bot-acct-123"}, "body": comment_body})
    return {
        "key": key,
        "fields": {
            "summary": "Test issue",
            "status": {"name": "Planning"},
            "priority": {"name": "Major"},
            "labels": ["darwin"],
            "comment": {"comments": comments},
        },
    }


def _mock_search_response(issues: list[dict]):
    """Patch httpx.AsyncClient so the JQL search GET returns the given issues."""
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = {"issues": issues}
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("httpx.AsyncClient", return_value=mock_client)


@pytest.mark.asyncio
async def test_list_missions_returns_empty_when_not_configured():
    with patch.dict(os.environ, {"JIRA_URL": "", "JIRA_EMAIL": "", "JIRA_API_TOKEN": ""}, clear=True):
        assert await list_missions() == []


@pytest.mark.asyncio
async def test_list_missions_converts_adf_analysis_to_markdown():
    """HIGH finding coverage: adf_to_markdown() is invoked and its result is used as `analysis`."""
    adf_body = {
        "type": "doc",
        "content": [{"type": "paragraph", "content": [{"type": "text", "text": "root cause found"}]}],
    }
    issue = _make_issue(comment_body=adf_body)
    with patch.dict(os.environ, _ENV, clear=True), _mock_search_response([issue]):
        result = await list_missions()

    assert len(result) == 1
    assert result[0]["key"] == "CNV-1"
    assert result[0]["analysis"] == "root cause found"


@pytest.mark.asyncio
async def test_list_missions_passes_through_string_analysis():
    """Non-ADF (plain string) comment bodies must not be routed through adf_to_markdown."""
    issue = _make_issue(comment_body="already plain text")
    with patch.dict(os.environ, _ENV, clear=True), _mock_search_response([issue]):
        result = await list_missions()

    assert result[0]["analysis"] == "already plain text"


@pytest.mark.asyncio
async def test_list_missions_returns_none_analysis_without_darwin_comment():
    issue = _make_issue(comment_body=None)
    with patch.dict(os.environ, _ENV, clear=True), _mock_search_response([issue]):
        result = await list_missions()

    assert result[0]["analysis"] is None


@pytest.mark.asyncio
async def test_list_missions_skips_bad_issue_without_failing_whole_request():
    """Reliability: a malformed issue (missing 'key') must not abort processing of the rest."""
    good_issue = _make_issue(key="CNV-2", comment_body="fine")
    bad_issue = {"fields": {"status": {"name": "Planning"}, "comment": {"comments": []}}}  # no "key"
    with patch.dict(os.environ, _ENV, clear=True), _mock_search_response([bad_issue, good_issue]):
        result = await list_missions()

    assert len(result) == 1
    assert result[0]["key"] == "CNV-2"


@pytest.mark.asyncio
async def test_list_missions_returns_empty_on_search_failure():
    mock_resp = MagicMock()
    mock_resp.is_success = False
    mock_resp.status_code = 500
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    with patch.dict(os.environ, _ENV, clear=True), patch("httpx.AsyncClient", return_value=mock_client):
        assert await list_missions() == []


# =============================================================================
# POST Mutation Security Tests (Auth + Jira Key Validation + Audit Logging)
# =============================================================================

_MUTATION_ACTIONS = ("approve", "reanalyze", "dismiss", "retry")


def _make_test_client(mock_bb: MagicMock) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_blackboard] = lambda: mock_bb
    return TestClient(app)


def _mock_jira_http_client() -> AsyncMock:
    """Mock httpx.AsyncClient handling GET/POST/PUT for all 4 Jira mutation endpoints."""
    async def _fake_get(url, **_kwargs):
        resp = MagicMock()
        resp.is_success = True
        resp.status_code = 200
        if url.endswith("/transitions"):
            resp.json.return_value = {"transitions": [{"id": "11", "name": "To Do"}]}
        else:
            resp.json.return_value = {
                "fields": {"labels": ["darwin", "other"], "status": {"name": "To Do"}},
            }
        return resp

    ok_resp = MagicMock()
    ok_resp.is_success = True
    ok_resp.status_code = 200

    client = AsyncMock()
    client.get = AsyncMock(side_effect=_fake_get)
    client.post = AsyncMock(return_value=ok_resp)
    client.put = AsyncMock(return_value=ok_resp)
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    return client


@pytest.mark.parametrize("action", _MUTATION_ACTIONS)
@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"Authorization": "Bearer not-a-valid-jwt"},
    ],
)
def test_mutation_routes_return_401_when_dex_enabled_without_valid_auth(
    monkeypatch, action: str, headers: dict[str, str],
):
    monkeypatch.setattr(auth, "DEX_ENABLED", True)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
    mock_bb = MagicMock()
    mock_bb.clear_jira_mission_state = AsyncMock()
    client = _make_test_client(mock_bb)

    with patch.dict(os.environ, _ENV, clear=True), patch("httpx.AsyncClient") as mock_http:
        resp = client.post(f"/jira/missions/VMER-2464/{action}", headers=headers)

    assert resp.status_code == 401
    mock_bb.clear_jira_mission_state.assert_not_awaited()
    mock_http.assert_not_called()


@pytest.mark.parametrize("action", _MUTATION_ACTIONS)
def test_mutation_routes_return_401_when_trusted_proxy_enabled_without_auth(
    monkeypatch, action: str,
):
    monkeypatch.setattr(auth, "DEX_ENABLED", False)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", True)
    mock_bb = MagicMock()
    mock_bb.clear_jira_mission_state = AsyncMock()
    client = _make_test_client(mock_bb)

    with patch.dict(os.environ, _ENV, clear=True), patch("httpx.AsyncClient") as mock_http:
        resp = client.post(f"/jira/missions/VMER-2464/{action}")

    assert resp.status_code == 401
    mock_bb.clear_jira_mission_state.assert_not_awaited()
    mock_http.assert_not_called()


@pytest.mark.parametrize("action", _MUTATION_ACTIONS)
def test_mutation_routes_succeed_with_dex_authenticated_user_and_emit_audit_log(
    monkeypatch, caplog, action: str,
):
    monkeypatch.setattr(auth, "DEX_ENABLED", True)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
    monkeypatch.setattr(
        auth,
        "get_user_from_request",
        lambda _req: UserContext(user_id="alice", display_name="Alice", email="alice@example.com"),
    )
    mock_bb = MagicMock()
    mock_bb.clear_jira_mission_state = AsyncMock()
    client = _make_test_client(mock_bb)
    mock_http_client = _mock_jira_http_client()

    with (
        caplog.at_level(logging.INFO, logger="src.routes.jira"),
        patch.dict(os.environ, _ENV, clear=True),
        patch("httpx.AsyncClient", return_value=mock_http_client),
    ):
        resp = client.post(f"/jira/missions/VMER-2464/{action}")

    assert resp.status_code == 200
    assert resp.json()["key"] == "VMER-2464"
    audit_records = [r.getMessage() for r in caplog.records if "[Audit]" in r.getMessage()]
    assert len(audit_records) == 1
    assert "alice@example.com" in audit_records[0]
    assert "VMER-2464" in audit_records[0]
    assert action in audit_records[0]


@pytest.mark.parametrize("action", _MUTATION_ACTIONS)
def test_mutation_routes_succeed_in_dev_mode_when_auth_disabled(monkeypatch, action: str):
    monkeypatch.setattr(auth, "DEX_ENABLED", False)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
    mock_bb = MagicMock()
    mock_bb.clear_jira_mission_state = AsyncMock()
    client = _make_test_client(mock_bb)
    mock_http_client = _mock_jira_http_client()

    with (
        patch.dict(os.environ, _ENV, clear=True),
        patch("httpx.AsyncClient", return_value=mock_http_client),
    ):
        resp = client.post(f"/jira/missions/VMER-2464/{action}")

    assert resp.status_code == 200
    assert resp.json()["key"] == "VMER-2464"


@pytest.mark.parametrize("action", _MUTATION_ACTIONS)
@pytest.mark.parametrize(
    "raw_key",
    [
        "VMER-1%3Fexpand=all",
        "VMER-1%0A",
        "VMER-1%23frag",
        "..%5C..%5Cproject",
        "vmer-1",
    ],
)
def test_mutation_routes_reject_malicious_encoded_keys_via_http(
    monkeypatch, action: str, raw_key: str,
):
    monkeypatch.setattr(auth, "DEX_ENABLED", False)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
    mock_bb = MagicMock()
    mock_bb.clear_jira_mission_state = AsyncMock()
    client = _make_test_client(mock_bb)

    with patch.dict(os.environ, _ENV, clear=True), patch("httpx.AsyncClient") as mock_http:
        resp = client.post(f"/jira/missions/{raw_key}/{action}")

    assert resp.status_code == 400
    mock_bb.clear_jira_mission_state.assert_not_awaited()
    mock_http.assert_not_called()


@pytest.mark.parametrize("action", _MUTATION_ACTIONS)
@pytest.mark.parametrize("raw_key", ["..%2F..%2Fproject", "..%252F..%252Fproject"])
def test_mutation_routes_block_encoded_slash_traversal_via_http(
    monkeypatch, action: str, raw_key: str,
):
    """Encoded slash traversal is blocked before any state mutation (404 at router or 400 in handler)."""
    monkeypatch.setattr(auth, "DEX_ENABLED", False)
    monkeypatch.setattr(auth, "TRUSTED_PROXY_ENABLED", False)
    mock_bb = MagicMock()
    mock_bb.clear_jira_mission_state = AsyncMock()
    client = _make_test_client(mock_bb)

    with patch.dict(os.environ, _ENV, clear=True), patch("httpx.AsyncClient") as mock_http:
        resp = client.post(f"/jira/missions/{raw_key}/{action}")

    assert resp.status_code in (400, 404)
    mock_bb.clear_jira_mission_state.assert_not_awaited()
    mock_http.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "bad_key",
    ["../../project", "../foo", "VMER-1\n", "VMER-1#frag", "VMER-1?expand=all", "vmer-1"],
)
async def test_mutation_handlers_reject_invalid_keys_directly(bad_key: str):
    mock_bb = MagicMock()
    mock_bb.clear_jira_mission_state = AsyncMock()
    user = UserContext(user_id="alice", email="alice@example.com")

    with patch.dict(os.environ, _ENV, clear=True), patch("httpx.AsyncClient") as mock_http:
        with pytest.raises(HTTPException) as exc_approve:
            await approve_mission(bad_key, user=user)
        assert exc_approve.value.status_code == 400

        with pytest.raises(HTTPException) as exc_reanalyze:
            await reanalyze_mission(bad_key, blackboard=mock_bb, user=user)
        assert exc_reanalyze.value.status_code == 400

        with pytest.raises(HTTPException) as exc_dismiss:
            await dismiss_mission(bad_key, user=user)
        assert exc_dismiss.value.status_code == 400

        with pytest.raises(HTTPException) as exc_retry:
            await retry_mission(bad_key, blackboard=mock_bb, user=user)
        assert exc_retry.value.status_code == 400

    mock_bb.clear_jira_mission_state.assert_not_awaited()
    mock_http.assert_not_called()


@pytest.mark.parametrize("valid_key", ["VMER-2464", "CNV_1-99"])
def test_is_valid_jira_key_accepts_canonical_keys(valid_key: str):
    assert is_valid_jira_key(valid_key) is True


@pytest.mark.parametrize(
    "invalid_key",
    ["VMER-2464\n", "../etc", "VMER-1?a=b", "VMER-1#frag", "vmer-1", "", None, 123],
)
def test_is_valid_jira_key_rejects_invalid_values(invalid_key):
    assert is_valid_jira_key(invalid_key) is False


@pytest.mark.asyncio
async def test_blackboard_clear_jira_mission_state_rejects_invalid_key():
    bb = BlackboardState.__new__(BlackboardState)
    bb.redis = AsyncMock()

    with pytest.raises(ValueError, match="Invalid Jira issue key format"):
        await bb.clear_jira_mission_state("../etc")

    bb.redis.delete.assert_not_awaited()

    await bb.clear_jira_mission_state("VMER-2464")
    bb.redis.delete.assert_awaited_once_with("darwin:headhunter:jira:VMER-2464")
