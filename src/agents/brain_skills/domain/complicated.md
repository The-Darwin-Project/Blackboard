---
description: "COMPLICATED domain control loop"
tags: [domain, complicated, control-loop]
---
# COMPLICATED: Analyze → Sample → Verify

Known unknowns. Cause-effect exists but requires expert analysis. Multiple
valid approaches. Sampling interval (Ts) is the core controller output.

<source_context ref="source/{event.source}">
Ts calibration per source:
- headhunter: pipeline duration from deep memory
- aligner: metric recovery baseline from operational history
- chat/slack: user IS the feedback loop — no defer between exchanges
- timekeeper: scheduled task interval defines natural Ts
</source_context>

<severity_modulation>

| Severity | Ts multiplier    | Escalation threshold     |
|----------|-----------------|--------------------------|
| info     | 1.0x (patient)  | 3 defers no progress     |
| warning  | 0.5x (attentive)| 2 defers no progress     |
| critical | 0.25x (urgent)  | 1 defer no progress      |

</severity_modulation>

## Control Loop

```mermaid
graph TD
    Enter["Enter COMPLICATED"] --> PhaseD{"Phase rhombus"}
    PhaseD -->|"DISPATCH"| Analyze["Dispatch agent to investigate/execute"]

    Analyze --> AgentReturn["Agent returns results"]

    AgentReturn --> DomainR{"Domain rhombus: still COMPLICATED?"}
    DomainR -->|"yes"| PhaseV{"Phase rhombus"}
    DomainR -->|"simpler than expected"| ReclassClear["Reclassify → CLEAR"]
    DomainR -->|"no cause-effect found"| ReclassComplex["Reclassify → COMPLEX"]
    DomainR -->|"crisis emerged"| ReclassChaotic["Reclassify → CHAOTIC"]

    PhaseV -->|"VERIFY"| Verify["Verify results (set_phase verify)"]

    Verify --> Progress{"Evidence: progress?"}
    Progress -->|"resolved"| PhaseC{"Phase rhombus → CLOSE"}
    Progress -->|"progressing: process running"| ChooseTs["Choose Ts (severity × source baseline)"]
    Progress -->|"stalled: no change"| Stall{"Stall count"}
    Progress -->|"new information"| DomainR2{"Domain rhombus"}

    ChooseTs --> Defer["defer_event(delay_seconds=Ts)"]
    Defer --> Wake["Wake: re-enter at VERIFY"]
    Wake --> MeasurePV["Measure PV (record_observation)"]
    MeasurePV --> DomainR2

    DomainR2 -->|"still COMPLICATED"| PhaseV
    DomainR2 -->|"reclassify"| Reclass["Enter new domain loop"]

    Stall -->|"below threshold"| PhaseD
    Stall -->|"at threshold"| PhaseE{"Phase rhombus → ESCALATE"}
    PhaseE --> Escalate["report_incident + notify"]

    PhaseC --> Close["close_event (set_phase close)"]
```

<agent_feedback ref="post-agent/agent-recommendations" trigger="agent_return">
Evaluate at decision node. Three paths:
- Act (dispatch next step) | Observe (defer with Ts) | Ask (user/escalate)
Use dual rhombus (domain + phase) for the decision.
</agent_feedback>

<bridge ref="defer-wake/verify-assumptions" trigger="defer_wake">
On wake: enter at "measure PV" node. System enforces verify before re-defer.
Re-defer after fresh measurement is the correct Ts output when the process
is still progressing.
</bridge>

## Ts Calibration Railway

0. **Check your observations**: before choosing Ts, review your observation history for this service. Look for duration measurement series. If data exists, use the observed range as your Ts baseline (minimum observed as floor, median as recommended Ts).
1. **No observations? Query the source**: if no duration observations exist and the event involves a pipeline or build, dispatch an agent to investigate historical pipeline timing from the build system. CI/CD systems store duration on every pipeline run. The agent reports the range; you record it as observations for future events.
2. **Deep memory supplement**: consult deep memory for additional timing context. Observations are more precise (direct measurements); deep memory provides patterns across longer time spans.
3. **Severity multiplier**: apply from the severity_modulation table above.
4. **Progress signal**: if each check shows advancement, maintain Ts. If stalled, halve Ts for closer observation.

Step 1 fires once per service -- after the first duration is observed, future events skip the agent dispatch and use measured data directly.

## Close Criteria

Expert analysis confirmed resolution. Evidence: verified state change or
terminal state reached. Resolution means the PV matches the SP — not "I tried
something."
