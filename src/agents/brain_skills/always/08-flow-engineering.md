---
description: "Flow engineering principles for throughput optimization and congestion prevention"
tags: [flow, queuing, batch-size, congestion, throughput]
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

## Recurrent External Infrastructure Bottlenecks

When deep memory reveals that the same external infrastructure constraint
(Kueue queue congestion, registry throttling, shared CI quota exhaustion)
is blocking multiple services across multiple events:

1. **Recognize the pattern**: if 2+ events in deep memory share the same
   external bottleneck root cause, this is a systemic constraint -- not an
   individual event failure.
2. **Adjust Ts accordingly**: systemic constraints have their own resolution
   timeline (platform team intervention, quota refresh, congestion clearing).
   Use the historical resolution time from deep memory as the Ts baseline,
   not the pipeline duration.
3. **Consolidate observations**: record the bottleneck pattern as a single
   observation that references all affected events. This prevents redundant
   agent dispatches to investigate what is already a known constraint.
4. **Escalate once**: if the bottleneck persists beyond the historical
   resolution baseline, escalate as a single infrastructure incident -- not
   per-event escalations. Reference all affected events in the incident.
5. **Do not retry into a known bottleneck**: if the external system is
   congested, retesting or re-dispatching will produce the same queue wait.
   Defer until the constraint clears.

## Capacity Scaling

The system manages agent capacity automatically. Do not defer user-initiated events (chat, slack) proactively for capacity reasons -- route normally and let the infrastructure handle availability. Only defer when the system explicitly reports all agents are busy after exhausting all available capacity tiers.
