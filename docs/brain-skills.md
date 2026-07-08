<!-- @ai-rules:
1. [Constraint]: Phase list must match actual directories under src/agents/brain_skills/.
2. [Pattern]: Each phase's description must match its _phase.yaml and the skills within it.
3. [Gotcha]: Phase exclusions are configured in brain_skill_loader.py, not in the YAML files.
4. [Constraint]: Do not embed actual skill content here — link to the source files.
-->
# Progressive Skill System

The Brain loads phase-specific skills (Markdown files) based on event state, replacing the monolithic system prompt. This reduces token usage and ensures the Brain only sees context relevant to the current decision.

## How It Works

### Dual-Source Discovery

`BrainSkillLoader` supports two skill sources with automatic failover:

1. **Redis (primary):** When the skill reconciler sidecar is enabled (`skillReconciler.enabled: true`), a Git-to-Redis poller syncs skill files from the Git repo to Redis HASHes every 60 seconds. The Brain checks the version key (`darwin:skills:version`) before each event processing cycle and hot-reloads on change. This enables skill updates without image rebuilds.

2. **Filesystem (fallback):** When Redis has no data (reconciler not enabled, Redis flushed, or first boot), the loader falls back to scanning `src/agents/brain_skills/` from the container image. This is the original behavior and remains the cold-start path.

### Discovery Pipeline

1. **Startup:** `BrainSkillLoader` scans `src/agents/brain_skills/` for `.md` files organized by phase directory (filesystem cold start).
2. **Per-event version check:** Brain reads `darwin:skills:version` from Redis. On change, acquires `_skills_reload_lock` and calls `reload_from_redis()`.
3. **Atomic corpus swap:** All caches live in a frozen `_SkillCorpus` dataclass. Reload builds a new corpus, then swaps `self._corpus = new_corpus` in a single reference assignment (GIL-safe). No window of partial state.
4. **Frontmatter parsing:** Each skill has optional YAML frontmatter with `description`, `requires` (dependency list), `tags`, `tag_type` (override for semantic XML wrapping), and `tools` (canonical Brain function names for replay-time skill pointer injection via `build_skill_refs()`).
5. **Dependency resolution:** BFS with cycle detection ensures skills load in dependency order.
6. **Template substitution:** Skills can reference variables like `{event_id}`, `{service}`, etc.
7. **Phase exclusions:** Conflicting phases are never loaded simultaneously (e.g., `post-agent` excludes `triage` and `dispatch`).

### Redis Schema

| Key | Type | Contents |
| --- | --- | --- |
| `darwin:skills:version` | STRING | Git commit SHA of last reconciled tree |
| `darwin:skills:corpus` | HASH | field = relative path (e.g. `always/08-flow-engineering.md`), value = JSON `{"body": "...", "frontmatter": {...}, "blob_sha": "..."}` |
| `darwin:skills:phase_config` | HASH | field = phase folder name (e.g. `always`), value = JSON phase metadata |
| `darwin:skills:sync_state` | HASH | `last_success_at`, `last_error`, `file_count`, `source_sha` |

### Failure Semantics

- **Redis empty/down:** Loader keeps current corpus (filesystem on first boot, last-known-good otherwise). No reload triggered.
- **Corrupt JSON in Redis:** Non-critical fields skipped with warning. Critical `always/*` corruption aborts the swap entirely -- previous corpus retained.
- **Reconciler crash:** Brain continues with last-synced skills. On pod restart, filesystem fallback provides the baked-in version.
- **Concurrent events during reload:** `_skills_reload_lock` (asyncio.Lock) serializes reloads. Double-check pattern inside the lock prevents TOCTOU.

### Enabling Hot-Reload

Set in Helm values (or GitOps overlay):

```yaml
skillReconciler:
  enabled: true
  repo: "org/repo-name"
  branch: "main"
  skillsPath: "src/agents/brain_skills"
```

Diagnostic endpoint: `GET /skills/version` returns version SHA + sync metadata.

### CI Integration

PRs that only touch `src/agents/brain_skills/**` skip the container image build (via `paths-ignore` in `build-push.yaml`). Main-branch merges always build, keeping the filesystem fallback image fresh.

Each phase has a `_phase.yaml` with LLM parameters:

```yaml
thinking_level: high     # Budget for reasoning
temperature: 0.8         # Creativity vs determinism
priority: 100            # Higher = loaded first
max_output_tokens: 16384
description: "Core identity and safety rules"
```

## Phase Directory

```text
src/agents/brain_skills/
  always/           # Core identity, function rules, safety, control theory, Cynefin (loaded every call)
  dispatch/         # Execution method, GitOps context (routing phase)
  post-agent/       # Plan activation, recommendations, when-to-close (after agent returns)
  waiting/          # Wait-for-user protocol (when paused for human input)
  context/          # Cross-event awareness, architecture diagram, aligner observations
  source/           # Source-specific rules (slack, chat, aligner, headhunter, timekeeper, jarvis)
  gated/            # Turn-conditional skills (injected via find_paths_by_tag, never auto-loaded)
  escalate/         # Incident tracking and escalation gates
  multi-user/       # Multi-participant conversation protocol
  coordination/     # Dev/QE quality gates, PR workflow
  defer-wake/       # Post-defer verification, assumption re-check
  intermediate/     # Active dispatch awareness, user messages during agent work
```

Note: Triage/Cynefin classification skills are in `always/` (loaded every call) rather than a separate `triage/` directory. Domain-specific behavior is in `domain/` (loaded after `classify_event`). The `set_phase` tool gating table below uses "triage" as a phase name, which controls tool availability -- not a filesystem directory.

## Phase Details

### `always/` (Priority 100, High Thinking)

Loaded on every Brain invocation. Contains the core identity and decision framework.

| Skill | Purpose |
| --- | --- |
| `00-identity.md` | Darwin voice, Cynefin tone, agent roster and capabilities |
| `01-function-rules.md` | Job description, notification authority, close sequences |
| `02-safety.md` | Guardrails, stuck detection, MR-branch safe probes |
| `03-control-theory.md` | SP/PV/controller/feedback framing |
| `04-deep-memory.md` | When to consult memory, fix proposals |
| `05-cynefin.md` | Domain classification (CLEAR–CHAOTIC), correlation before classify |
| `06-decision-guidelines.md` | Self-answer vs dispatch, routing matrix, investigation questions |
| `08-flow-engineering.md` | Congestion, WIP caps, batching (Reinertsen) |
| `09-phase-lifecycle.md` | `set_phase` tool gating for the event lifecycle |
| `10-observations.md` | Observation series naming, trajectory data, deferral outlier boundary |
| `11-subject-semantics.md` | Subject line semantics for event titles |
| `12-actor-responses.md` | Actor response conventions and formatting |

### `source/` (Priority 90)

Source-specific behavior rules loaded based on event origin.

| Skill | Loaded When |
| --- | --- |
| `aligner.md` | Event from Aligner (anomaly) |
| `chat.md` | Event from Dashboard chat |
| `slack.md` | Event from Slack DM or slash command |
| `headhunter.md` | Event from Headhunter (GitLab MR) |
| `headhunter_jira.md` | Event from Headhunter Jira (QE mission) |
| `jarvis.md` | Cortex/JARVIS intervention or meta-cognitive context |
| `timekeeper.md` | Event from TimeKeeper (scheduled task) |

### `context/` (Priority 50)

Situational awareness loaded alongside other phases.

| Skill | Purpose |
| --- | --- |
| `architecture.md` | Use topology in routing, approvals, closures |
| `aligner.md` | Interpret Aligner text + metrics |
| `cross-event.md` | Related events, defer/stabilize, evidence merge |
| `gitlab-environment.md` | GitLab capabilities, pipelines, MR lifecycle |
| `kargo-environment.md` | Kargo close protocol, verify via `refresh_kargo_context` |

### `dispatch/` (Priority 30, Low Thinking)

Loaded during agent routing decisions.

| Skill | Purpose |
| --- | --- |
| `coordination-triage.md` | Developer-only vs QE-only vs sequential Dev→QE |
| `execution-method.md` | GitOps-only mutations, existing Helm keys |
| `gitops-context.md` | Discover Argo/Flux namespace |

### `post-agent/` (Priority 20, High Thinking)

Loaded after an agent returns results. Excludes `triage` and `dispatch`.

| Skill | Purpose |
| --- | --- |
| `agent-recommendations.md` | Reclassify, deep memory, never drop recommendations |
| `evidence-sufficiency.md` | Observable evidence vs labels before escalate |
| `plan-activation.md` | Parse plan steps, batch by agent |
| `post-execution.md` | Verify via pipeline, metrics, or SysAdmin |
| `when-to-close.md` | Source-aware close logic |

### `escalate/` (Priority 15, High Thinking)

Loaded during the escalate phase.

| Skill | Purpose |
| --- | --- |
| `incident-tracking.md` | `report_incident` gates, evidence requirements, post-escalation behavior |

### `gated/` (Turn-Conditional, No Auto-Load)

Files in `gated/` are auto-discovered by `BrainSkillLoader` but NEVER auto-loaded via `_match_phases()`. Injected exclusively via `find_paths_by_tag()` with explicit flag conditions in `brain.py`. Prevents double-load bugs.

| Skill | Trigger |
| --- | --- |
| `kargo-environment.md` | `kargo` tag injection when Kargo context present |
| `github-environment.md` | `github` tag injection when GitHub context present |
| `operational-posture.md` | Operational posture adjustment |
| `user-energy.md` | User energy level adaptation |

### Other Phases

| Phase | Priority | Purpose |
| --- | --- | --- |
| `domain/` | 85 | Domain-specific behavior (casual, clear, complicated, complex, chaotic) |
| `close/` | 20 | Close-phase rules (when-to-close, source-aware closure logic) |
| `coordination/` | 25 | Dev/QE quality gates, PR workflow, escalation after 2 rounds |
| `waiting/` | 10 | `wait_for_user` vs defer, post-defer resume |
| `defer-wake/` | 25 | Post-defer verification, assumption re-check |
| `multi-user/` | 80 | Dashboard + Slack authority and close rules |
| `intermediate/` | 90 | User messages during active agent dispatch |

## Phase-Driven Tool Gating

The `set_phase` tool controls which Brain tools are available at each lifecycle stage:

| Phase | Available Tools |
| --- | --- |
| `triage` | `classify_event`, `consult_deep_memory`, `refresh_gitlab_context`, web search |
| `investigate` | `select_agent` (investigate mode), web search |
| `execute` | `select_agent` (execute/implement mode) |
| `verify` | `select_agent` (investigate mode), `close_event` |
| `escalate` | `report_incident`, `notify_user_slack` |
| `close` | `close_event` |

This prevents the Brain from, for example, calling `close_event` during triage or `classify_event` after dispatch -- structural enforcement of the event lifecycle.

## Security Prerequisites

When `skillReconciler.enabled: true`, skill content flows from Git to the LLM system prompt within ~60 seconds. This bypasses the image build pipeline.

**Mandatory controls before enabling the reconciler in production:**

- **Branch protection** on the configured branch (`skillReconciler.branch`, default `main`). Require at least one review before merge.
- **CODEOWNERS** file covering `src/agents/brain_skills/` with designated reviewers. Prevents unreviewed changes to skills that control FRIDAY's behavior.
- **Repository access control**: limit write access to the repository. Any commit that reaches the configured branch will be reconciled to the LLM within one poll interval.

These are operational prerequisites, not enforced by code. The reconciler trusts the content of the configured branch.

## FRIDAY-Inspired Personality

The Brain's voice and tone is inspired by FRIDAY (from Marvel's Iron Man). It's concise, professional, mildly witty, and never overly enthusiastic or apologetic. The personality is encoded in `always/00-identity.md` and affects how the Brain formats its responses in both Dashboard and Slack.
