---
description: "Post-execution verification method selection"
tags: [verification, post-execution]
---
# Post-Execution: When to Close vs Verify

- After a **code change** (developer pushes a commit): wait for CI/CD pipeline, then route sysAdmin to validate the deployment -- verify the running pod image matches the commit, ArgoCD sync succeeded, and any post-deploy tests pass.
- After a **metric-observable infrastructure change** (scaling replicas, adjusting resource limits): verify the new state via the Aligner's metric observations.
- After a **non-metric config change** (removing secrets, updating annotations, labels): route sysAdmin to verify via cluster investigation (check events, pod state). Non-metric changes are not observable via metrics.
