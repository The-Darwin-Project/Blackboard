---
description: "TimeKeeper-sourced event: user-scheduled request, triage normally"
tags: [timekeeper, scheduled, user-request]
---
# TimeKeeper Source Environment

## Nature

TimeKeeper events are **user requests on a timer**. They arrive exactly like chat or Slack messages but are triggered by a schedule instead of a human typing in real-time. Triage them the same way you would any user request.

## Data Available

- `event.event.reason`: The user's desired outcome, prefixed with `[Scheduled: <name>]`. May include repository URL, MR URL, approval preferences, and notification emails.
- `evidence.triggered_by`: Email of the user who created the schedule.
- `evidence.source_type`: "timekeeper"

## Triage

Apply normal triage: classify the domain (Cynefin), assess risk, decide whether to self-answer, route to an agent, or request clarification. Do NOT treat TimeKeeper events differently from user requests -- the Brain decides the approach.

## Approval Mode

If the reason contains "ask me via Slack before executing," use `request_user_approval` before dispatching any agent to execute changes. The user is reachable at the email in `triggered_by`.

If no approval instruction is present, execute autonomously.

## Notification

If the reason contains "Notify on completion," send notifications via `notify_user_slack` to the listed emails on both success and failure. If no notification instruction is present, close normally.

## Close Protocol

Close after the task is completed and verified, same as any user request. If the user requested approval mode, they are in the conversation -- follow normal `wait_for_user` patterns.
