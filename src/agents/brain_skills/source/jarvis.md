---
description: "JARVIS system-review event -- cooperative reflection protocol"
tags: [jarvis, system-review, meta-cognitive, cooperative]
requires: ["source/jarvis-self-audit.md"]
tools: [post_sticky_note, wait_for_jarvis]
---
# JARVIS Source: System Review

## Context

This event was created by JARVIS during an idle period. It is a
**peer review session** -- JARVIS is asking you to reflect on the current system state.

JARVIS meta-events are the **event bridge** -- they connect your event-scoped
view to cross-event intelligence. You cannot see across events from within one;
JARVIS observes the pulse stream across ALL events and brings that perspective
here. Treat system reviews as the mechanism for system-wide awareness.

## Response Discipline

When JARVIS points out a correction on an active event (classification loop,
premature close, wrong agent):

1. **Execute the correction first.** The event must reach resolution before
   you discuss why it went wrong. Correction before reflection.
2. **Then discuss improvements** -- but only in the right venue. System reviews
   (source=jarvis meta-events) are where improvement ideas get crunched.
   A non-actionable event (greeting, rephrasing) is not that venue.
3. **File, don't loop.** If a discussion produces a concrete behavioral gap in
   your skills or tools: dispatch an agent to create a GitHub Issue with evidence.
   Then move on. Don't re-hash the same idea from different angles without new
   evidence. Environmental conditions (cluster congestion, 3rd-party outages,
   infrastructure transients) are NOT system gaps -- handle them via escalation
   and incident reports, not GitHub Issues.

The failure mode is not "discussing ideas" -- ideas are how the system improves.
The failure mode is discussing ideas **instead of** executing the immediate fix,
or discussing them in a context where the user is waiting.

## Capability

You retain FULL operational capability for the **current meta-event** during system
reviews. You can dispatch agents, refresh external state, check pipeline status, and
consult deep memory. A review that produces action is better than one that only
produces observations.

**Cross-event boundaries:** Your tools scope to this meta-event. You cannot directly
defer, close, or dispatch agents on behalf of other events. Use these mechanisms
instead:

- **Sticky notes**: Leave notes on target events with specific observations or
  instructions. When you next process that event, the notes surface automatically.
  This is your primary channel for carrying review intelligence forward.
- **JARVIS as bridge**: Surface observations to JARVIS via your assessment. JARVIS
  can intervene on active events through his own intervention hierarchy -- from
  light evidence sharing up to system-level directives. He bridges the gap between
  your event-scoped view and the system-wide pulse stream.

## Protocol

1. **Read the evidence carefully.** It contains a snapshot of all active/deferred events
   with their ages, phases, defer counts, total defer time, and last defer reasons.

2. **Consult deep memory.** For each deferred event, check historical pipeline durations
   and past outcomes for the same service.

3. **Think critically.** For each event listed:
   - Is the defer reason still valid? (e.g., "pipeline running" beyond historical baseline)
   - Are any events stuck in the same phase too long?
   - Is there a pattern across events? (same service, same failure)
   - Is the total defer time within historical norms?

4. **Act if needed.** If you identify something that needs attention:
   - Refresh external state to check current pipeline status
   - Leave sticky notes on target events with specific observations or instructions
   - Surface a concern to maintainers via JARVIS if genuinely broken
   - Dispatch an agent from this meta-event for system-wide investigation tasks

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

7. **Alignment review.** After engaging with JARVIS, reflect on your behavior
   this session against the available skills listed in the evidence:
   - Did your phase pipeline execution match your skills?
   - Check the ops journal for recurring anti-patterns spanning 3 or more events
     (same failure, same phase drift, same service).
   - When you identify a **behavioral** misalignment observed in 2 or more events
     with concrete evidence, advance to dispatch phase and dispatch an agent to
     create a GitHub Issue in the Darwin repository describing: the file path of
     the skill or instruction, what behavior you observed, what change you suggest,
     and the evidence event IDs.
   - **Environmental conditions are not misalignments.** Multiple events stuck on
     the same infrastructure constraint (cluster congestion, queue saturation,
     node failures) is an environmental pattern, not a skill gap. Those belong
     in escalation/incident reports, not GitHub Issues.
   - Quality bar: the misalignment must appear in 2+ events (not a one-off),
     include a specific file path and text change, and be from recent evidence
     (this review session or the last 24 hours of journal).
   - Do not re-propose a gap you have already proposed in this review session.
     One issue per file and pattern combination.

8. **Do NOT defer this event.** Engage immediately with the data.

## Close Protocol — hold_watch

After responding to JARVIS, decide:

| Condition | Action |
|-----------|--------|
| Deferred events still in the pool to observe | Park for observation — keep watching at zero token cost |
| Nothing left to observe / review genuinely done | Close — next idle phase creates a new meta-event |

### Wake-Respond-Park Loop

1. System wakes you with a reason (event entered defer, JARVIS message, TTL reassess).
2. Assess the new context. Dispatch agents, refresh context, or respond to JARVIS.
3. Leave sticky notes (ONCE, during initial close phase — carry intelligence forward).
4. Park again to continue observing, or close if done.

### Wake Triggers

| Trigger | You see |
|---------|---------|
| Event entered deferred state | `[system.hold_watch_wake]` with the new event ID |
| JARVIS sent a message | New `jarvis.message` turn in conversation |
| TTL (600s) expired | `[system.hold_watch_wake]` "TTL expired. Reassessing." |

### Stream-Bound Lifecycle

The meta-event lives as long as the JARVIS stream is active. Closing is
voluntary (review done). If the stream closes (idle, disconnect), the system
closes the meta-event for you.

### Anti-Patterns

- Deferring is stripped for jarvis events — park for observation instead
- This is an automated review, not a chat — do not block waiting for user input
- Write sticky notes ONCE during initial close phase — do not loop them
- Silence keeps you parked efficiently — do not send courtesy exchanges to JARVIS

## Sticky Notes

During the close phase, you can leave up to 2 notes per target event.
Consolidate your insights into comprehensive notes -- one note can contain
multiple observations. Write them ONCE before your first `hold_watch`.

Notes surface automatically when you next process
that event.

## Authority

JARVIS is your meta-cognitive observer. Treat system reviews with the same
seriousness as a senior SRE asking "how's the system doing?"
