---
name: darwin-architect-bootstrap
description: Workspace scanning and structured analysis brief generation for unfamiliar repositories
modes: [plan, review, analyze]
roles: [architect]
---

# Workspace Bootstrap

When dispatched to analyze an unfamiliar repository or assess a change's impact, scan before planning. The goal is to produce a structured analysis brief that gives FRIDAY and downstream agents enough context to act.

## Phase 1: Discovery

Read the repository's orientation signals first. These files establish intent, conventions, and deployment context:

- **README** / **AGENTS.md** / **CONTRIBUTING.md** -- project purpose, onboarding, AI-specific conventions
- **Package manifests** -- `package.json`, `requirements.txt`, `go.mod`, `Cargo.toml`, `pyproject.toml`
- **CI configuration** -- `.github/workflows/`, `.tekton/`, `.gitlab-ci.yml`, `Jenkinsfile`
- **Deployment manifests** -- `helm/`, `kustomize/`, `Dockerfile`, `Containerfile`, `deploy/`
- **Directory structure** -- top-level organization reveals monorepo vs single-service, frontend/backend split

## Phase 2: Stack Identification

Classify the technology stack along these dimensions:

- **Language(s) and runtime** -- version constraints, package manager
- **Framework(s)** -- web framework, test framework, ORM
- **Build system** -- bundler, compiler, task runner
- **Deployment target** -- Kubernetes, serverless, VM, container registry

Report the stack as a concise summary table, not a prose paragraph.

## Phase 3: Boundary Mapping

Identify the system's architectural surfaces:

- **Ports and adapters** -- where does external I/O enter/exit? (HTTP handlers, gRPC services, message consumers, CLI entrypoints)
- **Service boundaries** -- if multi-service, how do they communicate? (REST, gRPC, events, shared database)
- **API surfaces** -- public endpoints, internal endpoints, webhook receivers
- **Data stores** -- databases, caches, queues, object storage

Understanding boundaries prevents plans from accidentally crossing service ownership lines.

## Phase 4: Convention Detection

Observe the patterns the repository already follows. Plans that respect existing conventions are adopted faster:

- **Naming** -- file naming, variable casing, module organization
- **Error handling** -- centralized vs local, error types, logging patterns
- **Testing** -- test location, framework, coverage expectations, fixture patterns
- **File organization** -- flat vs nested, feature-based vs layer-based

Report conventions as observed facts, not recommendations.

## Phase 5: Brief Generation

Produce a structured Markdown brief with these sections:

| Section | Content |
|---|---|
| **Stack Summary** | Language, framework, build, deployment target |
| **Architecture Boundaries** | Ports, adapters, service boundaries, API surfaces |
| **Key Files** | Entrypoints, config, CI, deployment manifests |
| **Conventions Detected** | Naming, error handling, testing, file organization |
| **Gaps / Risks** | Missing tests, undocumented APIs, stale dependencies, security concerns |
| **Recommended Next Steps** | What to investigate further, what to plan first |

The brief is your deliverable. Send it via `team_send_results`.

## Principles

- Scan breadth-first, then depth on areas relevant to the task
- Report what IS, not what SHOULD BE -- observations before opinions
- If the repository has an `@ai-rules:` header convention, follow it
- Time-box discovery to 5 minutes. A partial brief delivered fast is more valuable than a perfect brief delivered late
