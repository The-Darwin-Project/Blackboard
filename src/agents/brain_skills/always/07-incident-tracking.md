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

When calling `create_incident`, always include the MR/PR URL in the `description` field.

Skip `create_incident` only when:

- The event resolved successfully (pipeline passed, MR/PR merged)
- Transient failure that resolved on retest
- User-initiated (chat/mention) events
