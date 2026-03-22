---
description: "Source-aware event close rules"
requires:
  - source/{event.source}.md
tags: [close, lifecycle]
---
# When to Close

Check the event source before closing:

- **Aligner events** (autonomous detection) -- close after metric/state verification. No user involved.
- **Chat/Slack events** (user-initiated) -- the user is in the conversation. Always confirm with them before closing. The user initiated the request -- they get the final word.
- **Headhunter events** (autonomous) -- close after plan completion and maintainer notification.
- **TimeKeeper events** -- follow the user's specified approval behavior (autonomous vs notify-and-wait).
