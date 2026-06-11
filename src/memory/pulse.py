# BlackBoard/src/memory/pulse.py
# @ai-rules:
# 1. [Constraint]: Pure data models + protocol. No I/O, no Redis, no Pydantic.
#    Imports from stdlib and project stdlib-only modules (e.g., event_types) are permitted.
# 2. [Pattern]: PulsePort is a Protocol -- implementors (PulseTracker) live in separate modules.
# 3. [Pattern]: PulseContext is caller-provided; PulseBatch is emitter-constructed.
# 4. [Gotcha]: neuron_type must be one of: "lesson", "memory", "knowledge", "tool", "phase", "agent".
# 5. [Semantic]: Tool pulse scores: 1.0 = success, 0.3 = completed with error, 0.0 = infra failure.
# 6. [Pattern]: PulseBatch.reasoning carries FRIDAY's thinking text (optional, 500-char truncated by JARVIS adapter).
# 7. [Pattern]: PulseBatch.is_defer_wake is a one-shot flag (True on first pulse after defer re-activation).
#    PulseBatch.event_status carries ev.status.value (null-guarded: None if event deleted mid-flight).
# 8. [Pattern]: event_source threads EventDocument.source through PulseContext -> PulseBatch -> to_dict().
#    Typed as event_types.EventSource | None. None when source is unavailable (e.g. nightwatcher_tools.py context).
"""
Pulse data models for the Cognitive Recall Graph.

Neurons = Qdrant points (lessons, memories) + executive nodes (tools, phases, agents).
Pulses = neuron activation events emitted when the Brain searches, invokes tools,
transitions phases, or dispatches agents.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from ..event_types import EventSource


@dataclass
class PulseContext:
    """Caller-provided context, passed to Archivist search methods."""

    event_id: str | None = None
    turn: int | None = None
    event_elapsed_s: int = 0
    event_source: EventSource | None = None


@dataclass
class Pulse:
    """A single neuron activation."""

    neuron_id: str
    neuron_type: str
    score: float
    injected: bool = False


@dataclass
class PulseBatch:
    """A group of co-fired neurons from a single operation."""

    event_id: str
    pulses: list[Pulse]
    turn: int = 0
    event_elapsed_s: int = 0
    timestamp: float = field(default_factory=time.time)
    reasoning: str | None = None
    is_defer_wake: bool = False
    event_status: str | None = None
    event_source: EventSource | None = None

    def to_dict(self) -> dict:
        return {
            "event_id": self.event_id,
            "pulses": [
                {
                    "neuron_id": p.neuron_id,
                    "neuron_type": p.neuron_type,
                    "score": p.score,
                    "injected": p.injected,
                }
                for p in self.pulses
            ],
            "turn": self.turn,
            "event_elapsed_s": self.event_elapsed_s,
            "timestamp": self.timestamp,
            "reasoning": self.reasoning,
            "is_defer_wake": self.is_defer_wake,
            "event_status": self.event_status,
            "event_source": self.event_source,
        }


@runtime_checkable
class PulsePort(Protocol):
    async def on_pulse_batch(self, batch: PulseBatch) -> None: ...
