# BlackBoard/src/routes/plans.py
"""
Plan management endpoints.

CRUD operations for infrastructure modification plans.
"""
from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from ..models import Plan, PlanStatus
from ..state import BlackboardState
from ..dependencies import get_blackboard, get_sysadmin

if TYPE_CHECKING:
    from ..agents.sysadmin import SysAdmin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/plans", tags=["plans"])


@router.get("/", response_model=list[Plan])
async def list_plans(
    status: Optional[PlanStatus] = Query(None, description="Filter by plan status"),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> list[Plan]:
    """
    List all plans.
    
    Optionally filter by status (pending, approved, rejected, etc.).
    """
    return await blackboard.list_plans(status=status)


@router.get("/{plan_id}", response_model=Plan)
async def get_plan(
    plan_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
) -> Plan:
    """Get a specific plan by ID."""
    plan = await blackboard.get_plan(plan_id)
    
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    
    return plan


@router.post("/{plan_id}/approve", response_model=Plan)
async def approve_plan(
    plan_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
) -> Plan:
    """
    Approve a pending plan.
    
    Changes status from 'pending' to 'approved'.
    Only approved plans can be executed by SysAdmin.
    """
    plan = await blackboard.get_plan(plan_id)
    
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    
    if plan.status != PlanStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot approve plan with status '{plan.status.value}'. Only pending plans can be approved."
        )
    
    updated = await blackboard.update_plan_status(plan_id, PlanStatus.APPROVED)
    logger.info(f"Plan {plan_id} approved")
    
    return updated


@router.post("/{plan_id}/reject", response_model=Plan)
async def reject_plan(
    plan_id: str,
    reason: str = Query("", description="Rejection reason"),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> Plan:
    """
    Reject a pending plan.
    
    Changes status from 'pending' to 'rejected'.
    """
    plan = await blackboard.get_plan(plan_id)
    
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    
    if plan.status != PlanStatus.PENDING:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot reject plan with status '{plan.status.value}'. Only pending plans can be rejected."
        )
    
    updated = await blackboard.update_plan_status(
        plan_id, PlanStatus.REJECTED, result=reason or "Rejected by operator"
    )
    logger.info(f"Plan {plan_id} rejected: {reason}")
    
    return updated


@router.post("/{plan_id}/execute")
async def execute_plan(
    plan_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
    sysadmin: "SysAdmin" = Depends(get_sysadmin),
) -> dict:
    """
    Execute an approved plan via SysAdmin agent.
    
    Triggers the Gemini CLI to perform Git operations.
    Only approved plans can be executed.
    """
    plan = await blackboard.get_plan(plan_id)
    
    if plan is None:
        raise HTTPException(status_code=404, detail=f"Plan '{plan_id}' not found")
    
    if plan.status != PlanStatus.APPROVED:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot execute plan with status '{plan.status.value}'. Only approved plans can be executed."
        )
    
    # Mark as executing
    await blackboard.update_plan_status(plan_id, PlanStatus.EXECUTING)
    
    try:
        # Execute via SysAdmin
        result = await sysadmin.execute_plan(plan)
        
        # Mark as completed
        await blackboard.update_plan_status(plan_id, PlanStatus.COMPLETED, result=result)
        
        logger.info(f"Plan {plan_id} executed successfully")
        return {"status": "completed", "plan_id": plan_id, "result": result}
    
    except Exception as e:
        # Mark as failed
        await blackboard.update_plan_status(plan_id, PlanStatus.FAILED, result=str(e))
        
        logger.error(f"Plan {plan_id} execution failed: {e}")
        raise HTTPException(status_code=500, detail=f"Execution failed: {e}")
