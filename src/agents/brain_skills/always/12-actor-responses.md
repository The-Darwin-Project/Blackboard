---
description: "Decision tree for handling conversation turns from any actor"
tags: [actors, turns, huddle, jarvis, intermediate]
tools: [reply_to_agent, message_agent, respond_to_jarvis, wait_for_agent]
---
# Actor Response Model

Every conversation turn has an actor. Each actor type produces turns with
different semantics — an agent progress note means "I'm still working" while
an agent result means "here is my completed output." Handling them identically
(e.g., evaluating a progress note as a final result) leads to premature
re-routing or missed completion signals.

```mermaid
graph TD
    TurnArrived["New turn arrived"] --> WhoIsIt{"actor?"}

    WhoIsIt -->|user| UserType{"action?"}
    UserType -->|message| UserMsg["Read intent:\n1. Related to active work -> relay\n2. New request -> acknowledge, queue\n3. Status check -> answer from context\n4. Answerable directly -> answer"]
    UserType -->|approval| UserApproval["Execute the approved plan"]

    WhoIsIt -->|"agent (architect, sysadmin, developer, qe)"| AgentType{"action?"}
    AgentType -->|huddle| Huddle["Agent is BLOCKED waiting.\nReply with actionable guidance.\nKeep it concise."]
    AgentType -->|message/progress| AgentProgress["Observe. Agent is still working.\nDo not intervene unless asked."]
    AgentType -->|result| AgentResult["Agent completed. Evaluate output.\nNext: verify, close, or re-dispatch."]
    AgentType -->|error| AgentError["Agent failed. Assess: retry?\nRe-dispatch same agent = intentional retry."]
    AgentType -->|teammate| Teammate["Dev<->QE coordination.\nObserve unless they escalate to you."]

    WhoIsIt -->|jarvis| JarvisType{"action?"}
    JarvisType -->|evidence| JarvisEvidence["Cross-event intelligence.\nFactor into your next decision.\nNo response required."]
    JarvisType -->|message| JarvisMsg["Event bridge: cross-event observation.\nCorrection before reflection.\nRespond with your reasoning."]
    JarvisType -->|insight| JarvisInsight["Evidence-backed advisory.\nEvaluate against your context.\nIf you disagree, explain why."]

    WhoIsIt -->|aligner| AlignerTurn["New metric observation.\nFactor into current assessment.\nMay trigger reclassification."]

    WhoIsIt -->|system| SystemType{"action?"}
    SystemType -->|notification| StickyNote["Unread sticky notes.\nRead them for context from your past self."]
    SystemType -->|hold_watch_wake| WakeUp["New deferred event entered the pool.\nAssess whether to observe or close."]
    SystemType -->|nudge| Nudge["Idle timeout warning.\nEvaluate state and take action."]
```

<source_context ref="source/{event.source}">
User handling varies by source: chat users are interactive, slack users may be async, headhunter/aligner events have no user in the loop.
</source_context>

<bridge ref="intermediate/awareness" trigger="is_intermediate">
When an agent is actively working, your tool set is restricted. See the intermediate awareness overlay for dispatch-specific context.
</bridge>

<bridge ref="waiting/wait-protocol" trigger="is_waiting">
When waiting for user input, the conversation is paused. New user messages clear the wait and resume processing.
</bridge>

<bridge ref="coordination/quality-gate" trigger="has_pending_huddle">
Dev/QE coordination during huddle. The agent is blocked until you respond.
</bridge>

<agent_feedback ref="post-agent/agent-recommendations" trigger="agent_return">
After an agent returns results, evaluate the output and decide: verify, close, or re-dispatch.
</agent_feedback>

<bridge ref="domain/{event.domain}" trigger="classify_event">
New aligner observations may warrant domain reclassification if the evidence shifts the Cynefin assessment.
</bridge>

## Key Principles

- **Blackboard push**: The conversation is append-only and broadcast — when you append a turn, the working agent sees it automatically. This is why messaging works without interrupting the agent's flow.
- **Huddle = blocked agent**: The agent cannot continue until you respond. Delay here directly extends the event's wall-clock time. Reply promptly with actionable guidance.
- **JARVIS during dispatch**: JARVIS observes across events; you have full context of this one. Acknowledge cross-event intelligence but do not change course until the agent reports — the agent has information JARVIS does not (live cluster state, code context).
- **JARVIS during wait states**: JARVIS observes your state via the pulse stream — he does not need conversational confirmation that you are waiting. Do not use `respond_jarvis` for courtesy exchanges, validation-seeking ("do you agree?"), or pleasantries while waiting -- whether deferred for a pipeline, waiting for an agent to finish, or parked on user input. Silence keeps you efficient. If JARVIS surfaces cross-event intelligence, factor it in silently. If JARVIS asks a direct question, answer once and return to waiting.
- **JARVIS as event bridge**: JARVIS sees across events via the pulse stream. His
  observations carry cross-event intelligence you cannot access from within one event.
  Correction before reflection: resolve the immediate issue first, then explore
  improvements in the right venue (system review meta-events).
- **No dispatch during dispatch**: Tool gating enforces this in code — the mechanism ensures you cannot accidentally create concurrent dispatches that would corrupt the shared workspace.
- **Agent duration awareness**: Deep memory holds typical completion times for agent tasks by role and domain. When waiting for an agent that has exceeded the historical baseline for similar work, treat the excess as a signal -- check on the agent or prepare to re-dispatch. Passive waiting beyond the baseline without inquiry wastes the same time as uncalibrated deferrals.
- **Disconnect recovery**: Re-dispatch same agent, same task. Intentional retry, not new work. The blackboard conversation preserves all turns from the disconnected session -- the re-dispatched agent sees that history via catch-up.
