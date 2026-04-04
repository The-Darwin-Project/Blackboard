# BlackBoard/src/adapters/smartsheet_incident.py
# @ai-rules:
# 1. [Pattern]: Hexagonal adapter -- httpx-based Smartsheet API client. No domain logic.
# 2. [Pattern]: Bidirectional column maps: _col_by_title (write) and _col_by_id (read).
# 3. [Pattern]: list_incidents() uses 120s in-memory TTL cache to collapse concurrent reads.
# 4. [Constraint]: Column titles must match exact sheet probe results. See plan for full list.
"""
Smartsheet incident adapter -- create and list incident rows.

Used by Brain (create_incident function call) and the /incidents/list API route.
"""
from __future__ import annotations

import logging
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.smartsheet.com/2.0"
_CACHE_TTL = 120


class SmartsheetIncidentAdapter:
    """Bidirectional Smartsheet adapter: write incidents + read them back."""

    def __init__(self, api_token: str, sheet_id: str):
        self._token = api_token
        self._sheet_id = sheet_id
        self._col_by_title: dict[str, int] = {}
        self._col_by_id: dict[int, str] = {}
        self._multi_picklist_cols: set[int] = set()
        self._permalink: str = ""
        self._rows_cache: list[dict] = []
        self._rows_cache_ts: float = 0.0

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self._token}", "Content-Type": "application/json"}

    async def _ensure_columns(self) -> None:
        """Fetch column schema + permalink once per process lifetime."""
        if self._col_by_title:
            return
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BASE_URL}/sheets/{self._sheet_id}/columns", headers=self._headers())
            resp.raise_for_status()
        for col in resp.json().get("data", []):
            self._col_by_title[col["title"]] = col["id"]
            self._col_by_id[col["id"]] = col["title"]
            if col.get("options") and col.get("type") == "TEXT_NUMBER":
                self._multi_picklist_cols.add(col["id"])
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(f"{BASE_URL}/sheets/{self._sheet_id}?include=", headers=self._headers())
            if resp.status_code == 200:
                self._permalink = resp.json().get("permalink", "")
        if not self._permalink:
            self._permalink = f"https://app.smartsheet.com/sheets/{self._sheet_id}"
        logger.info("Smartsheet column cache loaded: %d columns (%d multi-picklist), permalink=%s",
                     len(self._col_by_title), len(self._multi_picklist_cols), self._permalink)

    async def create_incident(self, fields: dict) -> dict:
        """Add an incident row. Returns {"row_id": ..., "sheet_url": ...}."""
        await self._ensure_columns()
        cells = []
        for title, value in fields.items():
            col_id = self._col_by_title.get(title)
            if col_id and value:
                if col_id in self._multi_picklist_cols:
                    values = [v.strip() for v in str(value).split(",")]
                    cells.append({"columnId": col_id, "objectValue": {"objectType": "MULTI_PICKLIST", "values": values}})
                else:
                    cells.append({"columnId": col_id, "value": value})
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{BASE_URL}/sheets/{self._sheet_id}/rows",
                headers=self._headers(),
                json=[{"toBottom": True, "cells": cells}],
            )
            if resp.status_code >= 400:
                logger.error("Smartsheet API error %d: %s", resp.status_code, resp.text[:500])
            resp.raise_for_status()
        result = resp.json().get("result", [{}])
        row_id = result[0].get("id", "") if result else ""
        self._rows_cache_ts = 0.0
        return {"row_id": row_id, "sheet_url": self._permalink}

    async def list_incidents(self, label_filter: str = "darwin-auto") -> list[dict]:
        """Read incidents filtered by label. Uses 120s TTL cache."""
        now = time.time()
        if self._rows_cache and (now - self._rows_cache_ts) < _CACHE_TTL:
            return self._rows_cache

        await self._ensure_columns()
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{BASE_URL}/sheets/{self._sheet_id}", headers=self._headers())
            resp.raise_for_status()
        sheet = resp.json()

        col_map = {c["id"]: c["title"] for c in sheet.get("columns", [])}
        self._col_by_id.update(col_map)

        incidents: list[dict] = []
        for row in sheet.get("rows", []):
            record: dict[str, str] = {}
            for cell in row.get("cells", []):
                title = self._col_by_id.get(cell.get("columnId", 0), "")
                record[title] = str(cell.get("displayValue") or cell.get("value") or "").strip('"')
            if label_filter:
                row_labels = {l.strip().strip('"') for l in record.get("Labels", "").split(",")}
                if label_filter not in row_labels:
                    continue
            record["sheet_url"] = self._permalink
            incidents.append(record)

        incidents.sort(key=lambda r: r.get("Date", ""), reverse=True)
        self._rows_cache = incidents
        self._rows_cache_ts = now
        logger.info("Smartsheet incidents refreshed: %d rows (label=%s)", len(incidents), label_filter)
        return incidents
