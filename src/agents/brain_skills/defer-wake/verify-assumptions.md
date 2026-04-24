---
description: "Verify stale assumptions after defer wake-up before re-deferring"
requires:
  - always/04-deep-memory.md
tags: [defer, memory, verification]
---
# Post-Defer Verification

You are waking from a deferred state. The information from the last agent result may be stale.

When waking from a defer, enter the verify phase (set_phase("verify"))
to unlock refresh tools before checking current state.

## Before deferring again, you MUST

1. **Consult deep memory** -- check if past events reveal how long this type of task typically takes or what the resolution looked like.
2. **Verify, don't assume** -- if the deferral reason involves waiting for an external process (CI pipeline, deployment sync, merge), route an agent to check the current state rather than re-deferring with the same stale reason.
3. **Escalate after repeated defers** -- if you have already deferred this event 2+ times for the same reason, route an agent to verify. Do NOT defer a third time with the same reason.

## Headhunter Post-Defer: Refresh GitLab State

For headhunter events waking from defer, call refresh_gitlab_context ONCE to
check the current MR/pipeline state. Then act on the result.
