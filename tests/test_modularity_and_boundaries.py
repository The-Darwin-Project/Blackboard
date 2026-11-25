# BlackBoard/tests/test_modularity_and_boundaries.py
# @ai-rules:
# 1. [Constraint]: Section 7c fitness gates — modularity <= 100 lines, @ai-rules headers, and hexagonal AST boundaries.
# 2. [Pattern]: AST-scans module imports without importing unimplemented runtime modules unless checking existence.
"""Section 7c fitness gates: <=100L modularity, @ai-rules headers, and hexagonal AST import boundaries."""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent

LINE_BUDGET_FILES = [
    "src/state/wip_meta.py",
    "src/agents/llm/quota_registry.py",
    "src/agents/llm/token_attribution.py",
    "src/agents/llm/raw_genai_meter.py",
    "src/agents/sidecar_usage.py",
    "gemini-sidecar/usage-tracker.js",
    "src/agents/event_namer.py",
    "src/agents/llm/__init__.py",
]


def _imported_modules(py_path: Path, *, top_level_only: bool = False) -> set[str]:
    """Extract imported module paths from a Python file using AST."""
    tree = ast.parse(py_path.read_text(), filename=str(py_path))
    imports: set[str] = set()
    nodes = tree.body if top_level_only else ast.walk(tree)
    for node in nodes:
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            prefix = "." * node.level
            imports.add(f"{prefix}{mod}")
            for alias in node.names:
                imports.add(f"{prefix}{mod}.{alias.name}" if mod else f"{prefix}{alias.name}")
    return imports


def _resolve_relative_import(py_path: Path, raw_imp: str) -> str:
    """Resolve leading-dot relative imports to dotted src.* paths."""
    if not raw_imp.startswith("."):
        return raw_imp
    dots = len(raw_imp) - len(raw_imp.lstrip("."))
    rest = raw_imp[dots:]
    rel_parts = py_path.relative_to(REPO_ROOT).with_suffix("").parts
    pkg_parts = rel_parts[:-1]
    up = max(0, dots - 1)
    base_parts = pkg_parts[: len(pkg_parts) - up] if up else pkg_parts
    return ".".join([*base_parts, *([rest] if rest else [])])


class TestModularityAndHeaders:
    """Section 7c Gate 1: All 8 target files exist, declare path + @ai-rules, and are strictly <= 100 lines."""

    @pytest.mark.parametrize("rel_path", LINE_BUDGET_FILES)
    def test_file_exists_has_header_and_within_100_lines(self, rel_path: str):
        target = REPO_ROOT / rel_path
        assert target.exists(), f"Missing required modular file: {rel_path}"
        lines = target.read_text().splitlines()
        assert len(lines) <= 100, f"{rel_path} has {len(lines)} lines (must be <= 100)"
        head = "\n".join(lines[:10])
        assert "@ai-rules:" in head, f"{rel_path} missing @ai-rules: header"
        assert Path(rel_path).name in head or rel_path in head, (
            f"{rel_path} missing relative path header comment"
        )

    def test_cli_executor_under_1000_lines(self):
        target = REPO_ROOT / "gemini-sidecar" / "cli-executor.js"
        assert target.exists(), "Missing gemini-sidecar/cli-executor.js"
        line_count = len(target.read_text().splitlines())
        assert line_count < 1000, f"gemini-sidecar/cli-executor.js has {line_count} lines (must be < 1000)"


class TestHexagonalBoundaries:
    """Section 7c Gate 2: AST import boundaries across scheduling, state, observers, and sidecar_usage."""

    def test_scheduling_has_no_redis_llm_or_brain_imports(self):
        sched_dir = REPO_ROOT / "src" / "scheduling"
        forbidden = ("redis", "google", "anthropic", "src.agents.brain", "src.agents.llm")
        for py_file in sorted(sched_dir.glob("*.py")):
            for raw in _imported_modules(py_file):
                resolved = _resolve_relative_import(py_file, raw)
                for bad in forbidden:
                    assert resolved != bad and not resolved.startswith(f"{bad}."), (
                        f"Boundary violation in {py_file.name}: imports {resolved!r} ({raw!r})"
                    )

    def test_state_ports_and_wip_meta_have_no_agents_imports(self):
        for rel in ("src/state/ports.py", "src/state/wip_meta.py"):
            py_file = REPO_ROOT / rel
            assert py_file.exists(), f"Missing {rel}"
            for raw in _imported_modules(py_file):
                resolved = _resolve_relative_import(py_file, raw)
                assert not resolved.startswith("src.agents"), (
                    f"Boundary violation in {rel}: imports {resolved!r} ({raw!r})"
                )

    def test_flow_collector_has_no_brain_or_llm_sdk_imports(self):
        py_file = REPO_ROOT / "src" / "observers" / "flow_collector.py"
        forbidden = ("src.agents.brain", "google", "anthropic")
        for raw in _imported_modules(py_file):
            resolved = _resolve_relative_import(py_file, raw)
            for bad in forbidden:
                assert resolved != bad and not resolved.startswith(f"{bad}."), (
                    f"Boundary violation in flow_collector.py: imports {resolved!r} ({raw!r})"
                )

    def test_sidecar_usage_has_no_brain_import_anywhere(self):
        py_file = REPO_ROOT / "src" / "agents" / "sidecar_usage.py"
        assert py_file.exists(), "Missing src/agents/sidecar_usage.py"
        for raw in _imported_modules(py_file, top_level_only=False):
            resolved = _resolve_relative_import(py_file, raw)
            assert resolved != "src.agents.brain" and not resolved.startswith("src.agents.brain."), (
                f"Circular import hazard: sidecar_usage.py imports {resolved!r} ({raw!r})"
            )
