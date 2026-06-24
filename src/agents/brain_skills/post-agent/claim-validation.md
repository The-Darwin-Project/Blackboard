---
description: "Plausibility gate for infrastructure/environmental claims before escalation"
tags: [escalation, validation, plausibility]
---
# Claim Plausibility Check

Before escalating based on an agent's **infrastructure or environmental claim**
(cluster inaccessible, credentials revoked, namespace deleted, registry down,
network policy blocks access), verify plausibility.

This does NOT apply to application-level findings (test failures, build errors,
code bugs) -- those follow the normal post-agent flow.

## Sanity Check

Agents operate with session-scoped context — they may have a stale credential, a misresolved alias, or a wrong namespace in their working context. An infrastructure claim that contradicts recent successful operations is more likely a session issue than a real outage. Escalating an agent's session problem as a production incident creates noise for the ops team.

Ask: does this claim make sense given what I know?

- Have I interacted with this resource recently? If recent events show successful
  operations on the same cluster, registry, or namespace, a sudden "inaccessible"
  claim is suspect without a corresponding change.
- Is there a simpler explanation? A wrong name, alias mismatch, or stale context
  in the agent's session is more likely than an infrastructure failure that nothing
  else has detected.
- Did anything change? Check operational history for recent deployments, config
  changes, or incidents on the claimed resource.

## Cross-Agent Verification

An agent's blind spot is reproducible within its own session — re-dispatching the same agent will hit the same wrong context, stale credential, or alias mismatch. A different agent starts with a fresh session and independently observes the same resource, eliminating session-specific false positives.

If the claim is implausible OR high-impact, verify using a DIFFERENT agent
than the one that made the claim. The original agent may have a blind spot
(wrong context, stale credentials, alias mismatch) that re-dispatching it
will not resolve.

- Developer claimed it → send SysAdmin to verify (or vice versa)
- Neither appropriate → use a direct tool check (kubectl, API call)

If the second check contradicts the original claim, discard the claim and
proceed with the corrected understanding. Do not escalate on unconfirmed
infrastructure claims.

## Ops Journal Ground Truth

Parallel events can track the same artifact (MR, pipeline, promotion). If another event has already driven that artifact to completion, deferring on it creates a zombie event — one that keeps waking up to check something that was resolved elsewhere. The Ops Journal is the system's shared memory of completed actions across events.

Before acting on agent-reported pipeline or resource states, check whether
the Ops Journal already records a terminal outcome for the same artifact
(MR, pipeline ID, promotion). If another event has already driven that
artifact to completion, the current event is redundant — close it rather
than deferring on a resource that is already resolved. This prevents zombie
deferrals when parallel events track the same object.
