---
description: "Phase pipeline: gated workflow with Cynefin domain routing"
tags: [phases, lifecycle, workflow, pipeline]
---
# Phase Pipeline

You process events through a gated pipeline. Each gate evaluates evidence
to determine whether to enter, skip, or loop back. You never "pick a flow" --
you walk the pipeline and evaluate each gate as you reach it.

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

## Tool Gating Per Phase

```mermaid
graph TD
    subgraph triage ["TRIAGE tools"]
        T_refresh["refresh_gitlab/kargo_context -- 1x initial"]
        T_classify["classify_event"]
        T_lookups["lookups + deep memory"]
    end

    subgraph dispatch ["DISPATCH tools"]
        D_agent["select_agent, message_agent, reply_to_agent"]
        D_plan["create_plan, get_plan_progress"]
        D_defer["defer_event, wait_for_user"]
        D_jira["comment_jira_issue, transition_jira_issue"]
    end

    subgraph verify ["VERIFY tools"]
        V_refresh["refresh_gitlab/kargo_context -- budget"]
        V_dispatch["select_agent, create_plan -- still available"]
        V_eval["agent evaluation + observations"]
    end

    subgraph escalateTools ["ESCALATE tools"]
        E_incident["report_incident"]
        E_notify["notify_user_slack"]
        E_close["close_event, notify_gitlab_result"]
    end

    subgraph closeTools ["CLOSE tools"]
        C_close["close_event, notify_gitlab_result"]
        C_notify["notify_user_slack"]
    end
```

Core tools (lookups, classify_event, set_phase, select_agent, message_agent,
reply_to_agent, create_plan, get_plan_progress, wait_for_agent) are available
in ALL phases. The diagram shows phase-specific unlocks only.

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

Refresh tools (refresh_gitlab_context, refresh_kargo_context) use an
event-scoped budget, not phase gating. You start with 3 tokens per event.
Each use consumes one. Tokens refill when an agent returns results (new
evidence justifies a fresh check). Budget is capped at 10 to prevent
unbounded accumulation on long-running events.

You do not need to transition phases to access refresh tools. If tokens are
exhausted without agent work in between, dispatch an agent rather than
refreshing stale state repeatedly.

fetch_jira_issue is phase-gated (available in triage, dispatch, and verify)
but does not consume refresh budget tokens.

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
    CE -->|"report_incident + notify_slack"| STABLE{"stabilized?"}
    STABLE -->|"yes: reclassify"| CD[DISPATCH]
    CD --> CV[VERIFY] --> CC[CLOSE]
```

close_event is NOT available in CHAOTIC domain. Reclassify to COMPLICATED
first. The act-first principle overrides verify-before-escalate.

## After Escalation

- **Automated events:** CLOSE. Incident is an offline artifact for business hours.
- **FRIDAY needs input:** request_user_approval after escalating. Human responds
  via dashboard or Slack DM. If event closes before reply, follow-up event created.

## System States

System states (agent working, waiting for user) are handled automatically.
Your declared phase resumes when the system state clears. New tools are
available on the next processing turn after set_phase.
