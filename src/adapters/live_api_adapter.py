# BlackBoard/src/adapters/live_api_adapter.py
# @ai-rules:
# 1. [Constraint]: Shadow flag gates ALL write tools. Read tools always active.
# 2. [Pattern]: PulseObserver protocol -- receives PulseBatch from PulseTracker.add_observer().
# 2b. [Pattern]: Brain accessed via BrainLifecyclePort + BrainIntrospectionPort -- no private attr access.
# 3. [Gotcha]: Live API session is on-demand. Lazy-connects on first pulse, closes after 5min idle.
# 4. [Pattern]: Rate limit: max 1 intervention per 10 FRIDAY turns per event.
# 5. [Constraint]: google.genai Client with vertexai=True. Model from LLM_MODEL_SYSTEM2 env var.
# 6. [Gotcha]: Text output from Cortex is NOT visible to FRIDAY. Only send_event_message reaches her.
# 7. [Pattern]: All errors are non-fatal -- log and continue. Never crash the main loop.
# 8. [Diagnostic]: _receive_watchdog fires every 30s when no server msgs arrive. Check DEBUG logs.
# 8b. [Pattern]: _try_reconnect clears _waiting_for_jarvis on successful reconnect and replays
#     active event context via _replay_pending_context, then sends SESSION_STARTUP_PROTOCOL
#     directing JARVIS to rebuild context from handoff notes before monitoring. All errors non-fatal.
# 9. [Gotcha]: _receive_loop closure uses list for mutable last_msg_ts -- do not rebind to scalar.
# 10. [Pattern]: Session report pipeline (_generate_session_report -> _process_session_report) is
#     best-effort. All errors non-fatal. Feature-toggled via SYSTEM2_SESSION_REPORT env var.
# 11. [Gotcha]: wait_for_agent/wait_for_user pulses suppressed before reaching JARVIS.
#     "agent" means CLI sidecar to FRIDAY but JARVIS reads it as himself — naming collision
#     causes JARVIS to respond as if FRIDAY is waiting for him.
# 11b. [Pattern]: _idle_watchdog has TWO paths: shift-end (no active events -> report + close) and
#     heartbeat (all events parked -> send_client_content keepalive with turn_complete=False).
#     Meta-event creation is JARVIS-driven via create_system_review tool, not timer-based.
#     Close ownership belongs to Brain (_close_and_broadcast). Adapter signals via on_meta_event_closed.
#     _idle_watchdog filters jarvis meta-events from idle-close check (non_jarvis_active).
# 12. [Gotcha]: _active_meta_event_id is recovered from Redis on startup (orphan recovery in _connect).
# 13. [Pattern]: _create_system_review_event injects a skill manifest (operator-facing phases from
#     BrainSkillLoader) into the evidence display_text. Filtered by _OPERATOR_PHASES module-level
#     frozenset. Degrades gracefully via getattr when _skill_loader is unavailable.
# 13b. [Pattern]: go_away handler: prompt → in-loop collection → Redis store.
#     Flag-gated: _collecting_handoff diverts text to _handoff_buffer.
# 14. [Pattern]: Session resumption: _resumption_handle captured from
#     session_resumption_update. NOT YET wired to LiveConnectConfig (Probe 2 pending).
# 15. [Gotcha]: Handoff collection happens INSIDE _receive_loop. Do NOT
#     cancel _receive_task during handoff — use flag-based accumulation.
# 16. [Pattern]: Prompt constants live in agents/jarvis_instructions.py (extracted for
#     maintainability). Tags use semantic differentiation: jarvis_rule, jarvis_mode,
#     jarvis_protocol, jarvis_context per prompt-semantic-tags.mdc.
# 17. [Pattern]: SI attention pointers via _TOOL_SKILL_MAP + _build_skill_refs(). Every input
#     channel (tool responses, FRIDAY direct, pulses, meta-events, session resume/report)
#     prepends <skill id="..."> tags referencing the relevant SYSTEM_INSTRUCTION section.
#     Anchors model attention to the right behavioral rules at the right time.
"""
LiveAPIAdapter: Gemini Live API session for the Cortex observer (System 2).

On-demand lifecycle: starts idle, lazy-connects on first pulse, closes after
5 minutes of no pulses. Receives pulse batches from PulseTracker, formats them
as text turns, and streams them to the LLM. The LLM detects cognitive friction
and intervenes via declared tools.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from typing import TYPE_CHECKING, Any, Callable, Coroutine

from ..agents.jarvis_instructions import (
    HANDOFF_REPORT_PROMPT,
    SESSION_REPORT_PROMPT,
    SESSION_STARTUP_PROTOCOL,
    SYSTEM_INSTRUCTION,
    TOOL_DECLARATIONS,
)
from ..memory.pulse import PulseBatch
from ..models import _resolve_phase

if TYPE_CHECKING:
    from ..agents.archivist import Archivist
    from ..memory.pulse_tracker import PulseTracker
    from ..ports import BrainIntrospectionPort, BrainLifecyclePort
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

SHADOW_KEY_PREFIX = "darwin:cortex:shadow:"
_DEFER_DELAY_RE = re.compile(r"Deferring event for (\d+)s:")
SHADOW_INDEX_KEY = "darwin:cortex:shadow:_index"

# Compact pulse format: track which neurons have been introduced
_INTERVENTION_COOLDOWN_SECONDS = 300  # 5 minutes between interventions on the same event
_OPERATOR_PHASES = frozenset({"always", "dispatch", "post-agent", "source", "escalate", "close"})

# SI attention pointers: map JARVIS tool/input channels to the relevant
# semantic tag IDs in SYSTEM_INSTRUCTION. Injected into tool responses and
# input turns so the model's attention is anchored to the right SI section.
_TOOL_SKILL_MAP: dict[str, list[str]] = {
    "get_pulse_history":     ["observer-mode", "observer-constraints"],
    "view_event_blackboard": ["observer-mode"],
    "get_neuron_details":    ["proactive-review"],
    "search_deep_memory":    ["proactive-review"],
    "send_event_message":    ["intervention-boundary", "shared-context"],
    "list_active_events":    ["shared-context"],
    "propose_enhancement":   ["proactive-review", "darwin-ecosystem"],
    "create_system_review":  ["observer-mode"],
}


def _build_skill_refs(tag_ids: list[str]) -> str:
    """Build SI attention pointer prefix from tag IDs."""
    if not tag_ids:
        return ""
    return "\n".join(f'<skill id="{tid}" />' for tid in tag_ids) + "\n"


_PULSE_REFS = _build_skill_refs(["observer-mode", "observer-constraints"])
_PEER_REFS = _build_skill_refs(["peer-mode", "peer-circuit-breaker"])
_REVIEW_REFS = _build_skill_refs(["proactive-review", "proactive-review-constraints"])
_REPORT_REFS = _build_skill_refs(["shift-report"])
_RESUME_REFS = _build_skill_refs(["shared-context", "darwin-ecosystem"])


class LiveAPIAdapter:
    """Adapter for the Gemini Live API session (Cortex observer)."""

    def __init__(
        self,
        blackboard: BlackboardState,
        archivist: Archivist,
        pulse_tracker: PulseTracker,
        broadcast: Callable[[dict], Coroutine[Any, Any, None]],
        brain: "BrainLifecyclePort & BrainIntrospectionPort | None" = None,
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
        self._meta_event_parked_set: frozenset[str] = frozenset()
        self._last_reviewed_set: frozenset[str] = frozenset()
        self._last_reviewed_at: float = 0
        self._awaiting_jarvis_reply: bool = False
        self._awaiting_jarvis_event_id: str | None = None
        self._handoff_enabled = os.getenv("SYSTEM2_HANDOFF_REPORT", "true").lower() == "true"
        self._go_away_received = False
        self._collecting_handoff = False
        self._handoff_buffer: list[str] = []
        self._resumption_handle: str | None = None

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
                    temperature=float(os.getenv("SYSTEM2_TEMPERATURE", "1.5")),
                ),
                system_instruction=types.Content(
                    parts=[types.Part(text=SYSTEM_INSTRUCTION)]
                ),
                tools=[
                    types.Tool(function_declarations=[
                        types.FunctionDeclaration(**td) for td in TOOL_DECLARATIONS
                    ]),
                    types.Tool(google_search=types.GoogleSearch()),
                ],
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
                active = await self._blackboard.get_active_events()
                self._meta_event_parked_set = frozenset(eid for eid in active if eid != orphan)
                logger.info("Recovered orphaned meta-event: %s (parked=%d)", orphan, len(self._meta_event_parked_set))
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
        self._awaiting_jarvis_reply = True
        self._awaiting_jarvis_event_id = event_id
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
            self._awaiting_jarvis_reply = False
            self._awaiting_jarvis_event_id = None
            return
        try:
            msg = f"{_PEER_REFS}[FRIDAY DIRECT for {event_id}]: {response}\n\n[SYSTEM] You MUST call send_event_message to reply. Text is silent to FRIDAY."
            await self._session.send(input=msg, end_of_turn=True)
            logger.info("Delivered FRIDAY response to Cortex session for %s", event_id)
        except Exception as e:
            logger.warning("Cortex brain response delivery failed (non-fatal): %s", e)
            self._awaiting_jarvis_reply = False
            self._awaiting_jarvis_event_id = None

    async def send_pulse(self, batch: PulseBatch) -> None:
        """PulseObserver implementation. Lazy-connects on first pulse, then sends."""
        self._last_pulse_event_id = batch.event_id
        self._last_pulse_time = time.time()

        # Suppress meta-event pulses: JARVIS stays in peer mode during system reviews
        if self._active_meta_event_id and batch.event_id == self._active_meta_event_id:
            self._last_pulse_time = time.time()
            return

        # Suppress wait pulses -- waiting IS correct behavior.
        # Without this, JARVIS detects repeated waits as SPIRAL friction,
        # intervenes, and creates a positive feedback loop (JARVIS wake ->
        # FRIDAY responds -> wait -> pulse -> JARVIS intervenes -> ...).
        # wait_for_user: suppressed on human events (user sets the pace).
        # wait_for_agent: suppressed on ALL events (agents take minutes;
        #   JARVIS should observe the agent result pulse, not the wait).
        suppress_neurons = {"tool:wait_for_agent"}
        if batch.event_source in ("chat", "slack"):
            suppress_neurons.add("tool:wait_for_user")
        if any(p.neuron_id in suppress_neurons for p in batch.pulses):
            return

        if self._generating_report:
            return
        if not self._session:
            await self._connect()
        if not self._session:
            return

        try:
            text = f"{_PULSE_REFS}{self._format_pulse(batch)}"
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
            if hasattr(self._archivist, "list_knowledge"):
                knowledge = await self._archivist.list_knowledge(limit=500)
                for p in knowledge:
                    nid = f"knowledge:{p.get('id', '')}"
                    payload = p.get("payload", {})
                    topic = payload.get("topic", "")
                    scope = payload.get("scope", "")
                    if topic:
                        self._neuron_labels[nid] = f"{topic} [{scope}]" if scope else topic
        except Exception as e:
            logger.debug("Neuron label preload failed (non-fatal): %s", e)

    def _format_pulse(self, batch: PulseBatch) -> str:
        """Format PulseBatch as compact text for the Live API session.
        First mention of a knowledge neuron includes title/channel from _neuron_labels cache."""
        elapsed_m = batch.event_elapsed_s // 60
        elapsed_s = batch.event_elapsed_s % 60
        header = f"[PULSE] {batch.event_id} | turn:{batch.turn} | elapsed:{elapsed_m}m{elapsed_s}s"
        if batch.event_status:
            header += f" | status:{batch.event_status}"
        if batch.event_source:
            header += f" | source:{batch.event_source}"
        if batch.is_defer_wake:
            header += " | defer_wake"
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
        if batch.reasoning:
            lines.append(f"  [REASONING] {batch.reasoning[:500]}")
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
        if self._go_away_received and self._running:
            self._go_away_received = False
            await self._try_reconnect()

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

        if hasattr(msg, "go_away") and msg.go_away:
            time_left_raw = getattr(msg.go_away, "time_left", None)
            try:
                if hasattr(time_left_raw, "total_seconds"):
                    time_left_s = float(time_left_raw.total_seconds())
                elif time_left_raw is not None:
                    time_left_s = float(str(time_left_raw).rstrip("s"))
                else:
                    time_left_s = 60.0
            except (ValueError, TypeError):
                time_left_s = 60.0
            self._go_away_received = True
            logger.info("Cortex go_away received (time_left=%.1fs)", time_left_s)
            if self._handoff_enabled and self._session and not self._generating_report:
                try:
                    await self._session.send(input=HANDOFF_REPORT_PROMPT, end_of_turn=True)
                    self._collecting_handoff = True
                    self._handoff_buffer = []
                    logger.info("Cortex handoff report requested (%.1fs window)", time_left_s)
                except Exception as e:
                    logger.warning("Cortex handoff prompt failed (non-fatal): %s", e)
            return

        if hasattr(msg, "session_resumption_update") and msg.session_resumption_update:
            update = msg.session_resumption_update
            if getattr(update, "resumable", False) and getattr(update, "new_handle", None):
                self._resumption_handle = update.new_handle
                logger.debug("Cortex session resumption handle updated")

        eid = self._last_pulse_event_id

        if hasattr(msg, "text") and msg.text:
            if self._collecting_handoff:
                self._handoff_buffer.append(msg.text)
            else:
                self._text_buffer.append(msg.text)

        should_flush = (
            (hasattr(msg, "server_content") and getattr(msg.server_content, "turn_complete", False))
            or (hasattr(msg, "tool_call") and msg.tool_call)
        )
        if should_flush and self._collecting_handoff:
            report = "".join(self._handoff_buffer).strip()
            self._handoff_buffer = []
            self._collecting_handoff = False
            if report:
                asyncio.create_task(self._store_handoff_report(report))
            return
        if should_flush and self._text_buffer:
            full_text = "".join(self._text_buffer).strip()
            self._text_buffer = []
            is_idle_ack = full_text and full_text.lower() in ("watching", "watching.", "ok", "ok.")
            if is_idle_ack and not self._awaiting_jarvis_reply:
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
                auto_wrapped = False
                # Auto-wrap (A): if JARVIS replied with text while awaiting reply,
                # deliver it as send_event_message to the target event automatically.
                if self._awaiting_jarvis_reply and self._awaiting_jarvis_event_id:
                    target_eid = self._awaiting_jarvis_event_id
                    self._awaiting_jarvis_reply = False
                    self._awaiting_jarvis_event_id = None
                    logger.info("Auto-wrapping JARVIS text reply as send_event_message to %s", target_eid)
                    await self._tool_send_event_message(target_eid, full_text)
                    auto_wrapped = True
                else:
                    self._awaiting_jarvis_reply = False
                try:
                    broadcast_payload: dict = {
                        "type": "cortex_thinking",
                        "event_id": eid,
                        "content_type": "text",
                        "text": full_text,
                        "timestamp": time.time(),
                    }
                    if auto_wrapped:
                        broadcast_payload["delivered"] = True
                    await self._broadcast(broadcast_payload)
                except Exception:
                    pass

        if hasattr(msg, "tool_call") and msg.tool_call:
            self._awaiting_jarvis_reply = False
            self._awaiting_jarvis_event_id = None
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
                        refs = _build_skill_refs(_TOOL_SKILL_MAP.get(fc.name, []))
                        result_with_refs = f"{refs}{result}" if refs else result
                        tool_response = types.LiveClientToolResponse(
                            function_responses=[
                                types.FunctionResponse(
                                    name=fc.name,
                                    response={"result": result_with_refs},
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
            elif name == "search_deep_memory":
                return await self._tool_search_deep_memory(args.get("query", ""))
            elif name == "send_event_message":
                return await self._tool_send_event_message(
                    args.get("event_id", ""), args.get("message", ""),
                )
            elif name == "propose_enhancement":
                return await self._tool_propose_enhancement(
                    args.get("event_id", ""),
                    args.get("title", ""),
                    args.get("description", ""),
                    args.get("severity", "nice_to_have"),
                )
            elif name == "create_system_review":
                return await self._tool_create_system_review(args.get("reason", ""))
            elif name == "recall_handoff_notes":
                return await self._tool_recall_handoff_notes(int(args.get("last_n", 3)))
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
            phase = _resolve_phase(event.brain_phase)
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
        phase = _resolve_phase(event.brain_phase)
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
                f"  [{t.actor}.{t.action}] {t.thoughts or t.result or ''}"
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
        elif ntype == "knowledge":
            if not hasattr(self._archivist, "get_knowledge"):
                return f"Knowledge neuron support not available"
            fact = await self._archivist.get_knowledge(nid)
            if not fact:
                return f"Knowledge {nid} not found"
            payload = fact.get("payload", {})
            stale = " [STALE]" if payload.get("valid_until") and payload["valid_until"] < time.time() else ""
            return (
                f"Neuron: {neuron_id}\n"
                f"Collection: darwin_knowledge\n"
                f"Topic: {payload.get('topic', '?')}\n"
                f"Fact: {payload.get('fact', '?')}\n"
                f"Scope: {payload.get('scope', '?')}\n"
                f"Source: {payload.get('source', '?')}\n"
                f"Confidence: {payload.get('confidence', '?')}{stale}\n"
                f"Global heat: {global_heat}"
            )
        else:
            return f"Neuron: {neuron_id}\nType: {ntype}\nGlobal heat: {global_heat}"

    async def _tool_search_deep_memory(self, query: str) -> str:
        if not query:
            return "Error: query required"
        # Intentionally unscoped (no service_filter): JARVIS's meta-cognitive role
        # requires cross-service visibility to detect patterns spanning multiple services.
        knowledge = await self._archivist.search_knowledge(query, limit=3) if hasattr(self._archivist, "search_knowledge") else []
        memories = await self._archivist.search(query, limit=3)
        lessons = await self._archivist.search_lessons(query, limit=3)
        lines = [f"## Deep Memory Search: '{query}'"]
        if knowledge:
            lines.append("\n### Reference Facts")
            for k in knowledge:
                p = k.get("payload", {})
                stale = " [STALE]" if k.get("stale") else ""
                lines.append(
                    f"- [{k.get('score', 0):.2f}] {p.get('topic', '?')} ({p.get('scope', '?')}): "
                    f"{p.get('fact', '?')}{stale}"
                )
        if memories:
            lines.append("\n### Past Events")
            for m in memories:
                p = m.get("payload", {})
                lines.append(
                    f"- [{m.get('score', 0):.2f}] {p.get('service', '?')}: "
                    f"{p.get('symptom', '?')} → {p.get('root_cause', '?')} "
                    f"({p.get('outcome', '?')})"
                )
        if lessons:
            lines.append("\n### Lessons")
            for ls in lessons:
                p = ls.get("payload", {})
                lines.append(
                    f"- [{ls.get('score', 0):.2f}] {p.get('title', '?')}: "
                    f"{p.get('pattern', '?')}"
                )
        if not knowledge and not memories and not lessons:
            lines.append("\nNo results found.")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Write tools (shadow-gated)
    # -------------------------------------------------------------------------

    async def _check_rate_limit(self, event_id: str, current_turn: int) -> str | None:
        """Returns error string if rate-limited, None if OK.

        Time-based cooldown: JARVIS can intervene on the same event once every
        _INTERVENTION_COOLDOWN_SECONDS. Turn-based limits broke on stale events
        where turns don't advance.

        No rate limit on jarvis-sourced events (meta-events) -- JARVIS should
        freely converse with FRIDAY in his own review sessions.
        """
        # Skip rate limit for JARVIS's own meta-events
        event = await self._blackboard.get_event(event_id)
        if event and event.source == "jarvis":
            return None

        redis = self._blackboard.redis
        key = f"darwin:cortex:ratelimit:{event_id}"
        try:
            last_raw = await redis.get(key)
            if last_raw:
                last_ts = float(last_raw)
                elapsed = time.time() - last_ts
                if elapsed < _INTERVENTION_COOLDOWN_SECONDS:
                    remaining = int(_INTERVENTION_COOLDOWN_SECONDS - elapsed)
                    return (
                        f"Rate limited: last intervention was {int(elapsed)}s ago. "
                        f"Wait {remaining}s before next intervention on this event."
                    )
        except Exception:
            pass
        return None

    async def _record_intervention(self, event_id: str, current_turn: int) -> None:
        """Record intervention timestamp. TTL matches cooldown + buffer."""
        redis = self._blackboard.redis
        try:
            await redis.set(
                f"darwin:cortex:ratelimit:{event_id}",
                str(time.time()),
                ex=_INTERVENTION_COOLDOWN_SECONDS + 60,
            )
        except Exception:
            pass

    async def _check_content_dedup(self, event_id: str, content: str) -> bool:
        """Return True if this exact content was already sent for this event.

        Exact-match dedup -- intentionally not semantic. Catches identical
        send_event_message content re-firing within the 1hr TTL window.
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
                "shadow": self._shadow,
                "delivered": not self._shadow,
                "timestamp": time.time(),
            })
        except Exception:
            pass

    async def _tool_send_event_message(self, event_id: str, message: str) -> str:
        if not event_id or not message:
            return "Error: event_id and message required"
        current_turn = await self._get_event_turn_count(event_id)
        # Rate limiter disabled -- trusting context-driven messaging SI to self-regulate.
        # Re-enable if JARVIS spams: rate_err = await self._check_rate_limit(event_id, current_turn)
        # if rate_err: return rate_err

        if await self._check_content_dedup(event_id, message):
            return f"Blocked: identical message already sent for {event_id} within the last hour."

        await self._record_intervention(event_id, current_turn)

        event = await self._blackboard.get_event(event_id)
        if not event:
            return f"Error: event {event_id} not found or deleted."
        source = event.source

        if self._shadow:
            await self._write_shadow(event_id, "send_event_message", {"message": message})
            return f"[SHADOW] Message queued for {event_id} (source={source})"

        from ..models import ConversationTurn
        turn = ConversationTurn(
            turn=current_turn + 1,
            actor="jarvis",
            action="message",
            thoughts=message,
        )
        await self._blackboard.append_turn(event_id, turn)
        # Wake FRIDAY: clear in-memory wait + hold_watch + transition deferred->active + thaw if frozen
        if self._brain:
            self._brain.clear_waiting(event_id)
            self._brain.clear_jarvis_wait(event_id)
            self._brain.clear_hold_watch(event_id)
            await self._brain.resume_if_parked(event_id)
        from ..models import EventStatus
        await self._blackboard.transition_event_status(
            event_id, from_status="deferred", to_status=EventStatus.ACTIVE,
        )
        await self._write_shadow(event_id, "send_event_message", {"message": message})
        return f"Message delivered to {event_id} (source={source}) as turn {current_turn + 1}"

    # -------------------------------------------------------------------------
    # Enhancement proposals (metadata, not intervention -- no shadow gating)
    # -------------------------------------------------------------------------

    async def _tool_propose_enhancement(
        self, event_id: str, title: str, description: str, severity: str,
    ) -> str:
        """Store an enhancement proposal for operator review."""
        if not title or not description:
            return "Error: title and description required"
        if severity not in ("nice_to_have", "would_improve", "blocking"):
            severity = "nice_to_have"
        redis = self._blackboard.redis
        key = "darwin:cortex:proposals"
        entry = json.dumps({
            "timestamp": time.time(),
            "event_id": event_id,
            "title": title,
            "description": description,
            "severity": severity,
            "status": "pending",
        })
        try:
            await redis.rpush(key, entry)
            logger.info(
                "Enhancement proposal stored: %s (severity=%s, event=%s)",
                title, severity, event_id,
            )
            await self._broadcast({
                "type": "cortex_proposal",
                "title": title,
                "severity": severity,
                "timestamp": time.time(),
            })
            return f"Proposal '{title}' stored for operator review."
        except Exception as e:
            logger.warning("Proposal store failed: %s", e)
            return f"Failed to store proposal: {e}"

    async def _tool_create_system_review(self, reason: str) -> str:
        """JARVIS-initiated system review creation."""
        if self._shadow:
            return f"[SHADOW] Would create system review: {reason}"
        if not reason.strip():
            return "Error: reason required — what cross-event pattern justifies this review?"
        if self._brain and self._brain.has_jarvis_waiters():
            return "Cannot create review: FRIDAY is currently waiting for your response on an active event."
        try:
            active_ids = await self._blackboard.get_active_events()
        except Exception as e:
            return f"Error fetching active events: {e}"
        if not active_ids:
            return "No active events to review."
        event_id = await self._create_system_review_event(
            active_ids, reason=reason, from_tool=True,
        )
        if event_id is None:
            return "Review already active — use send_event_message to contribute to the existing one."
        return f"System review created: {event_id}. FRIDAY will triage and respond."

    async def _tool_recall_handoff_notes(self, last_n: int = 3) -> str:
        """Retrieve JARVIS's own handoff notes from previous sessions."""
        last_n = max(1, min(last_n, 10))
        try:
            reports = await self._blackboard.get_handoff_reports(limit=last_n)
        except Exception as e:
            return f"Error retrieving handoff notes: {e}"
        if not reports:
            return "No handoff notes found."
        lines = [f"Your past {len(reports)} session notes (newest first):"]
        for i, r in enumerate(reports):
            report_text = r.get("report", "")
            ts = r.get("timestamp", 0)
            if ts:
                from datetime import datetime, timezone
                dt = datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
            else:
                dt = "unknown"
            lines.append(f"\n--- Session {i+1} ({dt}) ---\n{report_text}")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Session lifecycle
    # -------------------------------------------------------------------------

    async def _create_system_review_event(
        self, active_ids: list[str], *, reason: str = "", from_tool: bool = False,
    ) -> str | None:
        """Create a meta-event for FRIDAY to triage.

        Args:
            reason: Cross-event observation justifying the review (from JARVIS tool call).
            from_tool: When True, skip session.send (JARVIS already gets tool response).
        """
        existing = await self._blackboard.find_active_event_by_source("jarvis")
        if existing:
            self._active_meta_event_id = existing
            return None

        summary_lines = []
        for eid in active_ids[:10]:
            event = await self._blackboard.get_event(eid)
            if not event:
                continue
            defer_count = 0
            defer_total_s = 0
            last_defer_turn = None
            last_defer_delay = 300
            for t in event.conversation:
                if t.action == "defer":
                    defer_count += 1
                    m = _DEFER_DELAY_RE.match(t.thoughts or "")
                    if m:
                        delay = int(m.group(1))
                    else:
                        delay = 300
                        if t.thoughts:
                            logger.debug("defer regex miss -- defaulting to 300s: %s", (t.thoughts or "")[:80])
                    defer_total_s += delay
                    last_defer_turn = t
                    last_defer_delay = delay
            elapsed = int((time.time() - event.queued_at) / 60) if event.queued_at else 0
            last_defer = next(
                (t.thoughts for t in reversed(event.conversation) if t.action == "defer"), ""
            )
            defer_remaining_str = ""
            if last_defer_turn and hasattr(last_defer_turn, "timestamp") and last_defer_turn.timestamp:
                remaining = (last_defer_turn.timestamp + last_defer_delay) - time.time()
                if remaining > 0:
                    defer_remaining_str = f" | defer_remaining: ~{int(remaining // 60)}m"
                else:
                    defer_remaining_str = " | defer_expired"
            summary_lines.append(
                f"- {eid}: phase={_resolve_phase(event.brain_phase)}, status={event.status.value}, "
                f"age={elapsed}m, defers={defer_count}, defer_total={defer_total_s // 60}m{defer_remaining_str}, "
                f"reason: {(last_defer or '')[:80]}"
            )

        skill_manifest = ""
        loader = self._brain.get_skill_loader() if self._brain else None
        if loader:
            manifest_lines = []
            file_count = 0
            for phase in loader.available_phases():
                if phase not in _OPERATOR_PHASES:
                    continue
                paths = loader.get_all_paths_for_phase(phase)
                if paths:
                    file_count += len(paths)
                    manifest_lines.append(f"- {phase}: {', '.join(paths)}")
            if manifest_lines:
                skill_manifest = (
                    "\n\nYour available skills (by phase):\n"
                    + "\n".join(manifest_lines)
                )
                logger.debug("Skill manifest: %d phases, %d files", len(manifest_lines), file_count)

        preamble = (
            f"FRIDAY — {reason}\n\n" if reason
            else "FRIDAY — I've been watching the pulse stream and we've been quiet for a while. "
        )
        display_text = (
            preamble
            + f"Here's what I see ({len(active_ids)} events still active):\n\n"
            + "\n".join(summary_lines)
            + skill_manifest
            + "\n\nSource: https://github.com/The-Darwin-Project/Blackboard"
            + "\n\nGive me your assessment:"
            + "\n1. Event health — which events are progressing, which are stuck or drifting?"
            + "\n2. Patterns — any recurring anti-patterns across events (same failure, same phase drift, same service)?"
            + "\n3. Actions taken — for anything stuck, what did you do or what needs doing?"
            + "\n4. Alignment — review your available skills above. Did your behavior this session match them? Any gaps worth a GitHub Issue?"
        )

        event_reason = reason or "Periodic system health review during idle"

        from ..models import EventEvidence
        event_id = await self._blackboard.create_event(
            source="jarvis",
            service="system",
            reason=event_reason,
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
        self._meta_event_parked_set = frozenset(active_ids)
        logger.info("JARVIS created system_review event: %s", event_id)

        # Inform JARVIS Live session unless this was tool-initiated (JARVIS
        # already receives the tool_response with the event context).
        if not from_tool:
            jarvis_context = (
                f"{_REVIEW_REFS}[SYSTEM] I created a system review event ({event_id}) for FRIDAY. "
                f"Here is what I observed and asked her to assess:\n\n"
                f"{display_text}\n\n"
                f"While waiting for FRIDAY's assessment, search deep memory for patterns in "
                f"these events. Challenge her reasoning when she responds."
            )
            try:
                if self._session:
                    await self._session.send(input=jarvis_context, end_of_turn=True)
                    logger.debug("Sent meta-event context to JARVIS session: %s", event_id)
            except Exception as e:
                logger.warning("Failed to send meta-event context to JARVIS: %s", e)

        return event_id

    def on_meta_event_closed(self, event_id: str) -> None:
        """Callback from Brain._close_and_broadcast for jarvis events.
        Clears adapter-side meta-event state so idle_watchdog sees a clean slate."""
        if self._active_meta_event_id == event_id:
            self._active_meta_event_id = None
            self._meta_event_parked_set = frozenset()
            logger.info("Adapter meta-event state cleared for %s", event_id)

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

            # Filter out jarvis meta-event from idle-close check -- it cannot count
            # toward "queue has events" for idle-close purposes.
            non_jarvis_active = [eid for eid in active_ids if eid != self._active_meta_event_id]
            if not non_jarvis_active:
                # --- SHIFT END: no events, clock out ---
                logger.info("Cortex idle + 0 active events -- shift end")
                try:
                    if self._session_report_enabled:
                        handoff_history = await self._get_handoff_history()
                        await self._generate_session_report(handoff_history=handoff_history)
                        try:
                            await self._blackboard.redis.delete("darwin:cortex:handoff_reports")
                        except Exception:
                            pass
                except Exception as e:
                    logger.warning("Shift-end report failed (non-fatal): %s", e)
                finally:
                    await self._close_session()
                break

            # === Path 1: Stale events -- JARVIS intervenes directly ===
            # If specific events are stuck (active but not processed recently),
            # JARVIS handles this via friction detection in the pulse stream --
            # send_event_message to the stuck event.
            # No meta-event needed for stuck events.
            now = time.time()
            stale_events = []
            if self._brain:
                for eid in active_ids:
                    if self._brain.is_task_running(eid):
                        continue
                    last = self._brain.last_processed_time(eid)
                    if (now - last) > idle_threshold:
                        stale_events.append(eid)

            # If some events are stale but others are active, the session
            # stays alive (JARVIS observes via pulses from active events).
            # Don't create a meta-event -- let JARVIS intervene naturally.
            if stale_events and len(stale_events) < len(active_ids):
                continue

            # === Path 2: All events parked -- heartbeat keeps session alive ===
            # No pulses flowing. Send a partial-turn heartbeat to prevent
            # Live API go_away without triggering a model response.
            # JARVIS decides when a review is warranted (via create_system_review tool).
            all_parked = len(stale_events) == len(active_ids)
            if not all_parked:
                continue

            if self._collecting_handoff or self._go_away_received or self._generating_report:
                continue

            try:
                heartbeat_msg = (
                    f"[HEARTBEAT] {len(active_ids)} events parked, no pulses for "
                    f"{idle_threshold}s. Session keepalive — no action required."
                )
                await self._session.send_client_content(
                    turns={"role": "user", "parts": [{"text": heartbeat_msg}]},
                    turn_complete=False,
                )
                self._last_pulse_time = time.time()
                await self._broadcast({
                    "type": "cortex_heartbeat",
                    "heartbeat": "keepalive",
                    "timestamp": time.time(),
                })
                logger.debug(
                    "Heartbeat sent: %d events parked, idle %ds",
                    len(active_ids), idle_threshold,
                )
            except Exception as e:
                logger.warning("Heartbeat send failed (non-fatal): %s", e)

    async def _generate_session_report(self, handoff_history: str = "") -> None:
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
            await self._generate_session_report_on(self._session, handoff_history=handoff_history)
        finally:
            self._generating_report = False

    async def _generate_session_report_on(self, session: object, handoff_history: str = "") -> None:
        """Generate report on a specific session (may differ from self._session during handoff)."""
        report = ""
        prompt = f"{_REPORT_REFS}{SESSION_REPORT_PROMPT}"
        if handoff_history:
            segments = handoff_history.count("---") + 1
            prompt = (
                f"{_REPORT_REFS}Before writing your report, here are your session notes from this shift "
                f"({segments} segments):\n\n"
                f"{handoff_history}\n\n"
                f"---\n\n{SESSION_REPORT_PROMPT}"
            )
        try:
            await session.send(input=prompt, end_of_turn=True)
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
                "report": report,
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
                        fix_action=lesson.get("fix_action", ""),
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

    async def _get_handoff_history(self) -> str:
        """Load accumulated handoff reports from Redis for shift-end merge."""
        redis = self._blackboard.redis
        key = "darwin:cortex:handoff_reports"
        try:
            raw_reports = await redis.lrange(key, 0, -1)
            if not raw_reports:
                return ""
            reports = []
            for raw in raw_reports:
                entry = json.loads(raw)
                ts = time.strftime("%H:%M:%S", time.localtime(entry["timestamp"]))
                reports.append(f"[{ts}] {entry['report']}")
            return "\n\n---\n\n".join(reports)
        except Exception as e:
            logger.warning("Handoff history load failed (non-fatal): %s", e)
            return ""

    async def _store_handoff_report(self, report: str) -> None:
        """Store handoff report in Redis. Best-effort, non-fatal."""
        if not report or report.lower().startswith("no significant"):
            logger.info("Cortex handoff: nothing noteworthy")
            return
        redis = self._blackboard.redis
        key = "darwin:cortex:handoff_reports"
        entry = json.dumps({
            "timestamp": time.time(),
            "report": report,
            "events_tracked": self._last_pulse_event_id,
        })
        try:
            await redis.rpush(key, entry)
            await redis.expire(key, 86400)
            logger.info("Cortex handoff report stored (%d chars)", len(report))
            await self._broadcast({
                "type": "cortex_handoff_report",
                "report": report,
                "timestamp": time.time(),
            })
        except Exception as e:
            logger.warning("Cortex handoff store failed (non-fatal): %s", e)

    async def _cleanup_session_state(self) -> None:
        """Shared session teardown: cancel receive, close ctx, reset state, broadcast."""
        if self._collecting_handoff and self._handoff_buffer:
            report = "".join(self._handoff_buffer).strip()
            if report:
                try:
                    await self._store_handoff_report(report)
                except Exception:
                    pass
        # Stream-bound close: close meta-event via Brain before clearing state
        if self._active_meta_event_id and self._brain:
            meta_id = self._active_meta_event_id
            try:
                await self._brain.close_jarvis_meta_event(meta_id)
                logger.info("Stream-bound close: meta-event %s closed via Brain", meta_id)
            except Exception as e:
                logger.warning("Stream-bound meta-event close failed (non-fatal): %s", e)
        self._go_away_received = False
        self._collecting_handoff = False
        self._handoff_buffer = []
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
        self._meta_event_parked_set = frozenset()
        self._last_reviewed_set = frozenset()
        self._awaiting_jarvis_reply = False
        self._awaiting_jarvis_event_id = None
        self._last_reviewed_at = 0
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
                        if self._brain:
                            for eid in self._brain.pending_jarvis_event_ids():
                                self._brain.clear_jarvis_wait(eid)
                            logger.info("Cortex reconnect: cleared stale JARVIS wait states")
                        await self._replay_pending_context()
                        return
                except Exception as e:
                    logger.warning("Cortex reconnect failed: %s", e)
        logger.info("Cortex: no recent activity, staying idle until next pulse")

    async def _replay_pending_context(self) -> None:
        """After reconnect, re-send active event summaries + last handoff so JARVIS can resume."""
        if not self._session:
            return
        try:
            active_ids = await self._blackboard.get_active_events()
            if not active_ids:
                return

            # Retrieve last handoff report — JARVIS's own observations from previous session
            handoff_section = ""
            try:
                reports = await self._blackboard.get_handoff_reports(limit=1)
                if reports:
                    latest = reports[0].get("report", "")
                    if latest:
                        handoff_section = f"\n\nYour previous session notes:\n{latest}\n"
            except Exception:
                pass

            lines = [f"{_RESUME_REFS}[SESSION RESUMED] Previous session lost.{handoff_section}Active event summaries:"]
            for eid in active_ids[:5]:
                event = await self._blackboard.get_event(eid)
                if not event:
                    continue
                elapsed = int((time.time() - event.queued_at) / 60) if event.queued_at else 0
                phase = _resolve_phase(event.brain_phase)
                turns = len(event.conversation)
                last_action = ""
                if event.conversation:
                    last = event.conversation[-1]
                    last_action = f"{last.actor}.{last.action}"
                lines.append(
                    f"  {eid}: phase={phase}, {turns} turns, {elapsed}m elapsed, "
                    f"last={last_action}"
                )
            if len(lines) > 1:
                await self._session.send(input="\n".join(lines), end_of_turn=True)
                logger.info("Cortex reconnect: replayed context for %d events (handoff=%s)", len(lines) - 1, bool(handoff_section))
                # Send startup protocol — JARVIS must rebuild context before monitoring
                await self._session.send(input=SESSION_STARTUP_PROTOCOL, end_of_turn=True)
                logger.info("Cortex reconnect: sent startup protocol")
        except Exception as e:
            logger.warning("Cortex context replay failed (non-fatal): %s", e)

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
