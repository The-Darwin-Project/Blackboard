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

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
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
        
        # Initialize agents (WebSocket clients to sidecars)
        from .agents import Aligner, Architect, SysAdmin, Developer, Brain
        import asyncio
        
        aligner = Aligner(blackboard)
        architect = Architect()
        sysadmin = SysAdmin()
        developer = Developer()
        
        # Connect agent WebSocket clients (async with retry)
        await architect.connect()
        await sysadmin.connect()
        await developer.connect()
        
        set_agents(aligner, architect, sysadmin, developer)
        logger.info("Agents initialized + WebSocket connected (Aligner, Architect, SysAdmin, Developer)")
        
        # UI WebSocket broadcast function (wired in Step 4)
        # For now, a no-op until the /ws endpoint is added
        connected_ui_clients: set = set()
        
        async def broadcast_to_ui(message: dict) -> None:
            """Push message to all connected UI WebSocket clients."""
            import json as _json
            data = _json.dumps(message)
            disconnected = set()
            for client in connected_ui_clients:
                try:
                    await client.send_text(data)
                except Exception:
                    disconnected.add(client)
            # Use difference_update (in-place mutation) to avoid reassignment
            # which would break the closure over connected_ui_clients
            connected_ui_clients.difference_update(disconnected)
        
        # Initialize Brain orchestrator with agents + broadcast
        brain = Brain(
            blackboard=blackboard,
            agents={
                "architect": architect,
                "sysadmin": sysadmin,
                "developer": developer,
                "_aligner": aligner,  # In-process agent for verification checks
            },
            broadcast=broadcast_to_ui,
        )
        set_brain(brain)
        # Store connected_clients on app state for the WS endpoint
        app.state.connected_ui_clients = connected_ui_clients
        app.state.brain = brain
        logger.info("Brain orchestrator initialized with WebSocket agents + broadcast")
        
        # Start Brain event loop
        asyncio.create_task(brain.start_event_loop())
        logger.info("Brain event loop started - WebSocket conversation queue active")
        
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
    
    # Stop Brain event loop + close agent WebSocket connections
    if redis:
        await brain.stop_event_loop()
        await architect.close()
        await sysadmin.close()
        await developer.close()
        logger.info("Brain event loop stopped, agent WebSocket connections closed")
    
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
# WebSocket Endpoint (UI real-time communication)
# =============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time UI communication.
    
    Receives: chat messages, approval actions
    Sends: conversation turns, progress updates, event lifecycle
    """
    await websocket.accept()
    
    # Add to connected clients (set stored on app.state during lifespan)
    clients = getattr(app.state, 'connected_ui_clients', set())
    clients.add(websocket)
    logger.info(f"UI WebSocket connected ({len(clients)} clients)")
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "chat":
                # Create event from chat message
                from .dependencies import _blackboard
                from .models import ConversationTurn
                if _blackboard:
                    message = data.get("message", "")
                    service = data.get("service", "general")
                    event_id = await _blackboard.create_event(
                        source="chat",
                        service=service,
                        reason=message,
                        evidence="User request via WebSocket chat",
                    )
                    # Add user message as the first conversation turn
                    user_turn = ConversationTurn(
                        turn=1,
                        actor="user",
                        action="message",
                        thoughts=message,
                    )
                    await _blackboard.append_turn(event_id, user_turn)
                    await websocket.send_json({
                        "type": "event_created",
                        "event_id": event_id,
                        "service": service,
                        "reason": message,
                    })
                    logger.info(f"WS chat event created: {event_id}")
                    
            elif msg_type == "user_message":
                # Add user message to an existing event conversation
                from .dependencies import _blackboard
                from .models import ConversationTurn
                event_id = data.get("event_id", "")
                message = data.get("message", "")
                if _blackboard and event_id and message:
                    event = await _blackboard.get_event(event_id)
                    if event:
                        turn = ConversationTurn(
                            turn=len(event.conversation) + 1,
                            actor="user",
                            action="message",
                            thoughts=message,
                        )
                        await _blackboard.append_turn(event_id, turn)
                        await websocket.send_json({
                            "type": "turn",
                            "event_id": event_id,
                            "turn": turn.model_dump(),
                        })
                        logger.info(f"WS user message added to event: {event_id}")

            elif msg_type == "approve":
                from .dependencies import _blackboard
                from .models import ConversationTurn
                event_id = data.get("event_id", "")
                if _blackboard and event_id:
                    event = await _blackboard.get_event(event_id)
                    if event:
                        turn = ConversationTurn(
                            turn=len(event.conversation) + 1,
                            actor="user",
                            action="approve",
                            thoughts="User approved the plan.",
                        )
                        await _blackboard.append_turn(event_id, turn)
                        await websocket.send_json({
                            "type": "turn",
                            "event_id": event_id,
                            "turn": turn.model_dump(),
                        })
                        logger.info(f"WS approval for event: {event_id}")
                        
    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        clients.discard(websocket)
        logger.info(f"UI WebSocket disconnected ({len(clients)} clients)")


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
