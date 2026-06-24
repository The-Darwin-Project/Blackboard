# BlackBoard/src/utils/event_markdown.py
# @ai-rules:
# 1. [Constraint]: No imports from src/agents/ or src/state/ -- standalone utility.
# 2. [Pattern]: Extracted from Brain._event_to_markdown (staticmethod). Called by brain.py,
#    blackboard.py, routes/queue.py, routes/events.py.
# 3. [Constraint]: Only depends on src/models (EventDocument, EventEvidence) + stdlib.
"""Event-to-Markdown converter for Darwin event documents."""
from __future__ import annotations

from datetime import datetime, timezone

from ..models import EventDocument, EventEvidence

_MD_SUBJECT_LABEL = {
    "kargo_stage": "Stage",
    "system": "Subject",
    "jira": "Jira Issue",
}


def event_to_markdown(event: EventDocument, service_meta=None, mermaid: str = "") -> str:
    """Convert event document to readable Markdown, enriched with service metadata and topology."""
    evidence = event.event.evidence
    subject_type = getattr(event, "subject_type", "service")
    if subject_type != "service":
        subj_label = _MD_SUBJECT_LABEL.get(subject_type, "Service")
    elif isinstance(evidence, EventEvidence) and evidence.gitlab_context:
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
        lines.append(f"- **Evidence:** {evidence.display_text}")
        lines.append(f"- **Domain:** {evidence.brain_domain or evidence.domain}")
        lines.append(f"- **Severity:** {evidence.brain_severity or evidence.severity}")
        if evidence.gitlab_context:
            gl = evidence.gitlab_context
            lines.append(f"")
            lines.append(f"## GitLab Context")
            lines.append(f"- **Project ID:** {gl.get('project_id', '')}")
            lines.append(f"- **Project Path:** {gl.get('project_path', '')}")
            lines.append(f"- **MR IID:** !{gl.get('mr_iid', '')}")
            lines.append(f"- **MR Title:** {gl.get('mr_title', '')}")
            lines.append(f"- **MR URL:** {gl.get('target_url', '')}")
            lines.append(f"- **Action:** {gl.get('action_name', '')}")
            lines.append(f"- **Pipeline:** {gl.get('pipeline_status', 'unknown')}")
            if gl.get("pipeline_id"):
                lines.append(f"- **Pipeline ID:** {gl['pipeline_id']}")
            lines.append(f"- **Merge Status:** {gl.get('merge_status', '')}")
            lines.append(f"- **Source Branch:** {gl.get('source_branch', '')}")
            lines.append(f"- **Target Branch:** {gl.get('target_branch', '')}")
            lines.append(f"- **Author:** {gl.get('author', '')}")
            maintainer = gl.get("maintainer", {})
            if maintainer:
                emails = maintainer.get("emails", [])
                lines.append(f"- **Maintainer Emails:** {', '.join(emails) if emails else 'none'}")
                lines.append(f"- **Maintainer Source:** {maintainer.get('source', '')}")
        if evidence.kargo_context:
            kc = evidence.kargo_context
            lines.append("")
            lines.append("## Kargo Context")
            lines.append(f"- **Project:** {kc.get('project', '')}")
            lines.append(f"- **Stage:** {kc.get('stage', '')}")
            lines.append(f"- **Promotion:** {kc.get('promotion', '')}")
            lines.append(f"- **Freight:** {(kc.get('freight') or '')[:12]}...")
            lines.append(f"- **Phase:** {kc.get('phase', '')}")
            lines.append(f"- **Failed Step:** {kc.get('failed_step', 'N/A')}")
            lines.append(f"- **Error:** {kc.get('message', '')}")
            if kc.get("mr_url"):
                lines.append(f"- **MR URL:** {kc['mr_url']}")
            lines.append(f"- **Started:** {kc.get('started_at', '')}")
            lines.append(f"- **Finished:** {kc.get('finished_at', '')}")
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
        lines.append(f"- **CPU:** {service_meta.metrics.cpu:.1f}%")
        lines.append(f"- **Memory:** {service_meta.metrics.memory:.1f}%")
        lines.append(f"- **Error Rate:** {service_meta.metrics.error_rate:.2f}%")

    lines.extend([
        f"",
        f"## Conversation",
        f"",
    ])
    prev_ts = event.conversation[0].timestamp if event.conversation else 0
    for turn in event.conversation:
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
