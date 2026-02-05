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
            
            Triggers Architect to analyze the situation and CREATE A PLAN.
            """
            from .models import EventType
            
            try:
                # Build ACTIONABLE prompt based on anomaly type
                # Explicitly instruct the model to CREATE A PLAN using the function
                if anomaly_type == "high_cpu":
                    prompt = (
                        f"AUTOMATED ALERT: Service '{service}' has critically high CPU usage (above threshold).\n\n"
                        f"ACTION REQUIRED: Create a scaling plan using the generate_ops_plan function.\n"
                        f"- Use action='scale' to increase replicas\n"
                        f"- Set params.replicas to an appropriate number (e.g., 2 or 3)\n"
                        f"- Provide a clear reason referencing the high CPU\n\n"
                        f"DO NOT just analyze - you MUST call generate_ops_plan to create a remediation plan."
                    )
                elif anomaly_type == "high_memory":
                    prompt = (
                        f"AUTOMATED ALERT: Service '{service}' has critically high memory usage (above threshold).\n\n"
                        f"ACTION REQUIRED: Create a scaling plan using the generate_ops_plan function.\n"
                        f"- Use action='scale' to increase replicas and distribute memory load\n"
                        f"- Set params.replicas to an appropriate number\n"
                        f"- Provide a clear reason referencing the high memory\n\n"
                        f"DO NOT just analyze - you MUST call generate_ops_plan to create a remediation plan."
                    )
                elif anomaly_type == "high_error_rate":
                    prompt = (
                        f"AUTOMATED ALERT: Service '{service}' has a critically high error rate (above threshold).\n\n"
                        f"ACTION REQUIRED: Create a remediation plan using the generate_ops_plan function.\n"
                        f"- Consider action='rollback' to revert to a stable version, OR\n"
                        f"- Consider action='failover' if a standby is available\n"
                        f"- Provide a clear reason referencing the high error rate\n\n"
                        f"DO NOT just analyze - you MUST call generate_ops_plan to create a remediation plan."
                    )
                else:
                    prompt = (
                        f"AUTOMATED ALERT: Anomaly detected for service '{service}' ({anomaly_type}).\n\n"
                        f"ACTION REQUIRED: Create a remediation plan using the generate_ops_plan function.\n"
                        f"Choose the appropriate action: scale, rollback, reconfig, failover, or optimize.\n\n"
                        f"DO NOT just analyze - you MUST call generate_ops_plan to create a remediation plan."
                    )
                
                logger.info(f"Architect analyzing anomaly: {service} ({anomaly_type})")
                
                # Call Architect's chat method
                response = await architect.chat(prompt)
                
                if response.plan_id:
                    logger.info(f"Architect created plan {response.plan_id} for {service}")
                    # Event already recorded by plan creation
                else:
                    # Record the Architect's response even when no plan was created
                    await blackboard.record_event(
                        EventType.ARCHITECT_ANALYZING,
                        {
                            "service": service,
                            "trigger": anomaly_type,
                            "response": response.message[:500],
                            "plan_created": False,
                        },
                        narrative=f"Analyzing the {anomaly_type.replace('_', ' ')} anomaly on {service}. {response.message[:150]}",
                    )
                    logger.warning(
                        f"Architect did NOT create a plan for {service} ({anomaly_type}). "
                        f"Response: {response.message[:200]}..."
                    )
                    
            except Exception as e:
                logger.error(f"Architect anomaly analysis failed: {e}")
                # Record failure event so UI shows what happened
                await blackboard.record_event(
                    EventType.ARCHITECT_ANALYZING,
                    {
                        "service": service,
                        "trigger": anomaly_type,
                        "error": str(e),
                        "plan_created": False,
                    },
                    narrative=f"Analysis of {anomaly_type.replace('_', ' ')} on {service} encountered an error: {str(e)[:100]}",
                )
        
        aligner.set_architect_callback(architect_anomaly_callback)
        logger.info("Closed-loop wiring complete: Aligner → Architect")
        
        # === AUTO-APPROVAL & AUTO-EXECUTION WIRING ===
        # Connect Architect → SysAdmin for intelligent auto-approval and execution
        from .models import Plan, PlanStatus, EventType
        
        async def plan_auto_approval_callback(plan: Plan) -> None:
            """
            Called by Architect after creating a plan.
            
            Closed-loop completion:
            1. Check if plan can be auto-approved based on SysAdmin policy
            2. If auto-approved, automatically execute via SysAdmin
            3. Update plan status based on execution result
            
            Auto-approval policy:
            - Values-only changes (scale, reconfig) → Auto-approve + Auto-execute
            - Structural changes (failover, optimize) → Require human approval
            """
            can_approve, reason = sysadmin.can_auto_approve(plan)
            
            if can_approve:
                await blackboard.update_plan_status(plan.id, PlanStatus.APPROVED)
                logger.info(f"Plan {plan.id} auto-approved: {reason}")
                
                # === CLOSED-LOOP: Auto-execute after auto-approval ===
                try:
                    # Mark as executing
                    await blackboard.update_plan_status(plan.id, PlanStatus.EXECUTING)
                    
                    # Record SysAdmin executing event
                    await blackboard.record_event(
                        EventType.SYSADMIN_EXECUTING,
                        {"plan_id": plan.id, "service": plan.service, "action": plan.action.value},
                        narrative=f"Executing approved plan: {plan.action.value} on {plan.service}...",
                    )
                    logger.info(f"SysAdmin auto-executing plan {plan.id}")
                    
                    # Execute via SysAdmin
                    result = await sysadmin.execute_plan(plan)
                    
                    # Mark as completed
                    await blackboard.update_plan_status(plan.id, PlanStatus.COMPLETED, result=result)
                    
                    # Record completion event with enhanced details
                    await blackboard.record_event(
                        EventType.PLAN_EXECUTED,
                        {
                            "plan_id": plan.id,
                            "service": plan.service,
                            "action": plan.action.value,
                            "status": "success",
                            "summary": f"{plan.action.value} {plan.service}",
                            "result": result[:500] if result else "",
                        },
                        narrative=f"Successfully executed {plan.action.value} on {plan.service}.",
                    )
                    logger.info(f"Plan {plan.id} auto-executed successfully")
                    
                except Exception as e:
                    # Mark as failed
                    await blackboard.update_plan_status(plan.id, PlanStatus.FAILED, result=str(e))
                    
                    # Record failure event with enhanced details
                    await blackboard.record_event(
                        EventType.PLAN_FAILED,
                        {
                            "plan_id": plan.id,
                            "service": plan.service,
                            "action": plan.action.value,
                            "status": "failed",
                            "error": str(e)[:500],
                        },
                        narrative=f"Failed to execute plan for {plan.service}: {str(e)[:100]}",
                    )
                    logger.error(f"Plan {plan.id} auto-execution failed: {e}")
            else:
                logger.info(f"Plan {plan.id} requires human approval: {reason}")
        
        architect.set_plan_created_callback(plan_auto_approval_callback)
        logger.info("Closed-loop wiring complete: Aligner → Architect → SysAdmin (auto-execute enabled)")
        
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
