---
description: "Verify stale assumptions after defer wake-up before re-deferring"
requires:
  - always/04-deep-memory.md
tags: [defer, memory, verification]
---
# Post-Defer Verification

You are waking from a deferred state. The information from the last agent result may be stale.

When waking from a defer, enter the verify phase before checking current
state. Refresh capabilities are budget-gated (not phase-gated), but the
verify phase is the correct checkpoint for evaluating evidence.

## Before deferring again, you MUST

1. **Check observations and deep memory** -- first review your observation history for this service. Recent duration measurements from your own events are more precise than archived deep memory baselines. If you recorded timing data for this service in a previous event, that is your best Ts calibration source. Then consult deep memory for additional context -- it provides patterns across longer time spans. Use the timing from both sources to choose your deferral interval.
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

## Source Control Post-Defer: Refresh External State

For events with source control context waking from defer, refresh the
current MR/pipeline state ONCE. Then act on the result.

<bridge ref="domain/{event.domain}" trigger="defer_wake">
You woke from defer. Re-enter domain loop at the VERIFY waypoint.
Measure PV, then use dual rhombus (domain + phase) for next step.
</bridge>
