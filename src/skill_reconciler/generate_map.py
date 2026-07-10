# src/skill_reconciler/generate_map.py
# @ai-rules:
# 1. [Constraint]: ZERO imports from src.agents. Uses importlib.util file loader for GATE_REGISTRY.
# 2. [Pattern]: No module-level I/O — importlib load ONLY inside _load_gate_registry().
# 3. [Constraint]: stdlib only (importlib.util, json, pathlib, dataclasses). No Redis, no async.
# 4. [Pattern]: Public API returns tuple[str, str] — (corpus key, json.dumps'd corpus value).
# 5. [Gotcha]: JSON value MUST be json.dumps() serialized — BrainSkillLoader calls json.loads()
#    on every corpus entry. Corrupt JSON on always/* triggers always_corrupt abort.
"""
Generate brain_skills/always/phase-tool-map.md from GATE_REGISTRY.

Produces a navigation skill with Mermaid diagram, 24-gate table, skill pointers,
and behavioral annotations — derived from the single source of truth in tool_gates.py.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from dataclasses import dataclass
from pathlib import Path

CORPUS_KEY = "always/phase-tool-map.md"

_FRONTMATTER: dict = {
    "description": "Phase x domain navigation map -- generated from GATE_REGISTRY",
    "tags": ["navigation", "phases", "domains", "gates"],
    "tag_type": "navigation",
    "tools": [
        "classify_event", "set_phase", "select_agent",
        "close_event", "defer_event", "report_incident",
    ],
}

_CONDITION_SUMMARIES: dict[str, str] = {
    "DEFER_WAKE_ITER0": "first cycle after defer wake",
    "INTERMEDIATE": "agent actively working (is_intermediate flag)",
    "PHASE_ESCALATE": "phase is not escalate",
    "PHASE_NOTIFY": "phase is not escalate or close",
    "PHASE_CLOSE": "phase is not escalate or close",
    "PHASE_OBSERVATION": "phase is close",
    "PHASE_JIRA_COMMENT": "phase not in dispatch/verify/escalate/close",
    "NO_KARGO_CONTEXT": "no Kargo evidence on event",
    "NO_GITHUB_CONTEXT": "no GitHub evidence on event",
    "PHASE_JIRA_FETCH": "phase not in triage/dispatch/verify",
    "PHASE_INCIDENT_SEARCH": "phase not in triage/dispatch/verify/escalate",
    "BUDGET_EXHAUSTED": "refresh count exceeds budget",
    "PRE_CLASSIFICATION": "domain not yet classified",
    "DOMAIN_CLEAR": "domain is CLEAR",
    "DOMAIN_COMPLEX": "domain is COMPLEX, <4 agent rounds",
    "DOMAIN_CHAOTIC": "domain is CHAOTIC",
    "DOMAIN_CASUAL": "domain is CASUAL, source is chat/slack",
    "JARVIS_RESPONSE": "no pending JARVIS message",
    "JARVIS_WAIT": "wait prerequisites not met",
    "INSPECT_EVENT": "source not in jarvis/chat/slack",
    "HOLD_WATCH": "not (jarvis source + close phase)",
    "POST_STICKY": "not (jarvis source + close phase)",
    "READ_STICKY": "no unread sticky notes",
    "UNEVALUATED_CLOSE": "unevaluated jarvis/user message exists",
    "SILENT_PARK": "no brain.response after last user.message (chat/slack only)",
    "HARD_STRIP_DEFER": "triage phase OR jarvis source",
    "HARD_STRIP_WAIT_USER": "triage phase OR non-user source",
}

_MERMAID_DIAGRAM = (
    "```mermaid\n"
    "graph TD\n"
    "    %% Entry points\n"
    "    START((Event Arrives)) --> PRE_CLASS\n"
    "\n"
    "    %% Pre-classification override\n"
    "    subgraph override [Override States]\n"
    "        PRE_CLASS{PRE_CLASSIFICATION<br/>classification, lookups, memory<br/>"
    "\u2014 all other capabilities locked}\n"
    "        INTERMEDIATE{INTERMEDIATE<br/>agent communication only<br/>"
    "\u2014 all other capabilities suspended}\n"
    "    end\n"
    "\n"
    "    PRE_CLASS -->|classify| TRIAGE\n"
    "\n"
    "    %% Phase progression\n"
    "    subgraph phases [Phase Pipeline]\n"
    "        TRIAGE[TRIAGE<br/>context gathering, classification,<br/>"
    "observations, incident search<br/>"
    "\u2014 NO: dispatch, defer, close, notify]\n"
    "        DISPATCH[DISPATCH<br/>agent routing, planning,<br/>"
    "context refresh, integration actions<br/>"
    "\u2014 NO: close, escalate]\n"
    "        VERIFY[VERIFY<br/>observations, context refresh,<br/>"
    "integration actions<br/>"
    "\u2014 NO: escalate]\n"
    "        ESCALATE[ESCALATE<br/>incident reporting, user notification,<br/>"
    "closure<br/>"
    "\u2014 NO: dispatch, defer]\n"
    "        CLOSE[CLOSE<br/>closure, user notification,<br/>"
    "result delivery<br/>"
    "\u2014 NO: observations, dispatch]\n"
    "    end\n"
    "\n"
    "    TRIAGE -->|advance to dispatch| DISPATCH\n"
    "    DISPATCH -->|advance to verify| VERIFY\n"
    "    VERIFY -->|advance to escalate| ESCALATE\n"
    "    VERIFY -->|advance to close| CLOSE\n"
    "    ESCALATE -->|advance to close| CLOSE\n"
    "    DISPATCH -->|reclassify| TRIAGE\n"
    "\n"
    "    %% Domain modifiers\n"
    "    subgraph domains [Domain Modifiers \u2014 intersect with phase capabilities]\n"
    "        CLEAR[/CLEAR\\<br/>No planning needed<br/>Act directly, verify, close/]\n"
    "        COMPLICATED[/COMPLICATED\\<br/>Full capabilities<br/>No domain restrictions/]\n"
    "        COMPLEX[/COMPLEX\\<br/>Cannot close prematurely<br/>until 4+ agent rounds/]\n"
    "        CHAOTIC[/CHAOTIC\\<br/>Triage actions only:<br/>routing, notification, escalation/]\n"
    "        CASUAL[/CASUAL\\<br/>Conversational subset:<br/>classification, lookups, notes,"
    "<br/>wait for user \u2014 NO: dispatch, defer, escalate, notify/]\n"
    "    end\n"
    "\n"
    "    TRIAGE -.->|domain classified| CLEAR\n"
    "    TRIAGE -.->|domain classified| COMPLICATED\n"
    "    TRIAGE -.->|domain classified| COMPLEX\n"
    "    TRIAGE -.->|domain classified| CHAOTIC\n"
    "    TRIAGE -.->|domain classified| CASUAL\n"
    "\n"
    "    %% Return edges\n"
    "    CASUAL -.->|reclassify to complicated| TRIAGE\n"
    "    COMPLEX -.->|4+ agent rounds| CLOSE\n"
    "```"
)

_SKILL_POINTERS_TABLE = (
    "| Transition | Pointer |\n"
    "|---|---|\n"
    '| Enter triage | <skill id="always/06-decision-guidelines.md"/> |\n'
    '| Enter dispatch | <skill id="dispatch/decision-routing.md"/> |\n'
    '| Enter verify | <skill id="always/03-control-theory.md"/> |\n'
    '| Enter escalate | <skill id="escalate/incident-tracking.md"/> |\n'
    '| Domain loaded | <skill id="domain/{domain}.md"/> |\n'
    '| Source loaded | <skill id="source/{source}.md"/> |'
)

_BEHAVIORAL_ANNOTATIONS = (
    "- Agent progress: wait for completion \u2014 don't act on intermediates\n"
    "- Notification authority: YOU are the sole notification channel to users\n"
    "- Action sequencing: one action per turn, verify result before next\n"
    "- Route vs message: dispatch = full work package, message = coordination\n"
    "- Authorization boundary: autonomous actions vs human-gated fixes"
)


@dataclass
class _GateInfo:
    gate_id: str
    mode: str
    tools: list[str]
    annotation: str
    condition: str


def _load_gate_registry() -> tuple:
    """Load GATE_REGISTRY and GateContext via importlib file loader (no src.agents import)."""
    tool_gates_path = Path(__file__).resolve().parents[1] / "agents" / "tool_gates.py"
    spec = importlib.util.spec_from_file_location("_tool_gates_isolated", tool_gates_path)
    if not spec or not spec.loader:
        raise RuntimeError(f"Cannot load {tool_gates_path}")
    module = importlib.util.module_from_spec(spec)
    # dataclass decorator needs module in sys.modules during class creation
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module.GATE_REGISTRY, module.GateContext


def _enumerate_gates(registry: list, gate_context_cls: type) -> list[_GateInfo]:
    """Iterate ALL gates with two representative contexts to collect tools affected."""
    neutral = gate_context_cls(
        brain_phase="dispatch", event_source="aligner",
        context_flags={}, conversation=[], is_defer_wake=False,
        iteration=0, has_kargo_context=False, has_github_context=False, unread_notes=0,
    )
    chat = gate_context_cls(
        brain_phase="dispatch", event_source="chat",
        context_flags={}, conversation=[], is_defer_wake=False,
        iteration=0, has_kargo_context=False, has_github_context=False, unread_notes=0,
    )
    gates: list[_GateInfo] = []
    for gate in registry:
        tools_neutral = gate.tools_affected(neutral)
        tools_chat = gate.tools_affected(chat)
        chat_only = tools_chat - tools_neutral
        base_tools = sorted(tools_neutral | tools_chat)
        annotation = ""
        if chat_only:
            base_tools = sorted(tools_neutral)
            annotation = " + " + ", ".join(f"`{t}`" for t in sorted(chat_only)) + " (chat/slack only)"
        gates.append(_GateInfo(
            gate_id=gate.gate_id, mode=gate.mode, tools=base_tools,
            annotation=annotation,
            condition=_CONDITION_SUMMARIES.get(gate.gate_id, ""),
        ))
    return gates


def _render_markdown(gates: list[_GateInfo]) -> str:
    """Render the full phase-tool-map markdown document."""
    lines = [
        "# Phase\u00d7Domain Navigation Map",
        "",
        "> Exact tool availability is enforced at runtime by the gate system.",
        "> This map shows the capability topology \u2014 use it to navigate toward "
        "the right phase for your intent.",
        "> Generated from GATE_REGISTRY \u2014 do not edit manually.",
        "",
        _MERMAID_DIAGRAM,
        "",
        "## Transition Skill Pointers",
        "",
        _SKILL_POINTERS_TABLE,
        "",
        "## Conditional Gates (generated from GATE_REGISTRY)",
        "",
        "| Gate ID | Mode | Tools Affected | Condition |",
        "|---|---|---|---|",
    ]
    for g in gates:
        tools_str = ", ".join(f"`{t}`" for t in g.tools)
        if g.annotation:
            tools_str += g.annotation
        lines.append(f"| {g.gate_id} | {g.mode} | {tools_str} | {g.condition} |")
    lines.extend([
        "",
        "## Behavioral Annotations",
        "",
        _BEHAVIORAL_ANNOTATIONS,
    ])
    return "\n".join(lines)


def generate_phase_tool_map() -> tuple[str, str]:
    """Generate phase-tool-map skill. Returns (corpus_key, json_value)."""
    registry, gate_ctx_cls = _load_gate_registry()
    missing = [g.gate_id for g in registry if g.gate_id not in _CONDITION_SUMMARIES]
    if missing:
        raise RuntimeError(f"GATE_REGISTRY has gates without condition summaries: {missing}")
    gates = _enumerate_gates(registry, gate_ctx_cls)
    body = _render_markdown(gates)
    value = json.dumps(
        {"body": body, "frontmatter": _FRONTMATTER, "blob_sha": "generated"},
        default=str,
    )
    return CORPUS_KEY, value
