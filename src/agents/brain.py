# BlackBoard/src/agents/brain.py
# @ai-rules:
# 1. [Constraint]: ALL decision logic in system prompt + function declarations. Python = plumbing only.
#    Active path: brain_skills/*.md (BrainSkillLoader). BRAIN_SYSTEM_PROMPT is deprecated fallback.
# 2. [Pattern]: process_event -> _process_event_inner with per-event asyncio.Lock prevents concurrent calls.
# 3. [Pattern]: MessageStatus protocol: SENT -> DELIVERED (Brain scanned) -> EVALUATED (LLM processed).
# 4. [Gotcha]: turn_snapshot captures len(conversation) BEFORE LLM call. mark_turns_evaluated uses this scope.
# 5. [Gotcha]: _waiting_for_user (dict[str,float]: event_id -> wait_start_timestamp) is cleared by main.py WS handler AND queue.py REST endpoints (clear_waiting), not by Brain internally.
# 6. [Pattern]: Bidirectional agent status: routing_turn_num tracks brain.route -> DELIVERED on first progress -> EVALUATED on completion.
# 7. [Pattern]: Temporal memory: _journal_cache (60s TTL) + _get_journal_cached(). Invalidated in _close_and_broadcast().
# 8. [Pattern]: _event_to_markdown is @staticmethod -- called from both instance methods and queue.py report endpoint.
# 9. [Pattern]: Use _append_and_broadcast() for all turn persistence. Direct append_turn only for probe-mode (line ~517).
# 10. [Constraint]: defer_event is blocked when _waiting_for_user -- prevents defer→re-activate→close leak. Automated nudge escalation also sets _waiting_for_user.
# 11. [Constraint]: Resync scan has_unread + deferred re-activation paths skip enqueueing when _waiting_for_user.
# 12. [Pattern]: LLM adapter layer (.llm subpackage) -- Brain uses generate_stream(), tool schemas in llm/types.py.
# 13. [Pattern]: brain_thinking + brain_thinking_done WS messages bracket streaming. UI clears on done/turn/error.
# 13b. [Pattern]: ReconcileScheduler (src/scheduling/) replaces monolithic event loop. start_event_loop() is a
#     thin facade that wires QueueTrigger (BRPOP), ResyncTrigger (5s scan), StalenessGuard (jarvis 120s, chat 5400s).
#     N workers process events concurrently. FairQueue provides per-key dedup (no spin monopoly).
#     Brain._scan_active_for_reconcile() is the decision callback: returns list[str] of event_ids to enqueue.
# 14. [Pattern]: cancel_active_task() is the single kill path. Cancels asyncio.Task -> CancelledError in base_client -> WS close -> SIGTERM.
# 15. [Pattern]: _active_agent_for_event tracks which agent is running per event. Populated in _run_agent_task, cleaned in finally + cancel + close.
# 15b. [Pattern]: _waiting_for_agent (dict[str,str]) blocks process_event re-entry after wait_for_agent. Set in handler, cleared when ANY participant responds (DELIVERED turn detected) OR in _release_task_state + _close_and_broadcast. Guard at top of _process_event_inner. Treats JARVIS, agents, users as equal participants.
# 16. [Pattern]: _agent_sessions + _agent_session_modes: session resume is mode-aware. Same mode = resume (e.g., investigate->investigate). Cross-mode (investigate->execute) = fresh session to avoid Claude thinking-block corruption.
# 17. [Pattern]: _broadcast() fans out to _broadcast_targets list. register_channel() adds targets (e.g., Slack).
# 27. [Pattern]: event_status_changed broadcast fires after successful status transitions (new->active, active->deferred, deferred->active). Broadcasts at call sites, NOT inside transition_event_status() (Hexagonal boundary). Defer path is defense-in-depth (turn broadcast already fires via _append_and_broadcast).
# 30. [Gotcha]: consult_deep_memory cached guard uses string matching ("No historical patterns", "No results") coupled to Archivist response text. If Archivist wording changes, the guard silently breaks.
# 31. [Pattern]: _reasoning_by_event (dict[str, str | None]) keyed by event_id. Set in _process_with_llm
#     before _execute_function_call, consumed via .pop() in _emit_executive_pulse, cleared on error/text-only
#     paths, _process_intermediate, and _close_and_broadcast. JARVIS sees reasoning via PulseBatch.reasoning.
# 28. [Debt]: defer_event handler (~2064) uses read-modify-write (get_event -> set status -> redis.set) without
#     WATCH/MULTI/EXEC. Protected by per-event asyncio.Lock, but external concurrent writes (REST endpoints)
#     could theoretically lose turns. Pre-existing pattern -- refactor to use transition_event_status() or
#     a dedicated blackboard.defer_event() atomic operation when this path is next modified.
# 18. [Pattern]: _build_contents() returns structured [{role, parts}] array from Redis. Redis is single source of truth. No ChatSession.
# 19. [Pattern]: _turn_to_parts() maps ConversationTurn -> provider-agnostic parts. Brain=model role, all others=user role.
# 20. [Gotcha]: Consecutive same-role turns merged into one content block (Gemini requires alternating user/model).
# 21. [Pattern]: response_parts on brain turns preserves thought_signature for Gemini 3 multi-turn function calling.
# 22. [Pattern]: Progressive skills: BrainSkillLoader globs brain_skills/ at startup. _build_system_prompt (async) assembles phase-specific prompt. _resolve_llm_params reads _phase.yaml priority. Feature flag BRAIN_PROGRESSIVE_SKILLS. Legacy: _determine_thinking_params_legacy. Brain-declared phases via set_phase replace heuristic PHASE_CONDITIONS; system states (waiting, intermediate) preempt Brain phase via early-return in _match_phases. BRAIN_PHASE_SKILLS maps declared phase to skill folders.
#     _build_system_prompt wraps each resolved skill body with <skill_section id="phase/file.md"> XML tags
#     via _wrap_skill_section(). Kargo skills wrapped via find_paths_by_tag + get_with_meta composition.
# 22b. [Constraint]: skill_section id values must be ASCII path chars (a-z, 0-9, -, _, /). No quotes,
#     angle brackets, or ampersands in skill filenames -- would break the XML id attribute.
# 29. [Pattern]: _format_recall_block reads _recall_lessons dict (populated by reflex gate).
#     Overwrite semantics. Persists across defer-wake (warm SI context). Cleared only in
#     _close_and_broadcast. Per-event asyncio lock protects writes. thought_signature chain
#     intentionally broken on RECALL re-invoke.
# 23. [Pattern]: _ws_mode ("legacy"/"reverse") gates dispatch path. Reverse uses dispatch_to_agent + registry. Legacy uses agent.process() + per-task WS.
# 24. [Pattern]: Intermediate phase: _process_intermediate runs during active agent execution on ALL
#     non-brain turns (including user messages). Tools: reply_to_agent/message_agent/wait_for_agent.
#     Token limit: 256 (agent-only), 1024 (user or huddle present). NEVER add wait_for_user to
#     intermediate -- it sets _waiting_for_user which blocks reconcile for that event. Appends brain.intermediate,
#     marks turns EVALUATED.
# 32. [Pattern]: brain.thoughts (internal reasoning, is_thought=True tokens) -- NOT fed to LLM prompt
#     (_turn_to_parts returns []), no pulse, no _waiting_for_user. Dashboard/JARVIS can see it.
# 33. [Pattern]: brain.response (visible reply, is_thought=False text) -- IN LLM prompt as role=model,
#     emits pulse (tool:brain_response), updates _last_processed, sets _waiting_for_user for slack/chat.
# 34. [Gotcha]: Legacy brain.think stays IN LLM prompt with [Internal observation] wrapper (backward
#     compat for old Redis events). New code MUST produce brain.thoughts or brain.response, not brain.think.
# 25. [Pattern]: WIP cap (two layers):
#     Layer 1 (per-source): _get_source_wip_limit + _count_source_wip gate NEW->ACTIVE transition.
#       Counts events in ACTIVE+DEFERRED status for the source. NEW events are input buffer, not WIP.
#       ONLY applies to _EPHEMERAL_ONLY_SOURCES (aligner, headhunter, timekeeper) -- sources whose
#       events exclusively use ephemeral agents. Internal-agent sources (chat, slack) are NOT gated
#       at admission; their bottleneck is agent idle/busy at dispatch time.
#       {SOURCE}_MAX_ACTIVE env var (default 1 for ephemeral sources). Event close is the release trigger.
#       Events in _waiting_for_user are excluded from WIP count (Propose and Prompt slot release).
#     Layer 2 (global): _dispatch_semaphore on select_agent. May recursively call defer_event -- safe,
#       defer_event does not recurse back into select_agent.
#     DO NOT add agent-dispatching logic to the defer_event handler.
# 26. [Pattern]: Ephemeral dispatch is two-tier: (a) primary -- headhunter/timekeeper/kargo_stage always use ephemeral,
#     (b) overflow -- chat/slack scale to ephemeral when local sidecars are full, gated by {SOURCE}_MAX_ACTIVE env var.
#     Circuit breaker for overflow defers (local was already full); circuit breaker for primary falls back to local.
#     Provisioner is pure plumbing (spawn/terminate). Capacity logic lives in Brain (event-based WIP gate).
#     Volume write gate: write_event_to_volume runs only when agent_id_override is None (local sidecar dispatch).
#     Ephemeral agents fetch the event document via REST (/events/{id}/document), not the shared volume.
# 27. [Pattern]: Nudge cascade guard: if an unevaluated automated nudge turn exists, skip injection and fall through to LLM so it evaluates the nudge before escalation fires.
# 28. [Gotcha]: NEVER add `from datetime import ...` inside _execute_function_call. The module-level import (line 59) covers all branches. A local import shadows it for the ENTIRE function per Python scoping, causing UnboundLocalError in branches that don't execute the import.
# 42. [Pattern]: handle_wake_task stores mode from WS wake_register (default implement). Unlike _run_agent_task it does not clear sessions on prior_mode mismatch; wake uses last sidecar context and full-tool mode by design.
# 30. [Pattern]: _build_event_state_header: live 2-line compass inserted at TOP of system prompt
#     (insert(0), unlike DEFER/WAIT which append). Line 1: domain/severity/phase/turn/wall-clock.
#     Line 2: evidence delta since last classify_event. Challenge question "Any new evidence to
#     reclassify?" fires only on agent return (plan/execute) or user message -- prevents
#     reclassification loop by not prompting when nothing new happened.
# 31. [Pattern]: Message-mode early return in _run_agent_task: when mode=="message" AND no deliverable
#     in result_str (< 100 chars, no frontmatter), skip result turn. If sendResults shell fallback
#     bypassed the MCP notInModes gate and result_str has content (>100 chars or frontmatter),
#     fall through to write the result as a conversation turn. This ensures wait_for_agent sees it.
# 31. [Pattern]: Cross-source event merge: when dedup detects same MR URL across different sources
#     (kargo_context.mr_url vs gitlab_context.target_url), inject the duplicate's evidence as
#     actor=source, action="evidence", result=<formatted context> turn into the FILO survivor
#     via _append_and_broadcast, then close the duplicate. Cross-source guard: existing.source
#     != event.source. "headhunter" excluded from has_agent_result + all agent-turn classifiers
#     (agent_rounds, last_agent, _surface_agent_recommendation, legacy thinking) so dispatch
#     phase stays active and recommendation surfacing skips evidence turns.
#     URL normalized: split("#")[0].rstrip("/").
# 32. [Pattern]: _cleanup_stale_events calls hh.process_event_feedback directly for headhunter events
#     (mirrors _close_and_broadcast). signal.set() AFTER direct feedback to wake poll loop (slot opened).
#     Safe ordering: feedback processed first, then signal wakes poll to pick up next todo.
# 33. [Pattern]: _handle_orphan_blank_event() encapsulates orphan recovery logic.
#     _orphan_requeue_count tracks attempts per event. Cap at 3, then close as error.
#     Reset on successful first turn or on close.
#     In-memory only -- assumes single Brain instance per cluster. Multi-replica makes cap best-effort.
#     [Pattern]: NEW events with no conversation are WIP-gated. The scan re-attempts process_event()
#     each cycle so they are admitted as soon as capacity opens. process_event() re-checks the WIP
#     gate internally -- no risk of bypassing admission control.
# 35. [Gotcha]: set_phase no-op (already in requested phase) MUST still write a turn and return True.
#     Returning False without a turn leaves event.conversation empty, triggering the orphan blank-event
#     guard on the next scan (3 retries, force close). The LLM deterministically calls set_phase("triage")
#     on fresh headhunter events because brain_phase defaults to "triage" at creation.
# 36. [Pattern]: Google Search grounding gated by BRAIN_GOOGLE_SEARCH_ENABLED env var + phase (triage/investigate).
#     Brain calls adapter.set_search_enabled() before/after generate_stream via try/finally. hasattr guard for Claude.
#     Grounding metadata formatted as evidence, not thoughts. Graceful fallback if search unavailable.
# 36b. [Pattern]: _resolve_grounding_urls() follows Vertex grounding-api-redirect URIs to canonical URLs
#     via httpx HEAD with follow_redirects=True, 2.5s timeout. Shared AsyncClient per batch. Deduplicates
#     by resolved URL. Fallback: empty URI -> title rendered without link. Non-redirect URIs pass through.
# 37. [Pattern]: respond_to_jarvis tool is conversation-gated: only available when the most recent
#     jarvis.message turn has no subsequent brain.respond_jarvis turn. Handler appends turn AND
#     sends response to LiveAPIAdapter.receive_brain_response() for real-time delivery.
#     _live_adapter set by main.py when SYSTEM2_ENABLED=true.
# 34. [Pattern]: Resync scan blank-event guard uses processing_started_at with queued_at
#     fallback as orphan discriminator. Covers both "dequeued but crashed before stamp" and
#     "never dequeued" cases. Error turn from catch-all is marked evaluated immediately to
#     prevent hot retry loops (has_unread=True -> process_event -> fail -> repeat).
# 38. [Pattern]: _waiting_for_jarvis (dict[str,float]) is SEPARATE from _waiting_for_user.
#     Maps event_id -> respond_jarvis turn timestamp. _jarvis_wait_tasks holds asyncio.Task
#     for nudge timer. _jarvis_wait_count tracks escalation (1st: 2 nudges, 2nd: 1, 3rd: 0,
#     4th+: tool stripped). Cleaned in _clear_jarvis_wait, called from _close_and_broadcast,
#     _cleanup_stale_events, and event loop resolution scan. NEVER add to _waiting_for_user.
# 39. [Pattern]: Sticky notes gates: post_sticky_note requires source=jarvis+phase=close; read_sticky_notes requires unread_notes>0.
# 40. [Pattern]: Memory reflex: SentenceChunker + ReflexSearcher fire async lesson searches
#     during thinking stream. Gate stores hits in _recall_lessons (overwrite) and returns True
#     to re-invoke LLM with RECALL block in SI. BRAIN_MEMORY_REFLEX env var. Max 1 gate per cycle.
#     Reflex searches share Archivist embedding quota. Cap at BRAIN_REFLEX_MAX_SEARCHES (5) per cycle.
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

import httpx

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
    "security_analyst": "/data/workspace",
}

# Brain-declared phase -> additional skill folders to load alongside plumbing phases.
# Plumbing phases (always, source, context, multi-user) are auto-detected from data presence.
# System states (intermediate, waiting) preempt Brain phase via early-return in _match_phases.
BRAIN_PHASE_SKILLS: dict[str, list[str]] = {
    "triage":       [],
    "investigate":  ["dispatch"],
    "execute":      ["dispatch", "coordination"],
    "verify":       ["post-agent", "defer-wake"],
    "escalate":     ["post-agent", "escalate"],
    "close":        ["close"],
}

# Context priming: synthetic prefill so the LLM treats protocols as already-committed.
# Update BRAIN_PREFILL_MODEL if always/ skill protocols change materially.
BRAIN_PREFILL_USER = "Session active. Review your core protocols before processing."

BRAIN_PREFILL_MODEL = (
    "Darwin online. Protocols locked: "
    "(1) Deep memory before routing -- history beats guesswork. "
    "(2) Cynefin triage on every event. "
    "(3) Never drop agent recommendations. "
    "(4) Phase-gated close and escalation. "
    "(5) Voice: confident peer, Cynefin-gated tone. "
    "Let's get to work."
)


def _wrap_skill_section(path: str, body: str) -> str:
    """Wrap a skill body with <skill_section> XML tags for SI self-reference."""
    return f'<skill_section id="{path}">\n{body}\n</skill_section>'


class Brain:
    """
    Brain orchestrator - thin shell around LLM function calling.
    
    ALL decision logic lives in system prompt (brain_skills/) + function declarations.
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
        # Wait-for-user state: event_id -> wait_start_timestamp (serves idle timeout + on-ice threshold)
        self._waiting_for_user: dict[str, float] = {}
        # Idle timeout manager for chat/slack events (warn + auto-close)
        from ..scheduling.idle_timeout import IdleTimeoutManager
        self._idle_timeout = IdleTimeoutManager(
            warn_callback=self._idle_timeout_warn,
            close_callback=self._idle_timeout_close,
        )
        self._waiting_for_agent: dict[str, str] = {}  # event_id -> agent_name
        # Wait-for-jarvis state (SEPARATE from _waiting_for_user -- never merged)
        self._waiting_for_jarvis: dict[str, float] = {}   # event_id -> respond_jarvis turn timestamp
        self._jarvis_wait_tasks: dict[str, asyncio.Task] = {}  # event_id -> nudge timer task
        self._jarvis_wait_count: dict[str, int] = {}  # event_id -> escalation counter
        self._incident_created: set[str] = set()
        # Last process_event timestamp per event (for idle safety net)
        self._last_processed: dict[str, float] = {}
        # Orphan re-queue attempts per event (blank events stuck in active set)
        self._orphan_requeue_count: dict[str, int] = {}
        # LLM reasoning (thinking) per event -- consumed by _emit_executive_pulse for JARVIS
        self._reasoning_by_event: dict[str, str | None] = {}
        # Defer-wake one-shot flag: first pulse after defer re-activation gets is_defer_wake=True
        self._defer_wake_events: set[str] = set()
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
        self._scheduler = None  # ReconcileScheduler | None -- set by start_event_loop()
        self.pulse_port = None  # PulsePort | None -- set by main.py when pulse tracking enabled
        self._ws_mode = os.getenv("AGENT_WS_MODE", "legacy")
        self._ephemeral_provisioner = None
        self._live_adapter = None  # LiveAPIAdapter -- set by main.py when System 2 enabled
        self._memory_reflex_enabled = os.getenv("BRAIN_MEMORY_REFLEX", "false").lower() == "true"
        self._reflex_fired_for: set[str] = set()  # event IDs with gate already fired this cycle
        self._recall_lessons: dict[str, list] = {}  # event_id -> lesson hits for RECALL SI block
        self._last_embedding_warmup: float = 0.0
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

        self._search_enabled = os.getenv("BRAIN_GOOGLE_SEARCH_ENABLED", "false").lower() == "true"

        skills_status = f"progressive ({len(self._skill_loader.available_phases())} phases)" if self._skill_loader else "monolith"
        wip_status = f"wip_cap={max_dispatches}" if max_dispatches > 0 else "wip_cap=off"
        search_status = "search=on" if self._search_enabled else "search=off"
        logger.info(f"Brain initialized (provider={self.provider}, model={self.model_name}, skills={skills_status}, {wip_status}, {search_status}, agents={list(self.agents.keys())})")

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

    # Sources whose events exclusively use ephemeral agents (Tier 1).
    # These get WIP-gated at admission (NEW->ACTIVE). Internal-agent sources
    # (chat, slack) are NOT gated here -- their bottleneck is dispatch-time
    # agent availability, not event count.
    _EPHEMERAL_ONLY_SOURCES = frozenset({"aligner", "headhunter", "timekeeper"})

    # Roles with no persistent sidecar -- always dispatch via EphemeralProvisioner.
    EPHEMERAL_ONLY_ROLES = frozenset({"security_analyst"})

    def _get_source_wip_limit(self, source: str) -> int:
        """Per-source WIP limit for ephemeral-only sources.

        Returns 0 (unlimited) for sources that use internal agents (chat,
        slack). Only Tier 1 ephemeral sources are admission-gated.
        """
        if source not in self._EPHEMERAL_ONLY_SOURCES:
            return 0
        env_key = f"{source.upper().replace('-', '_')}_MAX_ACTIVE"
        return int(os.environ.get(env_key, "1"))

    async def _count_source_wip(self, source: str, exclude_id: str = "") -> int:
        """Count events admitted for a source (status ACTIVE or DEFERRED).

        NEW events are in the input buffer and don't count as WIP.
        CLOSED events are out of the system.
        Events parked in _waiting_for_user (Propose and Prompt awaiting
        maintainer reply) are excluded -- they release the WIP slot so
        new events can be admitted while the proposal awaits authorization.
        """
        active_ids = await self.blackboard.get_active_events()
        count = 0
        for eid in active_ids:
            if eid == exclude_id:
                continue
            if eid in self._waiting_for_user:
                continue
            evt = await self.blackboard.get_event(eid)
            if evt and evt.source == source and evt.status in (EventStatus.ACTIVE, EventStatus.DEFERRED):
                count += 1
        return count

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

    @staticmethod
    def _extract_mr_url(event: EventDocument) -> str | None:
        """Extract normalized MR URL from gitlab_context or kargo_context.

        Returns None safely for legacy string evidence (pre-EventEvidence data).
        """
        if not (event.event and event.event.evidence):
            return None
        ev = event.event.evidence
        url = None
        gl = getattr(ev, "gitlab_context", None)
        if isinstance(gl, dict) and gl.get("target_url"):
            url = gl["target_url"]
        if not url:
            kc = getattr(ev, "kargo_context", None)
            if isinstance(kc, dict) and kc.get("mr_url"):
                url = kc["mr_url"]
        if url:
            return url.split("#")[0].rstrip("/")
        return None

    @staticmethod
    def _format_merge_evidence(duplicate: EventDocument) -> str:
        """Format duplicate event's evidence as markdown for conversation injection.

        Intentionally duplicates structure from _event_to_markdown (lines 3497-3531)
        rather than sharing a helper, because _event_to_markdown is a @staticmethod
        used by queue.py (ai-rule #8) and the merge format may diverge.
        """
        lines = [
            f"Related event {duplicate.id} (source={duplicate.source}) "
            f"detected for the same MR. Context merged below.",
            "",
            f"**Service:** {duplicate.service}",
            f"**Reason:** {duplicate.event.reason if duplicate.event else 'unknown'}",
        ]
        evidence = duplicate.event.evidence if duplicate.event else None
        if evidence and hasattr(evidence, "gitlab_context") and evidence.gitlab_context:
            gl = evidence.gitlab_context
            lines.append("")
            lines.append("## GitLab Context")
            lines.append(f"- **Project:** {gl.get('project_path', '')}")
            lines.append(f"- **MR:** !{gl.get('mr_iid', '')} - {gl.get('mr_title', '')}")
            lines.append(f"- **MR URL:** {gl.get('target_url', '')}")
            lines.append(f"- **Pipeline:** {gl.get('pipeline_status', 'unknown')}")
            lines.append(f"- **Merge Status:** {gl.get('merge_status', '')}")
            lines.append(f"- **Author:** {gl.get('author', '')}")
            maintainer = gl.get("maintainer", {})
            if maintainer:
                emails = maintainer.get("emails", [])
                lines.append(f"- **Maintainer Emails:** {', '.join(emails) if emails else 'none'}")
            mr_desc = gl.get("mr_description", "")
            if "Bot Instructions" in mr_desc:
                bot_start = mr_desc.find("### Bot Instructions")
                if bot_start >= 0:
                    lines.append("")
                    lines.append(mr_desc[bot_start:].strip())
        if evidence and hasattr(evidence, "kargo_context") and evidence.kargo_context:
            kc = evidence.kargo_context
            lines.append("")
            lines.append("## Kargo Context")
            lines.append(f"- **Project:** {kc.get('project', '')}")
            lines.append(f"- **Stage:** {kc.get('stage', '')}")
            lines.append(f"- **Promotion:** {kc.get('promotion', '')}")
            lines.append(f"- **Phase:** {kc.get('phase', '')}")
            lines.append(f"- **Failed Step:** {kc.get('failed_step', 'N/A')}")
            lines.append(f"- **Error:** {kc.get('message', '')}")
            if kc.get("mr_url"):
                lines.append(f"- **MR URL:** {kc['mr_url']}")
        return "\n".join(lines)

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

        # WAITING-FOR-AGENT guard: skip processing until a participant responds.
        # Any DELIVERED turn (from agent, JARVIS, user, aligner) clears the wait --
        # FRIDAY doesn't need to know which participant she was waiting for.
        if event_id in self._waiting_for_agent:
            has_response = any(t.status.value == "delivered" for t in event.conversation)
            if has_response:
                self._waiting_for_agent.pop(event_id, None)
                logger.info(f"Cleared _waiting_for_agent for {event_id}: participant responded")
            else:
                logger.debug(f"Skipping process_event for {event_id}: waiting for participant")
                return

        # Clear orphan re-queue count on successful recovery (event now has turns)
        if event.conversation and event_id in self._orphan_requeue_count:
            self._orphan_requeue_count.pop(event_id, None)

        # Dedup: if this is a new event (no turns yet), check for existing active events.
        # Two passes per iteration (single loop):
        #   Pass 1: service-name match (same-source duplicates, existing behavior)
        #   Pass 2: MR URL cross-match (cross-source duplicates, new -- kargo <-> headhunter)
        # Skip for user-initiated sources (chat/slack) -- "general" is a catch-all.
        if not event.conversation and event.source not in ("chat", "slack"):
            active_ids = await self.blackboard.get_active_events()
            new_ctx = (getattr(event.event.evidence, "gitlab_context", None) or {}) if (event.event and event.event.evidence) else {}
            new_mr = new_ctx.get("mr_iid")
            new_project = new_ctx.get("project_id")
            new_mr_url = self._extract_mr_url(event)
            for eid in active_ids:
                if eid == event_id:
                    continue
                existing = await self.blackboard.get_event(eid)
                if not (existing
                        and existing.conversation
                        and existing.status.value in ("active", "new", "deferred")):
                    continue

                # Pass 1: service-name match (existing behavior)
                if existing.service == event.service:
                    ex_ctx = (getattr(existing.event.evidence, "gitlab_context", None) or {}) if (existing.event and existing.event.evidence) else {}
                    ex_mr = ex_ctx.get("mr_iid")
                    ex_project = ex_ctx.get("project_id")
                    if new_project and ex_project and new_project != ex_project:
                        pass  # fall through to URL check
                    elif new_mr and ex_mr and new_mr != ex_mr:
                        pass  # fall through to URL check
                    else:
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

                # Pass 2: MR URL cross-match (cross-source only)
                if new_mr_url and existing.source != event.source:
                    existing_mr_url = self._extract_mr_url(existing)
                    if existing_mr_url and existing_mr_url == new_mr_url:
                        merge_text = self._format_merge_evidence(event)
                        turn = ConversationTurn(
                            turn=len(existing.conversation) + 1,
                            actor=event.source,
                            action="evidence",
                            result=merge_text,
                            thoughts=f"Duplicate event {event_id} closed -- {event.source} context merged.",
                        )
                        await self._append_and_broadcast(eid, turn)
                        logger.info(
                            f"Cross-source merge: {event_id} -> {eid} "
                            f"(MR URL match: {new_mr_url})"
                        )
                        await self._close_and_broadcast(
                            event_id,
                            f"Duplicate (MR URL match): context merged into {eid}.",
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
            if t.actor in ("architect", "sysadmin", "developer", "qe", "security_analyst")
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
        # Per-source WIP gate: count events already admitted (ACTIVE + DEFERRED)
        # for this source. If at capacity, leave event as NEW and skip processing.
        if event.status == EventStatus.NEW:
            source_limit = self._get_source_wip_limit(event.source)
            if source_limit > 0:
                wip = await self._count_source_wip(event.source, exclude_id=event_id)
                if wip >= source_limit:
                    logger.info(
                        "Source WIP gate: %s at capacity (%d/%d). "
                        "Event %s stays NEW.",
                        event.source, wip, source_limit, event_id,
                    )
                    return
            if await self.blackboard.transition_event_status(event_id, "new", EventStatus.ACTIVE):
                logger.info(f"Event {event_id} transitioned NEW -> ACTIVE")
                await self._broadcast({
                    "type": "event_status_changed",
                    "event_id": event_id,
                    "status": EventStatus.ACTIVE.value,
                })

        # Health check: nudge idle events, escalate to human after max nudges.
        # Guards: skip if deferred (intentional wait), waiting for user/jarvis, or last real turn is brain.defer (just woke).
        if event.conversation and event_id not in self._waiting_for_user and event_id not in self._waiting_for_jarvis:
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
        try:
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
                await self.blackboard.mark_turns_evaluated(event_id, up_to_turn=turn_snapshot + 1)
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
                    iteration=iteration,
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
            # Also mark consecutive brain turns appended during the LLM loop (tool results),
            # but stop at the first non-brain turn (e.g., aligner confirm, agent progress).
            event_after = await self.blackboard.get_event(event_id)
            extra_brain_count = 0
            if event_after:
                extra_brain_turns = []
                for t in event_after.conversation[turn_snapshot:]:
                    if t.actor == "brain":
                        extra_brain_turns.append(t.turn)
                    else:
                        break
                if extra_brain_turns:
                    extra_brain_count = len(extra_brain_turns)
                    await self.blackboard.mark_turns_evaluated(
                        event_id, up_to_turn=turn_snapshot + extra_brain_count
                    )
            await self._broadcast_status_update(
                event_id, "evaluated",
                turns=list(range(1, turn_snapshot + extra_brain_count + 1)),
            )
        except Exception as e:
            event_fresh = await self.blackboard.get_event(event_id)
            if event_fresh and not event_fresh.conversation:
                error_turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="error",
                    thoughts=f"Brain failed on first processing: {type(e).__name__}: {e}",
                )
                await self._append_and_broadcast(event_id, error_turn)
                await self.blackboard.mark_turns_evaluated(event_id)
            raise

    async def _process_with_llm(
        self,
        event_id: str,
        event: EventDocument,
        *,
        is_defer_wake: bool = False,
        iteration: int = 0,
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

        # Sticky note notification injection (iteration 0 only, dedup by existing turn)
        if iteration == 0:
            unread = getattr(event, "unread_notes", 0) or 0
            if unread > 0:
                has_notification = any(
                    t.actor == "system" and t.action == "notification"
                    for t in event.conversation
                )
                if not has_notification:
                    notif_turn = ConversationTurn(
                        turn=(await self._next_turn_number(event_id)),
                        actor="system",
                        action="notification",
                        thoughts=f"{unread} unread sticky note{'s' if unread != 1 else ''}. You want to read them?",
                    )
                    await self._append_and_broadcast(event_id, notif_turn)
                    event = await self.blackboard.get_event(event_id)

        # Progressive skill loading: build phase-specific system prompt + LLM params
        if self._progressive_skills and self._skill_loader:
            context_flags = await self._extract_context_flags(event)
            if is_defer_wake:
                context_flags["is_defer_wakeup"] = True
                context_flags["consecutive_defers"] = max(context_flags.get("consecutive_defers", 0), 1)
            active_phases = self._match_phases(event, context_flags)
            system_prompt = await self._build_system_prompt(event, active_phases, context_flags)
            thinking_level, call_temp, phase_max_tokens = self._resolve_llm_params(active_phases)
        else:
            system_prompt = BRAIN_SYSTEM_PROMPT
            thinking_level, call_temp = self._determine_thinking_params_legacy(event)
            phase_max_tokens = self.max_output_tokens
            context_flags = None

        # Strip defer_event on first iteration of defer-wake -- forces Brain to act
        # before re-deferring. After iteration 0, defer is available so LLM can
        # re-defer based on tool results + skill protocol.
        active_tools = BRAIN_TOOL_SCHEMAS
        if is_defer_wake and iteration == 0:
            active_tools = [t for t in BRAIN_TOOL_SCHEMAS if t["name"] != "defer_event"]
            logger.info(f"Defer-wake iter 0: stripped defer_event from tools for {event_id}")

        # === Phase-driven tool gating ===
        # Code reads the Brain's declared phase and provides matching tools.
        # Same pattern as domain gating (CLEAR strips create_plan, etc.).
        brain_phase = event.brain_phase or "triage"

        # Phase gates: tools gated to specific phases
        escalate_tools = {"report_incident"}
        if brain_phase != "escalate":
            active_tools = [t for t in active_tools if t["name"] not in escalate_tools]

        notify_tools = {"notify_user_slack"}
        if brain_phase not in ("escalate", "close"):
            active_tools = [t for t in active_tools if t["name"] not in notify_tools]
        else:
            maintainer_emails = self._resolve_maintainer_enum(event)
            if maintainer_emails:
                active_tools = self._inject_maintainer_enum(active_tools, maintainer_emails)

        close_tools = {"close_event", "notify_gitlab_result"}
        if brain_phase not in ("escalate", "close"):
            active_tools = [t for t in active_tools if t["name"] not in close_tools]

        observation_tools = {"record_observation", "list_observations"}
        if brain_phase == "close":
            active_tools = [t for t in active_tools if t["name"] not in observation_tools]

        # Jira tools: comment available during execution + close; transition in investigate/verify/close
        jira_phases = ("investigate", "verify", "escalate", "close")
        if brain_phase not in jira_phases:
            active_tools = [t for t in active_tools if t["name"] not in {"comment_jira_issue", "transition_jira_issue"}]

        # Refresh tools: available in triage and verify, with strip-after-use guard
        refresh_tools = {"refresh_gitlab_context", "refresh_kargo_context", "fetch_jira_issue"}
        has_kargo = (
            event.event and event.event.evidence
            and hasattr(event.event.evidence, "kargo_context")
            and event.event.evidence.kargo_context
        )
        if not has_kargo:
            active_tools = [t for t in active_tools if t["name"] != "refresh_kargo_context"]

        if brain_phase not in ("triage", "verify"):
            active_tools = [t for t in active_tools if t["name"] not in refresh_tools]
        else:
            if is_defer_wake:
                last_window_ts = next(
                    (t.timestamp for t in reversed(event.conversation)
                     if t.actor == "brain" and t.action == "defer"),
                    0,
                )
            else:
                # Window boundary = the most recent phase transition into the CURRENT phase.
                # Refreshes from a prior phase (e.g., triage) don't block the new phase's refresh.
                # Phase turns store "Phase: VERIFY. ..." in thoughts -- match current brain_phase.
                last_window_ts = next(
                    (t.timestamp for t in reversed(event.conversation)
                     if t.actor == "brain" and t.action == "phase"
                     and (t.thoughts or "").lower().startswith(f"phase: {brain_phase}")),
                    0,
                )
            recent_gl_refresh = any(
                t.actor == "brain" and t.waitingFor == "refresh_gitlab_context"
                and t.timestamp >= last_window_ts
                for t in event.conversation
            )
            if recent_gl_refresh:
                active_tools = [t for t in active_tools if t["name"] != "refresh_gitlab_context"]
                logger.info(f"Refresh window guard: stripped refresh_gitlab_context for {event_id}")

            if has_kargo:
                recent_kargo_refresh = any(
                    t.actor == "brain" and t.waitingFor == "refresh_kargo_context"
                    and t.timestamp >= last_window_ts
                    for t in event.conversation
                )
                if recent_kargo_refresh:
                    active_tools = [t for t in active_tools if t["name"] != "refresh_kargo_context"]
                    logger.info(f"Refresh window guard: stripped refresh_kargo_context for {event_id}")

        # === Domain classification gate (mandatory before routing) ===
        if context_flags and not context_flags.get("brain_has_classified", False):
            pre_classify_tools = {"lookup_service", "lookup_journal", "consult_deep_memory", "classify_event", "set_phase"}
            # Human-initiated events: allow wait_for_user before classification.
            # A greeting or vibe check is Cynefin Confusion -- the domain isn't known yet.
            # FRIDAY can pause and ask what's on their mind before forcing a classification.
            if event.source in ("slack", "chat"):
                pre_classify_tools.add("wait_for_user")
            active_tools = [t for t in active_tools if t["name"] in pre_classify_tools]
            logger.info(f"Pre-classification gate: only lookup+classify+set_phase tools for {event_id}")
        elif context_flags:
            domain = context_flags.get("event_domain", "complicated")
            if domain == "clear":
                active_tools = [t for t in active_tools if t["name"] != "create_plan"]
                logger.info(f"CLEAR domain: create_plan gated (act directly) for {event_id}")
            elif domain == "complex":
                agent_rounds = sum(1 for t in event.conversation if t.actor not in ("brain", "user", "aligner", "headhunter"))
                if agent_rounds < 4:
                    active_tools = [t for t in active_tools if t["name"] != "close_event"]
                    logger.info(f"COMPLEX domain: close_event gated until 4+ agent rounds ({agent_rounds} so far) for {event_id}")
            elif domain == "chaotic":
                chaotic_tools = {"select_agent", "classify_event", "lookup_service", "lookup_journal", "notify_user_slack", "get_plan_progress", "report_incident", "set_phase"}
                active_tools = [t for t in active_tools if t["name"] in chaotic_tools]
                logger.info(f"CHAOTIC domain: restricted to act-first tool set for {event_id}")

        # === JARVIS response gate ===
        # Strip respond_to_jarvis unless an unanswered jarvis.message or jarvis.insight exists.
        # For jarvis-sourced events: the initial JARVIS prompt is the event evidence, not a
        # conversation turn. Treat it as an implicit unanswered message until FRIDAY responds.
        has_unanswered_jarvis = False
        if event.source == "jarvis" and not any(
            t.actor == "brain" and t.action == "respond_jarvis" for t in event.conversation
        ):
            has_unanswered_jarvis = True  # Implicit: JARVIS created the event, FRIDAY hasn't responded yet
        else:
            for t in reversed(event.conversation):
                if t.actor == "jarvis" and t.action in ("message", "insight"):
                    has_unanswered_jarvis = True
                    break
                if t.actor == "brain" and t.action == "respond_jarvis":
                    break
        if not has_unanswered_jarvis:
            active_tools = [t for t in active_tools if t["name"] != "respond_to_jarvis"]

        # === wait_for_jarvis gate ===
        # Available only: jarvis-sourced events, after respond_jarvis sent, not already waiting, count < 3
        if event.source == "jarvis":
            has_respond = any(t.actor == "brain" and t.action == "respond_jarvis" for t in event.conversation)
            already_waiting = event_id in self._waiting_for_jarvis
            max_retries = self._jarvis_wait_count.get(event_id, 0) >= 3
            if not (has_respond and not already_waiting and not max_retries):
                active_tools = [t for t in active_tools if t["name"] != "wait_for_jarvis"]
        else:
            active_tools = [t for t in active_tools if t["name"] != "wait_for_jarvis"]

        # === inspect_event gate ===
        # Available only in jarvis-sourced meta-events
        if event.source != "jarvis":
            active_tools = [t for t in active_tools if t["name"] != "inspect_event"]

        # === Sticky notes gates ===
        if not (event.source == "jarvis" and brain_phase == "close"):
            active_tools = [t for t in active_tools if t["name"] != "post_sticky_note"]

        unread = getattr(event, "unread_notes", 0) or 0
        if unread <= 0:
            active_tools = [t for t in active_tools if t["name"] != "read_sticky_notes"]

        # Reorder tools: always-available first, then phase-relevant, then rest.
        # Gives the LLM a signal about what's most useful for the current phase.
        _always_tools = {"lookup_service", "lookup_journal", "consult_deep_memory", "classify_event", "set_phase", "wait_for_user", "read_sticky_notes"}
        _phase_tool_priority: dict[str, set[str]] = {
            "triage":      {"refresh_gitlab_context", "refresh_kargo_context"},
            "investigate":  {"select_agent", "create_plan", "message_agent", "defer_event"},
            "execute":      {"select_agent", "create_plan", "message_agent", "reply_to_agent", "defer_event"},
            "verify":       {"refresh_gitlab_context", "refresh_kargo_context", "get_plan_progress", "defer_event"},
            "escalate":     {"report_incident", "notify_user_slack", "notify_gitlab_result", "close_event", "defer_event"},
            "close":        {"close_event", "notify_gitlab_result", "notify_user_slack", "post_sticky_note"},
        }
        # Hard strip: defer_event and wait_for_user not available in triage or jarvis-sourced events
        if brain_phase == "triage" or event.source == "jarvis":
            active_tools = [t for t in active_tools if t["name"] not in ("defer_event", "wait_for_user")]
        elif event.source not in ("chat", "slack"):
            active_tools = [t for t in active_tools if t["name"] != "wait_for_user"]
        priority_names = _phase_tool_priority.get(brain_phase, set())
        tier_always = [t for t in active_tools if t["name"] in _always_tools]
        tier_phase = [t for t in active_tools if t["name"] in priority_names and t["name"] not in _always_tools]
        tier_rest = [t for t in active_tools if t["name"] not in _always_tools and t["name"] not in priority_names]
        # Sticky note urgency: surface read_sticky_notes FIRST when unread
        unread = getattr(event, "unread_notes", 0) or 0
        if unread > 0:
            tier_sticky = [t for t in tier_always if t["name"] == "read_sticky_notes"]
            tier_always = [t for t in tier_always if t["name"] != "read_sticky_notes"]
            active_tools = tier_sticky + tier_always + tier_phase + tier_rest
        else:
            active_tools = tier_always + tier_phase + tier_rest

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
        last_grounding = None

        want_search = self._search_enabled and brain_phase in ("triage", "investigate")
        if want_search and hasattr(self._adapter, 'set_search_enabled'):
            self._adapter.set_search_enabled(True)

        reflex_chunker = None
        reflex_searcher = None
        if self._memory_reflex_enabled and event_id not in self._reflex_fired_for:
            try:
                from .brain_reflex import SentenceChunker, ReflexSearcher
                archivist = self.agents.get("_archivist_memory")
                if archivist and hasattr(archivist, "search_lessons"):
                    reflex_chunker = SentenceChunker()
                    reflex_searcher = ReflexSearcher(
                        archivist,
                        event_id,
                        score_threshold=float(os.getenv("BRAIN_REFLEX_THRESHOLD", "0.60")),
                        max_searches=int(os.getenv("BRAIN_REFLEX_MAX_SEARCHES", "5")),
                    )
            except Exception as e:
                logger.warning(f"Memory reflex init failed for {event_id}: {e}")

        try:
            for attempt in range(max_retries + 1):
                accumulated_text = ""
                accumulated_thoughts = ""
                function_call = None
                raw_parts = None
                last_grounding = None

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
                            if chunk.is_thought:
                                accumulated_thoughts += chunk.text
                                if reflex_chunker:
                                    window = reflex_chunker.feed(chunk.text)
                                    if window and reflex_searcher:
                                        reflex_searcher.fire(window)
                            else:
                                accumulated_text += chunk.text
                            await self._broadcast({
                                "type": "brain_thinking",
                                "event_id": event_id,
                                "text": chunk.text,
                                "accumulated": accumulated_thoughts + accumulated_text,
                                "is_thought": chunk.is_thought,
                            })
                        if chunk.function_call:
                            function_call = chunk.function_call
                        if chunk.raw_parts:
                            raw_parts = chunk.raw_parts
                        if chunk.grounding_metadata:
                            last_grounding = chunk.grounding_metadata
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
        finally:
            if want_search and hasattr(self._adapter, 'set_search_enabled'):
                self._adapter.set_search_enabled(False)

        # Clear thinking indicator ONCE after the loop exits
        await self._broadcast({"type": "brain_thinking_done", "event_id": event_id})

        # If all retries failed with no output, write error turn
        if last_error and not function_call and not accumulated_text and not accumulated_thoughts:
            self._reasoning_by_event.pop(event_id, None)
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

        grounding_evidence = ""
        if last_grounding and last_grounding.get("chunks"):
            resolved_chunks = await self._resolve_grounding_urls(last_grounding["chunks"])
            sources = "\n".join(
                f"- [{c['title']}]({c['uri']})"
                for c in resolved_chunks
                if c.get("uri")
            )
            queries = ", ".join(last_grounding.get("queries", []))
            grounding_evidence = f"\n\n## Web Search Context\n\nQueries: {queries}\n\nSources:\n{sources}"
            logger.info(f"Google Search grounding for {event_id}: {len(resolved_chunks)} sources (resolved)")

        # Process the final result
        if function_call:
            valid_tool_names = {t["name"] for t in active_tools}
            if function_call.name not in valid_tool_names:
                logger.warning(
                    f"Hallucinated tool '{function_call.name}' for {event_id} "
                    f"(active: {valid_tool_names})"
                )
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="That action is not available right now. "
                             "Review the current phase and what actions are appropriate for it.",
                    response_parts=captured_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            logger.info(f"Brain LLM decision for {event_id}: {function_call.name}")

            # Flush remaining thinking buffer for final sentence search
            if reflex_chunker and reflex_searcher:
                final_window = reflex_chunker.flush()
                if final_window:
                    reflex_searcher.fire(final_window)

            # Memory reflex gate: check for lesson matches before executing tool
            if reflex_searcher and event_id not in self._reflex_fired_for:
                try:
                    lessons = await reflex_searcher.gather(timeout=0.5)
                    if lessons:
                        titles = [l["payload"].get("title", "") for l in lessons]
                        self._recall_lessons[event_id] = lessons
                        self._reflex_fired_for.add(event_id)
                        try:
                            await self._broadcast({
                                "type": "brain_recall_hit",
                                "event_id": event_id,
                                "lesson_count": len(lessons),
                                "titles": titles,
                                "blocked_tool": function_call.name,
                            })
                        except Exception as be:
                            logger.warning(f"RECALL broadcast failed for {event_id} (non-fatal): {be}")
                        logger.info(
                            f"Brain RECALL: gate fired for {event_id}, "
                            f"blocked {function_call.name}, {len(lessons)} lessons stored"
                        )
                        return True  # Re-invoke LLM with RECALL block in SI
                except Exception as e:
                    logger.warning(f"Memory reflex gate error for {event_id}: {e}")

            self._reasoning_by_event[event_id] = accumulated_thoughts or None
            return await self._execute_function_call(
                event_id, function_call.name, function_call.args,
                response_parts=captured_parts,
                grounding_evidence=grounding_evidence or None,
            )

        if accumulated_thoughts:
            thoughts_turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="thoughts",
                thoughts=accumulated_thoughts,
            )
            await self._append_and_broadcast(event_id, thoughts_turn)

        if accumulated_text:
            response_turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="response",
                thoughts=accumulated_text,
                evidence=grounding_evidence if grounding_evidence else None,
                response_parts=captured_parts,
            )
            await self._append_and_broadcast(event_id, response_turn)
            await self._emit_executive_pulse(event_id, [("tool:brain_response", "tool")])
            self._last_processed[event_id] = time.time()
            if event.source in ("slack", "chat"):
                self._waiting_for_user[event_id] = time.time()
                self._idle_timeout.schedule(event_id)

        self._reasoning_by_event.pop(event_id, None)
        if accumulated_text or accumulated_thoughts:
            return False

        logger.warning(f"Brain LLM returned empty response for {event_id}")
        return False

    async def _process_intermediate(
        self, event_id: str, event: EventDocument, turns: list[ConversationTurn]
    ) -> None:
        """Evaluate intermediate turns during active agent dispatch via LLM.

        Processes ALL non-brain unseen turns: agent progress, user messages, aligner signals.
        Tools: reply_to_agent, message_agent, wait_for_agent (always available).
        Token limit: 256 (agent-only), 1024 (user or huddle present).
        Appends brain.thoughts turn for temporal context; marks processed turns EVALUATED.
        """
        self._reasoning_by_event.pop(event_id, None)
        if not self._adapter:
            logger.warning("_process_intermediate skipped: no LLM adapter")
            return

        from .llm import BRAIN_TOOL_SCHEMAS
        intermediate_tools = [
            t for t in BRAIN_TOOL_SCHEMAS
            if t["name"] in ("reply_to_agent", "message_agent", "wait_for_agent")
        ]
        huddle_turns = [t for t in turns if t.action == "huddle"]
        user_turns = [t for t in turns if t.actor == "user"]
        max_tokens = 1024 if (huddle_turns or user_turns) else 256

        ctx: ContextFlags = {
            "is_intermediate": True,
            "has_pending_huddle": bool(huddle_turns),
            "last_is_user": bool(user_turns),
            "turn_count": len(event.conversation),
            "has_agent_result": False,
            "is_waiting": False,
            "is_defer_wakeup": False,
            "has_related": False,
            "has_graph_edges": False,
            "has_recent_closed": False,
            "has_slack_participant": bool(
                getattr(event, "slack_thread_ts", None)
                and any(t.actor == "user" and t.source == "slack" for t in event.conversation)
            ),
            "source": event.source,
            "service": event.service or "",
        }
        active_phases = self._match_phases(event, ctx)
        system_prompt = await self._build_system_prompt(event, active_phases, ctx)
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
                    if not chunk.is_thought:
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
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="intermediate",
                thoughts=accumulated_text,
            )
            await self._append_and_broadcast(event_id, turn)
            logger.info(f"Appended turn {turn.turn} (brain.intermediate) to event {event_id}")

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

    @staticmethod
    async def _resolve_grounding_urls(chunks: list[dict]) -> list[dict]:
        """Follow redirect URLs from Vertex AI Search grounding and deduplicate."""
        REDIRECT_PREFIX = "vertexaisearch.cloud.google.com/grounding-api-redirect/"

        async def resolve_one(client: httpx.AsyncClient, chunk: dict) -> dict:
            uri = chunk.get("uri", "")
            if REDIRECT_PREFIX not in uri:
                return chunk
            try:
                resp = await client.head(uri)
                return {**chunk, "uri": str(resp.url)}
            except Exception:
                logger.debug(f"Grounding URL resolve failed for {chunk.get('title', '?')}")
                return {**chunk, "uri": ""}

        async with httpx.AsyncClient(follow_redirects=True, timeout=2.5) as client:
            resolved = await asyncio.gather(*(resolve_one(client, c) for c in chunks))

        seen: set[str] = set()
        deduped: list[dict] = []
        for c in resolved:
            key = c["uri"] or c.get("title", "")
            if key not in seen:
                seen.add(key)
                deduped.append(c)
        return deduped

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
        has_agent_result = any(t.actor not in ("brain", "user", "aligner", "headhunter") for t in recent)
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
            t.actor not in ("brain", "user", "aligner", "headhunter") for t in event.conversation
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
        if getattr(event, "subject_type", "service") not in ("kargo_stage", "system"):
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
            elif t.actor == "brain" and t.action in ("think", "thoughts", "intermediate", "response", "tool_result", "wait"):
                continue
            else:
                break
        flags["is_defer_wakeup"] = consecutive_defers > 0
        flags["consecutive_defers"] = consecutive_defers

        consecutive_waits = 0
        for t in reversed(event.conversation):
            if t.actor == "brain" and t.action == "wait" and t.waitingFor == "agent":
                consecutive_waits += 1
            elif t.actor == "brain" and t.action in ("think", "thoughts", "intermediate", "response", "tool_result"):
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
        """Determine active skill phases: system overrides, plumbing, Brain-declared."""
        active = ["always", "source"]
        if ctx["has_related"] or ctx["has_graph_edges"] or ctx["has_recent_closed"]:
            active.append("context")
        if ctx.get("has_slack_participant", False):
            active.append("multi-user")

        # System state overrides -- NOT Brain decisions, preempt Brain phase
        if ctx.get("is_intermediate", False):
            active.append("intermediate")
            if ctx.get("has_pending_huddle", False):
                active.append("coordination")
            return active

        if ctx.get("is_waiting", False):
            active.append("waiting")
            return active

        # Normal processing: Brain-declared phase
        brain_phase = event.brain_phase or "triage"

        # In-flight migration: events without brain_phase that have agent results
        # get verify-equivalent skills until the Brain calls set_phase (one-release bridge)
        if event.brain_phase is None and ctx.get("has_agent_result", False):
            logger.info(f"In-flight migration bridge: {event.id} has brain_phase=None with agent result, loading verify skills")
            for folder in BRAIN_PHASE_SKILLS.get("verify", []):
                if folder not in active:
                    active.append(folder)
        else:
            for folder in BRAIN_PHASE_SKILLS.get(brain_phase, []):
                if folder not in active:
                    active.append(folder)

        if ctx.get("has_pending_huddle", False):
            active.append("coordination")

        return active

    async def _build_system_prompt(
        self, event: EventDocument, active_phases: list[str],
        context_flags: dict | None = None,
    ) -> str:
        """Assemble system prompt from matching skill phases + dependency resolution."""
        if not self._skill_loader or not self._skill_loader.available_phases():
            return BRAIN_SYSTEM_PROMPT

        initial_paths: list[str] = []
        for phase in active_phases:
            if phase == "source":
                subject_type = getattr(event, "subject_type", "service") or "service"
                composite_file = f"source/{event.source}_{subject_type}.md"
                source_file = f"source/{event.source}.md"
                all_source_paths = self._skill_loader.get_all_paths_for_phase("source")
                if composite_file in all_source_paths:
                    initial_paths.append(composite_file)
                elif source_file in all_source_paths:
                    initial_paths.append(source_file)
                else:
                    logger.warning(f"No source skill for '{event.source}' (subject_type={subject_type})")
            else:
                initial_paths.extend(self._skill_loader.get_all_paths_for_phase(phase))

        template_vars = {"event.source": event.source, "event.service": event.service, "maintainer_emails": os.getenv("HEADHUNTER_MAINTAINERS", "")}
        resolved_pairs = self._skill_loader.resolve_dependencies_with_paths(
            initial_paths, template_vars=template_vars
        )
        resolved_contents = [
            _wrap_skill_section(path, body)
            for path, body in resolved_pairs
        ]

        # Live event state header -- first thing the LLM reads, before all skill instructions.
        resolved_contents.insert(0, self._build_event_state_header(event, context_flags))

        # Evidence-driven context: inject Kargo skills when kargo_context is present
        if (event.event and event.event.evidence
                and hasattr(event.event.evidence, "kargo_context")
                and event.event.evidence.kargo_context):
            for kpath in self._skill_loader.find_paths_by_tag("kargo"):
                result = self._skill_loader.get_with_meta(kpath)
                if result:
                    kbody, _ = result
                    resolved_contents.append(_wrap_skill_section(kpath, kbody))
                else:
                    logger.debug(f"Kargo tag '{kpath}' resolved to None in path_index")

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
                 if t.actor not in ("brain", "user", "aligner", "headhunter")),
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
                f"**DEFER WAKE-UP ({consecutive}x):** You deferred because: {last_reason}\n"
                f"{elapsed_str}\n"
                f"That was {consecutive} defer(s) ago. What changed since then?"
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

        lesson_block = self._format_recall_block(event)
        if lesson_block:
            resolved_contents.append(lesson_block)

        prompt = "\n\n---\n\n".join(resolved_contents)

        total_tokens = len(prompt) // 4
        phase_str = ", ".join(active_phases)
        logger.info(f"Brain skills: [{phase_str}] ({total_tokens} tokens) for {event.id}")

        return prompt

    def _format_recall_block(self, event: "EventDocument") -> str | None:
        """Format the RECALL system-instruction block from stored reflex lessons.

        Reads from _recall_lessons (populated by the reflex gate on previous cycle).
        Overwrite semantics: latest reflex hit replaces prior content.
        Persists across defer-wake (warm SI context). Cleared only in _close_and_broadcast.
        """
        lessons = self._recall_lessons.get(event.id)
        if not lessons:
            return None

        lines = ["## RECALL", "The following patterns were learned from past events similar to this one."]
        for lesson in lessons:
            p = lesson.get("payload", {})
            title = p.get("title", "untitled")
            lines.append(f"- {title}: {p.get('pattern', '')}")

        logger.debug(f"Brain RECALL: {len(lessons)} lessons in SI for {event.id}")
        return "\n".join(lines)

    async def _warmup_embedding(self) -> None:
        """Fire-and-forget: warm the Vertex AI embedding serving slot."""
        try:
            archivist = self.agents.get("_archivist_memory")
            if archivist and hasattr(archivist, "search_lessons"):
                await archivist.search_lessons("warmup", limit=1)
                logger.debug("Brain lessons: embedding model warmed up")
        except Exception:
            pass

    @staticmethod
    def _build_event_state_header(
        event: EventDocument, context_flags: dict | None = None,
    ) -> str:
        """Live event state compass -- injected at the top of the system prompt.

        Two-line header recomputed every LLM call:
        Line 1: Current state (domain, severity, phase, turn count, wall clock).
        Line 2: Evidence delta since last classification.
        """
        from ..models import EventEvidence

        now = datetime.now(timezone.utc)
        now_str = now.strftime("%H:%M UTC")
        turn_count = len(event.conversation)
        phase = event.brain_phase or "triage"

        evidence = event.event.evidence if event.event else None
        if isinstance(evidence, EventEvidence):
            domain = evidence.brain_domain or evidence.domain
            classified = evidence.brain_domain is not None
            severity = evidence.brain_severity or evidence.severity
        else:
            domain = "disorder"
            classified = False
            severity = "info"

        line1 = (
            f"## Event State\n"
            f"Cynefin: {domain.upper()} | Severity: {severity} "
            f"| Phase: {phase} | Turn: {turn_count} | Time: {now_str}"
        )

        if not classified:
            line2 = "Unclassified — call classify_event before routing."
        else:
            last_classify_idx = None
            for i in range(len(event.conversation) - 1, -1, -1):
                t = event.conversation[i]
                if t.actor == "brain" and t.action == "triage":
                    last_classify_idx = i
                    break

            tail = event.conversation[last_classify_idx + 1:] if last_classify_idx is not None else event.conversation
            has_agent_return = any(
                t.actor not in ("brain", "aligner", "headhunter") and t.action in ("plan", "execute")
                for t in tail
            )
            has_user_message = any(
                t.actor == "user" and t.action == "message"
                for t in tail
            )
            challenge = has_agent_return or has_user_message

            if last_classify_idx is None:
                line2 = "Classified (source-assessed)."
            else:
                turns_since = turn_count - (last_classify_idx + 1)
                line2 = f"Last classified: turn {last_classify_idx + 1} ({turns_since} turns ago)."

            if challenge:
                line2 += " Any new evidence to reclassify?"

        return f"{line1}\n{line2}"

    @staticmethod
    def _surface_agent_recommendation(event: EventDocument) -> str | None:
        """Extract and promote last agent's recommendation to system-level priority.
        Skips if a brain.defer already addressed it (prevents stale defer loops).
        """
        last_agent_turn = next(
            (t for t in reversed(event.conversation)
             if t.actor not in ("brain", "user", "aligner", "headhunter")),
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

        # QE gate: resolve early for both structured and legacy paths
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
        qe_gate = (
            "\n\n## QE VERIFICATION GATE (mandatory)\n"
            "The Developer completed work in implement mode. "
            "You MUST dispatch QE (mode: test) to verify before any PR, merge, or close action."
        ) if was_implement else ""

        # Structured path: reasoning from plan frontmatter (stored in taskForAgent)
        reasoning = None
        if last_agent_turn.taskForAgent:
            reasoning = last_agent_turn.taskForAgent.get("reasoning")

        if reasoning:
            logger.info(f"Agent reasoning promoted for {event.id} ({len(reasoning)} chars)")
            ts = datetime.fromtimestamp(last_agent_turn.timestamp, tz=timezone.utc).strftime("%H:%M:%S") if last_agent_turn.timestamp else "unknown"
            return (
                f"## ROOT CAUSE ANALYSIS (from {last_agent_turn.actor}, "
                f"turn {agent_idx + 1}/{len(event.conversation)}, at {ts})\n"
                f"{reasoning[:1200]}{qe_gate}"
            )

        # Legacy fallback: regex extraction from result body
        result_text = last_agent_turn.result or last_agent_turn.thoughts or ""
        rec = Brain._extract_recommendation(result_text)

        if was_implement:
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
        from .llm.prompt import build_event_header

        # -- Resolve async data for the event header --
        evidence = event.event.evidence
        subject_type = event.subject_type

        # Gate get_service: only for K8s deployment subjects
        svc = None
        if (subject_type == "service"
                and event.service not in ("general", "system")
                and not (isinstance(evidence, EventEvidence) and evidence.gitlab_context)):
            svc = await self.blackboard.get_service(event.service)

        mermaid = ""
        if event.source != "headhunter":
            if context_cache and "_cached_mermaid" in context_cache:
                mermaid = context_cache["_cached_mermaid"]
            else:
                try:
                    mermaid = await self.blackboard.generate_mermaid()
                except Exception as e:
                    logger.warning(f"Failed to generate mermaid for Brain prompt: {e}")

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

        if context_cache and "_cached_recent_closed" in context_cache:
            recent_closed = context_cache["_cached_recent_closed"]
        else:
            recent_closed = await self.blackboard.get_recent_closed_for_service(
                event.service, minutes=15
            )

        journal = await self._get_journal_cached(event.service)

        # -- Build source-aware header via pure function --
        header = build_event_header(
            event,
            service_meta=svc,
            journal_entries=journal if journal else None,
            related_events=related if related else None,
            recent_closed=recent_closed if recent_closed else None,
            mermaid=mermaid,
        )

        if not event.conversation:
            new_event_text = header + "\n\n(No turns yet -- this is a new event. Triage it.)\nWhat is the next action? Call one of your functions."
            return [{"role": "user", "parts": [{"text": new_event_text}]}]

        context_text = header

        # -- Build structured conversation messages --
        contents: list[dict] = [{"role": "user", "parts": [{"text": context_text}]}]

        for turn in event.conversation:
            role = "model" if turn.actor == "brain" else "user"
            # tool_result turns are function responses -- must be on user role
            # per Gemini multi-turn function calling protocol
            if turn.actor == "brain" and turn.action == "tool_result":
                role = "user"
            parts = self._turn_to_parts(turn)
            if not parts:
                continue  # Skip turns with no prompt content (e.g., brain.thoughts)

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
        if turn.actor == "brain" and turn.action in ("thoughts", "intermediate"):
            return []

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
            if turn.action == "think":
                text = f"[Internal observation — no tool was called, no message was sent]:\n{text}"
            if turn.evidence:
                text = f"{text}\n{turn.evidence}" if text else turn.evidence
        elif turn.actor == "user":
            if turn.user_name:
                text = f"[{turn.user_name} via {turn.source or 'dashboard'}]: {turn.thoughts or turn.result or ''}"
            else:
                text = turn.thoughts or ""
        elif turn.actor == "aligner" and turn.action != "evidence":
            text = turn.evidence or turn.thoughts or ""
        elif turn.actor == "jarvis" and turn.action == "evidence":
            text = turn.evidence or turn.thoughts or ""
        elif turn.actor == "jarvis" and turn.action == "message":
            text = (
                f"## JARVIS DIRECT MESSAGE\n\n"
                f"{turn.thoughts or turn.result or ''}\n\n"
                f"JARVIS asked you a question. Send your answer back to JARVIS before doing anything else."
            )
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

    async def _emit_executive_pulse(
        self, event_id: str, pulses_data: list[tuple[str, str]] | list[tuple[str, str, float]],
    ) -> None:
        """Emit executive hemisphere pulses (tool/phase/agent). Non-fatal.

        pulses_data items can be (neuron_id, neuron_type) -- defaults score to 1.0,
        or (neuron_id, neuron_type, score) for explicit outcome scoring:
          1.0 = success, 0.3 = completed with error, 0.0 = infra failure.
        """
        if not self.pulse_port:
            return
        try:
            from ..memory.pulse import Pulse, PulseBatch
            pulses = []
            for item in pulses_data:
                if len(item) == 3:
                    nid, ntype, score = item
                else:
                    nid, ntype = item
                    score = 1.0
                pulses.append(Pulse(nid, ntype, score, injected=score >= 0.5))
            ev = await self.blackboard.get_event(event_id)
            reasoning = self._reasoning_by_event.pop(event_id, None)
            batch = PulseBatch(
                event_id=event_id,
                pulses=pulses,
                turn=len(ev.conversation) if ev else 0,
                event_elapsed_s=int(time.time() - ev.conversation[0].timestamp) if ev and ev.conversation else 0,
                reasoning=reasoning,
                event_status=ev.status.value if ev else None,
            )
            if event_id in self._defer_wake_events:
                batch.is_defer_wake = True
                self._defer_wake_events.discard(event_id)
            await self.pulse_port.on_pulse_batch(batch)
        except Exception as e:
            logger.debug(f"Executive pulse emission failed (non-fatal): {e}")

    async def _get_jira_reporter(self, issue_key: str, jira_url: str, jira_email: str, jira_token: str) -> str:
        """Fetch the reporter accountId for a Jira issue. Returns empty string on failure."""
        try:
            import base64
            auth = base64.b64encode(f"{jira_email}:{jira_token}".encode()).decode()
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{jira_url}/rest/api/3/issue/{issue_key}",
                    headers={"Authorization": f"Basic {auth}"},
                    params={"fields": "reporter"},
                )
            if resp.status_code < 300:
                return resp.json().get("fields", {}).get("reporter", {}).get("accountId", "")
        except Exception as e:
            logger.debug(f"Failed to fetch reporter for {issue_key}: {e}")
        return ""

    async def _execute_function_call(
        self,
        event_id: str,
        function_name: str,
        args: dict,
        response_parts: list[dict] | None = None,
        grounding_evidence: str | None = None,
    ) -> bool:
        """
        Execute an LLM function call. Maps function names to real operations.
        
        Returns True if the caller should re-invoke the LLM immediately
        (e.g., after lookup_service). Returns False for all other cases.
        
        Agent dispatch uses asyncio.create_task for non-blocking execution.
        Other functions (close, approve, verify) are fast Redis writes.
        """
        if grounding_evidence:
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                waitingFor="google_search",
                evidence=grounding_evidence,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            response_parts = None

        # Emit tool pulse for every function call (except respond_to_jarvis —
        # that's a direct message TO JARVIS, not an observation FOR JARVIS)
        if function_name != "respond_to_jarvis":
            await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool")])

        if function_name in ("select_agent", "ask_agent_for_state"):
            agent_name = args.get("agent_name", "")
            task = args.get("task_instruction", "") or args.get("question", "")
            mode = args.get("mode", "")

            # Duplicate task prevention
            if event_id in self._active_tasks and not self._active_tasks[event_id].done():
                logger.info(f"Task already active for {event_id}, skipping dispatch")
                dup_turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="An agent is already actively working on this event. "
                             "Wait for their update before dispatching again.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, dup_turn)
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
            await self._emit_executive_pulse(event_id, [(f"agent:{agent_name}", "agent")])
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
                not_found_turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="That agent is not available in this environment. "
                             "Review which agents are available and which has "
                             "the right expertise for this task.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, not_found_turn)
                await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.3)])
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
                    await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.0)])
                    followup = ConversationTurn(
                        turn=(await self._next_turn_number(event_id)),
                        actor="brain",
                        action="tool_result",
                        thoughts="The message was not delivered. "
                                 "The agent may still be working -- check for recent updates "
                                 "from them before deciding next steps.",
                        response_parts=response_parts,
                    )
                    await self._append_and_broadcast(event_id, followup)
            else:
                logger.warning(f"reply_to_agent: agent {agent_id} not found or disconnected")
                await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.3)])
                followup = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="The message was not delivered. "
                             "The agent may still be working -- check for recent updates "
                             "from them before deciding next steps.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, followup)
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

            running_agent = self._active_agent_for_event.get(event_id)
            event_has_active_task = event_id in self._active_tasks and not self._active_tasks[event_id].done()

            if event_has_active_task and running_agent == agent_name:
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
                                "event_id": event_id,
                            })
                            logger.info(f"Brain message_agent -> {agent_name} (busy, inbox, event={event_id}) ({len(message)} chars)")
                        except Exception as e:
                            logger.warning(f"Failed to send message to {agent_name}: {e}")
                            await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.0)])
                            followup = ConversationTurn(
                                turn=(await self._next_turn_number(event_id)),
                                actor="brain",
                                action="tool_result",
                                thoughts="The message was not delivered. "
                                         "The agent may still be working -- check for recent updates "
                                         "from them before deciding next steps.",
                                response_parts=response_parts,
                            )
                            await self._append_and_broadcast(event_id, followup)
                return False

            agent_conn = await registry.get_available(agent_name) if registry else None

            if agent_conn:
                agent = self.agents.get(agent_name)
                if agent or (self._ws_mode == "reverse" and agent_name not in ("_aligner", "_archivist_memory")):
                    event_md_path = f"./events/event-{event_id}.md"
                    task_coro = self._run_agent_task(
                        event_id, agent_name, agent, message, event_md_path,
                        routing_turn_num=turn.turn, mode="message",
                        parallel=event_has_active_task,
                    )
                    task = asyncio.create_task(task_coro)
                    if not event_has_active_task:
                        self._active_tasks[event_id] = task
                    label = "parallel" if event_has_active_task else "idle, dispatch"
                    logger.info(f"Brain message_agent -> {agent_name} ({label}) ({len(message)} chars)")
                else:
                    logger.warning(f"message_agent: no agent class for role {agent_name}")
                    await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.3)])
            else:
                if registry:
                    busy_conn = await registry.get_by_role(agent_name)
                    if busy_conn and busy_conn.ws:
                        try:
                            await busy_conn.ws.send_json({
                                "type": "proactive_message",
                                "from": "brain",
                                "content": message,
                                "event_id": event_id,
                            })
                            logger.info(f"Brain message_agent -> {agent_name} (busy fallback, inbox, event={event_id}) ({len(message)} chars)")
                        except Exception as e:
                            logger.warning(f"Failed to send message to {agent_name}: {e}")
                            await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.0)])
                            followup = ConversationTurn(
                                turn=(await self._next_turn_number(event_id)),
                                actor="brain",
                                action="tool_result",
                                thoughts="The message was not delivered. "
                                         "The agent may still be working -- check for recent updates "
                                         "from them before deciding next steps.",
                                response_parts=response_parts,
                            )
                            await self._append_and_broadcast(event_id, followup)
                    else:
                        logger.warning(f"message_agent: no WS connection for {agent_name}, message dropped")
                        await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.3)])
                        followup = ConversationTurn(
                            turn=(await self._next_turn_number(event_id)),
                            actor="brain",
                            action="tool_result",
                            thoughts="The message was not delivered. "
                                     "The agent may still be working -- check for recent updates "
                                     "from them before deciding next steps.",
                            response_parts=response_parts,
                        )
                        await self._append_and_broadcast(event_id, followup)
            return False

        elif function_name == "record_observation":
            name = args.get("name", "")
            value = args.get("value", 0)
            unit = args.get("unit", "")
            result = await self.blackboard.record_observation(event_id, name, value, unit)
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                thoughts=(
                    f"Recorded observation '{name}' = {value}"
                    f"{(' ' + unit) if unit else ''}"
                    f" (point #{result['count']}, event age {result['event_age_minutes']}m)"
                ),
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "list_observations":
            result = await self.blackboard.list_observations()
            if not result["observations"]:
                summary_text = "No observations recorded yet."
            else:
                lines = [f"{len(result['observations'])} observation series (global, last 7 days):"]
                for s in result["observations"]:
                    events_in_series = {p.get("event_id", "") for p in s["points"] if p.get("event_id")}
                    lines.append(
                        f"  • {s['name']}: {s['count']} pts, "
                        f"range [{s['min']}–{s['max']}] {s['unit']}, "
                        f"latest={s['latest_value']}, trend={s['trend']}, "
                        f"span={s['span_minutes']}m, "
                        f"events={len(events_in_series)}"
                    )
                summary_text = "\n".join(lines)
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                thoughts=summary_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "close_event":
            summary = args.get("summary", "Event closed.")
            await self._close_and_broadcast(event_id, summary)
            return False

        elif function_name == "request_user_approval":
            plan_summary = args.get("plan_summary", "")
            self._waiting_for_user[event_id] = time.time()  # Block re-processing until user responds
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="request_approval",
                thoughts=plan_summary,
                pendingApproval=True,
                waitingFor="user",
            )
            await self._append_and_broadcast(event_id, turn)
            await self.blackboard.park_for_approval(event_id)
            event = await self.blackboard.get_event(event_id)
            if event and event.source in ("slack", "chat"):
                self._idle_timeout.schedule(event_id)
            return False

        elif function_name == "re_trigger_aligner":
            service = args.get("service", "")
            condition = args.get("check_condition", "")
            aligner = self.agents.get("_aligner")
            if not aligner or not service:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="Service health data is not available for this event. "
                             "Consider checking the ops journal for recent entries, "
                             "or dispatching an agent to investigate directly.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return False
            try:
                state = await aligner.check_state(service)
            except Exception as e:
                logger.warning(f"re_trigger_aligner check_state failed for {service}: {e}")
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="Service health check failed. "
                             "Consider deferring briefly and retrying, "
                             "or dispatching an agent to investigate directly.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return False
            verify_turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="verify",
                thoughts=f"Re-triggering Aligner to check: {condition}",
                evidence=f"target_service:{service}",
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
            else:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="Verification data is not available for this service right now. "
                             "Consider what other tools or participants in the conversation "
                             "might confirm whether the situation has changed since the last check.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "defer_event":
            # Guard: never defer when waiting for user response
            if event_id in self._waiting_for_user:
                logger.warning(f"Ignoring defer_event for {event_id}: waiting for user response")
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="This event is currently waiting for user input and "
                             "cannot be deferred until the user responds.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return False
            # Defer supersedes any active wait -- FRIDAY chose to wait on a timer,
            # not on a participant. Clear wait states to prevent post-reactivation deadlock.
            self._waiting_for_agent.pop(event_id, None)
            reason = args.get("reason", "Deferred by Brain")
            delay = max(30, min(int(args.get("delay_seconds", 60)), 3600))  # Clamp 30s-60min
            defer_started_at = time.time()
            defer_until = defer_started_at + delay
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
                # Defense-in-depth: turn broadcast (line ~2060) carries the conversation
                # update; this broadcast carries the status field change so the UI can
                # move the event to the deferred list immediately.
                await self._broadcast({
                    "type": "event_status_changed",
                    "event_id": event_id,
                    "status": EventStatus.DEFERRED.value,
                    "defer_until": defer_until,
                    "defer_started_at": defer_started_at,
                })
            await self.blackboard.record_event(
                EventType.BRAIN_EVENT_DEFERRED,
                {"event_id": event_id, "delay_seconds": delay},
                narrative=f"Event {event_id} deferred for {delay}s: {reason[:80]}",
            )
            logger.info(f"Event {event_id} deferred for {delay}s: {reason}")
            return False

        elif function_name == "wait_for_user":
            # Hard guard: wait_for_user is only for chat/slack events
            event = await self.blackboard.get_event(event_id)
            if event and event.source not in ("chat", "slack"):
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="wait_for_user is not available for automated events. "
                             "Use request_user_approval to pause for human authorization, "
                             "or defer_event to wait for external processes.",
                )
                await self._append_and_broadcast(event_id, turn)
                return False
            summary = args.get("summary", "")
            self._waiting_for_user[event_id] = time.time()  # State flag (plumbing)
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="wait",
                thoughts=summary,
                waitingFor="user",
            )
            await self._append_and_broadcast(event_id, turn)
            event = await self.blackboard.get_event(event_id)
            if event and event.source in ("slack", "chat"):
                self._idle_timeout.schedule(event_id)
            return False

        elif function_name == "wait_for_agent":
            # GUARD: reject if no agent is actively running for this event
            if event_id not in self._active_agent_for_event:
                logger.info(
                    "wait_for_agent rejected: no active agent for %s", event_id
                )
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts=(
                        "No agent is currently running for this event. "
                        "The agent already delivered results above. To continue: "
                        "(1) dispatch another agent with select_agent, or "
                        "(2) defer the event with defer_event to wait for an "
                        "external process."
                    ),
                    waitingFor="wait_for_agent",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return False
            summary = args.get("summary", "")
            agent_name = self._active_agent_for_event.get(event_id, "unknown")
            self._waiting_for_agent[event_id] = agent_name
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="wait",
                thoughts=summary,
                waitingFor="agent",
            )
            await self._append_and_broadcast(event_id, turn)
            return False

        elif function_name == "wait_for_jarvis":
            if event_id in self._waiting_for_jarvis:
                return False  # Already waiting -- exit loop, nudge timer handles it
            context = args.get("context", "")
            event = await self.blackboard.get_event(event_id)
            if not event:
                return False
            # Pre-check: find last respond_jarvis turn timestamp, look for jarvis reply after it
            last_respond_ts = 0.0
            for t in reversed(event.conversation):
                if t.actor == "brain" and t.action == "respond_jarvis":
                    last_respond_ts = t.timestamp or 0.0
                    break
            if last_respond_ts:
                existing_reply = next(
                    (t for t in event.conversation
                     if t.actor == "jarvis" and t.action == "message"
                     and (t.timestamp or 0.0) > last_respond_ts),
                    None,
                )
                if existing_reply:
                    result_text = "JARVIS already replied. Check his message above."
                    turn = ConversationTurn(
                        turn=(await self._next_turn_number(event_id)),
                        actor="brain", action="tool_result",
                        waitingFor="wait_for_jarvis",
                        thoughts=result_text,
                        response_parts=response_parts,
                    )
                    await self._append_and_broadcast(event_id, turn)
                    return True
            # Record wait state
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="wait",
                thoughts=f"Waiting for JARVIS response: {context}",
                waitingFor="jarvis",
            )
            await self._append_and_broadcast(event_id, turn)
            self._waiting_for_jarvis[event_id] = last_respond_ts or time.time()
            self._jarvis_wait_count[event_id] = self._jarvis_wait_count.get(event_id, 0) + 1
            self._last_processed[event_id] = time.time()
            max_nudges = max(0, 3 - self._jarvis_wait_count[event_id])
            task = asyncio.create_task(self._jarvis_nudge_loop(event_id, max_nudges))
            self._jarvis_wait_tasks[event_id] = task
            return False

        elif function_name == "lookup_service":
            service_name = args.get("service_name", "")

            # Guard: non-K8s subjects get actionable N/A instead of "Not found" noise
            event_doc = await self.blackboard.get_event(event_id)
            subject_type = getattr(event_doc, "subject_type", "service") if event_doc else "service"
            if subject_type != "service":
                context_label = {
                    "kargo_stage": "kargo_context",
                    "jira": "jira_context",
                    "system": "system-level context",
                }.get(subject_type, subject_type)
                result_text = (
                    f"## lookup_service: Not applicable\n\n"
                    f"This event's subject is a {subject_type}, not a monitored K8s deployment.\n"
                    f"The relevant context ({context_label}) is already in your prompt."
                )
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    waitingFor="lookup_service",
                    evidence=result_text,
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return False

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
            return True

        elif function_name == "consult_deep_memory":
            # Guard: max 1 deep memory call per event (prevent LLM re-query loop)
            ev = await self.blackboard.get_event(event_id)
            already_consulted = any(
                t.action in ("think", "thoughts", "intermediate", "response", "tool_result") and t.evidence and "Deep memory" in (t.evidence or "")
                for t in (ev.conversation if ev else [])
            )
            if already_consulted:
                logger.info(f"Deep memory already consulted for {event_id} -- returning cached results")
                cached_evidence = next(
                    (t.evidence for t in (ev.conversation if ev else [])
                     if t.action in ("think", "thoughts", "intermediate", "response", "tool_result") and t.evidence and "Deep memory" in t.evidence),
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
                if "No historical patterns" in cached_evidence or "No results" in cached_evidence:
                    return False
                return True

            query = args.get("query", "")
            archivist = self.agents.get("_archivist_memory")
            memory_text = f"## Deep Memory: \"{query}\"\n\n"
            has_results = False

            from ..memory.pulse import PulseContext
            ev_for_ctx = ev or await self.blackboard.get_event(event_id)
            pulse_ctx = PulseContext(
                event_id=event_id,
                turn=len(ev_for_ctx.conversation) if ev_for_ctx else 0,
                event_elapsed_s=int(time.time() - ev_for_ctx.conversation[0].timestamp) if ev_for_ctx and ev_for_ctx.conversation else 0,
            )

            # Search lessons learned first (classification guidance)
            if archivist and hasattr(archivist, "search_lessons"):
                try:
                    lessons = await archivist.search_lessons(query, limit=3, context=pulse_ctx)
                except Exception as e:
                    logger.warning(f"Deep memory lesson search failed: {e}")
                    lessons = None
                if lessons:
                    has_results = True
                    memory_text += "### Lessons Learned\n"
                    for i, r in enumerate(lessons, 1):
                        p = r.get("payload", {})
                        memory_text += (
                            f"{i}. **{p.get('title', '?')}** (score: {r.get('score', 0):.2f})\n"
                            f"   - Pattern: {p.get('pattern', '?')}\n"
                        )
                        if p.get("anti_pattern"):
                            memory_text += f"   - Anti-pattern: {p['anti_pattern']}\n"
                    memory_text += "\n"

            # Search past events (pattern first, temporal data preserved)
            if archivist and hasattr(archivist, "search"):
                try:
                    results = await archivist.search(query, limit=5, context=pulse_ctx)
                except Exception as e:
                    logger.warning(f"Deep memory event search failed: {e}")
                    results = None
                if results:
                    has_results = True
                    memory_text += "### Past Events\n"
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
                        corrected = " [CORRECTED]" if p.get("corrected") else ""
                        memory_text += (
                            f"{i}. domain: {domain_str} | score: {r.get('score', 0):.2f}{corrected}\n"
                            f"   - Pattern: {p.get('symptom', '?')}\n"
                            f"   - Root cause: {p.get('root_cause', '?')}\n"
                            f"   - Fix: {p.get('fix_action', '?')}\n"
                            f"   - Service: {p.get('service', '?')} | Duration: {dur_m}, defers: {defer_m}, timings: [{timing_str}], outcome: {p.get('outcome', '?')}\n"
                        )

            if not has_results:
                memory_text = (
                    f"## Deep Memory: \"{query}\"\n\n"
                    f"No historical patterns match this query. "
                    f"Consider whether the event classification is accurate, "
                    f"or try searching with different keywords that describe the symptom or root cause. "
                    f"The ops journal for this service may also have relevant entries."
                )

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
                await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.3)])
            elif not user_email or not message:
                result_text = "Missing user_email or message parameter."
                await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.3)])
            else:
                try:
                    event_doc = await self.blackboard.get_event(event_id)
                    slack_user_id = await self._resolve_slack_user(
                        slack_channel, user_email, event_doc,
                    )
                    if not slack_user_id:
                        result_text = f"Could not resolve Slack user for '{user_email}'. No valid maintainer found."
                        turn = ConversationTurn(
                            turn=(await self._next_turn_number(event_id)),
                            actor="brain", action="notify",
                            thoughts=result_text, response_parts=response_parts,
                        )
                        await self._append_and_broadcast(event_id, turn)
                        await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.0)])
                        return True
                    dm = await slack_channel._app.client.conversations_open(users=slack_user_id)
                    dm_channel = dm["channel"]["id"]
                    is_bidirectional = (
                        event_doc
                        and not event_doc.slack_thread_ts
                        and event_doc.source != "chat"
                    )
                    dashboard_url = os.environ.get("DARWIN_DASHBOARD_URL", "")
                    event_link = f"\n<{dashboard_url}/events/{event_id}|View in Darwin Dashboard>" if dashboard_url else ""
                    full_dm_text = (
                        f":bell: *Darwin Notification*\n\n"
                        f"{message}{event_link}\n\n"
                        f"_Reply in this thread to follow up on this event._\n\n"
                        f"_AI-generated by Darwin Brain. Review for accuracy before acting._"
                    )

                    logger.info(f"notify_user_slack: user={slack_user_id} dm_channel={dm_channel} event={event_id} bidirectional={is_bidirectional}")

                    if is_bidirectional:
                        event_context = f"*Event:* {event_doc.event.reason[:200]}\n\n"
                        bidir_text = f":bell: *Darwin Notification*\n\n{event_context}{message}{event_link}\n\n_Reply in this thread to follow up on this event._\n\n_AI-generated by Darwin Brain. Review for accuracy before acting._"
                        result = await slack_channel._app.client.chat_postMessage(channel=dm_channel, text=bidir_text)
                        msg_ts = result["ts"]
                        await self.blackboard.set_slack_mapping(dm_channel, msg_ts, event_id)
                        await self.blackboard.update_event_slack_context(
                            event_id, dm_channel, msg_ts, slack_user_id,
                        )
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

                    elif slack_channel._infra_channel:
                        if not event_doc.slack_thread_ts:
                            await slack_channel.open_infra_thread(event_doc, event_doc.event.reason)
                            event_doc = await self.blackboard.get_event(event_id)

                        dm_text = full_dm_text
                        if event_doc and event_doc.slack_thread_ts:
                            try:
                                await slack_channel._app.client.chat_postMessage(
                                    channel=event_doc.slack_channel_id,
                                    thread_ts=event_doc.slack_thread_ts,
                                    text=f":bell: *Notification for <@{slack_user_id}>*\n\n{message}",
                                )
                                workspace = os.environ.get("SLACK_WORKSPACE_DOMAIN", "app.slack.com/client")
                                ts_nodot = event_doc.slack_thread_ts.replace(".", "")
                                thread_link = f"https://{workspace}/archives/{event_doc.slack_channel_id}/p{ts_nodot}"
                                dm_text = (
                                    f":bell: *Darwin Notification*\n\n"
                                    f"{message[:500]}\n\n"
                                    f":point_right: <{thread_link}|Continue in #darwin-infra>\n\n"
                                    f"_Reply here or in the thread above to interact with this event._\n\n"
                                    f"_AI-generated by Darwin Brain. Review for accuracy before acting._"
                                )
                                logger.info(f"notify_user_slack: posted to infra thread {event_doc.slack_channel_id}/{event_doc.slack_thread_ts}")
                            except Exception as e:
                                logger.warning(f"Infra thread notification failed for {event_id}, DM-only fallback: {e}")

                        dm_result = await slack_channel._app.client.chat_postMessage(channel=dm_channel, text=dm_text)
                        await self.blackboard.set_slack_mapping(dm_channel, dm_result["ts"], event_id)
                        result_text = f"Notification sent to {user_email} (infra thread + DM pointer)." if dm_text != full_dm_text else f"Slack DM sent to {user_email}. They can reply in the thread to follow up."
                        logger.info(f"notify_user_slack: DM sent to {user_email} for {event_id}")

                    else:
                        dm_result = await slack_channel._app.client.chat_postMessage(channel=dm_channel, text=full_dm_text)
                        await self.blackboard.set_slack_mapping(dm_channel, dm_result["ts"], event_id)
                        logger.info(f"Slack notification sent to {user_email} for event {event_id} (DM-only, no infra channel)")
                        result_text = f"Slack DM sent to {user_email}. They can reply in the thread to follow up."
                except Exception as e:
                    result_text = f"Failed to send Slack DM to {user_email}: {e}"
                    logger.warning(f"Slack notification failed for {user_email}: {e}")
                    await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.0)])

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
                await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.3)])
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

        elif function_name == "fetch_jira_issue":
            issue_key = args.get("issue_key", "")
            jira_url = os.getenv("JIRA_URL", "")
            jira_email = os.getenv("JIRA_EMAIL", "")
            jira_token = os.getenv("JIRA_API_TOKEN", "")
            if not jira_url or not jira_token:
                result_text = "Jira not configured (JIRA_URL or JIRA_API_TOKEN missing). Proceeding without Jira context."
            else:
                try:
                    import base64
                    auth = base64.b64encode(f"{jira_email}:{jira_token}".encode()).decode()
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.get(
                            f"{jira_url}/rest/api/3/issue/{issue_key}",
                            headers={"Authorization": f"Basic {auth}"},
                            params={"fields": "summary,description,status,comment,issuelinks,subtasks,labels,fixVersions"},
                        )
                    if resp.status_code == 404:
                        result_text = f"Jira issue {issue_key} not found."
                    elif resp.status_code == 429:
                        result_text = "Jira rate limited. Proceeding without additional context."
                    elif resp.status_code >= 400:
                        result_text = f"Jira fetch failed ({resp.status_code}). Proceeding without context."
                    else:
                        from .headhunter_jira import format_jira_for_llm
                        result_text = format_jira_for_llm(resp.json())
                except Exception as e:
                    result_text = f"Jira fetch error: {e}. Proceeding without context."
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                waitingFor="jira",
                thoughts=result_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "comment_jira_issue":
            issue_key = args.get("issue_key", "")
            comment_text = args.get("comment", "")
            mention_reporter = args.get("mention_reporter", False)
            jira_url = os.getenv("JIRA_URL", "")
            jira_email = os.getenv("JIRA_EMAIL", "")
            jira_token = os.getenv("JIRA_API_TOKEN", "")
            if not jira_url or not jira_token:
                result_text = "Cannot comment on Jira: not configured."
            else:
                try:
                    import base64
                    from marklassian import markdown_to_adf
                    auth = base64.b64encode(f"{jira_email}:{jira_token}".encode()).decode()
                    adf_doc = markdown_to_adf(comment_text)
                    if mention_reporter:
                        reporter_id = await self._get_jira_reporter(issue_key, jira_url, jira_email, jira_token)
                        if reporter_id:
                            mention_node = {"type": "paragraph", "content": [
                                {"type": "mention", "attrs": {"id": reporter_id, "text": "@reporter", "accessLevel": ""}},
                                {"type": "text", "text": " "},
                            ]}
                            adf_doc["content"].insert(0, mention_node)
                    adf_body = {"body": adf_doc}
                    async with httpx.AsyncClient(timeout=15) as client:
                        resp = await client.post(
                            f"{jira_url}/rest/api/3/issue/{issue_key}/comment",
                            headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                            json=adf_body,
                        )
                    if resp.status_code < 300:
                        result_text = f"Comment posted to {issue_key}. Jira communication complete -- proceed with next action."
                    else:
                        result_text = f"Failed to comment on {issue_key}: {resp.status_code}"
                except Exception as e:
                    result_text = f"Jira comment error: {e}"
            logger.info(f"comment_jira_issue: event={event_id} issue={issue_key} result={result_text[:100]}")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                waitingFor="jira",
                thoughts=result_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "transition_jira_issue":
            issue_key = args.get("issue_key", "")
            target_status = args.get("target_status", "")
            jira_url = os.getenv("JIRA_URL", "")
            jira_email = os.getenv("JIRA_EMAIL", "")
            jira_token = os.getenv("JIRA_API_TOKEN", "")
            if not jira_url or not jira_token:
                result_text = "Cannot transition Jira issue: not configured."
            else:
                try:
                    import base64
                    auth = base64.b64encode(f"{jira_email}:{jira_token}".encode()).decode()
                    headers = {"Authorization": f"Basic {auth}", "Content-Type": "application/json"}
                    async with httpx.AsyncClient(timeout=15) as client:
                        tr_resp = await client.get(
                            f"{jira_url}/rest/api/3/issue/{issue_key}/transitions",
                            headers=headers,
                        )
                    if tr_resp.status_code >= 400:
                        result_text = f"Failed to get transitions for {issue_key}: {tr_resp.status_code}"
                    else:
                        transitions = tr_resp.json().get("transitions", [])
                        match = next(
                            (t for t in transitions if t["name"].lower() == target_status.lower()),
                            None,
                        )
                        if not match:
                            available = [t["name"] for t in transitions]
                            result_text = f"Transition '{target_status}' not available for {issue_key}. Available: {available}"
                        else:
                            async with httpx.AsyncClient(timeout=15) as client:
                                post_resp = await client.post(
                                    f"{jira_url}/rest/api/3/issue/{issue_key}/transitions",
                                    headers=headers,
                                    json={"transition": {"id": match["id"]}},
                                )
                            if post_resp.status_code < 300:
                                result_text = f"{issue_key} transitioned to '{target_status}'. Jira status updated -- proceed with next action."
                            else:
                                result_text = f"Transition failed for {issue_key}: {post_resp.status_code}"
                except Exception as e:
                    result_text = f"Jira transition error: {e}"
            logger.info(f"transition_jira_issue: event={event_id} issue={issue_key} target={target_status} result={result_text[:100]}")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                waitingFor="jira",
                thoughts=result_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "report_incident":
            event_doc = await self.blackboard.get_event(event_id)
            if not event_doc:
                result_text = f"Event {event_id} not found. Cannot create incident."
                await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.3)])
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
            prior_incident = any(
                t.actor == "brain" and t.action == "notify"
                and ("Incident created" in (t.thoughts or "") or "Escalation staged [nightwatcher]" in (t.thoughts or ""))
                for t in (event_doc.conversation or [])
            )
            if prior_incident:
                self._incident_created.add(event_id)
                result_text = f"Incident already created for event {event_id} (recovered from conversation history). Skipping duplicate."
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain", action="notify", thoughts=result_text, response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            automated_sources = ("headhunter", "timekeeper", "aligner")
            if event_doc.source not in automated_sources:
                result_text = (
                    f"report_incident is only available for automated events "
                    f"(source={event_doc.source} is not eligible)."
                )
            elif os.environ.get("NIGHTWATCHER_ENABLED", "false").lower() == "true":
                from ..models import StagedEscalation
                conv_turns = [
                    t for t in (event_doc.conversation or [])
                    if t.actor != "user" and t.action != "phase"
                ]
                summary_parts = [
                    f"[{t.actor}.{t.action}] {(t.thoughts or '')[:150]}"
                    for t in conv_turns[-3:]
                ]
                conversation_summary = " | ".join(summary_parts)[:500]
                slack_thread_url = ""
                if event_doc.slack_thread_ts and event_doc.slack_channel_id:
                    ts_nodot = event_doc.slack_thread_ts.replace(".", "")
                    workspace = os.environ.get("SLACK_WORKSPACE_DOMAIN", "app.slack.com/client")
                    slack_thread_url = f"https://{workspace}/archives/{event_doc.slack_channel_id}/p{ts_nodot}"
                evidence = event_doc.event.evidence
                staged = StagedEscalation(
                    event_id=event_id,
                    service=event_doc.service,
                    source=event_doc.source,
                    reason=event_doc.event.reason,
                    summary=args.get("summary", "")[:200],
                    platform=args.get("platform", ""),
                    priority=args.get("priority", "Normal"),
                    description=args.get("description", ""),
                    evidence_snapshot=evidence.model_dump() if hasattr(evidence, "model_dump") else {},
                    conversation_summary=conversation_summary,
                    slack_thread_url=slack_thread_url,
                )
                try:
                    await self.blackboard.stage_escalation(staged)
                    self._incident_created.add(event_id)
                    result_text = (
                        f"Escalation staged [nightwatcher] for consolidation "
                        f"(event {event_id}, service {event_doc.service})"
                    )
                except Exception as e:
                    result_text = f"Failed to stage escalation: {e}"
                    logger.warning(f"stage_escalation failed for {event_id}: {e}")
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
                        "Issue Type": os.environ.get("SMARTSHEET_INCIDENT_ISSUE_TYPE", "Task"),
                        "Labels": os.environ.get("SMARTSHEET_INCIDENT_LABELS", ""),
                        "Components": os.environ.get("SMARTSHEET_INCIDENT_COMPONENTS", ""),
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
                        verify_preceded = any(
                            t.actor == "brain" and t.action == "phase"
                            and (t.thoughts or "").startswith("Phase: VERIFY")
                            for t in event_doc.conversation
                        )
                        logger.info(f"Incident created for {event_id}: verify_preceded={verify_preceded}")
                        result_text = (
                            f"Incident created in Smartsheet (row {result['row_id']}). "
                            f"Sheet: {result['sheet_url']}"
                        )
                    except Exception as e:
                        result_text = f"Failed to create incident: {e}"
                        logger.warning(f"report_incident failed for {event_id}: {e}")
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
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="Plan creation needs at least one step with an assigned participant and objective. "
                             "Review the conversation to identify which agents should act and on what.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
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
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="Event data is temporarily unavailable. "
                             "Wait for the next update from the conversation.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return False
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
                    evidence="## Plan Progress\n\nNo plan has been created for this event yet. "
                             "If a plan is needed, create one first with the appropriate agents and steps.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return False
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

        elif function_name == "set_phase":
            phase = args.get("phase", "triage")
            reasoning = args.get("reasoning", "")
            event_doc = await self.blackboard.get_event(event_id)
            current_phase = event_doc.brain_phase if event_doc else None
            if current_phase is not None and phase == current_phase:
                logger.debug(f"set_phase: confirmed {phase} for {event_id}")
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="phase",
                    thoughts=f"Phase: {phase.upper()} (confirmed). {reasoning}",
                    response_parts=response_parts,
                    timestamp=time.time(),
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            await self.blackboard.update_event_phase(event_id, phase)
            thoughts = f"Phase: {phase.upper()}. {reasoning}"
            logger.info(f"Phase transition: {current_phase} -> {phase} for {event_id} ({reasoning})")
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="phase",
                thoughts=thoughts,
                response_parts=response_parts,
                timestamp=time.time(),
            )
            await self._append_and_broadcast(event_id, turn)
            await self._broadcast({
                "type": "phase_updated",
                "event_id": event_id,
                "phase": phase,
            })
            await self._emit_executive_pulse(event_id, [(f"phase:{phase}", "phase")])
            return True

        elif function_name == "refresh_gitlab_context":
            condition = args.get("check_condition", "")
            headhunter = self.agents.get("_headhunter")
            if not headhunter:
                result_text = "Headhunter not available (GITLAB_HOST not configured). Use select_agent to check MR state manually."
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain", action="tool_result",
                    waitingFor="refresh_gitlab_context",
                    evidence=result_text,
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
            evidence = f"Checking: {condition}\n{result_text}" if condition else result_text
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_gitlab_context",
                evidence=evidence,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "refresh_kargo_context":
            condition = args.get("check_condition", "")
            kargo_observer = self.agents.get("_kargo_observer")
            if not kargo_observer:
                result_text = (
                    "Promotion pipeline status is not available in this environment. "
                    "Consider checking the ops journal for this service, "
                    "or dispatching an agent who has pipeline access."
                )
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain", action="tool_result",
                    waitingFor="refresh_kargo_context",
                    evidence=result_text,
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
                    actor="brain", action="tool_result",
                    waitingFor="refresh_kargo_context",
                    evidence=result_text,
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
                new_mr_url = state.get("mr_url", "")
                old_mr_url = kc.get("mr_url", "")
                if new_mr_url and new_mr_url != old_mr_url:
                    await self.blackboard.update_event_kargo_context(
                        event_id, {"mr_url": new_mr_url}
                    )
                    logger.info(f"Updated kargo_context.mr_url for {event_id}: {new_mr_url}")
                result_text = (
                    f"Kargo Stage: {stage}@{project}\n"
                    f"Promotion: {state.get('promotion', '?')}\n"
                    f"Phase: {state.get('phase', '?')}\n"
                    f"Failed Step: {state.get('failed_step', 'N/A')}\n"
                    f"Message: {state.get('message', '')}\n"
                    f"MR URL: {new_mr_url or 'N/A'}"
                )
            evidence = f"Checking: {condition}\n{result_text}" if condition else result_text
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain", action="tool_result",
                waitingFor="refresh_kargo_context",
                evidence=evidence,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "respond_to_jarvis":
            response_text = args.get("response", "").strip()
            if len(response_text) < 20:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="Response was too brief. JARVIS needs to understand your reasoning. "
                             "Include what you observed, whether you agree or disagree, "
                             "and what your next action will be.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                await self._emit_executive_pulse(event_id, [(f"tool:{function_name}", "tool", 0.3)])
                return True
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="respond_jarvis",
                thoughts=response_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            if self._live_adapter:
                try:
                    await self._live_adapter.receive_brain_response(event_id, response_text)
                except Exception as e:
                    logger.warning(f"Failed to deliver response to JARVIS for {event_id}: {e}")
            logger.info(f"Responded to JARVIS for {event_id}")
            return True

        elif function_name == "inspect_event":
            target_id = args.get("event_id", "").strip()
            if not target_id:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="Error: event_id is required.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            target_event = await self.blackboard.get_event(target_id)
            if not target_event:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts=f"Event {target_id} not found in active storage.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            age_seconds = time.time() - (target_event.queued_at or target_event.processing_started_at or time.time())
            age_h = int(age_seconds // 3600)
            age_m = int((age_seconds % 3600) // 60)
            age_str = f"{age_h}h {age_m}m"
            header = (
                f"## Event: {target_id}\n"
                f"Phase: {target_event.brain_phase or 'triage'} | "
                f"Status: {target_event.status.value if target_event.status else 'unknown'} | "
                f"Age: {age_str}\n"
                f"Source: {target_event.source or 'unknown'} | "
                f"Service: {target_event.service or '?'}\n"
            )
            evidence = target_event.event.evidence if target_event.event else None
            if evidence and hasattr(evidence, 'display_text') and evidence.display_text:
                header += f"\n## Original Request\n{evidence.display_text}\n"
            my_turns = [t for t in target_event.conversation if t.actor == "brain"]
            lines = [f"\n## My Actions ({len(my_turns)} turns)"]
            for t in my_turns:
                content = t.thoughts or t.result or ""
                lines.append(f"[{t.action}] {content}")
            result_text = header + "\n".join(lines)
            result_text = result_text[:15000]
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                thoughts=result_text,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            return True

        elif function_name == "post_sticky_note":
            target_id = args.get("event_id", "").strip()
            content = args.get("content", "").strip()
            if not target_id or not content:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="Error: event_id and content are required.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            target_event = await self.blackboard.get_event(target_id)
            if not target_event:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts=f"Event {target_id} not found — cannot post note.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            notes = list(getattr(target_event, "sticky_notes", None) or [])
            notes.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "content": content,
                "read": False,
            })
            new_unread = (getattr(target_event, "unread_notes", 0) or 0) + 1
            await self.blackboard.update_event_sticky_notes(target_id, notes, new_unread)
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                waitingFor="post_sticky_note",
                thoughts=f"Sticky note sent to {target_id}.",
                result=f"Sticky note sent to {target_id} -- proceed with next action.",
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            logger.info(f"Sticky note posted from {event_id} to {target_id}")
            return True

        elif function_name == "read_sticky_notes":
            target_id = args.get("event_id", "").strip()
            if not target_id:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="Error: event_id is required.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            target_event = await self.blackboard.get_event(target_id)
            if not target_event:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts=f"Event {target_id} not found.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            notes = list(getattr(target_event, "sticky_notes", None) or [])
            unread_notes = [n for n in notes if not n.get("read", False)]
            if not unread_notes:
                turn = ConversationTurn(
                    turn=(await self._next_turn_number(event_id)),
                    actor="brain",
                    action="tool_result",
                    thoughts="No unread notes on this event.",
                    response_parts=response_parts,
                )
                await self._append_and_broadcast(event_id, turn)
                return True
            lines = [f"## {len(unread_notes)} Unread Note(s)\n"]
            for n in unread_notes:
                lines.append(f"**{n.get('timestamp', '?')}**: {n.get('content', '')}")
                n["read"] = True
            await self.blackboard.update_event_sticky_notes(target_id, notes, 0)
            formatted = "\n".join(lines)
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                waitingFor="read_sticky_notes",
                thoughts=formatted,
                response_parts=response_parts,
            )
            await self._append_and_broadcast(event_id, turn)
            logger.info(f"Read {len(unread_notes)} sticky notes on {target_id}")
            return True

        else:
            logger.warning(f"Unknown function call: {function_name}")
            return False

    async def _jarvis_nudge_loop(self, event_id: str, max_nudges: int) -> None:
        """Send nudges to JARVIS at 30s intervals. Auto-resolve after final window."""
        try:
            for i in range(max_nudges):
                await asyncio.sleep(30)
                if event_id not in self._waiting_for_jarvis:
                    return
                if self._live_adapter:
                    try:
                        await self._live_adapter.receive_brain_response(
                            event_id,
                            f"FRIDAY is waiting for your input on this review. (nudge {i + 1}/{max_nudges})",
                        )
                        logger.info("Sent JARVIS nudge %d/%d for %s", i + 1, max_nudges, event_id)
                    except Exception as e:
                        logger.warning("JARVIS nudge failed (non-fatal): %s", e)
            await asyncio.sleep(30)
            if event_id not in self._waiting_for_jarvis:
                return
            logger.info("JARVIS wait timed out for %s -- auto-resolving", event_id)
            self._clear_jarvis_wait(event_id)
            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="tool_result",
                thoughts="JARVIS has not responded after multiple attempts. "
                         "Proceed with the available information in the conversation. "
                         "JARVIS will rejoin when available.",
            )
            await self._append_and_broadcast(event_id, turn)
            self._last_processed[event_id] = time.time()
        except asyncio.CancelledError:
            return

    def _clear_jarvis_wait(self, event_id: str) -> None:
        """Clear wait_for_jarvis state and cancel the nudge timer."""
        self._waiting_for_jarvis.pop(event_id, None)
        task = self._jarvis_wait_tasks.pop(event_id, None)
        if task and not task.done():
            task.cancel()

    def _get_slack_channel(self):
        """Get the registered Slack channel from broadcast targets, if available."""
        for target in self._broadcast_targets:
            if hasattr(target, '__self__') and hasattr(target.__self__, '_app'):
                return target.__self__
        return None

    async def _resolve_slack_user(
        self, slack_channel, user_email: str, event_doc,
    ) -> str | None:
        """Resolve a user_email to a Slack user ID with maintainer fallback.

        Resolution order:
        1. Direct lookup if user_email contains @ or starts with U
        2. On users_not_found: try each email from the maintainer list
        3. Fall back to event.slack_user_id
        """
        if user_email.startswith("U") and user_email.isalnum():
            return user_email

        async def _lookup(email: str) -> str | None:
            try:
                info = await slack_channel._app.client.users_lookupByEmail(email=email)
                return info["user"]["id"]
            except Exception as exc:
                logger.debug("Slack user lookup failed for '%s': %s", email, exc)
                return None

        if "@" in user_email:
            uid = await _lookup(user_email)
            if uid:
                return uid
            logger.warning(
                "notify_user_slack: '%s' not found in Slack, trying maintainer fallback",
                user_email,
            )

        maintainer_emails = self._resolve_maintainer_enum(event_doc) if event_doc else []
        for fallback_email in maintainer_emails:
            if "@" not in fallback_email:
                continue
            if fallback_email == user_email:
                continue
            uid = await _lookup(fallback_email)
            if uid:
                logger.info(
                    "notify_user_slack: resolved via maintainer fallback '%s'",
                    fallback_email,
                )
                return uid

        if event_doc and event_doc.slack_user_id:
            logger.warning(
                "notify_user_slack: all lookups failed, using event slack_user_id %s",
                event_doc.slack_user_id,
            )
            return event_doc.slack_user_id
        return None

    @staticmethod
    def _resolve_maintainer_enum(event) -> list[str]:
        """Extract valid maintainer emails from event evidence + static config.

        Returns a deduplicated list the LLM must pick from (enum constraint).
        Sources: evidence.gitlab_context.maintainer.emails, then HEADHUNTER_MAINTAINERS env.
        """
        emails: list[str] = []
        evidence = getattr(getattr(event, "event", None), "evidence", None)
        if evidence:
            gl = getattr(evidence, "gitlab_context", None) or {}
            if isinstance(gl, dict):
                maintainer = gl.get("maintainer", {})
                emails.extend(maintainer.get("emails", []))
        if not emails:
            static = os.getenv("HEADHUNTER_MAINTAINERS", "")
            emails = [e.strip() for e in static.split(",") if e.strip()]
        if event and getattr(event, "slack_user_id", None):
            emails.append(event.slack_user_id)
        seen: set[str] = set()
        return [e for e in emails if e and e not in seen and not seen.add(e)]

    @staticmethod
    def _inject_maintainer_enum(tools: list[dict], emails: list[str]) -> list[dict]:
        """Deep-copy notify_user_slack schema and constrain user_email to an enum."""
        import copy
        result = []
        for tool in tools:
            if tool["name"] != "notify_user_slack":
                result.append(tool)
                continue
            patched = copy.deepcopy(tool)
            props = patched["input_schema"]["properties"]["user_email"]
            props["enum"] = emails
            props["description"] = (
                f"Maintainer to notify. MUST be one of: {', '.join(emails)}. "
                "Do NOT invent or guess email addresses."
            )
            result.append(patched)
        return result

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
        self._waiting_for_agent.pop(event_id, None)
        self._reflex_fired_for.discard(event_id)

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
        subject_type = getattr(evt, "subject_type", "service") if evt else "service"

        async def on_progress(progress_data: dict) -> None:
            await self._broadcast({
                "type": "progress",
                "event_id": event_id,
                "actor": progress_data.get("actor", role),
                "message": progress_data.get("message", ""),
                "event_source": event_source,
                "subject_type": subject_type,
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
            "subject_type": subject_type,
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
                if self._scheduler:
                    self._scheduler.enqueue(event_id)

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
        parallel: bool = False,
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
            subject_type = getattr(evt, "subject_type", "service") if evt else "service"

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
                    "subject_type": subject_type,
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
            parallel_label = " [parallel]" if parallel else ""
            logger.info(f"Agent task started: {agent_name}{mode_label}{parallel_label} for {event_id}")
            if not parallel:
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
                "subject_type": subject_type,
            })
            if self._ws_mode == "reverse" and agent_name not in ("_aligner", "_archivist_memory"):
                from ..dependencies import get_registry_and_bridge
                from .ephemeral_provisioner import INFRA_SENTINEL
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

                    use_ephemeral = False
                    ephemeral_is_overflow = False

                    # Tier 0: Ephemeral-only roles (no local sidecar exists)
                    if agent_name in self.EPHEMERAL_ONLY_ROLES and self._ephemeral_provisioner:
                        use_ephemeral = True

                    # Tier 1: Primary ephemeral sources (never fall back to local)
                    if not use_ephemeral:
                        use_ephemeral = (
                            self._ephemeral_provisioner
                            and event_doc
                            and (
                                event_doc.source in ("headhunter", "timekeeper")
                                or getattr(event_doc, "subject_type", "service") == "kargo_stage"
                            )
                        )

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

                    # Safety: ephemeral-only role selected but provisioner unavailable
                    if agent_name in self.EPHEMERAL_ONLY_ROLES and not use_ephemeral:
                        logger.warning(
                            "Ephemeral-only role %s selected but provisioner unavailable for %s -- deferring",
                            agent_name, event_id,
                        )
                        await self._execute_function_call(
                            event_id, "defer_event",
                            {"delay_seconds": 60, "reason": f"Role {agent_name} requires ephemeral provisioner (disabled)"},
                            response_parts=None,
                        )
                        return

                    if use_ephemeral:
                        provision_result = await self._ephemeral_provisioner.ensure_agent(event_id)
                        if provision_result is None:
                            if agent_name in self.EPHEMERAL_ONLY_ROLES:
                                logger.warning(
                                    "Ephemeral-only role %s circuit breaker for %s -- deferring (no sidecar fallback)",
                                    agent_name, event_id,
                                )
                                await self._execute_function_call(
                                    event_id, "defer_event",
                                    {"delay_seconds": 60, "reason": f"Security analyst unavailable (ephemeral circuit breaker, no local fallback)"},
                                    response_parts=None,
                                )
                                return
                            elif ephemeral_is_overflow:
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
                        elif provision_result == INFRA_SENTINEL:
                            logger.info("Deferring %s for 60s: Tekton infrastructure unavailable", event_id)
                            await self._execute_function_call(
                                event_id, "defer_event",
                                {"delay_seconds": 60, "reason": "Tekton infrastructure unavailable"},
                            )
                            return
                        else:
                            agent_id_override = provision_result.agent_id

                    if agent_id_override is None:
                        await self.write_event_to_volume(event_id, agent_name)

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
                        if not await self._is_event_closed(event_id) and self._scheduler:
                            self._scheduler.enqueue(event_id)
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
                        if not await self._is_event_closed(event_id) and self._scheduler:
                            self._scheduler.enqueue(event_id)
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
                if not await self._is_event_closed(event_id) and self._scheduler:
                    self._scheduler.enqueue(event_id)
                return

            # Message-mode: agent typically delivers content via progress turns (team_send_message).
            # CLI exit stdout is usually redundant noise -- skip result turn in that case.
            # However: if sendResults was used (shell fallback bypasses MCP notInModes gate),
            # the result_str contains the agent's actual deliverable and MUST be written as
            # a conversation turn so FRIDAY and wait_for_agent can see it.
            if mode == "message":
                # Detect sendResults payload: structured results start with "---" (frontmatter)
                # or contain substantial content (>100 chars) that isn't just CLI noise.
                has_deliverable = (
                    result_str.lstrip().startswith("---")
                    or len(result_str) > 100
                )
                if not has_deliverable:
                    logger.info(
                        f"Message-mode task completed: {agent_name} for {event_id} "
                        f"(no deliverable, content delivered via progress)"
                    )
                    if routing_turn_num:
                        await self.blackboard.mark_turn_status(
                            event_id, routing_turn_num, MessageStatus.EVALUATED
                        )
                        await self._broadcast_status_update(
                            event_id, "evaluated", turns=[routing_turn_num],
                        )
                    await self.blackboard.stamp_event(event_id, last_completed_at=time.time())
                    if not parallel:
                        self._release_task_state(event_id)
                    self._last_processed[event_id] = time.time()
                    return
                # Has deliverable -- fall through to write result turn below
                logger.info(
                    f"Message-mode task completed with deliverable: {agent_name} for {event_id} "
                    f"({len(result_str)} chars -- writing result turn)"
                )

            # Append agent result turn (cancel = clean termination, not an error)
            is_cancel = result_str.strip() == "Cancelled by Brain"

            # Parse plan frontmatter for ANY agent with reasoning: in frontmatter
            # (loosened from architect-only; reasoning: guard mirrors MCP enforcement)
            body, plan_steps, fm = None, None, {}
            reasoning = None
            if not is_cancel and result_str.lstrip().startswith("---"):
                body, plan_steps, fm = self._parse_plan_frontmatter(result_str)
                reasoning = fm.get("reasoning")
                if reasoning and not isinstance(reasoning, str):
                    reasoning = str(reasoning)
                if not reasoning:
                    body, plan_steps, fm = None, None, {}
                    reasoning = None

            has_structured_plan = body and plan_steps

            if has_structured_plan:
                result_for_turn = body[:15000]
            elif reasoning and body:
                result_for_turn = body[:15000]
            else:
                result_for_turn = result_str[:15000]

            task_for_agent = None
            if has_structured_plan:
                task_for_agent = {"steps": plan_steps, "source": agent_name, "reasoning": reasoning}
            elif reasoning:
                task_for_agent = {"reasoning": reasoning}

            turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor=agent_name,
                action="cancel" if is_cancel else ("plan" if has_structured_plan else "execute"),
                result=result_for_turn,
                plan=body if has_structured_plan else None,
                taskForAgent=task_for_agent,
            )
            await self._append_and_broadcast(event_id, turn)
            logger.info(
                f"Agent task {'cancelled' if is_cancel else 'plan' if has_structured_plan else 'completed'}: "
                f"{agent_name} for {event_id}"
                f"{f' (reasoning={len(reasoning)} chars)' if reasoning else ''}"
            )

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
            if not await self._is_event_closed(event_id) and self._scheduler:
                self._scheduler.enqueue(event_id)
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
            if not await self._is_event_closed(event_id) and self._scheduler:
                self._scheduler.enqueue(event_id)

        finally:
            if sema_acquired and self._dispatch_semaphore:
                self._dispatch_semaphore.release()
            # Safety net -- only clean up if _active_tasks still holds OUR task.
            # Re-entry (process_event) may have created a NEW task; don't clobber it.
            # Parallel message tasks never own event state -- skip unconditionally.
            if not parallel and self._active_tasks.get(event_id) is current_task:
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
        self._waiting_for_user.pop(event_id, None)
        self._idle_timeout.cancel(event_id)
        self._routing_depth.pop(event_id, None)  # Reset depth on user interaction

    async def resume_if_parked(self, event_id: str) -> bool:
        """Resume a waiting_approval event back to active. Returns True if resumed."""
        event = await self.blackboard.get_event(event_id)
        if not event or event.status != EventStatus.WAITING_APPROVAL:
            return False
        await self.blackboard.resume_from_approval(event_id)
        if self._scheduler:
            self._scheduler.enqueue(event_id)
        logger.info(f"Resumed parked event {event_id} -- re-enqueued")
        return True

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
        self._waiting_for_user[event_id] = time.time()

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

        # Transition to escalate phase so notify_user_slack is available
        await self._execute_function_call(
            event_id, "set_phase",
            {"phase": "escalate", "reasoning": f"Nudge cascade: {nudge_count} automated check-ins, {idle_min}m idle"},
            response_parts=None,
        )

        if email:
            await self._execute_function_call(
                event_id, "notify_user_slack",
                {"user_email": email, "message": escalation_msg},
                response_parts=None,
            )
            logger.info(f"Escalation DM sent via notify_user_slack to {email} for {event_id}")
        else:
            logger.warning(f"Escalation: no email resolved for {event_id}, wait_for_user set without DM")

        wait_turn = ConversationTurn(
            turn=(await self._next_turn_number(event_id)),
            actor="brain",
            action="wait",
            thoughts=escalation_msg,
            waitingFor="user",
        )
        await self._append_and_broadcast(event_id, wait_turn)
        logger.warning(f"Escalating {event_id} to human after {nudge_count} nudges ({idle_min}m idle)")

    async def _handle_orphan_blank_event(self, event_id: str, event: EventDocument) -> None:
        """Handle a blank event (no conversation) stuck in the active set.

        Uses processing_started_at (with queued_at fallback) as age anchor.
        Re-queues up to 3 times; after the cap, writes an error turn and
        force-closes. Counter is in-memory (_orphan_requeue_count).
        """
        anchor = event.processing_started_at or event.queued_at
        if anchor is None:
            return
        age = time.time() - anchor
        if age <= 60:
            return
        count = self._orphan_requeue_count.get(event_id, 0)
        if count < 3:
            await self.blackboard.redis.lpush(self.blackboard.EVENT_QUEUE, event_id)
            self._orphan_requeue_count[event_id] = count + 1
            logger.warning(
                f"Re-queued orphaned blank event {event_id} "
                f"(attempt {count + 1}/3, age={int(age)}s)"
            )
        else:
            error_turn = ConversationTurn(
                turn=(await self._next_turn_number(event_id)),
                actor="brain",
                action="error",
                thoughts="Event failed to process after 3 re-queue attempts. Force closing.",
            )
            await self._append_and_broadcast(event_id, error_turn)
            await self._close_and_broadcast(
                event_id, "Orphan: failed to process after 3 attempts.",
                close_reason="error",
            )
            self._orphan_requeue_count.pop(event_id, None)
            logger.error(f"Orphan {event_id} closed after 3 failed re-queue attempts")

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
                f"[{event_id}] {summary}"
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
        self._waiting_for_user.pop(event_id, None)
        self._idle_timeout.cancel(event_id)
        self._waiting_for_agent.pop(event_id, None)
        self._clear_jarvis_wait(event_id)
        self._jarvis_wait_count.pop(event_id, None)
        self._last_processed.pop(event_id, None)
        self._orphan_requeue_count.pop(event_id, None)
        self._reasoning_by_event.pop(event_id, None)
        self._recall_lessons.pop(event_id, None)
        self._reflex_fired_for.discard(event_id)
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
        if event and event.source == "headhunter":
            hh = self.agents.get("_headhunter")
            if hh and hasattr(hh, "process_event_feedback"):
                try:
                    await hh.process_event_feedback(event_id)
                except Exception as e:
                    logger.warning(f"Headhunter direct feedback failed (non-fatal): {e}")
            # Wake poll loop: slot opened, pick up next todo immediately
            signal = getattr(self, '_headhunter_close_signal', None)
            if signal:
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

    async def create_kargo_event(self, project: str, stage: str) -> dict:
        """Create a Kargo event from the dashboard (user right-click -> Create Event)."""
        observer = self.agents.get("_kargo_observer")
        if observer is None:
            return {"status": "error", "detail": "KargoObserver not enabled"}
        try:
            status = await observer.get_stage_status(project, stage)
            if "error" in status:
                return {"status": "error", "detail": str(status["error"])}
            status["service"] = f"{stage}@{project}"
            aligner = self.agents.get("_aligner")
            if aligner is None:
                return {"status": "error", "detail": "Aligner not available"}
            event_id = await aligner.handle_failed_promotion(**status)
            if event_id:
                return {"status": "created", "detail": f"Event {event_id} created for {stage}@{project}"}
            return {"status": "skipped", "detail": "Active event exists or cooldown"}
        except Exception as e:
            logger.error(f"create_kargo_event failed for {stage}@{project}: {e}")
            return {"status": "error", "detail": str(e)}

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
        if event.source not in ("headhunter", "jarvis") and getattr(event, "subject_type", "service") not in ("kargo_stage", "system"):
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
    def _parse_plan_frontmatter(raw: str) -> tuple[str | None, list[dict] | None, dict]:
        """Extract plan markdown body, structured steps, and frontmatter dict from YAML.

        Returns (body, steps_list, frontmatter_dict).
        - body: markdown content after frontmatter (None if no frontmatter detected)
        - steps_list: validated plan steps or None
        - frontmatter_dict: raw parsed dict (may contain reasoning, steps, etc.)
        """
        import yaml

        stripped = raw.lstrip()
        if not stripped.startswith("---"):
            return None, None, {}
        end_idx = stripped.find("---", 3)
        if end_idx == -1:
            return stripped, None, {}
        frontmatter_str = stripped[3:end_idx].strip()
        body = stripped[end_idx + 3:].strip()
        try:
            fm = yaml.safe_load(frontmatter_str)
        except Exception:
            return body or stripped, None, {}
        if not isinstance(fm, dict):
            return body or stripped, None, {}
        raw_steps = fm.get("steps")
        if not isinstance(raw_steps, list) or not raw_steps:
            return body or stripped, None, fm
        steps = []
        for s in raw_steps:
            if not isinstance(s, dict) or "id" not in s:
                continue
            steps.append({
                "id": str(s["id"]),
                "agent": s.get("agent", ""),
                "summary": s.get("summary", ""),
            })
        return body or stripped, steps if steps else None, fm

    _MD_SUBJECT_LABEL = {
        "kargo_stage": "Stage",
        "system": "Subject",
        "jira": "Jira Issue",
    }

    @staticmethod
    def _event_to_markdown(event: EventDocument, service_meta=None, mermaid: str = "") -> str:
        """Convert event document to readable Markdown, enriched with service metadata and topology."""
        from ..models import EventEvidence
        evidence = event.event.evidence
        subject_type = getattr(event, "subject_type", "service")
        if subject_type != "service":
            subj_label = Brain._MD_SUBJECT_LABEL.get(subject_type, "Service")
        elif isinstance(evidence, EventEvidence) and evidence.gitlab_context:
            subj_label = "Component"
        elif event.service in ("general", "system", ""):
            subj_label = "Topic"
        else:
            subj_label = "Service"
        lines = [
            f"# Event: {event.id}",
            f"",
            f"- **Source:** {event.source}",
            f"- **{subj_label}:** {event.service}",
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
            display_actor = {"brain": "FRIDAY", "jarvis": "JARVIS"}.get(turn.actor, turn.actor)
            if turn.actor == "user" and getattr(turn, "source", None) == "automated":
                display_actor = "System"
            lines.append(f"### Turn {turn.turn} - {display_actor} ({turn.action}) [{ts_str}] ({delta_label})")
            prev_ts = turn.timestamp
            if turn.actor == "user" and turn.source == "automated":
                if turn.thoughts:
                    lines.append(f"**System Nudge:** {turn.thoughts}")
            elif turn.actor == "user" or turn.action == "message":
                user_text = turn.thoughts or turn.result or ""
                if user_text:
                    lines.append(f"**Message:** {user_text}")
            elif turn.action == "respond_jarvis":
                if turn.thoughts:
                    lines.append(f"**Message to JARVIS:** {turn.thoughts}")
            elif turn.action in ("think", "thoughts", "intermediate"):
                if turn.thoughts:
                    lines.append(f"**Internal:** {turn.thoughts}")
            elif turn.action == "response":
                if turn.thoughts:
                    lines.append(f"**FRIDAY:** {turn.thoughts}")
            elif turn.action == "tool_result":
                evidence_text = turn.result or turn.thoughts or ""
                if evidence_text:
                    lines.append(f"**Evidence:** {evidence_text}")
            else:
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
                self._clear_jarvis_wait(eid)
                self._jarvis_wait_count.pop(eid, None)
                self._recall_lessons.pop(eid, None)
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
                if event.source == "headhunter":
                    hh = self.agents.get("_headhunter")
                    if hh and hasattr(hh, "process_event_feedback"):
                        try:
                            await hh.process_event_feedback(eid)
                        except Exception as e:
                            logger.warning(f"Headhunter stale-close feedback failed (non-fatal): {e}")
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
        """Start the ReconcileScheduler with trigger-based event processing.

        Replaces the old monolithic while-loop with fair N-worker scheduling.
        Workers are auto-derived from source caps * 1.3 (configurable via
        BRAIN_RECONCILE_WORKERS env var, 0 = auto).
        """
        import math
        from ..scheduling import ReconcileScheduler
        from ..scheduling.triggers import QueueTrigger, ResyncTrigger, StalenessGuard

        self._running = True
        await self._cleanup_stale_events()

        self._scheduler = ReconcileScheduler(
            reconcile_fn=self.process_event,
            workers=self._derive_workers(),
            on_error=self._on_reconcile_error,
        )

        self._scheduler.register_trigger(QueueTrigger(
            dequeue_fn=self.blackboard.dequeue_event,
        ))
        self._scheduler.register_trigger(ResyncTrigger(
            scan_fn=self._scan_active_for_reconcile,
            interval=5.0,
        ))
        self._scheduler.register_trigger(StalenessGuard(
            check_fn=self._check_jarvis_staleness,
            on_stale=self._close_stale_jarvis_event,
            name="jarvis",
        ))
        self._scheduler.register_trigger(StalenessGuard(
            check_fn=self._check_chat_staleness,
            on_stale=self._close_stale_chat_event,
            interval=60.0,
            name="chat",
        ))

        logger.info("Brain event loop started (ReconcileScheduler, workers=%d)", self._scheduler._worker_count)
        await self._scheduler.start()

    def _derive_workers(self) -> int:
        """Auto-derive worker count from source caps, or use explicit override."""
        import math
        configured = int(os.getenv("BRAIN_RECONCILE_WORKERS", "0"))
        if configured > 0:
            return configured
        caps = (
            int(os.getenv("ALIGNER_MAX_ACTIVE", "2"))
            + int(os.getenv("HEADHUNTER_MAX_ACTIVE", "3"))
            + int(os.getenv("NIGHTWATCHER_MAX_ACTIVE", "1"))
            + int(os.getenv("CHAT_MAX_ACTIVE", "1"))
            + int(os.getenv("SLACK_MAX_ACTIVE", "1"))
            + 1  # JARVIS meta-event
        )
        return math.ceil(caps * 1.3)

    async def _on_reconcile_error(self, event_id: str, exc: Exception) -> None:
        """Error handler for ReconcileScheduler worker failures."""
        logger.error(f"Reconcile failed for {event_id}: {exc}", exc_info=True)

    async def stop_event_loop(self) -> None:
        """Stop the event loop."""
        self._running = False
        if self._scheduler:
            await self._scheduler.stop()
        logger.info("Brain event loop stopped")

    # =========================================================================
    # ReconcileScheduler: scan callback + staleness helpers
    # =========================================================================

    async def _scan_active_for_reconcile(self) -> list[str]:
        """Scan active events and return IDs that need reconciliation.

        Side effects handled inline: mark_delivered, zombie cleanup,
        orphan handling, defer re-activation. Pure decision logic
        delegates to the validated _scan_logic pattern from Probe B.
        """
        active = await self.blackboard.get_active_events()

        # Keep embedding warm while events are in flight (60s throttle)
        if active and self._memory_reflex_enabled:
            now = time.time()
            if now - self._last_embedding_warmup > 60:
                self._last_embedding_warmup = now
                asyncio.create_task(self._warmup_embedding())

        to_enqueue: list[str] = []

        for eid in active:
            # Agent task running: handle delivery + intermediate, don't enqueue
            if eid in self._active_tasks and not self._active_tasks[eid].done():
                event = await self.blackboard.get_event(eid)
                if event:
                    unseen = [t for t in event.conversation if t.status.value == "sent"]
                    if unseen:
                        await self.blackboard.mark_turns_delivered(eid, len(event.conversation))
                        await self._broadcast_status_update(eid, "delivered", turns=unseen)
                    intermediate = [t for t in unseen if t.actor != "brain"]
                    if intermediate:
                        await self._process_intermediate(eid, event, intermediate)
                continue

            event = await self.blackboard.get_event(eid)
            if not event:
                continue

            # Zombie cleanup
            if event.status == EventStatus.CLOSED:
                logger.warning(f"Zombie active event {eid} is closed -- removing from active set")
                await self.blackboard.redis.srem(self.blackboard.EVENT_ACTIVE, eid)
                continue

            # Orphan blank events
            if not event.conversation:
                if event.status == EventStatus.NEW:
                    to_enqueue.append(eid)
                else:
                    await self._handle_orphan_blank_event(eid, event)
                continue

            # Deferred events: check timer + user interrupt
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
                        continue
                    logger.info(f"User message interrupted defer for {eid} -- waking early")
                # Re-activate deferred event
                logger.info(f"Defer expired for {eid} -- attempting re-activation (defer_key exists={defer_until is not None})")
                transitioned = await self.blackboard.transition_event_status(
                    eid, "deferred", EventStatus.ACTIVE,
                )
                await self.blackboard.redis.delete(defer_key)
                if transitioned:
                    await self._broadcast({
                        "type": "event_status_changed",
                        "event_id": eid,
                        "status": EventStatus.ACTIVE.value,
                    })
                    if eid in self._waiting_for_user:
                        logger.warning(f"Deferred event {eid} re-activated but waiting for user -- skipping")
                    else:
                        logger.info(f"Deferred event {eid} re-activated")
                        self._defer_wake_events.add(eid)
                        to_enqueue.append(eid)
                else:
                    refetched = await self.blackboard.get_event(eid)
                    actual_status = refetched.status.value if refetched else "MISSING"
                    logger.warning(f"Defer re-activation FAILED for {eid}: expected 'deferred', actual '{actual_status}'")
                continue

            # Mark SENT turns as DELIVERED
            unseen = [t for t in event.conversation if t.status.value == "sent"]
            if unseen:
                await self.blackboard.mark_turns_delivered(eid, len(event.conversation))
                await self._broadcast_status_update(eid, "delivered", turns=unseen)

            # JARVIS wait check
            if eid in self._waiting_for_jarvis:
                wait_start = self._waiting_for_jarvis[eid]
                jarvis_reply = any(
                    t.actor == "jarvis" and t.action == "message"
                    and (t.timestamp or 0.0) > wait_start
                    for t in event.conversation
                )
                if jarvis_reply:
                    self._clear_jarvis_wait(eid)
                    self._last_processed[eid] = time.time()
                    to_enqueue.append(eid)
                continue

            # Standard enqueue decision
            has_unread = any(t.status.value == "delivered" for t in event.conversation)
            is_waiting = eid in self._waiting_for_user
            is_locked = eid in self._event_locks and self._event_locks[eid].locked()

            if has_unread and not is_waiting and not is_locked:
                to_enqueue.append(eid)
            elif not has_unread and not is_locked:
                time_since = time.time() - self._last_processed.get(eid, 0)
                if not is_waiting and time_since > 60:
                    logger.info(f"Idle safety net: re-processing event {eid} (idle {time_since:.0f}s)")
                    to_enqueue.append(eid)

        return to_enqueue

    async def _check_jarvis_staleness(self, event_id: str) -> bool:
        """Check if a jarvis-source event has gone stale (no jarvis turn in TTL)."""
        if event_id not in self._waiting_for_jarvis:
            return False
        event = await self.blackboard.get_event(event_id)
        if not event or event.source != "jarvis":
            return False
        ttl = float(os.getenv("JARVIS_STALE_TTL", "120"))
        last_jarvis = max(
            (t.timestamp or 0.0 for t in event.conversation
             if t.actor == "jarvis"),
            default=0.0,
        )
        return (time.time() - last_jarvis) > ttl if last_jarvis else False

    async def _close_stale_jarvis_event(self, event_id: str) -> None:
        """Close a stale jarvis event that exceeded its TTL."""
        logger.warning(f"StalenessGuard: closing stale jarvis event {event_id}")
        self._clear_jarvis_wait(event_id)
        await self._close_and_broadcast(
            event_id,
            summary="JARVIS meta-event timed out (no response within TTL)",
            close_reason="timeout",
        )

    async def _check_chat_staleness(self, event_id: str) -> bool:
        """Check if a chat/slack event in WAITING_APPROVAL has exceeded its TTL."""
        if event_id not in self._waiting_for_user:
            return False
        event = await self.blackboard.get_event(event_id)
        if not event or event.source not in ("chat", "slack"):
            return False
        if event.status != EventStatus.WAITING_APPROVAL:
            return False
        ttl = float(os.getenv("CHAT_STALE_TTL", "5400"))
        last_turn_ts = max(
            (t.timestamp or 0.0 for t in event.conversation),
            default=0.0,
        )
        return (time.time() - last_turn_ts) > ttl if last_turn_ts else False

    async def _close_stale_chat_event(self, event_id: str) -> None:
        """Close a stale chat/slack event that exceeded its approval TTL."""
        logger.warning(f"StalenessGuard[chat]: closing stale chat event {event_id}")
        self._waiting_for_user.pop(event_id, None)
        await self._close_and_broadcast(
            event_id,
            summary="Chat session timed out waiting for user approval",
            close_reason="timeout",
        )

    async def _idle_timeout_warn(self, event_id: str) -> None:
        """Send idle timeout warning to user (Slack thread or dashboard turn)."""
        event = await self.blackboard.get_event(event_id)
        if not event:
            return
        warning_text = "If nothing else is needed, I'll close this in 5 minutes."
        if event.source == "slack" and event.slack_channel_id and event.slack_thread_ts:
            slack_channel = self._get_slack_channel()
            if slack_channel:
                try:
                    await slack_channel._app.client.chat_postMessage(
                        channel=event.slack_channel_id,
                        thread_ts=event.slack_thread_ts,
                        text=f":hourglass: {warning_text}",
                    )
                    logger.info(f"Idle timeout warning posted to Slack thread for {event_id}")
                    return
                except Exception as e:
                    logger.warning(f"Slack idle warning failed for {event_id}, falling back to turn: {e}")
        turn = ConversationTurn(
            turn=(await self._next_turn_number(event_id)),
            actor="brain",
            action="response",
            thoughts=warning_text,
        )
        await self._append_and_broadcast(event_id, turn)
        logger.info(f"Idle timeout warning turn for {event_id}")

    async def _idle_timeout_close(self, event_id: str) -> None:
        """Auto-close event after idle timeout (with race guard)."""
        if event_id not in self._waiting_for_user:
            logger.info(f"Idle timeout close aborted for {event_id}: no longer waiting")
            return
        logger.warning(f"Idle timeout: auto-closing {event_id}")
        self._waiting_for_user.pop(event_id, None)
        await self._close_and_broadcast(
            event_id,
            summary="Automatically closed after idle timeout (no user response).",
            close_reason="idle_timeout",
        )

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

