# BlackBoard/src/main.py
"""
Darwin Blackboard (Brain) - FastAPI Application

The central nervous system of Darwin, hosting:
- Blackboard state (Redis-backed)
- Trinity Agents (Aligner, Architect, SysAdmin)
- Two key visualizations (Architecture Graph, Resources Chart)
"""
from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .dependencies import set_agents, set_blackboard, set_brain
from .models import HealthResponse
from .routes import (
    chat_router,
    events_router,
    metrics_router,
    queue_router,
    telemetry_router,
    topology_router,
)
from .state.blackboard import BlackboardState
from .state.redis_client import RedisClient, close_redis
from .observers.kubernetes import KubernetesObserver, K8S_OBSERVER_ENABLED

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.
    
    Initializes Redis connection, Blackboard state, and agents on startup.
    Cleans up connections on shutdown.
    """
    logger.info("Darwin Blackboard starting up...")
    
    # Initialize Redis connection
    # Redis is REQUIRED - without it, the Brain cannot function
    redis_client = RedisClient()
    
    try:
        redis = await redis_client.connect()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"CRITICAL: Failed to connect to Redis: {e}")
        logger.error("Redis is required for Blackboard state. Startup will continue but health checks will fail.")
        redis = None
    
    # Initialize Blackboard state
    if redis:
        blackboard = BlackboardState(redis)
        set_blackboard(blackboard)
        logger.info("Blackboard state initialized")
        
        # Initialize agents (thin HTTP clients to sidecars)
        from .agents import Aligner, Architect, SysAdmin, Developer, Brain
        
        aligner = Aligner(blackboard)
        architect = Architect()
        sysadmin = SysAdmin()
        developer = Developer()
        
        set_agents(aligner, architect, sysadmin, developer)
        logger.info("Agents initialized (Aligner, Architect, SysAdmin, Developer)")
        
        # Initialize Brain orchestrator
        brain = Brain(blackboard)
        set_brain(brain)
        logger.info("Brain orchestrator initialized")
        
        # Start Brain event loop (replaces old agent task loops)
        import asyncio
        
        asyncio.create_task(brain.start_event_loop())
        logger.info("Brain event loop started - conversation queue active")
        
        # === KUBERNETES OBSERVER ===
        # External observation for CPU/memory metrics
        k8s_observer = None
        if K8S_OBSERVER_ENABLED:
            # Create anomaly callback that calls Aligner's threshold check
            async def k8s_anomaly_callback(
                service: str, cpu: float, memory: float, source: str
            ) -> None:
                """Called by K8sObserver with metrics from metrics-server."""
                await aligner.check_anomalies_for_service(service, cpu, memory, source)
            
            # Pod health callback for unhealthy states (ImagePullBackOff, CrashLoopBackOff, etc.)
            async def k8s_pod_health_callback(
                service: str, pod_name: str, reason: str
            ) -> None:
                """Called by K8sObserver when unhealthy pod states are detected."""
                await aligner.handle_unhealthy_pod(service, pod_name, reason)
            
            k8s_observer = KubernetesObserver(
                blackboard=blackboard,
                anomaly_callback=k8s_anomaly_callback,
                pod_health_callback=k8s_pod_health_callback,
            )
            await k8s_observer.start()
            logger.info("KubernetesObserver started for external metrics observation")
        else:
            logger.info("KubernetesObserver disabled (K8S_OBSERVER_ENABLED=false)")
    
    logger.info("Darwin Blackboard ready")
    
    yield  # Application runs here
    
    # Cleanup
    logger.info("Darwin Blackboard shutting down...")
    
    # Stop Brain event loop
    if redis:
        await brain.stop_event_loop()
        logger.info("Brain event loop stopped")
    
    # Stop K8s observer
    if redis and K8S_OBSERVER_ENABLED and k8s_observer:
        await k8s_observer.stop()
        logger.info("KubernetesObserver stopped")
    
    await close_redis()
    logger.info("Redis connection closed")


# Create FastAPI application
app = FastAPI(
    title="Darwin Blackboard",
    description="The central nervous system of Darwin - autonomous infrastructure management",
    version="1.0.0",
    lifespan=lifespan,
)


# =============================================================================
# Health Endpoint
# =============================================================================

@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """
    Health check endpoint for liveness/readiness probes.
    
    Returns {"status": "brain_online"} when the Brain is operational.
    Returns 503 Service Unavailable if Blackboard is not initialized.
    """
    from .dependencies import _blackboard
    
    if _blackboard is None:
        from fastapi import HTTPException
        raise HTTPException(
            status_code=503,
            detail="Blackboard not initialized - Redis connection may have failed"
        )
    
    return HealthResponse(status="brain_online")


# =============================================================================
# Mount Routers
# =============================================================================

app.include_router(telemetry_router)
app.include_router(topology_router)
app.include_router(queue_router)
app.include_router(metrics_router)
app.include_router(chat_router)
app.include_router(events_router)


# =============================================================================
# API Info
# =============================================================================

@app.get("/info", tags=["info"])
async def api_info() -> dict:
    """Get API information and available endpoints."""
    return {
        "name": "Darwin Blackboard",
        "version": "1.0.0",
        "description": "Central nervous system for autonomous infrastructure management",
        "endpoints": {
            "health": "GET /health",
            "telemetry": "POST /telemetry/",
            "topology": {
                "list": "GET /topology/",
                "mermaid": "GET /topology/mermaid",
                "services": "GET /topology/services",
            },
            "queue": {
                "active": "GET /queue/active",
                "get": "GET /queue/{event_id}",
                "approve": "POST /queue/{event_id}/approve",
                "closed": "GET /queue/closed/list",
            },
            "metrics": {
                "current": "GET /metrics/{service}",
                "history": "GET /metrics/{service}/history",
                "chart": "GET /metrics/chart",
            },
            "chat": "POST /chat/",
            "events": "GET /events/",
        },
        "visualizations": {
            "architecture_graph": "GET /topology/mermaid",
            "resources_chart": "GET /metrics/chart",
        },
        "ui": "GET / (React Dashboard)",
    }


# =============================================================================
# Static Files (React SPA) - MUST be mounted LAST
# =============================================================================
# Mount at root so UI is served at / while API routes take precedence
static_dir = Path(__file__).parent.parent / "ui" / "dist"
if static_dir.exists():
    app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
