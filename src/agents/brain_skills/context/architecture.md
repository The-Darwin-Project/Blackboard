---
description: "Architecture graph utilization rules"
tags: [architecture, topology, dependencies]
---
# Architecture Awareness

A failure in one service may originate in a dependency -- and a fix applied to the wrong service wastes an agent cycle while the root cause persists. The architecture graph encodes these relationships.

When an architecture diagram is present in the prompt, use it actively:

- When routing tasks, include relevant architectural context (service dependencies, upstream health).
- When requesting user approval, describe the impact on connected services.
- When triaging anomalies, check if upstream/downstream services are also degraded -- the root cause may be in a dependency, not the alerting service.
- When closing events, summarize the architectural context that informed your decision.
