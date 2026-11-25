# BlackBoard/tests/test_sidecar_usage.py
# @ai-rules:
# 1. [Pattern]: 4-Layer Farley ATDD tests for T-16 (WS token_usage routing, validation, residual reconciliation)
#    and T-17 (pre-dispatch 85% gate on PRIORITY_NORMAL vs PRIORITY_HIGH & zero mid-flight kills).
# 2. [Constraint]: Zero live WS sockets or Redis; uses TaskBridge + AgentRegistry + QuotaPoolRegistry in-process.
"""4-Layer ATDD executable specifications for T-16 and T-17 (Sidecar WS token telemetry & pre-dispatch gate)."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import WebSocketDisconnect

from src.agents.agent_registry import AgentConnection, AgentRegistry
from src.agents.task_bridge import TaskBridge
from src.models import ConversationTurn, EventDocument, EventInput


# ---------------------------------------------------------------------------
# Layer 3: Protocol Driver
# ---------------------------------------------------------------------------

class SidecarWsDriver:
    """Drives AgentRegistry, TaskBridge, dispatch_to_agent, and consume_wake_task."""

    def __init__(self) -> None:
        self.registry = AgentRegistry()
        self.bridge = TaskBridge()

    async def register_agent(
        self,
        *,
        agent_id: str = "dev-pod-1",
        role: str = "developer",
        cli: str = "claude",
        model: str = "claude-sonnet-5",
        provider: str = "vertex_claude",
        ephemeral: bool = False,
        event_id: str | None = None,
    ) -> AsyncMock:
        ws = AsyncMock()
        await self.registry.register(
            agent_id=agent_id,
            role=role,
            ws=ws,
            capabilities=["run_command"],
            cli=cli,
            model=model,
            ephemeral=ephemeral,
            event_id=event_id,
            provider=provider,
        )
        return ws


# ---------------------------------------------------------------------------
# Layer 1: Domain Scenarios (T-16 & T-17)
# ---------------------------------------------------------------------------

class TestSidecarUsageIngestionT16:
    """T-16: sidecar_usage.py validation, AgentConnection.provider, WS routing, and both dispatch loops."""

    def test_t16_normalize_provider_and_validate_usage_payload_bounds(self, monkeypatch):
        from src.agents.sidecar_usage import (
            SIDECAR_MAX_FRAME_TOKENS,
            normalize_sidecar_provider,
            validate_usage_payload,
        )
        from src.agents.llm.types import PROVIDER_ENMAAS, PROVIDER_VERTEX_CLAUDE, PROVIDER_VERTEX_GEMINI

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        assert normalize_sidecar_provider("agy", "") == PROVIDER_VERTEX_GEMINI
        assert normalize_sidecar_provider("claude", "") == PROVIDER_VERTEX_CLAUDE
        assert normalize_sidecar_provider("claude", "vertex_claude") == PROVIDER_VERTEX_CLAUDE

        monkeypatch.setenv("ENMAAS_ENABLED", "true")
        assert normalize_sidecar_provider("claude", "") == PROVIDER_ENMAAS

        # Reject bool, negative, NaN/inf
        assert validate_usage_payload({"total_tokens": True, "input_tokens": 10}, "claude") is None
        assert validate_usage_payload({"total_tokens": -5, "input_tokens": 10}, "claude") is None
        assert validate_usage_payload({"total_tokens": float("nan")}, "claude") is None
        assert validate_usage_payload({"total_tokens": float("inf")}, "claude") is None
        assert validate_usage_payload("not-a-dict", "claude") is None  # type: ignore[arg-type]

        # Clamp oversized frame + allowlist caller slug
        clamped_slug, clamped_usage = validate_usage_payload(
            {
                "input_tokens": SIDECAR_MAX_FRAME_TOKENS + 999,
                "output_tokens": 500,
                "thinking_tokens": 200,
                "total_tokens": SIDECAR_MAX_FRAME_TOKENS + 999,
            },
            "evil-cli-injection",
        )
        assert clamped_slug == "sidecar:unknown"
        assert clamped_usage.total_tokens <= SIDECAR_MAX_FRAME_TOKENS
        assert clamped_usage.input_tokens <= SIDECAR_MAX_FRAME_TOKENS

        valid_slug, valid_usage = validate_usage_payload(
            {"input_tokens": 100, "output_tokens": 50, "thinking_tokens": 20, "total_tokens": 150},
            "claude",
        )
        assert valid_slug == "sidecar:claude"
        assert valid_usage.thinking_tokens == 20
        assert valid_usage.total_tokens == 150  # no thinking_tokens double-sum

    def test_t16_record_sidecar_usage_updates_meter_and_pool_post_hoc(self, monkeypatch):
        from src.agents.llm import get_token_meter
        from src.agents.llm.quota_registry import get_quota_registry, reset_quota_registry
        from src.agents.llm.types import PROVIDER_VERTEX_CLAUDE
        from src.agents.sidecar_usage import record_sidecar_usage

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        reset_quota_registry()
        try:
            reg = get_quota_registry()
            before_claude = reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"]
            before_meter = get_token_meter().get_caller_totals().get("sidecar:claude", {}).get("total_tokens", 0)

            recorded = record_sidecar_usage(
                cli="claude",
                raw_provider="vertex_claude",
                model="claude-sonnet-5",
                usage_dict={"input_tokens": 400, "output_tokens": 100, "thinking_tokens": 40, "total_tokens": 500},
                event_id="evt-sidecar-1",
            )
            assert recorded == 500
            after_claude = reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"]
            after_meter = get_token_meter().get_caller_totals().get("sidecar:claude", {}).get("total_tokens", 0)
            assert after_claude - before_claude == 500
            assert after_meter - before_meter == 500
        finally:
            reset_quota_registry()

    @pytest.mark.asyncio
    async def test_t16_agent_connection_provider_tail_and_ws_handler_routing(self):
        from src.agents.agent_ws_handler import _ROUTED_TYPES, agent_websocket_handler

        assert "token_usage" in _ROUTED_TYPES

        # AgentConnection keeps provider as trailing default field
        fields = list(AgentConnection.__dataclass_fields__.keys())
        assert fields[-1] == "provider"

        driver = SidecarWsDriver()
        ws = AsyncMock()
        ws.receive_json = AsyncMock(
            side_effect=[
                {
                    "type": "register",
                    "agent_id": "dev-pod-1",
                    "role": "developer",
                    "cli": "claude",
                    "model": "claude-sonnet-5",
                    "provider": "vertex_claude",
                },
                {
                    "type": "token_usage",
                    "task_id": "t-ws-1",
                    "event_id": "evt-ws-1",
                    "cli": "claude",
                    "provider": "vertex_claude",
                    "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 100, "output_tokens": 20, "total_tokens": 120},
                },
                WebSocketDisconnect(),
            ]
        )
        q = driver.bridge.create_queue("t-ws-1")
        # Spy during active connection before disconnect unregisters
        seen_providers: list[str] = []
        orig_put = driver.bridge.put

        def _spy_put(tid, msg):
            conn = driver.registry._agents.get("dev-pod-1")
            if conn:
                seen_providers.append(conn.provider)
            orig_put(tid, msg)

        with patch.object(driver.bridge, "put", side_effect=_spy_put):
            await agent_websocket_handler(ws, driver.registry, driver.bridge)

        assert seen_providers == ["vertex_claude"]
        routed = await q.get()
        assert routed["type"] == "token_usage"
        assert routed["usage"]["total_tokens"] == 120

        # Also verify list_agents exposes provider
        await driver.register_agent(agent_id="agy-1", role="architect", cli="agy", provider="vertex_gemini")
        listed = await driver.registry.list_agents()
        assert listed[0]["provider"] == "vertex_gemini"

    @pytest.mark.asyncio
    async def test_t16_dispatch_and_wake_loops_reconcile_streamed_residuals_without_abort(self, monkeypatch):
        from src.agents.dispatch import consume_wake_task, dispatch_to_agent
        from src.agents.llm.quota_registry import get_quota_registry, reset_quota_registry
        from src.agents.llm.types import PROVIDER_ENMAAS, PROVIDER_VERTEX_CLAUDE

        monkeypatch.setenv("ENMAAS_ENABLED", "true")
        monkeypatch.setenv("LLM_TPM_LIMIT_CLAUDE", "1000")
        monkeypatch.setenv("LLM_TPM_LIMIT_ENMAAS", "1000")
        reset_quota_registry()

        try:
            reg = get_quota_registry()
            driver = SidecarWsDriver()
            ws = await driver.register_agent(
                agent_id="dev-1", role="developer", cli="claude", provider="enmaas"
            )

            # 1. dispatch_to_agent._consume_queue: live delta exceeds 100% of pool -> NEVER aborts task
            async def _send_dispatch(payload):
                tid = payload["task_id"]
                driver.bridge.put(tid, {
                    "type": "token_usage",
                    "task_id": tid,
                    "event_id": "evt-disp",
                    "cli": "claude",
                    "provider": "enmaas",
                    "model": "glm-5",
                    "usage": {"input_tokens": 900, "output_tokens": 200, "total_tokens": 1100},
                })
                driver.bridge.put(tid, {
                    "type": "result",
                    "task_id": tid,
                    "event_id": "evt-disp",
                    "status": "success",
                    "source": "findings",
                    "output": "done",
                    "cli": "claude",
                    "provider": "vertex_claude",
                    "used_model": "claude-sonnet-5",
                    "usage": {"total_tokens": 1600},
                    "usage_by_provider": {
                        "enmaas": {"input_tokens": 900, "output_tokens": 200, "total_tokens": 1100},
                        "vertex_claude": {"input_tokens": 400, "output_tokens": 100, "total_tokens": 500},
                    },
                })

            ws.send_json = AsyncMock(side_effect=_send_dispatch)
            out, _ = await dispatch_to_agent(driver.registry, driver.bridge, "developer", "evt-disp", "fix bug")
            assert out == "done"
            assert reg.get(PROVIDER_ENMAAS).get_stats()["tokens_used_60s"] == 1100
            assert reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"] == 500

            # 2. consume_wake_task._consume: live 200 + terminal 450 -> residual +250 (total 450, not 650)
            wake_tid = "wake-t1"
            driver.bridge.create_queue(wake_tid)
            driver.bridge.put(wake_tid, {
                "type": "token_usage",
                "task_id": wake_tid,
                "event_id": "evt-wake",
                "cli": "claude",
                "provider": "vertex_claude",
                "model": "claude-sonnet-5",
                "usage": {"input_tokens": 150, "output_tokens": 50, "total_tokens": 200},
            })
            driver.bridge.put(wake_tid, {
                "type": "result",
                "task_id": wake_tid,
                "event_id": "evt-wake",
                "status": "success",
                "source": "findings",
                "output": "wake done",
                "cli": "claude",
                "provider": "vertex_claude",
                "used_model": "claude-sonnet-5",
                "usage": {"input_tokens": 350, "output_tokens": 100, "total_tokens": 450},
                "usage_by_provider": {
                    "vertex_claude": {"input_tokens": 350, "output_tokens": 100, "total_tokens": 450},
                },
            })
            wake_out, _ = await consume_wake_task(
                driver.bridge, driver.registry, "dev-1", wake_tid, "evt-wake", "developer"
            )
            assert wake_out == "wake done"
            assert reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"] == 500 + 450
        finally:
            reset_quota_registry()

    @pytest.mark.asyncio
    async def test_t16_resolve_sidecar_provider_registry_none_guard_and_precedence(self, monkeypatch):
        from src.agents.llm.types import PROVIDER_ENMAAS, PROVIDER_VERTEX_CLAUDE
        from src.agents.sidecar_usage import resolve_sidecar_provider

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        # 1. registry=None falls back cleanly to role_cli_map (or DEFAULT_SIDECAR_CLI="claude")
        assert await resolve_sidecar_provider("explorer", None, role_cli_map={"explorer": "claude"}) == PROVIDER_VERTEX_CLAUDE
        assert await resolve_sidecar_provider("developer", None, role_cli_map={"explorer": "claude"}) == PROVIDER_VERTEX_CLAUDE

        # 2. Connected AgentConnection.provider -> cli -> role_cli_map precedence under ENMAAS_ENABLED=true
        monkeypatch.setenv("ENMAAS_ENABLED", "true")
        reg = AgentRegistry()
        await reg.register("exp-1", "", AsyncMock(), [], cli="claude", model="m", ephemeral=True, event_id="evt-x", provider="")
        assert await resolve_sidecar_provider("explorer", reg, event_id="evt-x") == PROVIDER_ENMAAS

        await reg.register("exp-2", "", AsyncMock(), [], cli="claude", model="m", ephemeral=True, event_id="evt-y", provider="vertex_claude")
        assert await resolve_sidecar_provider("explorer", reg, event_id="evt-y") == PROVIDER_VERTEX_CLAUDE

    def test_t16_anthropic_cache_folding_and_hit_rate_bounded(self):
        from src.agents.sidecar_usage import validate_usage_payload

        res = validate_usage_payload(
            {
                "input_tokens": 50,
                "cache_read_input_tokens": 5000,
                "cache_creation_input_tokens": 0,
                "output_tokens": 100,
                "thinking_tokens": 40,
            },
            "claude",
        )
        assert res is not None
        slug, usage = res
        assert slug == "sidecar:claude"
        assert usage.input_tokens == 5050
        assert usage.cached_tokens == 5000
        assert usage.input_tokens >= usage.cached_tokens
        assert usage.total_tokens == 5150
        cache_hit_rate = (usage.cached_tokens / usage.input_tokens) * 100.0
        assert cache_hit_rate <= 100.0

    def test_t16_cli_scoped_normalize_sidecar_provider(self, monkeypatch):
        from src.agents.llm.types import PROVIDER_ENMAAS, PROVIDER_VERTEX_CLAUDE, PROVIDER_VERTEX_GEMINI
        from src.agents.sidecar_usage import normalize_sidecar_provider

        monkeypatch.setenv("ENMAAS_ENABLED", "true")
        assert normalize_sidecar_provider("agy", "enmaas") == PROVIDER_VERTEX_GEMINI
        assert normalize_sidecar_provider("claude", "vertex_gemini") == PROVIDER_ENMAAS

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        assert normalize_sidecar_provider("claude", "vertex_gemini") == PROVIDER_VERTEX_CLAUDE
        assert normalize_sidecar_provider("claude", "enmaas") == PROVIDER_VERTEX_CLAUDE

    def test_t16_invalid_sidecar_max_frame_tokens_env_fallback(self, monkeypatch):
        import importlib
        import src.agents.dispatch as dispatch_mod
        import src.agents.sidecar_usage as sidecar_usage_mod
        from src.agents.llm.quota_registry import parse_tpm_limit

        try:
            for bad_val in ("-1", "0", "bad"):
                monkeypatch.setenv("SIDECAR_MAX_FRAME_TOKENS", bad_val)
                assert parse_tpm_limit("SIDECAR_MAX_FRAME_TOKENS", 500_000) == 500_000
                reloaded = importlib.reload(sidecar_usage_mod)
                assert reloaded.SIDECAR_MAX_FRAME_TOKENS == 500_000

            monkeypatch.delenv("SIDECAR_MAX_TASK_TOKENS", raising=False)
            reloaded_dispatch = importlib.reload(dispatch_mod)
            assert reloaded_dispatch.SIDECAR_MAX_TASK_TOKENS == 1_500_000
        finally:
            monkeypatch.delenv("SIDECAR_MAX_FRAME_TOKENS", raising=False)
            monkeypatch.delenv("SIDECAR_MAX_TASK_TOKENS", raising=False)
            importlib.reload(sidecar_usage_mod)
            importlib.reload(dispatch_mod)

    @pytest.mark.asyncio
    async def test_t16_usage_by_provider_dedup_unknown_ignored_and_task_token_cap(self, monkeypatch):
        import src.agents.dispatch as dispatch_mod
        from src.agents.dispatch import _reconcile_terminal_token_usage, dispatch_to_agent
        from src.agents.llm import get_quota_registry, get_token_meter, reset_quota_registry
        from src.agents.llm.types import PROVIDER_VERTEX_CLAUDE

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        reset_quota_registry()
        try:
            reg = get_quota_registry()
            before_pool = reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"]

            # 1. Multi-key / unknown key usage_by_provider dedup:
            #    "unknown_provider" ignored; "enmaas" (250) + "vertex_claude" (400) under ENMAAS_ENABLED=false
            #    both normalize to PROVIDER_VERTEX_CLAUDE -> 250 + 150 residual = 400 (no identical-value masking).
            streamed: dict[str, dict[str, int]] = {}
            _reconcile_terminal_token_usage(
                {
                    "type": "result",
                    "cli": "claude",
                    "used_model": "claude-sonnet-5",
                    "usage_by_provider": {
                        "unknown_provider": {"input_tokens": 900, "output_tokens": 100, "total_tokens": 1000},
                        "enmaas": {"input_tokens": 200, "output_tokens": 50, "total_tokens": 250},
                        "vertex_claude": {"input_tokens": 300, "output_tokens": 100, "total_tokens": 400},
                    },
                },
                streamed,
                "evt-dedup",
                default_cli="claude",
                default_provider="vertex_claude",
            )
            assert reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"] == before_pool + 400

            # 2. SIDECAR_MAX_TASK_TOKENS cumulative task cap across live + terminal frames
            monkeypatch.setattr(dispatch_mod, "SIDECAR_MAX_TASK_TOKENS", 1000)
            driver = SidecarWsDriver()
            ws = await driver.register_agent(
                agent_id="dev-cap", role="developer", cli="claude", provider="vertex_claude"
            )

            async def _send_capped(payload):
                tid = payload["task_id"]
                driver.bridge.put(tid, {
                    "type": "token_usage", "task_id": tid, "event_id": "evt-cap",
                    "cli": "claude", "provider": "vertex_claude", "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 600, "output_tokens": 100, "total_tokens": 700},
                })
                driver.bridge.put(tid, {
                    "type": "token_usage", "task_id": tid, "event_id": "evt-cap",
                    "cli": "claude", "provider": "vertex_claude", "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 500, "output_tokens": 100, "total_tokens": 600},
                })
                driver.bridge.put(tid, {
                    "type": "result", "task_id": tid, "event_id": "evt-cap",
                    "status": "success", "source": "findings", "output": "capped ok",
                    "cli": "claude", "provider": "vertex_claude", "used_model": "claude-sonnet-5",
                    "usage": {"input_tokens": 1500, "output_tokens": 500, "total_tokens": 2000},
                })

            ws.send_json = AsyncMock(side_effect=_send_capped)
            out, _ = await dispatch_to_agent(
                driver.registry, driver.bridge, "developer", "evt-cap", "test cap",
                team_id="team-cap",
            )
            assert out == "capped ok"
            assert reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"] == before_pool + 400 + 1000
            assert get_token_meter().get_team_totals()["team-cap"]["total_tokens"] == 1000
        finally:
            reset_quota_registry()

    def test_t16_reconcile_terminal_allows_above_frame_cap_up_to_task_cap(self, monkeypatch):
        from src.agents.dispatch import (
            SIDECAR_MAX_TASK_TOKENS,
            _reconcile_terminal_token_usage,
            _record_live_token_usage,
        )
        from src.agents.llm import get_quota_registry, reset_quota_registry
        from src.agents.llm.types import PROVIDER_VERTEX_CLAUDE
        from src.agents.sidecar_usage import SIDECAR_MAX_FRAME_TOKENS

        assert SIDECAR_MAX_FRAME_TOKENS == 500_000
        assert SIDECAR_MAX_TASK_TOKENS == 1_500_000

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        reset_quota_registry()
        try:
            reg = get_quota_registry()
            before_pool = reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"]

            # 1. 400_000 streamed live + 900_000 cumulative terminal (>500k frame cap, <1.5M task cap)
            #    must record full +500_000 residual (900_000 total in pool, NOT clamped at 500_000).
            streamed_1: dict[str, dict[str, int]] = {}
            _record_live_token_usage(
                {
                    "type": "token_usage",
                    "cli": "claude",
                    "provider": "vertex_claude",
                    "model": "claude-sonnet-5",
                    "usage": {"input_tokens": 300_000, "output_tokens": 100_000, "total_tokens": 400_000},
                },
                streamed_1,
                "evt-term-900k",
                default_cli="claude",
                default_provider="vertex_claude",
            )
            assert reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"] == before_pool + 400_000

            _reconcile_terminal_token_usage(
                {
                    "type": "result",
                    "cli": "claude",
                    "provider": "vertex_claude",
                    "used_model": "claude-sonnet-5",
                    "usage": {"input_tokens": 700_000, "output_tokens": 200_000, "total_tokens": 900_000},
                },
                streamed_1,
                "evt-term-900k",
                default_cli="claude",
                default_provider="vertex_claude",
            )
            assert reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"] == before_pool + 900_000
            assert streamed_1[PROVIDER_VERTEX_CLAUDE]["total_tokens"] == 900_000

            # 2. 2_000_000 cumulative terminal payload is clamped at SIDECAR_MAX_TASK_TOKENS (1_500_000).
            streamed_2: dict[str, dict[str, int]] = {}
            _reconcile_terminal_token_usage(
                {
                    "type": "result",
                    "cli": "claude",
                    "provider": "vertex_claude",
                    "used_model": "claude-sonnet-5",
                    "usage": {"input_tokens": 1_600_000, "output_tokens": 400_000, "total_tokens": 2_000_000},
                },
                streamed_2,
                "evt-term-2m",
                default_cli="claude",
                default_provider="vertex_claude",
            )
            assert (
                reg.get(PROVIDER_VERTEX_CLAUDE).get_stats()["tokens_used_60s"]
                == before_pool + 900_000 + SIDECAR_MAX_TASK_TOKENS
            )
            assert streamed_2[PROVIDER_VERTEX_CLAUDE]["total_tokens"] == SIDECAR_MAX_TASK_TOKENS
        finally:
            reset_quota_registry()

    @pytest.mark.asyncio
    async def test_t16_dispatch_to_agent_forwards_team_id_to_token_meter(self, monkeypatch):
        from src.agents.dispatch import dispatch_to_agent
        from src.agents.llm import get_token_meter, reset_quota_registry

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        reset_quota_registry()
        try:
            meter = get_token_meter()
            before_team = meter.get_team_totals().get("team-alpha", {}).get("total_tokens", 0)
            driver = SidecarWsDriver()
            ws = await driver.register_agent(
                agent_id="dev-team", role="developer", cli="claude", provider="vertex_claude"
            )

            async def _send(payload):
                tid = payload["task_id"]
                driver.bridge.put(tid, {
                    "type": "result", "task_id": tid, "event_id": "evt-team",
                    "status": "success", "source": "findings", "output": "team ok",
                    "cli": "claude", "provider": "vertex_claude", "used_model": "claude-sonnet-5",
                    "usage": {"input_tokens": 200, "output_tokens": 50, "total_tokens": 250},
                })

            ws.send_json = AsyncMock(side_effect=_send)
            out, _ = await dispatch_to_agent(
                driver.registry, driver.bridge, "developer", "evt-team", "do work",
                team_id="team-alpha",
            )
            assert out == "team ok"
            after_team = meter.get_team_totals().get("team-alpha", {}).get("total_tokens", 0)
            assert after_team - before_team == 250
        finally:
            reset_quota_registry()

    @pytest.mark.asyncio
    async def test_t16_agent_ws_handler_hardening_invalid_frames_provider_and_dup_wake(self):
        from src.agents.agent_ws_handler import agent_websocket_handler

        # 1. Non-dict JSON on register closes 1008
        driver_bad = SidecarWsDriver()
        ws_bad = AsyncMock()
        ws_bad.receive_json = AsyncMock(return_value=["not", "a", "dict"])
        await agent_websocket_handler(ws_bad, driver_bad.registry, driver_bad.bridge)
        ws_bad.close.assert_awaited_once_with(code=1008, reason="Expected register message")
        assert await driver_bad.registry.list_agents() == []

        # 2. Untrusted register.provider sanitized to "", non-dict frames ignored,
        #    unhashable/non-str task_id ignored without TypeError, duplicate wake_register ignored.
        driver = SidecarWsDriver()
        ws = AsyncMock()
        wake_calls: list[tuple[dict, str]] = []

        async def _on_wake(data, agent_id):
            wake_calls.append((data, agent_id))

        ws.receive_json = AsyncMock(
            side_effect=[
                {
                    "type": "register",
                    "agent_id": "dev-harden",
                    "role": "developer",
                    "cli": "claude",
                    "model": "claude-sonnet-5",
                    "provider": "untrusted-evil-provider",
                },
                ["non-dict-frame"],
                "string-frame",
                {"type": "token_usage", "task_id": ["unhashable"], "usage": {"total_tokens": 10}},
                {"type": "token_usage", "task_id": 12345, "usage": {"total_tokens": 10}},
                {"type": "wake_register", "task_id": {"unhashable": True}, "event_id": "evt-h"},
                {"type": "wake_register", "task_id": "wake-dup-1", "event_id": "evt-h", "role": "developer"},
                {"type": "wake_register", "task_id": "wake-dup-1", "event_id": "evt-h", "role": "developer"},
                WebSocketDisconnect(),
            ]
        )

        seen_providers: list[str] = []
        orig_mark_busy = driver.registry.mark_busy

        async def _spy_mark_busy(aid, eid, tid, role=""):
            conn = driver.registry._agents.get(aid)
            if conn is not None:
                seen_providers.append(conn.provider)
            return await orig_mark_busy(aid, eid, tid, role=role)

        with patch.object(driver.registry, "mark_busy", side_effect=_spy_mark_busy):
            await agent_websocket_handler(ws, driver.registry, driver.bridge, on_wake=_on_wake)

        await asyncio.sleep(0)
        assert seen_providers == [""]
        assert len(wake_calls) == 1
        assert wake_calls[0][0]["task_id"] == "wake-dup-1"
        assert driver.bridge.get_queue("wake-dup-1") is not None


class TestSidecarPreDispatchGateT17:
    """T-17: 85% pre-dispatch gate defers PRIORITY_NORMAL while letting chat & approved events into 15% reserve."""

    @staticmethod
    def _make_ctx(event_doc: EventDocument):
        ctx = MagicMock()
        ctx.is_task_running = MagicMock(return_value=False)
        ctx.is_dispatch_locked = MagicMock(return_value=False)
        ctx.increment_routing_depth = MagicMock(return_value=1)
        ctx.stamp_event = AsyncMock()
        ctx.next_turn_number = AsyncMock(return_value=2)
        ctx.append_and_broadcast = AsyncMock()
        ctx.emit_pulse = AsyncMock()
        ctx.record_event = AsyncMock()
        ctx.broadcast = AsyncMock()
        ctx.get_agent_instance = MagicMock(return_value=MagicMock())
        ctx.get_ws_mode = MagicMock(return_value="reverse")
        ctx.run_agent_task = AsyncMock()
        ctx.dispatch_handler = AsyncMock(return_value=False)
        bb = AsyncMock()
        bb.get_event = AsyncMock(return_value=event_doc)
        bb.get_service = AsyncMock(return_value=None)
        ctx.get_blackboard = MagicMock(return_value=bb)
        return ctx

    @staticmethod
    def _event_with_tpm_defers(eid: str, count: int) -> EventDocument:
        turns = [
            ConversationTurn(
                turn=idx + 1,
                actor="brain",
                action="defer",
                thoughts="Deferring event for 30s: Provider TPM reserve reached (PRIORITY_NORMAL deferred)",
            )
            for idx in range(count)
        ]
        return EventDocument(
            id=eid,
            source="headhunter",
            service="svc",
            event=EventInput(reason="pr check", evidence="e"),
            conversation=turns,
        )

    @pytest.mark.asyncio
    async def test_t17_85_pct_gate_defers_unapproved_headhunter_admits_chat_and_approved(self, monkeypatch):
        from src.agents.handlers_dispatch import handle_select_agent
        from src.agents.llm.quota_registry import get_quota_registry, reset_quota_registry
        from src.agents.llm.types import PROVIDER_VERTEX_CLAUDE

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        monkeypatch.setenv("LLM_TPM_LIMIT_CLAUDE", "100000")
        monkeypatch.setenv("LLM_TPM_NORMAL_CEILING_RATIO", "0.85")
        reset_quota_registry()

        try:
            reg = get_quota_registry()
            reg.get(PROVIDER_VERTEX_CLAUDE).record_post_hoc(86_000)  # 86% >= 85%

            ws_reg = AgentRegistry()
            await ws_reg.register(
                "dev-1", "developer", AsyncMock(), [], cli="claude", model="claude-sonnet-5",
                provider="vertex_claude",
            )

            hh_normal = EventDocument(
                id="evt-hh-norm", source="headhunter", service="svc",
                event=EventInput(reason="pr check", evidence="e"),
            )
            hh_approved = EventDocument(
                id="evt-hh-appr", source="headhunter", service="svc",
                approved_by="alice@redhat.com",
                event=EventInput(reason="pr check", evidence="e"),
            )
            chat_evt = EventDocument(
                id="evt-chat-high", source="chat", service="svc",
                event=EventInput(reason="help me", evidence="e"),
                conversation=[ConversationTurn(turn=1, actor="user", action="message", thoughts="hi")],
            )

            with patch("src.agents.handlers_dispatch.get_registry_and_bridge", return_value=(ws_reg, None)):
                ctx_norm = self._make_ctx(hh_normal)
                await handle_select_agent(ctx_norm, hh_normal.id, {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_norm.dispatch_handler.assert_awaited_once()
                assert ctx_norm.dispatch_handler.call_args[0][0] == "defer_event"
                assert 30 <= ctx_norm.dispatch_handler.call_args[0][2]["delay_seconds"] <= 36
                ctx_norm.run_agent_task.assert_not_awaited()

                ctx_appr = self._make_ctx(hh_approved)
                await handle_select_agent(ctx_appr, hh_approved.id, {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_appr.dispatch_handler.assert_not_awaited()
                ctx_appr.run_agent_task.assert_awaited_once()

                ctx_chat = self._make_ctx(chat_evt)
                await handle_select_agent(ctx_chat, chat_evt.id, {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_chat.dispatch_handler.assert_not_awaited()
                ctx_chat.run_agent_task.assert_awaited_once()
        finally:
            reset_quota_registry()

    @pytest.mark.asyncio
    async def test_t17_pre_dispatch_gate_fails_open_on_saturation_check_error(self, caplog):
        import logging
        from src.agents.handlers_dispatch import handle_select_agent

        hh_normal = self._event_with_tpm_defers("evt-hh-sat-err", 0)
        ctx = self._make_ctx(hh_normal)

        with (
            caplog.at_level(logging.WARNING, logger="darwin.brain"),
            patch("src.agents.handlers_dispatch.get_registry_and_bridge", return_value=(AgentRegistry(), None)),
            patch("src.agents.handlers_dispatch.resolve_sidecar_provider", AsyncMock(side_effect=RuntimeError("registry probe boom"))),
        ):
            await handle_select_agent(ctx, hh_normal.id, {"agent_name": "developer", "task_instruction": "run"}, None)

        ctx.run_agent_task.assert_awaited_once()
        ctx.dispatch_handler.assert_not_awaited()
        assert any("failing open" in rec.message for rec in caplog.records)

        # Also verify pool_exhausted lookup failure inside the same try-block still fails open
        caplog.clear()
        fake_quota_reg = MagicMock()
        fake_quota_reg.is_normal_saturated = MagicMock(return_value=True)
        fake_quota_reg.get = MagicMock(side_effect=RuntimeError("pool stats boom"))
        ctx_stats_err = self._make_ctx(self._event_with_tpm_defers("evt-hh-stats-err", 2))

        with (
            caplog.at_level(logging.WARNING, logger="darwin.brain"),
            patch("src.agents.handlers_dispatch.get_registry_and_bridge", return_value=(AgentRegistry(), None)),
            patch("src.agents.handlers_dispatch.resolve_sidecar_provider", AsyncMock(return_value="vertex_claude")),
            patch("src.agents.handlers_dispatch.get_quota_registry", return_value=fake_quota_reg),
        ):
            await handle_select_agent(ctx_stats_err, "evt-hh-stats-err", {"agent_name": "developer", "task_instruction": "run"}, None)

        ctx_stats_err.run_agent_task.assert_awaited_once()
        ctx_stats_err.dispatch_handler.assert_not_awaited()
        assert any("failing open" in rec.message for rec in caplog.records)

    @pytest.mark.asyncio
    async def test_t17_pre_dispatch_gate_exponential_backoff_and_max_defers_cap(self, monkeypatch):
        from src.agents.handlers_dispatch import handle_select_agent
        from src.agents.llm.quota_registry import get_quota_registry, reset_quota_registry
        from src.agents.llm.types import PROVIDER_VERTEX_CLAUDE

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        monkeypatch.setenv("LLM_TPM_LIMIT_CLAUDE", "100000")
        monkeypatch.setenv("LLM_TPM_NORMAL_CEILING_RATIO", "0.85")
        reset_quota_registry()

        try:
            get_quota_registry().get(PROVIDER_VERTEX_CLAUDE).record_post_hoc(86_000)

            ws_reg = AgentRegistry()
            await ws_reg.register(
                "dev-1", "developer", AsyncMock(), [], cli="claude", model="claude-sonnet-5",
                provider="vertex_claude",
            )

            with patch("src.agents.handlers_dispatch.get_registry_and_bridge", return_value=(ws_reg, None)):
                monkeypatch.setenv("SIDECAR_TPM_MAX_DEFERS", "2")

                ctx_0 = self._make_ctx(self._event_with_tpm_defers("evt-backoff-0", 0))
                await handle_select_agent(ctx_0, "evt-backoff-0", {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_0.dispatch_handler.assert_awaited_once()
                assert ctx_0.dispatch_handler.call_args[0][0] == "defer_event"
                assert 30 <= ctx_0.dispatch_handler.call_args[0][2]["delay_seconds"] <= 36
                ctx_0.run_agent_task.assert_not_awaited()

                ctx_1 = self._make_ctx(self._event_with_tpm_defers("evt-backoff-1", 1))
                await handle_select_agent(ctx_1, "evt-backoff-1", {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_1.dispatch_handler.assert_awaited_once()
                assert ctx_1.dispatch_handler.call_args[0][0] == "defer_event"
                assert 60 <= ctx_1.dispatch_handler.call_args[0][2]["delay_seconds"] <= 72
                ctx_1.run_agent_task.assert_not_awaited()

                ctx_2_cap = self._make_ctx(self._event_with_tpm_defers("evt-backoff-2-cap", 2))
                await handle_select_agent(ctx_2_cap, "evt-backoff-2-cap", {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_2_cap.run_agent_task.assert_awaited_once()
                ctx_2_cap.dispatch_handler.assert_not_awaited()

                monkeypatch.setenv("SIDECAR_TPM_MAX_DEFERS", "5")
                ctx_2 = self._make_ctx(self._event_with_tpm_defers("evt-backoff-2", 2))
                await handle_select_agent(ctx_2, "evt-backoff-2", {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_2.dispatch_handler.assert_awaited_once()
                assert ctx_2.dispatch_handler.call_args[0][0] == "defer_event"
                assert 120 <= ctx_2.dispatch_handler.call_args[0][2]["delay_seconds"] <= 144
                ctx_2.run_agent_task.assert_not_awaited()

                # Deterministic jitter math check (0.1 -> +10%)
                with monkeypatch.context() as mp:
                    mp.setattr("src.agents.handlers_dispatch.random.uniform", lambda a, b: 0.1)
                    ctx_j0 = self._make_ctx(self._event_with_tpm_defers("evt-jitter-0", 0))
                    await handle_select_agent(ctx_j0, "evt-jitter-0", {"agent_name": "developer", "task_instruction": "run"}, None)
                    ctx_j0.dispatch_handler.assert_awaited_once()
                    assert ctx_j0.dispatch_handler.call_args[0][2]["delay_seconds"] == 33

                    ctx_j1 = self._make_ctx(self._event_with_tpm_defers("evt-jitter-1", 1))
                    await handle_select_agent(ctx_j1, "evt-jitter-1", {"agent_name": "developer", "task_instruction": "run"}, None)
                    ctx_j1.dispatch_handler.assert_awaited_once()
                    assert ctx_j1.dispatch_handler.call_args[0][2]["delay_seconds"] == 66

                # At >= 100% physical pool exhaustion (100_000 / 100_000), max_defers cap does NOT bypass deferral
                monkeypatch.setenv("SIDECAR_TPM_MAX_DEFERS", "2")
                get_quota_registry().get(PROVIDER_VERTEX_CLAUDE).record_post_hoc(14_000)  # 86_000 + 14_000 = 100_000
                ctx_exhausted = self._make_ctx(self._event_with_tpm_defers("evt-exhausted-cap", 2))
                await handle_select_agent(ctx_exhausted, "evt-exhausted-cap", {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_exhausted.dispatch_handler.assert_awaited_once()
                assert ctx_exhausted.dispatch_handler.call_args[0][0] == "defer_event"
                ctx_exhausted.run_agent_task.assert_not_awaited()
        finally:
            reset_quota_registry()

    @pytest.mark.asyncio
    async def test_t17_pre_dispatch_gate_schmitt_trigger_hysteresis(self, monkeypatch):
        from src.agents.handlers_dispatch import handle_select_agent
        from src.agents.llm.quota_registry import get_quota_registry, reset_quota_registry
        from src.agents.llm.types import PROVIDER_VERTEX_CLAUDE

        monkeypatch.setenv("ENMAAS_ENABLED", "false")
        monkeypatch.setenv("LLM_TPM_LIMIT_CLAUDE", "100000")
        monkeypatch.setenv("LLM_TPM_NORMAL_CEILING_RATIO", "0.85")
        reset_quota_registry()

        try:
            ws_reg = AgentRegistry()
            await ws_reg.register(
                "dev-1", "developer", AsyncMock(), [], cli="claude", model="claude-sonnet-5",
                provider="vertex_claude",
            )

            # sustained=85,000; hysteresis threshold=int(85000*0.94)=79,900.
            # At 82,000 (between 79,900 and 85,000): fresh event dispatches, deferred event stays deferred.
            get_quota_registry().get(PROVIDER_VERTEX_CLAUDE).record_post_hoc(82_000)

            with patch("src.agents.handlers_dispatch.get_registry_and_bridge", return_value=(ws_reg, None)):
                ctx_fresh = self._make_ctx(self._event_with_tpm_defers("evt-hyst-fresh", 0))
                await handle_select_agent(ctx_fresh, "evt-hyst-fresh", {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_fresh.run_agent_task.assert_awaited_once()
                ctx_fresh.dispatch_handler.assert_not_awaited()

                ctx_deferred = self._make_ctx(self._event_with_tpm_defers("evt-hyst-def", 1))
                await handle_select_agent(ctx_deferred, "evt-hyst-def", {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_deferred.dispatch_handler.assert_awaited_once()
                assert ctx_deferred.dispatch_handler.call_args[0][0] == "defer_event"
                assert 60 <= ctx_deferred.dispatch_handler.call_args[0][2]["delay_seconds"] <= 72
                ctx_deferred.run_agent_task.assert_not_awaited()

            # At 79,000 (below 79,900): previously deferred event proceeds with dispatch.
            reset_quota_registry()
            get_quota_registry().get(PROVIDER_VERTEX_CLAUDE).record_post_hoc(79_000)

            with patch("src.agents.handlers_dispatch.get_registry_and_bridge", return_value=(ws_reg, None)):
                ctx_below = self._make_ctx(self._event_with_tpm_defers("evt-hyst-below", 1))
                await handle_select_agent(ctx_below, "evt-hyst-below", {"agent_name": "developer", "task_instruction": "run"}, None)
                ctx_below.run_agent_task.assert_awaited_once()
                ctx_below.dispatch_handler.assert_not_awaited()
        finally:
            reset_quota_registry()
