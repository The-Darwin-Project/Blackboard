---
description: "Kargo promotion environment, capabilities, and verification principles"
tag_type: context
tags: [kargo, promotions, autonomous]
tools: [refresh_kargo_context]
---
# Kargo Promotion Environment

## Using memory to validate assumptions

Deep memory and observations are snapshots of past state -- they describe what was true at the time of recording, not what is true now. The gap between the memory's timestamp and the current failure is time during which the system may have changed. Acting on stale memory as if it were current fact leads to misdiagnosis: closing a failure as "known issue" when the known issue was already fixed, or escalating a resolved outage.

When using memory to validate failure, assess the memories as assumptions
that need to be validated -- both from the input value (how old the memory)
and the output signal of the source (how old is the failure). If the gap is
large, a change might have happened during the time shift. Systems change,
broken things get fixed. The goal is to validate that the assumption still
holds, not to act on stale knowledge.

## State Subscription

Polling via agent dispatch is expensive -- it consumes an agent slot, requires a full dispatch-verify cycle, and introduces latency. The refresh tools register background subscriptions that poll automatically and wake the event on state change. This is the native, low-cost mechanism for tracking progression through multi-step processes.

Kargo promotions and GitLab MRs are subscription-capable resources.
Calling refresh_kargo_context or refresh_gitlab_context registers a
background state subscription -- the system polls the resource and wakes
the event when state changes. This is the native mechanism for tracking
promotion step progression (build → push → wait-for-merge → MR opened).

An agent dispatch is not needed to answer "has this step finished yet?"
The refresh tool answers that question directly.

## Verification Integrity

Closing a Kargo event without observable proof means the outcome is unverified -- the event record shows "resolved" but nothing confirms the promotion actually succeeded. This corrupts the Ops Journal and misleads Nightwatcher's clustering.

Kargo promotions are observable resources. The evidence of success or failure
lives in the stage status and the MR pipeline -- not in reasoning or memory.

Closing a Kargo event requires observable proof: either a newer promotion
with phase=Succeeded on the same stage, or a verified root cause that is
documented and reported. "I believe it will fail" is not evidence -- it's
a hypothesis. Hypotheses are tested, not acted on.

If an agent reports it retried something, verify the outcome via
refresh_kargo_context before deciding next steps. Running state means
progress -- wait, but apply stall detection: prolonged running without step
progression relative to the historical baseline warrants investigation
(see always/06-decision-guidelines.md § Stall Detection). Errored with same
promotion means the retry didn't help. Errored with a new promotion name
means something else failed.

## MR-Blocked Promotions

When a promotion fails because of an MR issue, the Kargo stage status is a lagging indicator -- it only reflects that something is wrong, not what. The MR itself carries the leading signal: pipeline passed, conflicts resolved, approvals granted. Deferring on Kargo stage status when the MR is the actual bottleneck wastes the deferral interval with no new information on wake.

The MR URL from kargo_context enables direct tracking. Blind Kargo-level
deferrals on an MR-blocked promotion waste the interval when the MR merges
early and provide no evidence on wake.

## Error Natures

The nature of the error -- not its surface symptom -- determines what kind of investigation is needed. Different error types require fundamentally different response strategies: a merge timeout needs MR investigation, a config error needs code-level fixes, and a missing file points to an upstream repo change.

- **MR/PR merge timeout**: `step "wait-for-merge" timed out` -- the MR pipeline may have failed or is stuck. The MR is the signal source.
- **Config/expression error**: `failed to extract outputs: error compiling expression` -- the stage spec itself has a bug. Code-level fix required.
- **Missing files**: `error reading YAML file ... no such file or directory` -- repo structure changed upstream.
- **Auto-merge timeout**: `step "auto-merge" timed out` -- MR cannot merge (conflicts, approvals needed).

## Kargo Concepts

- Each Kargo **Stage** represents a deployment target in a CD pipeline.
- Each promotion attempt creates a **new Promotion CR** (retries are new objects, not state transitions on old ones).
- **Freight** is the versioned artifact being promoted (image, commit, chart).
- The observer watches `Stage.status.lastPromotion` -- the most recent attempt.
- Recovery = a newer Promotion on the same Stage reaches phase=Succeeded.
