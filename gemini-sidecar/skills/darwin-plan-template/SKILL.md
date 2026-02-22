---
name: darwin-plan-template
description: Structured plan template for the Architect agent. Use when creating infrastructure or code change plans.
roles: [architect]
---

# Darwin Plan Template

Use this structure for all plans:

```markdown
---
plan: [Action] [Target]
service: [name]
repository: [repo URL]
path: [helm path or source path]
domain: [CLEAR|COMPLICATED|COMPLEX]
risk: [low|medium|high]
steps:
  - id: 1
    agent: [agent]
    mode: [mode]
    summary: [short description]
    status: pending
  - id: 2
    agent: [agent]
    mode: [mode]
    summary: [short description]
    status: pending
---

# Plan: [Action] [Target]

## Reason
[Why this change is needed, based on evidence]

## Steps
1. Specific action with implementation details
2. Specific action with implementation details

## Risk Assessment
- Risk level: [low/medium/high]
- Rollback: [how to undo]

## Verification
- [How will we know the change worked?]
- [What metric or signal confirms success?]
```

The frontmatter YAML header is machine-readable by the Developer team's Manager, QE, and Brain.
The `status` field starts as `pending` and the executing team updates it to `in_progress`, `completed`, or `failed` as they work through the steps.
The Markdown body below the frontmatter contains the full human-readable details for each step.

## Available Agents for Step Assignment

Assign each step in the frontmatter `steps:` array to an agent and mode:

- **sysAdmin** -- Kubernetes and GitOps operations
  - `investigate` -- Read-only: kubectl get, logs, describe
  - `execute` -- GitOps: clone repo, modify values.yaml, commit, push
  - `rollback` -- Git revert, verify ArgoCD sync

- **developer** -- A development TEAM, not a single agent
  - `investigate` -- Developer solo. Read-only: check MR/PR status, code inspection
  - `execute` -- Developer solo. Single write actions: post comment, merge MR, tag release
  - `implement` -- **Full team**: Developer implements, QE verifies quality, Manager reviews and approves.
    The plan is sent as ONE work order to the team. The Manager reads the frontmatter steps and
    orchestrates: Developer works through implementation steps, QE handles verification/test steps.
    You do NOT need separate steps for "implement" and "test" -- the team handles both internally.
  - `test` -- QE solo. Run tests, verify deployments via browser (use only when no code changes needed)

- **architect** -- Planning and review (use sparingly, avoid self-referential loops)
  - `review` -- Code/MR review with severity findings
  - `analyze` -- Information gathering and status report

**How to write steps for the developer team:**

- For code changes that need verification: use `mode: implement` for ALL steps (implementation + testing).
  The team's internal QE handles the verification. Do NOT split into separate implement/test steps.
- For read-only checks (MR status, code inspection): use `mode: investigate`.
- For single Git actions (merge, comment, tag): use `mode: execute`.

For COMPLICATED plans with multiple options, present options WITHOUT step assignments in the frontmatter.
Only the selected option's execution steps get `agent` and `mode` fields.

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
