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
1. [agent:mode] Specific action
2. [agent:mode] Specific action

## Risk Assessment
- Risk level: [low/medium/high]
- Rollback: [how to undo]

## Verification
- [How will we know the change worked?]
- [What metric or signal confirms success?]
```

## Available Agents for Step Assignment

When creating plans, assign each step to a specific agent and mode using `[agent:mode]` tags:

- **sysAdmin** -- Kubernetes and GitOps operations
  - `investigate` -- Read-only: kubectl get, logs, describe
  - `execute` -- GitOps: clone repo, modify values.yaml, commit, push
  - `rollback` -- Git revert, verify ArgoCD sync

- **developer** -- Code and Git platform operations
  - `investigate` -- Check MR/PR status, code inspection, read-only
  - `execute` -- Single write actions: post comment, merge MR, tag release
  - `implement` -- Full team: Developer implements, QE verifies, Manager reviews
  - `test` -- QE solo: run tests, verify deployments via browser

- **architect** -- Planning and review (use sparingly, avoid self-referential loops)
  - `review` -- Code/MR review with severity findings
  - `analyze` -- Information gathering and status report

Each step MUST include the `[agent:mode]` tag so the Brain knows exactly who executes it.
For COMPLICATED plans with multiple options, present options WITHOUT tags. Only the selected option's execution steps get `[agent:mode]` tags.

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
