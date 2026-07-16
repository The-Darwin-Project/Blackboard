# BlackBoard/src/agents/headhunter_utils.py
# @ai-rules:
# 1. [Constraint]: Zero-import module. No headhunter/adapter/blackboard imports allowed.
# 2. [Pattern]: Shared constants for all Headhunter adapters.
# 3. [Gotcha]: Imported by headhunter.py, headhunter_gitlab.py, and headhunter_github.py
#    — circular imports are fatal if this file imports any of those.
"""Shared constants for Headhunter adapters. Import-cycle-safe (no sibling imports)."""
from __future__ import annotations

import os


def _safe_int(env_key: str, default: int) -> int:
    """Parse int env var with fallback on invalid values."""
    raw = os.getenv(env_key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


_COMMENT_LIMIT = _safe_int("HEADHUNTER_COMMENT_LIMIT", 2000)
_DESC_SAFETY_CAP = _safe_int("HEADHUNTER_DESCRIPTION_CAP", 100_000)
