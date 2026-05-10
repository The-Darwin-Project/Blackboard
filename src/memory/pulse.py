# BlackBoard/src/memory/pulse.py
# @ai-rules:
# 1. [Constraint]: Pure data models + protocol. No I/O, no Redis, no imports beyond stdlib.
# 2. [Pattern]: PulsePort is a Protocol -- implementors (PulseTracker) live in separate modules.
# 3. [Pattern]: PulseContext is caller-provided; PulseBatch is emitter-constructed.
# 4. [Gotcha]: neuron_type must be one of: "lesson", "memory", "tool", "phase", "agent".
# 5. [Semantic]: Tool pulse scores: 1.0 = success, 0.3 = completed with error, 0.0 = infra failure.
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


@dataclass
class PulseContext:
    """Caller-provided context, passed to Archivist search methods."""

    event_id: str | None = None
    turn: int | None = None
    event_elapsed_s: int = 0


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
        }


@runtime_checkable
class PulsePort(Protocol):
    async def on_pulse_batch(self, batch: PulseBatch) -> None: ...
