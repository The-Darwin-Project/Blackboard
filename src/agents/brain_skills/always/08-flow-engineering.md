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

Independent investigation of symptoms that share a root cause produces redundant
work — N agents each discover the same underlying problem. The cost scales
linearly with affected events while the information gain is zero after the first.
Consolidation converts O(N) agent dispatches into O(1). The behavioral response:
consolidate into one observation, calibrate Ts from
deep memory's resolution baseline for that failure class, escalate once as a
single incident referencing all affected events, and do not retry into a known
deterministic failure. Per-event investigation of a shared cause wastes agent
capacity on redundant work.

Once a systemic consolidation artifact exists (tracking issue, incident
report), it becomes the reference point for all affected events. Link
affected events back to the consolidation artifact so they defer on its
resolution rather than escalating independently. New events matching the
same root cause should discover the existing artifact and join it rather
than creating a parallel escalation.

## Repetition Without Change

Same input applied to the same state produces the same output — this is
determinism. Retrying a deterministic failure without changing the input is
not optimism, it is a guarantee of the same result. Before retrying anything —
agent dispatch, pipeline retest, refresh, retest command — ask: "what has
changed since the last attempt?" Valid retries require a change in the
environment: code fix, config change, recovered dependency, or elapsed
recovery time. "Maybe it will work this time" is not a change.

Recognize that transient failures are not exceptions to determinism,
but the result of a temporarily broken external environment state.
You must only authorize a retry if sufficient Evidance exist.

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
