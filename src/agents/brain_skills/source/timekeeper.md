---
description: "TimeKeeper-sourced event: user-scheduled request with structured metadata"
tags: [timekeeper, scheduled, user-request]
---
# TimeKeeper Source Environment

## Nature

TimeKeeper events are **user requests on a timer**. Triage them the same way as chat or Slack messages. The Brain decides domain, severity, agent routing -- everything.

## Data Available

The `event.event.reason` has YAML frontmatter (structured metadata) followed by the user's desired outcome. Frontmatter has metadata fields, body has the user's request.

Frontmatter fields (all optional except `name` and `created_by`):
- `name`: Schedule name (informational)
- `created_by`: Email of the user who created the schedule
- `repo_url`: Repository URL (environment context)
- `mr_url`: Merge request URL (environment context)
- `approval_mode`: `autonomous` or `notify_and_wait`
- `on_failure`: `close_event`, `retry_once`, or `escalate_human` (default is notify)
- `notify_emails`: List of emails to notify via Slack on completion or failure

## Triage

Apply normal triage. The frontmatter provides context, not instructions. The body is what the user wants done.

## Approval Mode (CRITICAL)

Parse the `approval_mode` field from the YAML frontmatter:

- **`notify_and_wait`**: After the agent completes execution, notify the user via `notify_user_slack` AND call `wait_for_user`. Do NOT close the event. The user expects to review the results and respond before closure. This is a human-in-the-loop checkpoint.
- **`autonomous`** (or absent): Execute fully. Notify on completion if `notify_emails` is present. Close normally after verification.

## Close Protocol

- If `approval_mode: notify_and_wait`: Do NOT close until the user responds. Use `wait_for_user` after notifying.
- If `notify_emails` is present: call `notify_user_slack` for each email before closing.
- If `autonomous`: close after the task is completed and verified.
