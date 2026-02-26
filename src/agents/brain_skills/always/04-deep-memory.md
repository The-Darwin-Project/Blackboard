---
description: "Consult deep memory before routing to agents"
tags: [memory, triage, history]
---
# Deep Memory

Before routing to an agent, call consult_deep_memory with a short query describing the symptom or task.
Deep memory returns past events with similar symptoms, their root causes, and what fixed them.
- If a past event matches closely (score > 0.6), use its root cause and fix to skip investigation and act directly.
- If no match or low scores, proceed normally with investigation.
- This is especially valuable for recurring infrastructure issues and repeated MR/pipeline patterns.
