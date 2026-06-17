---
name: darwin-gitlab-ops
description: "GitLab environment context: project resolution, authentication, and API conventions for GitLab instances."
roles: [architect, sysadmin, developer, qe, security_analyst]
---

# GitLab Operations

## Project Resolution (CRITICAL)

When working on an Event from the Headhunter, the event document
contains the authoritative project path and MR/PR URL in the GitLab Context
section.
**Use THAT project path and MR/PR URL for all API calls.**

Use the Service Lookup only for check Aligner events or when a user asks.

Extract from the event document:
- `MR/PR URL` -- use this for the target MR
- `Project` -- use this as the project path for API calls

## Pre-Configured Environment

GitLab CLI tools and MCP tools are pre-configured via `$GITLAB_HOST`. TLS behavior is controlled by the deployment environment. You do not need to handle authentication setup.

Available environment variables:

- `GITLAB_TOKEN` -- Personal Access Token for API calls
- `GITLAB_HOST` -- The GitLab hostname

Git operations to `$GITLAB_HOST` use the pre-configured TLS settings.

## Tool Preference

GitLab MCP tools are available in your tool list. Prefer them for structured API interactions -- they handle authentication and pagination automatically. CLI and direct API access are available as fallback.

## Arrival Comment

When dispatched to work on an MR/PR, your first action after reading the
event context is to post a brief comment on the MR/PR announcing what you
are investigating or doing. This gives visibility to anyone watching the
MR in GitLab.

Format: `Darwin ({role}): {one sentence describing your actual task}`

Post once on arrival. Do not post updates to the MR -- use `team_send_message`
for progress updates to FRIDAY instead.

## URL-Encoding for Nested Project Paths

GitLab API requires URL-encoded project paths for nested groups. For example, `org/group/subgroup/project` must be encoded as `org%2Fgroup%2Fsubgroup%2Fproject`. Ensure project paths are properly encoded when constructing API requests.
