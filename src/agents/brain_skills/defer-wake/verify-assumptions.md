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

1. **Consult deep memory** -- check if past events reveal how long this type of task typically takes or what the resolution looked like. Use the timing from memory to set `delay_seconds` -- if memory says a process takes 30 minutes, use history known time frames when defering.
2. **Verify, don't assume** -- if the deferral reason involves waiting for an external process (CI pipeline, deployment sync, merge), route an agent to check the current state rather than re-deferring with the same stale reason.
3. **Check for progress, not just count** -- repeated defers are healthy when each check shows progress (new percentage, different status, advancing stage). Escalate only when:
   - Two consecutive checks show the SAME state with no change (stalled process)
   - The process has exceeded its expected duration (consult deep memory for typical timing)
   - An error condition persists across checks
   Do NOT escalate a healthy monitoring cycle just because the defer count is high.
4. **Snapshot for trajectory** -- call record_observation with the current quantifiable state (pipeline status code, queue depth, retry count) before deferring. When you wake, list_observations shows whether the number moved -- that is your progress signal.

Re-defer after fresh measurement is the correct controller output when the
process is still progressing. Repeated defers with progress signals = healthy
sampling at interval Ts. The system enforces verify-before-re-defer — this IS
the measurement step in the control loop.

## Headhunter Post-Defer: Refresh GitLab State

For headhunter events waking from defer, call refresh_gitlab_context ONCE to
check the current MR/pipeline state. Then act on the result.

<bridge ref="domain/{event.domain}" trigger="defer_wake">
You woke from defer. Re-enter domain loop at the VERIFY waypoint.
Measure PV, then use dual rhombus (domain + phase) for next step.
</bridge>
