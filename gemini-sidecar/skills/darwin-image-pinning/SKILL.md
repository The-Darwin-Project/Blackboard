---
name: darwin-image-pinning
description: Container image reference format and pinning conventions. Activates when updating FROM lines, image tags, or base image references in Dockerfiles, build-args, or PipelineRun params.
roles: [developer, sysadmin]
modes: [implement, execute]
---

# Image Pinning Convention

## Format

All container image references MUST include both a human-readable tag AND a digest:

```
<registry>/<repository>:<tag>@<digest>
```

The tag provides readability (which version). The digest provides immutability (exactly which build). A tag alone is a floating pointer that can change underneath you. A digest alone is immutable but unreadable.

## When Updating Image References

1. Determine the new tag from the task instruction or maintainer authorization
2. Resolve the digest for that tag (pull the manifest, extract the sha256)
3. Write the full pinned reference: `<registry>/<repo>:<new_tag>@sha256:<hash>`
4. Update ALL components in the repository that reference the old tag

## Where Image References Live

Image references appear in multiple locations depending on the repository structure:

- `Dockerfile` / `Containerfile` -- `FROM` lines
- `build-args.conf` -- build-time argument overrides
- `.tekton/*.yaml` -- PipelineRun param values
- `kustomization.yaml` -- `newTag` / `newName` fields

When updating, grep the entire repository for the old tag to find all occurrences. A partial update (some files pinned, others still floating) breaks reproducibility.

## Verification

After updating, confirm:
- The digest resolves (the image exists at that digest in the registry)
- All references in the repo are consistent (same tag + digest everywhere)
- No floating tags remain for the same image
