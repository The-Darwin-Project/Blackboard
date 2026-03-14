# BlackBoard/src/routes/__init__.py
"""API routes for Darwin Blackboard."""
from .chat import router as chat_router
from .events import router as events_router
from .feedback import router as feedback_router
from .metrics import router as metrics_router
from .queue import router as queue_router
from .reports import router as reports_router
from .telemetry import router as telemetry_router
from .topology import router as topology_router
from .dex_proxy import router as dex_proxy_router
from .timekeeper import router as timekeeper_router

__all__ = [
    "chat_router",
    "dex_proxy_router",
    "events_router",
    "feedback_router",
    "metrics_router",
    "queue_router",
    "reports_router",
    "telemetry_router",
    "timekeeper_router",
    "topology_router",
]
