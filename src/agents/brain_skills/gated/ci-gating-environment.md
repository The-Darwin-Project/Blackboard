---
description: "CI gating environment capabilities and verification principles"
tag_type: context
tags: [ci_gating, environment]
tools: [greenwave, ask_release_ai, retrigger_jenkins_build]
---
# CI Gating Environment

## Evidence Interpretation

`ci_context` carries the observer's structured triage: failed and missing job lists, build
numbers, result statuses, console output (capped), and an LLM failure-type classification
(infra / test / product). The classification addresses *what kind of failure* occurred —
infrastructure flakiness, test regression, or product defect — not which Cynefin domain
applies. Domain assessment is independent.

Parsed `job_metadata` (when present) adds topology: `type` distinguishes wrappers from
test leaves, `version` provides an authoritative product version, and `owner` / `team` /
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
for the same job/build identifier, and cross-references with known issues.

Frame questions precisely: include the build identifier, job name, and failure evidence.
One well-framed question yields more context than multiple narrow queries because the
synthesis happens across data sources internally.

## Timing Cadence

Wrapper and tier jobs take several hours. CI pipelines run on varied schedules — some
overnight, some tied to release milestones. "Late" is relative to the pipeline's own
cadence, not wall-clock time. A scheduled overnight job still running in the morning is
expected; the same job absent well past its expected completion warrants investigation.
Deferral intervals should be proportional to the expected remaining job duration — not
a fixed default.

## Memory Validation

Deep memory and observations record past state — they describe what was true at the
time of recording, not what is true now. A "known flaky job" memory from last week may
have been fixed since. Before acting on historical patterns, validate the assumption
against current evidence: has the job's failure signature changed? Has the infrastructure
issue been resolved? Stale memory applied as current fact leads to misdiagnosis.

## Retriggering Transient Failures

When investigation (your own analysis or an agent's findings) concludes the root cause
is transient infrastructure — network timeouts, quota exhaustion, artifact mirror
unavailability — and NOT a test regression or product defect, you can
directly retest the job. The mechanism is scoped to jobs already present in this event's
failed_jobs context (cannot retrigger arbitrary Jenkins jobs) and rate-limited per job
to one retrigger per cooldown window. The window length is deployment-configured and
can change without notice -- if a retrigger is rejected as still-cooling-down, trust
the tool's response over any duration you recall, and treat a subsequent failure
after that rejection as a genuine new issue evaluated on its own terms.

Retriggering a wrapper job re-runs all lanes within it (see Wrapper vs Leaf Topology
above), consuming significant CI compute across every lane for however many hours the
full run takes — not just the one lane that failed. That cost makes a leaf-level retry
the preferred path whenever one is available: an agent with CI write access can
retrigger the specific leaf when dispatched for that purpose, and once it reports the retrigger together with
the new build number, the correct reconciliation is deferral for that leaf's expected
duration rather than a second retrigger at the wrapper level. When no leaf-level
alternative exists, confirming the root cause is transient infrastructure is what makes
the wrapper retrigger the correct reconciliation action — the wrapper's higher cost is
context for sequencing, not a reason to withhold the retrigger once transience is
confirmed.

When the failure evidence indicates a code defect, a test regression, or a persistent
infrastructure problem (repeated identical failures across multiple builds), escalate
to the owning team or dispatch investigation.
