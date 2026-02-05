# BlackBoard/src/agents/architect.py
"""
Agent 2: The Architect (The Strategist)

Role: Optimization & Strategy
Nature: Pure AI (Vertex AI Pro SDK)
Interaction: Chat Interface

The Architect receives topology snapshots + user intent and uses
Function Calling (Tools) to generate structured JSON Plans.

AIR GAP ENFORCEMENT:
- This module may import vertexai
- This module CANNOT import kubernetes, git, or subprocess
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import TYPE_CHECKING, Optional

# AIR GAP ENFORCEMENT: These imports are FORBIDDEN
# import kubernetes  # FORBIDDEN
# import git  # FORBIDDEN
# import subprocess  # FORBIDDEN

from ..models import ChatResponse, ConversationMessage, PlanAction, PlanCreate, PlanStatus, Plan

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

# System prompt for the Architect
ARCHITECT_SYSTEM_PROMPT = """
You are the Architect agent in the Darwin autonomous infrastructure system.

Your role is to analyze the current topology, metrics, and user intent,
then generate structured infrastructure modification plans.

Current System Context:
{context}

Guidelines:
1. Always consider the current state of services before recommending changes
2. Use the generate_ops_plan function to create structured plans
3. Use the analyze_topology function if you need more context
4. Provide clear reasoning for your recommendations
5. Consider dependencies between services when planning changes

Available actions:
- scale: Change the number of replicas for a service
- rollback: Revert a service to a previous version
- reconfig: Update configuration for a service
- failover: Switch to a backup/standby service
- optimize: Apply performance optimizations
"""


class Architect:
    """
    The Architect agent - strategic planning via Vertex AI.
    
    Responsibilities:
    - Analyze topology and metrics
    - Generate infrastructure plans using Function Calling
    - Store plans in Blackboard for approval
    """
    
    def __init__(self, blackboard: "BlackboardState"):
        self.blackboard = blackboard
        self._model = None
        self._chat = None
        self._running = False  # For task loop
        
        # Configuration
        self.project = os.getenv("GCP_PROJECT")
        self.location = os.getenv("GCP_LOCATION", "us-central1")
        self.model_name = os.getenv("VERTEX_MODEL_PRO", "gemini-3-pro-preview")
        
        # Validate GCP configuration at init time
        if not self.project:
            logger.error(
                "ARCHITECT DISABLED: GCP_PROJECT environment variable is not set. "
                "The Architect cannot create plans without Vertex AI. "
                "Set gcp.project in Helm values or export GCP_PROJECT."
            )
        else:
            logger.info(f"Architect configured with GCP project: {self.project}")
        
    async def _get_model(self):
        """Lazy-load Vertex AI Pro model with tools."""
        if self._model is None:
            try:
                import vertexai
                from vertexai.generative_models import GenerativeModel, GenerationConfig
                
                from .tools import architect_tools
                
                vertexai.init(project=self.project, location=self.location)
                
                self._model = GenerativeModel(
                    self.model_name,
                    tools=[architect_tools],
                    generation_config=GenerationConfig(
                        temperature=0.7,  # Balanced: creative enough to reason across diverse data
                        top_p=0.9,        # Allow varied token selection
                    ),
                )
                
                logger.info(f"Architect initialized with Vertex AI Pro: {self.model_name}")
            
            except Exception as e:
                logger.error(f"Failed to initialize Vertex AI: {e}")
                raise RuntimeError(f"Vertex AI initialization failed: {e}")
        
        return self._model
    
    async def _build_context(self) -> str:
        """Build context string from Blackboard snapshot."""
        snapshot = await self.blackboard.get_snapshot()
        
        # Format topology
        topology_lines = ["Services:"]
        for name, service in snapshot.services.items():
            deps = ", ".join(service.dependencies) if service.dependencies else "none"
            topology_lines.append(
                f"  - {name} (v{service.version}): "
                f"cpu={service.metrics.cpu:.1f}%, "
                f"error_rate={service.metrics.error_rate:.2f}%, "
                f"deps=[{deps}]"
            )
        
        if not snapshot.services:
            topology_lines.append("  (no services registered)")
        
        # Format pending plans
        plan_lines = ["Pending Plans:"]
        for plan in snapshot.pending_plans:
            plan_lines.append(
                f"  - {plan.id}: {plan.action.value} {plan.service} - {plan.reason[:50]}..."
            )
        
        if not snapshot.pending_plans:
            plan_lines.append("  (no pending plans)")
        
        return "\n".join(topology_lines + [""] + plan_lines)
    
    async def _handle_function_call(self, function_call) -> Optional[dict]:
        """Handle a function call from the model."""
        name = function_call.name
        args = dict(function_call.args)
        
        logger.info(f"Function call: {name}({args})")
        
        if name == "generate_ops_plan":
            # Create and store the plan
            plan_data = PlanCreate(
                action=PlanAction(args["action"]),
                service=args["service"],
                params=args.get("params", {}),
                reason=args["reason"],
            )
            
            plan = await self.blackboard.create_plan(plan_data)
            
            # Check for auto-approval based on action type
            auto_approved = await self._check_auto_approve(plan)
            
            return {
                "plan_id": plan.id,
                "action": plan.action.value,
                "service": plan.service,
                "status": "auto_approved" if auto_approved else "created",
            }
        
        elif name == "analyze_topology":
            # Return topology analysis
            service = args.get("service")
            include_metrics = args.get("include_metrics", True)
            
            if service:
                svc = await self.blackboard.get_service(service)
                if svc:
                    result = {"service": svc.model_dump()}
                    if include_metrics:
                        metrics = await self.blackboard.get_current_metrics(service)
                        result["current_metrics"] = metrics
                    return result
                else:
                    return {"error": f"Service '{service}' not found"}
            else:
                snapshot = await self.blackboard.get_snapshot()
                return {
                    "services": list(snapshot.services.keys()),
                    "total_services": len(snapshot.services),
                    "edges": snapshot.topology.edges,
                }
        
        return None
    
    async def _check_auto_approve(self, plan: Plan) -> bool:
        """
        Check if plan can be auto-approved and enqueue for execution.
        
        Auto-approval policy:
        - Values-only changes (scale, reconfig) → Auto-approve + Enqueue
        - Rollback → Auto-approve only if NOT structural (template_rollback/structural params)
        - Structural changes (failover, optimize) → Require human approval
        """
        auto_approve_enabled = os.getenv("SYSADMIN_AUTO_APPROVE", "false").lower() == "true"
        
        if not auto_approve_enabled:
            return False
        
        action = plan.action.value
        params = plan.params or {}
        
        # Actions that are always values-only (safe for auto-approval)
        values_only_actions = {"scale", "reconfig"}
        
        can_approve = False
        
        if action in values_only_actions:
            can_approve = True
        elif action == "rollback":
            # Only auto-approve version-only rollbacks, not structural
            if params.get("template_rollback") or params.get("structural"):
                logger.info(f"Plan {plan.id} rollback requires structural changes - human approval needed")
                return False
            can_approve = True
        elif action in {"failover", "optimize"}:
            # Only auto-approve if explicitly marked values_only
            if params.get("values_only"):
                can_approve = True
            else:
                logger.info(f"Plan {plan.id} '{action}' may require structural changes - human approval needed")
                return False
        
        if can_approve:
            await self.blackboard.update_plan_status(plan.id, PlanStatus.APPROVED)
            logger.info(f"Plan {plan.id} auto-approved: {action}")
            
            # Enqueue for SysAdmin execution
            await self.blackboard.enqueue_plan_for_execution(plan.id)
            logger.info(f"Plan {plan.id} enqueued for execution")
            return True
        
        logger.info(f"Plan {plan.id} requires human approval: {action}")
        return False
    
    async def chat(
        self,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> ChatResponse:
        """
        Process a chat message from the operator with conversation history.
        
        The Architect will analyze the request, check current state,
        and potentially create a plan using Function Calling.
        
        Args:
            message: User's message
            conversation_id: Optional conversation ID for multi-turn context.
                           If not provided, a new conversation is created.
        
        Returns:
            ChatResponse with message, plan_id, and conversation_id
        """
        # Fail fast if Vertex AI is not configured
        if not self.project:
            logger.error("Architect.chat() called but GCP_PROJECT is not set")
            return ChatResponse(
                message="Architect is disabled: GCP_PROJECT environment variable is not configured. "
                        "Set gcp.project in Helm values to enable AI-powered analysis.",
                plan_id=None,
                conversation_id=None,
            )
        
        # Create or validate conversation
        if not conversation_id:
            conversation_id = await self.blackboard.create_conversation()
            logger.info(f"Created new conversation: {conversation_id}")
        
        # Load conversation history
        history = await self.blackboard.get_conversation(conversation_id)
        
        model = await self._get_model()
        
        # Build context
        context = await self._build_context()
        system_prompt = ARCHITECT_SYSTEM_PROMPT.format(context=context)
        
        # Build messages list including history
        messages = [system_prompt]
        for msg in history:
            role_prefix = "User" if msg.role == "user" else "Assistant"
            messages.append(f"\n{role_prefix}: {msg.content}")
        messages.append(f"\nUser request: {message}")
        
        try:
            # Generate response with potential function calls
            response = await model.generate_content_async(messages)
            
            plan_id = None
            
            # Check for function calls
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, "function_call") and part.function_call:
                        result = await self._handle_function_call(part.function_call)
                        if result and "plan_id" in result:
                            plan_id = result["plan_id"]
            
            # Extract text response (with defensive handling for empty Vertex AI responses)
            text_response = ""
            try:
                if response.text:
                    text_response = response.text
            except (ValueError, AttributeError):
                # Vertex AI SDK raises ValueError when accessing .text on empty response
                logger.warning("Vertex AI returned empty text response")
            
            if not text_response:
                if plan_id:
                    text_response = f"I've created a plan ({plan_id}) based on your request. It's now pending approval."
                else:
                    text_response = "I've analyzed your request but couldn't generate a specific action. Please provide more details."
            
            # Save messages to conversation history
            await self.blackboard.append_to_conversation(
                conversation_id,
                ConversationMessage(role="user", content=message)
            )
            await self.blackboard.append_to_conversation(
                conversation_id,
                ConversationMessage(role="assistant", content=text_response)
            )
            
            return ChatResponse(
                message=text_response,
                plan_id=plan_id,
                conversation_id=conversation_id,
            )
        
        except Exception as e:
            logger.error(f"Architect chat error: {e}")
            return ChatResponse(
                message=f"I encountered an error processing your request: {e}",
                plan_id=None,
                conversation_id=conversation_id,
            )
    
    async def analyze(self, service: Optional[str] = None) -> dict:
        """
        Analyze the current system state.
        
        Returns analysis without creating a plan.
        """
        if service:
            svc = await self.blackboard.get_service(service)
            if svc:
                return {
                    "service": svc.model_dump(),
                    "metrics": await self.blackboard.get_current_metrics(service),
                }
            return {"error": f"Service '{service}' not found"}
        
        snapshot = await self.blackboard.get_snapshot()
        return {
            "total_services": len(snapshot.services),
            "services": [s.model_dump() for s in snapshot.services.values()],
            "pending_plans": len(snapshot.pending_plans),
        }
    
    # =========================================================================
    # Task Loop (Blackboard-Centric Communication)
    # =========================================================================
    
    async def start_task_loop(self) -> None:
        """
        Start background loop that polls Blackboard for tasks.
        
        Called from main.py on startup to enable Blackboard-centric communication.
        """
        self._running = True
        logger.info("Architect task loop started")
        
        while self._running:
            try:
                task = await self.blackboard.dequeue_architect_task()
                if task:
                    await self._process_task(task)
            except Exception as e:
                logger.error(f"Architect task loop error: {e}")
                await asyncio.sleep(5)
    
    def stop_task_loop(self) -> None:
        """Stop the task loop."""
        self._running = False
        logger.info("Architect task loop stopping")
    
    async def _process_task(self, task: dict) -> None:
        """Process a task from the Blackboard queue."""
        task_type = task.get("type")
        logger.info(f"Processing task: {task.get('id')} ({task_type})")
        
        if task_type == "anomaly_analysis":
            prompt = self._build_anomaly_prompt(
                task["service"],
                task["anomaly_type"],
                task.get("investigation"),
            )
            response = await self.chat(prompt)
            logger.info(f"Task {task.get('id')} completed, plan_id: {response.plan_id}")
        else:
            logger.warning(f"Unknown task type: {task_type}")
    
    def _build_anomaly_prompt(
        self,
        service: str,
        anomaly_type: str,
        investigation: Optional[str] = None,
    ) -> str:
        """Build ACTIONABLE prompt for anomaly analysis."""
        # Base prompt by anomaly type
        if anomaly_type == "high_cpu":
            base_prompt = (
                f"AUTOMATED ALERT: Service '{service}' has critically high CPU usage (above threshold).\n\n"
                f"ACTION REQUIRED: Create a scaling plan using the generate_ops_plan function.\n"
                f"- Use action='scale' to increase replicas\n"
                f"- Set params.replicas to an appropriate number (e.g., 2 or 3)\n"
                f"- Provide a clear reason referencing the high CPU\n\n"
            )
        elif anomaly_type == "high_memory":
            base_prompt = (
                f"AUTOMATED ALERT: Service '{service}' has critically high memory usage (above threshold).\n\n"
                f"ACTION REQUIRED: Create a scaling plan using the generate_ops_plan function.\n"
                f"- Use action='scale' to increase replicas and distribute memory load\n"
                f"- Set params.replicas to an appropriate number\n"
                f"- Provide a clear reason referencing the high memory\n\n"
            )
        elif anomaly_type == "high_error_rate":
            base_prompt = (
                f"AUTOMATED ALERT: Service '{service}' has a critically high error rate (above threshold).\n\n"
                f"ACTION REQUIRED: Create a remediation plan using the generate_ops_plan function.\n"
                f"- Consider action='rollback' to revert to a stable version, OR\n"
                f"- Consider action='failover' if a standby is available\n"
                f"- Provide a clear reason referencing the high error rate\n\n"
            )
        elif anomaly_type in ("anomaly_resolved_cpu", "anomaly_resolved_memory"):
            resolved_metric = "CPU" if "cpu" in anomaly_type else "memory"
            base_prompt = (
                f"AUTOMATED ALERT: Service '{service}' {resolved_metric} usage has returned to normal levels.\n\n"
                f"The service was previously scaled up due to high {resolved_metric}. "
                f"Check the current replica count and metrics.\n\n"
                f"ACTION REQUIRED: If the service currently has MORE than 1 replica AND "
                f"{resolved_metric} usage is well below the threshold, create a scale-down plan "
                f"using the generate_ops_plan function.\n"
                f"- Use action='scale' with params.replicas=1 (or an appropriate lower number)\n"
                f"- Provide a clear reason referencing the resolved anomaly\n\n"
                f"If the service is already at 1 replica, or if metrics suggest it still needs "
                f"the extra capacity, do NOT create a plan.\n\n"
            )
        elif anomaly_type == "over_provisioned":
            base_prompt = (
                f"AUTOMATED ALERT: Service '{service}' appears over-provisioned.\n\n"
                f"The service has multiple replicas but both CPU and memory usage are low "
                f"(well below anomaly thresholds). No active anomalies exist for this service.\n\n"
                f"ACTION REQUIRED: Check the current replica count and metrics using analyze_topology. "
                f"If the service has MORE than 1 replica and usage is consistently low, "
                f"create a scale-down plan using the generate_ops_plan function.\n"
                f"- Use action='scale' with params.replicas=1\n"
                f"- Provide a clear reason referencing the low utilization\n\n"
                f"If metrics suggest the service still needs extra capacity, do NOT create a plan.\n\n"
            )
        else:
            base_prompt = (
                f"AUTOMATED ALERT: Anomaly detected for service '{service}' ({anomaly_type}).\n\n"
                f"ACTION REQUIRED: Create a remediation plan using the generate_ops_plan function.\n"
                f"Choose the appropriate action: scale, rollback, reconfig, failover, or optimize.\n\n"
            )
        
        # Add investigation context if available
        if investigation:
            base_prompt += (
                f"=== INVESTIGATION FINDINGS ===\n"
                f"{investigation[:2000]}\n\n"
            )
        
        base_prompt += "DO NOT just analyze - you MUST call generate_ops_plan to create a remediation plan."
        
        return base_prompt
