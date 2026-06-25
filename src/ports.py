# BlackBoard/src/ports.py
# @ai-rules:
# 1. [Pattern]: Ports define interfaces consumed by the Brain core. Adapters implement them.
# 2. [Pattern]: BroadcastPort uses __call__ to preserve backward compatibility with existing callbacks.
# 3. [Constraint]: No implementation logic in this file -- protocols only.
# 4. [Pattern]: BrainLifecyclePort + BrainIntrospectionPort are the JarvisPort boundary.
#    LiveAPIAdapter depends on these Protocols, not the Brain class.
"""Hexagonal Architecture port definitions for the Darwin Brain."""
from __future__ import annotations

from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .agents.brain_skill_loader import BrainSkillLoader


class BroadcastPort(Protocol):
    """Port for broadcasting messages to external channels (Dashboard WS, Slack, etc.).

    Uses __call__ so existing bare-function callbacks (broadcast_to_ui, slack.broadcast_handler)
    satisfy the protocol without modification. Brain calls: await target(message)
    """

    async def __call__(self, message: dict) -> None: ...


class BrainLifecyclePort(Protocol):
    """Adapter-facing port for mutating Brain event state.

    Covers the 5 lifecycle operations LiveAPIAdapter needs when JARVIS
    triggers a wake or close:
    - Clear user-wait / JARVIS-wait / hold-watch states
    - Resume parked (waiting_approval) events
    - Close JARVIS meta-events on stream teardown
    """

    def clear_waiting(self, event_id: str) -> None: ...

    def clear_jarvis_wait(self, event_id: str) -> None: ...

    def clear_hold_watch(self, event_id: str) -> None: ...

    async def resume_if_parked(self, event_id: str) -> bool: ...

    async def close_jarvis_meta_event(self, event_id: str) -> None: ...


class BrainIntrospectionPort(Protocol):
    """Adapter-facing port for reading Brain state without mutation.

    Covers the 5 read-only queries LiveAPIAdapter needs for stale-event
    detection, skill manifest generation, and meta-event gating.
    """

    def is_task_running(self, event_id: str) -> bool: ...

    def last_processed_time(self, event_id: str) -> float: ...

    def has_jarvis_waiters(self) -> bool: ...

    def pending_jarvis_event_ids(self) -> list[str]: ...

    def get_skill_loader(self) -> BrainSkillLoader | None: ...
