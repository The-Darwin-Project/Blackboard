# tests/test_downsample_tokens.py
"""Verify _downsample_snapshots preserves token fields and WIP fields."""
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
    assert result[0].token_input_delta == 30
    assert result[0].token_output_delta == 15
    assert result[0].token_total_delta == 45
    assert result[0].token_calls_delta == 3


def test_downsample_preserves_token_cumulative():
    """Cumulative fields aggregate via max()."""
    bb = BlackboardState.__new__(BlackboardState)
    snapshots = [
        _snap(100, token_total_cumulative=1000),
        _snap(200, token_total_cumulative=1500),
    ]
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
    assert result[0].wip_used == 12  # round((10+14)/2)
    assert result[0].wip_cap == 20
    assert result[0].wip_utilization_pct == 60.0
    assert result[0].wip_available == 8
    assert result[0].waiting_approval_events == 3
    assert result[0].headhunter_pending == 4


def test_downsample_single_snapshot():
    """Single snapshot passes through unchanged."""
    bb = BlackboardState.__new__(BlackboardState)
    snapshots = [_snap(100, token_total_delta=42, wip_used=5)]
    result = bb._downsample_snapshots(snapshots, bucket_seconds=600)
    assert len(result) == 1
    assert result[0].token_total_delta == 42
    assert result[0].wip_used == 5


def test_downsample_empty():
    bb = BlackboardState.__new__(BlackboardState)
    assert bb._downsample_snapshots([], bucket_seconds=600) == []


def test_downsample_covers_all_flow_snapshot_fields():
    """Every non-timestamp FlowSnapshot field must appear in _downsample_snapshots output."""
    bb = BlackboardState.__new__(BlackboardState)
    snap = FlowSnapshot(timestamp=100, token_total_delta=1, wip_used=1)
    result = bb._downsample_snapshots([snap], bucket_seconds=600)
    result_fields = set(result[0].model_dump().keys())
    model_fields = set(FlowSnapshot.model_fields.keys())
    assert result_fields == model_fields, f"Missing: {model_fields - result_fields}"
