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
NOTE: app label MUST differ from darwin.selectorLabels to avoid
      EventListener pods polluting the Brain Service endpoints.
*/}}
{{- define "darwin.ephemeralLabels" -}}
app: darwin-ephemeral-dispatcher
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

{{/*
Skills Catalog URL env block — included in sidecar containers and Tekton TriggerTemplate.
Gated on .Values.jenkinsObserver.skillsCatalog.url being truthy (independent of .Values.jenkinsObserver.enabled).
*/}}
{{- define "darwin.skillsCatalogEnv" -}}
{{- if and .Values.jenkinsObserver .Values.jenkinsObserver.skillsCatalog .Values.jenkinsObserver.skillsCatalog.url }}
- name: SKILLS_CATALOG_URL
  value: "{{ .Values.jenkinsObserver.skillsCatalog.url }}"
{{- end }}
{{- end }}


{{/*
Validate every CLI selector in the chart. The sidecar entrypoint / Brain only support 'claude' and 'agy'
(legacy 'gemini' was sunset in VMER-2030); a stale override such as cliType=gemini would otherwise render
fine and crash-loop the sidecar or ephemeral agent at startup. Checked values:
  - sidecars.{architect,sysadmin,developer,qe}.cliType   (enabled sidecars only; empty => 'claude')
  - ephemeralAgents.cli                                  (when ephemeralAgents.enabled; empty tolerated)
  - ephemeralAgents.roleCli.<role>                       (every entry; empty => unset/default)
Usage: {{ include "darwin.validateSidecars" . }}
*/}}
{{- define "darwin.validateSidecars" -}}
{{- $allowed := list "claude" "agy" -}}
{{- range $role := list "architect" "sysadmin" "developer" "qe" -}}
{{- $sc := index $.Values.sidecars $role | default dict -}}
{{- if and (kindIs "map" $sc) (ne (toString (get $sc "enabled")) "false") -}}
{{- $cli := (get $sc "cliType") | default "claude" -}}
{{- if not (has $cli $allowed) -}}
{{- fail (printf "sidecars.%s.cliType=%q is invalid: must be one of %s (legacy 'gemini' was removed in VMER-2030; update or remove the stale override)" $role $cli (join ", " $allowed)) -}}
{{- end -}}
{{- $model := (get $sc "modelName") | default "" -}}
{{- if and (eq $cli "agy") (hasPrefix "claude" $model) -}}
{{- fail (printf "sidecars.%s.cliType is 'agy' but modelName=%q is a Claude model: agy requires a Gemini model (e.g. gemini-3.7-flash)" $role $model) -}}
{{- end -}}
{{- if and (eq $cli "claude") (hasPrefix "gemini" $model) -}}
{{- fail (printf "sidecars.%s.cliType is 'claude' but modelName=%q is a Gemini model: claude requires a Claude model (e.g. claude-sonnet-5-5)" $role $model) -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- $ea := $.Values.ephemeralAgents | default dict -}}
{{- if and (kindIs "map" $ea) (ne (toString (get $ea "enabled")) "false") -}}
{{- $cli := (get $ea "cli") | default "" -}}
{{- if and $cli (not (has $cli $allowed)) -}}
{{- fail (printf "ephemeralAgents.cli=%q is invalid: must be one of %s (legacy 'gemini' was removed in VMER-2030)" $cli (join ", " $allowed)) -}}
{{- end -}}
{{- range $role, $rcli := (get $ea "roleCli" | default dict) -}}
{{- if and $rcli (not (has (toString $rcli) $allowed)) -}}
{{- fail (printf "ephemeralAgents.roleCli.%s=%q is invalid: must be one of %s (legacy 'gemini' was removed in VMER-2030)" $role $rcli (join ", " $allowed)) -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end }}

{{/*
Per-sidecar storage env: DEFAULT_WORK_DIR must match the container's actual volume mount (the storage recycler measures
and sweeps that mount), plus the optional sidecars.storageRecycler tunables. Unset tunables are omitted so the
sidecar's validated defaults apply.
Usage: {{ include "darwin.storageEnv" (dict "root" $ "mount" "/data/gitops-developer") | nindent 12 }}
*/}}
{{- define "darwin.storageEnv" -}}
- name: DEFAULT_WORK_DIR
  value: {{ .mount | quote }}
{{- $sr := (.root.Values.sidecars.storageRecycler | default dict) }}
{{- range $env, $key := dict "STORAGE_HIGH_WATERMARK" "highWatermark" "STORAGE_CRITICAL_WATERMARK" "criticalWatermark" "STORAGE_STALE_MS" "staleMs" "STORAGE_SWEEP_INTERVAL_MS" "sweepIntervalMs" }}
{{- $val := get $sr $key }}
{{- if not (kindIs "invalid" $val) }}
{{- if ne (toString $val) "" }}
- name: {{ $env }}
  value: {{ $val | toString | quote }}
{{- end }}
{{- end }}
{{- end }}
{{- end -}}
