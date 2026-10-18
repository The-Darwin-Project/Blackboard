# src/utils/jarvis_ack.py
# @ai-rules:
# 1. [Constraint]: Pure helper. No Redis, no Brain import, no LLM.
# 2. [Pattern]: Matches bare observations and acknowledgments from JARVIS.
"""JARVIS acknowledgment detection helper."""
from __future__ import annotations

import re

_JARVIS_ACK_PATTERN = re.compile(
    r"^(?:silently\s+observing|watching|acknowledged|confirmed|understood|no\s+observations|noted|ok)[\s.!,]*$",
    re.IGNORECASE,
)


def is_jarvis_acknowledgment(text: str | None) -> bool:
    """Return True if text is a bare observation or acknowledgment from JARVIS."""
    if not text or not isinstance(text, str):
        return False
    stripped = text.strip().strip("*_\"'").strip()
    return bool(_JARVIS_ACK_PATTERN.search(stripped))
