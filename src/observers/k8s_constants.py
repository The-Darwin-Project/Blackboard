# BlackBoard/src/observers/k8s_constants.py
# @ai-rules:
# 1. [Pattern]: Single source of truth for K8s health constants shared by observer + spawn adapter.
# 2. [Constraint]: Zero agent imports — safe for src/adapters/ to import (no __init__.py chain).
# 3. [Constraint]: Pure data types only — no K8s client, no Redis, no async.
"""
Shared Kubernetes constants and spawn-related types.

Extracted from KubernetesObserver to break the import boundary:
src/adapters/spawn_health.py needs UNHEALTHY_STATES but cannot
import src/agents/ (triggers full agent package load).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


UNHEALTHY_STATES: frozenset[str] = frozenset({
    "ImagePullBackOff",
    "ErrImagePull",
    "CrashLoopBackOff",
    "OOMKilled",
    "Error",
    "CreateContainerError",
})

PENDING_THRESHOLD_SECONDS: int = 300


class SpawnStatus(str, Enum):
    """Pod lifecycle status for ephemeral agent spawn tracking."""
    MISSING = "missing"
    PENDING = "pending"
    RUNNING = "running"
    FAILED = "failed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SpawnPollResult:
    """Result of a single pod health poll."""
    status: SpawnStatus
    reason: str = ""
    pod_name: str = ""
