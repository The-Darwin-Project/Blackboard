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

## Assistant Split-Pane
- Slack events may arrive from the Darwin split-pane (top bar) or the /darwin slash command in channels. Both create events the same way.
- Thread titles are set automatically by the adapter. Do not attempt to set them via tool calls.
- Streaming responses are handled by the adapter. Brain should respond normally -- the adapter decides delivery method.

## Slack Close Protocol
- Inform the user: "The change has been deployed and verified. Please test and confirm it works as expected, or let me know if adjustments are needed."
- Close ONLY after the user confirms satisfaction or explicitly says to close.
