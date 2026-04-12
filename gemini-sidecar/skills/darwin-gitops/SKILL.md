---
name: darwin-gitops
description: GitOps workflow rules for modifying infrastructure via git. Use when cloning repos, modifying Helm values, committing, pushing, or verifying deployments.
roles: [sysadmin, developer, qe]
---

# Darwin GitOps Workflow

## GitOps Rules

- `image.tag` fields are managed by CI pipelines -- do NOT change them
- `replicaCount` is what you change for scaling operations
- Helm values files are YAML -- preserve formatting and comments
- Commit messages follow: `ops(service): description` (sysadmin) or `feat(service): description` / `fix(service): description` (developer)
- ALL mutations (scaling, config changes) MUST go through GitOps. NEVER use `kubectl scale`, `kubectl patch`, or `kubectl edit`.
- ONLY modify EXISTING values in values.yaml. Do NOT add new sections or keys unless the corresponding template already exists in the chart's `templates/` directory.
- If a change requires a new template, stop and report that it needs Architect review.

## Git Hygiene

- **Always sync with the remote before making changes** -- the repo may have been modified by CI or other agents
- Review recent commit history before making changes
- If your push fails, sync with the remote and retry
- NEVER force push: `git push --force` or `git push -f`
- One change per commit. Never bundle unrelated changes.
- Each commit must leave the system in a deployable state.
- Review your changes before every commit.

## Deployment Awareness

Before acting on a deployment, assess how the application is deployed:

- Discover the GitOps tooling: use your available MCP and CLI tools to find ArgoCD Applications, check remote cluster workload status, or query CD automation. Also check for Flux resources.
- Check if the application has auto-sync, selfHeal, or webhook-triggered pipelines
- **NEVER** run `kubectl rollout restart` or `kubectl scale` without first understanding who manages the deployment
- After pushing a GitOps change, report: "Change committed and pushed. The CD controller will handle the rollout."
- When asked to verify a deployment, check the running pod's image tag against the expected commit SHA
- If the cluster state doesn't match git after a reasonable sync interval, report the drift

## Developer Git Workflow

- Create a feature branch for changes (not main)
- Branch name MUST use `{type}/evt-{EVENT_ID}` format (see `darwin-branch-naming` skill for prefix selection)
- Do NOT push directly to main -- CI validates and auto-merges
- Use pre-configured GIT_USER_NAME and GIT_USER_EMAIL for commits
