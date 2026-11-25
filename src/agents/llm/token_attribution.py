# src/agents/llm/token_attribution.py
# @ai-rules:
# 1. [Constraint]: Stdlib-only. Safe to import from TokenMeter without cycles.
# 2. [Pattern]: OrderedDict LRU eviction at max_teams=256 folds evicted totals into "_other" to prevent spray DoS.
# 3. [Gotcha]: "global" bucket (from team_id=None/blank) is never evicted on spray overflow.
"""Bounded team_id normalization and LRU attribution counter for token telemetry."""
from __future__ import annotations

from collections import OrderedDict
import re

_MAX_TEAMS = 256
_TEAM_SLUG_MAX_LEN = 64
_SAFE_CHAR_RE = re.compile(r"[^a-z0-9_-]+")
_FIELDS = (
    "input_tokens",
    "output_tokens",
    "thinking_tokens",
    "cached_tokens",
    "tool_use_tokens",
    "total_tokens",
    "calls",
)


def _zero_bucket() -> dict[str, int]:
    return {k: 0 for k in _FIELDS}


def normalize_team_id(team_id: str | None) -> str:
    """Normalize arbitrary team_id to a bounded [a-z0-9_-] slug ('global' if missing/blank)."""
    if team_id is None or not isinstance(team_id, str):
        return "global"
    cleaned = _SAFE_CHAR_RE.sub("-", team_id.strip().lower()).strip("-_")
    if not cleaned:
        return "global"
    return cleaned[:_TEAM_SLUG_MAX_LEN].strip("-_") or "global"


class BoundedTeamCounter:
    """OrderedDict-backed LRU team token counter capped at max_teams + '_other' overflow."""

    def __init__(self, max_teams: int = _MAX_TEAMS) -> None:
        self._max_teams = max(1, max_teams)
        self._teams: OrderedDict[str, dict[str, int]] = OrderedDict()
        self._other: dict[str, int] = _zero_bucket()

    def add(self, team_id: str | None, usage_delta: dict[str, int]) -> None:
        key = normalize_team_id(team_id)
        if key in self._teams:
            self._teams.move_to_end(key)
            bucket = self._teams[key]
        else:
            if len(self._teams) >= self._max_teams:
                evict_key = next((k for k in self._teams if k != "global"), None)
                if evict_key is not None:
                    evicted = self._teams.pop(evict_key)
                    for field in _FIELDS:
                        self._other[field] += evicted.get(field, 0)
            bucket = _zero_bucket()
            self._teams[key] = bucket
        for field in _FIELDS:
            bucket[field] += int(usage_delta.get(field, 0) or 0)

    def totals(self) -> dict[str, dict[str, int]]:
        out = {k: dict(v) for k, v in self._teams.items()}
        if self._other["calls"] > 0 or self._other["total_tokens"] > 0:
            out["_other"] = dict(self._other)
        return out
