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
    async def test_aligner_headroom_gate_exception_fallback_to_local(self):
        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active", "evt-2": "deferred"})
        aligner = Aligner(bb)
        aligner._wip_cap = 10
        aligner.set_wip_counter(AsyncMock(side_effect=RuntimeError("Redis timeout")))

        headroom = await aligner._get_wip_headroom()
        assert headroom == 8

    @pytest.mark.asyncio
    async def test_aligner_headroom_gate_fails_to_default_when_all_fail(self):
        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(side_effect=RuntimeError("BlackBoard unavailable"))
        aligner = Aligner(bb)
        aligner._wip_cap = 10
        aligner.set_wip_counter(AsyncMock(side_effect=RuntimeError("Redis timeout")))

        headroom = await aligner._get_wip_headroom()
        assert headroom == 5

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
    async def test_jenkins_observer_headroom_exception_fallback(self):
        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active", "evt-2": "new"})
        jenkins = JenkinsObserver(bb)
        jenkins._wip_cap = 10
        jenkins.set_wip_counter(AsyncMock(side_effect=RuntimeError("Redis timeout")))

        headroom = await jenkins._get_wip_headroom()
        assert headroom == 8

    @pytest.mark.asyncio
    async def test_jenkins_observer_headroom_fails_to_default_when_all_fail(self):
        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(side_effect=RuntimeError("BlackBoard unavailable"))
        jenkins = JenkinsObserver(bb)
        jenkins._wip_cap = 10
        jenkins.set_wip_counter(AsyncMock(side_effect=RuntimeError("Redis timeout")))

        headroom = await jenkins._get_wip_headroom()
        assert headroom == 5

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


class TestHeadhunterFailClosed:
    """M9: Headhunter / HeadhunterJira must fail CLOSED (return False) when every WIP source fails.

    Contrast: Aligner / JenkinsObserver fail OPEN with headroom 5 (see the *_fails_to_default tests above).
    """

    @staticmethod
    def _bb_local_fails():
        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(side_effect=RuntimeError("BlackBoard unavailable"))
        return bb

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cls", [Headhunter, HeadhunterJira])
    async def test_gate_closed_when_injected_and_local_counters_both_fail(self, cls):
        obs = cls(self._bb_local_fails())
        obs._wip_cap = 10
        counter = AsyncMock(side_effect=RuntimeError("Redis timeout"))
        obs.set_wip_counter(counter)

        assert await obs.check_flow_gate() is False
        counter.assert_awaited_once_with(include_new=True)
        obs.blackboard.get_active_events_with_status.assert_awaited_once()  # fallback was attempted

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cls", [Headhunter, HeadhunterJira])
    async def test_gate_closed_when_no_counter_and_local_fails(self, cls):
        obs = cls(self._bb_local_fails())
        obs._wip_cap = 10
        obs._wip_counter = None

        assert await obs.check_flow_gate() is False

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cls", [Headhunter, HeadhunterJira])
    async def test_gate_opens_again_after_failure_clears(self, cls):
        """Fail-closed is per-call, not sticky."""
        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(
            side_effect=[RuntimeError("down"), {"evt-1": "active"}]
        )
        obs = cls(bb)
        obs._wip_cap = 10
        obs._wip_counter = None

        assert await obs.check_flow_gate() is False
        assert await obs.check_flow_gate() is True

    @pytest.mark.asyncio
    async def test_aligner_and_jenkins_fail_open_in_same_condition(self):
        """Pins the (intentional or not) asymmetry so a policy change is a visible test change."""
        for cls in (Aligner, JenkinsObserver):
            obs = cls(self._bb_local_fails())
            obs._wip_cap = 10
            obs.set_wip_counter(AsyncMock(side_effect=RuntimeError("Redis timeout")))
            assert await obs._get_wip_headroom() == 5


class TestObserversRequestIncludeNew:
    """M9: every observer gate must ask for count_global_wip(include_new=True); dropping it must fail a test."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cls", [Headhunter, HeadhunterJira])
    async def test_flow_gate_calls_counter_with_include_new_true(self, cls):
        obs = cls(MagicMock())
        obs._wip_cap = 20
        counter = AsyncMock(return_value=3)
        obs.set_wip_counter(counter)

        assert await obs.check_flow_gate() is True
        counter.assert_awaited_once_with(include_new=True)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("cls", [Aligner, JenkinsObserver])
    async def test_headroom_calls_counter_with_include_new_true(self, cls):
        obs = cls(MagicMock())
        obs._wip_cap = 20
        counter = AsyncMock(return_value=3)
        obs.set_wip_counter(counter)

        assert await obs._get_wip_headroom() == 17
        counter.assert_awaited_once_with(include_new=True)

    @pytest.mark.asyncio
    async def test_headhunter_propagates_counter_to_jira_sub_observer(self):
        hh = Headhunter(MagicMock())
        counter = AsyncMock(return_value=0)
        hh.set_wip_counter(counter)

        if getattr(hh, "_jira", None) is None:
            pytest.skip("Headhunter has no Jira sub-observer in this configuration")
        hh._jira._wip_cap = 5
        assert await hh._jira.check_flow_gate() is True
        counter.assert_awaited_once_with(include_new=True)

    @pytest.mark.asyncio
    async def test_brain_facade_observer_parity(self, brain_stub):
        """Observers fed Brain.count_global_wip see N+A+D-W: a NEW backlog closes the gate, a waiting event frees a slot."""
        brain_stub.blackboard.get_active_events_with_status = AsyncMock(
            return_value={"e1": "new", "e2": "new", "e3": "active", "e4": "deferred"}
        )
        hh = Headhunter(MagicMock())
        hh._wip_cap = 4
        hh.set_wip_counter(brain_stub.count_global_wip)
        assert await hh.check_flow_gate() is False  # 4 >= 4 (NEW counted)

        brain_stub._waiting_for_user = {"e3": 1.0}
        assert await hh.check_flow_gate() is True  # 3 < 4 (waiting event frees a slot)


class TestWipMetaAndInteractiveExclusion:
    """VMER-2505 T-1 & T-5: ActiveEventMeta projection, blank-source fail-safe, MagicMock fallback, and interactive exclusion."""

    def test_t5_is_automated_wip_event_rules_and_blank_source_failsafe(self):
        from src.state.wip_meta import ActiveEventMeta, is_automated_wip_event

        # Blank/unknown source MUST fail-safe count as automated WIP
        assert is_automated_wip_event(ActiveEventMeta(status="active", source="")) is True
        assert is_automated_wip_event(ActiveEventMeta(status="deferred", source="aligner")) is True
        assert is_automated_wip_event(ActiveEventMeta(status="new", source="headhunter"), include_new=False) is False
        assert is_automated_wip_event(ActiveEventMeta(status="new", source="headhunter"), include_new=True) is True

        # Interactive/excluded sources and waiting_user parks MUST be excluded
        for src in ("chat", "slack", "jarvis"):
            assert is_automated_wip_event(ActiveEventMeta(status="active", source=src), include_new=True) is False
        assert is_automated_wip_event(ActiveEventMeta(status="active", source="aligner", is_waiting_user=True)) is False

    @pytest.mark.asyncio
    async def test_t5_fetch_active_events_meta_uses_2rtt_metadata_dict_path(self):
        from src.state.wip_meta import ActiveEventMeta, fetch_active_events_meta

        expected = {
            "evt-a": ActiveEventMeta(status="active", source="aligner"),
            "evt-c": ActiveEventMeta(status="active", source="chat"),
        }
        bb = MagicMock()
        bb.get_active_events_metadata = AsyncMock(return_value=expected)
        bb.get_active_events_with_status = AsyncMock(side_effect=AssertionError("legacy fallback should not run"))

        meta = await fetch_active_events_meta(bb)
        assert meta == expected
        bb.get_active_events_metadata.assert_awaited_once()
        bb.get_active_events_with_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_t5_fetch_active_events_meta_magicmock_fallback(self):
        from src.state.wip_meta import ActiveEventMeta, fetch_active_events_meta, is_automated_wip_event

        bb = MagicMock()
        bb.get_active_events_with_status = AsyncMock(return_value={"evt-1": "active", "evt-2": "new"})

        meta = await fetch_active_events_meta(bb)
        assert set(meta.keys()) == {"evt-1", "evt-2"}
        assert meta["evt-1"] == ActiveEventMeta(status="active", source="")
        assert meta["evt-2"] == ActiveEventMeta(status="new", source="")
        assert is_automated_wip_event(meta["evt-1"]) is True
        bb.get_active_events_with_status.assert_awaited_once_with()

    @pytest.mark.asyncio
    async def test_t1_brain_and_all_four_observers_exclude_interactive_and_waiting_wip(self, brain_stub, monkeypatch):
        from src.state.wip_meta import ActiveEventMeta

        monkeypatch.setenv("MAX_ACTIVE_EVENTS", "2")
        meta = {
            "evt-chat": ActiveEventMeta(status="active", source="chat"),
            "evt-slack": ActiveEventMeta(status="active", source="slack"),
            "evt-jarvis": ActiveEventMeta(status="active", source="jarvis"),
            "evt-parked": ActiveEventMeta(status="active", source="aligner", is_waiting_user=True),
            "evt-inflight": ActiveEventMeta(status="active", source="headhunter", is_waiting_user=False),
        }
        bb = MagicMock()
        bb.get_active_events_metadata = AsyncMock(return_value=meta)
        brain_stub.blackboard = bb
        brain_stub._waiting_for_user = {"evt-inflight": 1000.0}

        assert await brain_stub.count_global_wip(include_new=False) == 0
        assert await brain_stub.count_global_wip(include_new=True) == 0

        # Observers share same metadata exclusion (excluding evt-inflight only via Redis metadata;
        # use purely Redis-parked + interactive metadata for observer tests)
        obs_meta = {k: v for k, v in meta.items() if k != "evt-inflight"}
        obs_bb = MagicMock()
        obs_bb.get_active_events_metadata = AsyncMock(return_value=obs_meta)

        aligner = Aligner(obs_bb)
        aligner._wip_cap = 2
        aligner._wip_counter = None
        assert await aligner._local_count_wip() == 0
        assert await aligner._get_wip_headroom() == 2

        jenkins = JenkinsObserver(obs_bb)
        jenkins._wip_cap = 2
        jenkins._wip_counter = None
        assert await jenkins._local_count_wip() == 0
        assert await jenkins._get_wip_headroom() == 2

        hh = Headhunter(obs_bb)
        hh._wip_cap = 2
        hh._wip_counter = None
        assert await hh._local_count_wip() == 0
        assert await hh.check_flow_gate() is True

        hh_jira = HeadhunterJira(obs_bb)
        hh_jira._wip_cap = 2
        hh_jira._wip_counter = None
        assert await hh_jira._local_count_wip() == 0
        assert await hh_jira.check_flow_gate() is True
