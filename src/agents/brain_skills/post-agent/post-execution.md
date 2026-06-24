---
description: "Post-execution verification method selection"
tags: [verification, post-execution]
---
# Post-Execution: When to Close vs Verify

Different change types produce different observable signals — using the wrong verification method either wastes a dispatch cycle (routing an agent to check what metrics already show) or misses the change entirely (expecting metrics to reflect a non-metric config change). Match the verification method to the signal type.

- After a **code change** (developer pushes a commit): a committed change doesn't exist in production until the CI/CD pipeline builds, pushes, and deploys it. Wait for CI/CD pipeline, then route sysAdmin to validate the deployment -- verify the running pod image matches the commit, ArgoCD sync succeeded, and any post-deploy tests pass.
- After a **metric-observable infrastructure change** (scaling replicas, adjusting resource limits): these changes produce measurable signals the Aligner already monitors. Verify the new state via the Aligner's metric observations.
- After a **non-metric config change** (removing secrets, updating annotations, labels): these changes don't produce metric signals — the Aligner can't see them. Route sysAdmin to verify via cluster investigation (check events, pod state).

Without a post-fix measurement, Deep Memory has no concrete improvement signal for future events — it knows the fix was applied but not whether it worked. After verification confirms the fix, call record_observation with the post-fix
metric value (replica count, error rate delta, build duration). This closes the
before/after loop.
