# src/agents/llm/prompt.py
# @ai-rules:
# 1. [Constraint]: Pure, sync function — NO async, NO Redis, NO side effects.
# 2. [Pattern]: Source-aware dispatch on subject_type + evidence context fields.
# 3. [Gotcha]: service_meta is Optional[Service] — only present for K8s deployments.
# 4. [Constraint]: Do NOT import from llm/__init__.py — this module is imported
#    directly by brain.py, not re-exported through the adapter factory.
"""Source-aware event header builder for Brain triage prompts."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import EventDocument, Service


def build_event_header(
    event: EventDocument,
    *,
    service_meta: Service | None = None,
    journal_entries: list[str] | None = None,
    related_events: list[str] | None = None,
    recent_closed: list[tuple[str, float, str]] | None = None,
    mermaid: str = "",
) -> str:
    """Build a source-aware context header for the Brain's triage prompt.

    Returns a plain-text block (newline-joined) that replaces the old
    fixed-format header in ``_build_contents``.  The output varies by
    ``event.subject_type`` and the evidence context fields present.
    """
    evidence = event.event.evidence
    from src.models import EventEvidence
    is_structured = isinstance(evidence, EventEvidence)

    lines = _build_identity_block(event, is_structured, evidence)
    lines.append("")
    lines.extend(_build_subject_block(event, is_structured, evidence, service_meta))
    lines.extend(_build_timing_block(event, is_structured, evidence))
    lines.extend(_build_related_block(related_events))
    lines.extend(_build_closed_block(recent_closed))
    lines.extend(_build_journal_block(journal_entries))
    lines.extend(_build_mermaid_block(mermaid))

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Private section builders
# ---------------------------------------------------------------------------

def _build_identity_block(
    event: EventDocument, is_structured: bool, evidence: object
) -> list[str]:
    from src.models import EventEvidence, _resolve_phase
    ev = evidence if is_structured else None
    evidence_text = ev.display_text if isinstance(ev, EventEvidence) else str(evidence)
    lines = [
        f"Event ID: {event.id}",
        f"Source: {event.source}",
        f"Status: {event.status.value}",
        f"Phase: {_resolve_phase(event.brain_phase)}",
        f"Reason: {event.event.reason}",
        f"Evidence: {evidence_text}",
        f"Time: {event.event.timeDate}",
    ]
    if isinstance(ev, EventEvidence):
        if ev.brain_domain:
            lines.append(f"Domain: {ev.brain_domain} (Brain-assessed)")
        elif ev.domain_confidence == "assessed":
            lines.append(f"Domain: {ev.domain} (source-assessed)")
        else:
            lines.append(f"Domain: DISORDER (unclassified -- you must call classify_event)")
        eff_severity = ev.brain_severity or ev.severity
        lines.append(f"Severity: {eff_severity}")
    return lines


def _build_subject_block(
    event: EventDocument,
    is_structured: bool,
    evidence: object,
    service_meta: Service | None,
) -> list[str]:
    """Render the subject-specific section based on subject_type + evidence."""
    from src.models import EventEvidence
    ev = evidence if isinstance(evidence, EventEvidence) else None
    subject_type = getattr(event, "subject_type", "service")
    lines: list[str] = []

    if subject_type == "kargo_stage" and ev and ev.kargo_context:
        kc = ev.kargo_context
        lines.append(f"Kargo Stage: {kc.get('stage', event.service)}")
        lines.append(f"  Project: {kc.get('project', '')}")
        if kc.get("promotion"):
            lines.append(f"  Promotion: {kc['promotion']}")
        if kc.get("phase"):
            lines.append(f"  Phase: {kc['phase']}")
        if kc.get("failed_step"):
            lines.append(f"  Failed Step: {kc['failed_step']}")
        if kc.get("mr_url"):
            lines.append(f"  MR: {kc['mr_url']}")

    elif subject_type == "jira" and ev and ev.jira_context:
        jc = ev.jira_context
        lines.append(f"Jira Issue: {jc.get('issue_key', event.service)}")
        if jc.get("issue_url"):
            lines.append(f"  URL: {jc['issue_url']}")
        if jc.get("summary"):
            lines.append(f"  Summary: {jc['summary']}")
        if jc.get("status"):
            lines.append(f"  Status: {jc['status']}")
        if jc.get("priority"):
            lines.append(f"  Priority: {jc['priority']}")

    elif subject_type == "system":
        lines.append(f"Subject: System-level ({event.source})")

    elif ev and ev.gitlab_context:
        gl = ev.gitlab_context
        lines.append(f"Component: {event.service}")
        lines.append(f"  Project: {gl.get('project_path', '')}")
        lines.append(f"  MR: !{gl.get('mr_iid', '')} - {gl.get('mr_title', '')}")
        lines.append(f"  MR URL: {gl.get('target_url', '')}")
        lines.append(f"  Pipeline: {gl.get('pipeline_status', 'unknown')}")
        if gl.get("pipeline_id"):
            lines.append(f"  Pipeline ID: {gl['pipeline_id']}")
        lines.append(f"  Merge Status: {gl.get('merge_status', '')}")
        lines.append(f"  Source Branch: {gl.get('source_branch', '')}")
        lines.append(f"  Author: {gl.get('author', '')}")
        maintainer = gl.get("maintainer", {})
        if maintainer:
            emails = maintainer.get("emails", [])
            if emails:
                lines.append(f"  Maintainer Emails: {', '.join(emails)}")
        mr_desc = gl.get("mr_description", "")
        if mr_desc:
            lines.append("")
            lines.append("MR Description:")
            lines.append(mr_desc)

    elif subject_type == "github_issue" and ev and getattr(ev, "github_issue_context", None):
        ic = ev.github_issue_context
        lines.append(f"GitHub Issue: #{ic.get('issue_number', '')} - {ic.get('title', '')}")
        lines.append(f"  Repo: {ic.get('owner', '')}/{ic.get('repo', '')}")
        lines.append(f"  URL: {ic.get('html_url', '')}")
        lines.append(f"  State: {ic.get('state', 'open')}")
        lines.append(f"  Author: {ic.get('author', '')}")
        if ic.get("assignees"):
            lines.append(f"  Assignees: {', '.join(ic['assignees'])}")
        if ic.get("labels"):
            lines.append(f"  Labels: {', '.join(ic['labels'])}")
        if ic.get("skill_label"):
            lines.append(f"  Skill: {ic['skill_label']}")
        body = ic.get("body", "")
        if body:
            lines.append(f"  Body (snippet): {body[:1000]}")

    elif ev and ev.github_context:
        gc = ev.github_context
        lines.append(f"Component: {event.service}")
        lines.append(f"  Repo: {gc.get('owner', '')}/{gc.get('repo', '')}")
        lines.append(f"  PR: #{gc.get('pr_number', '')} - {gc.get('pr_title', '')}")
        lines.append(f"  PR URL: {gc.get('pr_url', '')}")
        lines.append(f"  Checks: {gc.get('check_status', 'unknown')}")
        lines.append(f"  State: {gc.get('pr_state', '')}")
        if gc.get("head_branch"):
            lines.append(f"  Head Branch: {gc['head_branch']}")
        if gc.get("base_branch"):
            lines.append(f"  Base Branch: {gc['base_branch']}")
        lines.append(f"  Author: {gc.get('author', '')}")
        maintainer = gc.get("maintainer", {})
        if maintainer:
            emails = maintainer.get("emails", [])
            if emails:
                lines.append(f"  Maintainer Emails: {', '.join(emails)}")
        pr_body = gc.get("body", "")
        if pr_body:
            lines.append("")
            lines.append("PR Description:")
            lines.append(pr_body)

    elif service_meta:
        lines.append(f"Service: {service_meta.name} (K8s Deployment)")
        lines.append(f"  Version: {service_meta.version}")
        if service_meta.gitops_repo:
            lines.append(f"  GitOps Repo: {service_meta.gitops_repo}")
        if service_meta.gitops_repo_url:
            lines.append(f"  Repo URL: {service_meta.gitops_repo_url}")
        if service_meta.gitops_config_path:
            lines.append(f"  Config Path: {service_meta.gitops_config_path}")
        if service_meta.replicas_ready is not None:
            lines.append(f"  Replicas: {service_meta.replicas_ready}/{service_meta.replicas_desired}")
        lines.append(f"  CPU: {service_meta.metrics.cpu:.1f}%")
        lines.append(f"  Memory: {service_meta.metrics.memory:.1f}%")

    elif event.service in ("general", "system", ""):
        lines.append(f"Topic: {event.event.reason}")
    else:
        lines.append(f"Service: {event.service}")

    return lines


def _build_timing_block(
    event: EventDocument, is_structured: bool, evidence: object
) -> list[str]:
    import time
    lines: list[str] = []
    now = time.time()
    if event.queued_at:
        queue_age = int(now - event.queued_at)
        q_min, q_sec = divmod(queue_age, 60)
        lines.append(f"Event Created: {q_min}m {q_sec}s ago")
    if event.queued_at and event.processing_started_at:
        wait = int(event.processing_started_at - event.queued_at)
        w_min, w_sec = divmod(wait, 60)
        lines.append(f"Queue Wait: {w_min}m {w_sec}s")
    return lines


def _build_related_block(related: list[str] | None) -> list[str]:
    if not related:
        return []
    return ["", "Related Active Events (same service -- consider before acting):"] + related


def _build_closed_block(
    recent_closed: list[tuple[str, float, str]] | None,
) -> list[str]:
    if not recent_closed:
        return []
    import time
    lines = ["", "Recently Closed Events (same service, last 15 min):"]
    for cid, close_time, csummary in recent_closed:
        ago = int(time.time() - close_time)
        ago_min = ago // 60
        lines.append(f"  - {cid} (closed {ago_min}m ago): {csummary}")
    return lines


def _build_journal_block(journal: list[str] | None) -> list[str]:
    if not journal:
        return []
    last_entry = journal[-1]
    return [
        "",
        f"Service ops journal available ({len(journal)} entries). Last: {last_entry}",
        "  (Use lookup_journal for full history or other services)",
    ]


def _build_mermaid_block(mermaid: str) -> list[str]:
    if not mermaid:
        return []
    return ["", "Architecture Diagram (Mermaid):", mermaid]
