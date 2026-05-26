# BlackBoard/tests/test_headhunter_jira.py
# @ai-rules:
# 1. [Constraint]: No real Jira or Claude API calls. All mocked via unittest.mock.
# 2. [Pattern]: StubBlackboard with create_event mock for event capture.
# 3. [Pattern]: Each test creates a HeadhunterJira with monkeypatched env vars.
"""Unit tests for HeadhunterJira polling head."""
from __future__ import annotations

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.headhunter_jira import HeadhunterJira, _walk_adf_mentions, format_jira_for_llm


# =========================================================================
# Fixtures
# =========================================================================

def _make_issue(key: str = "CNV-85192", status: str = "Planning", summary: str = "Test VM boot") -> dict:
    return {
        "key": key,
        "fields": {
            "summary": summary,
            "status": {"name": status},
            "issuetype": {"name": "Bug"},
            "priority": {"name": "Major"},
            "description": {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "VM fails to boot"}]}]},
            "comment": {"comments": []},
            "issuelinks": [],
            "parent": {},
            "labels": ["darwin"],
            "components": [{"name": "kubevirt-ui"}],
            "fixVersions": [{"name": "4.18"}],
        },
    }


def _make_adf_comment(comment_id: str, author_id: str, mentions: list[str] | None = None) -> dict:
    """Build a Jira comment with ADF body, optionally with @mentions."""
    content_nodes = [{"type": "text", "text": "Please re-analyze"}]
    if mentions:
        for m in mentions:
            content_nodes.append({"type": "mention", "attrs": {"id": m, "text": f"@user-{m}"}})
    return {
        "id": comment_id,
        "author": {"accountId": author_id},
        "body": {
            "type": "doc",
            "content": [{"type": "paragraph", "content": content_nodes}],
        },
    }


@pytest.fixture
def stub_blackboard():
    bb = MagicMock()
    bb.create_event = AsyncMock(return_value="evt-jira-001")
    return bb


@pytest.fixture
def jira_head(stub_blackboard, monkeypatch):
    monkeypatch.setenv("JIRA_URL", "https://jira.example.com")
    monkeypatch.setenv("JIRA_EMAIL", "bot@example.com")
    monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
    monkeypatch.setenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "bot-acct-123")
    monkeypatch.setenv("HEADHUNTER_JIRA_LABEL", "darwin")
    return HeadhunterJira(stub_blackboard)


# =========================================================================
# ADF Mention Parsing
# =========================================================================

class TestADFMentionParsing:
    def test_empty_body(self):
        assert _walk_adf_mentions({}) == set()

    def test_single_mention(self):
        body = {
            "type": "doc",
            "content": [
                {"type": "paragraph", "content": [
                    {"type": "mention", "attrs": {"id": "user-1", "text": "@alice"}},
                ]},
            ],
        }
        assert _walk_adf_mentions(body) == {"user-1"}

    def test_nested_mentions(self):
        body = {
            "type": "doc",
            "content": [
                {"type": "panel", "content": [
                    {"type": "paragraph", "content": [
                        {"type": "mention", "attrs": {"id": "user-a"}},
                        {"type": "text", "text": " and "},
                        {"type": "mention", "attrs": {"id": "user-b"}},
                    ]},
                ]},
            ],
        }
        assert _walk_adf_mentions(body) == {"user-a", "user-b"}

    def test_no_mentions(self):
        body = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "plain text"}]}]}
        assert _walk_adf_mentions(body) == set()


# =========================================================================
# Enabled Check
# =========================================================================

class TestEnabled:
    def test_enabled_when_configured(self, jira_head):
        assert jira_head.enabled() is True

    def test_disabled_when_missing_url(self, stub_blackboard, monkeypatch):
        monkeypatch.setenv("JIRA_URL", "")
        monkeypatch.setenv("JIRA_API_TOKEN", "token")
        monkeypatch.setenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "bot")
        h = HeadhunterJira(stub_blackboard)
        assert h.enabled() is False


# =========================================================================
# Re-Evaluation Gate
# =========================================================================

class TestReevalSignal:
    @pytest.mark.asyncio
    async def test_no_reeval_when_no_new_comments(self, jira_head):
        issue = _make_issue()
        issue["fields"]["comment"]["comments"] = [
            _make_adf_comment("c1", "bot-acct-123"),
        ]
        with patch.object(jira_head, "get_watchers", new_callable=AsyncMock, return_value={"watcher-1"}):
            assert await jira_head.has_reeval_signal(issue, "c1") is False

    @pytest.mark.asyncio
    async def test_reeval_when_watcher_mentions_bot(self, jira_head):
        issue = _make_issue()
        issue["fields"]["comment"]["comments"] = [
            _make_adf_comment("c1", "bot-acct-123"),
            _make_adf_comment("c2", "watcher-1", mentions=["bot-acct-123"]),
        ]
        with patch.object(jira_head, "get_watchers", new_callable=AsyncMock, return_value={"watcher-1"}):
            assert await jira_head.has_reeval_signal(issue, "c1") is True

    @pytest.mark.asyncio
    async def test_no_reeval_when_non_watcher_mentions(self, jira_head):
        issue = _make_issue()
        issue["fields"]["comment"]["comments"] = [
            _make_adf_comment("c1", "bot-acct-123"),
            _make_adf_comment("c2", "random-user", mentions=["bot-acct-123"]),
        ]
        with patch.object(jira_head, "get_watchers", new_callable=AsyncMock, return_value={"watcher-1"}):
            assert await jira_head.has_reeval_signal(issue, "c1") is False


# =========================================================================
# Format for LLM
# =========================================================================

class TestFormatJiraForLLM:
    def test_basic_formatting(self):
        issue = _make_issue()
        text = format_jira_for_llm(issue)
        assert "CNV-85192" in text
        assert "Test VM boot" in text
        assert "kubevirt-ui" in text


# =========================================================================
# Event Creation
# =========================================================================

class TestEventCreation:
    @pytest.mark.asyncio
    async def test_create_qe_event(self, jira_head, stub_blackboard):
        issue = _make_issue()
        event_id = await jira_head.create_qe_event(issue, "---\nplan: test\n---")
        assert event_id == "evt-jira-001"
        stub_blackboard.create_event.assert_called_once()
        call_kwargs = stub_blackboard.create_event.call_args
        assert call_kwargs.kwargs["subject_type"] == "jira"
        assert call_kwargs.kwargs["source"] == "headhunter"


# =========================================================================
# Poll and Process (mocked)
# =========================================================================

class TestPollAndProcess:
    @pytest.mark.asyncio
    async def test_planning_issue_gets_analyzed(self, jira_head):
        issue = _make_issue(status="Planning")
        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "analyze_and_comment", new_callable=AsyncMock, return_value=("comment-1", "analysis text")),
        ):
            await jira_head.poll_and_process()
            assert jira_head._analyzed_issues["CNV-85192"]["phase"] == "analyzed"

    @pytest.mark.asyncio
    async def test_todo_issue_creates_event(self, jira_head, stub_blackboard):
        issue = _make_issue(status="To Do")
        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "_run_claude_analysis", new_callable=AsyncMock, return_value="analysis text"),
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, return_value="---\nplan: test\n---"),
            patch.object(jira_head, "create_qe_event", new_callable=AsyncMock, return_value="evt-001"),
        ):
            await jira_head.poll_and_process()
            assert jira_head._analyzed_issues["CNV-85192"]["phase"] == "event_created"

    @pytest.mark.asyncio
    async def test_already_processed_todo_is_skipped(self, jira_head):
        issue = _make_issue(status="To Do")
        jira_head._analyzed_issues["CNV-85192"] = {"last_comment_id": "", "phase": "event_created"}
        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "create_qe_event", new_callable=AsyncMock) as mock_create,
        ):
            await jira_head.poll_and_process()
            mock_create.assert_not_called()
