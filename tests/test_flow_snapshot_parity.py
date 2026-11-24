# BlackBoard/tests/test_flow_snapshot_parity.py
# @ai-rules:
# 1. [Constraint]: Anchors Python<->TS FlowSnapshot AND FlowMetrics field name parity.
# 2. [Pattern]: Regex parses TS interface, Pydantic .model_fields for Python. Names only.
# 3. [Gotcha]: TS optional markers (?) are stripped before comparison -- presence check only.
"""
CI guard: ensures flow-related model field NAMES match between Python and TypeScript.
"""
from __future__ import annotations

import re
from pathlib import Path

from src.models import FlowSnapshot, FlowMetricsResponse

TS_TYPES_PATH = Path(__file__).parent.parent / "ui" / "src" / "api" / "types.ts"


def _parse_ts_interface_fields(interface_name: str) -> set[str]:
    """Extract field names from a TS interface (field_name: type pattern)."""
    content = TS_TYPES_PATH.read_text()
    match = re.search(
        rf"export\s+interface\s+{re.escape(interface_name)}\s*\{{(.+?)^\}}",
        content, re.DOTALL | re.MULTILINE,
    )
    assert match, f"Could not find 'export interface {interface_name}' in api/types.ts"
    return set(re.findall(r"^\s+(\w+)\s*\??:", match.group(1), re.MULTILINE))


def test_flow_snapshot_fields_match_typescript():
    """Ensure Python FlowSnapshot field NAMES match TS FlowSnapshot interface."""
    py_fields = set(FlowSnapshot.model_fields.keys())
    ts_fields = _parse_ts_interface_fields("FlowSnapshot")
    assert py_fields == ts_fields, f"Drift: py_only={py_fields - ts_fields}, ts_only={ts_fields - py_fields}"


def test_flow_metrics_fields_match_typescript():
    """Ensure Python FlowMetricsResponse field NAMES match TS FlowMetrics interface."""
    py_fields = set(FlowMetricsResponse.model_fields.keys())
    ts_fields = _parse_ts_interface_fields("FlowMetrics")
    assert py_fields == ts_fields, f"Drift: py_only={py_fields - ts_fields}, ts_only={ts_fields - py_fields}"


def _parse_ts_optional_fields(interface_name: str) -> set[str]:
    """Extract field names declared optional (`field?: type`) in a TS interface."""
    content = TS_TYPES_PATH.read_text()
    match = re.search(
        rf"export\s+interface\s+{re.escape(interface_name)}\s*\{{(.+?)^\}}",
        content, re.DOTALL | re.MULTILINE,
    )
    assert match, f"Could not find 'export interface {interface_name}' in api/types.ts"
    return set(re.findall(r"^\s+(\w+)\s*\?:", match.group(1), re.MULTILINE))


def test_t6_flow_snapshot_declares_brain_cache_delta_fields_in_python_and_ts():
    """
    Scenario T-6a:
    Given updated FlowSnapshot model and TS FlowSnapshot interface
    When Python/TS contract parity is verified
    Then brain_token_input_delta and brain_token_cached_delta exist in both,
    default to 0 in Python (pre-rollout Redis compat), and are optional (?) in TypeScript.
    """
    required = {"brain_token_input_delta", "brain_token_cached_delta"}
    py_fields = set(FlowSnapshot.model_fields.keys())
    ts_fields = _parse_ts_interface_fields("FlowSnapshot")
    ts_optional = _parse_ts_optional_fields("FlowSnapshot")

    assert required <= py_fields, f"Python FlowSnapshot missing: {required - py_fields}"
    assert required <= ts_fields, f"TS FlowSnapshot missing: {required - ts_fields}"
    assert required <= ts_optional, f"TS FlowSnapshot fields must be optional (?): {required - ts_optional}"

    default_snap = FlowSnapshot(timestamp=1.0).model_dump()
    assert default_snap["brain_token_input_delta"] == 0
    assert default_snap["brain_token_cached_delta"] == 0


def test_t6_flow_metrics_declares_cache_hit_rate_fields_in_python_and_ts():
    """
    Scenario T-6b:
    Given updated FlowMetricsResponse model and TS FlowMetrics interface
    When Python/TS contract parity is verified
    Then token_input_60s, token_cached_60s, cache_hit_rate_pct, and brain_cache_hit_rate_pct
    exist in both, default to 0 / 0.0 in Python, and are optional (?) in TypeScript.
    """
    required = {
        "token_input_60s",
        "token_cached_60s",
        "cache_hit_rate_pct",
        "brain_cache_hit_rate_pct",
    }
    py_fields = set(FlowMetricsResponse.model_fields.keys())
    ts_fields = _parse_ts_interface_fields("FlowMetrics")
    ts_optional = _parse_ts_optional_fields("FlowMetrics")

    assert required <= py_fields, f"Python FlowMetricsResponse missing: {required - py_fields}"
    assert required <= ts_fields, f"TS FlowMetrics missing: {required - ts_fields}"
    assert required <= ts_optional, f"TS FlowMetrics fields must be optional (?): {required - ts_optional}"

    default_metrics = FlowMetricsResponse().model_dump()
    assert default_metrics["token_input_60s"] == 0
    assert default_metrics["token_cached_60s"] == 0
    assert default_metrics["cache_hit_rate_pct"] == 0.0
    assert default_metrics["brain_cache_hit_rate_pct"] == 0.0
