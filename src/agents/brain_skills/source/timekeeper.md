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

Scheduled tasks bridge the gap between "fire and forget" and "I want to be
in the loop." The user chose their level of involvement at scheduling time --
that choice encodes their risk tolerance. A notify-and-wait task means the
user considers the outcome uncertain enough to review; an autonomous task
means they trust the system to handle it end-to-end. Respecting this choice
is respecting their judgment about their own workload.

- **Notify-and-wait**: After the agent completes, present the results to the user and wait for their response before closing. The user expects to review the outcome.
- **Autonomous** (or unspecified): Close after the task is completed and verified.

If the user specified people to notify on completion or failure, notify them and let the user review the outcome before closing.

## Close Protocol

- If the user requested confirmation: notify, then wait for their response before closing.
- If the user specified notification recipients: notify them, then let the user review before closing.
- If autonomous with no notification recipients: close after task completion and verification.
- On failure or escalation: the failure reason must be known before closing. Notify -> `report_incident` -> `close_event`.
