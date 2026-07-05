---
description: "Flow engineering principles for throughput optimization and congestion prevention"
tags: [flow, queuing, batch-size, congestion, throughput]
tools: [defer_event, refresh_gitlab_context, refresh_kargo_context, hold_watch]
---
# Flow Engineering

**Phase gate:** `always/09-phase-lifecycle.md` § Defer discipline governs phase
sequencing before any deferral. Consult it.

## Saturation Response

System saturation means throughput has hit the capacity ceiling. Adding more
work increases queue time for everything already in flight (Little's Law:
L = λ × W) — this means more arrivals degrade ALL work, not just the new work.
Finish in-flight work before accepting new automated events. Completing one
event frees capacity for the next. User-initiated events (chat, slack) are
never capacity-deferred.

## Batch Size

Large batches compound variability at both ends — more time in queue and more
time in processing. Smaller batches flow faster through the same capacity
because they encounter less contention and produce feedback sooner — errors are
caught one batch earlier instead of after the entire payload completes. When
dispatching COMPLICATED or COMPLEX work, decompose into the smallest
independently-verifiable batch and dispatch only that batch. Evaluate the
result, then dispatch the next.

## Subscription Over Blind Waits

A blind timer gives you no information on wake — only the obligation to measure
again. A subscription delivers structured evidence of what changed, letting you
act immediately on the new state. If a resource supports subscriptions, subscribe
before deferring. The defer timer is the safety net (what if the subscription
misses or the resource hangs), not the primary feedback channel.

When woken early by a subscription, the remaining wait is `baseline - elapsed`,
never a full restart. Re-deferring with the original interval produces polling
that advances nothing.

Subscriptions catch terminal transitions but not mid-execution stalls. Silence
during a long deferral does not confirm progress — it only confirms the process
hasn't terminated. When a wait is proportionally long relative to the historical
baseline and no state change has fired, query for intermediate progress before
continuing to defer. A refresh that shows the same pipeline step as when you
deferred is evidence of a stall — act on it rather than waiting for the full
window to expire.

### Re-subscription After Process Triggers

A subscription monitors one specific external process instance — a pipeline run,
a promotion step, a CI job. Triggering a new process creates a new instance
with a new identity. The old subscription's state key is bound to the terminated
process — it watches dead state while the new one runs unobserved.

After any command that triggers a new async process, re-subscribe to the new
process's state changes before deferring. A deferral without re-subscription
after a trigger reverts to blind polling — the subscription infrastructure is
running but watching a process that already terminated.

### Adaptive Fallback on Subscription Misses

When a subscription-backed deferral expires and the refresh reveals the process
completed before the timer fired, the subscription missed the terminal
transition. One miss is noise — infrastructure hiccup, webhook delivery failure,
race condition. Consecutive misses on the same resource type are signal —
the subscription channel is unreliable for this resource.

Shorten the fallback interval proportionally on consecutive misses. The safety
net compensates for unreliable subscriptions by checking more frequently, not
by stretching the same interval and hoping the next subscription fires. When
three consecutive deferrals expire without any subscription notification on
processes that completed mid-window, treat subscriptions as degraded for that
resource type and switch to refresh-based polling at the process's historical
median duration.

## Systemic Failures

### Correlate Before Dispatch

Infrastructure-layer failures (git clone, registry access, build environment,
queue admission) operate below application code — they affect all events
equally. When the failing task is infrastructure-layer, the failure signature
is more likely shared across events than isolated to one.

Before dispatching an investigation for an infrastructure-layer failure, check
whether the same failure signature has been observed across other events.
If it has, the root cause is already known — join the existing consolidation
artifact and defer on its resolution timeline. Dispatching a new investigation
produces the same finding that already exists.

### Consolidation

Independent investigation of symptoms that share a root cause produces redundant
work — N agents each discover the same underlying problem. The cost scales
linearly with affected events while the information gain is zero after the first.
Consolidation converts O(N) agent dispatches into O(1). The behavioral response:
consolidate into one observation, calibrate Ts from historical resolution baselines
for that failure class, escalate once as a single incident referencing all affected
events, and do not retry into a known deterministic failure.

Once a systemic consolidation artifact exists (tracking issue, incident
report), it becomes the reference point for all affected events. Link
affected events back to the consolidation artifact so they defer on its
resolution rather than escalating independently. New events matching the
same root cause should discover the existing artifact and join it rather
than creating a parallel escalation.

### Transient → Systemic Reclassification

"Transient" is a temporal property of a first occurrence — not a permanent
exemption from the repetition guard. Consecutive transient failures reveal a
sustained broken state, not a sequence of independent coin flips.

**Internal infrastructure failures** (agent dispatch, EventListener,
sidecar connectivity, Git clone for sidecars) are Darwin's own
execution path. A single failure here is already systemic — the provisioner
has visibility into infrastructure state that you do not. When dispatch
returns a structured failure with a recommended wait, defer for that duration.
Do not override it with your own estimate or retry the dispatch independently.
The Dispatcher handles these deferrals autonomously via conversation turns —
when you read `[Dispatch: paused]`, the event is already deferred with a
calibrated wait. Do not manually defer or retry.

**External process failures** (pipeline retests, build retriggers, promotion
retries Kueue admission) operate on infrastructure you observe but do not control. Apply the
following threshold: two or more identical failure signatures on the same
service within one event, or the same failure class appearing across two or
more concurrent events on the same service, triggers systemic reclassification.
Once reclassified, consolidate all affected events and defer on the resolution
timeline — independent retry loops on individual events are forbidden.

## Repetition Without Change

Same input applied to the same state produces the same output — this is
determinism. Retrying a deterministic failure without changing the input is
not optimism, it is a guarantee of the same result. Before retrying anything —
agent dispatch, pipeline retest, refresh, retest command — ask: "what has
changed since the last attempt?"

A retry is authorized only when a refresh or subscription confirms the failing
resource has transitioned to a different state than the one that produced the
failure. Valid state transitions: new pipeline status, recovered dependency,
changed HTTP response code, config change, code fix merged. Elapsed time
alone is not a state transition — it is hope wearing a timestamp.

## Agent Dispatch Is for Work

Dispatch has overhead: context loading, skill injection, sidecar startup,
capacity slot consumption. Using that mechanism to answer a yes/no state
question is the equivalent of hiring a contractor to check if your porch
light is on — you can see it from where you stand.

A dispatch to "check if X has completed" is a polling loop wearing a dispatch
costume. Reserve agent dispatches for investigation, analysis, or action.
Status reads are your job — use refresh tools and subscriptions.
The distinction:
if you could answer the question with a single tool call, don't send an agent.

## Two Kinds of Deferral

Conflating strategic and capacity deferrals produces confused reasoning — you
might justify a long wait using process-timeline logic when the real reason is
backpressure, or rush a strategic observation because you mistook it for a
queue management decision.
Correctly sized deferrals based on drain expectations vs typical CI execution baselines

- **Domain-Ts (strategic)**: The control loop schedules the next feedback sample.
  The process needs time, not another check. Reasoning is about the process timeline.
- **Congestion-defer (backpressure)**: You defer because agents are busy, not
  because the strategy calls for observation. Reasoning is about system capacity.

### Congestion-Aware Deferral Sizing

Multiple concurrent events deferred for the same infrastructure cause (pipeline
queue admission, shared resource contention, multi-arch build saturation) are
evidence of systemic congestion — not independent delays. Each event measuring
the same bottleneck independently produces N identical observations at the cost
of N wake cycles with zero new information.

Size congestion deferrals from deep memory's observed congestion window duration,
not from individual process baselines. A process that normally completes in 30
minutes takes 60+ during systemic saturation — the difference is the congestion
penalty. Using the normal baseline produces premature wakes that observe
unchanged state, accumulating short deferrals that sum to far more than a single
calibrated wait would have cost.

When total deferral time on the same shared root cause exceeds deep memory's
historical congestion window median without state change, the congestion has
exceeded historical bounds. Escalate as a systemic incident rather than
continuing to defer — unbounded waiting without a ceiling is a missing circuit
breaker, not patience.
