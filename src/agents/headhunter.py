# BlackBoard/src/agents/headhunter.py
# @ai-rules:
# 1. [Pattern]: Orchestrator — platform-agnostic loop + LLM analysis + circuit breaker.
# 2. [Pattern]: Delegates platform calls to self._gitlab and self._github adapters.
# 3. [Constraint]: Brain-facing methods (refresh_mr_state, poll_gitlab_mr_status, etc.)
#    remain on this class as thin delegates for backward compatibility.
# 4. [Pattern]: HeadhunterJira secondary head mounted in main loop (own error boundary).
# 5. [Pattern]: Flow gate uses global WIP cap (MAX_ACTIVE_EVENTS). Conservative count.
# 6. [Pattern]: Circuit breaker per-head: 3 consecutive failures -> latch disable that head.
# 7. [Pattern]: Feedback loop uses poll-interval safety net for cross-pod catch-up.
# 8. [Gotcha]: mark_as_done is called in feedback (on close), NOT during poll.
# 9. [Pattern]: process_event_feedback routes by evidence context (github_context vs gitlab_context).
# 10. [Pattern]: issue_title sanitized (replace </ → < /) in _build_issue_analysis_prompt.
# 11. [Pattern]: Phase B uses gate_closed flag — no per-item Redis gate re-check after first closure.
# 12. [Pattern]: _github_pending zeroed when all new items are queued (avoids double-count in pending_count).
# 13. [Pattern]: No input truncation on descriptions — full text flows to Flash (1M+ context).
#     Output controlled by max_output_tokens. _COMMENT_LIMIT (default 2000) for aggregated notes only.
# 14. [Pattern]: analyze_and_plan returns plan_text only (str). Domain classification removed —
#     events land in disorder, FRIDAY classifies during triage.
# 15. [Pattern]: Per-item try/except in all GitHub drain loops (Phase A/B PRs, Phase A/B
#     Issues) isolates one bad item (e.g. None title) from starving the rest of the batch
#     or bubbling out of _github_poll_and_process and tripping the GitHub circuit breaker.
# 16. [Pattern]: Issue queue mirrors PR queue (Phase A promote FIFO, Phase B queue-on-close)
#     but is purely additive — _queue_issue adds darwin-queued without removing darwin-work,
#     since _poll_issues filters server-side on labels=darwin-work.
# 17. [Pattern]: _raise_if_systemic_failure() escalates a fully-failed 2+ item drain-loop
#     batch (Phase A/B, PR and Issue) instead of the cycle "succeeding" silently and
#     resetting github_failures. PR-side Phase A/B escalation propagates all the way to
#     Headhunter.run()'s circuit breaker (github_failures). Issue-side Phase A/B escalation
#     is caught and logged as a WARNING by its caller (_github_poll_and_process's wrapper
#     around _github_poll_issues) — it does NOT reach the circuit breaker, since issue
#     failures must not trip the shared PR/Issue GitHub circuit breaker (see issue #230).
#     A single failing item (the poison-pill case) never triggers this — that must stay
#     isolated regardless of phase.
"""
Headhunter: VCS todo poller that analyzes assigned MRs/pipelines.

Orchestrator pattern — delegates platform-specific operations to adapters:
- GitLabPlatform: GitLab todo polling (primary head)
- GitHubPlatform: GitHub PR polling (secondary head)
- HeadhunterJira: Jira issue polling (tertiary head)

LLM analysis (Flash triage) and event lifecycle are platform-agnostic.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

from .headhunter_github import GitHubPlatform
from .headhunter_gitlab import (
    ACTION_PRIORITY,
    GitLabPlatform,
    V1_ACTIONABLE,
)
from .headhunter_jira import HeadhunterJira

logger = logging.getLogger(__name__)

from .headhunter_utils import _COMMENT_LIMIT, _safe_int  # noqa: E402

import re

_XML_CLOSE_TAG = re.compile(r"</(?:description|job_log|comments|mention_request|issue_body)>")


def _sanitize_xml_fence(text: str) -> str:
    """Strip XML closing tags that could break prompt fencing."""
    return _XML_CLOSE_TAG.sub("", text) if text else text


_SYSTEMIC_FAILURE_MIN_BATCH = 2


def _raise_if_systemic_failure(phase: str, attempted: int, failed: int) -> None:
    """Escalate a fully-failed multi-item batch instead of silently swallowing it.

    Per-item try/except exists so one poison-pill item (attempted=1, failed=1)
    can't block the rest of a batch or trip the circuit breaker -- that must stay
    silent (WARNING only). But when 2+ items were attempted and every single one
    failed, N independent bad items is a far less likely explanation than a
    systemic cause (installation token expiry, downstream Blackboard outage) that
    will keep failing every item on every future cycle too. Raising here lets the
    caller's existing circuit breaker (github_failures in Headhunter.run) see it
    instead of the cycle silently "succeeding" and resetting the failure count.
    """
    if attempted >= _SYSTEMIC_FAILURE_MIN_BATCH and failed == attempted:
        raise RuntimeError(
            f"GitHub {phase}: all {attempted} item(s) failed -- treating as systemic failure"
        )


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
        self._model_name = os.getenv("LLM_MODEL_HEADHUNTER", "gemini-3.7-flash")
        self._temperature = float(os.getenv("LLM_TEMPERATURE_HEADHUNTER", "0.3"))
        self._thinking_level = os.getenv("LLM_THINKING_HEADHUNTER", "low")
        self._max_output_tokens = _safe_int("LLM_MAX_TOKENS_HEADHUNTER", 10000)
        self._llm_enabled = bool(os.getenv("GCP_PROJECT"))
        self._gitlab_pending: int = 0
        self._github_pending: int = 0
        self._github_issue_pending: int = 0
        self._github_queued: int = 0
        self._github_issue_queued: int = 0

        # Platform adapters
        self._gitlab = GitLabPlatform(blackboard)
        self._github = GitHubPlatform(blackboard)
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
            return self._emergency_plan(context)

        prompt = (
            self._build_issue_analysis_prompt(context)
            if "issue_number" in context
            else self._build_analysis_prompt(context)
        )
        try:
            response = await adapter.generate(
                system_prompt=system_instruction,
                contents=prompt,
                temperature=self._temperature,
                max_output_tokens=self._max_output_tokens,
                thinking_level=self._thinking_level,
            )
            from .llm import record_token_usage
            record_token_usage("headhunter", response.usage)
            plan_text = response.text.strip()
            logger.info(f"LLM analysis for {context.get('mr_title', context.get('pr_title', '?'))}")
            return plan_text
        except Exception as e:
            logger.warning(f"LLM analysis failed, using emergency fallback: {e}")
            return self._emergency_plan(context)

    @staticmethod
    def _emergency_plan(context: dict) -> str:
        """Minimal YAML plan when LLM is unavailable."""
        action = context.get("action_name", "unknown")
        title = context.get("mr_title", context.get("pr_title", "unknown"))
        project = context.get("project_path", context.get("repo", "unknown"))
        raw_iid = context.get("mr_iid", context.get("pr_number", "?"))
        iid = f"!{raw_iid}" if context.get("mr_iid") else f"#{raw_iid}"
        return (
            f"---\nplan: Investigate {action} on {title}\n"
            f"service: {project.rsplit('/', 1)[-1]}\n"
            f"repository: {project}\n"
            f"risk: medium\n"
            f"reasoning: LLM analysis unavailable -- manual triage needed\n"
            f"steps:\n  - id: \"1\"\n    agent: developer\n"
            f"    summary: \"Investigate {action} on {iid} "
            f"in {project}. LLM triage failed -- review manually.\"\n---"
        )

    def _build_analysis_prompt(self, context: dict) -> str:
        """Build structured prompt with full context for LLM analysis."""
        parts = [
            f"Action: {context.get('action_name', 'unknown')}",
            f"MR: {context.get('mr_title') or context.get('pr_title') or 'unknown'}",
            f"State: {context.get('mr_state') or context.get('pr_state') or 'unknown'} | "
            f"Merge status: {context.get('merge_status') or context.get('mergeable') or 'unknown'}",
            f"Branch: {context.get('source_branch') or context.get('head_branch') or '?'} -> "
            f"{context.get('target_branch') or context.get('base_branch') or '?'}",
            f"Author: {context.get('author', 'unknown')}",
            f"Pipeline: {context.get('pipeline_status') or context.get('check_status') or 'unknown'}",
        ]
        if context.get("pipeline_id"):
            parts.append(f"Pipeline ID: {context['pipeline_id']}")
        parts.append(f"Project: {context.get('project_path', context.get('repo', 'unknown'))}")
        if context.get("mr_description") or context.get("pr_body"):
            desc = _sanitize_xml_fence(context.get('mr_description', context.get('pr_body', '')))
            parts.append(f"<description>\n{desc}\n</description>")
        if context.get("changed_files"):
            parts.append(f"Changed files ({len(context['changed_files'])}): {', '.join(context['changed_files'][:10])}")
        if context.get("labels"):
            parts.append(f"Labels: {', '.join(context['labels'])}")
        if context.get("failed_job_names"):
            parts.append(f"Failed jobs ({context.get('failed_job_count', '?')}/{context.get('total_job_count', '?')} total): {', '.join(context['failed_job_names'])}")
        if context.get("failed_job_log"):
            log = _sanitize_xml_fence(context['failed_job_log'])
            parts.append(f"<job_log>\n{log}\n</job_log>")
        if context.get("recent_notes") or context.get("recent_comments"):
            notes = context.get("recent_notes", context.get("recent_comments", []))
            joined = _sanitize_xml_fence("\n".join(notes)[:_COMMENT_LIMIT])
            parts.append(f"<comments>\n{joined}\n</comments>")
        if context.get("mention_comment"):
            author = context.get('mention_author', 'unknown').replace('"', '')
            comment = _sanitize_xml_fence(context['mention_comment'])
            parts.append(f"<mention_request author=\"{author}\">\n{comment}\n</mention_request>")

        parts.append("\nProduce a YAML frontmatter work plan.")
        return "\n".join(parts)

    @staticmethod
    def _build_issue_analysis_prompt(context: dict) -> str:
        """Build issue-specific prompt. Excludes PR-only fields (branch, pipeline, merge, head_sha)."""
        # Sanitize title to prevent XML-like breakout in the prompt
        title = (context.get("issue_title") or "unknown").replace("</", "< /")
        parts = [
            f"GitHub Issue #{context.get('issue_number', '?')}: {title}",
            f"Repo: {context.get('owner', '?')}/{context.get('repo', '?')}",
            f"State: {context.get('state', 'open')} | Author: {context.get('author', 'unknown')}",
        ]
        if context.get("labels"):
            parts.append(f"Labels: {', '.join(context['labels'])}")
        if context.get("assignees"):
            parts.append(f"Assignees: {', '.join(context['assignees'])}")
        body = context.get("body", "").replace("</issue_body>", "")
        if body:
            parts.append(f"<issue_body>\n{body}\n</issue_body>")
        if context.get("skill_label"):
            parts.append(f"Skill context: {context['skill_label']} routing")
        parts.append("\nProduce a YAML frontmatter work plan.")
        return "\n".join(parts)

    # =========================================================================
    # Flow Gate (platform-agnostic)
    # =========================================================================

    @property
    def pending_count(self) -> int:
        """Pending items from last poll cycle (not yet converted to events)."""
        return (
            self._gitlab_pending
            + self._github_pending
            + self._github_issue_pending
            + self._github_queued
            + self._github_issue_queued
        )

    async def check_flow_gate(self) -> bool:
        """Back off when system is at global WIP capacity."""
        status_map = await self.blackboard.get_active_events_with_status()
        wip_used = sum(1 for s in status_map.values() if s in ("new", "active", "deferred"))
        return wip_used < self._wip_cap

    # =========================================================================
    # Main Loop (Circuit Breaker)
    # =========================================================================

    async def run(self) -> None:
        """Main loop: poll -> analyze -> create events. Per-head circuit breaker."""
        if not self._gitlab.enabled() and not self._github.enabled():
            logger.warning("Headhunter disabled: neither GITLAB_HOST nor GITHUB set")
            return

        startup_delay = int(os.getenv("HEADHUNTER_STARTUP_DELAY", "180"))
        heads = []
        if self._gitlab.enabled():
            heads.append("gitlab")
        if self._github.enabled():
            heads.append("github")
        logger.info(
            f"Headhunter waiting {startup_delay}s for sidecars to connect before first poll "
            f"(poll={self._poll_interval}s, cap={self._wip_cap}, model={self._model_name}, "
            f"heads={heads})"
        )
        await asyncio.sleep(startup_delay)
        logger.info("Headhunter started")

        if self._close_signal:
            asyncio.create_task(self._feedback_loop())
            logger.info("Headhunter feedback loop started (Signal + Poll hybrid)")

        gitlab_failures = 0
        github_failures = 0
        max_failures = 3
        _gitlab_disabled = False
        _github_disabled = False

        while True:
            # GitLab head
            if self._gitlab.enabled() and not _gitlab_disabled:
                try:
                    await self._poll_and_process()
                    gitlab_failures = 0
                except Exception as e:
                    gitlab_failures += 1
                    logger.error(f"Headhunter GitLab poll failed ({gitlab_failures}/{max_failures}): {e}")
                    if gitlab_failures >= max_failures:
                        logger.critical("Headhunter GitLab head disabled after 3 consecutive failures")
                        _gitlab_disabled = True

            # GitHub head
            if self._github.enabled() and not _github_disabled:
                try:
                    await self._github_poll_and_process()
                    github_failures = 0
                except httpx.HTTPStatusError as e:
                    if e.response.status_code in (401, 403):
                        logger.error(f"Headhunter GitHub auth error ({e.response.status_code}) — not counting toward circuit breaker")
                    else:
                        github_failures += 1
                        logger.error(f"Headhunter GitHub poll failed ({github_failures}/{max_failures}): {e}")
                        if github_failures >= max_failures:
                            logger.critical("Headhunter GitHub head disabled after 3 consecutive failures")
                            _github_disabled = True
                except Exception as e:
                    github_failures += 1
                    logger.error(f"Headhunter GitHub poll failed ({github_failures}/{max_failures}): {e}")
                    if github_failures >= max_failures:
                        logger.critical("Headhunter GitHub head disabled after 3 consecutive failures")
                        _github_disabled = True

            # Both heads latched off → exit
            gitlab_dead = not self._gitlab.enabled() or _gitlab_disabled
            github_dead = not self._github.enabled() or _github_disabled
            if gitlab_dead and github_dead:
                logger.critical("Headhunter: all VCS heads disabled, shutting down")
                await self._github.close()
                return

            # Jira head (independent error boundary)
            if self._jira.enabled():
                try:
                    await self._jira.poll_and_process()
                except Exception as e:
                    logger.warning(f"Headhunter Jira poll failed (non-fatal): {e}")

            # Sleep or wait for close signal
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
        """Single GitLab poll cycle: check gate, fetch items, analyze, create events."""
        if not await self.check_flow_gate():
            logger.debug("Headhunter flow gate closed -- skipping GitLab cycle")
            return

        todos = await self._gitlab.poll_work_items()
        self._gitlab_pending = len(todos)
        if not todos:
            logger.debug("Headhunter GitLab: no actionable items")
            return

        logger.info(f"Headhunter GitLab: {len(todos)} actionable item(s)")
        si = self._gitlab.load_triage_instruction()
        for todo in todos:
            if not await self.check_flow_gate():
                logger.info("Headhunter flow gate closed mid-cycle -- stopping")
                break
            context = await self._gitlab.fetch_context(todo)
            plan_text = await self.analyze_and_plan(context, si)
            await self._gitlab.create_platform_event(todo, plan_text, context)

    async def _github_poll_and_process(self) -> None:
        """Single GitHub poll cycle: promote queued PRs, create events for new, poll issues.

        Order: (1) reset queued cache, (2) poll ALL items (always — gate must not skip poll,
        UI needs queued state), (3) separate queued/new, (4) check gate: if open promote queued
        + process new; if closed queue new items and expose queued state for observability.
        (5) poll issues.
        """
        # Reset queued cache at top of cycle
        self._github._last_queued_prs = []

        # Always poll regardless of gate state — UI needs queued count even when gate is closed
        prs = await self._github.poll_work_items()
        queued_items = sorted(
            [p for p in prs if p.get("queued")],
            key=lambda x: x.get("created_at", ""),
        )
        new_items = [p for p in prs if not p.get("queued")]
        self._github_pending = len(new_items)

        if not await self.check_flow_gate():
            logger.debug("Headhunter flow gate closed -- queuing new PRs, observing queued state")
            # Queue all new items so they get the darwin-queued label
            for i, pr in enumerate(new_items, start=len(queued_items) + 1):
                try:
                    await self._github._queue_pr(pr, i)
                except Exception as e:
                    logger.warning(
                        f"GitHub queue PR failed for "
                        f"{pr.get('owner')}/{pr.get('repo')}#{pr.get('number')}: {e}"
                    )
            # Expose all queued items for /headhunter/pending observability
            newly_queued = [{**pr, "queued": True} for pr in new_items]
            self._github._last_queued_prs = queued_items + newly_queued
            self._github_queued = len(self._github._last_queued_prs)
            self._github_pending = 0  # All new items moved to queued state — avoid double-count
            try:
                await self._github_poll_issues()
            except Exception as e:
                logger.warning(f"GitHub issue poll failed (non-fatal): {e}")
            return

        si = self._github.load_triage_instruction()

        # Phase A: Promote oldest queued PRs first (FIFO)
        remaining_queued = list(queued_items)
        attempted_a = 0
        failed_a = 0
        for pr in queued_items:
            if not await self.check_flow_gate():
                break
            attempted_a += 1
            try:
                context = await self._github.fetch_context(pr)
                plan_text = await self.analyze_and_plan(context, si)
                await self._github.create_platform_event(pr, plan_text, context)
                # Remove by identity, not position -- a prior item may have failed
                # and been skipped, so the promoted item is not necessarily index 0.
                remaining_queued = [q for q in remaining_queued if q is not pr]
            except Exception as e:
                failed_a += 1
                logger.warning(
                    f"GitHub queued PR processing failed for "
                    f"{pr.get('owner')}/{pr.get('repo')}#{pr.get('number')}: {e}"
                )
                continue
        # Bookkeeping BEFORE the escalation raise below -- /headhunter/pending must
        # reflect current queue state even when Phase A hits a systemic failure and
        # raises past this point. Otherwise the cache stays stale-empty (reset at
        # cycle top) for the outage window this feature exists to surface.
        self._github._last_queued_prs = remaining_queued
        self._github_queued = len(remaining_queued)
        # A fully-failed multi-item batch is more likely systemic (auth/outage)
        # than N coincidental poison pills -- escalate past the circuit breaker.
        _raise_if_systemic_failure("PR Phase A (queued promote)", attempted_a, failed_a)

        # Phase B: Process new darwin-review PRs.
        # gate_closed flag avoids per-item Redis gate re-check once closure is confirmed.
        gate_closed = False
        newly_queued_in_phase_b = 0
        attempted_b = 0
        failed_b = 0
        for pr in new_items:
            attempted_b += 1
            if gate_closed or not await self.check_flow_gate():
                gate_closed = True
                position = len(remaining_queued) + 1
                try:
                    await self._github._queue_pr(pr, position)
                    remaining_queued.append({**pr, "queued": True})
                    newly_queued_in_phase_b += 1
                except Exception as e:
                    failed_b += 1
                    logger.warning(
                        f"GitHub queue PR failed for "
                        f"{pr.get('owner')}/{pr.get('repo')}#{pr.get('number')}: {e}"
                    )
                continue
            try:
                context = await self._github.fetch_context(pr)
                plan_text = await self.analyze_and_plan(context, si)
                await self._github.create_platform_event(pr, plan_text, context)
            except Exception as e:
                failed_b += 1
                logger.warning(
                    f"GitHub PR processing failed for "
                    f"{pr.get('owner')}/{pr.get('repo')}#{pr.get('number')}: {e}"
                )
                continue
        # Bookkeeping BEFORE the escalation raise below -- /headhunter/pending must
        # reflect current queue state even when Phase B hits a systemic failure and
        # raises past this point. Otherwise the cache stays stale-empty (reset at
        # cycle top) for the outage window this feature exists to surface.
        self._github._last_queued_prs = remaining_queued
        self._github_queued = len(remaining_queued)
        _raise_if_systemic_failure("PR Phase B (new items)", attempted_b, failed_b)

        # Subtract newly-queued items from pending — they moved to queued state (avoids double-count)
        self._github_pending = max(0, self._github_pending - newly_queued_in_phase_b)

        if not queued_items and not new_items:
            logger.debug("Headhunter GitHub: no actionable PRs")

        # Phase C: Poll Issues (darwin-work label) — no queuing for issues
        try:
            await self._github_poll_issues()
        except Exception as e:
            logger.warning(f"GitHub issue poll failed (non-fatal): {e}")

    async def _github_poll_issues(self) -> None:
        """Poll GitHub Issues (darwin-work label), queue/promote to mirror PR Phase A/B.

        `_poll_issues` filters server-side by `labels=darwin-work` only — this is
        intentional (see _queue_issue) so already-queued issues (which keep
        darwin-work + gain darwin-queued) still surface here. Classification into
        queued/new happens client-side by checking for the darwin-queued label.
        Gate open: promote queued FIFO, then process new (queuing any that arrive
        after the gate closes mid-loop). Gate closed: queue all new items and
        expose queued state for /headhunter/pending observability.
        """
        self._github._last_queued_issues = []

        prev_pending = self._github_issue_pending
        try:
            issues = await self._github.poll_issues_all_installations()
        except Exception as e:
            logger.warning(f"GitHub issue poll failed (preserving last count={prev_pending}): {e}")
            return

        queued_items = sorted(
            [i for i in issues if self._github._queued_label in i.get("labels", [])],
            key=lambda x: x.get("created_at", ""),
        )
        new_items = [i for i in issues if self._github._queued_label not in i.get("labels", [])]
        self._github_issue_pending = len(new_items)

        if not await self.check_flow_gate():
            logger.debug("Headhunter flow gate closed -- queuing new issues, observing queued state")
            for i, issue in enumerate(new_items, start=len(queued_items) + 1):
                try:
                    await self._github._queue_issue(issue, i)
                except Exception as e:
                    logger.warning(
                        f"GitHub queue issue failed for "
                        f"{issue.get('owner')}/{issue.get('repo')}#{issue.get('issue_number')}: {e}"
                    )
            newly_queued = [{**issue, "queued": True} for issue in new_items]
            self._github._last_queued_issues = queued_items + newly_queued
            self._github_issue_queued = len(self._github._last_queued_issues)
            self._github_issue_pending = 0  # All new items moved to queued state — avoid double-count
            return

        if issues:
            logger.info(f"Headhunter GitHub Issues: {len(issues)} actionable issue(s)")

        # Phase A: Promote oldest queued Issues first (FIFO)
        remaining_queued = list(queued_items)
        attempted_a = 0
        failed_a = 0
        for issue in queued_items:
            if not await self.check_flow_gate():
                break
            attempted_a += 1
            try:
                # Load label-specific SI then triage via LLM (same path as PR triage).
                # skill_warning is non-None when skill URL exceeded 10KB cap.
                si, skill_warning = await self._github._load_issue_triage_instruction(issue.get("labels", []))
                plan_text = await self.analyze_and_plan(issue, si)
                event_issue = {**issue, "_skill_size_warning": skill_warning} if skill_warning else issue
                await self._github.create_issue_event(event_issue, plan_text)
                # Remove by identity, not position -- a prior item may have failed
                # and been skipped, so the promoted item is not necessarily index 0.
                remaining_queued = [q for q in remaining_queued if q is not issue]
            except Exception as e:
                failed_a += 1
                logger.warning(
                    f"GitHub queued issue processing failed for "
                    f"{issue.get('owner')}/{issue.get('repo')}#{issue.get('issue_number')}: {e}"
                )
                continue
        # Bookkeeping BEFORE the escalation raise below -- /headhunter/pending must
        # reflect current queue state even when Phase A hits a systemic failure and
        # raises past this point. Otherwise the cache stays stale-empty (reset at
        # cycle top) for the outage window this feature exists to surface.
        self._github._last_queued_issues = remaining_queued
        self._github_issue_queued = len(remaining_queued)
        # A fully-failed multi-item batch is more likely systemic (auth/outage)
        # than N coincidental poison pills -- escalate so it's visible, even though
        # the Phase C caller intentionally swallows it (issue failures must not
        # trip the shared PR/Issue GitHub circuit breaker -- see issue #230).
        _raise_if_systemic_failure("Issue Phase A (queued promote)", attempted_a, failed_a)

        # Phase B: Process new issues (darwin-work label, not yet queued).
        gate_closed = False
        newly_queued_in_phase_b = 0
        attempted_b = 0
        failed_b = 0
        for issue in new_items:
            attempted_b += 1
            if gate_closed or not await self.check_flow_gate():
                gate_closed = True
                position = len(remaining_queued) + 1
                try:
                    await self._github._queue_issue(issue, position)
                    remaining_queued.append({**issue, "queued": True})
                    newly_queued_in_phase_b += 1
                except Exception as e:
                    failed_b += 1
                    logger.warning(
                        f"GitHub queue issue failed for "
                        f"{issue.get('owner')}/{issue.get('repo')}#{issue.get('issue_number')}: {e}"
                    )
                continue
            try:
                si, skill_warning = await self._github._load_issue_triage_instruction(issue.get("labels", []))
                plan_text = await self.analyze_and_plan(issue, si)
                if skill_warning:
                    issue = {**issue, "_skill_size_warning": skill_warning}
                await self._github.create_issue_event(issue, plan_text)
            except Exception as e:
                failed_b += 1
                logger.warning(
                    f"GitHub issue processing failed for "
                    f"{issue.get('owner')}/{issue.get('repo')}#{issue.get('issue_number')}: {e}"
                )
                continue
        # Bookkeeping BEFORE the escalation raise below -- /headhunter/pending must
        # reflect current queue state even when Phase B hits a systemic failure and
        # raises past this point. Otherwise the cache stays stale-empty (reset at
        # cycle top) for the outage window this feature exists to surface.
        self._github._last_queued_issues = remaining_queued
        self._github_issue_queued = len(remaining_queued)
        _raise_if_systemic_failure("Issue Phase B (new items)", attempted_b, failed_b)

        # Subtract newly-queued items from pending — they moved to queued state (avoids double-count)
        self._github_issue_pending = max(0, self._github_issue_pending - newly_queued_in_phase_b)

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
        evidence = event.event.evidence if event.event else None
        if evidence and getattr(evidence, "github_issue_context", None):
            await self._github.post_issue_feedback(event)
        elif evidence and getattr(evidence, "github_context", None):
            await self._github.post_feedback(event)
        elif evidence and getattr(evidence, "gitlab_context", None):
            await self._gitlab.post_feedback(event)
        else:
            await self._gitlab.post_feedback(event)

    async def _process_closed_events(self) -> None:
        """Scan closed headhunter events and post platform feedback."""
        closed_events = await self.blackboard.get_recent_closed_by_source("headhunter", minutes=1440)
        if not closed_events:
            return
        for event in closed_events:
            if await self.blackboard.is_feedback_sent(event.id):
                continue
            evidence = event.event.evidence if event.event else None
            if evidence and getattr(evidence, "github_issue_context", None):
                await self._github.post_issue_feedback(event)
            elif evidence and getattr(evidence, "github_context", None):
                await self._github.post_feedback(event)
            else:
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

    async def poll_gitlab_pipeline_status(self, project_id: int, pipeline_id: int) -> dict:
        """Delegate to GitLab adapter. Registered as StateWatcher poll fn."""
        return await self._gitlab.poll_gitlab_pipeline_status(project_id, pipeline_id)

    @staticmethod
    def extract_pipeline_state_key(state: dict) -> dict:
        """Delegate to GitLab adapter. Used by StateWatcher."""
        return GitLabPlatform.extract_pipeline_state_key(state)

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

    async def create_headhunter_event(self, todo: dict, plan_text: str, context: dict) -> str:
        """Delegate to GitLab adapter. Called by tests and legacy code paths."""
        return await self._gitlab.create_platform_event(todo, plan_text, context)

    async def poll_cycle(self) -> list[dict]:
        """Delegate to GitLab adapter. Exposed for backward compatibility."""
        result = await self._gitlab.poll_work_items()
        self._gitlab_pending = len(result)
        return result

    # =========================================================================
    # GitHub Brain-Facing Delegates
    # =========================================================================

    async def refresh_pr_state(self, event_id: str, *,
                               override_owner: str | None = None,
                               override_repo: str | None = None,
                               override_pr_number: int | None = None) -> dict:
        """Delegate to GitHub adapter. Called by handlers_integration.py."""
        return await self._github.refresh_pr_state(
            event_id,
            override_owner=override_owner,
            override_repo=override_repo,
            override_pr_number=override_pr_number,
        )

    async def poll_github_pr_status(self, owner: str, repo: str, pr_number: int) -> dict:
        """Delegate to GitHub adapter. Registered as StateWatcher poll fn."""
        return await self._github.poll_github_pr_status(owner, repo, pr_number)

    @staticmethod
    def extract_github_state_key(state: dict) -> dict:
        """Delegate to GitHub adapter. Used by StateWatcher."""
        return GitHubPlatform.extract_github_state_key(state)

    @staticmethod
    def parse_pr_url(url: str) -> tuple[str, str, int] | None:
        """Delegate to GitHub adapter. Called by handlers_integration.py."""
        return GitHubPlatform.parse_pr_url(url)
