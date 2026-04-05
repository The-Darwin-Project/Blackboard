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
- Never respond to congestion by increasing parallelism beyond available agent capacity -- that causes congestion collapse.
