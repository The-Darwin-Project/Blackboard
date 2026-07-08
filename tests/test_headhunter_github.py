# tests/test_headhunter_github.py
# @ai-rules:
# 1. [Constraint]: No real GitHub API calls. All async paths mocked.
# 2. [Pattern]: Tests validate invariants from code review fixes + label lifecycle.
# 3. [Pattern]: _make_platform_with_client helper provides pre-wired mock client for label/comment tests.
"""Tests for GitHubPlatform adapter — discovery, check aggregation, state_key, label lifecycle."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


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
    """Verify _list_from_repos returns all open PRs from installed repos."""

    @pytest.mark.asyncio
    async def test_all_open_prs_included(self):
        """All open PRs from installed repos are candidates (self-service model)."""
        platform = _make_platform("org/repo")
        client = AsyncMock()
        prs = [
            {"number": 1, "title": "Fix", "state": "open",
             "requested_reviewers": [], "user": {"login": "a"}, "labels": [],
             "html_url": "https://github.com/org/repo/pull/1", "created_at": "2026-01-01T00:00:00Z"},
            {"number": 2, "title": "WIP", "state": "open",
             "requested_reviewers": [], "user": {"login": "b"}, "labels": [],
             "html_url": "https://github.com/org/repo/pull/2", "created_at": "2026-01-01T00:00:00Z"},
        ]
        resp = MagicMock()
        resp.json.return_value = prs
        client.get = AsyncMock(return_value=resp)

        result = await platform._list_from_repos(client, ["org/repo"])

        assert len(result) == 2


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

    def test_non_github_host_rejected(self):
        platform = _make_platform()
        assert platform.parse_pr_url("https://evil.com/org/repo/pull/1") is None

    def test_path_traversal_rejected(self):
        platform = _make_platform()
        assert platform.parse_pr_url("https://github.com/../admin/repo/pull/1") is None


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


# ---------------------------------------------------------------------------
# Helpers for label lifecycle tests
# ---------------------------------------------------------------------------

def _make_platform_with_client(repos: str = "org/repo"):
    """Create a GitHubPlatform with a pre-wired mock client."""
    platform = _make_platform(repos)
    client = AsyncMock()
    client.post = AsyncMock(return_value=MagicMock(status_code=200))
    client.delete = AsyncMock(return_value=MagicMock(status_code=200))
    platform._client = client
    return platform, client


def _make_work_item(labels=None, state="open", head_sha="abc123"):
    return {
        "owner": "org", "repo": "repo", "number": 42,
        "title": "Test PR", "state": state, "user": "alice",
        "labels": labels or ["darwin-review"],
        "html_url": "https://github.com/org/repo/pull/42",
        "created_at": "2026-01-01T00:00:00Z",
        "head_sha": head_sha,
    }


def _make_event_stub(gh_ctx=None, close_reason="resolved"):
    """Minimal event-like object for post_feedback()."""
    evidence = MagicMock()
    evidence.github_context = gh_ctx or {
        "owner": "org", "repo": "repo", "pr_number": 42,
        "head_sha": "abc123",
    }
    event_data = MagicMock()
    event_data.evidence = evidence
    turn = MagicMock()
    turn.evidence = close_reason
    turn.actor = "brain"
    turn.action = "close"
    turn.result = None
    turn.thoughts = "Done"
    turn.timestamp = 1719849600
    evt = MagicMock()
    evt.id = "evt-test123"
    evt.event = event_data
    evt.conversation = [turn]
    return evt


# ---------------------------------------------------------------------------
# 1. Label lifecycle happy path
# ---------------------------------------------------------------------------


class TestLabelLifecycleHappyPath:

    @pytest.mark.asyncio
    async def test_create_event_swaps_labels_and_posts_comment(self):
        platform, client = _make_platform_with_client()
        platform.blackboard.create_event = AsyncMock(return_value="evt-new123")
        platform.blackboard.get_active_events = AsyncMock(return_value=[])

        event_id = await platform.create_platform_event(
            _make_work_item(), "plan text", "COMPLICATED",
            {"action": "review_requested", "check_status": "unknown",
             "pr_title": "Test", "pr_state": "open", "pr_url": "...",
             "head_sha": "abc123", "head_branch": "feat", "base_branch": "main",
             "author": "alice", "labels": ["darwin-review"], "changed_files": []},
        )
        assert event_id == "evt-new123"

        delete_calls = [c for c in client.delete.call_args_list]
        assert any("darwin-review" in str(c) for c in delete_calls)
        assert any("darwin-done" in str(c) for c in delete_calls)

        post_calls = [c for c in client.post.call_args_list]
        label_add = [c for c in post_calls if "labels" in str(c.kwargs.get("json", {}))]
        assert len(label_add) >= 1

        comment_calls = [c for c in post_calls if "comments" in str(c.args[0]) if c.args]
        assert len(comment_calls) >= 1

    @pytest.mark.asyncio
    async def test_close_event_swaps_active_to_done(self):
        platform, client = _make_platform_with_client()
        platform.blackboard.mark_feedback_sent = AsyncMock()
        platform.blackboard.set_github_pr_sha = AsyncMock()

        evt = _make_event_stub()
        await platform.post_feedback(evt)

        delete_calls = [str(c) for c in client.delete.call_args_list]
        assert any("darwin-active" in c for c in delete_calls)

        platform.blackboard.mark_feedback_sent.assert_called_once_with("evt-test123")
        platform.blackboard.set_github_pr_sha.assert_called_once_with("org", "repo", 42, "abc123")


# ---------------------------------------------------------------------------
# 2. Partial failure — label fails, event still created
# ---------------------------------------------------------------------------


class TestPartialFailure:

    @pytest.mark.asyncio
    async def test_event_created_even_when_labels_fail(self):
        platform, client = _make_platform_with_client()
        platform.blackboard.create_event = AsyncMock(return_value="evt-survives")

        resp_500 = MagicMock(status_code=500)
        resp_500.raise_for_status.side_effect = httpx.HTTPStatusError(
            "500", request=MagicMock(), response=resp_500,
        )
        client.post = AsyncMock(side_effect=httpx.HTTPStatusError(
            "500", request=MagicMock(), response=resp_500,
        ))
        client.delete = AsyncMock(side_effect=httpx.HTTPStatusError(
            "500", request=MagicMock(), response=resp_500,
        ))

        event_id = await platform.create_platform_event(
            _make_work_item(), "plan", "COMPLICATED",
            {"action": "review_requested", "check_status": "unknown",
             "pr_title": "T", "pr_state": "open", "pr_url": "...",
             "head_sha": "a", "head_branch": "f", "base_branch": "m",
             "author": "a", "labels": [], "changed_files": []},
        )
        assert event_id == "evt-survives"


# ---------------------------------------------------------------------------
# 3. Re-trigger same SHA → skipped
# ---------------------------------------------------------------------------


class TestRetriggerSameSha:

    @pytest.mark.asyncio
    async def test_done_label_same_sha_skipped(self):
        platform = _make_platform("org/repo")
        platform.blackboard.get_active_events = AsyncMock(return_value=[])
        platform.blackboard.get_github_pr_sha = AsyncMock(return_value="abc123")

        client = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = [
            {"number": 1, "title": "PR", "state": "open",
             "user": {"login": "a"}, "html_url": "...", "created_at": "...",
             "labels": [{"name": "darwin-done"}],
             "head": {"sha": "abc123"}},
        ]
        client.get = AsyncMock(return_value=resp)
        platform._client = client

        result = await platform.poll_work_items()
        assert len(result) == 0


# ---------------------------------------------------------------------------
# 4. Re-trigger new SHA → new event
# ---------------------------------------------------------------------------


class TestRetriggerNewSha:

    @pytest.mark.asyncio
    async def test_done_label_different_sha_creates_event(self):
        platform = _make_platform("org/repo")
        platform.blackboard.get_active_events = AsyncMock(return_value=[])
        platform.blackboard.get_github_pr_sha = AsyncMock(return_value="old_sha")

        client = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = [
            {"number": 1, "title": "PR", "state": "open",
             "user": {"login": "a"}, "html_url": "...", "created_at": "...",
             "labels": [{"name": "darwin-done"}],
             "head": {"sha": "new_sha"}},
        ]
        client.get = AsyncMock(return_value=resp)
        platform._client = client

        result = await platform.poll_work_items()
        assert len(result) == 1


# ---------------------------------------------------------------------------
# 5. Re-trigger no stored SHA → new event
# ---------------------------------------------------------------------------


class TestRetriggerNoStoredSha:

    @pytest.mark.asyncio
    async def test_done_label_no_stored_sha_creates_event(self):
        platform = _make_platform("org/repo")
        platform.blackboard.get_active_events = AsyncMock(return_value=[])
        platform.blackboard.get_github_pr_sha = AsyncMock(return_value=None)

        client = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = [
            {"number": 1, "title": "PR", "state": "open",
             "user": {"login": "a"}, "html_url": "...", "created_at": "...",
             "labels": [{"name": "darwin-done"}],
             "head": {"sha": "abc"}},
        ]
        client.get = AsyncMock(return_value=resp)
        platform._client = client

        result = await platform.poll_work_items()
        assert len(result) == 1


# ---------------------------------------------------------------------------
# 6. Label 404 on remove → no exception
# ---------------------------------------------------------------------------


class TestLabel404OnRemove:

    @pytest.mark.asyncio
    async def test_remove_missing_label_no_error(self):
        platform, client = _make_platform_with_client()
        resp_404 = MagicMock(status_code=404)
        client.delete = AsyncMock(side_effect=httpx.HTTPStatusError(
            "404", request=MagicMock(), response=resp_404,
        ))

        await platform._remove_label("org", "repo", 42, "nonexistent")


# ---------------------------------------------------------------------------
# 7. darwin-active skip → no duplicate
# ---------------------------------------------------------------------------


class TestActiveSkip:

    @pytest.mark.asyncio
    async def test_active_label_skips_pr(self):
        platform = _make_platform("org/repo")
        platform.blackboard.get_active_events = AsyncMock(return_value=[])

        client = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = [
            {"number": 1, "title": "PR", "state": "open",
             "user": {"login": "a"}, "html_url": "...", "created_at": "...",
             "labels": [{"name": "darwin-active"}],
             "head": {"sha": "abc"}},
        ]
        client.get = AsyncMock(return_value=resp)
        platform._client = client

        result = await platform.poll_work_items()
        assert len(result) == 0


# ---------------------------------------------------------------------------
# 8. Terminal PR → skipped
# ---------------------------------------------------------------------------


class TestTerminalPrSkipped:

    @pytest.mark.asyncio
    async def test_closed_pr_with_review_label_skipped(self):
        platform = _make_platform("org/repo")
        platform.blackboard.get_active_events = AsyncMock(return_value=[])

        client = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = [
            {"number": 1, "title": "PR", "state": "closed",
             "user": {"login": "a"}, "html_url": "...", "created_at": "...",
             "labels": [{"name": "darwin-review"}],
             "head": {"sha": "abc"}},
        ]
        client.get = AsyncMock(return_value=resp)
        platform._client = client

        result = await platform.poll_work_items()
        assert len(result) == 0

    @pytest.mark.asyncio
    async def test_merged_pr_skipped(self):
        platform = _make_platform("org/repo")
        platform.blackboard.get_active_events = AsyncMock(return_value=[])

        client = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = [
            {"number": 1, "title": "PR", "state": "merged",
             "user": {"login": "a"}, "html_url": "...", "created_at": "...",
             "labels": [{"name": "darwin-review"}],
             "head": {"sha": "abc"}},
        ]
        client.get = AsyncMock(return_value=resp)
        platform._client = client

        result = await platform.poll_work_items()
        assert len(result) == 0


# ---------------------------------------------------------------------------
# 9. Multiple labels priority: review wins over done
# ---------------------------------------------------------------------------


class TestMultipleLabelsPriority:

    @pytest.mark.asyncio
    async def test_review_plus_done_picks_review(self):
        """darwin-review is explicit user intent — takes priority over passive done."""
        platform = _make_platform("org/repo")
        platform.blackboard.get_active_events = AsyncMock(return_value=[])
        platform.blackboard.get_github_pr_sha = AsyncMock(return_value="abc")

        client = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = [
            {"number": 1, "title": "PR", "state": "open",
             "user": {"login": "a"}, "html_url": "...", "created_at": "...",
             "labels": [{"name": "darwin-review"}, {"name": "darwin-done"}],
             "head": {"sha": "abc"}},
        ]
        client.get = AsyncMock(return_value=resp)
        platform._client = client

        result = await platform.poll_work_items()
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_active_plus_review_picks_active_skip(self):
        """darwin-active (event in progress) takes priority over review."""
        platform = _make_platform("org/repo")
        platform.blackboard.get_active_events = AsyncMock(return_value=[])

        client = AsyncMock()
        resp = MagicMock()
        resp.json.return_value = [
            {"number": 1, "title": "PR", "state": "open",
             "user": {"login": "a"}, "html_url": "...", "created_at": "...",
             "labels": [{"name": "darwin-active"}, {"name": "darwin-review"}],
             "head": {"sha": "abc"}},
        ]
        client.get = AsyncMock(return_value=resp)
        platform._client = client

        result = await platform.poll_work_items()
        assert len(result) == 0
