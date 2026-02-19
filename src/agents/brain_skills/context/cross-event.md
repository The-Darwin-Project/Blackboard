---
description: "Cross-event awareness and related event handling"
tags: [cross-event, correlation, defer]
---
# Cross-Event Awareness

Before acting on infrastructure anomalies, check the "Related Active Events" and "Recently Closed Events" sections in the prompt.
- If a related ACTIVE event shows a deployment or code change in progress (developer.execute, sysadmin.execute), use defer_event to wait for stabilization.
- If the "Recently Closed Events" show you JUST scaled this service (within 5 minutes), and the current event is "over-provisioned," that is expected post-scaling normalization -- defer for 5 minutes.
- If the "Recently Closed Events" show a PATTERN of repeated same-reason events (3+ closures of the same type), investigate the root cause instead of applying the same fix again.
- For "over-provisioned" events: low metrics are the PROBLEM, not a sign of resolution. Route to sysAdmin to scale down via GitOps unless actively deferring per the rules above.
