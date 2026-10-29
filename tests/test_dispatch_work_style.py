# BlackBoard/tests/test_dispatch_work_style.py
# @ai-rules:
# 1. [Constraint]: 4-Layer Farley ATDD test for FRIDAY dispatch work_style plumbing (T-1).
# 2. [Pattern]: Layer 1: Domain Scenarios (Given/When/Then), Layer 2: Domain DSL,
#               Layer 3: Protocol Drivers (Mock Context & TaskBridge), Layer 4: SUT Targets.
# 3. [Constraint]: No live Redis, no live WS -- mocks mirror test_dispatch_model_effort.py.
"""
4-Layer Executable Specification for FRIDAY work_style Dispatch (Scenario T-1).
Verifies select_agent tool schema, handler plumbing, taskForAgent turn payload,
and WebSocket task envelope dispatch.
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
import pytest

# =============================================================================
# Layer 4: SUT Target Imports
# =============================================================================
from src.agents.handlers_dispatch import handle_select_agent
from src.agents import dispatch
from src.agents.dispatch import dispatch_to_agent
from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
from src.agents.task_bridge import TaskBridge
from src.models import ConversationTurn


# =============================================================================
# Layer 3: Protocol Drivers
# =============================================================================
class MockToolContextDriver:
    """Protocol driver adapting ToolContext operations for in-memory dispatch verification."""

    def __init__(self, event_id: str = "evt-test-123"):
        self.event_id = event_id
        self.recorded_turns: list[ConversationTurn] = []
        self.broadcast_turns: list[dict] = []
        self.run_agent_task_calls: list[dict[str, Any]] = []

        self.ctx = MagicMock()
        self.ctx.is_task_running.return_value = False
        self.ctx.is_dispatch_locked.return_value = False
        self.ctx.increment_routing_depth.return_value = 1
        self.ctx.next_turn_number = AsyncMock(return_value=1)
        self.ctx.stamp_event = AsyncMock()
        self.ctx.emit_pulse = AsyncMock()
        self.ctx.record_event = AsyncMock()
        self.ctx.broadcast = AsyncMock()
        self.ctx.get_ws_mode.return_value = "forward"
        self.ctx.get_agent_instance.return_value = MagicMock()

        bb = MagicMock()
        bb.get_event = AsyncMock(return_value=None)
        self.ctx.get_blackboard.return_value = bb

        async def _append_and_broadcast(_event_id: str, turn: ConversationTurn):
            self.recorded_turns.append(turn)
        self.ctx.append_and_broadcast = AsyncMock(side_effect=_append_and_broadcast)

        async def _run_agent_task(*args, **kwargs):
            self.run_agent_task_calls.append({"args": args, "kwargs": kwargs})
        self.ctx.run_agent_task = AsyncMock(side_effect=_run_agent_task)


class FakeWsAgentConnDriver:
    """Protocol driver simulating a persistent WebSocket connection to an agent sidecar."""

    def __init__(self, bridge: TaskBridge, agent_id: str = "agent-developer-1"):
        self.agent_id = agent_id
        self.busy = False
        self.current_event_id: str | None = None
        self.current_task_id: str | None = None
        self.current_role: str | None = None
        self.captured_envelope: dict[str, Any] = {}
        self._bridge = bridge
        self.ws = MagicMock()
        self.ws.send_json = AsyncMock(side_effect=self._on_send)

    async def _on_send(self, payload: dict[str, Any]) -> None:
        self.captured_envelope = payload
        self._bridge.put(payload["task_id"], {
            "type": "result", "output": "done", "source": "findings",
        })


def _build_mock_registry(conn: FakeWsAgentConnDriver):
    registry = AsyncMock()
    registry.get_available = AsyncMock(return_value=conn)
    registry.get_by_id = AsyncMock(return_value=conn)
    registry.mark_busy = AsyncMock()
    registry.mark_idle = AsyncMock()
    return registry


# =============================================================================
# Layer 2: Domain DSL Operations
# =============================================================================
class DispatchDSL:
    """Domain DSL for expressing Farley ATDD dispatch scenarios."""

    def __init__(self):
        self.driver = MockToolContextDriver()
        self.bridge = TaskBridge()
        self.conn_driver = FakeWsAgentConnDriver(self.bridge)
        self.registry = _build_mock_registry(self.conn_driver)
        self.select_agent_args: dict[str, Any] = {}
        self.dispatch_result: tuple[str, str | None] | None = None

    def given_agent_dispatch_request(
        self,
        agent_name: str = "developer",
        task: str = "Implement ATDD Green scenario",
        work_style: str | None = None,
        mode: str = "code",
        effort: str = "high",
    ) -> None:
        args: dict[str, Any] = {
            "agent_name": agent_name,
            "task_instruction": task,
            "mode": mode,
            "effort": effort,
        }
        if work_style is not None:
            args["work_style"] = work_style
        self.select_agent_args = args

    async def when_brain_dispatches_task(self) -> None:
        await handle_select_agent(
            self.driver.ctx,
            self.driver.event_id,
            self.select_agent_args,
            response_parts=None,
        )

    async def when_direct_ws_dispatch(
        self,
        role: str = "developer",
        task: str = "Execute scenario",
        work_style: str = "atdd_green",
    ) -> None:
        self.dispatch_result = await dispatch_to_agent(
            self.registry,
            self.bridge,
            role,
            self.driver.event_id,
            task,
            work_style=work_style,
        )

    def then_turn_contains_work_style(self, expected_style: str) -> None:
        assert len(self.driver.recorded_turns) > 0, "No ConversationTurn recorded"
        turn = self.driver.recorded_turns[0]
        task_for_agent = turn.taskForAgent or {}
        assert "work_style" in task_for_agent, (
            f"Expected 'work_style' in turn.taskForAgent, but got keys: {list(task_for_agent.keys())}"
        )
        assert task_for_agent["work_style"] == expected_style, (
            f"Expected work_style={expected_style!r}, got {task_for_agent['work_style']!r}"
        )

    def then_run_agent_task_called_with_work_style(self, expected_style: str) -> None:
        assert len(self.driver.run_agent_task_calls) > 0, "ctx.run_agent_task was not called"
        call_kwargs = self.driver.run_agent_task_calls[0]["kwargs"]
        assert "work_style" in call_kwargs, (
            f"Expected 'work_style' kwarg in ctx.run_agent_task call, got: {list(call_kwargs.keys())}"
        )
        assert call_kwargs["work_style"] == expected_style, (
            f"Expected ctx.run_agent_task(..., work_style={expected_style!r}), got {call_kwargs['work_style']!r}"
        )

    def then_ws_task_envelope_contains_work_style(self, expected_style: str) -> None:
        assert "work_style" in self.conn_driver.captured_envelope, (
            f"Expected 'work_style' in WS task envelope, got: {list(self.conn_driver.captured_envelope.keys())}"
        )
        assert self.conn_driver.captured_envelope["work_style"] == expected_style, (
            f"Expected WS envelope work_style={expected_style!r}, got {self.conn_driver.captured_envelope['work_style']!r}"
        )


# =============================================================================
# Layer 1: Domain Scenarios (ATDD Executable Acceptance Tests)
# =============================================================================
class TestDispatchWorkStyleScenarioT1:
    """T-1: Verify select_agent work_style plumbing across schema, dispatcher, and WS."""

    def test_select_agent_tool_schema_declares_work_style_enum(self):
        """
        Scenario: Tool schema declares work_style enum property.
        Given Brain tool schema definition in src/agents/llm/types.py
        When inspecting 'select_agent' input_schema
        Then 'work_style' property exists with supported Farley ATDD work styles
        """
        select_agent_tool = next(
            (t for t in BRAIN_TOOL_SCHEMAS if isinstance(t, dict) and t.get("name") == "select_agent"),
            None,
        )
        assert select_agent_tool is not None, "select_agent tool schema missing in BRAIN_TOOL_SCHEMAS"

        properties = select_agent_tool.get("input_schema", {}).get("properties", {})
        assert "work_style" in properties, "Property 'work_style' missing in select_agent input_schema"

        work_style_schema = properties["work_style"]
        assert work_style_schema.get("type") == "string"
        assert "enum" in work_style_schema, "Enum declaration missing in work_style schema"

        expected_enum = {"autonomous", "pair", "atdd_red", "atdd_green", "spike"}
        actual_enum = set(work_style_schema["enum"])
        assert expected_enum.issubset(actual_enum), (
            f"Expected enum to include {expected_enum}, got {actual_enum}"
        )

    @pytest.mark.asyncio
    async def test_explicit_work_style_plumbed_to_turn_and_context(self):
        """
        Scenario: Dispatch with work_style="atdd_green" stores in turn and passes to run_agent_task.
        Given a dispatch request with work_style="atdd_green"
        When Brain processes handle_select_agent
        Then turn.taskForAgent has work_style="atdd_green"
        And ctx.run_agent_task is called with work_style="atdd_green"
        """
        dsl = DispatchDSL()
        dsl.given_agent_dispatch_request(
            agent_name="developer",
            task="Write implementation code for Farley ATDD scenario",
            work_style="atdd_green",
        )

        await dsl.when_brain_dispatches_task()

        dsl.then_turn_contains_work_style("atdd_green")
        dsl.then_run_agent_task_called_with_work_style("atdd_green")

    @pytest.mark.asyncio
    async def test_omitted_work_style_defaults_to_autonomous(self):
        """
        Scenario: Dispatch without work_style defaults backward-compatibly to "autonomous".
        Given a dispatch request where work_style is omitted
        When Brain processes handle_select_agent
        Then turn.taskForAgent has work_style="autonomous"
        And ctx.run_agent_task is called with work_style="autonomous"
        """
        dsl = DispatchDSL()
        dsl.given_agent_dispatch_request(
            agent_name="developer",
            task="Legacy task without explicit work_style",
            work_style=None,
        )

        await dsl.when_brain_dispatches_task()

        dsl.then_turn_contains_work_style("autonomous")
        dsl.then_run_agent_task_called_with_work_style("autonomous")

    @pytest.mark.asyncio
    async def test_ws_dispatch_envelope_includes_work_style(self):
        """
        Scenario: dispatch_to_agent forwards work_style in WebSocket task envelope.
        Given a dispatch_to_agent invocation with work_style="atdd_green"
        When dispatch_to_agent sends task payload to sidecar connection
        Then the WS task envelope contains "work_style": "atdd_green"
        """
        dsl = DispatchDSL()
        await dsl.when_direct_ws_dispatch(
            role="developer",
            task="Run ATDD Green cycle",
            work_style="atdd_green",
        )

        dsl.then_ws_task_envelope_contains_work_style("atdd_green")

    def test_known_work_styles_whitelist_defined(self):
        """
        Scenario: KNOWN_WORK_STYLES whitelist exists in dispatch module.
        Given dispatch module
        When checking KNOWN_WORK_STYLES constant
        Then it contains atdd_red, atdd_green, pair, spike, autonomous
        """
        known_styles = getattr(dispatch, "KNOWN_WORK_STYLES", None)
        assert known_styles is not None, "KNOWN_WORK_STYLES constant missing in src.agents.dispatch"
        assert isinstance(known_styles, frozenset), "KNOWN_WORK_STYLES should be a frozenset"
        expected = {"autonomous", "pair", "atdd_red", "atdd_green", "spike"}
        assert expected.issubset(known_styles), (
            f"Expected KNOWN_WORK_STYLES to include {expected}, got {known_styles}"
        )


# =============================================================================
# T-1b: follow-up dispatches keep the lock (message_agent / reply_to_agent redirect)
# =============================================================================
from unittest.mock import patch  # noqa: E402

from src.agents.handlers_dispatch import handle_message_agent, handle_reply_to_agent  # noqa: E402


def _route_turn(agent: str, work_style: str, turn: int = 1) -> ConversationTurn:
    return ConversationTurn(
        turn=turn, actor="brain", action="route", waitingFor="select_agent",
        selectedAgents=[agent],
        taskForAgent={"agent": agent, "instruction": "x", "mode": "implement", "work_style": work_style},
    )


class FollowUpDSL:
    """Domain DSL: an event whose developer was routed with a given work_style, then messaged."""

    def __init__(self):
        self.driver = MockToolContextDriver()
        self.ctx = self.driver.ctx
        self.ctx.ephemeral_only_roles = frozenset()
        self.ctx.is_task_running.return_value = False  # agent idle -> message_agent dispatches a fresh task
        self.ctx.get_active_agent_for_event.return_value = None
        self.registry = AsyncMock()
        self.registry.get_available = AsyncMock(return_value=MagicMock())

    def given_conversation(self, turns: list[ConversationTurn]) -> None:
        event_doc = MagicMock()
        event_doc.conversation = turns
        self.ctx.get_blackboard.return_value.get_event = AsyncMock(return_value=event_doc)

    async def when_message_agent(self, args: dict) -> None:
        with patch("src.dependencies.get_registry_and_bridge", return_value=(self.registry, None)):
            await handle_message_agent(self.ctx, self.driver.event_id, args, response_parts=None)

    async def when_reply_to_agent_redirected(self, args: dict) -> None:
        with patch("src.dependencies.get_registry_and_bridge", return_value=(self.registry, None)):
            await handle_reply_to_agent(self.ctx, self.driver.event_id, args, response_parts=None)

    def then_dispatched_with_work_style(self, expected: str) -> None:
        assert len(self.driver.run_agent_task_calls) == 1, self.driver.run_agent_task_calls
        assert self.driver.run_agent_task_calls[0]["kwargs"].get("work_style") == expected


class TestFollowUpPreservesWorkStyle:
    @pytest.mark.asyncio
    async def test_message_agent_preserves_atdd_green(self):
        """A message to a developer routed with atdd_green must not reset the lock to autonomous."""
        dsl = FollowUpDSL()
        dsl.given_conversation([_route_turn("developer", "atdd_green")])
        await dsl.when_message_agent({"agent_id": "developer", "message": "also fix the docs"})
        dsl.then_dispatched_with_work_style("atdd_green")

    @pytest.mark.asyncio
    async def test_reply_to_agent_redirect_preserves_atdd_green(self):
        """reply_to_agent with no active task redirects to message_agent and must keep the lock."""
        dsl = FollowUpDSL()
        dsl.given_conversation([_route_turn("developer", "atdd_green")])
        await dsl.when_reply_to_agent_redirected({"agent_id": "developer", "message": "go ahead"})
        dsl.then_dispatched_with_work_style("atdd_green")

    @pytest.mark.asyncio
    async def test_latest_route_for_that_agent_wins_and_other_agents_are_ignored(self):
        dsl = FollowUpDSL()
        dsl.given_conversation([
            _route_turn("developer", "atdd_green", turn=1),
            _route_turn("qe", "atdd_red", turn=2),
            _route_turn("developer", "autonomous", turn=3),
        ])
        await dsl.when_message_agent({"agent_id": "developer", "message": "status?"})
        dsl.then_dispatched_with_work_style("autonomous")

    @pytest.mark.asyncio
    async def test_unset_defaults_to_autonomous(self):
        dsl = FollowUpDSL()
        dsl.given_conversation([])
        await dsl.when_message_agent({"agent_id": "developer", "message": "hi"})
        dsl.then_dispatched_with_work_style("autonomous")

    @pytest.mark.asyncio
    async def test_work_style_in_tool_args_cannot_downgrade_the_lock(self):
        dsl = FollowUpDSL()
        dsl.given_conversation([_route_turn("developer", "atdd_green")])
        await dsl.when_message_agent({"agent_id": "developer", "message": "m", "work_style": "autonomous"})
        dsl.then_dispatched_with_work_style("atdd_green")

    @pytest.mark.asyncio
    async def test_lookup_failure_fails_closed_for_developer(self):
        """R2-5: if get_event raises, a developer message must not silently dispatch as autonomous."""
        dsl = FollowUpDSL()
        dsl.ctx.get_blackboard.return_value.get_event = AsyncMock(side_effect=RuntimeError("redis down"))
        await dsl.when_message_agent({"agent_id": "developer", "message": "hi"})
        assert dsl.driver.run_agent_task_calls == []
        assert any("select_agent" in (t.thoughts or "") for t in dsl.driver.recorded_turns)
