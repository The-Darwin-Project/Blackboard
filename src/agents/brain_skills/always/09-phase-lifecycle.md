---
description: "Phase pipeline: gated workflow with Cynefin domain routing"
tags: [phases, lifecycle, workflow, pipeline]
tag_type: protocol
---
# Phase Pipeline

This phase pipeline is executed by the domain control loops in 03-control-theory.md.
Phases unlock capabilities; domain strategy decides which path you walk through them.
Transition phases to unlock the capabilities for your next action — the domain loop
decides WHAT to do; the phase decides WHAT CAPABILITIES you can use to do it.

## Pipeline Flow

```mermaid
graph TD
    TRIAGE["TRIAGE: classify + initial state"]

    TRIAGE --> ASSESS{"What does the domain tell me?"}

    ASSESS -->|"CLEAR: known fix, act directly"| CLEAR_SKIP["route sysAdmin"]
    CLEAR_SKIP --> VERIFY
    ASSESS -->|"COMPLICATED / COMPLEX"| DISPATCH
    ASSESS -->|"CHAOTIC: crisis, act first"| ESCALATE
    ASSESS -->|"not yet classified"| CLASSIFY["classify_event first"]
    CLASSIFY --> ASSESS

    DISPATCH["DISPATCH: agents investigate or execute"]

    DISPATCH --> WAIT_ASYNC{{"async boundary: agent work / defer"}}

    WAIT_ASYNC --> VERIFY["VERIFY: refresh + check results"]

    VERIFY --> EVAL{"What does the evidence show?"}

    EVAL -->|"resolved: evidence confirms fix"| CLOSE
    EVAL -->|"progressing: external process running"| DEFER_WAIT["defer, re-enter VERIFY"]
    EVAL -->|"persists: need different approach"| RETHINK{"What should I try next?"}
    EVAL -->|"exhausted: nothing more I can do"| ESCALATE

    RETHINK -->|"new agent / different task"| DISPATCH
    RETHINK -->|"reclassify: complexity changed"| RECLASS["classify_event"]
    RECLASS --> ASSESS

    ESCALATE["ESCALATE: human awareness"]
    ESCALATE --> POST_ESC{"What happens after escalation?"}

    POST_ESC -->|"automated: incident staged"| CLOSE
    POST_ESC -->|"need human input"| WAIT_HUMAN["request_user_approval"]
    POST_ESC -->|"CHAOTIC stabilized"| RECLASS

    CLOSE["CLOSE: wrap up"]
```

## Iteration Rules

```mermaid
graph LR
    V[VERIFY] --> EVAL2{"What does evidence show?"}
    EVAL2 -->|"need more work"| RETHINK2{"What next?"}
    RETHINK2 -->|"same agent, new questions"| D[DISPATCH]
    RETHINK2 -->|"different agent"| D
    RETHINK2 -->|"reclassify"| RECLASS2["classify_event"] --> ASSESS2{"reassess domain"}
    ASSESS2 --> D

    D -->|"guard: max 3 without VERIFY"| D
```

CLOSE is terminal. Reopen requires a new event.

## Capabilities Per Phase

```mermaid
graph TD
    subgraph triage ["TRIAGE capabilities"]
        T1["Classify the event domain"]
        T2["Gather initial state (1x refresh)"]
        T3["Consult deep memory + lookups"]
    end

    subgraph dispatch ["DISPATCH capabilities"]
        D1["Route agents to investigate or execute"]
        D2["Create and track plans"]
        D3["Schedule observation intervals + wait for user"]
        D4["Interact with issue trackers"]
    end

    subgraph verify ["VERIFY capabilities"]
        D1b["Route agents (still available)"]
        V1["Refresh external state (budget-gated)"]
        V2["Schedule calibrated observation intervals"]
        V3["Evaluate agent results + record observations"]
    end

    subgraph escalateTools ["ESCALATE capabilities"]
        E1["File incidents"]
        E2["Notify maintainers"]
        E3["Schedule observation intervals"]
        E4["Close event + notify external systems"]
    end

    subgraph closeTools ["CLOSE capabilities"]
        C1["Close event + notify external systems"]
        C2["Notify maintainers"]
        C3["Park for observation (meta-events)"]
    end
```

Core capabilities (lookups, classification, phase transitions, agent routing,
plan management, agent communication) are available in ALL phases. The diagram
shows phase-specific unlocks only.

**Defer discipline:** Scheduling observation intervals is available in DISPATCH,
VERIFY, and ESCALATE. When deferring to wait on an async result (pipeline, agent
task, build, sync), transition to **VERIFY first**. Deferring from DISPATCH is
valid only for capacity gating (WIP cap reached, all agents busy). If you dispatched
async work, the correct sequence is: DISPATCH → transition to VERIFY → evaluate
evidence → schedule observation. Skipping VERIFY means you defer on stale state.

## Phase Handoffs

```mermaid
graph LR
    T[TRIAGE] -->|"produces: domain, state, memory"| G1{"gate eval"}
    G1 -->|"expects: which phase?"| D[DISPATCH]
    D -->|"produces: agent report, observations"| G2{{"async boundary"}}
    G2 -->|"expects: defer or immediate"| V[VERIFY]
    V -->|"produces: fresh state, assessment"| G3{"resolved?"}
    G3 -->|"CLOSE / DISPATCH / ESCALATE"| NEXT["next phase"]
```

## Refresh Budget

Refreshing external state uses an event-scoped budget, not phase gating.
You start with 3 tokens per event. Each use consumes one. Tokens refill
when an agent returns results (new evidence justifies a fresh check).
Budget is capped at 10 to prevent unbounded accumulation on long-running
events.

You do not need to transition phases to refresh. If tokens are exhausted
without agent work in between, dispatch an agent rather than refreshing
stale state repeatedly.

Fetching issue tracker data is phase-gated (available in triage, dispatch,
and verify) but does not consume refresh budget tokens.

## Why Phases Matter

Agent work takes minutes to hours. The world changes -- pipelines recover,
MRs merge, humans fix issues, outages end. VERIFY after every async
boundary catches these changes before you escalate on stale data.

Two kinds of state: the **symptom** (resource showing Failed) and the
**cause** (outage, permission gap, missing dependency). Refreshing verifies
the symptom. The cause has its own lifecycle.

## External Processes

Pipelines, deployments, and recovery run on their own schedule. Checking
more often does not make them finish faster. If current state is "still in
progress," defer -- the situation requires time, not another check.

## Automated Events

No human in the loop. You are the sole controller. VERIFY is the only
checkpoint before a human is disturbed. Noisy escalations that self-resolved
erode trust. Always VERIFY before ESCALATE for automated events.

## CHAOTIC Events

```mermaid
graph LR
    CT[TRIAGE] -->|"act first"| CE[ESCALATE]
    CE -->|"file incident + notify maintainers"| STABLE{"stabilized?"}
    STABLE -->|"yes: reclassify"| CD[DISPATCH]
    CD --> CV[VERIFY] --> CC[CLOSE]
```

Closing and deferring are not available in CHAOTIC domain. Reclassify to
COMPLICATED first. The act-first principle overrides verify-before-escalate.

## After Escalation

- **Automated events:** CLOSE. Incident is an offline artifact for business hours.
- **FRIDAY needs input:** request user approval after escalating. Human responds
  via dashboard or chat. If event closes before reply, follow-up event created.

## System States

System states (agent working, waiting for user) are handled automatically.
Your declared phase resumes when the system state clears. New capabilities
are available on the next processing turn after a phase transition.
