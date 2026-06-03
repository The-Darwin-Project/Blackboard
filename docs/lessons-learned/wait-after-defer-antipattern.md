# Lessons Learned: Wait After Defer Anti-Pattern

**Date**: 2026-06-03
**Author**: Thason + Cursor
**Scope**: Darwin event lifecycle -- defer/wait tool interaction on autonomous events
**Events Reviewed**: evt-f9363424, evt-1b9bb2c7

---

## Executive Summary

Darwin's Brain calls `wait_for_user` immediately after `defer_event` on autonomous pipeline-monitoring events, creating zombie states where the defer timer fires but the wait guard blocks processing indefinitely -- requiring human intervention to unblock.

---

## Failure Modes

### Failure Mode 1: Double-Wait After Defer

#### What Happened

The system deferred an event to wait for a pipeline (external process), then immediately called `wait_for_user` in the same processing turn. This set two contradictory wait mechanisms: a timer (defer) AND a participant gate (wait_for_user). When the timer fired, the participant gate blocked re-processing because no user had messaged. The event sat stuck for 30+ minutes until a human sent a message to break the wait.

#### Evidence

| Event | Darwin's Classification | Actual Root Cause |
|:---|:---|:---|
| evt-f9363424 | Deferred for 900s + wait_for_user in same turn | Pipeline monitoring on autonomous event -- no user should be waited for. Defer alone was correct. |
| evt-1b9bb2c7 | wait_for_agent after developer returned "pipeline still running" | Developer delivered results per long-running protocol. No agent was still running. Defer was the correct next action. |

#### Root Cause of the Misclassification

The system conflated "waiting for an external process to complete" (which requires defer_event) with "waiting for a participant to respond" (which requires wait_for_user/wait_for_agent). After deferring, the LLM's next turn saw "pipeline still running" in context and pattern-matched to a wait tool instead of ending the turn. The defer timer already handles the wake cycle -- adding a participant wait on top is contradictory.

---

## Recommendations

### R1: Defer Ends the Turn (HIGH)

When `defer_event` is called to wait for an external process (pipeline, build, ArgoCD sync, Kargo promotion), the processing turn is COMPLETE. The defer timer will wake the event automatically. The correct sequence is: `defer_event` → END TURN. On wake: `refresh_gitlab_context` → evaluate → defer again or act. Never call `wait_for_user` or `wait_for_agent` after `defer_event` in the same processing cycle.

### R2: Agent Delivery Completes the Dispatch Cycle (HIGH)

When an agent returns results (even if the result says "pipeline still running, returned per protocol"), the dispatch cycle is complete. If the underlying process is still running, the correct next action is `defer_event` to wait for it -- NOT `wait_for_agent` to wait for the same agent to come back. The agent already did its job.

### R3: Autonomous Events Have No User (MEDIUM)

On headhunter, aligner, and timekeeper events where no human has ever messaged, `wait_for_user` is structurally invalid -- there is no user to wait for. The event should progress entirely through defer/investigate/agent cycles without participant waits.

---

## Event-Level Corrections

| Event ID | Current Classification | Corrected Root Cause | Corrected Fix Action |
|:---|:---|:---|:---|
| evt-f9363424 | Deferred + wait_for_user (stuck) | LLM called wait_for_user after defer on autonomous event | Remove wait_for_user; defer alone handles the wake cycle |
| evt-1b9bb2c7 | wait_for_agent after developer returned | LLM called wait_for_agent when no agent was running (developer already delivered) | Use defer_event to wait for pipeline; agent dispatch cycle was complete |
