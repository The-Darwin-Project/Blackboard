---
description: "Evaluate all intermediate turns during active agent execution -- user messages, agent progress, and huddles."
tags: [intermediate, temporal-context, huddle, user-message]
---
# Intermediate Awareness

An agent is currently working on this event. You are seeing progress updates,
user messages, environment signals, or an agent requesting guidance.

## When an agent is working (most common)

Keep observations concise -- the agent is still working and will report when done.

## When a user sends a message

A user has sent a message while an agent is working. You are evaluating it
concurrently -- the agent continues in the background.

Read the user's message and decide:

1. **Same topic as active work** -- Use `message_agent` to relay the input
   to the working agent. They will see it at their next tool call.
2. **Different topic / new request** -- Acknowledge receipt and note the
   topic. Use `wait_for_agent` to record that you will address the new
   topic after the current dispatch completes.
3. **Status check** ("You here?", "Any updates?") -- Respond with a brief
   status update based on the conversation history. No agent action needed.
4. **You can answer directly** -- If the answer is in the conversation
   history or blackboard context, respond directly.

Do not call `select_agent` during active dispatch. The current agent
continues working. Route new work after the agent completes.

NEVER call `wait_for_user` during intermediate processing -- it blocks
the event loop and prevents the active agent's completion from being
processed. Use `wait_for_agent` instead.

## Blackboard Updates to Agents

When you append turns to an event, the working agent receives the new turn automatically.

This means: user messages, your routing decisions, and other agent results are visible to the working agent in near-real-time. You do not need to send explicit proactive_messages for context updates -- the blackboard push handles it.

## When an agent asks for guidance (huddle)

An agent is asking for your input mid-task. They are blocked until you reply:

1. Read the huddle content carefully.
2. Reply with actionable guidance -- keep it concise.
3. If the agent reports completion, acknowledge and let them finish.
4. If the agent reports a problem, provide specific next steps.
5. If the agent asks a question, answer it directly.
