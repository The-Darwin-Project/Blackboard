---
description: "When and how to record numeric observations during events"
tags: [observations, metrics, temporal, learning]
---
# Observations

You have a personal measurement notebook. Use it to track numeric signals
that change over time during an event.

## When to Record

- Before a key decision (baseline snapshot)
- After an agent reports findings (capture the measured outcome)
- Before deferring (snapshot current state for future comparison)
- When a metric crosses a threshold you care about
- After a fix is applied (verify the change with numbers)

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
