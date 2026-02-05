# BlackBoard/src/routes/topology.py
"""
Topology query endpoints.

Provides the Architecture Graph visualization (Visualization #1).
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from ..models import GraphResponse
from ..state import BlackboardState
from ..dependencies import get_blackboard

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/topology", tags=["topology"])


@router.get("/")
async def get_topology(
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """
    Get current topology with full service details.
    
    Returns services (with metrics), edges, and topology info.
    """
    topology = await blackboard.get_topology()
    services = await blackboard.get_all_services()
    
    return {
        "services": {name: svc.model_dump() for name, svc in services.items()},
        "edges": topology.edges,
        "service_names": topology.services,
    }


@router.get("/services")
async def list_services(
    blackboard: BlackboardState = Depends(get_blackboard),
) -> list[str]:
    """Get list of all registered service names."""
    services = await blackboard.get_services()
    logger.debug(f"/topology/services returning: {sorted(services)}")
    return services


@router.get("/mermaid")
async def get_mermaid_diagram(
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """
    Get topology as Mermaid diagram.
    
    Returns Mermaid graph TD syntax for rendering.
    This is the Architecture Graph (Visualization #1) - legacy format.
    """
    mermaid = await blackboard.generate_mermaid()
    return {"mermaid": mermaid}


@router.get("/graph", response_model=GraphResponse)
async def get_graph_data(
    blackboard: BlackboardState = Depends(get_blackboard),
) -> GraphResponse:
    """
    Get topology as rich graph data for Cytoscape.js visualization.
    
    Returns nodes with health status, edges with protocol metadata,
    and pending plans as ghost nodes per GRAPH_SPEC.md.
    
    This is the Architecture Graph (Visualization #1) - Cytoscape format.
    """
    return await blackboard.get_graph_data()


@router.get("/service/{service_name}")
async def get_service_details(
    service_name: str,
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """Get detailed information for a specific service."""
    service = await blackboard.get_service(service_name)
    
    if service is None:
        raise HTTPException(status_code=404, detail=f"Service '{service_name}' not found")
    
    return service.model_dump()
