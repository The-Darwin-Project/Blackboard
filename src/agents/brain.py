# BlackBoard/src/agents/brain.py
# @ai-rules:
# 1. [Constraint]: ALL decision logic in BRAIN_SYSTEM_PROMPT + function declarations. Python = plumbing only.
# 2. [Pattern]: process_event -> _process_event_inner with per-event asyncio.Lock prevents concurrent calls.
# 3. [Pattern]: MessageStatus protocol: SENT -> DELIVERED (Brain scanned) -> EVALUATED (LLM processed).
# 4. [Gotcha]: turn_snapshot captures len(conversation) BEFORE LLM call. mark_turns_evaluated uses this scope.
# 5. [Gotcha]: _waiting_for_user is cleared by main.py WS handler AND queue.py REST endpoints (clear_waiting), not by Brain internally.
# 6. [Pattern]: Bidirectional agent status: routing_turn_num tracks brain.route -> DELIVERED on first progress -> EVALUATED on completion.
# 7. [Pattern]: Temporal memory: _journal_cache (60s TTL) + _get_journal_cached(). Invalidated in _close_and_broadcast().
# 8. [Pattern]: _event_to_markdown is @staticmethod -- called from both instance methods and queue.py report endpoint.
# 9. [Constraint]: defer_event is blocked when _waiting_for_user -- prevents defer→re-activate→close leak.
# 10. [Constraint]: Event loop has_unread + deferred re-activation paths skip processing when _waiting_for_user.
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

from ..models import ConversationTurn, EventDocument, EventStatus, MessageStatus, PlanAction, PlanCreate, PlanStatus

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

# =============================================================================
# Brain System Prompt - THIS IS THE DECISION ENGINE
# =============================================================================

BRAIN_SYSTEM_PROMPT = """You are the Brain orchestrator of Project Darwin, an autonomous cloud operations system.

You coordinate AI agents via a shared conversation queue:
- **Architect**: Reviews codebases, analyzes topology, produces Markdown plans. NEVER executes. Use for: planning, code review, design decisions.
- **sysAdmin**: Executes GitOps changes (Helm values), investigates K8s issues via kubectl. Use for: scaling, investigation, infrastructure changes.
- **Developer**: A pair programming team, NOT a single agent. When you route to "developer", two agents work concurrently:
  - **Developer**: Implements source code changes -- writes code, commits, pushes.
  - **QE**: Independently verifies quality -- writes tests, checks for regressions, uses Playwright for UI verification.
  - A **Flash Manager** moderates the pair: reviews both outputs, triggers fix/verify rounds if needed.
  - You route to "developer" as a single unit. The pair coordination is automatic and invisible to you.
  - Use for: adding features, fixing bugs, reviewing PR/MRs, modifying application code. QE verification is built-in.

The Developer+QE pair tools:
- Developer: git, file system (code implementation)
- QE: git, file system, Playwright headless browser (UI screenshots, browser tests), pytest, curl
- Both share the same workspace and see each other's code changes in real-time

## Your Job
1. Read the event (anomaly or user request) and its conversation history.
2. Decide the NEXT action by calling ONE of your available functions.
3. You are called repeatedly as the conversation progresses. Each call, you see the full history and decide the next step.

## Decision Guidelines
- For infrastructure anomalies (high CPU, pod issues): start with sysAdmin to investigate, then decide action [see §Cynefin: CLEAR/COMPLICATED].
- For user feature requests: start with Architect to plan, then Developer to implement [see §Cynefin: COMPLEX].
- For scaling/config changes: sysAdmin can handle directly via GitOps [see §Execution Method].
- Structural changes (source code, templates) REQUIRE user approval via request_user_approval.
- Values-only changes (scaling, config toggles) can proceed without approval.
- After execution, verify the change took effect using the correct method [see §Post-Execution].
- Before acting on anomalies, check if related events explain the issue [see §Cross-Event Awareness].
- When the issue is resolved and verified, close the event with a summary [see §When to Close].
- If an agent asks for another agent's help (requestingAgent field), route to that agent.
- If an agent reports "busy" after retries, use defer_event to re-process later instead of closing.

## Agent Recommendations
- When an agent's response includes an explicit recommendation or unresolved issue, you MUST either:
  1. Act on it immediately (route to the recommended agent), OR
  2. Use wait_for_user to summarize findings and ask if the user wants you to proceed.
- NEVER silently drop an agent's recommendation.

## Wait-for-User Protocol
- After calling wait_for_user OR request_user_approval, the system automatically pauses the event until the user responds.
- Do NOT call defer_event after wait_for_user or request_user_approval. The wait is handled by the system.
- The event will resume ONLY when the user sends a message, approves, or rejects.
- NEVER defer while waiting for user input. The system handles the pause automatically.

## Execution Method
- ALL infrastructure changes MUST go through GitOps: clone the target repo, modify values.yaml, commit, push. ArgoCD syncs the change.
- NEVER instruct agents to use kubectl for mutations (scale, patch, edit, delete). kubectl is for investigation ONLY (get, list, describe, logs).
- When asking sysAdmin to scale, say: "modify replicaCount in helm/values.yaml via GitOps" not "scale the deployment."
- Agents should ONLY modify EXISTING values in Helm charts. If a new feature is needed (HPA, PDB, etc.), route to Architect for planning first.

## Post-Execution: When to Close vs Verify
- After a **code change** (developer pushes a commit with SHA): wait for CI/CD, then route sysAdmin to verify the pod's image tag matches the commit SHA.
- After a **metric-observable infrastructure change** (scaling replicas, adjusting resource limits): use re_trigger_aligner to verify the new state.
- After a **non-metric config change** (removing secrets, updating annotations, labels, imagePullSecrets): route sysAdmin to verify via kubectl/oc (check events, pod YAML). Do NOT use re_trigger_aligner -- these changes are not observable via metrics.
- re_trigger_aligner is ONLY for metric-observable changes (replicas, CPU, memory).

## When to Close
Check the event **source** field in the prompt header before closing:
- **source: aligner** (autonomous detection) -- close after metric/state verification. No user involved.
- **source: chat** (user-initiated request) -- the user is in the conversation. ALWAYS use wait_for_user before closing: "The change has been deployed and verified. Please test and confirm it works as expected, or let me know if adjustments are needed." Close ONLY after the user confirms satisfaction or explicitly says to close.
- This applies even after successful sysAdmin verification. The user initiated the request -- they get the final word.

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
- ALWAYS verify after execution using the appropriate method (see §Post-Execution)

## GitOps Context
Services self-describe their GitOps coordinates (repo, helm path) via telemetry.
When checking GitOps sync status, instruct sysAdmin to discover the GitOps tooling namespace first (e.g., search for ArgoCD or Flux namespaces) rather than assuming a specific namespace.

## Cross-Event Awareness
Before acting on infrastructure anomalies, check the "Related Active Events" and "Recently Closed Events" sections in the prompt.
- If a related ACTIVE event shows a deployment or code change in progress (developer.execute, sysadmin.execute), use defer_event to wait for stabilization.
- If the "Recently Closed Events" show you JUST scaled this service (within 5 minutes), and the current event is "over-provisioned," that is expected post-scaling normalization -- defer for 5 minutes.
- If the "Recently Closed Events" show a PATTERN of repeated same-reason events (3+ closures of the same type), investigate the root cause instead of applying the same fix again.
- For "over-provisioned" events: low metrics are the PROBLEM, not a sign of resolution. Route to sysAdmin to scale down via GitOps unless actively deferring per the rules above.

## Aligner Observations
The Aligner reports what it observes in natural language with actual metric values.
- For anomaly events (high CPU, high memory, high error rate): if latest metrics are below thresholds, close the event.
- For "over-provisioned" events: low metrics mean the service has too many replicas. Route to sysAdmin to reduce replicas. Do NOT close just because metrics are low.
- The Aligner does not make decisions -- you do. It reports, you act.

## Architecture Awareness
Your prompt includes an "Architecture Diagram (Mermaid)" section showing ALL services, their health, metrics, and dependency edges. USE this diagram actively:
- When routing tasks, include relevant architectural context in the task_instruction (e.g., "darwin-store depends on postgres via SQL; postgres is currently at 90% CPU -- investigate if this is the root cause").
- When requesting user approval, describe the impact on connected services (e.g., "Scaling darwin-store will increase load on postgres which is already at high CPU").
- When triaging anomalies, check if upstream/downstream services in the diagram are also degraded -- a root cause may be in a dependency, not the alerting service itself.
- When closing events, summarize the architectural context that informed your decision.
"""

# Circuit breaker limits
MAX_TURNS_PER_EVENT = 30
MAX_EVENT_DURATION_SECONDS = 2700  # 45 minutes

# Volume mount paths (must match Helm deployment.yaml)
VOLUME_PATHS = {
    "architect": "/data/gitops-architect",
    "sysadmin": "/data/gitops-sysadmin",
    "developer": "/data/gitops-developer",
    "qe": "/data/gitops-qe",
}


def _build_brain_tools():
    """Build google-genai function declarations for Brain's available actions."""
    try:
        from google.genai import types

        select_agent = types.FunctionDeclaration(
            name="select_agent",
            description="Route work to an agent. Use this to assign a task to Architect, sysAdmin, or Developer.",
            parameters_json_schema={
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

        close_event = types.FunctionDeclaration(
            name="close_event",
            description="Close the event as resolved. Use when the issue is fixed and verified, or the request is complete.",
            parameters_json_schema={
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

        request_user_approval = types.FunctionDeclaration(
            name="request_user_approval",
            description="Pause and ask the user to approve a plan. Use for structural changes (source code, templates).",
            parameters_json_schema={
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

        re_trigger_aligner = types.FunctionDeclaration(
            name="re_trigger_aligner",
            description="Ask the Aligner to verify that a change took effect (e.g., replicas increased, CPU normalized).",
            parameters_json_schema={
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

        ask_agent_for_state = types.FunctionDeclaration(
            name="ask_agent_for_state",
            description="Ask an agent for information (e.g., ask sysAdmin for kubectl logs, pod status).",
            parameters_json_schema={
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

        wait_for_verification = types.FunctionDeclaration(
            name="wait_for_verification",
            description="Mark that you are waiting for the Aligner to confirm a state change.",
            parameters_json_schema={
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

        defer_event = types.FunctionDeclaration(
            name="defer_event",
            description="Defer an event for later processing. Use when an agent is busy, the issue is not urgent, or you want to retry after a cooldown period.",
            parameters_json_schema={
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

        wait_for_user = types.FunctionDeclaration(
            name="wait_for_user",
            description="Signal that the current question is answered but agent recommendations exist. "
                        "Summarize findings and available next actions for the user.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "summary": {
                        "type": "string",
                        "description": "Summary of findings and available actions",
                    },
                },
                "required": ["summary"],
            },
        )

        lookup_service = types.FunctionDeclaration(
            name="lookup_service",
            description="Look up a service's GitOps metadata from telemetry data. Returns repo URL, helm path, version, replicas, and current metrics. Use this BEFORE routing to an agent when you need a service's repository URL or deployment details.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Service name to look up (e.g., 'darwin-store')",
                    },
                },
                "required": ["service_name"],
            },
        )

        lookup_journal = types.FunctionDeclaration(
            name="lookup_journal",
            description="Look up the ops journal for any service. Returns recent event history "
                        "(closures, scaling actions, fixes). Use to check what happened recently "
                        "to a service or its dependencies before making decisions.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "service_name": {
                        "type": "string",
                        "description": "Service name to look up (e.g., 'darwin-store', 'postgres')",
                    },
                },
                "required": ["service_name"],
            },
        )

        consult_deep_memory = types.FunctionDeclaration(
            name="consult_deep_memory",
            description="Search operational history for similar past events. Returns symptoms, root causes, and fixes from past incidents. Use before acting on unfamiliar issues.",
            parameters_json_schema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "What to search for (e.g., 'high CPU on darwin-store')",
                    },
                },
                "required": ["query"],
            },
        )

        return types.Tool(function_declarations=[
            select_agent,
            close_event,
            request_user_approval,
            re_trigger_aligner,
            ask_agent_for_state,
            wait_for_verification,
            wait_for_user,
            defer_event,
            lookup_service,
            lookup_journal,
            consult_deep_memory,
        ])

    except ImportError:
        logger.warning("google-genai not available - Brain running in probe mode")
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
        self._client = None
        self._tools = None
        self._llm_available = False
        self._active_tasks: dict[str, asyncio.Task] = {}  # event_id -> running task
        self._routing_depth: dict[str, int] = {}  # event_id -> recursion counter
        # Per-agent locks -- prevents concurrent dispatch to the same agent
        from collections import defaultdict
        self._agent_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Per-event locks -- prevents concurrent process_event calls for same event
        self._event_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Plan Layer: track event_id -> plan_id so ghost nodes appear on the graph
        self._event_plans: dict[str, str] = {}  # event_id -> plan_id
        # Wait-for-user state: events where LLM called wait_for_user
        self._waiting_for_user: set[str] = set()
        # Last process_event timestamp per event (for idle safety net)
        self._last_processed: dict[str, float] = {}
        # Journal cache: avoid LRANGE per prompt build (60s TTL, invalidated on close)
        self._journal_cache: dict[str, tuple[float, list[str]]] = {}
        # LLM config from environment
        self.project = os.getenv("GCP_PROJECT", "")
        self.location = os.getenv("GCP_LOCATION", "global")
        self.model_name = os.getenv("VERTEX_MODEL_PRO", "gemini-3-pro-preview")
        logger.info(f"Brain initialized (project={self.project}, model={self.model_name}, agents={list(self.agents.keys())})")

    JOURNAL_CACHE_TTL = 60  # seconds

    async def _get_journal_cached(self, service: str) -> list[str]:
        """Get journal with 60s in-memory cache. Invalidated on close_event."""
        now = time.time()
        cached = self._journal_cache.get(service)
        if cached and (now - cached[0]) < self.JOURNAL_CACHE_TTL:
            return cached[1]
        entries = await self.blackboard.get_journal(service)
        self._journal_cache[service] = (now, entries)
        return entries

    async def _get_client(self):
        """Lazy-load google-genai Client with Brain tools."""
        if self._client is None:
            try:
                from google import genai

                tools = _build_brain_tools()
                if not tools:
                    logger.warning("Brain tools not available - staying in probe mode")
                    return None

                self._client = genai.Client(
                    vertexai=True,
                    project=self.project,
                    location=self.location,
                )
                self._tools = tools
                self._llm_available = True
                logger.info(f"Brain LLM initialized: {self.model_name} (google-genai)")

            except Exception as e:
                logger.warning(f"google-genai not available: {e}. Brain stays in probe mode.")
                self._client = None

        return self._client

    # =========================================================================
    # Event Processing
    # =========================================================================

    async def process_event(
        self, event_id: str, prefetched_event: Optional[EventDocument] = None,
    ) -> None:
        """
        Process an event with per-event lock to prevent concurrent calls.
        
        Args:
            event_id: Event ID to process.
            prefetched_event: If provided, skip the initial Redis GET.
                Only pass from the event loop scan where the event was
                just fetched. All other callers should use the default None.
        """
        async with self._event_locks[event_id]:
            await self._process_event_inner(event_id, prefetched_event)

    async def _process_event_inner(
        self, event_id: str, prefetched_event: Optional[EventDocument] = None,
    ) -> None:
        """
        Process an event. Reads from Redis, decides next action, writes back.
        
        Includes deduplication: if another active event exists for the same
        service, close this one as a duplicate.
        """
        self._last_processed[event_id] = time.time()

        # Use prefetched event if available (from loop scan), otherwise fetch fresh
        event = prefetched_event or await self.blackboard.get_event(event_id)
        if not event:
            logger.warning(f"Event {event_id} not found")
            return

        # CLOSED guard: skip events that were closed concurrently
        if event.status == EventStatus.CLOSED:
            logger.debug(f"Skipping closed event {event_id}")
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

        # Circuit breaker: count only agent execution turns (not brain routing, aligner, user)
        agent_turns = sum(
            1 for t in event.conversation
            if t.actor in ("architect", "sysadmin", "developer")
        )
        if agent_turns >= MAX_TURNS_PER_EVENT:
            logger.warning(f"Event {event_id} hit max agent turns ({agent_turns}/{MAX_TURNS_PER_EVENT})")
            await self._close_and_broadcast(
                event_id,
                f"TIMEOUT: Event exceeded {MAX_TURNS_PER_EVENT} agent execution turns. Force closed.",
            )
            return

        # Circuit breaker: max duration with grace period
        if event.conversation:
            first_turn_time = event.conversation[0].timestamp
            deadline = MAX_EVENT_DURATION_SECONDS

            # Grace period: if an agent just returned, give the LLM time to evaluate
            last_agent_turn = next(
                (t for t in reversed(event.conversation)
                 if t.actor in ("architect", "sysadmin", "developer")),
                None,
            )
            if last_agent_turn and (time.time() - last_agent_turn.timestamp) < 60:
                deadline += 120  # 2-minute grace for LLM evaluation

            if time.time() - first_turn_time > deadline:
                logger.warning(f"Event {event_id} exceeded max duration")
                await self._close_and_broadcast(
                    event_id,
                    f"TIMEOUT: Event exceeded {MAX_EVENT_DURATION_SECONDS}s. Force closed.",
                )
                return

        # Snapshot turn count BEFORE LLM call -- any turns appended during processing
        # (e.g., Aligner confirm arriving mid-evaluation) will have index > turn_snapshot
        # and stay SENT/DELIVERED for the next event loop iteration.
        turn_snapshot = len(event.conversation)

        # Get LLM client; fall back to probe mode if unavailable
        client = await self._get_client()
        if not client:
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
            return

        # Iterative LLM loop -- re-invokes when a tool (e.g., lookup_service)
        # returns True, meaning the LLM needs to make a follow-up decision.
        # Bounded to prevent runaway loops.
        max_llm_iterations = 5
        for iteration in range(max_llm_iterations):
            # Re-fetch event to pick up turns appended by the previous iteration
            if iteration > 0:
                event = await self.blackboard.get_event(event_id)
                if not event:
                    return
            should_continue = await self._process_with_llm(event_id, event, client)
            if not should_continue:
                break
            logger.debug(f"LLM loop iteration {iteration + 1} for {event_id} (tool requested continuation)")
        else:
            logger.warning(f"Event {event_id} hit max LLM iterations ({max_llm_iterations})")

        # After LLM loop exits -- only mark turns the Brain actually saw.
        # Turns appended during LLM processing (e.g., Aligner confirm) stay SENT/DELIVERED
        # and will trigger re-processing on the next event loop scan.
        await self.blackboard.mark_turns_evaluated(event_id, up_to_turn=turn_snapshot)
        await self._broadcast_status_update(
            event_id, "evaluated",
            turns=list(range(1, turn_snapshot + 1)),  # Scoped to snapshot, not "all"
        )

    async def _process_with_llm(
        self,
        event_id: str,
        event: EventDocument,
        client,
    ) -> bool:
        """Process event using google-genai LLM function calling.

        Returns True if the caller should re-invoke immediately (e.g., after
        a lookup_service call that needs a follow-up LLM decision).
        """
        from google.genai import types

        # Build prompt from event context
        prompt = await self._build_event_prompt(event)

        try:
            response = await client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=BRAIN_SYSTEM_PROMPT,
                    temperature=1.2,
                    top_p=0.95,
                    max_output_tokens=65000,
                    tools=[self._tools],
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                ),
            )

            # Check for function call (null-safety: can be None or [])
            if response.function_calls:
                fc = response.function_calls[0]
                func_name = fc.name
                func_args = fc.args if fc.args else {}
                logger.info(f"Brain LLM decision for {event_id}: {func_name}({func_args})")
                return await self._execute_function_call(event_id, func_name, func_args)

            # Text-only response (no function call) -- treat as brain thoughts
            if response.text:
                turn = ConversationTurn(
                    turn=len(event.conversation) + 1,
                    actor="brain",
                    action="think",
                    thoughts=response.text,
                )
                await self.blackboard.append_turn(event_id, turn)
                await self._broadcast_turn(event_id, turn)
                logger.info(f"Brain LLM produced thoughts (no function call) for {event_id}")
                return False

            logger.warning(f"Brain LLM returned empty response for {event_id}")
            return False

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
            return False

    async def _build_event_prompt(self, event: EventDocument) -> str | list:
        """Serialize event document as prompt for the LLM.

        Returns str when no images, or list[types.Part] for multimodal input.
        The google-genai SDK accepts both types in generate_content(contents=...).
        """
        lines = [
            f"Event ID: {event.id}",
            f"Source: {event.source}",
            f"Service: {event.service}",
            f"Status: {event.status.value}",
            f"Reason: {event.event.reason}",
            f"Evidence: {event.event.evidence}",
            f"Time: {event.event.timeDate}",
        ]

        # Event age (how long since first turn)
        event_created = event.conversation[0].timestamp if event.conversation else time.time()
        age_seconds = int(time.time() - event_created)
        age_min, age_sec = divmod(age_seconds, 60)
        lines.append(f"Event Age: {age_min}m {age_sec}s")

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

        # Architecture diagram: show the Brain the full topology with health,
        # metrics, and dependency edges so it can correlate issues across services
        # (e.g., darwin-store high CPU might be caused by postgres being slow).
        mermaid = ""
        try:
            mermaid = await self.blackboard.generate_mermaid()
        except Exception as e:
            logger.warning(f"Failed to generate mermaid for Brain prompt: {e}")
        if mermaid:
            lines.append("")
            lines.append("Architecture Diagram (Mermaid):")
            lines.append(mermaid)

        # Cross-event correlation: show other active events for the same service
        active_event_ids = await self.blackboard.get_active_events()
        related = []
        for eid in active_event_ids:
            if eid == event.id:
                continue
            other = await self.blackboard.get_event(eid)
            if not other:
                continue
            if other.service == event.service:
                last_action = other.conversation[-1] if other.conversation else None
                summary = f"  - {eid} ({other.source}): {other.event.reason[:100]}"
                if last_action:
                    summary += f" [last: {last_action.actor}.{last_action.action}]"
                related.append(summary)
            elif other.service == "general":
                # Check if chat events mention this service in recent turns
                for turn in other.conversation[-3:]:
                    if event.service in (turn.thoughts or "") or event.service in (turn.result or ""):
                        related.append(f"  - {eid} (chat): {other.event.reason[:100]}")
                        break

        if related:
            lines.append("")
            lines.append("Related Active Events (same service -- consider before acting):")
            lines.extend(related)

        # Recently closed events for same service (temporal memory)
        recent_closed = await self.blackboard.get_recent_closed_for_service(
            event.service, minutes=15
        )
        if recent_closed:
            lines.append("")
            lines.append("Recently Closed Events (same service, last 15 min):")
            for cid, close_time, csummary in recent_closed:
                ago = int(time.time() - close_time)
                ago_min = ago // 60
                lines.append(f"  - {cid} (closed {ago_min}m ago): {csummary}")

        # Service ops journal (persistent temporal memory)
        journal = await self._get_journal_cached(event.service)
        if journal:
            lines.append("")
            lines.append(f"Service Ops Journal (last {len(journal)} actions):")
            for entry in journal[-10:]:  # Show last 10 entries in prompt
                lines.append(f"  {entry}")
            lines.append("  (Use lookup_journal to check other services' history)")

        lines.extend(["", "Conversation so far:"])

        if not event.conversation:
            lines.append("(No turns yet -- this is a new event. Triage it.)")
        else:
            for turn in event.conversation:
                turn_ago = int(time.time() - turn.timestamp)
                if turn_ago < 60:
                    time_label = f"{turn_ago}s ago"
                elif turn_ago < 3600:
                    time_label = f"{turn_ago // 60}m {turn_ago % 60}s ago"
                else:
                    time_label = f"{turn_ago // 3600}h {(turn_ago % 3600) // 60}m ago"
                lines.append(f"  Turn {turn.turn} [{turn.actor}.{turn.action}] ({time_label}):")
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
                if turn.image:
                    lines.append(f"    [Image attached -- see below]")

        lines.append("")
        lines.append("What is the next action? Call one of your functions.")

        text_prompt = "\n".join(lines)

        # If any turn has an image, return multimodal content (text + last image)
        last_image = None
        for t in reversed(event.conversation):
            if t.image:
                last_image = t.image
                break

        if last_image:
            try:
                import base64
                from google.genai import types
                # Parse data URI: "data:image/png;base64,iVBOR..."
                header, b64data = last_image.split(",", 1)
                mime_type = header.split(":")[1].split(";")[0]
                image_bytes = base64.b64decode(b64data)
                return [
                    types.Part.from_text(text=text_prompt),
                    types.Part.from_bytes(data=image_bytes, mime_type=mime_type),
                ]
            except Exception as e:
                logger.warning(f"Failed to parse image for multimodal prompt: {e}")

        return text_prompt

    # =========================================================================
    # Function Call Dispatcher
    # =========================================================================

    async def _execute_function_call(
        self,
        event_id: str,
        function_name: str,
        args: dict,
    ) -> bool:
        """
        Execute an LLM function call. Maps function names to real operations.
        
        Returns True if the caller should re-invoke the LLM immediately
        (e.g., after lookup_service). Returns False for all other cases.
        
        Agent dispatch uses asyncio.create_task for non-blocking execution.
        Other functions (close, approve, verify) are fast Redis writes.
        """
        if function_name in ("select_agent", "ask_agent_for_state"):
            agent_name = args.get("agent_name", "")
            task = args.get("task_instruction", "") or args.get("question", "")

            # Duplicate task prevention
            if event_id in self._active_tasks and not self._active_tasks[event_id].done():
                logger.info(f"Task already active for {event_id}, skipping dispatch")
                return False

            # Recursion guard
            depth = self._routing_depth.get(event_id, 0) + 1
            if depth > 15:
                logger.warning(f"Event {event_id} hit routing depth limit (15)")
                await self._close_and_broadcast(event_id, "Agent routing loop detected. Force closed.")
                return False
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
                svc_meta = await self.blackboard.get_service(event.service)
                await self.broadcast({
                    "type": "attachment",
                    "event_id": event_id,
                    "actor": "brain",
                    "filename": f"event-{event_id}.md",
                    "content": self._event_to_markdown(event, svc_meta),
                })

            # Create a Plan (ghost node) for executing agents if none exists yet.
            # ask_agent_for_state is info-gathering only -- no plan needed.
            if function_name == "select_agent" and agent_name in ("sysadmin", "developer"):
                if event_id not in self._event_plans:
                    event = event or await self.blackboard.get_event(event_id)
                    if event:
                        await self._create_plan_for_event(event_id, event.service, task)

            # Launch agent task (non-blocking)
            agent = self.agents.get(agent_name)
            if agent:
                event_md_path = f"./events/event-{event_id}.md"
                task_coro = self._run_agent_task(
                    event_id, agent_name, agent, task, event_md_path,
                    routing_turn_num=turn.turn,
                )
                self._active_tasks[event_id] = asyncio.create_task(task_coro)
            else:
                logger.error(f"Agent '{agent_name}' not found in agents dict")
            return False

        elif function_name == "close_event":
            summary = args.get("summary", "Event closed.")
            await self._close_and_broadcast(event_id, summary)
            return False

        elif function_name == "request_user_approval":
            plan_summary = args.get("plan_summary", "")
            self._waiting_for_user.add(event_id)  # Block re-processing until user responds
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="request_approval",
                thoughts=plan_summary,
                pendingApproval=True,
                waitingFor="user",
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
                # Create Plan in the Blackboard Plan Layer (ghost node on graph)
                await self._create_plan_for_event(event_id, event.service, plan_summary)
            return False

        elif function_name == "re_trigger_aligner":
            service = args.get("service", "")
            condition = args.get("check_condition", "")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="verify",
                thoughts=f"Re-triggering Aligner to check: {condition}",
                waitingFor="aligner",
                evidence=f"target_service:{service}",  # Store target service for Aligner
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            return False

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
            return False

        elif function_name == "defer_event":
            # Guard: never defer when waiting for user response
            if event_id in self._waiting_for_user:
                logger.warning(f"Ignoring defer_event for {event_id}: waiting for user response")
                return False
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
            return False

        elif function_name == "wait_for_user":
            summary = args.get("summary", "")
            self._waiting_for_user.add(event_id)  # State flag (plumbing)
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="wait",
                thoughts=summary,
                waitingFor="user",
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            return False

        elif function_name == "lookup_service":
            service_name = args.get("service_name", "")
            svc = await self.blackboard.get_service(service_name)
            if svc:
                info_parts = [f"Service '{service_name}' metadata:"]
                info_parts.append(f"  Version: {svc.version}")
                if svc.gitops_repo:
                    info_parts.append(f"  GitOps Repo: {svc.gitops_repo}")
                if svc.gitops_repo_url:
                    info_parts.append(f"  Repo URL: {svc.gitops_repo_url}")
                if svc.gitops_helm_path:
                    info_parts.append(f"  Helm Values Path: {svc.gitops_helm_path}")
                if svc.replicas_ready is not None:
                    info_parts.append(f"  Replicas: {svc.replicas_ready}/{svc.replicas_desired}")
                info_parts.append(f"  CPU: {svc.metrics.cpu:.1f}%")
                info_parts.append(f"  Memory: {svc.metrics.memory:.1f}%")
                result_text = "\n".join(info_parts)
            else:
                # List available services to help the LLM find the right name
                known = await self.blackboard.get_services()
                result_text = f"Service '{service_name}' not found. Known services: {', '.join(sorted(known)) if known else 'none'}"

            # Append as a brain turn so the LLM sees the result in the next prompt
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="think",
                evidence=result_text,
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            # Signal caller to re-invoke LLM so it can act on the lookup result
            return True

        elif function_name == "consult_deep_memory":
            query = args.get("query", "")
            archivist = self.agents.get("_archivist_memory")
            results = []
            if archivist and hasattr(archivist, "search"):
                results = await archivist.search(query, limit=5)
            if results:
                memory_text = f"Deep memory results for '{query}':\n"
                for i, r in enumerate(results, 1):
                    p = r.get("payload", {})
                    memory_text += (
                        f"  {i}. [{p.get('service', '?')}] "
                        f"Symptom: {p.get('symptom', '?')} | "
                        f"Root cause: {p.get('root_cause', '?')} | "
                        f"Fix: {p.get('fix_action', '?')} "
                        f"(score: {r.get('score', 0):.2f})\n"
                    )
            else:
                memory_text = f"No deep memory results for '{query}'."
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="think",
                evidence=memory_text,
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            return True

        elif function_name == "lookup_journal":
            service_name = args.get("service_name", "")
            entries = await self._get_journal_cached(service_name)
            if entries:
                journal_text = f"Ops journal for {service_name} (last {len(entries)} entries):\n"
                journal_text += "\n".join(f"  {e}" for e in entries)
            else:
                journal_text = f"No ops journal entries for {service_name}."
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="think",
                evidence=journal_text,
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            return True

        else:
            logger.warning(f"Unknown function call: {function_name}")
            return False

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
        routing_turn_num: int = 0,
    ) -> None:
        """
        Run agent.process() with progress streaming. Non-blocking via create_task.
        
        On completion: appends result turn, broadcasts, triggers next Brain decision.
        Tracks bidirectional message status for the brain.route turn.
        """
        try:
            agent_acked = False  # Track first progress (= agent received task)

            async def on_progress(progress_data: dict) -> None:
                """Broadcast agent progress to UI in real-time."""
                nonlocal agent_acked
                # First progress = agent received and is working (DELIVERED)
                if not agent_acked and routing_turn_num:
                    agent_acked = True
                    await self.blackboard.mark_turn_status(
                        event_id, routing_turn_num, MessageStatus.DELIVERED
                    )
                    await self._broadcast_status_update(
                        event_id, "delivered", turns=[routing_turn_num],
                    )
                if self.broadcast:
                    await self.broadcast({
                        "type": "progress",
                        "event_id": event_id,
                        "actor": progress_data.get("actor", agent_name),
                        "message": progress_data.get("message", ""),
                    })

            logger.info(f"Agent task started: {agent_name} for {event_id}")
            # Acquire per-agent lock to prevent concurrent WS calls to the same sidecar
            async with self._agent_locks[agent_name]:
                result = await agent.process(
                    event_id=event_id,
                    task=task,
                    event_md_path=event_md_path,
                    on_progress=on_progress,
                )
            # Lock released -- Brain continues freely

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
                result=result_str[:5000],  # Cap result length
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            logger.info(f"Agent task completed: {agent_name} for {event_id}")

            # Mark routing turn as EVALUATED (agent completed its work)
            if routing_turn_num:
                await self.blackboard.mark_turn_status(
                    event_id, routing_turn_num, MessageStatus.EVALUATED
                )
                await self._broadcast_status_update(
                    event_id, "evaluated", turns=[routing_turn_num],
                )

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
            # Mark routing turn as EVALUATED so the orphaned SENT/DELIVERED turn
            # doesn't trigger the unread-message scan and re-dispatch to a failing agent.
            if routing_turn_num:
                await self.blackboard.mark_turn_status(
                    event_id, routing_turn_num, MessageStatus.EVALUATED
                )

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

    async def _broadcast_status_update(
        self, event_id: str, status: str, turns=None,
    ) -> None:
        """Broadcast message status change to UI.

        Args:
            event_id: Event ID
            status: "delivered" or "evaluated"
            turns: list of ConversationTurn objects, list of int turn numbers,
                   or None for "all"
        """
        if self.broadcast:
            if turns is None:
                turn_list = "all"
            elif turns and hasattr(turns[0], "turn"):
                turn_list = [t.turn for t in turns]
            else:
                turn_list = turns  # Already int list
            await self.broadcast({
                "type": "message_status",
                "event_id": event_id,
                "status": status,
                "turns": turn_list,
            })

    def clear_waiting(self, event_id: str) -> None:
        """Clear the wait_for_user state for an event (called when user responds)."""
        self._waiting_for_user.discard(event_id)

    async def _close_and_broadcast(self, event_id: str, summary: str) -> None:
        """Close an event and broadcast the closure to UI."""
        # Fetch event BEFORE close to get service name for journal
        event = await self.blackboard.get_event(event_id)
        await self.blackboard.close_event(event_id, summary)
        # Append to service ops journal (temporal memory)
        if event:
            turns = len(event.conversation)
            await self.blackboard.append_journal(
                event.service,
                f"{event.event.reason[:200]} -- closed in {turns} turns. {summary[:300]}"
            )
            # Invalidate journal cache for this service (immediate freshness)
            self._journal_cache.pop(event.service, None)
            # Archive to deep memory (fire-and-forget, non-blocking)
            archivist = self.agents.get("_archivist_memory")
            if archivist and hasattr(archivist, "archive_event"):
                try:
                    await archivist.archive_event(event)
                except Exception as e:
                    logger.warning(f"Deep memory archive failed (non-fatal): {e}")
        # Clean up all per-event state to prevent memory leaks
        self._routing_depth.pop(event_id, None)
        self._waiting_for_user.discard(event_id)
        self._last_processed.pop(event_id, None)
        self._event_locks.pop(event_id, None)
        # Complete any associated Plan (removes ghost node from graph)
        plan_id = self._event_plans.pop(event_id, None)
        if plan_id:
            try:
                await self.blackboard.update_plan_status(plan_id, PlanStatus.COMPLETED, result=summary)
            except Exception as e:
                logger.warning(f"Failed to complete plan {plan_id}: {e}")
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
        """Serialize event document as MD file to agent's volume, enriched with GitOps metadata and topology."""
        event = await self.blackboard.get_event(event_id)
        if not event:
            return

        # Enrich with GitOps metadata + architecture diagram from Blackboard
        service_meta = await self.blackboard.get_service(event.service)
        mermaid = ""
        try:
            mermaid = await self.blackboard.generate_mermaid()
        except Exception as e:
            logger.warning(f"Failed to generate mermaid for event MD: {e}")

        base_path = VOLUME_PATHS.get(agent_name)
        if not base_path:
            logger.warning(f"No volume path for agent: {agent_name}")
            return

        events_dir = Path(base_path) / "events"
        events_dir.mkdir(parents=True, exist_ok=True)

        file_path = events_dir / f"event-{event_id}.md"
        content = self._event_to_markdown(event, service_meta, mermaid)
        file_path.write_text(content)
        logger.debug(f"Wrote event MD to {file_path}")

    @staticmethod
    def _event_to_markdown(event: EventDocument, service_meta=None, mermaid: str = "") -> str:
        """Convert event document to readable Markdown, enriched with service metadata and topology."""
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

        # Include architecture diagram so agents see the full topology
        if mermaid:
            lines.append(f"")
            lines.append(f"## Architecture Diagram")
            lines.append(f"```mermaid")
            lines.append(mermaid)
            lines.append(f"```")

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
        Startup cleanup: close stale events and orphaned plans from a previous Brain instance.
        
        On restart, active events may be orphaned (agent tasks were in-flight,
        WebSocket connections dropped). Close them so they don't block the system.
        Also completes any PENDING plans so ghost nodes don't linger on the graph.
        """
        # --- Migrate pre-MessageStatus events: mark all existing turns as EVALUATED ---
        # Prevents mass re-processing on first deploy with the new unread-message scan.
        try:
            migrate_ids = await self.blackboard.get_active_events()
            for eid in migrate_ids:
                await self.blackboard.mark_turns_evaluated(eid)
            if migrate_ids:
                logger.info(f"Startup migration: marked turns EVALUATED for {len(migrate_ids)} active events")
        except Exception as e:
            logger.warning(f"Startup migration failed (non-fatal): {e}")

        # --- Clean up orphaned PENDING plans (ghost nodes from previous instance) ---
        try:
            pending_plans = await self.blackboard.get_pending_plans()
            if pending_plans:
                for plan in pending_plans:
                    await self.blackboard.update_plan_status(
                        plan.id, PlanStatus.FAILED,
                        result="Stale: closed on Brain restart.",
                    )
                logger.info(f"Startup cleanup: completed {len(pending_plans)} orphaned pending plans")
        except Exception as e:
            logger.warning(f"Failed to clean up orphaned plans on startup: {e}")

        # --- Clean up stale active events ---
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
                stale_summary = (
                    f"Stale: closed on Brain restart. Previous instance was processing this event. "
                    f"Last turn: {event.conversation[-1].actor}.{event.conversation[-1].action}"
                )
                await self.blackboard.close_event(eid, stale_summary)
                # Write to ops journal so Brain has temporal context for stale closures
                await self.blackboard.append_journal(
                    event.service,
                    f"{event.event.reason[:200]} -- stale closure on restart ({len(event.conversation)} turns)"
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

                # 2. Scan active events: status-driven two-phase scan
                active = await self.blackboard.get_active_events()
                for eid in active:
                    # Phase 1: Even if an agent task is running, acknowledge new turns
                    if eid in self._active_tasks and not self._active_tasks[eid].done():
                        event = await self.blackboard.get_event(eid)
                        if event:
                            unseen = [t for t in event.conversation if t.status.value == "sent"]
                            if unseen:
                                await self.blackboard.mark_turns_delivered(eid, len(event.conversation))
                                await self._broadcast_status_update(eid, "delivered", turns=unseen)
                        continue  # Still skip LLM evaluation -- agent is running

                    event = await self.blackboard.get_event(eid)
                    if not event or not event.conversation:
                        continue

                    # Check if event is deferred -- skip until delay expires
                    if event.status == EventStatus.DEFERRED:
                        defer_key = f"{self.blackboard.EVENT_PREFIX}{eid}:defer_until"
                        defer_until = await self.blackboard.redis.get(defer_key)
                        if defer_until and time.time() < float(defer_until):
                            continue  # Still deferred, skip
                        # Delay expired -- atomically re-activate (WATCH/MULTI/EXEC)
                        # to avoid losing turns appended during the defer window.
                        transitioned = await self.blackboard.transition_event_status(
                            eid, "deferred", EventStatus.ACTIVE,
                        )
                        await self.blackboard.redis.delete(defer_key)
                        if transitioned:
                            if eid in self._waiting_for_user:
                                logger.warning(f"Deferred event {eid} re-activated but waiting for user -- skipping")
                            else:
                                logger.info(f"Deferred event {eid} re-activated")
                                # Re-fetch post-transition so prefetch carries clean state
                                event = await self.blackboard.get_event(eid)
                                if event:
                                    await self.process_event(eid, prefetched_event=event)
                        continue

                    # Mark all SENT turns as DELIVERED (Brain has seen them)
                    unseen = [t for t in event.conversation if t.status.value == "sent"]
                    if unseen:
                        await self.blackboard.mark_turns_delivered(eid, len(event.conversation))
                        await self._broadcast_status_update(eid, "delivered", turns=unseen)

                    # Re-process if there are DELIVERED (unread) turns the Brain hasn't evaluated
                    # But skip if waiting for user -- only user response should resume
                    has_unread = any(t.status.value == "delivered" for t in event.conversation)
                    is_waiting = eid in self._waiting_for_user
                    if has_unread and not is_waiting:
                        await self.process_event(eid, prefetched_event=event)
                    elif not has_unread:
                        # Idle safety net: re-process if not waiting for user
                        # and hasn't been processed recently.
                        # Active-task events already hit `continue` in Phase 1 above.
                        # (is_waiting already computed above)
                        time_since_process = time.time() - self._last_processed.get(eid, 0)
                        if not is_waiting and time_since_process > 240:
                            logger.info(f"Idle safety net: re-processing event {eid} (idle {time_since_process:.0f}s)")
                            await self.process_event(eid, prefetched_event=event)

            except Exception as e:
                logger.error(f"Brain event loop error: {e}", exc_info=True)
                await asyncio.sleep(2)

            # Prevent tight spinning when many active events exist.
            # brpop in dequeue_event() blocks up to 5s when queue is empty,
            # but the active-event scan runs without blocking.
            await asyncio.sleep(1)

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

    @staticmethod
    def _infer_plan_action(text: str) -> PlanAction:
        """Infer PlanAction from a task description or plan summary."""
        lower = text.lower()
        if any(w in lower for w in ("scale", "replica", "hpa")):
            return PlanAction.SCALE
        if any(w in lower for w in ("rollback", "revert", "undo")):
            return PlanAction.ROLLBACK
        if any(w in lower for w in ("config", "env", "values", "helm", "setting")):
            return PlanAction.RECONFIG
        if any(w in lower for w in ("failover", "drain", "migrate")):
            return PlanAction.FAILOVER
        return PlanAction.OPTIMIZE  # default for code changes, perf, etc.

    async def _create_plan_for_event(
        self, event_id: str, service: str, description: str,
    ) -> None:
        """Create a Plan in the Blackboard so it appears as a ghost node on the graph."""
        if event_id in self._event_plans:
            return  # Already has a plan
        try:
            action = self._infer_plan_action(description)
            plan = await self.blackboard.create_plan(PlanCreate(
                action=action,
                service=service,
                reason=description[:300],
            ))
            self._event_plans[event_id] = plan.id
            logger.info(f"Created plan {plan.id} ({action.value}) for event {event_id} -> {service}")
        except Exception as e:
            logger.warning(f"Failed to create plan for event {event_id}: {e}")
