# BlackBoard/src/agents/headhunter.py
# @ai-rules:
# 1. [Pattern]: Orchestrator — platform-agnostic loop + LLM analysis + circuit breaker.
# 2. [Pattern]: Delegates platform calls to self._gitlab (GitLabPlatform adapter).
# 3. [Constraint]: Brain-facing methods (refresh_mr_state, poll_gitlab_mr_status, etc.)
#    remain on this class as thin delegates for backward compatibility.
# 4. [Pattern]: HeadhunterJira secondary head mounted in main loop (own error boundary).
# 5. [Pattern]: Flow gate uses global WIP cap (MAX_ACTIVE_EVENTS). Conservative count.
# 6. [Pattern]: Circuit breaker: 3 consecutive poll failures -> self-disable.
# 7. [Pattern]: Feedback loop uses poll-interval safety net for cross-pod catch-up.
# 8. [Gotcha]: mark_as_done is called in feedback (on close), NOT during poll.
"""
Headhunter: VCS todo poller that analyzes assigned MRs/pipelines.

Orchestrator pattern — delegates platform-specific operations to adapters:
- GitLabPlatform: GitLab todo polling (primary head)
- HeadhunterJira: Jira issue polling (secondary head)
- GitHubPlatform: GitHub PR polling (future)

LLM analysis (Flash triage) and event lifecycle are platform-agnostic.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

from .headhunter_gitlab import (
    ACTION_PRIORITY,
    GitLabPlatform,
    V1_ACTIONABLE,
)
from .headhunter_jira import HeadhunterJira

logger = logging.getLogger(__name__)


class Headhunter:
    """VCS todo poller orchestrator — platform-agnostic loop with pluggable adapters."""

    def __init__(
        self,
        blackboard: "BlackboardState",
        close_signal: asyncio.Event | None = None,
    ):
        self.blackboard = blackboard
        self._adapter = None
        self._close_signal = close_signal
        self._poll_interval = int(os.getenv("HEADHUNTER_POLL_INTERVAL", "300"))
        self._wip_cap = int(os.getenv("MAX_ACTIVE_EVENTS", "20"))
        self._model_name = os.getenv("LLM_MODEL_HEADHUNTER", "gemini-3.5-flash")
        self._temperature = float(os.getenv("LLM_TEMPERATURE_HEADHUNTER", "0.3"))
        self._thinking_level = os.getenv("LLM_THINKING_HEADHUNTER", "low")
        self._llm_enabled = bool(os.getenv("GCP_PROJECT"))
        self._last_poll_pending: int = 0

        # Platform adapters
        self._gitlab = GitLabPlatform(blackboard)
        self._jira = HeadhunterJira(blackboard)

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
    # LLM Analysis (platform-agnostic)
    # =========================================================================

    async def analyze_and_plan(self, context: dict, system_instruction: str = "") -> tuple[str, str]:
        """LLM-based triage with full context.

        All work items pass through Flash LLM analysis for consistent evidence quality.
        Emergency inline fallback when LLM is unavailable.
        """
        adapter = await self._get_adapter()
        if not adapter:
            logger.warning(f"Emergency fallback plan for {context.get('mr_title', context.get('pr_title', '?'))}")
            return self._emergency_plan(context), "complicated"

        prompt = self._build_analysis_prompt(context)
        try:
            response = await adapter.generate(
                system_prompt=system_instruction,
                contents=prompt,
                temperature=self._temperature,
                max_output_tokens=10000,
                thinking_level=self._thinking_level,
            )
            plan_text = response.text.strip()
            domain = self._extract_domain(plan_text)
            logger.info(f"LLM analysis for {context.get('mr_title', context.get('pr_title', '?'))} -> {domain}")
            return plan_text, domain
        except Exception as e:
            logger.warning(f"LLM analysis failed, using emergency fallback: {e}")
            return self._emergency_plan(context), "complicated"

    @staticmethod
    def _emergency_plan(context: dict) -> str:
        """Minimal YAML plan when LLM is unavailable."""
        action = context.get("action_name", "unknown")
        title = context.get("mr_title", context.get("pr_title", "unknown"))
        project = context.get("project_path", context.get("repo", "unknown"))
        iid = context.get("mr_iid", context.get("pr_number", "?"))
        return (
            f"---\nplan: Investigate {action} on {title}\n"
            f"service: {project.rsplit('/', 1)[-1]}\n"
            f"repository: {project}\n"
            f"domain: COMPLICATED\nrisk: medium\n"
            f"reasoning: LLM analysis unavailable -- manual triage needed\n"
            f"steps:\n  - id: \"1\"\n    agent: developer\n"
            f"    summary: \"Investigate {action} on #{iid} "
            f"in {project}. LLM triage failed -- review manually.\"\n---"
        )

    def _build_analysis_prompt(self, context: dict) -> str:
        """Build structured prompt with full context for LLM analysis."""
        parts = [
            f"Action: {context.get('action_name', 'unknown')}",
            f"MR: {context.get('mr_title', context.get('pr_title', 'unknown'))}",
            f"State: {context.get('mr_state', context.get('pr_state', 'unknown'))} | "
            f"Merge status: {context.get('merge_status', context.get('mergeable', 'unknown'))}",
            f"Branch: {context.get('source_branch', context.get('head_branch', '?'))} -> "
            f"{context.get('target_branch', context.get('base_branch', '?'))}",
            f"Author: {context.get('author', 'unknown')}",
            f"Pipeline: {context.get('pipeline_status', context.get('check_status', 'unknown'))}",
        ]
        if context.get("pipeline_id"):
            parts.append(f"Pipeline ID: {context['pipeline_id']}")
        parts.append(f"Project: {context.get('project_path', context.get('repo', 'unknown'))}")
        if context.get("mr_description") or context.get("pr_body"):
            parts.append(f"Description:\n{context.get('mr_description', context.get('pr_body', ''))}")
        if context.get("changed_files"):
            parts.append(f"Changed files ({len(context['changed_files'])}): {', '.join(context['changed_files'][:10])}")
        if context.get("labels"):
            parts.append(f"Labels: {', '.join(context['labels'])}")
        if context.get("failed_job_names"):
            parts.append(f"Failed jobs ({context.get('failed_job_count', '?')}/{context.get('total_job_count', '?')} total): {', '.join(context['failed_job_names'])}")
        if context.get("failed_job_log"):
            parts.append(f"First failed job log (last lines):\n{context['failed_job_log']}")
        if context.get("recent_notes") or context.get("recent_comments"):
            notes = context.get("recent_notes", context.get("recent_comments", []))
            parts.append(f"Recent comments (newest first):\n" + "\n".join(notes))
        if context.get("mention_comment"):
            parts.append(f"Request from @{context.get('mention_author', 'unknown')}: {context['mention_comment']}")

        parts.append("\nProduce a YAML frontmatter work plan.")
        return "\n".join(parts)

    @staticmethod
    def _extract_domain(plan_text: str) -> str:
        for line in plan_text.splitlines():
            if line.strip().startswith("domain:"):
                val = line.split(":", 1)[1].strip().lower()
                if val in ("clear", "complicated", "complex"):
                    return val
        return "complicated"

    # =========================================================================
    # Flow Gate (platform-agnostic)
    # =========================================================================

    @property
    def pending_count(self) -> int:
        """Pending items from last poll cycle (not yet converted to events)."""
        return self._last_poll_pending

    async def check_flow_gate(self) -> bool:
        """Back off when system is at global WIP capacity."""
        status_map = await self.blackboard.get_active_events_with_status()
        wip_used = sum(1 for s in status_map.values() if s in ("new", "active", "deferred"))
        return wip_used < self._wip_cap

    # =========================================================================
    # Main Loop (Circuit Breaker)
    # =========================================================================

    async def run(self) -> None:
        """Main loop: poll -> analyze -> create events. Circuit breaker after 3 failures."""
        if not self._gitlab.enabled():
            logger.warning("Headhunter disabled: GITLAB_HOST not set")
            return

        startup_delay = int(os.getenv("HEADHUNTER_STARTUP_DELAY", "180"))
        logger.info(
            f"Headhunter waiting {startup_delay}s for sidecars to connect before first poll "
            f"(poll={self._poll_interval}s, cap={self._wip_cap}, model={self._model_name})"
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
            if self._jira.enabled():
                try:
                    await self._jira.poll_and_process()
                except Exception as e:
                    logger.warning(f"Headhunter Jira poll failed (non-fatal): {e}")
            if self._close_signal:
                try:
                    await asyncio.wait_for(self._close_signal.wait(), timeout=self._poll_interval)
                    self._close_signal.clear()
                    logger.debug("Headhunter poll woke early: event closed, slot may be open")
                except asyncio.TimeoutError:
                    pass
            else:
                await asyncio.sleep(self._poll_interval)

    async def _poll_and_process(self) -> None:
        """Single poll cycle: check gate, fetch items, analyze, create events."""
        if not await self.check_flow_gate():
            logger.debug("Headhunter flow gate closed -- skipping cycle")
            return

        todos = await self._gitlab.poll_work_items()
        self._last_poll_pending = len(todos)
        if not todos:
            logger.debug("Headhunter: no actionable items")
            return

        logger.info(f"Headhunter: {len(todos)} actionable item(s)")
        si = self._gitlab.load_triage_instruction()
        for todo in todos:
            if not await self.check_flow_gate():
                logger.info("Headhunter flow gate closed mid-cycle -- stopping")
                break
            context = await self._gitlab.fetch_context(todo)
            plan_text, domain = await self.analyze_and_plan(context, si)
            await self._gitlab.create_platform_event(todo, plan_text, domain, context)

    # =========================================================================
    # Feedback Loop (Signal + Poll Hybrid)
    # =========================================================================

    async def _feedback_loop(self) -> None:
        """Process platform feedback for closed headhunter events."""
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

    async def process_event_feedback(self, event_id: str) -> None:
        """Process feedback for a single closed headhunter event (called by Brain)."""
        if await self.blackboard.is_feedback_sent(event_id):
            return
        event = await self.blackboard.get_event(event_id)
        if not event:
            return
        await self._gitlab.post_feedback(event)

    async def _process_closed_events(self) -> None:
        """Scan closed headhunter events and post platform feedback."""
        closed_events = await self.blackboard.get_recent_closed_by_source("headhunter", minutes=1440)
        if not closed_events:
            return
        for event in closed_events:
            if await self.blackboard.is_feedback_sent(event.id):
                continue
            await self._gitlab.post_feedback(event)

    # =========================================================================
    # Brain-Facing Delegates (backward-compatible API)
    # =========================================================================

    async def refresh_mr_state(self, event_id: str, *,
                               override_project_id: int | None = None,
                               override_mr_iid: int | None = None) -> dict:
        """Delegate to GitLab adapter. Called by handlers_integration.py."""
        return await self._gitlab.refresh_mr_state(
            event_id,
            override_project_id=override_project_id,
            override_mr_iid=override_mr_iid,
        )

    async def poll_gitlab_mr_status(self, project_id: int, mr_iid: int) -> dict:
        """Delegate to GitLab adapter. Registered as StateWatcher poll fn."""
        return await self._gitlab.poll_gitlab_mr_status(project_id, mr_iid)

    @staticmethod
    def extract_gitlab_state_key(state: dict) -> dict:
        """Delegate to GitLab adapter. Used by StateWatcher."""
        return GitLabPlatform.extract_gitlab_state_key(state)

    @staticmethod
    def parse_mr_url(url: str) -> tuple[int | str, int] | None:
        """Delegate to GitLab adapter. Called by handlers_integration.py."""
        return GitLabPlatform.parse_mr_url(url)

    async def resolve_project_id(self, path_or_id) -> int | None:
        """Delegate to GitLab adapter. Called by handlers_integration.py."""
        return await self._gitlab.resolve_project_id(path_or_id)

    @staticmethod
    def _group_by_mr(todos: list[dict]) -> dict[tuple[int, int], list[dict]]:
        """Delegate to GitLab adapter. Exposed for backward compatibility."""
        return GitLabPlatform._group_by_mr(todos)

    @staticmethod
    def _classify_severity(action_name: str, pipeline_status: str) -> str:
        """Delegate to GitLab adapter. Exposed for backward compatibility."""
        return GitLabPlatform.classify_severity(action_name, pipeline_status)

    async def _resolve_service(self, project_path: str) -> str:
        """Delegate to GitLab adapter. Exposed for backward compatibility."""
        return await self._gitlab._resolve_service(project_path)

    async def create_headhunter_event(self, todo: dict, plan_text: str, domain: str, context: dict) -> str:
        """Delegate to GitLab adapter. Called by tests and legacy code paths."""
        return await self._gitlab.create_platform_event(todo, plan_text, domain, context)

    async def poll_cycle(self) -> list[dict]:
        """Delegate to GitLab adapter. Exposed for backward compatibility."""
        result = await self._gitlab.poll_work_items()
        self._last_poll_pending = len(result)
        return result
