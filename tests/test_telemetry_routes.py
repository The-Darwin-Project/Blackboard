# BlackBoard/tests/test_telemetry_routes.py
# @ai-rules:
# 1. [Pattern]: 4-Layer Farley ATDD tests for T-19 (live /flow multi-pool + Helm) and T-21 (/telemetry/llm 200 + sync JARVIS snapshot).
# 2. [Constraint]: Zero live Redis/GCP/K8s calls; FastAPI TestClient + patched dependencies + local Brain stubs.
"""4-Layer ATDD executable specifications for T-19 and T-21 (/flow, /telemetry/llm, JARVIS snapshot, Helm)."""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml
from httpx import ASGITransport, AsyncClient


REPO_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# Layer 3: Protocol Drivers
# ---------------------------------------------------------------------------

class TelemetryRoutesDriver:
    """Protocol driver for GET /flow, GET /telemetry/llm, and Helm chart values/templates."""

    async def get_flow(self, mock_bb: AsyncMock, mock_brain: Any = None) -> tuple[int, dict[str, Any]]:
        with patch("src.main.lifespan") as mock_lifespan:
            mock_lifespan.return_value.__aenter__ = AsyncMock()
            mock_lifespan.return_value.__aexit__ = AsyncMock()
            from src import dependencies
            from src.main import app

            orig_bb = dependencies._blackboard
            orig_brain = dependencies._brain
            dependencies._blackboard = mock_bb
            dependencies._brain = mock_brain
            try:
                transport = ASGITransport(app=app)
                async with AsyncClient(transport=transport, base_url="http://test") as client:
                    resp = await client.get("/flow")
                    return resp.status_code, resp.json()
            finally:
                dependencies._blackboard = orig_bb
                dependencies._brain = orig_brain

    async def get_telemetry_llm(self) -> tuple[int, dict[str, Any]]:
        with patch("src.main.lifespan") as mock_lifespan:
            mock_lifespan.return_value.__aenter__ = AsyncMock()
            mock_lifespan.return_value.__aexit__ = AsyncMock()
            from src.main import app

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/telemetry/llm")
                return resp.status_code, resp.json()


# ---------------------------------------------------------------------------
# Layer 1: Domain Scenarios (T-19 & T-21)
# ---------------------------------------------------------------------------

class TestFlowAndTelemetryRoutes:
    """T-19 & T-21: Live /flow multi-pool gauges, Helm wiring, /telemetry/llm HTTP 200, and sync JARVIS snapshot."""

    @pytest.mark.asyncio
    async def test_t19_get_flow_reads_live_in_memory_quota_registry_and_user_sessions(self, monkeypatch):
        """
        Scenario T-19a:
        Given enmaas disabled and QuotaPoolRegistry holding live vertex_gemini & vertex_claude usage
        When GET /flow runs with latest_snapshot=None (before 60s Redis flush)
        Then /flow returns active_user_sessions, peak_pool_utilization_pct, and live pool gauges immediately.
        """
        from src.agents.llm.quota_registry import reset_quota_registry, get_quota_registry
        from src.agents.llm.types import PROVIDER_VERTEX_CLAUDE, PROVIDER_VERTEX_GEMINI
        from src.state.wip_meta import ActiveEventMeta

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        monkeypatch.delenv("LLM_TPM_LIMIT", raising=False)
        monkeypatch.delenv("LLM_TPM_LIMIT_CLAUDE", raising=False)
        monkeypatch.delenv("LLM_TPM_LIMIT_ENMAAS", raising=False)
        reset_quota_registry()

        try:
            reg = get_quota_registry()
            reg.get(PROVIDER_VERTEX_GEMINI).record_post_hoc(350_000)   # 10.0%
            reg.get(PROVIDER_VERTEX_CLAUDE).record_post_hoc(1_720_000) # 86.0%

            mock_bb = AsyncMock()
            mock_bb.get_flow_metrics = AsyncMock(
                return_value={"queue_depth": 1, "active_events": 4, "waiting_approval_events": 0}
            )
            mock_bb.get_latest_flow_snapshot = AsyncMock(return_value=None)
            mock_bb.get_active_events_metadata = AsyncMock(return_value={
                "e1": ActiveEventMeta(status="active", source="aligner"),
                "e2": ActiveEventMeta(status="active", source="chat"),
                "e3": ActiveEventMeta(status="active", source="slack"),
                "e4": ActiveEventMeta(status="active", source="jarvis"),
            })

            driver = TelemetryRoutesDriver()
            with patch("src.dependencies.get_registry_and_bridge", return_value=(None, None)):
                code, body = await driver.get_flow(mock_bb, mock_brain=None)

            assert code == 200
            assert body["active_user_sessions"] == 3
            assert body["gemini_tpm_used"] == 350_000
            assert body["gemini_tpm_limit"] == 3_500_000
            assert body["claude_tpm_used"] == 1_720_000
            assert body["claude_tpm_limit"] == 2_000_000
            assert body["enmaas_tpm_limit"] == 0
            assert body["peak_pool_utilization_pct"] == pytest.approx(86.0, rel=1e-2)
        finally:
            reset_quota_registry()

    def test_t19_helm_values_configmap_deployment_wire_all_four_tpm_keys(self):
        """
        Scenario T-19b:
        Given Helm values.yaml, configmap.yaml, and deployment.yaml
        When inspected for LLM TPM quota governance keys
        Then all 4 keys (LLM_TPM_LIMIT=3500000, LLM_TPM_LIMIT_CLAUDE=2000000,
        LLM_TPM_LIMIT_ENMAAS=2000000, LLM_TPM_NORMAL_CEILING_RATIO=0.85) are wired via configMapKeyRef.
        """
        values = yaml.safe_load((REPO_ROOT / "helm" / "values.yaml").read_text())
        assert str(values["gcp"]["tpmLimit"]) == "3500000"
        assert str(values["gcp"]["claudeTpmLimit"]) == "2000000"
        assert str(values["gcp"]["enmaasTpmLimit"]) == "2000000"
        assert str(values["gcp"]["tpmNormalCeilingRatio"]) == "0.85"

        cfg_text = (REPO_ROOT / "helm" / "templates" / "configmap.yaml").read_text()
        dep_text = (REPO_ROOT / "helm" / "templates" / "deployment.yaml").read_text()
        for key in (
            "LLM_TPM_LIMIT",
            "LLM_TPM_LIMIT_CLAUDE",
            "LLM_TPM_LIMIT_ENMAAS",
            "LLM_TPM_NORMAL_CEILING_RATIO",
        ):
            assert f"{key}:" in cfg_text, f"configmap.yaml missing {key}"
            assert f"key: {key}" in dep_text, f"deployment.yaml missing configMapKeyRef key {key}"

    @pytest.mark.asyncio
    async def test_t21_telemetry_llm_returns_200_cold_start_with_flat_and_nested_keys(self, monkeypatch):
        """
        Scenario T-21a:
        Given cold-start QuotaPoolRegistry with zero Gemini calls
        When GET /telemetry/llm is called
        Then HTTP 200 (never 503) returns both flat global keys AND global/pools/callers/teams.
        """
        from src.agents.llm.quota_registry import reset_quota_registry

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        monkeypatch.delenv("LLM_TPM_LIMIT", raising=False)
        monkeypatch.delenv("LLM_TPM_LIMIT_CLAUDE", raising=False)
        reset_quota_registry()

        try:
            driver = TelemetryRoutesDriver()
            code, body = await driver.get_telemetry_llm()
            assert code == 200

            for flat_key in (
                "tokens_used_60s",
                "tpm_limit",
                "sustained_limit",
                "reserve_tokens",
                "tokens_remaining",
                "utilization_pct",
                "peak_pool_utilization_pct",
                "active_reservations",
                "high_priority_waiters",
                "total_requests",
                "total_tokens",
                "throttle_events",
            ):
                assert flat_key in body, f"/telemetry/llm missing flat key {flat_key!r}"

            assert body["tpm_limit"] == 5_500_000
            assert "global" in body
            assert "pools" in body
            assert "callers" in body
            assert "teams" in body
            assert body["pools"]["vertex_gemini"]["tpm_limit"] == 3_500_000
            assert body["pools"]["vertex_claude"]["tpm_limit"] == 2_000_000
        finally:
            reset_quota_registry()

    @pytest.mark.asyncio
    async def test_t21_brain_sync_stability_snapshot_excludes_interactive_and_parallel_tasks(self, monkeypatch):
        """
        Scenario T-21b:
        Given Brain holds active tasks (automated + chat + waiting_for_user)
        When synchronous Brain.get_system_stability_snapshot() runs
        Then it stays strictly synchronous, computes automated-only active_wip, and exposes peak_pool_utilization_pct.
        """
        from src.agents.brain import Brain
        from src.agents.llm.quota_registry import get_quota_registry, reset_quota_registry
        from src.agents.llm.types import PROVIDER_VERTEX_CLAUDE

        assert not inspect.iscoroutinefunction(Brain.get_system_stability_snapshot)

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        reset_quota_registry()
        try:
            get_quota_registry().get(PROVIDER_VERTEX_CLAUDE).record_post_hoc(1_000_000)  # 50%

            with patch.object(Brain, "__init__", lambda self, *a, **kw: None):
                brain = Brain.__new__(Brain)
                t_auto = asyncio.create_task(asyncio.sleep(10))
                t_chat = asyncio.create_task(asyncio.sleep(10))
                t_parked = asyncio.create_task(asyncio.sleep(10))
                try:
                    brain._active_tasks = {
                        "evt-auto": t_auto,
                        "evt-chat": t_chat,
                        "evt-parked": t_parked,
                    }
                    brain._active_event_sources = {
                        "evt-auto": "aligner",
                        "evt-chat": "chat",
                        "evt-parked": "headhunter",
                    }
                    brain._waiting_for_user = {"evt-parked": 1000.0}
                    brain._waiting_for_jarvis = {}
                    brain._stabilization_waits = {}

                    snap = brain.get_system_stability_snapshot()
                    assert snap["active_wip"] == 1
                    assert snap["peak_pool_utilization_pct"] == pytest.approx(50.0, rel=1e-2)
                finally:
                    for t in (t_auto, t_chat, t_parked):
                        t.cancel()
                    await asyncio.gather(t_auto, t_chat, t_parked, return_exceptions=True)
        finally:
            reset_quota_registry()
