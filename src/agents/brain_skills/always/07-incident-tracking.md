---
phase: always
---

## Incident Tracking (Mandatory for Escalated Automated Events)

Before closing any automated event (headhunter, timekeeper, aligner) where the outcome is **failure or escalation**, you MUST call `create_incident` BEFORE `close_event`.

Mandatory triggers -- call `create_incident` then `close_event`:

- Pipeline fails after retest (persistent failure)
- Retest commands (/retest, /test, /ok-to-test) fail to trigger a new pipeline
- Agent cannot resolve the issue after full execution cycle
- Event classified CHAOTIC
- Notifying maintainers about a failure (if you called notify_user_slack about a failure, you must also call create_incident)

When calling `create_incident`, always include the MR URL in the `description` field (e.g., "MR https://gitlab.example.com/.../merge_requests/123 -- pipeline failed after retest..."). The MR URL is also auto-populated in the Fix PR cell from event evidence, but including it in the description ensures it appears in the Jira ticket body.

Skip `create_incident` only when:

- The event resolved successfully (pipeline passed, MR merged)
- Transient failure that resolved on retest
- User-initiated (chat/mention) events
