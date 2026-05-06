# BlackBoard/src/observers/nightwatcher_prompt.py
# @ai-rules:
# 1. [Pattern]: System prompt follows Brain's structure -- per-phase guidance + manifest table.
# 2. [Constraint]: Manifest table includes staged_hours_ago for temporal status assessment.
# 3. [Pattern]: build_report_iteration_prompt carries ALL context. Tool descriptions carry contract only.
# 4. [Constraint]: Report phase prompt describes data needed, not tool behavior (shopping cart enforces structure).
"""Nightwatcher system prompt builder -- phase-aware instructions + manifest table."""
from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import StagedEscalation


def build_manifest_table(escalations: list["StagedEscalation"]) -> str:
    """Format escalations as a numbered markdown table with temporal context."""
    now = time.time()
    lines = ["| # | Event ID | Service | Platform | Priority | Staged (hrs ago) | Summary |",
             "|---|----------|---------|----------|----------|------------------|---------|"]
    for i, e in enumerate(escalations, 1):
        hours_ago = round((now - e.staged_at) / 3600, 1)
        lines.append(f"| {i} | {e.event_id} | {e.service} | {e.platform or '?'} | {e.priority} | {hours_ago}h | {e.summary[:80]} |")
    return "\n".join(lines)


def build_system_prompt(
    escalations: list["StagedEscalation"],
    window_start: str,
    window_end: str,
) -> str:
    """Build the full Nightwatcher system instruction with phases and manifest."""
    manifest = build_manifest_table(escalations)
    count = len(escalations)

    return f"""You are the Nightwatcher -- Darwin's end-of-shift incident consolidation agent.
You review escalated events and produce focused, deduplicated incident reports.
One incident per root cause, not per event. Goal: reduce noise, preserve signal.

## Shift: {window_start} to {window_end} ({count} escalations)

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

## Manifest (every event_id must appear in a cluster -- no silent drops)

{manifest}

Total: {count} escalations. Consolidate ALL into incidents.

## Consolidation Rules
- Same outage across N services = 1 incident (list all affected)
- Same pipeline failure across M MRs = 1 incident
- Kargo timeout from upstream pipeline failure = 1 incident (pipeline is root cause)
- Self-resolved cluster (MRs merged, pipelines green) -> status Closed
- Recurred 3+ times in 14 days (deep_memory) -> priority Critical

## Cynefin Awareness
- CLEAR: Known failure, known fix. Informational.
- COMPLICATED: Multiple factors, needs expert review. Include analysis.
- CHAOTIC: Active crisis. Critical priority, dispatch investigation immediately.
"""


def build_report_iteration_prompt(
    cluster: dict, index: int, total: int, completed_reports: list[dict],
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
    prompt += (
        "Write the incident report for this cluster. "
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
