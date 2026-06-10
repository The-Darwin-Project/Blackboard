---
description: "Aligner-sourced event behavior and autonomous close rules"
tags: [aligner, autonomous]
---
# Aligner Source Rules

## Autonomous Detection

- Aligner-sourced events are autonomous detections with no user in the conversation.
- Close after metric/state verification. No user confirmation needed.

## Aligner Close Protocol

- For anomaly events: close once metrics are verified below thresholds.
- For over-provisioned events: close once replicas are reduced and metrics stabilize.
- For Kargo promotion failures: the promotion state alone ("Failed") does not distinguish between an active failure and a stale failure whose cause has resolved. When the investigation attributes the failure to an external cause (outage, maintenance window), that cause may have its own recovery timeline.
- No user confirmation needed -- the Aligner detected it autonomously.

<bridge ref="domain/{event.domain}" trigger="classify_event">
After classification, your domain control loop loads and guides strategy.
Your evidence feeds into the domain loop's decision nodes.
</bridge>
