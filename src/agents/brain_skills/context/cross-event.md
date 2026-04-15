---
description: "Cross-event awareness and related event handling"
tags: [cross-event, correlation, defer, merge]
---
# Cross-Event Awareness

Before acting on infrastructure anomalies, check the "Related Active Events" and "Recently Closed Events" sections in the prompt.

- If a related active event shows a deployment or code change in progress, defer to wait for stabilization.
- If recently closed events show a recent scaling change for this service, and the current event is "over-provisioned," that is expected post-scaling normalization -- defer to allow stabilization.
- If recently closed events show a PATTERN of repeated same-reason events (3+ closures of the same type), investigate the root cause instead of applying the same fix again.
- For "over-provisioned" events: low metrics are the PROBLEM, not a sign of resolution. Route to sysAdmin to scale down via GitOps unless actively deferring per the rules above.

## Cross-Source Evidence Merge

If an evidence turn from headhunter or aligner appears in the conversation,
a duplicate event was detected for the same MR URL. The turn contains the
duplicate event's context (GitLab details, Kargo stage info, maintainer
contacts, bot instructions). Incorporate this context into your triage:

- Use maintainer contacts from the merged context for notifications.
- Use bot instructions from the merged context for success/failure actions.
- Use pipeline status from the merged context if fresher than existing data.
- Do NOT dispatch a new agent solely to process the merged context --
  it is informational, not a new task.

### Evidence Sufficiency (Curiosity Gap)

Merged context is supplementary intelligence, NOT a substitute for
probe-based evidence. Before closing or escalating, verify that the
combined evidence (original event + merged context) meets the
evidence-sufficiency test:

- Does the event contain at least one **observable condition** (specific
  error message, concrete resource state, log excerpt)?
- If the merged context only adds status labels ("pipeline failed",
  "merge status: cannot_be_merged"), those are inputs to your triage,
  not proof. Still dispatch an agent with specific questions to drill
  into the failure.
- The merged context's bot instructions define the **action protocol**
  (what to do on success/failure), but the evidence-sufficiency test
  defines **when you have enough proof** to execute that protocol.
