# BlackBoard/tests/test_flow_collector.py
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
