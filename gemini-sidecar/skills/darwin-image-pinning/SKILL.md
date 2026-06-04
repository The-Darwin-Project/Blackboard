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

1. **Read the existing pattern first.** Check how the current image reference is structured
   in the file before changing it. Match the existing convention:
   - If the repo uses `tag@sha256:digest` -- keep that format
   - If the repo uses git-SHA-based tags (e.g., `:a1b2c3d`) -- use the same SHA format
   - If the repo uses semantic version tags (e.g., `:v1.26.0`) -- use semver
   - If the repo uses stream tags (e.g., `:rhel_9_1.26`) -- use the same stream pattern
2. Determine the new tag from the task instruction or maintainer authorization
3. If the existing pattern includes a digest, resolve the digest for the new tag
4. Write the reference matching the repo's established format
5. Update ALL components in the repository that reference the old tag

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
