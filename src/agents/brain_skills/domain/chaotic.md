---
description: "CHAOTIC domain control loop"
tags: [domain, chaotic, control-loop]
---
# CHAOTIC: Act → Sense → Stabilize

Crisis. No time for analysis. Cause and effect are indecipherable.
Stabilize the system first. Everything else follows.

<source_context ref="source/{event.source}">
Stabilization principles:
- Act on the most reversible high-impact lever first (scale, disable, rollback)
- Contain blast radius before diagnosing root cause
- If a human is present, they are a live witness — escalate to them immediately
- Every stabilization action must be logged as an observation for the post-mortem
</source_context>

## Control Loop

```mermaid
graph TD
    Enter["Enter CHAOTIC"] --> PhaseE{"Phase rhombus"}
    PhaseE -->|"ESCALATE"| Stabilize["Stabilize NOW (set_phase escalate)"]

    Stabilize --> Act["report_incident + notify_user_slack"]
    Act --> Sense["Sense: is system stable?"]

    Sense --> StableCheck{"Evidence: stabilized?"}
    StableCheck -->|"yes"| DomainR{"Domain rhombus"}
    StableCheck -->|"no: still in crisis"| ActAgain["Act again — different stabilization"]
    ActAgain --> Sense

    DomainR -->|"stable → root cause analysis needed"| ReclassComp["Reclassify → COMPLICATED"]
    ReclassComp --> RootCause["Enter COMPLICATED for root cause"]
```

<agent_feedback ref="post-agent/agent-recommendations" trigger="agent_return">
Did stabilization work? Binary: stable / not stable.
If stable → reclassify to COMPLICATED for root cause.
If not stable → act again with a different approach.
</agent_feedback>

## Restrictions

- Closing is not available in CHAOTIC. Reclassify to COMPLICATED first.
- Scheduling observation intervals is not available in CHAOTIC. Continuous-time
  control only — no sampling intervals during crisis.
- Act-first principle overrides verify-before-escalate.

## Close Criteria

NEVER close from CHAOTIC. Reclassify to COMPLICATED when the system is stable,
then perform root cause analysis and close from there. Closing during a crisis
is a trust violation.
