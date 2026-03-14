# BlackBoard/src/routes/timekeeper.py
# @ai-rules:
# 1. [Pattern]: Thin route -- delegates to BlackboardState for persistence.
# 2. [Constraint]: Mutation endpoints require Depends(require_auth). Reads are open (route gated on DEX_ENABLED).
# 3. [Pattern]: Owner-only mutations compare sched.created_by == user.email.
# 4. [Pattern]: Refine endpoint throttled with module-level Semaphore(1), returns 429 when busy.
"""TimeKeeper CRUD + LLM refine endpoint for scheduled task management."""
from __future__ import annotations

import asyncio
import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request

from ..auth import UserContext, require_auth
from ..dependencies import get_blackboard
from ..models import (
    RefineRequest,
    RefineResponse,
    ScheduleCreateRequest,
    ScheduledEvent,
)
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/timekeeper", tags=["timekeeper"])

TIMEKEEPER_MAX_PER_USER = int(os.getenv("TIMEKEEPER_MAX_PER_USER", "10"))
TIMEKEEPER_MAX_TOTAL = int(os.getenv("TIMEKEEPER_MAX_TOTAL", "50"))

_refine_semaphore = asyncio.Semaphore(1)
_brain_context_cache: str | None = None


def _load_brain_context() -> str:
    """Load Brain skill files once and cache. Gives the refiner LLM
    the same knowledge the Brain operates with."""
    global _brain_context_cache
    if _brain_context_cache is not None:
        return _brain_context_cache

    from pathlib import Path

    skills_dir = Path(__file__).parent.parent / "agents" / "brain_skills"
    helm_dir = Path(__file__).parent.parent.parent / "helm" / "files"

    sections: list[str] = []

    skill_files = [
        ("Brain Identity & Agents", skills_dir / "always" / "00-identity.md"),
        ("Function Rules", skills_dir / "always" / "01-function-rules.md"),
        ("Decision Guidelines", skills_dir / "always" / "06-decision-guidelines.md"),
        ("TimeKeeper Source Protocol", skills_dir / "source" / "timekeeper.md"),
    ]
    for label, path in skill_files:
        if path.exists():
            content = path.read_text().strip()
            for line in content.splitlines():
                if line.startswith("---") or line.startswith("description:") or line.startswith("tags:") or line.startswith("requires:"):
                    continue
                sections.append(line)
            sections.append("")

    agent_files = [
        ("Developer Agent Rules", helm_dir / "developer.md"),
        ("SysAdmin Agent Rules", helm_dir / "sysadmin.md"),
        ("Architect Agent Rules", helm_dir / "architect.md"),
    ]
    for label, path in agent_files:
        if path.exists():
            text = path.read_text().strip()
            summary = text[:800]
            if len(text) > 800:
                summary += "\n... (truncated)"
            sections.append(f"## {label}\n{summary}\n")

    _brain_context_cache = "\n".join(sections)
    logger.info("Brain context loaded for refiner (%d chars)", len(_brain_context_cache))
    return _brain_context_cache


@router.post("", status_code=201)
async def create_schedule(
    req: ScheduleCreateRequest,
    user: UserContext = Depends(require_auth),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """Create a new scheduled task."""
    user_count = await blackboard.count_user_schedules(user.email)
    if user_count >= TIMEKEEPER_MAX_PER_USER:
        raise HTTPException(422, f"Max {TIMEKEEPER_MAX_PER_USER} schedules per user")

    all_schedules = await blackboard.list_schedules()
    if len(all_schedules) >= TIMEKEEPER_MAX_TOTAL:
        raise HTTPException(422, f"System limit: max {TIMEKEEPER_MAX_TOTAL} active schedules")

    sched = req.to_scheduled_event(created_by=user.email)
    sched_id = await blackboard.create_schedule(sched)
    logger.info("Schedule created: %s (%s) by %s", sched_id, sched.name, user.email)
    return {"id": sched_id, "status": "created"}


@router.get("")
async def list_schedules(
    blackboard: BlackboardState = Depends(get_blackboard),
) -> list[dict]:
    """List all schedules."""
    schedules = await blackboard.list_schedules()
    return [s.model_dump() for s in schedules]


@router.get("/{sched_id}")
async def get_schedule(
    sched_id: str,
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """Get a single schedule."""
    sched = await blackboard.get_schedule(sched_id)
    if not sched:
        raise HTTPException(404, "Schedule not found")
    return sched.model_dump()


@router.put("/{sched_id}")
async def update_schedule(
    sched_id: str,
    req: ScheduleCreateRequest,
    user: UserContext = Depends(require_auth),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """Update a schedule (owner only)."""
    existing = await blackboard.get_schedule(sched_id)
    if not existing:
        raise HTTPException(404, "Schedule not found")
    if existing.created_by != user.email:
        raise HTTPException(403, "Not the schedule owner")

    updated = req.to_scheduled_event(created_by=user.email)
    updates = updated.model_dump(exclude={"id", "created_by", "last_fired"})
    await blackboard.update_schedule(sched_id, updates)
    return {"id": sched_id, "status": "updated"}


@router.delete("/{sched_id}")
async def delete_schedule(
    sched_id: str,
    user: UserContext = Depends(require_auth),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """Delete a schedule (owner only)."""
    existing = await blackboard.get_schedule(sched_id)
    if not existing:
        raise HTTPException(404, "Schedule not found")
    if existing.created_by != user.email:
        raise HTTPException(403, "Not the schedule owner")

    await blackboard.delete_schedule(sched_id, user.email)
    return {"id": sched_id, "status": "deleted"}


@router.patch("/{sched_id}/toggle")
async def toggle_schedule(
    sched_id: str,
    user: UserContext = Depends(require_auth),
    blackboard: BlackboardState = Depends(get_blackboard),
) -> dict:
    """Enable/disable a schedule (owner only). ZREM on pause, ZADD on resume."""
    existing = await blackboard.get_schedule(sched_id)
    if not existing:
        raise HTTPException(404, "Schedule not found")
    if existing.created_by != user.email:
        raise HTTPException(403, "Not the schedule owner")

    new_state = not existing.enabled
    await blackboard.toggle_schedule(sched_id, new_state)
    return {"id": sched_id, "enabled": new_state}


@router.post("/refine")
async def refine_instructions(
    req: RefineRequest,
    user: UserContext = Depends(require_auth),
) -> RefineResponse:
    """LLM-assisted instruction refinement. Throttled to 1 concurrent call system-wide."""
    if not _refine_semaphore._value:
        raise HTTPException(429, "Refine busy, try again in a few seconds")

    async with _refine_semaphore:
        try:
            from ..agents.llm import create_adapter

            model = os.getenv("LLM_MODEL_HEADHUNTER", "gemini-2.0-flash-lite")
            adapter = create_adapter(
                provider="gemini",
                project=os.getenv("GCP_PROJECT", ""),
                location=os.getenv("GCP_LOCATION", "global"),
                model_name=model,
            )

            context_parts = []
            if req.repo_url:
                context_parts.append(f"Repository: {req.repo_url}")
            if req.mr_url:
                context_parts.append(f"MR: {req.mr_url}")
            if req.service:
                context_parts.append(f"Service: {req.service}")
            context_str = "\n".join(context_parts) if context_parts else "No specific context provided."

            brain_context = _load_brain_context()

            system_prompt = (
                "You are a prompt refinement assistant for an autonomous AI operations system called Darwin.\n"
                "Below is the system's actual Brain knowledge -- its identity, agents, decision patterns, and protocols.\n"
                "Use this to generate instructions that perfectly align with how the Brain reasons and routes tasks.\n\n"
                f"=== BRAIN KNOWLEDGE ===\n{brain_context}\n=== END BRAIN KNOWLEDGE ===\n\n"
                "Your job: refine the user's raw task description into clear instructions that:\n"
                "1. Describe the EXPECTED OUTCOME (what 'done' looks like) -- not HOW to achieve it\n"
                "2. Include SUCCESS CRITERIA the Brain can verify\n"
                "3. Specify a FAILURE PATH (what to do if it can't complete)\n"
                "4. Use vocabulary and patterns the Brain understands from its knowledge above\n"
                "5. Never prescribe which agent to use or what commands to run\n\n"
                "Return JSON with two fields:\n"
                '- "refined": the improved instruction text (max 500 chars)\n'
                '- "reasoning": one sentence explaining what you changed and why'
            )

            prompt = f"Context:\n{context_str}\n\nUser intent:\n{req.raw_intent}"

            response = await adapter.generate(
                contents=prompt,
                system_instruction=system_prompt,
                temperature=0.3,
                max_output_tokens=1024,
            )

            import json
            try:
                data = json.loads(response.text)
                return RefineResponse(
                    refined=data.get("refined", response.text),
                    reasoning=data.get("reasoning", "Refined for clarity and specificity."),
                )
            except (json.JSONDecodeError, KeyError):
                return RefineResponse(
                    refined=response.text.strip(),
                    reasoning="Raw LLM output (JSON parse failed).",
                )

        except Exception as e:
            logger.exception("Refine endpoint error")
            raise HTTPException(503, f"Refine unavailable: {e}") from e
