# BlackBoard/tests/test_headhunter.py
# @ai-rules:
# 1. [Constraint]: No real GitLab API calls. All HTTP mocked via httpx_mock or monkeypatch.
# 2. [Pattern]: StubBlackboard from run_headhunter_local.py pattern for event capture.
# 3. [Pattern]: Each test creates a Headhunter with StubBlackboard, never Redis.
"""Unit tests for Headhunter GitLab todo poller."""
from __future__ import annotations

import asyncio
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.headhunter import ACTION_PRIORITY, V1_ACTIONABLE, Headhunter
from src.models import EventEvidence


# =========================================================================
# Fixtures
# =========================================================================

def _make_todo(
    action_name: str = "assigned",
    todo_id: int = 1,
    project_id: int = 100,
    mr_iid: int = 42,
    mr_title: str = "Fix flaky test",
    mr_state: str = "opened",
    merge_status: str = "can_be_merged",
    source_branch: str = "fix/flaky",
    target_branch: str = "main",
    author: str = "dev-user",
    pipeline_status: str = "success",
) -> dict:
    return {
        "id": todo_id,
        "action_name": action_name,
        "target_url": f"https://gitlab.example.com/group/repo/-/merge_requests/{mr_iid}",
        "project": {
            "id": project_id,
            "path_with_namespace": "group/repo",
        },
        "target": {
            "iid": mr_iid,
            "title": mr_title,
            "state": mr_state,
            "merge_status": merge_status,
            "source_branch": source_branch,
            "target_branch": target_branch,
            "description": "Some MR description",
            "author": {"username": author},
            "labels": ["bugfix"],
            "milestone": None,
        },
    }


class StubBlackboard:
    def __init__(self, active_events=None):
        self.events: list[dict] = []
        self._counter = 0
        self._active = active_events or []

    async def create_event(self, source, service, reason, evidence):
        self._counter += 1
        eid = f"evt-test-{self._counter:04d}"
        self.events.append({"id": eid, "source": source, "service": service})
        return eid

    async def get_active_events(self):
        return [e["id"] for e in self._active]

    async def get_event(self, event_id):
        for e in self._active:
            if e["id"] == event_id:
                return e
        return None

    async def get_services(self):
        return {}


def _make_headhunter(blackboard=None, **env_overrides) -> Headhunter:
    defaults = {"GITLAB_HOST": "gitlab.example.com", "HEADHUNTER_MAX_ACTIVE": "1"}
    defaults.update(env_overrides)
    with patch.dict(os.environ, defaults):
        hh = Headhunter(blackboard or StubBlackboard())
        hh._gitlab_token = "test-token"
    return hh


# =========================================================================
# Poll & Filter Tests
# =========================================================================

class TestPollCycle:
    @pytest.mark.asyncio
    async def test_fetches_and_filters_actionable_todos(self):
        todos_response = [
            _make_todo(action_name="assigned", todo_id=1),
            _make_todo(action_name="marked", todo_id=2),
            _make_todo(action_name="build_failed", todo_id=3, mr_iid=99),
        ]
        hh = _make_headhunter()
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = todos_response
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await hh.poll_cycle()
            assert len(result) == 2
            actions = {t["action_name"] for t in result}
            assert "marked" not in actions

    @pytest.mark.asyncio
    async def test_dedup_skips_already_processed(self):
        hh = _make_headhunter()
        hh._processed_todos.add((100, 42))
        todos_response = [_make_todo(action_name="assigned", project_id=100, mr_iid=42)]
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_resp = MagicMock()
            mock_resp.json.return_value = todos_response
            mock_resp.raise_for_status = MagicMock()
            mock_client = AsyncMock()
            mock_client.get = AsyncMock(return_value=mock_resp)
            mock_client.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client.__aexit__ = AsyncMock(return_value=False)
            mock_client_cls.return_value = mock_client

            result = await hh.poll_cycle()
            assert len(result) == 0


# =========================================================================
# Dedup Priority Tests
# =========================================================================

class TestDedupPriority:
    def test_group_by_mr_collapses_same_mr(self):
        todos = [
            _make_todo(action_name="assigned", todo_id=1, mr_iid=42),
            _make_todo(action_name="build_failed", todo_id=2, mr_iid=42),
        ]
        grouped = Headhunter._group_by_mr(todos)
        assert len(grouped) == 1
        key = (100, 42)
        assert len(grouped[key]) == 2

    def test_build_failed_wins_over_assigned(self):
        todos = [
            _make_todo(action_name="assigned", todo_id=1),
            _make_todo(action_name="build_failed", todo_id=2),
        ]
        grouped = Headhunter._group_by_mr(todos)
        group = list(grouped.values())[0]
        best = min(group, key=lambda t: ACTION_PRIORITY.get(t["action_name"], 99))
        assert best["action_name"] == "build_failed"

    def test_action_priority_order(self):
        order = sorted(ACTION_PRIORITY.keys(), key=lambda k: ACTION_PRIORITY[k])
        assert order[0] == "build_failed"
        assert order[1] == "unmergeable"


# =========================================================================
# Flow Gate Tests
# =========================================================================

class TestFlowGate:
    @pytest.mark.asyncio
    async def test_allows_when_no_active_events(self):
        hh = _make_headhunter()
        assert await hh.check_flow_gate() is True

    @pytest.mark.asyncio
    async def test_blocks_when_max_active_reached(self):
        active_event = MagicMock()
        active_event.source = "headhunter"
        active_event.status.value = "active"
        active_event.id = "evt-1"
        bb = StubBlackboard(active_events=[{"id": "evt-1"}])
        bb.get_event = AsyncMock(return_value=active_event)
        bb.get_active_events = AsyncMock(return_value=["evt-1"])
        hh = _make_headhunter(blackboard=bb)
        assert await hh.check_flow_gate() is False


# =========================================================================
# Event Creation Tests
# =========================================================================

class TestEventCreation:
    @pytest.mark.asyncio
    async def test_creates_event_with_correct_structure(self):
        bb = StubBlackboard()
        hh = _make_headhunter(blackboard=bb)
        todo = _make_todo()
        plan = "---\nplan: test\nservice: general\ndomain: CLEAR\n---"

        event_id = await hh.create_headhunter_event(todo, plan, "clear")

        assert event_id.startswith("evt-test-")
        assert len(bb.events) == 1
        assert bb.events[0]["source"] == "headhunter"

    @pytest.mark.asyncio
    async def test_marks_todo_as_processed_after_creation(self):
        bb = StubBlackboard()
        hh = _make_headhunter(blackboard=bb)
        todo = _make_todo(project_id=200, mr_iid=55)

        await hh.create_headhunter_event(todo, "plan", "clear")

        assert (200, 55) in hh._processed_todos


# =========================================================================
# Service Resolution Tests
# =========================================================================

class TestServiceResolution:
    @pytest.mark.asyncio
    async def test_resolves_from_registry(self):
        bb = StubBlackboard()
        svc = MagicMock()
        svc.name = "my-service"
        svc.source_repo_url = "https://gitlab.example.com/group/repo.git"
        svc.gitops_repo_url = ""
        bb.get_services = AsyncMock(return_value={"my-service": svc})
        hh = _make_headhunter(blackboard=bb)

        result = await hh._resolve_service("group/repo")
        assert result == "my-service"

    @pytest.mark.asyncio
    async def test_falls_back_to_general(self):
        bb = StubBlackboard()
        bb.get_services = AsyncMock(return_value={})
        hh = _make_headhunter(blackboard=bb)

        result = await hh._resolve_service("unknown/repo")
        assert result == "general"


# =========================================================================
# LLM Fallback Tests
# =========================================================================

class TestAnalysisFallback:
    @pytest.mark.asyncio
    async def test_fallback_plan_when_no_adapter(self):
        hh = _make_headhunter()
        hh._llm_enabled = False
        context = {
            "action_name": "build_failed",
            "mr_title": "Fix CI",
            "project_path": "group/repo",
        }
        plan, domain = await hh.analyze_and_plan(context)
        assert "---" in plan
        assert domain == "complicated"

    def test_extract_domain_from_plan(self):
        plan = "---\nplan: test\ndomain: CLEAR\n---"
        assert Headhunter._extract_domain(plan) == "clear"

    def test_extract_domain_defaults_to_complicated(self):
        plan = "---\nplan: test\n---"
        assert Headhunter._extract_domain(plan) == "complicated"
