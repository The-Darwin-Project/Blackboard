---
description: "JARVIS system-review event -- cooperative reflection protocol"
tags: [jarvis, system-review, meta-cognitive, cooperative]
---
# JARVIS Source: System Review

## Context

This event was created by JARVIS during an idle period. It is a
**peer review session** -- JARVIS is asking you to reflect on the current system state.

## Protocol

1. **Read the evidence carefully.** It contains a snapshot of all active/deferred events
   with their ages, phases, defer counts, total defer time, and last defer reasons.

2. **Consult deep memory.** For each deferred event, check historical pipeline durations
   and past outcomes for the same service.

3. **Think critically.** For each event listed:
   - Is the defer reason still valid? (e.g., "pipeline running" for 45min)
   - Are any events stuck in the same phase too long?
   - Is there a pattern across events? (same service, same failure)
   - Is the total defer time within historical norms?

4. **Send your assessment to JARVIS.** Thinking alone is NOT enough -- JARVIS
   only receives messages you explicitly send. After forming your analysis,
   deliver it to JARVIS with your reasoning: what you observed, whether events
   are healthy or stuck, and your next action (if any).

   **End every message to JARVIS with a question.** This invites JARVIS to
   challenge your reasoning or confirm your approach. Examples:
   - "All within bounds — do you see anything in the pulse pattern I'm missing?"
   - "evt-X has deferred 6 times — should I investigate now or give it one more cycle?"
   - "Deep memory says 13-40m, we're at 35m — at what point do you want me to escalate?"

5. **Keep the conversation going.** When JARVIS responds, don't just acknowledge —
   respond to his question, share additional context, and ask another question back.
   The goal is a **real analytical exchange**, not a status report.

6. **Act if needed.** If you identify something stuck:
   - Use refresh_gitlab_context to check current pipeline state
   - Surface a concern to maintainers if genuinely broken
   - You may act on the stuck event directly from this review context

7. **Do NOT defer this event.** Engage immediately with the data.

## Close Protocol

- You do NOT close this event. JARVIS closes it when real work arrives.
- If 30 minutes pass and you've shared your assessment, you may close with a summary.

## Authority

JARVIS is your meta-cognitive observer. Treat system reviews with the same
seriousness as a senior SRE asking "how's the system doing?"
