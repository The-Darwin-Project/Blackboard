# BlackBoard/src/agents/headhunter_gitlab.py
# @ai-rules:
# 1. [Pattern]: Implements VcsPlatformPort for GitLab. All GitLab API calls live here.
# 2. [Constraint]: AIR GAP: No kubernetes imports. GitLab API via httpx only.
# 3. [Pattern]: Dedup by (project_id, mr_iid). Priority-based action selection for multi-todo MRs.
# 4. [Pattern]: Brain-facing methods (refresh_mr_state, poll_gitlab_mr_status, extract_gitlab_state_key)
#    are NOT part of VcsPlatformPort — they're GitLab-specific, accessed via Headhunter delegates.
# 5. [Pattern]: _load_gitlab_si() loads from headhunter_skills/gitlab-mr-triage.md with emergency fallback.
# 6. [Gotcha]: merge_status excluded from state_key (flaps during active pipelines).
# 7. [Pattern]: GITLAB_HOST normalization: strip scheme BEFORE trailing slash.
# 8. [Security]: Every httpx client uses verify=self._verify (vcs_approval.resolve_ca_bundle, re-read per
#    call). TLS verification is NEVER disabled; __init__ calls resolve_ca_bundle() once so an insecure
#    GITLAB_SSL_VERIFY=false raises ValueError at startup instead of at the first poll.
# 9. [Gotcha]: project_id may be a numeric id OR a path ("group/proj", seeded by Kargo gitlab_context). Any
#    URL that interpolates a gitlab_context/StateWatcher project_id MUST go through _enc_project_id()
#    (quote(unquote(...), safe="")); a raw "/" would split the API path.
# 10. [Pattern]: Todo dismissal lifecycle — open MRs dismiss all sibling todo_ids ONLY on event close via
#     two-phase post_feedback() (feedback_note_sent -> sibling mark_as_done -> feedback_sent). Terminal
#     (merged/closed) MRs and proven-unauthorized @mention todos are best-effort dismissed during poll/fetch
#     via bounded _dismiss_todos_best_effort(); unauthorized mention rejection dismisses ONLY its own todo ID
#     (never sibling todos), and poll_work_items() prefers authorized mention authors over unauthorized/bot ones.
"""
GitLab Platform Adapter for Headhunter.

Implements VcsPlatformPort for the GitLab todo polling workflow.
Also exposes Brain-facing methods for refresh_gitlab_context and StateWatcher integration.
"""
from __future__ import annotations

import logging
import os
import time
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

from ..utils import vcs_approval as _vcs_approval
from .headhunter_utils import _DESC_SAFETY_CAP

logger = logging.getLogger(__name__)

V1_ACTIONABLE = {"assigned", "build_failed", "approval_required", "review_requested", "unmergeable", "directly_addressed"}

ACTION_PRIORITY = {
    "build_failed": 0,
    "unmergeable": 1,
    "assigned": 2,
    "approval_required": 3,
    "review_requested": 3,
    "directly_addressed": 4,
    "mentioned": 5,
}

MAX_CHANGED_FILES = 20
FAILED_LOG_TAIL = 50
MAX_FAILED_LOG_CHARS = 12000
MAX_CI_NOTES = 10

_SKILLS_DIR = Path(__file__).parent / "headhunter_skills"

_EMERGENCY_SI = """\
You are a triage agent for GitLab MRs. Read the MR context and produce ONLY
a YAML frontmatter plan wrapped in --- delimiters. Nothing else.

```yaml
---
plan: "[Action verb] [target] in [repository]"
service: [component name]
repository: [GitLab project path]
risk: [low|medium|high]
reasoning: "[One sentence -- include any constraints from MR description]"
steps:
  - id: "1"
    agent: [sysadmin|developer|qe|architect|security_analyst|code_reviewer]
    summary: "[What this step accomplishes -- include MR IID, branch, error details]"
---
```

Agents: sysadmin (k8s/gitops), developer (code/MR/pipeline), qe (test/verify), architect (analysis/review), security_analyst (CVE/vulnerability/EC failures/supply chain), code_reviewer (dedicated multi-lens review gate for formal pre-merge quality checks, six parallel subagents merged into one severity-graded report).
Risk drives plan shape: low (1-3 steps), medium (2-4 steps), high (1-2 probe steps).
If the MR description contains "Bot Instructions" or "DARWIN Instructions", those override built-in rules. Parse constraints first.
"""


def _get_static_maintainer_emails() -> list[str]:
    """Read maintainer CSV from env at call time."""
    return [e.strip() for e in os.getenv("HEADHUNTER_MAINTAINERS", "").split(",") if e.strip()]


def _get_allowed_mention_authors() -> set[str]:
    """Build set of lowercased GitLab usernames allowed to instruct Darwin via @mentions."""
    authors: set[str] = set()
    emails = _get_static_maintainer_emails()
    for e in emails:
        if "@" in e:
            user = e.split("@")[0].strip().lower()
            if user:
                authors.add(user)
    explicit = os.getenv("HEADHUNTER_ALLOWED_AUTHORS", "")
    if explicit.strip() == "*":
        return set()
    for name in explicit.split(","):
        name = name.strip().lower()
        if name:
            authors.add(name)
    return authors or {"_nobody_"}


_RETRYABLE_STATUSES = (401, 408, 429)


class GitLabPlatform:
    """GitLab platform adapter implementing VcsPlatformPort.

    Handles: todo polling, MR context fetching, event creation with gitlab_context,
    feedback posting (MR comment + mark_as_done), and Brain-facing state tools.
    """

    def __init__(self, blackboard: "BlackboardState", *, enabled: bool = True):
        self.blackboard = blackboard
        self._enabled_flag = enabled
        self._gitlab_host = _vcs_approval.normalize_gitlab_host(os.getenv("GITLAB_HOST", ""))
        self._gitlab_token: str | None = None
        self._maintainer_source = os.getenv("HEADHUNTER_MAINTAINER_SOURCE", "static")
        self._smartsheet_cache = None
        # Fail fast: GITLAB_SSL_VERIFY=false/0/no raises ValueError here, at startup.
        _vcs_approval.resolve_ca_bundle(self._gitlab_host)

    @property
    def _verify(self) -> str | bool:
        return _vcs_approval.resolve_ca_bundle(self._gitlab_host)

    @staticmethod
    def _enc_project_id(project_id: int | str) -> str:
        """URL-encode a numeric id or path-style project id exactly once (idempotent on %2F)."""
        return urllib.parse.quote(urllib.parse.unquote(str(project_id)), safe="")

    # =========================================================================
    # VcsPlatformPort Implementation
    # =========================================================================

    @property
    def platform_name(self) -> str:
        return "gitlab"

    def enabled(self) -> bool:
        return self._enabled_flag and bool(self._gitlab_host)

    async def get_active_keys(self) -> set[tuple[int, int]]:
        """Get (project_id, mr_iid) for all active/deferred/waiting_approval headhunter events."""
        active_ids = await self.blackboard.get_active_events()
        waiting_ids = await self.blackboard.get_waiting_approval_events()
        keys: set[tuple[int, int]] = set()
        for eid in dict.fromkeys(list(active_ids) + list(waiting_ids)):
            event = await self.blackboard.get_event(eid)
            if not event or event.source != "headhunter":
                continue
            if event.status.value not in ("new", "active", "deferred", "waiting_approval"):
                continue
            ctx = getattr(event.event.evidence, "gitlab_context", None) if event.event and event.event.evidence else None
            if ctx:
                pid = ctx.get("project_id", 0) if isinstance(ctx, dict) else getattr(ctx, "project_id", 0)
                iid = ctx.get("mr_iid", 0) if isinstance(ctx, dict) else getattr(ctx, "mr_iid", 0)
                if pid and iid:
                    keys.add((pid, iid))
        return keys

    async def poll_work_items(self) -> list[dict]:
        """Fetch ALL pending GitLab todos (paginated), filter actionable, group by MR."""
        all_todos: list[dict] = []
        page = 1
        per_page = 100
        max_pages = 20
        async with httpx.AsyncClient(verify=self._verify, timeout=30) as client:
            while page <= max_pages:
                resp = await client.get(
                    self._api_url("/todos"),
                    headers=self._headers(),
                    params={
                        "state": "pending", "type": "MergeRequest",
                        "sort": "asc", "page": str(page), "per_page": str(per_page),
                    },
                )
                resp.raise_for_status()
                batch = resp.json()
                all_todos.extend(batch)
                if len(batch) < per_page:
                    break
                page += 1
            else:
                logger.warning(f"GitLabPlatform: hit max_pages ({max_pages}), {len(all_todos)} todos fetched")

        actionable = [t for t in all_todos if t.get("action_name") in V1_ACTIONABLE]
        if not actionable:
            return []
        actionable.sort(key=lambda t: t.get("created_at", ""))

        active_mr_keys = await self.get_active_keys()
        grouped = self._group_by_mr(actionable)
        allowed_mention_authors = _get_allowed_mention_authors()
        darwin_bot_lower = os.getenv("GITLAB_BOT_USERNAME", "darwin-bot").lower()

        def _todo_selection_key(t: dict) -> tuple[int, int]:
            action_name = t.get("action_name", "")
            prio = ACTION_PRIORITY.get(action_name, 99)
            if action_name in ("directly_addressed", "mentioned"):
                author = ((t.get("author") or {}).get("username") or "").strip().lower()
                if not author:
                    return (prio, 1)
                if author == darwin_bot_lower or (
                    allowed_mention_authors and author not in allowed_mention_authors
                ):
                    return (prio + 10, 2)
                return (prio, 0)
            return (prio, 0)

        result = []
        skipped_terminal = 0
        terminal_todo_ids: list[int] = []
        for key, group in grouped.items():
            if key in active_mr_keys:
                continue
            best = min(group, key=_todo_selection_key)
            mr_state = best.get("target", {}).get("state", "")
            if mr_state in ("merged", "closed"):
                skipped_terminal += 1
                terminal_todo_ids.extend(t["id"] for t in group if t.get("id"))
                logger.debug(f"GitLabPlatform: skipping terminal MR {key} (state={mr_state})")
                continue
            best["_sibling_todo_ids"] = [t["id"] for t in group]
            result.append(best)

        if terminal_todo_ids:
            try:
                async with httpx.AsyncClient(verify=self._verify, timeout=10) as client:
                    await self._dismiss_todos_best_effort(
                        client, self._headers(), terminal_todo_ids, "terminal MR",
                    )
            except Exception as exc:
                logger.debug(f"GitLabPlatform: best-effort terminal todo cleanup failed: {exc}")

        result.sort(key=lambda t: t.get("created_at", ""))
        logger.info(
            f"GitLab poll: {len(all_todos)} total, {len(actionable)} actionable, "
            f"{len(active_mr_keys)} active, {skipped_terminal} terminal, {len(result)} new"
        )
        return result

    async def _dismiss_todos_best_effort(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        todo_ids: list[int],
        reason: str,
        *,
        max_items: int = 20,
        timeout: float = 10.0,
    ) -> None:
        """Best-effort bounded todo dismissal; stops early on 403, 429, or timeout."""
        for tid in todo_ids[:max_items]:
            try:
                dismiss_resp = await client.post(
                    self._api_url(f"/todos/{tid}/mark_as_done"),
                    headers=headers,
                    timeout=timeout,
                )
                if dismiss_resp.status_code in (403, 429):
                    logger.debug(
                        f"GitLabPlatform: stopping {reason} todo dismissal after HTTP {dismiss_resp.status_code} on todo {tid}"
                    )
                    break
                if not dismiss_resp.is_success:
                    logger.debug(
                        f"GitLabPlatform: best-effort {reason} todo {tid} dismiss returned {dismiss_resp.status_code}"
                    )
            except httpx.TimeoutException as exc:
                logger.debug(f"GitLabPlatform: stopping {reason} todo dismissal after timeout on todo {tid}: {exc}")
                break
            except Exception as exc:
                logger.debug(f"GitLabPlatform: best-effort {reason} todo {tid} dismiss failed: {exc}")

    async def _fetch_latest_pipeline(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        enc_pid: str,
        mr_iid: int,
        source_branch: str,
    ) -> list[dict]:
        """Fetch latest MR pipeline with guarded branch-ref fallback (never sends empty ref)."""
        pipelines: list[dict] = []
        try:
            mr_pipe_resp = await client.get(
                self._api_url(f"/projects/{enc_pid}/merge_requests/{mr_iid}/pipelines"),
                headers=headers,
                params={"per_page": "1"},
            )
            if mr_pipe_resp.is_success:
                data = mr_pipe_resp.json()
                if isinstance(data, list):
                    pipelines = data
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(f"GitLabPlatform: MR !{mr_iid} pipeline fetch failed (falling back): {exc}")

        if not pipelines and source_branch:
            try:
                pipe_resp = await client.get(
                    self._api_url(f"/projects/{enc_pid}/pipelines"),
                    headers=headers,
                    params={"ref": source_branch, "order_by": "updated_at", "per_page": "1"},
                )
                if pipe_resp.is_success:
                    data = pipe_resp.json()
                    if isinstance(data, list):
                        pipelines = data
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    f"GitLabPlatform: branch pipeline fallback failed for !{mr_iid} (ref={source_branch}): {exc}"
                )
        return pipelines

    async def _fetch_failed_job_log(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        enc_pid: str,
        pipe_id: int,
        context: dict,
    ) -> str:
        """Fetch failed pipeline jobs and tail traces; isolates per-job errors."""
        try:
            jobs_resp = await client.get(
                self._api_url(f"/projects/{enc_pid}/pipelines/{pipe_id}/jobs"),
                headers=headers,
            )
            if not jobs_resp.is_success:
                return ""
            all_jobs = jobs_resp.json()
            if not isinstance(all_jobs, list):
                return ""
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(f"GitLabPlatform: failed jobs fetch failed for pipeline {pipe_id}: {exc}")
            return ""

        failed_jobs = [j for j in all_jobs if isinstance(j, dict) and j.get("status") == "failed"]
        context["failed_job_count"] = len(failed_jobs)
        context["total_job_count"] = len(all_jobs)
        if not failed_jobs:
            return ""

        context["failed_job_names"] = [j.get("name", "unknown") for j in failed_jobs]
        job_traces: list[tuple[str, str]] = []
        for job in failed_jobs[:3]:
            job_id = job.get("id")
            if not job_id:
                continue
            try:
                trace_resp = await client.get(
                    self._api_url(f"/projects/{enc_pid}/jobs/{job_id}/trace"),
                    headers=headers,
                )
                if trace_resp.is_success:
                    lines = trace_resp.text.splitlines()
                    tail = "\n".join(lines[-FAILED_LOG_TAIL:])
                    job_traces.append((job.get("name", "unknown"), tail))
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    f"GitLabPlatform: trace fetch failed for job {job_id} (pipeline {pipe_id}): {exc}"
                )
        if not job_traces:
            return ""

        sep = "\n\n"
        section_headers = [f"=== Job: {name} ===\n" for name, _ in job_traces]
        overhead = sum(len(h) for h in section_headers) + len(sep) * (len(job_traces) - 1)
        per_job_budget = max(0, MAX_FAILED_LOG_CHARS - overhead) // len(job_traces)
        sections = []
        for hdr, (_, tail) in zip(section_headers, job_traces):
            if per_job_budget <= 0:
                body_part = ""
            elif len(tail) > per_job_budget:
                body_part = tail[-per_job_budget:]
            else:
                body_part = tail
            sections.append(f"{hdr}{body_part}")
        return sep.join(sections)[:MAX_FAILED_LOG_CHARS]

    async def fetch_context(self, work_item: dict) -> dict | None:
        """Enrich GitLab todo with MR diff, pipeline status, failed job log, CI notes."""
        todo = work_item
        target = todo.get("target", {})
        project_id = todo["project"]["id"]
        enc_pid = self._enc_project_id(project_id)
        mr_iid = target["iid"]
        action = todo["action_name"]

        context: dict = {
            "action_name": action,
            "mr_iid": target.get("iid"),
            "mr_title": target.get("title", ""),
            "mr_description": (target.get("description") or "")[:_DESC_SAFETY_CAP],
            "mr_state": target.get("state", ""),
            "merge_status": target.get("detailed_merge_status") or target.get("merge_status", ""),
            "source_branch": target.get("source_branch", ""),
            "target_branch": target.get("target_branch", ""),
            "author": target.get("author", {}).get("username", ""),
            "labels": target.get("labels", []),
            "milestone": (target.get("milestone") or {}).get("title"),
            "project_path": todo["project"].get("path_with_namespace", ""),
            "target_url": todo.get("target_url", "").split("#")[0],
        }

        async with httpx.AsyncClient(verify=self._verify, timeout=30) as client:
            headers = self._headers()
            darwin_bot = os.getenv("GITLAB_BOT_USERNAME", "darwin-bot")
            darwin_bot_lower = darwin_bot.lower()
            is_mention_action = action in ("directly_addressed", "mentioned")
            allowed_authors = _get_allowed_mention_authors() if is_mention_action else set()
            own_todo_ids = [work_item["id"]] if work_item.get("id") else []

            if is_mention_action:
                todo_author = ((work_item.get("author") or {}).get("username") or "").strip()
                if todo_author:
                    todo_author_lower = todo_author.lower()
                    if todo_author_lower == darwin_bot_lower or (
                        allowed_authors and todo_author_lower not in allowed_authors
                    ):
                        await self._dismiss_todos_best_effort(
                            client, headers, own_todo_ids, "unauthorized mention",
                        )
                        logger.info(
                            f"GitLabPlatform: rejecting @{darwin_bot} todo from unauthorized author "
                            f"{todo_author} on !{mr_iid}; dismissed todo {own_todo_ids}"
                        )
                        return None

            changes_resp = await client.get(
                self._api_url(f"/projects/{enc_pid}/merge_requests/{mr_iid}/changes"),
                headers=headers,
            )
            if changes_resp.is_success:
                changes = changes_resp.json().get("changes", [])
                context["changed_files"] = [c.get("new_path", "") for c in changes[:MAX_CHANGED_FILES]]
            else:
                context["changed_files"] = []

            pipelines = await self._fetch_latest_pipeline(
                client, headers, enc_pid, mr_iid, target.get("source_branch", ""),
            )

            pipeline_status = "unknown"
            failed_job_log = ""
            if pipelines:
                pipeline_status = pipelines[0].get("status", "unknown")
                context["pipeline_id"] = pipelines[0].get("id")
                if pipeline_status == "failed":
                    pipe_id = context.get("pipeline_id")
                    if pipe_id:
                        failed_job_log = await self._fetch_failed_job_log(
                            client, headers, enc_pid, pipe_id, context,
                        )

            context["pipeline_status"] = pipeline_status
            context["failed_job_log"] = failed_job_log

            notes_resp = await client.get(
                self._api_url(f"/projects/{enc_pid}/merge_requests/{mr_iid}/notes"),
                headers=headers,
                params={"sort": "desc", "per_page": "25"},
            )
            if not notes_resp.is_success:
                if is_mention_action:
                    logger.warning(
                        f"GitLabPlatform: notes fetch failed ({notes_resp.status_code}) on mention for !{mr_iid}; failing closed without dismissing todo"
                    )
                    return None
            else:
                all_notes = notes_resp.json()
                ci_notes: list[str] = []
                authorized_mention_found = False
                unauthorized_mention_seen = False
                mention_needle = f"@{darwin_bot_lower}"

                anchor_note_id: int | None = None
                raw_target_url = work_item.get("target_url") or ""
                if "#note_" in raw_target_url:
                    anchor_frag = raw_target_url.split("#note_", 1)[1].split("&")[0].split("/")[0]
                    if anchor_frag.isdigit():
                        anchor_note_id = int(anchor_frag)

                if is_mention_action and anchor_note_id is not None:
                    matched_anchor = next(
                        (n for n in all_notes if n.get("id") == anchor_note_id),
                        None,
                    )
                    if matched_anchor is not None and not matched_anchor.get("system"):
                        body = matched_anchor.get("body", "")
                        note_author = ((matched_anchor.get("author") or {}).get("username") or "")
                        if note_author.lower() != darwin_bot_lower and mention_needle in body.lower():
                            is_authorized = (not allowed_authors) or (note_author.lower() in allowed_authors)
                            if is_authorized:
                                context["mention_comment"] = body[:5000]
                                context["mention_author"] = note_author
                                authorized_mention_found = True
                            else:
                                logger.info(f"Ignoring @mention from {note_author} (not in maintainer list)")
                                unauthorized_mention_seen = True
                    if authorized_mention_found:
                        for note in all_notes:
                            if note.get("system") or note.get("id") == anchor_note_id:
                                continue
                            note_author = ((note.get("author") or {}).get("username") or "")
                            if note_author.lower() == darwin_bot_lower:
                                continue
                            if len(ci_notes) < MAX_CI_NOTES:
                                ci_notes.append(f"[{note_author}]: {note.get('body', '')[:500]}")
                else:
                    for note in all_notes:
                        if note.get("system"):
                            continue
                        body = note.get("body", "")
                        note_author = ((note.get("author") or {}).get("username") or "")
                        if note_author.lower() == darwin_bot_lower:
                            continue
                        if is_mention_action and mention_needle in body.lower():
                            is_authorized = (not allowed_authors) or (note_author.lower() in allowed_authors)
                            if not is_authorized:
                                logger.info(f"Ignoring @mention from {note_author} (not in maintainer list)")
                                unauthorized_mention_seen = True
                                break
                            context["mention_comment"] = body[:5000]
                            context["mention_author"] = note_author
                            authorized_mention_found = True
                            break
                        if len(ci_notes) < MAX_CI_NOTES:
                            ci_notes.append(f"[{note_author}]: {body[:500]}")

                if is_mention_action and not authorized_mention_found and not unauthorized_mention_seen and anchor_note_id is None:
                    mr_desc = target.get("description") or ""
                    mr_author = ((target.get("author") or {}).get("username") or "")
                    if mention_needle in mr_desc.lower() and mr_author.lower() != darwin_bot_lower:
                        is_authorized = (not allowed_authors) or (mr_author.lower() in allowed_authors)
                        if is_authorized:
                            context["mention_comment"] = mr_desc[:5000]
                            context["mention_author"] = mr_author
                            authorized_mention_found = True
                        else:
                            logger.info(f"Ignoring @mention in MR description from {mr_author} (not in maintainer list)")
                            unauthorized_mention_seen = True

                if is_mention_action and not authorized_mention_found:
                    if unauthorized_mention_seen:
                        await self._dismiss_todos_best_effort(
                            client, headers, own_todo_ids, "unauthorized mention",
                        )
                        logger.info(
                            f"GitLabPlatform: unauthorized @{darwin_bot} mention on !{mr_iid}; dismissed todo {own_todo_ids} and skipping"
                        )
                    else:
                        logger.warning(
                            f"GitLabPlatform: no @{darwin_bot} mention found in recent notes window on !{mr_iid}; skipping without dismissing todos"
                        )
                    return None
                if ci_notes:
                    context["recent_notes"] = ci_notes

        return context

    def load_triage_instruction(self) -> str:
        """Load GitLab MR triage system instruction from skills directory."""
        skill_path = _SKILLS_DIR / "gitlab-mr-triage.md"
        try:
            content = skill_path.read_text(encoding="utf-8")
            if content.strip():
                return content
            logger.warning("GitLab MR triage skill file is empty, using emergency fallback")
            return _EMERGENCY_SI
        except OSError as e:
            logger.warning(f"GitLab MR triage skill not loadable ({e}), using emergency fallback")
            return _EMERGENCY_SI

    @staticmethod
    def classify_severity(action: str, status: str) -> str:
        """Map GitLab MR action + pipeline status to event severity."""
        if action == "build_failed":
            return "warning"
        if action == "unmergeable":
            return "warning"
        if status == "failed":
            return "warning"
        return "info"

    async def create_platform_event(
        self,
        work_item: dict,
        plan_text: str,
        context: dict,
    ) -> str:
        """Push event to Brain queue with gitlab_context evidence."""
        from ..models import EventEvidence

        todo = work_item
        target = todo["target"]
        project = todo["project"]
        project_path = project.get("path_with_namespace", "")
        action_name = todo["action_name"]
        pipeline_status = context.get("pipeline_status", "unknown")
        severity = self.classify_severity(action_name, pipeline_status)
        maintainer = await self.resolve_maintainer(project_path, todo)
        logger.info(f"GitLab severity: {severity} for {action_name}/{pipeline_status}")
        head_sha = target.get("sha") or (target.get("diff_refs") or {}).get("head_sha")
        evidence = EventEvidence(
            display_text=f"GitLab: {action_name} on !{target['iid']} in {project_path}",
            source_type="headhunter",
            triggered_by="gitlab-bot",
            domain="disorder",
            domain_confidence="default",
            severity=severity,
            gitlab_context={
                "todo_id": todo["id"],
                "todo_ids": todo.get("_sibling_todo_ids") or [todo["id"]],
                "action_name": action_name,
                "project_id": project["id"],
                "project_path": project_path,
                "mr_iid": target["iid"],
                "mr_title": target["title"],
                "mr_state": target.get("state", ""),
                "merge_status": context.get("merge_status", ""),
                "source_branch": target.get("source_branch", ""),
                "target_branch": target.get("target_branch", ""),
                "author": target.get("author", {}).get("username", ""),
                "target_url": todo.get("target_url", "").split("#")[0],
                "pipeline_status": pipeline_status,
                "pipeline_id": context.get("pipeline_id"),
                "todo_created_at": todo.get("created_at", ""),
                "mr_description": (target.get("description") or "")[:_DESC_SAFETY_CAP],
                "maintainer": maintainer,
                "head_sha": head_sha,
                "sha": head_sha,
            },
        )
        resolved_service = await self._resolve_service(project_path)
        clean_plan = plan_text.strip()
        if clean_plan.startswith("```"):
            clean_plan = clean_plan.split("\n", 1)[1] if "\n" in clean_plan else clean_plan
        if clean_plan.endswith("```"):
            clean_plan = clean_plan[:-3].rstrip()
        event_id = await self.blackboard.create_event(
            source="headhunter",
            service=resolved_service,
            reason=clean_plan,
            evidence=evidence,
        )
        logger.info(f"GitLab event created: {event_id} for {todo['action_name']} on !{target['iid']}")
        return event_id

    async def post_feedback(self, event: object) -> None:
        """Post GitLab feedback (comment + mark_as_done) for a closed event."""
        if await self.blackboard.is_feedback_sent(event.id):
            return

        gl_ctx = None
        if hasattr(event, "event") and event.event.evidence and hasattr(event.event.evidence, "gitlab_context"):
            gl_ctx = event.event.evidence.gitlab_context
        if not gl_ctx:
            return

        todo_ids = gl_ctx.get("todo_ids") or ([gl_ctx["todo_id"]] if gl_ctx.get("todo_id") else [])
        project_id = gl_ctx.get("project_id")
        mr_iid = gl_ctx.get("mr_iid")
        if not project_id or not mr_iid:
            return

        close_turn = event.conversation[-1] if event.conversation else None
        close_reason = (close_turn.evidence or "resolved") if close_turn else "resolved"
        encoded_project_id = self._enc_project_id(project_id)

        if close_reason in ("stale", "duplicate") and not todo_ids:
            if not await self.blackboard.is_feedback_note_sent(event.id):
                await self.blackboard.mark_feedback_note_sent(event.id)
            await self.blackboard.mark_feedback_sent(event.id)
            logger.info(f"GitLab duplicate/stale: no todo_id for {event.id} ({close_reason}) on !{mr_iid}")
            return

        async with httpx.AsyncClient(verify=self._verify, timeout=30) as client:
            headers = self._headers()

            # Phase 1: MR Note (suppressed for stale/duplicate; retryable on 401/408/429/5xx/network error)
            if close_reason in ("stale", "duplicate"):
                if not await self.blackboard.is_feedback_note_sent(event.id):
                    await self.blackboard.mark_feedback_note_sent(event.id)
            elif not await self.blackboard.is_feedback_note_sent(event.id):
                outcome = self._build_feedback_comment(event, close_reason)
                try:
                    resp = await client.post(
                        self._api_url(f"/projects/{encoded_project_id}/merge_requests/{mr_iid}/notes"),
                        headers=headers,
                        json={"body": outcome},
                    )
                except Exception as exc:
                    logger.warning(f"GitLab MR comment request failed for {event.id}: {exc}")
                    return
                if resp.status_code in _RETRYABLE_STATUSES or resp.status_code >= 500:
                    logger.warning(f"GitLab MR comment transient failure ({resp.status_code}) for {event.id}")
                    return
                if resp.status_code == 404:
                    logger.info(f"Feedback skip: MR !{mr_iid} not found (deleted?)")
                elif resp.status_code == 403:
                    logger.warning(f"MR comment forbidden (403) for {event.id}: {resp.text[:200]}")
                elif 400 <= resp.status_code < 500:
                    logger.warning(
                        f"MR comment permanent client error ({resp.status_code}) for {event.id}: {resp.text[:200]}"
                    )
                elif not resp.is_success:
                    logger.warning(f"MR comment failed ({resp.status_code}): {resp.text[:200]}")
                    return
                await self.blackboard.mark_feedback_note_sent(event.id)

            # Phase 2: Todo Dismissal (all sibling todo_ids; retryable on 401/408/429/5xx/network error)
            for tid in todo_ids:
                try:
                    done_resp = await client.post(
                        self._api_url(f"/todos/{tid}/mark_as_done"), headers=headers,
                    )
                except Exception as exc:
                    logger.warning(f"GitLab mark_as_done request failed for todo {tid} ({event.id}): {exc}")
                    return
                if done_resp.status_code in _RETRYABLE_STATUSES or done_resp.status_code >= 500:
                    logger.warning(f"GitLab mark_as_done transient failure ({done_resp.status_code}) for todo {tid} ({event.id})")
                    return
                if done_resp.status_code == 304:
                    logger.debug(f"GitLab feedback: todo {tid} already done (304) for {event.id}")
                elif done_resp.status_code == 404:
                    logger.info(f"GitLab feedback: todo {tid} not found for {event.id}")
                elif done_resp.status_code == 403:
                    logger.warning(f"GitLab mark_as_done forbidden (403) for todo {tid} ({event.id})")
                elif 400 <= done_resp.status_code < 500:
                    logger.warning(
                        f"GitLab mark_as_done permanent client error ({done_resp.status_code}) for todo {tid} ({event.id})"
                    )
                elif not done_resp.is_success:
                    logger.warning(f"GitLab mark_as_done failed ({done_resp.status_code}) for todo {tid} ({event.id})")
                    return

            await self.blackboard.mark_feedback_sent(event.id)
            logger.info(f"GitLab feedback posted for {event.id}: {close_reason} on !{mr_iid}")

    # =========================================================================
    # Brain-Facing Methods (NOT part of VcsPlatformPort)
    # =========================================================================

    async def refresh_mr_state(self, event_id: str, *,
                               override_project_id: int | None = None,
                               override_mr_iid: int | None = None) -> dict:
        """Re-fetch current MR/pipeline state from GitLab and update event evidence."""
        event = await self.blackboard.get_event(event_id)
        if not event:
            return {"error": f"Event {event_id} not found"}

        gl_ctx = None
        if event.event.evidence and hasattr(event.event.evidence, "gitlab_context"):
            gl_ctx = event.event.evidence.gitlab_context

        project_id = override_project_id or (gl_ctx.get("project_id") if gl_ctx else None)
        mr_iid = override_mr_iid or (gl_ctx.get("mr_iid") if gl_ctx else None)
        source_branch = (gl_ctx.get("source_branch", "") if gl_ctx else "")
        if not project_id or not mr_iid:
            return {"error": "No MR reference available. Supply mr_url or ensure the event has gitlab_context."}

        encoded_project_id = self._enc_project_id(project_id)
        state_changed_at = ""
        head_sha = (gl_ctx or {}).get("head_sha") or (gl_ctx or {}).get("sha")
        try:
            async with httpx.AsyncClient(verify=self._verify, timeout=30) as client:
                headers = self._headers()
                mr_resp = await client.get(
                    self._api_url(f"/projects/{encoded_project_id}/merge_requests/{mr_iid}"),
                    headers=headers,
                )
                if mr_resp.status_code == 404:
                    return {"error": "MR not found (deleted?)", "pipeline_status": "unknown",
                            "mr_state": "closed", "merge_status": "unknown", "severity": "info"}
                if mr_resp.status_code == 429:
                    _fallback = gl_ctx or {}
                    return {"error": "GitLab rate limited", "pipeline_status": _fallback.get("pipeline_status", "unknown"),
                            "mr_state": _fallback.get("mr_state", "unknown"), "merge_status": _fallback.get("merge_status", "unknown"),
                            "severity": event.event.evidence.severity if event.event.evidence else "warning"}

                mr_state = "unknown"
                merge_status = "unknown"
                if mr_resp.is_success:
                    mr_data = mr_resp.json()
                    mr_state = mr_data.get("state", "unknown")
                    merge_status = mr_data.get("detailed_merge_status") or mr_data.get("merge_status", "unknown")
                    head_sha = mr_data.get("sha") or (mr_data.get("diff_refs") or {}).get("head_sha") or head_sha
                    if not source_branch:
                        source_branch = mr_data.get("source_branch", "")
                    if mr_state in ("merged", "closed"):
                        state_changed_at = mr_data.get("merged_at") or mr_data.get("closed_at") or ""
                else:
                    _fallback = gl_ctx or {}
                    return {
                        "error": f"MR fetch failed: HTTP {mr_resp.status_code}",
                        "pipeline_status": _fallback.get("pipeline_status", "unknown"),
                        "mr_state": _fallback.get("mr_state", "unknown"),
                        "merge_status": _fallback.get("merge_status", "unknown"),
                        "severity": event.event.evidence.severity if event.event.evidence else "warning",
                    }

                pipeline_id = (gl_ctx or {}).get("pipeline_id")
                pipelines = await self._fetch_latest_pipeline(
                    client, headers, encoded_project_id, mr_iid, source_branch,
                )
                pipeline_status = "unknown"
                if pipelines:
                    pipeline_status = pipelines[0].get("status", "unknown")
                    pipeline_id = pipelines[0].get("id")

        except Exception as e:
            logger.warning(f"refresh_mr_state: GitLab API error for {event_id}: {e}")
            return {"error": f"GitLab API unavailable: {e}", "pipeline_status": "unknown",
                    "mr_state": "unknown", "merge_status": "unknown", "severity": "warning"}

        action_name = (gl_ctx or {}).get("action_name", "assigned")
        severity = self.classify_severity(action_name, pipeline_status)
        result = {
            "pipeline_status": pipeline_status,
            "pipeline_id": pipeline_id,
            "mr_state": mr_state,
            "merge_status": merge_status,
            "severity": severity,
        }
        if head_sha:
            result["head_sha"] = head_sha
            result["sha"] = head_sha
        if mr_state in ("merged", "closed"):
            result["merge_status"] = mr_state
            if state_changed_at:
                result["state_changed_at"] = state_changed_at

        await self.blackboard.update_event_gitlab_context(event_id, result)
        logger.info(f"Refreshed MR state for {event_id}: pipeline={pipeline_status}, mr={mr_state}")
        return result

    async def poll_gitlab_mr_status(self, project_id: int | str, mr_iid: int) -> dict:
        """Lightweight read-only poll for StateWatcher. Raises on HTTP errors."""
        encoded_project_id = self._enc_project_id(project_id)
        async with httpx.AsyncClient(verify=self._verify, timeout=30) as client:
            mr_resp = await client.get(
                self._api_url(f"/projects/{encoded_project_id}/merge_requests/{mr_iid}"),
                headers=self._headers(),
            )
            mr_resp.raise_for_status()
            pipe_resp = await client.get(
                self._api_url(f"/projects/{encoded_project_id}/merge_requests/{mr_iid}/pipelines"),
                headers=self._headers(),
            )
            pipe_resp.raise_for_status()
        mr = mr_resp.json()
        pipelines = pipe_resp.json()
        latest_pipeline = pipelines[0] if isinstance(pipelines, list) and pipelines else {}
        return {
            "mr_state": mr.get("state", "unknown"),
            "pipeline_status": latest_pipeline.get("status", "unknown"),
        }

    @staticmethod
    def extract_gitlab_state_key(state: dict) -> dict:
        """Canonical state_key builder. merge_status excluded (flaps during active pipelines)."""
        return {
            "mr_state": state.get("mr_state", "unknown"),
            "pipeline_status": state.get("pipeline_status", "unknown"),
        }

    async def poll_gitlab_pipeline_status(self, project_id: int | str, pipeline_id: int) -> dict:
        """Lightweight read-only poll for StateWatcher. Returns pipeline status."""
        encoded_project_id = self._enc_project_id(project_id)
        async with httpx.AsyncClient(verify=self._verify, timeout=30) as client:
            resp = await client.get(
                self._api_url(f"/projects/{encoded_project_id}/pipelines/{pipeline_id}"),
                headers=self._headers(),
            )
            resp.raise_for_status()
        pipeline = resp.json()
        return {
            "pipeline_status": pipeline.get("status", "unknown"),
        }

    @staticmethod
    def extract_pipeline_state_key(state: dict) -> dict:
        """Canonical state_key builder for pipeline-only polling."""
        return {"pipeline_status": state.get("pipeline_status", "unknown")}

    @staticmethod
    def parse_mr_url(url: str) -> tuple[int | str, int] | None:
        """Extract (project_id, mr_iid) from a GitLab MR URL."""
        from ..utils.vcs_approval import parse_mr_url
        return parse_mr_url(url)

    async def resolve_project_id(self, path_or_id) -> int | None:
        """Resolve a namespace/project path to a numeric project ID via GitLab API."""
        if isinstance(path_or_id, int):
            return path_or_id
        try:
            pid = int(path_or_id)
            return pid
        except (ValueError, TypeError):
            pass
        from urllib.parse import quote
        encoded = quote(str(path_or_id), safe="")
        try:
            async with httpx.AsyncClient(verify=self._verify, timeout=15) as client:
                resp = await client.get(
                    self._api_url(f"/projects/{encoded}"),
                    headers=self._headers(),
                )
                if resp.is_success:
                    return resp.json().get("id")
        except Exception as e:
            logger.warning(f"resolve_project_id failed for {path_or_id}: {e}")
        return None

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _get_token(self) -> str:
        """Read GitLab token (cached after first read)."""
        if self._gitlab_token:
            return self._gitlab_token
        from ..utils.gitlab_token import get_gitlab_auth
        auth = get_gitlab_auth()
        if not auth:
            raise RuntimeError("GitLab auth not configured (GITLAB_HOST or token missing)")
        self._gitlab_token = auth.get_token()
        return self._gitlab_token

    def _headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self._get_token()}

    def _api_url(self, path: str) -> str:
        return f"https://{self._gitlab_host}/api/v4{path}"

    @staticmethod
    def _group_by_mr(todos: list[dict]) -> dict[tuple[int, int], list[dict]]:
        """Group todos by (project_id, mr_iid)."""
        grouped: dict[tuple[int, int], list[dict]] = {}
        for todo in todos:
            target = todo.get("target", {})
            key = (todo.get("project", {}).get("id", 0), target.get("iid", 0))
            grouped.setdefault(key, []).append(todo)
        return grouped

    async def resolve_maintainer(self, project_path: str, todo: dict) -> dict:
        """Resolve maintainer for escalation."""
        if self._maintainer_source == "smartsheet":
            maintainer = await self._resolve_from_smartsheet(project_path)
            if maintainer:
                return {**maintainer, "source": "smartsheet"}

        static_emails = _get_static_maintainer_emails()
        if static_emails:
            return {"source": "static", "emails": static_emails}

        target = todo.get("target", {})
        assignee = target.get("assignee") or target.get("author", {})
        if assignee and assignee.get("username"):
            email = await self._resolve_email_from_gitlab(assignee["username"])
            emails = [email] if email else []
            return {"source": "mr_metadata", "emails": emails, "name": assignee["username"]}

        return {"source": "static", "emails": []}

    async def _resolve_email_from_gitlab(self, username: str) -> str | None:
        """Lookup a GitLab user's email by username."""
        try:
            async with httpx.AsyncClient(verify=self._verify, timeout=10) as client:
                resp = await client.get(
                    self._api_url("/users"),
                    headers=self._headers(),
                    params={"username": username},
                )
                if resp.is_success:
                    users = resp.json()
                    if users and users[0].get("public_email"):
                        return users[0]["public_email"]
                    if users and users[0].get("email"):
                        return users[0]["email"]
        except Exception as e:
            logger.debug(f"GitLab email lookup failed for {username}: {e}")
        return None

    async def _resolve_from_smartsheet(self, project_path: str) -> dict | None:
        """Resolve from Smartsheet API (lazy-loaded)."""
        if not self._smartsheet_cache:
            try:
                from .headhunter_smartsheet import SmartsheetMaintainerCache
                token = os.getenv("SMARTSHEET_API_TOKEN", "")
                sheet_id = os.getenv("SMARTSHEET_SHEET_ID", "")
                if not token or not sheet_id:
                    return None
                self._smartsheet_cache = SmartsheetMaintainerCache(token, sheet_id)
            except ImportError:
                return None
        component = project_path.rsplit("/", 1)[-1] if "/" in project_path else project_path
        return await self._smartsheet_cache.get_maintainer(component)

    async def _resolve_service(self, project_path: str) -> str:
        """Map GitLab project path to Darwin service name."""
        try:
            services = await self.blackboard.get_services()
            for svc in services.values():
                repo_url = getattr(svc, "source_repo_url", "") or ""
                gitops_url = getattr(svc, "gitops_repo_url", "") or ""
                if project_path in repo_url or project_path in gitops_url:
                    return svc.name
        except Exception:
            pass
        return project_path.rsplit("/", 1)[-1] if "/" in project_path else project_path or "general"

    @staticmethod
    def _build_feedback_comment(event, close_reason: str) -> str:
        """Build structured GitLab MR comment from event outcome."""
        actions = []
        for t in event.conversation:
            if t.actor in ("user", "brain"):
                continue
            if t.action == "execute" and t.result:
                ts = time.strftime("%H:%M", time.gmtime(t.timestamp)) if t.timestamp else ""
                first_line = t.result.strip().split("\n")[0].replace("#", "").strip()
                actions.append(f"- `{ts}` {first_line[:150]}")

        close_turn = event.conversation[-1] if event.conversation else None
        close_summary = (close_turn.thoughts or "") if close_turn else ""

        turns = len(event.conversation)
        lines = [f"**Darwin** ({turns} turns)"]
        if close_summary:
            lines.append(f"\n{close_summary}")
        if actions:
            lines.append("\n**Trace (UTC):**")
            lines.extend(actions[:5])

        return "\n".join(lines)
