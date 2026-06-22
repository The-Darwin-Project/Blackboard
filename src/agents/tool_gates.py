# src/agents/tool_gates.py
# @ai-rules:
# 1. [Constraint]: Pure evaluation logic -- no I/O, no async, no Redis, no LLM calls, no sibling imports.
# 2. [Pattern]: GATE_REGISTRY is the single source of truth for both stripping and diagnostics.
# 3. [Pattern]: mode="strip" removes listed tools; mode="allow" keeps ONLY listed tools.
# 4. [Gotcha]: Gate predicates are named functions (not lambdas) for per-gate unit testing.
# 5. [Gotcha]: evaluate_gates() returns list[dict], not set -- preserves tool schema dicts.
# 6. [Constraint]: context_flags is always a dict by the time it reaches GateContext
#    (build_gate_context normalizes None -> {}).
# 7. [Gotcha]: GateDefinition.hint is appended by diagnose_rejection(), not by _msg_* functions.
# 8. [Pattern]: 4 allow-mode gates: INTERMEDIATE, PRE_CLASSIFICATION, CHAOTIC, CASUAL.
"""
Tool gate evaluation and rejection diagnostics.

Single source of truth for which tools are available in a given Brain state
and why a rejected tool was blocked. Extracted from brain.py inline gate logic.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Literal

if TYPE_CHECKING:
    from ..models import EventDocument


@dataclass(frozen=True)
class GateContext:
    """All state needed for gate evaluation. Built once per LLM call."""
    brain_phase: str
    event_source: str
    context_flags: dict
    conversation: list
    is_defer_wake: bool
    iteration: int
    has_kargo_context: bool
    unread_notes: int
    refresh_budget: int = 0
    refresh_count: int = 0
    agent_completions: int = 0
    jarvis_already_waiting: bool = False
    jarvis_wait_count: int = 0


@dataclass(frozen=True)
class GateDefinition:
    """A single gate in the registry."""
    gate_id: str
    mode: Literal["strip", "allow"]
    predicate: Callable[[GateContext], bool]
    tools_affected: Callable[[GateContext], set[str]]
    message: Callable[[str, GateContext], str]
    hint: str | None = None


# ---------------------------------------------------------------------------
# Gate predicate functions (named for testability)
# ---------------------------------------------------------------------------

def _pred_defer_wake_iter0(ctx: GateContext) -> bool:
    return ctx.is_defer_wake and ctx.iteration == 0


def _pred_intermediate(ctx: GateContext) -> bool:
    return bool(ctx.context_flags.get("is_intermediate"))


def _pred_phase_escalate(ctx: GateContext) -> bool:
    return ctx.brain_phase != "escalate"


def _pred_phase_notify(ctx: GateContext) -> bool:
    return ctx.brain_phase not in ("escalate", "close")


def _pred_phase_close(ctx: GateContext) -> bool:
    return ctx.brain_phase not in ("escalate", "close")


def _pred_phase_observation(ctx: GateContext) -> bool:
    return ctx.brain_phase == "close"


def _pred_phase_jira_comment(ctx: GateContext) -> bool:
    return ctx.brain_phase not in ("dispatch", "verify", "escalate", "close")


def _pred_no_kargo_context(ctx: GateContext) -> bool:
    return not ctx.has_kargo_context


def _pred_phase_jira_fetch(ctx: GateContext) -> bool:
    return ctx.brain_phase not in ("triage", "dispatch", "verify")


def _pred_budget_exhausted(ctx: GateContext) -> bool:
    return ctx.refresh_budget <= 0


def _pred_pre_classification(ctx: GateContext) -> bool:
    return not ctx.context_flags.get("brain_has_classified", False)


def _pred_domain_clear(ctx: GateContext) -> bool:
    if not ctx.context_flags or not ctx.context_flags.get("brain_has_classified", False):
        return False
    return ctx.context_flags.get("event_domain", "complicated") == "clear"


def _pred_domain_complex(ctx: GateContext) -> bool:
    if not ctx.context_flags or not ctx.context_flags.get("brain_has_classified", False):
        return False
    if ctx.context_flags.get("event_domain", "complicated") != "complex":
        return False
    if ctx.brain_phase == "close":
        return False
    agent_rounds = sum(
        1 for t in ctx.conversation
        if t.actor not in ("brain", "user", "aligner", "headhunter", "jarvis")
    )
    return agent_rounds < 4


def _pred_domain_chaotic(ctx: GateContext) -> bool:
    if not ctx.context_flags or not ctx.context_flags.get("brain_has_classified", False):
        return False
    return ctx.context_flags.get("event_domain", "complicated") == "chaotic"


def _pred_domain_casual(ctx: GateContext) -> bool:
    if ctx.context_flags and ctx.context_flags.get("is_intermediate"):
        return False
    if not ctx.context_flags or not ctx.context_flags.get("brain_has_classified", False):
        return False
    if ctx.context_flags.get("event_domain", "complicated") != "casual":
        return False
    return ctx.event_source in ("chat", "slack")


def _pred_jarvis_response(ctx: GateContext) -> bool:
    """True when respond_to_jarvis should be STRIPPED (no unanswered jarvis message)."""
    has_unanswered = False
    if ctx.event_source == "jarvis" and not any(
        t.actor == "brain" and t.action == "respond_jarvis" for t in ctx.conversation
    ):
        has_unanswered = True
    else:
        for t in reversed(ctx.conversation):
            if t.actor == "jarvis" and t.action in ("message", "insight"):
                has_unanswered = True
                break
            if t.actor == "brain" and t.action == "respond_jarvis":
                break
    return not has_unanswered


def _pred_jarvis_wait(ctx: GateContext) -> bool:
    """True when wait_for_jarvis should be STRIPPED."""
    if ctx.event_source != "jarvis":
        return True
    has_respond = any(
        t.actor == "brain" and t.action == "respond_jarvis" for t in ctx.conversation
    )
    if not has_respond:
        return True
    if ctx.jarvis_already_waiting:
        return True
    if ctx.jarvis_wait_count >= 3:
        return True
    return False


def _pred_inspect_event(ctx: GateContext) -> bool:
    return ctx.event_source != "jarvis"


def _pred_hold_watch(ctx: GateContext) -> bool:
    return not (ctx.event_source == "jarvis" and ctx.brain_phase == "close")


def _pred_post_sticky(ctx: GateContext) -> bool:
    return not (ctx.event_source == "jarvis" and ctx.brain_phase == "close")


def _pred_read_sticky(ctx: GateContext) -> bool:
    return ctx.unread_notes <= 0


def _pred_hard_strip_defer(ctx: GateContext) -> bool:
    return ctx.brain_phase == "triage" or ctx.event_source == "jarvis"


def _pred_hard_strip_wait_user(ctx: GateContext) -> bool:
    if ctx.brain_phase == "triage":
        return True
    return ctx.event_source not in ("chat", "slack")


# ---------------------------------------------------------------------------
# Gate tools_affected functions (named for testability)
# ---------------------------------------------------------------------------

def _tools_defer_event(_ctx: GateContext) -> set[str]:
    return {"defer_event"}


def _tools_intermediate(_ctx: GateContext) -> set[str]:
    return {"reply_to_agent", "message_agent", "wait_for_agent", "respond_to_jarvis"}


def _tools_escalate(_ctx: GateContext) -> set[str]:
    return {"report_incident"}


def _tools_notify(_ctx: GateContext) -> set[str]:
    return {"notify_user_slack"}


def _tools_close(_ctx: GateContext) -> set[str]:
    return {"close_event", "notify_gitlab_result"}


def _tools_observation(_ctx: GateContext) -> set[str]:
    return {"record_observation", "list_observations", "take_note", "review_notes"}


def _tools_jira_comment(_ctx: GateContext) -> set[str]:
    return {"comment_jira_issue", "transition_jira_issue"}


def _tools_kargo(_ctx: GateContext) -> set[str]:
    return {"refresh_kargo_context"}


def _tools_jira_fetch(_ctx: GateContext) -> set[str]:
    return {"fetch_jira_issue"}


def _tools_budget(_ctx: GateContext) -> set[str]:
    return {"refresh_gitlab_context", "refresh_kargo_context"}


def _tools_pre_classification(ctx: GateContext) -> set[str]:
    allowed = {"lookup_service", "lookup_journal", "consult_deep_memory",
               "classify_event", "set_phase"}
    if ctx.event_source in ("slack", "chat"):
        allowed.add("wait_for_user")
    return allowed


def _tools_domain_clear(_ctx: GateContext) -> set[str]:
    return {"create_plan"}


def _tools_domain_complex(_ctx: GateContext) -> set[str]:
    return {"close_event"}


def _tools_domain_chaotic(_ctx: GateContext) -> set[str]:
    return {
        "select_agent", "classify_event", "lookup_service", "lookup_journal",
        "notify_user_slack", "get_plan_progress", "report_incident", "set_phase",
        "wait_for_agent", "reply_to_agent", "message_agent",
        "respond_to_jarvis", "wait_for_jarvis",
    }


def _tools_domain_casual(_ctx: GateContext) -> set[str]:
    return {
        "classify_event", "set_phase", "wait_for_user",
        "consult_deep_memory", "lookup_service", "lookup_journal",
        "respond_to_jarvis", "read_sticky_notes",
        "take_note", "review_notes",
    }


def _tools_jarvis_response(_ctx: GateContext) -> set[str]:
    return {"respond_to_jarvis"}


def _tools_jarvis_wait(_ctx: GateContext) -> set[str]:
    return {"wait_for_jarvis"}


def _tools_inspect_event(_ctx: GateContext) -> set[str]:
    return {"inspect_event"}


def _tools_hold_watch(_ctx: GateContext) -> set[str]:
    return {"hold_watch"}


def _tools_post_sticky(_ctx: GateContext) -> set[str]:
    return {"post_sticky_note"}


def _tools_read_sticky(_ctx: GateContext) -> set[str]:
    return {"read_sticky_notes"}


def _tools_wait_user(_ctx: GateContext) -> set[str]:
    return {"wait_for_user"}


# ---------------------------------------------------------------------------
# Gate message functions
# ---------------------------------------------------------------------------

def _msg_defer_wake_iter0(tool: str, _ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: first wake cycle. Prerequisite: verify state before re-deferring."


def _msg_intermediate(tool: str, _ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: agent is actively working. Constraint: communication tools only during active dispatch."


def _msg_phase_escalate(tool: str, ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: phase is {ctx.brain_phase}. Prerequisite: escalate phase."


def _msg_phase_notify(tool: str, ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: phase is {ctx.brain_phase}. Prerequisite: escalate or close phase."


def _msg_phase_close(tool: str, ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: phase is {ctx.brain_phase}. Prerequisite: escalate or close phase."


def _msg_phase_observation(tool: str, _ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: phase is close. Constraint: observations not available after close."


def _msg_phase_jira_comment(tool: str, ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: phase is {ctx.brain_phase}. Prerequisite: dispatch, verify, escalate, or close phase."


def _msg_no_kargo_context(tool: str, _ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: event has no Kargo context. Constraint: only available for Kargo-related events."


def _msg_phase_jira_fetch(tool: str, ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: phase is {ctx.brain_phase}. Prerequisite: triage, dispatch, or verify phase."


def _msg_budget_exhausted(tool: str, ctx: GateContext) -> str:
    return (
        f"[GATE] {tool} unavailable. State: refresh budget exhausted "
        f"({ctx.refresh_count} used, {ctx.agent_completions} refills). "
        f"Constraint: budget replenishes after agent completion turns."
    )


def _msg_pre_classification(tool: str, _ctx: GateContext) -> str:
    return (
        f"[GATE] {tool} unavailable. State: domain not yet classified. "
        f"Prerequisite: classification."
    )


def _msg_domain_clear(tool: str, _ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: domain is CLEAR. Constraint: CLEAR domain acts directly."


def _msg_domain_complex(tool: str, ctx: GateContext) -> str:
    agent_rounds = sum(
        1 for t in ctx.conversation
        if t.actor not in ("brain", "user", "aligner", "headhunter", "jarvis")
    )
    return (
        f"[GATE] {tool} unavailable. State: domain is COMPLEX, {agent_rounds} agent rounds completed. "
        f"Prerequisite: 4+ agent rounds."
    )


def _msg_domain_chaotic(tool: str, _ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: domain is CHAOTIC. Constraint: only act-first tools available."


def _msg_domain_casual(tool: str, _ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: domain is CASUAL. Constraint: conversational tools only. Reclassify to access operational tools."


def _msg_jarvis_response(tool: str, _ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: no pending JARVIS message in conversation."


def _msg_jarvis_wait(tool: str, _ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: wait_for_jarvis prerequisites not met."


def _msg_inspect_event(tool: str, ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: source is {ctx.event_source}. Prerequisite: jarvis source (meta-event only)."


def _msg_hold_watch(tool: str, ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: source={ctx.event_source}, phase={ctx.brain_phase}. Prerequisite: jarvis source + close phase."


def _msg_post_sticky(tool: str, ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: source={ctx.event_source}, phase={ctx.brain_phase}. Prerequisite: jarvis source + close phase."


def _msg_read_sticky(tool: str, _ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: no unread sticky notes."


def _msg_hard_strip_defer(tool: str, ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: phase={ctx.brain_phase}, source={ctx.event_source}. Constraint: not available in triage or jarvis events."


def _msg_hard_strip_wait_user(tool: str, ctx: GateContext) -> str:
    return f"[GATE] {tool} unavailable. State: source={ctx.event_source}. Constraint: only available for user-facing events past triage."


# ---------------------------------------------------------------------------
# GATE_REGISTRY: ordered list of all gates (precedence order)
# ---------------------------------------------------------------------------

GATE_REGISTRY: list[GateDefinition] = [
    GateDefinition(
        gate_id="DEFER_WAKE_ITER0",
        mode="strip",
        predicate=_pred_defer_wake_iter0,
        tools_affected=_tools_defer_event,
        message=_msg_defer_wake_iter0,
    ),
    GateDefinition(
        gate_id="INTERMEDIATE",
        mode="allow",
        predicate=_pred_intermediate,
        tools_affected=_tools_intermediate,
        message=_msg_intermediate,
    ),
    GateDefinition(
        gate_id="PHASE_ESCALATE",
        mode="strip",
        predicate=_pred_phase_escalate,
        tools_affected=_tools_escalate,
        message=_msg_phase_escalate,
    ),
    GateDefinition(
        gate_id="PHASE_NOTIFY",
        mode="strip",
        predicate=_pred_phase_notify,
        tools_affected=_tools_notify,
        message=_msg_phase_notify,
    ),
    GateDefinition(
        gate_id="PHASE_CLOSE",
        mode="strip",
        predicate=_pred_phase_close,
        tools_affected=_tools_close,
        message=_msg_phase_close,
    ),
    GateDefinition(
        gate_id="PHASE_OBSERVATION",
        mode="strip",
        predicate=_pred_phase_observation,
        tools_affected=_tools_observation,
        message=_msg_phase_observation,
    ),
    GateDefinition(
        gate_id="PHASE_JIRA_COMMENT",
        mode="strip",
        predicate=_pred_phase_jira_comment,
        tools_affected=_tools_jira_comment,
        message=_msg_phase_jira_comment,
    ),
    GateDefinition(
        gate_id="NO_KARGO_CONTEXT",
        mode="strip",
        predicate=_pred_no_kargo_context,
        tools_affected=_tools_kargo,
        message=_msg_no_kargo_context,
        hint="agent-based exploration can discover Kargo stage and freight state.",
    ),
    GateDefinition(
        gate_id="PHASE_JIRA_FETCH",
        mode="strip",
        predicate=_pred_phase_jira_fetch,
        tools_affected=_tools_jira_fetch,
        message=_msg_phase_jira_fetch,
        hint="available in triage, dispatch, and verify states.",
    ),
    GateDefinition(
        gate_id="BUDGET_EXHAUSTED",
        mode="strip",
        predicate=_pred_budget_exhausted,
        tools_affected=_tools_budget,
        message=_msg_budget_exhausted,
        hint="budget replenishes when agent completion turns are present.",
    ),
    GateDefinition(
        gate_id="PRE_CLASSIFICATION",
        mode="allow",
        predicate=_pred_pre_classification,
        tools_affected=_tools_pre_classification,
        message=_msg_pre_classification,
        hint="lookups and classification are available in current state.",
    ),
    GateDefinition(
        gate_id="DOMAIN_CLEAR",
        mode="strip",
        predicate=_pred_domain_clear,
        tools_affected=_tools_domain_clear,
        message=_msg_domain_clear,
    ),
    GateDefinition(
        gate_id="DOMAIN_COMPLEX",
        mode="strip",
        predicate=_pred_domain_complex,
        tools_affected=_tools_domain_complex,
        message=_msg_domain_complex,
        hint="additional agent rounds build the evidence base needed for closure.",
    ),
    GateDefinition(
        gate_id="DOMAIN_CHAOTIC",
        mode="allow",
        predicate=_pred_domain_chaotic,
        tools_affected=_tools_domain_chaotic,
        message=_msg_domain_chaotic,
    ),
    GateDefinition(
        gate_id="DOMAIN_CASUAL",
        mode="allow",
        predicate=_pred_domain_casual,
        tools_affected=_tools_domain_casual,
        message=_msg_domain_casual,
        hint="reclassify to complicated or clear to unlock full capabilities.",
    ),
    GateDefinition(
        gate_id="JARVIS_RESPONSE",
        mode="strip",
        predicate=_pred_jarvis_response,
        tools_affected=_tools_jarvis_response,
        message=_msg_jarvis_response,
    ),
    GateDefinition(
        gate_id="JARVIS_WAIT",
        mode="strip",
        predicate=_pred_jarvis_wait,
        tools_affected=_tools_jarvis_wait,
        message=_msg_jarvis_wait,
    ),
    GateDefinition(
        gate_id="INSPECT_EVENT",
        mode="strip",
        predicate=_pred_inspect_event,
        tools_affected=_tools_inspect_event,
        message=_msg_inspect_event,
    ),
    GateDefinition(
        gate_id="HOLD_WATCH",
        mode="strip",
        predicate=_pred_hold_watch,
        tools_affected=_tools_hold_watch,
        message=_msg_hold_watch,
    ),
    GateDefinition(
        gate_id="POST_STICKY",
        mode="strip",
        predicate=_pred_post_sticky,
        tools_affected=_tools_post_sticky,
        message=_msg_post_sticky,
    ),
    GateDefinition(
        gate_id="READ_STICKY",
        mode="strip",
        predicate=_pred_read_sticky,
        tools_affected=_tools_read_sticky,
        message=_msg_read_sticky,
    ),
    GateDefinition(
        gate_id="HARD_STRIP_DEFER",
        mode="strip",
        predicate=_pred_hard_strip_defer,
        tools_affected=_tools_defer_event,
        message=_msg_hard_strip_defer,
    ),
    GateDefinition(
        gate_id="HARD_STRIP_WAIT_USER",
        mode="strip",
        predicate=_pred_hard_strip_wait_user,
        tools_affected=_tools_wait_user,
        message=_msg_hard_strip_wait_user,
    ),
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def evaluate_gates(
    all_tools: list[dict],
    ctx: GateContext,
) -> list[dict]:
    """Apply all gates in precedence order, return filtered active_tools list.

    Replaces the inline stripping logic formerly in brain.py L886-1041.
    """
    active_names: set[str] = {t["name"] for t in all_tools}

    for gate in GATE_REGISTRY:
        if not gate.predicate(ctx):
            continue

        affected = gate.tools_affected(ctx)

        if gate.mode == "allow":
            active_names &= affected
        else:
            active_names -= affected

    return [t for t in all_tools if t["name"] in active_names]


def diagnose_rejection(
    tool_name: str,
    ctx: GateContext,
) -> str:
    """Return a [GATE] diagnostic for the first gate that would block tool_name.

    Iterates the same GATE_REGISTRY in precedence order. First match wins.
    """
    for gate in GATE_REGISTRY:
        if not gate.predicate(ctx):
            continue

        affected = gate.tools_affected(ctx)

        if gate.mode == "allow":
            if tool_name not in affected:
                msg = gate.message(tool_name, ctx)
                if gate.hint:
                    msg += f" Hint: {gate.hint}"
                return msg
        else:
            if tool_name in affected:
                msg = gate.message(tool_name, ctx)
                if gate.hint:
                    msg += f" Hint: {gate.hint}"
                return msg

    return f"[UNKNOWN GATE] {tool_name} stripped by undocumented runtime condition."


def build_gate_context(
    event: "EventDocument",
    brain_phase: str,
    context_flags: dict | None,
    is_defer_wake: bool = False,
    iteration: int = 0,
    jarvis_already_waiting: bool = False,
    jarvis_wait_count: int = 0,
) -> GateContext:
    """Construct GateContext from event + Brain runtime state.

    Defensive: context_flags defaults to {} if None.
    Computes budget state from conversation history.
    """
    flags = context_flags or {}
    conversation = event.conversation or []

    has_kargo = bool(
        event.event
        and event.event.evidence
        and hasattr(event.event.evidence, "kargo_context")
        and event.event.evidence.kargo_context
    )
    unread = getattr(event, "unread_notes", 0) or 0

    # Budget computation (refresh tools)
    refresh_tools_budgeted = {"refresh_gitlab_context", "refresh_kargo_context"}
    refresh_count = sum(
        1 for t in conversation
        if t.actor == "brain" and t.waitingFor in refresh_tools_budgeted
    )
    agent_completions = sum(
        1 for t in conversation
        if t.actor not in ("brain", "user", "aligner", "headhunter", "jarvis")
        and t.action in ("execute", "plan")
    )
    budget = min(3 + agent_completions, 10) - refresh_count

    return GateContext(
        brain_phase=brain_phase,
        event_source=event.source,
        context_flags=flags,
        conversation=conversation,
        is_defer_wake=is_defer_wake,
        iteration=iteration,
        has_kargo_context=has_kargo,
        unread_notes=unread,
        refresh_budget=budget,
        refresh_count=refresh_count,
        agent_completions=agent_completions,
        jarvis_already_waiting=jarvis_already_waiting,
        jarvis_wait_count=jarvis_wait_count,
    )
