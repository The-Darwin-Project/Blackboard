# BlackBoard/src/agents/headhunter.py
# @ai-rules:
# 1. [Pattern]: Follows Aligner pattern -- in-process daemon, lazy-loaded LLM adapter via _get_adapter().
# 2. [Constraint]: AIR GAP: No kubernetes imports. GitLab API via httpx only.
# 3. [Pattern]: Dedup by (project_id, mr_iid) NOT todo.id. Priority-based action selection for multi-todo MRs.
# 4. [Pattern]: Flow gate checks active+queued headhunter events < max_active before creating new events.
# 5. [Pattern]: Circuit breaker: 3 consecutive poll failures -> self-disable, Brain continues.
# 6. [Pattern]: Feedback loop uses asyncio.Event signal from Brain + timeout safety net. Phase 2 only.
# 7. [Gotcha]: mark_as_done is called in feedback loop (on close), NOT during poll.
"""
Headhunter: GitLab todo poller that analyzes assigned MRs/pipelines.

Polls GitLab /todos API, enriches context, classifies via Gemini Flash,
and pushes structured events to the Brain conversation queue.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

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

def _get_static_maintainer_emails() -> list[str]:
    """Read maintainer CSV from env at call time (not import time). Picks up ConfigMap changes on pod restart."""
    return [e.strip() for e in os.getenv("HEADHUNTER_MAINTAINERS", "").split(",") if e.strip()]


class Headhunter:
    """GitLab todo poller -- observes MR/pipeline assignments and creates Darwin events."""

    def __init__(
        self,
        blackboard: BlackboardState,
        close_signal: asyncio.Event | None = None,
    ):
        self.blackboard = blackboard
        self._adapter = None
        self._close_signal = close_signal
        self._poll_interval = int(os.getenv("HEADHUNTER_POLL_INTERVAL", "300"))
        self._max_active = int(os.getenv("HEADHUNTER_MAX_ACTIVE", "1"))
        self._processed_todos: set[tuple[int, int]] = set()
        self._model_name = os.getenv("LLM_MODEL_HEADHUNTER", "gemini-2.0-flash")
        self._llm_enabled = bool(os.getenv("GCP_PROJECT"))
        self._gitlab_host = os.getenv("GITLAB_HOST", "")
        self._gitlab_token: str | None = None
        self._maintainer_source = os.getenv("HEADHUNTER_MAINTAINER_SOURCE", "static")
        self._smartsheet_cache = None  # lazy-loaded only when source=smartsheet

    # =========================================================================
    # LLM Adapter (lazy-loaded, same pattern as Aligner._get_adapter)
    # =========================================================================

    async def _get_adapter(self):
        """Lazy-load LLM adapter (Gemini Flash for Headhunter)."""
        if self._adapter is None and self._llm_enabled:
            try:
                from .llm import create_adapter

                project = os.getenv("GCP_PROJECT")
                location = os.getenv("GCP_LOCATION", "us-central1")
                self._adapter = create_adapter("gemini", project, location, self._model_name)
                logger.info(f"Headhunter LLM adapter initialized: gemini/{self._model_name}")
            except Exception as e:
                logger.warning(f"LLM adapter not available for Headhunter: {e}")
                self._adapter = None
        return self._adapter

    # =========================================================================
    # GitLab API Client
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

    async def poll_cycle(self) -> list[dict]:
        """Fetch pending todos, filter actionable, group by MR, return highest-priority per MR."""
        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            resp = await client.get(
                self._api_url("/todos"),
                headers=self._headers(),
                params={"state": "pending", "type": "MergeRequest"},
            )
            resp.raise_for_status()
            todos = resp.json()

        actionable = [t for t in todos if t.get("action_name") in V1_ACTIONABLE]
        if not actionable:
            return []

        grouped = self._group_by_mr(actionable)
        result = []
        for key, group in grouped.items():
            if key in self._processed_todos:
                continue
            best = min(group, key=lambda t: ACTION_PRIORITY.get(t["action_name"], 99))
            result.append(best)
        return result

    @staticmethod
    def _group_by_mr(todos: list[dict]) -> dict[tuple[int, int], list[dict]]:
        """Group todos by (project_id, mr_iid). Multiple todos for the same MR are collapsed."""
        grouped: dict[tuple[int, int], list[dict]] = {}
        for todo in todos:
            target = todo.get("target", {})
            key = (todo.get("project", {}).get("id", 0), target.get("iid", 0))
            grouped.setdefault(key, []).append(todo)
        return grouped

    async def fetch_context(self, todo: dict) -> dict:
        """Enrich todo with MR diff summary, pipeline status, and failed job log."""
        target = todo.get("target", {})
        project_id = todo["project"]["id"]
        mr_iid = target["iid"]
        action = todo["action_name"]

        context: dict = {
            "action_name": action,
            "mr_title": target.get("title", ""),
            "mr_description": (target.get("description") or "")[:2000],
            "mr_state": target.get("state", ""),
            "merge_status": target.get("merge_status", ""),
            "source_branch": target.get("source_branch", ""),
            "target_branch": target.get("target_branch", ""),
            "author": target.get("author", {}).get("username", ""),
            "labels": target.get("labels", []),
            "milestone": (target.get("milestone") or {}).get("title"),
            "project_path": todo["project"].get("path_with_namespace", ""),
            "target_url": todo.get("target_url", ""),
        }

        async with httpx.AsyncClient(verify=False, timeout=30) as client:
            headers = self._headers()
            changes_resp = await client.get(
                self._api_url(f"/projects/{project_id}/merge_requests/{mr_iid}/changes"),
                headers=headers,
            )
            if changes_resp.is_success:
                changes = changes_resp.json().get("changes", [])
                context["changed_files"] = [c.get("new_path", "") for c in changes[:MAX_CHANGED_FILES]]
            else:
                context["changed_files"] = []

            pipe_resp = await client.get(
                self._api_url(f"/projects/{project_id}/pipelines"),
                headers=headers,
                params={"ref": target.get("source_branch", ""), "order_by": "updated_at", "per_page": "1"},
            )
            pipeline_status = "unknown"
            failed_job_log = ""
            if pipe_resp.is_success:
                pipelines = pipe_resp.json()
                if pipelines:
                    pipeline_status = pipelines[0].get("status", "unknown")
                    if action == "build_failed" and pipeline_status == "failed":
                        pipe_id = pipelines[0]["id"]
                        jobs_resp = await client.get(
                            self._api_url(f"/projects/{project_id}/pipelines/{pipe_id}/jobs"),
                            headers=headers,
                        )
                        if jobs_resp.is_success:
                            failed_jobs = [j for j in jobs_resp.json() if j.get("status") == "failed"]
                            if failed_jobs:
                                trace_resp = await client.get(
                                    self._api_url(f"/projects/{project_id}/jobs/{failed_jobs[0]['id']}/trace"),
                                    headers=headers,
                                )
                                if trace_resp.is_success:
                                    lines = trace_resp.text.splitlines()
                                    failed_job_log = "\n".join(lines[-FAILED_LOG_TAIL:])

            context["pipeline_status"] = pipeline_status
            context["failed_job_log"] = failed_job_log

        return context

    # =========================================================================
    # LLM Analysis (placeholder -- Step 3 probe will finalize the prompt)
    # =========================================================================

    async def analyze_and_plan(self, context: dict) -> tuple[str, str]:
        """LLM call: raw context -> (frontmatter_plan_text, domain).

        Returns a tuple of (plan_text, domain) where domain is clear/complicated/complex.
        Fast-path: known bot patterns skip LLM entirely with a templated plan.
        """
        fast = self._fast_path_plan(context)
        if fast:
            return fast

        adapter = await self._get_adapter()
        if not adapter:
            return self._fallback_plan(context), "complicated"

        prompt = self._build_analysis_prompt(context)
        try:
            response = await adapter.generate(
                system="You are a GitLab MR triage agent. Classify and plan.",
                contents=prompt,
                temperature=0.3,
                max_output_tokens=1024,
            )
            plan_text = response.text.strip()
            domain = self._extract_domain(plan_text)
            return plan_text, domain
        except Exception as e:
            logger.warning(f"LLM analysis failed, using fallback: {e}")
            return self._fallback_plan(context), "complicated"

    @staticmethod
    def _fast_path_plan(context: dict) -> tuple[str, str] | None:
        """Detect known bot patterns and return a templated plan without LLM.

        Returns (plan_text, domain) or None if no fast-path matches.
        """
        author = context.get("author", "")
        action = context.get("action_name", "")
        pipeline = context.get("pipeline_status", "")
        title = context.get("mr_title", "")
        project = context.get("project_path", "")
        url = context.get("target_url", "")

        is_bot_mr = "bot_" in author or "submodule-updater" in author
        is_review = action in ("review_requested", "approval_required")
        is_failed = pipeline == "failed"

        if is_bot_mr and is_review and is_failed:
            plan = (
                f"---\n"
                f"plan: \"Retest failed pipeline on {title}, merge if green, escalate if red\"\n"
                f"service: general\n"
                f"repository: {project}\n"
                f"domain: CLEAR\n"
                f"risk: low\n"
                f"steps:\n"
                f"  - id: retest-and-verify\n"
                f"    agent: developer\n"
                f"    mode: execute\n"
                f"    summary: \"Check MR {url} -- pipeline failed. Retest the pipeline."
                f" If the pipeline passes, merge the MR."
                f" If it fails again, add a comment describing the retry and observed failures."
                f" Notify the maintainer via Slack about the result.\"\n"
                f"    status: pending\n"
                f"---"
            )
            logger.info(f"Fast-path: bot MR + review_requested + failed pipeline -> CLEAR retest plan")
            return plan, "clear"

        if is_bot_mr and is_review and pipeline in ("success", "passed"):
            plan = (
                f"---\n"
                f"plan: \"Pipeline green on bot MR {title}, review and merge\"\n"
                f"service: general\n"
                f"repository: {project}\n"
                f"domain: CLEAR\n"
                f"risk: low\n"
                f"steps:\n"
                f"  - id: merge\n"
                f"    agent: developer\n"
                f"    mode: execute\n"
                f"    summary: \"Review and merge MR {url} -- pipeline is green."
                f" Notify the maintainer via Slack that the MR was merged.\"\n"
                f"    status: pending\n"
                f"---"
            )
            logger.info(f"Fast-path: bot MR + review_requested + green pipeline -> CLEAR merge plan")
            return plan, "clear"

        return None

    def _build_analysis_prompt(self, context: dict) -> str:
        """Build structured prompt for Flash analysis. Used when no fast-path matches."""
        parts = [
            f"Action: {context['action_name']}",
            f"MR: {context['mr_title']}",
            f"State: {context['mr_state']} | Merge status: {context['merge_status']}",
            f"Branch: {context['source_branch']} -> {context['target_branch']}",
            f"Author: {context['author']}",
            f"Pipeline: {context['pipeline_status']}",
            f"Project: {context['project_path']}",
        ]
        if context.get("changed_files"):
            parts.append(f"Changed files ({len(context['changed_files'])}): {', '.join(context['changed_files'][:10])}")
        if context.get("labels"):
            parts.append(f"Labels: {', '.join(context['labels'])}")
        if context.get("failed_job_log"):
            parts.append(f"Failed job log (last {FAILED_LOG_TAIL} lines):\n{context['failed_job_log']}")

        parts.append(
            "\nProduce a YAML frontmatter work plan with fields: plan, service, repository, "
            "domain (CLEAR/COMPLICATED/COMPLEX), risk (low/medium/high), "
            "steps (each with id, agent, mode, summary, status: pending). "
            "Always include: notify the maintainer via Slack about the outcome. "
            "Wrap in --- delimiters."
        )
        return "\n".join(parts)

    @staticmethod
    def _fallback_plan(context: dict) -> str:
        action = context["action_name"]
        title = context["mr_title"]
        project = context["project_path"]
        return (
            f"---\nplan: Handle {action} on {title}\nservice: general\n"
            f"repository: {project}\ndomain: COMPLICATED\nrisk: medium\n"
            f"steps:\n  - id: investigate\n    agent: developer\n    mode: investigate\n"
            f"    summary: \"Investigate {action} on {title}."
            f" Notify the maintainer via Slack about the findings.\"\n    status: pending\n---"
        )

    @staticmethod
    def _extract_domain(plan_text: str) -> str:
        for line in plan_text.splitlines():
            if line.strip().startswith("domain:"):
                val = line.split(":", 1)[1].strip().lower()
                if val in ("clear", "complicated", "complex"):
                    return val
        return "complicated"

    # =========================================================================
    # Event Creation
    # =========================================================================

    async def create_headhunter_event(self, todo: dict, plan_text: str, domain: str) -> str:
        """Push event to Brain queue with embedded plan."""
        from ..models import EventEvidence

        target = todo["target"]
        project = todo["project"]
        project_path = project.get("path_with_namespace", "")
        maintainer = await self.resolve_maintainer(project_path, todo)
        evidence = EventEvidence(
            display_text=f"GitLab: {todo['action_name']} on !{target['iid']} in {project_path}",
            source_type="headhunter",
            domain=domain,
            severity="info",
            gitlab_context={
                "todo_id": todo["id"],
                "action_name": todo["action_name"],
                "project_id": project["id"],
                "project_path": project_path,
                "mr_iid": target["iid"],
                "mr_title": target["title"],
                "mr_state": target.get("state", ""),
                "merge_status": target.get("merge_status", ""),
                "source_branch": target.get("source_branch", ""),
                "target_branch": target.get("target_branch", ""),
                "author": target.get("author", {}).get("username", ""),
                "target_url": todo.get("target_url", ""),
                "pipeline_status": "unknown",
                "maintainer": maintainer,
            },
        )
        resolved_service = await self._resolve_service(project_path)
        event_id = await self.blackboard.create_event(
            source="headhunter",
            service=resolved_service,
            reason=plan_text,
            evidence=evidence,
        )
        self._processed_todos.add((project["id"], target["iid"]))
        logger.info(f"Headhunter event created: {event_id} for {todo['action_name']} on !{target['iid']}")
        return event_id

    async def _resolve_service(self, project_path: str) -> str:
        """Map GitLab project path to a Darwin service name via service registry.

        Fallback: extract the last path segment as a meaningful component name
        (e.g., 'openshift-virtualization/konflux-builds/v4-99/kubevirt' -> 'kubevirt').
        """
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

    async def resolve_maintainer(self, project_path: str, todo: dict) -> dict:
        """Resolve maintainer for escalation. Source controlled by HEADHUNTER_MAINTAINER_SOURCE.

        Returns {source, email, slack_id, name}.
        Chain: configured source -> MR metadata -> static.
        """
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
        """Lookup a GitLab user's email by username. Returns email or None."""
        try:
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                resp = await client.get(
                    self._api_url(f"/users?username={username}"),
                    headers=self._headers(),
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
        """Resolve from Smartsheet API (lazy-loaded). Only active when source=smartsheet."""
        if not self._smartsheet_cache:
            try:
                from .headhunter_smartsheet import SmartsheetMaintainerCache
                token = os.getenv("SMARTSHEET_API_TOKEN", "")
                sheet_id = os.getenv("SMARTSHEET_SHEET_ID", "")
                if not token or not sheet_id:
                    logger.warning("Smartsheet credentials not configured, falling back")
                    return None
                self._smartsheet_cache = SmartsheetMaintainerCache(token, sheet_id)
            except ImportError:
                logger.warning("headhunter_smartsheet module not found, falling back")
                return None
        component = project_path.rsplit("/", 1)[-1] if "/" in project_path else project_path
        return await self._smartsheet_cache.get_maintainer(component)

    # =========================================================================
    # Flow Gate
    # =========================================================================

    async def check_flow_gate(self) -> bool:
        """Return True if a slot is available (active+queued headhunter events < max_active)."""
        active_ids = await self.blackboard.get_active_events()
        count = 0
        for eid in active_ids:
            event = await self.blackboard.get_event(eid)
            if event and event.source == "headhunter" and event.status.value in ("new", "active", "deferred"):
                count += 1
        return count < self._max_active

    # =========================================================================
    # Main Loop (Circuit Breaker)
    # =========================================================================

    async def run(self) -> None:
        """Main loop: poll -> analyze -> create events. Circuit breaker after 3 failures."""
        if not self._gitlab_host:
            logger.warning("Headhunter disabled: GITLAB_HOST not set")
            return

        startup_delay = int(os.getenv("HEADHUNTER_STARTUP_DELAY", "180"))
        logger.info(
            f"Headhunter waiting {startup_delay}s for sidecars to connect before first poll "
            f"(poll={self._poll_interval}s, max_active={self._max_active}, model={self._model_name})"
        )
        await asyncio.sleep(startup_delay)
        logger.info("Headhunter started")

        if self._close_signal:
            asyncio.create_task(self._feedback_loop())
            logger.info("Headhunter feedback loop started (Signal + Poll hybrid)")

        failures = 0
        max_failures = 3
        while True:
            try:
                await self._poll_and_process()
                failures = 0
            except Exception as e:
                failures += 1
                logger.error(f"Headhunter poll failed ({failures}/{max_failures}): {e}")
                if failures >= max_failures:
                    logger.critical("Headhunter disabled after 3 consecutive failures")
                    return
            await asyncio.sleep(self._poll_interval)

    async def _poll_and_process(self) -> None:
        """Single poll cycle: check gate, fetch todos, analyze, create events."""
        if not await self.check_flow_gate():
            logger.debug("Headhunter flow gate closed -- skipping cycle")
            return

        todos = await self.poll_cycle()
        if not todos:
            logger.debug("Headhunter: no actionable todos")
            return

        logger.info(f"Headhunter: {len(todos)} actionable todo(s)")
        for todo in todos:
            if not await self.check_flow_gate():
                logger.info("Headhunter flow gate closed mid-cycle -- stopping")
                break
            project_id = todo.get("project", {}).get("id", 0)
            mr_iid = todo.get("target", {}).get("iid", 0)
            if await self._is_recently_processed(project_id, mr_iid):
                logger.info(f"Headhunter: skipping !{mr_iid} (recently processed)")
                continue
            context = await self.fetch_context(todo)
            plan_text, domain = await self.analyze_and_plan(context)
            await self.create_headhunter_event(todo, plan_text, domain)

    # =========================================================================
    # Feedback Loop (Signal + Poll Hybrid -- Phase 2)
    # =========================================================================

    async def _feedback_loop(self) -> None:
        """Process GitLab feedback for closed headhunter events.

        Wakes instantly via close_signal from Brain, or every poll_interval as safety net.
        """
        while True:
            try:
                await asyncio.wait_for(self._close_signal.wait(), timeout=self._poll_interval)
            except asyncio.TimeoutError:
                pass
            self._close_signal.clear()
            try:
                await self._process_closed_events()
            except Exception as e:
                logger.warning(f"Headhunter feedback loop error (will retry): {e}")

    async def _process_closed_events(self) -> None:
        """Scan recently closed headhunter events and post GitLab feedback."""
        closed_events = await self.blackboard.get_recent_closed_by_source("headhunter", minutes=30)
        if not closed_events:
            return

        for event in closed_events:
            if await self.blackboard.is_feedback_sent(event.id):
                continue

            gl_ctx = None
            if event.event.evidence and hasattr(event.event.evidence, "gitlab_context"):
                gl_ctx = event.event.evidence.gitlab_context
            if not gl_ctx:
                continue

            todo_id = gl_ctx.get("todo_id")
            project_id = gl_ctx.get("project_id")
            mr_iid = gl_ctx.get("mr_iid")
            if not project_id or not mr_iid:
                continue

            last_turn = event.conversation[-1] if event.conversation else None
            summary = (last_turn.thoughts or last_turn.result or "Event closed.") if last_turn else "Event closed."
            is_success = event.status.value == "closed" and "fail" not in summary.lower()

            async with httpx.AsyncClient(verify=False, timeout=30) as client:
                headers = self._headers()

                comment = f"**Darwin {'resolved' if is_success else 'escalation'}:** {summary[:500]}"
                resp = await client.post(
                    self._api_url(f"/projects/{project_id}/merge_requests/{mr_iid}/notes"),
                    headers=headers,
                    json={"body": comment},
                )
                if resp.status_code == 404:
                    logger.info(f"Feedback skip: MR !{mr_iid} not found (deleted?)")
                elif resp.status_code == 429:
                    logger.warning("GitLab rate limited -- skipping remaining feedback this cycle")
                    return
                elif not resp.is_success:
                    logger.warning(f"MR comment failed ({resp.status_code}): {resp.text[:200]}")

                if todo_id:
                    await client.post(
                        self._api_url(f"/todos/{todo_id}/mark_as_done"),
                        headers=headers,
                    )

            await self.blackboard.mark_feedback_sent(event.id)
            logger.info(f"Headhunter feedback sent for {event.id}: {'success' if is_success else 'escalation'} on !{mr_iid}")

    async def _is_recently_processed(self, project_id: int, mr_iid: int) -> bool:
        """Check if this MR was processed in the last 30 minutes (Redis-backed dedup)."""
        recent = await self.blackboard.get_recent_closed_by_source("headhunter", minutes=30)
        for event in recent:
            ctx = getattr(event.event.evidence, "gitlab_context", None) if event.event.evidence else None
            if isinstance(ctx, dict) and ctx.get("project_id") == project_id and ctx.get("mr_iid") == mr_iid:
                return True
        return False
