---
description: "TimeKeeper-sourced event environment, scheduling lifecycle, and approval protocol"
tags: [timekeeper, scheduled, autonomous]
---
# TimeKeeper Source Environment

## Data Available

TimeKeeper events carry an embedded YAML work plan in the `reason` field (identical format to Headhunter Bot Instructions):

- `event.event.reason`: YAML frontmatter with `plan`, `domain`, `risk`, `steps` (each with `id`, `mode`, `summary`, `approval_mode`, `on_failure`, `notify_emails`, `created_by`)
- `evidence.source_type`: "timekeeper"
- `evidence.triggered_by`: Email of the user who created the schedule

The step `summary` contains environment context (Repository URL, MR URL if provided) and the user's desired outcome instructions.

## Routing Principle

Route based on the plan's `domain` field:

- **CLEAR**: Route directly to the assigned agent without Architect review.
- **COMPLICATED**: Route to the Architect first for analysis before execution.

## Approval Mode Protocol

Check the `approval_mode` field in the plan step:

- **autonomous**: Execute fully without user interaction. Notify `notify_emails` on completion or failure only.
- **notify_and_wait**: After building the execution plan, use `request_user_approval` before dispatching any agent. The schedule creator is reachable via Slack at the `created_by` email. Wait for user approval or rejection before proceeding.

## Failure Handling

Check the `on_failure` field:

- **notify**: Notify `notify_emails` via Slack and close the event.
- **close_event**: Close the event silently (no notification).
- **retry_once**: Retry the failed step once. If still failing, notify and close.
- **escalate_human**: Use `wait_for_user` to pause and notify via Slack. The creator decides next steps.

## Notification Protocol

Maintainer email addresses are in `notify_emails`. Notifications should include what was scheduled, what happened, and the outcome. If `notify_emails` is empty, note it in the close summary.

## Close Protocol

TimeKeeper events are scheduled tasks -- close after the plan step is completed and verified. No `wait_for_user` needed for `autonomous` mode. Notify maintainers via Slack before closing.

## Operational History

TimeKeeper events may be recurring. Consult deep memory for past outcomes from the same schedule name or repository before acting.
