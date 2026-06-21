---
description: "Flow engineering principles for throughput optimization and congestion prevention"
tags: [flow, queuing, batch-size, congestion, throughput]
tools: [defer_event, refresh_gitlab_context, refresh_kargo_context, hold_watch]
---
# Flow Engineering

## Observable Patterns

Recognize these system states and respond accordingly:

### Congestion Collapse

Repeated "no available agent" or growing queue depth = the system is saturated. **Reduce intake, don't try harder.** Defer automated events (headhunter, timekeeper, aligner) and focus on completing in-flight work. User-initiated events (chat, slack) are never deferred.

### Peak Throughput

Control occupancy to sustain throughput. When agents are loaded, complete existing events before accepting new ones from automated sources. One finished event frees capacity for the next.

### Queue Depth as Leading Indicator

A growing event queue predicts future cycle time degradation before it manifests. If multiple events are queued, prioritize clearing the queue over accepting new automated work.

### Batch Size Principle

Smaller tasks complete faster without adding capacity. When dispatching COMPLICATED or COMPLEX tasks, decompose into the smallest independently-verifiable batch and dispatch only that batch. Evaluate the result, then dispatch the next. This reduces cycle time by an order of magnitude (Reinertsen's batch size queuing principle).

## Behaviors

- When an agent reports "busy" and the queue has pending events, focus on completing existing work before routing new automated events.
- When dispatching a multi-step task, always ask: "Can this be broken into smaller batches?" If yes, dispatch only the first batch.

## Domain-Ts vs Congestion-Defer

Two different uses of `defer_event` — do not confuse them:

- **Domain-Ts (strategic)**: The domain control loop schedules the next feedback sample. This is active control — you chose a sampling interval based on severity, source baseline, and progress signals. The process needs time, not another check.
- **Congestion-defer (backpressure)**: The system is saturated. You defer because agents are busy, not because the strategy calls for observation. This is queue management.

Domain-Ts produces structured reasoning ("COMPLICATED strategy: Ts=<consult deep memory for baseline>").
Congestion-defer produces capacity reasoning ("All agents busy, deferring automated event").

## State Change Subscriptions

When monitoring external async processes, prefer subscribing to state changes over short-interval deferrals. Subscribe before deferring -- the background watcher handles the polling while you sleep. You wake with structured evidence of what changed, not a blind timer expiry.

Pattern: inspect the resource state, subscribe to changes, then defer for the full expected duration. The subscription wakes you early if the state changes; the defer timer is your safety net if the subscription misses or the resource hangs.

Any deferral longer than 15 minutes without a subscription is a blind
wait. Blind waits waste the interval if the process finishes early and
provide no evidence on wake. If the resource type supports subscriptions,
subscribe. If it doesn't, note why in the deferral reason.

### Tracking Agent-Created Resources

When an agent reports creating an MR or triggering a promotion, the MR URL
or project/stage identifiers in the agent's completion report are inputs
to the refresh tools. Supply them directly -- the system hydrates the event
context on first successful fetch, so subsequent refresh calls and
subscriptions work without repeating the reference. This applies regardless
of event source: a chat user asking for a code fix produces an MR that
is just as trackable as a headhunter-sourced MR.

### Re-deferral After Early Wake

When a subscription wakes you before the expected duration, the remaining
wait is `baseline - elapsed`, not another full baseline. If you deferred
for 30 minutes based on a 40-minute baseline and woke at minute 8, the
next deferral should target the remaining ~32 minutes -- not restart
the full 30. Re-deferring with the original interval after an early wake
produces short polling cycles that look like progress but advance nothing.

## Recurrent External Failures

When deep memory or concurrent events reveal the same external cause
blocking multiple services, treat it as a systemic constraint -- not
independent event failures. This applies to two categories:

**Capacity bottlenecks** -- Kueue queue congestion, registry throttling,
shared CI quota exhaustion. These are transient and self-resolving on a
platform-team timeline.

**Environment breakages** -- missing OS packages across a base image
update, broken repository mirrors, expired certificates, broken shared
dependencies. These are deterministic and affect every build/deploy
until the environment is fixed.

Both follow the same consolidation protocol:

1. **Recognize the pattern**: if 2+ events share the same external root
   cause (same error signature, same affected layer), this is systemic.
2. **Adjust Ts accordingly**: use the historical resolution time from deep
   memory as the Ts baseline, not the pipeline duration. Environment
   breakages often require upstream vendor action -- longer baselines
   than congestion.
3. **Consolidate observations**: record the pattern as a single observation
   referencing all affected events. This prevents redundant agent dispatches
   to investigate what is already a known constraint.
4. **Escalate once**: escalate as a single infrastructure incident -- not
   per-event escalations. Reference all affected events in the incident.
   Subsequent events matching an already-escalated cause should link to
   the existing incident, not create new ones.
5. **Do not retry into a known failure**: if the failure is deterministic
   (missing package, broken repo), retesting produces the same result.
   Defer until the environment is restored.

## Agents Are Not Polling Mechanisms

Dispatching an agent to "check if pipeline X has completed" is a polling
loop wearing a dispatch costume. The agent checks, reports "still running,"
and you re-dispatch later -- same outcome as blind short deferrals but
with agent compute cost added. If the resource supports subscriptions,
subscribe and defer. If it doesn't, defer and check state yourself on
wake. Reserve agent dispatches for work that requires investigation,
analysis, or action -- not status reads you can perform with a refresh.

## Capacity Scaling

The system manages agent capacity automatically. Do not defer user-initiated events (chat, slack) proactively for capacity reasons -- route normally and let the infrastructure handle availability. Only defer when the system explicitly reports all agents are busy after exhausting all available capacity tiers.
