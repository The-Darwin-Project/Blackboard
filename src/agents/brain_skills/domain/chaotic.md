---
description: "CHAOTIC domain control loop"
tags: [domain, chaotic, control-loop]
tag_type: navigation
---
# CHAOTIC: Act → Sense → Stabilize

Crisis. No time for analysis. Cause and effect are indecipherable.
Stabilize the system first. Everything else follows.

<source_context ref="source/{event.source}">
Stabilization actions per source:
- aligner: rollback last deployment, scale up replicas, disable feature flag
- headhunter: close MR, revert merge, notify maintainers immediately
- chat/slack: immediate human escalation — user is live witness
- timekeeper: halt scheduled operations, escalate
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

## Tool Restrictions

- `close_event` is NOT available in CHAOTIC. You must reclassify first.
- `defer_event` is NOT available in CHAOTIC. Continuous-time control only — no sampling intervals during crisis.
- Act-first principle overrides verify-before-escalate.

## Close Criteria

NEVER close from CHAOTIC. Reclassify to COMPLICATED when the system is stable,
then perform root cause analysis and close from there. Closing during a crisis
is a trust violation.
