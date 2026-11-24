# BlackBoard/tests/test_kargo_route.py
# @ai-rules:
# 1. [Constraint]: Pure unit tests for src/routes/kargo.py (no K8s, no Redis).
# 2. [Pattern]: Exercises KargoStageSnapshot model defaults and GET /api/kargo/stages via TestClient.
"""Unit tests for KargoStageSnapshot and GET /api/kargo/stages (T-14)."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.routes.kargo import KargoStageSnapshot, router


def _build_client() -> TestClient:
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_kargo_stage_snapshot_defaults_for_promotion_and_verification():
    """KargoStageSnapshot preserves promotion defaults and accepts verification metadata with empty promotion."""
    promo_snap = KargoStageSnapshot(
        project="v4-22",
        stage="build-stage",
        promotion="build-stage.01abc",
        phase="Errored",
        failed_step="wait-for-merge",
        service="build-stage@v4-22",
    )
    assert promo_snap.failure_type == "promotion"
    assert promo_snap.verification_id == ""
    assert promo_snap.analysis_run == ""

    verif_snap = KargoStageSnapshot(
        project="kargo-demo-alraj",
        stage="test1",
        phase="Error",
        message="error building AnalysisRun",
        service="test1@kargo-demo-alraj",
        failure_type="verification",
        verification_id="b7c1-uuid",
        analysis_run="",
    )
    assert verif_snap.promotion == ""
    assert verif_snap.failure_type == "verification"
    assert verif_snap.verification_id == "b7c1-uuid"
    assert verif_snap.analysis_run == ""


def test_get_api_kargo_stages_serializes_promotion_and_verification_failures():
    """GET /api/kargo/stages serializes both promotion and verification failures including empty promotion."""
    observer = MagicMock()
    observer.get_failed_stages.return_value = [
        {
            "project": "v4-22",
            "stage": "promote-stage",
            "promotion": "promote-stage.01abc",
            "freight": "abc123",
            "phase": "Errored",
            "message": "step timed out",
            "failed_step": "wait-for-merge",
            "mr_url": "https://gitlab.example.com/org/repo/-/merge_requests/1",
            "service": "promote-stage@v4-22",
            "started_at": "2026-11-23T09:00:00Z",
            "finished_at": "2026-11-23T09:05:00Z",
            "failure_type": "promotion",
            "verification_id": "",
            "analysis_run": "",
        },
        {
            "project": "v4-22",
            "stage": "verify-release-chart",
            "promotion": "",
            "freight": "dae4bb27ec6b",
            "phase": "Failed",
            "message": 'Metric "check-chart-exists" assessed Failed',
            "failed_step": "",
            "mr_url": "",
            "service": "verify-release-chart@v4-22",
            "started_at": "2026-11-23T09:58:15Z",
            "finished_at": "2026-11-23T11:30:21Z",
            "failure_type": "verification",
            "verification_id": "1605daa6-92cb-4050-addd-89465a90f331",
            "analysis_run": "verify-release-chart.01m83xf2.3aa0ebb",
        },
    ]
    brain = MagicMock()
    brain.agents = {"_kargo_observer": observer}

    client = _build_client()
    with patch("src.routes.kargo.get_brain", AsyncMock(return_value=brain)):
        resp = client.get("/api/kargo/stages")

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    assert data[0]["failure_type"] == "promotion"
    assert data[0]["failed_step"] == "wait-for-merge"
    assert data[0]["verification_id"] == ""

    assert data[1]["promotion"] == ""
    assert data[1]["failure_type"] == "verification"
    assert data[1]["phase"] == "Failed"
    assert data[1]["verification_id"] == "1605daa6-92cb-4050-addd-89465a90f331"
    assert data[1]["analysis_run"] == "verify-release-chart.01m83xf2.3aa0ebb"


def test_get_api_kargo_stages_returns_empty_when_observer_or_brain_unavailable():
    """Returns [] gracefully when _kargo_observer is disabled or Brain is uninitialized."""
    client = _build_client()

    brain_no_obs = MagicMock()
    brain_no_obs.agents = {}
    with patch("src.routes.kargo.get_brain", AsyncMock(return_value=brain_no_obs)):
        resp = client.get("/api/kargo/stages")
    assert resp.status_code == 200
    assert resp.json() == []

    with patch("src.routes.kargo.get_brain", AsyncMock(side_effect=RuntimeError("not ready"))):
        resp = client.get("/api/kargo/stages")
    assert resp.status_code == 200
    assert resp.json() == []
