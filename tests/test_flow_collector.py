# BlackBoard/tests/test_flow_collector.py
# @ai-rules:
# 1. [Pattern]: 4-Layer Farley ATDD specification for FlowCollector telemetry, TPM quota stats, and downsampling.
# 2. [Constraint]: Tests exercise protocol drivers and Domain DSL without direct Redis/network side effects.
"""
4-Layer Farley ATDD Executable Acceptance Specification
Scenario T-8: Tampering Strike Telemetry & ATDD Cycle Time Downsampling

Layer 1: Domain Scenarios (Given/When/Then)
Layer 2: Domain DSL operations
Layer 3: Protocol Drivers (FastAPI HTTP Client & Blackboard State Aggregator)
Layer 4: System Under Test (events.py route, blackboard.py downsampler, models.py)
"""
from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from src.models import FlowSnapshot


# =============================================================================
# Layer 3: Protocol Drivers
# =============================================================================
class FlowCollectorProtocolDriver:
    """Adapts HTTP calls to /events/{id}/tamper and downsampling state."""

    def __init__(self, app, mock_bb, mock_redis):
        self.app = app
        self.mock_bb = mock_bb
        self.mock_redis = mock_redis

    async def post_tamper(self, event_id: str) -> tuple[int, dict]:
        from src import dependencies
        self.app.dependency_overrides[dependencies.get_blackboard] = lambda: self.mock_bb
        self.app.dependency_overrides[dependencies.get_redis] = lambda: self.mock_redis
        try:
            transport = ASGITransport(app=self.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(f"/events/{event_id}/tamper")
                return resp.status_code, resp.json() if resp.is_success else {}
        finally:
            self.app.dependency_overrides.clear()

    def downsample_snapshots(
        self, snapshots: list[FlowSnapshot], bucket_seconds: int = 300
    ) -> list[FlowSnapshot]:
        from src.state.blackboard import BlackboardState
        bb = BlackboardState.__new__(BlackboardState)
        return bb._downsample_snapshots(snapshots, bucket_seconds=bucket_seconds)


# =============================================================================
# Layer 2: Domain DSL
# =============================================================================
class FlowCollectorDSL:
    """Domain DSL for verifying tampering strikes and ATDD cycle telemetry."""

    def __init__(self, driver: FlowCollectorProtocolDriver):
        self.driver = driver
        self.last_status_code: int | None = None
        self.last_response: dict | None = None
        self.downsampled_results: list[FlowSnapshot] = []

    def given_active_event(self, event_id: str):
        mock_event = MagicMock()
        mock_event.id = event_id
        self.driver.mock_bb.get_event = AsyncMock(return_value=mock_event)

    def given_redis_strike_increment(self, new_count: int):
        self.driver.mock_redis.incr = AsyncMock(return_value=new_count)

    def given_snapshots(self, snapshots: list[FlowSnapshot]):
        self.snapshots_input = snapshots

    async def when_tamper_reported(self, event_id: str):
        code, body = await self.driver.post_tamper(event_id)
        self.last_status_code = code
        self.last_response = body

    def when_downsampler_invoked(self, bucket_seconds: int = 300):
        self.downsampled_results = self.driver.downsample_snapshots(
            self.snapshots_input, bucket_seconds=bucket_seconds
        )

    def then_tamper_response_recorded(self, expected_strikes: int):
        assert self.last_status_code == 200, f"Expected 200, got {self.last_status_code}"
        assert self.last_response.get("ok") is True
        assert self.last_response.get("strikes") == expected_strikes

    def then_redis_key_incremented(self, expected_key: str = "darwin:flow:tampering_strikes"):
        self.driver.mock_redis.incr.assert_any_await(expected_key)

    def then_redis_event_scoped_key_incremented_last(self, event_id: str):
        # The returned strike count comes from the event-scoped key, so it must be the last incr.
        self.driver.mock_redis.incr.assert_awaited_with(f"darwin:flow:tampering_strikes:{event_id}")

    def then_downsampled_strikes_is(self, expected_strikes: int):
        assert len(self.downsampled_results) == 1, f"Expected 1 bucket, got {len(self.downsampled_results)}"
        actual = getattr(self.downsampled_results[0], "tampering_strikes", None)
        assert actual == expected_strikes, f"Expected tampering_strikes={expected_strikes}, got {actual}"

    def then_downsampled_cycle_sec_is(self, expected_sec: float):
        assert len(self.downsampled_results) == 1, f"Expected 1 bucket, got {len(self.downsampled_results)}"
        actual = getattr(self.downsampled_results[0], "atdd_cycle_sec", None)
        assert actual == pytest.approx(expected_sec, rel=1e-3), (
            f"Expected atdd_cycle_sec={expected_sec}, got {actual}"
        )


# =============================================================================
# Layer 1: Domain Scenarios (Scenario T-8)
# =============================================================================
class TestFlowCollectorScenarioT8:
    """Scenario T-8: Farley ATDD closed-loop telemetry & downsampling invariants."""

    @pytest.mark.asyncio
    async def test_t8_tamper_endpoint_increments_strike_counter(self):
        """
        Scenario: Sidecar proxy reports tampering denial to FastAPI backend.
        Given an active event 'evt-strike-01'
        When POST /events/evt-strike-01/tamper is invoked
        Then status 200 returned with strike count, and Redis counter incremented.
        """
        with patch("src.main.lifespan") as mock_lifespan:
            mock_lifespan.return_value.__aenter__ = AsyncMock()
            mock_lifespan.return_value.__aexit__ = AsyncMock()
            from src.main import app

            mock_bb = AsyncMock()
            mock_redis = AsyncMock()
            driver = FlowCollectorProtocolDriver(app, mock_bb, mock_redis)
            dsl = FlowCollectorDSL(driver)

            dsl.given_active_event("evt-strike-01")
            dsl.given_redis_strike_increment(new_count=3)

            await dsl.when_tamper_reported("evt-strike-01")

            dsl.then_tamper_response_recorded(expected_strikes=3)
            dsl.then_redis_key_incremented("darwin:flow:tampering_strikes")
            dsl.then_redis_event_scoped_key_incremented_last("evt-strike-01")

    def test_t8_downsample_snapshots_preserves_monotonic_strikes_with_max(self):
        """
        Scenario: 5-minute bucket aggregation preserves cumulative strike counter.
        Given a bucket of snapshots with tampering_strikes = [1, 5, 2]
        When _downsample_snapshots aggregates the bucket
        Then tampering_strikes equals 5 (monotonic max invariant).
        """
        driver = FlowCollectorProtocolDriver(None, None, None)
        dsl = FlowCollectorDSL(driver)

        # Build 3 snapshots within the same 300s bucket (t=300 to t=599)
        s1 = FlowSnapshot(timestamp=310.0)
        s2 = FlowSnapshot(timestamp=320.0)
        s3 = FlowSnapshot(timestamp=330.0)

        # Set tampering_strikes on snapshots (testing attribute downsampling)
        object.__setattr__(s1, "tampering_strikes", 1)
        object.__setattr__(s2, "tampering_strikes", 5)
        object.__setattr__(s3, "tampering_strikes", 2)

        dsl.given_snapshots([s1, s2, s3])
        dsl.when_downsampler_invoked(bucket_seconds=300)

        dsl.then_downsampled_strikes_is(5)

    def test_t8_downsample_snapshots_averages_atdd_cycle_sec(self):
        """
        Scenario: 5-minute bucket aggregation computes arithmetic average of cycle time.
        Given snapshots with atdd_cycle_sec = [40.0, 80.0, None]
        When _downsample_snapshots aggregates the bucket
        Then atdd_cycle_sec equals 60.0.
        """
        driver = FlowCollectorProtocolDriver(None, None, None)
        dsl = FlowCollectorDSL(driver)

        s1 = FlowSnapshot(timestamp=610.0)
        s2 = FlowSnapshot(timestamp=620.0)
        s3 = FlowSnapshot(timestamp=630.0)

        object.__setattr__(s1, "atdd_cycle_sec", 40.0)
        object.__setattr__(s2, "atdd_cycle_sec", 80.0)
        object.__setattr__(s3, "atdd_cycle_sec", None)

        dsl.given_snapshots([s1, s2, s3])
        dsl.when_downsampler_invoked(bucket_seconds=300)

        dsl.then_downsampled_cycle_sec_is(60.0)

    def test_t8_flow_snapshot_schema_contains_tampering_and_cycle_fields(self):
        """
        Scenario: FlowSnapshot Pydantic schema contains required Farley telemetry fields.
        """
        fields = FlowSnapshot.model_fields
        assert "tampering_strikes" in fields, "FlowSnapshot missing tampering_strikes field"
        assert "atdd_cycle_sec" in fields, "FlowSnapshot missing atdd_cycle_sec field"
        assert "quota_shed_tier1_total" in fields, "FlowSnapshot missing quota_shed_tier1_total"
        assert "quota_shed_tier2_total" in fields, "FlowSnapshot missing quota_shed_tier2_total"

    @pytest.mark.asyncio
    async def test_flow_collector_build_snapshot_quota_shedding_telemetry(self):
        """Scenario: FlowCollector._build_snapshot reads quota shedding telemetry from Redis.
        Given Redis keys darwin:flow:quota_shed_tier1_total=7 and quota_shed_tier2_total=3,
        When _build_snapshot() is called,
        Then the snapshot populates quota_shed_tier1_total=7 and quota_shed_tier2_total=3.
        When Redis raises an error, values default to 0 without failing snapshot generation.
        """
        from src.observers.flow_collector import FlowCollector

        mock_scheduler = MagicMock()
        mock_scheduler.metrics = {"reconcile_count": 0, "error_count": 0}
        mock_bb = AsyncMock()
        mock_bb.get_flow_metrics = AsyncMock(return_value={"queue_depth": 0, "waiting_approval_events": 0})
        mock_bb.get_active_events_with_status = AsyncMock(return_value={})
        mock_redis = AsyncMock()
        mock_bb.redis = mock_redis

        collector = FlowCollector(
            scheduler=mock_scheduler,
            blackboard=mock_bb,
        )

        async def mock_redis_get(key):
            if key == "darwin:flow:quota_shed_tier1_total":
                return "7"
            if key == "darwin:flow:quota_shed_tier2_total":
                return "3"
            return None

        mock_redis.get = AsyncMock(side_effect=mock_redis_get)
        mock_redis.mget = AsyncMock(return_value=["7", "3"])

        snapshot = await collector._build_snapshot()
        assert snapshot.quota_shed_tier1_total == 7
        assert snapshot.quota_shed_tier2_total == 3

        # Failure resiliency: Redis connection error falls back to 0
        mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))
        mock_redis.mget = AsyncMock(side_effect=ConnectionError("Redis down"))

        snapshot_err = await collector._build_snapshot()
        assert snapshot_err.quota_shed_tier1_total == 0
        assert snapshot_err.quota_shed_tier2_total == 0

    @pytest.mark.asyncio
    async def test_flow_collector_quota_tracker_metrics_and_reset_guard(self):
        """Scenario: FlowCollector populates TPM usage, limit, utilization, and interval throttle delta."""
        from src.observers.flow_collector import FlowCollector

        mock_scheduler = MagicMock()
        mock_scheduler.metrics = {"reconcile_count": 0, "error_count": 0}
        mock_bb = AsyncMock()
        mock_bb.get_flow_metrics = AsyncMock(return_value={"queue_depth": 0, "waiting_approval_events": 0})
        mock_bb.get_active_events_with_status = AsyncMock(return_value={})
        mock_bb.redis = None

        # Cold-start: callable returning None before first Gemini call -> all zeros
        cold_collector = FlowCollector(
            scheduler=mock_scheduler,
            blackboard=mock_bb,
            quota_tracker=lambda: None,
        )
        s0 = await cold_collector._build_snapshot()
        assert (s0.tpm_used, s0.tpm_limit, s0.tpm_utilization_pct, s0.quota_throttle_delta) == (0, 0, 0.0, 0)

        tracker = MagicMock()
        tracker.get_stats.side_effect = [
            {"tokens_used_60s": 1_200_000, "tpm_limit": 3_000_000, "utilization_pct": 40.0, "throttle_events": 2},
            {"tokens_used_60s": 1_800_000, "tpm_limit": 3_000_000, "utilization_pct": 60.0, "throttle_events": 5},
            {"tokens_used_60s": 300_000, "tpm_limit": 3_000_000, "utilization_pct": 10.0, "throttle_events": 1},
            RuntimeError("stats broken"),
            {"tokens_used_60s": 900_000, "tpm_limit": 3_000_000, "utilization_pct": 30.0, "throttle_events": 4},
        ]
        collector = FlowCollector(
            scheduler=mock_scheduler,
            blackboard=mock_bb,
            quota_tracker=lambda: tracker,
        )

        s1 = await collector._build_snapshot()
        assert (s1.tpm_used, s1.tpm_limit, s1.tpm_utilization_pct, s1.quota_throttle_delta) == (1_200_000, 3_000_000, 40.0, 2)

        s2 = await collector._build_snapshot()
        assert (s2.tpm_used, s2.tpm_limit, s2.tpm_utilization_pct, s2.quota_throttle_delta) == (1_800_000, 3_000_000, 60.0, 3)

        # Counter reset (new tracker / restart): must not emit negative throttle delta
        s3 = await collector._build_snapshot()
        assert s3.quota_throttle_delta == 1

        # Exception resilience
        s4 = await collector._build_snapshot()
        assert (s4.tpm_used, s4.tpm_limit, s4.tpm_utilization_pct, s4.quota_throttle_delta) == (0, 0, 0.0, 0)

        # Direct instance DI (non-callable QuotaTracker)
        direct_collector = FlowCollector(
            scheduler=mock_scheduler,
            blackboard=mock_bb,
            quota_tracker=tracker,
        )
        s5 = await direct_collector._build_snapshot()
        assert (s5.tpm_used, s5.tpm_limit, s5.tpm_utilization_pct, s5.quota_throttle_delta) == (900_000, 3_000_000, 30.0, 4)

    def test_default_tpm_limit_matches_helm_values(self, monkeypatch):
        """Scenario: Helm gcp.tpmLimit and llm.create_adapter default agree on 3,000,000 TPM."""
        from pathlib import Path
        import yaml
        import src.agents.llm as llm_pkg

        repo_root = Path(__file__).resolve().parent.parent
        values = yaml.safe_load((repo_root / "helm" / "values.yaml").read_text())
        assert str(values["gcp"]["tpmLimit"]) == str(llm_pkg.DEFAULT_TPM_LIMIT) == "3000000"

        for bad_env in (None, "", "-5", "bad"):
            if bad_env is None:
                monkeypatch.delenv("LLM_TPM_LIMIT", raising=False)
            else:
                monkeypatch.setenv("LLM_TPM_LIMIT", bad_env)
            monkeypatch.setattr(llm_pkg, "_quota_tracker", None)
            with patch("src.agents.llm.gemini_client.GeminiAdapter") as mock_adapter_cls:
                llm_pkg.create_adapter("gemini", "proj", "global", "gemini-4-carbon")
            assert mock_adapter_cls.call_args.kwargs["quota_tracker"].get_stats()["tpm_limit"] == 3_000_000


# =============================================================================
# Slice 2C ATDD (Step 9 / T-15): Headhunter Per-Platform & Breaker Telemetry
# =============================================================================


class HeadhunterTelemetryProtocolDriver:
    """Layer 3 Protocol Driver for Headhunter properties, FlowCollector, GET /flow, and downsampler."""

    async def get_flow_metrics(self, mock_bb: AsyncMock, mock_brain: MagicMock) -> tuple[int, dict]:
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
                    return resp.status_code, resp.json() if resp.is_success else {}
            finally:
                dependencies._blackboard = orig_bb
                dependencies._brain = orig_brain


class TestFlowCollectorHeadhunterParityT15:
    """Layer 1-4 ATDD scenarios for T-15 (per-platform pending & breaker telemetry)."""

    def test_t15a_headhunter_public_telemetry_properties_and_sum_invariant(self):
        """Given Headhunter with GitLab/GitHub pending, queued, issue, and feedback sub-counters
        When public telemetry properties are read
        Then gitlab_pending_count, github_pending_count, gitlab_breaker_state, github_breaker_state
        are exposed and pending_count == gitlab_pending_count + github_pending_count."""
        from src.agents.headhunter import Headhunter

        mock_bb = MagicMock()
        hh = Headhunter(mock_bb, gitlab_enabled=False)
        hh._gitlab_pending = 2
        hh._gitlab_queued = 3
        hh._github_pending = 4
        hh._github_issue_pending = 1
        hh._github_queued = 5
        hh._github_issue_queued = 2
        hh._github_feedback_pending = 6
        hh._breakers["gitlab"].state = "open"
        hh._breakers["github"].state = "half_open"

        assert hh.gitlab_pending_count == 5
        assert hh.github_pending_count == 18
        assert hh.pending_count == hh.gitlab_pending_count + hh.github_pending_count
        assert hh.gitlab_breaker_state == "open"
        assert hh.github_breaker_state == "half_open"

    @pytest.mark.asyncio
    async def test_t15b_flow_collector_and_get_flow_populate_per_platform_and_breaker_fields(self):
        """Given Headhunter exposing per-platform pending counts and breaker states
        When FlowCollector._build_snapshot() and GET /flow execute
        Then FlowSnapshot and FlowMetricsResponse both populate all 4 Headhunter telemetry fields."""
        from src.agents.headhunter import Headhunter
        from src.observers.flow_collector import FlowCollector

        mock_bb = AsyncMock()
        mock_bb.get_flow_metrics = AsyncMock(
            return_value={"queue_depth": 1, "active_events": 2, "waiting_approval_events": 0}
        )
        mock_bb.get_active_events_with_status = AsyncMock(return_value={})
        mock_bb.get_latest_flow_snapshot = AsyncMock(return_value=None)
        mock_bb.redis = None

        hh = Headhunter(mock_bb, gitlab_enabled=False)
        hh._gitlab_pending = 3
        hh._gitlab_queued = 1
        hh._github_pending = 2
        hh._github_queued = 4
        hh._breakers["gitlab"].state = "half_open"
        hh._breakers["github"].state = "open"

        mock_scheduler = MagicMock()
        mock_scheduler.metrics = {"reconcile_count": 0, "error_count": 0}
        collector = FlowCollector(scheduler=mock_scheduler, blackboard=mock_bb, headhunter=hh)
        snap = await collector._build_snapshot()
        assert snap.headhunter_pending == 10
        assert snap.headhunter_gitlab_pending == 4
        assert snap.headhunter_github_pending == 6
        assert snap.headhunter_gitlab_breaker == "half_open"
        assert snap.headhunter_github_breaker == "open"

        mock_brain = MagicMock()
        mock_brain.agents = {"_headhunter": hh}
        mock_brain.get_staleness_guard_metrics = MagicMock(return_value=[])
        mock_brain.get_active_subscription_count = MagicMock(return_value=0)
        mock_brain.count_global_wip = AsyncMock(return_value=2)

        driver = HeadhunterTelemetryProtocolDriver()
        code, body = await driver.get_flow_metrics(mock_bb, mock_brain)
        assert code == 200
        assert body["headhunter_pending"] == 10
        assert body["headhunter_gitlab_pending"] == 4
        assert body["headhunter_github_pending"] == 6
        assert body["headhunter_gitlab_breaker"] == "half_open"
        assert body["headhunter_github_breaker"] == "open"

    def test_t15c_legacy_flow_snapshot_deserialization_and_downsampler_worst_case_breaker(self):
        """Given legacy pre-deploy Redis FlowSnapshot JSON missing new fields and snapshots with
        mixed breaker states across a 300s bucket
        When deserialized and aggregated via _downsample_snapshots()
        Then legacy payloads default safely, pending gauges average via round(sum/n),
        and breaker strings preserve worst-case open > half_open > closed."""
        from types import SimpleNamespace
        from src.state.blackboard import BlackboardState

        legacy = FlowSnapshot.model_validate({"timestamp": 310.0, "headhunter_pending": 5})
        assert legacy.headhunter_gitlab_pending == 0
        assert legacy.headhunter_github_pending == 0
        assert legacy.headhunter_gitlab_breaker == "closed"
        assert legacy.headhunter_github_breaker == "closed"

        # Legacy object missing attributes altogether (simulates getattr fallback requirement)
        legacy_obj = SimpleNamespace(
            timestamp=305.0,
            queue_depth=0,
            active_events=0,
            deferred_events=0,
            waiting_approval_events=0,
            headhunter_pending=2,
            aligner_pending=0,
            jenkins_pending=0,
            jenkins_breaker_open=False,
            jenkins_view_unhealthy=False,
            wip_used=0,
            wip_cap=20,
            wip_utilization_pct=0.0,
            wip_available=20,
            busy_agents=0,
            idle_agents=0,
            active_subscriptions=0,
            avg_event_age_sec=0.0,
            avg_reconcile_ms=0.0,
            avg_spawn_latency_sec=0.0,
            dispatch_success_rate_pct=100.0,
            tpm_used=0,
            tpm_limit=0,
            tpm_utilization_pct=0.0,
            reconcile_count_delta=0,
            error_count_delta=0,
            quota_throttle_delta=0,
            token_input_delta=0,
            token_output_delta=0,
            token_thinking_delta=0,
            token_cached_delta=0,
            token_tool_use_delta=0,
            token_total_delta=0,
            token_calls_delta=0,
            dispatch_total=0,
            dispatch_infra_fails=0,
            dispatch_circuit_breaks=0,
            token_total_cumulative=0,
        )
        s1 = FlowSnapshot(
            timestamp=310.0,
            headhunter_pending=3,
            headhunter_gitlab_pending=2,
            headhunter_github_pending=1,
            headhunter_gitlab_breaker="closed",
            headhunter_github_breaker="half_open",
        )
        s2 = FlowSnapshot(
            timestamp=320.0,
            headhunter_pending=7,
            headhunter_gitlab_pending=4,
            headhunter_github_pending=5,
            headhunter_gitlab_breaker="half_open",
            headhunter_github_breaker="open",
        )

        bb = BlackboardState.__new__(BlackboardState)
        buckets = bb._downsample_snapshots([legacy_obj, s1, s2], bucket_seconds=300)
        assert len(buckets) == 1
        agg = buckets[0]
        assert agg.headhunter_gitlab_pending == round((0 + 2 + 4) / 3)
        assert agg.headhunter_github_pending == round((0 + 1 + 5) / 3)
        assert agg.headhunter_gitlab_breaker == "half_open"
        assert agg.headhunter_github_breaker == "open"
