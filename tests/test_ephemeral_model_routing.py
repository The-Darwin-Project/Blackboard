# tests/test_ephemeral_model_routing.py
# @ai-rules:
# 1. [Constraint]: No Redis, no Tekton -- MagicMock blackboard + patched dispatch_to_agent.
# 2. [Pattern]: Follows test_task_lifecycle_ordering.py structure: Brain(blackboard=mock, agents={}).
# 3. [Pattern]: Gate under test is `agent_id_override is not None` at the dispatch_to_agent call
#    site in _run_agent_task -- NOT is_ephemeral_dispatch (see brain.py L45 ai-rule).
"""Verify ephemeral-only model/effort routing gate in Brain._run_agent_task.

Covers the Run #2 pre-flight regression guard: the model/effort override must be
keyed off `agent_id_override is not None` (ground truth), not the early-computed
`is_ephemeral_dispatch` flag (which diverges on circuit-breaker fallback and MMC
overflow).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.brain import Brain
from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
from src.models import EventDocument, EventEvidence, EventInput


def _make_headhunter_event(event_id: str = "evt-hh0001") -> EventDocument:
    evidence = EventEvidence(
        display_text="Auto-generated MR", source_type="headhunter", severity="info",
    )
    return EventDocument(
        id=event_id, source="headhunter", service="test-svc", brain_phase="dispatch",
        event=EventInput(reason="mr review", evidence=evidence),
        conversation=[],
    )


def _make_brain() -> Brain:
    bb = MagicMock()
    bb.get_event = AsyncMock(return_value=_make_headhunter_event())
    bb.append_turn = AsyncMock(return_value=1)
    bb.mark_turn_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.get_active_events = AsyncMock(return_value=[])
    bb.get_recent_closed_for_service = AsyncMock(return_value=[])
    bb.generate_mermaid = AsyncMock(return_value="")
    brain = Brain(blackboard=bb, agents={})
    brain._broadcast = AsyncMock()
    brain._broadcast_turn = AsyncMock()
    brain._broadcast_status_update = AsyncMock()
    brain._append_and_broadcast = AsyncMock(return_value=1)
    brain._emit_executive_pulse = AsyncMock()
    brain.write_event_to_volume = AsyncMock()
    brain._dispatch_semaphore = None
    brain._ws_mode = "reverse"
    return brain


@pytest.fixture
def registry_and_bridge():
    registry = MagicMock()
    bridge = MagicMock()
    with patch(
        "src.dependencies.get_registry_and_bridge",
        return_value=(registry, bridge),
    ):
        yield registry, bridge


class TestEphemeralHappyPath:
    """agent_id_override is not None -> role model/effort resolved for dispatch_to_agent."""

    @pytest.mark.asyncio
    async def test_architect_gets_opus_and_role_default_effort(self, registry_and_bridge):
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-architect-1"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Plan ready.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-hh0001", agent_name="architect", agent=None,
                task="Plan the fix", event_md_path="/tmp/x.md",
                routing_turn_num=1, mode="plan", effort="",
            )

        assert mock_dispatch.call_args.kwargs["model"] == "claude-opus-4-6[1m]"
        assert mock_dispatch.call_args.kwargs["effort"] == "high"
        assert mock_dispatch.call_args.kwargs["agent_id"] == "agent-architect-1"

        ensure_kwargs = brain._ephemeral_provisioner.ensure_agent.call_args.kwargs
        assert ensure_kwargs["model"] == "claude-opus-4-6[1m]"

    @pytest.mark.asyncio
    async def test_effort_override_beats_role_default(self, registry_and_bridge):
        """FRIDAY's explicit effort param overrides the role default (architect default=high)."""
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-architect-2"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Plan ready.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-hh0001", agent_name="architect", agent=None,
                task="Plan the fix", event_md_path="/tmp/x.md",
                routing_turn_num=1, mode="plan", effort="max",
            )

        assert mock_dispatch.call_args.kwargs["effort"] == "max"

    @pytest.mark.asyncio
    async def test_sysadmin_gets_sonnet(self, registry_and_bridge):
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-sysadmin-1"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Done.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-hh0001", agent_name="sysadmin", agent=None,
                task="Scale the deployment", event_md_path="/tmp/x.md",
                routing_turn_num=1, mode="execute", effort="",
            )

        assert mock_dispatch.call_args.kwargs["model"] == "claude-sonnet-5"
        assert mock_dispatch.call_args.kwargs["effort"] == "medium"


class TestCircuitBreakerFallbackGate:
    """agent_id_override stays None on circuit-breaker fallback -> model="" (Run #2 regression guard)."""

    @pytest.mark.asyncio
    async def test_provision_none_falls_back_to_local_with_empty_model(self, registry_and_bridge):
        """ensure_agent returns None (circuit breaker) for a non-EPHEMERAL_ONLY role on a
        Tier-1 source -> falls through to dispatch_to_agent with agent_id=None, model="".
        is_ephemeral_dispatch is True here (computed early), but the gate must key off
        agent_id_override, not that flag -- this is the exact regression Run #2 caught.
        """
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(return_value=None)
        brain._ephemeral_provisioner.record_dispatch_sidecar_fallback = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Done locally.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-hh0001", agent_name="sysadmin", agent=None,
                task="Scale the deployment", event_md_path="/tmp/x.md",
                routing_turn_num=1, mode="execute", effort="",
            )

        assert mock_dispatch.call_args.kwargs["agent_id"] is None
        assert mock_dispatch.call_args.kwargs["model"] == ""
        assert mock_dispatch.call_args.kwargs["effort"] == ""
        brain._ephemeral_provisioner.record_dispatch_sidecar_fallback.assert_called_once()

    @pytest.mark.asyncio
    async def test_provision_none_fallback_passes_raw_effort_through(self, registry_and_bridge):
        """Local-dispatch fallback still forwards FRIDAY's raw effort (no role-default injection)."""
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(return_value=None)
        brain._ephemeral_provisioner.record_dispatch_sidecar_fallback = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Done locally.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-hh0001", agent_name="sysadmin", agent=None,
                task="Scale the deployment", event_md_path="/tmp/x.md",
                routing_turn_num=1, mode="execute", effort="low",
            )

        assert mock_dispatch.call_args.kwargs["model"] == ""
        assert mock_dispatch.call_args.kwargs["effort"] == "low"


class TestCodeReviewerRouting:
    """code_reviewer (code-reviewer-agent plan) is EPHEMERAL_ONLY_ROLES like security_analyst --
    no persistent sidecar exists. T-1 mirrors TestEphemeralHappyPath's happy-path pattern; T-2
    mirrors the Tier-0 circuit-breaker defer path (distinct from TestCircuitBreakerFallbackGate's
    sysadmin case, which DOES have a local sidecar to fall back to); T-3 is a schema smoke test.
    """

    @pytest.mark.asyncio
    async def test_code_reviewer_gets_sonnet_and_high_effort(self, registry_and_bridge):
        """T-1: agent_id_override is not None -> code_reviewer resolves via _ROLE_MODEL_MAP/
        _ROLE_EFFORT_MAP to claude-sonnet-5/high (EPHEMERAL_MODEL_CODE_REVIEWER/
        EPHEMERAL_EFFORT_CODE_REVIEWER env defaults, per plan Step 2/18)."""
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-code_reviewer-1"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Findings ready.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-hh0001", agent_name="code_reviewer", agent=None,
                task="Review the recent changes", event_md_path="/tmp/x.md",
                routing_turn_num=1, mode="review", effort="",
            )

        assert mock_dispatch.call_args.kwargs["model"] == "claude-sonnet-5"
        assert mock_dispatch.call_args.kwargs["effort"] == "high"
        assert mock_dispatch.call_args.kwargs["agent_id"] == "agent-code_reviewer-1"

    @pytest.mark.asyncio
    async def test_code_reviewer_provisioner_disabled_defers_safely(self, registry_and_bridge):
        """T-2: code_reviewer has NO local sidecar to fall back to (EPHEMERAL_ONLY_ROLES member).
        ensure_agent returning None must fire the Tier-0 circuit-breaker defer guard --
        record_dispatch_circuit_break() + execute_tool_locked(event_id, "defer_event", ...) --
        NOT the sysadmin-style record_dispatch_sidecar_fallback + local dispatch_to_agent path
        (that path only exists for roles WITH a persistent sidecar). dispatch_to_agent must
        never be called; there is no sidecar for code_reviewer to dispatch to.
        """
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(return_value=None)
        brain._ephemeral_provisioner.record_dispatch_circuit_break = MagicMock()
        brain._ephemeral_provisioner.record_dispatch_sidecar_fallback = MagicMock()
        brain.execute_tool_locked = AsyncMock(return_value=True)

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Findings ready.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-hh0001", agent_name="code_reviewer", agent=None,
                task="Review the recent changes", event_md_path="/tmp/x.md",
                routing_turn_num=1, mode="review", effort="",
            )

        mock_dispatch.assert_not_called()
        brain._ephemeral_provisioner.record_dispatch_circuit_break.assert_called_once()
        brain._ephemeral_provisioner.record_dispatch_sidecar_fallback.assert_not_called()
        brain.execute_tool_locked.assert_called_once()
        defer_args = brain.execute_tool_locked.call_args.args
        assert defer_args[0] == "evt-hh0001"
        assert defer_args[1] == "defer_event"

    def test_code_reviewer_present_in_tool_schema_enums(self):
        """T-3: types.py parses with code_reviewer present in all 3 agent-name enum sites
        (select_agent, ask_agent_for_state, create_plan step agent)."""
        schemas_by_name = {tool["name"]: tool for tool in BRAIN_TOOL_SCHEMAS}

        select_agent_enum = schemas_by_name["select_agent"]["input_schema"]["properties"]["agent_name"]["enum"]
        assert "code_reviewer" in select_agent_enum

        ask_agent_enum = schemas_by_name["ask_agent_for_state"]["input_schema"]["properties"]["agent_name"]["enum"]
        assert "code_reviewer" in ask_agent_enum

        create_plan_agent_schema = schemas_by_name["create_plan"]["input_schema"]["properties"]["steps"]["items"][
            "properties"
        ]["agent"]
        assert "code_reviewer" in create_plan_agent_schema["enum"]


class TestDeferEventSafely:
    """_defer_event_safely (C4-F5 fix): a defer_event failure must not fall through to
    _run_agent_task's outer handler's zero-backoff immediate re-enqueue."""

    @pytest.mark.asyncio
    async def test_defer_failure_does_not_raise(self, registry_and_bridge):
        """execute_tool_locked raising (e.g. Redis blip during get_event) is swallowed --
        the circuit-breaker defer call-site must not propagate to the outer handler."""
        brain = _make_brain()
        brain.execute_tool_locked = AsyncMock(side_effect=RuntimeError("redis unavailable"))

        result = await brain._defer_event_safely("evt-hh0001", 60, "test reason")

        assert result is False
        brain.execute_tool_locked.assert_called_once_with(
            "evt-hh0001", "defer_event", {"delay_seconds": 60, "reason": "test reason"},
        )

    @pytest.mark.asyncio
    async def test_defer_success_returns_true(self, registry_and_bridge):
        brain = _make_brain()
        brain.execute_tool_locked = AsyncMock(return_value=True)

        result = await brain._defer_event_safely("evt-hh0001", 30, "test reason")

        assert result is True

    @pytest.mark.asyncio
    async def test_code_reviewer_defer_failure_does_not_crash_run_agent_task(self, registry_and_bridge):
        """End-to-end: circuit-breaker path for an EPHEMERAL_ONLY role whose defer_event
        call itself fails must return cleanly (no exception surfaces to the caller), not
        fall through to the generic error-turn + immediate-re-enqueue path."""
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(return_value=None)
        brain._ephemeral_provisioner.record_dispatch_circuit_break = MagicMock()
        brain._ephemeral_provisioner.record_dispatch_sidecar_fallback = MagicMock()
        brain.execute_tool_locked = AsyncMock(side_effect=RuntimeError("redis unavailable"))

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Findings ready.", None),
        ) as mock_dispatch:
            # Must not raise -- the defer failure is caught inside _defer_event_safely.
            await brain._run_agent_task(
                event_id="evt-hh0001", agent_name="code_reviewer", agent=None,
                task="Review the recent changes", event_md_path="/tmp/x.md",
                routing_turn_num=1, mode="review", effort="",
            )

        mock_dispatch.assert_not_called()
