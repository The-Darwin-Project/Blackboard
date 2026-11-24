# BlackBoard/tests/test_downsample_tokens.py
# @ai-rules:
# 1. [Pattern]: Unit tests for BlackboardState._downsample_snapshots bucket aggregation invariants.
# 2. [Constraint]: Verifies gauges (avg), setpoints/counters (max), deltas (sum), and full FlowSnapshot field coverage.
"""Verify _downsample_snapshots preserves token fields, TPM gauges/setpoint, and WIP fields."""
from src.models import FlowSnapshot
from src.state.blackboard import BlackboardState


def _snap(ts: float, **kwargs) -> FlowSnapshot:
    return FlowSnapshot(timestamp=ts, **kwargs)


def test_downsample_preserves_token_deltas():
    """Delta fields aggregate via sum()."""
    bb = BlackboardState.__new__(BlackboardState)
    snapshots = [
        _snap(100, token_input_delta=10, token_output_delta=5, token_total_delta=15, token_calls_delta=1),
        _snap(200, token_input_delta=20, token_output_delta=10, token_total_delta=30, token_calls_delta=2),
    ]
    result = bb._downsample_snapshots(snapshots, bucket_seconds=600)
    assert len(result) == 1
    assert (result[0].token_input_delta, result[0].token_output_delta) == (30, 15)
    assert (result[0].token_total_delta, result[0].token_calls_delta) == (45, 3)


def test_downsample_preserves_token_cumulative():
    """Cumulative fields aggregate via max()."""
    bb = BlackboardState.__new__(BlackboardState)
    snapshots = [_snap(100, token_total_cumulative=1000), _snap(200, token_total_cumulative=1500)]
    result = bb._downsample_snapshots(snapshots, bucket_seconds=600)
    assert result[0].token_total_cumulative == 1500


def test_downsample_preserves_wip_fields():
    """Pre-existing missing WIP fields aggregate via round(sum/n)."""
    bb = BlackboardState.__new__(BlackboardState)
    snapshots = [
        _snap(100, wip_used=10, wip_cap=20, wip_utilization_pct=50.0, wip_available=10,
              waiting_approval_events=2, headhunter_pending=3),
        _snap(200, wip_used=14, wip_cap=20, wip_utilization_pct=70.0, wip_available=6,
              waiting_approval_events=4, headhunter_pending=5),
    ]
    result = bb._downsample_snapshots(snapshots, bucket_seconds=600)
    assert (result[0].wip_used, result[0].wip_cap, result[0].wip_utilization_pct) == (12, 20, 60.0)
    assert (result[0].wip_available, result[0].waiting_approval_events, result[0].headhunter_pending) == (8, 3, 4)


def test_downsample_single_snapshot():
    """Single snapshot passes through unchanged."""
    bb = BlackboardState.__new__(BlackboardState)
    result = bb._downsample_snapshots([_snap(100, token_total_delta=42, wip_used=5)], bucket_seconds=600)
    assert len(result) == 1
    assert (result[0].token_total_delta, result[0].wip_used) == (42, 5)


def test_downsample_empty():
    bb = BlackboardState.__new__(BlackboardState)
    assert bb._downsample_snapshots([], bucket_seconds=600) == []


def test_downsample_preserves_quota_shedding_cumulative_counters():
    """Quota shedding counters aggregate via max() across the bucket."""
    bb = BlackboardState.__new__(BlackboardState)
    snapshots = [
        _snap(100, quota_shed_tier1_total=1, quota_shed_tier2_total=2),
        _snap(200, quota_shed_tier1_total=9, quota_shed_tier2_total=6),
        _snap(250, quota_shed_tier1_total=4, quota_shed_tier2_total=3),
    ]
    result = bb._downsample_snapshots(snapshots, bucket_seconds=300)
    assert len(result) == 1
    assert (result[0].quota_shed_tier1_total, result[0].quota_shed_tier2_total) == (9, 6)


def test_downsample_preserves_tpm_gauges_and_throttle_delta():
    """TPM gauges average, tpm_limit takes max() against cold-start 0, and quota_throttle_delta sums."""
    bb = BlackboardState.__new__(BlackboardState)
    snapshots = [
        _snap(100, tpm_used=300_000, tpm_limit=0, tpm_utilization_pct=10.0, quota_throttle_delta=1),
        _snap(150, tpm_used=600_000, tpm_limit=3_000_000, tpm_utilization_pct=20.0, quota_throttle_delta=0),
        _snap(200, tpm_used=1_200_000, tpm_limit=3_000_000, tpm_utilization_pct=40.0, quota_throttle_delta=2),
    ]
    result = bb._downsample_snapshots(snapshots, bucket_seconds=300)
    assert len(result) == 1
    assert result[0].tpm_used == 700_000
    assert result[0].tpm_limit == 3_000_000
    assert result[0].tpm_utilization_pct == 23.3
    assert result[0].quota_throttle_delta == 3


def test_downsample_covers_all_flow_snapshot_fields():
    """Every non-timestamp FlowSnapshot field must appear in _downsample_snapshots output."""
    bb = BlackboardState.__new__(BlackboardState)
    snap = FlowSnapshot(timestamp=100, token_total_delta=1, wip_used=1)
    result = bb._downsample_snapshots([snap], bucket_seconds=600)
    result_fields = set(result[0].model_dump().keys())
    model_fields = set(FlowSnapshot.model_fields.keys())
    assert result_fields == model_fields, f"Missing: {model_fields - result_fields}"


def test_t5_downsample_sums_brain_token_deltas_across_five_snapshots():
    """
    Scenario T-5:
    Given 5 FlowSnapshots in one bucket with varying brain_token_input_delta and brain_token_cached_delta
    When _downsample_snapshots() aggregates the bucket
    Then both brain token delta fields are summed (not averaged or maxed) and all FlowSnapshot fields are covered.
    """
    assert "brain_token_input_delta" in FlowSnapshot.model_fields, (
        "FlowSnapshot missing brain_token_input_delta field"
    )
    assert "brain_token_cached_delta" in FlowSnapshot.model_fields, (
        "FlowSnapshot missing brain_token_cached_delta field"
    )

    bb = BlackboardState.__new__(BlackboardState)
    # 5 snapshots within one 300s bucket (t=300..599):
    # brain_token_input_delta:  [100, 200, 300, 400, 500] -> sum=1500 (avg=300, max=500)
    # brain_token_cached_delta: [ 80, 150, 270, 350, 450] -> sum=1300 (avg=260, max=450)
    snapshots = [
        _snap(300, token_input_delta=150, token_cached_delta=80,
              brain_token_input_delta=100, brain_token_cached_delta=80),
        _snap(360, token_input_delta=250, token_cached_delta=150,
              brain_token_input_delta=200, brain_token_cached_delta=150),
        _snap(420, token_input_delta=350, token_cached_delta=270,
              brain_token_input_delta=300, brain_token_cached_delta=270),
        _snap(480, token_input_delta=450, token_cached_delta=350,
              brain_token_input_delta=400, brain_token_cached_delta=350),
        _snap(540, token_input_delta=550, token_cached_delta=450,
              brain_token_input_delta=500, brain_token_cached_delta=450),
    ]

    result = bb._downsample_snapshots(snapshots, bucket_seconds=300)
    assert len(result) == 1
    assert result[0].brain_token_input_delta == 1500
    assert result[0].brain_token_cached_delta == 1300
    assert result[0].token_input_delta == 1750
    assert result[0].token_cached_delta == 1300
    assert set(result[0].model_dump().keys()) == set(FlowSnapshot.model_fields.keys())
