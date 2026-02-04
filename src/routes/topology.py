# BlackBoard/src/routes/topology.py
"""
Topology query endpoints.

Provides the Architecture Graph visualization (Visualization #1).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from fastapi.responses import PlainTextResponse

from ..models import TopologySnapshot
from ..state import BlackboardState
from ..dependencies import get_blackboard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/topology", tags=["topology"])


@router.get("/", response_model=TopologySnapshot)
async def get_topology(
    blackboard: BlackboardState = Depends(get_blackboard),
) -> TopologySnapshot:
    """
    Get current topology as JSON.
    
    Returns services list and edges dict.
    """
    return await blackboard.get_topology()


@router.get("/services")
async def list_services(
    blackboard: BlackboardState = Depends(get_blackboard),
) -> list[str]:
    """Get list of all registered service names."""
    return await blackboard.get_services()


@router.get("/mermaid", response_class=PlainTextResponse)
async def get_mermaid_diagram(
    blackboard: BlackboardState = Depends(get_blackboard),
) -> str:
    """
    Get topology as Mermaid diagram.
    
    Returns Mermaid graph TD syntax for rendering.
    This is the Architecture Graph (Visualization #1).
    """
    return await blackboard.generate_mermaid()


@router.get("/service/{service_name}")
async def get_service_details(
    service_name: str,
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """Get detailed information for a specific service."""
    service = await blackboard.get_service(service_name)
    
    if service is None:
        return {"error": f"Service '{service_name}' not found"}
    
    return service.model_dump()
