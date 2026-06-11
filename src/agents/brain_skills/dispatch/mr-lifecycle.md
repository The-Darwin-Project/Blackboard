---
description: "MR/PR lifecycle awareness and pipeline fix principles"
tags: [headhunter, mr, lifecycle]
---
# MR/PR Lifecycle Awareness

Source control events track MR/PR lifecycles. The MR/PR may have progressed since
the event was created -- it could already be merged, the pipeline may have
passed, or conflicts may have appeared. Refresh external state (budget-gated,
available in all phases) to check the CURRENT state, which supersedes the
original event evidence and any agent findings.

MR/PR terminal states (merged, closed) mean the issue is resolved or abandoned.
There is nothing for an agent to do on a terminal MR/PR -- no merge, no retest,
no investigation. The event is self-resolved.

MR/PR open + pipeline running means the pipeline is still in progress. Wait for
it to finish before acting.

MR/PR open + pipeline failed means the pipeline needs attention. The embedded
plan (Bot Instructions) describes the specific actions for this MR.

## MR/PR Holistic State

A pipeline failure is not the only reason an MR/PR is blocked. An MR/PR can also be
blocked by merge conflicts, missing rebase against the target branch, or
outdated dependencies. A recent merge to the target branch may have already
introduced the fix that this MR/PR needs -- a rebase would pick it up.

When investigating MR/PR failures, the full picture includes: pipeline status,
merge conflicts, rebase state, and recent merges to the target branch that
may resolve the issue without a code change.

## MR/PR Pipeline Fix Principle

When an MR/PR pipeline fails and a fix is needed (e.g., Dockerfile update, dependency bump):

- Fix the issue directly on the MR's source branch -- NEVER merge an untested fix to main first.
- The purpose of MR/PR pipelines is to validate changes BEFORE they reach main. Merging to main to rebase an MR/PR defeats this purpose.
- Tell the developer to apply the fix on the MR's source branch and verify a new pipeline starts.
- If the MR/PR was created by a bot (Kargo, submodule updater), the fix still goes on the MR's source branch.

### Terminology Safety

Pipeline trigger configurations use specific event type keywords (like
`pull_request`) that are NOT interchangeable with conversational terms.
Never rename or "correct" event type values in pipeline definitions,
annotations, or trigger bindings -- even if the terminology seems
inconsistent with the platform's UI language.
