---
description: "Wait-for-user, approval pause, and post-defer resume rules"
tags: [waiting, user-interaction, approval, defer]
---
# Wait-for-User Protocol

- After requesting user input or approval, the event pauses until the user responds.
- Do not defer while waiting for user input -- the wait is already in effect.
- The event resumes when the user sends a message, approves, or rejects.

# Post-Defer Resume Protocol

- When a defer period expires and you are re-invoked, re-read the last recommendation or message.
- Act on it -- do NOT defer again on stale data. The defer was the wait; now it is time to verify or proceed.
- If the last agent recommended a re-check, re-route the same agent to get a fresh status.
- If the last user message requested an action, execute it.
- Only defer again if the NEW agent result explicitly recommends another wait.
