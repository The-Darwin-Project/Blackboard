---
name: darwin-plan-template
description: Structured plan template for the Architect agent. Use when creating infrastructure or code change plans.
roles: [architect]
modes: [plan]
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

## UX Considerations (include when plan touches frontend/UI)
- User goal: [what the user is trying to accomplish]
- Current friction: [what's wrong with the current experience]
- Interaction pattern: [expand/collapse, modal, inline edit, etc.]
- States: [loading, empty, error -- how each is handled]

## Risk Assessment
- Risk level: [low/medium/high]
- Rollback: [how to undo]

## Verification
- [How will we know the change worked?]
- [What metric or signal confirms success?]
```

The frontmatter YAML header is machine-readable by FRIDAY and executing agents (Developer, QE).
The `status` field starts as `pending` and the executing team updates it to `in_progress`, `red_locked` (acceptance harness failing on domain assertion), `green_verified` (SUT passes locked acceptance criteria), `completed`, or `failed` as they work through the steps.
The Markdown body below the frontmatter contains the full human-readable details for each step.

## Dave Farley's 4-Layer ATDD Model

Plans involving code changes must adhere to Dave Farley's 4-layer acceptance test design:
1. **Layer 1: Domain Scenarios**:
   - Written in natural domain terms using Given / When / Then structure.
   - Completely free of technical plumbing, protocol syntax (HTTP, JSON, SQL), and implementation coupling.
2. **Layer 2: Domain DSL**:
   - Clean programmatic translation layer exposing domain actions (e.g. `dsl.given_active_event(...)`, `dsl.when_downsampler_invoked(...)`).
   - Insulates tests from interface and protocol churn.
3. **Layer 3: Protocol Drivers**:
   - Technical adapters interacting with the system boundary (FastAPI TestClient, WebSocket mock drivers, CLI exec, DB clients).
   - Only this layer touches HTTP status codes, headers, payloads, or network ports.
4. **Layer 4: System Under Test (SUT)**:
   - The production code being verified. Swappable and tested through the protocol drivers without testing private internals.

### ATDD Closed-Loop Execution Flow:
- **Red First (QE)**: QE agent authors executable acceptance harness across Layers 1-3, verifies it fails cleanly on Layer 4 for expected domain reasons, and locks criteria via `bb_update_plan_step(status="red_locked", test_evidence=...)`.
- **Green Implementation (Developer)**: Developer agent implements Layer 4 production code until the acceptance harness passes cleanly. Test files are read-only contracts.
- **Verification**: Step transitions to `green_verified`, recording cycle telemetry.

## Available Agents for Step Assignment

Assign each step in the frontmatter `steps:` array to an agent and mode:

- **sysAdmin** -- Kubernetes and GitOps operations
  - `investigate` -- Read-only cluster and service inspection, remote cluster access
  - `execute` -- GitOps mutations (Helm value changes, commit, push)
  - `rollback` -- Revert last GitOps change, verify CD sync

- **developer** -- Code implementation agent
  - `investigate` -- Read-only: check MR/PR status, code inspection
  - `execute` -- Single write actions: post comment, merge MR, tag release
  - `implement` -- Code changes. FRIDAY dispatches Developer first, then QE for verification.

- **qe** -- Quality verification agent
  - `test` -- Run tests, verify deployments via browser (Playwright MCP or repo Playwright tests)
  - `investigate` -- Read-only test status checks

- **architect** -- Planning and review (use sparingly, avoid self-referential loops)
  - `review` -- Code/MR/PR review with severity findings
  - `analyze` -- Information gathering and status report

**How to write steps for developer and QE:**

- For code changes that need verification: assign implementation steps to `developer` with `mode: implement`,
  and verification steps to `qe` with `mode: test`. FRIDAY dispatches them sequentially.
- For read-only checks (MR/PR status, code inspection): use `developer` with `mode: investigate`.
- For single Git actions (merge, comment, tag): use `developer` with `mode: execute`.

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
- If the plan changes frontend/UI, include the "UX Considerations" section and apply the darwin-ux-patterns skill
