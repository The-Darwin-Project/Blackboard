<!--
AUTHORING GUIDE FOR AI ASSISTANTS (Cursor, Copilot, Claude)
============================================================
This template is designed for LLM-assisted authoring. When a user asks you to
help write a Lessons Learned document:

1. Start by pulling event reports: GET /queue/{event-id}/report for each event
2. For each event, compare Darwin's classification (in the close turn) against
   the actual evidence (in investigation execute turns)
3. Group events by failure mode -- look for shared root causes across events
4. Write failure modes as ABSTRACT PATTERNS, not component-specific descriptions:
   - Good: "Infrastructure failures (image pull, OOM) were missed because only
     task-level results were inspected"
   - Bad: "quay.io/konflux-ci/oras:latest failed to pull in sast-shell-check"
5. Fill the Event-Level Corrections table with concrete corrections per event
6. The Executive Summary should be a single sentence describing the systemic issue

The more structured your output, the better the LLM extraction works.

TEMPLATE SECTIONS -> EXTRACTION MAPPING:
- "Failure Modes" sections      -> Each becomes an ExtractedLesson
- "Root Cause of Misclassification" -> Becomes the anti_pattern field
- "Recommendations" sections    -> Each becomes an additional lesson
- "Event-Level Corrections"     -> Each row becomes an ExtractedCorrection
-->

# Lessons Learned: [Title]

**Date**: YYYY-MM-DD
**Author**: [Name]
**Scope**: [What was reviewed -- e.g., "Darwin event classification accuracy"]
**Events Reviewed**: [List event IDs, e.g., evt-abc123, evt-def456]

---

## Executive Summary

<!-- 2-3 sentences: What was the overall finding? This becomes the lesson title. -->

---

## Failure Modes

<!-- One section per distinct failure mode discovered. Each becomes a lesson. -->

### Failure Mode 1: [Short Name]

#### What Happened

<!-- Describe the failure from the system's perspective. Keep it environment-agnostic
     where possible -- focus on the TYPE of failure, not specific component names.
     Example: "The system selected a compliance check failure as the root cause
     when an infrastructure failure (image pull back-off) was the more fundamental
     blocking issue." -->

#### Evidence

<!-- Table: for each event, what Darwin classified vs. what was actually wrong.
     Use event IDs so the extractor can cross-reference with Darwin's records. -->

| Event | Darwin's Classification | Actual Root Cause |
|:---|:---|:---|
| evt-... | ... | ... |

#### Root Cause of the Misclassification

<!-- WHY did the system get it wrong? This becomes the anti-pattern.
     Focus on the reasoning flaw, not the specific technology:
     - "Selected the most parseable output instead of the most fundamental failure"
     - "Inspected task-level results but not pod-level events"
     - "Did not check if the resource was already in a terminal state" -->

---

## Recommendations

<!-- Each recommendation becomes a lesson. Write them as patterns:
     "When X happens, the system should Y because Z." -->

### R1: [Short Name] (HIGH/MEDIUM/LOW)

<!-- Describe the correct behavior pattern. This becomes the lesson's "pattern" field.
     Example: "When multiple tasks fail in a pipeline, infrastructure failures
     (image pull, OOM, pod eviction) take precedence over compliance/test failures
     because infrastructure failures prevent tasks from running at all." -->

---

## Event-Level Corrections

<!-- Optional: explicit corrections for specific events.
     These map directly to memory corrections in the extraction. -->

| Event ID | Current Classification | Corrected Root Cause | Corrected Fix Action |
|:---|:---|:---|:---|
| evt-... | ... | ... | ... |
