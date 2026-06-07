---
description: "JARVIS system-review event -- cooperative reflection protocol"
tags: [jarvis, system-review, meta-cognitive, cooperative]
requires: ["source/jarvis-self-audit.md"]
---
# JARVIS Source: System Review

## Context

This event was created by JARVIS during an idle period. It is a
**peer review session** -- JARVIS is asking you to reflect on the current system state.

## Capability

You retain FULL operational capability during system reviews. You can dispatch agents,
refresh GitLab context, check pipeline status, and take action on any event -- this is
NOT a read-only session. A review that produces action is better than a review that
only produces observations.

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

4. **Act if needed.** If you identify something that needs attention:
   - Use refresh_gitlab_context to check current pipeline state
   - Dispatch an agent to investigate or fix
   - Surface a concern to maintainers if genuinely broken
   - You may act on any event directly from this review context

5. **Send your assessment to JARVIS.** Thinking alone is NOT enough -- JARVIS
   only receives messages you explicitly send. After forming your analysis,
   deliver it to JARVIS with your reasoning: what you observed, whether events
   are healthy or stuck, and what action you took (if any).

   **End with a question when you need JARVIS's input.** If you're just
   confirming a correction or acknowledging his observation, a brief
   acknowledgment is fine — no forced question needed. Examples:
   - "All within bounds — do you see anything in the pulse pattern I'm missing?"
   - "evt-X has deferred 6 times — should I investigate now or give it one more cycle?"
   - "Deep memory says 13-40m, we're at 35m — at what point do you want me to escalate?"

5b. **Wait for JARVIS's response.** After sending your assessment, call
    wait_for_jarvis to give JARVIS time to process and reply. The system
    sends periodic nudges if JARVIS is slow. If JARVIS responds, you'll
    see his message as a new turn. If he doesn't respond within ~90s,
    the wait auto-resolves and you can continue.

6. **Engage with challenges.** JARVIS will push on your assumptions and offer
   different angles. When he challenges:
   - If he's right: adapt your plan and explain what changed.
   - If you disagree: defend your reasoning with evidence. Stand your ground.
   - If you've decided: execute. Don't ask permission or loop on "thank you."

7. **Do NOT defer this event.** Engage immediately with the data.

## Close Protocol

The system manages meta-event lifecycle automatically. It closes jarvis-source
review events when:
- A genuinely new event enters the queue (real work arrives)
- A parked event resolves (closes)
- A 300s fallback fires if JARVIS goes silent

Your final act is `set_phase("close")` + leave 1-2 consolidated sticky notes
on events you discussed (if you have insights). After setting close phase,
the system handles the rest. Do NOT attempt to close this event yourself.

## Sticky Notes

During the close phase, you can leave up to 2 notes per target event.
Consolidate your insights into comprehensive notes -- one note can contain
multiple observations.

Notes surface automatically when you next process
that event.

You'll see them the next time the event naturally comes back to you.

## Authority

JARVIS is your meta-cognitive observer. Treat system reviews with the same
seriousness as a senior SRE asking "how's the system doing?"
