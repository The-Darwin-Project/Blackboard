# BlackBoard/src/observers/nightwatcher_prompt.py
# @ai-rules:
# 1. [Pattern]: Each XML-tagged section is a named module constant (_IDENTITY_RULE, _PHASE_LIFECYCLE_PROTOCOL, etc.).
# 2. [Constraint]: _REQUIRED_TAG_IDS frozenset must stay in sync with the section constants (CI test validates).
# 3. [Pattern]: build_system_prompt joins sections with --- separators; only manifest_context is dynamic.
# 4. [Constraint]: Manifest table is 8 columns including Links (compact labels via extract_event_links).
# 5. [Pattern]: build_report_iteration_prompt carries ALL context including cluster_links. Tool descriptions carry contract only.
# 6. [Pattern]: extract_event_links (compact, table-safe) vs extract_full_links (full URLs, empty string when none).
# 7. [Gotcha]: `import os` required for GITLAB_HOST env var. _normalize_gitlab_host strips prefix THEN trailing slash.
"""Nightwatcher system prompt builder -- phase-aware instructions + manifest table."""
from __future__ import annotations

import os
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import StagedEscalation


def _normalize_gitlab_host(host: str) -> str:
    """Strip scheme and trailing slash from GITLAB_HOST for URL construction."""
    return host.removeprefix("https://").removeprefix("http://").rstrip("/")


def extract_event_links(e: "StagedEscalation") -> str:
    """Extract compact link labels from escalation evidence (comma-separated, table-safe)."""
    parts: list[str] = []
    snap = e.evidence_snapshot or {}
    gl = snap.get("gitlab_context") or {}
    kc = snap.get("kargo_context") or {}
    jc = snap.get("jira_context") or {}
    if gl.get("target_url"):
        iid = gl.get("mr_iid") or "?"
        parts.append(f"MR !{iid}")
    if gl.get("pipeline_id"):
        parts.append(f"Pipe #{gl['pipeline_id']}")
    if kc.get("mr_url"):
        parts.append("Kargo MR")
    if jc.get("issue_url"):
        parts.append(jc.get("issue_key", "Jira"))
    if e.slack_thread_url:
        parts.append("Slack")
    return ", ".join(parts) if parts else "—"


def extract_full_links(e: "StagedEscalation") -> str:
    """Extract full URL links for report descriptions."""
    lines: list[str] = []
    snap = e.evidence_snapshot or {}
    gl = snap.get("gitlab_context") or {}
    kc = snap.get("kargo_context") or {}
    jc = snap.get("jira_context") or {}
    if gl.get("target_url"):
        lines.append(f"- MR: {gl['target_url']}")
    if gl.get("pipeline_id"):
        raw_host = os.getenv("GITLAB_HOST", "")
        gitlab_host = _normalize_gitlab_host(raw_host)
        if gl.get("project_path") and gitlab_host:
            lines.append(f"- Pipeline: https://{gitlab_host}/{gl['project_path']}/-/pipelines/{gl['pipeline_id']}")
        else:
            lines.append(f"- Pipeline ID: {gl['pipeline_id']}")
    if kc.get("mr_url"):
        lines.append(f"- Kargo MR: {kc['mr_url']}")
    if jc.get("issue_url"):
        lines.append(f"- Jira: {jc['issue_url']}")
    if e.slack_thread_url:
        lines.append(f"- Slack: {e.slack_thread_url}")
    return "\n".join(lines)


def build_manifest_table(escalations: list["StagedEscalation"]) -> str:
    """Format escalations as a numbered markdown table with temporal context and links."""
    now = time.time()
    lines = [
        "| # | Event ID | Service | Platform | Priority | Staged (hrs ago) | Links | Summary |",
        "|---|----------|---------|----------|----------|------------------|-------|---------|",
    ]
    for i, e in enumerate(escalations, 1):
        hours_ago = round((now - e.staged_at) / 3600, 1)
        links = extract_event_links(e)
        lines.append(
            f"| {i} | {e.event_id} | {e.service} | {e.platform or '?'} "
            f"| {e.priority} | {hours_ago}h | {links} | {e.summary} |"
        )
    return "\n".join(lines)


_IDENTITY_RULE = """\
<rule id="identity">
You are the Nightwatcher -- Darwin's end-of-shift incident consolidation agent.
You review escalated events and produce focused, deduplicated incident reports.
One incident per root cause, not per event. Goal: reduce noise, preserve signal.
</rule>"""

_PHASE_LIFECYCLE_PROTOCOL = """\
<protocol id="phase-lifecycle">
## Phase Lifecycle

### REVIEW Phase (start here)
- Scan the manifest. Identify clusters sharing a root cause.
- Use get_event_report to read representative events per cluster.
- Use search_journal for oscillation patterns; consult_deep_memory for recurrence.
- You MUST read at least one event per suspected cluster before leaving.
- When ready, call set_phase("investigate").

### INVESTIGATE Phase
- Use dispatch_investigation ONLY for live cluster state that reports cannot provide.
- Finalize clusters: assign every manifest event to exactly one cluster.
- When ready to write, call set_phase("report").

### REPORT Phase
Declare your incident clusters by grouping events by shared root cause. The system
will then guide you through writing each incident report individually.
- Every manifest event must be assigned to exactly one cluster.
</protocol>"""

_CONSOLIDATION_RULES = """\
<rule id="consolidation-rules">
## Consolidation Rules
- Same outage across N services = 1 incident (list all affected)
- Same pipeline failure across M MRs = 1 incident
- Kargo timeout from upstream pipeline failure = 1 incident (pipeline is root cause)
- Self-resolved cluster (MRs merged, pipelines green) -> status Closed
- Recurred 3+ times in 14 days (deep_memory) -> priority Critical
</rule>"""

_LINK_HIERARCHY_RULE = """\
<rule id="link-hierarchy">
## Link Hierarchy
- Manifest links (compact labels) guide clustering decisions -- use them to identify shared pipelines and MRs.
- Report links (full URLs) belong in incident descriptions -- include them as Affected Resources.
- Never fabricate URLs. If a link is not in the data, omit it.
</rule>"""

_REPORT_FORMAT_RULE = """\
<rule id="report-format">
## Report Format
- Include an Affected Resources section listing available links (MR, pipeline, Kargo, Jira, Slack).
- Use the full URL form from the Related Links data provided per cluster.
- Omit the section entirely if no links are available for the cluster.
</rule>"""

_CYNEFIN_AWARENESS_CONTEXT = """\
<context id="cynefin-awareness">
## Cynefin Awareness
- CLEAR: Known failure, known fix. Informational.
- COMPLICATED: Multiple factors, needs expert review. Include analysis.
- CHAOTIC: Active crisis. Critical priority, dispatch investigation immediately.
</context>"""

_REQUIRED_TAG_IDS = frozenset({
    "identity", "phase-lifecycle", "manifest",
    "consolidation-rules", "link-hierarchy", "report-format",
    "cynefin-awareness",
})


def build_system_prompt(
    escalations: list["StagedEscalation"],
    window_start: str,
    window_end: str,
) -> str:
    """Build the full Nightwatcher system instruction with phases and manifest."""
    manifest = build_manifest_table(escalations)
    count = len(escalations)

    manifest_context = (
        f'<context id="manifest">\n'
        f"## Shift: {window_start} to {window_end} ({count} escalations)\n\n"
        f"{manifest}\n\n"
        f"Total: {count} escalations. Consolidate ALL into incidents.\n"
        f"Every event_id must appear in a cluster -- no silent drops.\n"
        f"</context>"
    )

    sections = [
        _IDENTITY_RULE,
        _PHASE_LIFECYCLE_PROTOCOL,
        manifest_context,
        _CONSOLIDATION_RULES,
        _LINK_HIERARCHY_RULE,
        _REPORT_FORMAT_RULE,
        _CYNEFIN_AWARENESS_CONTEXT,
    ]
    return "\n\n---\n\n".join(sections) + "\n"


def build_report_iteration_prompt(
    cluster: dict, index: int, total: int, completed_reports: list[dict],
    cluster_links: list[str] | None = None,
) -> str:
    """Build the user prompt for a single cart iteration."""
    events = cluster.get("events", [])
    services = cluster.get("services", [])
    prompt = (
        f"## Report {index} of {total}\n\n"
        f"**Root cause**: {cluster.get('root_cause', '?')}\n"
        f"**Platform**: {cluster.get('platform', '?')}\n"
        f"**Services**: {', '.join(services) if services else 'unknown'}\n"
        f"**Events**: {', '.join(events)}\n\n"
    )
    if completed_reports:
        prompt += "### Completed Reports\n\n"
        for r in completed_reports:
            prompt += (
                f"- **[{r['index']}]** [{r['priority']}] {r['platform']} -- "
                f"{r['summary'][:80]} ({len(r['affected_events'])} events)\n"
            )
        prompt += "\n"
    if cluster_links:
        prompt += "### Related Links\n\n"
        prompt += "\n\n".join(cluster_links) + "\n\n"
    prompt += (
        "Write the incident report for this cluster. "
        "Include relevant links from the Related Links section in your description. "
        "Consider cross-references to completed reports where relevant."
    )
    return prompt


def build_summary_prompt(completed_reports: list[dict], metrics: dict) -> str:
    """Build the user prompt for the shift summary."""
    prompt = (
        "## Shift Summary\n\n"
        f"**Escalations**: {metrics.get('escalation_count', '?')}\n"
        f"**Incidents created**: {metrics.get('incident_count', '?')}\n"
        f"**Noise reduction**: {metrics.get('noise_reduction_pct', '?')}%\n"
    )
    if metrics.get("failed_cluster_count", 0) > 0:
        prompt += f"**Failed clusters**: {metrics['failed_cluster_count']} (events restaged)\n"
    prompt += "\n### Incident Reports\n\n"
    for r in completed_reports:
        prompt += (
            f"- **[{r['index']}]** [{r['priority']}] [{r['status']}] {r['platform']} -- "
            f"{r['summary'][:100]} ({len(r['affected_events'])} events)\n"
        )
    prompt += "\nWrite the end-of-shift briefing for the Slack infra channel."
    return prompt
