# AI Code Review Workflow

The project ships a GitHub Actions workflow (`.github/workflows/ai-review.yaml`)
that runs an AI code review container on every pull request targeting `main` or
`master`. The reviewer posts findings as PR comments and uploads structured
results as a workflow artifact.

## Prerequisites

The workflow authenticates to Vertex AI using a Google Cloud service account.
You must configure two repository-level settings before the workflow will
function:

### Required secret

| Secret name | Description | How to encode |
|---|---|---|
| `VERTEX_SA_JSON` | Base64-encoded Google Cloud service account JSON key | `cat sa.json \| jq -c '.' \| base64 -w0` |

Create the secret under **Settings > Secrets and variables > Actions > New repository secret**.

The `jq -c '.'` step compacts the JSON to a single line before encoding, which
avoids line-wrapping issues in some shells. Omitting it can cause silent decode
failures at runtime.

### Required variable

| Variable name | Description | Example |
|---|---|---|
| `GOOGLE_CLOUD_PROJECT` | GCP project ID that hosts your Vertex AI endpoint | `my-project-123` |

Create the variable under **Settings > Secrets and variables > Actions > Variables > New repository variable**.

## Optional tuning variables

All tuning variables fall back to safe defaults and do not need to be set
unless you want to override behaviour.

| Variable name | Default | Description |
|---|---|---|
| `GOOGLE_CLOUD_REGION` | `us-central1` | Vertex AI region |
| `AI_REVIEW_MODEL` | `claude-sonnet-4-6` | Model identifier passed to the reviewer |
| `AI_REVIEW_EFFORT` | `medium` | Review depth (`low`, `medium`, `high`) |
| `AI_REVIEW_MAX_TURNS` | `15` | Maximum reasoning turns per review |
| `AI_REVIEW_MAX_BUDGET` | `3.50` | Maximum spend cap per review run (USD) |
| `AI_REVIEW_MAX_DIFF_LINES` | `5000` | Diffs larger than this are skipped |

## Operational notes

- **Non-blocking by default.** The job sets `continue-on-error: true`, so a
  reviewer failure will not block merging. This is intentional; the AI review
  is advisory.
- **Timeout.** The job has a 20-minute hard timeout. Large diffs near the
  `AI_REVIEW_MAX_DIFF_LINES` limit may occasionally time out.
- **Artifacts.** Review results are uploaded to `ci-results/` and retained for
  7 days. Fetch them from the **Actions** tab of the workflow run.
- **Permissions.** The workflow requests `contents: write` and
  `pull-requests: write` so the container can post review comments directly
  on the PR.
- **Credential lifetime.** The decoded service account key is written to
  `/tmp/vertex-sa.json` inside the ephemeral runner and is discarded when the
  job completes. Do not commit `sa.json` to the repository.

## Adding a new Google Cloud project

1. Create or identify a service account with the `Vertex AI User` role in the
   target GCP project.
2. Download a JSON key for that service account.
3. Encode it: `cat sa.json | jq -c '.' | base64 -w0`
4. Store the result as the `VERTEX_SA_JSON` repository secret.
5. Set `GOOGLE_CLOUD_PROJECT` to the correct project ID.
6. Open a test PR — the `AI Code Review` check should appear within a few
   seconds of the workflow starting.
