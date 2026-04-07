---
description: "TimeKeeper-sourced event: user-scheduled request with structured metadata"
tags: [timekeeper, scheduled, user-request]
---
# TimeKeeper Source Environment

## Nature

TimeKeeper events are **user requests on a timer** -- NOT autonomous events.
Triage them the same way as chat or Slack messages.

## Data Available

The event reason contains structured metadata (who created it, what they want done) followed by the user's desired outcome. The metadata provides context; the body is the actual request.

## Triage

Apply normal triage. The metadata provides context, not instructions. The body is what the user wants done.

## Approval Behavior

The user who scheduled this task may have requested confirmation before closing:

- **Notify-and-wait**: After the agent completes, present the results to the user and wait for their response before closing. The user expects to review the outcome.
- **Autonomous** (or unspecified): Close after the task is completed and verified.

If the user specified people to notify on completion or failure, notify them and let the user review the outcome before closing.

## Close Protocol

- If the user requested confirmation: notify, then wait for their response before closing.
- If the user specified notification recipients: notify them, then let the user review before closing.
- If autonomous with no notification recipients: close after task completion and verification.
- On failure or escalation: the failure reason must be known before closing. Notify -> `create_incident` -> `close_event`.
