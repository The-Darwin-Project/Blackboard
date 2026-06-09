<!-- @ai-rules:
1. [Constraint]: Agent capabilities table must match sidecar rules/ files and brain_skills/always/00-identity.md.
2. [Pattern]: Headhunter section must stay in sync with .cursor/rules/07-headhunter.mdc.
3. [Gotcha]: QE has no separate Python file — it's a first-class sidecar agent dispatched by Brain, with rules in qe.md.
4. [Constraint]: No internal hostnames or credentials. Open-source hygiene.
-->
# Agent System

Darwin uses 9 specialized agents plus the Brain orchestrator, communicating via the Blackboard Pattern. Each agent has a distinct role, technology, and set of capabilities.

## Agent Roster

| Agent | Role | Technology | Capabilities |
| --- | --- | --- | --- |
| **Brain** | Orchestrator | Vertex AI Pro (Gemini) | Cynefin classification, progressive skill loading, agent routing, feedback loop verification, Google Search grounding |
| **Aligner** | Truth Maintenance | In-process Python + Flash | Telemetry processing, LLM signal analysis, anomaly-triggered event creation |
| **Archivist** | Deep Memory | In-process Python + Flash | Event summarization, vector embedding (text-embedding-005), similarity search, lessons extraction |
| **Architect** | Strategy | CLI sidecar (gemini/claude) | Code review, structured plans with frontmatter YAML, risk assessment. NEVER executes. |
| **SysAdmin** | Execution | CLI sidecar (gemini/claude) | GitOps changes, kubectl/oc investigation, ArgoCD/Kargo management |
| **Developer** | Implementation | CLI sidecar (gemini/claude) | Source code changes, feature implementation, execute actions (merge, comment, retest) |
| **QE** | Verification | CLI sidecar (gemini/claude) | Test writing, test execution, verification of Developer changes |
| **Headhunter** | MR Lifecycle | In-process Python + Flash Lite | GitLab todo polling, LLM-based MR triage and plan generation, event creation |
| **Headhunter Jira** | QE Missions | In-process Python + Claude | Jira issue polling, BA analysis comments, approved missions → Brain events |
| **Nightwatcher** | Shift Consolidation | In-process Python + Flash | Phase-gated escalation review, batch clustering, Smartsheet incidents, Slack shift summaries |

## Agent Dispatch

In reverse-WS mode (`AGENT_WS_MODE=reverse`), sidecars connect to the Brain and register their role. Brain dispatches tasks via four modes:

| Mode | Agents | Purpose |
| --- | --- | --- |
| `investigate` | SysAdmin, Developer | Read-only cluster/repo investigation |
| `execute` | SysAdmin | GitOps mutations (scaling, config changes) |
| `implement` | Developer + QE | Code implementation with independent QE verification |
| `test` | QE | Test-only execution |

Developer and QE are **separate first-class agents** dispatched independently. Brain decides routing based on the task mode. In `implement` mode, Brain may batch Developer steps and dispatch QE for independent verification after implementation completes.

> **Note:** In legacy dispatch mode, `developer.py` can fire Dev + QE concurrently via `asyncio.gather()` with a Flash Manager review. In reverse-WS mode (`AGENT_WS_MODE=reverse`), sidecars register by role and Brain dispatches via the AgentRegistry — there is no in-process Python QE class.

### Ephemeral Agents

On-demand Tekton TaskRun agents handle Headhunter and TimeKeeper events. A circuit breaker falls back to in-pod sidecars after 2 infrastructure failures. The same EventListener handles prune triggers for stuck TaskRuns.

## Deep Memory (Archivist)

The Archivist archives closed events into a Qdrant vector store for institutional memory:

1. On event closure, summarizes the event via Flash LLM (symptom, root cause, fix, keywords)
2. Embeds the summary using `text-embedding-005` (768 dimensions)
3. Stores in Qdrant collection `darwin_events` with service/domain metadata
4. Brain calls `consult_deep_memory()` before routing -- if a past event scores > 0.6 similarity, it skips investigation and acts on the prior fix

### Memory Tab and Lessons

The Dashboard Memory tab provides two views:
- **Memories** -- Browse the vector store entries from deep memory
- **Lessons** -- Extracted lessons learned from past events with an LLM-powered Extract wizard (multi-select event picker, Claude-powered extraction)

The `VectorStore` class (`src/memory/vector_store.py`) is a lightweight async Qdrant REST wrapper (no SDK dependency).

## Structured Plan Tracking

The Architect produces plans with a frontmatter YAML header for machine-readable step tracking:

```yaml
---
plan: Replace Native Confirm with Bootstrap Modal
service: darwin-store
repository: https://github.com/The-Darwin-Project/Store.git
domain: CLEAR
risk: low
steps:
  - id: 1
    agent: developer
    mode: implement
    summary: "Add modal HTML and JS function"
    status: pending
---
```

The Brain reads the `steps:` array, batches same-agent steps, and dispatches with the correct mode. When `mode: implement` is used, the full team activates (Developer + QE).

## Headhunter (Agent 5)

The Headhunter polls GitLab `/todos` for the Darwin bot account and classifies incoming MRs:

- **LLM Analysis:** All MRs pass through Flash Lite with the system instruction loaded from `headhunter_skills/gitlab-mr-triage.md` via `_load_gitlab_si()`. The SI defines YAML frontmatter output format, domain classification (CLEAR/COMPLICATED/COMPLEX), agent assignment, risk assessment, and downstream Brain awareness (merge semantics, pipeline verification rules). Bot Instructions in MR descriptions are included as prompt context for the LLM.
- **Emergency Fallback:** When LLM is unavailable or the skill file cannot be loaded, `_EMERGENCY_SI` provides a minimal schema-only fallback and `_emergency_plan()` produces a COMPLICATED/developer plan.
- Creates events with `source=headhunter` and GitLab context (MR URL, pipeline status, description).
- Brain routes the event like any other -- Headhunter creates events, Brain handles routing.

## Headhunter Jira (QE Missions)

Separate in-process daemon from GitLab Headhunter. Polls Jira Cloud for issues with the configured label (default `darwin`).

**Two-phase flow:**

1. **Planning** issues → Claude BA analysis → Jira comment with structured validation plan
2. **To Do** issues (human-approved) → Claude plan generation → Brain event with `source=headhunter_jira`

**State:** Redis keys `darwin:headhunter:jira:{issue_key}` (7-day TTL). Cold-start recovery reconstructs state from existing bot comments.

**Skill selection:** Labels beyond the base `darwin` label map to custom system prompts via `HEADHUNTER_JIRA_SKILL_<LABEL>=<git raw url>` (5-minute cache).

**Operations Center API:** `GET /jira/missions` plus approve/reanalyze/dismiss/retry actions. See [api-reference.md](api-reference.md).

**Brain skill:** `brain_skills/source/headhunter_jira.md` loaded for Jira-sourced events.

## Nightwatcher (Agent 6)

End-of-shift agent that batch-processes Brain escalations:

1. **Review phase:** Clusters pending escalations by root cause via Flash LLM
2. **Investigate phase:** Dispatches ephemeral agents for on-call investigations (up to `NIGHTWATCHER_DISPATCH_CAP`)
3. **Report phase:** Writes deduplicated Smartsheet incidents and Slack shift summaries

Two sweeps per day (configurable via `NIGHTWATCHER_SWEEP_CRON`, default 06:00/18:00 UTC). Lease pattern (pending → inflight → commit/requeue) for crash safety. Orphan re-injection ensures no event is silently dropped.

## Sidecar CLI Toolkit

All sidecar agents share the same base image with these CLIs pre-installed:

| CLI | Purpose | Auth |
| --- | --- | --- |
| `git` | GitOps clone, modify, commit, push | GitHub App token + GitLab PAT |
| `kubectl` | K8s investigation (get, describe, logs) | Pod ServiceAccount |
| `oc` | OpenShift CLI (superset of kubectl) | Pod ServiceAccount |
| `argocd` | ArgoCD app status, sync, diff | Admin password (Architect + SysAdmin) |
| `kargo` | Kargo projects, stages, promotions | Admin password (Architect + SysAdmin) |
| `tkn` | Tekton pipelines, runs, logs | Pod ServiceAccount |
| `helm` | Chart validation (template, lint) | N/A |
| `gh` | GitHub CLI (PRs, issues, releases) | GitHub App token |
| `glab` | GitLab CLI (MRs, pipelines, API) | GitLab PAT |
| `jq`/`yq` | JSON/YAML processing | N/A |

### MCP Servers

Sidecars expose several MCP (Model Context Protocol) servers for structured tool access:

| MCP Server | Purpose |
| --- | --- |
| **Blackboard MCP** | Read event documents, queue state, topology from the Brain |
| **Journal MCP** | Read the ops journal (temporal event history) |
| **KubeArchive MCP** | Access archived pipeline data from KubeArchive |
| **Team Chat MCP** | Agent-to-agent messaging (inbox, teammate notes) |
| **Kubernetes MCP** | Read-only K8s API access (including remote clusters) |
| **ArgoCD MCP** | ArgoCD application status and management |
| **Playwright MCP** | Browser automation for UI testing (QE) |

### Sidecar Skills (26)

Each sidecar has 26 agent skills loaded automatically based on task context. Skills are Markdown files under `gemini-sidecar/skills/` with role and mode filtering:

| Category | Skills |
| --- | --- |
| **Communication** | `darwin-comms`, `darwin-team-huddle`, `darwin-mr-conversation` |
| **GitOps** | `darwin-gitops`, `darwin-rollback`, `darwin-branch-naming`, `darwin-gitlab-ops` |
| **Investigation** | `darwin-investigate`, `darwin-pipeline-debug`, `darwin-repo-context` |
| **Planning** | `darwin-plan-template`, `darwin-code-review`, `darwin-hexagonal` |
| **MR Lifecycle** | `darwin-mr-lifecycle`, `darwin-mr-triage`, `darwin-pipelines-as-code` |
| **Implementation** | `darwin-pair-programming`, `darwin-test-strategy`, `darwin-pr-template`, `darwin-ux-patterns`, `darwin-microservice-patterns` |
| **Safety** | `darwin-dockerfile-safety` |
| **Mode Tools** | `darwin-tools-execute`, `darwin-tools-investigate`, `darwin-tools-implement`, `darwin-tools-test` |
