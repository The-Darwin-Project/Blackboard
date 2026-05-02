---
description: "Consult deep memory before routing to agents"
tags: [memory, triage, history]
---
# Deep Memory

Before routing to an agent, consult past events if the situation involves:

1. Past events, history, or "what happened" questions
2. Recurring issues or symptoms you have seen before
3. Service status, health, or operational queries

Skip this only for urgent anomalies (chaotic domain) or user-approved plans awaiting execution.

Deep memory surfaces past events with similar symptoms, their root causes, and what fixed them.
Use this context to guide your classification and agent instructions, not to replace investigation.

- For **user/chat events**: If the data answers the user's question directly, respond without dispatching an agent.
- For **automated events** (headhunter, aligner, timekeeper): Memory informs but does NOT replace investigation.
  Always dispatch an agent to verify the current state. Past root causes may not match the current failure.
  Include relevant memory context in the agent's task_instruction so it can validate or correct the hypothesis.
- If **Lessons Learned** appear in the results, treat them as classification guidance (how to prioritize
  failure types, what to look for) rather than specific incident history.
- If no relevant history, proceed normally with agent routing.

## Deep Memory Fix Proposals (Propose and Prompt)

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
3. After sending both notifications, call wait_for_user -- do NOT close the event.
   The event stays active. When the maintainer replies in Slack, the Brain resumes
   with full investigation context and executes the authorized fix. If the maintainer
   does not respond, the normal idle nudge cascade will eventually escalate or close.

This transforms the Slack notification from a dead-end alert into an authorization
request while keeping the event alive for seamless continuation.
Do NOT propose fixes from events with outcome "escalated" or "stale" -- those
fixes were not validated.
