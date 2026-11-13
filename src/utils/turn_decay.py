# src/utils/turn_decay.py
# @ai-rules:
# 1. [Constraint]: Pure constants only -- no imports from src.agents. Shared by context_parts.py
#    (applies decay), brain.py (_build_contents) and tool_gates.py (recall un-gating) so the three can
#    never disagree on WHEN a turn decays.
# 2. [Pattern]: A turn decays when its distance from the conversation tail is > DEFAULT_TURN_DECAY_DISTANCE
#    (distance = len(conversation) - 1 - index) AND its payload is > DECAY_MIN_CHARS characters.
"""Constants for sliding-window evidence decay (VMER-2341)."""
from __future__ import annotations

# Turns further than this many positions from the tail are eligible for decay.
DEFAULT_TURN_DECAY_DISTANCE = 10

# Payloads at or below this length stay raw (399/400 raw, 401 decays).
DECAY_MIN_CHARS = 400
