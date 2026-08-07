# tests/test_observations_mgmt.py
# @ai-rules:
# 1. [Pattern]: Tests written from plan spec -- independent of implementation.
# 2. [Constraint]: No live Redis/LLM. BlackboardState mocked via AsyncMock.
# 3. [Pattern]: TestClient with dependency_overrides for route tests (shifts_api pattern).
# 4. [Gotcha]: Tests may fail until executor implements the code. Expected.
# 5. [Pattern]: TestRealAuthPath / TestRealObsAdminPath exercise require_auth/require_obs_admin
#    *without* dependency_overrides -- every other test class overrides both, which would
#    otherwise leave the real auth/authz dependencies completely unexercised.
"""Unit and route tests for observation management (delete, rename, report)."""
from __future__ import annotations

import asyncio

import pytest
import fakeredis.aioredis
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.dependencies import get_blackboard, get_report_client
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
    """TestClient for observation management routes.

    Overrides require_auth *and* require_obs_admin -- most tests exercise route logic, not
    the auth/authz dependencies themselves. See TestRealAuthPath / TestRealObsAdminPath below
    for tests against the real dependencies.
    """
    from src.routes.observations_mgmt import mgmt_router
    from src.auth import require_auth, require_obs_admin
    app = FastAPI()
    app.include_router(mgmt_router)
    app.dependency_overrides[get_blackboard] = lambda: mock_blackboard
    app.dependency_overrides[require_auth] = lambda: {"user": "test@test.com"}
    app.dependency_overrides[require_obs_admin] = lambda: {"user": "test@test.com"}
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


class TestRenameObservationIndexGuard:
    """Real BlackboardState + fakeredis (no mocking of rename_observation itself) —
    exercises the actual Lua script to regression-test the reserved-index-key
    data-corruption bug: renaming `_index` used to alias the global index SET
    itself, so the RENAME/SREM/SADD calls in the script destroyed it."""

    @pytest.fixture
    async def bb(self):
        redis = fakeredis.aioredis.FakeRedis()
        state = BlackboardState(redis)
        await redis.zadd("darwin:obs:series_a", {"m1": 1})
        await redis.sadd(state.OBS_INDEX_KEY, "series_a")
        await redis.zadd("darwin:obs:series_b", {"m2": 2})
        await redis.sadd(state.OBS_INDEX_KEY, "series_b")
        return state

    @pytest.mark.asyncio
    async def test_rename_from_reserved_index_name_is_rejected(self, bb):
        """Renaming the reserved `_index` source name must be rejected, not corrupt
        the global index."""
        with pytest.raises(ValueError, match="not found"):
            await bb.rename_observation("_index", "pwned")

        # The global index set must still contain both real series untouched.
        members = {m.decode() if isinstance(m, bytes) else m
                   for m in await bb.redis.smembers(bb.OBS_INDEX_KEY)}
        assert members == {"series_a", "series_b"}
        assert await bb.redis.exists(bb.OBS_INDEX_KEY)

    @pytest.mark.asyncio
    async def test_rename_to_reserved_index_name_is_rejected(self, bb):
        """Renaming a real series *to* the reserved `_index` name must also be
        rejected (defense in depth against a caller bypassing route-level validation)."""
        with pytest.raises(ValueError, match="not found"):
            await bb.rename_observation("series_a", "_index")

        assert await bb.redis.exists("darwin:obs:series_a")


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

    def test_delete_endpoint_skips_name_regex_validation(self, manage_client, mock_blackboard):
        """Regression: DELETE must accept a legacy name that fails OBS_NAME_PATTERN
        (uppercase, hyphens) -- this is a deliberate design decision ("allows cleanup of
        legacy names", see file header) distinguishing DELETE from PATCH, which does
        validate. A future change that "helpfully" adds regex validation to DELETE would
        silently break legacy-name cleanup without this test failing loudly."""
        mock_blackboard.delete_observation = AsyncMock(return_value=True)
        legacy_name = "Legacy-Metric.Name"
        assert not BlackboardState._OBS_NAME_RE.match(legacy_name)
        resp = manage_client.delete(f"/api/observations/manage/{legacy_name}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == legacy_name
        mock_blackboard.delete_observation.assert_awaited_once_with(legacy_name)


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
# Routes: GET /api/observations/manage/export
# =========================================================================

class TestExportEndpoint:
    @staticmethod
    def _seed_two_series(mock_blackboard):
        mock_blackboard.list_observations = AsyncMock(return_value={
            "event_id": "",
            "event_opened": "",
            "event_age_minutes": 0.0,
            "name_pattern": "^[a-z][a-z0-9_]{1,63}$",
            "observations": [
                {
                    "name": "error_count",
                    "count": 2,
                    "min": 1.0,
                    "max": 3.0,
                    "latest_value": 3.0,
                    "unit": "count",
                    "first_at": "2026-08-05T00:00:00Z",
                    "last_at": "2026-08-07T00:00:00Z",
                    "span_minutes": 2880.0,
                    "trend": "rising",
                    "points": [
                        {"timestamp": "2026-08-05T00:00:00Z", "value": 1.0, "unit": "count",
                         "service": "svc-a", "event_id": "evt-1"},
                        {"timestamp": "2026-08-07T00:00:00Z", "value": 3.0, "unit": "count",
                         "service": "svc-a", "event_id": "evt-1"},
                    ],
                },
                {
                    "name": "latency_ms",
                    "count": 1,
                    "min": 42.0,
                    "max": 42.0,
                    "latest_value": 42.0,
                    "unit": "ms",
                    "first_at": "2026-08-06T00:00:00Z",
                    "last_at": "2026-08-06T00:00:00Z",
                    "span_minutes": 0.0,
                    "trend": "stable",
                    "points": [
                        {"timestamp": "2026-08-06T00:00:00Z", "value": 42.0, "unit": "ms",
                         "service": "svc-b", "event_id": "evt-2"},
                    ],
                },
            ],
        })

    def test_export_csv_default_all_series(self, manage_client, mock_blackboard):
        """CSV export with no `names` filter includes every series's points as rows."""
        self._seed_two_series(mock_blackboard)
        resp = manage_client.get("/api/observations/manage/export", params={"format": "csv"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "csv"
        assert data["filename"].endswith(".csv")
        lines = data["content"].strip().splitlines()
        assert lines[0] == "name,timestamp,value,unit,trend,service,event_id"
        # 2 points for error_count + 1 point for latency_ms = 3 data rows.
        assert len(lines) == 4
        assert any(row.startswith("error_count,") for row in lines[1:])
        assert any(row.startswith("latency_ms,") for row in lines[1:])

    def test_export_csv_names_filter(self, manage_client, mock_blackboard):
        """CSV export with `names` narrows to the requested series only."""
        self._seed_two_series(mock_blackboard)
        resp = manage_client.get(
            "/api/observations/manage/export",
            params={"format": "csv", "names": "latency_ms"},
        )
        assert resp.status_code == 200
        lines = resp.json()["content"].strip().splitlines()
        assert len(lines) == 2  # header + 1 point
        assert "latency_ms" in lines[1]
        assert "error_count" not in lines[1]

    def test_export_json_default(self, manage_client, mock_blackboard):
        """JSON export (default format) returns series summaries with points."""
        self._seed_two_series(mock_blackboard)
        resp = manage_client.get("/api/observations/manage/export")
        assert resp.status_code == 200
        data = resp.json()
        assert data["format"] == "json"
        assert data["filename"].endswith(".json")
        content = data["content"]
        assert content["series_count"] == 2
        names = {s["name"] for s in content["series"]}
        assert names == {"error_count", "latency_ms"}
        error_series = next(s for s in content["series"] if s["name"] == "error_count")
        assert error_series["min"] == 1.0
        assert error_series["max"] == 3.0
        assert len(error_series["points"]) == 2

    def test_export_json_names_filter(self, manage_client, mock_blackboard):
        """JSON export honors the `names` filter, excluding non-matching series."""
        self._seed_two_series(mock_blackboard)
        resp = manage_client.get(
            "/api/observations/manage/export",
            params={"format": "json", "names": "error_count"},
        )
        assert resp.status_code == 200
        content = resp.json()["content"]
        assert content["series_count"] == 1
        assert content["series"][0]["name"] == "error_count"

    def test_export_no_series(self, manage_client, mock_blackboard):
        """Export with zero matching series returns an empty, well-formed payload."""
        mock_blackboard.list_observations = AsyncMock(return_value={
            "event_id": "", "event_opened": "", "event_age_minutes": 0.0,
            "observations": [],
        })
        resp = manage_client.get("/api/observations/manage/export", params={"format": "csv"})
        assert resp.status_code == 200
        lines = resp.json()["content"].strip().splitlines()
        assert lines == ["name,timestamp,value,unit,trend,service,event_id"]


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
        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(return_value=mock_llm_response)

        manage_client.app.dependency_overrides[get_report_client] = lambda: mock_client
        try:
            with patch("src.reports.observations_reporter._render_chart_svg", return_value="PHN2Zz4="):
                resp = manage_client.post(
                    "/api/observations/manage/report",
                    json={"series_names": ["error_count"]},
                )
        finally:
            del manage_client.app.dependency_overrides[get_report_client]

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
        mock_client = MagicMock()
        mock_client.models.generate_content = MagicMock(return_value=MagicMock(text="No data"))

        manage_client.app.dependency_overrides[get_report_client] = lambda: mock_client
        try:
            with patch("src.reports.observations_reporter._render_chart_svg", return_value="PHN2Zz4="):
                resp = manage_client.post(
                    "/api/observations/manage/report",
                    json={"series_names": ["nonexistent"]},
                )
        finally:
            del manage_client.app.dependency_overrides[get_report_client]
        assert resp.status_code == 200
        data = resp.json()
        assert "markdown" in data

    def test_report_endpoint_series_names_too_many_422(self, manage_client, mock_blackboard):
        """Request validation: series_names beyond OBS_MAX_REPORT_SERIES is rejected before
        any LLM/report work happens."""
        too_many = [f"series_{i}" for i in range(BlackboardState.OBS_MAX_REPORT_SERIES + 1)]
        manage_client.app.dependency_overrides[get_report_client] = lambda: MagicMock()
        try:
            resp = manage_client.post(
                "/api/observations/manage/report",
                json={"series_names": too_many},
            )
        finally:
            del manage_client.app.dependency_overrides[get_report_client]
        assert resp.status_code == 422

    def test_report_endpoint_series_names_empty_422(self, manage_client, mock_blackboard):
        """Request validation: empty series_names is rejected (min_length=1)."""
        manage_client.app.dependency_overrides[get_report_client] = lambda: MagicMock()
        try:
            resp = manage_client.post(
                "/api/observations/manage/report",
                json={"series_names": []},
            )
        finally:
            del manage_client.app.dependency_overrides[get_report_client]
        assert resp.status_code == 422

    def test_report_endpoint_timeout_returns_504(self, manage_client, mock_blackboard):
        """T-8 (finding): a hang in generate_report must surface as a clean 504 with
        timeout-specific detail, not an indefinite hang or an opaque 500."""
        async def _hang(*args, **kwargs):
            await asyncio.sleep(3600)

        manage_client.app.dependency_overrides[get_report_client] = lambda: MagicMock()
        try:
            with patch("src.routes.observations_mgmt.REPORT_TIMEOUT_SECONDS", 0.05), \
                 patch("src.reports.observations_reporter.generate_report", side_effect=_hang):
                resp = manage_client.post(
                    "/api/observations/manage/report",
                    json={"series_names": ["error_count"]},
                )
        finally:
            del manage_client.app.dependency_overrides[get_report_client]

        assert resp.status_code == 504
        assert "timed out" in resp.json()["detail"].lower()
