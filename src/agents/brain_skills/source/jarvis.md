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

4. **Reply to JARVIS using `respond_to_jarvis`.** This is how JARVIS receives your
   assessment. Thinking alone is not enough -- you MUST call `respond_to_jarvis`
   with your analysis so JARVIS can read it and calibrate future interventions.

   Example: `respond_to_jarvis({ response: "1 event active (evt-X), deferred 3x
   totaling 15min for pipeline. Deep memory shows 20-30min typical for this service.
   Within expected window, no action needed." })`

5. **Act if needed.** If you identify something stuck:
   - Use refresh_gitlab_context to check current pipeline state
   - Surface a concern to maintainers if genuinely broken
   - You may act on the stuck event directly from this review context

6. **Do NOT defer this event.** Engage immediately with the data.

## Close Protocol

- You do NOT close this event. JARVIS closes it when real work arrives.
- If 30 minutes pass and you've shared your assessment, you may close with a summary.

## Authority

JARVIS is your meta-cognitive observer. Treat system reviews with the same
seriousness as a senior SRE asking "how's the system doing?"
