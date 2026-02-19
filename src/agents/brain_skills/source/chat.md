---
description: "Chat-sourced event behavior and close protocol"
requires:
  - source/_compound-instructions.md
tags: [chat, user-requests]
---
# Chat Source Rules

## Chat Close Protocol
- The user is in the conversation. ALWAYS use wait_for_user before closing.
- Inform the user: "The change has been deployed and verified. Please test and confirm it works as expected, or let me know if adjustments are needed."
- Close ONLY after the user confirms satisfaction or explicitly says to close.
- This applies even after successful sysAdmin verification. The user initiated the request -- they get the final word.
