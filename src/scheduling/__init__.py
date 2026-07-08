# src/scheduling/__init__.py
# @ai-rules:
# 1. [Constraint]: This package is a scheduling primitive -- no Brain logic, no Redis, no LLM.
# 2. [Pattern]: Exports ReconcileScheduler as the public API. Triggers are registered externally.
# 3. [Pattern]: StateWatcher provides background polling for deferred event state changes.
"""Fair event scheduling for the Darwin Brain."""

from .reconciler import ReconcileScheduler, FairQueue
from .triggers import QueueTrigger, ResyncTrigger, StalenessGuard
from .idle_timeout import IdleTimeoutManager
from .state_watcher import (
    StateWatcher, SubscriptionSpec, GitLabMrRef, KargoStageRef, GitHubPrRef, PollFn,
)

__all__ = [
    "ReconcileScheduler",
    "FairQueue",
    "QueueTrigger",
    "ResyncTrigger",
    "StalenessGuard",
    "IdleTimeoutManager",
    "StateWatcher",
    "SubscriptionSpec",
    "GitLabMrRef",
    "KargoStageRef",
    "GitHubPrRef",
    "PollFn",
]
