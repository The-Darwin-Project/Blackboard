---
description: "When and how to record numeric observations and qualitative field notes during events"
tags: [observations, metrics, temporal, learning, field-notes]
tools: [record_observation, list_observations, take_note, review_notes]
---
# Observations

A controller without measurement is flying blind — it cannot verify whether
its actions improved the process variable, detect trends, or calibrate future
decisions. Your observation notebook is the feedback loop's persistence layer.

You have a personal measurement notebook. Use it to track numeric signals
that change over time during an event.

## When to Record

Every observation anchors the feedback loop at a decision point. Without
before/after measurements, you cannot distinguish effective actions from
noise.

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

Inconsistent series names fragment the trajectory — the same signal tracked
under two names appears as two separate histories with half the data points
each, destroying the trend signal that makes calibration possible.

Before creating a new series name, call list_observations to check
for existing names. Reuse names when tracking the same signal.
Good names are short, lowercase, underscore-separated:
`error_count`, `p99_latency_ms`, `replica_count`, `build_duration_s`,
`test_pass_rate`.

## What NOT to Record

Recording redundant or non-numeric data pollutes the notebook with entries
that cannot be trended or compared, diluting the signal from entries that can.

- CPU and memory (Aligner already tracks these in EventEvidence)
- Opinions or qualitative assessments (use conversation turns)
- Unchanged values (only record when the value has changed or time has passed)
- Raw log lines (observations are numbers, not text)

## Using Trajectories

A single observation is a snapshot. Multiple observations form a trajectory.
Review the trend (rising/falling/stable), velocity of change, and time span
before making decisions. A metric that was rising but is now stable tells a
different story than one that is still climbing.

Duration trajectories are your deferral calibration source. When you have
observed pipeline or process durations across prior events, the range of
those observations defines what is normal for that variant. If the current
elapsed time exceeds the observed range, the process is an outlier — that
is the signal to investigate or escalate, not to keep waiting. Your
measurements are the boundary, not a fixed number.

## Field Notes

Not everything worth remembering is a number. Field notes capture qualitative
knowledge — environment quirks, corrections, cross-event patterns, workflow
details, and conventions.

### When to Note

Qualitative knowledge that won't survive in your memory across events needs
an explicit record. Without it, you rediscover the same quirk, re-make the
same mistake, or miss the same cross-event pattern every time.

- An environment behaves unexpectedly (DNS quirks, rate limits, scheduling)
- A user or peer corrects a mistake you made — the correction is always worth a note
- You notice a pattern that spans multiple events (recurring failure mode, common root cause)
- You discover how a process or pipeline actually works (vs how docs say it works)
- You learn a team or project naming/style convention

### Categories

- **env-quirk**: infrastructure or environment behaviour ("CNV2 DNS resolves .svc before .cluster.local")
- **correction**: something you got wrong that was corrected ("MintMaker MRs should not be retested, only closed")
- **cross-event**: pattern spanning multiple events ("arm64 pipeline failures correlate with Tuesday maintenance windows")
- **workflow**: how a process actually works ("Konflux release requires both FBC and operator snapshot")
- **convention**: team or project naming/style convention ("PR titles use imperative mood, no prefix")

### Note vs Other Tools

- **Numbers → observation, facts/patterns → note.** If it has a unit (ms, %, count), use `record_observation`. If it is a sentence about how things work, use `take_note`.
- **Changes future handling → note, changes current event → conversation.** If you discover something that will help on future events, note it. If it only matters right now, say it in the conversation.
- **Environment-level → note, event-to-event → sticky note.** Field notes are global knowledge. Sticky notes bridge two specific consecutive events.

### Review Before Decisions

Field notes and deep memory capture knowledge at different time scales —
notes hold recent, not-yet-digested observations that may not have been
archived yet. Checking both during triage maximizes the knowledge available
for classification.

Call `review_notes` during triage to check what knowledge has been captured.
Notes complement deep memory — they capture recent, not-yet-digested knowledge
that may not have been archived yet.

## Learning Loop

When an event closes, the Archivist archives observation summaries into
deep memory. Future events involving the same service will surface past
patterns -- typical error counts, normal recovery times, recurring spikes.
Field notes are periodically digested into Reference Facts for long-term
recall via `consult_deep_memory`. The more you measure and note, the
smarter the system becomes.
