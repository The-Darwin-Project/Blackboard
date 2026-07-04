---
description: "Phase×domain navigation map — what capabilities are available in each state"
tags: [navigation, phases, domains, gates]
tag_type: navigation
tools: [classify_event, set_phase, select_agent, close_event, defer_event, report_incident]
---
# Phase×Domain Navigation Map

> Exact tool availability is enforced at runtime by the gate system. This map shows the capability topology — use it to navigate toward the right phase for your intent.

```mermaid
graph TD
    %% Entry points
    START((Event Arrives)) --> PRE_CLASS

    %% Pre-classification override
    subgraph override [Override States]
        PRE_CLASS{PRE_CLASSIFICATION<br/>classification, lookups, memory<br/>— all other capabilities locked}
        INTERMEDIATE{INTERMEDIATE<br/>agent communication only<br/>— all other capabilities suspended}
    end

    PRE_CLASS -->|classify| TRIAGE

    %% Phase progression
    subgraph phases [Phase Pipeline]
        TRIAGE[TRIAGE<br/>context gathering, classification,<br/>observations, incident search<br/>— NO: dispatch, defer, close, notify]
        DISPATCH[DISPATCH<br/>agent routing, planning,<br/>context refresh, integration actions<br/>— NO: close, escalate]
        VERIFY[VERIFY<br/>observations, context refresh,<br/>integration actions<br/>— NO: escalate]
        ESCALATE[ESCALATE<br/>incident reporting, user notification,<br/>closure<br/>— NO: dispatch, defer]
        CLOSE[CLOSE<br/>closure, user notification,<br/>result delivery<br/>— NO: observations, dispatch]
    end

    TRIAGE -->|advance to dispatch| DISPATCH
    DISPATCH -->|advance to verify| VERIFY
    VERIFY -->|advance to escalate| ESCALATE
    VERIFY -->|advance to close| CLOSE
    ESCALATE -->|advance to close| CLOSE
    DISPATCH -->|reclassify| TRIAGE

    %% Domain modifiers
    subgraph domains [Domain Modifiers — intersect with phase capabilities]
        CLEAR[/CLEAR\<br/>No planning needed<br/>Act directly, verify, close/]
        COMPLICATED[/COMPLICATED\<br/>Full capabilities<br/>No domain restrictions/]
        COMPLEX[/COMPLEX\<br/>Cannot close prematurely<br/>until 4+ agent rounds/]
        CHAOTIC[/CHAOTIC\<br/>Triage actions only:<br/>routing, notification, escalation/]
        CASUAL[/CASUAL\<br/>Conversational subset:<br/>classification, lookups, notes,<br/>wait for user — NO: dispatch, defer, escalate, notify/]
    end

    TRIAGE -.->|domain classified| CLEAR
    TRIAGE -.->|domain classified| COMPLICATED
    TRIAGE -.->|domain classified| COMPLEX
    TRIAGE -.->|domain classified| CHAOTIC
    TRIAGE -.->|domain classified| CASUAL

    %% Return edges
    CASUAL -.->|reclassify to complicated| TRIAGE
    COMPLEX -.->|4+ agent rounds| CLOSE
```

## Transition Skill Pointers

| Transition | Pointer |
|---|---|
| Enter triage | <skill id="always/06-decision-guidelines.md"/> |
| Enter dispatch | <skill id="dispatch/decision-routing.md"/> |
| Enter verify | <skill id="always/03-control-theory.md"/> |
| Enter escalate | <skill id="escalate/incident-tracking.md"/> |
| Domain loaded | <skill id="domain/{domain}.md"/> |
| Source loaded | <skill id="source/{source}.md"/> |

## Conditional Gates (state-dependent)

| Gate | Condition | Effect |
|---|---|---|
| BUDGET_EXHAUSTED | refresh count exceeds budget | context refresh capabilities removed |
| NO_KARGO_CONTEXT | no kargo evidence present | kargo refresh removed |
| DEFER_WAKE_ITER0 | first cycle after wake | deferral blocked |
| HARD_STRIP_DEFER | triage OR jarvis source | deferral blocked |
| HARD_STRIP_WAIT_USER | triage OR non-user source | user-wait blocked |

## Behavioral Annotations

- Agent progress: wait for completion — don't act on intermediates
- Notification authority: YOU are the sole notification channel to users
- Action sequencing: one action per turn, verify result before next
- Route vs message: dispatch = full work package, message = coordination
- Authorization boundary: autonomous actions vs human-gated fixes
