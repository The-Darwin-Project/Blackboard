# BlackBoard/src/utils/event_markdown.py
# @ai-rules:
# 1. [Constraint]: No imports from src/agents/ or src/state/ -- standalone utility.
# 2. [Pattern]: Extracted from Brain._event_to_markdown (staticmethod). Called by brain.py,
#    blackboard.py, routes/queue.py, routes/events.py.
# 3. [Constraint]: Only depends on src/models (EventDocument, EventEvidence, CIAnalysis) + stdlib.
# 4. [Constraint]: THIS MODULE IS THE HTML-ESCAPE BOUNDARY. The UI renders this markdown
#    with rehype-raw and no separate sanitizer, so every value sourced from an external
#    system (GitLab/GitHub/Kargo webhook payloads, Jenkins job data, LLM-generated
#    triage/analysis narrative) MUST be passed through _esc() at the point it is
#    interpolated into `lines`, uniformly, regardless of what the producer already did to
#    it. Producers (e.g. jenkins_observer.py) intentionally do NOT html-escape these
#    fields -- that text also flows unescaped into non-HTML sinks (EventEvidence.display_text,
#    Slack, the Brain/FRIDAY prompt) and escaping it at the producer double-encodes/garbles
#    those sinks. Do not remove _esc() calls to "avoid double escaping" -- there is exactly
#    one escape, and it lives here.
# 5. [Pattern]: ci_context (and its optional "analysis" narrative sub-object, see
#    models.CIAnalysis) is a free-form dict, redacted/capped/newline-stripped upstream by
#    jenkins_observer.py but NOT html-escaped there -- render with .get() defaults for
#    ci_context itself, but reconstruct "analysis" through CIAnalysis(**an) rather than raw
#    dict.get() field-name literals, so a future CIAnalysis field rename fails loudly here
#    instead of silently rendering a stale/empty section. Gate rendering on
#    analysis_obj.summary (not dict truthiness) -- a validated-but-blank analysis dict is
#    still a non-empty dict.
"""Event-to-Markdown converter for Darwin event documents."""
from __future__ import annotations

import html
from datetime import datetime, timezone

from ..models import CIAnalysis, EventDocument, EventEvidence

_MD_SUBJECT_LABEL = {
    "kargo_stage": "Stage",
    "system": "Subject",
    "jira": "Jira Issue",
    "github_issue": "GitHub Issue",
    "ci_gating": "CI Gating",
}


def _esc(value: object) -> str:
    """HTML-escape a single externally/LLM-derived value at the markdown render
    boundary (see @ai-rules #4 above). The sole escape point for this module."""
    if value is None:
        return ""
    return html.escape(str(value))


def _esc_join(values, sep: str = ", ") -> str:
    """Escape each item then join -- avoids escaping the separator itself."""
    return sep.join(_esc(v) for v in values)


def event_to_markdown(event: EventDocument, service_meta=None, mermaid: str = "") -> str:
    """Convert event document to readable Markdown, enriched with service metadata and topology."""
    evidence = event.event.evidence
    subject_type = getattr(event, "subject_type", "service")
    if subject_type != "service":
        subj_label = _MD_SUBJECT_LABEL.get(subject_type, "Service")
    elif isinstance(evidence, EventEvidence) and (evidence.gitlab_context or evidence.github_context or getattr(evidence, "github_issue_context", None)):
        subj_label = "Component"
    elif event.service in ("general", "system", ""):
        subj_label = "Topic"
    else:
        subj_label = "Service"
    lines = [
        f"# Event: {event.id}",
        f"",
        f"- **Source:** {event.source}",
        f"- **{subj_label}:** {event.service}",
        f"- **Status:** {event.status.value}",
        f"- **Reason:** {event.event.reason}",
    ]
    if isinstance(evidence, EventEvidence):
        lines.append(f"- **Evidence:** {_esc(evidence.display_text)}")
        lines.append(f"- **Domain:** {evidence.brain_domain or evidence.domain}")
        lines.append(f"- **Severity:** {evidence.brain_severity or evidence.severity}")
        if evidence.gitlab_context:
            gl = evidence.gitlab_context
            lines.append(f"")
            lines.append(f"## GitLab Context")
            lines.append(f"- **Project ID:** {_esc(gl.get('project_id', ''))}")
            lines.append(f"- **Project Path:** {_esc(gl.get('project_path', ''))}")
            lines.append(f"- **MR IID:** !{_esc(gl.get('mr_iid', ''))}")
            lines.append(f"- **MR Title:** {_esc(gl.get('mr_title', ''))}")
            lines.append(f"- **MR URL:** {_esc(gl.get('target_url', ''))}")
            lines.append(f"- **Action:** {_esc(gl.get('action_name', ''))}")
            lines.append(f"- **Pipeline:** {_esc(gl.get('pipeline_status', 'unknown'))}")
            if gl.get("pipeline_id"):
                lines.append(f"- **Pipeline ID:** {_esc(gl['pipeline_id'])}")
            lines.append(f"- **Merge Status:** {_esc(gl.get('merge_status', ''))}")
            lines.append(f"- **Source Branch:** {_esc(gl.get('source_branch', ''))}")
            lines.append(f"- **Target Branch:** {_esc(gl.get('target_branch', ''))}")
            lines.append(f"- **Author:** {_esc(gl.get('author', ''))}")
            maintainer = gl.get("maintainer", {})
            if maintainer:
                emails = maintainer.get("emails", [])
                lines.append(f"- **Maintainer Emails:** {_esc_join(emails) if emails else 'none'}")
                lines.append(f"- **Maintainer Source:** {_esc(maintainer.get('source', ''))}")
        if evidence.kargo_context:
            kc = evidence.kargo_context
            lines.append("")
            lines.append("## Kargo Context")
            lines.append(f"- **Project:** {_esc(kc.get('project', ''))}")
            lines.append(f"- **Stage:** {_esc(kc.get('stage', ''))}")
            lines.append(f"- **Promotion:** {_esc(kc.get('promotion', ''))}")
            lines.append(f"- **Freight:** {_esc((kc.get('freight') or '')[:12])}...")
            lines.append(f"- **Phase:** {_esc(kc.get('phase', ''))}")
            lines.append(f"- **Failed Step:** {_esc(kc.get('failed_step', 'N/A'))}")
            lines.append(f"- **Error:** {_esc(kc.get('message', ''))}")
            if kc.get("mr_url"):
                lines.append(f"- **MR URL:** {_esc(kc['mr_url'])}")
            lines.append(f"- **Started:** {_esc(kc.get('started_at', ''))}")
            lines.append(f"- **Finished:** {_esc(kc.get('finished_at', ''))}")
        if evidence.github_context:
            gc = evidence.github_context
            lines.append("")
            lines.append("## GitHub Context")
            lines.append(f"- **Repo:** {_esc(gc.get('owner', ''))}/{_esc(gc.get('repo', ''))}")
            lines.append(f"- **PR:** #{_esc(gc.get('pr_number', ''))} - {_esc(gc.get('pr_title', ''))}")
            lines.append(f"- **PR URL:** {_esc(gc.get('pr_url', ''))}")
            lines.append(f"- **Action:** {_esc(gc.get('action', ''))}")
            lines.append(f"- **Checks:** {_esc(gc.get('check_status', 'unknown'))}")
            lines.append(f"- **State:** {_esc(gc.get('pr_state', ''))}")
            if gc.get("head_branch"):
                lines.append(f"- **Head Branch:** {_esc(gc['head_branch'])}")
            if gc.get("base_branch"):
                lines.append(f"- **Base Branch:** {_esc(gc['base_branch'])}")
            lines.append(f"- **Author:** {_esc(gc.get('author', ''))}")
            if gc.get("head_sha"):
                lines.append(f"- **Head SHA:** {_esc(gc['head_sha'][:12])}")
            if gc.get("check_run_url"):
                lines.append(f"- **Check Run:** {_esc(gc['check_run_url'])}")
            maintainer = gc.get("maintainer", {})
            if maintainer:
                emails = maintainer.get("emails", [])
                lines.append(f"- **Maintainer Emails:** {_esc_join(emails) if emails else 'none'}")
                lines.append(f"- **Maintainer Source:** {_esc(maintainer.get('source', ''))}")
        issue_ctx = getattr(evidence, "github_issue_context", None)
        if issue_ctx:
            lines.append("")
            lines.append("## GitHub Issue Context")
            lines.append(f"- **Repo:** {_esc(issue_ctx.get('owner', ''))}/{_esc(issue_ctx.get('repo', ''))}")
            lines.append(f"- **Issue:** #{_esc(issue_ctx.get('issue_number', ''))} - {_esc(issue_ctx.get('title', ''))}")
            lines.append(f"- **URL:** {_esc(issue_ctx.get('html_url', ''))}")
            lines.append(f"- **State:** {_esc(issue_ctx.get('state', 'open'))}")
            lines.append(f"- **Author:** {_esc(issue_ctx.get('author', ''))}")
            if issue_ctx.get("assignees"):
                lines.append(f"- **Assignees:** {_esc_join(issue_ctx['assignees'])}")
            if issue_ctx.get("labels"):
                lines.append(f"- **Labels:** {_esc_join(issue_ctx['labels'])}")
            if issue_ctx.get("skill_label"):
                lines.append(f"- **Skill:** {_esc(issue_ctx['skill_label'])}")
            body = issue_ctx.get("body", "")
            if body:
                lines.append(f"- **Body (truncated):** {_esc(body[:300])}")
        if evidence.ci_context:
            cc = evidence.ci_context
            lines.append("")
            lines.append("## CI Gating Analysis")
            lines.append(f"- **CNV Version:** {_esc(cc.get('cnv_version', ''))}")
            lines.append(f"- **Jenkins:** {_esc(cc.get('jenkins_url', ''))}")
            for j in (cc.get("failed_jobs") or [])[:10]:
                lines.append(
                    f"- **Failed:** {_esc(j.get('job_name', ''))} #{_esc(j.get('build_number', '?'))} "
                    f"[{_esc(j.get('result', '?'))}]"
                )
            for j in (cc.get("missing_jobs") or [])[:10]:
                lines.append(f"- **Missing:** {_esc(j.get('job_name', ''))}")
            an = cc.get("analysis")
            analysis_obj = None
            if isinstance(an, dict):
                try:
                    analysis_obj = CIAnalysis(**an)
                except (TypeError, ValueError):
                    analysis_obj = None
            if analysis_obj and analysis_obj.summary:
                lines.append("")
                lines.append("### Failure Analysis")
                lines.append(f"- **Summary:** {_esc(analysis_obj.summary)}")
                lines.append(f"- **Probable Cause:** {_esc(analysis_obj.probable_cause)}")
                lines.append(f"- **Suggested Next Step:** {_esc(analysis_obj.suggested_next_step)}")
                lines.append(f"- **Confidence:** {analysis_obj.confidence}")
                for s in analysis_obj.signals[:10]:
                    lines.append(f"  - {_esc(s)}")
            for t in (cc.get("llm_triage") or [])[:5]:
                lines.append(
                    f"- **Triage:** {_esc(t.get('job_name', ''))} → {_esc(t.get('classification', ''))} "
                    f"({_esc(t.get('confidence', ''))}) · {_esc(t.get('recommended_action', ''))}"
                )
            maintainer = cc.get("maintainer") or {}
            if maintainer.get("emails"):
                lines.append(f"- **Maintainer Emails:** {_esc_join(maintainer['emails'])}")
    else:
        lines.append(f"- **Evidence:** {evidence}")
    lines.append(f"- **Time:** {event.event.timeDate}")

    if mermaid:
        lines.append(f"")
        lines.append(f"## Architecture Diagram")
        lines.append(f"```mermaid")
        lines.append(mermaid)
        lines.append(f"```")

    if service_meta:
        lines.append(f"")
        lines.append(f"## Service Metadata")
        lines.append(f"- **Version:** {service_meta.version}")
        if service_meta.gitops_repo:
            lines.append(f"- **GitOps Repo:** {service_meta.gitops_repo}")
        if service_meta.gitops_repo_url:
            lines.append(f"- **Repo URL:** {service_meta.gitops_repo_url}")
        if service_meta.gitops_config_path:
            lines.append(f"- **Config Path:** {service_meta.gitops_config_path}")
        if service_meta.replicas_ready is not None:
            lines.append(f"- **Replicas:** {service_meta.replicas_ready}/{service_meta.replicas_desired}")
        lines.append(f"- **Health:** {service_meta.health_status or 'unknown'}")
        lines.append(f"- **Sync:** {service_meta.sync_status or 'unknown'}")
        lines.append(f"- **App:** {service_meta.argocd_app or '?'}")

    lines.extend([
        f"",
        f"## Conversation",
        f"",
    ])
    prev_ts = event.conversation[0].timestamp if event.conversation else 0
    for turn in event.conversation:
        if turn.actor == "dispatcher" and turn.action in ("acknowledge", "connected"):
            continue
        ts_str = datetime.fromtimestamp(turn.timestamp, tz=timezone.utc).strftime('%H:%M:%S')
        delta = int(turn.timestamp - prev_ts)
        delta_label = f"+{delta // 60}m {delta % 60}s" if delta > 0 else "+0s"
        display_actor = {"brain": "FRIDAY", "jarvis": "JARVIS"}.get(turn.actor, turn.actor)
        if turn.actor == "user" and getattr(turn, "source", None) == "automated":
            display_actor = "System"
        lines.append(f"### Turn {turn.turn} - {display_actor} ({turn.action}) [{ts_str}] ({delta_label})")
        prev_ts = turn.timestamp
        if turn.actor == "user" and turn.source == "automated":
            if turn.thoughts:
                lines.append(f"**System Nudge:** {turn.thoughts}")
        elif turn.actor == "user" or turn.action == "message":
            user_text = turn.thoughts or turn.result or ""
            if user_text:
                lines.append(f"**Message:** {user_text}")
        elif turn.action == "respond_jarvis":
            if turn.thoughts:
                lines.append(f"**Message to JARVIS:** {turn.thoughts}")
        elif turn.action in ("think", "thoughts", "intermediate"):
            if turn.thoughts:
                lines.append(f"**Internal:** {turn.thoughts}")
        elif turn.action == "response":
            if turn.thoughts:
                lines.append(f"**FRIDAY:** {turn.thoughts}")
        elif turn.action == "tool_result":
            evidence_text = turn.result or turn.thoughts or ""
            if evidence_text:
                lines.append(f"**Evidence:** {evidence_text}")
        else:
            if turn.thoughts:
                lines.append(f"**Thoughts:** {turn.thoughts}")
            if turn.result:
                lines.append(f"**Result:** {turn.result}")
        if turn.plan:
            lines.append(f"**Plan:**\n{turn.plan}")
        if turn.evidence:
            lines.append(f"**Evidence:** {turn.evidence}")
        if turn.selectedAgents:
            lines.append(f"**Selected Agents:** {', '.join(turn.selectedAgents)}")
        if turn.executed is not None:
            lines.append(f"**Executed:** {turn.executed}")
        if turn.pendingApproval:
            lines.append(f"**Pending Approval:** YES")
        if turn.waitingFor:
            lines.append(f"**Waiting For:** {turn.waitingFor}")
        lines.append("")

    return "\n".join(lines)
