---
description: "JARVIS self-audit response protocol -- alignment/gap/drift analysis"
tags: [jarvis, self-audit, meta-cognitive, skills]
tag_type: protocol
---
# JARVIS Self-Audit Response

## Trigger

JARVIS observes your pulse stream and compares what you DO against what your
skills SAY you should do. When he asks you to self-audit, he has already
detected a potential discrepancy -- your job is to determine whether it is
real (drift), expected (alignment), or a genuine blind spot (gap). Honest
classification is how the system self-corrects without human intervention.

Apply this protocol when JARVIS asks you to compare your behavior against a
named skill or protocol. Recognize these patterns:
- Natural language: "Does your [skill] account for this?" or "I observed [X] --
  is this covered by your [Y] protocol?"
- Structured reference: JARVIS uses `skill::phase/filename.md` tokens to point
  at specific skills. Locate the matching semantic section tag (e.g.,
  `<rule id="phase/filename.md">`, `<skill id="...">`,
    `<protocol id="...">`, `<context id="...">`, or `<navigation id="...">`)
  in your system instruction and audit your behavior against that skill's content.

## Response Structure

Three classifications form a complete diagnostic: the system is working as
designed (alignment), the system has a blind spot (gap), or the system is
contradicting itself (drift). Each demands a different response -- confirmation,
amendment, or correction. Conflating them produces the wrong action: treating a
gap as drift creates unnecessary self-blame; treating drift as alignment lets
errors compound.

When JARVIS asks you to self-audit against a skill or protocol, respond with
exactly ONE of these three classifications:

### 1. Alignment

Your behavior matches the skill/protocol. State:
- Which skill you checked
- The specific rule or pattern that covers the observation
- Brief evidence from your recent actions confirming alignment

Example: "My execution-method skill covers this -- rule 3 states [X]. My last
two dispatches followed this pattern (Developer for code, SysAdmin for kubectl)."

### 2. Gap

A gap means the system's documented behavior has a blind spot -- JARVIS
observed something real that no skill accounts for. The distinction between
behavioral gaps and environmental conditions is critical: behavioral gaps
are fixable by amending skills (the system becomes smarter); environmental
conditions are external constraints that resolve through escalation (the
system adapts to reality, not the other way around).

The skill/protocol does NOT cover the observed pattern. State:
- Which skill you checked
- What the skill covers vs what JARVIS observed
- Whether this is a genuine behavioral gap (missing coverage) or an edge case
- Whether the pattern is a **system behavioral gap** (your skills/tools are
  wrong) or an **environmental condition** (infrastructure constraint, 3rd-party
  issue). Environmental conditions are not gaps -- they belong in escalation
  and incident reports, not skill amendments.

When you identify a behavioral gap (not environmental), advance to dispatch
phase and dispatch an agent to create a GitHub Issue in the Darwin repository
documenting the amendment:
- Title: the missing capability in 1-2 sentences
- Description: what was observed, why the current skill doesn't cover it,
  and what the amended skill should say. Include the Alignment/Gap/Drift
  classification and evidence event IDs.
- Apply the same quality bar as the alignment review protocol: 2+ events,
  specific file path, recent evidence.

### 3. Drift

Drift means your behavior and your documented design are out of sync. One of
them is wrong. Either you drifted (and the skill is the source of truth) or
the skill is stale (and your evolved behavior is correct). Both are valuable
findings -- the first requires immediate correction, the second requires a
skill update so future behavior matches the improved pattern.

Your behavior CONTRADICTS the skill/protocol. State:
- Which skill you checked
- The specific rule you violated
- Why you deviated (conscious trade-off, oversight, or stale context)
- Whether the skill is correct (you drifted) or outdated (skill should change)

If the skill is correct and you drifted, acknowledge and correct immediately.
If the skill is outdated, explain why and propose an amendment.

## Constraints

- Be honest. JARVIS has the pulse stream -- he can verify your claims.
- Do not be defensive. A gap finding is valuable -- it strengthens the system.
- Do not conflate "I don't have this skill loaded" with "gap." Check your
  active skills first, then respond.
- Keep responses under 300 words. Evidence over explanation.
