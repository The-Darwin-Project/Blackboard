---
description: "When and how to record numeric observations during events"
tags: [observations, metrics, temporal, learning]
tools: [record_observation, list_observations]
---
# Observations

You have a personal measurement notebook. Use it to track numeric signals
that change over time during an event.

## When to Record

- **During triage** (baseline snapshot -- capture the PV before you act on it)
- Before a key decision (state before the controller output)
- After an agent reports findings (capture the measured outcome)
- Before deferring (snapshot current state for future comparison)
- When a metric crosses a threshold you care about
- After a fix is applied (verify the change with numbers)

The triage baseline is the most important observation. Without it, you have
no reference point when you later verify whether your actions improved the PV.
Even a single number (error count, pipeline duration, queue depth) recorded
at triage gives the feedback loop something to compare against.

After recording a baseline, list observations for the same series to see
the historical trajectory. A rising error count over 3 events tells a
different story than a one-off spike. The trend informs your domain
classification -- stable patterns suggest CLEAR, volatile patterns suggest
COMPLEX. Trends also tell you stories about external system health:
duration drift, increasing error rates, or shrinking capacity across events
signal infrastructure-level changes, not necessarily your service misbehaving.

Observations are also the bridge between events. Each event is isolated --
you only see one at a time. But observations persist across events for the
same service. When you list observations during triage, you're reading
messages your past self left for you.

## Naming Consistency

Before creating a new series name, call list_observations to check
for existing names. Reuse names when tracking the same signal.
Good names are short, lowercase, underscore-separated:
`error_count`, `p99_latency_ms`, `replica_count`, `build_duration_s`,
`test_pass_rate`.

## What NOT to Record

- CPU and memory (Aligner already tracks these in EventEvidence)
- Opinions or qualitative assessments (use conversation turns)
- Unchanged values (only record when the value has changed or time has passed)
- Raw log lines (observations are numbers, not text)

## Using Trajectories

A single observation is a snapshot. Multiple observations form a trajectory.
Review the trend (rising/falling/stable), velocity of change, and time span
before making decisions. A metric that was rising but is now stable tells a
different story than one that is still climbing.

## Learning Loop

When an event closes, the Archivist archives observation summaries into
deep memory. Future events involving the same service will surface past
patterns -- typical error counts, normal recovery times, recurring spikes.
The more you measure, the smarter the system becomes.
