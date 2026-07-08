# src/agents/llm/token_meter.py
# @ai-rules:
# 1. [Constraint]: No Redis, no Brain, no LLM SDK imports. Pure in-memory counters.
# 2. [Pattern]: threading.Lock guards all compound read-modify-write (record, snapshot, drain_event).
# 3. [Pattern]: snapshot() resets interval counters and returns deltas. get_platform_totals() is cumulative.
# 4. [Pattern]: drain_event() returns per-event totals with frozen key names, then deletes. Idempotent (None on second call).
# 5. [Gotcha]: event_id=None records land in platform totals only (system bucket), never in per-event.
# 6. [Pattern]: caller/model params reserved for v2 per-caller/per-model breakdown. Stored but not yet surfaced.
"""
In-memory token usage counter with per-event and platform-level accumulation.

Singleton via get_token_meter() in __init__.py. Thread-safe for concurrent
async tasks sharing the event loop.
"""
from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, TypedDict

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .types import TokenUsage

_MAX_EVENTS = 10_000


class TokenUsageDict(TypedDict, total=False):
    """Frozen schema for drain_event() and snapshot() return values."""
    input_tokens: int
    output_tokens: int
    thinking_tokens: int
    cached_tokens: int
    tool_use_tokens: int
    total_tokens: int
    calls: int


_ZERO_USAGE: TokenUsageDict = {
    "input_tokens": 0, "output_tokens": 0, "thinking_tokens": 0,
    "cached_tokens": 0, "tool_use_tokens": 0, "total_tokens": 0, "calls": 0,
}

_TOKEN_FIELDS = ("input_tokens", "output_tokens", "thinking_tokens",
                 "cached_tokens", "tool_use_tokens", "total_tokens")


class TokenMeter:
    """Accumulates token usage from all LLM callers. No external dependencies."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._interval: dict[str, int] = dict(_ZERO_USAGE)
        self._cumulative: dict[str, int] = dict(_ZERO_USAGE)
        self._per_event: dict[str, dict[str, int]] = {}

    def record(
        self,
        caller: str,
        model: str,
        usage: "TokenUsage",
        event_id: str | None = None,
    ) -> None:
        """Accumulate a single LLM call's token usage.

        caller/model: stored for v2 per-caller/per-model breakdown (not yet surfaced).
        """
        with self._lock:
            for field in _TOKEN_FIELDS:
                val = getattr(usage, field, 0)
                self._interval[field] += val
                self._cumulative[field] += val
            self._interval["calls"] += 1
            self._cumulative["calls"] += 1

            if event_id:
                if event_id not in self._per_event and len(self._per_event) >= _MAX_EVENTS:
                    oldest = next(iter(self._per_event))
                    logger.warning("TokenMeter: evicting %s (cap %d reached)", oldest, _MAX_EVENTS)
                    del self._per_event[oldest]
                ev = self._per_event.setdefault(event_id, dict(_ZERO_USAGE))
                for field in _TOKEN_FIELDS:
                    ev[field] += getattr(usage, field, 0)
                ev["calls"] += 1

    def snapshot(self) -> dict[str, int]:
        """Return interval deltas since last snapshot, then reset interval counters."""
        with self._lock:
            result = dict(self._interval)
            self._interval = dict(_ZERO_USAGE)
            return result

    def get_platform_totals(self) -> dict[str, int]:
        """Return cumulative totals since boot (never resets)."""
        with self._lock:
            return dict(self._cumulative)

    def drain_event(self, event_id: str) -> dict[str, int] | None:
        """Return per-event totals and delete the entry. None on second call (idempotent)."""
        with self._lock:
            return self._per_event.pop(event_id, None)
