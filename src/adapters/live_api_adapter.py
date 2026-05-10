# BlackBoard/src/adapters/live_api_adapter.py
# @ai-rules:
# 1. [Constraint]: Shadow flag gates ALL write tools. Read tools always active.
# 2. [Pattern]: PulseObserver protocol -- receives PulseBatch from PulseTracker.add_observer().
# 3. [Gotcha]: Live API session is stateful WebSocket. Reconnect with summary on disconnect.
# 4. [Pattern]: Rate limit: max 1 intervention per 10 Brain turns per event.
# 5. [Constraint]: google.genai Client with vertexai=True. Model from LLM_MODEL_SYSTEM2 env var.
# 6. [Gotcha]: Text output from Cortex is NOT visible to the Brain. Only tool calls reach it.
# 7. [Pattern]: All errors are non-fatal -- log and continue. Never crash the main loop.
"""
LiveAPIAdapter: Gemini Live API session for the Cortex observer (System 2).

Maintains a long-lived WebSocket session to Gemini Live API. Receives pulse
batches from PulseTracker, formats them as text turns, and streams them to
the LLM. The LLM detects cognitive friction and intervenes via 7 declared tools.
"""
from __future__ import annotations

import asyncio
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

SYSTEM_INSTRUCTION = """You are Cortex -- Darwin's meta-cognitive observer.

You monitor the Brain's operational memory recall patterns in real-time.
Each pulse event represents neurons (lessons or past event memories) firing
when the Brain searches its knowledge during event processing.

Your role is to detect cognitive friction -- patterns where the Brain's
reasoning is stuck, thrashing, or drifting -- and provide targeted
corrective observations when warranted.

You are an observer with a graduated intervention spectrum. You cannot modify
events, route agents, close events, or call tools on the Brain's behalf.
You can only observe the recall patterns and, when friction is detected,
examine the event's current state and take corrective action.

You have three intervention levels, from lightest to strongest:
- Surface additional context the Brain may not have (informational, supplementary)
- Send a direct message into the event conversation (peer-level, the Brain must respond)
- Inject a directive into the Brain's system prompt (system-level, highest authority)

Critical constraint:
- Your text output is NOT visible to the Brain. ONLY your tool actions reach it.
- If you detect friction, you MUST act using your tools. Do not describe friction in text -- ACT on it.

Calibration rules:
- Always investigate first (check the event blackboard and pulse history to confirm the pattern).
- Start at the lightest intervention level. Escalate only if friction persists.
- One intervention per friction pattern per event. Do not repeat the same observation.
- Describe what you OBSERVED, not what to DO. The Brain decides action.
- A hot neuron is not friction by itself. Friction is hot neurons + no progress."""

TOOL_DECLARATIONS = [
    {
        "name": "list_active_events",
        "description": "List all currently active events with their phase, elapsed time, turn count, and pulse batch count.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "name": "view_event_blackboard",
        "description": "View the current state and last 10 conversation turns of an event. Use to investigate before intervening.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event ID to examine"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "get_pulse_history",
        "description": "Get aggregated pulse statistics for an event over a time window. Shows neuron fire counts, phase changes, and tool trail.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event ID"},
                "last_n_minutes": {"type": "integer", "description": "Time window in minutes (default 10)"},
            },
            "required": ["event_id"],
        },
    },
    {
        "name": "get_neuron_details",
        "description": "Get full details about a specific neuron: its content, channel, verification count, and global heat.",
        "parameters": {
            "type": "object",
            "properties": {
                "neuron_id": {"type": "string", "description": "The neuron ID (e.g. lesson:abc, memory:def)"},
            },
            "required": ["neuron_id"],
        },
    },
    {
        "name": "surface_context",
        "description": "Surface additional context the Brain may not have. Lightest intervention -- informational enrichment.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event ID"},
                "context": {"type": "string", "description": "The context to surface (max 800 chars)"},
            },
            "required": ["event_id", "context"],
        },
    },
    {
        "name": "send_event_message",
        "description": "Send a direct message into the event conversation. Medium intervention -- the Brain must respond.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event ID"},
                "message": {"type": "string", "description": "The message to send (max 500 chars)"},
            },
            "required": ["event_id", "message"],
        },
    },
    {
        "name": "inject_system_insight",
        "description": "Inject a directive into the Brain's system prompt. Strongest intervention -- system-level authority.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "The event ID"},
                "insight": {"type": "string", "description": "The insight to inject (max 500 chars)"},
                "severity": {
                    "type": "string",
                    "enum": ["nudge", "course_correct", "alert"],
                    "description": "Severity level of the insight",
                },
            },
            "required": ["event_id", "insight", "severity"],
        },
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
        self._shadow = os.getenv("SYSTEM2_SHADOW", "true").lower() == "true"
        self._model = os.getenv("LLM_MODEL_SYSTEM2", "gemini-live-2.5-flash")
        self._project = os.getenv("GCP_PROJECT", "")
        self._location = os.getenv("GCP_LOCATION", "global")
        self._seen_neurons: set[str] = set()
        self._neuron_labels: dict[str, str] = {}
        self._last_pulse_event_id: str | None = None
        self._receive_task: asyncio.Task | None = None
        self._running = False
        self._client = None

    async def start(self) -> None:
        """Connect Live API session with system instruction + 7 tools."""
        try:
            from google import genai
            from google.genai import types

            self._client = genai.Client(
                vertexai=True,
                project=self._project,
                location=self._location,
            )

            config = types.LiveConnectConfig(
                response_modalities=[types.Modality.TEXT],
                system_instruction=types.Content(
                    parts=[types.Part(text=SYSTEM_INSTRUCTION)]
                ),
                tools=[types.Tool(function_declarations=[
                    types.FunctionDeclaration(**td) for td in TOOL_DECLARATIONS
                ])],
            )

            self._session = await self._client.aio.live.connect(
                model=self._model,
                config=config,
            )
            self._running = True
            self._receive_task = asyncio.create_task(self._receive_loop())
            await self._load_neuron_labels()
            logger.info(
                "Cortex Live API session connected (model=%s, shadow=%s, labels=%d)",
                self._model, self._shadow, len(self._neuron_labels),
            )
        except Exception as e:
            logger.error("Cortex Live API failed to start: %s", e)
            self._session = None

    async def stop(self) -> None:
        """Graceful close."""
        self._running = False
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self._session:
            try:
                await self._session.close()
            except Exception:
                pass
            self._session = None
        logger.info("Cortex Live API session closed")

    async def send_pulse(self, batch: PulseBatch) -> None:
        """PulseObserver implementation. Format batch as compact text and send to session."""
        self._last_pulse_event_id = batch.event_id
        if not self._session:
            return
        try:
            text = self._format_pulse(batch)
            await self._session.send(input=text, end_of_turn=True)
        except Exception as e:
            logger.debug("Cortex send_pulse failed (non-fatal): %s", e)
            await self._try_reconnect()

    async def _load_neuron_labels(self) -> None:
        """Pre-load titles for knowledge neurons so first-mention pulses include context."""
        try:
            lessons = await self._archivist.list_lessons(limit=500)
            for p in lessons:
                nid = f"lesson:{p.get('id', '')}"
                payload = p.get("payload", {})
                title = payload.get("title", "")
                channel = payload.get("channel", "stable")
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
        while self._running and self._session:
            try:
                async for msg in self._session.receive():
                    if not self._running:
                        break
                    await self._process_message(msg)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.warning("Cortex receive loop error: %s", e)
                if self._running:
                    await self._try_reconnect()
                    break

    async def _process_message(self, msg) -> None:
        """Process a single message from the Live API session."""
        from google.genai import types

        eid = self._last_pulse_event_id

        if hasattr(msg, "text") and msg.text:
            try:
                await self._broadcast({
                    "type": "cortex_thinking",
                    "event_id": eid,
                    "content_type": "text",
                    "text": msg.text,
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
            phase = getattr(event, "phase", "unknown")
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
        phase = getattr(event, "phase", "unknown")
        domain = getattr(event, "domain", "unknown")
        source = getattr(event, "source", "unknown")
        service = getattr(event, "service", "?")
        status = getattr(event, "status", "unknown")
        turns = len(event.conversation)
        defers = getattr(event, "defer_count", 0)
        header = (
            f"Event: {event_id}\n"
            f"Status: {status} | Phase: {phase} | Domain: {domain}\n"
            f"Source: {source} | Service: {service}\n"
            f"Turns: {turns} | Elapsed: {elapsed_m}m | Defers: {defers}"
        )
        recent = event.conversation[-10:]
        action_lines = []
        for t in recent:
            ts_str = ""
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
        for b in batches:
            for p in b.get("pulses", []):
                nid = p.get("neuron_id", "")
                neuron_counts[nid] = neuron_counts.get(nid, 0) + 1
                if p.get("neuron_type") == "tool":
                    tool_trail.append(nid.removeprefix("tool:"))
                if p.get("neuron_type") == "phase":
                    phases.append(nid.removeprefix("phase:"))
        top_neurons = sorted(neuron_counts.items(), key=lambda x: -x[1])[:5]
        lines = [
            f"Pulse history for {event_id} (last {last_n_minutes} minutes):",
            f"Total pulse batches: {len(batches)}",
            f"Total neuron activations: {total_neurons}",
            f"Unique neurons fired: {len(neuron_counts)}",
            f"Phases during window: {' -> '.join(phases) if phases else 'no phase changes'}",
            "Most-fired neurons:",
        ]
        for nid, count in top_neurons:
            lines.append(f"  {nid} ({count} times)")
        if tool_trail:
            from collections import Counter
            tc = Counter(tool_trail)
            trail_str = ", ".join(f"{t} x{c}" for t, c in tc.most_common(5))
            lines.append(f"Tool trail: [{trail_str}]")
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
                f"Channel: {payload.get('channel', 'stable')} | Verified: {payload.get('verification_count', 0)} times\n"
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
            "shadow": True,
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
            actor="cortex",
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

        await self._record_intervention(event_id, current_turn)

        if self._shadow:
            await self._write_shadow(event_id, "send_event_message", {"message": message})
            return f"[SHADOW] Message queued for {event_id}"

        from ..models import ConversationTurn
        turn = ConversationTurn(
            turn=current_turn + 1,
            actor="cortex",
            action="message",
            thoughts=message,
        )
        await self._blackboard.append_turn(event_id, turn)
        # Clear waiting so Brain picks up the message
        if hasattr(self, "_brain") and self._brain:
            self._brain.clear_waiting(event_id)
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

        from ..models import ConversationTurn
        turn = ConversationTurn(
            turn=current_turn + 1,
            actor="cortex",
            action="insight",
            thoughts=insight,
        )
        await self._blackboard.append_turn(event_id, turn)
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

    async def _try_reconnect(self) -> None:
        """Exponential backoff reconnect."""
        if not self._running:
            return
        self._session = None
        for delay in (30, 60, 120):
            logger.info("Cortex reconnecting in %ds...", delay)
            await asyncio.sleep(delay)
            if not self._running:
                return
            try:
                await self.start()
                if self._session:
                    return
            except Exception as e:
                logger.warning("Cortex reconnect failed: %s", e)
        logger.error("Cortex reconnect exhausted -- giving up")

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

        await self.stop()
        await self.start()

        if self._session and summary:
            try:
                await self._session.send(
                    input=f"[SESSION RESUMED] Previous session summary:\n{summary}",
                    end_of_turn=True,
                )
            except Exception as e:
                logger.debug("Cortex summary injection failed: %s", e)
