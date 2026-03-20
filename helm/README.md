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

## Full Values Reference

See [values.yaml](values.yaml) for all available configuration options with inline documentation.

## Upgrading

```bash
helm upgrade darwin-brain oci://ghcr.io/the-darwin-project/charts/darwin-brain \
  --version 1.1.0 \
  --reuse-values
```
