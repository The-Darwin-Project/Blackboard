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


# ---------------------------------------------------------------------------
# ci_context / CI Gating Analysis rendering (Phase 1 verbose evidence)
# ---------------------------------------------------------------------------

def _make_ci_gating_event(ci_context):
    evidence = EventEvidence(
        display_text="CNV 4.23: 1 failed CI gating job(s)",
        source_type="aligner",
        severity="warning",
        domain_confidence="default",
        ci_context=ci_context,
    )
    return EventDocument(
        source="aligner", service="verify-cnv-4.23.z-build-tier1|4.23",
        subject_type="ci_gating",
        event=EventInput(reason="CI gating failure", evidence=evidence),
    )


def test_no_ci_context_renders_no_ci_gating_section():
    """Zero-state: evidence.ci_context is None -> no '## CI Gating Analysis' block."""
    ev = _make_typed_event(source="aligner", service="darwin-store")
    md = Brain._event_to_markdown(ev)
    assert "## CI Gating Analysis" not in md


def test_ci_context_renders_failed_and_missing_jobs():
    event = _make_ci_gating_event({
        "cnv_version": "4.23",
        "jenkins_url": "https://jenkins.example.com",
        "failed_jobs": [{"job_name": "verify-cnv-4.23.z-build-tier1", "build_number": 42, "result": "FAILURE"}],
        "missing_jobs": [{"job_name": "verify-cnv-4.23.z-build-tier2"}],
        "llm_triage": [],
    })
    md = Brain._event_to_markdown(event)
    assert "## CI Gating Analysis" in md
    assert "- **CNV Version:** 4.23" in md
    assert "- **Jenkins:** https://jenkins.example.com" in md
    assert "- **Failed:** verify-cnv-4.23.z-build-tier1 #42 [FAILURE]" in md
    assert "- **Missing:** verify-cnv-4.23.z-build-tier2" in md


def test_ci_context_without_analysis_omits_failure_analysis_section():
    """No 'analysis' key in ci_context (old events, or analysis disabled) -> no
    '### Failure Analysis' sub-section, but the rest of the block still renders."""
    event = _make_ci_gating_event({
        "cnv_version": "4.23",
        "jenkins_url": "https://jenkins.example.com",
        "failed_jobs": [],
        "missing_jobs": [],
        "llm_triage": [],
    })
    md = Brain._event_to_markdown(event)
    assert "## CI Gating Analysis" in md
    assert "### Failure Analysis" not in md


def test_ci_context_analysis_renders_narrative_fields():
    event = _make_ci_gating_event({
        "cnv_version": "4.23",
        "jenkins_url": "https://jenkins.example.com",
        "failed_jobs": [],
        "missing_jobs": [],
        "llm_triage": [],
        "analysis": {
            "summary": "Tier1 network suite failed due to a flaky NIC driver.",
            "probable_cause": "Known infra flake on worker node pool.",
            "suggested_next_step": "Restart the job.",
            "signals": ["dial tcp: connection refused"],
            "confidence": 0.8,
        },
    })
    md = Brain._event_to_markdown(event)
    assert "### Failure Analysis" in md
    assert "- **Summary:** Tier1 network suite failed due to a flaky NIC driver." in md
    assert "- **Probable Cause:** Known infra flake on worker node pool." in md
    assert "- **Suggested Next Step:** Restart the job." in md
    assert "- **Confidence:** 0.8" in md
    assert "  - dial tcp: connection refused" in md


def test_ci_context_analysis_empty_dict_omits_failure_analysis_section():
    """PR #228 codereview MEDIUM finding: a validated-but-blank analysis dict
    (all fields default/empty) is still a non-empty, truthy dict -- rendering
    must gate on a populated field (summary), not dict truthiness, or the event
    report shows an empty '### Failure Analysis' sub-section."""
    event = _make_ci_gating_event({
        "cnv_version": "4.23",
        "jenkins_url": "https://jenkins.example.com",
        "failed_jobs": [],
        "missing_jobs": [],
        "llm_triage": [],
        "analysis": {
            "summary": "",
            "probable_cause": "",
            "suggested_next_step": "",
            "signals": [],
            "confidence": 0.0,
        },
    })
    md = Brain._event_to_markdown(event)
    assert "### Failure Analysis" not in md


def test_ci_context_analysis_malformed_does_not_raise():
    """A malformed ci_context.analysis must degrade safely instead of raising
    out of markdown rendering (e.g. a legacy record or a future producer that
    skips jenkins_observer.py::_validate_analysis)."""
    event = _make_ci_gating_event({
        "cnv_version": "4.23",
        "jenkins_url": "https://jenkins.example.com",
        "failed_jobs": [],
        "missing_jobs": [],
        "llm_triage": [],
        "analysis": "not a dict",
    })
    md = Brain._event_to_markdown(event)
    assert "### Failure Analysis" not in md


def test_ci_context_renders_triage_and_maintainer():
    event = _make_ci_gating_event({
        "cnv_version": "4.23",
        "jenkins_url": "https://jenkins.example.com",
        "failed_jobs": [],
        "missing_jobs": [],
        "llm_triage": [
            {"job_name": "tier1", "classification": "infrastructure", "confidence": 0.9, "recommended_action": "restart"},
        ],
        "maintainer": {"source": "static", "emails": ["alice@example.com"]},
    })
    md = Brain._event_to_markdown(event)
    assert "- **Triage:** tier1 → infrastructure (0.9) · restart" in md
    assert "- **Maintainer Emails:** alice@example.com" in md
