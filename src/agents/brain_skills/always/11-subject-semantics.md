---
description: "How to interpret the event's subject_type and use the right context"
tags: [subject, service, kargo, jira, context]
tools: [lookup_service, refresh_kargo_context]
---
# Subject Types

Events have a `subject_type` field that tells you what the `service` field
actually refers to. Use this to determine what context is available and what
actions make sense.

## Subject Type Reference

### service (K8s Deployment)

The event targets a monitored Kubernetes deployment. The prompt includes
deployment metadata (version, replicas, CPU, memory, GitOps repo) when
the service is discovered via K8s annotations. Service lookup and agent
investigation are appropriate.

### service (GitLab Component)

When GitLab context is present (project, MR, pipeline, branch, author),
the event targets a pipeline component — not a running K8s deployment.
The prompt shows `Component:` with the full MR context. The relevant data
is already in front of you; service lookup will not find deployment metadata.

### kargo_stage

The event targets a Kargo promotion stage. The prompt shows `Kargo Stage:`
with project, promotion ID, phase, and failed step.

Kargo stages are subscription-capable resources — the Brain has a native
mechanism to read current stage state and register background subscriptions
that wake the event on state change. This means status checks ("has this
promotion step finished?") never require agent dispatch. Dispatching an
agent to answer a state question that the native refresh can answer wastes
a sidecar slot and violates the principle that agent dispatch is for work,
not polling.

Service lookup is not applicable for Kargo stages.

### jira

The event targets a Jira issue. The prompt shows `Jira Issue:` with key,
summary, status, and priority. Jira-specific tools provide issue state
and transitions. Service lookup is not applicable.

### github_issue

The event targets a GitHub Issue assigned to Darwin for autonomous work. The prompt shows
`GitHub Issue:` with the issue number, title, repository, and body.

The issue body is the specification — it describes what the requester wants done, not a
failure to triage. No deployment metadata, no pipeline state, no service lookup applies.
Labels may indicate a skill domain or routing preference; the issue body is the authoritative
source of intent.

Darwin's execution boundary is the repository. Agents may create commits and pull requests
within that repository. A PR link in the close comment is the expected deliverable when
the work involves code changes.

### system

The event is system-level (e.g., from JARVIS). There is no specific
service or component target. The prompt shows `Subject: System-level`.

## General Guidance

- Read the subject block in your prompt to understand what you are working with.
- If the subject is not a K8s deployment, the deployment-oriented data
  (replicas, CPU, memory) is not relevant to this event.
- The structured evidence in your prompt (GitLab context, Kargo context,
  Jira context) provides the details you need for non-deployment subjects.
