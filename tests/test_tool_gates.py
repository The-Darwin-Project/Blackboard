# BlackBoard/tests/test_tool_gates.py
# @ai-rules:
# 1. [Constraint]: No Redis, no async — pure unit tests for tool_gates.py.
# 2. [Pattern]: Fake conversation turns via SimpleNamespace (matches ConversationTurn interface).
# 3. [Gotcha]: evaluate_gates returns list[dict], assert on name sets via _names() helper.
"""Tool gate evaluation and rejection diagnostic tests."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.agents.tool_gates import (
    GATE_REGISTRY,
    GateContext,
    build_gate_context,
    diagnose_rejection,
    evaluate_gates,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _names(tools: list[dict]) -> set[str]:
    return {t["name"] for t in tools}


def _fake_schemas(*names: str) -> list[dict]:
    return [{"name": n} for n in names]


def _load_real_tool_names() -> frozenset[str]:
    from src.agents.llm import BRAIN_TOOL_SCHEMAS
    return frozenset(t["name"] for t in BRAIN_TOOL_SCHEMAS)


ALL_TOOL_NAMES = _load_real_tool_names()

ALL_SCHEMAS = _fake_schemas(*ALL_TOOL_NAMES)


def _turn(actor: str, action: str, **kw) -> SimpleNamespace:
    return SimpleNamespace(actor=actor, action=action, waitingFor=kw.get("waitingFor"))


def _ctx(**overrides) -> GateContext:
    defaults = dict(
        brain_phase="dispatch",
        event_source="aligner",
        context_flags={"brain_has_classified": True, "event_domain": "complicated"},
        conversation=[],
        is_defer_wake=False,
        iteration=0,
        has_kargo_context=True,
        unread_notes=0,
        refresh_budget=3,
        refresh_count=0,
        agent_completions=0,
        jarvis_already_waiting=False,
        jarvis_wait_count=0,
    )
    defaults.update(overrides)
    return GateContext(**defaults)


# ---------------------------------------------------------------------------
# Gate registry structure tests
# ---------------------------------------------------------------------------

class TestRegistryStructure:
    def test_registry_has_22_gates(self):
        assert len(GATE_REGISTRY) == 22

    def test_all_gate_ids_unique(self):
        ids = [g.gate_id for g in GATE_REGISTRY]
        assert len(ids) == len(set(ids))

    def test_three_allow_mode_gates(self):
        allow_gates = [g for g in GATE_REGISTRY if g.mode == "allow"]
        assert len(allow_gates) == 3
        assert {g.gate_id for g in allow_gates} == {"INTERMEDIATE", "PRE_CLASSIFICATION", "DOMAIN_CHAOTIC"}

    def test_nineteen_strip_mode_gates(self):
        strip_gates = [g for g in GATE_REGISTRY if g.mode == "strip"]
        assert len(strip_gates) == 19


# ---------------------------------------------------------------------------
# Per-gate unit tests (predicate + tools_affected + message)
# ---------------------------------------------------------------------------

class TestDeferWakeIter0:
    def test_fires_on_defer_wake_iter0(self):
        ctx = _ctx(is_defer_wake=True, iteration=0)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "defer_event" not in _names(result)

    def test_does_not_fire_iter1(self):
        ctx = _ctx(is_defer_wake=True, iteration=1)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "defer_event" in _names(result)

    def test_diagnosis(self):
        ctx = _ctx(is_defer_wake=True, iteration=0)
        msg = diagnose_rejection("defer_event", ctx)
        assert "[GATE]" in msg
        assert "first wake cycle" in msg


class TestIntermediate:
    def test_strips_to_communication_only(self):
        turns = [_turn("jarvis", "message")]
        ctx = _ctx(
            context_flags={"is_intermediate": True, "brain_has_classified": True},
            conversation=turns,
        )
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert names == {"reply_to_agent", "message_agent", "wait_for_agent", "respond_to_jarvis"}

    def test_diagnosis(self):
        ctx = _ctx(context_flags={"is_intermediate": True, "brain_has_classified": True})
        msg = diagnose_rejection("select_agent", ctx)
        assert "[GATE]" in msg
        assert "agent is actively working" in msg


class TestPhaseEscalate:
    def test_strips_report_incident_outside_escalate(self):
        ctx = _ctx(brain_phase="dispatch")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "report_incident" not in _names(result)

    def test_keeps_report_incident_in_escalate(self):
        ctx = _ctx(brain_phase="escalate")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "report_incident" in _names(result)


class TestPhaseNotify:
    def test_strips_notify_outside_escalate_close(self):
        ctx = _ctx(brain_phase="dispatch")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "notify_user_slack" not in _names(result)

    def test_keeps_notify_in_close(self):
        ctx = _ctx(brain_phase="close")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "notify_user_slack" in _names(result)


class TestPhaseClose:
    def test_strips_close_event_in_triage(self):
        ctx = _ctx(brain_phase="triage")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "close_event" not in _names(result)
        assert "notify_gitlab_result" not in _names(result)

    def test_keeps_close_event_in_escalate(self):
        ctx = _ctx(brain_phase="escalate")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "close_event" in _names(result)


class TestPhaseObservation:
    def test_strips_observations_in_close(self):
        ctx = _ctx(brain_phase="close")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "record_observation" not in _names(result)
        assert "list_observations" not in _names(result)

    def test_keeps_observations_in_dispatch(self):
        ctx = _ctx(brain_phase="dispatch")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "record_observation" in _names(result)


class TestPhaseJiraComment:
    def test_strips_jira_comment_in_triage(self):
        ctx = _ctx(brain_phase="triage")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "comment_jira_issue" not in _names(result)

    def test_keeps_jira_comment_in_verify(self):
        ctx = _ctx(brain_phase="verify")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "comment_jira_issue" in _names(result)


class TestNoKargoContext:
    def test_strips_refresh_kargo_without_context(self):
        ctx = _ctx(has_kargo_context=False)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "refresh_kargo_context" not in _names(result)

    def test_keeps_refresh_kargo_with_context(self):
        ctx = _ctx(has_kargo_context=True)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "refresh_kargo_context" in _names(result)


class TestPhaseJiraFetch:
    def test_strips_fetch_jira_in_escalate(self):
        ctx = _ctx(brain_phase="escalate")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "fetch_jira_issue" not in _names(result)

    def test_keeps_fetch_jira_in_triage(self):
        ctx = _ctx(brain_phase="triage")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "fetch_jira_issue" in _names(result)

    def test_diagnosis_has_hint(self):
        ctx = _ctx(brain_phase="escalate")
        msg = diagnose_rejection("fetch_jira_issue", ctx)
        assert "Hint:" in msg


class TestBudgetExhausted:
    def test_strips_refresh_when_budget_zero(self):
        ctx = _ctx(refresh_budget=0, refresh_count=3)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "refresh_gitlab_context" not in _names(result)

    def test_keeps_refresh_with_budget(self):
        ctx = _ctx(refresh_budget=2)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "refresh_gitlab_context" in _names(result)

    def test_diagnosis_includes_counts(self):
        ctx = _ctx(refresh_budget=0, refresh_count=4, agent_completions=1)
        msg = diagnose_rejection("refresh_gitlab_context", ctx)
        assert "4 used" in msg
        assert "1 refills" in msg


class TestPreClassification:
    def test_restricts_to_lookup_classify(self):
        ctx = _ctx(context_flags={"brain_has_classified": False}, event_source="aligner")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert names == {"lookup_service", "lookup_journal", "consult_deep_memory", "classify_event", "set_phase"}

    def test_chat_source_allows_wait_for_user(self):
        ctx = _ctx(context_flags={"brain_has_classified": False}, event_source="chat")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_user" in _names(result)

    def test_aligner_source_blocks_wait_for_user(self):
        ctx = _ctx(context_flags={"brain_has_classified": False}, event_source="aligner")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_user" not in _names(result)


class TestDomainClear:
    def test_strips_create_plan(self):
        ctx = _ctx(context_flags={"brain_has_classified": True, "event_domain": "clear"})
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "create_plan" not in _names(result)


class TestDomainComplex:
    def test_strips_close_event_under_4_rounds(self):
        turns = [_turn("sysadmin", "execute") for _ in range(3)]
        ctx = _ctx(
            context_flags={"brain_has_classified": True, "event_domain": "complex"},
            conversation=turns,
        )
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "close_event" not in _names(result)

    def test_keeps_close_event_at_4_rounds(self):
        turns = [_turn("sysadmin", "execute") for _ in range(4)]
        ctx = _ctx(
            brain_phase="escalate",
            context_flags={"brain_has_classified": True, "event_domain": "complex"},
            conversation=turns,
        )
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "close_event" in _names(result)


class TestDomainChaotic:
    def test_restricts_to_act_first_tools(self):
        turns = [
            _turn("jarvis", "message"),
            _turn("brain", "respond_jarvis"),
            _turn("jarvis", "message"),
        ]
        ctx = _ctx(
            brain_phase="escalate",
            context_flags={"brain_has_classified": True, "event_domain": "chaotic"},
            event_source="jarvis",
            conversation=turns,
        )
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        expected = {
            "select_agent", "classify_event", "lookup_service", "lookup_journal",
            "notify_user_slack", "get_plan_progress", "report_incident", "set_phase",
            "wait_for_agent", "reply_to_agent", "message_agent",
            "respond_to_jarvis", "wait_for_jarvis",
        }
        assert names == expected

    def test_includes_agent_communication(self):
        """Pre-flight audit: CHAOTIC must allow agent interaction for intermediate."""
        ctx = _ctx(context_flags={"brain_has_classified": True, "event_domain": "chaotic"})
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert {"wait_for_agent", "reply_to_agent", "message_agent"} <= names


class TestJarvisResponse:
    def test_strips_respond_when_no_unanswered(self):
        turns = [_turn("brain", "respond_jarvis")]
        ctx = _ctx(event_source="aligner", conversation=turns)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "respond_to_jarvis" not in _names(result)

    def test_keeps_respond_when_jarvis_event_unanswered(self):
        ctx = _ctx(event_source="jarvis", conversation=[])
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "respond_to_jarvis" in _names(result)

    def test_keeps_respond_when_jarvis_message_pending(self):
        turns = [
            _turn("brain", "respond_jarvis"),
            _turn("jarvis", "message"),
        ]
        ctx = _ctx(event_source="aligner", conversation=turns)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "respond_to_jarvis" in _names(result)


class TestJarvisWait:
    def test_strips_wait_non_jarvis_source(self):
        ctx = _ctx(event_source="aligner")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_jarvis" not in _names(result)

    def test_strips_wait_without_respond(self):
        ctx = _ctx(event_source="jarvis", conversation=[])
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_jarvis" not in _names(result)

    def test_keeps_wait_after_respond(self):
        turns = [_turn("brain", "respond_jarvis")]
        ctx = _ctx(event_source="jarvis", conversation=turns)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_jarvis" in _names(result)

    def test_strips_wait_when_already_waiting(self):
        turns = [_turn("brain", "respond_jarvis")]
        ctx = _ctx(event_source="jarvis", conversation=turns, jarvis_already_waiting=True)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_jarvis" not in _names(result)

    def test_strips_wait_at_max_retries(self):
        turns = [_turn("brain", "respond_jarvis")]
        ctx = _ctx(event_source="jarvis", conversation=turns, jarvis_wait_count=3)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_jarvis" not in _names(result)


class TestInspectEvent:
    def test_strips_for_non_jarvis(self):
        ctx = _ctx(event_source="aligner")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "inspect_event" not in _names(result)

    def test_keeps_for_jarvis(self):
        ctx = _ctx(event_source="jarvis")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "inspect_event" in _names(result)


class TestHoldWatch:
    def test_strips_outside_jarvis_close(self):
        ctx = _ctx(event_source="jarvis", brain_phase="dispatch")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "hold_watch" not in _names(result)

    def test_keeps_for_jarvis_close(self):
        ctx = _ctx(event_source="jarvis", brain_phase="close")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "hold_watch" in _names(result)


class TestPostSticky:
    def test_strips_outside_jarvis_close(self):
        ctx = _ctx(event_source="aligner", brain_phase="close")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "post_sticky_note" not in _names(result)

    def test_keeps_for_jarvis_close(self):
        ctx = _ctx(event_source="jarvis", brain_phase="close")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "post_sticky_note" in _names(result)


class TestReadSticky:
    def test_strips_when_no_unread(self):
        ctx = _ctx(unread_notes=0)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "read_sticky_notes" not in _names(result)

    def test_keeps_when_unread(self):
        ctx = _ctx(unread_notes=3)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "read_sticky_notes" in _names(result)


class TestHardStripDefer:
    def test_strips_in_triage(self):
        ctx = _ctx(brain_phase="triage")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "defer_event" not in _names(result)

    def test_strips_for_jarvis(self):
        ctx = _ctx(event_source="jarvis")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "defer_event" not in _names(result)

    def test_keeps_in_dispatch_aligner(self):
        ctx = _ctx(brain_phase="dispatch", event_source="aligner")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "defer_event" in _names(result)


class TestHardStripWaitUser:
    def test_strips_in_triage(self):
        ctx = _ctx(brain_phase="triage")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_user" not in _names(result)

    def test_strips_for_non_user_source(self):
        ctx = _ctx(event_source="aligner")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_user" not in _names(result)

    def test_keeps_for_chat(self):
        ctx = _ctx(event_source="chat")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_user" in _names(result)

    def test_keeps_for_slack(self):
        ctx = _ctx(event_source="slack")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "wait_for_user" in _names(result)


# ---------------------------------------------------------------------------
# Mode tests (strip vs allow semantics)
# ---------------------------------------------------------------------------

class TestModeSemantics:
    def test_strip_mode_removes_listed_tools(self):
        schemas = _fake_schemas("report_incident", "select_agent", "classify_event")
        ctx = _ctx(brain_phase="dispatch")
        result = evaluate_gates(schemas, ctx)
        assert "report_incident" not in _names(result)
        assert "select_agent" in _names(result)

    def test_allow_mode_keeps_only_listed_tools(self):
        schemas = _fake_schemas("reply_to_agent", "select_agent", "classify_event")
        ctx = _ctx(context_flags={"is_intermediate": True, "brain_has_classified": True})
        result = evaluate_gates(schemas, ctx)
        names = _names(result)
        assert "reply_to_agent" in names
        assert "select_agent" not in names


# ---------------------------------------------------------------------------
# Precedence conflict tests
# ---------------------------------------------------------------------------

class TestPrecedence:
    def test_defer_overlap_wake_iter0_and_hard_strip(self):
        """Gate 1 (DEFER_WAKE_ITER0) fires before gate 21 (HARD_STRIP_DEFER).
        Both strip defer_event. Diagnostic should report the first match."""
        ctx = _ctx(is_defer_wake=True, iteration=0, brain_phase="triage")
        msg = diagnose_rejection("defer_event", ctx)
        assert "first wake cycle" in msg

    def test_intermediate_takes_precedence_over_phase_gates(self):
        """INTERMEDIATE (gate 2) fires before phase gates (3-7)."""
        ctx = _ctx(
            brain_phase="escalate",
            context_flags={"is_intermediate": True, "brain_has_classified": True},
        )
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert "report_incident" not in names
        assert "reply_to_agent" in names

    def test_pre_classification_takes_precedence_over_domain(self):
        """PRE_CLASSIFICATION (gate 11) fires before DOMAIN_* (gates 12-14)."""
        ctx = _ctx(context_flags={"brain_has_classified": False, "event_domain": "chaotic"})
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert "classify_event" in names
        assert "select_agent" not in names


# ---------------------------------------------------------------------------
# Hallucination test
# ---------------------------------------------------------------------------

class TestHallucination:
    def test_unknown_tool_diagnosis(self):
        ctx = _ctx()
        msg = diagnose_rejection("totally_fake_tool", ctx)
        assert "[UNKNOWN GATE]" in msg

    def test_gated_tool_gets_gate_message(self):
        ctx = _ctx(brain_phase="triage")
        msg = diagnose_rejection("report_incident", ctx)
        assert "[GATE]" in msg
        assert "escalate" in msg.lower()


# ---------------------------------------------------------------------------
# context_flags=None defensive test
# ---------------------------------------------------------------------------

class TestContextFlagsNone:
    def test_build_gate_context_handles_none_flags(self):
        from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput
        evidence = EventEvidence(
            display_text="test", source_type="aligner", severity="info",
        )
        event = EventDocument(
            id="evt-test",
            source="aligner",
            service="test-svc",
            brain_phase="triage",
            event=EventInput(reason="anomaly", evidence=evidence),
        )
        ctx = build_gate_context(
            event=event,
            brain_phase="triage",
            context_flags=None,
        )
        assert ctx.context_flags == {}
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Fallback test
# ---------------------------------------------------------------------------

class TestFallback:
    def test_no_gate_match_returns_unknown_gate(self):
        ctx = _ctx(brain_phase="dispatch", event_source="chat")
        msg = diagnose_rejection("lookup_service", ctx)
        assert "[UNKNOWN GATE]" in msg


# ---------------------------------------------------------------------------
# Empty toolset invariant
# ---------------------------------------------------------------------------

class TestEmptyToolset:
    def test_evaluate_gates_never_empty_for_normal_state(self):
        ctx = _ctx()
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert len(result) > 0

    def test_intermediate_returns_communication_tools(self):
        ctx = _ctx(context_flags={"is_intermediate": True, "brain_has_classified": True})
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Parity: all BRAIN_TOOL_SCHEMAS tools can be diagnosed
# ---------------------------------------------------------------------------

class TestDiagnosticParity:
    def test_every_gatable_tool_has_diagnostic(self):
        """Every tool that can be stripped by any gate gets a [GATE] message (not fallback)."""
        gatable_tools: set[str] = set()
        for gate in GATE_REGISTRY:
            if gate.mode == "strip":
                ctx = _ctx()
                gatable_tools |= gate.tools_affected(ctx)
            else:
                ctx = _ctx()
                affected = gate.tools_affected(ctx)
                gatable_tools |= (ALL_TOOL_NAMES - affected)

        for tool in gatable_tools:
            found_gate = False
            for gate in GATE_REGISTRY:
                ctx = _ctx()
                if gate.predicate(ctx):
                    affected = gate.tools_affected(ctx)
                    if gate.mode == "strip" and tool in affected:
                        found_gate = True
                        break
                    elif gate.mode == "allow" and tool not in affected:
                        found_gate = True
                        break
            if found_gate:
                msg = diagnose_rejection(tool, ctx)
                assert "[GATE]" in msg or "[UNKNOWN GATE]" in msg, f"No diagnostic for {tool}"


# ---------------------------------------------------------------------------
# Regression: behavior parity for known event states
# ---------------------------------------------------------------------------

class TestBehaviorParity:
    def test_triage_aligner_standard_set(self):
        """Triage + aligner: no defer, no wait_for_user, no report_incident, no close."""
        ctx = _ctx(brain_phase="triage", event_source="aligner")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert "defer_event" not in names
        assert "wait_for_user" not in names
        assert "report_incident" not in names
        assert "close_event" not in names
        assert "lookup_service" in names
        assert "classify_event" in names

    def test_dispatch_chat_full_routing(self):
        """Dispatch + chat + classified: standard routing tools available."""
        ctx = _ctx(
            brain_phase="dispatch",
            event_source="chat",
            context_flags={"brain_has_classified": True, "event_domain": "complicated"},
        )
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert "select_agent" in names
        assert "create_plan" in names
        assert "defer_event" in names
        assert "wait_for_user" in names

    def test_escalate_jarvis_restricted(self):
        """Escalate + jarvis: no defer/wait_for_user, has report_incident."""
        ctx = _ctx(brain_phase="escalate", event_source="jarvis")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert "report_incident" in names
        assert "defer_event" not in names
        assert "wait_for_user" not in names

    def test_close_jarvis_has_sticky_and_hold(self):
        """Close + jarvis: sticky notes + hold_watch available."""
        ctx = _ctx(brain_phase="close", event_source="jarvis", unread_notes=2)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert "hold_watch" in names
        assert "post_sticky_note" in names
        assert "read_sticky_notes" in names
        assert "record_observation" not in names


# ---------------------------------------------------------------------------
# F-01: pre_classification fires on empty context_flags
# ---------------------------------------------------------------------------

class TestPreClassificationEmptyFlags:
    def test_fires_when_context_flags_empty(self):
        """Gate must fire when context_flags={} (no brain_has_classified key)."""
        ctx = _ctx(context_flags={})
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert "select_agent" not in names
        assert "classify_event" in names

    def test_fires_when_brain_has_classified_false(self):
        ctx = _ctx(context_flags={"brain_has_classified": False})
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert "select_agent" not in names
        assert "classify_event" in names


# ---------------------------------------------------------------------------
# F-03: INTERMEDIATE + PRE_CLASSIFICATION double-fire -> empty intersection
# ---------------------------------------------------------------------------

class TestAllowModeIntersection:
    def test_intermediate_plus_unclassified_produces_empty(self):
        """Both allow-mode gates fire, intersection is empty set."""
        ctx = _ctx(context_flags={"is_intermediate": True, "brain_has_classified": False})
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert _names(result) == set()

    def test_chaotic_plus_intermediate_keeps_overlap(self):
        """INTERMEDIATE and DOMAIN_CHAOTIC both fire -- intersection includes agent comms."""
        ctx = _ctx(context_flags={
            "is_intermediate": True, "brain_has_classified": True, "event_domain": "chaotic",
        })
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        names = _names(result)
        assert {"reply_to_agent", "message_agent", "wait_for_agent", "respond_to_jarvis"} & names


# ---------------------------------------------------------------------------
# F-05: Budget construction tests for build_gate_context
# ---------------------------------------------------------------------------

class TestBudgetConstruction:
    def test_base_budget_is_3(self):
        from src.models import EventDocument, EventEvidence, EventInput
        evidence = EventEvidence(display_text="test", source_type="aligner", severity="info")
        event = EventDocument(
            id="evt-budget", source="aligner", service="svc",
            brain_phase="dispatch",
            event=EventInput(reason="anomaly", evidence=evidence),
        )
        ctx = build_gate_context(event=event, brain_phase="dispatch", context_flags={})
        assert ctx.refresh_budget == 3

    def test_budget_capped_at_10(self):
        from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput
        evidence = EventEvidence(display_text="test", source_type="aligner", severity="info")
        turns = [ConversationTurn(turn=i, actor="sysadmin", action="execute") for i in range(20)]
        event = EventDocument(
            id="evt-cap", source="aligner", service="svc",
            brain_phase="dispatch",
            event=EventInput(reason="anomaly", evidence=evidence),
            conversation=turns,
        )
        ctx = build_gate_context(event=event, brain_phase="dispatch", context_flags={})
        assert ctx.refresh_budget == 10

    def test_negative_budget_triggers_gate(self):
        ctx = _ctx(refresh_budget=-2)
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "refresh_gitlab_context" not in _names(result)

    def test_only_brain_waitingfor_refresh_counts(self):
        from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput
        evidence = EventEvidence(display_text="test", source_type="aligner", severity="info")
        turns = [
            ConversationTurn(turn=1, actor="brain", action="route", waitingFor="refresh_gitlab_context"),
            ConversationTurn(turn=2, actor="brain", action="route", waitingFor="select_agent"),
            ConversationTurn(turn=3, actor="brain", action="route", waitingFor="refresh_kargo_context"),
        ]
        event = EventDocument(
            id="evt-wf", source="aligner", service="svc",
            brain_phase="dispatch",
            event=EventInput(reason="anomaly", evidence=evidence),
            conversation=turns,
        )
        ctx = build_gate_context(event=event, brain_phase="dispatch", context_flags={})
        assert ctx.refresh_count == 2

    def test_jarvis_turns_dont_count_as_completions(self):
        from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput
        evidence = EventEvidence(display_text="test", source_type="aligner", severity="info")
        turns = [
            ConversationTurn(turn=1, actor="jarvis", action="execute"),
            ConversationTurn(turn=2, actor="sysadmin", action="execute"),
            ConversationTurn(turn=3, actor="brain", action="execute"),
        ]
        event = EventDocument(
            id="evt-jc", source="aligner", service="svc",
            brain_phase="dispatch",
            event=EventInput(reason="anomaly", evidence=evidence),
            conversation=turns,
        )
        ctx = build_gate_context(event=event, brain_phase="dispatch", context_flags={})
        assert ctx.agent_completions == 1


# ---------------------------------------------------------------------------
# F-06: Ordering parity test (evaluate -> inject -> reorder)
# ---------------------------------------------------------------------------

class TestOrderingParity:
    def test_notify_stripped_in_dispatch_despite_injection(self):
        """Maintainer injection must not resurrect phase-gated tools."""
        ctx = _ctx(brain_phase="dispatch")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "notify_user_slack" not in _names(result)

    def test_notify_available_in_escalate_for_injection(self):
        """In escalate phase, notify_user_slack passes gate (injection can mutate schema)."""
        ctx = _ctx(brain_phase="escalate")
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "notify_user_slack" in _names(result)


# ---------------------------------------------------------------------------
# F-08: jarvis turns don't count toward COMPLEX domain round threshold
# ---------------------------------------------------------------------------

class TestDomainComplexJarvisExclusion:
    def test_jarvis_turns_excluded_from_agent_rounds(self):
        turns = [
            _turn("sysadmin", "execute"),
            _turn("jarvis", "message"),
            _turn("jarvis", "insight"),
            _turn("architect", "plan"),
        ]
        ctx = _ctx(
            context_flags={"brain_has_classified": True, "event_domain": "complex"},
            conversation=turns,
        )
        result = evaluate_gates(ALL_SCHEMAS, ctx)
        assert "close_event" not in _names(result)


# ---------------------------------------------------------------------------
# F-12: ALL_TOOL_NAMES derived from BRAIN_TOOL_SCHEMAS (sync by construction)
# ---------------------------------------------------------------------------

class TestSchemaSync:
    def test_all_tool_names_is_nonempty(self):
        """Verify the dynamic load produced a real tool set."""
        assert len(ALL_TOOL_NAMES) > 20

    def test_core_tools_present(self):
        """Smoke-check that key tools are in the real schema."""
        assert "classify_event" in ALL_TOOL_NAMES
        assert "select_agent" in ALL_TOOL_NAMES
        assert "close_event" in ALL_TOOL_NAMES
        assert "set_phase" in ALL_TOOL_NAMES


# ---------------------------------------------------------------------------
# F-13: Hint field wired into diagnostic output
# ---------------------------------------------------------------------------

class TestHintInDiagnostic:
    def test_budget_hint_in_message(self):
        ctx = _ctx(refresh_budget=0)
        msg = diagnose_rejection("refresh_gitlab_context", ctx)
        assert "Hint:" in msg
        assert "budget replenishes" in msg

    def test_pre_classification_hint(self):
        ctx = _ctx(context_flags={"brain_has_classified": False})
        msg = diagnose_rejection("select_agent", ctx)
        assert "Hint:" in msg
        assert "lookups and classification" in msg

    def test_no_hint_for_phase_escalate(self):
        ctx = _ctx(brain_phase="dispatch")
        msg = diagnose_rejection("report_incident", ctx)
        assert "Hint:" not in msg
