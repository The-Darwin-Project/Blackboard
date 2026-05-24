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

### Headhunter

| Variable | Description | Default |
| --- | --- | --- |
| `HEADHUNTER_ENABLED` | Enable GitLab MR lifecycle agent | `false` |
| `HEADHUNTER_POLL_INTERVAL` | Todo poll interval (seconds) | (see code) |
| `GITLAB_HOST` | GitLab instance hostname | (required if enabled) |
| `LLM_MODEL_HEADHUNTER` | Headhunter Flash model | (see code) |

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

### Ephemeral Agents

| Variable | Description | Default |
| --- | --- | --- |
| `TEKTON_EVENTLISTENER_URL` | Tekton EventListener URL for spawning | (required if enabled) |

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

After image builds, the workflow auto-commits the new SHA tag to `helm/values.yaml` (with `[skip ci]`), which ArgoCD detects and syncs.
