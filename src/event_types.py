# BlackBoard/src/event_types.py
# @ai-rules:
# 1. [Constraint]: stdlib-only. No Pydantic, no I/O. Safe to import from pulse.py.
# 2. [Pattern]: Single source of truth for EventSource vocabulary across Python.
# 3. [Gotcha]: Adding a new source requires updating: this file, ui/src/api/types.ts,
#    SYSTEM_INSTRUCTION taxonomy prose, and 05-event-evidence-contract.mdc.
from typing import Literal

EventSource = Literal["aligner", "chat", "slack", "headhunter", "timekeeper", "jarvis"]
