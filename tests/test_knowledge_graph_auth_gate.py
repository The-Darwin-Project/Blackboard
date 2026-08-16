# tests/test_knowledge_graph_auth_gate.py
# @ai-rules:
# 1. [Purpose]: Regression coverage for the HIGH finding fixed in ac4f086 -- the KG REST
#    API router was mounted unconditionally in main.py, exposing an unbounded JSONB
#    properties blob (LLM-extracted) with no auth gate.
# 2. [Constraint]: DEX_ENABLED is read once at src.main import time to decide whether
#    knowledge_graph_router is mounted -- monkeypatching src.auth.DEX_ENABLED after import
#    has no effect on the already-built route table. The "gated on" case therefore runs in
#    a subprocess with the env var set before interpreter start, rather than reloading
#    src.main in-process (which would re-run app-level side effects for every other test
#    sharing this session).
# 3. [Pattern]: The "gated off" (default) case is asserted directly against the real,
#    already-imported src.main.app -- this is the actual test-session default and the
#    common non-Dex deployment default, so it is the case most worth testing in-process.
"""Verifies knowledge_graph_router is only reachable when DEX_ENABLED=true."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parent.parent

KG_PATHS = [
    "/api/knowledge-graph/services",
    "/api/knowledge-graph/stats",
    "/api/knowledge-graph/services/service:darwin-brain",
]


class TestAuthGateDisabledByDefault:
    """DEX_ENABLED=false (test session default) -- router must not be mounted at all."""

    @pytest.mark.parametrize("path", KG_PATHS)
    def test_kg_routes_404_when_dex_disabled(self, path):
        from src.main import app

        client = TestClient(app)
        resp = client.get(path)
        assert resp.status_code == 404

    def test_router_absent_from_route_table(self):
        from src.main import app

        kg_routes = [r for r in app.routes if getattr(r, "path", "").startswith("/api/knowledge-graph")]
        assert kg_routes == []


class TestAuthGateEnabled:
    """DEX_ENABLED=true -- router must be mounted and reachable (still fail-open on no store)."""

    def test_kg_routes_reachable_when_dex_enabled(self):
        script = (
            "from fastapi.testclient import TestClient\n"
            "from src.main import app\n"
            "c = TestClient(app)\n"
            "codes = [c.get(p).status_code for p in %r]\n"
            "print(codes)\n"
        ) % KG_PATHS

        result = subprocess.run(
            [sys.executable, "-c", script],
            env={"DEX_ENABLED": "true", "PATH": "/usr/bin:/bin"},
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=60,
        )
        assert result.returncode == 0, result.stderr
        codes = eval(result.stdout.strip().splitlines()[-1])
        # Fail-open (no store configured) -> 200 for services/stats, 404 for the
        # specific-entity lookup (no such entity) -- none of these are 404-because-
        # unmounted, unlike the disabled case above.
        assert codes == [200, 200, 404]
