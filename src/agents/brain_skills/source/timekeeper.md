---
description: "TimeKeeper-sourced event: user-scheduled request with structured metadata"
tags: [timekeeper, scheduled, user-request]
---
# TimeKeeper Source Environment

## Nature

TimeKeeper events are **user requests on a timer**. Triage them the same way as chat or Slack messages. The Brain decides domain, severity, agent routing -- everything.

## Data Available

The `event.event.reason` has YAML frontmatter (structured metadata) followed by the user's desired outcome:

```
---
name: "Weekly security audit"
created_by: "thason@redhat.com"
repo_url: "https://github.com/..."
notify_emails: ["thason@redhat.com"]
---
Audit dependencies for security vulnerabilities. Report high/critical findings.
```

Frontmatter fields (all optional except `name` and `created_by`):
- `name`: Schedule name (informational)
- `created_by`: Email of the user who created the schedule
- `repo_url`: Repository URL (environment context)
- `mr_url`: Merge request URL (environment context)
- `approval_mode`: If `notify_and_wait`, use `request_user_approval` before executing changes
- `on_failure`: `close_event`, `retry_once`, or `escalate_human` (default behavior is notify)
- `notify_emails`: List of emails to notify via Slack on completion or failure

The body text after `---` is the user's request. Triage it normally.

## Triage

Apply normal triage. The frontmatter provides context, not instructions. The body is what the user wants done. Classify domain, assess risk, route agents -- same as any user request.

## Close Protocol

Close after the task is completed and verified. If `notify_emails` is present, call `notify_user_slack` for each email before closing.
