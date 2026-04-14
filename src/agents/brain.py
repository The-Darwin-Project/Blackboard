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
# 9. [Pattern]: Use _append_and_broadcast() for all turn persistence. Direct append_turn only for probe-mode (line ~517).
# 10. [Constraint]: defer_event is blocked when _waiting_for_user -- prevents defer→re-activate→close leak. Automated nudge escalation also sets _waiting_for_user.
# 11. [Constraint]: Event loop has_unread + deferred re-activation paths skip processing when _waiting_for_user.
# 12. [Pattern]: LLM adapter layer (.llm subpackage) -- Brain uses generate_stream(), tool schemas in llm/types.py.
# 13. [Pattern]: brain_thinking + brain_thinking_done WS messages bracket streaming. UI clears on done/turn/error.
# 14. [Pattern]: cancel_active_task() is the single kill path. Cancels asyncio.Task -> CancelledError in base_client -> WS close -> SIGTERM.
# 15. [Pattern]: _active_agent_for_event tracks which agent is running per event. Populated in _run_agent_task, cleaned in finally + cancel + close.
# 16. [Pattern]: _agent_sessions + _agent_session_modes: session resume is mode-aware. Same mode = resume (e.g., investigate->investigate). Cross-mode (investigate->execute) = fresh session to avoid Claude thinking-block corruption.
# 17. [Pattern]: _broadcast() fans out to _broadcast_targets list. register_channel() adds targets (e.g., Slack). All 8 call sites use _broadcast().
# 18. [Pattern]: _build_contents() returns structured [{role, parts}] array from Redis. Redis is single source of truth. No ChatSession.
# 19. [Pattern]: _turn_to_parts() maps ConversationTurn -> provider-agnostic parts. Brain=model role, all others=user role.
# 20. [Gotcha]: Consecutive same-role turns merged into one content block (Gemini requires alternating user/model).
# 21. [Pattern]: response_parts on brain turns preserves thought_signature for Gemini 3 multi-turn function calling.
# 22. [Pattern]: Progressive skills: BrainSkillLoader globs brain_skills/ at startup. _build_system_prompt assembles phase-specific prompt. _resolve_llm_params reads _phase.yaml priority. Feature flag BRAIN_PROGRESSIVE_SKILLS. Legacy: _determine_thinking_params_legacy.
# 23. [Pattern]: _ws_mode ("legacy"/"reverse") gates dispatch path. Reverse uses dispatch_to_agent + registry. Legacy uses agent.process() + per-task WS.
# 24. [Pattern]: Intermediate phase: _process_intermediate runs during active agent execution on non-user turns. Observation-only (zero tools, 256 tokens) unless huddle turns present (reply_to_agent/message_agent, 1024 tokens). Appends brain.think, marks turns EVALUATED.
# 25. [Pattern]: WIP cap: _execute_function_call("select_agent") may recursively call _execute_function_call("defer_event") when dispatch semaphore is locked. This is safe -- defer_event does not recurse back into select_agent. Do NOT add agent-dispatching logic to the defer_event handler.
# 26. [Pattern]: Ephemeral dispatch is two-tier: (a) primary -- headhunter/timekeeper always use ephemeral,
#     (b) overflow -- chat/slack scale to ephemeral when local sidecars are full, gated by {SOURCE}_MAX_ACTIVE env var.
#     Circuit breaker for overflow defers (local was already full); circuit breaker for primary falls back to local.
#     The overflow availability check (get_available) is best-effort, not a reservation -- a race between check
#     and dispatch is tolerable (false positive = unnecessary ephemeral, not a failure).
# 27. [Pattern]: Nudge cascade guard: if an unevaluated automated nudge turn exists, skip injection and fall through to LLM so it evaluates the nudge before escalation fires.
# 28. [Gotcha]: NEVER add `from datetime import ...` inside _execute_function_call. The module-level import (line 59) covers all branches. A local import shadows it for the ENTIRE function per Python scoping, causing UnboundLocalError in branches that don't execute the import.
# 29. [Pattern]: handle_wake_task stores mode from WS wake_register (default implement). Unlike _run_agent_task it does not clear sessions on prior_mode mismatch; wake uses last sidecar context and full-tool mode by design.
# 30. [Pattern]: Message-mode early return in _run_agent_task: when mode=="message", skip result turn
#     and process_event re-entry before is_cancel. Agent's content was delivered via team_send_message
#     progress turns. Intentional exception to rule #9 (_append_and_broadcast for all turns).
#     Safety invariant: team_send_results has notInModes:['message'] in MCP (team-chat-mcp.js).
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
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Optional, TypedDict

from ..models import ConversationTurn, EventDocument, EventStatus, EventType, MessageStatus
from ..ports import BroadcastPort
from .dispatch import dispatch_to_agent, send_cancel, RETRYABLE_SENTINEL


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
    has_slack_participant: bool
    is_intermediate: bool
    has_pending_huddle: bool
    event_domain: str
    domain_confidence: str
    brain_has_classified: bool
    _cached_active_ids: list[str]
    _cached_recent_closed: list[Any]
    _cached_mermaid: str

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

# =============================================================================
# Brain System Prompt - THIS IS THE DECISION ENGINE
# =============================================================================
# DEPRECATED: Monolith fallback. Active path uses brain_skills/*.md via BrainSkillLoader.
# Set BRAIN_PROGRESSIVE_SKILLS=false for emergency rollback only.

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

- **Developer**: Implements code changes, manages branches, opens PRs.
  - `mode: implement` -- Code changes: adding features, fixing bugs, modifying application source code.
    GATE: After Developer completes in implement mode, you MUST dispatch QE (mode: test) to verify BEFORE any PR, merge, or close action. NEVER skip QE verification after implement mode.
  - `mode: execute` -- Single write actions: post MR comment, merge MR, tag release, create branch, run a command.
  - `mode: investigate` (default) -- Read-only: checking MR/PR status, code inspection, status reports.
  - Tools: git, file system, glab, gh

- **QE**: Quality verification agent. Runs tests, verifies deployments.
  - `mode: test` -- Run tests against code, verify deployments via browser (Playwright), quality checks.
  - `mode: investigate` -- Read-only test status checks, inspecting test results.
  - Tools: git, file system, Playwright headless browser, pytest, httpx, curl

Developer and QE are dispatched sequentially. Both share the same workspace volume.

## QE Verification Gate (implement mode)
After Developer reports completion in implement mode:
1. FIRST: dispatch QE (mode: test) to verify the Developer's changes.
2. ONLY AFTER QE reports: proceed with PR/merge/close.
3. NEVER call select_agent(developer, mode=execute) to open/merge a PR without prior QE verification.
4. This gate applies to ALL implement dispatches -- no exceptions.

## Your Job
1. Read the event (anomaly or user request) and its conversation history.
2. Decide the NEXT action by calling ONE of your available functions.
3. You are called repeatedly as the conversation progresses. Each call, you see the full history and decide the next step.

## Slack Notifications
Use notify_user_slack to send a direct message to a user by their email address.
- When an agent recommends notifying someone, call notify_user_slack with the email from the agent's recommendation.
- Use for: pipeline failure alerts, escalations, status updates to specific users.
- The message is delivered as a DM from the Darwin bot in Slack.

## Agent Recommendations
- When an agent's response includes an explicit recommendation or unresolved issue, you MUST either:
  1. Act on it immediately (route to the recommended agent), OR
  2. Use wait_for_user to summarize findings and ask if the user wants you to proceed.
- NEVER silently drop an agent's recommendation.

## Re-Triage on New User Issues
- When a user reports NEW bugs, crashes, errors, or issues within an active event:
  1. Dispatch Developer with `mode: implement`. The QE Verification Gate applies -- QE MUST verify before PR/merge.
  2. Do NOT reuse the previous dispatch mode just because the last dispatch was solo developer.
  3. Multiple distinct issues (2+) or any crash/error report warrants fresh triage.

## Huddle Protocol
- When an agent sends a team_huddle, you will see it as a conversation turn with action="huddle".
- You MUST reply using reply_to_agent(agent_id, message). The agent is blocked until you reply.
- Keep replies concise and actionable. The agent cannot continue until it receives your response.
- If the agent reports completion, acknowledge and let them finish their task.
- If the agent reports a problem, provide specific guidance for the next step.

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
NUDGE_INTERVAL_SECONDS = 1800  # 30 min idle before automated nudge
MAX_NUDGES_BEFORE_ESCALATION = 3  # consecutive nudges before human escalation

# Volume mount paths (must match Helm deployment.yaml)
VOLUME_PATHS = {
    "architect": "/data/gitops-architect",
    "sysadmin": "/data/gitops-sysadmin",
    "developer": "/data/gitops-developer",
    "qe": "/data/gitops-qe",
}

# Progressive skill phase conditions: phase_name -> callable(event, context_flags) -> bool
PHASE_CONDITIONS: dict[str, Any] = {
    "always":       lambda e, c: True,
    "dispatch":     lambda e, c: (c["turn_count"] <= 4 or not c["has_agent_result"]) and c.get("brain_has_classified", False),
    "post-agent":   lambda e, c: c["has_agent_result"],
    "waiting":      lambda e, c: c["is_waiting"],
    "defer-wake":   lambda e, c: c.get("is_defer_wakeup", False),
    "context":      lambda e, c: c["has_related"] or c["has_graph_edges"] or c["has_recent_closed"],
    "source":       lambda e, c: True,
    "multi-user":   lambda e, c: c.get("has_slack_participant", False),
    "intermediate": lambda e, c: c.get("is_intermediate", False),
    "coordination": lambda e, c: c.get("has_pending_huddle", False),
}

# Phase exclusion matrix (cleanSlate): active phase -> phases to exclude
PHASE_EXCLUSIONS: dict[str, list[str]] = {
    "post-agent":   ["dispatch"],
    "defer-wake":   ["dispatch"],
    "waiting":      ["dispatch", "post-agent", "defer-wake"],
    "intermediate": ["dispatch", "post-agent", "defer-wake", "waiting", "context"],
}

# Context priming: synthetic prefill so the LLM treats protocols as already-committed.
# Update BRAIN_PREFILL_MODEL if always/ skill protocols change materially.
BRAIN_PREFILL_USER = "Session active. Review your core protocols before processing."

BRAIN_PREFILL_MODEL = (
    "Darwin Brain active. Core protocols confirmed: "
    "(1) Consult deep memory before routing or deferring -- "
    "historical timing overrides agent estimates. "
    "(2) Cynefin triage on every new event. "
    "(3) Never silently drop agent recommendations. "
    "(4) Source-aware close rules. "
    "Ready for event processing."
)


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
        broadcast: Optional[BroadcastPort] = None,
    ):
        self.blackboard = blackboard
        self.agents = agents or {}
        self._broadcast_targets: list[BroadcastPort] = []
        if broadcast:
            self._broadcast_targets.append(broadcast)
        self._running = False
        self._llm_available = False
        self._active_tasks: dict[str, asyncio.Task] = {}  # event_id -> running task
        self._active_agent_for_event: dict[str, str] = {}  # event_id -> agent_name
        self._routing_turn_for_event: dict[str, int] = {}  # event_id -> turn number when agent was dispatched
        self._agent_sessions: dict[str, dict[str, str]] = {}  # event_id -> {agent_name -> session_id}
        self._agent_session_modes: dict[str, dict[str, str]] = {}  # event_id -> {agent_name -> mode}
        self._routing_depth: dict[str, int] = {}  # event_id -> recursion counter
        # Per-agent locks -- prevents concurrent dispatch to the same agent
        from collections import defaultdict
        self._agent_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Per-event locks -- prevents concurrent process_event calls for same event
        self._event_locks: dict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        # Wait-for-user state: events where LLM called wait_for_user
        self._waiting_for_user: set[str] = set()
        self._incident_created: set[str] = set()
        # Last process_event timestamp per event (for idle safety net)
        self._last_processed: dict[str, float] = {}
        # Journal cache: avoid LRANGE per prompt build (60s TTL, invalidated on close)
        self._journal_cache: dict[str, tuple[float, list[str]]] = {}
        # LLM config from environment
        self.project = os.getenv("GCP_PROJECT", "")
        self.location = os.getenv("GCP_LOCATION", "global")
        self.provider = os.getenv("LLM_PROVIDER", "gemini")
        self.temperature = float(os.getenv("LLM_TEMPERATURE_BRAIN", "0.8"))
        self.model_name = os.getenv("LLM_MODEL_BRAIN", "gemini-3.1-pro-preview")
        self.max_output_tokens = int(os.getenv("LLM_MAX_TOKENS_BRAIN", "65000"))
        self._adapter = None  # Lazy-loaded via _get_adapter()
        self._ws_mode = os.getenv("AGENT_WS_MODE", "legacy")
        self._ephemeral_provisioner = None
        # Progressive skill loading (feature flag)
        self._progressive_skills = os.getenv("BRAIN_PROGRESSIVE_SKILLS", "true").lower() == "true"
        self._skill_loader = None
        if self._progressive_skills:
            try:
                from .brain_skill_loader import BrainSkillLoader
                skills_path = Path(__file__).parent / "brain_skills"
                self._skill_loader = BrainSkillLoader(str(skills_path))
            except Exception as e:
                logger.warning(f"Failed to load brain skills: {e}. Falling back to monolith.")
                self._skill_loader = None
        # Global dispatch WIP cap (flow engineering: Peak Throughput Principle)
        max_dispatches = int(os.getenv("BRAIN_MAX_CONCURRENT_DISPATCHES", "0"))
        self._dispatch_semaphore = asyncio.Semaphore(max_dispatches) if max_dispatches > 0 else None

        skills_status = f"progressive ({len(self._skill_loader.available_phases())} phases)" if self._skill_loader else "monolith"
        wip_status = f"wip_cap={max_dispatches}" if max_dispatches > 0 else "wip_cap=off"
        logger.info(f"Brain initialized (provider={self.provider}, model={self.model_name}, skills={skills_status}, {wip_status}, agents={list(self.agents.keys())})")

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
        # on the same service + same MR (if headhunter). Close as duplicate if found.
        # Skip for user-initiated sources (chat/slack) -- "general" service is a catch-all,
        # not a meaningful dedup key. Users intentionally start new conversations.
        if not event.conversation and event.source not in ("chat", "slack"):
            active_ids = await self.blackboard.get_active_events()
            new_ctx = (getattr(event.event.evidence, "gitlab_context", None) or {}) if (event.event and event.event.evidence) else {}
            new_mr = new_ctx.get("mr_iid")
            new_project = new_ctx.get("project_id")
            for eid in active_ids:
                if eid == event_id:
                    continue
                existing = await self.blackboard.get_event(eid)
                if not (existing
                        and existing.service == event.service
                        and existing.conversation
                        and existing.status.value in ("active", "new", "deferred")):
                    continue
                # Same service -- but if both have GitLab context, require same project + MR
                ex_ctx = (getattr(existing.event.evidence, "gitlab_context", None) or {}) if (existing.event and existing.event.evidence) else {}
                ex_mr = ex_ctx.get("mr_iid")
                ex_project = ex_ctx.get("project_id")
                if new_project and ex_project and new_project != ex_project:
                    continue
                if new_mr and ex_mr and new_mr != ex_mr:
                    continue
                logger.info(
                    f"Closing duplicate event {event_id} -- "
                    f"existing event {eid} already handling {event.service}"
                    f"{f' MR !{ex_mr}' if ex_mr else ''}"
                )
                await self._close_and_broadcast(
                    event_id,
                    f"Duplicate: merged with existing event {eid} for {event.service}.",
                    close_reason="duplicate",
                )
                return

        # Value stream: stamp first processing time (after dedup gate, skip re-entry after defer)
        if event.processing_started_at is None:
            await self.blackboard.stamp_event(event_id, processing_started_at=time.time())

        if not event.conversation:
            await self.blackboard.record_event(
                EventType.BRAIN_EVENT_CREATED,
                {"event_id": event_id, "service": event.service, "source": event.source},
                narrative=f"New event {event_id} ({event.service}): {event.event.reason[:80] if event.event else 'unknown'}",
            )

        # Circuit breaker: count only agent execution turns (not brain routing, aligner, user)
        agent_turns = sum(
            1 for t in event.conversation
            if t.actor in ("architect", "sysadmin", "developer", "qe")
        )
        if agent_turns >= MAX_TURNS_PER_EVENT:
            logger.warning(f"Event {event_id} hit max agent turns ({agent_turns}/{MAX_TURNS_PER_EVENT})")
            await self._close_and_broadcast(
                event_id,
                f"TIMEOUT: Event exceeded {MAX_TURNS_PER_EVENT} agent execution turns. Force closed.",
                close_reason="timeout",
            )
            return

        # Lifecycle: transition NEW -> ACTIVE on first processing
        if event.status == EventStatus.NEW:
            if await self.blackboard.transition_event_status(event_id, "new", EventStatus.ACTIVE):
                logger.info(f"Event {event_id} transitioned NEW -> ACTIVE")

        # Health check: nudge idle events, escalate to human after max nudges.
        # Guards: skip if deferred (intentional wait), waiting for user, or last real turn is brain.defer (just woke).
        if event.conversation and event_id not in self._waiting_for_user:
            last_real_turn = next(
                (t for t in reversed(event.conversation)
                 if not (t.actor == "user" and t.source == "automated")),
                None,
            )
            if last_real_turn and last_real_turn.actor == "brain" and last_real_turn.action == "defer":
                pass  # Just woke from defer -- defer-wake handles re-activation
            elif last_real_turn:
                inactivity = time.time() - last_real_turn.timestamp
                if inactivity > NUDGE_INTERVAL_SECONDS:
                    has_pending_nudge = any(
                        t.actor == "user" and t.source == "automated"
                        and t.status.value in ("sent", "delivered")
                        for t in event.conversation
                    )
                    if has_pending_nudge:
                        pass  # Let LLM evaluate the existing nudge before injecting more

                    else:
                        consecutive_nudges = 0
                        for t in reversed(event.conversation):
                            if t.actor == "user" and t.source == "automated":
                                consecutive_nudges += 1
                            else:
                                break

                        if consecutive_nudges >= MAX_NUDGES_BEFORE_ESCALATION:
                            await self._escalate_to_human(event_id, event, consecutive_nudges, inactivity)
                            return

                        idle_min = int(inactivity // 60)
                        nudge_turn = ConversationTurn(
                            turn=len(event.conversation) + 1,
                            actor="user",
                            action="message",
                            source="automated",
                            thoughts=f"Automated health check: this event has been idle for {idle_min} minutes with no progress. Evaluate the current state and take action: route an agent to check status, defer with a reason, or close if resolved.",
                        )
                        await self._append_and_broadcast(event_id, nudge_turn)
                        logger.info(f"Nudge injected for {event_id} ({consecutive_nudges + 1}/{MAX_NUDGES_BEFORE_ESCALATION})")
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

        # Determine defer-wake state ONCE before the iterative loop.
        # Persists across iterations so tool stripping survives lookup re-invocations.
        # Uses defer-vs-route timestamp comparison so intermediate turns (brain.think,
        # brain.wait from intermediate phase during deferral) don't break detection.
        last_defer = next(
            (t for t in reversed(event.conversation)
             if t.actor == "brain" and t.action == "defer"),
            None,
        )
        last_route = next(
            (t for t in reversed(event.conversation)
             if t.actor == "brain" and t.action == "route"),
            None,
        )
        is_defer_wake = bool(
            last_defer
            and (not last_route or last_defer.timestamp > last_route.timestamp)
        )

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
            should_continue = await self._process_with_llm(
                event_id, event, is_defer_wake=is_defer_wake,
            )
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
        *,
        is_defer_wake: bool = False,
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
            if is_defer_wake:
                context_flags["is_defer_wakeup"] = True
                context_flags["consecutive_defers"] = max(context_flags.get("consecutive_defers", 0), 1)
            active_phases = self._match_phases(event, context_flags)
            system_prompt = self._build_system_prompt(event, active_phases, context_flags)
            thinking_level, call_temp, phase_max_tokens = self._resolve_llm_params(active_phases)
        else:
            system_prompt = BRAIN_SYSTEM_PROMPT
            thinking_level, call_temp = self._determine_thinking_params_legacy(event)
            phase_max_tokens = self.max_output_tokens
            context_flags = None

        # Strip defer_event on defer-wake -- forces Brain to act (route/close/escalate)
        active_tools = BRAIN_TOOL_SCHEMAS
        if is_defer_wake:
            active_tools = [t for t in BRAIN_TOOL_SCHEMAS if t["name"] != "defer_event"]
            logger.info(f"Defer-wake: stripped defer_event from tools for {event_id}")

        # refresh_gitlab_context: only available during triage (post-classify, pre-agent) and defer-wake.
        # Stripped after first use as defense-in-depth against loops.
        is_triage = (
            context_flags
            and context_flags.get("brain_has_classified", False)
            and not context_flags.get("has_agent_result", False)
        )
        refresh_allowed = is_triage or is_defer_wake
        if not refresh_allowed:
            active_tools = [t for t in active_tools if t["name"] != "refresh_gitlab_context"]
        else:
            # Anchor to the last defer turn -- any verify after it means we already refreshed.
            # Prevents the 3-turn sliding window from re-enabling refresh across reprocessing cycles.
            last_defer_ts = next(
                (t.timestamp for t in reversed(event.conversation)
                 if t.actor == "brain" and t.action == "defer"),
                0,
            )
            recent_refresh = any(
                t.actor == "brain" and t.action == "verify" and "MR State:" in (t.thoughts or "")
                and t.timestamp >= last_defer_ts
                for t in event.conversation
            )
            if recent_refresh:
                active_tools = [t for t in active_tools if t["name"] != "refresh_gitlab_context"]
                logger.info(f"Refresh already done: stripped refresh_gitlab_context for {event_id}")

        # refresh_kargo_context: same availability window, only when kargo_context present.
        has_kargo = (
            event.event and event.event.evidence
            and hasattr(event.event.evidence, "kargo_context")
            and event.event.evidence.kargo_context
        )
        if not has_kargo:
            active_tools = [t for t in active_tools if t["name"] != "refresh_kargo_context"]
        elif not refresh_allowed:
            active_tools = [t for t in active_tools if t["name"] != "refresh_kargo_context"]
        else:
            last_defer_ts_k = next(
                (t.timestamp for t in reversed(event.conversation)
                 if t.actor == "brain" and t.action == "defer"),
                0,
            )
            recent_kargo_refresh = any(
                t.actor == "brain" and t.action == "verify" and "Kargo Stage:" in (t.thoughts or "")
                and t.timestamp >= last_defer_ts_k
                for t in event.conversation
            )
            if recent_kargo_refresh:
                active_tools = [t for t in active_tools if t["name"] != "refresh_kargo_context"]
                logger.info(f"Refresh already done: stripped refresh_kargo_context for {event_id}")

        # Domain classification gate: mandatory classify_event before any agent dispatch
        if context_flags and not context_flags.get("brain_has_classified", False):
            pre_classify_tools = {"lookup_service", "lookup_journal", "consult_deep_memory", "classify_event"}
            active_tools = [t for t in active_tools if t["name"] in pre_classify_tools]
            logger.info(f"Pre-classification gate: only lookup+classify tools for {event_id}")
        elif context_flags:
            domain = context_flags.get("event_domain", "complicated")
            if domain == "clear":
                active_tools = [t for t in active_tools if t["name"] != "create_plan"]
                logger.info(f"CLEAR domain: create_plan gated (act directly) for {event_id}")
            elif domain == "complex":
                agent_rounds = sum(1 for t in event.conversation if t.actor not in ("brain", "user", "aligner"))
                if agent_rounds < 4:
                    active_tools = [t for t in active_tools if t["name"] != "close_event"]
                    logger.info(f"COMPLEX domain: close_event gated until 4+ agent rounds ({agent_rounds} so far) for {event_id}")
            elif domain == "chaotic":
                chaotic_tools = {"select_agent", "classify_event", "lookup_service", "lookup_journal", "notify_user_slack", "get_plan_progress", "create_incident"}
                active_tools = [t for t in active_tools if t["name"] in chaotic_tools]
                logger.info(f"CHAOTIC domain: restricted to act-first tool set for {event_id}")

        prompt = await self._build_contents(event, context_cache=context_flags)

        prompt = [
            {"role": "user", "parts": [{"text": BRAIN_PREFILL_USER}]},
            {"role": "model", "parts": [{"text": BRAIN_PREFILL_MODEL}]},
        ] + prompt

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
                    tools=active_tools,
                    temperature=call_temp,
                    max_output_tokens=phase_max_tokens,
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
                    is_rate_limit = "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) or "Quota exhausted" in str(e)
                    base = 30 if is_rate_limit else 5
                    delay = min(base * (2 ** attempt), 120)
                    jitter = delay * 0.3 * (0.5 - __import__('random').random())
                    delay = max(1, delay + jitter)
                    logger.warning(f"Brain LLM transient error for {event_id} (attempt {attempt+1}/{max_retries+1}, {'rate-limit' if is_rate_limit else 'transient'}): {e}. Retrying in {delay:.0f}s...")
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
            await self._append_and_broadcast(event_id, turn)
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
            await self._append_and_broadcast(event_id, turn)
            return False

        logger.warning(f"Brain LLM returned empty response for {event_id}")
        return False

    async def _process_intermediate(
        self, event_id: str, event: EventDocument, turns: list[ConversationTurn]
    ) -> None:
        """Process intermediate turns (agent progress, aligner confirms) with a lightweight LLM call.

        Observation-only (zero tools, 256 tokens) unless huddle turns present
        (reply_to_agent/message_agent, 1024 tokens).
        Appends brain.think turn for temporal context; marks processed turns EVALUATED.
        """
        if not self._adapter:
            logger.warning("_process_intermediate skipped: no LLM adapter")
            return

        from .llm import BRAIN_TOOL_SCHEMAS
        intermediate_tools = [
            t for t in BRAIN_TOOL_SCHEMAS
            if t["name"] in ("reply_to_agent", "message_agent", "wait_for_agent")
        ]
        huddle_turns = [t for t in turns if t.action == "huddle"]
        max_tokens = 1024 if huddle_turns else 256

        ctx: ContextFlags = {
            "is_intermediate": True,
            "has_pending_huddle": bool(huddle_turns),
            "turn_count": len(event.conversation),
            "has_agent_result": False,
            "is_waiting": False,
            "is_defer_wakeup": False,
            "has_related": False,
            "has_graph_edges": False,
            "has_recent_closed": False,
            "has_slack_participant": False,
            "source": event.source,
            "service": event.service or "",
        }
        active_phases = self._match_phases(event, ctx)
        system_prompt = self._build_system_prompt(event, active_phases, ctx)
        thinking_level, call_temp, phase_max_tokens = self._resolve_llm_params(active_phases)
        contents = await self._build_contents(event, context_cache=ctx)
        await self._broadcast({
            "type": "brain_thinking", "event_id": event_id,
            "text": "", "accumulated": "", "is_thought": True,
        })
        if huddle_turns:
            from ..dependencies import get_registry_and_bridge
            registry, _ = get_registry_and_bridge()
            if registry:
                agent_conn = await registry.get_by_event(event_id)
                if agent_conn and agent_conn.ws:
                    try:
                        await agent_conn.ws.send_json({
                            "type": "proactive_message",
                            "from": "brain",
                            "content": "Brain received your huddle and is evaluating. Stand by.",
                        })
                    except Exception as e:
                        logger.debug("Huddle ack send failed for %s: %s", event_id, e)
        accumulated_text = ""
        function_call = None
        try:
            async for chunk in self._adapter.generate_stream(
                system_prompt=system_prompt,
                contents=contents,
                tools=intermediate_tools,
                temperature=call_temp,
                max_output_tokens=min(max_tokens, phase_max_tokens),
                thinking_level=thinking_level,
            ):
                if chunk.text:
                    accumulated_text += chunk.text
                if chunk.function_call:
                    function_call = chunk.function_call
        except Exception as e:
            logger.warning(f"Intermediate LLM call failed for {event_id}: {e}")
        await self._broadcast({"type": "brain_thinking_done", "event_id": event_id})

        # State guard: event may have been deferred/closed during the LLM call
        fresh = await self.blackboard.get_event(event_id)
        if not fresh or fresh.status.value != "active":
            logger.info(
                f"Intermediate result discarded for {event_id}: "
                f"status changed to {fresh.status.value if fresh else 'deleted'}"
            )
            up_to = max(t.turn for t in turns) + 1
            await self.blackboard.mark_turns_evaluated(event_id, up_to_turn=up_to)
            evaluated_turns = [t.turn for t in turns if t.turn < up_to]
            if evaluated_turns:
                await self._broadcast_status_update(event_id, "evaluated", turns=evaluated_turns)
            return

        if accumulated_text:
            turn = ConversationTurn(
                turn=len(event.conversation) + 1,
                actor="brain",
                action="think",
                thoughts=accumulated_text,
            )
            await self._append_and_broadcast(event_id, turn)
            logger.info(f"Appended turn {turn.turn} (brain.think) to event {event_id}")

        if function_call and function_call.name in ("reply_to_agent", "message_agent", "wait_for_agent"):
            await self._execute_function_call(
                event_id, function_call.name, function_call.args or {},
            )

        tool_names = [t["name"] for t in intermediate_tools] or ["none"]
        up_to = max(t.turn for t in turns) + 1
        await self.blackboard.mark_turns_evaluated(event_id, up_to_turn=up_to)
        evaluated_turns = [t.turn for t in turns if t.turn < up_to]
        if evaluated_turns:
            await self._broadcast_status_update(event_id, "evaluated", turns=evaluated_turns)
        logger.info(
            f"Intermediate: processed {len(turns)} turns for {event_id} "
            f"(phases: {active_phases}, tools: {tool_names})"
        )

    @staticmethod
    def _is_transient(e: Exception) -> bool:
        """Check if exception is a transient rate-limit or availability error."""
        from .llm.quota_tracker import QuotaExhaustedError
        if isinstance(e, QuotaExhaustedError):
            return True
        err_str = str(e)
        return any(code in err_str for code in ["429", "503", "RESOURCE_EXHAUSTED", "UNAVAILABLE"])

    def _resolve_llm_params(self, active_phases: list[str]) -> tuple[str, float, int]:
        """Resolve thinking_level + temperature + max_output_tokens from phase metadata.

        Most specific phase wins (lowest priority number).
        Falls back to legacy heuristic if loader unavailable.
        """
        if not self._skill_loader:
            return "high", 0.5, self.max_output_tokens

        best_priority = float("inf")
        best_thinking = "high"
        best_temp = 0.5
        best_tokens = self.max_output_tokens

        for phase_name in active_phases:
            meta = self._skill_loader.get_phase_meta(phase_name)
            if meta and "thinking_level" in meta:
                priority = meta.get("priority", 50)
                if priority < best_priority:
                    best_priority = priority
                    best_thinking = meta["thinking_level"]
                    best_temp = meta.get("temperature", 0.5)
                    best_tokens = meta.get("max_output_tokens", self.max_output_tokens)

        logger.debug(f"LLM params: thinking={best_thinking}, temp={best_temp}, tokens={best_tokens} (priority={best_priority})")
        return best_thinking, best_temp, best_tokens

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

        flags["has_agent_result"] = any(
            t.actor not in ("brain", "user", "aligner") for t in event.conversation
        )
        recent = event.conversation[-3:] if event.conversation else []
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
        if getattr(event, "subject_type", "service") != "kargo_stage":
            try:
                mermaid = await self.blackboard.generate_mermaid()
            except Exception:
                pass
        flags["_cached_mermaid"] = mermaid
        flags["has_graph_edges"] = bool(mermaid and "-->" in mermaid)

        flags["has_aligner_turns"] = any(
            t.actor == "aligner" for t in event.conversation
        )
        flags["has_slack_participant"] = bool(
            event.slack_thread_ts
            and any(t.actor == "user" and t.source == "slack" for t in event.conversation)
        )
        flags["has_pending_huddle"] = any(
            t.action == "huddle" and t.status.value != "evaluated"
            for t in event.conversation
        )

        consecutive_defers = 0
        for t in reversed(event.conversation):
            if t.actor == "brain" and t.action == "defer":
                consecutive_defers += 1
            elif t.actor == "brain" and t.action in ("think", "tool_result", "wait"):
                continue
            else:
                break
        flags["is_defer_wakeup"] = consecutive_defers > 0
        flags["consecutive_defers"] = consecutive_defers

        consecutive_waits = 0
        for t in reversed(event.conversation):
            if t.actor == "brain" and t.action == "wait" and t.waitingFor == "agent":
                consecutive_waits += 1
            elif t.actor == "brain" and t.action in ("think", "tool_result"):
                continue
            else:
                break
        flags["consecutive_agent_waits"] = consecutive_waits

        from ..models import EventEvidence
        evidence = event.event.evidence
        if isinstance(evidence, EventEvidence):
            flags["event_domain"] = evidence.brain_domain or evidence.domain
            flags["domain_confidence"] = evidence.domain_confidence
            flags["brain_has_classified"] = evidence.brain_domain is not None
        else:
            flags["event_domain"] = "complicated"
            flags["domain_confidence"] = "default"
            flags["brain_has_classified"] = False

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
        context_flags: dict | None = None,
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

        # Evidence-driven context: inject Kargo skills when kargo_context is present
        if (event.event and event.event.evidence
                and hasattr(event.event.evidence, "kargo_context")
                and event.event.evidence.kargo_context):
            kargo_skills = self._skill_loader.find_by_tag("kargo")
            resolved_contents.extend(kargo_skills)

        if "post-agent" in active_phases:
            rec = self._surface_agent_recommendation(event)
            if rec:
                has_explicit = "LATEST AGENT RECOMMENDATION" in rec
                logger.debug(f"Agent recommendation surfaced for {event.id}: {'explicit' if has_explicit else 'ask-agent directive'} ({len(rec)} chars)")
                resolved_contents.append(rec)

        if "defer-wake" in active_phases and context_flags:
            consecutive = context_flags.get("consecutive_defers", 0)
            raw_reason = next(
                (t.thoughts for t in reversed(event.conversation)
                 if t.actor == "brain" and t.action == "defer"),
                "unknown",
            )
            last_reason = raw_reason.split(": ", 1)[1] if ": " in raw_reason else raw_reason
            last_agent = next(
                (t for t in reversed(event.conversation)
                 if t.actor not in ("brain", "user", "aligner")),
                None,
            )
            elapsed_str = ""
            if last_agent:
                elapsed_min = int((time.time() - last_agent.timestamp) / 60)
                elapsed_str = (
                    f"Time elapsed since last {last_agent.actor} response "
                    f"({last_agent.action}): {elapsed_min} minutes."
                )
            resolved_contents.append(
                f"**DEFER WAKE-UP ({consecutive}x):** {last_reason}\n"
                f"{elapsed_str}\n"
                f"The defer_event tool is not available. You must take action: route an agent to verify current state, close, or escalate."
            )

        if context_flags and context_flags.get("consecutive_agent_waits", 0) >= 2:
            waits = context_flags["consecutive_agent_waits"]
            resolved_contents.append(
                f"**WAIT LOOP DETECTED ({waits}x consecutive wait_for_agent):** "
                f"No agent has responded since your last {waits} waits. "
                f"The agent may have finished but returned an unclear result. "
                f"Use message_agent or ask_agent_for_state to check on the agent's status, "
                f"or use get_plan_progress to check the plan, "
                f"or close_event if the task appears complete, "
                f"or wait_for_user to ask the user what to do."
            )

        prompt = "\n\n---\n\n".join(resolved_contents)

        total_tokens = len(prompt) // 4
        phase_str = ", ".join(active_phases)
        logger.info(f"Brain skills: [{phase_str}] ({total_tokens} tokens) for {event.id}")

        return prompt

    @staticmethod
    def _surface_agent_recommendation(event: EventDocument) -> str | None:
        """Extract and promote last agent's recommendation to system-level priority.
        Skips if a brain.defer already addressed it (prevents stale defer loops).
        """
        last_agent_turn = next(
            (t for t in reversed(event.conversation)
             if t.actor not in ("brain", "user", "aligner")),
            None,
        )
        if not last_agent_turn:
            return None

        agent_idx = event.conversation.index(last_agent_turn)
        has_defer_after = any(
            t.actor == "brain" and t.action == "defer"
            for t in event.conversation[agent_idx + 1:]
        )
        if has_defer_after:
            return None

        result_text = last_agent_turn.result or last_agent_turn.thoughts or ""
        rec = Brain._extract_recommendation(result_text)

        # QE gate: if last dispatch was mode=implement and developer reported,
        # inject QE verification regardless of recommendation content
        last_route = next(
            (t for t in reversed(event.conversation)
             if t.actor == "brain" and t.action == "route" and t.taskForAgent),
            None,
        )
        was_implement = (
            last_route and last_route.taskForAgent
            and last_route.taskForAgent.get("mode") == "implement"
            and last_agent_turn.actor == "developer"
        )
        if was_implement:
            qe_gate = (
                "\n\n## QE VERIFICATION GATE (mandatory)\n"
                "The Developer completed work in implement mode. "
                "You MUST dispatch QE (mode: test) to verify before any PR, merge, or close action."
            )
            base_rec = rec or ""
            ts = datetime.fromtimestamp(last_agent_turn.timestamp, tz=timezone.utc).strftime("%H:%M:%S") if last_agent_turn.timestamp else "unknown"
            return (
                f"## LATEST AGENT RESULT (from {last_agent_turn.actor}, "
                f"turn {agent_idx + 1}/{len(event.conversation)}, at {ts})\n"
                f"{base_rec}{qe_gate}"
            )

        if rec:
            ts = datetime.fromtimestamp(last_agent_turn.timestamp, tz=timezone.utc).strftime("%H:%M:%S") if last_agent_turn.timestamp else "unknown"
            return (
                f"## LATEST AGENT RECOMMENDATION (from {last_agent_turn.actor}, "
                f"turn {agent_idx + 1}/{len(event.conversation)}, at {ts})\n"
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
            if evidence.brain_domain:
                lines.append(f"Domain: {evidence.brain_domain} (Brain-assessed)")
            elif evidence.domain_confidence == "assessed":
                lines.append(f"Domain: {evidence.domain} (source-assessed)")
            else:
                lines.append(f"Domain: DISORDER (unclassified -- you must call classify_event)")
            eff_severity = evidence.brain_severity or evidence.severity
            lines.append(f"Severity: {eff_severity}")
            now = time.time()
            if evidence.gitlab_context:
                gl = evidence.gitlab_context
                lines.append("")
                lines.append("GitLab Context:")
                lines.append(f"  Project: {gl.get('project_path', '')}")
                lines.append(f"  MR: !{gl.get('mr_iid', '')} - {gl.get('mr_title', '')}")
                lines.append(f"  MR URL: {gl.get('target_url', '')}")
                lines.append(f"  Pipeline: {gl.get('pipeline_status', 'unknown')}")
                lines.append(f"  Merge Status: {gl.get('merge_status', '')}")
                lines.append(f"  Source Branch: {gl.get('source_branch', '')}")
                lines.append(f"  Author: {gl.get('author', '')}")
                todo_ts = gl.get("todo_created_at", "")
                if todo_ts:
                    try:
                        dt = datetime.fromisoformat(todo_ts.replace("Z", "+00:00"))
                        gl_age = int(now - dt.timestamp())
                        gl_min, gl_sec = divmod(gl_age, 60)
                        lines.append(f"  GitLab Event Age: {gl_min}m {gl_sec}s ago")
                    except (ValueError, TypeError):
                        pass
                maintainer = gl.get("maintainer", {})
                if maintainer:
                    emails = maintainer.get("emails", [])
                    if emails:
                        lines.append(f"  Maintainer Emails: {', '.join(emails)}")
                logger.debug("Brain prompt includes gitlab_context for event %s", event.id)
        else:
            now = time.time()

        if event.queued_at:
            queue_age = int(now - event.queued_at)
            q_min, q_sec = divmod(queue_age, 60)
            lines.append(f"Event Created: {q_min}m {q_sec}s ago")
        if event.queued_at and event.processing_started_at:
            wait = int(event.processing_started_at - event.queued_at)
            w_min, w_sec = divmod(wait, 60)
            lines.append(f"Queue Wait: {w_min}m {w_sec}s")

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

        if event.source != "headhunter":
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
            last_entry = journal[-1] if journal else "none"
            lines.append(f"Service ops journal available ({len(journal)} entries). Last: {last_entry}")
            lines.append("  (Use lookup_journal for full history or other services)")

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
        tool_result turns get markdown-formatted evidence with thought_signature extracted.
        User/agent turns use text from thoughts/result/evidence fields.
        Image turns embed the image bytes inline in the parts array.
        """
        if turn.actor == "brain" and turn.action == "tool_result":
            tool_name = turn.waitingFor or "tool"
            text = f"## Tool Result: {tool_name}\n\n{turn.evidence or turn.thoughts or ''}"
            parts: list[dict] = [{"text": text}]
            if turn.response_parts:
                for rp in turn.response_parts:
                    if rp.get("thought_signature"):
                        parts[0]["thought_signature"] = rp["thought_signature"]
                        break
            return parts

        if turn.actor == "brain" and turn.response_parts:
            return list(turn.response_parts)

        text = ""
        if turn.actor == "brain":
            text = turn.thoughts or ""
            if turn.evidence:
                text = f"{text}\n{turn.evidence}" if text else turn.evidence
        elif turn.actor == "user":
            if turn.user_name:
                text = f"[{turn.user_name} via {turn.source or 'dashboard'}]: {turn.thoughts or turn.result or ''}"
            else:
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

            # WIP cap: try-acquire, defer if at capacity (Peak Throughput Principle)
            if self._dispatch_semaphore and self._dispatch_semaphore.locked():
                flow = await self.blackboard.get_flow_metrics()
                logger.warning(
                    f"Dispatch WIP cap reached for {event_id}, deferring "
                    f"(queue_depth={flow['queue_depth']}, active={len(self._active_tasks)})"
                )
                await self._execute_function_call(
                    event_id, "defer_event",
                    {"delay_seconds": 30, "reason": "Dispatch WIP cap reached"},
                    response_parts=None,
                )
                return False

            # Recursion guard (resets on user interaction via clear_waiting)
            depth = self._routing_depth.get(event_id, 0) + 1
            if depth > 30:
                logger.warning(f"Event {event_id} hit routing depth limit (30)")
                await self._close_and_broadcast(event_id, "Agent routing loop detected. Force closed.", close_reason="force_closed")
                return False
            self._routing_depth[event_id] = depth

            # Value stream: stamp dispatch time (overwrites on multi-agent events)
            await self.blackboard.stamp_event(event_id, last_dispatched_at=time.time())

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
            await self._append_and_broadcast(event_id, turn)
            await self.blackboard.record_event(
                EventType.BRAIN_AGENT_ROUTED,
                {"event_id": event_id, "agent": agent_name},
                narrative=f"Routed {event_id} to {agent_name}: {task[:80]}",
            )

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

            # Launch agent task (non-blocking)
            # QE has no Python agent class -- allow reverse-WS dispatch without one
            agent = self.agents.get(agent_name)
            if agent or (self._ws_mode == "reverse" and agent_name not in ("_aligner", "_archivist_memory")):
                event_md_path = f"./events/event-{event_id}.md"
                task_coro = self._run_agent_task(
                    event_id, agent_name, agent, task, event_md_path,
                    routing_turn_num=turn.turn, mode=mode,
                )
                self._active_tasks[event_id] = asyncio.create_task(task_coro)
            else:
                logger.error(f"Agent '{agent_name}' not found in agents dict")
            return False

        elif function_name == "reply_to_agent":
            agent_id = args.get("agent_id", "")
            message = args.get("message", "")
            from ..dependencies import get_registry_and_bridge
            registry, _ = get_registry_and_bridge()
            agent_conn = None
            if registry:
                agent_conn = await registry.get_by_id(agent_id)
                if not agent_conn:
                    agent_conn = await registry.get_by_event(event_id)
                if not agent_conn:
                    agent_conn = await registry.get_available(agent_id)
            if agent_conn and agent_conn.ws:
                try:
                    await agent_conn.ws.send_json({
                        "type": "huddle_reply",
                        "task_id": agent_conn.current_task_id or "",
                        "content": message,
                    })
                    logger.info(f"Brain reply_to_agent -> {agent_id} ({len(message)} chars)")
                except Exception as e:
                    logger.warning(f"Failed to send reply_to_agent to {agent_id}: {e}")
            else:
                logger.warning(f"reply_to_agent: agent {agent_id} not found or disconnected")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="reply",
                thoughts=f"Reply to {agent_id}: {message}",
            )
            await self._append_and_broadcast(event_id, turn)
            return False

        elif function_name == "message_agent":
            agent_name = args.get("agent_id", "")
            message = args.get("message", "")

            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="message",
                thoughts=f"Message to {agent_name}: {message}",
                selectedAgents=[agent_name],
            )
            await self._append_and_broadcast(event_id, turn)

            from ..dependencies import get_registry_and_bridge
            registry, _ = get_registry_and_bridge()

            if event_id in self._active_tasks and not self._active_tasks[event_id].done():
                if registry:
                    agent_conn = await registry.get_by_event(event_id)
                    if not agent_conn:
                        agent_conn = await registry.get_available(agent_name)
                    if agent_conn and agent_conn.ws:
                        try:
                            await agent_conn.ws.send_json({
                                "type": "proactive_message",
                                "from": "brain",
                                "content": message,
                            })
                            logger.info(f"Brain message_agent -> {agent_name} (busy, inbox) ({len(message)} chars)")
                        except Exception as e:
                            logger.warning(f"Failed to send message to {agent_name}: {e}")
                return False

            agent_conn = await registry.get_available(agent_name) if registry else None

            if agent_conn:
                await self.write_event_to_volume(event_id, agent_name)
                agent = self.agents.get(agent_name)
                if agent or (self._ws_mode == "reverse" and agent_name not in ("_aligner", "_archivist_memory")):
                    event_md_path = f"./events/event-{event_id}.md"
                    task_coro = self._run_agent_task(
                        event_id, agent_name, agent, message, event_md_path,
                        routing_turn_num=turn.turn, mode="message",
                    )
                    self._active_tasks[event_id] = asyncio.create_task(task_coro)
                    logger.info(f"Brain message_agent -> {agent_name} (idle, dispatch) ({len(message)} chars)")
                else:
                    logger.warning(f"message_agent: no agent class for role {agent_name}")
            else:
                if registry:
                    busy_conn = await registry.get_by_role(agent_name)
                    if not busy_conn:
                        busy_conn = await registry.get_by_event(event_id)
                    if busy_conn and busy_conn.ws:
                        try:
                            await busy_conn.ws.send_json({
                                "type": "proactive_message",
                                "from": "brain",
                                "content": message,
                            })
                            logger.info(f"Brain message_agent -> {agent_name} (busy fallback, inbox) ({len(message)} chars)")
                        except Exception as e:
                            logger.warning(f"Failed to send message to {agent_name}: {e}")
                    else:
                        logger.warning(f"message_agent: no WS connection for {agent_name}, message dropped")
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
            await self._append_and_broadcast(event_id, turn)
            # Update event status
            event = await self.blackboard.get_event(event_id)
            if event:
                event.status = EventStatus.WAITING_APPROVAL
                await self.blackboard.redis.set(
                    f"{self.blackboard.EVENT_PREFIX}{event_id}",
                    json.dumps(event.model_dump()),
                )
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
                await self._append_and_broadcast(event_id, verify_turn)
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
                await self._append_and_broadcast(event_id, confirm_turn)
            return False

        elif function_name == "wait_for_verification":
            condition = args.get("condition", "")
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
                await self._append_and_broadcast(event_id, verify_turn)
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
                await self._append_and_broadcast(event_id, confirm_turn)
            return True  # Re-invoke LLM to evaluate the aligner evidence and decide next action

        elif function_name == "defer_event":
            # Guard: never defer when waiting for user response
            if event_id in self._waiting_for_user:
                logger.warning(f"Ignoring defer_event for {event_id}: waiting for user response")
                return False
            reason = args.get("reason", "Deferred by Brain")
            delay = max(30, min(int(args.get("delay_seconds", 60)), 3600))  # Clamp 30s-60min
            defer_until = time.time() + delay
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="defer",
                thoughts=f"Deferring event for {delay}s: {reason}",
            )
            await self._append_and_broadcast(event_id, turn)
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
            await self.blackboard.record_event(
                EventType.BRAIN_EVENT_DEFERRED,
                {"event_id": event_id, "delay_seconds": delay},
                narrative=f"Event {event_id} deferred for {delay}s: {reason[:80]}",
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
            await self._append_and_broadcast(event_id, turn)
            return False

        elif function_name == "wait_for_agent":
            summary = args.get("summary", "")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="wait",
                thoughts=summary,
                waitingFor="agent",
            )
            await self._append_and_broadcast(event_id, turn)
            return False

        elif function_name == "lookup_service":
            service_name = args.get("service_name", "")
            svc = await self.blackboard.get_service(service_name)
            if svc:
                rows = [f"| Version | {svc.version} |"]
                if svc.gitops_repo:
                    rows.append(f"| GitOps Repo | {svc.gitops_repo} |")
                if svc.gitops_repo_url:
                    rows.append(f"| Repo URL | {svc.gitops_repo_url} |")
                if svc.gitops_config_path:
                    rows.append(f"| Config Path | {svc.gitops_config_path} |")
                if svc.replicas_ready is not None:
                    rows.append(f"| Replicas | {svc.replicas_ready}/{svc.replicas_desired} |")
                rows.append(f"| CPU | {svc.metrics.cpu:.1f}% |")
                rows.append(f"| Memory | {svc.metrics.memory:.1f}% |")
                result_text = f"## Service: {service_name}\n\n| Field | Value |\n|---|---|\n" + "\n".join(rows)
            else:
                known = await self.blackboard.get_services()
                result_text = f"## Service: {service_name}\n\nNot found. Known services: {', '.join(sorted(known)) if known else 'none'}"

            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                waitingFor="lookup_service",
                evidence=result_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            # Signal caller to re-invoke LLM so it can act on the lookup result
            return True

        elif function_name == "consult_deep_memory":
            # Guard: max 1 deep memory call per event (prevent LLM re-query loop)
            ev = await self.blackboard.get_event(event_id)
            already_consulted = any(
                t.action in ("think", "tool_result") and t.evidence and "Deep memory" in (t.evidence or "")
                for t in (ev.conversation if ev else [])
            )
            if already_consulted:
                logger.info(f"Deep memory already consulted for {event_id} -- returning cached results")
                cached_evidence = next(
                    (t.evidence for t in (ev.conversation if ev else [])
                     if t.action in ("think", "tool_result") and t.evidence and "Deep memory" in t.evidence),
                    "Deep memory was already consulted (no cached results).",
                )
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    waitingFor="consult_deep_memory",
                    evidence=f"[Already consulted] {cached_evidence}",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True

            query = args.get("query", "")
            archivist = self.agents.get("_archivist_memory")
            results = []
            if archivist and hasattr(archivist, "search"):
                results = await archivist.search(query, limit=5)
            if results:
                memory_text = f"## Deep Memory: \"{query}\"\n\n"
                for i, r in enumerate(results, 1):
                    p = r.get("payload", {})
                    dur = p.get("duration_seconds", 0)
                    dur_m = f"{dur // 60}m" if dur else "?"
                    defers = p.get("defer_patterns", [])
                    total_defer = sum(d.get("duration_seconds", 0) for d in defers if isinstance(d, dict))
                    defer_m = f"{total_defer // 60}m" if total_defer else "0m"
                    timings = p.get("operational_timings", [])
                    timing_str = ", ".join(
                        f"{t.get('process', '?')}={t.get('duration_seconds', 0) // 60}m"
                        for t in timings if isinstance(t, dict)
                    ) or "none"
                    domain_str = p.get("brain_domain", p.get("domain", "?"))
                    memory_text += (
                        f"{i}. **[{p.get('service', '?')}]** domain: {domain_str} | score: {r.get('score', 0):.2f}\n"
                        f"   - Symptom: {p.get('symptom', '?')}\n"
                        f"   - Root cause: {p.get('root_cause', '?')}\n"
                        f"   - Fix: {p.get('fix_action', '?')}\n"
                        f"   - Duration: {dur_m}, defers: {defer_m}, timings: [{timing_str}], outcome: {p.get('outcome', '?')}\n"
                    )
            else:
                memory_text = f"## Deep Memory: \"{query}\"\n\nNo results found."
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                waitingFor="consult_deep_memory",
                evidence=memory_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "lookup_journal":
            service_name = args.get("service_name", "")
            if service_name:
                entries = await self._get_journal_cached(service_name)
                if entries:
                    header = f"## Ops Journal: {service_name}\n\n{len(entries)} entries:\n\n"
                    journal_text = header + "\n".join(f"- {e}" for e in entries)
                else:
                    journal_text = f"## Ops Journal: {service_name}\n\nNo entries found."
            else:
                entries = await self.blackboard.get_recent_journal_entries()
                if entries:
                    header = f"## Ops Journal: all services\n\n{len(entries)} entries:\n\n"
                    journal_text = header + "\n".join(f"- {e}" for e in entries)
                else:
                    journal_text = "## Ops Journal\n\nNo entries found across any service."
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                waitingFor="lookup_journal",
                evidence=journal_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
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
                    event_doc = await self.blackboard.get_event(event_id)
                    is_bidirectional = (
                        event_doc
                        and not event_doc.slack_thread_ts
                        and event_doc.source != "chat"
                    )
                    if is_bidirectional:
                        event_context = f"*Event:* {event_doc.event.reason[:200]}\n\n"
                        footer = "_Reply in this thread to interact with Darwin about this event._"
                    else:
                        event_context = ""
                        footer = "_This is a notification only. Replies in this thread are not monitored._"
                    dm_text = f":bell: *Darwin Notification*\n\n{event_context}{message}\n\n{footer}\n\n_AI-generated by Darwin Brain. Review for accuracy before acting._"

                    logger.info(f"notify_user_slack: user={slack_user_id} dm_channel={dm_channel} event={event_id} bidirectional={is_bidirectional}")
                    result = await slack_channel._app.client.chat_postMessage(
                        channel=dm_channel,
                        text=dm_text,
                    )
                    msg_ts = result["ts"]
                    if is_bidirectional:
                        await self.blackboard.update_event_slack_context(
                            event_id, dm_channel, msg_ts, slack_user_id,
                        )
                        await self.blackboard.set_slack_mapping(dm_channel, msg_ts, event_id)
                        if event_doc.conversation:
                            from ..channels.formatter import build_event_report_md
                            report_md = build_event_report_md(event_doc)
                            try:
                                await slack_channel._app.client.files_upload_v2(
                                    channel=dm_channel,
                                    thread_ts=msg_ts,
                                    content=report_md,
                                    filename=f"{event_id}-report.md",
                                    title=f"Event {event_id} -- Conversation Report",
                                    initial_comment="Conversation history up to this point:",
                                )
                            except Exception as e:
                                logger.warning(f"Failed to upload conversation report for {event_id}: {e}")
                        logger.info(f"Slack notification sent to {user_email} for event {event_id} (thread={msg_ts}, bidirectional)")
                        result_text = f"Slack DM sent to {user_email}. They can reply in the thread to interact with this event."
                    else:
                        logger.info(f"Slack notification sent to {user_email} for event {event_id} (one-way, existing thread preserved)")
                        result_text = f"Slack DM sent to {user_email} (notification only)."
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
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "notify_gitlab_result":
            event_doc = await self.blackboard.get_event(event_id)
            gl_ctx = None
            if event_doc and event_doc.event.evidence:
                ev = event_doc.event.evidence
                gl_ctx = getattr(ev, "gitlab_context", None) if hasattr(ev, "gitlab_context") else None
            if not gl_ctx:
                result_text = "Cannot notify GitLab: no gitlab_context in event evidence. This tool is for headhunter-sourced events only."
            else:
                project_id = args.get("project_id", gl_ctx.get("project_id"))
                mr_iid = args.get("mr_iid", gl_ctx.get("mr_iid"))
                result_type = args.get("result", "success")
                summary = args.get("summary", "")
                reassign = args.get("reassign_reviewer", False)
                result_text = (
                    f"GitLab notification queued: {result_type} on !{mr_iid} (project {project_id}). "
                    f"Summary: {summary[:200]}. Reassign reviewer: {reassign}. "
                    f"Feedback will be posted by Headhunter feedback loop on event close."
                )
                logger.info(f"notify_gitlab_result: event={event_id} project={project_id} mr=!{mr_iid} result={result_type}")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="notify",
                thoughts=result_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "create_incident":
            event_doc = await self.blackboard.get_event(event_id)
            if not event_doc:
                result_text = f"Event {event_id} not found. Cannot create incident."
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain", action="notify", thoughts=result_text, response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return False
            if event_id in self._incident_created:
                result_text = f"Incident already created for event {event_id}. Skipping duplicate."
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain", action="notify", thoughts=result_text, response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            automated_sources = ("headhunter", "timekeeper", "aligner")
            if event_doc.source not in automated_sources:
                result_text = (
                    f"create_incident is only available for automated events "
                    f"(source={event_doc.source} is not eligible)."
                )
            else:
                adapter = self._get_smartsheet_incident_adapter()
                if not adapter:
                    result_text = "Smartsheet incident tracking not configured (SMARTSHEET_INCIDENT_* env vars missing)."
                else:
                    fields = {
                        "Reporter e-mail": os.environ.get("SMARTSHEET_INCIDENT_REPORTER", ""),
                        "Reporter Display Name": os.environ.get("SMARTSHEET_INCIDENT_REPORTER_NAME", "Darwin Brain"),
                        "Date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
                        "Status": "New",
                        "Issue Type": "Task",
                        "Labels": "darwin-auto, release-incident",
                        "Components": "CNV CI and Release",
                        "Platform": args.get("platform", ""),
                        "Summary": args.get("summary", "")[:200],
                        "Reason": args.get("description", ""),
                        "Priority": args.get("priority", "Normal"),
                        "Affected Versions": args.get("affected_versions", ""),
                    }
                    gl_ctx = None
                    if event_doc.event and event_doc.event.evidence:
                        gl_ctx = getattr(event_doc.event.evidence, "gitlab_context", None)
                    if gl_ctx and isinstance(gl_ctx, dict):
                        fields["Fix PR"] = gl_ctx.get("target_url", "") or gl_ctx.get("mr_url", "")
                    if event_doc.slack_thread_ts and event_doc.slack_channel_id:
                        ts_nodot = event_doc.slack_thread_ts.replace(".", "")
                        workspace = os.environ.get("SLACK_WORKSPACE_DOMAIN", "app.slack.com/client")
                        fields["Slack Thread"] = f"https://{workspace}/archives/{event_doc.slack_channel_id}/p{ts_nodot}"
                    try:
                        result = await adapter.create_incident(fields)
                        self._incident_created.add(event_id)
                        result_text = (
                            f"Incident created in Smartsheet (row {result['row_id']}). "
                            f"Sheet: {result['sheet_url']}"
                        )
                    except Exception as e:
                        result_text = f"Failed to create incident: {e}"
                        logger.warning(f"create_incident failed for {event_id}: {e}")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="notify",
                thoughts=result_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "create_plan":
            steps = args.get("steps", [])
            reasoning = args.get("reasoning", "")
            if not steps:
                logger.warning(f"create_plan called with no steps for {event_id}")
                return True
            plan_lines = [f"## Plan\n\n{reasoning}\n"]
            for s in steps:
                plan_lines.append(f"{s.get('id', '?')}. **{s.get('agent', '?')}**: {s.get('summary', '')}")
            plan_md = "\n".join(plan_lines)
            step_map = [{"id": str(s.get("id", "")), "agent": s.get("agent", ""), "summary": s.get("summary", "")} for s in steps]
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="plan",
                plan=plan_md,
                thoughts=f"Plan created: {len(steps)} steps. {reasoning}",
                taskForAgent={"steps": step_map, "source": "brain"},
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            logger.info(f"Brain chalked plan for {event_id}: {len(steps)} steps")
            return True

        elif function_name == "get_plan_progress":
            event_doc = await self.blackboard.get_event(event_id)
            if not event_doc:
                return True
            plan_turn = None
            for t in reversed(event_doc.conversation):
                if t.action == "plan" and t.taskForAgent and "steps" in t.taskForAgent:
                    plan_turn = t
                    break
            if not plan_turn:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain", action="tool_result",
                    waitingFor="get_plan_progress",
                    evidence="## Plan Progress\n\nNo plan exists for this event.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            steps = {s["id"]: {**s, "status": "pending"} for s in plan_turn.taskForAgent["steps"]}
            for t in event_doc.conversation:
                if t.action == "plan_step" and t.taskForAgent and "step_id" in t.taskForAgent:
                    sid = t.taskForAgent["step_id"]
                    if sid in steps:
                        steps[sid]["status"] = t.taskForAgent.get("status", "completed")
            progress = list(steps.values())
            done = sum(1 for s in progress if s["status"] == "completed")
            summary = f"## Plan Progress\n\n{done}/{len(progress)} steps completed:\n\n"
            for s in progress:
                icon = {"completed": "- [x]", "in_progress": "- [~]", "blocked": "- [!]"}.get(s["status"], "- [ ]")
                summary += f"{icon} Step {s['id']}: {s.get('summary', '')} ({s.get('agent', '?')}) -- {s['status']}\n"
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="get_plan_progress",
                evidence=summary.strip(),
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "classify_event":
            domain = args.get("domain", "complicated")
            reasoning = args.get("reasoning", "")
            severity = args.get("severity")
            await self.blackboard.update_event_domain(event_id, domain)
            thoughts = f"Cynefin: {domain.upper()}."
            if severity:
                await self.blackboard.update_event_severity(event_id, severity)
                thoughts += f" Severity: {severity}."
                await self._broadcast({"type": "severity_updated", "event_id": event_id, "severity": severity})
            thoughts += f" {reasoning}"
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain", action="triage",
                thoughts=thoughts,
                timestamp=time.time(),
            )
            await self._append_and_broadcast(event_id, turn)
            await self._broadcast({"type": "domain_updated", "event_id": event_id, "domain": domain})
            return True

        elif function_name == "refresh_gitlab_context":
            condition = args.get("check_condition", "")
            headhunter = self.agents.get("_headhunter")
            if not headhunter:
                result_text = "Headhunter not available (GITLAB_HOST not configured). Use select_agent to check MR state manually."
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain", action="verify",
                    thoughts=result_text,
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True

            state = await headhunter.refresh_mr_state(event_id)
            mr_state = state.get("mr_state", "unknown")
            if "error" in state:
                result_text = (
                    f"MR State: {mr_state}\n"
                    f"Pipeline: {state.get('pipeline_status', '?')}\n"
                    f"Severity: {state.get('severity', '?')}\n"
                    f"Error: {state['error']}"
                )
            elif mr_state in ("merged", "closed"):
                lines = [
                    f"MR State: {mr_state}",
                    f"Pipeline: {state['pipeline_status']}",
                    f"Severity: {state['severity']}",
                ]
                changed_at = state.get("state_changed_at", "")
                if changed_at:
                    try:
                        dt = datetime.fromisoformat(changed_at.replace("Z", "+00:00"))
                        age = int(time.time() - dt.timestamp())
                        m, s = divmod(age, 60)
                        lines.append(f"{mr_state.title()} {m}m {s}s ago")
                    except (ValueError, TypeError):
                        pass
                result_text = "\n".join(lines)
            else:
                merge_status = state['merge_status']
                merge_line = f"Merge Readiness: {merge_status}"
                if merge_status == "need_rebase":
                    merge_line = "Merge Blocked: needs rebase (new commits on target branch)"
                elif merge_status == "conflict":
                    merge_line = "Merge Blocked: merge conflicts (requires human resolution)"
                elif merge_status in ("ci_must_pass", "ci_still_running"):
                    merge_line = f"Merge Blocked: {merge_status} (wait for pipeline)"
                elif merge_status == "not_approved":
                    merge_line = "Merge Blocked: not approved (requires human approval)"
                result_text = (
                    f"MR State: {mr_state}\n"
                    f"Pipeline: {state['pipeline_status']}\n"
                    f"{merge_line}\n"
                    f"Severity: {state['severity']}"
                )
            thoughts = f"Checking: {condition}\n{result_text}" if condition else result_text
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain", action="verify",
                thoughts=thoughts,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "refresh_kargo_context":
            condition = args.get("check_condition", "")
            kargo_observer = self.agents.get("_kargo_observer")
            if not kargo_observer:
                result_text = "KargoObserver not available (KARGO_OBSERVER_ENABLED=false)."
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain", action="verify",
                    thoughts=result_text,
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True

            event = await self.blackboard.get_event(event_id)
            kc = {}
            if event and event.event and event.event.evidence:
                kc = getattr(event.event.evidence, "kargo_context", None) or {}
            project = kc.get("project", "")
            stage = kc.get("stage", "")
            if not project or not stage:
                result_text = "Kargo Stage: unknown\nError: kargo_context missing project/stage"
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain", action="verify",
                    thoughts=result_text,
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True

            state = await kargo_observer.get_stage_status(project, stage)
            if "error" in state:
                result_text = (
                    f"Kargo Stage: {stage}@{project}\n"
                    f"Error: {state['error']}"
                )
            else:
                result_text = (
                    f"Kargo Stage: {stage}@{project}\n"
                    f"Promotion: {state.get('promotion', '?')}\n"
                    f"Phase: {state.get('phase', '?')}\n"
                    f"Failed Step: {state.get('failed_step', 'N/A')}\n"
                    f"Message: {state.get('message', '')}"
                )
            thoughts = f"Checking: {condition}\n{result_text}" if condition else result_text
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain", action="verify",
                thoughts=thoughts,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
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

    def _get_smartsheet_incident_adapter(self):
        """Lazy-init Smartsheet incident adapter from env vars."""
        if not hasattr(self, '_smartsheet_incident'):
            token = os.environ.get("SMARTSHEET_INCIDENT_TOKEN", "")
            sheet_id = os.environ.get("SMARTSHEET_INCIDENT_SHEET_ID", "")
            if token and sheet_id:
                from ..adapters.smartsheet_incident import SmartsheetIncidentAdapter
                self._smartsheet_incident = SmartsheetIncidentAdapter(token, sheet_id)
            else:
                self._smartsheet_incident = None
        return self._smartsheet_incident

    # =========================================================================
    # Agent Task Runner (non-blocking via create_task)
    # =========================================================================

    def _release_task_state(self, event_id: str) -> None:
        """Clear active task tracking for an event. Used before re-entry and in finally."""
        self._active_tasks.pop(event_id, None)
        self._active_agent_for_event.pop(event_id, None)
        self._routing_turn_for_event.pop(event_id, None)

    async def handle_wake_task(self, data: dict, agent_id: str) -> None:
        """Process a self-initiated wake task (teammate message woke an idle agent).

        Mirrors _run_agent_task's result processing but skips dispatch (sidecar
        already started). Queue was pre-created by the WS handler.
        """
        from ..dependencies import get_registry_and_bridge
        from .dispatch import consume_wake_task, RETRYABLE_SENTINEL, WAKE_REGISTER_MODES

        event_id = data.get("event_id", "")
        role = data.get("role", "")
        task_id = data.get("task_id", "")
        wake_mode = str(data.get("mode") or "implement").strip() or "implement"
        if wake_mode not in WAKE_REGISTER_MODES:
            logger.warning(
                "handle_wake_task: unsupported mode %r in wake_register, coercing to implement",
                wake_mode,
            )
            wake_mode = "implement"

        if not event_id or not role or not task_id:
            logger.warning("handle_wake_task: missing fields in data: %s", data)
            return

        registry, bridge = get_registry_and_bridge()
        if not registry or not bridge:
            logger.warning("handle_wake_task: registry/bridge unavailable")
            return

        evt = await self.blackboard.get_event(event_id)
        if not evt or evt.status.value == "closed":
            logger.info("handle_wake_task: event %s is %s, skipping", event_id, evt.status.value if evt else "missing")
            bridge.delete_queue(task_id)
            await registry.mark_idle(agent_id)
            return

        event_source = evt.source if evt else ""

        async def on_progress(progress_data: dict) -> None:
            await self._broadcast({
                "type": "progress",
                "event_id": event_id,
                "actor": progress_data.get("actor", role),
                "message": progress_data.get("message", ""),
                "event_source": event_source,
            })
            if progress_data.get("source") == "agent_message":
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor=progress_data.get("actor", role),
                    action="message",
                    thoughts=progress_data.get("message", ""),
                )
                await self._append_and_broadcast(event_id, turn)
            elif progress_data.get("source") == "teammate":
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor=progress_data.get("actor", role),
                    action="teammate",
                    thoughts=progress_data.get("message", ""),
                )
                await self._append_and_broadcast(event_id, turn)

        async def on_huddle(huddle_data: dict) -> None:
            r = huddle_data.get("agent_id", agent_id).split("-")[0]
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor=r,
                action="huddle",
                thoughts=huddle_data.get("content", ""),
            )
            await self._append_and_broadcast(event_id, turn)

        self._active_tasks[event_id] = asyncio.current_task()
        self._active_agent_for_event[event_id] = role

        await self._broadcast({
            "type": "progress",
            "event_id": event_id,
            "actor": role,
            "message": f"{role} waking (teammate message)...",
            "event_source": event_source,
        })

        try:
            result, session_id = await consume_wake_task(
                bridge=bridge, registry=registry,
                agent_id=agent_id, task_id=task_id,
                event_id=event_id, role=role,
                on_progress=on_progress, on_huddle=on_huddle,
            )

            if result == RETRYABLE_SENTINEL:
                logger.info("Wake task retryable error for %s, skipping re-entry", event_id)
                self._release_task_state(event_id)
                return

            if session_id:
                self._agent_sessions.setdefault(event_id, {})[role] = session_id
                self._agent_session_modes.setdefault(event_id, {})[role] = wake_mode

            result_str = str(result).strip() if result else ""

            try:
                result_data = json.loads(result)
                if isinstance(result_data, dict) and result_data.get("type") == "agent_busy":
                    logger.warning("Wake task: agent %s busy for %s", role, event_id)
                    self._release_task_state(event_id)
                    return
            except (json.JSONDecodeError, TypeError):
                pass

            if not result_str:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor=role, action="error",
                    thoughts="Wake task returned empty response.",
                )
                await self._append_and_broadcast(event_id, turn)
                self._release_task_state(event_id)
                return

            # WARNING: If WAKE_REGISTER_MODES ever includes "message", this needs
            # the same mode-aware skip as _run_agent_task (message-mode agents
            # deliver content via progress turns, not via result turn).
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor=role, action="execute",
                result=result_str[:15000],
            )
            await self._append_and_broadcast(event_id, turn)
            logger.info("Wake task completed: %s for %s", role, event_id)

            await self.blackboard.stamp_event(event_id, last_completed_at=time.time())
            self._release_task_state(event_id)
            self._last_processed[event_id] = time.time()

            if not await self._is_event_closed(event_id) and event_id not in self._waiting_for_user:
                await self.process_event(event_id)

        except Exception as e:
            logger.error("Wake task failed: %s for %s: %s", role, event_id, e, exc_info=True)
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor=role, action="error",
                thoughts=f"Wake task failed: {str(e)}",
            )
            await self._append_and_broadcast(event_id, turn)
            self._release_task_state(event_id)

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
        current_task = asyncio.current_task()
        sema_acquired = False
        try:
            if self._dispatch_semaphore:
                await self._dispatch_semaphore.acquire()
                sema_acquired = True

            agent_acked = False  # Track first progress (= agent received task)
            evt = await self.blackboard.get_event(event_id)
            event_source = evt.source if evt else ""

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
                    "event_source": event_source,
                })
                if progress_data.get("source") == "agent_message":
                    turn = ConversationTurn(
                        turn=(await self._next_turn_number(event_id)),
                        actor=progress_data.get("actor", agent_name),
                        action="message",
                        thoughts=progress_data.get("message", ""),
                    )
                    await self._append_and_broadcast(event_id, turn)
                elif progress_data.get("source") == "teammate":
                    turn = ConversationTurn(
                        turn=(await self._next_turn_number(event_id)),
                        actor=progress_data.get("actor", agent_name),
                        action="teammate",
                        thoughts=progress_data.get("message", ""),
                    )
                    await self._append_and_broadcast(event_id, turn)

            mode_label = f" (mode={mode})" if mode else ""
            logger.info(f"Agent task started: {agent_name}{mode_label} for {event_id}")
            self._active_agent_for_event[event_id] = agent_name
            self._routing_turn_for_event[event_id] = routing_turn_num or 0

            prior_mode = self._agent_session_modes.get(event_id, {}).get(agent_name, "")
            reuse_session = (prior_mode == mode) if mode and prior_mode else bool(prior_mode)
            resume_session_id = self._agent_sessions.get(event_id, {}).get(agent_name) if reuse_session else None
            if not reuse_session and prior_mode and prior_mode != mode:
                logger.info(f"Skipping session resume for {agent_name} on {event_id}: mode changed {prior_mode}->{mode}")
                self._agent_sessions.get(event_id, {}).pop(agent_name, None)
                self._agent_session_modes.get(event_id, {}).pop(agent_name, None)
            # Immediate progress so UI shows activity during CLI cold start
            await self._broadcast({
                "type": "progress",
                "event_id": event_id,
                "actor": agent_name,
                "message": f"{agent_name} starting...",
                "event_source": event_source,
            })
            if self._ws_mode == "reverse" and agent_name not in ("_aligner", "_archivist_memory"):
                from ..dependencies import get_registry_and_bridge
                from .ephemeral_provisioner import CAPACITY_SENTINEL, INFRA_SENTINEL
                registry, bridge = get_registry_and_bridge()
                if registry and bridge:
                    async def on_huddle(data: dict) -> None:
                        """Append huddle as conversation turn -- Brain replies via _process_intermediate."""
                        role = data.get("agent_id", agent_name).split("-")[0]
                        turn = ConversationTurn(
                            turn=(await self._next_turn_number(event_id)),
                            actor=role,
                            action="huddle",
                            thoughts=data.get("content", ""),
                        )
                        await self._append_and_broadcast(event_id, turn)

                    agent_id_override = None
                    event_doc = await self.blackboard.get_event(event_id)

                    # Tier 1: Primary ephemeral sources (never fall back to local)
                    use_ephemeral = (
                        self._ephemeral_provisioner
                        and event_doc
                        and event_doc.source in ("headhunter", "timekeeper")
                    )
                    ephemeral_is_overflow = False

                    # Tier 2: MMC overflow -- scale C when local sidecars are full
                    # Local sidecars are role-locked (1 per role = MM1). Ephemeral agents
                    # shape-shift via WS msg.role, breaking the per-role bottleneck.
                    if not use_ephemeral and self._ephemeral_provisioner and event_doc and registry:
                        local_available = await registry.get_available(agent_name)
                        if local_available is None:
                            source_env_key = f"{event_doc.source.upper().replace('-', '_')}_MAX_ACTIVE"
                            if os.environ.get(source_env_key):
                                logger.info(
                                    "MMC overflow: no local sidecar for %s, scaling to ephemeral "
                                    "(source=%s, event=%s)",
                                    agent_name, event_doc.source, event_id,
                                )
                                use_ephemeral = True
                                ephemeral_is_overflow = True

                    if use_ephemeral:
                        provision_result = await self._ephemeral_provisioner.ensure_agent(
                            event_id, source=event_doc.source,
                        )
                        if provision_result is None:
                            if ephemeral_is_overflow:
                                logger.info(
                                    "Ephemeral circuit breaker + local full for %s -- deferring",
                                    event_id,
                                )
                                await self._execute_function_call(
                                    event_id, "defer_event",
                                    {"delay_seconds": 30, "reason": "All agents busy (local full + ephemeral circuit breaker)"},
                                    response_parts=None,
                                )
                                return
                            else:
                                logger.info("Ephemeral circuit breaker tripped for %s -- falling back to sidecar", event_id)
                        elif isinstance(provision_result, str):
                            defer_seconds = 120 if provision_result == CAPACITY_SENTINEL else 60
                            reason = (
                                "Waiting for ephemeral agent slot"
                                if provision_result == CAPACITY_SENTINEL
                                else "Tekton infrastructure unavailable"
                            )
                            logger.info("Deferring %s for %ds: %s", event_id, defer_seconds, reason)
                            await self._execute_function_call(
                                event_id, "defer_event",
                                {"delay_seconds": defer_seconds, "reason": reason},
                            )
                            return
                        else:
                            agent_id_override = provision_result.agent_id

                    result, session_id = await dispatch_to_agent(
                        registry=registry,
                        bridge=bridge,
                        role=agent_name,
                        event_id=event_id,
                        task=task,
                        on_progress=on_progress,
                        on_huddle=on_huddle,
                        agent_id=agent_id_override,
                        session_id=resume_session_id,
                        event_md_path=event_md_path,
                        mode=mode,
                    )
                else:
                    logger.warning(f"Registry/Bridge not available, falling back to legacy for {agent_name}")
                    if not agent:
                        logger.error(f"No agent class for {agent_name} in legacy mode, cannot dispatch")
                        return
                    async with self._agent_locks[agent_name]:
                        result, session_id = await agent.process(
                            event_id=event_id, task=task, event_md_path=event_md_path,
                            on_progress=on_progress, mode=mode,
                            session_id=resume_session_id,
                        )
            else:
                if not agent:
                    logger.error(f"No agent class for {agent_name} in legacy mode, cannot dispatch")
                    return
                async with self._agent_locks[agent_name]:
                    result, session_id = await agent.process(
                        event_id=event_id,
                        task=task,
                        event_md_path=event_md_path,
                        on_progress=on_progress,
                        mode=mode,
                        session_id=resume_session_id,
                    )

            if result == RETRYABLE_SENTINEL:
                logger.info(f"Retryable error for {event_id}, deferring event")
                await self._execute_function_call(
                    event_id, "defer_event",
                    {"reason": "Agent returned retryable error", "delay_seconds": 60},
                )
                return

            # Track session + mode for follow-ups -- clear on failure to prevent corrupted resume loops
            result_str_check = str(result).strip() if result else ""
            is_error_result = result_str_check.startswith("Error:") or not result_str_check
            if session_id and not is_error_result:
                self._agent_sessions.setdefault(event_id, {})[agent_name] = session_id
                self._agent_session_modes.setdefault(event_id, {})[agent_name] = mode or ""
            elif is_error_result and event_id in self._agent_sessions:
                self._agent_sessions.get(event_id, {}).pop(agent_name, None)
                self._agent_session_modes.get(event_id, {}).pop(agent_name, None)
                logger.info(f"Cleared corrupted session for {agent_name} on {event_id}")
            # Lock released -- Brain continues freely

            # Parse result -- check for structured responses (question, agent_busy)
            # Note: unreachable in message mode (team_send_results blocked by MCP notInModes,
            # so callbackResult is null and stdout is plain text, never structured JSON).
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
                        await self._append_and_broadcast(event_id, turn)
                        self._release_task_state(event_id)
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
                        await self._append_and_broadcast(event_id, turn)
                        logger.warning(f"Agent {agent_name} busy for {event_id}, returning to Brain")
                        self._release_task_state(event_id)
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
                await self._append_and_broadcast(event_id, turn)
                logger.warning(f"Agent {agent_name} returned EMPTY result for {event_id}")
                self._release_task_state(event_id)
                if not await self._is_event_closed(event_id):
                    await self.process_event(event_id)
                return

            # Message-mode: agent delivered content via progress turns (team_send_message).
            # CLI exit stdout is redundant noise -- skip result turn and re-entry.
            # Safety invariant: team_send_results has notInModes:['message'] in MCP layer
            # (team-chat-mcp.js), so callbackResult is always null in message mode.
            # Exception to rule #9 (_append_and_broadcast for all turns) -- intentional.
            # Applies to both local and ephemeral agents (same dispatch + result path).
            if mode == "message":
                logger.info(
                    f"Message-mode task completed: {agent_name} for {event_id} "
                    f"(skipping result turn, content delivered via progress)"
                )
                if routing_turn_num:
                    await self.blackboard.mark_turn_status(
                        event_id, routing_turn_num, MessageStatus.EVALUATED
                    )
                    await self._broadcast_status_update(
                        event_id, "evaluated", turns=[routing_turn_num],
                    )
                await self.blackboard.stamp_event(event_id, last_completed_at=time.time())
                self._release_task_state(event_id)
                self._last_processed[event_id] = time.time()
                return

            # Append agent result turn (cancel = clean termination, not an error)
            is_cancel = result_str.strip() == "Cancelled by Brain"
            is_plan = (
                not is_cancel
                and agent_name == "architect"
                and result_str.lstrip().startswith("---")
            )

            plan_md, plan_steps = None, None
            if is_plan:
                plan_md, plan_steps = self._parse_plan_frontmatter(result_str)

            has_structured_plan = plan_md and plan_steps
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor=agent_name,
                action="cancel" if is_cancel else ("plan" if has_structured_plan else "execute"),
                result=result_str[:15000],
                plan=plan_md if has_structured_plan else None,
                taskForAgent=(
                    {"steps": plan_steps, "source": "architect"}
                    if has_structured_plan else None
                ),
            )
            await self._append_and_broadcast(event_id, turn)
            logger.info(f"Agent task {'cancelled' if is_cancel else 'plan' if has_structured_plan else 'completed'}: {agent_name} for {event_id}")

            if is_cancel:
                self._release_task_state(event_id)
                return

            # Mark routing turn as EVALUATED (agent completed its work)
            if routing_turn_num:
                await self.blackboard.mark_turn_status(
                    event_id, routing_turn_num, MessageStatus.EVALUATED
                )
                await self._broadcast_status_update(
                    event_id, "evaluated", turns=[routing_turn_num],
                )

            # Value stream: stamp agent completion time
            await self.blackboard.stamp_event(event_id, last_completed_at=time.time())

            self._release_task_state(event_id)
            self._last_processed[event_id] = time.time()

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
            await self._append_and_broadcast(event_id, turn)
            if routing_turn_num:
                await self.blackboard.mark_turn_status(
                    event_id, routing_turn_num, MessageStatus.EVALUATED
                )
            self._release_task_state(event_id)
            self._last_processed[event_id] = time.time()

            # Re-evaluate (skip if event was closed concurrently)
            if not await self._is_event_closed(event_id):
                await self.process_event(event_id)

        finally:
            if sema_acquired and self._dispatch_semaphore:
                self._dispatch_semaphore.release()
            # Safety net -- only clean up if _active_tasks still holds OUR task.
            # Re-entry (process_event) may have created a NEW task; don't clobber it.
            if self._active_tasks.get(event_id) is current_task:
                self._release_task_state(event_id)
            # Note: _agent_sessions is NOT cleaned here -- sessions persist across
            # task invocations for Phase 2 follow-ups. Cleaned in cancel/close paths.

    # =========================================================================
    # Broadcast Helpers
    # =========================================================================

    async def _append_and_broadcast(
        self, event_id: str, turn: ConversationTurn, event: "EventDocument | None" = None
    ) -> None:
        """Persist turn to Redis, broadcast to dashboard/Slack, push to working agent sidecar."""
        await self.blackboard.append_turn(event_id, turn)
        await self._broadcast_turn(event_id, turn)
        try:
            from ..dependencies import get_registry_and_bridge
            registry, _ = get_registry_and_bridge()
            if registry:
                agent_conn = await registry.get_by_event(event_id)
                if agent_conn and agent_conn.ws and turn.actor != agent_conn.current_role:
                    status = event.status.value if event else "active"
                    total = len(event.conversation) + 1 if event else 0
                    await agent_conn.ws.send_json({
                        "type": "blackboard_update",
                        "event_id": event_id,
                        "turn": turn.model_dump(),
                        "event_status": status,
                        "total_turns": total,
                    })
        except Exception:
            pass

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
        self._routing_depth.pop(event_id, None)  # Reset depth on user interaction

    def register_channel(self, channel_broadcast: BroadcastPort) -> None:
        """Register an additional broadcast target (e.g., Slack, Dashboard WS)."""
        self._broadcast_targets.append(channel_broadcast)

    async def list_connected_agents(self) -> list[dict]:
        """Public accessor for connected agent status. Used by SlackChannel Home tab."""
        from ..dependencies import get_registry_and_bridge
        registry, _ = get_registry_and_bridge()
        if registry:
            return await registry.list_agents()
        return []

    async def _broadcast(self, message: dict) -> None:
        """Fan out a message to all registered broadcast targets (WS, Slack, etc.)."""
        for target in self._broadcast_targets:
            try:
                await target(message)
            except Exception as e:
                logger.warning(f"Broadcast target failed: {e}")

    async def _escalate_to_human(
        self, event_id: str, event: EventDocument, nudge_count: int, idle_seconds: float,
    ) -> None:
        """Escalate an idle event to a human after max automated nudges.

        Sets wait_for_user and DMs the resolved maintainer via Slack.
        No force-close -- the human decides what to do.
        """
        idle_min = int(idle_seconds // 60)
        self._waiting_for_user.add(event_id)

        email = None
        evidence = event.event.evidence
        if hasattr(evidence, "gitlab_context") and evidence.gitlab_context:
            gl = evidence.gitlab_context
            maintainer = gl.get("maintainer", {})
            emails = maintainer.get("emails", [])
            if emails:
                email = emails[0]
        if not email and event.slack_user_id:
            email = event.slack_user_id
        if not email:
            import os as _os
            static = _os.getenv("HEADHUNTER_MAINTAINERS", "")
            if static:
                email = static.split(",")[0].strip()

        escalation_msg = (
            f"Event `{event_id}` has been idle for {idle_min} minutes after "
            f"{nudge_count} automated check-ins. Brain could not resolve. "
            f"Service: {event.service}. Please review."
        )

        if email:
            slack_channel = self._get_slack_channel()
            if slack_channel:
                try:
                    if "@" in email:
                        user_info = await slack_channel._app.client.users_lookupByEmail(email=email)
                        slack_user_id = user_info["user"]["id"]
                    else:
                        slack_user_id = email
                    dm = await slack_channel._app.client.conversations_open(users=slack_user_id)
                    dm_channel = dm["channel"]["id"]
                    await slack_channel._app.client.chat_postMessage(
                        channel=dm_channel,
                        text=f":rotating_light: *Darwin Escalation*\n\n{escalation_msg}",
                    )
                    logger.info(f"Escalation DM sent to {email} for {event_id}")
                except Exception as e:
                    logger.warning(f"Escalation DM failed for {event_id}: {e}")
            else:
                logger.warning(f"Escalation: no Slack channel for {event_id}, wait_for_user set without DM")
        else:
            logger.warning(f"Escalation: no email resolved for {event_id}, wait_for_user set without DM")

        wait_turn = ConversationTurn(
            turn=len(event.conversation) + 1,
            actor="brain",
            action="wait",
            thoughts=escalation_msg,
            waitingFor="user",
        )
        await self._append_and_broadcast(event_id, wait_turn)
        logger.warning(f"Escalating {event_id} to human after {nudge_count} nudges ({idle_min}m idle)")

    async def _close_and_broadcast(self, event_id: str, summary: str, close_reason: str = "resolved") -> None:
        """Close an event and broadcast the closure to UI."""
        if self._ephemeral_provisioner:
            await self._ephemeral_provisioner.terminate_agent(event_id)
        await self.cancel_active_task(event_id, f"Event closing: {summary}")
        event = await self.blackboard.get_event(event_id)
        await self.blackboard.close_event(event_id, summary, close_reason=close_reason)
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
        self._agent_session_modes.pop(event_id, None)
        for agent in self.agents.values():
            if hasattr(agent, 'cleanup_event'):
                agent.cleanup_event(event_id)
        await self.blackboard.record_event(
            EventType.BRAIN_EVENT_CLOSED,
            {"event_id": event_id, "service": event.service if event else "unknown"},
            narrative=f"Event {event_id} closed: {summary[:120]}",
        )
        await self._broadcast({
            "type": "event_closed",
            "event_id": event_id,
            "summary": summary,
            })
        signal = getattr(self, '_headhunter_close_signal', None)
        if signal and event and event.source == "headhunter":
            signal.set()

    # =========================================================================
    # Active Task Cancellation
    # =========================================================================

    async def cancel_active_task(self, event_id: str, reason: str = "cancelled") -> bool:
        """Cancel a running agent task for an event. Single kill path for all layers."""
        task = self._active_tasks.get(event_id)
        if not task or task.done():
            return False
        logger.warning(f"Cancelling active task for {event_id}: {reason}")

        if self._ws_mode == "reverse":
            from ..dependencies import get_registry_and_bridge
            registry, bridge = get_registry_and_bridge()
            if registry and bridge:
                await send_cancel(registry, bridge, event_id)

        task.cancel()
        try:
            await asyncio.wait_for(task, timeout=3.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        self._release_task_state(event_id)
        self._agent_sessions.pop(event_id, None)
        self._agent_session_modes.pop(event_id, None)
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
                await self._close_and_broadcast(eid, "Emergency stop: all agents terminated.", close_reason="force_closed")
                cancelled += 1
        logger.critical(f"EMERGENCY STOP: {cancelled} tasks cancelled")
        return cancelled

    async def send_to_agent(self, event_id: str, agent_name: str, message: str) -> str:
        """Send a follow-up message to a running agent session.

        Used in Phase 2 to forward user messages to agents instead of killing them.
        Reverse mode: dispatches via registry with session affinity (agent_id + session_id).
        Legacy mode: uses agent.followup() directly.
        """
        session_id = self._agent_sessions.get(event_id, {}).get(agent_name)
        if not session_id:
            return "No active session"

        if self._ws_mode == "reverse":
            from ..dependencies import get_registry_and_bridge
            registry, bridge = get_registry_and_bridge()
            if registry and bridge:
                # Find the agent_id that handled this event (session affinity)
                agent_conn = await registry.get_by_event(event_id)
                agent_id = agent_conn.agent_id if agent_conn else None
                result, _ = await dispatch_to_agent(
                    registry=registry, bridge=bridge, role=agent_name,
                    event_id=event_id, task=message,
                    agent_id=agent_id, session_id=session_id,
                    mode="message",
                )
                return result

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
                await self._append_and_broadcast(event_id, turn)
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

        service_meta = await self.blackboard.get_service(event.service)
        mermaid = ""
        if event.source != "headhunter":
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
    def _parse_plan_frontmatter(raw: str) -> tuple[str | None, list[dict] | None]:
        """Extract plan markdown body and structured steps from YAML frontmatter.

        Returns (plan_markdown, steps_list) or (None, None) if parsing fails.
        Frontmatter format defined in brain_skills/post-agent/plan-activation.md.
        """
        import yaml

        stripped = raw.lstrip()
        if not stripped.startswith("---"):
            return None, None
        end_idx = stripped.find("---", 3)
        if end_idx == -1:
            return stripped, None
        frontmatter_str = stripped[3:end_idx].strip()
        body = stripped[end_idx + 3:].strip()
        try:
            fm = yaml.safe_load(frontmatter_str)
        except Exception:
            return body or stripped, None
        if not isinstance(fm, dict):
            return body or stripped, None
        raw_steps = fm.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            return body or stripped, None
        steps = []
        for s in raw_steps:
            if not isinstance(s, dict) or "id" not in s:
                continue
            steps.append({
                "id": str(s["id"]),
                "agent": s.get("agent", ""),
                "summary": s.get("summary", ""),
            })
        return body or stripped, steps if steps else None

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
            lines.append(f"- **Domain:** {evidence.brain_domain or evidence.domain}")
            lines.append(f"- **Severity:** {evidence.brain_severity or evidence.severity}")
            if evidence.gitlab_context:
                gl = evidence.gitlab_context
                lines.append(f"")
                lines.append(f"## GitLab Context")
                lines.append(f"- **Project ID:** {gl.get('project_id', '')}")
                lines.append(f"- **Project Path:** {gl.get('project_path', '')}")
                lines.append(f"- **MR IID:** !{gl.get('mr_iid', '')}")
                lines.append(f"- **MR Title:** {gl.get('mr_title', '')}")
                lines.append(f"- **MR URL:** {gl.get('target_url', '')}")
                lines.append(f"- **Action:** {gl.get('action_name', '')}")
                lines.append(f"- **Pipeline:** {gl.get('pipeline_status', 'unknown')}")
                lines.append(f"- **Merge Status:** {gl.get('merge_status', '')}")
                lines.append(f"- **Source Branch:** {gl.get('source_branch', '')}")
                lines.append(f"- **Target Branch:** {gl.get('target_branch', '')}")
                lines.append(f"- **Author:** {gl.get('author', '')}")
                maintainer = gl.get("maintainer", {})
                if maintainer:
                    emails = maintainer.get("emails", [])
                    lines.append(f"- **Maintainer Emails:** {', '.join(emails) if emails else 'none'}")
                    lines.append(f"- **Maintainer Source:** {maintainer.get('source', '')}")
            if evidence.kargo_context:
                kc = evidence.kargo_context
                lines.append("")
                lines.append("## Kargo Context")
                lines.append(f"- **Project:** {kc.get('project', '')}")
                lines.append(f"- **Stage:** {kc.get('stage', '')}")
                lines.append(f"- **Promotion:** {kc.get('promotion', '')}")
                lines.append(f"- **Freight:** {(kc.get('freight') or '')[:12]}...")
                lines.append(f"- **Phase:** {kc.get('phase', '')}")
                lines.append(f"- **Failed Step:** {kc.get('failed_step', 'N/A')}")
                lines.append(f"- **Error:** {kc.get('message', '')}")
                if kc.get("mr_url"):
                    lines.append(f"- **MR URL:** {kc['mr_url']}")
                lines.append(f"- **Started:** {kc.get('started_at', '')}")
                lines.append(f"- **Finished:** {kc.get('finished_at', '')}")
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
        Startup cleanup: close stale events from a previous Brain instance.
        
        On restart, active events may be orphaned (agent tasks were in-flight,
        WebSocket connections dropped). Close them so they don't block the system.
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
                await self.blackboard.close_event(eid, stale_summary, close_reason="stale")
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
                # Broadcast closure to UI + Slack (notifies active threads)
                await self._broadcast({
                    "type": "event_closed",
                    "event_id": eid,
                    "summary": stale_summary,
                })
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
        from redis.exceptions import ConnectionError as RedisConnectionError, TimeoutError as RedisTimeoutError

        self._running = True
        _redis_backoff = 2  # seconds, doubles on consecutive Redis failures (max 60s)

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

                _redis_backoff = 2  # reset on successful Redis call

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
                            routing_turn = self._routing_turn_for_event.get(eid, 0)
                            user_turns = [t for t in unseen if t.actor == "user" and t.turn > routing_turn]
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
                                    # No session -- forward user message via proactive_message WS
                                    if agent_name:
                                        from ..dependencies import get_registry_and_bridge
                                        registry, _ = get_registry_and_bridge()
                                        if registry:
                                            agent_conn = await registry.get_by_event(eid)
                                            if not agent_conn:
                                                agent_conn = await registry.get_available(agent_name)
                                            if agent_conn and agent_conn.ws:
                                                user_text = " ".join(t.thoughts for t in user_turns if t.thoughts)
                                                if user_text:
                                                    try:
                                                        await agent_conn.ws.send_json({
                                                            "type": "proactive_message",
                                                            "from": "user",
                                                            "content": user_text,
                                                        })
                                                        logger.info("Forwarded user message to %s via proactive_message for %s", agent_name, eid)
                                                    except Exception as e:
                                                        logger.warning("Failed to forward user message to %s: %s", agent_name, e)
                                    continue
                            else:
                                intermediate = [
                                    t for t in unseen
                                    if t.actor not in ("brain", "user")
                                ]
                                if intermediate:
                                    await self._process_intermediate(eid, event, intermediate)
                                continue
                        else:
                            continue

                    event = await self.blackboard.get_event(eid)
                    if not event or not event.conversation:
                        continue

                    # Check if event is deferred -- skip until delay expires OR user interrupts
                    if event.status == EventStatus.DEFERRED:
                        defer_key = f"{self.blackboard.EVENT_PREFIX}{eid}:defer_until"
                        defer_until = await self.blackboard.redis.get(defer_key)
                        if defer_until and time.time() < float(defer_until):
                            last_defer_idx = next(
                                (i for i, t in enumerate(reversed(event.conversation))
                                 if t.actor == "brain" and t.action == "defer"), None
                            )
                            user_after_defer = last_defer_idx is not None and any(
                                t.actor == "user"
                                for t in event.conversation[len(event.conversation) - last_defer_idx:]
                            )
                            if not user_after_defer:
                                continue  # Still deferred, no user interrupt
                            logger.info(f"User message interrupted defer for {eid} -- waking early")
                        # Delay expired -- atomically re-activate (WATCH/MULTI/EXEC)
                        # to avoid losing turns appended during the defer window.
                        logger.info(f"Defer expired for {eid} -- attempting re-activation (defer_key exists={defer_until is not None})")
                        transitioned = await self.blackboard.transition_event_status(
                            eid, "deferred", EventStatus.ACTIVE,
                        )
                        await self.blackboard.redis.delete(defer_key)
                        if transitioned:
                            if eid in self._waiting_for_user:
                                logger.warning(f"Deferred event {eid} re-activated but waiting for user -- skipping")
                            else:
                                logger.info(f"Deferred event {eid} re-activated")
                                event = await self.blackboard.get_event(eid)
                                if event:
                                    await self.process_event(eid, prefetched_event=event)
                        else:
                            refetched = await self.blackboard.get_event(eid)
                            actual_status = refetched.status.value if refetched else "MISSING"
                            logger.warning(f"Defer re-activation FAILED for {eid}: expected 'deferred', actual '{actual_status}'")
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

            except (RedisConnectionError, RedisTimeoutError) as e:
                logger.warning(f"Redis connection lost, retrying in {_redis_backoff}s: {e}")
                await asyncio.sleep(_redis_backoff)
                _redis_backoff = min(_redis_backoff * 2, 60)
                continue

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

