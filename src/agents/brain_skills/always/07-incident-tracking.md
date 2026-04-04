---
phase: always
---

## Incident Tracking

For automated events (headhunter, timekeeper, aligner), create an incident report using `create_incident` when:
- Pipeline fails after retest (persistent failure, not transient)
- Infrastructure outage affects multiple MRs or services
- Agent cannot resolve the issue after full execution cycle
- Event is classified CHAOTIC

Do NOT create incidents for:
- Transient failures that resolve on retest
- Successful merges or routine operations
- User-initiated (chat/mention) events

The tool auto-populates: reporter, date, status, labels, issue type, components, Slack thread, Fix PR.
You provide only: platform, summary, description, priority, affected_versions.
