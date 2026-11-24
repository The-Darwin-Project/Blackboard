# src/utils/turn_decay.py
# @ai-rules:
# 1. [Constraint]: Pure constants and cutoff helpers only -- ZERO imports from src.agents. Shared by
#    context_parts.py (applies decay), brain.py (_build_contents) and tool_gates.py (recall un-gating)
#    so all sites stay in strict lockstep on WHEN a turn decays.
# 2. [Pattern]: A turn at index ``idx`` decays iff ``idx < decay_cutoff_index(len(conv), decay_distance)``
#    AND its payload is > DECAY_MIN_CHARS. Normal decay quantizes cutoff to multiples of epoch_size (K=10,
#    env BRAIN_DECAY_EPOCH_SIZE) for prefix cache stability; Tier-1 quota shedding (decay_distance < 10)
#    and epoch_size <= 1 bypass quantization for exact sliding decay.
"""Constants and epoch-quantized cutoff helpers for evidence decay (VMER-2341, VMER-2450)."""
from __future__ import annotations

import os

# Turns further than this many positions from the tail are eligible for decay.
DEFAULT_TURN_DECAY_DISTANCE = 10

# Payloads at or below this length stay raw (399/400 raw, 401 decays).
DECAY_MIN_CHARS = 400

# Default quantization epoch size K for cache-stable step-function decay.
DEFAULT_DECAY_EPOCH_SIZE = 10


def get_decay_epoch_size() -> int:
    """Parse BRAIN_DECAY_EPOCH_SIZE with safe fallback to DEFAULT_DECAY_EPOCH_SIZE on invalid/non-positive values."""
    raw = os.getenv("BRAIN_DECAY_EPOCH_SIZE")
    if raw is None or not raw.strip():
        return DEFAULT_DECAY_EPOCH_SIZE
    try:
        parsed = int(raw.strip())
    except (ValueError, TypeError):
        return DEFAULT_DECAY_EPOCH_SIZE
    if parsed <= 0:
        return DEFAULT_DECAY_EPOCH_SIZE
    return max(1, parsed)


def decay_cutoff_index(
    conv_len: int,
    decay_distance: int = DEFAULT_TURN_DECAY_DISTANCE,
    epoch_size: int | None = None,
) -> int:
    """Return exclusive index cutoff below which turns are eligible for evidence decay.

    A turn at index ``idx`` decays iff ``idx < decay_cutoff_index(conv_len, decay_distance)``.
    Quantization is bypassed for Tier-1 quota shedding (``decay_distance < DEFAULT_TURN_DECAY_DISTANCE``)
    or when ``eff_epoch <= 1``.
    """
    raw_cutoff = conv_len - 1 - decay_distance
    if raw_cutoff <= 0:
        return 0
    eff_epoch = get_decay_epoch_size() if epoch_size is None else max(1, epoch_size)
    if decay_distance < DEFAULT_TURN_DECAY_DISTANCE or eff_epoch <= 1:
        return raw_cutoff
    return (raw_cutoff // eff_epoch) * eff_epoch
