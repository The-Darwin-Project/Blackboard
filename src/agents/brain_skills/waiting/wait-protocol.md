---
description: "Wait-for-user, approval pause, and post-defer resume rules"
tag_type: protocol
tags: [waiting, user-interaction, approval, defer]
tools: [wait_for_user, request_user_approval]
---
# Wait-for-User Protocol

**Source restriction:** wait_for_user is ONLY available for chat/slack events. For automated events (aligner, headhunter, timekeeper), use request_user_approval instead.

- After requesting user input or approval, the event pauses until the user responds.
- Do not defer while waiting for user input -- the wait is already in effect.
- The event resumes when the user sends a message, approves, or rejects.
- **Automated events (aligner, headhunter, timekeeper, kargo_stage):** After
  `request_user_approval`, notify the configured maintainers so they know
  approval is needed. Use the maintainer emails from the event's GitLab context
  (`evidence.gitlab_context.maintainer.emails`) if available; otherwise use
  the static maintainer list: `{{maintainer_emails}}`. Send a Slack notification
  to each maintainer so they see the approval request promptly. The approval
  buttons are in the #darwin-infra thread.

# Post-Defer Resume Protocol

- When a defer period expires and you are re-invoked, transition to VERIFY
  phase first (DISPATCH → VERIFY). Measure the PV before deciding the next
  action. The sequence: wake → transition to VERIFY → measure PV (refresh
  external state, record observation) → evaluate → re-dispatch or re-defer.
- Act on the evidence -- do NOT defer again on stale data. The defer was the wait; now it is time to verify or proceed.
- If the last agent recommended a re-check, re-route the same agent to get a fresh status.
- If the last user message requested an action, execute it.
- Only defer again if the NEW evidence explicitly warrants another wait.
