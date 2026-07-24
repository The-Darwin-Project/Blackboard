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
