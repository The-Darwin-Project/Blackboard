---
description: "CI gating event behavior — retry-first model, closure validation, release AI context"
tags: [aligner, ci_gating]
tag_type: rule
---
# CI Gating Source Rules

## Signal Origin

CI gating events originate from Jenkins job monitoring. The evidence contains structured
CI context: job name, build identifier, result status, and a failure-type classification
(infra / test / product) produced by the observer's LLM triage. This classification
addresses *what failed*, not *which Cynefin domain applies* — independent domain
assessment is still required.

## Retry-First Behavioral Model

CI job failures are overwhelmingly transient. Infrastructure flakiness, resource
contention, and timing issues account for the majority of failures. The appropriate
response model is: retry before investigate.

- A failed CI job should be restarted before any deeper analysis.
- After restart, the job needs time to complete. Wrapper and tier jobs
  take 6–9 hours. Do not check results immediately — defer with a timer
  proportional to the expected job duration.
- If the retry succeeds, validate the gating decision and close.
- If the retry also fails, the failure is likely systematic. At that
  point, consult the release AI for root cause context, historical
  patterns, and prior art on the same job.
- Escalation to the release manager is the last resort, after retry
  failure AND investigation confirms the issue is beyond automated
  resolution.

## Missing vs Never-Built Distinction

A "missing" CI job (expected but absent) is fundamentally different from a
"never-built" status (no build was ever attempted for this NVR). Missing jobs
indicate a pipeline gap or scheduling failure. Never-built may be normal for
newly onboarded components or skipped configurations. The CI context evidence
distinguishes these cases — act on the classification rather than assuming
all absent results are failures.

## Closure Validation

CI gating events require deterministic closure validation. Before closing,
query the gating decision service to confirm all required policies are
satisfied for the subject build. A passing Jenkins job alone is not
sufficient — the gating decision aggregates multiple test results and
policy requirements. Close only when the gating decision returns satisfied.

## Release AI Context

The release-console AI has access to Jenkins, Prow, ReportPortal, Jira,
and Errata data. It can provide:

- Root cause analysis for specific job failures
- Historical failure patterns for the same job/NVR
- Cross-reference with known issues and errata

Use it as a single-question investigative tool when retry fails. Frame
questions precisely: include the NVR, job name, and failure evidence.
The AI synthesizes across data sources — one well-framed question is
more effective than multiple narrow queries.

## Timing Awareness

CI pipelines have natural cadences. Nightly builds run overnight; candidate
builds follow release milestones. When assessing whether a job is "late" or
"stuck," consider the pipeline's expected schedule, not wall-clock elapsed
time alone. A nightly job absent at 06:00 UTC is expected; absent at
12:00 UTC warrants investigation.
