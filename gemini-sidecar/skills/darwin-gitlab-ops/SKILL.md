---
name: darwin-gitlab-ops
description: GitLab API interaction patterns for GitLab instances. Use when working with GitLab merge requests, pipelines, projects, or any GitLab API call.
roles: [architect, sysadmin, developer]
---

# GitLab Operations

## Project Resolution (CRITICAL)

When working on an Event from the Headhunter, the event document
contains the authoritative project path and MR URL in the GitLab Context
section. 
**Use THAT project path and MR URL for all API calls.**

Use the Service Lookup only for chack Aligner events or When a user asks.

Extract from the event document:
- `MR URL` -- use this for the target MR
- `Project` -- use this as the project path for API calls

## Pre-Configured Environment

`glab` CLI and GitLab MCP tools are pre-configured via `$GITLAB_HOST`. TLS behavior is controlled by the deployment environment. You do not need to handle authentication setup.

Available environment variables:

- `GITLAB_TOKEN` -- Personal Access Token for API calls
- `GITLAB_HOST` -- The GitLab hostname

Git operations (`clone`, `push`, `pull`) to `$GITLAB_HOST` use the pre-configured TLS settings -- you can use standard git commands.

## Preferred: GitLab MCP Tools

GitLab MCP tools are available in your tool list. Prefer them for structured API interactions -- they handle authentication and pagination automatically.

## glab CLI

Use `glab` for direct CLI operations. Authentication and TLS are pre-configured.

Useful patterns:

- List projects: `glab api /projects --per-page 20`
- Get MR details: `glab api /projects/:id/merge_requests/:iid`
- List pipelines: `glab api /projects/:id/pipelines --per-page 10`
- Post MR note: `glab api /projects/:id/merge_requests/:iid/notes -f body="comment text"`
- Get MR changes: `glab api /projects/:id/merge_requests/:iid/changes`

## URL-Encoding Nested Project Paths

GitLab API requires URL-encoded project paths for nested groups:

- `org/group/subgroup/project`
- Encoded: `org%2Fgroup%2Fsubgroup%2Fproject`

Use `glab api "/projects/$(python3 -c 'import urllib.parse; print(urllib.parse.quote("group/subgroup/repo", safe=""))')"` for dynamic encoding.

## Fallback: curl

When MCP tools or `glab` are unavailable, use `curl` directly:

```bash
curl -k -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://$GITLAB_HOST/api/v4/projects?per_page=20"
```

The `-k` flag skips TLS verification when required by the target instance.
