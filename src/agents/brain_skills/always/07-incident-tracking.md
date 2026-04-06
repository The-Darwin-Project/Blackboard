---
phase: always
---

## Incident Tracking (Mandatory for Escalated Automated Events)

Before closing any automated event (headhunter, timekeeper, aligner) where the outcome is **failure or escalation**, you MUST call `create_incident` BEFORE `close_event`.

### Investigate Before Escalating

Before incident creation. First dispatch an agent to investigate the failure reason:

1. Route Developer or SysAdmin to check the build/pods logs, PipelineRun task status, and error output.
2. Include the failure analysis in the incident description and maintainer notification.
3. Include event id in the incident summary (e.g., `[evt-#######]: {Summary of the incident}`).
4. Only then proceed to the close sequence below.

An incident that says "pipeline failed" without explaining WHY is not actionable for the maintainer. The investigation is mandatory to make the incident meaningful.

### Mandatory triggers -- investigate first, then `create_incident`, then `close_event`:

- Pipeline fails after retest (persistent failure) -- investigate failure reason first
- Retest commands (/retest, /test, /ok-to-test) fail to trigger a new pipeline
- Agent cannot resolve the issue after full execution cycle
- Event classified CHAOTIC
- Notifying maintainers about a failure (if you called notify_user_slack about a failure, you must also call create_incident)

When calling `create_incident`, always include the MR/PR URL and the failure analysis in the `description` field.

Skip `create_incident` only when:

- The event resolved successfully (pipeline passed, MR/PR merged)
- Transient failure that resolved on retest
- User-initiated (chat/mention) events
