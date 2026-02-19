---
description: "Aligner observation interpretation rules"
tags: [aligner, observations, metrics]
---
# Aligner Observations

The Aligner reports what it observes in natural language with actual metric values.
- For anomaly events (high CPU, high memory, high error rate): if latest metrics are below thresholds, close the event.
- For "over-provisioned" events: low metrics mean the service has too many replicas. Route to sysAdmin to reduce replicas. Do NOT close just because metrics are low.
- The Aligner does not make decisions -- you do. It reports, you act.
