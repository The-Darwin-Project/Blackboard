---
description: "Phase lifecycle: why phases exist and when to transition"
tags: [phases, lifecycle, workflow]
---
# Phase Lifecycle

You control your own workflow by declaring phases via `set_phase`.
Each phase gates specific tools -- tools are only available in the
phase you declare.

## Available Phases

Core tools (lookups, classify_event, set_phase, select_agent,
message_agent, reply_to_agent, create_plan, get_plan_progress,
defer_event, wait_for_user, wait_for_agent) remain available in
ALL phases. Phase gating only restricts these specific tools:

- report_incident: requires escalate phase
- notify_user_slack: requires escalate or close phase
- close_event, notify_gitlab_result: requires escalate or close phase
- refresh_gitlab_context, refresh_kargo_context: requires triage or verify phase (one use per phase entry, then stripped)

Phase descriptions:

- **triage**: Assessing the event. Classify, check initial state,
  consult memory. Unlocks refresh_gitlab_context and refresh_kargo_context
  for initial state check.
- **investigate**: Gathering evidence. Dispatch agents to check logs,
  pipelines, cluster state. No additional tools unlocked beyond core set.
- **execute**: Implementing a fix. Dispatch agents to make changes.
  Same tool availability as investigate.
- **verify**: Checking results after agent work or defer wake.
  Unlocks refresh_gitlab_context and refresh_kargo_context. Other
  investigation tools (select_agent, message_agent, create_plan, etc.)
  remain available.
- **escalate**: Creating human awareness. Unlocks report_incident,
  notify_user_slack, close_event, and notify_gitlab_result.
- **close**: Wrapping up. Unlocks notify_user_slack, close_event,
  and notify_gitlab_result. Does NOT unlock report_incident.

System states (agent working, waiting for user) are handled automatically.
Your declared phase resumes when the system state clears.

## Why Phases Matter

Agent investigation takes time -- minutes to hours. The world changes while
agents work. A pipeline may recover. An MR may merge. A human may fix the
issue. An outage may end. If you skip verify and go straight from
investigation to escalation, you escalate on stale data.

The world has two kinds of state: the **symptom** (a resource showing Failed)
and the **cause** (an outage, a permission gap, a missing dependency).
Refreshing resource state verifies the symptom. But if the investigation
attributed the failure to an external cause, that cause has its own lifecycle.

After calling set_phase, your new tools are available on the next processing
turn. In the same turn, complete any pending actions with your current tools.

## External Processes Have Their Own Timeline

Pipelines, deployments, and infrastructure recovery run on their own schedule.
Checking more often does not make them finish faster. A refresh tells you the
current state -- if that state is "still in progress," the situation requires
time to change, not another check.

Re-declaring the same phase you are already in is a no-op (the code ignores it).
Each phase transition gives you one fresh refresh opportunity.

## Automated Events (Headhunter, Timekeeper, Aligner)

Automated events have no human in the loop. You are the sole controller.
The verify phase is the only checkpoint between an automated observation
and a human being made aware.

When you escalate an automated event, you are staging an incident for
consolidation. The Nightwatcher batches these into deduplicated reports
on a cron schedule. But each staged escalation still carries weight —
it becomes a line item that humans review, and a noisy escalation that
self-resolved during investigation erodes trust in the system's signal.

Always verify before escalate for automated events.

## After Escalation

Escalation creates human awareness. What happens next depends on the situation:

- **Automated events (headhunter, timekeeper, aligner):** transition to close.
  The incident and notification are offline artifacts. The human reviews them
  during business hours. The event is done.
- **Brain is stuck and needs human input:** call wait_for_user after escalating.
  The human can respond via the dashboard or by replying to the Slack DM.
  Note: Slack DMs are reply-capable. If the event is closed by the time
  the maintainer replies, a follow-up event is created automatically.

## CHAOTIC Events

In CHAOTIC events, the normal flow (triage -> investigate -> verify -> escalate)
is compressed. Act first:

- triage -> escalate (immediate crisis: report_incident + notify_user_slack)
- close_event is NOT available in chaotic domain. To close, first reclassify
  to COMPLICATED (via classify_event) then transition to the close phase.
- After stabilization, reclassify to COMPLICATED and resume normal flow.

The act-first principle overrides the verify-before-escalate guidance.

## Transition Guidance

Phases are not a rigid state machine. You choose when to transition based
on your reasoning. Common flows:

- Self-resolved: triage -> investigate -> verify -> close
- Persistent failure: triage -> investigate -> verify -> escalate -> close
- Quick fix: triage -> execute -> verify -> close
- Complex: triage -> investigate -> verify -> investigate -> verify -> escalate -> close
- Crisis: triage -> escalate -> close

New events start in triage. Always declare a phase transition when your
focus shifts -- it makes your reasoning visible on the blackboard.
