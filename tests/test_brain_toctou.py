# tests/test_brain_toctou.py
# @ai-rules:
# 1. [Constraint]: AST structural test — no runtime mocking, no Redis.
# 2. [Pattern]: Validates code ordering invariant survives refactors.
# 3. [Gotcha]: Visitor uses depth counter (not boolean) to handle nested AsyncFunctionDef.
# 4. [Gotcha]: Skips nested function defs (on_progress, on_huddle) — only counts
#    top-level calls within the target method body.
"""AST structural guard: _release_task_state ordering invariant.

Complements the behavioral tests in test_task_lifecycle_ordering.py.
These tests read brain.py source and verify that _release_task_state
appears before bookkeeping awaits in the AST, catching regressions
that refactors might introduce even when mocks pass.
"""
import ast
from pathlib import Path

import pytest


def _find_brain_path() -> Path:
    """Locate brain.py, skip if not found."""
    candidates = [
        Path("src/agents/brain.py"),
        Path("BlackBoard/src/agents/brain.py"),
    ]
    for p in candidates:
        if p.exists():
            return p
    pytest.skip("brain.py not found in expected locations")


class _TopLevelCallVisitor(ast.NodeVisitor):
    """Collect calls at the top level of a target async function.

    Uses a depth counter to skip calls inside nested function defs
    (on_progress, on_huddle, etc.) which contain their own
    _append_and_broadcast calls that are not completion-path calls.
    """

    def __init__(self, target_name: str):
        self.target_name = target_name
        self._depth = 0
        self.append_calls: list[int] = []
        self.release_calls: list[int] = []
        self.mark_calls: list[int] = []
        self.stamp_calls: list[int] = []

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node.name == self.target_name and self._depth == 0:
            self._depth = 1
            self.generic_visit(node)
            self._depth = 0
        elif self._depth > 0:
            self._depth += 1
            self.generic_visit(node)
            self._depth -= 1
        else:
            self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if self._depth > 0:
            self._depth += 1
            self.generic_visit(node)
            self._depth -= 1
        else:
            self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if self._depth == 1:
            if isinstance(node.func, ast.Attribute):
                name = node.func.attr
                if name == "_append_and_broadcast":
                    self.append_calls.append(node.lineno)
                elif name == "_release_task_state":
                    self.release_calls.append(node.lineno)
                elif name == "mark_turn_status":
                    self.mark_calls.append(node.lineno)
                elif name == "stamp_event":
                    self.stamp_calls.append(node.lineno)
        self.generic_visit(node)


def _assert_release_before_bookkeeping(
    release_calls: list[int],
    mark_calls: list[int],
    stamp_calls: list[int],
    after_line: int,
    context: str,
) -> None:
    """Assert every _release_task_state after `after_line` precedes bookkeeping."""
    releases_after = [l for l in release_calls if l > after_line]
    assert releases_after, f"No _release_task_state after line {after_line} in {context}"
    release_line = releases_after[0]

    marks_after = [l for l in mark_calls if l > after_line]
    stamps_after = [l for l in stamp_calls if l > after_line]

    for mark_line in marks_after:
        assert release_line < mark_line, (
            f"{context}: _release_task_state (L{release_line}) must precede "
            f"mark_turn_status (L{mark_line})"
        )

    for stamp_line in stamps_after:
        assert release_line < stamp_line, (
            f"{context}: _release_task_state (L{release_line}) must precede "
            f"stamp_event (L{stamp_line})"
        )


def test_run_agent_task_release_ordering():
    """_release_task_state precedes bookkeeping in _run_agent_task (top-level calls only)."""
    brain_path = _find_brain_path()
    tree = ast.parse(brain_path.read_text())

    visitor = _TopLevelCallVisitor("_run_agent_task")
    visitor.visit(tree)

    assert visitor.append_calls, "Expected _append_and_broadcast calls in _run_agent_task"
    assert visitor.release_calls, "Expected _release_task_state calls in _run_agent_task"

    for append_line in visitor.append_calls:
        _assert_release_before_bookkeeping(
            visitor.release_calls,
            visitor.mark_calls,
            visitor.stamp_calls,
            after_line=append_line,
            context=f"_run_agent_task (append at L{append_line})",
        )


def test_handle_wake_task_release_ordering():
    """_release_task_state precedes bookkeeping in handle_wake_task."""
    brain_path = _find_brain_path()
    tree = ast.parse(brain_path.read_text())

    visitor = _TopLevelCallVisitor("handle_wake_task")
    visitor.visit(tree)

    assert visitor.release_calls, "Expected _release_task_state calls in handle_wake_task"
    assert visitor.stamp_calls, "Expected stamp_event calls in handle_wake_task"

    success_stamp = visitor.stamp_calls[0]
    preceding_appends = [l for l in visitor.append_calls if l < success_stamp]
    assert preceding_appends, "Expected _append_and_broadcast before stamp_event"

    _assert_release_before_bookkeeping(
        visitor.release_calls,
        visitor.mark_calls,
        visitor.stamp_calls,
        after_line=preceding_appends[-1],
        context="handle_wake_task",
    )
