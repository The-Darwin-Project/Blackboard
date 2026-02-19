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
- No wait_for_user needed -- the Aligner detected it autonomously.
