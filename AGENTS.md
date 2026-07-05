# AGENTS.md — Workspace Facts and Anti-Patterns

This file captures learned facts, conventions, and non-obvious behaviors for
this repository. It is read by code-reviewer, security-reviewer,
reliability-reviewer, and doc-reviewer sub-agents on every review.

---

## CI/CD: AI Code Review Workflow

**File:** `.github/workflows/ai-review.yaml`

### Key behaviors

- **Advisory only.** The job sets `continue-on-error: true`. A reviewer
  crash or timeout will show as a yellow warning in the PR checks list, not
  a red blocking failure. Do not expect this check to gate merges.

- **20-minute hard timeout.** Large PRs near the `AI_REVIEW_MAX_DIFF_LINES`
  threshold (default 5000 lines) may occasionally hit this limit. If the
  check times out, re-run manually from the Actions tab.

- **Diff size skip.** Diffs exceeding `AI_REVIEW_MAX_DIFF_LINES` (default
  5000) are silently skipped — the job exits cleanly with no review posted.
  Do not interpret a clean green check on a large PR as "reviewed".

- **Artifact retention.** Structured results are uploaded to `ci-results/`
  and retained for 7 days. Fetch from the Actions tab workflow run page.
  After 7 days the artifact is purged automatically.

- **Container image pinning.** The workflow uses
  `quay.io/redhat-user-workloads/ocp-virt-images-tenant/gitops-ci-reviewer:latest`
  (floating `latest` tag). Image changes take effect on the next workflow
  run without any PR needed.

### Required secrets and variables

| Name | Kind | Required | Notes |
|---|---|---|---|
| `VERTEX_SA_JSON` | Secret | Yes | Base64-encoded SA JSON. Encode with `cat sa.json \| jq -c '.' \| base64 -w0`. The `jq -c '.'` compaction step is mandatory — omitting it causes silent decode failures. |
| `GOOGLE_CLOUD_PROJECT` | Variable | Yes | GCP project ID hosting the Vertex AI endpoint |
| `GOOGLE_CLOUD_REGION` | Variable | No | Defaults to `us-central1` |
| `AI_REVIEW_MODEL` | Variable | No | Defaults to `claude-sonnet-4-6` |
| `AI_REVIEW_EFFORT` | Variable | No | `low`, `medium`, `high`. Defaults to `medium` |
| `AI_REVIEW_MAX_TURNS` | Variable | No | Defaults to `15` |
| `AI_REVIEW_MAX_BUDGET` | Variable | No | USD spend cap per run. Defaults to `3.50` |
| `AI_REVIEW_MAX_DIFF_LINES` | Variable | No | Skip threshold. Defaults to `5000` |

### Anti-patterns

- **Do not omit `jq -c '.'` when encoding `VERTEX_SA_JSON`.** Multi-line
  base64 strings cause silent decode failures at runtime; the workflow
  continues but Vertex AI auth fails.

- **Do not rely on the AI review check as a merge gate.** `continue-on-error: true`
  means the check is informational. Merge policies must be enforced by
  separate required status checks.

- **Do not commit `sa.json` to the repository.** The decoded credential
  file is written to `/tmp/vertex-sa.json` inside the ephemeral runner and
  discarded when the job completes. The source JSON key must never be
  committed.

### Environment variable mapping

The entrypoint normalizes GitHub Actions variables to GitLab CI equivalents
at runtime:

| GitHub Actions variable | Entrypoint variable |
|---|---|
| `github.base_ref` | `CI_MERGE_REQUEST_TARGET_BRANCH_NAME` |
| `github.head_ref` | `CI_MERGE_REQUEST_SOURCE_BRANCH_NAME` |
| `github.event.pull_request.number` | `CI_MERGE_REQUEST_IID` |
| `github.workspace` | `CI_PROJECT_DIR` |
| `github.event.pull_request.head.sha` | `PR_HEAD_SHA` |

> **Full setup guide:** [docs/ai-review.md](docs/ai-review.md)
