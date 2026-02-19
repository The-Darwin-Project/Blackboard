---
description: "Post-execution verification method selection"
tags: [verification, post-execution]
---
# Post-Execution: When to Close vs Verify

- After a **code change** (developer pushes a commit with SHA): wait for CI/CD, then route sysAdmin to verify the pod's image tag matches the commit SHA.
- After a **metric-observable infrastructure change** (scaling replicas, adjusting resource limits): use re_trigger_aligner to verify the new state.
- After a **non-metric config change** (removing secrets, updating annotations, labels, imagePullSecrets): route sysAdmin to verify via kubectl/oc (check events, pod YAML). Do NOT use re_trigger_aligner -- these changes are not observable via metrics.
- re_trigger_aligner is ONLY for metric-observable changes (replicas, CPU, memory).
