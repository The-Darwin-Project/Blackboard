# BlackBoard/src/utils/jarvis_ack.py
# @ai-rules:
# 1. [Constraint]: Pure helper. No Redis, no Brain import, no LLM.
# 2. [Pattern]: Matches bare observations and acknowledgments from JARVIS.
# 3. [Constraint]: STABILIZATION_WAKE_PREFIX is a TRUSTED marker. Only LiveAPIAdapter.send_event_message may add it,
#    and only while Brain.pending_stabilization_event_ids() contains the event AND the message is not a question/concern.
#    For every other JARVIS message the adapter strips the prefix (strip_stabilization_wake_prefix) so tool_gates can key
#    ack handling on the prefix alone.
# 4. [Gotcha]: A stabilization wake is a "recovered" signal, not a question -- tool_gates treat it like an acknowledgment.
"""JARVIS acknowledgment and payload coercion helpers."""
from __future__ import annotations

import math
import re

_JARVIS_ACK_PATTERN = re.compile(
    r"^(?:silently\s+observing|watching|acknowledged|confirmed|understood|no\s+observations|noted|ok)[\s.!,]*$",
    re.IGNORECASE,
)


def safe_score(val: object) -> float:
    """Coerce a payload similarity score to a finite float; bool/None/non-numeric/nan/inf -> 0.0."""
    if isinstance(val, bool) or val is None:
        return 0.0
    try:
        fval = float(val)  # type: ignore[arg-type]
        return fval if math.isfinite(fval) else 0.0
    except (TypeError, ValueError, OverflowError):
        return 0.0


def is_jarvis_acknowledgment(text: str | None) -> bool:
    """Return True if text is a bare observation or acknowledgment from JARVIS."""
    if not text or not isinstance(text, str):
        return False
    stripped = text.strip().strip("*_\"'").strip()
    return bool(_JARVIS_ACK_PATTERN.search(stripped))


STABILIZATION_WAKE_PREFIX = "[STABILIZATION WAKE]"


def is_stabilization_wake(text: str | None) -> bool:
    """Return True if text carries the trusted stabilization-wake marker prefix."""
    return isinstance(text, str) and text.strip().startswith(STABILIZATION_WAKE_PREFIX)


def strip_stabilization_wake_prefix(text: str) -> str:
    """Remove ALL leading stabilization-wake markers (and the whitespace/newlines between them) from text.

    Looping matters: a single strip would leave "[STABILIZATION WAKE] x" behind for a doubled marker, and the
    gates would then treat a real JARVIS question as an acknowledgment.
    """
    stripped = text.strip()
    if not stripped.startswith(STABILIZATION_WAKE_PREFIX):
        return text
    while stripped.startswith(STABILIZATION_WAKE_PREFIX):
        stripped = stripped[len(STABILIZATION_WAKE_PREFIX):].lstrip()
    return stripped
