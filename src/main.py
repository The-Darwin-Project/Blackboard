# BlackBoard/src/main.py
# @ai-rules:
# 1. [Pattern]: clear_waiting(event_id) called in both user_message and approve WS branches.
# 2. [Gotcha]: Brain instance accessed via app.state.brain, guarded by hasattr check.
# 3. [Constraint]: Static files mount MUST be last -- API routes take precedence.
# 4. [Pattern]: emergency_stop WS handler cancels all active tasks and responds with cancelled count.
# 5. [Pattern]: Slack channel init is conditional on SLACK_BOT_TOKEN + SLACK_APP_TOKEN env vars. Graceful degradation if missing.
# 6. [Pattern]: /agent/ws endpoint delegates to agent_ws_handler.py. Registry + Bridge on app.state, initialized in lifespan().
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

from .dependencies import set_agents, set_archivist, set_blackboard, set_brain, set_registry_and_bridge
from .models import HealthResponse
from .routes import (
    chat_router,
    events_router,
    feedback_router,
    metrics_router,
    queue_router,
    reports_router,
    telemetry_router,
    topology_router,
)
from .state.blackboard import BlackboardState
from .state.redis_client import RedisClient, close_redis
from .observers.kubernetes import KubernetesObserver, K8S_OBSERVER_ENABLED
from .agents.agent_registry import AgentRegistry
from .agents.task_bridge import TaskBridge
from .agents.agent_ws_handler import agent_websocket_handler

# Configure logging
logging.basicConfig(
    level=logging.DEBUG if os.getenv("DEBUG") else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Squelch noisy loggers that pollute Brain output
for noisy in (
    "kubernetes.client.rest", "urllib3.connectionpool",
    "slack_bolt", "slack_bolt.AsyncApp", "slack_bolt.IgnoringSelfEvents",
    "slack_sdk", "slack_sdk.socket_mode", "slack_sdk.web.async_client",
):
    logging.getLogger(noisy).setLevel(logging.WARNING)

# WebSocket logger: keep agent TEXT frames, drop PING/PONG/CLOSE/EOF noise
class _WSFrameFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        return "TEXT" in msg or "text" in msg
_ws_logger = logging.getLogger("websockets.client")
_ws_logger.addFilter(_WSFrameFilter())


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
        from .agents import Aligner, Archivist, Architect, SysAdmin, Developer, Brain
        import asyncio
        
        aligner = Aligner(blackboard)
        archivist = Archivist()
        set_archivist(archivist)
        architect = Architect()
        sysadmin = SysAdmin()
        developer = Developer()
        
        # Connect agent WebSocket clients (legacy mode only -- sidecars connect to Brain in reverse mode)
        ws_mode = os.getenv("AGENT_WS_MODE", "legacy")
        if ws_mode != "reverse":
            await architect.connect()
            await sysadmin.connect()
            await developer.connect()
        
        set_agents(aligner, architect, sysadmin, developer)
        logger.info(f"Agents initialized (ws_mode={ws_mode})")
        
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
                "_archivist_memory": archivist,  # Deep memory archiver (Qdrant)
            },
            broadcast=broadcast_to_ui,
        )
        set_brain(brain)
        # Store connected_clients on app state for the WS endpoint
        app.state.connected_ui_clients = connected_ui_clients
        app.state.brain = brain
        logger.info("Brain orchestrator initialized with WebSocket agents + broadcast")
        
        # Initialize Agent Registry + TaskBridge (Phase A -- additive, no dispatch changes yet)
        agent_registry = AgentRegistry()
        task_bridge = TaskBridge()
        agent_registry.set_task_orphaned_callback(task_bridge.put_error)
        app.state.agent_registry = agent_registry
        app.state.task_bridge = task_bridge
        set_registry_and_bridge(agent_registry, task_bridge)
        logger.info("AgentRegistry + TaskBridge initialized")
        
        # Start Brain event loop
        asyncio.create_task(brain.start_event_loop())
        logger.info("Brain event loop started - WebSocket conversation queue active")
        
        # === SLACK CHANNEL ===
        # Bidirectional Slack integration via Socket Mode (conditional on env vars)
        slack_bot_token = os.getenv("SLACK_BOT_TOKEN", "")
        slack_app_token = os.getenv("SLACK_APP_TOKEN", "")
        if slack_bot_token and slack_app_token:
            from .channels.slack import SlackChannel
            slack = SlackChannel(
                bot_token=slack_bot_token,
                app_token=slack_app_token,
                infra_channel=os.getenv("SLACK_INFRA_CHANNEL", ""),
                mr_fallback_channel=os.getenv("SLACK_MR_CHANNEL", ""),
                blackboard=blackboard,
                brain=brain,
            )
            brain.register_channel(slack.broadcast_handler)
            await slack.start()
            app.state.slack = slack
            logger.info("Slack channel started (Socket Mode)")
        else:
            logger.info("Slack channel disabled (SLACK_BOT_TOKEN/SLACK_APP_TOKEN not set)")
        
        # === KUBERNETES OBSERVER ===
        # External observation for CPU/memory metrics
        k8s_observer = None
        if K8S_OBSERVER_ENABLED:
            # Create anomaly callback that calls Aligner's threshold check
            async def k8s_anomaly_callback(
                service: str, cpu: float, memory: float, source: str,
                error_rate: float = 0.0,
            ) -> None:
                """Called by K8sObserver with metrics from metrics-server."""
                await aligner.check_anomalies_for_service(
                    service, cpu, memory, source, error_rate=error_rate,
                )
            
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
    
    # Stop Slack channel
    if hasattr(app.state, "slack"):
        await app.state.slack.stop()
        logger.info("Slack channel stopped")
    
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
# Public Configuration (AI Transparency & Compliance)
# =============================================================================

@app.get("/config", tags=["config"])
async def get_config() -> dict:
    """Public configuration for the UI (no secrets)."""
    return {
        "contactEmail": os.getenv("DARWIN_CONTACT_EMAIL", ""),
        "feedbackFormUrl": os.getenv("DARWIN_FEEDBACK_FORM_URL", ""),
        "appVersion": os.getenv("APP_VERSION", "1.0.0"),
    }


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
    # TODO(dex): user = get_user_from_websocket(websocket); pass user.label to ConversationTurn(user_name=...)
    
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
                from .models import ConversationTurn, EventEvidence
                if _blackboard:
                    message = data.get("message", "")
                    service = data.get("service", "general")
                    event_id = await _blackboard.create_event(
                        source="chat",
                        service=service,
                        reason=message,
                        evidence=EventEvidence(
                            display_text=message,
                            source_type="chat",
                            domain="complicated",
                            severity="info",
                        ),
                    )
                    # Extract optional image (with size guard)
                    image = data.get("image")
                    if image and len(image) > 1_400_000:
                        await websocket.send_json({"type": "error", "message": "Image too large (max 1MB). Image was not attached."})
                        image = None
                    # Add user message as the first conversation turn
                    user_turn = ConversationTurn(
                        turn=1,
                        actor="user",
                        action="message",
                        thoughts=message,
                        image=image,
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
                image = data.get("image")
                if image and len(image) > 1_400_000:
                    await websocket.send_json({"type": "error", "message": "Image too large (max 1MB). Image was not attached."})
                    image = None
                if _blackboard and event_id and message:
                    event = await _blackboard.get_event(event_id)
                    if event:
                        turn = ConversationTurn(
                            turn=len(event.conversation) + 1,
                            actor="user",
                            action="message",
                            thoughts=message,
                            image=image,
                        )
                        await _blackboard.append_turn(event_id, turn)
                        # Clear wait_for_user state so Brain re-processes
                        if hasattr(app.state, 'brain'):
                            app.state.brain.clear_waiting(event_id)
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
                        # Clear wait_for_user state so Brain re-processes
                        if hasattr(app.state, 'brain'):
                            app.state.brain.clear_waiting(event_id)
                        await websocket.send_json({
                            "type": "turn",
                            "event_id": event_id,
                            "turn": turn.model_dump(),
                        })
                        logger.info(f"WS approval for event: {event_id}")

            elif msg_type == "emergency_stop":
                # Master kill switch: cancel ALL active agent tasks
                if hasattr(app.state, 'brain'):
                    cancelled = await app.state.brain.emergency_stop()
                    await websocket.send_json({
                        "type": "emergency_stop_ack",
                        "cancelled": cancelled,
                    })
                    logger.critical(f"WS emergency stop: {cancelled} tasks cancelled")
                else:
                    await websocket.send_json({
                        "type": "emergency_stop_ack",
                        "cancelled": 0,
                    })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        clients.discard(websocket)
        logger.info(f"UI WebSocket disconnected ({len(clients)} clients)")


# =============================================================================
# Agent WebSocket Endpoint (sidecar connections -- reversed WS direction)
# =============================================================================

@app.websocket("/agent/ws")
async def agent_ws_endpoint(websocket: WebSocket):
    """WebSocket endpoint for agent sidecar connections (reverse mode)."""
    registry = getattr(app.state, 'agent_registry', None)
    bridge = getattr(app.state, 'task_bridge', None)
    if not registry or not bridge:
        await websocket.close(code=1013, reason="Registry not initialized")
        return
    await agent_websocket_handler(websocket, registry, bridge)


# =============================================================================
# Agent Registry REST Endpoint
# =============================================================================

@app.get("/api/agents", tags=["agents"])
async def list_agents() -> list[dict]:
    """Connected agent sidecars with role, status, and current event."""
    registry = getattr(app.state, "agent_registry", None)
    if not registry:
        return []
    return await registry.list_agents()


# =============================================================================
# Mount Routers
# =============================================================================

app.include_router(telemetry_router)
app.include_router(topology_router)
app.include_router(queue_router)
app.include_router(metrics_router)
app.include_router(chat_router)
app.include_router(events_router)
app.include_router(feedback_router)
app.include_router(reports_router)


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
