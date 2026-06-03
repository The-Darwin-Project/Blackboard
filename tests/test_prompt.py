# tests/test_prompt.py
# @ai-rules:
# 1. [Constraint]: Pure function tests — build_event_header is sync, no mocking needed.
# 2. [Pattern]: One fixture per source type (kargo, headhunter, jarvis, aligner, chat, slack).
# 3. [Gotcha]: EventDocument requires source Literal — use valid values from the enum.
"""Tests for source-aware build_event_header() in llm/prompt.py."""
from __future__ import annotations

import pytest

from src.agents.llm.prompt import build_event_header
from src.models import (
    EventDocument,
    EventEvidence,
    EventInput,
    Metrics,
    Service,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _evidence(
    *,
    source_type: str = "chat",
    display_text: str = "test evidence",
    domain: str = "complicated",
    severity: str = "info",
    domain_confidence: str = "assessed",
    gitlab_context: dict | None = None,
    kargo_context: dict | None = None,
    jira_context: dict | None = None,
) -> EventEvidence:
    return EventEvidence(
        display_text=display_text,
        source_type=source_type,
        domain=domain,
        severity=severity,
        domain_confidence=domain_confidence,
        gitlab_context=gitlab_context,
        kargo_context=kargo_context,
        jira_context=jira_context,
    )


def _event(
    *,
    source: str = "chat",
    service: str = "general",
    subject_type: str = "service",
    reason: str = "test request",
    evidence: EventEvidence | None = None,
) -> EventDocument:
    ev = evidence or _evidence(source_type=source)
    return EventDocument(
        source=source,
        service=service,
        subject_type=subject_type,
        event=EventInput(reason=reason, evidence=ev),
    )


def _service_meta(name: str = "darwin-store") -> Service:
    return Service(
        name=name,
        version="1.2.3",
        metrics=Metrics(cpu=12.4, memory=45.6),
        gitops_repo="org/darwin-store",
        gitops_repo_url="https://github.com/org/darwin-store",
        replicas_ready=3,
        replicas_desired=3,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestKargoEvent:
    def test_kargo_header_shows_stage(self):
        ev = _event(
            source="headhunter",
            service="verify@my-project",
            subject_type="kargo_stage",
            evidence=_evidence(
                source_type="headhunter",
                kargo_context={
                    "stage": "verify",
                    "project": "my-project",
                    "promotion": "promo-abc",
                    "phase": "Failed",
                    "failed_step": "verification",
                    "mr_url": "https://gitlab.example.com/mr/1",
                },
            ),
        )
        header = build_event_header(ev)
        assert "Kargo Stage: verify" in header
        assert "Project: my-project" in header
        assert "Promotion: promo-abc" in header
        assert "Service:" not in header

    def test_kargo_no_service_metadata(self):
        ev = _event(
            source="headhunter",
            service="verify@my-project",
            subject_type="kargo_stage",
            evidence=_evidence(
                source_type="headhunter",
                kargo_context={"stage": "verify", "project": "my-project"},
            ),
        )
        header = build_event_header(ev, service_meta=_service_meta())
        assert "Service:" not in header
        assert "CPU:" not in header


    def test_kargo_via_aligner_source(self):
        """Kargo events arrive via source=aligner in production."""
        ev = _event(
            source="aligner",
            service="kubevirt-v4.16@kargo-kubevirt-v4-16",
            subject_type="kargo_stage",
            evidence=_evidence(
                source_type="aligner",
                kargo_context={
                    "stage": "kubevirt-v4.16",
                    "project": "kargo-kubevirt-v4-16",
                    "promotion": "promo-xyz",
                    "phase": "Errored",
                    "failed_step": "wait-for-merge",
                },
            ),
        )
        header = build_event_header(ev)
        assert "Kargo Stage: kubevirt-v4.16" in header
        assert "Project: kargo-kubevirt-v4-16" in header
        assert "Service:" not in header


class TestHeadhunterGitLabEvent:
    def test_gitlab_context_shows_component(self):
        ev = _event(
            source="headhunter",
            service="release-console",
            subject_type="service",
            evidence=_evidence(
                source_type="headhunter",
                gitlab_context={
                    "project_path": "org/release-console",
                    "mr_iid": 42,
                    "mr_title": "Bump version",
                    "target_url": "https://gitlab.example.com/mr/42",
                    "pipeline_status": "success",
                    "merge_status": "can_be_merged",
                    "source_branch": "feature/bump",
                    "author": "bot",
                },
            ),
        )
        header = build_event_header(ev)
        assert "Component: release-console" in header
        assert "MR: !42" in header
        assert "Service:" not in header


class TestJarvisEvent:
    def test_system_level_header(self):
        ev = _event(
            source="jarvis",
            service="system",
            subject_type="system",
        )
        header = build_event_header(ev)
        assert "Subject: System-level (jarvis)" in header
        assert "Service:" not in header


class TestAlignerMetricsEvent:
    def test_service_with_k8s_metadata(self):
        ev = _event(
            source="aligner",
            service="darwin-store",
            subject_type="service",
            evidence=_evidence(source_type="aligner", severity="warning"),
        )
        svc = _service_meta("darwin-store")
        header = build_event_header(ev, service_meta=svc)
        assert "Service: darwin-store (K8s Deployment)" in header
        assert "CPU: 12.4%" in header
        assert "Memory: 45.6%" in header
        assert "Replicas: 3/3" in header

    def test_aligner_no_registry_preserves_service_name(self):
        """When get_service returns None (registry not populated), show Service: name."""
        ev = _event(
            source="aligner",
            service="darwin-store",
            subject_type="service",
            evidence=_evidence(source_type="aligner", severity="warning"),
        )
        header = build_event_header(ev, service_meta=None)
        assert "Service: darwin-store" in header
        assert "Topic:" not in header


class TestChatGeneralEvent:
    def test_general_shows_topic(self):
        ev = _event(
            source="chat",
            service="general",
            subject_type="service",
            reason="How do I deploy?",
        )
        header = build_event_header(ev)
        assert "Topic: How do I deploy?" in header
        assert "Service:" not in header

    def test_no_service_metadata_noise(self):
        ev = _event(source="chat", service="general")
        header = build_event_header(ev)
        assert "Not found" not in header
        assert "Known services" not in header


class TestSlackEvent:
    def test_slack_specific_service_no_k8s(self):
        """Slack event targeting a named service that has no K8s match preserves name."""
        ev = _event(
            source="slack",
            service="my-custom-tool",
            subject_type="service",
            reason="Check my-custom-tool logs",
        )
        header = build_event_header(ev)
        assert "Service: my-custom-tool" in header
        assert "Topic:" not in header

    def test_slack_general_shows_topic(self):
        """Slack /darwin command with service=general shows Topic."""
        ev = _event(
            source="slack",
            service="general",
            subject_type="service",
            reason="What happened last night?",
        )
        header = build_event_header(ev)
        assert "Topic: What happened last night?" in header
        assert "Service:" not in header


class TestJiraEvent:
    def test_jira_header_shows_issue(self):
        ev = _event(
            source="headhunter",
            service="CNV-12345",
            subject_type="jira",
            evidence=_evidence(
                source_type="headhunter",
                jira_context={
                    "issue_key": "CNV-12345",
                    "issue_url": "https://issues.redhat.com/browse/CNV-12345",
                    "summary": "Fix broken pipeline",
                    "status": "In Progress",
                    "priority": "Major",
                },
            ),
        )
        header = build_event_header(ev)
        assert "Jira Issue: CNV-12345" in header
        assert "Summary: Fix broken pipeline" in header
        assert "Service:" not in header


class TestSharedSections:
    def test_related_events_rendered(self):
        ev = _event(source="chat", service="general")
        related = ["  - evt-abc (chat): some other event"]
        header = build_event_header(ev, related_events=related)
        assert "Related Active Events" in header
        assert "evt-abc" in header

    def test_journal_hint_rendered(self):
        ev = _event(source="chat", service="general")
        journal = ["entry-1", "entry-2"]
        header = build_event_header(ev, journal_entries=journal)
        assert "Service ops journal available (2 entries)" in header
        assert "Last: entry-2" in header

    def test_mermaid_rendered(self):
        ev = _event(source="chat", service="general")
        header = build_event_header(ev, mermaid="graph LR\n  A-->B")
        assert "Architecture Diagram (Mermaid):" in header
        assert "A-->B" in header

    def test_domain_disorder_label(self):
        ev = _event(
            source="chat",
            service="general",
            evidence=_evidence(domain_confidence="default"),
        )
        header = build_event_header(ev)
        assert "DISORDER (unclassified" in header
