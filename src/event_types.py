# BlackBoard/src/event_types.py
# @ai-rules:
# 1. [Constraint]: stdlib-only. No Pydantic, no I/O. Safe to import from pulse.py.
# 2. [Pattern]: Single source of truth for EventSource vocabulary across Python.
# 3. [Gotcha]: Adding a new source requires updating: this file, ui/src/api/types.ts,
#    SYSTEM_INSTRUCTION taxonomy prose, and 05-event-evidence-contract.mdc.
from typing import Literal

EventSource = Literal["aligner", "chat", "slack", "headhunter", "timekeeper", "jarvis"]

# Human-facing interactive channels eligible for the 4-agent squad tier.
USER_INTERACTIVE_SOURCES: frozenset[str] = frozenset({"chat", "slack"})

# Dual-semantics exclusion partition:
# 1. Excluded from automated WIP counts, NEW->ACTIVE cap admission, and automated _dispatch_semaphore.
# 2. Granted PRIORITY_HIGH LLM quota & sidecar burst-reserve access (interactive + JARVIS meta-cognitive).
AUTOMATED_WIP_EXCLUDED_SOURCES: frozenset[str] = frozenset({"chat", "slack", "jarvis"})

# Background/sensor sources subject to global automated WIP capacity and automated dispatch gating.
AUTOMATED_SOURCES: frozenset[str] = frozenset({"aligner", "headhunter", "timekeeper"})
