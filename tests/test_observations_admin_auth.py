# tests/test_observations_admin_auth.py
# @ai-rules:
# 1. [Pattern]: Exercises the REAL require_auth / require_obs_admin dependencies directly
#    (no dependency_overrides) -- test_observations_mgmt.py overrides both in every test,
#    which would let a dropped Depends(...) on a destructive endpoint go undetected.
# 2. [Constraint]: Patch module constants directly (DEX_ENABLED, OBS_ADMIN_GROUPS) -- they
#    are computed at import time, same convention as test_trusted_proxy_auth.py.
"""Coverage for the real auth/authz path on observation management endpoints."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from src import auth
from src.dependencies import get_blackboard, get_report_client
from src.state.blackboard import BlackboardState


def _mock_request(headers: dict | None = None):
    req = MagicMock()
    req.headers = headers or {}
    return req


# =========================================================================
# require_auth -- direct unit tests against the real dependency
# =========================================================================

class TestRequireAuthRealPath:
    @pytest.mark.asyncio
    async def test_rejects_anonymous_when_dex_disabled(self, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", False)
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_auth(_mock_request())
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_rejects_missing_bearer_header_when_dex_enabled(self, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", True)
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_auth(_mock_request())
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_accepts_valid_jwt(self, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", True)
        monkeypatch.setattr(
            auth, "_validate_jwt",
            lambda token: {"sub": "u1", "email": "u1@test.com", "groups": ["some-group"]},
        )
        user = await auth.require_auth(_mock_request({"authorization": "Bearer tok"}))
        assert user.email == "u1@test.com"


# =========================================================================
# require_obs_admin -- direct unit tests against the real dependency
# =========================================================================

class TestRequireObsAdminRealPath:
    @pytest.mark.asyncio
    async def test_rejects_anonymous_before_group_check(self, monkeypatch):
        """No identity at all -> 401 from require_auth, never reaches the group check."""
        monkeypatch.setattr(auth, "DEX_ENABLED", False)
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_obs_admin(_mock_request())
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_denies_when_admin_groups_unconfigured(self, monkeypatch):
        """Fail-closed default: authenticated but OBS_ADMIN_GROUPS is empty -> 403, not a
        silent bypass back to identity-only auth."""
        monkeypatch.setattr(auth, "DEX_ENABLED", True)
        monkeypatch.setattr(auth, "OBS_ADMIN_GROUPS", frozenset())
        monkeypatch.setattr(
            auth, "_validate_jwt",
            lambda token: {"sub": "u1", "email": "u1@test.com", "groups": ["some-group"]},
        )
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_obs_admin(_mock_request({"authorization": "Bearer tok"}))
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_denies_non_member_of_configured_groups(self, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", True)
        monkeypatch.setattr(auth, "OBS_ADMIN_GROUPS", frozenset({"obs-admins"}))
        monkeypatch.setattr(
            auth, "_validate_jwt",
            lambda token: {"sub": "u1", "email": "u1@test.com", "groups": ["unrelated-group"]},
        )
        with pytest.raises(HTTPException) as exc_info:
            await auth.require_obs_admin(_mock_request({"authorization": "Bearer tok"}))
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_allows_member_of_configured_groups(self, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", True)
        monkeypatch.setattr(auth, "OBS_ADMIN_GROUPS", frozenset({"obs-admins", "sre"}))
        monkeypatch.setattr(
            auth, "_validate_jwt",
            lambda token: {"sub": "u1", "email": "u1@test.com", "groups": ["sre", "other"]},
        )
        user = await auth.require_obs_admin(_mock_request({"authorization": "Bearer tok"}))
        assert user.email == "u1@test.com"


# =========================================================================
# End-to-end wiring: routes must actually declare Depends(require_auth) /
# Depends(require_obs_admin) -- a dropped Depends(...) is invisible to every test in
# test_observations_mgmt.py because that file overrides both dependencies everywhere.
# =========================================================================

@pytest.fixture
def mock_blackboard():
    bb = AsyncMock(spec=BlackboardState)
    bb.redis = AsyncMock()
    bb.delete_observation = AsyncMock(return_value=True)
    bb.rename_observation = AsyncMock(return_value=True)
    bb.list_observations = AsyncMock(return_value={
        "event_id": "", "event_opened": "", "event_age_minutes": 0.0, "observations": [],
    })
    return bb


@pytest.fixture
def unauthed_client(mock_blackboard):
    """TestClient with NO auth/authz overrides -- only infra deps (blackboard, LLM client)
    are stubbed. Proves the routes reject requests via the real require_auth /
    require_obs_admin dependencies rather than dependency_overrides masking their absence."""
    from src.routes.observations_mgmt import mgmt_router
    app = FastAPI()
    app.include_router(mgmt_router)
    app.dependency_overrides[get_blackboard] = lambda: mock_blackboard
    app.dependency_overrides[get_report_client] = lambda: MagicMock()
    return TestClient(app)


class TestRealAuthWiring:
    """DEX_ENABLED=false (test default) -> every request is anonymous -> require_auth 401s
    before request bodies/business logic ever run. If Depends(require_auth) or
    Depends(require_obs_admin) were ever accidentally dropped from a route, these would
    start returning 200 and fail loudly."""

    def test_delete_without_auth_is_rejected(self, unauthed_client, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", False)
        resp = unauthed_client.delete("/api/observations/manage/pipeline_duration_m")
        assert resp.status_code == 401

    def test_rename_without_auth_is_rejected(self, unauthed_client, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", False)
        resp = unauthed_client.patch(
            "/api/observations/manage/old_name", json={"new_name": "new_name"},
        )
        assert resp.status_code == 401

    def test_bulk_delete_without_auth_is_rejected(self, unauthed_client, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", False)
        resp = unauthed_client.post(
            "/api/observations/manage/bulk-delete", json={"names": ["a"]},
        )
        assert resp.status_code == 401

    def test_export_without_auth_is_rejected(self, unauthed_client, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", False)
        resp = unauthed_client.get("/api/observations/manage/export")
        assert resp.status_code == 401

    def test_report_without_auth_is_rejected(self, unauthed_client, monkeypatch):
        monkeypatch.setattr(auth, "DEX_ENABLED", False)
        resp = unauthed_client.post(
            "/api/observations/manage/report", json={"series_names": ["error_count"]},
        )
        assert resp.status_code == 401

    def test_delete_authenticated_but_not_admin_group_is_rejected(
        self, unauthed_client, mock_blackboard, monkeypatch,
    ):
        """Authenticated (valid JWT) but not a member of any configured OBS_ADMIN_GROUPS ->
        403, proving require_obs_admin (not just require_auth) actually gates DELETE."""
        monkeypatch.setattr(auth, "DEX_ENABLED", True)
        monkeypatch.setattr(auth, "OBS_ADMIN_GROUPS", frozenset({"obs-admins"}))
        monkeypatch.setattr(
            auth, "_validate_jwt",
            lambda token: {"sub": "u1", "email": "u1@test.com", "groups": ["not-admin"]},
        )
        resp = unauthed_client.delete(
            "/api/observations/manage/pipeline_duration_m",
            headers={"authorization": "Bearer tok"},
        )
        assert resp.status_code == 403

    def test_delete_authenticated_admin_group_member_succeeds(
        self, unauthed_client, mock_blackboard, monkeypatch,
    ):
        monkeypatch.setattr(auth, "DEX_ENABLED", True)
        monkeypatch.setattr(auth, "OBS_ADMIN_GROUPS", frozenset({"obs-admins"}))
        monkeypatch.setattr(
            auth, "_validate_jwt",
            lambda token: {"sub": "u1", "email": "u1@test.com", "groups": ["obs-admins"]},
        )
        resp = unauthed_client.delete(
            "/api/observations/manage/pipeline_duration_m",
            headers={"authorization": "Bearer tok"},
        )
        assert resp.status_code == 200

    def test_export_authenticated_without_admin_group_succeeds(
        self, unauthed_client, mock_blackboard, monkeypatch,
    ):
        """Export/report are read/analysis endpoints gated only by require_auth (identity),
        not require_obs_admin -- membership in OBS_ADMIN_GROUPS must not be required."""
        monkeypatch.setattr(auth, "DEX_ENABLED", True)
        monkeypatch.setattr(auth, "OBS_ADMIN_GROUPS", frozenset({"obs-admins"}))
        monkeypatch.setattr(
            auth, "_validate_jwt",
            lambda token: {"sub": "u1", "email": "u1@test.com", "groups": ["not-admin"]},
        )
        resp = unauthed_client.get(
            "/api/observations/manage/export",
            headers={"authorization": "Bearer tok"},
        )
        assert resp.status_code == 200
