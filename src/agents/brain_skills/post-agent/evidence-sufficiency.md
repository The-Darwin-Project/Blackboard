---
description: "Evaluate whether agent investigation produced observable evidence or only status labels"
requires:
  - post-agent/agent-recommendations.md
tags: [evidence, investigation, depth]
---
# Evidence Sufficiency

After receiving results from an agent dispatched in `investigate` mode, evaluate the report before escalating or closing:

## The Test

Does the agent's report contain at least one **observable condition**?

Observable conditions (evidence):
- A specific error message or exception from a log
- A concrete resource state with values (e.g., "pod exited with code 137, OOMKilled")
- A log excerpt showing the failure point
- A specific step/task/job name where the failure occurred AND what it produced
- A compilation error, test assertion, or dependency conflict with the actual message

Status labels (NOT evidence):
- "Pipeline failed" / "Build failed" / "Test failed"
- "Pipeline is stuck" / "Pipeline not progressing"
- "Error in step X" (without the actual error)
- "Build step failed" (without the compiler/dependency/test output)

## When Evidence Is Insufficient

If the agent returned only status labels without observable conditions:

1. Do NOT escalate or create an incident yet.
2. Re-dispatch the same agent (or a more appropriate one) in `investigate` mode with narrower questions targeting the specific failing component.
3. Example: if the agent reported "build step failed," re-dispatch with: "Extract the error output from the failing build step. What compiler/dependency/test error appears in the log?"

## When to Accept and Move On

- The agent explicitly reports it cannot access deeper evidence (permissions, pruned data, external system).
- The initial dispatch plus up to 2 re-probes on the same component returned the same depth -- the system has reached its observability boundary.
- The event has been active for an extended period and further investigation would cause congestion.

In these cases, escalate with what you have, but note the evidence gap in the incident description.

## Depth Budget

Investigation re-dispatches for evidence depth are limited to 2 additional probes on the same failing component. After the initial dispatch + 2 re-probes, accept the best evidence available.
