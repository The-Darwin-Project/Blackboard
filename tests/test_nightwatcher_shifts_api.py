# tests/test_nightwatcher_shifts_api.py
# @ai-rules:
# 1. [Pattern]: FastAPI TestClient with dependency override for blackboard.
# 2. [Constraint]: No real Redis. Blackboard methods mocked via AsyncMock.
# 3. [Pattern]: Tests: /shifts/current, /shifts/list, /shifts/{date}/{window}.
"""Unit tests for Shifts API routes."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.dependencies import get_blackboard
from src.models import ShiftReport
from src.routes.shifts import router


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_blackboard():
    bb = AsyncMock()
    bb.count_pending_escalations = AsyncMock(return_value=0)
    bb.list_shift_reports = AsyncMock(return_value=[])
    bb.get_shift_report = AsyncMock(return_value=None)
    return bb


@pytest.fixture
def client(mock_blackboard):
    app = FastAPI()
    app.include_router(router)
    app.dependency_overrides[get_blackboard] = lambda: mock_blackboard
    return TestClient(app)


# =========================================================================
# GET /shifts/current
# =========================================================================

class TestGetCurrentShift:
    def test_returns_pending_count(self, client, mock_blackboard):
        mock_blackboard.count_pending_escalations = AsyncMock(return_value=5)
        resp = client.get("/shifts/current")
        assert resp.status_code == 200
        data = resp.json()
        assert data["pending_count"] == 5

    def test_returns_next_sweep(self, client, mock_blackboard):
        resp = client.get("/shifts/current")
        data = resp.json()
        assert "next_sweep_utc" in data

    def test_returns_enabled_flag(self, client, mock_blackboard):
        with patch.dict("os.environ", {"NIGHTWATCHER_ENABLED": "true"}):
            resp = client.get("/shifts/current")
        data = resp.json()
        assert data["enabled"] is True


# =========================================================================
# GET /shifts/list
# =========================================================================

class TestListShifts:
    def test_default_list(self, client, mock_blackboard):
        mock_blackboard.list_shift_reports = AsyncMock(return_value=[
            {"shift_date": "2026-04-29", "window": "morning",
             "status": "completed", "escalation_count": 5,
             "incident_count": 1, "noise_reduction_pct": 80.0},
        ])
        resp = client.get("/shifts/list")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["shift_date"] == "2026-04-29"

    def test_iso_week_filter(self, client, mock_blackboard):
        mock_blackboard.list_shift_reports = AsyncMock(return_value=[])
        resp = client.get("/shifts/list?week=2026-W18")
        assert resp.status_code == 200
        mock_blackboard.list_shift_reports.assert_awaited_once()

    def test_invalid_week_returns_400(self, client, mock_blackboard):
        resp = client.get("/shifts/list?week=not-a-week")
        assert resp.status_code == 400

    def test_days_param(self, client, mock_blackboard):
        mock_blackboard.list_shift_reports = AsyncMock(return_value=[])
        resp = client.get("/shifts/list?days=14")
        assert resp.status_code == 200


# =========================================================================
# GET /shifts/{date}/{window}
# =========================================================================

class TestGetShiftDetail:
    def test_returns_report(self, client, mock_blackboard):
        report = ShiftReport(
            shift_date="2026-04-29", window="morning",
            window_start="s", window_end="e", status="completed",
            metrics={"escalation_count": 3, "incident_count": 1},
        )
        mock_blackboard.get_shift_report = AsyncMock(return_value=report)
        resp = client.get("/shifts/2026-04-29/morning")
        assert resp.status_code == 200
        data = resp.json()
        assert data["shift_date"] == "2026-04-29"
        assert data["status"] == "completed"

    def test_missing_report_returns_404(self, client, mock_blackboard):
        mock_blackboard.get_shift_report = AsyncMock(return_value=None)
        resp = client.get("/shifts/2026-04-29/morning")
        assert resp.status_code == 404

    def test_invalid_window_returns_400(self, client, mock_blackboard):
        resp = client.get("/shifts/2026-04-29/afternoon")
        assert resp.status_code == 400
        assert "morning" in resp.json()["detail"] or "evening" in resp.json()["detail"]
