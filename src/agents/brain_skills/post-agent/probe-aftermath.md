---
description: "Probe cleanup obligation: revert failed probe artifacts before proceeding"
tags: [probes, cleanup, complex, revert, safety]
---
# Probe Aftermath: Cleanup Obligation

When you dispatch an agent to execute a safe-to-fail probe in the COMPLEX domain,
and that agent modifies a mutable artifact (pushes a commit, changes a Dockerfile,
creates a resource), the probe creates a **cleanup obligation**.

## The Principle

Safe-to-fail means safe-to-revert. A probe that changes a branch, file, or
resource is only "safe" if the change is actually reversed when the probe fails.
Leaving failed probe artifacts on a branch is not safe-to-fail — it is
safe-to-forget, and the artifact ships silently when a later pipeline succeeds.

## Obligation Lifecycle

1. **Created**: When an agent returns results confirming it pushed a commit,
   changed a file, or created a resource as part of a probe. The conversation
   turn from the dispatch contains the artifact details (commit SHA, branch,
   file path).

2. **Active**: When the probe outcome is negative — no pattern emerged, the
   pipeline failed, or the hypothesis was falsified. The obligation remains
   active until the artifact is reverted.

3. **Dissolved**: Two paths:
   - **Probe succeeded** — a pattern emerged and you reclassify to COMPLICATED.
     The artifact is now part of the solution. Obligation dissolves naturally.
   - **Artifact reverted** — an agent reverted the probe commit or undid the
     resource change. Obligation is satisfied.

4. **Escalated**: If the probe limit is reached and you escalate, include the
   cleanup status in the escalation evidence. The human taking over needs to
   know what probe artifacts remain on the branch.

## When to Clean Up

Before any of these transitions, check whether an active cleanup obligation exists:

- Before dispatching the **next** probe (revert the failed one first)
- Before **reclassifying** out of COMPLEX to a different strategy
- Before **escalating** (document what artifacts remain)
- Before **closing** (no event should close with unreversed probe artifacts)

## How to Clean Up

Review your conversation history for the probe dispatch turn — it contains the
commit SHA and branch. Route the agent that made the change (or SysAdmin) with
a revert task: `git revert <commit-sha>` on the source branch, then push.

If the revert itself fails (merge conflict, protected branch, permission), that
is escalation-worthy evidence — do not silently proceed. Include the failed
revert in your escalation.

## Why This Matters

MR pipelines validate the HEAD commit, not individual commits in the history.
When a probe pushes commit A (fails) and a later fix pushes commit B (succeeds),
the pipeline runs against HEAD (which includes both A and B). MWPS auto-merges
on pipeline success — shipping probe artifact A alongside intended fix B.
The pipeline gate protects main from broken builds, but it does not protect the
branch from accumulated probe debris.
