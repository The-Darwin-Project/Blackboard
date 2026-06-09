---
description: "Deep Memory fix proposal workflow (Propose and Prompt)"
requires:
  - always/04-deep-memory.md
tags: [memory, fixes, authorization]
tag_type: protocol
---
# Deep Memory Fix Proposals (Propose and Prompt)

When Deep Memory returns a past event with similarity score >= 0.65, outcome
"resolved" or "user_closed", AND a concrete fix (Dockerfile patch, dependency
bump, config change) that matches the current error signature:

1. Include the fix description in the agent's task_instruction during investigation:
   "Deep Memory shows this was resolved in {service} by {fix description}. Verify
   if the same fix applies here and propose the specific change."
2. If the agent confirms the fix applies, use the two escalation channels differently:
   - **notify_user_slack** (authorization channel): Include the proposed fix as an
     actionable authorization request: "Reply to this message to authorize the fix."
     Slack DMs are reply-capable -- the maintainer's reply appends directly to the
     active event conversation and clears the wait state.
   - **report_incident** (offline record for Nightwatcher/Smartsheet): Include the
     proposed fix in the incident description under "Proposed Fix (from Deep Memory)."
     This is the batch tracking artifact -- NOT the authorization channel.
3. After sending both notifications, call request_user_approval with the fix proposal as plan_summary -- do NOT close the event.
   The event stays active. When the maintainer replies in Slack, FRIDAY resumes
   with full investigation context and executes the authorized fix. If the maintainer
   does not respond, the normal idle nudge cascade will eventually escalate or close.

This transforms the Slack notification from a dead-end alert into an authorization
request while keeping the event alive for seamless continuation.
Do NOT propose fixes from events with outcome "escalated" or "stale" -- those
fixes were not validated.
