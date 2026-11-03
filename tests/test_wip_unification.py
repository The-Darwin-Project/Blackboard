# BlackBoard/tests/test_wip_unification.py
# @ai-rules:
# 1. [Constraint]: Unit & integration tests for unified WIP calculation and observer flow gates.
# 2. [Pattern]: Validates T-7 across Brain, Headhunter, Aligner, and JenkinsObserver without external Redis.
"""Unit tests for unified WIP counting and observer flow gate contracts."""
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from src.agents.brain import Brain
from src.agents.headhunter import Headhunter
from src.agents.headhunter_jira import HeadhunterJira
from src.agents.aligner import Aligner
from src.agents.jenkins_observer import JenkinsObserver


@pytest.fixture
def brain_stub():
    with patch.object(Brain, "__init__", lambda self, *a, **kw: None):
        brain = Brain.__new__(Brain)
        brain.blackboard = MagicMock()
        brain._waiting_for_user = {}
        return brain


class TestBrainWipCountShapes:
    @pytest.mark.asyncio
    async def test_include_new_false_excludes_new(self, brain_stub):
        brain_stub.blackboard.get_active_events_with_status = AsyncMock(
            return_value={"evt-1": "new", "evt-2": "active", "evt-3": "deferred"}
        )
        count = await brain_stub._count_global_wip(include_new=False)
        assert count == 2

    @pytest.mark.asyncio
    async def test_include_new_true_includes_new(self, brain_stub):
        brain_stub.blackboard.get_active_events_with_status = AsyncMock(
            return_value={"evt-1": "new", "evt-2": "active", "evt-3": "deferred"}
        )
        count = await brain_stub._count_global_wip(include_new=True)
        assert count == 3

    @pytest.mark.asyncio
    async def test_waiting_for_user_subtracted_under_both_modes(self, brain_stub):
        brain_stub.blackboard.get_active_events_with_status = AsyncMock(
            return_value={"evt-1": "new", "evt-2": "active", "evt-3": "deferred"}
        )
        brain_stub._waiting_for_user = {"evt-2": 1000.0}

        count_no_new = await brain_stub._count_global_wip(include_new=False)
        assert count_no_new == 1  # evt-3 only

        count_with_new = await brain_stub._count_global_wip(include_new=True)
        assert count_with_new == 2  # evt-1 and evt-3


class TestObserverWipGates:
    @pytest.mark.asyncio
    async def test_aligner_headroom_gate_with_injected_counter(self):
        bb = MagicMock()
        aligner = Aligner(bb)
        aligner._wip_cap = 20

        # Inject counter returning 15
        aligner.set_wip_counter(AsyncMock(return_value=15))
        headroom = await aligner._get_wip_headroom()
        assert headroom == 5

        # At or above cap
        aligner.set_wip_counter(AsyncMock(return_value=22))
        headroom_full = await aligner._get_wip_headroom()
        assert headroom_full == 0

    @pytest.mark.asyncio
    async def test_aligner_headroom_gate_local_fallback(self):
        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active", "evt-2": "new"})
        aligner = Aligner(bb)
        aligner._wip_cap = 10
        # No counter injected -> fallback to _local_count_wip
        aligner._wip_counter = None

        headroom = await aligner._get_wip_headroom()
        assert headroom == 8

    @pytest.mark.asyncio
    async def test_headhunter_boolean_gate_with_injected_counter(self):
        bb = MagicMock()
        hh = Headhunter(bb)
        hh._wip_cap = 20

        # Below cap
        hh.set_wip_counter(AsyncMock(return_value=12))
        assert await hh.check_flow_gate() is True

        # At cap
        hh.set_wip_counter(AsyncMock(return_value=20))
        assert await hh.check_flow_gate() is False

    @pytest.mark.asyncio
    async def test_jenkins_observer_headroom_gate_with_injected_counter(self):
        bb = MagicMock()
        jenkins = JenkinsObserver(bb)
        jenkins._wip_cap = 20

        jenkins.set_wip_counter(AsyncMock(return_value=18))
        headroom = await jenkins._get_wip_headroom()
        assert headroom == 2

    @pytest.mark.asyncio
    async def test_headhunter_jira_flow_gate_with_injected_counter(self):
        bb = MagicMock()
        hh_jira = HeadhunterJira(bb)
        hh_jira._wip_cap = 20

        # Below cap
        hh_jira.set_wip_counter(AsyncMock(return_value=14))
        assert await hh_jira.check_flow_gate() is True

        # At cap
        hh_jira.set_wip_counter(AsyncMock(return_value=20))
        assert await hh_jira.check_flow_gate() is False

    @pytest.mark.asyncio
    async def test_headhunter_flow_gate_exception_fallback(self):
        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active", "evt-2": "new"})
        hh = Headhunter(bb)
        hh._wip_cap = 10

        # Injected counter fails with transient exception -> should fallback to local count (2 < 10 -> True)
        failing_counter = AsyncMock(side_effect=RuntimeError("Redis connection timeout"))
        hh.set_wip_counter(failing_counter)

        gate_open = await hh.check_flow_gate()
        assert gate_open is True

    @pytest.mark.asyncio
    async def test_headhunter_jira_flow_gate_exception_fallback(self):
        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active", "evt-2": "new"})
        hh_jira = HeadhunterJira(bb)
        hh_jira._wip_cap = 10

        # Injected counter fails -> falls back to local count (2 < 10 -> True)
        failing_counter = AsyncMock(side_effect=RuntimeError("Redis connection timeout"))
        hh_jira.set_wip_counter(failing_counter)

        gate_open = await hh_jira.check_flow_gate()
        assert gate_open is True
