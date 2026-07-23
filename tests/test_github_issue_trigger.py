# BlackBoard/tests/test_github_issue_trigger.py
# @ai-rules:
# 1. [Pattern]: Unit tests only — no Redis, no HTTP, mock everything.
# 2. [Constraint]: Tests must be hermetic (no external I/O).
# 3. [Pattern]: Use AsyncMock for coroutines, MagicMock for sync objects.
"""Tests for GitHub Headhunter v1.1: queue feedback + issue trigger."""
from __future__ import annotations

import asyncio
import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.headhunter_github import GitHubPlatform, _EMERGENCY_ISSUE_SI
from src.agents.headhunter import Headhunter
from src.models import EventEvidence


# =============================================================================
# Fixtures
# =============================================================================

def _make_blackboard():
    bb = MagicMock()
    bb.get_active_events = AsyncMock(return_value=[])
    bb.get_event = AsyncMock(return_value=None)
    bb.get_github_pr_sha = AsyncMock(return_value=None)
    bb.get_github_issue_processed = AsyncMock(return_value=False)
    bb.set_github_issue_processed = AsyncMock()
    bb.mark_feedback_sent = AsyncMock()
    bb.create_event = AsyncMock(return_value="evt-test1234")
    return bb


def _make_platform(extra_env=None):
    env = {
        "HEADHUNTER_GITHUB_ENABLED": "true",
        "GITHUB_APP_ID": "123",
        "GITHUB_INSTALLATION_ID": "456",
    }
    if extra_env:
        env.update(extra_env)
    with patch.dict(os.environ, env, clear=False):
        bb = _make_blackboard()
        p = GitHubPlatform(bb)
    return p, bb


# =============================================================================
# Test: poll_issues filters out PRs
# =============================================================================

@pytest.mark.asyncio
async def test_poll_issues_filters_out_prs():
    """GitHub /issues API returns both issues and PRs; PRs must be excluded."""
    platform, bb = _make_platform()
    client = MagicMock()
    issue_item = {"number": 10, "title": "Fix bug", "state": "open",
                  "user": {"login": "bob"}, "labels": [{"name": "darwin-work"}],
                  "assignees": [], "html_url": "https://github.com/o/r/issues/10",
                  "created_at": "2026-07-01T00:00:00Z", "body": "desc"}
    pr_item = {**issue_item, "number": 11, "pull_request": {"url": "https://..."}}
    resp = MagicMock()
    resp.json.return_value = [issue_item, pr_item]
    client.get = AsyncMock(return_value=resp)

    issues = await platform._poll_issues(client, ["o/r"], "456")
    assert len(issues) == 1
    assert issues[0]["issue_number"] == 10


# =============================================================================
# Test: _normalize_issue_data shape
# =============================================================================

def test_normalize_issue_data_shape():
    """All expected fields must be present in normalized issue."""
    raw = {"number": 5, "title": "Audit needed", "state": "open",
           "user": {"login": "alice"}, "labels": [{"name": "darwin_audit"}],
           "assignees": [{"login": "bob"}], "html_url": "https://github.com/o/r/issues/5",
           "created_at": "2026-07-01T00:00:00Z", "body": "Please audit"}
    result = GitHubPlatform._normalize_issue_data("o/r", raw, "456")
    assert result["owner"] == "o"
    assert result["repo"] == "r"
    assert result["issue_number"] == 5
    assert result["issue_title"] == "Audit needed"
    assert result["author"] == "alice"
    assert "darwin_audit" in result["labels"]
    assert "bob" in result["assignees"]
    assert result["html_url"] == "https://github.com/o/r/issues/5"
    assert result["body"] == "Please audit"


# =============================================================================
# Test: create_issue_event sets correct subject_type + context
# =============================================================================

@pytest.mark.asyncio
async def test_create_issue_event_with_skill_label():
    """create_issue_event must produce subject_type=github_issue and github_issue_context."""
    platform, bb = _make_platform({"HEADHUNTER_GITHUB_SKILL_DARWIN_AUDIT": "https://raw.example.com/audit.md"})
    # Reload skill_urls since env is now set
    platform._issue_skill_urls = {"darwin_audit": "https://raw.example.com/audit.md"}

    issue = {
        "owner": "o", "repo": "r", "issue_number": 7,
        "issue_title": "Security audit", "state": "open", "author": "alice",
        "labels": ["darwin_audit", "darwin-work"], "assignees": [],
        "html_url": "https://github.com/o/r/issues/7",
        "created_at": "2026-07-01T00:00:00Z", "body": "Needs audit",
    }
    platform._add_labels = AsyncMock()
    platform._remove_label = AsyncMock()
    platform._post_comment = AsyncMock()

    event_id = await platform.create_issue_event(issue)

    assert event_id == "evt-test1234"
    call_kwargs = bb.create_event.call_args[1]
    assert call_kwargs["subject_type"] == "github_issue"
    evidence = call_kwargs["evidence"]
    assert evidence.github_issue_context["issue_number"] == 7
    assert evidence.github_issue_context["owner"] == "o"
    assert evidence.github_issue_context["skill_label"] == "darwin_audit"


# =============================================================================
# Test: get_active_keys reads both github_context and github_issue_context
# =============================================================================

@pytest.mark.asyncio
async def test_get_active_keys_reads_both_contexts():
    """Active keys must cover both PR context and Issue context."""
    platform, bb = _make_platform()

    pr_event = MagicMock()
    pr_event.source = "headhunter"
    pr_event.status.value = "active"
    pr_event.event.evidence.github_context = {"owner": "o", "repo": "r", "pr_number": 3}
    pr_event.event.evidence.github_issue_context = None

    issue_event = MagicMock()
    issue_event.source = "headhunter"
    issue_event.status.value = "active"
    issue_event.event.evidence.github_context = None
    issue_event.event.evidence.github_issue_context = {"owner": "o", "repo": "r", "issue_number": 9}

    bb.get_active_events = AsyncMock(return_value=["evt-pr", "evt-issue"])
    bb.get_event = AsyncMock(side_effect=lambda eid: pr_event if eid == "evt-pr" else issue_event)

    keys = await platform.get_active_keys()
    assert ("o", "r", 3) in keys
    assert ("o", "r", 9) in keys


# =============================================================================
# Test: _queue_pr label ordering (ADD before REMOVE)
# =============================================================================

@pytest.mark.asyncio
async def test_queue_pr_label_ordering():
    """darwin-queued must be ADDED before darwin-review is REMOVED."""
    platform, _ = _make_platform()
    call_order = []
    platform._add_labels = AsyncMock(side_effect=lambda *a, **kw: call_order.append("add"))
    platform._remove_label = AsyncMock(side_effect=lambda *a, **kw: call_order.append("remove"))
    platform._post_comment = AsyncMock()

    pr = {"owner": "o", "repo": "r", "number": 1, "labels": ["darwin-review"], "title": "T"}
    await platform._queue_pr(pr, 1)

    assert call_order[0] == "add"
    assert call_order[1] == "remove"


# =============================================================================
# Test: _queue_pr idempotency (no duplicate comment)
# =============================================================================

@pytest.mark.asyncio
async def test_queue_pr_idempotency():
    """If darwin-queued already present (pod restart), skip the comment."""
    platform, _ = _make_platform()
    platform._add_labels = AsyncMock()
    platform._remove_label = AsyncMock()
    platform._post_comment = AsyncMock()

    pr = {"owner": "o", "repo": "r", "number": 2, "labels": ["darwin-queued"], "title": "T"}
    await platform._queue_pr(pr, 1)

    platform._post_comment.assert_not_called()


# =============================================================================
# Test: promote-before-discover ordering
# =============================================================================

@pytest.mark.asyncio
async def test_promote_before_discover_ordering():
    """Queued PRs must be processed before new darwin-review PRs."""
    bb = _make_blackboard()
    bb.get_active_events_with_status = AsyncMock(return_value={})
    bb.create_event = AsyncMock(return_value="evt-x")

    with patch.dict(os.environ, {
        "HEADHUNTER_GITHUB_ENABLED": "true",
        "GITHUB_APP_ID": "123",
        "GITHUB_INSTALLATION_ID": "456",
    }, clear=False):
        hh = Headhunter(bb)

    processed_order = []

    async def mock_fetch_context(pr):
        return {"owner": pr["owner"], "repo": pr["repo"],
                "pr_number": pr["number"], "pr_title": pr.get("title", ""),
                "pr_state": "open", "action": "review_requested",
                "check_status": "success", "head_sha": "abc"}

    async def mock_create_event(pr, plan, ctx):
        processed_order.append(pr["number"])
        return f"evt-{pr['number']}"

    queued_pr = {"owner": "o", "repo": "r", "number": 1, "labels": ["darwin-queued"],
                 "title": "Old PR", "queued": True, "created_at": "2026-07-01T00:00:00Z",
                 "state": "open", "user": "", "html_url": "", "head_sha": ""}
    new_pr = {"owner": "o", "repo": "r", "number": 2, "labels": ["darwin-review"],
              "title": "New PR", "queued": False, "created_at": "2026-07-02T00:00:00Z",
              "state": "open", "user": "", "html_url": "", "head_sha": ""}

    hh._github.poll_work_items = AsyncMock(return_value=[queued_pr, new_pr])
    hh._github.fetch_context = AsyncMock(side_effect=mock_fetch_context)
    hh._github.create_platform_event = AsyncMock(side_effect=mock_create_event)
    hh._github.load_triage_instruction = MagicMock(return_value="")
    hh._github.poll_issues_all_installations = AsyncMock(return_value=[])
    hh._github._repos = ["o/r"]

    await hh._github_poll_and_process()

    assert processed_order[0] == 1   # queued PR processed first
    assert processed_order[1] == 2   # new PR processed second


# =============================================================================
# Test: one-of validator rejects github_context + github_issue_context
# =============================================================================

def test_one_of_validator_rejects_pr_plus_issue():
    """Having both github_context and github_issue_context must raise ValueError."""
    with pytest.raises(Exception):
        EventEvidence(
            display_text="test",
            source_type="headhunter",
            github_context={"owner": "o", "repo": "r", "pr_number": 1},
            github_issue_context={"owner": "o", "repo": "r", "issue_number": 2},
        )


# =============================================================================
# Test: issue skill URL failure returns fallback
# =============================================================================

@pytest.mark.asyncio
async def test_issue_skill_url_failure_uses_fallback():
    """Any URL fetch failure must return _EMERGENCY_ISSUE_SI."""
    import httpx
    platform, _ = _make_platform()
    platform._issue_skill_urls = {"darwin_general": "https://bad.example.com/skill.md"}

    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = MagicMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)
        mock_client.get = AsyncMock(side_effect=Exception("connection refused"))
        mock_client_cls.return_value = mock_client

        si, warning = await platform._load_issue_triage_instruction(["darwin_general"])

    assert si == _EMERGENCY_ISSUE_SI
    assert warning is None


# =============================================================================
# Test: issue Redis dedup key is separate namespace from PR SHA key
# =============================================================================

@pytest.mark.asyncio
async def test_issue_dedup_key_separate_namespace():
    """Issue dedup key must use darwin:github:issue: prefix, distinct from PR SHA HASH."""
    bb = _make_blackboard()
    bb.redis = MagicMock()
    bb.redis.set = AsyncMock()
    bb.redis.exists = AsyncMock(return_value=0)

    # Simulate the blackboard methods directly
    from src.state.blackboard import BlackboardState
    async def set_github_issue_processed(owner, repo, number):
        key = f"darwin:github:issue:{owner}:{repo}:{number}"
        await bb.redis.set(key, "1", ex=604800)

    await set_github_issue_processed("o", "r", 5)
    call_args = bb.redis.set.call_args
    key = call_args[0][0]
    assert key.startswith("darwin:github:issue:")
    assert ":" in key.replace("darwin:github:issue:", "")
    # Confirm it's NOT the PR SHA HASH key
    assert key != "darwin:github:pr_sha"


# =============================================================================
# Test: pending_count includes all three counters
# =============================================================================

def test_pending_count_includes_all_three():
    """pending_count must sum gitlab + github_pr + github_issue pending."""
    bb = _make_blackboard()
    with patch.dict(os.environ, {"HEADHUNTER_GITHUB_ENABLED": "false"}, clear=False):
        hh = Headhunter(bb)
    hh._gitlab_pending = 3
    hh._github_pending = 2
    hh._github_issue_pending = 5
    assert hh.pending_count == 10


# =============================================================================
# Test: _build_issue_analysis_prompt has no PR-only fields
# =============================================================================

def test_build_issue_analysis_prompt_no_pr_fields():
    """Issue prompt must not contain branch, pipeline, merge, or head_sha fields."""
    bb = _make_blackboard()
    with patch.dict(os.environ, {"HEADHUNTER_GITHUB_ENABLED": "false"}, clear=False):
        hh = Headhunter(bb)
    ctx = {
        "issue_number": 42,
        "issue_title": "Needs audit",
        "owner": "org",
        "repo": "project",
        "state": "open",
        "author": "alice",
        "labels": ["darwin_audit"],
        "issue_body": "Please do the audit",
        "skill_label": "darwin_audit",
    }
    prompt = hh._build_issue_analysis_prompt(ctx)
    for forbidden in ("branch", "pipeline", "merge", "head_sha", "check_status"):
        assert forbidden not in prompt.lower(), f"Found forbidden field '{forbidden}' in issue prompt"
    assert "42" in prompt
    assert "alice" in prompt


# =============================================================================
# Test: _process_closed_events routes issue events to post_issue_feedback
# =============================================================================

@pytest.mark.asyncio
async def test_process_closed_events_routes_issue_to_github():
    """Issue events must route to post_issue_feedback, not gitlab or PR feedback."""
    bb = _make_blackboard()
    with patch.dict(os.environ, {
        "HEADHUNTER_GITHUB_ENABLED": "true",
        "GITHUB_APP_ID": "123",
        "GITHUB_INSTALLATION_ID": "456",
    }, clear=False):
        hh = Headhunter(bb)

    issue_event = MagicMock()
    issue_event.id = "evt-issue-001"
    issue_event.event.evidence.github_issue_context = {"owner": "o", "repo": "r", "issue_number": 5}
    issue_event.event.evidence.github_context = None
    issue_event.event.evidence.gitlab_context = None

    bb.get_recent_closed_by_source = AsyncMock(return_value=[issue_event])
    bb.is_feedback_sent = AsyncMock(return_value=False)

    hh._github.post_issue_feedback = AsyncMock()
    hh._github.post_feedback = AsyncMock()
    hh._gitlab.post_feedback = AsyncMock()

    await hh._process_closed_events()

    hh._github.post_issue_feedback.assert_called_once_with(issue_event)
    hh._github.post_feedback.assert_not_called()
    hh._gitlab.post_feedback.assert_not_called()
