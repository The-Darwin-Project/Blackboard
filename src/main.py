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

from .dependencies import set_agents, set_blackboard
from .models import HealthResponse
from .routes import (
    chat_router,
    events_router,
    metrics_router,
    plans_router,
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
    redis_client = RedisClient()
    
    try:
        redis = await redis_client.connect()
        logger.info("Redis connection established")
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        logger.warning("Continuing without Redis - some features will be unavailable")
        redis = None
    
    # Initialize Blackboard state
    if redis:
        blackboard = BlackboardState(redis)
        set_blackboard(blackboard)
        logger.info("Blackboard state initialized")
        
        # Initialize agents
        from .agents import Aligner, Architect, SysAdmin
        
        aligner = Aligner(blackboard)
        architect = Architect(blackboard)
        sysadmin = SysAdmin(blackboard)
        
        set_agents(aligner, architect, sysadmin)
        logger.info("Trinity agents initialized (Aligner, Architect, SysAdmin)")
        
        # === CLOSED-LOOP WIRING ===
        # Connect Aligner → Architect for autonomous analysis
        async def architect_anomaly_callback(service: str, anomaly_type: str) -> None:
            """
            Called by Aligner when anomalies are detected.
            
            Triggers Architect to analyze the situation and potentially create a plan.
            """
            try:
                # Build analysis prompt based on anomaly type
                if anomaly_type == "high_cpu":
                    prompt = f"AUTOMATED ALERT: Service '{service}' has high CPU usage. Analyze the situation and recommend actions. Consider scaling, optimization, or investigating the cause."
                elif anomaly_type == "high_memory":
                    prompt = f"AUTOMATED ALERT: Service '{service}' has high memory usage. Analyze the situation and recommend actions. Consider scaling, memory optimization, or investigating memory leaks."
                elif anomaly_type == "high_error_rate":
                    prompt = f"AUTOMATED ALERT: Service '{service}' has a high error rate. Analyze the situation and recommend actions. Consider rollback, failover, or investigating dependencies."
                else:
                    prompt = f"AUTOMATED ALERT: Anomaly detected for service '{service}' ({anomaly_type}). Analyze and recommend actions."
                
                logger.info(f"Architect analyzing anomaly: {service} ({anomaly_type})")
                
                # Call Architect's chat method
                response = await architect.chat(prompt)
                
                if response.plan_id:
                    logger.info(f"Architect created plan {response.plan_id} for {service}")
                else:
                    logger.info(f"Architect analysis complete for {service}: {response.message[:100]}...")
                    
            except Exception as e:
                logger.error(f"Architect anomaly analysis failed: {e}")
        
        aligner.set_architect_callback(architect_anomaly_callback)
        logger.info("Closed-loop wiring complete: Aligner → Architect")
        
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
            
            k8s_observer = KubernetesObserver(
                blackboard=blackboard,
                anomaly_callback=k8s_anomaly_callback,
            )
            await k8s_observer.start()
            logger.info("KubernetesObserver started for external metrics observation")
        else:
            logger.info("KubernetesObserver disabled (K8S_OBSERVER_ENABLED=false)")
    
    logger.info("Darwin Blackboard ready")
    
    yield  # Application runs here
    
    # Cleanup
    logger.info("Darwin Blackboard shutting down...")
    
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
    """
    return HealthResponse(status="brain_online")


# =============================================================================
# Mount Routers
# =============================================================================

app.include_router(telemetry_router)
app.include_router(topology_router)
app.include_router(plans_router)
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
            "plans": {
                "list": "GET /plans/",
                "get": "GET /plans/{id}",
                "approve": "POST /plans/{id}/approve",
                "reject": "POST /plans/{id}/reject",
                "execute": "POST /plans/{id}/execute",
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
