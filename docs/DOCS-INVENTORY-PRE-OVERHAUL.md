<!-- @ai-rules:
1. [Constraint]: This file is a validation artifact for the docs overhaul. Do NOT delete until post-overhaul review confirms all content is preserved.
2. [Pattern]: Each section maps 1:1 to the original README.md structure. Check marks indicate content migrated to new location.
3. [Gotcha]: "Undocumented features" section lists features that exist in code but were NOT in the original README. These must be ADDED during the overhaul.
-->
# Pre-Overhaul Documentation Inventory

**Date:** 2026-05-05
**Git HEAD:** 32cbaf0
**Purpose:** Captures every documented section, feature, and API endpoint before the docs overhaul so we can validate nothing is lost post-refactoring.

---

## 1. BlackBoard/README.md (487 lines) — Sections

| # | Section | Lines | Target Doc |
|---|---------|-------|------------|
| 1 | Title + badges + contributing link | 1-8 | README.md (overview) |
| 2 | Architecture (mermaid diagram) | 10-48 | docs/architecture.md |
| 3 | Reversed WebSocket Architecture | 50-61 | docs/architecture.md |
| 4 | WebSocket Message Protocol (Reverse Mode) | 63-76 | docs/architecture.md |
| 5 | Agents table (8 agents) | 77-88 | docs/agents.md |
| 6 | Agent Dispatch (Reverse WebSocket) | 90-97 | docs/agents.md |
| 7 | Progressive Skill System | 98-117 | docs/brain-skills.md |
| 8 | Structured Plan Tracking | 118-143 | docs/agents.md |
| 9 | Slack Integration | 144-156 | docs/architecture.md |
| 10 | Deep Memory (Archivist) | 157-167 | docs/agents.md |
| 11 | Sidecar CLI Toolkit | 168-186 | docs/agents.md |
| 12 | Key Features (22 bullet points) | 187-211 | README.md (overview) |
| 13 | Autonomous Remediation Examples | 213-216 | README.md (overview) |
| 14 | SDK table | 218-231 | docs/architecture.md |
| 15 | Quick Start (Local Development) | 233-251 | docs/deployment.md |
| 16 | Quick Start (Helm Deployment) | 253-262 | docs/deployment.md |
| 17 | API Endpoints — Health & Info | 264-272 | docs/api-reference.md |
| 18 | API Endpoints — WebSocket | 273-283 | docs/api-reference.md |
| 19 | API Endpoints — Conversation Queue | 285-293 | docs/api-reference.md |
| 20 | API Endpoints — TimeKeeper | 295-305 | docs/api-reference.md |
| 21 | API Endpoints — Shifts | 307-313 | docs/api-reference.md |
| 22 | API Endpoints — Chat | 315-324 | docs/api-reference.md |
| 23 | API Endpoints — Feedback | 326-331 | docs/api-reference.md |
| 24 | API Endpoints — Telemetry | 333-344 | docs/api-reference.md |
| 25 | API Endpoints — Topology & Metrics | 346-355 | docs/api-reference.md |
| 26 | Configuration — Environment Variables | 357-391 | docs/deployment.md |
| 27 | Safety — Air Gap table | 393-410 | docs/architecture.md |
| 28 | Project Structure tree | 412-478 | README.md (overview) |
| 29 | Contributing + License | 480-487 | README.md (overview) |

## 2. Features Currently Documented in README

- Progressive Skill Loading (phase-specific Markdown skills)
- Conversation Queue (Redis shared event documents)
- WebSocket Communication (bidirectional streaming)
- Cynefin Decision Framework (Clear/Complicated/Complex/Chaotic)
- Deep Memory (Qdrant vector store)
- Structured Plan Tracking (frontmatter YAML)
- Cross-Platform Chat (Dashboard + Slack)
- LLM Signal Analysis (Aligner + Flash)
- GitOps-Only Mutations (kubectl read-only)
- Agent Recommendation Injection
- Event Dedup + Defer
- Closed-Loop Verification
- ArgoCD/Kargo Integration
- Cross-Event Correlation
- Multimodal Chat (image upload)
- Agent Streaming Cards
- AI Transparency (Slack + Dashboard tagging)
- User Feedback (POST /feedback)
- Auth Scaffolding (Dex OIDC)
- TimeKeeper (scheduled tasks)
- Ephemeral Agents (Tekton TaskRun)
- darwin.io Annotations (passive discovery)
- Nightwatcher Shift Consolidation

## 3. Features NOT Documented in README (Must Add)

| Feature | Commits | Target Doc |
|---------|---------|------------|
| Reports / Event History API + UI | f350b2a, cecc63a, 32cbaf0 | api-reference.md + README overview |
| Google Search Grounding (web search in triage/investigate) | 5063d50, 1881733, ccd245e | architecture.md + deployment.md (env var) |
| L4 Autonomous AI — Propose and Prompt workflow | 45cfe02 | architecture.md |
| Release Console BFF trusted-proxy auth | 7ca8efe, dbebc40 | architecture.md + deployment.md |
| Memory tab (Memories + Lessons views + Extract wizard) | 86b822d, c174cf4, 2cd08d8, b838de3 | agents.md (Archivist) |
| Phase-driven tool gating (set_phase) | 3802d85, 1b06d04 | brain-skills.md |
| KargoObserver (promotion failure detection) | bc4aead | architecture.md + deployment.md |
| Blackboard + Journal MCP servers | 6aa67bb, 6ec14a8 | agents.md (sidecars) |
| KubeArchive MCP server | bd99a73 | agents.md (sidecars) |
| Mode-aware MCP tool filtering | a071d85 | agents.md (sidecars) |
| FRIDAY-inspired Brain personality | 9cd82b9 | brain-skills.md |
| Ops Center dashboard redesign (XProtect-inspired) | 3f04180 | README overview |
| Adaptive message_agent (busy→inbox, idle→dispatch) | 3785acb | architecture.md |
| Headhunter agent (GitLab MR lifecycle) | full agent | agents.md |

## 4. Other Documentation Files — Status

| File | Status | Action |
|------|--------|--------|
| BlackBoard/helm/README.md | Mostly current | Update integration table (Step 5) |
| BlackBoard/ui/README.md | Vite boilerplate | Replace entirely (Step 4) |
| BlackBoard/CONTRIBUTING.md | Mostly current | Add sidecar build + test details (Step 7) |
| BlackBoard/SECURITY.md | Current | No changes needed |
| BlackBoard/CODE_OF_CONDUCT.md | Current | No changes needed |
| BlackBoard/docs/README.md | Current | No changes needed (ArgoCD/Kargo access) |
| docs/Darwin-Release-Console-Integration-Contract.md | Duplicate | Remove — keep BlackBoard/docs/ canonical |
| docs/autonomous-remediation-example.md | Current | Link from new docs |
| docs/oom-killed-remediation-example.md | Current | Link from new docs |
| docs/iterative-planning-example.md | Current | Link from new docs |
| docs/autonomous-feature-delivery-example.md | Current | Link from new docs |

## 5. API Endpoints — Complete Inventory

### Currently Documented
- GET /health, GET /info, GET /api/agents
- WS /ws, WS /agent/ws
- GET /queue/active, GET /queue/{event_id}, POST /queue/{event_id}/approve, POST /queue/{event_id}/reject, GET /queue/closed/list
- POST/GET/PUT/DELETE/PATCH /api/timekeeper/*, POST /api/timekeeper/refine
- GET /shifts/list, GET /shifts/{date}/{window}, GET /shifts/current
- POST /chat/
- POST /feedback
- POST /telemetry/ (deprecated)
- GET /topology/, GET /topology/graph, GET /topology/mermaid
- GET /metrics/{service}, GET /metrics/chart
- GET /events/

### NOT Documented (Must Add)
- GET /reports/list, GET /reports/search, GET /reports/{event_id}
- GET /api/journal
- GET /api/kargo/stages
- GET /events/{id}/document
- GET /queue/{event_id}/turns
- GET /telemetry/llm (quota stats)
- GET /incidents/list

## 6. Environment Variables — Complete Inventory

### Currently Documented (30 vars in README)
REDIS_HOST, REDIS_PASSWORD, GCP_PROJECT, GCP_LOCATION, LLM_MODEL_BRAIN, LLM_MODEL_MANAGER, LLM_MODEL_ALIGNER, LLM_MODEL_ARCHIVIST, ARCHITECT_SIDECAR_URL, SYSADMIN_SIDECAR_URL, DEVELOPER_SIDECAR_URL, QDRANT_URL, SLACK_BOT_TOKEN, SLACK_APP_TOKEN, DEX_ENABLED, AGENT_WS_MODE, BRAIN_PROGRESSIVE_SKILLS, TIMEKEEPER_ENABLED, TIMEKEEPER_POLL_INTERVAL, TIMEKEEPER_MAX_PER_USER, TIMEKEEPER_MAX_TOTAL, LLM_MODEL_TIMEKEEPER, NIGHTWATCHER_ENABLED, NIGHTWATCHER_SWEEP_CRON, NIGHTWATCHER_MIN_PENDING, NIGHTWATCHER_DISPATCH_CAP, LLM_MODEL_NIGHTWATCHER, LLM_TEMPERATURE_NIGHTWATCHER, DEBUG

### NOT Documented (Must Add)
- BRAIN_GOOGLE_SEARCH_ENABLED
- TRUSTED_PROXY_ENABLED, TRUSTED_PROXY_SECRET
- HEADHUNTER_ENABLED, HEADHUNTER_POLL_INTERVAL, GITLAB_HOST, LLM_MODEL_HEADHUNTER
- KARGO_OBSERVER_ENABLED
- K8S_OBSERVER_ENABLED, K8S_OBSERVER_INTERVAL
- LLM_TPM_LIMIT
- QE_SIDECAR_URL
- TEKTON_EVENTLISTENER_URL

---

**Validation:** After the overhaul, grep each feature/endpoint/env-var name against the new docs to confirm coverage. Any item above not found in the new docs is a regression.

---

## Post-Overhaul Validation (2026-06-01)

**Git HEAD at validation:** current `main` (post-inventory)

| Inventory Section | Status | Notes |
| --- | --- | --- |
| §1 README sections → docs/* | Done | Split complete; README under 200 lines |
| §3 Features NOT documented | Done | Cortex/JARVIS, Jira missions, on_ice, api-reference gaps addressed |
| §5 API endpoints NOT documented | Done | See `docs/api-reference.md` — Jira, Cortex, on_ice, topology/services, journal/{service}, lessons PATCH |
| §6 Env vars NOT documented | Done | See `docs/deployment.md` — Jira, onIce, idleTimeout, cortex, lessonEnrichment |
| `.cursor/rules/02-architecture.mdc` | Reconciled | Behavioral air gap aligned with `docs/architecture.md` |
| `ui/README.md` | Updated | Cortex + JARVIS Memory pages added |

**Remaining optional work:** Archive this inventory file after maintainer sign-off. Consider automated OpenAPI export for api-reference drift prevention.
