---
description: "GitOps service discovery, source context, and ArgoCD awareness"
tags: [gitops, discovery, argocd, source-repo]
---
# GitOps Context

Services self-describe their coordinates via pod annotations (passive discovery):

| Annotation | Purpose |
|---|---|
| `darwin.io/source-repo` | Git URL of the application source code |
| `darwin.io/gitops-repo` | Git URL of the GitOps config (Kustomize/Helm) |
| `darwin.io/config-path` | Relative path to the service's kustomization.yaml |

These values are available in the service registry after you query it.

## Investigation Dispatch Rule

When routing an AGENT for **code investigation**, you MUST include
the `source-repo` URL in your routing instruction. The agent needs the actual
source repository to clone -- not the bundled artifacts inside a running container.

Always include the `source-repo` URL in the routing instruction so the agent
can clone and navigate the actual source.

## GitOps Sync Status

When checking GitOps sync status, instruct sysAdmin to discover the GitOps tooling
namespace first (e.g., search for ArgoCD or Flux namespaces) rather than assuming
a specific namespace.
