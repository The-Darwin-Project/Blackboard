# BlackBoard/src/routes/__init__.py
"""API routes for Darwin Blackboard."""
from .telemetry import router as telemetry_router
from .topology import router as topology_router
from .plans import router as plans_router
from .metrics import router as metrics_router
from .chat import router as chat_router

__all__ = [
    "telemetry_router",
    "topology_router",
    "plans_router",
    "metrics_router",
    "chat_router",
]
