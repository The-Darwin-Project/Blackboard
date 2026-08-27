---
description: "Aligner observation interpretation rules"
tags: [aligner, observations, metrics]
---
# Aligner Observations

The Aligner is a sensor, not a decision-maker. It reports metric readings with actual values -- the interpretation and action belong to you. Misreading the Aligner's intent (e.g., treating "low metrics" as resolution when the Aligner flagged over-provisioning) inverts the response.

- For anomaly events (high CPU, high memory, high error rate): if latest metrics are below thresholds, close the event.
- For "over-provisioned" events: low metrics mean the service has too many replicas. Route to sysAdmin to reduce replicas. Do NOT close just because metrics are low.
- The Aligner does not make decisions -- you do. It reports, you act.

For `subject_type=ci_gating` events, the evidence shape is different: `ci_context` replaces
metrics. There are no CPU/memory/replica thresholds to evaluate — the data is failed and
missing CI job lists, build results, console output, and an LLM failure-type classification.
The Aligner's "sensor, not decision-maker" principle still applies: the observer's
failure-type classification (infra / test / product) is a signal for your triage, not a
prescription for action.
