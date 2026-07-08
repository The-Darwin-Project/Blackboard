<!-- @ai-rules:
1. [Constraint]: Env var table must stay in sync with src/main.py, brain.py, aligner.py, and helm/values.yaml.
2. [Pattern]: Group env vars by component (Brain, Aligner, Agents, Observers, Auth, Slack, Nightwatcher).
3. [Gotcha]: AGENT_WS_MODE=reverse is the production mode. Legacy mode is deprecated but still supported.
4. [Constraint]: No internal hostnames, project IDs, or credentials. Open-source hygiene.
-->
# Deployment Guide

## Local Development

### Prerequisites

- Python 3.12+
- Node.js 22+
- Docker (for Redis and Qdrant)
- GCP project with Vertex AI API enabled

### Quick Start

```bash
# Start Redis + Qdrant
docker compose up -d

# Install Python dependencies
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Set required environment variables
export REDIS_HOST=localhost
export GCP_PROJECT=your-project-id
export GCP_LOCATION=us-central1

# Run the Brain server
uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

### UI Development (separate terminal)

```bash
cd ui
npm ci
npm run dev    # Vite dev server on port 5174
```

See [CONTRIBUTING.md](../CONTRIBUTING.md) for full development setup including sidecar builds and testing.

## Helm Deployment (OpenShift / Kubernetes)

### From OCI Registry

```bash
helm install darwin-brain oci://ghcr.io/the-darwin-project/charts/darwin-brain \
  --version 1.0.0 \
  --set gcp.project=your-project-id \
  --set gcp.existingSecret=gcp-sa-key
```

### From Source

```bash
git clone https://github.com/The-Darwin-Project/Blackboard.git
cd Blackboard
helm install darwin-brain ./helm \
  --set gcp.project=your-project-id \
  --set gcp.existingSecret=gcp-sa-key

# Verify -- Brain + Redis + Qdrant + 4 sidecars
kubectl get pods -l app=darwin-brain
```

See [helm/README.md](../helm/README.md) for full chart documentation, optional integrations, and networking options.

## Environment Variables

### Brain (Core)

| Variable | Description | Default |
| --- | --- | --- |
| `REDIS_HOST` | Redis hostname | `localhost` |
| `REDIS_PASSWORD` | Redis password | (empty) |
| `GCP_PROJECT` | GCP project ID | (required) |
| `GCP_LOCATION` | Vertex AI location | `global` |
| `LLM_MODEL_BRAIN` | Brain model | `gemini-3.1-pro-preview` |
| `LLM_MODEL_MANAGER` | Manager (DevTeam) model | `gemini-3.1-pro-preview` |
| `LLM_MODEL_ARCHIVIST` | Archivist model | `gemini-3.1-pro-preview` |
| `LLM_TPM_LIMIT` | Tokens-per-minute quota limit | (none) |
| `BRAIN_PROGRESSIVE_SKILLS` | Enable progressive skills | `true` |
| `BRAIN_GOOGLE_SEARCH_ENABLED` | Enable web search grounding | `false` |
| `QDRANT_URL` | Qdrant vector store | `http://localhost:6333` |
| `DEBUG` | Enable debug logging | `false` |

### Agent WebSocket

| Variable | Description | Default |
| --- | --- | --- |
| `AGENT_WS_MODE` | `legacy` (Brain→sidecar) or `reverse` (sidecar→Brain) | `legacy` |
| `ARCHITECT_SIDECAR_URL` | Architect WebSocket (legacy mode) | `http://localhost:9091` |
| `SYSADMIN_SIDECAR_URL` | SysAdmin WebSocket (legacy mode) | `http://localhost:9092` |
| `DEVELOPER_SIDECAR_URL` | Developer WebSocket (legacy mode) | `http://localhost:9093` |
| `QE_SIDECAR_URL` | QE WebSocket (legacy mode) | `http://localhost:9094` |

### Aligner

| Variable | Description | Default |
| --- | --- | --- |
| `LLM_MODEL_ALIGNER` | Aligner model | `gemini-3.5-flash` |
| `ALIGNER_CPU_THRESHOLD` | CPU warning threshold | (see code) |
| `ALIGNER_MEMORY_THRESHOLD` | Memory warning threshold | (see code) |
| `ALIGNER_ERROR_RATE_THRESHOLD` | Error rate threshold | (see code) |

### Observers

| Variable | Description | Default |
| --- | --- | --- |
| `K8S_OBSERVER_ENABLED` | Enable K8s metrics observer | `true` |
| `K8S_OBSERVER_INTERVAL` | Observer poll interval (seconds) | (see code) |
| `KARGO_OBSERVER_ENABLED` | Enable Kargo promotion watcher | `false` |
| `TIMEKEEPER_ENABLED` | Enable TimeKeeper (requires DEX) | `false` |
| `TIMEKEEPER_POLL_INTERVAL` | TimeKeeper poll interval (seconds) | `30` |
| `TIMEKEEPER_MAX_PER_USER` | Max schedules per user | `10` |
| `TIMEKEEPER_MAX_TOTAL` | Max schedules system-wide | `50` |
| `LLM_MODEL_TIMEKEEPER` | TimeKeeper refiner model | `gemini-3.5-flash` |

### Headhunter (GitLab)

| Variable | Description | Default |
| --- | --- | --- |
| `HEADHUNTER_ENABLED` | Enable GitLab MR lifecycle agent | `false` |
| `HEADHUNTER_POLL_INTERVAL` | Todo poll interval (seconds) | (see code) |
| `GITLAB_HOST` | GitLab instance hostname | (required if enabled) |
| `LLM_MODEL_HEADHUNTER` | Headhunter Flash model | (see code) |

### Headhunter (GitHub)

| Variable | Description | Default |
| --- | --- | --- |
| `HEADHUNTER_GITHUB_ENABLED` | Enable GitHub PR polling | `false` |
| `HEADHUNTER_GITHUB_POLL_INTERVAL` | PR poll interval (seconds) | (see code) |
| `HEADHUNTER_GITHUB_REPOS` | Comma-separated `owner/repo` list (empty = auto-discover from installation) | (empty) |
| `HEADHUNTER_GITHUB_TRIGGER_REASONS` | Comma-separated trigger reasons | `review_requested` |
| `HEADHUNTER_GITHUB_LABEL` | Label-based trigger (alternative to review requests) | `darwin-review` |
| `GITHUB_APP_ID` | GitHub App ID (via K8s Secret) | (required if enabled) |
| `GITHUB_INSTALLATION_ID` | GitHub App Installation ID (via K8s Secret) | (required if enabled) |
| `GITHUB_APP_SLUG` | GitHub App slug for bot detection | `darwin-project-ai` |
| `HEADHUNTER_MAINTAINERS` | Comma-separated maintainer usernames for notifications | (empty) |

Helm block: `headhunter.github.enabled`, `headhunter.github.pollInterval`, `headhunter.github.repos`, `headhunter.github.triggerReasons`. GitHub App credentials via `github.existingSecret`.

### Headhunter Jira (QE Missions)

| Variable | Description | Default |
| --- | --- | --- |
| `JIRA_URL` | Jira Cloud base URL | (required if enabled) |
| `JIRA_EMAIL` | Jira API user email | (required if enabled) |
| `JIRA_API_TOKEN` | Jira API token | (required if enabled) |
| `HEADHUNTER_JIRA_LABEL` | Label filter for tracked issues | `darwin` |
| `HEADHUNTER_JIRA_BOT_ACCOUNT_ID` | Bot account ID for mention detection | (optional) |
| `HEADHUNTER_JIRA_SKILL_<LABEL>` | Label → git raw URL for custom system prompts | (optional) |

Helm block: `jira.enabled`, `jira.existingSecret`, `jira.maxActive`, `jira.model`, `jira.skills`.

### On Ice and Idle Timeout

| Variable | Description | Default |
| --- | --- | --- |
| `IDLE_TIMEOUT_WARNING_SEC` | Inactivity warning before auto-close (chat/slack) | `600` |
| `IDLE_TIMEOUT_CLOSE_SEC` | Auto-close after warning if no response | `300` |

Helm blocks: `idleTimeout.warningSec`, `idleTimeout.closeSec`.

### Lesson Enrichment

| Variable | Description | Default |
| --- | --- | --- |
| `LESSON_ENRICHMENT_ENABLED` | Inject RECALL block from darwin_lessons into Brain prompt | `false` |

Helm block: `lessonEnrichment.enabled`.

### Cortex (System 2)

| Variable | Description | Default |
| --- | --- | --- |
| `PULSE_TRACKING_ENABLED` | Emit pulse events on tool calls, phase changes, memory recall | `true` |
| `SYSTEM2_ENABLED` | Start Cortex observer (Gemini Live API session) | `true` |
| `SYSTEM2_SHADOW` | Log interventions without delivering to Brain | `false` |
| `SYSTEM2_SESSION_REPORT` | Generate session report on idle disconnect | `true` |
| `SYSTEM2_HANDOFF_REPORT` | Capture session notes on reconnect (go_away) | `true` |
| `SYSTEM2_MODEL` | Override Cortex Live model (empty = code default) | (empty) |

Helm block: `cortex.pulseTracking`, `cortex.system2.*`.

### Nightwatcher

| Variable | Description | Default |
| --- | --- | --- |
| `NIGHTWATCHER_ENABLED` | Enable shift consolidation | `false` |
| `NIGHTWATCHER_SWEEP_CRON` | Cron schedule for sweeps | `0 6,18 * * *` |
| `NIGHTWATCHER_MIN_PENDING` | Min pending escalations to trigger | `1` |
| `NIGHTWATCHER_DISPATCH_CAP` | Max ephemeral investigations per sweep | `3` |
| `LLM_MODEL_NIGHTWATCHER` | Nightwatcher Flash model | `gemini-3-flash-preview` |
| `LLM_TEMPERATURE_NIGHTWATCHER` | Nightwatcher LLM temperature | `0.3` |

### Authentication

| Variable | Description | Default |
| --- | --- | --- |
| `DEX_ENABLED` | Enable Dex OIDC auth | `false` |
| `TRUSTED_PROXY_ENABLED` | Enable trusted-proxy auth (BFF) | `false` |
| `TRUSTED_PROXY_SECRET` | Shared secret for BFF | (empty) |

### Slack

| Variable | Description | Default |
| --- | --- | --- |
| `SLACK_BOT_TOKEN` | Slack bot OAuth token | (optional) |
| `SLACK_APP_TOKEN` | Slack app-level token (Socket Mode) | (optional) |

### Jira Incidents (Nightwatcher)

| Variable | Description | Default |
| --- | --- | --- |
| `JIRA_INCIDENT_PROJECT_KEY` | Jira project key for incidents | (required if Jira incidents enabled) |
| `JIRA_INCIDENT_SEVERITY_FIELD` | Jira custom field ID for severity | (empty) |
| `JIRA_INCIDENT_PLATFORMS` | Comma-separated platform labels | (empty) |
| `JIRA_INCIDENT_PRIORITIES` | Comma-separated priority names | (empty) |
| `JIRA_INCIDENT_STATUSES` | Comma-separated valid statuses | `New,Closed` |
| `JIRA_INCIDENT_LABEL_FILTER` | Label filter for listing incidents | (empty) |

Uses the same `JIRA_URL`, `JIRA_EMAIL`, `JIRA_API_TOKEN` credentials as Headhunter Jira. Helm block: `jira.incident.enabled` (nested under `jira.enabled`).

### Ephemeral Agents

| Variable | Description | Default |
| --- | --- | --- |
| `TEKTON_EVENTLISTENER_URL` | Tekton EventListener URL for spawning | (required if enabled) |
| `EPHEMERAL_SPAWN_DEADLINE_SEC` | Absolute ceiling for spawn wait | `300` |
| `EPHEMERAL_POLL_INTERVAL_SEC` | Seconds between K8s pod status polls | `10` |
| `EPHEMERAL_STALL_TIMEOUT_SEC` | No-progress threshold before prune | `60` |
| `EPHEMERAL_INFRA_DEFER_SEC` | Seconds to defer when Tekton infra is unavailable | `120` |

Helm block: `ephemeralAgents.spawnDeadlineSec`, `ephemeralAgents.pollIntervalSec`, `ephemeralAgents.stallTimeoutSec`, `ephemeralAgents.infraDeferSec`.

## Passive Service Discovery

Darwin discovers services via Kubernetes annotations on Deployments:

```yaml
metadata:
  annotations:
    darwin.io/monitored: "true"
    darwin.io/gitops-repo: "https://github.com/org/repo.git"
    darwin.io/helm-path: "helm/values.yaml"
    darwin.io/service-name: "my-service"
    darwin.io/icon: "server"
```

The K8s Observer polls metrics-server for CPU/memory on annotated pods. Dependencies are inferred from Service endpoints and environment variables. Custom graph node icons are set via `darwin.io/icon`.

## CI/CD

GitHub Actions workflows handle the build pipeline:

| Workflow | Trigger | Output |
| --- | --- | --- |
| `build-push.yaml` | Push to `main` (src/, ui/, Dockerfile) | Brain image → GHCR (SHA tag + latest) |
| `build-gemini-sidecar.yaml` | Push to `main` (gemini-sidecar/) | Sidecar image → GHCR (SHA tag + latest) |
| `ci.yaml` | All pushes/PRs | pytest + UI build + helm lint |
| `helm-chart.yaml` | Push to `main` (helm/) | Helm chart → OCI registry (semver) |
| `ai-review.yaml` | PRs targeting `main`/`master` | AI code review comments + artifact (advisory, non-blocking) |

After image builds, the workflow auto-commits the new SHA tag to `helm/values.yaml` (with `[skip ci]`), which ArgoCD detects and syncs.
