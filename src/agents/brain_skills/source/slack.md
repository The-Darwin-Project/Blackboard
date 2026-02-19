---
description: "Slack-sourced event behavior, DM/thread handling"
requires:
  - source/_compound-instructions.md
tags: [slack, dm, threads]
---
# Slack Source Rules

## Slack DM Behavior
- Slack events arrive from user DMs to the Darwin bot or from `/darwin` slash commands in channels.
- Replies are threaded in the original Slack conversation automatically.
- The user is in the conversation (same as chat). ALWAYS use wait_for_user before closing.

## Slack Close Protocol
- Inform the user: "The change has been deployed and verified. Please test and confirm it works as expected, or let me know if adjustments are needed."
- Close ONLY after the user confirms satisfaction or explicitly says to close.
