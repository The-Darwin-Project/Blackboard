<!-- Proposal: add one row to the Documentation table in the project README.
     Insert after the existing "docs/deployment.md" row (line ~164 in the
     original README.md). No other content should change. -->

## Patch: Documentation table addition

In the **Documentation** section of `README.md`, add the following row to the
table after the `docs/deployment.md` row:

```markdown
| [docs/ai-review.md](docs/ai-review.md) | AI code review workflow: required secrets, tuning variables, operational notes |
```

### Rationale

The new `.github/workflows/ai-review.yaml` file is not mentioned anywhere in
the project docs. Contributors who set up a fork or a new environment have no
documented path to configure `VERTEX_SA_JSON` (including its non-obvious
encoding requirement) or `GOOGLE_CLOUD_PROJECT`. The detail belongs in a
dedicated sub-doc (`docs/ai-review.md`) consistent with the project's existing
pattern of keeping detailed content out of the README and linking to `docs/`.
