# BlackBoard/tests/test_prefix_builder.py
# @ai-rules:
# 1. [Constraint]: Executable ATDD specifications for Step 7 (VMER-2450) — T-21, T-22, T-23, T-24 + Seam Guards.
# 2. [Pattern]: Follows Dave Farley's 4-layer ATDD model (Domain Intent, DSL, Protocol Driver, SUT).
# 3. [Boundary]: Imports of new modules (prefix_builder, event_state_tail) stay inside test methods so pytest
#    collects cleanly and proves RED per scenario before implementation.
"""Executable specifications for static preamble locking (Step 7: T-21..T-24 & Seam Guards).

Dave Farley 4-Layer ATDD Model:
  Layer 1 (Domain Intent): Given/When/Then scenarios for boot ordering, atomic static preamble
      (canonical sorted wire_tools + versioned Global Core SI), SHA-8 observability, and hexagonal seams.
  Layer 2 (DSL): Event, Brain, and fake-stream synthesis helpers.
  Layer 3 (Protocol Driver): Calls to prefix_builder, event_state_tail, Brain._build_system_prompt,
      Brain._process_with_llm, and AST inspection of src/main.py & new modules.
  Layer 4 (SUT): src/agents/prefix_builder.py, src/agents/event_state_tail.py, src/agents/brain.py,
      src/agents/brain_skills/always/02-safety.md, src/main.py.
"""
from __future__ import annotations

import ast
import asyncio
import copy
import inspect
import json
import logging
import re
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.brain import BRAIN_PREFILL_MODEL, Brain, _QuotaShedState
from src.agents.brain_skill_loader import BrainSkillLoader
from src.agents.llm.types import BRAIN_TOOL_SCHEMAS
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "src" / "agents" / "brain_skills"


# ---------------------------------------------------------------------------
# Layer 2: DSL Helpers
# ---------------------------------------------------------------------------

def _make_chunk(text: str = "ok", function_call=None, raw_parts=None, done: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        text=text,
        is_thought=False,
        function_call=function_call,
        raw_parts=raw_parts or [],
        grounding_metadata=None,
        usage=None,
        done=done,
    )


async def _stream_once(chunks: list[SimpleNamespace]):
    for chunk in chunks:
        yield chunk


def _make_event(
    event_id: str,
    *,
    source: str = "aligner",
    brain_phase: str = "triage",
    unread_notes: int = 0,
    gitlab_context: dict | None = None,
    conversation: list[ConversationTurn] | None = None,
) -> EventDocument:
    evidence = EventEvidence(
        display_text=f"Evidence for {event_id}",
        source_type=source,
        domain="complicated",
        severity="warning",
        gitlab_context=gitlab_context,
    )
    return EventDocument(
        id=event_id,
        source=source,
        service="payments",
        status=EventStatus.ACTIVE,
        brain_phase=brain_phase,
        unread_notes=unread_notes,
        event=EventInput(reason=f"Reason for {event_id}", evidence=evidence, timeDate="2026-01-01T00:00:00Z"),
        conversation=conversation or [],
    )


def _make_real_brain_for_preamble(event_lookup: dict[str, EventDocument]) -> tuple[Brain, list[dict]]:
    """Build a real Brain with real BrainSkillLoader and a recording adapter stub."""
    bb = MagicMock()
    bb.get_event = AsyncMock(side_effect=lambda eid: event_lookup.get(eid))
    bb.get_service = AsyncMock(return_value=None)
    bb.get_active_events = AsyncMock(return_value=[])
    bb.get_recent_closed_for_service = AsyncMock(return_value=[])
    bb.get_journal = AsyncMock(return_value=[])
    bb.append_turn = AsyncMock(return_value=1)
    bb.mark_turn_status = AsyncMock()
    bb.stamp_event = AsyncMock()
    bb.redis = MagicMock()
    bb.redis.get = AsyncMock(return_value=None)
    bb.redis.incr = AsyncMock()

    brain = Brain(blackboard=bb, agents={})
    brain._get_journal_cached = AsyncMock(return_value=[])
    brain._check_graph_edges = AsyncMock(return_value=False)
    brain._broadcast = AsyncMock()
    brain._append_and_broadcast = AsyncMock(return_value=1)
    brain._next_turn_number = AsyncMock(return_value=1)
    brain._is_event_closed = AsyncMock(return_value=False)
    brain._emit_executive_pulse = AsyncMock()
    brain._emit_thinking_pulse = AsyncMock()
    brain._execute_function_call = AsyncMock(return_value=True)
    brain._memory_reflex_enabled = False
    brain._search_enabled = False

    captured_calls: list[dict] = []

    def _capture_stream(**kwargs):
        captured_calls.append(copy.deepcopy(kwargs))
        fc = SimpleNamespace(name="lookup_service", args={"service_name": "payments"})
        return _stream_once([
            _make_chunk(
                text="",
                function_call=fc,
                raw_parts=[{"functionCall": {"name": "lookup_service", "args": {"service_name": "payments"}}}],
            )
        ])

    adapter = MagicMock()
    adapter.generate_stream = MagicMock(side_effect=_capture_stream)
    adapter.set_search_enabled = MagicMock()
    brain._adapter = adapter
    return brain, captured_calls


def _assert_forbidden_imports(file_path: Path, forbidden_prefixes: tuple[str, ...]) -> None:
    tree = ast.parse(file_path.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING":
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Import):
                for alias in child.names:
                    for pref in forbidden_prefixes:
                        assert not alias.name.startswith(pref), (
                            f"{file_path.name} imports forbidden module {alias.name!r}"
                        )
            elif isinstance(child, ast.ImportFrom):
                mod = child.module or ""
                if child.level > 0:
                    # Relative import inside src/agents/*
                    for forbidden_rel in ("brain", "llm", "state"):
                        assert not (mod == forbidden_rel or mod.startswith(f"{forbidden_rel}.")), (
                            f"{file_path.name} uses forbidden relative import from .{mod}"
                        )
                for pref in forbidden_prefixes:
                    assert not mod.startswith(pref), (
                        f"{file_path.name} imports from forbidden module {mod!r}"
                    )


# ---------------------------------------------------------------------------
# Layer 1 & 3: T-21 — Boot Ordering & Brain FS Generated Map Parity
# ---------------------------------------------------------------------------

class TestT21BootOrderAndBrainLoaderMap:
    """T-21: main.py lifespan runs set_incident_options before brain.start_event_loop,
    and Brain initializes BrainSkillLoader with include_generated_map=True."""

    def test_main_lifespan_calls_set_incident_options_before_brain_start_event_loop(self):
        main_path = REPO_ROOT / "src" / "main.py"
        tree = ast.parse(main_path.read_text(encoding="utf-8"))

        lifespan_fn = next(
            (n for n in tree.body if isinstance(n, ast.AsyncFunctionDef) and n.name == "lifespan"),
            None,
        )
        assert lifespan_fn is not None, "lifespan async function not found in src/main.py"

        set_opts_lines: list[int] = []
        start_loop_lines: list[int] = []
        incident_adapter_assign_lines: list[int] = []

        for node in ast.walk(lifespan_fn):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "set_incident_options":
                    set_opts_lines.append(node.lineno)
                elif isinstance(node.func, ast.Attribute) and node.func.attr == "start_event_loop":
                    start_loop_lines.append(node.lineno)
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Attribute) and target.attr == "_incident_adapter":
                        incident_adapter_assign_lines.append(node.lineno)

        assert set_opts_lines, "set_incident_options() call not found in lifespan()"
        assert start_loop_lines, "brain.start_event_loop() call not found in lifespan()"
        assert incident_adapter_assign_lines, "brain._incident_adapter assignment must remain intact in lifespan()"
        assert min(set_opts_lines) < min(start_loop_lines), (
            f"set_incident_options (line {min(set_opts_lines)}) MUST execute before "
            f"brain.start_event_loop (line {min(start_loop_lines)}) so Jira enums are locked "
            "into BRAIN_TOOL_SCHEMAS before Brain caches wire_tools."
        )

    def test_brain_init_enables_generated_phase_tool_map_on_fs_fallback(self):
        bb = MagicMock()
        bb.redis = None
        brain = Brain(blackboard=bb, agents={})
        assert brain.skill_loader is not None
        assert brain.skill_loader.get_with_meta("always/phase-tool-map.md") is not None, (
            "Brain.__init__ must construct BrainSkillLoader(..., include_generated_map=True) "
            "so FS fallback includes always/phase-tool-map.md."
        )


# ---------------------------------------------------------------------------
# Layer 1 & 3: T-22 — Atomic Static Preamble (wire_tools + Global Core SI)
# ---------------------------------------------------------------------------

class TestT22AtomicStaticPreamble:
    """T-22: Canonical sorted wire_tools, byte-identical preamble across unrelated events,
    _inject_maintainer_enum removed, and safety rules + prefill updated."""

    def test_canonical_wire_tools_sorted_immutable_dynamic_length(self):
        from src.agents.prefix_builder import canonical_wire_tools

        reversed_input = list(reversed(BRAIN_TOOL_SCHEMAS))
        original_order = [t["name"] for t in reversed_input]

        wire = canonical_wire_tools(reversed_input)
        assert len(wire) == len(BRAIN_TOOL_SCHEMAS), "wire_tools must match dynamic len(BRAIN_TOOL_SCHEMAS)"
        assert [t["name"] for t in wire] == sorted(t["name"] for t in BRAIN_TOOL_SCHEMAS)
        assert [t["name"] for t in reversed_input] == original_order, "input list must not be mutated"
        assert wire == canonical_wire_tools(BRAIN_TOOL_SCHEMAS), "sorting must be order-independent"

    @pytest.mark.asyncio
    async def test_two_unrelated_events_produce_byte_identical_wire_tools_and_global_core_si(self):
        from src.agents.prefix_builder import canonical_wire_tools

        ev_a = _make_event(
            "evt-alpha-triage",
            source="aligner",
            brain_phase="triage",
            unread_notes=0,
            conversation=[
                ConversationTurn(turn=1, actor="aligner", action="alert", thoughts="Pod crashloop"),
            ],
        )
        ev_b = _make_event(
            "evt-beta-escalate",
            source="headhunter",
            brain_phase="escalate",
            unread_notes=2,
            gitlab_context={"maintainer": {"emails": ["alice@redhat.com", "bob@redhat.com"]}},
            conversation=[
                ConversationTurn(turn=1, actor="headhunter", action="alert", thoughts="MR failed"),
                ConversationTurn(turn=2, actor="brain", action="defer", thoughts="Waiting for CI: pipeline running"),
                ConversationTurn(turn=3, actor="developer", action="result", result="Pipeline still failing"),
            ],
        )

        brain, calls = _make_real_brain_for_preamble({ev_a.id: ev_a, ev_b.id: ev_b})
        brain._get_graph_recall = AsyncMock(
            side_effect=lambda ev: "## GRAPH RECALL MARKER" if ev.id == ev_b.id else None
        )
        brain._post_agent_recall = AsyncMock(return_value="## POST-AGENT RECALL\n- Secret pattern")
        brain._recall_lessons[ev_b.id] = [{"payload": {"title": "Lesson X", "pattern": "Avoid Y"}}]

        await brain._process_with_llm(ev_a.id, ev_a, is_defer_wake=False, iteration=0)
        await brain._process_with_llm(ev_b.id, ev_b, is_defer_wake=True, iteration=0)

        assert len(calls) == 2
        tools_a, si_a = calls[0]["tools"], calls[0]["system_prompt"]
        tools_b, si_b = calls[1]["tools"], calls[1]["system_prompt"]

        # 1. wire_tools are 100% byte-identical and match canonical sorted BRAIN_TOOL_SCHEMAS
        expected_wire = canonical_wire_tools(BRAIN_TOOL_SCHEMAS)
        assert json.dumps(tools_a) == json.dumps(tools_b), "wire_tools must be byte-identical across events"
        assert [t["name"] for t in tools_a] == [t["name"] for t in expected_wire]
        assert len(tools_a) == len(BRAIN_TOOL_SCHEMAS)
        # No maintainer enum mutation on notify_user_slack in wire_tools
        notify_b = next(t for t in tools_b if t["name"] == "notify_user_slack")
        assert "enum" not in notify_b["input_schema"]["properties"]["user_email"], (
            "wire_tools notify_user_slack must never be mutated with per-event maintainer enums"
        )

        # 2. Global Core system_prompt is 100% byte-identical with zero dynamic strings
        assert si_a == si_b, "Global Core system_prompt must be 100% byte-identical across unrelated events"
        for forbidden in (
            "evt-alpha-triage",
            "evt-beta-escalate",
            "## Current Event State",
            "## EVENT STATE",
            "DEFER WAKE-UP",
            "## POST-AGENT RECALL",
            "## RECALL",
            "## GRAPH RECALL MARKER",
            "alice@redhat.com",
        ):
            assert forbidden not in si_a, f"Dynamic string {forbidden!r} leaked into Global Core SI"
            assert forbidden not in si_b, f"Dynamic string {forbidden!r} leaked into Global Core SI"

        # 3. Iteration-0 unread sticky note notification turn is preserved (only tool reorder removed)
        notif_turns = [
            c.args[1] for c in brain._append_and_broadcast.await_args_list
            if c.args[0] == ev_b.id and getattr(c.args[1], "action", None) == "notification"
        ]
        assert len(notif_turns) == 1, "Iteration-0 sticky note notification turn must remain intact"

    def test_inject_maintainer_enum_removed_while_resolve_maintainer_enum_intact(self):
        assert not hasattr(Brain, "_inject_maintainer_enum"), (
            "Brain._inject_maintainer_enum must be removed atomically with its caller in Step 7"
        )
        assert hasattr(Brain, "_resolve_maintainer_enum"), (
            "Brain._resolve_maintainer_enum must remain intact for <event_state> hints"
        )

    def test_always_safety_rules_and_prefill_document_hierarchy_and_prow_guards(self):
        safety_path = SKILLS_DIR / "always" / "02-safety.md"
        lines = safety_path.read_text(encoding="utf-8").splitlines()
        assert len(lines) <= 50, f"always/02-safety.md must stay <= 50 lines (got {len(lines)})"

        text = "\n".join(lines)
        assert "<skill_overlay>" in text, "always/02-safety.md must define trust hierarchy for <skill_overlay>"
        assert "<event_state>" in text, "always/02-safety.md must define trust hierarchy for <event_state>"
        assert "/lgtm" in text and "/approve" in text, "always/02-safety.md must carry Prow merge-guard rules"
        assert "@darwin-project.io" in text, "always/02-safety.md must carry @darwin-project.io manual-approval rule"

        assert "<skill_overlay>" in BRAIN_PREFILL_MODEL, "BRAIN_PREFILL_MODEL must document <skill_overlay>"
        assert "<event_state>" in BRAIN_PREFILL_MODEL, "BRAIN_PREFILL_MODEL must document <event_state>"


# ---------------------------------------------------------------------------
# Layer 1 & 3: T-23 — Global Core Transitive Closure, Dedup & Cache Invalidation
# ---------------------------------------------------------------------------

class TestT23GlobalCoreClosureAndCacheInvalidation:
    """T-23: GLOBAL_CORE_EXTRA_PATHS, transitive requires: dedup, _skills_version/_corpus
    invalidation, and SimpleNamespace stub safety."""

    def test_global_core_extra_paths_constant(self):
        from src.agents.prefix_builder import GLOBAL_CORE_EXTRA_PATHS

        assert GLOBAL_CORE_EXTRA_PATHS == (
            "dispatch/execution-method.md",
            "coordination/quality-gate.md",
            "source/headhunter.md",
        )

    @pytest.mark.asyncio
    async def test_global_core_includes_transitive_requires_and_deduplicates_strictly(self):
        loader = BrainSkillLoader(str(SKILLS_DIR), include_generated_map=True)
        bb = MagicMock()
        bb.redis = None
        brain = Brain(blackboard=bb, agents={})
        brain._skill_loader = loader

        ev = _make_event("evt-closure", source="chat", brain_phase="triage")
        si = await brain._build_system_prompt(ev, ["always", "source", "dispatch"], context_flags={})

        section_ids = re.findall(r'<(?:rule|skill|protocol|context|navigation)\s+id="([^"]+)">', si)
        assert section_ids, "Expected wrapped skill sections in Global Core SI"
        assert len(section_ids) == len(set(section_ids)), (
            f"Duplicate skill paths in Global Core SI: "
            f"{[p for p in section_ids if section_ids.count(p) > 1]}"
        )
        for required_path in (
            "always/02-safety.md",
            "always/phase-tool-map.md",
            "dispatch/execution-method.md",
            "coordination/quality-gate.md",
            "source/headhunter.md",
            "context/architecture.md",
            "dispatch/deep-memory-fixes.md",
        ):
            assert required_path in section_ids, f"Missing Global Core path {required_path}"

        # Non-Global-Core phase/domain/gated skills must NOT leak into Global Core SI
        for excluded_path in (
            "domain/casual.md",
            "domain/complicated.md",
            "context/gitlab-environment.md",
            "gated/kargo-environment.md",
        ):
            assert excluded_path not in section_ids, f"Dynamic skill {excluded_path} must not be in Global Core SI"

    @pytest.mark.asyncio
    async def test_global_core_si_cache_invalidates_on_version_and_corpus_swap(self, tmp_path: Path):
        (tmp_path / "always").mkdir(parents=True)
        (tmp_path / "always" / "00-core.md").write_text("# Core V1", encoding="utf-8")

        loader = BrainSkillLoader(str(tmp_path))
        bb = MagicMock()
        bb.redis = None
        brain = Brain(blackboard=bb, agents={})
        brain._skill_loader = loader
        brain._skills_version = "ver-1"

        ev = _make_event("evt-cache")

        with patch.object(
            loader,
            "resolve_dependencies_with_paths",
            wraps=loader.resolve_dependencies_with_paths,
        ) as spy_resolve:
            si_v1_a = await brain._build_system_prompt(ev, ["always"], context_flags={})
            si_v1_b = await brain._build_system_prompt(ev, ["dispatch"], context_flags={})
            assert si_v1_a == si_v1_b
            assert "# Core V1" in si_v1_a
            assert spy_resolve.call_count == 1, "Second call with same version/corpus must hit SI cache"

            # 1. Swap corpus on FS reload (same _skills_version) -> MUST invalidate cache
            (tmp_path / "always" / "00-core.md").write_text("# Core V2 FS", encoding="utf-8")
            loader.reload()
            si_v2 = await brain._build_system_prompt(ev, ["always"], context_flags={})
            assert "# Core V2 FS" in si_v2
            assert "# Core V1" not in si_v2
            assert spy_resolve.call_count == 2, "Corpus swap (same _skills_version) must invalidate SI cache"

            # 2. Bump _skills_version WITHOUT swapping _corpus -> MUST independently invalidate cache
            brain._skills_version = "ver-2"
            si_v3 = await brain._build_system_prompt(ev, ["always"], context_flags={})
            assert "# Core V2 FS" in si_v3
            assert spy_resolve.call_count == 3, "_skills_version bump must invalidate SI cache independently"

    @pytest.mark.asyncio
    async def test_global_core_si_tolerates_simplenamespace_stubs_missing_version_and_corpus(self):
        loader = MagicMock(
            spec=["available_phases", "get_all_paths_for_phase", "resolve_dependencies_with_paths", "get_tag_type"]
        )
        loader.available_phases.return_value = ["always"]
        loader.get_all_paths_for_phase.return_value = ["always/00-id.md"]
        loader.resolve_dependencies_with_paths.return_value = [("always/00-id.md", "# Stub Core")]
        loader.get_tag_type.return_value = "rule"

        # SimpleNamespace stub deliberately omits _skills_version, _cached_global_core_si, and loader._corpus
        stub_brain = SimpleNamespace(_skill_loader=loader)
        ev = _make_event("evt-stub")

        si = await Brain._build_system_prompt(stub_brain, ev, ["triage"], context_flags=None)
        assert '<rule id="always/00-id.md">' in si
        assert "# Stub Core" in si


# ---------------------------------------------------------------------------
# Layer 1 & 3: T-24 — Prefix SHA-8 Digests, INFO Logging & QuotaShed Parity
# ---------------------------------------------------------------------------

class TestT24PrefixHashesLoggingAndQuotaShed:
    """T-24: compute_prefix_hashes(), INFO log fields on Brain LLM calls, and
    _QuotaShedState.adopt preserving server-side recall_pruned_turns without mutating wire_tools."""

    def test_compute_prefix_hashes_deterministic_canonical_and_sensitive(self):
        from src.agents.prefix_builder import compute_prefix_hashes

        tools_a = [{"name": "alpha", "description": "A", "input_schema": {"type": "object"}}]
        tools_a_reordered_keys = [{"input_schema": {"type": "object"}, "description": "A", "name": "alpha"}]
        tools_b = [{"name": "alpha", "description": "B", "input_schema": {"type": "object"}}]

        h1 = compute_prefix_hashes(tools_a, "SI body", "Header body")
        h2 = compute_prefix_hashes(tools_a_reordered_keys, "SI body", "Header body")
        assert set(h1.keys()) == {"tools_sha8", "si_sha8", "hdr_sha8"}
        for k, v in h1.items():
            assert re.fullmatch(r"[0-9a-f]{8}", v), f"{k} must be 8 lowercase hex chars, got {v!r}"
        assert h1 == h2, "Canonical JSON must ignore dict key order inside wire_tools"

        h_tools_diff = compute_prefix_hashes(tools_b, "SI body", "Header body")
        assert h_tools_diff["tools_sha8"] != h1["tools_sha8"]
        assert h_tools_diff["si_sha8"] == h1["si_sha8"]
        assert h_tools_diff["hdr_sha8"] == h1["hdr_sha8"]

        h_si_diff = compute_prefix_hashes(tools_a, "SI body!", "Header body")
        assert h_si_diff["si_sha8"] != h1["si_sha8"]
        assert h_si_diff["tools_sha8"] == h1["tools_sha8"]
        assert h_si_diff["hdr_sha8"] == h1["hdr_sha8"]

        h_hdr_diff = compute_prefix_hashes(tools_a, "SI body", "Header body!")
        assert h_hdr_diff["hdr_sha8"] != h1["hdr_sha8"]
        assert h_hdr_diff["tools_sha8"] == h1["tools_sha8"]
        assert h_hdr_diff["si_sha8"] == h1["si_sha8"]

    @pytest.mark.asyncio
    async def test_brain_llm_call_logs_prefix_hashes_and_metadata_at_info(self, caplog):
        from src.agents.prefix_builder import compute_prefix_hashes

        ev = _make_event(
            "evt-log-hashes",
            source="aligner",
            brain_phase="dispatch",
            conversation=[ConversationTurn(turn=1, actor="user", action="message", thoughts="status?")],
        )
        brain, calls = _make_real_brain_for_preamble({ev.id: ev})

        with caplog.at_level(logging.INFO):
            await brain._process_with_llm(ev.id, ev)

        assert len(calls) == 1
        captured_tools = calls[0]["tools"]
        captured_si = calls[0]["system_prompt"]
        captured_hdr = calls[0]["contents"][2]["parts"][0]["text"]
        expected = compute_prefix_hashes(captured_tools, captured_si, captured_hdr)

        info_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
        matching = [
            m for m in info_msgs
            if all(
                token in m
                for token in ("tools_sha8", "si_sha8", "hdr_sha8", "phase", "domain", "thinking_level", "turn_count")
            )
        ]
        assert matching, (
            "Expected INFO log containing tools_sha8, si_sha8, hdr_sha8, phase, domain, "
            f"thinking_level, turn_count. Saw INFO logs: {info_msgs}"
        )
        log_line = matching[0]
        assert expected["tools_sha8"] in log_line, f"tools_sha8 mismatch in {log_line!r}"
        assert expected["si_sha8"] in log_line, f"si_sha8 mismatch in {log_line!r}"
        assert re.search(r"hdr_sha8[=:\s]+[0-9a-f]{8}", log_line), f"hdr_sha8 missing 8-hex digest in {log_line!r}"

    def test_quota_shed_state_adopt_enables_server_side_recall_without_touching_wire_tools(self):
        from src.agents.prefix_builder import canonical_wire_tools

        wire_tools = canonical_wire_tools(BRAIN_TOOL_SCHEMAS)
        wire_snapshot = json.dumps(wire_tools)
        restricted_active = [t for t in BRAIN_TOOL_SCHEMAS if t["name"] != "recall_pruned_turns"]

        shed = _QuotaShedState(
            raw_contents=[{"role": "user", "parts": [{"text": "initial"}]}],
            active_tools=restricted_active,
            tail_budget=40_000,
            recall_enabled=False,
        )
        decayed_contents = [
            {
                "role": "user",
                "parts": [
                    {"text": "Event Header"},
                    {
                        "text": '<blackboard_evidence_reference turn="2" tool="run_bash" chars="15000">'
                                "Do NOT recall routinely</blackboard_evidence_reference>"
                    },
                ],
            }
        ]
        shed.adopt(decayed_contents)

        assert shed.recall_enabled is True
        assert "recall_pruned_turns" in {t["name"] for t in shed.active_tools}
        assert json.dumps(wire_tools) == wire_snapshot, "wire_tools must remain untouched"


# ---------------------------------------------------------------------------
# Hexagonal Seam Guards (Step 7)
# ---------------------------------------------------------------------------

class TestStep7HexagonalSeamGuards:
    """Seam guards: prefix_builder.py and event_state_tail.py <=100L, @ai-rules header,
    zero Redis/LLM/Brain imports, and format_event_state_tail returns <event_state> block."""

    def test_prefix_builder_seam_guard_line_limit_header_and_imports(self):
        path = REPO_ROOT / "src" / "agents" / "prefix_builder.py"
        assert path.is_file(), "src/agents/prefix_builder.py must exist"
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert len(lines) <= 100, f"src/agents/prefix_builder.py must be <= 100 lines (got {len(lines)})"
        assert "@ai-rules" in text, "src/agents/prefix_builder.py must carry an @ai-rules header"
        _assert_forbidden_imports(
            path,
            ("redis", "google", "anthropic", "src.agents.brain", "src.agents.llm", "src.state"),
        )

    def test_event_state_tail_seam_guard_line_limit_header_imports_and_fencing(self):
        path = REPO_ROOT / "src" / "agents" / "event_state_tail.py"
        assert path.is_file(), "src/agents/event_state_tail.py must exist"
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        assert len(lines) <= 100, f"src/agents/event_state_tail.py must be <= 100 lines (got {len(lines)})"
        assert "@ai-rules" in text, "src/agents/event_state_tail.py must carry an @ai-rules header"
        _assert_forbidden_imports(
            path,
            ("redis", "google", "anthropic", "src.agents.brain", "src.agents.llm", "src.state"),
        )

        from src.agents.event_state_tail import format_event_state_tail

        assert callable(format_event_state_tail)
        sig = inspect.signature(format_event_state_tail)
        # Supply minimal values only for any required parameters without defaults
        kwargs: dict = {}
        for name, param in sig.parameters.items():
            if param.default is inspect.Parameter.empty and param.kind in (
                inspect.Parameter.POSITIONAL_OR_KEYWORD,
                inspect.Parameter.KEYWORD_ONLY,
            ):
                kwargs[name] = ""
        rendered = format_event_state_tail(**kwargs)
        assert isinstance(rendered, str)
        assert "<event_state>" in rendered and "</event_state>" in rendered, (
            f"format_event_state_tail must emit fenced <event_state>...</event_state> block, got: {rendered!r}"
        )

class TestC6_03_R1_L1_R6_F5:
    def test_c6_03_build_global_core_si_collapses_path_traversal(self):
        """[C6-03] build_global_core_si collapses .. path traversal in XML id attribute."""
        from src.agents.prefix_builder import build_global_core_si
        
        class MockLoader:
            def __init__(self):
                self.skills = {
                    "../secret.md": {"name": "secret", "content": "secret data"}
                }
            def build_generated_map(self):
                return ""
            def get_all_paths_for_phase(self, phase):
                return self.skills.keys()
            def resolve_dependencies_with_paths(self, paths):
                return [(p, self.skills[p]) for p in paths if p in self.skills]
            def get_tag_type(self, path):
                return "core"
        
        loader = MockLoader()
        core_si = build_global_core_si(loader)
        assert 'id="__/secret.md"' in core_si
        assert 'id="../secret.md"' not in core_si

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_r1_l1_r6_f5_prefix_hashes_logging_and_prune_notice(self, caplog, monkeypatch):
        from src.models import EventDocument, ConversationTurn
        from src.state.blackboard import BlackboardState
        from fakeredis.aioredis import FakeRedis
        from src.agents.brain import Brain
        import time

        ev = MagicMock(
            id="evt-log-test", title="test", source="chat", user_id="U1", domain="CASUAL",
            unread_notes=0,
            conversation=[
                ConversationTurn(turn=i, actor="user" if i%2==0 else "brain", action="message" if i%2==0 else "response", result=f"msg {i} " * 1000, thoughts="t " * 1000)
                for i in range(150)
            ]
        )

        

        redis = FakeRedis()
        state = BlackboardState(redis)
        brain = Brain(state, [], MagicMock())
        # mock skill loader
        brain._skill_loader = MagicMock()
        brain._skill_loader.build_generated_map.return_value = ""
        brain._skill_loader.get_phase_meta.return_value = {"priority": 10, "terminal_prompt": "Proceed."}

        import logging
        caplog.set_level(logging.INFO, logger="src.agents.brain")

        brain.blackboard.update_event_domain = AsyncMock()
        brain.blackboard.update_event_phase = AsyncMock()
        brain._is_event_closed = AsyncMock(return_value=False)
        brain.tool_handler = AsyncMock()
        
        # Mock the adapter instead of _call_vertex_llm so the log in _process_with_llm runs!
        # Wait, the log is in `_process_with_llm`! 
        # `stream = self._adapter.generate_stream(...)`
        mock_adapter = MagicMock()
        
        class MockStreamIter:
            def __aiter__(self): return self
            async def __anext__(self):
                # Return one chunk then stop
                if getattr(self, "done", False):
                    raise StopAsyncIteration()
                self.done = True
                return MagicMock(
                    text="Hello", 
                    function_call=None, 
                    raw_parts=[MagicMock(text="Hello", function_call=None)],
                    usage_metadata=MagicMock(total_token_count=1)
                )
                
        mock_adapter.generate_stream = MagicMock(return_value=MockStreamIter())
        brain._adapter = mock_adapter
        
        await brain._process_with_llm("evt-log-test", ev)

        log_msgs = [r.message for r in caplog.records if "hdr_full_sha8=" in r.message]
        assert len(log_msgs) >= 1
        log_msg = log_msgs[-1]

        assert "hdr_full_sha8=" in log_msg
        assert "decay_cutoff=" in log_msg
        assert "pruned_turns=" in log_msg

        contents_with_notice = await brain._build_contents(ev, terminal_prompt="Proceed.")
        parts = contents_with_notice[0].get("parts", [])
        assert any("pruned" in p.get("text", "") for p in parts)
        
        ev_short = MagicMock(
            id="evt-log-test-short", title="test", source="chat", user_id="U1", domain="CASUAL",
            conversation=[
                ConversationTurn(turn=0, actor="user", action="message", result="msg", thoughts="t")
            ]
        )
        contents_without_notice = await brain._build_contents(ev_short, terminal_prompt="Proceed.")
        
        from src.agents.prefix_builder import sha8_json
        assert sha8_json(contents_with_notice[0]) != sha8_json(contents_without_notice[0])
