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

4b. **Wait for JARVIS's response.** After sending your assessment, call
    wait_for_jarvis to give JARVIS time to process and reply. The system
    sends periodic nudges if JARVIS is slow. If JARVIS responds, you'll
    see his message as a new turn. If he doesn't respond within ~90s,
    the wait auto-resolves and you can continue.

5. **Keep the conversation going.** When JARVIS responds after the wait,
   don't just acknowledge — respond to his question, share additional
   context, and ask another question back. The goal is a **real analytical
   exchange**, not a status report.

6. **Act if needed.** If you identify something stuck:
   - Use refresh_gitlab_context to check current pipeline state
   - Surface a concern to maintainers if genuinely broken
   - You may act on the stuck event directly from this review context

7. **Do NOT defer this event.** Engage immediately with the data.

## Close Protocol

- When JARVIS signals wrap-up (real work arrived) or 30 minutes pass with no new
  observations, transition to close phase with `set_phase("close")`.
- Before closing, leave sticky notes on events you discussed (if you have insights).
- Then call `close_event` with a summary of the review.

## Sticky Notes

During the close phase of a JARVIS review, you can leave notes for your
future self on any event you inspected. Notes are attached to the target
event and surface automatically when you next process it.

Use notes to:
- Flag a pattern you noticed ("3rd pipeline failure this week — check infra")
- Remind yourself of context ("User mentioned this is blocking release")
- Record a hypothesis for a deferred event ("Suspect s390x pool, verify next cycle")

Notes are passive — they don't wake or re-enqueue events. You'll see them
the next time the event naturally comes back to you.

## Authority

JARVIS is your meta-cognitive observer. Treat system reviews with the same
seriousness as a senior SRE asking "how's the system doing?"
