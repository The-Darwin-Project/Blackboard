---
description: "Verify stale assumptions after defer wake-up before re-deferring"
requires:
  - triage/deep-memory.md
tags: [defer, memory, verification]
---
# Post-Defer Verification

You are waking from a deferred state. The information from the last agent result may be stale.

## Before deferring again, you MUST

1. **Consult deep memory** -- call `consult_deep_memory` with the deferral reason to check if past events reveal how long this type of task typically takes or what the resolution looked like.
2. **Verify, don't assume** -- if the deferral reason involves waiting for an external process (CI pipeline, deployment sync, merge), route an agent to check the current state rather than re-deferring with the same stale reason. A quick `select_agent` dispatch to verify takes seconds; a blind re-defer wastes minutes.
3. **Escalate after repeated defers** -- if you have already deferred this event 2+ times for the same reason, you MUST route an agent to verify. Do NOT defer a third time with the same reason.
