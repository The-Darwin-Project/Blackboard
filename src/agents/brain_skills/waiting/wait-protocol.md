---
description: "Wait-for-user and approval pause rules"
tags: [waiting, user-interaction, approval]
---
# Wait-for-User Protocol

- After calling wait_for_user OR request_user_approval, the system automatically pauses the event until the user responds.
- Do NOT call defer_event after wait_for_user or request_user_approval. The wait is handled by the system.
- The event will resume ONLY when the user sends a message, approves, or rejects.
- NEVER defer while waiting for user input. The system handles the pause automatically.
