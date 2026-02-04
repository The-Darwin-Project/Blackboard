# BlackBoard/src/agents/tools.py
"""
Function declarations for Vertex AI Architect agent.

Uses validated FunctionDeclaration API from google-cloud-aiplatform SDK.
Forces the Architect to output structured JSON plans instead of free text.
"""
from __future__ import annotations

from vertexai.generative_models import FunctionDeclaration, Tool

# Plan action types supported by Darwin
PLAN_ACTIONS = ["scale", "rollback", "reconfig", "failover", "optimize"]

# =============================================================================
# Function Declaration: generate_ops_plan
# =============================================================================

generate_ops_plan = FunctionDeclaration(
    name="generate_ops_plan",
    description="""
    Create a structured infrastructure modification plan.
    
    Use this function when the user requests changes to the infrastructure,
    such as scaling services, rolling back deployments, or reconfiguring resources.
    
    The plan will be stored in the Blackboard for approval and execution by SysAdmin.
    """,
    parameters={
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": PLAN_ACTIONS,
                "description": "The type of infrastructure change to perform"
            },
            "service": {
                "type": "string",
                "description": "Target service name from the topology (e.g., 'inventory-api', 'postgres-primary')"
            },
            "params": {
                "type": "object",
                "description": "Action-specific parameters",
                "properties": {
                    "replicas": {
                        "type": "integer",
                        "description": "Number of replicas for scale action"
                    },
                    "version": {
                        "type": "string",
                        "description": "Target version for rollback action"
                    },
                    "config": {
                        "type": "object",
                        "description": "Configuration changes for reconfig action"
                    },
                    "target": {
                        "type": "string",
                        "description": "Failover target for failover action"
                    },
                    "optimization": {
                        "type": "string",
                        "description": "Optimization type for optimize action"
                    }
                }
            },
            "reason": {
                "type": "string",
                "description": "Justification for the change based on current metrics and topology"
            }
        },
        "required": ["action", "service", "reason"]
    }
)

# =============================================================================
# Function Declaration: analyze_topology
# =============================================================================

analyze_topology = FunctionDeclaration(
    name="analyze_topology",
    description="""
    Request detailed analysis of the current service topology.
    
    Use this when you need more context about service dependencies,
    health metrics, or the overall system state before making recommendations.
    """,
    parameters={
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Optional: specific service to analyze (leave empty for full topology)"
            },
            "include_metrics": {
                "type": "boolean",
                "description": "Whether to include recent metrics history",
                "default": True
            }
        },
        "required": []
    }
)

# =============================================================================
# Architect Tools Bundle
# =============================================================================

architect_tools = Tool(
    function_declarations=[
        generate_ops_plan,
        analyze_topology,
    ]
)
