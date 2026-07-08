# tests/test_headhunter_github.py
# @ai-rules:
# 1. [Constraint]: No real GitHub API calls. All async paths mocked.
# 2. [Pattern]: Tests validate invariants from the code review fixes (F3-F9).
"""Tests for GitHubPlatform adapter — discovery, check aggregation, state_key, parse_pr_url."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_platform(repos: str = ""):
    """Create a GitHubPlatform with a mocked blackboard."""
    with patch.dict("os.environ", {
        "HEADHUNTER_GITHUB_REPOS": repos,
        "HEADHUNTER_GITHUB_ENABLED": "true",
        "GITHUB_APP_ID": "123",
        "GITHUB_INSTALLATION_ID": "456",
    }):
        from src.agents.headhunter_github import GitHubPlatform
        bb = AsyncMock()
        return GitHubPlatform(bb)


# ---------------------------------------------------------------------------
# F3: _list_from_repos only includes PRs where bot IS in requested_reviewers
# ---------------------------------------------------------------------------


class TestListFromReposFiltering:
    """F3: Verify that _list_from_repos doesn't flood queue with unassigned PRs."""

    @pytest.mark.asyncio
    async def test_only_bot_requested_prs_included(self):
        platform = _make_platform("org/repo")
        client = AsyncMock()
        pr_with_bot = {
            "number": 1, "title": "Fix", "state": "open",
            "requested_reviewers": [{"login": "darwin-project-ai[bot]"}],
            "user": {"login": "author"}, "labels": [],
            "html_url": "https://github.com/org/repo/pull/1",
            "created_at": "2026-01-01T00:00:00Z",
        }
        pr_no_reviewers = {
            "number": 2, "title": "WIP", "state": "open",
            "requested_reviewers": [],
            "user": {"login": "author"}, "labels": [],
            "html_url": "https://github.com/org/repo/pull/2",
            "created_at": "2026-01-01T00:00:00Z",
        }
        pr_other_reviewer = {
            "number": 3, "title": "Other", "state": "open",
            "requested_reviewers": [{"login": "human-dev"}],
            "user": {"login": "author"}, "labels": [],
            "html_url": "https://github.com/org/repo/pull/3",
            "created_at": "2026-01-01T00:00:00Z",
        }
        resp = MagicMock()
        resp.json.return_value = [pr_with_bot, pr_no_reviewers, pr_other_reviewer]
        client.get = AsyncMock(return_value=resp)

        result = await platform._list_from_repos(client)

        assert len(result) == 1
        assert result[0]["number"] == 1


# ---------------------------------------------------------------------------
# F7: _aggregate_check_status handles terminal conclusions
# ---------------------------------------------------------------------------


class TestAggregateCheckStatus:

    def test_failure_detected(self):
        platform = _make_platform()
        runs = [{"conclusion": "failure", "status": "completed"}]
        assert platform._aggregate_check_status(runs) == "failure"

    def test_cancelled_is_failure(self):
        platform = _make_platform()
        runs = [{"conclusion": "cancelled", "status": "completed"}]
        assert platform._aggregate_check_status(runs) == "failure"

    def test_timed_out_is_failure(self):
        platform = _make_platform()
        runs = [{"conclusion": "timed_out", "status": "completed"}]
        assert platform._aggregate_check_status(runs) == "failure"

    def test_action_required_is_failure(self):
        platform = _make_platform()
        runs = [{"conclusion": "action_required", "status": "completed"}]
        assert platform._aggregate_check_status(runs) == "failure"

    def test_all_success(self):
        platform = _make_platform()
        runs = [
            {"conclusion": "success", "status": "completed"},
            {"conclusion": "success", "status": "completed"},
        ]
        assert platform._aggregate_check_status(runs) == "success"

    def test_in_progress_is_pending(self):
        platform = _make_platform()
        runs = [
            {"conclusion": "success", "status": "completed"},
            {"conclusion": None, "status": "in_progress"},
        ]
        assert platform._aggregate_check_status(runs) == "pending"

    def test_empty_is_unknown(self):
        platform = _make_platform()
        assert platform._aggregate_check_status([]) == "unknown"


# ---------------------------------------------------------------------------
# parse_pr_url
# ---------------------------------------------------------------------------


class TestParsePrUrl:

    def test_standard_url(self):
        platform = _make_platform()
        result = platform.parse_pr_url("https://github.com/The-Darwin-Project/BlackBoard/pull/42")
        assert result == ("The-Darwin-Project", "BlackBoard", 42)

    def test_url_with_fragment(self):
        platform = _make_platform()
        result = platform.parse_pr_url("https://github.com/org/repo/pull/7#discussion_r123")
        assert result == ("org", "repo", 7)

    def test_invalid_url_returns_none(self):
        platform = _make_platform()
        assert platform.parse_pr_url("https://gitlab.com/org/repo/-/merge_requests/1") is None

    def test_non_numeric_pr(self):
        platform = _make_platform()
        assert platform.parse_pr_url("https://github.com/org/repo/pull/abc") is None


# ---------------------------------------------------------------------------
# extract_github_state_key (mergeable excluded)
# ---------------------------------------------------------------------------


class TestExtractGitHubStateKey:

    def test_excludes_mergeable(self):
        platform = _make_platform()
        state = {"pr_state": "open", "check_status": "success", "mergeable": True}
        key = platform.extract_github_state_key(state)
        assert "mergeable" not in key
        assert key == {"pr_state": "open", "check_status": "success"}


# ---------------------------------------------------------------------------
# Tool schema: refresh_github_context exists in BRAIN_TOOL_SCHEMAS
# ---------------------------------------------------------------------------


class TestToolSchemaPresence:

    def test_refresh_github_context_in_brain_schemas(self):
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
        names = {t["name"] for t in BRAIN_TOOL_SCHEMAS}
        assert "refresh_github_context" in names

    def test_refresh_github_context_schema_shape(self):
        from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
        schema = next(t for t in BRAIN_TOOL_SCHEMAS if t["name"] == "refresh_github_context")
        props = schema["input_schema"]["properties"]
        assert "check_condition" in props
        assert "pr_url" in props
        assert "subscribe" in props
        assert schema["input_schema"]["required"] == ["check_condition"]


# ---------------------------------------------------------------------------
# Formatter: context-aware emoji
# ---------------------------------------------------------------------------


class TestFormatterEmoji:

    def test_headhunter_gitlab_default(self):
        from src.channels.formatter import resolve_source_emoji
        assert resolve_source_emoji({"source": "headhunter"}) == ":gitlab:"

    def test_headhunter_github_context(self):
        from src.channels.formatter import resolve_source_emoji
        evt = {"source": "headhunter", "evidence": {"github_context": {"owner": "org"}}}
        assert resolve_source_emoji(evt) == ":github:"

    def test_non_headhunter_unaffected(self):
        from src.channels.formatter import resolve_source_emoji
        assert resolve_source_emoji({"source": "chat"}) == ":speech_balloon:"
