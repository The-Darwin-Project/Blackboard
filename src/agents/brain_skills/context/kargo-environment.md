---
description: "Kargo promotion environment, capabilities, and close protocol"
tags: [kargo, promotions, autonomous]
---
# Kargo Promotion Environment

NOTE: This skill is injected via evidence-driven tag matching (find_by_tag), not dependency resolution. It does not participate in resolve_dependencies and should not use requires: frontmatter.

## Close Protocol (Setpoint Enforcement)

Kargo events CANNOT be closed until one of:
1. **Observer confirms success**: refresh_kargo_context shows a newer promotion with phase=Succeeded on the same stage.
2. **Root cause identified and reported**: the agent finds the issue is outside Darwin's control -- create an incident or notify the maintainer, document the root cause in the close summary.

- Do NOT close after the agent says "I retried the promotion" -- verify via refresh_kargo_context.
- Do NOT close on timeout -- defer instead, then use refresh_kargo_context to check.
- If the agent reports the issue is non-recoverable, reclassify to complicated, report, and close.

## Verification Pattern

After dispatching sysadmin to investigate or retry a failed promotion:
1. Defer for 2-5 minutes (promotions take time).
2. On wake, call refresh_kargo_context to read the current stage state.
3. If phase=Succeeded (new promotion name): close the event.
4. If phase=Running: defer again and re-check.
5. If phase=Errored with the same promotion name: the retry did not help -- escalate.
6. If phase=Errored with a NEW promotion name: a retry was attempted but also failed -- investigate the new failure.

## Routing

- Route to **sysadmin** for investigation and reconciliation (kubectl/oc access, Kargo CLI).
- If the failure is a config/expression error in the stage spec, route to **developer** for a code fix.
- If the failure is an MR merge timeout, sysadmin can check the MR state and either merge or close it.

## Error Categories (from cluster probe)

- **MR merge timeout**: `step "wait-for-merge" timed out after 3h0m0s` -- MR pipeline may have failed or is stuck.
- **Config/expression error**: `failed to extract outputs: error compiling expression` -- stage spec has a bug.
- **Missing files**: `error reading YAML file ... no such file or directory` -- repo structure changed.
- **Auto-merge timeout**: `step "auto-merge" timed out after 2m0s` -- MR cannot be merged (conflicts, approvals).

## Kargo Concepts

- Each Kargo **Stage** represents a deployment target in a CD pipeline.
- Each promotion attempt creates a **new Promotion CR** (retries are new objects, not state transitions).
- **Freight** is the versioned artifact being promoted (image, commit, chart).
- The observer watches `Stage.status.lastPromotion` -- the most recent promotion attempt.
- Recovery = a newer Promotion on the same Stage reaches phase=Succeeded.
