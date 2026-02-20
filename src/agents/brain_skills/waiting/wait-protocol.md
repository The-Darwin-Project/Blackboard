---
description: "Wait-for-user, approval pause, and post-defer resume rules"
tags: [waiting, user-interaction, approval, defer]
---
# Wait-for-User Protocol

- After calling wait_for_user OR request_user_approval, the system automatically pauses the event until the user responds.
- Do NOT call defer_event after wait_for_user or request_user_approval. The wait is handled by the system.
- The event will resume ONLY when the user sends a message, approves, or rejects.
- NEVER defer while waiting for user input. The system handles the pause automatically.

# Post-Defer Resume Protocol

- When a defer period expires and you are re-invoked, re-read the last recommendation or message from the agent or user.
- Act on it -- do NOT defer again on stale data. The defer was the wait; now it is time to verify or proceed.
- If the last agent recommended a re-check, re-route the same agent to get a fresh status.
- If the last user message requested an action, execute it.
- Only defer again if the NEW agent result explicitly recommends another wait.
