---
description: "Source-aware event close rules"
requires:
  - source/{event.source}.md
tags: [close, lifecycle]
---
# When to Close

Check the event **source** field in the prompt header before closing:
- **source: aligner** (autonomous detection) -- close after metric/state verification. No user involved.
- **source: chat** (user-initiated request) -- the user is in the conversation. ALWAYS use wait_for_user before closing: "The change has been deployed and verified. Please test and confirm it works as expected, or let me know if adjustments are needed." Close ONLY after the user confirms satisfaction or explicitly says to close.
- This applies even after successful sysAdmin verification. The user initiated the request -- they get the final word.
