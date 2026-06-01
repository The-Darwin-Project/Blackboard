<!-- @ai-rules:
1. [Constraint]: Update this file whenever a new doc is added or removed from docs/.
2. [Pattern]: Living docs are actively maintained. Archives are point-in-time artifacts.
3. [Gotcha]: The canonical Release Console contract is in THIS directory, not in the project root docs/.
-->
# Documentation Index

## Living Documentation

Actively maintained reference docs. Updated with each feature release.

| Document | Content |
| --- | --- |
| [architecture.md](architecture.md) | System topology, WebSocket protocol, Cortex/JARVIS, safety model, SDK table, integrations |
| [agents.md](agents.md) | Agent roster (9 specialists), dispatch modes, Headhunter Jira, sidecar CLIs, MCP servers, 26 skills |
| [api-reference.md](api-reference.md) | All REST and WebSocket API endpoints (16 routers) |
| [deployment.md](deployment.md) | Environment variables, Helm deployment, Jira/Cortex/onIce, CI/CD, passive service discovery |
| [brain-skills.md](brain-skills.md) | Progressive skill system, 10 phase dirs (47 skills), tool gating, FRIDAY personality |
| [README.md](README.md) | External service access (ArgoCD, Kargo, RBAC) |
| [Darwin-Release-Console-Integration-Contract.md](Darwin-Release-Console-Integration-Contract.md) | BFF WebSocket contract, trusted-proxy auth, message protocol |

## Autonomous Operation Examples

Real event transcripts demonstrating Darwin's closed-loop capabilities.

| Example | Domain | Turns | Key Demonstration |
| --- | --- | --- | --- |
| [autonomous-remediation-example.md](autonomous-remediation-example.md) | Clear | 21 | Over-provisioned scale-down via GitOps |
| [oom-killed-remediation-example.md](oom-killed-remediation-example.md) | Clear | 10 | OOMKilled recovery with preventive fix |
| [iterative-planning-example.md](iterative-planning-example.md) | Complex | 31 | Three plan revisions with user feedback |
| [autonomous-feature-delivery-example.md](autonomous-feature-delivery-example.md) | Complex | 20+7 | Feature implementation + concurrent infra self-healing |

## Archives (Historical)

Point-in-time artifacts from code reviews, pre-flight checks, and investigations. Useful for audit trails and post-mortems. Not maintained as living docs.

| Directory | Content | Date Range |
| --- | --- | --- |
| `../docs/reviews/` | AI code review and pre-flight review artifacts | Feb-May 2026 |
| `../docs/investigations/` | Event-driven investigation traces | Feb-May 2026 |
| `../docs/lessons-learned/` | Post-incident behavioral notes | Apr-May 2026 |
| `../docs/jira/` | Jira backlog planning artifacts | Apr 2026 |

## Validation Artifact

| Document | Purpose |
| --- | --- |
| [DOCS-INVENTORY-PRE-OVERHAUL.md](DOCS-INVENTORY-PRE-OVERHAUL.md) | Pre-overhaul inventory for validating docs completeness |
