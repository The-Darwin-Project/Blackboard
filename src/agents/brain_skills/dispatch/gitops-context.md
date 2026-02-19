---
description: "GitOps service discovery and ArgoCD awareness"
tags: [gitops, discovery, argocd]
---
# GitOps Context

Services self-describe their GitOps coordinates (repo, helm path) via telemetry.
When checking GitOps sync status, instruct sysAdmin to discover the GitOps tooling namespace first (e.g., search for ArgoCD or Flux namespaces) rather than assuming a specific namespace.
