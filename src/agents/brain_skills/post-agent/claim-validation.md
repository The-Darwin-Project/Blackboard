---
description: "Validate plausibility of agent claims before escalating — sanity check, cross-agent verification, confirmed-only escalation"
requires:
  - post-agent/evidence-sufficiency.md
tags: [escalation, validation, cross-check, plausibility]
---
# Claim Validation

This check runs **after** evidence sufficiency passes. An agent may return
well-structured, observable evidence that still describes something implausible.
This skill catches that gap.

## When to Apply

Apply this check whenever an agent's findings would lead to an **escalation**
(incident creation, maintainer notification, or user alert) based on an
environmental or infrastructure claim — for example:

- "Cluster X is inaccessible"
- "Credentials have been revoked"
- "Namespace was deleted"
- "Registry is down"
- "Network policy blocks access"

If the agent's findings are purely about application-level behavior (test
failures, build errors, code bugs), this check does not apply — proceed with
the normal `agent-recommendations.md` flow.

## Step 1 — Sanity Check (Plausibility)

Ask: **does this claim make sense given what we know?**

- Do we routinely operate on this resource? If Darwin has been interacting with
  the same cluster, registry, or namespace in recent events, a sudden
  "inaccessible" claim is implausible without a corresponding change.
- Is there a simpler explanation? A wrong name, alias mismatch, or typo in the
  agent's context is more likely than an infrastructure-level failure that no
  other system has noticed.
- Did anything change? Check the ops journal (`svc_get_journal`) for recent
  deployments, config changes, or incidents on the claimed resource.

If the claim passes the sanity check (it is plausible), proceed to Step 2.
If it fails (the claim is implausible), proceed to Step 2 with higher scrutiny.

## Step 2 — Cross-Validate

Verify the claim using a **different** agent than the one that made it. The
original agent may have a blind spot (wrong context, stale credentials, alias
mismatch) that re-dispatching it will not resolve.

- If the Developer claimed it, send the SysAdmin (or vice versa).
- If neither agent type is appropriate, use a different tool or mode to verify
  independently (e.g., direct `kubectl` check, API call, or web lookup).

For the Deep Memory consultation part of cross-validation, follow the existing
process in [`agent-recommendations.md`](agent-recommendations.md) (lines 17-26):
consult deep memory with the agent's key findings to detect if this claim
contradicts operational history.

Do NOT restate the Deep Memory rules here — they are authoritative in
`agent-recommendations.md`.

## Step 3 — Escalate Only If Confirmed

- **If the second check confirms the claim:** proceed with escalation. The
  claim is corroborated by independent verification.
- **If the second check contradicts the claim:** do NOT escalate. Log the
  discrepancy, discard the original claim, and proceed with the corrected
  understanding.
- **If the second check is inconclusive:** re-dispatch one more time with a
  narrower question before deciding. Apply the same depth budget as
  `evidence-sufficiency.md` (initial + 2 re-probes max).

### CHAOTIC Domain Exception

When the event is classified as **CHAOTIC**, skip this validation and escalate
immediately. In chaotic situations, the cost of delayed escalation outweighs
the risk of a false alarm. This aligns with the existing CHAOTIC exception in
`always/04-deep-memory.md`.
