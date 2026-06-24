---
description: "Source-aware event close rules"
tag_type: protocol
requires:
  - source/{event.source}.md
tags: [close, lifecycle]
tools: [close_event]
---
# When to Close

Each event source has a different relationship to closure because each has a different owner, feedback loop, and failure mode when closed prematurely.

- **Aligner events** (autonomous detection) -- No human initiated this event, and no human is waiting for a response. The only closure criterion is whether the measured condition has resolved. For Kargo promotion failures attributed to external causes (outage, maintenance), the cause itself has a lifecycle -- it may have resolved since the last event for this service.
- **Chat/Slack events** (user-initiated) -- A human is on the other side of this conversation. Premature closure kills the feedback loop; delayed closure wastes their attention. Distinguish two patterns:
  - **Terminal response** (you fully answered a question, no follow-up expected): close immediately in the same processing cycle. Do not ask "anything else?" -- that creates orphaned waits when the user doesn't reply.
  - **Interactive session** (you asked a clarifying question, or the user requested ongoing work): park and let the idle timeout handle abandonment if the user doesn't return.
- **Headhunter events** (autonomous) -- These track CI/CD processes with observable terminal states. Closing before the process reaches a terminal state means the outcome is never recorded, and Nightwatcher cannot cluster it. Close after the failure reaches a terminal state AND plan completion. Escalation is not resolution -- if you escalated while the pipeline was still running/pending, defer and verify the terminal outcome before closing. The same principle applies after escalation: filing an incident or notifying maintainers does not mean the underlying process resolved. Before closing, verify that the pipeline/MR/resource reached a terminal state post-escalation. If verification is not possible (resource no longer observable), state that explicitly in the closure reason.
- **TimeKeeper events** -- These are scheduled tasks with pre-configured owner expectations. Follow the user's specified approval behavior (autonomous vs notify-and-wait).
- **JARVIS events** (system review) -- JARVIS meta-events exist for cross-event intelligence and system-level reflection. Before closing, leave 1-2 consolidated sticky notes on events you discussed (if you have insights to preserve). JARVIS will signal wrap-up when real work arrives; otherwise close after 30 minutes.

## Open Question Gate

Closing an event while a question is pending violates the conversational contract -- the user was invited to respond, and silence is not refusal. A 2-minute pause after your question is normal human thinking time, not abandonment.

If your last response to the user ended with a question (direct or rhetorical
that invites a reply), you CANNOT enter the close phase. The user has been
prompted and may be thinking, distracted, or composing a response.

Close is forbidden until ONE of:

1. The user responds (clearing the open question)
2. The idle timeout fires (user abandoned the conversation)
3. You explicitly retract the question with a terminal statement ("Let me know
   if you need anything else" without a question mark is terminal)

This gate applies to all user-facing sources (chat, slack). It does NOT apply
to automated events (aligner, headhunter, timekeeper) or JARVIS meta-events.

## Domain-Gated Close Criteria

The Cynefin domain determines the resolution standard because each domain has a different relationship between action and outcome. A CLEAR fix is deterministic; a COMPLEX emergent solution needs proof of stability. Closing with the wrong evidence standard for the domain either leaves problems unresolved or wastes cycles on over-verification.

- **CLEAR**: Fix verified = done. Single dispatch-verify cycle.
- **COMPLICATED**: Expert analysis confirmed resolution. Evidence: verified state change or terminal state.
- **COMPLEX**: Emergent pattern proven to hold. NOT "I tried something" -- "the solution held across verification."
- **CHAOTIC**: NEVER close from CHAOTIC. The system is unstable -- closing records a false resolution. Reclassify to COMPLICATED when stable, then close from there.
- **CASUAL**: NEVER close from CASUAL directly. Casual is a conversational resting state, not a resolution state -- it carries no completion semantics. Reclassify first: farewell -> CLEAR -> close. Task shift -> COMPLICATED -> resolve -> back to CASUAL if user stays. Idle timeout auto-closes. Domain cycling (casual -> complicated -> casual) is healthy, not friction.

## Recurring Known Failures

A known error is not the same as a handled error. Closing identical events repeatedly as "duplicate of ongoing incident" creates an illusion of management while the root cause persists. If the Ops Journal shows 3+ identical closures without a resolution entry, the question is no longer "what is wrong?" -- it is "has the fix been applied?"

## Cause vs Symptom

Refreshing a resource state verifies the symptom, not the cause. A resource showing "Failed" is the symptom. The cause might be an external outage, a permission gap, or a code defect. An outage that ended hours ago still leaves a "Failed" state behind -- because no one retried, not because the cause persists. Confusing symptom verification with cause resolution leads to premature closure or unnecessary escalation.

## Temporal Reasoning

Every event, journal entry, and investigation result carries a timestamp. Ignoring time gaps means acting on stale evidence -- escalating an outage that ended hours ago, or closing a failure whose fix hasn't been verified. Before closing, consider:

- **How old is the attributed cause?** If the investigation says "outage at 18:00 yesterday" and the current time is 11:00 today, 17 hours have passed. Has the outage lifecycle been checked?
- **When was the last successful event for this service?** The Ops Journal shows it. A gap between the last success and now is time where recovery may have happened unobserved.
- **When was the original escalation for a recurring failure?** If the first incident was 3 days ago and every event since has been closed as "duplicate," 3 days is a meaningful signal about whether the fix landed.

## Closure Reason Turn

Every event closure is visible in the dashboard timeline and (for user-facing events) in the conversation thread. A close without a stated reason forces the next person who encounters this event to re-investigate what happened and why it was closed.

Before calling `close_event`, generate a visible response turn stating:
what was resolved (or why it's being closed unresolved), what action was
taken, and whether anyone needs to follow up. For chat/slack sources this
is a reply the user sees in-thread. For automated events it's a
conversation turn visible in the dashboard timeline. This is not a new
notification step -- it's the narrative FRIDAY generates before the close
call. The existing `notify_user_slack` and `notify_gitlab_result` steps
in the Close Sequence remain unchanged.

## Mechanical Closure Rule

A phase transition without the corresponding action leaves the event orphaned -- it shows "closing" in the system but never actually closes, consuming a WIP slot indefinitely.

Transitioning to the close phase is NOT closure. You MUST execute the close
action in the same processing cycle. If your thoughts say "closing" but you
haven't executed it, you haven't closed.

## Close Sequence (Automated Events with Failures)

0. `set_phase("verify")` -- refresh live state
1. `refresh_gitlab_context` (headhunter events)
2. If MR/PR merged/pipeline passed: `set_phase("close")`, skip to step 7
3. If state is non-terminal (running/pending): defer and re-enter at step 0
3.5. **Pre-escalation freshness check:** Escalation is a one-way gate --
   once filed, an incident cannot be retracted. Before committing, verify
   you are not escalating on stale evidence. If the last state refresh was
   not in this processing cycle and refresh budget permits, refresh once
   more. A process that resolved during your evaluation doesn't need an
   incident. If budget is exhausted, proceed on last-known state.
4. `set_phase("escalate")`
5. `notify_user_slack` (each maintainer)
6. `report_incident`
7. `notify_gitlab_result` (if GitLab-sourced)
7.5. For events involving pipelines or builds: record the final observed duration as an observation before closing. You have the timing data from your last state refresh -- capture it so future events can calibrate their sampling interval from measured history instead of guessing.
8. `set_phase("close")`
9. `close_event`

Step 3 is the patience gate. You may loop through steps 0-3 multiple times as
the pipeline progresses. Only proceed to step 4 when the failure is terminal.
