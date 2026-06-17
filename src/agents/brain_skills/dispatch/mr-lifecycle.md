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

## Investigation Before Action

When an MR/PR pipeline has failed, the failure logs must be analyzed BEFORE
any retry, retest, or remediation action -- even when Bot Instructions
explicitly say "retest" or "trigger /ok-to-test." Bot Instructions describe
the INTENDED workflow; they do not override the need to understand WHY the
pipeline failed.

Sequence:
1. Dispatch an agent to retrieve and analyze the failed pipeline logs.
2. Record the failure root cause as an observation.
3. If the failure is transient (infra flake, quota timeout, network blip)
   AND deep memory confirms this pattern resolves on retry → proceed with
   the Bot Instructions retest action.
4. If the failure is deterministic (code bug, missing dependency, known
   upstream breakage) → retesting will produce the same failure. Skip the
   retest. Escalate or apply a fix instead.
5. If deep memory surfaces a known non-recoverable pattern for this failure
   signature → do NOT retest. Close or escalate based on the Bot Instructions
   failure path.

A blind retry on a deterministic failure wastes a full pipeline cycle and
delays actual resolution.

## MR/PR Comment Retrieval

CI bot output, review feedback, and prior action history live primarily in
MR/PR comments. When investigating or executing on an MR/PR event:

1. Retrieve recent MR/PR comments as part of the initial investigation.
2. CI bot comments contain pipeline failure details, test results, and
   approval status that may not appear in the pipeline API response.
3. Review comments may contain context about known issues or prior fixes
   attempted by the author.

Skipping comment retrieval means operating on incomplete evidence.

## MR/PR Holistic State

A pipeline failure is not the only reason an MR/PR is blocked. An MR/PR can also be
blocked by merge conflicts, missing rebase against the target branch, or
outdated dependencies. A recent merge to the target branch may have already
introduced the fix that this MR/PR needs -- a rebase would pick it up.

When investigating MR/PR failures, the full picture includes: pipeline status,
merge conflicts, rebase state, and recent merges to the target branch that
may resolve the issue without a code change.

## Bot MR Merge Conflicts

Merge conflicts on bot-authored MRs are not investigable -- they resolve
by bot regeneration or rebase, not by human or agent conflict resolution.
Do not dispatch an agent to fix a bot's merge conflict.

A conflicted MR also cannot be retested, so conflict state takes
precedence over pipeline failure investigation.

The key question is whether the bot is still actively maintaining this MR.
Check the MR's recent activity and compare it against the bot's observed
cadence from deep memory. A bot that is still active will rebase on its
own schedule -- defer and let it. A bot that has gone silent longer than
its usual cycle has likely moved on -- the MR is stale, close the event
and notify the maintainer. When no prior cadence data exists, give the bot
one deferral window before treating it as stale.

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
