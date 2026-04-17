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

from .dependencies import set_agents, set_archivist, set_blackboard, set_brain, set_kargo_observer, set_registry_and_bridge
from .models import FlowMetricsResponse, HealthResponse
from .routes import (
    chat_router,
    dex_proxy_router,
    events_router,
    feedback_router,
    incidents_router,
    journal_router,
    kargo_router,
    metrics_router,
    queue_router,
    reports_router,
    telemetry_router,
    timekeeper_router,
    topology_router,
)
from .auth import DEX_ENABLED, set_oidc_adapter
from .state.blackboard import BlackboardState
from .state.redis_client import RedisClient, close_redis
from .observers.kubernetes import KubernetesObserver, K8S_OBSERVER_ENABLED
from .observers.kargo import KargoObserver, KARGO_OBSERVER_ENABLED
from .observers.timekeeper import TimeKeeperObserver, TIMEKEEPER_ENABLED
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
        
        # Initialize Brain orchestrator (no broadcast in constructor -- registered via adapters)
        brain = Brain(
            blackboard=blackboard,
            agents={
                "architect": architect,
                "sysadmin": sysadmin,
                "developer": developer,
                "_aligner": aligner,
                "_archivist_memory": archivist,
            },
        )
        set_brain(brain)
        app.state.brain = brain

        # Dashboard WebSocket adapter (implements BroadcastPort)
        # kargo_observer may not exist yet; attached after Kargo init below
        from .adapters.dashboard_ws import DashboardWSAdapter
        dashboard_adapter = DashboardWSAdapter(brain=brain, blackboard=blackboard, auth_enabled=DEX_ENABLED)
        brain.register_channel(dashboard_adapter)
        app.state.dashboard_adapter = dashboard_adapter
        logger.info("Brain orchestrator initialized with Dashboard WS adapter")
        
        # Initialize Agent Registry + TaskBridge (Phase A -- additive, no dispatch changes yet)
        agent_registry = AgentRegistry()
        task_bridge = TaskBridge()
        agent_registry.set_task_orphaned_callback(task_bridge.put_error)
        app.state.agent_registry = agent_registry
        app.state.task_bridge = task_bridge
        set_registry_and_bridge(agent_registry, task_bridge)
        logger.info("AgentRegistry + TaskBridge initialized")

        el_url = os.getenv("TEKTON_EVENTLISTENER_URL", "")
        if el_url:
            from .agents.ephemeral_provisioner import EphemeralProvisioner
            provisioner = EphemeralProvisioner(
                registry=agent_registry,
                event_listener_url=el_url,
            )
            agent_registry.set_ephemeral_registered_callback(provisioner.on_ephemeral_registered)
            brain._ephemeral_provisioner = provisioner
            logger.info("EphemeralProvisioner initialized (url=%s)", el_url)
        
        # === DEX OIDC Key Adapter ===
        if DEX_ENABLED:
            from .adapters.oidc_adapter import OIDCKeyAdapter
            dex_internal_url = os.getenv("DEX_INTERNAL_URL", "")
            oidc_adapter = OIDCKeyAdapter(f"{dex_internal_url}/dex/keys")
            await oidc_adapter.start()
            set_oidc_adapter(oidc_adapter)
            app.state.oidc_adapter = oidc_adapter

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
        
        # === HEADHUNTER (GitLab Todo Poller) ===
        headhunter_task = None
        headhunter_enabled = os.getenv("HEADHUNTER_ENABLED", "false").lower() == "true"
        gitlab_host = os.getenv("GITLAB_HOST", "")
        if headhunter_enabled and gitlab_host:
            from .agents.headhunter import Headhunter
            close_signal = asyncio.Event()
            brain._headhunter_close_signal = close_signal
            headhunter = Headhunter(blackboard, close_signal=close_signal)
            brain.agents["_headhunter"] = headhunter
            headhunter_task = asyncio.create_task(headhunter.run())
            logger.info("Headhunter started (GitLab todo poller)")
        else:
            if headhunter_enabled and not gitlab_host:
                logger.warning("HEADHUNTER_ENABLED=true but GITLAB_HOST not set -- Headhunter disabled")
            else:
                logger.info("Headhunter disabled (HEADHUNTER_ENABLED=false)")
        
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
        
        # === KARGO OBSERVER ===
        kargo_observer = None
        if KARGO_OBSERVER_ENABLED:
            async def kargo_failure_callback(**kwargs) -> None:
                await aligner.handle_failed_promotion(**kwargs)

            async def kargo_recovery_callback(**kwargs) -> None:
                await aligner.handle_promotion_recovery(**kwargs)

            async def kargo_broadcast_callback() -> None:
                await brain._broadcast({
                    "type": "kargo_stages_update",
                    "stages": kargo_observer.get_failed_stages(),
                })

            kargo_observer = KargoObserver(
                blackboard=blackboard,
                failure_callback=kargo_failure_callback,
                recovery_callback=kargo_recovery_callback,
                broadcast_callback=kargo_broadcast_callback,
            )
            brain.agents["_kargo_observer"] = kargo_observer
            await kargo_observer.start()
            dashboard_adapter.set_kargo_observer(kargo_observer)
            set_kargo_observer(kargo_observer)
            logger.info("KargoObserver started for promotion state watching")
        else:
            logger.info("KargoObserver disabled (KARGO_OBSERVER_ENABLED=false)")
        
        # === TIMEKEEPER OBSERVER ===
        timekeeper_observer = None
        if DEX_ENABLED and TIMEKEEPER_ENABLED:
            timekeeper_observer = TimeKeeperObserver(blackboard=blackboard)
            await timekeeper_observer.start()
            logger.info("TimeKeeperObserver started (DEX + TIMEKEEPER enabled)")
        elif TIMEKEEPER_ENABLED and not DEX_ENABLED:
            logger.warning("TIMEKEEPER_ENABLED=true but DEX_ENABLED=false -- TimeKeeper requires auth, disabled")
        else:
            logger.info("TimeKeeperObserver disabled (TIMEKEEPER_ENABLED=false)")
    
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
    
    # Stop OIDC key adapter
    if hasattr(app.state, "oidc_adapter"):
        await app.state.oidc_adapter.stop()

    # Stop Slack channel
    if hasattr(app.state, "slack"):
        await app.state.slack.stop()
        logger.info("Slack channel stopped")
    
    # Stop Headhunter
    if headhunter_task and not headhunter_task.done():
        headhunter_task.cancel()
        logger.info("Headhunter task cancelled")
    
    # Stop Kargo observer
    if redis and kargo_observer:
        await kargo_observer.stop()
        logger.info("KargoObserver stopped")
    
    # Stop K8s observer
    if redis and K8S_OBSERVER_ENABLED and k8s_observer:
        await k8s_observer.stop()
        logger.info("KubernetesObserver stopped")
    
    # Stop TimeKeeper observer
    if redis and timekeeper_observer:
        await timekeeper_observer.stop()
        logger.info("TimeKeeperObserver stopped")
    
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
# Flow Observability (Lewis's "camera on the tills")
# =============================================================================

@app.get("/flow", response_model=FlowMetricsResponse, tags=["flow"])
async def get_flow_metrics() -> FlowMetricsResponse:
    """
    Flow health metrics -- leading indicators for system throughput.
    
    Separate from /health (which stays zero-Redis for K8s probes).
    Returns queue depth, active events, and per-role agent utilization.
    """
    from .dependencies import _blackboard, get_registry_and_bridge

    flow = {"queue_depth": 0, "active_events": 0}
    if _blackboard is not None:
        flow = await _blackboard.get_flow_metrics()

    busy = 0
    idle = 0
    by_role: dict[str, dict[str, int]] = {}
    try:
        registry, _ = get_registry_and_bridge()
        if registry:
            agents = await registry.list_agents()
            for a in agents:
                role = a.get("role", "unknown")
                if role not in by_role:
                    by_role[role] = {"busy": 0, "idle": 0}
                if a.get("busy"):
                    busy += 1
                    by_role[role]["busy"] += 1
                else:
                    idle += 1
                    by_role[role]["idle"] += 1
    except Exception:
        pass

    return FlowMetricsResponse(
        queue_depth=flow["queue_depth"],
        active_events=flow["active_events"],
        busy_agents=busy,
        idle_agents=idle,
        agents_by_role=by_role,
    )


@app.get("/flow/{event_id}", tags=["flow"])
async def get_event_flow(event_id: str) -> dict:
    """Value stream breakdown for a single event."""
    from .dependencies import _blackboard

    if _blackboard is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Blackboard not initialized")

    event = await _blackboard.get_event(event_id)
    if not event:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail=f"Event {event_id} not found")

    t = {
        "queued_at": event.queued_at,
        "processing_started_at": event.processing_started_at,
        "last_dispatched_at": event.last_dispatched_at,
        "last_completed_at": event.last_completed_at,
        "closed_at": event.closed_at,
    }

    def delta(a: str, b: str) -> float | None:
        va, vb = t.get(a), t.get(b)
        return round(vb - va, 3) if va is not None and vb is not None else None

    agent_turns = sum(
        1 for turn in event.conversation
        if turn.actor in ("architect", "sysadmin", "developer", "qe")
    )

    return {
        "event_id": event_id,
        "timestamps": t,
        "intervals": {
            "queue_wait_s": delta("queued_at", "processing_started_at"),
            "routing_s": delta("processing_started_at", "last_dispatched_at"),
            "execution_s": delta("last_dispatched_at", "last_completed_at"),
            "total_lead_time_s": delta("queued_at", "closed_at"),
        },
        "agent_turns": agent_turns,
    }


# =============================================================================
# Public Configuration (AI Transparency & Compliance)
# =============================================================================

@app.get("/config", tags=["config"])
async def get_config() -> dict:
    """Public configuration for the UI (no secrets)."""
    config = {
        "contactEmail": os.getenv("DARWIN_CONTACT_EMAIL", ""),
        "feedbackFormUrl": os.getenv("DARWIN_FEEDBACK_FORM_URL", ""),
        "appVersion": os.getenv("APP_VERSION", "1.0.0"),
    }
    if DEX_ENABLED:
        config["auth"] = {
            "enabled": True,
            "issuerUrl": os.getenv("DEX_ISSUER_URL", ""),
            "clientId": os.getenv("DEX_CLIENT_ID", "darwin-dashboard"),
            "loginDisclaimer": os.getenv("DEX_LOGIN_DISCLAIMER", ""),
        }
    else:
        config["auth"] = {"enabled": False}
    return config


# =============================================================================
# WebSocket Endpoint (UI real-time communication)
# =============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time UI communication. Delegates to DashboardWSAdapter."""
    adapter = getattr(app.state, 'dashboard_adapter', None)
    if not adapter:
        await websocket.close(code=1013, reason="Dashboard adapter not initialized")
        return
    await adapter.websocket_handler(websocket)


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
    from .dependencies import _blackboard
    brain = getattr(app.state, 'brain', None)
    on_wake = brain.handle_wake_task if brain else None
    await agent_websocket_handler(websocket, registry, bridge, blackboard=_blackboard, on_wake=on_wake)


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
app.include_router(journal_router)
app.include_router(metrics_router)
app.include_router(chat_router)
app.include_router(events_router)
app.include_router(feedback_router)
app.include_router(reports_router)
app.include_router(incidents_router)
app.include_router(kargo_router)
if DEX_ENABLED:
    app.include_router(dex_proxy_router)
    app.include_router(timekeeper_router)


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
# Mount static assets (JS, CSS, images) at root, then add SPA fallback
# for client-side routes (/callback, /reports, /guide, etc.)
static_dir = Path(__file__).parent.parent / "ui" / "dist"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(static_dir / "assets")), name="static-assets")

    _index_html = (static_dir / "index.html").read_bytes()

    @app.get("/{path:path}", include_in_schema=False)
    async def spa_fallback(path: str):
        file_path = static_dir / path
        if file_path.is_file():
            from starlette.responses import FileResponse
            return FileResponse(file_path)
        from starlette.responses import HTMLResponse
        return HTMLResponse(content=_index_html)
