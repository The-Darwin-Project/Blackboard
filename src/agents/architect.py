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

import json
import logging
import os
from typing import TYPE_CHECKING, Optional, Callable, Awaitable

# AIR GAP ENFORCEMENT: These imports are FORBIDDEN
# import kubernetes  # FORBIDDEN
# import git  # FORBIDDEN
# import subprocess  # FORBIDDEN

from ..models import ChatResponse, ConversationMessage, PlanAction, PlanCreate, Plan

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
        
        # Callback for auto-approval check after plan creation
        self._plan_created_callback: Optional[Callable[["Plan"], Awaitable[None]]] = None
    
    def set_plan_created_callback(
        self, callback: Callable[["Plan"], Awaitable[None]]
    ) -> None:
        """
        Set callback for auto-approval check after plan creation.
        
        Callback signature: async def callback(plan: Plan) -> None
        This is called after each plan is created, allowing SysAdmin to
        check if the plan can be auto-approved.
        """
        self._plan_created_callback = callback
        logger.info("Plan created callback registered for auto-approval")
    
    async def _get_model(self):
        """Lazy-load Vertex AI Pro model with tools."""
        if self._model is None:
            try:
                import vertexai
                from vertexai.generative_models import GenerativeModel
                
                from .tools import architect_tools
                
                vertexai.init(project=self.project, location=self.location)
                
                self._model = GenerativeModel(
                    self.model_name,
                    tools=[architect_tools],
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
            
            # Check for auto-approval (if callback registered)
            auto_approved = False
            if self._plan_created_callback:
                try:
                    await self._plan_created_callback(plan)
                    # Re-fetch plan to get updated status
                    updated_plan = await self.blackboard.get_plan(plan.id)
                    if updated_plan and updated_plan.status.value == "approved":
                        auto_approved = True
                except Exception as e:
                    logger.warning(f"Auto-approval check failed: {e}")
            
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
            
            # Extract text response
            text_response = ""
            if response.text:
                text_response = response.text
            elif plan_id:
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
