# BlackBoard/src/state/wip_meta.py
# @ai-rules:
# 1. [Constraint]: Zero src.agents imports — state-layer projection safe for Brain, observers, and FlowCollector.
# 2. [Pattern]: fetch_active_events_meta() tries 2-RTT pipeline get_active_events_metadata() first and falls back to
#    no-arg get_active_events_with_status() for legacy mocks (never uses inspect.iscoroutinefunction).
# 3. [Gotcha]: Blank/unknown source == "" fail-safes to automated WIP (counted against cap).
"""Lightweight active-event metadata projection and 2-RTT pipeline WIP helper."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

from ..event_types import AUTOMATED_WIP_EXCLUDED_SOURCES

_logger = logging.getLogger(__name__)
_AUTOMATED_WIP_STATUSES = frozenset({"active", "deferred"})
_AUTOMATED_WIP_STATUSES_WITH_NEW = frozenset({"new", "active", "deferred"})


@dataclass(slots=True)
class ActiveEventMeta:
    """Minimal per-event fields needed for WIP, FlowCollector, and /flow gauges."""

    status: str
    source: str = ""
    is_waiting_user: bool = False
    queued_at: float | None = None
    atdd_cycle_sec: float | None = None
    team_id: str | None = None


def is_automated_wip_event(meta: ActiveEventMeta, include_new: bool = False) -> bool:
    """Return True if event counts toward automated WIP capacity.

    Excludes interactive/excluded sources (chat, slack, jarvis) and user-parked
    events. Blank/unknown source fail-safes to automated WIP.
    """
    valid = _AUTOMATED_WIP_STATUSES_WITH_NEW if include_new else _AUTOMATED_WIP_STATUSES
    if meta.status not in valid:
        return False
    if meta.source in AUTOMATED_WIP_EXCLUDED_SOURCES:
        return False
    if meta.is_waiting_user:
        return False
    return True


def count_interactive_sessions(meta_map: Mapping[str, ActiveEventMeta]) -> int:
    """Count open interactive/user sessions (chat, slack, jarvis) across active statuses."""
    return sum(
        1 for m in meta_map.values()
        if m.status in _AUTOMATED_WIP_STATUSES_WITH_NEW and m.source in AUTOMATED_WIP_EXCLUDED_SOURCES
    )


async def fetch_active_events_meta(blackboard: Any) -> dict[str, ActiveEventMeta]:
    """Fetch active-event metadata in 2 RTTs, falling back to get_active_events_with_status().

    Legacy MagicMock stubs may define neither or make get_active_events_metadata() return
    a non-dict / fail on await; swallow metadata-lookup errors and propagate status_map
    errors so fail-closed observers (Headhunter/HeadhunterJira) retain their safety contract.
    """
    if blackboard is None:
        return {}
    try:
        get_meta = getattr(blackboard, "get_active_events_metadata", None)
        if callable(get_meta):
            res = get_meta()
            if hasattr(res, "__await__"):
                res = await res
            if isinstance(res, dict):
                return res
    except Exception:
        _logger.debug("fetch_active_events_meta: get_active_events_metadata failed; falling back", exc_info=True)
    status_map = await blackboard.get_active_events_with_status()
    if not isinstance(status_map, Mapping):
        return {}
    return {eid: ActiveEventMeta(status=s, source="") for eid, s in status_map.items()}
