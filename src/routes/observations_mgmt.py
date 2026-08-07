# BlackBoard/src/routes/observations_mgmt.py
# @ai-rules:
# 1. [Pattern]: Management endpoints for observation CRUD — separate from read-only observations.py.
# 2. [Constraint]: All endpoints gated behind Dex OIDC auth via Depends(require_auth).
# 3. [Pattern]: DELETE does NOT validate name regex — allows cleanup of legacy names.
# 4. [Pattern]: Report endpoint returns JSON {markdown, filename} — frontend creates blob download.
"""Observation management API — delete, rename, bulk-delete, export, report."""
from __future__ import annotations

import csv
import io
import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..auth import require_auth
from ..dependencies import get_blackboard
from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

mgmt_router = APIRouter(prefix="/api/observations/manage", tags=["observations-mgmt"])


class RenameRequest(BaseModel):
    new_name: str = Field(..., min_length=2, max_length=64)


class BulkDeleteRequest(BaseModel):
    names: list[str] = Field(default_factory=list, max_length=100)


class ReportRequest(BaseModel):
    series_names: list[str] = Field(..., min_length=1, max_length=10)
    context: str = ""


# ── DELETE single series ────────────────────────────────────────────────────

@mgmt_router.delete("/{name}")
async def delete_observation(
    name: str,
    blackboard: BlackboardState = Depends(get_blackboard),
    _user=Depends(require_auth),
):
    existed = await blackboard.delete_observation(name)
    if not existed:
        raise HTTPException(status_code=404, detail=f"Observation '{name}' not found")
    return {"deleted": name}


# ── PATCH rename ────────────────────────────────────────────────────────────

@mgmt_router.patch("/{name}")
async def rename_observation(
    name: str,
    body: RenameRequest,
    blackboard: BlackboardState = Depends(get_blackboard),
    _user=Depends(require_auth),
):
    try:
        BlackboardState.validate_obs_name(body.new_name)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    try:
        await blackboard.rename_observation(name, body.new_name)
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        if "already exists" in msg:
            raise HTTPException(status_code=409, detail=msg)
        raise HTTPException(status_code=400, detail=msg)
    return {"renamed": name, "new_name": body.new_name}


# ── POST bulk-delete ────────────────────────────────────────────────────────

@mgmt_router.post("/bulk-delete")
async def bulk_delete_observations(
    body: BulkDeleteRequest,
    blackboard: BlackboardState = Depends(get_blackboard),
    _user=Depends(require_auth),
):
    deleted = 0
    for name in body.names:
        if await blackboard.delete_observation(name):
            deleted += 1
    return {"deleted": deleted}


# ── GET export (CSV or JSON) ────────────────────────────────────────────────

@mgmt_router.get("/export")
async def export_observations(
    format: str = "json",
    names: str | None = None,
    blackboard: BlackboardState = Depends(get_blackboard),
    _user=Depends(require_auth),
):
    obs_data = await blackboard.list_observations()
    all_series = obs_data.get("observations", [])

    if names:
        name_set = set(names.split(","))
        all_series = [s for s in all_series if s["name"] in name_set]

    now_str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_slug = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    if format == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["name", "timestamp", "value", "unit", "trend", "service", "event_id"])
        for s in all_series:
            for p in s["points"]:
                writer.writerow([
                    s["name"], p["timestamp"], p["value"],
                    p.get("unit", ""), s["trend"],
                    p.get("service", ""), p.get("event_id", ""),
                ])
        return {
            "content": buf.getvalue(),
            "filename": f"observations-{date_slug}.csv",
            "format": "csv",
        }

    json_series = []
    for s in all_series:
        json_series.append({
            "name": s["name"], "count": s["count"],
            "min": s["min"], "max": s["max"],
            "trend": s["trend"], "unit": s.get("unit", ""),
            "span_minutes": s["span_minutes"], "points": s["points"],
        })
    return {
        "content": {
            "exported_at": now_str,
            "series_count": len(json_series),
            "series": json_series,
        },
        "filename": f"observations-{date_slug}.json",
        "format": "json",
    }


# ── POST report (LLM analysis) ─────────────────────────────────────────────

def _get_report_client():
    """Create a genai Client for report generation."""
    from google import genai
    return genai.Client(
        vertexai=True,
        project=os.getenv("GCP_PROJECT", ""),
        location=os.getenv("GCP_LOCATION", "global"),
    )


@mgmt_router.post("/report")
async def generate_observations_report(
    body: ReportRequest,
    blackboard: BlackboardState = Depends(get_blackboard),
    _user=Depends(require_auth),
):
    import asyncio
    from ..reports.observations_reporter import generate_report

    client = _get_report_client()
    model = os.getenv("LLM_MODEL_OBSERVATIONS_REPORT", "gemini-3.5-flash-lite")
    async with asyncio.timeout(90):
        result = await generate_report(blackboard, client, model, body.series_names, body.context)
    return result
