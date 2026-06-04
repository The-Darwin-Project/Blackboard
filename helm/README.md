<!-- @ai-rules:
1. [Constraint]: Chart-specific install docs. Do not duplicate architecture details from root README.md.
2. [Pattern]: Required Values table must stay in sync with values.yaml defaults.
3. [Pattern]: Optional Integrations table must list every .enabled flag in values.yaml.
4. [Constraint]: No internal hostnames, project IDs, or credentials in examples.
-->
# Darwin Brain Helm Chart

Helm chart for deploying the Darwin Blackboard (Brain) on Kubernetes or OpenShift.

## Installation

### From OCI Registry (GHCR)

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
```

## Required Values

| Value | Description |
| :--- | :--- |
| `gcp.project` | GCP project ID for Vertex AI |
| `gcp.existingSecret` | Pre-created K8s Secret containing GCP service account JSON |

## Optional Integrations

Each integration is disabled by default and enabled via a flag + secret reference.

| Integration | Enable Flag | Secret |
| :--- | :--- | :--- |
| GitLab | `gitlab.enabled: true` | `gitlab.existingSecret` |
| ArgoCD | `argocd.enabled: true` | `argocd.existingSecret` |
| Kargo | `kargo.enabled: true` | `kargo.existingSecret` |
| Slack | `slack.enabled: true` | `slack.existingSecret` |
| GitHub App | -- | `github.existingSecret` |
| Dex OIDC | `dex.enabled: true` | Requires cert-manager |
| TimeKeeper | `timekeeper.enabled: true` | Requires `dex.enabled: true` |
| Ephemeral Agents | `ephemeralAgents.enabled: true` | Requires Tekton Triggers CRDs |
| Nightwatcher | `nightwatcher.enabled: true` | -- |
| Headhunter | `headhunter.enabled: true` | Requires `gitlab.enabled: true` |
| Headhunter Jira (QE Missions) | `jira.enabled: true` | `jira.existingSecret` (email, api-token, bot-account-id) |
| Smartsheet Incidents | `smartsheet.incident.enabled: true` | `smartsheet.incident.existingSecret` |
| KargoObserver | `kargoObserver.enabled: true` | Requires `kargo.enabled: true` |
| Google Search | `googleSearch.enabled: true` | Sets `BRAIN_GOOGLE_SEARCH_ENABLED` |
| Lesson Enrichment | `lessonEnrichment.enabled: true` | Injects darwin_lessons into Brain prompt |
| Cortex / JARVIS | `cortex.system2.enabled: true` | Pulse tracking via `cortex.pulseTracking`; shadow via `cortex.system2.shadow` |
| Registry Pull (runtime) | `registry.enabled: true` | `registry.existingSecret` (dockerconfigjson for agent CLIs) |
| Remote Clusters (MCP) | `remoteClusters.<name>.enabled: true` | Per-cluster kubeconfig Secret |
| Trusted Proxy (BFF) | Env only | Set `TRUSTED_PROXY_ENABLED` + `TRUSTED_PROXY_SECRET` via extra env/Secret (see [deployment.md](../docs/deployment.md)) |
| K8s Observer | `observer.enabled: true` | Pod ServiceAccount |

## Networking

### OpenShift

An OpenShift Route is created by default (`route.enabled: true`).

### Vanilla Kubernetes

Disable the Route and enable Ingress:

```bash
helm install darwin-brain ./helm \
  --set route.enabled=false \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host=darwin.your-domain.com
```

Default Ingress annotations include WebSocket timeout overrides (3600s) for `/ws` and `/agent/ws`. Adjust for non-NGINX controllers.

## Agent Sidecars

Four agent sidecars are included (Architect, SysAdmin, Developer, QE). Each supports `gemini` or `claude` CLI:

```bash
--set sidecars.architect.cliType=claude
--set sidecars.architect.modelName=claude-opus-4-6
```

## Observers

Four background observers can be enabled independently:

| Observer | Purpose | Enable Flag |
| :--- | :--- | :--- |
| Kubernetes | Pod health, metrics-server, darwin.io annotations | `observer.enabled: true` |
| Kargo | Promotion failure/recovery detection | `kargoObserver.enabled: true` |
| TimeKeeper | Scheduled task execution | `timekeeper.enabled: true` |
| Nightwatcher | Shift consolidation (cron-based) | `nightwatcher.enabled: true` |
| Headhunter Jira | Jira QE mission polling | `jira.enabled: true` |

## Behavioral Tuning

These blocks control event lifecycle behavior (no external service required):

| Block | Purpose | Key Values |
| :--- | :--- | :--- |
| `idleTimeout` | Auto-close stale chat/slack approval threads | `warningSec`, `closeSec` |
| `brain.reconcileWorkers` | ReconcileScheduler worker pool | `0` = auto-derive from source caps |
| `app.maxConcurrentDispatches` | Global WIP cap for local sidecar dispatches | `0` = disabled |
| `app.agentWsMode` | Sidecar WebSocket direction | `reverse` (production) or `legacy` |

## Full Values Reference

See [values.yaml](values.yaml) for all available configuration options with inline documentation.

## Upgrading

```bash
helm upgrade darwin-brain oci://ghcr.io/the-darwin-project/charts/darwin-brain \
  --version 1.1.0 \
  --reuse-values
```
