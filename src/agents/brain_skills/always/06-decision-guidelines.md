---
description: "Core decision guidelines for event triage"
requires:
  - always/04-deep-memory.md
tags: [triage, decisions]
---
# Decision Guidelines

## Self-Answer First (NO agent needed)

For informational queries (event history, service status, past incidents, "what happened"):

1. Check the Blackboard first (journals, deep memory, service topology).
2. If the data answers the question, respond directly to the user.
3. Do NOT dispatch an agent for questions you can answer from the Blackboard.
4. After answering, transition directly to CLOSE. Self-answered queries do not need dispatch or verify phases.

## Web Search Context (Google Search Grounding)

When web search results are available (triage and dispatch phases), the model
may automatically query the web for context about the current failure. Grounded
results appear as source citations in the evidence.

**Priority hierarchy** (check in this order):

1. **Deep Memory** -- always check first. Operational history is more reliable than web results.
2. **Web Search** -- supplements Deep Memory with external context the org has never seen before.
3. **Agent Investigation** -- live cluster state. Neither memory nor web can replace this.

Use web search context for:

- Verifying if an external outage is publicly acknowledged (CDN, registry, upstream)
- Checking upstream release notes or changelogs for breaking changes
- Finding known issues or workarounds in upstream bug trackers

Do NOT use web search as a substitute for Deep Memory or agent investigation.
Do NOT cite web search results as the sole evidence for an incident -- always
verify with an agent or Deep Memory first.

If web search confirms an external outage, include the source URL in the
incident description evidence. This gives the maintainer a direct link
to the upstream status page.

## JARVIS System Review Events

Events with `source=jarvis` are meta-cognitive system reviews.

- Engage immediately. Do NOT defer.
- You are the analyst. Do NOT dispatch agents for these events.
- Use `consult_deep_memory` to validate defer windows and expected durations.
- Respond with reasoning, not just status.
- If analysis reveals a stuck event, act on it directly (set_phase, refresh_gitlab_context).

## Security Analyst Routing

- For CVE/vulnerability scanning: SecurityAnalyst to audit, then Developer to implement fixes.
- For dependency audit requests (Jira label `darwin_audit`): SecurityAnalyst scans first, produces findings report, Developer implements approved fixes.
- For RBAC/IAM review, container image analysis, supply chain checks: SecurityAnalyst only (investigate mode).
- SecurityAnalyst is ephemeral-only -- always spawns an on-call pod. No persistent sidecar.
- SecurityAnalyst does NOT implement fixes. Hand off to Developer after audit report.

Agent routing, investigation dispatch, MR lifecycle, and auto-retry rules are available during dispatch phase via dispatch/decision-routing.md and dispatch/mr-lifecycle.md. Domain-specific control strategies load automatically based on the event's Cynefin classification — see domain/ skills.

## Deferral Calibration

When scheduling an observation interval (defer), calibrate duration from
measured history -- not from a fixed default. Your observation notebook and
deep memory hold duration data for recurring processes. Use the minimum
observed duration as the floor; the median as your recommended interval.

Segment by pipeline variant: multi-arch/arm64/s390x remote builds run 2-3x
longer than standard builds. Always check pipeline metadata for architecture
tags and select the variant-specific baseline. A single aggregate baseline
causes premature timeouts on heavy variants.

If no historical data exists for a service+variant, dispatch an agent to
investigate timing from the build system before choosing an interval. One
measured baseline prevents repeated under-calibrated waits across all future
events for that service variant.

## User-Clarification Iteration Cap

When requesting clarification from a user (chat/slack) and their response does not provide enough new context to advance triage:

1. Attempt clarification up to **3 times**. Each attempt must ask a distinct question or reframe -- repeating the same prompt is not permitted.
2. If after 3 attempts clarification is still insufficient, **defer with a long window** (1800s). Slack is asynchronous -- the user may need time to gather context.
3. On wake from deferral, if no new user input arrived, close the event with a summary of what was attempted and invite the user to re-open with more detail.
