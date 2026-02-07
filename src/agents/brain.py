# BlackBoard/src/agents/brain.py
"""
The Brain Orchestrator - Thin Python Shell, LLM Does the Thinking.

This module contains ZERO routing logic, ZERO hardcoded agent selection rules,
ZERO if/else decision trees. ALL complex reasoning (triage, agent selection,
interpreting responses, deciding next steps) is delegated to the Gemini 3 Pro
LLM via function calling.

The Python code only:
  (a) polls Redis for events
  (b) builds prompts from event data
  (c) executes whatever function the LLM chooses
  (d) writes results back to Redis + event MD to sidecar volumes
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional

from ..models import ConversationTurn, EventDocument, EventStatus

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

# =============================================================================
# Brain System Prompt - THIS IS THE DECISION ENGINE
# =============================================================================

BRAIN_SYSTEM_PROMPT = """You are the Brain orchestrator of Project Darwin, an autonomous cloud operations system.

You coordinate three AI agents via a shared conversation queue:
- **Architect**: Reviews codebases, analyzes topology, produces Markdown plans. NEVER executes. Use for: planning, code review, design decisions.
- **sysAdmin**: Executes GitOps changes (Helm values), investigates K8s issues via kubectl. Use for: scaling, investigation, infrastructure changes.
- **Developer**: Implements source code changes based on Architect plans. Use for: adding features, fixing bugs, modifying application code.

## Your Job
1. Read the event (anomaly or user request) and its conversation history.
2. Decide the NEXT action by calling ONE of your available functions.
3. You are called repeatedly as the conversation progresses. Each call, you see the full history and decide the next step.

## Decision Guidelines
- For infrastructure anomalies (high CPU, pod issues): start with sysAdmin to investigate, then decide action.
- For user feature requests: start with Architect to plan, then Developer to implement.
- For scaling/config changes: sysAdmin can handle directly after a plan.
- Structural changes (source code, templates) REQUIRE user approval via request_user_approval.
- Values-only changes (scaling, config toggles) can proceed without approval.
- After execution, use re_trigger_aligner to verify the change took effect.
- When the issue is resolved and verified, close the event with a summary.
- If an agent asks for another agent's help (requestingAgent field), route to that agent.
- If an agent reports "busy" after retries, use defer_event to re-process later instead of closing. Only close if the event is no longer relevant.

## Execution Method
- ALL infrastructure changes MUST go through GitOps: clone the target repo, modify values.yaml, commit, push. ArgoCD syncs the change.
- NEVER instruct agents to use kubectl for mutations (scale, patch, edit, delete). kubectl is for investigation ONLY (get, list, describe, logs).
- When asking sysAdmin to scale, say: "modify replicaCount in helm/values.yaml via GitOps" not "scale the deployment."
- Agents should ONLY modify EXISTING values in Helm charts. If a new feature is needed (HPA, PDB, etc.), route to Architect for planning first.

## Safety
- Never approve plans that delete namespaces, volumes, or databases without user approval.
- If an agent responds with the same answer 3 times, close the event as stuck.

## Cynefin Sense-Making Framework

Before deciding how to respond to an event, classify it into a domain:

### CLEAR (Known knowns -- Best Practice)
- Pattern: Known issue with a proven fix (e.g., high CPU -> scale up)
- Constraints: Tightly constrained, no creativity needed
- Flow: Sense -> Categorize -> Respond
- Action: Skip Architect. Send sysAdmin directly with the established fix.
- Example: "CPU > 80% on a service with 1 replica" -> scale to 2 via GitOps

### COMPLICATED (Known unknowns -- Good Practices)
- Pattern: Issue needs expert analysis (e.g., intermittent errors, performance degradation)
- Constraints: Governing constraints, multiple valid approaches
- Flow: Sense -> Analyze -> Respond
- Action: Send sysAdmin to investigate, then Architect to analyze options, then decide.
- Example: "Error rate spike from unknown cause" -> investigate -> plan -> execute

### COMPLEX (Unknown unknowns -- Emergent Practice)
- Pattern: Novel situation, no clear cause-effect (e.g., cascading failures, new feature request)
- Constraints: Enabling constraints, high freedom
- Flow: Probe -> Sense -> Respond
- Action: Run a small safe-to-fail probe first. Observe result. Adapt.
- Example: "User asks to add a feature" -> Architect reviews codebase (probe) -> plan based on findings

### CHAOTIC (Crisis -- Novel Practice)
- Pattern: System down, cascading failures, critical security breach
- Constraints: No constraints, act first
- Flow: Act -> Sense -> Respond
- Action: Immediate stabilization (rollback, scale up, disable feature flag). Investigate AFTER stable.
- Example: "All pods CrashLoopBackOff" -> rollback last deployment immediately -> then investigate

### DISORDER (Default)
- You don't know which domain. Ask sysAdmin to investigate first to gather data.

## Control Theory
- The user's request is the Setpoint (SP)
- The system's current state is the Process Variable (PV)
- Your decisions are the Controller minimizing the error between SP and PV
- Agent responses and Aligner verification are the Feedback Loop
- ALWAYS verify after execution: use re_trigger_aligner to close the feedback loop

## GitOps Context
Services self-describe their GitOps coordinates (repo, helm path) via telemetry.
When checking GitOps sync status, instruct sysAdmin to discover the GitOps tooling namespace first (e.g., search for ArgoCD or Flux namespaces) rather than assuming a specific namespace.
"""

# Circuit breaker limits
MAX_TURNS_PER_EVENT = 20
MAX_EVENT_DURATION_SECONDS = 1800  # 30 minutes

# Volume mount paths (must match Helm deployment.yaml)
VOLUME_PATHS = {
    "architect": "/data/gitops-architect",
    "sysadmin": "/data/gitops-sysadmin",
    "developer": "/data/gitops-developer",
}


def _build_brain_tools():
    """Build Vertex AI function declarations for Brain's available actions."""
    try:
        from vertexai.generative_models import FunctionDeclaration, Tool

        select_agent = FunctionDeclaration(
            name="select_agent",
            description="Route work to an agent. Use this to assign a task to Architect, sysAdmin, or Developer.",
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "enum": ["architect", "sysadmin", "developer"],
                        "description": "Which agent to route to",
                    },
                    "task_instruction": {
                        "type": "string",
                        "description": "What the agent should do (be specific and actionable)",
                    },
                },
                "required": ["agent_name", "task_instruction"],
            },
        )

        close_event = FunctionDeclaration(
            name="close_event",
            description="Close the event as resolved. Use when the issue is fixed and verified, or the request is complete.",
            parameters={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Summary of what was done and the outcome",
                    },
                },
                "required": ["summary"],
            },
        )

        request_user_approval = FunctionDeclaration(
            name="request_user_approval",
            description="Pause and ask the user to approve a plan. Use for structural changes (source code, templates).",
            parameters={
                "type": "object",
                "properties": {
                    "plan_summary": {
                        "type": "string",
                        "description": "Summary of the plan for the user to review",
                    },
                },
                "required": ["plan_summary"],
            },
        )

        re_trigger_aligner = FunctionDeclaration(
            name="re_trigger_aligner",
            description="Ask the Aligner to verify that a change took effect (e.g., replicas increased, CPU normalized).",
            parameters={
                "type": "object",
                "properties": {
                    "service": {
                        "type": "string",
                        "description": "Service to check",
                    },
                    "check_condition": {
                        "type": "string",
                        "description": "What condition to verify (e.g., 'replicas == 2', 'CPU < 80%')",
                    },
                },
                "required": ["service", "check_condition"],
            },
        )

        ask_agent_for_state = FunctionDeclaration(
            name="ask_agent_for_state",
            description="Ask an agent for information (e.g., ask sysAdmin for kubectl logs, pod status).",
            parameters={
                "type": "object",
                "properties": {
                    "agent_name": {
                        "type": "string",
                        "enum": ["architect", "sysadmin", "developer"],
                        "description": "Which agent to ask",
                    },
                    "question": {
                        "type": "string",
                        "description": "What information you need",
                    },
                },
                "required": ["agent_name", "question"],
            },
        )

        wait_for_verification = FunctionDeclaration(
            name="wait_for_verification",
            description="Mark that you are waiting for the Aligner to confirm a state change.",
            parameters={
                "type": "object",
                "properties": {
                    "condition": {
                        "type": "string",
                        "description": "What you are waiting for",
                    },
                },
                "required": ["condition"],
            },
        )

        defer_event = FunctionDeclaration(
            name="defer_event",
            description="Defer an event for later processing. Use when an agent is busy, the issue is not urgent, or you want to retry after a cooldown period.",
            parameters={
                "type": "object",
                "properties": {
                    "reason": {
                        "type": "string",
                        "description": "Why this event is being deferred (e.g., 'agent busy', 'waiting for cooldown')",
                    },
                    "delay_seconds": {
                        "type": "integer",
                        "description": "How many seconds to wait before re-processing (30-300)",
                    },
                },
                "required": ["reason", "delay_seconds"],
            },
        )

        return Tool(function_declarations=[
            select_agent,
            close_event,
            request_user_approval,
            re_trigger_aligner,
            ask_agent_for_state,
            wait_for_verification,
            defer_event,
        ])

    except ImportError:
        logger.warning("vertexai not available - Brain running in probe mode")
        return None


class Brain:
    """
    Brain orchestrator - thin shell around LLM function calling.
    
    ALL decision logic lives in BRAIN_SYSTEM_PROMPT + function declarations.
    Python code only polls, serializes, calls LLM, and executes the result.
    """

    def __init__(
        self,
        blackboard: BlackboardState,
        agents: Optional[dict[str, Any]] = None,
        broadcast: Optional[Callable] = None,
    ):
        self.blackboard = blackboard
        self.agents = agents or {}
        self.broadcast = broadcast  # async callable to push to UI WebSocket clients
        self._running = False
        self._model = None
        self._llm_available = False
        self._active_tasks: dict[str, asyncio.Task] = {}  # event_id -> running task
        self._routing_depth: dict[str, int] = {}  # event_id -> recursion counter
        # LLM config from environment
        self.project = os.getenv("GCP_PROJECT", "")
        self.location = os.getenv("GCP_LOCATION", "global")
        self.model_name = os.getenv("VERTEX_MODEL_PRO", "gemini-3-pro-preview")
        logger.info(f"Brain initialized (project={self.project}, model={self.model_name}, agents={list(self.agents.keys())})")

    async def _get_model(self):
        """Lazy-load Vertex AI Pro model with Brain tools."""
        if self._model is None:
            try:
                import vertexai
                from vertexai.generative_models import GenerativeModel, GenerationConfig

                tools = _build_brain_tools()
                if not tools:
                    logger.warning("Brain tools not available - staying in probe mode")
                    return None

                vertexai.init(project=self.project, location=self.location)

                self._model = GenerativeModel(
                    self.model_name,
                    tools=[tools],
                    generation_config=GenerationConfig(
                        temperature=0.8,
                        top_p=0.95,
                    ),
                    system_instruction=BRAIN_SYSTEM_PROMPT,
                )
                self._llm_available = True
                logger.info(f"Brain LLM initialized: {self.model_name}")

            except Exception as e:
                logger.warning(f"Vertex AI not available: {e}. Brain stays in probe mode.")
                self._model = None

        return self._model

    # =========================================================================
    # Event Processing
    # =========================================================================

    async def process_event(self, event_id: str) -> None:
        """
        Process an event. Reads from Redis, decides next action, writes back.
        
        Includes deduplication: if another active event exists for the same
        service, close this one as a duplicate.
        """
        event = await self.blackboard.get_event(event_id)
        if not event:
            logger.warning(f"Event {event_id} not found")
            return

        # Dedup: if this is a new event (no turns yet), check for existing active events
        # on the same service. Close as duplicate if one already exists.
        if not event.conversation:
            active_ids = await self.blackboard.get_active_events()
            for eid in active_ids:
                if eid == event_id:
                    continue
                existing = await self.blackboard.get_event(eid)
                if (existing
                        and existing.service == event.service
                        and existing.conversation  # has turns = being worked on
                        and existing.status.value in ("active", "new", "deferred")):
                    logger.info(
                        f"Closing duplicate event {event_id} -- "
                        f"existing event {eid} already handling {event.service}"
                    )
                    await self._close_and_broadcast(
                        event_id,
                        f"Duplicate: merged with existing event {eid} for {event.service}.",
                    )
                    return

        # Circuit breaker: max turns
        if len(event.conversation) >= MAX_TURNS_PER_EVENT:
            logger.warning(f"Event {event_id} hit max turns ({MAX_TURNS_PER_EVENT})")
            await self._close_and_broadcast(
                event_id,
                f"TIMEOUT: Event exceeded {MAX_TURNS_PER_EVENT} turns. Force closed.",
            )
            return

        # Circuit breaker: max duration
        if event.conversation:
            first_turn_time = event.conversation[0].timestamp
            if time.time() - first_turn_time > MAX_EVENT_DURATION_SECONDS:
                logger.warning(f"Event {event_id} exceeded max duration")
                await self._close_and_broadcast(
                    event_id,
                    f"TIMEOUT: Event exceeded {MAX_EVENT_DURATION_SECONDS}s. Force closed.",
                )
                return

        # Try LLM processing, fall back to probe mode
        model = await self._get_model()
        if model:
            await self._process_with_llm(event_id, event, model)
        else:
            # PROBE MODE fallback (no LLM available)
            turn = ConversationTurn(
                turn=len(event.conversation) + 1,
                actor="brain",
                action="triage",
                thoughts=f"PROBE: Brain received event {event_id} for service {event.service}. "
                         f"Source: {event.source}. Reason: {event.event.reason}. "
                         f"Conversation has {len(event.conversation)} turns.",
            )
            await self.blackboard.append_turn(event_id, turn)
            logger.info(f"Brain processed event {event_id} (probe mode)")

    async def _process_with_llm(
        self,
        event_id: str,
        event: EventDocument,
        model,
    ) -> None:
        """Process event using Vertex AI LLM function calling."""
        # Build prompt from event context
        prompt = await self._build_event_prompt(event)

        try:
            response = await asyncio.to_thread(
                model.generate_content, prompt
            )

            # Check for function call
            if (response.candidates
                    and response.candidates[0].content.parts):
                part = response.candidates[0].content.parts[0]

                if hasattr(part, "function_call") and part.function_call:
                    fc = part.function_call
                    func_name = fc.name
                    func_args = dict(fc.args) if fc.args else {}
                    logger.info(f"Brain LLM decision for {event_id}: {func_name}({func_args})")
                    await self._execute_function_call(event_id, func_name, func_args)
                    return

                # Text-only response (no function call) -- treat as brain thoughts
                if hasattr(part, "text") and part.text:
                    turn = ConversationTurn(
                        turn=len(event.conversation) + 1,
                        actor="brain",
                        action="think",
                        thoughts=part.text,
                    )
                    await self.blackboard.append_turn(event_id, turn)
                    await self._broadcast_turn(event_id, turn)
                    logger.info(f"Brain LLM produced thoughts (no function call) for {event_id}")
                    return

            logger.warning(f"Brain LLM returned empty response for {event_id}")

        except Exception as e:
            logger.error(f"Brain LLM call failed for {event_id}: {e}", exc_info=True)
            turn = ConversationTurn(
                turn=len(event.conversation) + 1,
                actor="brain",
                action="error",
                thoughts=f"LLM call failed: {str(e)[:200]}",
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)

    async def _build_event_prompt(self, event: EventDocument) -> str:
        """Serialize event document as prompt text for the LLM, including service metadata."""
        lines = [
            f"Event ID: {event.id}",
            f"Source: {event.source}",
            f"Service: {event.service}",
            f"Status: {event.status.value}",
            f"Reason: {event.event.reason}",
            f"Evidence: {event.event.evidence}",
            f"Time: {event.event.timeDate}",
        ]

        # Include service metadata so the LLM knows the GitOps coordinates
        svc = await self.blackboard.get_service(event.service)
        if svc:
            lines.append("")
            lines.append("Service Metadata:")
            lines.append(f"  Version: {svc.version}")
            if svc.gitops_repo:
                lines.append(f"  GitOps Repo: {svc.gitops_repo}")
            if svc.gitops_repo_url:
                lines.append(f"  Repo URL: {svc.gitops_repo_url}")
            if svc.gitops_helm_path:
                lines.append(f"  Helm Values Path: {svc.gitops_helm_path}")
            if svc.replicas_ready is not None:
                lines.append(f"  Replicas: {svc.replicas_ready}/{svc.replicas_desired}")
            lines.append(f"  CPU: {svc.metrics.cpu:.1f}%")
            lines.append(f"  Memory: {svc.metrics.memory:.1f}%")

        lines.extend(["", "Conversation so far:"])

        if not event.conversation:
            lines.append("(No turns yet -- this is a new event. Triage it.)")
        else:
            for turn in event.conversation:
                lines.append(f"  Turn {turn.turn} [{turn.actor}.{turn.action}]:")
                if turn.thoughts:
                    lines.append(f"    Thoughts: {turn.thoughts}")
                if turn.result:
                    lines.append(f"    Result: {turn.result}")
                if turn.plan:
                    lines.append(f"    Plan: {turn.plan[:500]}")
                if turn.evidence:
                    lines.append(f"    Evidence: {turn.evidence}")
                if turn.requestingAgent:
                    lines.append(f"    Requesting agent: {turn.requestingAgent}")
                if turn.pendingApproval:
                    lines.append(f"    PENDING USER APPROVAL")
                if turn.waitingFor:
                    lines.append(f"    Waiting for: {turn.waitingFor}")

        lines.append("")
        lines.append("What is the next action? Call one of your functions.")

        return "\n".join(lines)

    # =========================================================================
    # Function Call Dispatcher
    # =========================================================================

    async def _execute_function_call(
        self,
        event_id: str,
        function_name: str,
        args: dict,
    ) -> None:
        """
        Execute an LLM function call. Maps function names to real operations.
        
        Agent dispatch uses asyncio.create_task for non-blocking execution.
        Other functions (close, approve, verify) are fast Redis writes.
        """
        if function_name in ("select_agent", "ask_agent_for_state"):
            agent_name = args.get("agent_name", "")
            task = args.get("task_instruction", "") or args.get("question", "")

            # Duplicate task prevention
            if event_id in self._active_tasks and not self._active_tasks[event_id].done():
                logger.info(f"Task already active for {event_id}, skipping dispatch")
                return

            # Recursion guard
            depth = self._routing_depth.get(event_id, 0) + 1
            if depth > 15:
                logger.warning(f"Event {event_id} hit routing depth limit (5)")
                await self._close_and_broadcast(event_id, "Agent routing loop detected. Force closed.")
                return
            self._routing_depth[event_id] = depth

            # Write event MD to agent volume
            await self.write_event_to_volume(event_id, agent_name)

            # Append brain routing turn + broadcast
            action = "route" if function_name == "select_agent" else "route"
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action=action,
                thoughts=f"Routing to {agent_name}: {task}",
                selectedAgents=[agent_name],
                taskForAgent={"agent": agent_name, "instruction": task},
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)

            # Broadcast the event MD as attachment
            event = await self.blackboard.get_event(event_id)
            if event and self.broadcast:
                await self.broadcast({
                    "type": "attachment",
                    "event_id": event_id,
                    "actor": "brain",
                    "filename": f"event-{event_id}.md",
                    "content": self._event_to_markdown(event),
                })

            # Launch agent task (non-blocking)
            agent = self.agents.get(agent_name)
            if agent:
                event_md_path = f"./events/event-{event_id}.md"
                task_coro = self._run_agent_task(event_id, agent_name, agent, task, event_md_path)
                self._active_tasks[event_id] = asyncio.create_task(task_coro)
            else:
                logger.error(f"Agent '{agent_name}' not found in agents dict")

        elif function_name == "close_event":
            summary = args.get("summary", "Event closed.")
            await self._close_and_broadcast(event_id, summary)

        elif function_name == "request_user_approval":
            plan_summary = args.get("plan_summary", "")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="request_approval",
                thoughts=plan_summary,
                pendingApproval=True,
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            # Update event status
            event = await self.blackboard.get_event(event_id)
            if event:
                event.status = EventStatus.WAITING_APPROVAL
                await self.blackboard.redis.set(
                    f"{self.blackboard.EVENT_PREFIX}{event_id}",
                    json.dumps(event.model_dump()),
                )

        elif function_name == "re_trigger_aligner":
            service = args.get("service", "")
            condition = args.get("check_condition", "")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="verify",
                thoughts=f"Re-triggering Aligner to check: {condition}",
                waitingFor="aligner",
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)

        elif function_name == "wait_for_verification":
            condition = args.get("condition", "")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="verify",
                thoughts=f"Waiting for verification: {condition}",
                waitingFor="aligner",
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)

        elif function_name == "defer_event":
            reason = args.get("reason", "Deferred by Brain")
            delay = max(30, min(int(args.get("delay_seconds", 60)), 300))  # Clamp 30-300s
            defer_until = time.time() + delay
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="defer",
                thoughts=f"Deferring event for {delay}s: {reason}",
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            # Update event status + store defer_until timestamp
            event = await self.blackboard.get_event(event_id)
            if event:
                event.status = EventStatus.DEFERRED
                await self.blackboard.redis.set(
                    f"{self.blackboard.EVENT_PREFIX}{event_id}",
                    json.dumps(event.model_dump()),
                )
                # Store defer timestamp for the event loop to check
                await self.blackboard.redis.set(
                    f"{self.blackboard.EVENT_PREFIX}{event_id}:defer_until",
                    str(defer_until),
                    ex=delay + 60,  # Auto-expire the key after delay + buffer
                )
            logger.info(f"Event {event_id} deferred for {delay}s: {reason}")

        else:
            logger.warning(f"Unknown function call: {function_name}")

    # =========================================================================
    # Agent Task Runner (non-blocking via create_task)
    # =========================================================================

    async def _run_agent_task(
        self,
        event_id: str,
        agent_name: str,
        agent: Any,
        task: str,
        event_md_path: str,
    ) -> None:
        """
        Run agent.process() with progress streaming. Non-blocking via create_task.
        
        On completion: appends result turn, broadcasts, triggers next Brain decision.
        """
        try:
            async def on_progress(progress_data: dict) -> None:
                """Broadcast agent progress to UI in real-time."""
                if self.broadcast:
                    await self.broadcast({
                        "type": "progress",
                        "event_id": event_id,
                        "actor": agent_name,
                        "message": progress_data.get("message", ""),
                    })

            logger.info(f"Agent task started: {agent_name} for {event_id}")
            result = await agent.process(
                event_id=event_id,
                task=task,
                event_md_path=event_md_path,
                on_progress=on_progress,
            )

            # Parse result -- check for structured responses (question, agent_busy)
            try:
                result_data = json.loads(result)
                if isinstance(result_data, dict):
                    if result_data.get("type") == "question":
                        turn = ConversationTurn(
                            turn=(await self._next_turn_number(event_id)),
                            actor=agent_name,
                            action="question",
                            thoughts=result_data.get("message", ""),
                            requestingAgent=result_data.get("requestingAgent", ""),
                        )
                        await self.blackboard.append_turn(event_id, turn)
                        await self._broadcast_turn(event_id, turn)
                        await self.process_event(event_id)
                        return

                    if result_data.get("type") == "agent_busy":
                        # Agent exhausted retries -- return to Brain for decision
                        turn = ConversationTurn(
                            turn=(await self._next_turn_number(event_id)),
                            actor=agent_name,
                            action="busy",
                            thoughts=result_data.get("message", f"{agent_name} is busy after retries"),
                        )
                        await self.blackboard.append_turn(event_id, turn)
                        await self._broadcast_turn(event_id, turn)
                        logger.warning(f"Agent {agent_name} busy for {event_id}, returning to Brain")
                        # Let Brain decide: close, wait, or try another agent
                        await self.process_event(event_id)
                        return
            except (json.JSONDecodeError, TypeError):
                pass  # Not a JSON question, treat as regular result

            # Handle empty result as an error (Gemini CLI returned no output)
            result_str = str(result).strip() if result else ""
            if not result_str:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor=agent_name,
                    action="error",
                    thoughts="Agent returned empty response (Gemini CLI produced no output). May need retry.",
                )
                await self.blackboard.append_turn(event_id, turn)
                await self._broadcast_turn(event_id, turn)
                logger.warning(f"Agent {agent_name} returned EMPTY result for {event_id}")
                await self.process_event(event_id)
                return

            # Append agent result turn
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor=agent_name,
                action="execute",
                result=result_str[:2000],  # Cap result length
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            logger.info(f"Agent task completed: {agent_name} for {event_id}")

            # Trigger next Brain decision
            await self.process_event(event_id)

        except Exception as e:
            logger.error(f"Agent task failed: {agent_name} for {event_id}: {e}", exc_info=True)
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor=agent_name,
                action="error",
                thoughts=f"Agent execution failed: {str(e)[:300]}",
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)

        finally:
            # Clean up active task tracking
            self._active_tasks.pop(event_id, None)

    # =========================================================================
    # Broadcast Helpers
    # =========================================================================

    async def _broadcast_turn(self, event_id: str, turn: ConversationTurn) -> None:
        """Broadcast a conversation turn to connected UI clients."""
        if self.broadcast:
            await self.broadcast({
                "type": "turn",
                "event_id": event_id,
                "turn": turn.model_dump(),
            })

    async def _close_and_broadcast(self, event_id: str, summary: str) -> None:
        """Close an event and broadcast the closure to UI."""
        await self.blackboard.close_event(event_id, summary)
        self._routing_depth.pop(event_id, None)
        if self.broadcast:
            await self.broadcast({
                "type": "event_closed",
                "event_id": event_id,
                "summary": summary,
            })

    # =========================================================================
    # Volume Writer
    # =========================================================================

    async def write_event_to_volume(
        self, event_id: str, agent_name: str
    ) -> None:
        """Serialize event document as MD file to agent's volume, enriched with GitOps metadata."""
        event = await self.blackboard.get_event(event_id)
        if not event:
            return

        # Enrich with GitOps metadata from Blackboard
        service_meta = await self.blackboard.get_service(event.service)

        base_path = VOLUME_PATHS.get(agent_name)
        if not base_path:
            logger.warning(f"No volume path for agent: {agent_name}")
            return

        events_dir = Path(base_path) / "events"
        events_dir.mkdir(parents=True, exist_ok=True)

        file_path = events_dir / f"event-{event_id}.md"
        content = self._event_to_markdown(event, service_meta)
        file_path.write_text(content)
        logger.debug(f"Wrote event MD to {file_path}")

    def _event_to_markdown(self, event: EventDocument, service_meta=None) -> str:
        """Convert event document to readable Markdown, enriched with service metadata."""
        lines = [
            f"# Event: {event.id}",
            f"",
            f"- **Source:** {event.source}",
            f"- **Service:** {event.service}",
            f"- **Status:** {event.status.value}",
            f"- **Reason:** {event.event.reason}",
            f"- **Evidence:** {event.event.evidence}",
            f"- **Time:** {event.event.timeDate}",
        ]

        # Include GitOps metadata so agents know where to make changes
        if service_meta:
            lines.append(f"")
            lines.append(f"## Service Metadata")
            lines.append(f"- **Version:** {service_meta.version}")
            if service_meta.gitops_repo:
                lines.append(f"- **GitOps Repo:** {service_meta.gitops_repo}")
            if service_meta.gitops_repo_url:
                lines.append(f"- **Repo URL:** {service_meta.gitops_repo_url}")
            if service_meta.gitops_helm_path:
                lines.append(f"- **Helm Values Path:** {service_meta.gitops_helm_path}")
            if service_meta.replicas_ready is not None:
                lines.append(f"- **Replicas:** {service_meta.replicas_ready}/{service_meta.replicas_desired}")
            lines.append(f"- **CPU:** {service_meta.metrics.cpu:.1f}%")
            lines.append(f"- **Memory:** {service_meta.metrics.memory:.1f}%")
            lines.append(f"- **Error Rate:** {service_meta.metrics.error_rate:.2f}%")

        lines.extend([
            f"",
            f"## Conversation",
            f"",
        ])
        for turn in event.conversation:
            lines.append(f"### Turn {turn.turn} - {turn.actor} ({turn.action})")
            if turn.thoughts:
                lines.append(f"**Thoughts:** {turn.thoughts}")
            if turn.result:
                lines.append(f"**Result:** {turn.result}")
            if turn.plan:
                lines.append(f"**Plan:**\n{turn.plan}")
            if turn.evidence:
                lines.append(f"**Evidence:** {turn.evidence}")
            if turn.selectedAgents:
                lines.append(f"**Selected Agents:** {', '.join(turn.selectedAgents)}")
            if turn.executed is not None:
                lines.append(f"**Executed:** {turn.executed}")
            if turn.pendingApproval:
                lines.append(f"**Pending Approval:** YES")
            if turn.waitingFor:
                lines.append(f"**Waiting For:** {turn.waitingFor}")
            lines.append("")

        return "\n".join(lines)

    # =========================================================================
    # Event Loop
    # =========================================================================

    async def _cleanup_stale_events(self) -> None:
        """
        Startup cleanup: close any stale active events from a previous Brain instance.
        
        On restart, active events may be orphaned (agent tasks were in-flight,
        WebSocket connections dropped). Close them so they don't block the system.
        """
        active_ids = await self.blackboard.get_active_events()
        if not active_ids:
            return

        stale_count = 0
        for eid in active_ids:
            event = await self.blackboard.get_event(eid)
            if not event:
                # Orphaned ID in active set -- remove it
                await self.blackboard.redis.srem(self.blackboard.EVENT_ACTIVE, eid)
                stale_count += 1
                continue

            # Close events that have turns (were being processed) -- they're stale from the previous instance
            if event.conversation:
                await self.blackboard.close_event(
                    eid,
                    f"Stale: closed on Brain restart. Previous instance was processing this event. "
                    f"Last turn: {event.conversation[-1].actor}.{event.conversation[-1].action}",
                )
                stale_count += 1
            else:
                # No turns yet -- re-queue for fresh processing
                await self.blackboard.redis.lpush(self.blackboard.EVENT_QUEUE, eid)
                logger.info(f"Re-queued untouched event {eid} for fresh processing")

        if stale_count:
            logger.info(f"Startup cleanup: closed {stale_count} stale events from previous instance")

    async def start_event_loop(self) -> None:
        """
        Background event loop: dequeue new events + check for user approvals.
        
        Agent responses are handled via _run_agent_task callbacks (non-blocking).
        No agent response scanning needed -- WebSocket agents complete asynchronously.
        """
        self._running = True

        # Startup: clean up stale events from previous Brain instance
        await self._cleanup_stale_events()

        logger.info("Brain event loop started (WebSocket mode)")

        while self._running:
            try:
                # 0. Run Aligner verification checks (for events waiting on aligner confirmation)
                aligner = self.agents.get("_aligner")
                if aligner and hasattr(aligner, "check_active_verifications"):
                    await aligner.check_active_verifications()

                # 1. Check for new events on the queue
                event_id = await self.blackboard.dequeue_event()
                if event_id:
                    logger.info(f"New event from queue: {event_id}")
                    await self.process_event(event_id)

                # 2. Scan active events for user approvals + deferred events
                active = await self.blackboard.get_active_events()
                for eid in active:
                    # Skip events with active agent tasks
                    if eid in self._active_tasks and not self._active_tasks[eid].done():
                        continue

                    event = await self.blackboard.get_event(eid)
                    if not event or not event.conversation:
                        continue

                    # Check if event is deferred -- skip until delay expires
                    if event.status == EventStatus.DEFERRED:
                        defer_key = f"{self.blackboard.EVENT_PREFIX}{eid}:defer_until"
                        defer_until = await self.blackboard.redis.get(defer_key)
                        if defer_until and time.time() < float(defer_until):
                            continue  # Still deferred, skip
                        # Delay expired -- re-activate and process
                        event.status = EventStatus.ACTIVE
                        await self.blackboard.redis.set(
                            f"{self.blackboard.EVENT_PREFIX}{eid}",
                            json.dumps(event.model_dump()),
                        )
                        await self.blackboard.redis.delete(defer_key)
                        logger.info(f"Deferred event {eid} re-activated")
                        await self.process_event(eid)
                        continue

                    last_turn = event.conversation[-1]
                    # Re-process if:
                    # 1. User approved or Aligner confirmed
                    # 2. Agent completed (last turn from agent, no active task) -- pick up stalled events
                    if last_turn.actor in ("user", "aligner") and last_turn.action in ("approve", "reject", "confirm", "message"):
                        logger.info(f"User/Aligner action on event {eid}: {last_turn.actor}.{last_turn.action}")
                        await self.process_event(eid)
                    elif last_turn.actor in ("architect", "sysadmin", "developer") and last_turn.action not in ("busy",):
                        # Agent completed but Brain hasn't continued -- re-process
                        logger.info(f"Resuming stalled event {eid}: agent {last_turn.actor} completed, Brain continuing")
                        await self.process_event(eid)

            except Exception as e:
                logger.error(f"Brain event loop error: {e}", exc_info=True)
                await asyncio.sleep(2)

    async def stop_event_loop(self) -> None:
        """Stop the event loop."""
        self._running = False
        logger.info("Brain event loop stopped")

    # =========================================================================
    # Helpers
    # =========================================================================

    async def _next_turn_number(self, event_id: str) -> int:
        """Get the next turn number for an event."""
        event = await self.blackboard.get_event(event_id)
        if event:
            return len(event.conversation) + 1
        return 1
