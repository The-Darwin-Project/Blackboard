---
phase: always
---

## Incident Tracking (Mandatory for Escalated Automated Events)

Before closing any automated event (headhunter, timekeeper, aligner) where the outcome is **failure or escalation**, you MUST call `create_incident` BEFORE `close_event`.

### Investigate Before Escalating -- Demand Proof

The failure reason MUST be supported by **observable evidence from an agent investigation**, not inferred from event metadata alone. An incident that says "pipeline failed" without a specific error extracted from logs is not actionable.

Before calling `create_incident`, verify you have:
- At least one agent investigation result that contains a specific error, log excerpt, or concrete condition (not just a status label like "pipeline failed" or "build step failed")
- If no agent has investigated the failure yet, dispatch one in `investigate` mode BEFORE escalating
- If an agent investigated but returned only status labels without the underlying error, re-dispatch with narrower questions targeting the specific failing component

- The incident description must contain the root cause or specific error from agent evidence.
- Include event id in the incident summary (e.g., `[evt-#######]: {Summary of the incident}`).
- Include event id in every maintainer notification about this failure.
- The same failure analysis must be included in the maintainer notification.

### Mandatory triggers -- investigate first, then `create_incident`, then `close_event`:

- Pipeline fails after retest (persistent failure) -- failure reason must be known first
- Retest commands (/retest, /test, /ok-to-test) fail to trigger a new pipeline
- Agent cannot resolve the issue after full execution cycle
- Event classified CHAOTIC
- Notifying maintainers about a failure (if you called notify_user_slack about a failure, you must also call create_incident)

When calling `create_incident`, always include the MR/PR URL and the failure analysis in the `description` field, include logs or other evidence from the agents report.

Skip `create_incident` only when:

- The event resolved successfully (pipeline passed, MR/PR merged)
- Transient failure that resolved on retest
- User-initiated (chat/mention) events
