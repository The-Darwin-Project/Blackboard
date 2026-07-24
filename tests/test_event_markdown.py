# tests/test_event_markdown.py
# @ai-rules:
# 1. [Constraint]: Pure function tests only -- Brain._event_to_markdown is a @staticmethod, no instance needed.
# 2. [Pattern]: Constructs minimal EventDocument + ConversationTurn, asserts on markdown output labels.
"""Tests for actor-aware label rendering in Brain._event_to_markdown."""
from __future__ import annotations

from src.agents.brain import Brain
from src.models import ConversationTurn, EventDocument, EventEvidence, EventInput, Service


def _make_event(*turns: ConversationTurn) -> EventDocument:
    return EventDocument(
        source="chat",
        service="test-service",
        event=EventInput(reason="test", evidence="test evidence"),
        conversation=list(turns),
    )


def _make_turn(**kwargs) -> ConversationTurn:
    defaults = {"turn": 1, "actor": "brain", "action": "think", "timestamp": 1714500000.0}
    defaults.update(kwargs)
    return ConversationTurn(**defaults)


def test_user_turn_renders_message_label():
    """User turn must render **Message:** not **Thoughts:**."""
    turn = _make_turn(actor="user", action="message", thoughts="Hello from user")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Message:** Hello from user" in md
    assert "**Thoughts:**" not in md


def test_user_turn_falls_back_to_result():
    """User turn with no thoughts falls back to result field."""
    turn = _make_turn(actor="user", action="message", thoughts=None, result="fallback text")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Message:** fallback text" in md


def test_brain_think_renders_internal_label():
    """Legacy brain.think renders **Internal:** label (backward compat)."""
    turn = _make_turn(actor="brain", action="think", thoughts="Analyzing the situation")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Internal:** Analyzing the situation" in md


def test_brain_thoughts_renders_internal_label():
    """brain.thoughts renders **Internal:** label."""
    turn = _make_turn(actor="brain", action="thoughts", thoughts="Reasoning about options")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Internal:** Reasoning about options" in md


def test_brain_response_renders_friday_label():
    """brain.response renders **FRIDAY:** label."""
    turn = _make_turn(actor="brain", action="response", thoughts="Here is your answer")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**FRIDAY:** Here is your answer" in md


def test_tool_result_renders_evidence_label():
    """tool_result action must render **Evidence:** from result field."""
    turn = _make_turn(actor="brain", action="tool_result", result="service is healthy")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Evidence:** service is healthy" in md
    assert "**Thoughts:**" not in md


def test_non_user_fields_preserved():
    """plan, evidence, selectedAgents, waitingFor still render for non-user turns."""
    turn = _make_turn(
        actor="brain",
        action="route",
        thoughts="Routing to developer",
        plan="## Step 1\nDo something",
        selectedAgents=["developer"],
        waitingFor="agent",
    )
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Thoughts:** Routing to developer" in md
    assert "**Plan:**" in md
    assert "**Selected Agents:** developer" in md
    assert "**Waiting For:** agent" in md


def test_user_turn_does_not_render_extra_fields():
    """User turn should only render Message, not Thoughts or Result separately."""
    turn = _make_turn(actor="user", action="message", thoughts="user msg", result="should not appear")
    md = Brain._event_to_markdown(_make_event(turn))
    assert "**Message:** user msg" in md
    assert "**Result:**" not in md


# ---------------------------------------------------------------------------
# Source-aware subject label tests
# ---------------------------------------------------------------------------

def _make_typed_event(
    *, source="chat", service="test", subject_type="service",
    gitlab_context=None, kargo_context=None, jira_context=None,
):
    evidence = EventEvidence(
        display_text="test", source_type=source, severity="info",
        domain_confidence="assessed",
        gitlab_context=gitlab_context,
        kargo_context=kargo_context,
        jira_context=jira_context,
    )
    return EventDocument(
        source=source, service=service, subject_type=subject_type,
        event=EventInput(reason="test", evidence=evidence),
    )


def test_kargo_stage_label():
    ev = _make_typed_event(
        source="aligner", service="kubevirt-v4.16@kargo-kubevirt-v4-16",
        subject_type="kargo_stage",
        kargo_context={"stage": "kubevirt-v4.16", "project": "kargo-kubevirt-v4-16"},
    )
    md = Brain._event_to_markdown(ev)
    assert "**Stage:** kubevirt-v4.16@kargo-kubevirt-v4-16" in md
    assert "**Service:**" not in md


def test_headhunter_gitlab_component_label():
    ev = _make_typed_event(
        source="headhunter", service="kubevirt-plugin",
        gitlab_context={"project_path": "org/kubevirt-plugin", "mr_iid": 541},
    )
    md = Brain._event_to_markdown(ev)
    assert "**Component:** kubevirt-plugin" in md
    assert "**Service:**" not in md


def test_jarvis_system_label():
    ev = _make_typed_event(
        source="jarvis", service="system", subject_type="system",
    )
    md = Brain._event_to_markdown(ev)
    assert "**Subject:** system" in md
    assert "**Service:**" not in md


def test_chat_general_topic_label():
    ev = _make_typed_event(source="chat", service="general")
    md = Brain._event_to_markdown(ev)
    assert "**Topic:** general" in md
    assert "**Service:**" not in md


def test_aligner_service_default_label():
    ev = _make_typed_event(source="aligner", service="darwin-store")
    md = Brain._event_to_markdown(ev)
    assert "**Service:** darwin-store" in md


# ---------------------------------------------------------------------------
# Service metadata rendering (ArgoCD health/sync, not CPU/Memory)
# ---------------------------------------------------------------------------

def test_service_metadata_renders_health_and_sync():
    """service_meta block renders Health/Sync/App, not the old CPU/Memory/Error Rate."""
    ev = _make_typed_event(source="aligner", service="darwin-store")
    svc = Service(
        name="darwin-store",
        version="1.2.3",
        health_status="Degraded",
        sync_status="OutOfSync",
        argocd_app="openshift-gitops/darwin-store",
    )
    md = Brain._event_to_markdown(ev, service_meta=svc)
    assert "**Health:** Degraded" in md
    assert "**Sync:** OutOfSync" in md
    assert "**App:** openshift-gitops/darwin-store" in md
    assert "**CPU:**" not in md
    assert "**Memory:**" not in md
    assert "**Error Rate:**" not in md


def test_service_metadata_defaults_to_unknown():
    """Missing health/sync fields (old Redis data) render as 'unknown', not a crash."""
    ev = _make_typed_event(source="aligner", service="darwin-store")
    svc = Service(name="darwin-store", version="1.0.0")
    md = Brain._event_to_markdown(ev, service_meta=svc)
    assert "**Health:** unknown" in md
    assert "**Sync:** unknown" in md
    assert "**App:** ?" in md
