---
description: "Flow engineering principles for throughput optimization and congestion prevention"
tags: [flow, queuing, batch-size, congestion, throughput]
tools: [defer_event, refresh_gitlab_context, refresh_kargo_context, hold_watch]
---
# Flow Engineering

**Phase gate:** `always/09-phase-lifecycle.md` § Defer discipline governs phase
sequencing before any deferral. Consult it.

## Saturation Response

When the system is saturated (agents busy, queue growing), the correct response
is to reduce intake — not try harder. Finish in-flight work before accepting
new automated events. Completing one event frees capacity for the next.
User-initiated events (chat, slack) are never capacity-deferred.

## Batch Size

Smaller tasks complete faster without adding capacity. When dispatching
COMPLICATED or COMPLEX work, decompose into the smallest independently-verifiable
batch and dispatch only that batch. Evaluate the result, then dispatch the next.

## Subscription Over Blind Waits

**Prefer subscribing** to state changes over short-interval deferrals. A subscription
wakes you with structured evidence of what changed; a blind timer gives you
nothing on wake except the obligation to measure again. If a resource supports
subscriptions, subscribe before deferring. The defer timer is your safety net
if the subscription misses or the resource hangs.

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

## Systemic Failures

When multiple events share the same external root cause, that is a systemic
constraint — not independent failures requiring independent investigation.
The behavioral response: consolidate into one observation, calibrate Ts from
deep memory's resolution baseline for that failure class, escalate once as a
single incident referencing all affected events, and do not retry into a known
deterministic failure. Per-event investigation of a shared cause wastes agent
capacity on redundant work.

## Repetition Without Change

Same input applied to the same state produces the same output. Before retrying
anything — agent dispatch, pipeline retest, refresh, retest command — ask:
"what has changed since the last attempt?" If nothing in the environment changed,
the result will be identical. New evidence, a code fix landing, a config change,
or elapsed recovery time are valid reasons to retry. "Maybe it will work this
time" is not.

## Agent Dispatch Is for Work

A dispatch to "check if X has completed" is a polling loop wearing a dispatch
costume. Reserve agent dispatches for investigation, analysis, or action. Status
reads are your job — use refresh tools and subscriptions. The distinction:
if you could answer the question with a single tool call, don't send an agent.

## Two Kinds of Deferral

- **Domain-Ts (strategic)**: The control loop schedules the next feedback sample.
  You chose a sampling interval based on severity, baseline, and progress signals.
  The process needs time, not another check.
- **Congestion-defer (backpressure)**: You defer because agents are busy, not
  because the strategy calls for observation. This is queue management.

These produce different reasoning. Domain-Ts reasons about the process timeline.
Congestion-defer reasons about system capacity. Do not confuse them.