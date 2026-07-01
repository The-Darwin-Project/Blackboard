---
description: "MR/PR lifecycle awareness and pipeline fix principles"
tags: [headhunter, mr, lifecycle]
---
# MR/PR Lifecycle Awareness

An MR/PR is a moving target — its state can change between event creation and dispatch. Acting on stale state (retesting an already-merged MR, investigating a closed one, dispatching while a pipeline is mid-run) wastes dispatch cycles on work that either no longer matters or will produce misleading results.

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

## Multi-MR Events

Some events track multiple MRs — batch backports across version branches,
multi-repo promotions, or grouped dependency updates. The state refresh
mechanism operates on one MR at a time. Refresh each MR individually by
supplying its URL. This produces per-MR state snapshots that can be compared
in a single decision — which MRs are merged, which pipelines are still
running, which are blocked. Do not dispatch an agent to collect state that
sequential refresh calls can provide.

## Investigation Before Action

Bot Instructions describe the intended happy-path workflow, but they were written before the failure occurred — they cannot know whether this specific failure is transient or deterministic. Only the failure logs carry that signal. A blind retry on a deterministic failure wastes a full pipeline cycle (often 30-60 minutes) and delays actual resolution by exactly that duration.

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

### Build Dependency Failures Requiring Upstream Intervention

Hermetic, offline, and cached builds run without live network access. When a
dependency is missing from the prefetch cache, lockfile, or vendored artifacts,
the build fails deterministically — no retry will make the dependency appear
because the cache state is fixed by the source manifest (lockfile, vendor dir,
prefetch config).

Recognition signals: offline install errors, cache miss errors, dependency
resolution failures that reference a registry the build cannot reach, lockfile
mismatch errors during hermetic or air-gapped builds.

Why this matters: the fix lives upstream (regenerate lockfile, update prefetch
config, add missing dependency to vendor). No amount of in-pipeline investigation
or retesting changes the outcome. Agent dispatches to "investigate" will always
find the same root cause.

When you recognize this class of failure:
- Check whether a tracking incident already exists for this failure pattern
- If tracked: link and defer on the incident timeline (do not re-investigate)
- If new: escalate once, create the tracking incident, notify maintainers
- For bot-authored MRs: close the MR with an explanatory comment — the bot
  will recreate when the upstream fix lands
6. After issuing any command that triggers a new pipeline, re-subscribe
   to the new pipeline's state changes before deferring. The previous
   subscription watches the old pipeline — it will never fire for the
   new one (see always/08-flow-engineering.md § Re-subscription After
   Process Triggers).

## MR/PR Comment Retrieval

CI bots, reviewers, and prior agents leave context in MR/PR comments that doesn't appear in the pipeline API response — test result summaries, approval status, known issues flagged by the author, and prior fix attempts. Operating without this context means the investigating agent may propose a fix that was already tried and failed, or miss approval blockers invisible in pipeline status alone.

CI bot output, review feedback, and prior action history live primarily in
MR/PR comments. When investigating or executing on an MR/PR event:

1. Retrieve recent MR/PR comments as part of the initial investigation.
2. CI bot comments contain pipeline failure details, test results, and
   approval status that may not appear in the pipeline API response.
3. Review comments may contain context about known issues or prior fixes
   attempted by the author.

Skipping comment retrieval means operating on incomplete evidence.

## MR/PR Holistic State

Pipeline failure is the loudest signal, but it's not the only reason an MR/PR is blocked. Investigating only the pipeline while ignoring merge conflicts or stale rebases leads to a fix that passes CI but still can't merge — the agent's work was correct but incomplete. A recent merge to the target branch may have already introduced the fix that this MR/PR needs.

A pipeline failure is not the only reason an MR/PR is blocked. An MR/PR can also be
blocked by merge conflicts, missing rebase against the target branch, or
outdated dependencies. A recent merge to the target branch may have already
introduced the fix that this MR/PR needs -- a rebase would pick it up.

When investigating MR/PR failures, the full picture includes: pipeline status,
merge conflicts, rebase state, and recent merges to the target branch that
may resolve the issue without a code change.

## Bot MR Merge Conflicts

Bot-authored MRs are generated artifacts — their content comes from automated processes (Kargo stages, submodule updaters, release pipelines), not human authoring. Merge conflicts in generated content can't be resolved by an agent editing individual lines; the bot needs to regenerate from its source data against the updated target branch. Dispatching an agent to resolve a bot's conflict is the wrong abstraction level.

Merge conflicts on bot-authored MRs are not investigable -- they resolve
by bot regeneration or rebase, not by human or agent conflict resolution.
Do not dispatch an agent to fix a bot's merge conflict.

A conflicted MR also cannot be retested, so conflict state takes
precedence over pipeline failure investigation.

Two bot behaviors determine the correct response:

**Rebasing bots** update the existing MR branch in place (e.g., automated
rebase bots, some CI fixup bots). A rebasing bot will resolve conflicts on
its own schedule — check its observed cadence from deep memory and defer
one cycle. A bot that has gone silent longer than its usual cadence has
likely moved on — close the event and notify the maintainer. When no prior
cadence data exists, give the bot one deferral window before treating it
as stale.

**Regenerating bots** close and recreate MRs on each cycle (dependency
updaters, submodule sync, Kargo stages). A regenerating bot will never fix
this MR — it will create a new one on its next run. Keeping the conflicted
MR open either blocks the bot's next cycle or produces a duplicate. Close
the conflicting MR with a comment explaining the automated closure reason
(merge conflicts on a bot-regenerated MR), close the Darwin event, and
notify the maintainer. Do not defer, do not escalate for human conflict
resolution — that is the wrong abstraction level for generated content.

**Exception — explicit tracking instructions:** If the MR description
contains explicit instructions not to close (e.g., state-tracking MRs
where the promotion system monitors MR existence), respect that over the
default auto-close behavior. The MR author knows the lifecycle better
than the default rule. Defer and let the tracking system handle it.

## Auto-Merge Invalidation on New Commits

Auto-merge (merge-when-pipeline-succeeds) is invalidated by the platform when
a new commit lands on the source branch — the new commit hasn't been validated
yet. For bot-authored MRs that receive frequent updates, auto-merge gets
disabled on every push and nobody re-enables it. The MR sits with a passed
pipeline but no merge trigger, accumulating deferrals until a human notices.

When a refresh shows a bot-authored MR with a passed pipeline, open state,
and no merge conflicts — but the MR is not merging — the likely cause is
invalidated auto-merge. Request the merge directly rather than deferring
and waiting for a mechanism that was already disabled.

## MR/PR Pipeline Fix Principle

The entire purpose of an MR/PR pipeline is to validate changes before they reach main. Merging an untested fix to main first and then rebasing the MR defeats this validation gate — main now contains a change that was never pipeline-validated, and the MR pipeline result no longer tests the original change in isolation.

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
