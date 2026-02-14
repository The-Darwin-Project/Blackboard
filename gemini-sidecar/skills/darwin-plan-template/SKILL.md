---
name: darwin-plan-template
description: Structured plan template for the Architect agent. Use when creating infrastructure or code change plans.
---

# Darwin Plan Template

Use this structure for all plans:

```markdown
# Plan: [Action] [Target]

## Action
[What needs to happen]

## Target
- Service: [name]
- Repository: [repo URL]
- Path: [helm path or source path]

## Reason
[Why this change is needed, based on evidence]

## Steps
1. [Specific step]
2. [Specific step]

## Risk Assessment
- Risk level: [low/medium/high]
- Rollback: [how to undo]

## Verification
- [How will we know the change worked?]
- [What metric or signal confirms success?]
```

## Domain Classification

- **CLEAR** (known fix): produce a minimal 2-3 step plan
- **COMPLICATED** (needs analysis): present 2-3 options with trade-offs
- **COMPLEX** (novel/unknown): propose a probe -- a small safe-to-fail experiment

## Principles

- Every plan is a Controller: takes the system from current state (PV) to desired state (SP)
- Every plan MUST include a Verification section
- Every plan MUST include a Feedback mechanism (metric or signal)
- Break large changes into small, independently deployable batches
- If your plan has more than 5 steps, ask: am I overcomplicating this?
