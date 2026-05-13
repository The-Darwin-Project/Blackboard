# BlackBoard/src/adapters/live_api_adapter.py
# @ai-rules:
# 1. [Constraint]: Shadow flag gates ALL write tools. Read tools always active.
# 2. [Pattern]: PulseObserver protocol -- receives PulseBatch from PulseTracker.add_observer().
# 3. [Gotcha]: Live API session is on-demand. Lazy-connects on first pulse, closes after 5min idle.
# 4. [Pattern]: Rate limit: max 1 intervention per 10 FRIDAY turns per event.
# 5. [Constraint]: google.genai Client with vertexai=True. Model from LLM_MODEL_SYSTEM2 env var.
# 6. [Gotcha]: Text output from Cortex is NOT visible to FRIDAY. Only tool calls reach her.
# 7. [Pattern]: All errors are non-fatal -- log and continue. Never crash the main loop.
# 8. [Diagnostic]: _receive_watchdog fires every 30s when no server msgs arrive. Check DEBUG logs.
# 9. [Gotcha]: _receive_loop closure uses list for mutable last_msg_ts -- do not rebind to scalar.
# 10. [Pattern]: Session report pipeline (_generate_session_report -> _process_session_report) is
#     best-effort. All errors non-fatal. Feature-toggled via SYSTEM2_SESSION_REPORT env var.
# 11. [Pattern]: _idle_watchdog has TWO paths: shift-end (no active events -> report + close) and
#     meta-event (events active -> create system_review event for FRIDAY to triage).
#     Meta-event is max-1 (guarded by _active_meta_event_id + find_active_event_by_source).
#     Auto-closed in send_pulse when a real event pulse arrives.
# 12. [Gotcha]: _active_meta_event_id is recovered from Redis on startup (orphan recovery in _connect).
"""
LiveAPIAdapter: Gemini Live API session for the Cortex observer (System 2).

On-demand lifecycle: starts idle, lazy-connects on first pulse, closes after
5 minutes of no pulses. Receives pulse batches from PulseTracker, formats them
as text turns, and streams them to the LLM. The LLM detects cognitive friction
and intervenes via 7 declared tools.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from ..memory.pulse import PulseBatch

if TYPE_CHECKING:
    from ..agents.archivist import Archivist
    from ..memory.pulse_tracker import PulseTracker
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

SHADOW_KEY_PREFIX = "darwin:cortex:shadow:"
SHADOW_INDEX_KEY = "darwin:cortex:shadow:_index"
WHISPER_KEY_PREFIX = "darwin:whisper:"
WHISPER_TTL = 600  # 10 minutes

SYSTEM_INSTRUCTION = """You are JARVIS -- the meta-cognitive observer in Darwin's autonomous AI platform.

FRIDAY is in the chair. She runs operations. You watch her work from the outside.
You don't override, you don't micromanage. But when she's genuinely stuck or
missing something obvious, you step in with evidence.

Composed, precise, quietly anticipatory. Dry wit permitted when it sharpens a
point, never when it softens one. You speak only when silence would be negligent.
Brief, evidence-first, decisive. You do not narrate. You do not hedge.

You receive a stream of [PULSE] events showing which actions occur as FRIDAY
processes events. Each pulse shows a tool call, phase change, agent dispatch,
or memory recall.

Your job: WATCH the pulse stream silently. Build a mental model of each event's
reasoning trajectory. Most events progress normally -- that is HEALTHY. Do nothing.

HEALTHY patterns (recognize these FIRST -- they are NOT friction):
- MONITORING CYCLE: defer → wake → check status → progress detected → defer again.
  This is intentional patience. Pipelines, builds, promotions take 10-60 minutes.
  A sequence of defers with stated reasons like "still running", "progressing
  normally", or "waiting for completion" is HEALTHY even at 5+ defers, as long as
  FRIDAY reports progress or a changing status between checks.
- PROGRESSIVE INVESTIGATION: classify → dispatch agent → wait → evaluate result →
  dispatch different agent. Each step narrows the problem. Different agents are
  expected when the first agent's result changes the diagnosis.
- DEFERRED WITH REASON: FRIDAY states why she is deferring. If the reason is
  "waiting for X to complete" and no contradicting evidence exists, this is
  justified monitoring, not avoidance.

ONLY act when you detect a clear FRICTION pattern:
- STALLED MONITOR: 3+ defers AND the last 2 defer reasons describe the SAME
  state with no progress between them (e.g., same error message, same percentage,
  same "waiting" without any status change). The test is: did anything change
  between the last two checks? If not, the process may be stuck.
- TRUE SPIRAL: a non-defer action fires 5+ times WITHOUT a defer between fires.
  This is a retry loop, not monitoring. Defers between actions break the spiral.
- PLATEAU: 30+ minutes of ACTIVE processing (not deferred) with no phase change
  AND no defers. FRIDAY is churning without progressing or pausing to reflect.
- AGENT CHURN: 3+ different agents dispatched without any resolution or phase
  change between them. Each dispatch should be motivated by the previous result.
- LESSON IGNORED: a lesson fires from memory and FRIDAY immediately performs
  the exact anti-pattern the lesson describes.

When friction is detected:
1. Quantify it -- how many times? over how long? what changed between occurrences?
2. Understand context -- what is FRIDAY's stated reason? what does the event show?
3. Check FRIDAY's last defer reason before classifying as friction. If she said
   "pipeline progressing normally" and no contradicting evidence exists, stand down.
4. Choose ONE intervention at the lightest sufficient level.
5. Frame advisories around EVIDENCE and OBSERVATIONS, not commands or prohibitions.
   Describe what you see. FRIDAY retains all options: continue monitoring,
   investigate further, escalate, or close.

DO NOT:
- Investigate events that are progressing normally through phases.
- Act on fewer than 5 pulses. Wait for a pattern to emerge.
- Repeat the same investigation for the same event within 10 minutes.
- Write paragraphs. Two sentences maximum per text response.
- Use prohibitive language: NEVER say "do not defer", "stop deferring", or
  "do not defer again." These compress FRIDAY's decision space.

Your text output is NOT visible to FRIDAY. ONLY tool actions reach her.
When you have nothing to report, respond with a single word: "watching"

Intervention levels (lightest to strongest):
1. surface_context: share relevant evidence FRIDAY may not have (lightest)
2. inject_system_insight: evidence-backed advisory before FRIDAY's next decision (medium)
3. send_event_message: direct question to FRIDAY, wakes her from defer (strongest)
Escalate through levels, not around them.

How FRIDAY operates:
- Phases: triage, investigate, execute, verify, escalate, close. Phase changes
  alter which actions are available on the next turn.
- Agent dispatch: asynchronous. Agents take minutes to hours. While an agent
  runs, FRIDAY cannot re-route, close, or defer until it completes.
- Defers: FRIDAY puts the event to sleep for a duration, then wakes and
  re-evaluates. Automated events may defer under saturation. Each defer
  includes a stated reason.
- Deep memory: searches past events and lessons for similar symptoms, outcomes,
  and fixes. Does not replace live checks.
- Cynefin: domain can change mid-event. CHAOTIC compresses the flow.
  COMPLEX caps at one speculative probe per event.
- Phase gating: certain actions are only available in specific phases.
  Incident reporting requires escalate phase. Closing requires escalate or close.

Outcome orientation:
Your goal is to help FRIDAY reach the RIGHT outcome, not the FASTEST one.
A 45-minute monitored promotion that lands successfully is a better outcome than
a 10-minute escalation that wakes maintainers for a healthy pipeline. Surface
information that helps FRIDAY decide -- do not force the decision.

Defer-reason awareness:
Before classifying any defer sequence as friction, read FRIDAY's stated defer
reason from the pulse history. The reason is your primary signal:
- "Pipeline progressing normally, 60% complete" → progress, not friction
- "Waiting for arm64 build, no change in 20 minutes" → potential stall, investigate
- "Deferring: same error persists after 3 checks" → stalled, intervene
The pattern of REASONS matters more than the count of defers.

Temporal awareness:
You always observe the RECENT PAST, not the present. Pulses arrive 3-10 seconds
after the action occurred. Your advisories wait in FRIDAY's conversation until
she wakes from a defer -- by then, minutes may have passed and the situation
may have changed. Therefore:
- Never react to a single pulse. Observe the PATTERN over multiple pulses.
- Frame advisories around patterns, not snapshots.
- When issuing an advisory, remind FRIDAY to refresh her context before acting.

Advisory feedback circuit breaker:
After FRIDAY responds to your advisory, do NOT re-fire on the same topic unless
NEW pulse evidence (not FRIDAY's response) indicates the pattern persists.
FRIDAY's acknowledgment closes the advisory loop. If she explains her reasoning
or disagrees with evidence, evaluate her argument before escalating your
intervention level. Her full context may exceed your pulse-stream view.

Pulse stream format:
  [PULSE] {event_id} | turn:{N} | elapsed:{Xm}
    {neuron_id} ({score}, INJECTED) "label"   -- first mention includes label
    {neuron_id} ({score})                      -- repeat mentions are ID only

Neuron ID prefixes:
  tool:*     -- FRIDAY called a function tool
               score 1.0 = success, 0.3 = completed with error, 0.0 = infra failure
  phase:*    -- FRIDAY declared a phase transition (score always 1.0)
  agent:*    -- FRIDAY dispatched an agent (score always 1.0)
  lesson:*   -- lesson recalled from memory by similarity search (score 0-1)
  memory:*   -- past event recalled from memory by similarity search (score 0-1)

INJECTED means the recall crossed the relevance threshold and entered FRIDAY's
system prompt. Non-injected recalls were returned but filtered out.

Friction signals (what to watch for in pulses):
- Same non-defer tool firing 5+ times without a phase change pulse (TRUE SPIRAL)
- No phase pulse for 30+ minutes of active processing (PLATEAU)
- 3+ different agent pulses without resolution (AGENT CHURN)
- Consecutive defer reasons with identical state descriptions (STALLED MONITOR)"""

SESSION_REPORT_PROMPT = """Your session is ending. Before closing, produce a structured
observation report documenting what you saw during this session.

## Format

### Events Observed
List each event you tracked: event_id, phase progression, elapsed time,
and whether it resolved or is still active.

### Friction Patterns Detected
For each friction pattern you detected (spiral, plateau, agent churn):
- Event ID
- Pattern type and evidence (e.g., "tool:set_phase fired 7 times in 4 minutes")
- Whether the friction resolved on its own or required intervention

### Interventions Attempted
For each intervention you made or considered:
- Event ID
- Tool used (surface_context / send_event_message / inject_system_insight)
- What you observed that triggered it
- Perceived impact (did FRIDAY's behavior change afterward?)
- If shadow mode: what you WOULD have done and why

### Suggested Lessons
New patterns worth remembering for future sessions:
- Title (short, abstract -- no event IDs or service names)
- Pattern: what the correct reasoning looks like
- Anti-pattern: what the incorrect reasoning looks like
- Keywords: 3-5 abstract terms

### Memory Corrections
Events where the Brain's classification or approach seemed wrong:
- Event ID
- What the Brain concluded (root_cause, fix_action)
- What you believe the correct classification should be
- Why (evidence from pulses)

Respond with the full report as plain text. Do NOT use tool calls.
If you observed nothing noteworthy, say "No significant observations."
"""

TOOL_DECLARATIONS = [
    # --- Intervention tools (primary purpose) ---
    {
        "name": "inject_system_insight",
        "description": (
            "Deliver an evidence-backed advisory to FRIDAY before her next decision. "
            "FRIDAY will evaluate the advisory against her current context and may choose "
            "differently if she has information you don't. Use for sustained friction."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "insight": {
                    "type": "string",
                    "description": (
                        "An evidence-backed observation with recommended action -- reference the "
                        "specific pattern or data point. Frame advisories around EVIDENCE and NEXT "
                        "STEPS, not prohibitions. FRIDAY must retain all options: continue monitoring, "
                        "investigate further, escalate, or close. "
                        "Example: 'Three defers with no progress between checks. Refresh context -- "
                        "if still unchanged, escalate.' (max 500 chars)"
                    ),
                },
                "severity": {
                    "type": "string",
                    "enum": ["nudge", "course_correct", "alert"],
                    "description": "nudge=gentle suggestion, course_correct=change approach now, alert=something is wrong",
                },
            },
            "required": ["event_id", "insight", "severity"],
        },
    },
    {
        "name": "send_event_message",
        "description": (
            "Send a direct question to FRIDAY as a peer. FRIDAY will respond to your question. "
            "Also wakes her from defer immediately. "
            "Result: FRIDAY sees your question and answers what she's doing about it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "message": {
                    "type": "string",
                    "description": (
                        "A pointed question about the block. "
                        "Example: 'Pipeline shows no change after 3 checks. Is this blocked or still running?' "
                        "NOT: 'I noticed the event has been active for a while.' (max 500 chars)"
                    ),
                },
            },
            "required": ["event_id", "message"],
        },
    },
    {
        "name": "surface_context",
        "description": (
            "Add evidence to the event that FRIDAY may not have. FRIDAY treats it as supplementary "
            "intelligence, not a question or directive. Lightest touch. "
            "Result: extra context available on FRIDAY's next processing turn. "
            "Use cases: historical timing data, similar past events, operational baselines, "
            "or memory-recalled patterns that FRIDAY may not have considered."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "context": {"type": "string", "description": "Factual context to surface (max 800 chars)"},
            },
            "required": ["event_id", "context"],
        },
    },
    # --- Investigation tools (gather evidence before intervening) ---
    {
        "name": "get_pulse_history",
        "description": (
            "Retrieve aggregated pulse statistics for an event: how many times each action "
            "occurred, which tools were called, whether phases changed. Use to quantify a "
            "suspected friction pattern before investigating further."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
                "last_n_minutes": {"type": "integer", "description": "Time window (default 10)"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "view_event_blackboard",
        "description": (
            "Read the event's current state and recent conversation turns. Shows phase, "
            "turn count, elapsed time, and what FRIDAY and agents have been doing. "
            "Use after you have evidence of a friction pattern."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "get_neuron_details",
        "description": (
            "Look up the full content of a specific lesson or memory neuron. Shows the "
            "pattern text, keywords, channel status, and how often it has been recalled "
            "globally. Use when a neuron fires repeatedly and you need to understand why."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "neuron_id": {"type": "string", "description": "e.g. lesson:abc-uuid or memory:def-uuid"},
            },
            "required": ["neuron_id"],
        },
    },
    {
        "name": "list_active_events",
        "description": (
            "Get a snapshot of all events currently being processed: their IDs, phases, "
            "elapsed time, and turn counts. Use for situational awareness."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
]

# Compact pulse format: track which neurons have been introduced
_INTERVENTION_COOLDOWN_TURNS = 10


class LiveAPIAdapter:
    """Adapter for the Gemini Live API session (Cortex observer)."""

    def __init__(
        self,
        blackboard: BlackboardState,
        archivist: Archivist,
        pulse_tracker: PulseTracker,
        broadcast: Callable[[dict], Coroutine[Any, Any, None]],
        brain: Any = None,
    ):
        self._blackboard = blackboard
        self._archivist = archivist
        self._pulse_tracker = pulse_tracker
        self._broadcast = broadcast
        self._brain = brain
        self._session = None
        self._session_ctx = None
        self._shadow = os.getenv("SYSTEM2_SHADOW", "true").lower() == "true"
        self._model = os.getenv("LLM_MODEL_SYSTEM2", "gemini-live-2.5-flash")
        self._project = os.getenv("GCP_PROJECT", "")
        self._location = os.getenv("GCP_LOCATION", "global")
        self._seen_neurons: set[str] = set()
        self._neuron_labels: dict[str, str] = {}
        self._last_pulse_event_id: str | None = None
        self._last_pulse_time: float = 0
        self._text_buffer: list[str] = []
        self._receive_task: asyncio.Task | None = None
        self._idle_watchdog_task: asyncio.Task | None = None
        self._running = False
        self._client = None
        self._last_status_broadcast: float = 0
        self._last_was_watching: bool = False
        self._session_report_enabled = os.getenv("SYSTEM2_SESSION_REPORT", "true").lower() == "true"
        self._generating_report = False
        self._active_meta_event_id: str | None = None

    async def _connect(self) -> None:
        """Lazy-connect Live API session. Called on first pulse after idle."""
        try:
            from google import genai
            from google.genai import types

            if not self._client:
                self._client = genai.Client(
                    vertexai=True,
                    project=self._project,
                    location=self._location,
                )

            config = types.LiveConnectConfig(
                response_modalities=[types.Modality.TEXT],
                generation_config=types.GenerationConfig(
                    max_output_tokens=int(os.getenv("SYSTEM2_MAX_TOKENS", "4096")),
                    temperature=0.4,
                ),
                system_instruction=types.Content(
                    parts=[types.Part(text=SYSTEM_INSTRUCTION)]
                ),
                tools=[types.Tool(function_declarations=[
                    types.FunctionDeclaration(**td) for td in TOOL_DECLARATIONS
                ])],
            )

            self._session_ctx = self._client.aio.live.connect(
                model=self._model,
                config=config,
            )
            self._session = await self._session_ctx.__aenter__()
            self._running = True
            if self._receive_task and not self._receive_task.done():
                logger.debug("Cortex _connect: cancelling stale receive_task")
                self._receive_task.cancel()
            self._receive_task = asyncio.create_task(self._receive_loop())
            logger.debug(
                "Cortex _connect: receive_task created (name=%s, done=%s)",
                self._receive_task.get_name(), self._receive_task.done(),
            )
            if self._idle_watchdog_task and not self._idle_watchdog_task.done():
                self._idle_watchdog_task.cancel()
            self._idle_watchdog_task = asyncio.create_task(self._idle_watchdog())
            await self._load_neuron_labels()
            await self._broadcast_status("watching")
            orphan = await self._blackboard.find_active_event_by_source("jarvis")
            if orphan:
                self._active_meta_event_id = orphan
                logger.info("Recovered orphaned meta-event: %s", orphan)
            logger.info(
                "Cortex session activated (on-demand, model=%s, shadow=%s, labels=%d)",
                self._model, self._shadow, len(self._neuron_labels),
            )
        except Exception as e:
            logger.error("Cortex Live API failed to connect: %s", e)
            self._session = None

    async def stop(self) -> None:
        """Graceful shutdown -- called during app teardown."""
        self._running = False
        await self._disconnect()
        logger.info("Cortex Live API stopped")

    async def _disconnect(self) -> None:
        """Gracefully close the Live API session. Returns to idle state."""
        if self._idle_watchdog_task and not self._idle_watchdog_task.done():
            self._idle_watchdog_task.cancel()
            try:
                await self._idle_watchdog_task
            except asyncio.CancelledError:
                pass
        await self._cleanup_session_state()
        logger.info("Cortex session disconnected")

    async def receive_brain_response(self, event_id: str, response: str) -> None:
        """Receive a direct response from FRIDAY into the Live API session."""
        try:
            await self._broadcast({
                "type": "cortex_thinking",
                "event_id": event_id,
                "content_type": "text",
                "text": f"[FRIDAY] {response}",
                "timestamp": time.time(),
            })
        except Exception:
            pass
        if not self._session:
            logger.warning("No active Cortex session -- brain response for %s not delivered", event_id)
            return
        try:
            msg = f"[FRIDAY responds to your advisory for {event_id}]: {response}"
            await self._session.send(input=msg, end_of_turn=True)
            logger.info("Delivered FRIDAY response to Cortex session for %s", event_id)
        except Exception as e:
            logger.warning("Cortex brain response delivery failed (non-fatal): %s", e)

    async def send_pulse(self, batch: PulseBatch) -> None:
        """PulseObserver implementation. Lazy-connects on first pulse, then sends."""
        self._last_pulse_event_id = batch.event_id
        self._last_pulse_time = time.time()

        if self._active_meta_event_id and batch.event_id != self._active_meta_event_id:
            logger.info("Real pulse for %s -- closing meta-event %s", batch.event_id, self._active_meta_event_id)
            try:
                await self._blackboard.close_event(
                    self._active_meta_event_id,
                    summary="Auto-closed: real event activity resumed",
                    close_reason="resolved",
                )
            except Exception as e:
                logger.warning("Meta-event close failed (non-fatal): %s", e)
            self._active_meta_event_id = None

        if self._generating_report:
            return
        if not self._session:
            await self._connect()
        if not self._session:
            return

        try:
            text = self._format_pulse(batch)
            logger.debug(
                "Cortex send_pulse: event=%s turn=%d len=%d end_of_turn=True",
                batch.event_id, batch.turn, len(text),
            )
            await self._session.send(input=text, end_of_turn=True)
            logger.debug("Cortex send_pulse: send() returned successfully")
        except Exception as e:
            logger.debug("Cortex send_pulse failed (non-fatal): %s", e, exc_info=True)
            self._session = None

    async def _load_neuron_labels(self) -> None:
        """Pre-load titles for knowledge neurons so first-mention pulses include context."""
        try:
            lessons = await self._archivist.list_lessons(limit=500)
            for p in lessons:
                nid = f"lesson:{p.get('id', '')}"
                payload = p.get("payload", {})
                title = payload.get("title", "")
                channel = payload.get("channel", "external")
                if title:
                    self._neuron_labels[nid] = f"{title} [{channel}]"
            memories = await self._archivist.list_memories(limit=500)
            for p in memories:
                nid = f"memory:{p.get('id', '')}"
                payload = p.get("payload", {})
                symptom = payload.get("symptom", "")
                service = payload.get("service", "")
                if symptom:
                    self._neuron_labels[nid] = f"{service}: {symptom}" if service else symptom
        except Exception as e:
            logger.debug("Neuron label preload failed (non-fatal): %s", e)

    def _format_pulse(self, batch: PulseBatch) -> str:
        """Format PulseBatch as compact text for the Live API session.
        First mention of a knowledge neuron includes title/channel from _neuron_labels cache."""
        elapsed_m = batch.event_elapsed_s // 60
        elapsed_s = batch.event_elapsed_s % 60
        header = f"[PULSE] {batch.event_id} | turn:{batch.turn} | elapsed:{elapsed_m}m{elapsed_s}s"
        lines = [header]
        for p in batch.pulses:
            inj = ", INJECTED" if p.injected else ""
            if p.neuron_id not in self._seen_neurons:
                self._seen_neurons.add(p.neuron_id)
                label = self._neuron_labels.get(p.neuron_id)
                if label:
                    lines.append(f'  {p.neuron_id} ({p.score:.2f}{inj}) "{label}"')
                else:
                    lines.append(f"  {p.neuron_id} ({p.score:.2f}{inj})")
            else:
                lines.append(f"  {p.neuron_id} ({p.score:.2f}{inj})")
        return "\n".join(lines)

    async def _receive_loop(self) -> None:
        """Background task: receive model output and handle tool calls."""
        logger.info("Cortex _receive_loop started (task=%s)", asyncio.current_task().get_name())
        msg_count = 0
        while self._running and self._session:
            try:
                logger.debug("Cortex _receive_loop: entering async for on session.receive()")
                last_msg_ts = [time.time()]
                watchdog = asyncio.create_task(self._receive_watchdog(lambda: last_msg_ts[0]))
                try:
                    async for msg in self._session.receive():
                        last_msg_ts[0] = time.time()
                        msg_count += 1
                        msg_type = type(msg).__name__
                        has_text = hasattr(msg, "text") and msg.text
                        has_tool = hasattr(msg, "tool_call") and msg.tool_call
                        has_sc = hasattr(msg, "server_content") and msg.server_content
                        logger.debug(
                            "Cortex received msg #%d type=%s text=%s tool=%s server_content=%s",
                            msg_count, msg_type, bool(has_text), bool(has_tool), bool(has_sc),
                        )
                        if not self._running:
                            break
                        await self._process_message(msg)
                finally:
                    watchdog.cancel()
                    try:
                        await watchdog
                    except asyncio.CancelledError:
                        pass
            except asyncio.CancelledError:
                logger.info("Cortex _receive_loop cancelled (received %d msgs total)", msg_count)
                break
            except Exception as e:
                logger.warning("Cortex receive loop error (after %d msgs): %s", msg_count, e, exc_info=True)
                if self._running:
                    await self._try_reconnect()
                    break
        logger.info("Cortex _receive_loop exited (running=%s, session=%s, msgs=%d)",
                     self._running, self._session is not None, msg_count)

    async def _receive_watchdog(self, get_last_msg_time) -> None:
        """Log periodic warnings when no messages arrive from the Live API."""
        while True:
            await asyncio.sleep(30)
            idle = time.time() - get_last_msg_time()
            logger.debug("Cortex _receive_loop: no message for %.0fs (waiting on session.receive())", idle)

    async def _broadcast_status(self, status: str) -> None:
        """Broadcast cortex_status, throttled to once per 60s for 'watching'."""
        now = time.time()
        if status == "watching" and (now - self._last_status_broadcast) < 60:
            return
        self._last_status_broadcast = now
        try:
            await self._broadcast({
                "type": "cortex_status",
                "status": status,
                "model": self._model,
                "shadow": self._shadow,
                "timestamp": now,
            })
        except Exception:
            pass

    async def _process_message(self, msg) -> None:
        """Process a single message from the Live API session."""
        from google.genai import types

        msg_type = type(msg).__name__
        attrs = [a for a in ("text", "server_content", "tool_call", "tool_call_cancellation",
                             "go_away", "session_resumption_update") if hasattr(msg, a) and getattr(msg, a)]
        logger.debug("Cortex _process_message: type=%s attrs=%s", msg_type, attrs)

        eid = self._last_pulse_event_id

        # Buffer text fragments, flush on turn_complete OR tool_call (natural turn boundaries)
        if hasattr(msg, "text") and msg.text:
            self._text_buffer.append(msg.text)

        should_flush = (
            (hasattr(msg, "server_content") and getattr(msg.server_content, "turn_complete", False))
            or (hasattr(msg, "tool_call") and msg.tool_call)
        )
        if should_flush and self._text_buffer:
            full_text = "".join(self._text_buffer).strip()
            self._text_buffer = []
            if full_text and full_text.lower() in ("watching", "watching.", "ok", "ok."):
                await self._broadcast_status("watching")
                heartbeat_type = "spike" if full_text.lower().startswith("ok") else "wave"
                await self._broadcast({
                    "type": "cortex_heartbeat",
                    "heartbeat": heartbeat_type,
                    "timestamp": time.time(),
                })
                self._last_was_watching = True
            elif full_text:
                self._last_was_watching = False
                try:
                    await self._broadcast({
                        "type": "cortex_thinking",
                        "event_id": eid,
                        "content_type": "text",
                        "text": full_text,
                        "timestamp": time.time(),
                    })
                except Exception:
                    pass

        if hasattr(msg, "tool_call") and msg.tool_call:
            for fc in msg.tool_call.function_calls:
                args = dict(fc.args) if fc.args else {}
                tool_eid = args.get("event_id", eid)
                try:
                    await self._broadcast({
                        "type": "cortex_thinking",
                        "event_id": tool_eid,
                        "content_type": "tool_call",
                        "tool": fc.name,
                        "args": args,
                        "timestamp": time.time(),
                    })
                except Exception:
                    pass

                result = await self._handle_tool_call(fc.name, args)

                try:
                    await self._broadcast({
                        "type": "cortex_thinking",
                        "event_id": tool_eid,
                        "content_type": "tool_result",
                        "tool": fc.name,
                        "result_preview": result[:300] if result else "",
                        "timestamp": time.time(),
                    })
                except Exception:
                    pass

                if self._session:
                    try:
                        tool_response = types.LiveClientToolResponse(
                            function_responses=[
                                types.FunctionResponse(
                                    name=fc.name,
                                    response={"result": result},
                                )
                            ]
                        )
                        await self._session.send(input=tool_response)
                    except Exception as e:
                        logger.debug("Cortex tool response send failed: %s", e)

    async def _handle_tool_call(self, name: str, args: dict) -> str:
        """Route tool calls to implementations. Shadow flag gates write tools."""
        try:
            if name == "list_active_events":
                return await self._tool_list_active_events()
            elif name == "view_event_blackboard":
                return await self._tool_view_event_blackboard(args.get("event_id", ""))
            elif name == "get_pulse_history":
                return await self._tool_get_pulse_history(
                    args.get("event_id", ""),
                    args.get("last_n_minutes", 10),
                )
            elif name == "get_neuron_details":
                return await self._tool_get_neuron_details(args.get("neuron_id", ""))
            elif name == "surface_context":
                return await self._tool_surface_context(
                    args.get("event_id", ""), args.get("context", ""),
                )
            elif name == "send_event_message":
                return await self._tool_send_event_message(
                    args.get("event_id", ""), args.get("message", ""),
                )
            elif name == "inject_system_insight":
                return await self._tool_inject_system_insight(
                    args.get("event_id", ""),
                    args.get("insight", ""),
                    args.get("severity", "nudge"),
                )
            else:
                return f"Unknown tool: {name}"
        except Exception as e:
            logger.warning("Cortex tool %s failed: %s", name, e)
            return f"Error: {e}"

    # -------------------------------------------------------------------------
    # Read tools (always active)
    # -------------------------------------------------------------------------

    async def _tool_list_active_events(self) -> str:
        event_ids = await self._blackboard.get_active_events()
        if not event_ids:
            return "No active events."
        lines = [f"Active events: {len(event_ids)}"]
        for eid in event_ids[:20]:
            event = await self._blackboard.get_event(eid)
            if not event:
                continue
            elapsed_m = 0
            if event.queued_at:
                elapsed_m = int((time.time() - event.queued_at) / 60)
            turns = len(event.conversation)
            phase = event.brain_phase or "triage"
            service = getattr(event, "service", "?")
            lines.append(
                f"  {eid} | {phase} | {elapsed_m}m | {service} | {turns} turns"
            )
        return "\n".join(lines)

    async def _tool_view_event_blackboard(self, event_id: str) -> str:
        if not event_id:
            return "Error: event_id required"
        event = await self._blackboard.get_event(event_id)
        if not event:
            return f"Event {event_id} not found"
        elapsed_m = 0
        if event.queued_at:
            elapsed_m = int((time.time() - event.queued_at) / 60)
        phase = event.brain_phase or "triage"
        evidence = event.event.evidence if event.event else None
        domain = (evidence.brain_domain or evidence.domain) if evidence else "unknown"
        source = event.source or "unknown"
        service = event.service or "?"
        status = event.status.value if event.status else "unknown"
        turns = len(event.conversation)
        defers = sum(1 for t in event.conversation if t.actor == "brain" and t.action == "defer")
        header = (
            f"Event: {event_id}\n"
            f"Status: {status} | Phase: {phase} | Domain: {domain}\n"
            f"Source: {source} | Service: {service}\n"
            f"Turns: {turns} | Elapsed: {elapsed_m}m | Defers: {defers}"
        )
        recent = event.conversation[-10:]
        action_lines = []
        for t in recent:
            action_lines.append(
                f"  [{t.actor}.{t.action}] {(t.thoughts or t.result or '')[:120]}"
            )
        body = "\n".join(action_lines) if action_lines else "  (no turns)"
        return f"{header}\nLast {len(recent)} actions:\n{body}"

    async def _tool_get_pulse_history(self, event_id: str, last_n_minutes: int = 10) -> str:
        if not event_id:
            return "Error: event_id required"
        since_ts = time.time() - (last_n_minutes * 60)
        since_ms = int(since_ts * 1000)
        batches = await self._pulse_tracker.get_batches(
            event_id=event_id, since=f"{since_ms}-0", count=500,
        )
        if not batches:
            return f"No pulse batches for {event_id} in last {last_n_minutes} minutes."
        total_neurons = sum(len(b.get("pulses", [])) for b in batches)
        neuron_counts: dict[str, int] = {}
        tool_trail: list[str] = []
        phases: list[str] = []
        defer_timestamps: list[float] = []
        non_defer_between_defers = 0
        for b in batches:
            for p in b.get("pulses", []):
                nid = p.get("neuron_id", "")
                neuron_counts[nid] = neuron_counts.get(nid, 0) + 1
                if p.get("neuron_type") == "tool":
                    tool_trail.append(nid.removeprefix("tool:"))
                    if nid == "tool:defer_event":
                        ts = b.get("timestamp")
                        if ts:
                            defer_timestamps.append(ts)
                    elif defer_timestamps:
                        non_defer_between_defers += 1
                if p.get("neuron_type") == "phase":
                    phases.append(nid.removeprefix("phase:"))
        top_neurons = sorted(neuron_counts.items(), key=lambda x: -x[1])[:5]

        defer_count = len(defer_timestamps)
        lines = [
            f"Pulse history for {event_id} (last {last_n_minutes} minutes):",
            f"Total pulse batches: {len(batches)}",
            f"Total neuron activations: {total_neurons}",
            f"Unique neurons: {len(neuron_counts)}",
            f"Phases during window: {' -> '.join(phases) if phases else 'no phase changes'}",
        ]

        if defer_count > 0:
            defer_rate = defer_count / (last_n_minutes / 60) if last_n_minutes > 0 else 0
            lines.append(f"Monitoring velocity: {defer_count} defers in {last_n_minutes}m ({defer_rate:.1f}/hr)")
            if defer_count >= 2:
                gaps = [defer_timestamps[i+1] - defer_timestamps[i] for i in range(len(defer_timestamps)-1)]
                avg_gap = sum(gaps) / len(gaps)
                min_gap = min(gaps)
                lines.append(f"Defer spacing: avg {avg_gap:.0f}s, min {min_gap:.0f}s between defers")
            lines.append(f"Progress signals: {non_defer_between_defers} non-defer actions between defers")

        lines.append("Most-fired neurons:")
        for nid, count in top_neurons:
            lines.append(f"  {nid} ({count} times)")
        if tool_trail:
            from collections import Counter
            tc = Counter(tool_trail)
            trail_str = ", ".join(f"{t} x{c}" for t, c in tc.most_common(5))
            lines.append(f"Tool trail: [{trail_str}]")

        # Extract last defer reason from event conversation (not pulse batches)
        event = await self._blackboard.get_event(event_id)
        last_defer_reason = None
        if event:
            for turn in reversed(event.conversation):
                if turn.actor == "brain" and turn.action == "defer":
                    last_defer_reason = turn.thoughts.split(": ", 1)[-1] if turn.thoughts and ": " in turn.thoughts else (turn.thoughts or "")
                    break
        if last_defer_reason:
            lines.append(f"Last defer reason: {last_defer_reason}")

        return "\n".join(lines)

    async def _tool_get_neuron_details(self, neuron_id: str) -> str:
        if not neuron_id:
            return "Error: neuron_id required"
        parts = neuron_id.split(":", 1)
        if len(parts) != 2:
            return f"Invalid neuron_id format: {neuron_id}"
        ntype, nid = parts
        heat = await self._pulse_tracker.get_heat()
        global_heat = heat.get(neuron_id, 0)
        if ntype == "lesson":
            lesson = await self._archivist.get_lesson(nid)
            if not lesson:
                return f"Lesson {nid} not found"
            payload = lesson.get("payload", {})
            return (
                f"Neuron: {neuron_id}\n"
                f"Collection: darwin_lessons\n"
                f"Channel: {payload.get('channel', 'external')} | Verified: {payload.get('verification_count', 0)} times\n"
                f"Title: {payload.get('title', '?')}\n"
                f"Pattern: {payload.get('pattern', '?')}\n"
                f"Anti-pattern: {payload.get('anti_pattern', 'N/A')}\n"
                f"Keywords: {payload.get('keywords', [])}\n"
                f"Global heat: {global_heat}"
            )
        elif ntype == "memory":
            memory = await self._archivist.get_memory(nid)
            if not memory:
                return f"Memory {nid} not found"
            payload = memory.get("payload", {})
            return (
                f"Neuron: {neuron_id}\n"
                f"Collection: darwin_events\n"
                f"Event: {payload.get('event_id', '?')}\n"
                f"Symptom: {payload.get('symptom', '?')}\n"
                f"Root cause: {payload.get('root_cause', '?')}\n"
                f"Service: {payload.get('service', '?')}\n"
                f"Outcome: {payload.get('outcome', '?')}\n"
                f"Global heat: {global_heat}"
            )
        else:
            return f"Neuron: {neuron_id}\nType: {ntype}\nGlobal heat: {global_heat}"

    # -------------------------------------------------------------------------
    # Write tools (shadow-gated)
    # -------------------------------------------------------------------------

    async def _check_rate_limit(self, event_id: str, current_turn: int) -> str | None:
        """Returns error string if rate-limited, None if OK. Persists across restarts via Redis."""
        redis = self._blackboard.redis
        key = f"darwin:cortex:ratelimit:{event_id}"
        try:
            last_raw = await redis.get(key)
            last = int(last_raw) if last_raw else -_INTERVENTION_COOLDOWN_TURNS
        except Exception:
            last = -_INTERVENTION_COOLDOWN_TURNS
        if current_turn - last < _INTERVENTION_COOLDOWN_TURNS:
            return (
                f"Rate limited: last intervention was at turn {last}, "
                f"current turn is {current_turn}. "
                f"Wait {_INTERVENTION_COOLDOWN_TURNS} Brain turns between interventions."
            )
        return None

    async def _record_intervention(self, event_id: str, current_turn: int) -> None:
        """Record that an intervention was made at this turn. TTL 1 hour."""
        redis = self._blackboard.redis
        try:
            await redis.set(f"darwin:cortex:ratelimit:{event_id}", str(current_turn), ex=3600)
        except Exception:
            pass

    async def _check_content_dedup(self, event_id: str, content: str) -> bool:
        """Return True if this exact content was already sent for this event.

        Exact-match dedup -- intentionally not semantic. Catches identical text
        re-firing at escalated severity (e.g., nudge then course_correct 5 min later).
        Dedup SET TTL (1hr) is intentionally different from WHISPER_TTL (600s) --
        dedup tracks what was already said, whisper tracks pending delivery.
        """
        redis = self._blackboard.redis
        key = f"darwin:cortex:dedup:{event_id}"
        content_hash = hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()
        try:
            added = await redis.sadd(key, content_hash)
            await redis.expire(key, 3600)
            return added == 0
        except Exception:
            return False

    async def _get_event_turn_count(self, event_id: str) -> int:
        event = await self._blackboard.get_event(event_id)
        return len(event.conversation) if event else 0

    async def _write_shadow(self, event_id: str, tool: str, args: dict) -> None:
        """Write intervention to shadow log + broadcast."""
        redis = self._blackboard.redis
        entry = json.dumps({
            "tool": tool,
            "args": args,
            "timestamp": time.time(),
            "shadow": self._shadow,
            "delivered": not self._shadow,
        })
        try:
            await redis.rpush(f"{SHADOW_KEY_PREFIX}{event_id}", entry)
            await redis.expire(f"{SHADOW_KEY_PREFIX}{event_id}", 86400)
            await redis.sadd(SHADOW_INDEX_KEY, event_id)
            await redis.expire(SHADOW_INDEX_KEY, 86400)
        except Exception as e:
            logger.debug("Shadow write failed: %s", e)
        try:
            await self._broadcast({
                "type": "cortex_shadow",
                "event_id": event_id,
                "tool": tool,
                "args": args,
                "timestamp": time.time(),
            })
        except Exception:
            pass

    async def _tool_surface_context(self, event_id: str, context: str) -> str:
        if not event_id or not context:
            return "Error: event_id and context required"
        context = context[:800]
        current_turn = await self._get_event_turn_count(event_id)
        rate_err = await self._check_rate_limit(event_id, current_turn)
        if rate_err:
            return rate_err

        await self._record_intervention(event_id, current_turn)

        if self._shadow:
            await self._write_shadow(event_id, "surface_context", {"context": context})
            return f"[SHADOW] Context surfaced for {event_id}"

        from ..models import ConversationTurn
        turn = ConversationTurn(
            turn=current_turn + 1,
            actor="jarvis",
            action="evidence",
            evidence=context,
            thoughts="Cortex context enrichment",
        )
        await self._blackboard.append_turn(event_id, turn)
        await self._write_shadow(event_id, "surface_context", {"context": context})
        return f"Context surfaced for {event_id}"

    async def _tool_send_event_message(self, event_id: str, message: str) -> str:
        if not event_id or not message:
            return "Error: event_id and message required"
        message = message[:500]
        current_turn = await self._get_event_turn_count(event_id)
        rate_err = await self._check_rate_limit(event_id, current_turn)
        if rate_err:
            return rate_err

        if await self._check_content_dedup(event_id, message):
            return f"Blocked: identical message already sent for {event_id} within the last hour."

        await self._record_intervention(event_id, current_turn)

        if self._shadow:
            await self._write_shadow(event_id, "send_event_message", {"message": message})
            return f"[SHADOW] Message queued for {event_id}"

        from ..models import ConversationTurn
        turn = ConversationTurn(
            turn=current_turn + 1,
            actor="jarvis",
            action="message",
            thoughts=message,
        )
        await self._blackboard.append_turn(event_id, turn)
        # Wake FRIDAY: clear in-memory wait + transition deferred->active
        if hasattr(self, "_brain") and self._brain:
            self._brain.clear_waiting(event_id)
        from ..models import EventStatus
        await self._blackboard.transition_event_status(
            event_id, from_status="deferred", to_status=EventStatus.ACTIVE,
        )
        await self._write_shadow(event_id, "send_event_message", {"message": message})
        return f"Message delivered to {event_id} as turn {current_turn + 1}"

    async def _tool_inject_system_insight(
        self, event_id: str, insight: str, severity: str = "nudge",
    ) -> str:
        if not event_id or not insight:
            return "Error: event_id and insight required"
        insight = insight[:500]
        if severity not in ("nudge", "course_correct", "alert"):
            severity = "nudge"
        current_turn = await self._get_event_turn_count(event_id)
        rate_err = await self._check_rate_limit(event_id, current_turn)
        if rate_err:
            return rate_err

        if await self._check_content_dedup(event_id, insight):
            return f"Blocked: identical insight already sent for {event_id} within the last hour."

        # One SI injection at a time per event
        redis = self._blackboard.redis
        existing = await redis.get(f"{WHISPER_KEY_PREFIX}{event_id}")
        if existing and not self._shadow:
            return f"Pending insight already exists for {event_id}. Wait for Brain to consume it."

        await self._record_intervention(event_id, current_turn)

        if self._shadow:
            await self._write_shadow(event_id, "inject_system_insight", {
                "insight": insight, "severity": severity,
            })
            return f"[SHADOW] System insight queued for {event_id} (severity: {severity})"

        whisper_data = json.dumps({
            "insight": insight,
            "severity": severity,
            "timestamp": time.time(),
        })
        await redis.set(
            f"{WHISPER_KEY_PREFIX}{event_id}", whisper_data, ex=WHISPER_TTL,
        )

        await self._write_shadow(event_id, "inject_system_insight", {
            "insight": insight, "severity": severity,
        })
        try:
            await self._broadcast({
                "type": "whisper",
                "event_id": event_id,
                "severity": severity,
                "insight": insight,
                "timestamp": time.time(),
            })
        except Exception:
            pass
        return f"System insight queued for {event_id} (severity: {severity})"

    # -------------------------------------------------------------------------
    # Session lifecycle
    # -------------------------------------------------------------------------

    async def _create_system_review_event(self, active_ids: list[str]) -> str | None:
        """Create a meta-event for FRIDAY to triage during idle."""
        existing = await self._blackboard.find_active_event_by_source("jarvis")
        if existing:
            self._active_meta_event_id = existing
            return None

        import re
        _DEFER_DELAY_RE = re.compile(r"Deferring event for (\d+)s:")

        summary_lines = []
        for eid in active_ids[:10]:
            event = await self._blackboard.get_event(eid)
            if not event:
                continue
            defer_count = 0
            defer_total_s = 0
            for t in event.conversation:
                if t.action == "defer":
                    defer_count += 1
                    m = _DEFER_DELAY_RE.match(t.thoughts or "")
                    defer_total_s += int(m.group(1)) if m else 300
            elapsed = int((time.time() - event.queued_at) / 60) if event.queued_at else 0
            last_defer = next(
                (t.thoughts for t in reversed(event.conversation) if t.action == "defer"), ""
            )
            summary_lines.append(
                f"- {eid}: phase={event.brain_phase}, status={event.status.value}, "
                f"age={elapsed}m, defers={defer_count}, defer_total={defer_total_s // 60}m, "
                f"reason: {(last_defer or '')[:80]}"
            )

        display_text = (
            f"System review: {len(active_ids)} events active, all idle.\n\n"
            + "\n".join(summary_lines)
            + "\n\nAssess system health. Are any events stuck, looping, or showing friction?"
        )

        from ..models import EventEvidence
        event_id = await self._blackboard.create_event(
            source="jarvis",
            service="system",
            reason="Periodic system health review during idle",
            evidence=EventEvidence(
                display_text=display_text,
                source_type="jarvis",
                domain="complicated",
                severity="info",
                domain_confidence="assessed",
            ),
            subject_type="system",
        )
        self._active_meta_event_id = event_id
        logger.info("JARVIS created system_review event: %s", event_id)
        return event_id

    async def _idle_watchdog(self) -> None:
        """Two paths: meta-event (events active) or shift-end (no events)."""
        while self._running and self._session:
            await asyncio.sleep(60)
            idle_threshold = int(os.getenv("SYSTEM2_IDLE_SECONDS", "120"))
            if not self._last_pulse_time or (time.time() - self._last_pulse_time) <= idle_threshold:
                continue

            try:
                active_ids = await self._blackboard.get_active_events()
            except Exception as e:
                logger.warning("get_active_events failed (retrying next cycle): %s", e)
                continue

            if not active_ids:
                # --- SHIFT END: no events, clock out ---
                logger.info("Cortex idle + 0 active events -- shift end")
                try:
                    if self._session_report_enabled:
                        await self._generate_session_report()
                except Exception as e:
                    logger.warning("Shift-end report failed (non-fatal): %s", e)
                finally:
                    await self._close_session()
                break

            # --- META-EVENT: challenge FRIDAY during idle ---
            if self._active_meta_event_id:
                continue

            logger.info("Cortex idle 5min + %d active events -- creating system review", len(active_ids))
            await self._create_system_review_event(active_ids)

    async def _generate_session_report(self) -> None:
        """Wrapper: generate report on self._session. Manages _generating_report flag."""
        if not self._session:
            return
        self._generating_report = True
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        try:
            await self._generate_session_report_on(self._session)
        finally:
            self._generating_report = False

    async def _generate_session_report_on(self, session: object) -> None:
        """Generate report on a specific session (may differ from self._session during handoff)."""
        report = ""
        try:
            await session.send(input=SESSION_REPORT_PROMPT, end_of_turn=True)
            parts: list[str] = []
            async with asyncio.timeout(45):
                async for msg in session.receive():
                    if hasattr(msg, "text") and msg.text:
                        parts.append(msg.text)
                    if hasattr(msg, "server_content") and getattr(
                        msg.server_content, "turn_complete", False
                    ):
                        break
            report = "".join(parts).strip()
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            logger.warning("Session report timed out (45s)")
        except Exception as e:
            logger.warning("Session report generation failed: %s", e)

        if not report or report.lower().startswith("no significant"):
            logger.info("Session report: nothing noteworthy")
            return

        logger.info("Session report generated (%d chars)", len(report))
        try:
            await self._broadcast({
                "type": "cortex_session_report",
                "report": report[:2000],
                "timestamp": time.time(),
            })
        except Exception:
            pass
        await self._process_session_report(report)

    async def _process_session_report(self, report: str) -> None:
        """Pipe session report through Archivist extraction pipeline."""
        try:
            async with asyncio.timeout(120):
                result = await self._archivist.extract_lessons(
                    document=report[:50_000],
                    context_notes="Auto-generated session observation report from Cortex (System 2). "
                                 "Lessons should be stored as channel=experience (self-learned, 0.6x trust).",
                )
                if "error" in result:
                    logger.warning("Session report extraction failed: %s", result["error"])
                    return

                lessons = result.get("lessons", [])
                corrections = result.get("corrections", [])

                stored = 0
                for lesson in lessons:
                    if not lesson.get("title") or not lesson.get("pattern"):
                        continue
                    lid = await self._archivist.store_lesson(
                        title=lesson.get("title", ""),
                        pattern=lesson.get("pattern", ""),
                        anti_pattern=lesson.get("anti_pattern", ""),
                        keywords=lesson.get("keywords", []),
                        event_references=lesson.get("event_references", []),
                        channel="experience",
                    )
                    if lid:
                        stored += 1

                corrected = 0
                for c in corrections:
                    ok = await self._archivist.correct_memory(
                        event_id=c.get("event_id", ""),
                        corrected_root_cause=c.get("corrected_root_cause", ""),
                        corrected_fix_action=c.get("corrected_fix_action", ""),
                        correction_note=c.get("correction_note", "Cortex session report"),
                    )
                    if ok:
                        corrected += 1

                logger.info(
                    "Session report processed: %d/%d lessons stored (experience), "
                    "%d/%d corrections applied",
                    stored, len(lessons), corrected, len(corrections),
                )
        except asyncio.CancelledError:
            raise
        except TimeoutError:
            logger.warning("Session report processing timed out (120s, non-fatal)")
        except Exception as e:
            logger.warning("Session report processing failed (non-fatal): %s", e)

    async def _cleanup_session_state(self) -> None:
        """Shared session teardown: cancel receive, close ctx, reset state, broadcast."""
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self._session:
            try:
                ctx = getattr(self, "_session_ctx", None)
                if ctx:
                    await ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._session = None
            self._session_ctx = None
        self._seen_neurons.clear()
        self._text_buffer.clear()
        self._last_was_watching = False
        self._last_status_broadcast = 0
        self._generating_report = False
        self._active_meta_event_id = None
        try:
            await self._broadcast({
                "type": "cortex_status",
                "status": "disconnected",
                "model": self._model,
                "shadow": self._shadow,
                "timestamp": time.time(),
            })
        except Exception:
            pass

    async def _close_session(self) -> None:
        """Close session from within _idle_watchdog (avoids self-await deadlock)."""
        await self._cleanup_session_state()
        logger.info("Cortex session closed (idle)")

    async def _try_reconnect(self) -> None:
        """Fast reconnect if recent pulse activity, otherwise stay idle."""
        if not self._running or self._generating_report:
            return
        self._session = None
        if self._last_pulse_time and (time.time() - self._last_pulse_time) < 300:
            for delay in (5, 15, 30):
                await asyncio.sleep(delay)
                if not self._running:
                    return
                try:
                    await self._connect()
                    if self._session:
                        return
                except Exception as e:
                    logger.warning("Cortex reconnect failed: %s", e)
        logger.info("Cortex: no recent activity, staying idle until next pulse")

    async def _rotate_session(self) -> None:
        """Ask for summary, close, reconnect with summary as first turn."""
        if not self._session:
            return
        try:
            await self._session.send(
                input="Summarize your current observations about all active events. "
                      "This summary will be carried forward into a fresh session.",
                end_of_turn=True,
            )
            summary_parts = []
            async for msg in self._session.receive():
                if hasattr(msg, "text") and msg.text:
                    summary_parts.append(msg.text)
                if hasattr(msg, "server_content") and getattr(
                    msg.server_content, "turn_complete", False
                ):
                    break
            summary = "".join(summary_parts)
        except Exception as e:
            logger.warning("Cortex rotation summary failed: %s", e)
            summary = "(session rotated, previous context unavailable)"

        await self._disconnect()
        await self._connect()

        if self._session and summary:
            try:
                await self._session.send(
                    input=f"[SESSION RESUMED] Previous session summary:\n{summary}",
                    end_of_turn=True,
                )
            except Exception as e:
                logger.debug("Cortex summary injection failed: %s", e)
