"""Unit and integration tests for User-Facing Squad OnCall Dispatcher and AgentRegistry multi-agent coexistence.

Covers Dave Farley ATDD Layer 4 tests T-1, T-2, T-3, T-4, T-5, T-6 from .plan.md.
"""

from unittest.mock import AsyncMock, patch
import pytest

from src.agents.agent_registry import AgentRegistry
from src.agents.ephemeral_provisioner import EphemeralProvisioner


@pytest.fixture
def registry():
    return AgentRegistry()


@pytest.mark.asyncio
async def test_t1_squad_coexistence(registry: AgentRegistry):
    """T-1: Given 4 squad sidecars connecting for evt-100 When all register with distinct roles

    Then all 4 coexist in registry without evictions.
    """
    roles = ["architect", "developer", "sysadmin", "qe"]

    for role in roles:
        ws = AsyncMock()
        agent_id = f"{role}-pod-abc"
        await registry.register(
            agent_id=agent_id,
            role=role,
            ws=ws,
            capabilities=["run_command"],
            cli="claude",
            model="claude-sonnet-5-5",
            ephemeral=True,
            event_id="evt-100",
        )

    ephemerals = await registry.get_ephemerals("evt-100")
    assert len(ephemerals) == 4
    registered_roles = {c.role for c in ephemerals}
    assert registered_roles == {"architect", "developer", "sysadmin", "qe"}


@pytest.mark.asyncio
async def test_t2_same_role_reconnect_eviction(registry: AgentRegistry):
    """T-2: Given an existing squad agent architect for evt-100 When a new architect registers for evt-100

    Then stale architect is evicted and replaced.
    """
    ws1 = AsyncMock()
    await registry.register(
        agent_id="architect-pod-1",
        role="architect",
        ws=ws1,
        capabilities=["run_command"],
        cli="claude",
        model="claude-sonnet-5-5",
        ephemeral=True,
        event_id="evt-100",
    )

    ws2 = AsyncMock()
    await registry.register(
        agent_id="architect-pod-2",
        role="architect",
        ws=ws2,
        capabilities=["run_command"],
        cli="claude",
        model="claude-sonnet-5-5",
        ephemeral=True,
        event_id="evt-100",
    )

    ephemerals = await registry.get_ephemerals("evt-100")
    assert len(ephemerals) == 1
    assert ephemerals[0].agent_id == "architect-pod-2"
    ws1.close.assert_awaited()


@pytest.mark.asyncio
async def test_t3_multi_agent_fan_out_termination(registry: AgentRegistry):
    """T-3: Given an active squad on evt-100 When terminate_agent("evt-100") is called

    Then all 4 sidecars receive termination message and cancel fallback is triggered.
    """
    roles = ["architect", "developer", "sysadmin", "qe"]
    ws_mocks = {}

    for role in roles:
        ws = AsyncMock()
        ws_mocks[role] = ws
        await registry.register(
            agent_id=f"{role}-pod-1",
            role=role,
            ws=ws,
            capabilities=["run_command"],
            cli="claude",
            model="claude-sonnet-5-5",
            ephemeral=True,
            event_id="evt-100",
        )

    provisioner = EphemeralProvisioner(
        registry=registry,
        event_listener_url="http://mock-tekton:8080",
    )

    with patch.object(provisioner, "_cancel_taskrun", new_callable=AsyncMock) as mock_cancel:
        await provisioner.terminate_agent("evt-100")

        # Verify all 4 received WS terminate message
        for role, ws in ws_mocks.items():
            ws.send_json.assert_awaited_with({"type": "terminate", "event_id": "evt-100"})

        # Verify authoritative cancel fallback called
        mock_cancel.assert_awaited_once_with("evt-100")


@pytest.mark.asyncio
async def test_t4_t5_brain_tier_selection():
    """T-4 & T-5: User-facing events dispatch roster='squad'; sensor events dispatch roster='single'."""
    from src.agents.brain import _select_dispatch_tier

    # T-4: chat / slack / dashboard -> squad for core roles
    assert _select_dispatch_tier(source="chat", role="developer") == "squad"
    assert _select_dispatch_tier(source="slack", role="architect") == "squad"
    assert _select_dispatch_tier(source="workspace", role="sysadmin") == "squad"

    # T-5: sensor events -> single
    assert _select_dispatch_tier(source="aligner", role="developer") == "single"
    assert _select_dispatch_tier(source="headhunter", role="architect") == "single"
    assert _select_dispatch_tier(source="timekeeper", role="") == "single"


@pytest.mark.asyncio
async def test_t6_specialized_reviewer_coexistence(registry: AgentRegistry):
    """T-6: Given an active user event with squad When FRIDAY dispatches code_reviewer

    Then a dedicated single agent registers and coexists with squad on same bound_event_id.
    """
    # Register 4 squad sidecars
    for role in ["architect", "developer", "sysadmin", "qe"]:
        await registry.register(
            agent_id=f"{role}-pod-1",
            role=role,
            ws=AsyncMock(),
            capabilities=["run_command"],
            cli="claude",
            model="claude-sonnet-5-5",
            ephemeral=True,
            event_id="evt-100",
        )

    # Register specialized reviewer
    await registry.register(
        agent_id="code-reviewer-pod-1",
        role="code_reviewer",
        ws=AsyncMock(),
        capabilities=["run_command"],
        cli="claude",
        model="claude-sonnet-5-5",
        ephemeral=True,
        event_id="evt-100",
    )

    ephemerals = await registry.get_ephemerals("evt-100")
    assert len(ephemerals) == 5

    # Check role-filtered lookup
    reviewer = await registry.get_ephemeral("evt-100", role="code_reviewer")
    assert reviewer is not None
    assert reviewer.role == "code_reviewer"

    developer = await registry.get_ephemeral("evt-100", role="developer")
    assert developer is not None
    assert developer.role == "developer"


@pytest.mark.asyncio
async def test_shapeshifter_matching_and_precedence(registry: AgentRegistry):
    """Idle shapeshifter agent (role='') matches any requested role, but exact role match takes precedence."""
    # Register an idle shapeshifter (sensor oncall agent)
    await registry.register(
        agent_id="oncall-pod-1",
        role="",
        ws=AsyncMock(),
        capabilities=["run_command"],
        cli="claude",
        model="claude-sonnet-5-5",
        ephemeral=True,
        event_id="evt-200",
    )

    # Looking up any role should return the idle shapeshifter
    found = await registry.get_ephemeral("evt-200", role="developer")
    assert found is not None
    assert found.agent_id == "oncall-pod-1"

    # Now register an explicit developer agent
    await registry.register(
        agent_id="developer-pod-1",
        role="developer",
        ws=AsyncMock(),
        capabilities=["run_command"],
        cli="claude",
        model="claude-sonnet-5-5",
        ephemeral=True,
        event_id="evt-200",
    )

    # Exact match takes precedence
    exact = await registry.get_ephemeral("evt-200", role="developer")
    assert exact is not None
    assert exact.agent_id == "developer-pod-1"

    # Other roles still match the shapeshifter
    sysadmin = await registry.get_ephemeral("evt-200", role="sysadmin")
    assert sysadmin is not None
    assert sysadmin.agent_id == "oncall-pod-1"


@pytest.mark.asyncio
async def test_stale_eviction_busy_guard(registry: AgentRegistry):
    """Busy squad agent must NOT be evicted by a duplicate registration."""
    ws1 = AsyncMock()
    await registry.register(
        agent_id="developer-pod-1",
        role="developer",
        ws=ws1,
        capabilities=["run_command"],
        cli="claude",
        model="claude-sonnet-5-5",
        ephemeral=True,
        event_id="evt-300",
    )
    await registry.mark_busy("developer-pod-1", "evt-300", "task-1")

    # A reconnecting or racing agent with the same role
    ws2 = AsyncMock()
    await registry.register(
        agent_id="developer-pod-2",
        role="developer",
        ws=ws2,
        capabilities=["run_command"],
        cli="claude",
        model="claude-sonnet-5-5",
        ephemeral=True,
        event_id="evt-300",
    )

    # developer-pod-1 was busy so its websocket was NOT closed
    ws1.close.assert_not_awaited()
    ephemerals = await registry.get_ephemerals("evt-300")
    assert len(ephemerals) == 2


@pytest.mark.asyncio
async def test_shapeshifter_reregistration_dedups_by_event(registry: AgentRegistry):
    """Single-agent (role="") pods still dedup per event_id: a stale idle one is evicted."""
    ws1 = AsyncMock()
    await registry.register(
        agent_id="oncall-pod-1", role="", ws=ws1, capabilities=[], cli="claude",
        model="claude-sonnet-5-5", ephemeral=True, event_id="evt-400",
    )
    ws2 = AsyncMock()
    await registry.register(
        agent_id="oncall-pod-2", role="", ws=ws2, capabilities=[], cli="claude",
        model="claude-sonnet-5-5", ephemeral=True, event_id="evt-400",
    )
    ws1.close.assert_awaited_once()
    ephemerals = await registry.get_ephemerals("evt-400")
    assert [c.agent_id for c in ephemerals] == ["oncall-pod-2"]


@pytest.mark.asyncio
async def test_squad_spawn_inflight_guard_no_duplicate_post(registry: AgentRegistry):
    """Concurrent squad ensure_agent() calls for one event POST exactly one spawn."""
    import asyncio

    provisioner = EphemeralProvisioner(
        registry=registry, event_listener_url="http://el", deadline_sec=5, poll_interval_sec=0.05,
    )
    posts: list[dict] = []

    async def fake_post(event_id, installation_id="", model="", cli="", roster="", role=""):
        posts.append({"event_id": event_id, "roster": roster, "role": role})

    async def register_squad():
        await asyncio.sleep(0.2)
        for role in ("developer", "qe"):
            await registry.register(
                agent_id=f"{role}-pod", role=role, ws=AsyncMock(), capabilities=[],
                cli="claude", model="m", ephemeral=True, event_id="evt-500",
            )
            provisioner.on_ephemeral_registered("evt-500", role)

    with patch.object(provisioner, "_trigger_taskrun", side_effect=fake_post):
        dev, qe, _ = await asyncio.gather(
            provisioner.ensure_agent("evt-500", role="developer", roster="squad"),
            provisioner.ensure_agent("evt-500", role="qe", roster="squad"),
            register_squad(),
        )
    assert len(posts) == 1
    assert dev.role == "developer" and qe.role == "qe"


@pytest.mark.asyncio
async def test_terminate_agent_cancels_taskrun_only_when_spawned(registry: AgentRegistry):
    """terminate_agent() skips the prune TaskRun for events that never spawned anything."""
    provisioner = EphemeralProvisioner(registry=registry, event_listener_url="http://el")
    with patch.object(provisioner, "_cancel_taskrun", new_callable=AsyncMock) as cancel:
        await provisioner.terminate_agent("evt-600")
        cancel.assert_not_awaited()

        await registry.register(
            agent_id="developer-pod", role="developer", ws=AsyncMock(), capabilities=[],
            cli="claude", model="m", ephemeral=True, event_id="evt-601",
        )
        await provisioner.terminate_agent("evt-601")
        cancel.assert_awaited_once_with("evt-601")
