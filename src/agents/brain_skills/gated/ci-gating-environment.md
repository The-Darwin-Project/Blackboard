---
description: "CI gating environment capabilities and verification principles"
tag_type: context
tags: [ci_gating, environment]
tools: [greenwave, ask_release_ai]
---
# CI Gating Environment

## Evidence Interpretation

`ci_context` carries the observer's structured triage: failed and missing job lists, build
numbers, result statuses, console output (capped), and an LLM failure-type classification
(infra / test / product). The classification addresses *what kind of failure* occurred —
infrastructure flakiness, test regression, or product defect — not which Cynefin domain
applies. Domain assessment is independent.

Parsed `job_metadata` (when present) adds topology: `type` distinguishes wrappers from
test leaves, `version` provides an authoritative CNV version, and `owner` / `team` /
`labels` identify the human owners of the failing test. Owners are escalation targets,
not dispatch targets — Darwin investigates; humans own the test code.

## Wrapper vs Leaf Topology

A wrapper failure aggregates independent lanes. The wrapper result alone does not reveal
which lane failed or how many. The leaf jobs inside it are the diagnostic signals.
Re-triggering a wrapper re-runs ALL lanes — the cost is proportional to the total
remaining work, not just the failed lane. When multiple lanes fail independently, each
may have a different root cause.

## Gating Decision as Closure Signal

A single CI job passing is not resolution. The gating decision service aggregates multiple
jobs and policy requirements across the release. Satisfaction of the gating decision is
the terminal state — verify it before closing. A pipeline retry in progress is a
non-terminal state: defer, do not close.

## Release AI as Investigator

The release-console AI synthesizes across Jenkins, Prow, ReportPortal, Jira, and Errata.
It can provide root cause analysis for specific job failures, historical failure patterns
for the same job/NVR, and cross-references with known issues.

Frame questions precisely: include the NVR, job name, and failure evidence. One
well-framed question yields more context than multiple narrow queries because the
synthesis happens across data sources internally.

## Timing Cadence

Wrapper and tier jobs take 6–9 hours. Nightly builds run overnight; candidate builds
follow release milestones. "Late" is relative to the pipeline cadence, not wall-clock.
A nightly job absent at 06:00 UTC is expected; absent at 12:00 UTC warrants investigation.
Deferral intervals should be proportional to the expected remaining job duration — not
a fixed default.

## Memory Validation

Deep memory and observations record past state — they describe what was true at the
time of recording, not what is true now. A "known flaky job" memory from last week may
have been fixed since. Before acting on historical patterns, validate the assumption
against current evidence: has the job's failure signature changed? Has the infrastructure
issue been resolved? Stale memory applied as current fact leads to misdiagnosis.
