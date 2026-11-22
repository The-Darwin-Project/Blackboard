# BlackBoard/src/agents/headhunter_utils.py
# @ai-rules:
# 1. [Constraint]: Zero-import module (stdlib __future__/os only). No headhunter/adapter/blackboard
#    imports allowed.
# 2. [Pattern]: Shared constants for all Headhunter adapters and llm/prompt.py.
# 3. [Gotcha]: Imported by headhunter.py, headhunter_gitlab.py, headhunter_github.py, and
#    llm/prompt.py — circular imports are fatal if this file imports any of those.
# 4. [Security]: XML fence stripping and untrusted-text sanitization live exclusively in
#    src/utils/prompt_sanitize.py (consolidated in Batch 2 Slice 2A).
"""Shared constants for Headhunter adapters. Import-cycle-safe (stdlib-only)."""
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
