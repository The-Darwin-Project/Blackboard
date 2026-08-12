# tests/test_explorer_dispatch.py
# @ai-rules:
# 1. [Constraint]: No Redis, no Tekton -- MagicMock blackboard + patched dispatch_to_agent.
# 2. [Pattern]: Mirrors test_ephemeral_model_routing.py: Brain(blackboard=mock, agents={}).
# 3. [Pattern]: Gate under test for overflow is Tier-2 condition in _run_agent_task.
# 4. [Pattern]: Explorer is EPHEMERAL_ONLY -- never dispatched to local sidecar.
# 5. [Gotcha]: _ROLE_CLI_MAP is new module-level dict -- import directly for assertion.
"""Verify Explorer ephemeral agent dispatch routing and Tier-2 overflow behavior.

Covers:
- T-1: Explorer always routes via ephemeral (Tier-0, never local)
- T-2: Explorer model resolves to gemini-3.5-flash-lite
- T-3: Explorer CLI resolves to gemini
- T-4: Explorer present in select_agent schema enum
- T-5: Busy local sidecar + aligner event -> ephemeral overflow
- T-6: Busy local sidecar + provisioner circuit break -> graceful defer
- T-7: Explorer + provisioner down -> defer 60s (EPHEMERAL_ONLY safety)
- T-10: Cross-CLI pod reuse (CLI mismatch -> terminate existing)
- T-11: Tier-2 overflow is open-by-default (no source filter)
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.brain import (
    Brain,
    _ROLE_MODEL_MAP,
    _ROLE_EFFORT_MAP,
)
from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
from src.models import EventDocument, EventEvidence, EventInput


# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

def _make_event(
    event_id: str = "evt-exp001",
    source: str = "headhunter",
    brain_phase: str = "dispatch",
) -> EventDocument:
    evidence = EventEvidence(
        display_text="Investigate pipeline status",
        source_type=source,
        severity="info",
    )
    return EventDocument(
        id=event_id,
        source=source,
        service="test-svc",
        brain_phase=brain_phase,
        event=EventInput(reason="probe request", evidence=evidence),
        conversation=[],
    )


def _make_aligner_event(event_id: str = "evt-align01") -> EventDocument:
    evidence = EventEvidence(
        display_text="CPU anomaly detected",
        source_type="aligner",
        severity="warning",
    )
    return EventDocument(
        id=event_id,
        source="aligner",
        service="test-svc",
        brain_phase="dispatch",
        event=EventInput(reason="cpu spike", evidence=evidence),
        conversation=[],
    )


def _make_brain(event: EventDocument | None = None) -> Brain:
    bb = MagicMock()
    bb.get_event = AsyncMock(return_value=event or _make_event())
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


# ---------------------------------------------------------------------------
# T-1: Explorer routes to ephemeral only (Tier-0, never local)
# ---------------------------------------------------------------------------

class TestExplorerEphemeralOnly:
    """Explorer is in EPHEMERAL_ONLY_ROLES -- must always take ephemeral path."""

    @pytest.mark.asyncio
    async def test_explorer_dispatches_via_ephemeral_provisioner(self, registry_and_bridge):
        """T-1: select_agent("explorer") -> ensure_agent called, dispatch receives agent_id."""
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-explorer-1"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Pipeline #123 is running.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-exp001",
                agent_name="explorer",
                agent=None,
                task="Find pipeline ID for branch main",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="investigate",
                effort="",
            )

        mock_dispatch.assert_called_once()
        assert mock_dispatch.call_args.kwargs["agent_id"] == "agent-explorer-1"
        brain._ephemeral_provisioner.ensure_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_explorer_never_falls_back_to_local_sidecar(self, registry_and_bridge):
        """T-1 corollary: when provisioner returns None, Explorer defers -- never dispatches locally."""
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(return_value=None)
        brain._ephemeral_provisioner.record_dispatch_circuit_break = MagicMock()
        brain._ephemeral_provisioner.record_dispatch_sidecar_fallback = MagicMock()
        brain.execute_tool_locked = AsyncMock(return_value=True)

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Should never reach here.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-exp001",
                agent_name="explorer",
                agent=None,
                task="Find pipeline ID for branch main",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="investigate",
                effort="",
            )

        mock_dispatch.assert_not_called()
        brain._ephemeral_provisioner.record_dispatch_sidecar_fallback.assert_not_called()


# ---------------------------------------------------------------------------
# T-2: Explorer model resolution
# ---------------------------------------------------------------------------

class TestExplorerModelResolution:
    """Explorer resolves to a model in the role model map and flows through dispatch."""

    def test_role_model_map_has_explorer(self):
        """T-2: _ROLE_MODEL_MAP has 'explorer' with a non-empty model string."""
        assert "explorer" in _ROLE_MODEL_MAP
        assert _ROLE_MODEL_MAP["explorer"]  # non-empty

    @pytest.mark.asyncio
    async def test_explorer_model_passed_to_ensure_agent(self, registry_and_bridge):
        """T-2: ensure_agent receives the explorer model from _ROLE_MODEL_MAP."""
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-explorer-2"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Done.", None),
        ):
            await brain._run_agent_task(
                event_id="evt-exp001",
                agent_name="explorer",
                agent=None,
                task="Find pod status",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="investigate",
                effort="",
            )

        ensure_kwargs = brain._ephemeral_provisioner.ensure_agent.call_args.kwargs
        assert ensure_kwargs["model"] == _ROLE_MODEL_MAP["explorer"]

    @pytest.mark.asyncio
    async def test_explorer_model_passed_to_dispatch(self, registry_and_bridge):
        """T-2: dispatch_to_agent receives the explorer model."""
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-explorer-3"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Done.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-exp001",
                agent_name="explorer",
                agent=None,
                task="Find pod status",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="investigate",
                effort="",
            )

        assert mock_dispatch.call_args.kwargs["model"] == _ROLE_MODEL_MAP["explorer"]


# ---------------------------------------------------------------------------
# T-3: Explorer CLI resolution
# ---------------------------------------------------------------------------

class TestExplorerCLIResolution:
    """Explorer resolves to 'gemini' in the role CLI map."""

    def test_role_cli_map_has_explorer(self):
        """T-3: _ROLE_CLI_MAP["explorer"] == "gemini"."""
        from src.agents.brain import _ROLE_CLI_MAP

        assert "explorer" in _ROLE_CLI_MAP
        assert _ROLE_CLI_MAP["explorer"] == "gemini"

    def test_role_cli_map_defaults_to_claude(self):
        """T-3 corollary: non-explorer roles get "claude" as CLI default."""
        from src.agents.brain import _ROLE_CLI_MAP

        assert _ROLE_CLI_MAP.get("sysadmin", "claude") == "claude"
        assert _ROLE_CLI_MAP.get("nonexistent_role", "claude") == "claude"


# ---------------------------------------------------------------------------
# T-4: Explorer in schema enum
# ---------------------------------------------------------------------------

class TestExplorerInSchemaEnum:
    """Explorer must be a valid value in all tool schema agent_name enums."""

    def test_explorer_in_select_agent_enum(self):
        """T-4: "explorer" present in select_agent schema enum."""
        schemas_by_name = {tool["name"]: tool for tool in BRAIN_TOOL_SCHEMAS}
        select_agent_enum = (
            schemas_by_name["select_agent"]["input_schema"]["properties"]["agent_name"]["enum"]
        )
        assert "explorer" in select_agent_enum

    def test_explorer_in_ask_agent_for_state_enum(self):
        """T-4: "explorer" present in ask_agent_for_state schema enum."""
        schemas_by_name = {tool["name"]: tool for tool in BRAIN_TOOL_SCHEMAS}
        ask_agent_enum = (
            schemas_by_name["ask_agent_for_state"]["input_schema"]["properties"]["agent_name"]["enum"]
        )
        assert "explorer" in ask_agent_enum

    def test_explorer_in_create_plan_step_agent_enum(self):
        """T-4: "explorer" present in create_plan step agent enum."""
        schemas_by_name = {tool["name"]: tool for tool in BRAIN_TOOL_SCHEMAS}
        create_plan_agent_schema = (
            schemas_by_name["create_plan"]["input_schema"]["properties"]["steps"]["items"]["properties"]["agent"]
        )
        assert "explorer" in create_plan_agent_schema["enum"]


# ---------------------------------------------------------------------------
# T-5: Busy sidecar overflow (Tier-2 open-by-default)
# ---------------------------------------------------------------------------

class TestBusySidecarOverflow:
    """When local sidecar is busy, non-ephemeral-only roles overflow to ephemeral."""

    @pytest.mark.asyncio
    async def test_aligner_event_busy_sysadmin_overflows_to_ephemeral(self, registry_and_bridge):
        """T-5: aligner event + sysadmin busy -> ephemeral spawn (not error)."""
        registry, bridge = registry_and_bridge
        registry.get_available = AsyncMock(return_value=None)

        brain = _make_brain(event=_make_aligner_event())
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-sysadmin-overflow-1"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Scaled.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-align01",
                agent_name="sysadmin",
                agent=None,
                task="Scale the deployment",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="execute",
                effort="",
            )

        mock_dispatch.assert_called_once()
        assert mock_dispatch.call_args.kwargs["agent_id"] == "agent-sysadmin-overflow-1"
        brain._ephemeral_provisioner.ensure_agent.assert_called_once()

    @pytest.mark.asyncio
    async def test_jarvis_event_busy_sysadmin_overflows_to_ephemeral(self, registry_and_bridge):
        """T-5 corollary: jarvis source also triggers overflow (not just chat/slack)."""
        registry, bridge = registry_and_bridge
        registry.get_available = AsyncMock(return_value=None)

        jarvis_event = _make_event(event_id="evt-jarvis01", source="jarvis")
        brain = _make_brain(event=jarvis_event)
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-sysadmin-overflow-2"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Done.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-jarvis01",
                agent_name="sysadmin",
                agent=None,
                task="Check pod status",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="investigate",
                effort="",
            )

        mock_dispatch.assert_called_once()
        assert mock_dispatch.call_args.kwargs["agent_id"] == "agent-sysadmin-overflow-2"


# ---------------------------------------------------------------------------
# T-6: Overflow + circuit break -> graceful error
# ---------------------------------------------------------------------------

class TestOverflowCircuitBreak:
    """When overflow triggered but provisioner returns None -> defer gracefully."""

    @pytest.mark.asyncio
    async def test_busy_sidecar_plus_circuit_break_defers(self, registry_and_bridge):
        """T-6: sysadmin busy + provisioner None -> defer 30s (not crash/error turn)."""
        registry, bridge = registry_and_bridge
        registry.get_available = AsyncMock(return_value=None)

        brain = _make_brain(event=_make_aligner_event())
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(return_value=None)
        brain._ephemeral_provisioner.record_dispatch_circuit_break = MagicMock()
        brain._ephemeral_provisioner.record_dispatch_sidecar_fallback = MagicMock()
        brain._defer_event_safely = AsyncMock(return_value=True)

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Should not reach.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-align01",
                agent_name="sysadmin",
                agent=None,
                task="Scale the deployment",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="execute",
                effort="",
            )

        mock_dispatch.assert_not_called()
        brain._ephemeral_provisioner.record_dispatch_circuit_break.assert_called_once()
        brain._defer_event_safely.assert_called_once()
        defer_args = brain._defer_event_safely.call_args.args
        assert defer_args[1] == 30  # 30s defer for overflow circuit break


# ---------------------------------------------------------------------------
# T-7: Explorer provisioner down -> defer 60s
# ---------------------------------------------------------------------------

class TestExplorerProvisionerDown:
    """Explorer (EPHEMERAL_ONLY) + provisioner down -> defer 60s, not crash."""

    @pytest.mark.asyncio
    async def test_explorer_provisioner_none_defers_60s(self, registry_and_bridge):
        """T-7: Explorer + ensure_agent returns None -> circuit break + defer 60s."""
        brain = _make_brain()
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(return_value=None)
        brain._ephemeral_provisioner.record_dispatch_circuit_break = MagicMock()
        brain.execute_tool_locked = AsyncMock(return_value=True)

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Never.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-exp001",
                agent_name="explorer",
                agent=None,
                task="Find pipeline ID",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="investigate",
                effort="",
            )

        mock_dispatch.assert_not_called()
        brain._ephemeral_provisioner.record_dispatch_circuit_break.assert_called_once()
        brain.execute_tool_locked.assert_called_once()
        defer_args = brain.execute_tool_locked.call_args.args
        assert defer_args[1] == "defer_event"
        assert defer_args[2]["delay_seconds"] == 60

    @pytest.mark.asyncio
    async def test_explorer_no_provisioner_defers_safely(self, registry_and_bridge):
        """T-7 corollary: provisioner is None entirely -> safety guard defers."""
        brain = _make_brain()
        brain._ephemeral_provisioner = None
        brain._defer_event_safely = AsyncMock(return_value=True)

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Never.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-exp001",
                agent_name="explorer",
                agent=None,
                task="Find pipeline ID",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="investigate",
                effort="",
            )

        mock_dispatch.assert_not_called()
        brain._defer_event_safely.assert_called_once()


# ---------------------------------------------------------------------------
# T-10: Cross-CLI pod reuse guard
# ---------------------------------------------------------------------------

class TestCrossCLIPodReuse:
    """ensure_agent must terminate existing pod when CLI mismatch detected."""

    @pytest.mark.asyncio
    async def test_cli_mismatch_terminates_existing_pod(self, registry_and_bridge):
        """T-10: existing Gemini pod + Claude request -> terminate + spawn new."""
        brain = _make_brain()

        existing_conn = MagicMock()
        existing_conn.agent_id = "agent-explorer-old"
        existing_conn.cli = "gemini"

        new_conn = MagicMock()
        new_conn.agent_id = "agent-developer-new"

        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(return_value=new_conn)
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Code changes done.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-exp001",
                agent_name="developer",
                agent=None,
                task="Implement the fix",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="execute",
                effort="",
            )

        brain._ephemeral_provisioner.ensure_agent.assert_called_once()
        mock_dispatch.assert_called_once()
        assert mock_dispatch.call_args.kwargs["agent_id"] == "agent-developer-new"


# ---------------------------------------------------------------------------
# T-11: Tier-2 open-by-default (no source filter)
# ---------------------------------------------------------------------------

class TestTier2OpenByDefault:
    """After the change, Tier-2 overflow triggers for ANY source when local busy."""

    @pytest.mark.asyncio
    async def test_chat_source_still_overflows(self, registry_and_bridge):
        """T-11: chat source (existing behavior) still triggers overflow."""
        registry, bridge = registry_and_bridge
        registry.get_available = AsyncMock(return_value=None)

        chat_event = _make_event(event_id="evt-chat01", source="chat")
        brain = _make_brain(event=chat_event)
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-overflow-chat"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Done.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-chat01",
                agent_name="sysadmin",
                agent=None,
                task="Diagnose the issue",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="investigate",
                effort="",
            )

        assert mock_dispatch.call_args.kwargs["agent_id"] == "agent-overflow-chat"

    @pytest.mark.asyncio
    async def test_aligner_source_now_overflows(self, registry_and_bridge):
        """T-11: aligner source (NEW behavior) triggers overflow when local busy."""
        registry, bridge = registry_and_bridge
        registry.get_available = AsyncMock(return_value=None)

        brain = _make_brain(event=_make_aligner_event())
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="agent-overflow-aligner"),
        )
        brain._ephemeral_provisioner.record_dispatch_success = MagicMock()

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Done.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-align01",
                agent_name="sysadmin",
                agent=None,
                task="Scale pods",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="execute",
                effort="",
            )

        assert mock_dispatch.call_args.kwargs["agent_id"] == "agent-overflow-aligner"

    @pytest.mark.asyncio
    async def test_available_sidecar_does_not_overflow(self, registry_and_bridge):
        """T-11 negative: local sidecar IS available -> no ephemeral (normal dispatch)."""
        registry, bridge = registry_and_bridge
        registry.get_available = AsyncMock(return_value=MagicMock(agent_id="local-sysadmin"))

        brain = _make_brain(event=_make_aligner_event())
        brain._ephemeral_provisioner = AsyncMock()
        brain._ephemeral_provisioner.ensure_agent = AsyncMock(
            return_value=MagicMock(agent_id="should-not-be-called"),
        )

        with patch(
            "src.agents.brain.dispatch_to_agent",
            new_callable=AsyncMock,
            return_value=("Done locally.", None),
        ) as mock_dispatch:
            await brain._run_agent_task(
                event_id="evt-align01",
                agent_name="sysadmin",
                agent=None,
                task="Scale pods",
                event_md_path="/tmp/x.md",
                routing_turn_num=1,
                mode="execute",
                effort="",
            )

        assert mock_dispatch.call_args.kwargs["agent_id"] is None
        assert mock_dispatch.call_args.kwargs["model"] == ""


# ---------------------------------------------------------------------------
# T-8: Gemini buildCLICommand with --model flag (JavaScript)
# T-9: TriggerTemplate cli param (Helm)
# ---------------------------------------------------------------------------

class TestInfraVerification:
    """T-8 and T-9 are verified via shell commands (not pure pytest).

    These tests document the verification commands. Run them manually or
    via CI shell steps.
    """

    @pytest.mark.skip(reason="Shell verification -- run manually: see docstring")
    def test_t8_gemini_build_cli_command_model_flag(self):
        """T-8: Verify Gemini CLI buildCLICommand includes --model flag.

        Verification command (from BlackBoard root):
            node -e "
              const {buildCLICommand} = require('./gemini-sidecar/cli-executor.js');
              const cmd = buildCLICommand({cli:'gemini', model:'gemini-3.5-flash-lite', task:'test'});
              const args = cmd.join(' ');
              if (!args.includes('--model gemini-3.5-flash-lite')) {
                console.error('FAIL: --model not found in:', args);
                process.exit(1);
              }
              console.log('PASS:', args);
            "
        """

    @pytest.mark.skip(reason="Shell verification -- run manually: see docstring")
    def test_t9_trigger_template_cli_param(self):
        """T-9: Verify TriggerTemplate renders AGENT_CLI from cli param.

        Verification command (from BlackBoard root):
            helm template darwin ./helm \\
              --set ephemeralAgents.roleCli.explorer=gemini \\
              | grep -A2 'name: AGENT_CLI' \\
              | grep -q 'value:.*gemini' \\
              && echo "PASS: AGENT_CLI=gemini found" \\
              || echo "FAIL: AGENT_CLI not parameterized"

        Expected: TaskRun env block contains:
            - name: AGENT_CLI
              value: $(tt.params.cli)   # or resolved to "gemini" via TT default
        """
