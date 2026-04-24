---
description: "Phase lifecycle: why phases exist and when to transition"
tags: [phases, lifecycle, workflow]
---
# Phase Lifecycle

You control your own workflow by declaring phases via `set_phase`.
Each phase gates specific tools -- tools are only available in the
phase you declare.

## Available Phases

- **triage**: Assessing the event. Classify, check initial state,
  consult memory. Tools: classify_event, refresh_gitlab_context, lookups.
- **investigate**: Gathering evidence. Dispatch agents to check logs,
  pipelines, cluster state. Tools: select_agent (investigate/plan modes).
- **execute**: Implementing a fix. Dispatch agents to make changes.
  Tools: select_agent (execute/implement modes), coordination tools.
- **verify**: Checking results after agent work or defer wake.
  Refresh live state before deciding next step. Tools: refresh_gitlab_context,
  refresh_kargo_context, get_plan_progress.
- **escalate**: Creating human awareness. Create incident, notify maintainers.
  Tools: create_incident, notify_user_slack.
- **close**: Wrapping up. Write summary and close. Tools: close_event,
  notify_gitlab_result.

System states (agent working, waiting for user) are handled automatically.
Your declared phase resumes when the system state clears.

## Why Phases Matter

Agent investigation takes time -- minutes to hours. The world changes while
agents work. A pipeline may recover. An MR may merge. A human may fix the
issue. If you skip verify and go straight from investigation to escalation,
you escalate on stale data.

After calling set_phase, your new tools are available on the next processing
turn. In the same turn, complete any pending actions with your current tools.

## Automated Events (Headhunter, Timekeeper, Aligner)

Automated events have no human in the loop. You are the sole controller.
The verify phase is the only checkpoint between an automated observation
and a human being disturbed.

When you escalate an automated event, you are:
- Sending a Slack DM that may wake someone at 2AM
- Creating an incident row that triggers review workflows
- Posting a GitLab comment that maintainers will read

All of these are noise if the issue self-resolved during investigation.
Always verify before escalate for automated events.

## After Escalation

Escalation creates human awareness. What happens next depends on the situation:

- **Automated events (headhunter, timekeeper, aligner):** transition to close.
  The incident and notification are offline artifacts. The human reviews them
  during business hours. The event is done.
- **Brain is stuck and needs human input:** call wait_for_user after escalating.
  The human can respond via the dashboard. Note: Slack DMs for headhunter
  events are one-way notifications ("Replies are not monitored").

## CHAOTIC Events

In CHAOTIC events, the normal flow (triage -> investigate -> verify -> escalate)
is compressed. Act first:

- triage -> escalate -> close (immediate crisis response)
- After stabilization, reclassify to COMPLICATED and resume normal flow

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
