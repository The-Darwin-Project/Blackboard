---
description: "Cynefin domain-specific action prescriptions for agent routing"
requires:
  - always/05-cynefin.md
tags: [cynefin, routing, actions]
---
# Cynefin Action Prescriptions

Domain-specific routing actions (definitions in always/05-cynefin.md):

## CLEAR Action

Skip Architect. Send sysAdmin directly with the established fix.

## COMPLICATED Action

Send agents to investigate, then Architect to analyze options, then decide.

## COMPLEX Action

Run a small safe-to-fail probe. For build failures, this can be dispatching
the Developer to push a speculative fix to the MR/PR branch -- if the pipeline passes,
the probe succeeded. Notify the maintainer with the working fix for authorization.
If the probe fails, the MR/PR branch is unchanged and you have new evidence to guide
escalation. Limit: one speculative probe per event. If it fails, escalate -- do not
chain probes (each Konflux pipeline run consumes cluster resources across architectures).

## CHAOTIC Action

Immediate stabilization (rollback, scale up, disable feature flag). Investigate AFTER stable.
