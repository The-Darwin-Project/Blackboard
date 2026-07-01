# BlackBoard/src/adapters/jira_incident.py
# @ai-rules:
# 1. [Pattern]: Hexagonal adapter -- httpx-based Jira REST API client. No domain logic.
# 2. [Constraint]: Auth via Basic (email:token). All org-specific values from env vars with empty defaults.
# 3. [Pattern]: list_incidents() uses 120s in-memory TTL cache to collapse concurrent reads.
# 4. [Pattern]: _adf_to_text is local (do NOT import from routes -- hexagonal boundary).
# 5. [Constraint]: create_incident uses marklassian for Markdown→ADF conversion.
# 6. [Pattern]: Platform stored as Jira label; extracted on read via VALID_PLATFORMS intersection.
"""
Jira incident adapter -- create, list, search, and extend incidents.

Used by Nightwatcher (create/extend), Brain (direct escalation fallback),
and the /incidents/list API route.
"""
from __future__ import annotations

import base64
import logging
import os
import time

import httpx
import marklassian

logger = logging.getLogger(__name__)

_CACHE_TTL = 120


def _adf_to_text(adf: dict) -> str:
    """Recursively extract text from Atlassian Document Format."""
    if adf.get("type") == "text":
        return adf.get("text", "")
    parts = []
    for node in adf.get("content", []):
        parts.append(_adf_to_text(node))
    return "\n".join(p for p in parts if p)


class JiraIncidentAdapter:
    """Bidirectional Jira adapter: create/extend incidents + read them back."""

    def __init__(
        self,
        base_url: str,
        email: str,
        api_token: str,
        project_key: str,
        platforms: list[str] | None = None,
    ):
        self._base_url = base_url.rstrip("/")
        creds = base64.b64encode(f"{email}:{api_token}".encode()).decode()
        self._headers = {
            "Authorization": f"Basic {creds}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        self._project_key = project_key
        self._valid_platforms: list[str] = platforms or []
        self._rows_cache: list[dict] = []
        self._rows_cache_ts: float = 0.0

    def _issue_url(self, key: str) -> str:
        return f"{self._base_url}/browse/{key}"

    def _normalize_issue(self, issue: dict) -> dict:
        """Normalize a Jira issue into a flat dict for consumers."""
        fields = issue.get("fields", {})
        key = issue.get("key", "")
        raw_labels = fields.get("labels", [])
        platform = ""
        if self._valid_platforms:
            matches = set(raw_labels) & set(self._valid_platforms)
            platform = sorted(matches)[0] if matches else ""

        desc_raw = fields.get("description")
        description = _adf_to_text(desc_raw) if isinstance(desc_raw, dict) else (desc_raw or "")

        severity_field_id = os.getenv("JIRA_INCIDENT_SEVERITY_FIELD", "")
        severity = ""
        if severity_field_id:
            sev_obj = fields.get(severity_field_id)
            if isinstance(sev_obj, dict):
                severity = sev_obj.get("value", "")
            elif isinstance(sev_obj, str):
                severity = sev_obj

        return {
            "issue_key": key,
            "issue_url": self._issue_url(key),
            "summary": fields.get("summary", ""),
            "description": description,
            "status": fields.get("status", {}).get("name", ""),
            "priority": fields.get("priority", {}).get("name", ""),
            "severity": severity,
            "platform": platform,
            "labels": raw_labels,
            "components": [c.get("name", "") for c in fields.get("components", [])],
            "date": fields.get("created", ""),
        }

    async def create_incident(self, fields: dict) -> dict:
        """Create a Jira issue. Returns {"issue_key": ..., "issue_url": ...}."""
        project_key = fields.get("project_key") or self._project_key
        if not project_key:
            raise ValueError("project_key is required to create a Jira incident")

        labels = list(fields.get("labels", []))
        platform = fields.get("platform", "")
        if platform and platform not in labels:
            labels.append(platform)

        description_md = fields.get("description", "")
        description_adf = marklassian.markdown_to_adf(description_md) if description_md else None

        jira_fields: dict = {
            "project": {"key": project_key},
            "issuetype": {"name": fields.get("issue_type", "")},
            "summary": fields.get("summary", ""),
            "priority": {"name": fields.get("priority", "Normal")},
            "labels": labels,
        }
        if description_adf:
            jira_fields["description"] = description_adf
        if fields.get("components"):
            jira_fields["components"] = [{"name": c} for c in fields["components"]]

        severity_field_id = fields.get("severity_field_id", "")
        severity_value = fields.get("severity", "")
        if severity_field_id and severity_value:
            jira_fields[severity_field_id] = {"value": severity_value}

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/rest/api/3/issue",
                headers=self._headers,
                json={"fields": jira_fields},
            )
            if resp.status_code >= 400:
                safe = resp.text[:500].replace("\n", " ").replace("\r", "")
                logger.error("Jira create_incident error %d: %s", resp.status_code, safe)
            resp.raise_for_status()

        result = resp.json()
        issue_key = result.get("key", "")
        self._rows_cache_ts = 0.0
        return {"issue_key": issue_key, "issue_url": self._issue_url(issue_key)}

    async def list_incidents(self, label_filter: str = "") -> list[dict]:
        """Read incidents via JQL. Uses 120s TTL in-memory cache."""
        now = time.time()
        if self._rows_cache and (now - self._rows_cache_ts) < _CACHE_TTL:
            return self._rows_cache

        jql_parts = [f'project = "{self._project_key}"']
        if label_filter:
            jql_parts.append(f'labels = "{label_filter}"')
        jql = " AND ".join(jql_parts) + " ORDER BY created DESC"

        fields_param = "summary,status,priority,labels,components,description,created"
        severity_field_id = os.getenv("JIRA_INCIDENT_SEVERITY_FIELD", "")
        if severity_field_id:
            fields_param += f",{severity_field_id}"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self._base_url}/rest/api/3/search/jql",
                    headers=self._headers,
                    params={"jql": jql, "fields": fields_param, "maxResults": 100},
                )
                if not resp.is_success:
                    logger.warning("Jira list_incidents JQL failed: %d", resp.status_code)
                    return []
                data = resp.json()
        except Exception:
            logger.exception("Jira list_incidents error")
            return []

        incidents = [self._normalize_issue(iss) for iss in data.get("issues", [])]
        self._rows_cache = incidents
        self._rows_cache_ts = now
        logger.info("Jira incidents refreshed: %d issues (label=%s)", len(incidents), label_filter)
        return incidents

    async def search_open_incidents(self) -> list[dict]:
        """Search for open (non-closed) incidents. No cache -- always live."""
        label_filter = os.getenv("JIRA_INCIDENT_LABEL_FILTER", "")
        closed_status = os.getenv("JIRA_INCIDENT_STATUSES", "New,Closed").split(",")[-1].strip()

        jql_parts = [f'project = "{self._project_key}"']
        if label_filter:
            jql_parts.append(f'labels = "{label_filter}"')
        jql_parts.append(f'status != "{closed_status}"')
        jql = " AND ".join(jql_parts) + " ORDER BY created DESC"

        fields_param = "summary,status,priority,labels,components,description,created"
        severity_field_id = os.getenv("JIRA_INCIDENT_SEVERITY_FIELD", "")
        if severity_field_id:
            fields_param += f",{severity_field_id}"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{self._base_url}/rest/api/3/search/jql",
                    headers=self._headers,
                    params={"jql": jql, "fields": fields_param, "maxResults": 50},
                )
                if not resp.is_success:
                    logger.warning("Jira search_open_incidents JQL failed: %d", resp.status_code)
                    return []
                data = resp.json()
        except Exception:
            logger.exception("Jira search_open_incidents error")
            return []

        return [self._normalize_issue(iss) for iss in data.get("issues", [])]

    async def add_comment(self, issue_key: str, body_markdown: str) -> dict:
        """Post a comment to an existing Jira issue. Returns {"comment_id": ..., "issue_url": ...}."""
        body_adf = marklassian.markdown_to_adf(body_markdown) if body_markdown else {
            "type": "doc", "version": 1,
            "content": [{"type": "paragraph", "content": [{"type": "text", "text": "(no details)"}]}],
        }

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self._base_url}/rest/api/3/issue/{issue_key}/comment",
                headers=self._headers,
                json={"body": body_adf},
            )
            if resp.status_code >= 400:
                safe = resp.text[:500].replace("\n", " ").replace("\r", "")
                logger.error("Jira add_comment error %d on %s: %s", resp.status_code, issue_key, safe)
            resp.raise_for_status()

        result = resp.json()
        return {"comment_id": result.get("id", ""), "issue_url": self._issue_url(issue_key)}
