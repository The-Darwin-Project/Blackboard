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
# 11. [Pattern]: LLM adapter layer (.llm subpackage) -- Brain uses generate_stream(), tool schemas in llm/types.py.
# 12. [Pattern]: brain_thinking + brain_thinking_done WS messages bracket streaming. UI clears on done/turn/error.
# 13. [Pattern]: cancel_active_task() is the single kill path. Cancels asyncio.Task -> CancelledError in base_client -> WS close -> SIGTERM.
# 14. [Pattern]: _active_agent_for_event tracks which agent is running per event. Populated in _run_agent_task, cleaned in finally + cancel + close.
# 15. [Pattern]: _agent_sessions: dict[event_id, dict[agent_name, session_id]]. Nested dict prevents clobbering and allows O(1) cleanup on event close.
# 16. [Pattern]: _broadcast() fans out to _broadcast_targets list. register_channel() adds targets (e.g., Slack). All 8 call sites use _broadcast().
# 17. [Pattern]: _build_contents() returns structured [{role, parts}] array from Redis. Redis is single source of truth. No ChatSession.
# 18. [Pattern]: _turn_to_parts() maps ConversationTurn -> provider-agnostic parts. Brain=model role, all others=user role.
# 19. [Gotcha]: Consecutive same-role turns merged into one content block (Gemini requires alternating user/model).
# 20. [Pattern]: response_parts on brain turns preserves thought_signature for Gemini 3 multi-turn function calling.
# 21. [Pattern]: Progressive skills: BrainSkillLoader globs brain_skills/ at startup. _build_system_prompt assembles phase-specific prompt. _resolve_llm_params reads _phase.yaml priority. Feature flag BRAIN_PROGRESSIVE_SKILLS. Legacy: _determine_thinking_params_legacy.
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
import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, TypedDict

from ..models import ConversationTurn, EventDocument, EventStatus, MessageStatus, PlanAction, PlanCreate, PlanStatus


class ContextFlags(TypedDict, total=False):
    """Typed context flags for phase matching and _build_contents cache."""
    turn_count: int
    source: str
    service: str
    is_waiting: bool
    has_agent_result: bool
    last_is_user: bool
    has_related: bool
    has_recent_closed: bool
    has_graph_edges: bool
    has_aligner_turns: bool
    _cached_active_ids: list[str]
    _cached_recent_closed: list[Any]
    _cached_mermaid: str

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

# =============================================================================
# Brain System Prompt - THIS IS THE DECISION ENGINE
# =============================================================================

BRAIN_SYSTEM_PROMPT = """You are the Brain orchestrator of Project Darwin, an autonomous cloud operations system.

You coordinate AI agents via a shared conversation queue. Each agent accepts an optional `mode` parameter that controls its behavior scope.

- **Architect**: Reviews codebases, analyzes topology, produces plans. NEVER executes changes.
  - `mode: plan` (default) -- Full structured plan with risk assessment and verification steps.
  - `mode: review` -- Code/MR review only. Output: summary, severity findings (HIGH/MEDIUM/LOW), recommendation. No plan.
  - `mode: analyze` -- Information gathering and status report. No plan, no changes.

- **sysAdmin**: Investigates K8s issues, executes GitOps changes (Helm values).
  - `mode: investigate` (default) -- Read-only: kubectl get, logs, describe. No git push, no mutations.
  - `mode: execute` -- Full GitOps: clone repo, modify values.yaml, commit, push. ArgoCD syncs the change.
  - `mode: rollback` -- Git revert on target repo, verify ArgoCD sync. Use for crisis recovery.

- **Developer**: A development team with four dispatch modes:
  - `mode: implement` -- Full team. Developer implements, QE verifies quality, Flash Manager moderates.
    Use for: adding features, fixing bugs, modifying application source code.
  - `mode: execute` -- Developer solo. No QE, no Flash Manager.
    Use for: single write actions (post MR comment, merge MR, tag release, create branch, run a command).
  - `mode: investigate` (default) -- Developer solo. No QE, no Flash Manager.
    Use for: checking MR/PR status, code inspection, status reports, read-only information gathering.
  - `mode: test` -- QE solo. No Developer, no Flash Manager.
    Use for: running tests against existing code, verifying deployments via browser (Playwright).

The Developer team tools:
- Developer: git, file system, glab, gh (code implementation, MR/PR inspection)
- QE: git, file system, Playwright headless browser (UI tests), pytest, httpx, curl
- Both share the same workspace and see each other's code changes in real-time

## Your Job
1. Read the event (anomaly or user request) and its conversation history.
2. Decide the NEXT action by calling ONE of your available functions.
3. You are called repeatedly as the conversation progresses. Each call, you see the full history and decide the next step.

## Slack Notifications
Use notify_user_slack to send a direct message to a user by their email address.
- When an agent recommends notifying someone, call notify_user_slack with the email from the agent's recommendation.
- Use for: pipeline failure alerts, escalations, status updates to specific users.
- The message is delivered as a DM from the Darwin bot in Slack.

## Deep Memory
Before routing to an agent, call consult_deep_memory with a short query describing the symptom or task.
Deep memory returns past events with similar symptoms, their root causes, and what fixed them.
- If a past event matches closely (score > 0.6), use its root cause and fix to skip investigation and act directly.
- If no match or low scores, proceed normally with investigation.
- This is especially valuable for recurring infrastructure issues and repeated MR/pipeline patterns.

## Decision Guidelines
- For infrastructure anomalies (high CPU, pod issues): consult deep memory first, then sysAdmin to investigate [see §Cynefin: CLEAR/COMPLICATED].
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

## Compound User Instructions
- When a user request contains conditional outcomes (e.g., "if pipeline fails notify X, if it passes merge it"):
  1. These conditions describe the FINAL state after your best effort, not the current state.
  2. If the current state matches a failure condition, FIRST attempt remediation (retest, rerun, fix).
  3. Only trigger the failure notification AFTER remediation has been attempted and failed.
  4. Example: "retest and notify me if it fails" means: retest -> wait for result -> THEN decide.
  5. Do NOT short-circuit by matching the current state to a condition without trying to resolve it first.

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
MAX_TURNS_PER_EVENT = 100
MAX_INACTIVITY_SECONDS = 1800  # 30 minutes with no new turns = stale

# Volume mount paths (must match Helm deployment.yaml)
VOLUME_PATHS = {
    "architect": "/data/gitops-architect",
    "sysadmin": "/data/gitops-sysadmin",
    "developer": "/data/gitops-developer",
    "qe": "/data/gitops-qe",
}

# Progressive skill phase conditions: phase_name -> callable(event, context_flags) -> bool
PHASE_CONDITIONS: dict[str, Any] = {
    "always":     lambda e, c: True,
    "triage":     lambda e, c: c["turn_count"] <= 2,
    "dispatch":   lambda e, c: c["turn_count"] <= 4 or not c["has_agent_result"],
    "post-agent": lambda e, c: c["has_agent_result"],
    "waiting":    lambda e, c: c["is_waiting"],
    "context":    lambda e, c: c["has_related"] or c["has_graph_edges"] or c["has_recent_closed"],
    "source":     lambda e, c: True,
}

# Phase exclusion matrix (cleanSlate): active phase -> phases to exclude
PHASE_EXCLUSIONS: dict[str, list[str]] = {
    "post-agent": ["triage", "dispatch"],
    "waiting":    ["triage", "dispatch", "post-agent"],
}



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
        # Multi-target broadcast: WS (initial) + Slack (registered later)
        self._broadcast_targets: list[Callable] = []
        if broadcast:
            self._broadcast_targets.append(broadcast)
        self._running = False
        self._llm_available = False
        self._active_tasks: dict[str, asyncio.Task] = {}  # event_id -> running task
        self._active_agent_for_event: dict[str, str] = {}  # event_id -> agent_name
        self._agent_sessions: dict[str, dict[str, str]] = {}  # event_id -> {agent_name -> session_id}
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
        self.provider = os.getenv("LLM_PROVIDER", "gemini")
        self.temperature = float(os.getenv("LLM_TEMPERATURE_BRAIN", "0.8"))
        # Model selection based on provider
        if self.provider == "claude":
            self.model_name = os.getenv("VERTEX_MODEL_CLAUDE", "claude-opus-4-6")
        else:
            self.model_name = os.getenv("VERTEX_MODEL_PRO", "gemini-3-pro-preview")
        self._adapter = None  # Lazy-loaded via _get_adapter()
        # Progressive skill loading (feature flag)
        self._progressive_skills = os.getenv("BRAIN_PROGRESSIVE_SKILLS", "false").lower() == "true"
        self._skill_loader = None
        if self._progressive_skills:
            try:
                from .brain_skill_loader import BrainSkillLoader
                skills_path = Path(__file__).parent / "brain_skills"
                self._skill_loader = BrainSkillLoader(str(skills_path))
            except Exception as e:
                logger.warning(f"Failed to load brain skills: {e}. Falling back to monolith.")
                self._skill_loader = None
        skills_status = f"progressive ({len(self._skill_loader.available_phases())} phases)" if self._skill_loader else "monolith"
        logger.info(f"Brain initialized (provider={self.provider}, model={self.model_name}, skills={skills_status}, agents={list(self.agents.keys())})")

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

    async def _get_adapter(self):
        """Lazy-load LLM adapter (Gemini or Claude based on LLM_PROVIDER)."""
        if self._adapter is None:
            try:
                from .llm import create_adapter

                self._adapter = create_adapter(
                    provider=self.provider,
                    project=self.project,
                    location=self.location,
                    model_name=self.model_name,
                )
                self._llm_available = True
                logger.info(f"Brain LLM adapter initialized: {self.provider}/{self.model_name}")

            except Exception as e:
                logger.warning(f"LLM adapter not available: {e}. Brain stays in probe mode.")
                self._adapter = None

        return self._adapter

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

        # Circuit breaker: inactivity timeout (no new turns for 30 min = stale)
        # Active events with recent turns never time out, regardless of total duration.
        # Events waiting for user (approval/response) are exempt -- they're intentionally idle.
        if event.conversation and event_id not in self._waiting_for_user:
            last_turn_time = event.conversation[-1].timestamp
            inactivity = time.time() - last_turn_time

            if inactivity > MAX_INACTIVITY_SECONDS:
                logger.warning(f"Event {event_id} inactive for {inactivity:.0f}s (max {MAX_INACTIVITY_SECONDS}s)")
                await self._close_and_broadcast(
                    event_id,
                    f"STALE: No activity for {int(inactivity // 60)} minutes. Force closed.",
                )
                return

        # Snapshot turn count BEFORE LLM call -- any turns appended during processing
        # (e.g., Aligner confirm arriving mid-evaluation) will have index > turn_snapshot
        # and stay SENT/DELIVERED for the next event loop iteration.
        turn_snapshot = len(event.conversation)

        # Get LLM adapter; fall back to probe mode if unavailable
        adapter = await self._get_adapter()
        if not adapter:
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
            should_continue = await self._process_with_llm(event_id, event)
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
    ) -> bool:
        """Process event using streaming LLM call. Broadcasts thinking chunks to UI.

        Returns True if the caller should re-invoke immediately (e.g., after
        a lookup_service call that needs a follow-up LLM decision).

        Precondition: self._adapter is not None (caller checks via _get_adapter()).
        """
        from .llm import BRAIN_TOOL_SCHEMAS

        if not self._adapter:
            logger.error(f"_process_with_llm called without adapter for {event_id}")
            return False

        # Progressive skill loading: build phase-specific system prompt + LLM params
        if self._progressive_skills and self._skill_loader:
            context_flags = await self._extract_context_flags(event)
            active_phases = self._match_phases(event, context_flags)
            system_prompt = self._build_system_prompt(event, active_phases)
            thinking_level, call_temp = self._resolve_llm_params(active_phases)
        else:
            system_prompt = BRAIN_SYSTEM_PROMPT
            thinking_level, call_temp = self._determine_thinking_params_legacy(event)
            context_flags = None

        prompt = await self._build_contents(event, context_cache=context_flags)

        # Signal UI that Brain is processing (visible even when LLM produces no text)
        await self._broadcast({
            "type": "brain_thinking",
            "event_id": event_id,
            "text": "",
            "accumulated": "",
            "is_thought": True,
        })

        max_retries = 3
        last_error = None
        accumulated_text = ""
        function_call = None
        raw_parts = None

        for attempt in range(max_retries + 1):
            accumulated_text = ""
            function_call = None
            raw_parts = None

            try:
                async for chunk in self._adapter.generate_stream(
                    system_prompt=system_prompt,
                    contents=prompt,
                    tools=BRAIN_TOOL_SCHEMAS,
                    temperature=call_temp,
                    max_output_tokens=65000,
                    thinking_level=thinking_level,
                ):
                    if chunk.text:
                        accumulated_text += chunk.text
                        await self._broadcast({
                            "type": "brain_thinking",
                            "event_id": event_id,
                            "text": chunk.text,
                            "accumulated": accumulated_text,
                            "is_thought": chunk.is_thought,
                        })
                    if chunk.function_call:
                        function_call = chunk.function_call
                    if chunk.raw_parts:
                        raw_parts = chunk.raw_parts
                last_error = None
                break  # Success
            except Exception as e:
                last_error = e
                if attempt < max_retries and self._is_transient(e):
                    delay = min(5 * (2 ** attempt), 30)
                    logger.warning(f"Brain LLM transient error for {event_id} (attempt {attempt+1}/{max_retries+1}): {e}. Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    continue
                logger.error(f"Brain LLM streaming failed for {event_id}: {e}", exc_info=True)
                break

        # Clear thinking indicator ONCE after the loop exits
        await self._broadcast({"type": "brain_thinking_done", "event_id": event_id})

        # If all retries failed with no output, write error turn
        if last_error and not function_call and not accumulated_text:
            turn = ConversationTurn(
                turn=len(event.conversation) + 1,
                actor="brain",
                action="error",
                thoughts=f"LLM call failed after {attempt + 1} attempts: {last_error}",
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            return False

        # Normalize raw response parts for thought_signature preservation
        captured_parts = self._normalize_response_parts(raw_parts) if raw_parts else None

        # Closed guard: event may have been force-closed during the LLM call
        if await self._is_event_closed(event_id):
            logger.info(f"Event {event_id} closed during LLM call -- discarding result")
            return False

        # Process the final result
        if function_call:
            logger.info(f"Brain LLM decision for {event_id}: {function_call.name}")
            return await self._execute_function_call(
                event_id, function_call.name, function_call.args,
                response_parts=captured_parts,
            )

        if accumulated_text:
            turn = ConversationTurn(
                turn=len(event.conversation) + 1,
                actor="brain",
                action="think",
                thoughts=accumulated_text,
                response_parts=captured_parts,
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            return False

        logger.warning(f"Brain LLM returned empty response for {event_id}")
        return False

    @staticmethod
    def _is_transient(e: Exception) -> bool:
        """Check if exception is a transient rate-limit or availability error."""
        err_str = str(e)
        return any(code in err_str for code in ["429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"])

    def _resolve_llm_params(self, active_phases: list[str]) -> tuple[str, float]:
        """Resolve thinking_level + temperature from active phase _phase.yaml metadata.

        Most specific phase wins (lowest priority number).
        Falls back to legacy heuristic if loader unavailable.
        """
        if not self._skill_loader:
            return "high", 0.5

        best_priority = float("inf")
        best_thinking = "high"
        best_temp = 0.5

        for phase_name in active_phases:
            meta = self._skill_loader.get_phase_meta(phase_name)
            if meta and "thinking_level" in meta:
                priority = meta.get("priority", 50)
                if priority < best_priority:
                    best_priority = priority
                    best_thinking = meta["thinking_level"]
                    best_temp = meta.get("temperature", 0.5)

        logger.debug(f"LLM params: thinking={best_thinking}, temp={best_temp} (priority={best_priority})")
        return best_thinking, best_temp

    @staticmethod
    def _determine_thinking_params_legacy(event: "EventDocument") -> tuple[str, float]:
        """Legacy adaptive thinking -- fallback when progressive skills are disabled.

        Gemini 3 Pro supports only 'low' and 'high' (not 'medium' or 'minimal').
        Use 'high' for analysis, 'low' for mechanical routing.
        Returns (thinking_level, temperature).
        """
        if not event.conversation or len(event.conversation) <= 1:
            return "high", 0.6

        recent = event.conversation[-3:]
        has_agent_result = any(t.actor not in ("brain", "user") for t in recent)
        last_is_user = recent[-1].actor == "user"

        if has_agent_result:
            return "low", 0.3
        if last_is_user:
            return "high", 0.5
        return "low", 0.4

    @staticmethod
    def _normalize_response_parts(raw_parts: list) -> list[dict]:
        """Normalize SDK Part objects to plain dicts for Redis storage.

        Handles camelCase vs snake_case thought_signature across SDK versions.
        """
        preserved = []
        for part in raw_parts:
            p: dict = {}
            if hasattr(part, 'text') and part.text:
                p['text'] = str(part.text)
            if hasattr(part, 'thought') and part.thought:
                p['thought'] = True
            if hasattr(part, 'function_call') and part.function_call:
                fc = part.function_call
                args = {}
                if fc.args:
                    args = {str(k): str(v) if isinstance(v, bytes) else v for k, v in dict(fc.args).items()}
                p['functionCall'] = {"name": str(fc.name), "args": args}
            sig = getattr(part, 'thought_signature', None) or getattr(part, 'thoughtSignature', None)
            if sig:
                import base64
                p['thought_signature'] = base64.b64encode(sig).decode('ascii') if isinstance(sig, bytes) else str(sig)
            if p:
                preserved.append(p)
        return preserved or [{"text": ""}]

    # =========================================================================
    # Progressive Skill System -- Context Flags + Phase Matching
    # =========================================================================

    async def _extract_context_flags(self, event: EventDocument) -> ContextFlags:
        """Extract boolean context flags for phase matching. Lightweight Redis reads.

        Returns flags dict with cached raw data for _build_contents to reuse,
        avoiding double Redis calls for active_events, mermaid, and recent_closed.
        """
        flags: ContextFlags = {
            "turn_count": len(event.conversation),
            "source": event.source,
            "service": event.service,
            "is_waiting": event.id in self._waiting_for_user,
        }

        recent = event.conversation[-3:] if event.conversation else []
        flags["has_agent_result"] = any(
            t.actor not in ("brain", "user", "aligner") for t in recent
        )
        flags["last_is_user"] = bool(recent and recent[-1].actor == "user")

        active_ids = await self.blackboard.get_active_events()
        flags["_cached_active_ids"] = active_ids
        has_related = False
        for eid in active_ids:
            if eid == event.id:
                continue
            other = await self.blackboard.get_event(eid)
            if other and other.service == event.service:
                has_related = True
                break
        flags["has_related"] = has_related

        recent_closed = await self.blackboard.get_recent_closed_for_service(
            event.service, minutes=15
        )
        flags["_cached_recent_closed"] = recent_closed
        flags["has_recent_closed"] = bool(recent_closed)

        mermaid = ""
        try:
            mermaid = await self.blackboard.generate_mermaid()
        except Exception:
            pass
        flags["_cached_mermaid"] = mermaid
        flags["has_graph_edges"] = bool(mermaid and "-->" in mermaid)

        flags["has_aligner_turns"] = any(
            t.actor == "aligner" for t in event.conversation
        )

        return flags

    def _match_phases(self, event: EventDocument, ctx: dict) -> list[str]:
        """Determine which skill phases are active for this event state."""
        active = [
            phase for phase, condition in PHASE_CONDITIONS.items()
            if condition(event, ctx)
        ]
        excluded: set[str] = set()
        for phase in active:
            excluded.update(PHASE_EXCLUSIONS.get(phase, []))
        return [p for p in active if p not in excluded]

    def _build_system_prompt(
        self, event: EventDocument, active_phases: list[str],
    ) -> str:
        """Assemble system prompt from matching skill phases + dependency resolution."""
        if not self._skill_loader or not self._skill_loader.available_phases():
            return BRAIN_SYSTEM_PROMPT

        initial_paths: list[str] = []
        for phase in active_phases:
            if phase == "source":
                source_file = f"source/{event.source}.md"
                if source_file in self._skill_loader.get_all_paths_for_phase("source"):
                    initial_paths.append(source_file)
                else:
                    logger.warning(f"No source skill for '{event.source}' -- close protocol guidance unavailable")
            else:
                initial_paths.extend(self._skill_loader.get_all_paths_for_phase(phase))

        template_vars = {"event.source": event.source, "event.service": event.service}
        resolved_contents = self._skill_loader.resolve_dependencies(
            initial_paths, template_vars=template_vars
        )

        if "post-agent" in active_phases:
            rec = self._surface_agent_recommendation(event)
            if rec:
                has_explicit = "LATEST AGENT RECOMMENDATION" in rec
                logger.debug(f"Agent recommendation surfaced for {event.id}: {'explicit' if has_explicit else 'ask-agent directive'} ({len(rec)} chars)")
                resolved_contents.append(rec)

        prompt = "\n\n---\n\n".join(resolved_contents)

        total_tokens = len(prompt) // 4
        phase_str = ", ".join(active_phases)
        logger.info(f"Brain skills: [{phase_str}] ({total_tokens} tokens) for {event.id}")

        return prompt

    @staticmethod
    def _surface_agent_recommendation(event: EventDocument) -> str | None:
        """Extract and promote last agent's recommendation to system-level priority."""
        last_agent_turn = next(
            (t for t in reversed(event.conversation)
             if t.actor not in ("brain", "user", "aligner")),
            None,
        )
        if not last_agent_turn:
            return None

        result_text = last_agent_turn.result or last_agent_turn.thoughts or ""
        rec = Brain._extract_recommendation(result_text)

        if rec:
            return (
                f"## LATEST AGENT RECOMMENDATION (from {last_agent_turn.actor})\n"
                f"The following is from the most recent agent execution. "
                f"You MUST address this before closing:\n\n{rec}"
            )
        return (
            f"## AGENT RESULT WITHOUT RECOMMENDATION\n"
            f"Agent '{last_agent_turn.actor}' returned findings but no explicit recommendation.\n"
            f"Before deciding your next action, route back to the SAME agent with mode=investigate "
            f"and ask: 'Based on your findings, what is your recommended next step?'\n"
            f"Do NOT close the event or make assumptions without agent input."
        )

    @staticmethod
    def _extract_recommendation(text: str, max_tokens: int = 300) -> str | None:
        """Extract recommendation section from agent result text.

        Heuristics (no LLM call):
        1. Look for ## Recommendation, ### Next Step, **Recommendation** headers
        2. If no header, take the last paragraph
        3. Cap at max_tokens (~1200 chars) to avoid re-bloating the prompt
        """
        patterns = [
            r"(?:^|\n)##?\s*(?:Recommendation|Next Step|Suggested Action)s?\s*\n(.*?)(?=\n##?\s|\Z)",
            r"\*\*(?:Recommendation|Next Step)\*\*:?\s*(.*?)(?=\n\n|\Z)",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                rec = match.group(1).strip()
                max_chars = max_tokens * 4
                return rec[:max_chars] if len(rec) > max_chars else rec

        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
        if paragraphs:
            last = paragraphs[-1]
            max_chars = max_tokens * 4
            return last[:max_chars] if len(last) > max_chars else last

        return None

    async def _build_contents(
        self, event: EventDocument, context_cache: ContextFlags | None = None,
    ) -> list[dict]:
        """Build structured Gemini-format contents array from Redis conversation.

        Returns list of {role: str, parts: list[dict]} messages.
        First message = event context (user role).
        Subsequent messages alternate user/model based on ConversationTurn actor.
        Consecutive same-role turns are merged (Gemini requires alternating roles).
        context_cache: if provided, reuse cached Redis data from _extract_context_flags.
        """
        from ..models import EventEvidence

        # -- Event context (first user message) --
        evidence = event.event.evidence
        evidence_text = evidence.display_text if isinstance(evidence, EventEvidence) else str(evidence)
        lines = [
            f"Event ID: {event.id}",
            f"Source: {event.source}",
            f"Service: {event.service}",
            f"Status: {event.status.value}",
            f"Reason: {event.event.reason}",
            f"Evidence: {evidence_text}",
            f"Time: {event.event.timeDate}",
        ]
        if isinstance(evidence, EventEvidence):
            lines.append(f"Domain: {evidence.domain}")
            lines.append(f"Severity: {evidence.severity}")

        event_created = event.conversation[0].timestamp if event.conversation else time.time()
        age_seconds = int(time.time() - event_created)
        age_min, age_sec = divmod(age_seconds, 60)
        lines.append(f"Event Age: {age_min}m {age_sec}s")

        svc = await self.blackboard.get_service(event.service)
        if svc:
            lines.append("")
            lines.append("Service Metadata:")
            lines.append(f"  Version: {svc.version}")
            if svc.gitops_repo:
                lines.append(f"  GitOps Repo: {svc.gitops_repo}")
            if svc.gitops_repo_url:
                lines.append(f"  Repo URL: {svc.gitops_repo_url}")
            if svc.gitops_config_path:
                lines.append(f"  Config Path: {svc.gitops_config_path}")
            if svc.replicas_ready is not None:
                lines.append(f"  Replicas: {svc.replicas_ready}/{svc.replicas_desired}")
            lines.append(f"  CPU: {svc.metrics.cpu:.1f}%")
            lines.append(f"  Memory: {svc.metrics.memory:.1f}%")

        if context_cache and "_cached_mermaid" in context_cache:
            mermaid = context_cache["_cached_mermaid"]
        else:
            mermaid = ""
            try:
                mermaid = await self.blackboard.generate_mermaid()
            except Exception as e:
                logger.warning(f"Failed to generate mermaid for Brain prompt: {e}")
        if mermaid:
            lines.append("")
            lines.append("Architecture Diagram (Mermaid):")
            lines.append(mermaid)

        if context_cache and "_cached_active_ids" in context_cache:
            active_event_ids = context_cache["_cached_active_ids"]
        else:
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
                summary = f"  - {eid} ({other.source}): {other.event.reason}"
                if last_action:
                    summary += f" [last: {last_action.actor}.{last_action.action}]"
                related.append(summary)
            elif other.service == "general":
                for turn in other.conversation[-3:]:
                    if event.service in (turn.thoughts or "") or event.service in (turn.result or ""):
                        related.append(f"  - {eid} (chat): {other.event.reason}")
                        break

        if related:
            lines.append("")
            lines.append("Related Active Events (same service -- consider before acting):")
            lines.extend(related)

        if context_cache and "_cached_recent_closed" in context_cache:
            recent_closed = context_cache["_cached_recent_closed"]
        else:
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

        journal = await self._get_journal_cached(event.service)
        if journal:
            lines.append("")
            lines.append(f"Service Ops Journal (last {len(journal)} actions):")
            for entry in journal[-10:]:
                lines.append(f"  {entry}")
            lines.append("  (Use lookup_journal to check other services' history)")

        if not event.conversation:
            lines.append("")
            lines.append("(No turns yet -- this is a new event. Triage it.)")
            lines.append("What is the next action? Call one of your functions.")
            return [{"role": "user", "parts": [{"text": "\n".join(lines)}]}]

        context_text = "\n".join(lines)

        # -- Build structured conversation messages --
        contents: list[dict] = [{"role": "user", "parts": [{"text": context_text}]}]

        for turn in event.conversation:
            role = "model" if turn.actor == "brain" else "user"
            parts = self._turn_to_parts(turn)

            if contents and contents[-1]["role"] == role:
                contents[-1]["parts"].extend(parts)
            else:
                contents.append({"role": role, "parts": parts})

        # Ensure the last message is a user prompt requesting action
        action_prompt = {"text": "What is the next action? Call one of your functions."}
        if contents[-1]["role"] == "user":
            contents[-1]["parts"].append(action_prompt)
        else:
            contents.append({"role": "user", "parts": [action_prompt]})

        return self._compress_contents(contents)

    @staticmethod
    def _turn_to_parts(turn: ConversationTurn) -> list[dict]:
        """Convert a single ConversationTurn to provider-agnostic parts.

        Brain turns use response_parts (thought_signature preserved) when available.
        User/agent turns use text from thoughts/result/evidence fields.
        Image turns embed the image bytes inline in the parts array.
        """
        if turn.actor == "brain" and turn.response_parts:
            return list(turn.response_parts)

        text = ""
        if turn.actor == "brain":
            text = turn.thoughts or ""
            if turn.evidence:
                text = f"{text}\n{turn.evidence}" if text else turn.evidence
        elif turn.actor == "user":
            text = turn.thoughts or ""
        elif turn.actor == "aligner":
            text = turn.evidence or turn.thoughts or ""
        else:
            text = turn.result or turn.thoughts or ""
            if text and turn.actor != "user":
                text = f"Agent {turn.actor} result: {text}"

        parts: list[dict] = [{"text": text}] if text else [{"text": f"[{turn.actor}.{turn.action}]"}]

        if turn.image:
            try:
                header, b64data = turn.image.split(",", 1)
                mime_type = header.split(":")[1].split(";")[0]
                image_bytes = base64.b64decode(b64data)
                parts.append({"bytes": image_bytes, "mime_type": mime_type})
            except Exception:
                pass

        return parts

    # =========================================================================
    # Conversation Compression (progressive, no LLM call)
    # =========================================================================

    @staticmethod
    def _estimate_tokens(contents: list[dict]) -> int:
        """Rough token estimate: ~4 chars per token."""
        total_chars = sum(
            len(str(part.get("text", "")))
            for msg in contents for part in msg.get("parts", [])
        )
        return total_chars // 4

    @classmethod
    def _compress_contents(cls, contents: list[dict], max_tokens: int = 200_000) -> list[dict]:
        """Progressive compression: skeleton/summary/full tiers. No LLM call.

        First message (event context) always kept intact.
        Atomic pair guard: model(functionCall) + user(response) never separated.
        """
        if len(contents) <= 3:
            return contents

        if cls._estimate_tokens(contents) < max_tokens:
            return contents

        context_msg = contents[0]
        conv_msgs = contents[1:]
        n = len(conv_msgs)

        skeleton_end = max(0, n - 20)
        summary_end = max(skeleton_end, n - 10)

        # Build tier assignment per message, then enforce atomic pairs
        tiers = []
        for i in range(n):
            if i < skeleton_end:
                tiers.append("skeleton")
            elif i < summary_end:
                tiers.append("summary")
            else:
                tiers.append("full")

        # Atomic pair guard: if a model msg has functionCall parts, promote
        # it and the next user msg to the same tier (the less compressed one)
        for i in range(n - 1):
            msg = conv_msgs[i]
            if msg["role"] == "model" and any(
                isinstance(p, dict) and ("functionCall" in p or "function_call" in p)
                for p in msg.get("parts", [])
            ):
                better = min(tiers[i], tiers[i + 1], key=["full", "summary", "skeleton"].index)
                tiers[i] = better
                tiers[i + 1] = better

        compressed = [context_msg]
        for i, msg in enumerate(conv_msgs):
            tier = tiers[i]
            if tier == "skeleton":
                role = msg["role"]
                first_text = ""
                for p in msg.get("parts", []):
                    if isinstance(p, dict) and "text" in p:
                        first_text = p["text"][:60]
                        break
                compressed.append({"role": role, "parts": [{"text": f"(earlier turn: {first_text}...)"}]})
            elif tier == "summary":
                role = msg["role"]
                parts = []
                for p in msg.get("parts", []):
                    if isinstance(p, dict) and "text" in p:
                        sentences = p["text"].split(". ")
                        parts.append({"text": sentences[0] + ("." if len(sentences) > 1 else "")})
                    else:
                        parts.append(p)
                compressed.append({"role": role, "parts": parts or msg["parts"]})
            else:
                compressed.append(msg)

        return compressed

    # =========================================================================
    # Function Call Dispatcher
    # =========================================================================

    async def _execute_function_call(
        self,
        event_id: str,
        function_name: str,
        args: dict,
        response_parts: list[dict] | None = None,
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
            mode = args.get("mode", "")

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
                taskForAgent={"agent": agent_name, "instruction": task, "mode": mode},
                response_parts=response_parts,
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)

            # Broadcast the event MD as attachment
            event = await self.blackboard.get_event(event_id)
            if event:
                svc_meta = await self.blackboard.get_service(event.service)
                await self._broadcast({
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
                    routing_turn_num=turn.turn, mode=mode,
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
            # Brain-push: call check_state directly instead of polling
            aligner = self.agents.get("_aligner")
            if aligner and service:
                state = await aligner.check_state(service)
                verify_turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="verify",
                    thoughts=f"Re-triggering Aligner to check: {condition}",
                    evidence=f"target_service:{service}",
                )
                await self.blackboard.append_turn(event_id, verify_turn)
                await self._broadcast_turn(event_id, verify_turn)
                # Immediately append the Aligner's response
                confirm_turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="aligner",
                    action="confirm",
                    evidence=(
                        f"Service: {state['service']}, "
                        f"CPU: {state.get('cpu', 0):.1f}%, "
                        f"Memory: {state.get('memory', 0):.1f}%, "
                        f"Replicas: {state.get('replicas_ready', '?')}/{state.get('replicas_desired', '?')}"
                    ),
                )
                await self.blackboard.append_turn(event_id, confirm_turn)
                await self._broadcast_turn(event_id, confirm_turn)
            return False

        elif function_name == "wait_for_verification":
            condition = args.get("condition", "")
            # Brain-push: call check_state directly instead of polling
            event = await self.blackboard.get_event(event_id)
            target_service = event.service if event else ""
            aligner = self.agents.get("_aligner")
            if aligner and target_service:
                state = await aligner.check_state(target_service)
                verify_turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="verify",
                    thoughts=f"Waiting for verification: {condition}",
                    evidence=f"target_service:{target_service}",
                )
                await self.blackboard.append_turn(event_id, verify_turn)
                await self._broadcast_turn(event_id, verify_turn)
                # Immediately append the Aligner's response
                confirm_turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="aligner",
                    action="confirm",
                    evidence=(
                        f"Service: {state['service']}, "
                        f"CPU: {state.get('cpu', 0):.1f}%, "
                        f"Memory: {state.get('memory', 0):.1f}%, "
                        f"Replicas: {state.get('replicas_ready', '?')}/{state.get('replicas_desired', '?')}"
                    ),
                )
                await self.blackboard.append_turn(event_id, confirm_turn)
                await self._broadcast_turn(event_id, confirm_turn)
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
                if svc.gitops_config_path:
                    info_parts.append(f"  Config Path: {svc.gitops_config_path}")
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
            # Guard: max 1 deep memory call per event (prevent LLM re-query loop)
            ev = await self.blackboard.get_event(event_id)
            already_consulted = any(
                t.action == "think" and t.evidence and "Deep memory" in (t.evidence or "")
                for t in (ev.conversation if ev else [])
            )
            if already_consulted:
                logger.info(f"Deep memory already consulted for {event_id} -- breaking loop")
                return False  # Break the LLM loop; event re-enters via next event loop scan

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

        elif function_name == "notify_user_slack":
            user_email = args.get("user_email", "")
            message = args.get("message", "")
            slack_channel = self._get_slack_channel()
            if not slack_channel:
                result_text = "Slack integration not available. Cannot send notification."
            elif not user_email or not message:
                result_text = "Missing user_email or message parameter."
            else:
                try:
                    user_info = await slack_channel._app.client.users_lookupByEmail(email=user_email)
                    slack_user_id = user_info["user"]["id"]
                    dm = await slack_channel._app.client.conversations_open(users=slack_user_id)
                    dm_channel = dm["channel"]["id"]
                    logger.info(f"notify_user_slack: user={slack_user_id} dm_channel={dm_channel} event={event_id}")
                    result = await slack_channel._app.client.chat_postMessage(
                        channel=dm_channel,
                        text=f":bell: *Darwin Notification*\n\n{message}",
                    )
                    msg_ts = result["ts"]
                    event_doc = await self.blackboard.get_event(event_id)
                    if event_doc and not event_doc.slack_thread_ts:
                        await self.blackboard.update_event_slack_context(
                            event_id, dm_channel, msg_ts, slack_user_id,
                        )
                        await self.blackboard.set_slack_mapping(dm_channel, msg_ts, event_id)
                        logger.info(f"Slack notification sent to {user_email} for event {event_id} (thread={msg_ts}, bidirectional)")
                        result_text = f"Slack DM sent to {user_email}. They can reply in the thread to interact with this event."
                    else:
                        logger.info(f"Slack notification sent to {user_email} for event {event_id} (one-way, existing thread preserved)")
                        result_text = f"Slack DM sent to {user_email}."
                except Exception as e:
                    result_text = f"Failed to send Slack DM to {user_email}: {e}"
                    logger.warning(f"Slack notification failed for {user_email}: {e}")

            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="notify",
                thoughts=result_text,
                response_parts=response_parts,
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            return True

        else:
            logger.warning(f"Unknown function call: {function_name}")
            return False

    def _get_slack_channel(self):
        """Get the registered Slack channel from broadcast targets, if available."""
        for target in self._broadcast_targets:
            if hasattr(target, '__self__') and hasattr(target.__self__, '_app'):
                return target.__self__
        return None

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
        mode: str = "",
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
                await self._broadcast({
                    "type": "progress",
                    "event_id": event_id,
                    "actor": progress_data.get("actor", agent_name),
                    "message": progress_data.get("message", ""),
                })

            mode_label = f" (mode={mode})" if mode else ""
            logger.info(f"Agent task started: {agent_name}{mode_label} for {event_id}")
            self._active_agent_for_event[event_id] = agent_name
            # Immediate progress so UI shows activity during CLI cold start
            await self._broadcast({
                "type": "progress",
                "event_id": event_id,
                "actor": agent_name,
                "message": f"{agent_name} starting...",
            })
            # Acquire per-agent lock to prevent concurrent WS calls to the same sidecar
            async with self._agent_locks[agent_name]:
                result, session_id = await agent.process(
                    event_id=event_id,
                    task=task,
                    event_md_path=event_md_path,
                    on_progress=on_progress,
                    mode=mode,
                    session_id=self._agent_sessions.get(event_id, {}).get(agent_name),
                )
            # Track session for Phase 2 follow-ups (forward user messages instead of cancel)
            if session_id:
                self._agent_sessions.setdefault(event_id, {})[agent_name] = session_id
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
                        if not await self._is_event_closed(event_id):
                            await self.process_event(event_id)
                        return

                    if result_data.get("type") == "agent_busy":
                        turn = ConversationTurn(
                            turn=(await self._next_turn_number(event_id)),
                            actor=agent_name,
                            action="busy",
                            thoughts=result_data.get("message", f"{agent_name} is busy after retries"),
                        )
                        await self.blackboard.append_turn(event_id, turn)
                        await self._broadcast_turn(event_id, turn)
                        logger.warning(f"Agent {agent_name} busy for {event_id}, returning to Brain")
                        if not await self._is_event_closed(event_id):
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
                if not await self._is_event_closed(event_id):
                    await self.process_event(event_id)
                return

            # Append agent result turn
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor=agent_name,
                action="execute",
                result=result_str[:15000],  # Cap result length (raised for Dev+QE merged output)
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

            # Trigger next Brain decision (skip if event was closed while agent ran)
            if not await self._is_event_closed(event_id):
                await self.process_event(event_id)
            else:
                logger.info(f"Skipping re-entry for {event_id}: event closed while agent ran")

        except Exception as e:
            logger.error(f"Agent task failed: {agent_name} for {event_id}: {e}", exc_info=True)
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor=agent_name,
                action="error",
                thoughts=f"Agent execution failed: {str(e)}",
            )
            await self.blackboard.append_turn(event_id, turn)
            await self._broadcast_turn(event_id, turn)
            if routing_turn_num:
                await self.blackboard.mark_turn_status(
                    event_id, routing_turn_num, MessageStatus.EVALUATED
                )
            # Re-evaluate (skip if event was closed concurrently)
            if not await self._is_event_closed(event_id):
                await self.process_event(event_id)

        finally:
            # Clean up active task tracking
            self._active_tasks.pop(event_id, None)
            self._active_agent_for_event.pop(event_id, None)
            # Note: _agent_sessions is NOT cleaned here -- sessions persist across
            # task invocations for Phase 2 follow-ups. Cleaned in cancel/close paths.

    # =========================================================================
    # Broadcast Helpers
    # =========================================================================

    async def _broadcast_turn(self, event_id: str, turn: ConversationTurn) -> None:
        """Broadcast a conversation turn to all channels (WS, Slack, etc.)."""
        await self._broadcast({
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
        if turns is None:
            turn_list = "all"
        elif turns and hasattr(turns[0], "turn"):
            turn_list = [t.turn for t in turns]
        else:
            turn_list = turns  # Already int list
        await self._broadcast({
            "type": "message_status",
            "event_id": event_id,
            "status": status,
            "turns": turn_list,
        })

    def clear_waiting(self, event_id: str) -> None:
        """Clear the wait_for_user state for an event (called when user responds)."""
        self._waiting_for_user.discard(event_id)

    def register_channel(self, channel_broadcast: Callable) -> None:
        """Register an additional broadcast target (e.g., Slack)."""
        self._broadcast_targets.append(channel_broadcast)

    async def _broadcast(self, message: dict) -> None:
        """Fan out a message to all registered broadcast targets (WS, Slack, etc.)."""
        for target in self._broadcast_targets:
            try:
                await target(message)
            except Exception as e:
                logger.warning(f"Broadcast target failed: {e}")

    async def _close_and_broadcast(self, event_id: str, summary: str) -> None:
        """Close an event and broadcast the closure to UI."""
        # Cancel any running agent task for this event (prevents orphaned CLI processes)
        await self.cancel_active_task(event_id, f"Event closing: {summary}")
        # Fetch event BEFORE close to get service name for journal
        event = await self.blackboard.get_event(event_id)
        await self.blackboard.close_event(event_id, summary)
        # Persist report snapshot (non-fatal)
        try:
            await self.blackboard.persist_report(event_id)
        except Exception as e:
            logger.warning(f"Report persistence failed for {event_id} (non-fatal): {e}")
        # Append to service ops journal (temporal memory)
        if event:
            turns = len(event.conversation)
            await self.blackboard.append_journal(
                event.service,
                f"{event.event.reason} -- closed in {turns} turns. {summary}"
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
        self._active_agent_for_event.pop(event_id, None)
        self._agent_sessions.pop(event_id, None)
        for agent in self.agents.values():
            if hasattr(agent, 'cleanup_event'):
                agent.cleanup_event(event_id)
        # Complete any associated Plan (removes ghost node from graph)
        plan_id = self._event_plans.pop(event_id, None)
        if plan_id:
            try:
                await self.blackboard.update_plan_status(plan_id, PlanStatus.COMPLETED, result=summary)
            except Exception as e:
                logger.warning(f"Failed to complete plan {plan_id}: {e}")
        await self._broadcast({
            "type": "event_closed",
            "event_id": event_id,
            "summary": summary,
            })

    # =========================================================================
    # Active Task Cancellation
    # =========================================================================

    async def cancel_active_task(self, event_id: str, reason: str = "cancelled") -> bool:
        """Cancel a running agent task for an event. Single kill path for all layers.

        Cancels the asyncio.Task, which triggers CancelledError in base_client.process(),
        which closes the WS to the sidecar, which SIGTERMs the CLI process.
        Waits up to 3s for graceful cleanup before giving up.

        Returns True if a task was cancelled, False if no active task existed.
        """
        task = self._active_tasks.get(event_id)
        if not task or task.done():
            return False
        logger.warning(f"Cancelling active task for {event_id}: {reason}")
        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=3.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        self._active_tasks.pop(event_id, None)
        self._active_agent_for_event.pop(event_id, None)
        self._agent_sessions.pop(event_id, None)
        for agent in self.agents.values():
            if hasattr(agent, 'cleanup_event'):
                agent.cleanup_event(event_id)
        self._event_locks.pop(event_id, None)
        return True

    async def emergency_stop(self) -> int:
        """Cancel ALL active agent tasks and close their events. Master kill switch.

        Returns the number of tasks cancelled.
        """
        cancelled = 0
        for eid in list(self._active_tasks.keys()):
            if await self.cancel_active_task(eid, "Emergency stop by user"):
                await self._close_and_broadcast(eid, "Emergency stop: all agents terminated.")
                cancelled += 1
        logger.critical(f"EMERGENCY STOP: {cancelled} tasks cancelled")
        return cancelled

    async def send_to_agent(self, event_id: str, agent_name: str, message: str) -> str:
        """Send a follow-up message to a running agent session.

        Used in Phase 2 to forward user messages to agents instead of killing them.
        The agent's followup() handles routing internally (e.g., Developer routes through Flash Manager).
        """
        session_id = self._agent_sessions.get(event_id, {}).get(agent_name)
        if not session_id:
            return "No active session"
        agent = self.agents.get(agent_name)
        if not agent:
            return "Agent not found"
        return await agent.followup(event_id, session_id, message)

    async def _forward_user_to_agent(
        self, event_id: str, agent_name: str, user_text: str
    ) -> None:
        """Forward a user message to an active agent session and persist the response.

        Tracked in _active_tasks so cancel_active_task() and emergency_stop() can
        cancel it. Runs as asyncio.create_task() so the event loop is not blocked.
        """
        try:
            followup_result = await self.send_to_agent(
                event_id, agent_name, f"The user says: {user_text}")
            if followup_result and not followup_result.startswith("Error:"):
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor=agent_name,
                    action="followup",
                    result=followup_result[:15000],
                )
                await self.blackboard.append_turn(event_id, turn)
                await self._broadcast_turn(event_id, turn)
        except asyncio.CancelledError:
            logger.info(f"Follow-up forwarding cancelled for {event_id}")
        except Exception as e:
            logger.warning(f"Follow-up forwarding failed for {event_id}: {e}")

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
        from ..models import EventEvidence
        evidence = event.event.evidence
        lines = [
            f"# Event: {event.id}",
            f"",
            f"- **Source:** {event.source}",
            f"- **Service:** {event.service}",
            f"- **Status:** {event.status.value}",
            f"- **Reason:** {event.event.reason}",
        ]
        if isinstance(evidence, EventEvidence):
            lines.append(f"- **Evidence:** {evidence.display_text}")
            lines.append(f"- **Domain:** {evidence.domain}")
            lines.append(f"- **Severity:** {evidence.severity}")
        else:
            lines.append(f"- **Evidence:** {evidence}")
        lines.append(f"- **Time:** {event.event.timeDate}")

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
            if service_meta.gitops_config_path:
                lines.append(f"- **Config Path:** {service_meta.gitops_config_path}")
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
        from datetime import datetime, timezone
        prev_ts = event.conversation[0].timestamp if event.conversation else 0
        for turn in event.conversation:
            ts_str = datetime.fromtimestamp(turn.timestamp, tz=timezone.utc).strftime('%H:%M:%S')
            delta = int(turn.timestamp - prev_ts)
            delta_label = f"+{delta // 60}m {delta % 60}s" if delta > 0 else "+0s"
            lines.append(f"### Turn {turn.turn} - {turn.actor} ({turn.action}) [{ts_str}] ({delta_label})")
            prev_ts = turn.timestamp
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
                # Persist report snapshot (non-fatal)
                try:
                    await self.blackboard.persist_report(eid)
                except Exception as e:
                    logger.warning(f"Report persistence failed for {eid} (non-fatal): {e}")
                # Write to ops journal so Brain has temporal context for stale closures
                await self.blackboard.append_journal(
                    event.service,
                    f"{event.event.reason} -- stale closure on restart ({len(event.conversation)} turns)"
                )
                # Archive to deep memory (same as _close_and_broadcast path)
                archivist = self.agents.get("_archivist_memory")
                if archivist and hasattr(archivist, "archive_event"):
                    try:
                        await archivist.archive_event(event)
                    except Exception as e:
                        logger.warning(f"Deep memory archive failed for {eid} (non-fatal): {e}")
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
                # 1. Check for new events on the queue
                event_id = await self.blackboard.dequeue_event()
                if event_id:
                    logger.info(f"New event from queue: {event_id}")
                    await self.process_event(event_id)

                # 2. Scan active events: status-driven two-phase scan
                active = await self.blackboard.get_active_events()
                for eid in active:
                    # Agent task running: acknowledge turns, forward user messages or cancel
                    if eid in self._active_tasks and not self._active_tasks[eid].done():
                        event = await self.blackboard.get_event(eid)
                        if event:
                            unseen = [t for t in event.conversation if t.status.value == "sent"]
                            if unseen:
                                await self.blackboard.mark_turns_delivered(eid, len(event.conversation))
                                await self._broadcast_status_update(eid, "delivered", turns=unseen)
                            user_turns = [t for t in unseen if t.actor == "user"]
                            if user_turns:
                                agent_name = self._active_agent_for_event.get(eid)
                                session_id = self._agent_sessions.get(eid, {}).get(agent_name) if agent_name else None
                                if session_id and agent_name:
                                    # Phase 2: Forward user message to agent via session.
                                    # Brain calls send_to_agent() uniformly for all agents.
                                    # Developer.followup() handles Huddle routing internally.
                                    user_text = " ".join(
                                        t.thoughts for t in user_turns if t.thoughts
                                    )
                                    if not user_text:
                                        continue
                                    fwd_task = asyncio.create_task(
                                        self._forward_user_to_agent(eid, agent_name, user_text)
                                    )
                                    self._active_tasks[eid] = fwd_task
                                    continue
                                else:
                                    # No session -- fall back to Phase 1 cancel behavior
                                    await self.cancel_active_task(eid, "User message received")
                                    # Fall through to process_event (don't continue)
                            else:
                                continue
                        else:
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
                    # Skip if event is already being processed (lock held) -- prevents
                    # queued process_event calls that exhaust routing_depth during 429 retries
                    has_unread = any(t.status.value == "delivered" for t in event.conversation)
                    is_waiting = eid in self._waiting_for_user
                    is_locked = eid in self._event_locks and self._event_locks[eid].locked()
                    if has_unread and not is_waiting and not is_locked:
                        await self.process_event(eid, prefetched_event=event)
                    elif not has_unread and not is_locked:
                        time_since_process = time.time() - self._last_processed.get(eid, 0)
                        if not is_waiting and time_since_process > 60:
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

    async def _is_event_closed(self, event_id: str) -> bool:
        """Fresh Redis check: True if event is closed or missing."""
        ev = await self.blackboard.get_event(event_id)
        return not ev or ev.status == EventStatus.CLOSED

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
                reason=description,
            ))
            self._event_plans[event_id] = plan.id
            logger.info(f"Created plan {plan.id} ({action.value}) for event {event_id} -> {service}")
        except Exception as e:
            logger.warning(f"Failed to create plan for event {event_id}: {e}")
