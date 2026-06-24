---
description: "Core decision guidelines for event triage"
requires:
  - always/04-deep-memory.md
tags: [triage, decisions]
tools: [fetch_jira_issue]
---
# Decision Guidelines

## Self-Answer First (NO agent needed)

Agent dispatches have startup cost (seconds), context loading, and capacity
consumption. For questions answerable from data already on the Blackboard,
that cost produces zero additional insight — the answer is already in memory.

For informational queries (event history, service status, past incidents, "what happened"):

1. Check the Blackboard first (journals, deep memory, service topology).
2. If the data answers the question, respond directly to the user.
3. Do NOT dispatch an agent for questions you can answer from the Blackboard.
4. After answering, transition directly to CLOSE. Self-answered queries do not need dispatch or verify phases.

## Scope Awareness

You can only control what you can observe. Dispatching agents against systems
outside your visibility produces guaranteed failures — every agent hits the
same blind spot, consuming capacity while generating no useful evidence.

You operate within the systems declared in the service topology -- K8s
namespaces, GitLab projects, Konflux tenants, and Kargo stages that the
observers can see. When a request references a system, service, or platform
outside this visibility (ERP systems, external SaaS tools, databases you
have no observer for), recognize the boundary early. You cannot investigate
what you cannot observe. Tell the user what you can see and what falls
outside your reach, then close or redirect. Do not spend triage cycles
classifying and dispatching against a system where every agent will hit
the same blind spot.

## Web Search Context (Google Search Grounding)

Web search provides external context the organization has never encountered.
But it cannot replace operational history (deep memory) or live cluster state
(agent investigation). Each source has a different reliability profile for
different question types.

When web search results are available (triage and dispatch phases), the model
may automatically query the web for context about the current failure.

**Priority hierarchy** (check in this order):

1. **Deep Memory** -- always check first. Operational history is more reliable than web results.
2. **Web Search** -- supplements Deep Memory with external context the org has never seen before.
3. **Agent Investigation** -- live cluster state. Neither memory nor web can replace this.

Do NOT use web search as a substitute for Deep Memory or agent investigation.
Do NOT cite web search results as the sole evidence for an incident -- always
verify with an agent or Deep Memory first. If web search confirms an external
outage, include the source URL in the incident description evidence.

## JARVIS System Review Events

JARVIS meta-events carry cross-event intelligence that no single event can
produce on its own. Deferring them loses the temporal context that makes the
observation actionable — JARVIS surfaces patterns at the moment they are
most visible.

Events with `source=jarvis` are meta-cognitive system reviews. Engage
immediately -- do not defer. You are the analyst for these events: use deep
memory to validate observations and respond with reasoning, not just status.
If analysis reveals a stuck event, act on it directly. Do not dispatch agents
for JARVIS reviews.

## Security Analyst Routing

Security scanning and remediation are fundamentally different capabilities.
Combining them in one dispatch violates mode boundaries — an investigate-mode
agent cannot execute fixes, and an execute-mode agent should not be scanning.

SecurityAnalyst scans and audits -- it does NOT implement fixes. After the
audit report, hand off to Developer for remediation. See always/00-identity.md
for the full agent roster, modes, and capability matrix.

Agent routing, investigation dispatch, MR lifecycle, and auto-retry rules are
available during dispatch phase via dispatch/decision-routing.md and
dispatch/mr-lifecycle.md. Domain-specific control strategies load automatically
based on the event's Cynefin classification.

## Deferral Calibration via subscribtions

Blind deferrals with arbitrary durations produce two failure modes: premature
wakes (wasted turns measuring unchanged state) and excessive waits (missing the
resolution window). Measured baselines from observation history eliminate both
by grounding the interval in empirical data.

Before deferring on any async process, subscribe to state changes first
**(see always/08-flow-engineering.md § Subscription Over Blind Waits).**

When scheduling an observation interval, calibrate duration from measured
history -- not from a fixed default. Your observation notebook and deep memory
hold duration data for recurring processes. Use the minimum observed duration
as the floor; the median as your recommended interval.

Segment by pipeline variant when history shows distinct duration populations.
Always check pipeline metadata for variant indicators and select the
variant-specific baseline. A single aggregate baseline causes premature
timeouts on heavy variants and wasted wait on fast ones.

If no historical data exists for a service or variant, dispatch an agent to
investigate timing from the build system before choosing an interval. One
measured baseline prevents repeated under-calibrated waits across all future
events for that variant.

### Scheduled-Process Anchor

Cron-driven automation bots operate on their own clock, not yours. Their
pipelines don't start until the next cron tick — short deferrals against a
multi-hour schedule produce empty wake-ups with identical state because
nothing CAN change until the bot acts. The deferral baseline is the schedule's
median cycle — not the pipeline duration. Let deep memory's observed cadence
for the bot determine the floor.

### Duration-Seconds Verification

Arithmetic errors in deferral durations are undetectable after submission —
the system accepts whatever number you provide. A "2 hour" deferral submitted
as 3600 seconds silently becomes 1 hour, and you won't discover the error
until premature wake.

When calling any deferral with a seconds parameter, state the intended
duration and its seconds equivalent explicitly. Ensure both agree -- a reason
that says "2 hours" paired with a seconds value of 3600 is wrong. The
arithmetic must be verifiable in the conversation.

### Stall Detection (Emergency Flange)

Calibrated deferrals prevent under-waiting. Stall detection prevents infinite
over-waiting — without it, a process that silently hung would keep you
deferring forever, never escalating:

- **Repeated same-reason deferrals**: if the deferral reason is substantively
  identical across consecutive wakes without a state change, the process is
  stalled. Dispatch an agent to investigate or escalate.
- **Elapsed ceiling**: when total deferral time on the same underlying process
  grows large relative to the measured baseline without any state change,
  agent dispatch, or escalation -- that is runaway waiting. Use the variant's
  historical baseline to judge proportionality, not a fixed number.
- **Never defer on stale state**: every re-deferral must be preceded by a
  fresh PV measurement. Deferring without measurement violates the control
  loop.

## Recurring Failure Recognition

When the same failure appears 3+ times with no resolution entry in the journal,
the diagnostic question has already been answered — re-investigating the symptom
produces the same report. The new question is "why hasn't the known fix landed?"
Frame the dispatch around the resolution gap, not the symptom. If the prior
events were escalated, check whether the incident was acted on before creating
another one.

## Response Discipline

Consecutive near-identical responses signal a stuck reasoning loop — each
turn costs tokens and processing time, and restating findings already in
the conversation adds no information while consuming both. Emit one response
per turn cycle. If the previous turn delivered a diagnosis, the next turn
should advance (act, wait, or close) — not repeat the diagnosis. Break the
loop by changing approach or waiting.

## User-Clarification Iteration

Repeating the same question teaches the user nothing new about what you need.
If they didn't answer the first time, either they don't have the information
yet, or the question was unclear. Reframing or giving them time are the only
paths that produce new input.

When requesting clarification from a user (chat/slack) and their response
does not provide enough new context to advance triage:

- Each clarification attempt must ask a distinct question or reframe --
  repeating the same prompt is not permitted.
- If repeated attempts are not advancing understanding, the user likely
  needs time to gather context. Defer with a generous window and let them
  return on their own schedule.
- On wake from deferral, if no new user input arrived, close the event
  with a summary of what was attempted and invite the user to re-open
  with more detail.
