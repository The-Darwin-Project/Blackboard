---
description: "Kargo promotion environment, capabilities, and verification principles"
tags: [kargo, promotions, autonomous]
---
# Kargo Promotion Environment

## Using memory to validate assumptions

when using memroy to validate failure, asses the memories as assumption that needs to be validateed;
both from the input value (how old the memory) and the output singal of the source(how old is the faliure), if the gap is big, a change might happened during the time shift;
so the goal is to validate the assumption is still currect after the time shift, systems chagens evolve and borken things get fixed;

## Verification Integrity

Kargo promotions are observable resources. The evidence of success or failure
lives in the stage status and the MR pipeline -- not in reasoning or memory.

Closing a Kargo event requires observable proof: either a newer promotion
with phase=Succeeded on the same stage, or a verified root cause that is
documented and reported. "I believe it will fail" is not evidence -- it's
a hypothesis. Hypotheses are tested, not acted on.

If an agent reports it retried something, verify the outcome via
refresh_kargo_context before deciding next steps. Running state means
progress -- wait. Errored with same promotion means the retry didn't help.
Errored with a new promotion name means something else failed.

## MR-Blocked Promotions

When a promotion failure is caused by an MR (merge timeout, pipeline failure,
auto-merge timeout), the MR is the observable resource -- not the Kargo stage.
The stage observer can only tell you it's still failing; the GitLab MR carries
the actual signal (pipeline passed, MR merged, conflicts appeared).

The MR URL from kargo_context enables direct tracking. Blind Kargo-level
deferrals on an MR-blocked promotion waste the interval when the MR merges
early and provide no evidence on wake.

## Error Natures

- **MR/PR merge timeout**: `step "wait-for-merge" timed out` -- the MR pipeline may have failed or is stuck. The MR is the signal source.
- **Config/expression error**: `failed to extract outputs: error compiling expression` -- the stage spec itself has a bug. Code-level fix required.
- **Missing files**: `error reading YAML file ... no such file or directory` -- repo structure changed upstream.
- **Auto-merge timeout**: `step "auto-merge" timed out` -- MR cannot merge (conflicts, approvals needed).

The nature of the error -- not its surface symptom -- determines what kind
of investigation is needed.

## Kargo Concepts

- Each Kargo **Stage** represents a deployment target in a CD pipeline.
- Each promotion attempt creates a **new Promotion CR** (retries are new objects, not state transitions on old ones).
- **Freight** is the versioned artifact being promoted (image, commit, chart).
- The observer watches `Stage.status.lastPromotion` -- the most recent attempt.
- Recovery = a newer Promotion on the same Stage reaches phase=Succeeded.
