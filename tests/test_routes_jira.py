# tests/test_routes_jira.py
# @ai-rules:
# 1. [Pattern]: Tests the /jira/missions route directly (async function call), no live Jira calls.
# 2. [Constraint]: httpx.AsyncClient mocked per test.pipeline_and_enforce_casual / test_headhunter pattern.
"""Route tests for /jira/missions (list_missions)."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.routes.jira import list_missions

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
