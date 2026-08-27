---
description: "CI gating event envelope — Jenkins origin, wrapper topology, gating-decision lifecycle"
tags: [aligner, ci_gating]
tag_type: rule
---
# CI Gating Source Environment

## What This Source Means

`source=aligner` with `subject_type=ci_gating` means the detection bus observed a Jenkins
gating job failure — not an ArgoCD health anomaly, not a GitLab pipeline, not a Kargo
promotion. The Aligner's role is the same (sensor, not decision-maker), but the evidence
shape and closure semantics are entirely different from metric-based anomalies.

The close protocol for CI gating events is gating-decision satisfaction — all required
jobs pass or are waived — not "measured condition resolved." There is no metric threshold
to cross back below. The gating decision service aggregates multiple job results and policy
requirements; a single job passing is not closure.

## Evidence Shape

The `ci_context` evidence field carries structured data: failed and missing job lists,
build numbers, result statuses, console output (capped), and the observer's LLM triage.
The triage classification (infra / test / product) addresses *what kind of failure this
is*, not which Cynefin domain applies — independent domain assessment is still required.

Parsed `job_metadata` (from the JOB_METADATA build parameter, when present) provides:
- `type`: wrapper vs test leaf — wrappers aggregate independent lanes
- `version`: CNV version from the metadata, more authoritative than name-regex extraction
- `owner` / `team` / `labels`: identify the human owners of the failing test (escalation
  targets, not dispatch targets)

## Wrapper vs Leaf Topology

A wrapper job failure is not one failure — it aggregates independent lanes. The wrapper
result alone does not tell you which lane failed or how many. The leaf jobs inside the
wrapper are the real diagnostic signals. Re-triggering a wrapper re-runs ALL lanes, so
the cost is proportional to the total remaining work, not just the failed lane.

## Retry Before Investigation

CI job failures are overwhelmingly transient — infrastructure flakiness, resource
contention, and timing issues account for the majority. A restart before deeper
analysis is the natural first response because the expected value of a retry succeeding
exceeds the expected value of immediate investigation for most failure types.

After a restart, the job needs time to complete. Wrapper and tier jobs take 6–9 hours.
Attempting to check results immediately after a restart wastes a processing cycle with
no new information — defer proportional to the expected job duration.

If a retry also fails, the failure is likely deterministic. At that point, investigation
is warranted: consult the release AI for root cause context, historical patterns, and
prior art on the same job. Escalation to release maintainers is the last resort, after
retry failure AND investigation confirms the issue is beyond automated resolution.

## Missing vs Never-Built

A "missing" CI job (expected but absent) is fundamentally different from a "never-built"
status (no build was ever attempted for this NVR). Missing jobs indicate a pipeline gap
or scheduling failure. Never-built may be normal for newly onboarded components or skipped
configurations. The CI context evidence distinguishes these cases.

## Timing Cadence

CI pipelines have natural cadences. Nightly builds run overnight; candidate builds follow
release milestones. When assessing whether a job is "late" or "stuck," consider the
pipeline's expected schedule, not wall-clock elapsed time alone. A nightly job absent
at 06:00 UTC is expected; absent at 12:00 UTC warrants investigation.

## Scope Boundary

This source skill describes the Darwin event envelope only — what the event carries, how
closure works, and what the evidence means. Job-domain expertise (how to actually analyze,
fix, or triage a specific failing CI job) lives in the DevOps Skills Catalog, which is
available to dispatched sidecar agents. The orchestrator does not need that depth; the
agent does.
