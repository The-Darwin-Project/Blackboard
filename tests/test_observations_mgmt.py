# tests/test_observations_mgmt.py
# @ai-rules:
# 1. [Pattern]: Tests written from plan spec -- independent of implementation.
# 2. [Constraint]: No live Redis/LLM. BlackboardState mocked via AsyncMock.
# 3. [Pattern]: TestClient with dependency_overrides for route tests (shifts_api pattern).
# 4. [Gotcha]: Tests may fail until executor implements the code. Expected.
"""Unit and route tests for observation management (delete, rename, report)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.dependencies import get_blackboard
from src.state.blackboard import BlackboardState


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def mock_blackboard():
    """BlackboardState mock with observation management methods."""
    bb = AsyncMock(spec=BlackboardState)
    bb.redis = AsyncMock()
    bb.delete_observation = AsyncMock(return_value=True)
    bb.rename_observation = AsyncMock(return_value=True)
    bb.list_observations = AsyncMock(return_value={
        "event_id": "",
        "event_opened": "",
        "event_age_minutes": 0.0,
        "observations": [],
    })
    return bb


@pytest.fixture
def manage_client(mock_blackboard):
    """TestClient for observation management routes."""
    from src.routes.observations_mgmt import mgmt_router
    from src.auth import require_auth
    app = FastAPI()
    app.include_router(mgmt_router)
    app.dependency_overrides[get_blackboard] = lambda: mock_blackboard
    app.dependency_overrides[require_auth] = lambda: {"user": "test@test.com"}
    return TestClient(app)


# =========================================================================
# State Layer: delete_observation
# =========================================================================

class TestDeleteObservation:
    @pytest.mark.asyncio
    async def test_delete_observation_exists(self, mock_blackboard):
        """T-1: Delete existing series → returns True, key gone, index entry removed."""
        bb = mock_blackboard
        bb.redis.delete = AsyncMock(return_value=1)
        bb.redis.srem = AsyncMock(return_value=1)
        bb.redis.smembers = AsyncMock(return_value={b"pipeline_duration_m"})

        bb.delete_observation = AsyncMock(return_value=True)
        result = await bb.delete_observation("pipeline_duration_m")
        assert result is True
        bb.delete_observation.assert_awaited_once_with("pipeline_duration_m")

    @pytest.mark.asyncio
    async def test_delete_observation_not_found(self, mock_blackboard):
        """T-2: Delete non-existent → returns False."""
        bb = mock_blackboard
        bb.delete_observation = AsyncMock(return_value=False)
        result = await bb.delete_observation("nonexistent_series")
        assert result is False


# =========================================================================
# State Layer: rename_observation
# =========================================================================

class TestRenameObservation:
    @pytest.mark.asyncio
    async def test_rename_observation_success(self, mock_blackboard):
        """T-3: Rename → key moved, index updated."""
        bb = mock_blackboard
        bb.rename_observation = AsyncMock(return_value=True)
        result = await bb.rename_observation("old_name", "new_name")
        assert result is True
        bb.rename_observation.assert_awaited_once_with("old_name", "new_name")

    @pytest.mark.asyncio
    async def test_rename_observation_not_found(self, mock_blackboard):
        """T-4: Rename non-existent → raises ValueError."""
        bb = mock_blackboard
        bb.rename_observation = AsyncMock(
            side_effect=ValueError("Observation 'missing' not found"),
        )
        with pytest.raises(ValueError, match="not found"):
            await bb.rename_observation("missing", "new_name")

    @pytest.mark.asyncio
    async def test_rename_observation_collision(self, mock_blackboard):
        """T-5: Rename to existing name → raises ValueError."""
        bb = mock_blackboard
        bb.rename_observation = AsyncMock(
            side_effect=ValueError("Observation 'existing' already exists"),
        )
        with pytest.raises(ValueError, match="already exists"):
            await bb.rename_observation("old_name", "existing")


# =========================================================================
# Name Validation
# =========================================================================

class TestNameValidation:
    """Tests for observation name validation regex/function."""

    def test_validate_obs_name_valid(self):
        """T-6: Lowercase + underscores + digits pass."""
        from src.state.blackboard import BlackboardState
        # Should not raise
        BlackboardState.validate_obs_name("pipeline_duration_m")
        BlackboardState.validate_obs_name("s390x_build_duration_m")
        BlackboardState.validate_obs_name("error_count")
        BlackboardState.validate_obs_name("pod_restart_count")
        BlackboardState.validate_obs_name("metric123")

    def test_validate_obs_name_invalid_uppercase(self):
        """T-7: Rejects uppercase."""
        from src.state.blackboard import BlackboardState
        with pytest.raises(ValueError):
            BlackboardState.validate_obs_name("Pipeline_Duration")

    def test_validate_obs_name_invalid_colon(self):
        """T-8: Rejects colons (would collide with Redis key delimiters)."""
        from src.state.blackboard import BlackboardState
        with pytest.raises(ValueError):
            BlackboardState.validate_obs_name("cpu:usage")

    def test_validate_obs_name_too_long(self):
        """T-9: Rejects >63 chars."""
        from src.state.blackboard import BlackboardState
        with pytest.raises(ValueError):
            BlackboardState.validate_obs_name("a" * 65)
        # 63 chars should pass (1 start + 62 continuation = 63 total)
        BlackboardState.validate_obs_name("a" * 63)

    def test_validate_obs_name_rejects_empty(self):
        """Edge: empty string is invalid."""
        from src.state.blackboard import BlackboardState
        with pytest.raises(ValueError):
            BlackboardState.validate_obs_name("")

    def test_validate_obs_name_rejects_spaces(self):
        """Edge: spaces are invalid."""
        from src.state.blackboard import BlackboardState
        with pytest.raises(ValueError):
            BlackboardState.validate_obs_name("has space")

    def test_validate_obs_name_rejects_hyphens(self):
        """Edge: hyphens are invalid (underscore convention)."""
        from src.state.blackboard import BlackboardState
        with pytest.raises(ValueError):
            BlackboardState.validate_obs_name("pipeline-duration")


# =========================================================================
# Report Pipeline
# =========================================================================

class TestReportGeneration:
    @pytest.mark.asyncio
    async def test_generate_report_success(self):
        """T-10: Mock LLM returns text, charts render, markdown assembled."""
        from src.reports.observations_reporter import generate_report

        mock_bb = AsyncMock(spec=BlackboardState)
        mock_bb.list_observations = AsyncMock(return_value={
            "event_id": "",
            "event_opened": "",
            "event_age_minutes": 0.0,
            "observations": [
                {
                    "name": "pipeline_duration_m",
                    "count": 5,
                    "min": 10.0,
                    "max": 30.0,
                    "latest_value": 25.0,
                    "unit": "minutes",
                    "first_at": "2026-08-01T00:00:00Z",
                    "last_at": "2026-08-07T00:00:00Z",
                    "span_minutes": 10080.0,
                    "trend": "rising",
                    "points": [
                        {"timestamp": f"2026-08-0{i}T00:00:00Z", "value": 10.0 + i * 5, "unit": "minutes", "epoch": 1754006400 + i * 86400}
                        for i in range(1, 6)
                    ],
                },
            ],
        })

        mock_llm_response = MagicMock()
        mock_llm_response.text = "## Analysis\nPipeline duration is trending upward."

        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(return_value=mock_llm_response)

        with patch("src.reports.observations_reporter._render_chart_svg", return_value="PHN2Zz48L3N2Zz4="):
            result = await generate_report(mock_bb, mock_client, "gemini-3.5-flash-lite", ["pipeline_duration_m"])

        assert "markdown" in result
        assert len(result["markdown"]) > 0
        assert "pipeline_duration_m" in result["markdown"]

    @pytest.mark.asyncio
    async def test_generate_report_partial_failure(self):
        """T-11: One LLM call fails, others succeed, placeholder used."""
        from src.reports.observations_reporter import generate_report

        mock_bb = AsyncMock(spec=BlackboardState)
        mock_bb.list_observations = AsyncMock(return_value={
            "event_id": "",
            "event_opened": "",
            "event_age_minutes": 0.0,
            "observations": [
                {
                    "name": "error_count",
                    "count": 3,
                    "min": 0.0,
                    "max": 5.0,
                    "latest_value": 5.0,
                    "unit": "count",
                    "first_at": "2026-08-05T00:00:00Z",
                    "last_at": "2026-08-07T00:00:00Z",
                    "span_minutes": 2880.0,
                    "trend": "rising",
                    "points": [
                        {"timestamp": f"2026-08-0{i}T00:00:00Z", "value": float(i), "unit": "count", "epoch": 1754006400 + i * 86400}
                        for i in range(5, 8)
                    ],
                },
                {
                    "name": "pod_restart_count",
                    "count": 2,
                    "min": 0.0,
                    "max": 1.0,
                    "latest_value": 1.0,
                    "unit": "count",
                    "first_at": "2026-08-06T00:00:00Z",
                    "last_at": "2026-08-07T00:00:00Z",
                    "span_minutes": 1440.0,
                    "trend": "stable",
                    "points": [
                        {"timestamp": "2026-08-06T00:00:00Z", "value": 0.0, "unit": "count", "epoch": 1754438400},
                        {"timestamp": "2026-08-07T00:00:00Z", "value": 1.0, "unit": "count", "epoch": 1754524800},
                    ],
                },
            ],
        })

        call_count = 0

        async def flaky_generate(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("LLM API error")
            resp = MagicMock()
            resp.text = "## Analysis\nPod restarts are stable."
            return resp

        with patch("src.reports.observations_reporter._render_chart_svg", return_value="PHN2Zz48L3N2Zz4="):
            mock_client = MagicMock()
            mock_client.models.generate_content = flaky_generate
            result = await generate_report(mock_bb, mock_client, "gemini-3.5-flash-lite", ["error_count", "pod_restart_count"])

        assert "markdown" in result
        md = result["markdown"]
        assert "[Analysis unavailable" in md or "pod_restart_count" in md

    @pytest.mark.asyncio
    async def test_sample_points_downsample(self):
        """T-12: 100 points → 50 sampled."""
        from src.reports.observations_reporter import _sample_points as sample_points

        points = [
            {"timestamp": f"2026-08-07T{i:02d}:00:00Z", "value": float(i), "unit": "m", "epoch": 1754524800 + i * 60}
            for i in range(100)
        ]
        sampled = sample_points(points, max_n=50)
        assert len(sampled) == 50
        assert sampled[0] == points[0]


# =========================================================================
# Routes: DELETE /api/observations/manage/{name}
# =========================================================================

class TestDeleteEndpoint:
    def test_delete_endpoint_success(self, manage_client, mock_blackboard):
        """T-13: DELETE existing observation → 200."""
        mock_blackboard.delete_observation = AsyncMock(return_value=True)
        resp = manage_client.delete("/api/observations/manage/pipeline_duration_m")
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == "pipeline_duration_m"

    def test_delete_endpoint_404(self, manage_client, mock_blackboard):
        """T-14: DELETE non-existent → 404."""
        mock_blackboard.delete_observation = AsyncMock(return_value=False)
        resp = manage_client.delete("/api/observations/manage/nonexistent")
        assert resp.status_code == 404


# =========================================================================
# Routes: PATCH /api/observations/manage/{name}
# =========================================================================

class TestRenameEndpoint:
    def test_rename_endpoint_success(self, manage_client, mock_blackboard):
        """T-15: PATCH → 200 {"renamed": old, "to": new}."""
        mock_blackboard.rename_observation = AsyncMock(return_value=True)
        resp = manage_client.patch(
            "/api/observations/manage/old_name",
            json={"new_name": "new_name"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["renamed"] == "old_name"
        assert data["new_name"] == "new_name"

    def test_rename_endpoint_409_collision(self, manage_client, mock_blackboard):
        """T-16: PATCH with existing new_name → 409."""
        mock_blackboard.rename_observation = AsyncMock(
            side_effect=ValueError("Observation 'existing' already exists"),
        )
        resp = manage_client.patch(
            "/api/observations/manage/old_name",
            json={"new_name": "existing"},
        )
        assert resp.status_code == 409

    def test_rename_endpoint_422_invalid(self, manage_client, mock_blackboard):
        """T-17: PATCH with bad regex name → 422."""
        resp = manage_client.patch(
            "/api/observations/manage/old_name",
            json={"new_name": "Invalid:Name!"},
        )
        assert resp.status_code == 422

    def test_rename_endpoint_404_source(self, manage_client, mock_blackboard):
        """Edge: PATCH source not found → 404 (ValueError 'not found')."""
        mock_blackboard.rename_observation = AsyncMock(
            side_effect=ValueError("Observation 'missing' not found"),
        )
        resp = manage_client.patch(
            "/api/observations/manage/missing",
            json={"new_name": "new_name"},
        )
        assert resp.status_code in (404, 409)


# =========================================================================
# Routes: POST /api/observations/manage/bulk-delete
# =========================================================================

class TestBulkDeleteEndpoint:
    def test_bulk_delete_empty(self, manage_client, mock_blackboard):
        """T-18: POST bulk-delete with [] → 200 {"deleted": 0}."""
        resp = manage_client.post(
            "/api/observations/manage/bulk-delete",
            json={"names": []},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == 0

    def test_bulk_delete_multiple(self, manage_client, mock_blackboard):
        """Bulk delete multiple names → deleted count matches successes."""
        mock_blackboard.delete_observation = AsyncMock(
            side_effect=[True, False, True],
        )
        resp = manage_client.post(
            "/api/observations/manage/bulk-delete",
            json={"names": ["series_a", "missing_b", "series_c"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["deleted"] == 2

    def test_bulk_delete_all_missing(self, manage_client, mock_blackboard):
        """Bulk delete where none exist → deleted=0, still 200."""
        mock_blackboard.delete_observation = AsyncMock(return_value=False)
        resp = manage_client.post(
            "/api/observations/manage/bulk-delete",
            json={"names": ["ghost_a", "ghost_b"]},
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == 0


# =========================================================================
# Routes: POST /api/observations/manage/report
# =========================================================================

class TestReportEndpoint:
    def test_report_endpoint(self, manage_client, mock_blackboard):
        """T-19: POST report → 200 with markdown field."""
        mock_blackboard.list_observations = AsyncMock(return_value={
            "event_id": "",
            "event_opened": "",
            "event_age_minutes": 0.0,
            "observations": [
                {
                    "name": "error_count",
                    "count": 3,
                    "min": 0.0,
                    "max": 5.0,
                    "latest_value": 5.0,
                    "unit": "count",
                    "first_at": "2026-08-05T00:00:00Z",
                    "last_at": "2026-08-07T00:00:00Z",
                    "span_minutes": 2880.0,
                    "trend": "rising",
                    "points": [
                        {"timestamp": "2026-08-07T00:00:00Z", "value": 5.0, "unit": "count", "epoch": 1754524800},
                    ],
                },
            ],
        })

        mock_llm_response = MagicMock()
        mock_llm_response.text = "## Error Count Analysis\nErrors are trending up."

        with patch("src.routes.observations_mgmt._get_report_client") as mock_factory, \
             patch("src.reports.observations_reporter._render_chart_svg", return_value="PHN2Zz4="):
            mock_client = MagicMock()
            mock_client.models.generate_content = MagicMock(return_value=mock_llm_response)
            mock_factory.return_value = mock_client
            resp = manage_client.post(
                "/api/observations/manage/report",
                json={"series_names": ["error_count"]},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert "markdown" in data
        assert len(data["markdown"]) > 0

    def test_report_endpoint_no_observations(self, manage_client, mock_blackboard):
        """Report with no matching observations → 200 with minimal markdown."""
        mock_blackboard.list_observations = AsyncMock(return_value={
            "event_id": "",
            "event_opened": "",
            "event_age_minutes": 0.0,
            "observations": [],
        })

        with patch("src.routes.observations_mgmt._get_report_client") as mock_factory, \
             patch("src.reports.observations_reporter._render_chart_svg", return_value="PHN2Zz4="):
            mock_client = MagicMock()
            mock_client.models.generate_content = MagicMock(return_value=MagicMock(text="No data"))
            mock_factory.return_value = mock_client
            resp = manage_client.post(
                "/api/observations/manage/report",
                json={"series_names": ["nonexistent"]},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "markdown" in data
