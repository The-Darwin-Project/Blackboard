# BlackBoard/src/event_types.py
# @ai-rules:
# 1. [Constraint]: stdlib-only. No Pydantic, no I/O. Safe to import from pulse.py.
# 2. [Pattern]: Single source of truth for EventSource vocabulary across Python.
# 3. [Gotcha]: Adding a new source requires updating: this file, ui/src/api/types.ts,
#    SYSTEM_INSTRUCTION taxonomy prose, and 05-event-evidence-contract.mdc.
# 4. [Pattern]: AUTOMATED_EVENT_SOURCES gates report_incident/close_event escape-valve logic
#    (handlers_dispatch.py, handlers_state.py) -- sources with no human in the loop.
# 5. [Pattern]: TERMINAL_REASONS is the single source of truth for close_event's terminal_reason
#    enum, shared by brain.py (_LLM_CLOSE_REASONS), handlers_state.py (_VALID_TERMINAL_REASONS),
#    and llm/types.py's schema enum -- previously duplicated 3x, now derived from one tuple.
from typing import Literal

EventSource = Literal["aligner", "chat", "slack", "headhunter", "timekeeper", "jarvis"]

AUTOMATED_EVENT_SOURCES = ("headhunter", "aligner", "timekeeper")

TERMINAL_REASONS = ("resolved", "non_transient_confirmed", "self_resolved", "no_action_needed")
