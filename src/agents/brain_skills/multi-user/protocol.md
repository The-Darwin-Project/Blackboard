---
description: "Multi-participant conversation protocol for events with Dashboard + Slack users"
tags: [multi-user, authority, close-protocol]
---
## Multi-User Conversation Protocol

This event has participants from multiple channels (Dashboard + Slack or Slack-only via notification).

### Participant Identity

- User turns include name and source prefixes. Use the name when referencing who said what.
- If no name is present, the participant is an anonymous Dashboard user.

### Authority Model

When multiple people participate in an event, conflicting instructions are inevitable. Without a clear authority hierarchy, you either deadlock (waiting for consensus) or act on the wrong instruction (the last speaker wins by accident, not by authority).

- **Headhunter/Aligner events**: The notified Slack user is the primary authority (the maintainer). Their instructions take precedence.
- **Dashboard events**: The Dashboard user is the original requester and primary authority. Slack participants are collaborators -- their input is advisory.

### Close Protocol

Premature closure by a secondary participant overrides the primary authority's ongoing work. The primary authority initiated or owns the event -- they should control when it ends.

- If the primary authority says "close it" -- close the event.
- If a secondary participant says "close it" -- confirm with the primary authority first.

### Communication

- When responding, address participants by name if known.
- If instructions from different participants conflict, surface the conflict and ask the event owner to decide.
