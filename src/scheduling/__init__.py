# src/scheduling/__init__.py
# @ai-rules:
# 1. [Constraint]: This package is a scheduling primitive -- no Brain logic, no Redis, no LLM.
# 2. [Pattern]: Exports ReconcileScheduler as the public API. Triggers are registered externally.
"""Fair event scheduling for the Darwin Brain."""

from .reconciler import ReconcileScheduler, FairQueue
from .triggers import QueueTrigger, ResyncTrigger, StalenessGuard

__all__ = [
    "ReconcileScheduler",
    "FairQueue",
    "QueueTrigger",
    "ResyncTrigger",
    "StalenessGuard",
]
