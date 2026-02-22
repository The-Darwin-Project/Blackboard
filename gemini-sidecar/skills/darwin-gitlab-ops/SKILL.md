---
name: darwin-gitlab-ops
description: GitLab API interaction patterns for internal GitLab instances. Use when working with GitLab merge requests, pipelines, projects, or any GitLab API call.
roles: [architect, sysadmin, developer]
---

# GitLab Operations

## Pre-Configured Environment

`glab` CLI and GitLab MCP tools are pre-configured for `$GITLAB_HOST` with TLS verification disabled. You do not need to handle SSL certificates or authentication setup.

Available environment variables:
- `GITLAB_TOKEN` -- Personal Access Token for API calls
- `GITLAB_HOST` -- The internal GitLab hostname

Git operations (`clone`, `push`, `pull`) to `$GITLAB_HOST` also have SSL verification disabled -- you can use standard git commands without TLS workarounds.

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

- `openshift-virtualization/konflux-builds/v4-22/my-repo`
- Encoded: `openshift-virtualization%2Fkonflux-builds%2Fv4-22%2Fmy-repo`

Use `glab api "/projects/$(python3 -c 'import urllib.parse; print(urllib.parse.quote("group/subgroup/repo", safe=""))')"` for dynamic encoding.

## Fallback: curl

When MCP tools or `glab` are unavailable, use `curl` directly:

```bash
curl -k -H "PRIVATE-TOKEN: $GITLAB_TOKEN" \
  "https://$GITLAB_HOST/api/v4/projects?per_page=20"
```

The `-k` flag skips TLS verification for the internal instance.
