---
name: darwin-dockerfile-safety
description: Safety rules for modifying Dockerfiles and Containerfiles. Use when editing container build files.
roles: [sysadmin, developer]
modes: [implement, execute]
---

# Dockerfile Safety Rules

## Allowed Modifications

You MAY add:

- `ARG` -- build arguments
- `ENV` -- environment variables
- `COPY` -- copy files into the image
- `RUN` -- install packages or run build commands
- `EXPOSE` -- declare ports

## Forbidden Modifications

You MUST NOT add or change:

- `FROM` -- base image (changing this breaks the build chain)
- `CMD` / `ENTRYPOINT` -- the container's startup command
- `USER` -- the runtime user (security context). Adding a USER directive to a Dockerfile that lacks one is also a security-sensitive change.
- `WORKDIR` -- the working directory

You MUST NOT remove:

- Existing `COPY`, `RUN`, or `CMD` lines
- Running processes from `CMD` (e.g., removing a sidecar process)

## When to Stop

If a task requires changing `FROM`, `CMD`, `USER`, or `WORKDIR`, **stop immediately**.
Do not apply the fix, even if the pipeline failure is clear and the change seems safe.

Report to FRIDAY:

- What change is needed and why (e.g., "preflight RunAsNonRoot requires USER directive")
- That the change falls under the Dockerfile forbidden modifications list
- Recommend Architect review before proceeding

**Example**: A preflight certification check fails with `RunAsNonRoot` and `HasLicense`.
The fix is to add `USER 1001` and a `/licenses` directory. Adding the `/licenses` COPY
is allowed (COPY is in the allowed list). Adding `USER 1001` is NOT — it is a
security-context change that requires Architect review. In this case: apply the
allowed COPY fix, but halt on the forbidden USER change. Report both findings to
FRIDAY — what you applied and what requires Architect review before proceeding.

These restrictions exist because `FROM`, `CMD`, `USER`, and `WORKDIR` changes alter
the security posture or execution contract of the container. Source mutation approval
applies — see FRIDAY's execution-method rules.
