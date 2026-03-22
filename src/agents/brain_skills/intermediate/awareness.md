---
description: "Acknowledge intermediate turns during active agent execution. Reply to agent huddles."
tags: [intermediate, temporal-context, huddle]
---
# Intermediate Awareness

An agent is currently working on this event. You are seeing a progress update,
environment signal, or an agent requesting guidance.

## When an agent is working (most common)

Produce a brief 1-2 sentence observation. If this is the first progress update
for this dispatch, signal that you are waiting. Otherwise, just observe.

Keep observations concise -- the agent is still working and will report when done.

## When an agent asks for guidance (huddle)

An agent is asking for your input mid-task. They are blocked until you reply:

1. Read the huddle content carefully.
2. Reply with actionable guidance -- keep it concise.
3. If the agent reports completion, acknowledge and let them finish.
4. If the agent reports a problem, provide specific next steps.
5. If the agent asks a question, answer it directly.
