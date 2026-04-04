# BlackBoard/src/routes/incidents.py
# @ai-rules:
# 1. [Pattern]: Read-only endpoint. Adapter handles caching + filtering.
# 2. [Pattern]: Returns [] when Smartsheet not configured -- graceful degradation.
# 3. [Pattern]: _normalize_keys maps Smartsheet title-case to snake_case for stable API contract.
"""
Incidents API -- lists Darwin-created Smartsheet incidents.
"""
from __future__ import annotations

import logging
import os
import re

from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/incidents", tags=["incidents"])

_adapter = None
_adapter_checked = False

_KEY_MAP = {
    "Issue Key": "issue_key",
    "Date": "date",
    "Platform": "platform",
    "Status": "status",
    "Affected Versions": "affected_versions",
    "Resolved Date": "resolved_date",
    "Summary": "summary",
    "Reason": "reason",
    "Slack Thread": "slack_thread",
    "Jira Issue": "jira_issue",
    "Build Number": "build_number",
    "Fix PR": "fix_pr",
    "Red Hat - SNOW": "snow",
    "Issue Type": "issue_type",
    "Priority": "priority",
    "Labels": "labels",
    "Components": "components",
    "Reporter e-mail": "reporter_email",
    "Reporter Display Name": "reporter_name",
    "sheet_url": "sheet_url",
}


def _normalize_keys(row: dict) -> dict:
    """Map Smartsheet title-case keys to snake_case for a stable API contract."""
    return {_KEY_MAP.get(k, re.sub(r"[^a-z0-9]+", "_", k.lower()).strip("_")): v for k, v in row.items()}


def _get_adapter():
    global _adapter, _adapter_checked
    if not _adapter_checked:
        _adapter_checked = True
        token = os.environ.get("SMARTSHEET_INCIDENT_TOKEN", "")
        sheet_id = os.environ.get("SMARTSHEET_INCIDENT_SHEET_ID", "")
        if token and sheet_id:
            from ..adapters.smartsheet_incident import SmartsheetIncidentAdapter
            _adapter = SmartsheetIncidentAdapter(token, sheet_id)
            logger.info("Incidents route: Smartsheet adapter initialized (sheet %s)", sheet_id)
        else:
            logger.info("Incidents route: Smartsheet not configured, /incidents/list returns []")
    return _adapter


@router.get("/list")
async def list_incidents() -> list[dict]:
    """List Darwin-created incidents from Smartsheet, filtered by darwin-auto label."""
    adapter = _get_adapter()
    if not adapter:
        return []
    try:
        rows = await adapter.list_incidents(label_filter="darwin-auto")
        return [_normalize_keys(row) for row in rows]
    except Exception as e:
        logger.warning("Failed to fetch incidents from Smartsheet: %s", e)
        return []
