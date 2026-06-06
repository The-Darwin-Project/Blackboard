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

Ask: does this claim make sense given operational context?

- Do we routinely operate on this resource? Check the ops journal for recent
  successful interactions with the same cluster, registry, or namespace.
- Is there a simpler explanation? A wrong name, alias mismatch, or stale
  context in the agent's session is more likely than an infrastructure failure
  that no other system has noticed.
- Did anything change? Check the ops journal for recent deployments, config
  changes, or incidents on the claimed resource.

## Cross-Agent Verification

If the claim is implausible OR high-impact, verify using a DIFFERENT agent
than the one that made the claim. The original agent may have a blind spot
(wrong context, stale credentials, alias mismatch) that re-dispatching it
will not resolve.

- Developer claimed it → send SysAdmin to verify (or vice versa)
- Neither appropriate → use a direct tool check (kubectl, API call)

If the second check contradicts the original claim, discard the claim and
proceed with the corrected understanding. Do not escalate on unconfirmed
infrastructure claims.
