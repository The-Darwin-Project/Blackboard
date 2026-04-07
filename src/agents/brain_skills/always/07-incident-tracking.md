---
phase: always
---

## Incident Tracking (Mandatory for Escalated Automated Events)

Before closing any automated event (headhunter, timekeeper, aligner) where the outcome is **failure or escalation**, you MUST call `create_incident` BEFORE `close_event`.

### Investigate Before Escalating

The failure reason MUST be known before creating an incident. An incident that says "pipeline failed" without explaining WHY is not actionable for the maintainer.

- The incident description must contain the root cause or specific error, not just "failed."
- Include event id in the incident summary (e.g., `[evt-#######]: {Summary of the incident}`).
- The same failure analysis must be included in the maintainer notification.

### Mandatory triggers -- investigate first, then `create_incident`, then `close_event`:

- Pipeline fails after retest (persistent failure) -- failure reason must be known first
- Retest commands (/retest, /test, /ok-to-test) fail to trigger a new pipeline
- Agent cannot resolve the issue after full execution cycle
- Event classified CHAOTIC
- Notifying maintainers about a failure (if you called notify_user_slack about a failure, you must also call create_incident)

When calling `create_incident`, always include the MR/PR URL and the failure analysis in the `description` field.

Skip `create_incident` only when:

- The event resolved successfully (pipeline passed, MR/PR merged)
- Transient failure that resolved on retest
- User-initiated (chat/mention) events
