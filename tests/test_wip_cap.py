# BlackBoard/tests/test_wip_cap.py
# @ai-rules:
# 1. [Constraint]: Tests the global WIP cap gate (brain._count_global_wip, admission, bypass, workers).
# 2. [Pattern]: Uses minimal Brain stub — only blackboard + _waiting_for_user needed.
# 3. [Gotcha]: Brain.__init__ has many deps — patch at method level, not full instantiation.
"""Unit tests for the unified global WIP cap."""
import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def brain_stub():
    """Minimal Brain-like object with only the methods needed for WIP cap testing."""
    from src.agents.brain import Brain

    with patch.object(Brain, "__init__", lambda self, *a, **kw: None):
        brain = Brain.__new__(Brain)
        brain.blackboard = MagicMock()
        brain._waiting_for_user = {}
        return brain


class TestCountGlobalWip:
    @pytest.mark.asyncio
    async def test_empty_system(self, brain_stub):
        brain_stub.blackboard.get_active_events_with_status = AsyncMock(return_value={})
        count = await brain_stub._count_global_wip()
        assert count == 0

    @pytest.mark.asyncio
    async def test_counts_active_and_deferred(self, brain_stub):
        brain_stub.blackboard.get_active_events_with_status = AsyncMock(return_value={
            "evt-1": "active",
            "evt-2": "deferred",
            "evt-3": "new",
        })
        count = await brain_stub._count_global_wip()
        assert count == 2

    @pytest.mark.asyncio
    async def test_excludes_new_events(self, brain_stub):
        brain_stub.blackboard.get_active_events_with_status = AsyncMock(return_value={
            "evt-1": "new",
            "evt-2": "new",
        })
        count = await brain_stub._count_global_wip()
        assert count == 0

    @pytest.mark.asyncio
    async def test_excludes_waiting_for_user(self, brain_stub):
        brain_stub.blackboard.get_active_events_with_status = AsyncMock(return_value={
            "evt-1": "active",
            "evt-2": "active",
            "evt-3": "deferred",
        })
        brain_stub._waiting_for_user = {"evt-1": 1000.0, "evt-3": 1001.0}
        count = await brain_stub._count_global_wip()
        assert count == 1


class TestBypassSources:
    def test_chat_is_bypass(self):
        from src.agents.brain import Brain
        assert "chat" in Brain._BYPASS_SOURCES

    def test_slack_is_bypass(self):
        from src.agents.brain import Brain
        assert "slack" in Brain._BYPASS_SOURCES

    def test_jarvis_is_bypass(self):
        from src.agents.brain import Brain
        assert "jarvis" in Brain._BYPASS_SOURCES

    def test_aligner_is_not_bypass(self):
        from src.agents.brain import Brain
        assert "aligner" not in Brain._BYPASS_SOURCES

    def test_headhunter_is_not_bypass(self):
        from src.agents.brain import Brain
        assert "headhunter" not in Brain._BYPASS_SOURCES


class TestWorkerSentinel:
    def test_auto_mode_uses_max_active_events(self, monkeypatch):
        from src.agents.brain import Brain

        monkeypatch.setenv("BRAIN_RECONCILE_WORKERS", "0")
        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "20")
        with patch.object(Brain, "__init__", lambda self, *a, **kw: None):
            brain = Brain.__new__(Brain)
            workers = brain._derive_workers()
        assert workers == 20

    def test_explicit_override(self, monkeypatch):
        from src.agents.brain import Brain

        monkeypatch.setenv("BRAIN_RECONCILE_WORKERS", "13")
        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "20")
        with patch.object(Brain, "__init__", lambda self, *a, **kw: None):
            brain = Brain.__new__(Brain)
            workers = brain._derive_workers()
        assert workers == 13

    def test_auto_mode_always_positive(self, monkeypatch):
        from src.agents.brain import Brain

        monkeypatch.setenv("BRAIN_RECONCILE_WORKERS", "0")
        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "5")
        with patch.object(Brain, "__init__", lambda self, *a, **kw: None):
            brain = Brain.__new__(Brain)
            workers = brain._derive_workers()
        assert workers > 0

    def test_floor_prevents_zero_workers(self, monkeypatch):
        """MAX_ACTIVE_EVENTS=0 must still produce at least 1 worker."""
        from src.agents.brain import Brain

        monkeypatch.setenv("BRAIN_RECONCILE_WORKERS", "0")
        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "0")
        with patch.object(Brain, "__init__", lambda self, *a, **kw: None):
            brain = Brain.__new__(Brain)
            workers = brain._derive_workers()
        assert workers == 1


class TestHeadhunterFlowGate:
    @pytest.mark.asyncio
    async def test_allows_below_cap(self, monkeypatch):
        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "5")
        from src.agents.headhunter import Headhunter

        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(return_value={
            "evt-1": "active",
            "evt-2": "deferred",
        })
        with patch.dict(os.environ, {"GITLAB_HOST": "gitlab.example.com", "MAX_ACTIVE_EVENTS": "5"}):
            hh = Headhunter(bb)
        assert await hh.check_flow_gate() is True

    @pytest.mark.asyncio
    async def test_blocks_at_cap(self, monkeypatch):
        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "2")
        from src.agents.headhunter import Headhunter

        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(return_value={
            "evt-1": "active",
            "evt-2": "new",
        })
        with patch.dict(os.environ, {"GITLAB_HOST": "gitlab.example.com", "MAX_ACTIVE_EVENTS": "2"}):
            hh = Headhunter(bb)
        assert await hh.check_flow_gate() is False

    @pytest.mark.asyncio
    async def test_counts_new_events_conservatively(self, monkeypatch):
        """HH counts NEW events too (prevents single-cycle flooding)."""
        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "3")
        from src.agents.headhunter import Headhunter

        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(return_value={
            "evt-1": "new",
            "evt-2": "new",
            "evt-3": "active",
        })
        with patch.dict(os.environ, {"GITLAB_HOST": "gitlab.example.com", "MAX_ACTIVE_EVENTS": "3"}):
            hh = Headhunter(bb)
        assert await hh.check_flow_gate() is False


class TestBrainAdmissionGate:
    """Integration tests for the Brain.process_event admission path."""

    @pytest.fixture
    def brain_with_gate(self):
        from src.agents.brain import Brain
        with patch.object(Brain, "__init__", lambda self, *a, **kw: None):
            brain = Brain.__new__(Brain)
            brain.blackboard = MagicMock()
            brain._waiting_for_user = {}
            brain._waiting_for_jarvis = set()
            brain._broadcast = AsyncMock()
            return brain

    @pytest.mark.asyncio
    async def test_automated_source_rejected_at_cap(self, brain_with_gate, monkeypatch):
        """Automated sources stay NEW when global cap is reached."""
        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "2")
        brain_with_gate.blackboard.get_active_events_with_status = AsyncMock(return_value={
            "evt-1": "active",
            "evt-2": "deferred",
        })
        brain_with_gate.blackboard.transition_event_status = AsyncMock(return_value=True)

        event = MagicMock()
        event.status.value = "new"
        event.source = "aligner"
        from src.models import EventStatus
        event.status = EventStatus.NEW

        wip = await brain_with_gate._count_global_wip()
        cap = int(os.getenv("MAX_ACTIVE_EVENTS", "20"))
        assert wip >= cap
        # Gate would reject — automated source stays NEW

    @pytest.mark.asyncio
    async def test_bypass_source_admitted_at_cap(self, brain_with_gate, monkeypatch):
        """Chat/slack/jarvis bypass the cap regardless of WIP count."""
        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "2")
        brain_with_gate.blackboard.get_active_events_with_status = AsyncMock(return_value={
            "evt-1": "active",
            "evt-2": "deferred",
            "evt-3": "active",
        })
        from src.agents.brain import Brain
        assert "chat" in Brain._BYPASS_SOURCES
        assert "slack" in Brain._BYPASS_SOURCES
        assert "jarvis" in Brain._BYPASS_SOURCES

    @pytest.mark.asyncio
    async def test_automated_source_admitted_below_cap(self, brain_with_gate, monkeypatch):
        """Automated sources transition NEW→ACTIVE when below cap."""
        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "20")
        brain_with_gate.blackboard.get_active_events_with_status = AsyncMock(return_value={
            "evt-1": "active",
        })

        wip = await brain_with_gate._count_global_wip()
        cap = int(os.getenv("MAX_ACTIVE_EVENTS", "20"))
        assert wip < cap
        # Gate would admit — automated source transitions to ACTIVE
