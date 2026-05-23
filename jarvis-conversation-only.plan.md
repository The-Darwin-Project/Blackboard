# JARVIS Conversation Only

## Problem

JARVIS has 3 intervention tools but the 2 passive ones get ignored by FRIDAY:
- `surface_context` -- writes an evidence turn that FRIDAY treats as noise
- `inject_system_insight` -- async whisper queued to Redis, often consumed but not acted upon

JARVIS should just talk to FRIDAY directly via `send_event_message`. One channel, conversational, obligation-creating.

## After

JARVIS has one intervention tool: `send_event_message`. If he has something to say to FRIDAY, he says it as a conversation turn she must respond to. No whispers, no passive evidence drops.

## Affected Files

- `src/adapters/live_api_adapter.py` -- Remove 2 tool declarations, 2 handler branches, 2 methods, update SI
- `src/agents/brain.py` -- Remove whisper consumption block + `_get_pending_cortex_insight` method
- `src/agents/llm/types.py` -- Fix `wait_for_user` and `defer_event` descriptions
- `BlackBoard/.cursor/rules/01-identity.mdc` -- Update JARVIS behavior description
- `BlackBoard/.cursor/rules/02-architecture.mdc` -- Update intervention hierarchy
- `ui/src/components/cortex/` -- May have references to whisper/insight types (cosmetic, non-blocking)

## Atomic Steps

### Step 1: Remove `surface_context` tool declaration from TOOL_DECLARATIONS
**File:** `src/adapters/live_api_adapter.py` (L365 area)

### Step 2: Remove `inject_system_insight` tool declaration from TOOL_DECLARATIONS
**File:** `src/adapters/live_api_adapter.py` (L330 area)

### Step 3: Remove handler dispatch branches
**File:** `src/adapters/live_api_adapter.py` (L945-958)
Remove both `elif name == "surface_context"` and `elif name == "inject_system_insight"` branches.

### Step 4: Delete `_tool_surface_context` method
**File:** `src/adapters/live_api_adapter.py` (L1243-1268)

### Step 5: Delete `_tool_inject_system_insight` method
**File:** `src/adapters/live_api_adapter.py` (L1307-1360)

### Step 6: Update JARVIS system instruction
**File:** `src/adapters/live_api_adapter.py` (L133-141, L269)

Replace intervention levels with:
```
### How to Intervene

Your only tool to communicate with FRIDAY is **send_event_message**.
When you see friction, talk to her directly. End with a question.
```

Also update shift report template (L269) to remove references to surface_context/inject_system_insight.

### Step 7: Remove whisper consumption from brain.py
**File:** `src/agents/brain.py`
- Remove block at L1762-1765 (cortex_block injection in _build_system_prompt)
- Delete `_get_pending_cortex_insight` method (L1839-1868)

### Step 8: Fix FRIDAY wait vs defer tool descriptions
**File:** `src/agents/llm/types.py`

**`wait_for_user` (L384-388):** Replace description:
```python
"description": (
    "Pause processing until a human or agent responds. "
    "Use ONLY when waiting for a person's decision or an agent's final result. "
    "NOT for pipelines, timers, or external processes -- use defer_event for those."
),
```

**`defer_event` (L366-367):** Replace description:
```python
"description": (
    "Set a timer and pause this event. Use for pipeline completions, "
    "cooldown periods, or any timed wait. Works like an alarm clock -- "
    "you will be woken after delay_seconds to check again."
),
```

### Step 9: Update shift report template
**File:** `src/adapters/live_api_adapter.py` (L269)

Replace:
```
- Tool used (surface_context / send_event_message / inject_system_insight)
```
With:
```
- Tool used (send_event_message)
```

### Step 10: Update .cursor/rules
**File:** `BlackBoard/.cursor/rules/01-identity.mdc` (L62)
Replace: "Prefers surface_context (lightest) over send_event_message over inject_system_insight (strongest)"
With: "Communicates with FRIDAY exclusively via send_event_message (direct conversation turns)."

**File:** `BlackBoard/.cursor/rules/02-architecture.mdc` (L53)
Replace: "Intervention Hierarchy: surface_context -> send_event_message -> inject_system_insight"
With: "Intervention: send_event_message (direct conversation turn that wakes FRIDAY and creates response obligation)."

### Step 10: Update @ai-shebang on live_api_adapter.py
Remove/update rule #6 ("Text output from Cortex is NOT visible to FRIDAY. Only tool calls reach her.") -- still true but simplify since there's only one intervention tool now.

### Step 12: Run tests + UI build
- `pytest tests/ -x --timeout=30`
- `cd ui && npm run build` (verify cortex components still compile)
- Verify no import errors
- `grep -r "inject_system_insight\|surface_context" src/` returns 0 hits

## Verification
- `pytest` passes
- `grep -r "inject_system_insight\|surface_context" src/` returns 0 hits
- JARVIS tool list in live session contains only: send_event_message, view_event_blackboard, post_sticky_note (via FRIDAY), plus observation tools
- No `darwin:whisper:*` keys are written
