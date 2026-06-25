# BlackBoard/src/state/__init__.py
# @ai-rules:
# 1. [Pattern]: Re-exports BlackboardState (facade) + 6 domain Protocol ports.
# 2. [Constraint]: No implementation logic — only re-exports.
"""State management layer for Darwin Blackboard."""
from .blackboard import BlackboardState
from .ports import (
    EscalationRepository,
    EventRepository,
    MetricsRepository,
    ObservationRepository,
    ScheduleRepository,
    TopologyRepository,
)
from .redis_client import get_redis, RedisClient

__all__ = [
    "BlackboardState",
    "EscalationRepository",
    "EventRepository",
    "MetricsRepository",
    "ObservationRepository",
    "ScheduleRepository",
    "TopologyRepository",
    "get_redis",
    "RedisClient",
]
