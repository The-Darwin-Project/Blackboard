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
