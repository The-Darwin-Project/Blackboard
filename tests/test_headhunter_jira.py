# BlackBoard/tests/test_headhunter_jira.py
# @ai-rules:
# 1. [Constraint]: No real Jira, Claude, or Redis API calls. All mocked via unittest.mock.
# 2. [Pattern]: StubBlackboard with create_event + mock redis for state verification.
# 3. [Pattern]: Each test creates a HeadhunterJira with monkeypatched env vars.
# 4. [Pattern]: Redis mock uses dict-backed get/set/delete for deterministic testing.
"""Unit tests for HeadhunterJira polling head."""
from __future__ import annotations

import json
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.headhunter_jira import HeadhunterJira, _walk_adf_mentions, format_jira_for_llm


# =========================================================================
# Fixtures
# =========================================================================

def _make_issue(key: str = "CNV-85192", status: str = "Planning", summary: str = "Test VM boot", labels: list[str] | None = None) -> dict:
    if labels is None:
        labels = ["darwin"]
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
            "labels": labels,
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


def _make_mock_redis() -> MagicMock:
    """Create a dict-backed mock Redis client for deterministic testing."""
    store: dict[str, str] = {}
    redis = MagicMock()
    redis.get = AsyncMock(side_effect=lambda k: store.get(k))
    redis.set = AsyncMock(side_effect=lambda k, v, **kw: store.__setitem__(k, v))
    redis.delete = AsyncMock(side_effect=lambda k: store.pop(k, None))
    redis._store = store
    return redis


@pytest.fixture
def stub_blackboard():
    bb = MagicMock()
    bb.create_event = AsyncMock(return_value="evt-jira-001")
    bb.get_active_events = AsyncMock(return_value=[])
    bb.get_active_events_with_status = AsyncMock(return_value={})
    bb.get_event = AsyncMock(return_value=None)
    bb.redis = _make_mock_redis()
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
    async def test_create_jira_event(self, jira_head, stub_blackboard):
        issue = _make_issue()
        event_id = await jira_head.create_jira_event(issue, "---\nplan: test\n---")
        assert event_id == "evt-jira-001"
        stub_blackboard.create_event.assert_called_once()
        call_kwargs = stub_blackboard.create_event.call_args
        assert call_kwargs.kwargs["subject_type"] == "jira"
        assert call_kwargs.kwargs["source"] == "headhunter"
        evidence = call_kwargs.kwargs["evidence"]
        assert "mission_label" in evidence.jira_context

    @pytest.mark.asyncio
    async def test_create_jira_event_with_label(self, jira_head, stub_blackboard):
        issue = _make_issue()
        issue["fields"]["labels"] = ["darwin", "darwin_general"]
        event_id = await jira_head.create_jira_event(issue, "---\nplan: test\n---", mission_label="darwin_general")
        assert event_id == "evt-jira-001"
        call_kwargs = stub_blackboard.create_event.call_args
        evidence = call_kwargs.kwargs["evidence"]
        assert "(darwin_general)" in evidence.display_text
        assert evidence.jira_context["mission_label"] == "darwin_general"

    @pytest.mark.asyncio
    async def test_create_jira_event_generic_without_label(self, jira_head, stub_blackboard):
        """T-2: display_text is generic when mission_label is empty."""
        issue = _make_issue(labels=["darwin"])
        await jira_head.create_jira_event(
            issue, "---\nplan: test\n---", mission_label=""
        )
        evidence = stub_blackboard.create_event.call_args.kwargs["evidence"]
        assert evidence.display_text == "Jira mission: CNV-85192 - Test VM boot"
        assert "(" not in evidence.display_text


# =========================================================================
# Mission Label Resolution
# =========================================================================

class TestMissionLabelResolution:
    """T-4, T-5, T-6: unit tests for _resolve_mission_label."""

    def test_prefers_skill_url_match(self, jira_head):
        """T-4: when multiple non-base labels exist, prefer the one with a skill URL."""
        jira_head._skill_urls = {"darwin_qe": "https://example.com/skill.md"}
        issue = _make_issue(labels=["darwin", "darwin_general", "darwin_qe"])
        result = jira_head._resolve_mission_label(issue)
        assert result == "darwin_qe"

    def test_fallback_first_non_base_label(self, jira_head):
        """T-5: no skill URL match -> return first non-base label."""
        jira_head._skill_urls = {}
        issue = _make_issue(labels=["darwin", "some_label"])
        result = jira_head._resolve_mission_label(issue)
        assert result == "some_label"

    def test_returns_empty_for_base_only(self, jira_head):
        """T-6: only base label -> empty string."""
        jira_head._skill_urls = {}
        issue = _make_issue(labels=["darwin"])
        result = jira_head._resolve_mission_label(issue)
        assert result == ""


# =========================================================================
# Poll and Process (mocked)
# =========================================================================

class TestPollAndProcess:
    @pytest.mark.asyncio
    async def test_planning_issue_gets_analyzed(self, jira_head, stub_blackboard):
        issue = _make_issue(status="Planning")
        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "analyze_and_comment", new_callable=AsyncMock, return_value=("comment-1", "analysis text")),
        ):
            await jira_head.poll_and_process()
            state = await jira_head._get_issue_state("CNV-85192")
            assert state is not None
            assert state["phase"] == "analyzed"

    @pytest.mark.asyncio
    async def test_todo_issue_creates_event(self, jira_head, stub_blackboard):
        issue = _make_issue(status="To Do")
        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "_run_claude_analysis", new_callable=AsyncMock, return_value="analysis text"),
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, return_value="---\nplan: test\n---"),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, return_value="evt-001"),
        ):
            await jira_head.poll_and_process()
            state = await jira_head._get_issue_state("CNV-85192")
            assert state is not None
            assert state["phase"] == "event_created"

    @pytest.mark.asyncio
    async def test_already_processed_todo_is_skipped(self, jira_head, stub_blackboard):
        issue = _make_issue(status="To Do")
        await jira_head._set_issue_state("CNV-85192", {"phase": "event_created", "event_id": "evt-old"})
        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock) as mock_create,
        ):
            await jira_head.poll_and_process()
            mock_create.assert_not_called()

    @pytest.mark.asyncio
    async def test_poll_and_process_threads_mission_label(self, jira_head, stub_blackboard):
        """T-7: poll_and_process resolves label and passes mission_label to create_jira_event."""
        jira_head._skill_urls = {"darwin_general": "https://example.com/general.md"}
        issue = _make_issue(status="To Do", labels=["darwin", "darwin_general"])
        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "_run_claude_analysis", new_callable=AsyncMock, return_value="analysis text"),
            patch.object(jira_head, "_run_brain_plan", new_callable=AsyncMock, return_value="---\nplan: test\n---"),
            patch.object(jira_head, "create_jira_event", new_callable=AsyncMock, return_value="evt-001") as mock_create,
        ):
            await jira_head.poll_and_process()
            mock_create.assert_called_once()
            assert mock_create.call_args.kwargs.get("mission_label") == "darwin_general"


# =========================================================================
# Redis State Helpers
# =========================================================================

class TestRedisState:
    @pytest.mark.asyncio
    async def test_get_issue_state_returns_none_when_missing(self, jira_head):
        state = await jira_head._get_issue_state("NONEXISTENT-1")
        assert state is None

    @pytest.mark.asyncio
    async def test_set_issue_state_persists_with_ttl(self, jira_head, stub_blackboard):
        await jira_head._set_issue_state("CNV-100", {"phase": "analyzed", "last_comment_id": "c1"})
        stub_blackboard.redis.set.assert_called_once()
        call_kwargs = stub_blackboard.redis.set.call_args
        assert call_kwargs.kwargs.get("ex") == 604800
        state = await jira_head._get_issue_state("CNV-100")
        assert state["phase"] == "analyzed"
        assert "updated_at" in state

    @pytest.mark.asyncio
    async def test_state_survives_simulated_restart(self, stub_blackboard, monkeypatch):
        """Write state, create a new HeadhunterJira (simulated restart), verify read."""
        monkeypatch.setenv("JIRA_URL", "https://jira.example.com")
        monkeypatch.setenv("JIRA_EMAIL", "bot@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
        monkeypatch.setenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "bot-acct-123")
        h1 = HeadhunterJira(stub_blackboard)
        await h1._set_issue_state("CNV-200", {"phase": "event_created", "event_id": "evt-1"})
        h2 = HeadhunterJira(stub_blackboard)
        state = await h2._get_issue_state("CNV-200")
        assert state is not None
        assert state["phase"] == "event_created"


# =========================================================================
# Active Jira Keys Dedup
# =========================================================================

class TestActiveJiraKeys:
    @pytest.mark.asyncio
    async def test_extracts_issue_key_from_active_events(self, jira_head, stub_blackboard):
        mock_event = MagicMock()
        mock_event.source = "headhunter"
        mock_event.subject_type = "jira"
        mock_event.status.value = "active"
        mock_event.event.evidence.jira_context = {"issue_key": "CNV-300"}
        stub_blackboard.get_active_events = AsyncMock(return_value=["evt-1"])
        stub_blackboard.get_event = AsyncMock(return_value=mock_event)
        keys = await jira_head._get_active_jira_keys()
        assert keys == {"CNV-300"}

    @pytest.mark.asyncio
    async def test_excludes_closed_events(self, jira_head, stub_blackboard):
        mock_event = MagicMock()
        mock_event.source = "headhunter"
        mock_event.subject_type = "jira"
        mock_event.status.value = "closed"
        mock_event.event.evidence.jira_context = {"issue_key": "CNV-400"}
        stub_blackboard.get_active_events = AsyncMock(return_value=["evt-1"])
        stub_blackboard.get_event = AsyncMock(return_value=mock_event)
        keys = await jira_head._get_active_jira_keys()
        assert keys == set()


# =========================================================================
# Cold-Start Recovery
# =========================================================================

class TestColdStartRecovery:
    @pytest.mark.asyncio
    async def test_reconstructs_from_bot_comment(self, jira_head, stub_blackboard):
        issue = _make_issue(status="Planning")
        issue["fields"]["comment"]["comments"] = [
            _make_adf_comment("c10", "bot-acct-123"),
        ]
        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "analyze_and_comment", new_callable=AsyncMock) as mock_analyze,
        ):
            await jira_head.poll_and_process()
            mock_analyze.assert_not_called()
            state = await jira_head._get_issue_state("CNV-85192")
            assert state is not None
            assert state["phase"] == "analyzed"
            assert state["last_comment_id"] == "c10"

    @pytest.mark.asyncio
    async def test_skips_cold_start_when_redis_populated(self, jira_head, stub_blackboard):
        issue = _make_issue(status="Planning")
        await jira_head._set_issue_state("CNV-85192", {"phase": "analyzed", "last_comment_id": "c5"})
        with (
            patch.object(jira_head, "poll_planning", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira_head, "poll_todo", new_callable=AsyncMock, return_value=[]),
            patch.object(jira_head, "has_reeval_signal", new_callable=AsyncMock, return_value=False),
            patch.object(jira_head, "analyze_and_comment", new_callable=AsyncMock) as mock_analyze,
        ):
            await jira_head.poll_and_process()
            mock_analyze.assert_not_called()


# =========================================================================
# Retry Clears Redis State
# =========================================================================

class TestRetryAction:
    @pytest.mark.asyncio
    async def test_retry_clears_redis_state(self, jira_head, stub_blackboard):
        await jira_head._set_issue_state("CNV-500", {"phase": "event_created", "event_id": "evt-1"})
        state = await jira_head._get_issue_state("CNV-500")
        assert state is not None
        await stub_blackboard.redis.delete(f"darwin:headhunter:jira:CNV-500")
        state = await jira_head._get_issue_state("CNV-500")
        assert state is None


# =========================================================================
# Mission Label Threading (integration)
# =========================================================================

class TestMissionLabelThreading:
    @pytest.mark.asyncio
    async def test_poll_threads_mission_label(self, stub_blackboard, monkeypatch):
        """Multi-label issue with one matching _skill_urls passes correct mission_label to create_jira_event."""
        monkeypatch.setenv("JIRA_URL", "https://jira.example.com")
        monkeypatch.setenv("JIRA_EMAIL", "bot@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
        monkeypatch.setenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "bot-acct-123")
        monkeypatch.setenv("HEADHUNTER_JIRA_LABEL", "darwin")
        monkeypatch.setenv("HEADHUNTER_JIRA_SKILL_DARWIN_GENERAL", "https://raw.example.com/skill.md")
        jira = HeadhunterJira(stub_blackboard)
        issue = _make_issue(status="To Do")
        issue["fields"]["labels"] = ["darwin", "darwin_general", "other_label"]
        with (
            patch.object(jira, "poll_planning", new_callable=AsyncMock, return_value=[]),
            patch.object(jira, "poll_todo", new_callable=AsyncMock, return_value=[issue]),
            patch.object(jira, "_run_claude_analysis", new_callable=AsyncMock, return_value="analysis"),
            patch.object(jira, "_run_brain_plan", new_callable=AsyncMock, return_value="---\nplan: x\n---"),
            patch.object(jira, "create_jira_event", new_callable=AsyncMock, return_value="evt-lbl") as mock_create,
        ):
            await jira.poll_and_process()
            mock_create.assert_called_once()
            call_kwargs = mock_create.call_args
            assert call_kwargs.kwargs["mission_label"] == "darwin_general"

    @pytest.mark.asyncio
    async def test_resolve_mission_label_prefers_skill_url_match(self, stub_blackboard, monkeypatch):
        """_resolve_mission_label picks the label matching a configured skill URL over a non-matching one."""
        monkeypatch.setenv("JIRA_URL", "https://jira.example.com")
        monkeypatch.setenv("JIRA_EMAIL", "bot@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
        monkeypatch.setenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "bot-acct-123")
        monkeypatch.setenv("HEADHUNTER_JIRA_LABEL", "darwin")
        monkeypatch.setenv("HEADHUNTER_JIRA_SKILL_DARWIN_GENERAL", "https://raw.example.com/skill.md")
        jira = HeadhunterJira(stub_blackboard)
        issue = {"fields": {"labels": ["darwin", "unknown_label", "darwin_general"]}}
        assert jira._resolve_mission_label(issue) == "darwin_general"

    @pytest.mark.asyncio
    async def test_resolve_mission_label_falls_back_to_first(self, stub_blackboard, monkeypatch):
        """Without skill URL match, returns first non-base label."""
        monkeypatch.setenv("JIRA_URL", "https://jira.example.com")
        monkeypatch.setenv("JIRA_EMAIL", "bot@example.com")
        monkeypatch.setenv("JIRA_API_TOKEN", "test-token")
        monkeypatch.setenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "bot-acct-123")
        monkeypatch.setenv("HEADHUNTER_JIRA_LABEL", "darwin")
        jira = HeadhunterJira(stub_blackboard)
        issue = {"fields": {"labels": ["darwin", "some_other_label"]}}
        assert jira._resolve_mission_label(issue) == "some_other_label"
