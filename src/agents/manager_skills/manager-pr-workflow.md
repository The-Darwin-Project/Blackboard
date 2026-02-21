# Manager PR Workflow

After `approve_and_merge`, the developer executes the PR phase.

## Sequence

1. Create feature branch
2. Commit changes
3. Push branch
4. Open PR
5. Wait for pipeline
6. If green → merge
7. Report final PR URL and merge status via `report_to_brain`

## Pipeline Failures

- Developer fixes the issue, pushes, retries (up to 2 attempts)
- If merge fails after retries: report `status=partial` with the PR URL for manual intervention
