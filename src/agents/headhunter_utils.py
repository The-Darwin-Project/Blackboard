# BlackBoard/src/agents/headhunter_utils.py
# @ai-rules:
# 1. [Constraint]: Zero-import module. No headhunter/adapter/blackboard imports allowed.
# 2. [Pattern]: Shared constants for all Headhunter adapters.
# 3. [Gotcha]: Imported by headhunter.py, headhunter_gitlab.py, and headhunter_github.py
#    — circular imports are fatal if this file imports any of those.
# 4. [Pattern]: sanitize_comment_field() is the single sanitizer for any field interpolated
#    into an externally-visible GitHub/GitLab comment (close_reason, tracking_link) --
#    strips markdown/mention-breakout chars and caps length. Reuse it, don't re-derive.
"""Shared constants for Headhunter adapters. Import-cycle-safe (no sibling imports)."""
from __future__ import annotations

import os
import re


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

# Human-readable labels for close_event's terminal_reason/close_reason values.
# Display-time-only lookup -- never reassign the raw close_reason variable that
# feeds control-flow gates (e.g. `close_reason not in ("stale", "duplicate")`).
CLOSE_REASON_LABELS = {
    "resolved": "Resolved",
    "non_transient_confirmed": "Confirmed non-transient",
    "self_resolved": "Self-resolved",
    "no_action_needed": "No action needed",
}

_COMMENT_FIELD_STRIP_RE = re.compile(r'[<>@`]')


def sanitize_comment_field(value: str, max_len: int = 200) -> str:
    """Strip markdown/mention-breakout characters and cap length.

    Shared by every field (close_reason, tracking_link) interpolated into an
    externally-visible GitHub/GitLab comment -- prevents markdown injection,
    @mentions, and unbounded length from LLM- or user-supplied text.
    """
    return _COMMENT_FIELD_STRIP_RE.sub('', value)[:max_len]
