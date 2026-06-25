# BlackBoard/src/routes/jira.py
# @ai-rules:
# 1. [Pattern]: Endpoints query Jira directly; retry/reanalyze clear Redis state via Depends(get_blackboard).
# 2. [Constraint]: Returns [] when JIRA_URL not configured (graceful degradation).
# 3. [Pattern]: Same httpx + Basic auth pattern as headhunter_jira.py.
# 4. [Constraint]: No hardcoded org-specific values -- all from env vars.
# 5. [Pattern]: Redis key format: darwin:headhunter:jira:{issue_key} (shared with headhunter_jira.py).
"""Jira Missions API -- exposes tracked Jira issues for the Operations Center UI."""
from __future__ import annotations

import base64
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException

from ..dependencies import get_blackboard
from ..state.blackboard import BlackboardState
from ..agents.headhunter_jira import HeadhunterJira

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/jira", tags=["jira"])

_REDIS_PREFIX = HeadhunterJira.REDIS_PREFIX


def _jira_config() -> tuple[str, dict[str, str]] | None:
    """Return (base_url, headers) or None if Jira is not configured."""
    jira_url = os.getenv("JIRA_URL", "").rstrip("/")
    email = os.getenv("JIRA_EMAIL", "")
    token = os.getenv("JIRA_API_TOKEN", "")
    if not jira_url or not email or not token:
        return None
    creds = base64.b64encode(f"{email}:{token}".encode()).decode()
    headers = {"Authorization": f"Basic {creds}", "Accept": "application/json", "Content-Type": "application/json"}
    return jira_url, headers


def _infer_phase(status: str, has_darwin_comment: bool) -> str:
    if status.lower() == "planning" and has_darwin_comment:
        return "analyzed"
    if status.lower() == "planning":
        return "pending"
    if status.lower() == "to do":
        return "approved"
    return "executing"


@router.get("/missions")
async def list_missions():
    """List all Jira issues tracked by Darwin (Planning/To Do/In Progress with darwin label)."""
    cfg = _jira_config()
    if not cfg:
        return []

    base_url, headers = cfg
    label = os.getenv("HEADHUNTER_JIRA_LABEL", "darwin")
    bot_account_id = os.getenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "")

    jql = f'labels = "{label}" AND status in ("Planning", "To Do", "In Progress") ORDER BY created DESC'

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{base_url}/rest/api/3/search/jql",
                headers=headers,
                params={"jql": jql, "fields": "summary,status,priority,labels,comment", "maxResults": 50},
            )
            if not resp.is_success:
                logger.warning("Jira search failed: %s", resp.status_code)
                return []
            data = resp.json()
    except Exception:
        logger.exception("Jira search error")
        return []

    results = []
    for issue in data.get("issues", []):
        fields = issue.get("fields", {})
        status_name = fields.get("status", {}).get("name", "")
        comments = fields.get("comment", {}).get("comments", [])

        darwin_comments = [c for c in comments if c.get("author", {}).get("accountId") == bot_account_id] if bot_account_id else []
        latest_analysis = darwin_comments[-1].get("body", "") if darwin_comments else None

        # Convert Atlassian Document Format to plain text if needed
        if latest_analysis and isinstance(latest_analysis, dict):
            latest_analysis = _adf_to_text(latest_analysis)

        results.append({
            "key": issue["key"],
            "summary": fields.get("summary", ""),
            "status": status_name,
            "priority": fields.get("priority", {}).get("name", "Medium"),
            "labels": fields.get("labels", []),
            "phase": _infer_phase(status_name, bool(darwin_comments)),
            "issue_url": f"{base_url}/browse/{issue['key']}",
            "analysis": latest_analysis,
        })

    return results


def _adf_to_text(adf: dict) -> str:
    """Recursively extract text from Atlassian Document Format."""
    if adf.get("type") == "text":
        return adf.get("text", "")
    parts = []
    for node in adf.get("content", []):
        parts.append(_adf_to_text(node))
    return "\n".join(p for p in parts if p)


@router.post("/missions/{key}/approve")
async def approve_mission(key: str):
    """Transition a Jira issue to 'To Do' status."""
    cfg = _jira_config()
    if not cfg:
        raise HTTPException(503, "Jira not configured")

    base_url, headers = cfg
    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(f"{base_url}/rest/api/3/issue/{key}/transitions", headers=headers)
        if not resp.is_success:
            raise HTTPException(resp.status_code, f"Failed to get transitions for {key}")

        transitions = resp.json().get("transitions", [])
        todo_transition = next((t for t in transitions if "to do" in t["name"].lower()), None)
        if not todo_transition:
            raise HTTPException(404, f"No 'To Do' transition available for {key}")

        resp = await client.post(
            f"{base_url}/rest/api/3/issue/{key}/transitions",
            headers=headers,
            json={"transition": {"id": todo_transition["id"]}},
        )
        if not resp.is_success:
            raise HTTPException(resp.status_code, f"Failed to approve {key}")

    return {"status": "approved", "key": key}


@router.post("/missions/{key}/reanalyze")
async def reanalyze_mission(key: str, blackboard: BlackboardState = Depends(get_blackboard)):
    """Clear Redis state and post a comment requesting re-analysis."""
    await blackboard.clear_jira_mission_state(key)

    cfg = _jira_config()
    if not cfg:
        raise HTTPException(503, "Jira not configured")

    base_url, headers = cfg
    bot_account_id = os.getenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "")

    comment_body = {
        "type": "doc", "version": 1,
        "content": [{"type": "paragraph", "content": [
            {"type": "mention", "attrs": {"id": bot_account_id, "text": "@darwin"}} if bot_account_id else {"type": "text", "text": "@darwin"},
            {"type": "text", "text": " Please re-analyze this issue."},
        ]}],
    }

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.post(
            f"{base_url}/rest/api/3/issue/{key}/comment",
            headers=headers,
            json={"body": comment_body},
        )
        if not resp.is_success:
            raise HTTPException(resp.status_code, f"Failed to post comment on {key}")

    return {"status": "reanalyze_requested", "key": key}


@router.post("/missions/{key}/dismiss")
async def dismiss_mission(key: str):
    """Remove the darwin label from the issue."""
    cfg = _jira_config()
    if not cfg:
        raise HTTPException(503, "Jira not configured")

    base_url, headers = cfg
    label = os.getenv("HEADHUNTER_JIRA_LABEL", "darwin")

    async with httpx.AsyncClient(timeout=15) as client:
        # Get current labels
        resp = await client.get(f"{base_url}/rest/api/3/issue/{key}", headers=headers, params={"fields": "labels"})
        if not resp.is_success:
            raise HTTPException(resp.status_code, f"Failed to get issue {key}")

        current_labels = resp.json().get("fields", {}).get("labels", [])
        new_labels = [lbl for lbl in current_labels if lbl != label]

        resp = await client.put(
            f"{base_url}/rest/api/3/issue/{key}",
            headers=headers,
            json={"fields": {"labels": new_labels}},
        )
        if not resp.is_success:
            raise HTTPException(resp.status_code, f"Failed to update labels on {key}")

    return {"status": "dismissed", "key": key}


@router.post("/missions/{key}/retry")
async def retry_mission(key: str, blackboard: BlackboardState = Depends(get_blackboard)):
    """Clear Darwin state and re-trigger processing for a Jira issue."""
    await blackboard.clear_jira_mission_state(key)

    cfg = _jira_config()
    if cfg:
        base_url, headers = cfg
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{base_url}/rest/api/3/issue/{key}", headers=headers, params={"fields": "status"})
            if resp.is_success:
                current = resp.json().get("fields", {}).get("status", {}).get("name", "")
                if current.lower() not in ("to do", "planning"):
                    tr_resp = await client.get(f"{base_url}/rest/api/3/issue/{key}/transitions", headers=headers)
                    if tr_resp.is_success:
                        todo = next((t for t in tr_resp.json().get("transitions", []) if "to do" in t["name"].lower()), None)
                        if todo:
                            await client.post(
                                f"{base_url}/rest/api/3/issue/{key}/transitions",
                                headers=headers,
                                json={"transition": {"id": todo["id"]}},
                            )

    return {"status": "retried", "key": key}
