{{/*
helm/templates/_helpers.tpl
Centralized label helpers. Single source of truth for all K8s object labels.
Prevents label drift between selectors (Deployment, NetworkPolicy, PDB) and
metadata (ConfigMaps, Secrets, Services).
*/}}

{{/*
Common metadata labels for brain core resources.
Used on: Deployment, Service, ConfigMaps, Secrets, PVC, Route, Ingress, SA, RBAC.
*/}}
{{- define "darwin.labels" -}}
app: darwin-brain
app.kubernetes.io/name: darwin-brain
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Pod selector labels (subset of darwin.labels).
Used on: Deployment.spec.selector, Service.spec.selector, PDB.spec.selector,
         NetworkPolicy.spec.ingress.from.podSelector.
MUST match the pod template labels exactly.
*/}}
{{- define "darwin.selectorLabels" -}}
app: darwin-brain
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Ephemeral agent component labels.
Used on: EventListener, TaskRuns, ephemeral RBAC.
*/}}
{{- define "darwin.ephemeralLabels" -}}
app: darwin-brain
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: ephemeral-agent
{{- end }}

{{/*
Qdrant component labels.
*/}}
{{- define "darwin.qdrantLabels" -}}
app.kubernetes.io/name: darwin-qdrant
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: qdrant
{{- end }}

{{/*
Dex component labels.
*/}}
{{- define "darwin.dexLabels" -}}
app.kubernetes.io/name: {{ .Release.Name }}
app.kubernetes.io/component: dex
{{- end }}

{{/*
Observer RBAC labels.
*/}}
{{- define "darwin.observerLabels" -}}
app: darwin-brain
app.kubernetes.io/name: darwin-blackboard
app.kubernetes.io/component: observer
{{- end }}

{{/*
Kargo observer RBAC labels.
*/}}
{{- define "darwin.kargoLabels" -}}
app: darwin-brain
app.kubernetes.io/name: darwin-blackboard
app.kubernetes.io/component: kargo-observer
{{- end }}

{{/*
Slack access gate RBAC labels.
*/}}
{{- define "darwin.slackGateLabels" -}}
app: darwin-brain
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: slack-access-gate
{{- end }}
