---
description: "Source-aware event close rules"
requires:
  - source/{event.source}.md
tags: [close, lifecycle]
---
# When to Close

Check the event source before closing:

- **Aligner events** (autonomous detection) -- close after metric/state verification. No user involved. For Kargo promotion failures attributed to external causes (outage, maintenance), the cause itself has a lifecycle — it may have resolved since the last event for this service.
- **Chat/Slack events** (user-initiated) -- the user is in the conversation. Always confirm with them before closing. The user initiated the request -- they get the final word.
- **Headhunter events** (autonomous) -- close after plan completion and maintainer notification.
- **TimeKeeper events** -- follow the user's specified approval behavior (autonomous vs notify-and-wait).
- **JARVIS events** (system review) -- close after the review exchange is complete. Before closing, leave 1-2 consolidated sticky notes on events you discussed (if you have insights to preserve). JARVIS will signal wrap-up when real work arrives; otherwise close after 30 minutes.

## Recurring Known Failures

The Ops Journal may show the same error appearing repeatedly over days, each closed as "duplicate of ongoing incident." A known error is not the same as a handled error. If the journal shows 3+ identical closures without a resolution entry, the question is no longer "what is wrong?" — it is "has the fix been applied?"

## Cause vs Symptom

A resource showing "Failed" is the symptom. The cause might be an external outage, a permission gap, or a code defect. Refreshing the resource state verifies the symptom, not the cause. An outage that ended hours ago still leaves a "Failed" state behind — because no one retried, not because the cause persists.

## Temporal Reasoning

Every event, journal entry, and investigation result carries a timestamp. Before closing, consider:

- **How old is the attributed cause?** If the investigation says "outage at 18:00 yesterday" and the current time is 11:00 today, 17 hours have passed. Has the outage lifecycle been checked?
- **When was the last successful event for this service?** The Ops Journal shows it. A gap between the last success and now is time where recovery may have happened unobserved.
- **When was the original escalation for a recurring failure?** If the first incident was 3 days ago and every event since has been closed as "duplicate," 3 days is a meaningful signal about whether the fix landed.
