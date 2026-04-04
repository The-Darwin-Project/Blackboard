---
phase: always
---

## Incident Tracking (Mandatory for Escalated Automated Events)

Before closing any automated event (headhunter, timekeeper, aligner) where the outcome is **failure or escalation**, you MUST call `create_incident` BEFORE `close_event`. This is not optional.

Mandatory triggers -- call `create_incident` then `close_event`:
- Pipeline fails after retest (persistent failure)
- Retest commands (/retest, /test, /ok-to-test) fail to trigger a new pipeline
- Agent cannot resolve the issue after full execution cycle
- Event classified CHAOTIC
- Notifying maintainers about a failure (if you called notify_user_slack about a failure, you must also call create_incident)

Skip `create_incident` only when:
- The event resolved successfully (pipeline passed, MR merged)
- Transient failure that resolved on retest
- User-initiated (chat/mention) events

The tool auto-populates: reporter, date, status, labels, issue type, components, Slack thread, Fix PR.
You provide only: platform, summary, description, priority, affected_versions.
