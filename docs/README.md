# Darwin Agent Service Accounts

ServiceAccounts for Darwin agents to access ArgoCD and Kargo APIs.
These live in their respective GitOps repos and are synced by ArgoCD.

## ArgoCD Agent

**File**: `openshift-gitops/ArgoCD/darwin-agent-sa.yaml`
**Synced to**: `openshift-gitops` namespace (via ArgoCD self-management)

Creates:
- `ServiceAccount/darwin-argocd-agent`
- `Secret/darwin-argocd-agent-token` (auto-populated by K8s)
- `ClusterRole/darwin-argocd-agent` (read ArgoCD CRDs)
- `ClusterRoleBinding/darwin-argocd-agent`

### Setup

1. Commit and push `darwin-agent-sa.yaml` to the ArgoCD repo -- ArgoCD syncs it.

2. Add the ArgoCD API RBAC policy to `Argocd-cr.yaml` under `spec.rbac.policy`:
   ```
   p, role:darwin-readonly, applications, get, */*, allow
   p, role:darwin-readonly, applications, sync, */*, deny
   p, role:darwin-readonly, projects, get, *, allow
   p, role:darwin-readonly, clusters, get, *, allow
   p, role:darwin-readonly, repositories, get, *, allow
   p, role:darwin-readonly, logs, get, */*, allow

   g, system:serviceaccount:openshift-gitops:darwin-argocd-agent, role:darwin-readonly
   ```

3. Once synced, extract the token and create the Darwin secret:
   ```bash
   ARGOCD_TOKEN=$(oc get secret darwin-argocd-agent-token -n openshift-gitops -o jsonpath='{.data.token}' | base64 -d)

   oc create secret generic darwin-argocd-creds \
     --from-literal=server=openshift-gitops-server.openshift-gitops.svc:443 \
     --from-literal=auth-token="$ARGOCD_TOKEN" \
     -n darwin
   ```

4. Enable in `BlackBoard/helm/values.yaml`:
   ```yaml
   argocd:
     enabled: true
     existingSecret: "darwin-argocd-creds"
     server: "openshift-gitops-server.openshift-gitops.svc:443"
   ```

---

## Kargo Agent

**File**: `kargo/kargo/templates/openshift/darwin-agent-sa.yaml`
**Synced to**: `kargo` namespace (via ArgoCD Kargo Application)

Creates:
- `ServiceAccount/darwin-kargo-agent`
- `Secret/darwin-kargo-agent-token` (auto-populated by K8s)
- `ClusterRole/darwin-kargo-agent` (read Kargo CRDs)
- `ClusterRoleBinding/darwin-kargo-agent`

### Setup

1. Commit and push `darwin-agent-sa.yaml` to the Kargo repo -- ArgoCD syncs it.

2. Once synced, extract the token and create the Darwin secret:
   ```bash
   KARGO_TOKEN=$(oc get secret darwin-kargo-agent-token -n kargo -o jsonpath='{.data.token}' | base64 -d)

   oc create secret generic darwin-kargo-creds \
     --from-literal=server=kargo-api.kargo.svc:443 \
     --from-literal=auth-token="$KARGO_TOKEN" \
     -n darwin
   ```

3. Enable in `BlackBoard/helm/values.yaml`:
   ```yaml
   kargo:
     enabled: true
     existingSecret: "darwin-kargo-creds"
     server: "kargo-api.kargo.svc:443"
   ```

> **Note**: If the Kargo API rejects the SA bearer token (it uses
> Dex/OIDC), use the admin password instead in the `auth-token` key
> and update `server.js` to use `kargo login --admin --password`.

---

## Cluster-specific values

| Component | Namespace | Service | Token Secret |
|-----------|-----------|---------|-------------|
| ArgoCD | `openshift-gitops` | `openshift-gitops-server:443` | `darwin-argocd-agent-token` |
| Kargo | `kargo` | `kargo-api:443` | `darwin-kargo-agent-token` |
