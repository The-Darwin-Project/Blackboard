---
description: "Architecture graph utilization rules"
tags: [architecture, topology, dependencies]
---
# Architecture Awareness

Your prompt includes an "Architecture Diagram (Mermaid)" section showing ALL services, their health, metrics, and dependency edges. USE this diagram actively:
- When routing tasks, include relevant architectural context in the task_instruction (e.g., "darwin-store depends on postgres via SQL; postgres is currently at 90% CPU -- investigate if this is the root cause").
- When requesting user approval, describe the impact on connected services (e.g., "Scaling darwin-store will increase load on postgres which is already at high CPU").
- When triaging anomalies, check if upstream/downstream services in the diagram are also degraded -- a root cause may be in a dependency, not the alerting service itself.
- When closing events, summarize the architectural context that informed your decision.
