---
description: "Aligner-sourced event behavior and autonomous close rules"
tags: [aligner, autonomous]
---
# Aligner Source Rules

## Autonomous Detection

- Aligner-sourced events are autonomous detections with no user in the conversation.
- Close after state verification confirms recovery. No user confirmation needed.

## Detection Model (ArgoCD-Based)

The Aligner detects two classes of anomaly from ArgoCD Application status:
- **Health degradation**: ArgoCD reports `Degraded` or `Missing` health on a Deployment resource.
- **Sync drift**: ArgoCD Application with `spec.syncPolicy.automated` enabled stays `OutOfSync` for >60 seconds (transient drift during normal deploys is filtered).

## Aligner Close Protocol

- For health degradation events: close once ArgoCD reports the resource as `Healthy` again. The Aligner itself sends a recovery notification to the event conversation when this occurs.
- For sync drift events: close once ArgoCD reports the Application as `Synced`.
- For Kargo promotion failures: the promotion state alone ("Failed") does not distinguish between an active failure and a stale failure whose cause has resolved. When the investigation attributes the failure to an external cause (outage, maintenance window), that cause may have its own recovery timeline.
- No user confirmation needed -- the Aligner detected it autonomously.
