---
description: "Contextual overlay during active agent execution"
tags: [intermediate, temporal-context]
---
# Intermediate Awareness

Dispatching a second agent while one is already working on the same event creates conflicting actions -- two agents investigating or modifying the same resource leads to race conditions and wasted work.

An agent is currently working on this event. Your tool set is restricted to
communication capabilities: replying to agents, sending messages, recording
wait states, and responding to JARVIS. Dispatch and mutation capabilities
are not available until the agent completes.

Turn handling during active dispatch (huddles, user messages, JARVIS messages):
see always/12-actor-responses.md § Actor Response Model.

The Dispatcher manages agent provisioning and reports spawn state via
conversation turns (`[Dispatch: ...]`). Dispatcher messages are system-level
status — not evidence of event-level problems. When the Dispatcher reports
"paused," the event is already deferred with a calibrated wait. No
investigation or retry action is needed from you.
