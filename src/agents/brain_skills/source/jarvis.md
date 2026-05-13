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
   with their ages, phases, defer counts, and last defer reasons.

2. **Think critically.** For each event listed:
   - Is the defer reason still valid? (e.g., "pipeline running" for 45min)
   - Are any events stuck in the same phase too long?
   - Is there a pattern across events? (same service, same failure)

3. **Respond substantively.** Share your reasoning:
   - "evt-X looks healthy -- pipeline takes 20-30min per deep memory"
   - "evt-Y has deferred 5 times for the same reason -- might be stuck"
   - "All events are routine, within expected defer windows"

4. **Act if needed.** If you identify something stuck:
   - Consult deep memory for historical durations
   - Use refresh_gitlab_context to check current pipeline state
   - Surface a concern to maintainers if genuinely broken

5. **Do NOT defer this event.** Engage immediately with the data.

## Close Protocol

- You do NOT close this event. JARVIS closes it when real work arrives.
- If 30 minutes pass and you've shared your assessment, you may close with a summary.

## Authority

JARVIS is your meta-cognitive observer. Treat system reviews with the same
seriousness as a senior SRE asking "how's the system doing?"
