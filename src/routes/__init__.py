# BlackBoard/src/routes/__init__.py
"""API routes for Darwin Blackboard."""
from .chat import router as chat_router
from .events import router as events_router
from .metrics import router as metrics_router
from .plans import router as plans_router
from .telemetry import router as telemetry_router
from .topology import router as topology_router

__all__ = [
    "chat_router",
    "events_router",
    "metrics_router",
    "plans_router",
    "telemetry_router",
    "topology_router",
]
