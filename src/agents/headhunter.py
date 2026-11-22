# BlackBoard/src/agents/headhunter.py
# @ai-rules:
# 1. [Pattern]: Orchestrator — platform-agnostic loop + LLM analysis + circuit breaker.
# 2. [Pattern]: Delegates platform calls to self._gitlab and self._github adapters.
# 3. [Constraint]: Brain-facing methods (refresh_mr_state, poll_gitlab_mr_status, etc.)
#    remain on this class as thin delegates for backward compatibility.
# 4. [Pattern]: HeadhunterJira secondary head mounted in main loop (own error boundary).
# 5. [Pattern]: Flow gate uses global WIP cap (MAX_ACTIVE_EVENTS). Queries injected
#    Brain.count_global_wip(include_new=True) (subtracts _waiting_for_user), fallback to local.
# 6. [Pattern]: Circuit breaker per-head: 3 consecutive failures -> latch disable that head.
# 7. [Pattern]: Feedback loop uses poll-interval safety net for cross-pod catch-up.
# 8. [Gotcha]: For open MRs, mark_as_done is called in feedback (on close), NOT during poll;
#    terminal (merged/closed) MRs and unauthorized-only @mention todos have no event lifecycle so
#    best-effort dismissal during poll/fetch is allowed.
# 9. [Pattern]: process_event_feedback / _dispatch_feedback route by evidence context
#    (github_issue_context vs github_context vs gitlab_context; jira_context is quietly marked sent).
#    _process_closed_events isolates per-event exceptions so one failure cannot starve remaining events.
# 10. [Pattern]: issue_title sanitized (replace </ → < /) in _build_issue_analysis_prompt.
# 11. [Pattern]: Phase B uses gate_closed flag — no per-item Redis gate re-check after first closure.
# 12. [Pattern]: _github_pending zeroed when all new items are queued (avoids double-count in pending_count).
# 13. [Pattern]: Descriptions flow up to _DESC_SAFETY_CAP (default 100,000 chars) via
#     sanitize_untrusted_block(..., max_len=_DESC_SAFETY_CAP) so full text + trailing Bot Instructions reach
#     gemini-4-argon (1M+ context) without 8KB clipping. Output controlled by max_output_tokens.
#     _COMMENT_LIMIT (default 2000) for aggregated notes only.
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
# 18. [Pattern]: Phase D (_github_poll_review_feedback) runs after Phase C only when the flow gate
#     is open, behind HEADHUNTER_GITHUB_REVIEW_RESPONSE_ENABLED. Per-item exceptions are isolated;
#     any Phase D error is caught + logged in _github_poll_and_process (non-fatal, resets the
#     pending gauge) and never feeds the GitHub circuit breaker / _github_disabled latch.
#     Feedback is rendered into the triage prompt as a fenced <review_feedback> block (closing tag stripped, author quote-stripped).
# 19. [Security]: Untrusted blocks/scalars in _build_analysis_prompt and _emergency_plan go through
#     prompt_sanitize.{sanitize_untrusted_block,sanitize_untrusted_line} (bounded linear XML fence strip for
#     all Brain + Headhunter tags, PII redaction, control stripping, "[!call:" defang). _sanitize_xml_fence
#     (from headhunter_utils, re-exported here) remains for _render_review_feedback/_build_issue_analysis_prompt.
# 20. [Pattern]: analyze_and_plan(raise_on_error=True) (Phase D) raises on adapter unavailable, LLM error AND an
#     empty plan so the feedback is retried next cycle; raise_on_error=False keeps the emergency-plan fallback.
"""
Headhunter: VCS todo poller that analyzes assigned MRs/pipelines.

Orchestrator pattern — delegates platform-specific operations to adapters:
- GitLabPlatform: GitLab todo polling (primary head)
- GitHubPlatform: GitHub PR polling (secondary head)
- HeadhunterJira: Jira issue polling (tertiary head)

LLM analysis (gemini-4-argon triage) and event lifecycle are platform-agnostic.
"""
from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
import json
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
    MAX_FAILED_LOG_CHARS,
    V1_ACTIONABLE,
)
from .headhunter_jira import HeadhunterJira
from ..utils.prompt_sanitize import sanitize_untrusted_block, sanitize_untrusted_line

logger = logging.getLogger(__name__)

from .headhunter_utils import _COMMENT_LIMIT, _DESC_SAFETY_CAP, _safe_int  # noqa: E402

from .headhunter_utils import _XML_FENCE_TAG, _sanitize_xml_fence  # noqa: E402,F401


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
        *,
        gitlab_enabled: bool = True,
    ):
        self.blackboard = blackboard
        self._adapter = None
        self._close_signal = close_signal
        self._poll_wake_signal = asyncio.Event()
        self._feedback_task: asyncio.Task | None = None
        self._feedback_inflight: set[str] = set()
        self._poll_interval = int(os.getenv("HEADHUNTER_POLL_INTERVAL", "300"))
        self._wip_cap = int(os.getenv("MAX_ACTIVE_EVENTS", "20"))
        self._wip_counter: Callable[..., Awaitable[int]] | None = None
        self._model_name = os.getenv("LLM_MODEL_HEADHUNTER", "gemini-4-argon")
        self._temperature = float(os.getenv("LLM_TEMPERATURE_HEADHUNTER", "0.3"))
        self._thinking_level = os.getenv("LLM_THINKING_HEADHUNTER", "low")
        self._max_output_tokens = _safe_int("LLM_MAX_TOKENS_HEADHUNTER", 10000)
        self._llm_enabled = bool(os.getenv("GCP_PROJECT"))
        self._gitlab_pending: int = 0
        self._github_pending: int = 0
        self._github_issue_pending: int = 0
        self._github_queued: int = 0
        self._github_issue_queued: int = 0
        self._github_feedback_pending: int = 0

        # Platform adapters
        self._gitlab = GitLabPlatform(blackboard, enabled=gitlab_enabled)
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

    async def analyze_and_plan(
        self, context: dict, system_instruction: str = "", *, raise_on_error: bool = False,
    ) -> str:
        """LLM-based triage with full context.

        All work items pass through Flash LLM analysis for consistent evidence quality.
        Emergency inline fallback when LLM is unavailable unless ``raise_on_error=True``
        (used by Phase D so transient LLM outages defer delivery instead of burning a round).
        """
        adapter = await self._get_adapter()
        if not adapter:
            if raise_on_error:
                raise RuntimeError("LLM adapter unavailable for triage")
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
            plan_text = (response.text or "").strip()
            if not plan_text and raise_on_error:
                # Phase D: an empty plan must retry next cycle, not create an empty-plan event and burn a round.
                raise RuntimeError("LLM triage returned an empty plan")
            logger.info(f"LLM analysis for {context.get('mr_title', context.get('pr_title', '?'))}")
            return plan_text
        except Exception as e:
            if raise_on_error:
                raise
            logger.warning(f"LLM analysis failed, using emergency fallback: {e}")
            return self._emergency_plan(context)

    @staticmethod
    def _format_project(context: dict) -> str:
        """Resolve canonical project/repo string from GitLab or GitHub context."""
        return (
            context.get("project_path")
            or (
                f"{context['owner']}/{context['repo']}"
                if context.get("owner") and context.get("repo")
                else context.get("repo")
            )
            or "unknown"
        )

    @staticmethod
    def _emergency_plan(context: dict) -> str:
        """Minimal YAML plan when LLM is unavailable."""
        action = sanitize_untrusted_line(
            context.get("action_name") or context.get("action") or "unknown",
            max_len=200,
        )
        title = sanitize_untrusted_line(
            context.get("mr_title") or context.get("pr_title") or "unknown",
            max_len=200,
        )
        project = sanitize_untrusted_line(Headhunter._format_project(context), max_len=200)
        raw_iid = context.get("mr_iid", context.get("pr_number", "?"))
        iid = f"!{raw_iid}" if context.get("mr_iid") else f"#{raw_iid}"
        plan_scalar = json.dumps(f"Investigate {action} on {title}")
        summary_scalar = json.dumps(
            f"Investigate {action} on {iid} in {project}. LLM triage failed -- review manually."
        )
        return (
            f"---\nplan: {plan_scalar}\n"
            f"service: {project.rsplit('/', 1)[-1]}\n"
            f"repository: {project}\n"
            f"risk: medium\n"
            f"reasoning: LLM analysis unavailable -- manual triage needed\n"
            f"steps:\n  - id: \"1\"\n    agent: developer\n"
            f"    summary: {summary_scalar}\n---"
        )

    def _build_analysis_prompt(self, context: dict) -> str:
        """Build structured prompt with full context for LLM analysis."""
        merge_val = context.get("merge_status")
        if not merge_val:
            mergeable = context.get("mergeable")
            if mergeable is None or mergeable == "":
                merge_val = "unknown"
            elif isinstance(mergeable, bool):
                merge_val = "true" if mergeable else "false"
            else:
                merge_val = str(mergeable)
        project = sanitize_untrusted_line(self._format_project(context), max_len=200)
        title = sanitize_untrusted_line(
            context.get("mr_title") or context.get("pr_title") or "unknown",
            max_len=200,
        )
        src_branch = sanitize_untrusted_line(
            context.get("source_branch") or context.get("head_branch") or "?",
            max_len=200,
        )
        tgt_branch = sanitize_untrusted_line(
            context.get("target_branch") or context.get("base_branch") or "?",
            max_len=200,
        )
        author = sanitize_untrusted_line(context.get("author", "unknown"), max_len=120)
        parts = [
            f"Action: {sanitize_untrusted_line(context.get('action_name') or context.get('action') or 'unknown', max_len=80)}",
            f"MR: {title}",
            f"State: {context.get('mr_state') or context.get('pr_state') or 'unknown'} | "
            f"Merge status: {merge_val}",
            f"Branch: {src_branch} -> {tgt_branch}",
            f"Author: {author}",
            f"Pipeline: {context.get('pipeline_status') or context.get('check_status') or 'unknown'}",
        ]
        if context.get("pipeline_id"):
            parts.append(f"Pipeline ID: {context['pipeline_id']}")
        parts.append(f"Project: {project}")
        raw_desc = context.get("mr_description") or context.get("pr_body") or ""
        if raw_desc:
            desc = sanitize_untrusted_block(raw_desc, max_len=_DESC_SAFETY_CAP)
            parts.append(f"<description>\n{desc}\n</description>")
        if context.get("changed_files"):
            safe_files = [sanitize_untrusted_line(f, max_len=120) for f in context["changed_files"][:10]]
            parts.append(f"Changed files ({len(context['changed_files'])}): {', '.join(safe_files)}")
        if context.get("labels"):
            safe_labels = [sanitize_untrusted_line(lbl, max_len=120) for lbl in context["labels"]]
            parts.append(f"Labels: {', '.join(safe_labels)}")
        if context.get("failed_job_names"):
            safe_jobs = [sanitize_untrusted_line(j, max_len=120) for j in context["failed_job_names"]]
            parts.append(f"Failed jobs ({context.get('failed_job_count', '?')}/{context.get('total_job_count', '?')} total): {', '.join(safe_jobs)}")
        if context.get("failed_checks"):
            safe_checks = [sanitize_untrusted_line(c, max_len=120) for c in context["failed_checks"]]
            parts.append(f"Failed checks: {', '.join(safe_checks)}")
        if context.get("failed_job_log"):
            log = sanitize_untrusted_block(context["failed_job_log"], max_len=MAX_FAILED_LOG_CHARS)
            parts.append(f"<job_log>\n{log}\n</job_log>")
        notes = context.get("recent_notes") or context.get("recent_comments") or []
        if notes:
            joined = sanitize_untrusted_block("\n".join(notes), max_len=_COMMENT_LIMIT)
            parts.append(f"<comments>\n{joined}\n</comments>")
        if context.get("mention_comment"):
            mention_author = sanitize_untrusted_line(
                context.get("mention_author", "unknown"), max_len=120,
            ).replace('"', "")
            comment = sanitize_untrusted_block(context["mention_comment"])
            parts.append(f"<mention_request author=\"{mention_author}\">\n{comment}\n</mention_request>")
        if context.get("review_feedback"):
            parts.append(self._render_review_feedback(context["review_feedback"]))

        parts.append("\nProduce a YAML frontmatter work plan.")
        return "\n".join(parts)

    @staticmethod
    def _render_review_feedback(items: list[dict]) -> str:
        """Render GitHub review feedback as a single fenced block (untrusted reviewer text).

        Every free-text field is sanitized so it cannot close the fence; attribute values
        (author, path) are quote-stripped like mention_author.
        """
        def _attr(value: object) -> str:
            return (
                str(value if value is not None else "")
                .replace('"', "").replace("<", "").replace(">", "").replace("\n", " ")[:200]
            )

        lines: list[str] = []
        for it in items:
            head = (
                f'[{_attr(it.get("kind"))} id={_attr(it.get("id"))} author="{_attr(it.get("author"))}" '
                f'assoc={_attr(it.get("author_association"))} state={_attr(it.get("state"))}'
            )
            if it.get("review_id"):
                head += f' review_id={_attr(it["review_id"])}'
            if it.get("in_reply_to_id"):
                head += f' in_reply_to={_attr(it["in_reply_to_id"])}'
            if it.get("path"):
                head += f' path="{_attr(it["path"])}" line={_attr(it.get("line"))}'
            if it.get("html_url"):
                head += f' url={_attr(it["html_url"])}'
            lines.append(head + "]")
            if it.get("diff_hunk"):
                lines.append("diff_hunk:\n" + _sanitize_xml_fence(it["diff_hunk"]))
            lines.append(_sanitize_xml_fence(it.get("body", "")))
            lines.append("")
        return "<review_feedback>\n" + "\n".join(lines).rstrip() + "\n</review_feedback>"

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
        body = _sanitize_xml_fence(context.get("body", ""))
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
            + self._github_feedback_pending
        )

    def set_wip_counter(self, counter: Callable[..., Awaitable[int]] | None) -> None:
        """Inject global WIP counter (e.g. Brain.count_global_wip)."""
        self._wip_counter = counter
        if getattr(self, "_jira", None) is not None:
            self._jira.set_wip_counter(counter)

    async def _local_count_wip(self) -> int:
        status_map = await self.blackboard.get_active_events_with_status()
        return sum(1 for s in status_map.values() if s in ("new", "active", "deferred"))

    async def check_flow_gate(self) -> bool:
        """Back off when system is at global WIP capacity."""
        if self._wip_counter is not None:
            try:
                wip_used = await self._wip_counter(include_new=True)
            except Exception as e:
                logger.warning(
                    "Injected WIP counter failed in check_flow_gate, falling back to local: %s",
                    e,
                )
                try:
                    wip_used = await self._local_count_wip()
                except Exception as local_err:
                    logger.error(
                        "Local WIP count failed in check_flow_gate, assuming gate closed: %s",
                        local_err,
                    )
                    return False
        else:
            try:
                wip_used = await self._local_count_wip()
            except Exception as local_err:
                logger.error(
                    "Local WIP count failed in check_flow_gate, assuming gate closed: %s",
                    local_err,
                )
                return False
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
            self._feedback_task = asyncio.create_task(self._feedback_loop())
            logger.info("Headhunter feedback loop started (Signal + Poll hybrid)")

        gitlab_failures = 0
        github_failures = 0
        max_failures = 3
        _gitlab_disabled = False
        _github_disabled = False

        try:
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

                # Sleep or wait for relayed poll-wake signal
                if self._close_signal:
                    try:
                        await asyncio.wait_for(self._poll_wake_signal.wait(), timeout=self._poll_interval)
                        self._poll_wake_signal.clear()
                        logger.debug("Headhunter poll woke early: event closed, slot may be open")
                    except asyncio.TimeoutError:
                        pass
                else:
                    await asyncio.sleep(self._poll_interval)
        finally:
            if self._feedback_task is not None:
                if not self._feedback_task.done():
                    self._feedback_task.cancel()
                await asyncio.gather(self._feedback_task, return_exceptions=True)
                self._feedback_task = None

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
            if context is None:
                continue
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
            self._github_feedback_pending = 0  # Phase D is skipped while the gate is closed
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

        # Phase D: PR review feedback / @mentions (flag-gated, flow-gate gated). Non-fatal like
        # Phase C: an optional feature must never abort _poll_github or feed the circuit breaker
        # that latches _github_disabled.
        try:
            await self._github_poll_review_feedback()
        except Exception as e:
            self._github_feedback_pending = 0  # never leave the gauge stale after a failed poll
            logger.warning(f"GitHub review-feedback poll failed (non-fatal): {e}")

    async def _github_poll_review_feedback(self) -> None:
        """Phase D: turn trusted review feedback on Darwin PRs (and @mentions) into events.

        Items that are not turned into an event this cycle (flow gate closed, LLM/side-effect
        failure) are NOT marked handled, so they are retried next cycle. The caller treats any
        error from this phase as non-fatal (logged only); per-item failures are isolated.
        """
        if not self._github.review_response_enabled():
            self._github_feedback_pending = 0
            return
        items = await self._github.poll_review_feedback_all_installations()
        self._github_feedback_pending = len(items)
        if not items:
            return
        logger.info(f"Headhunter GitHub review feedback: {len(items)} PR(s) with new feedback")
        si = self._github.load_review_response_instruction()
        for item in items:
            if not await self.check_flow_gate():
                logger.info("Headhunter flow gate closed -- deferring review-feedback events to next cycle")
                break
            try:
                context = await self._github.fetch_context(item)
                plan_text = await self.analyze_and_plan(context, si, raise_on_error=True)
                await self._github.create_review_feedback_event(item, plan_text, context)
                self._github_feedback_pending = max(0, self._github_feedback_pending - 1)
            except Exception as e:
                logger.warning(
                    f"GitHub review-feedback processing failed for "
                    f"{item.get('owner')}/{item.get('repo')}#{item.get('number')}: {e}"
                )

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
        """Process platform feedback for closed headhunter events and relay wake signal to poll loop."""
        while True:
            try:
                await asyncio.wait_for(self._close_signal.wait(), timeout=self._poll_interval)
            except asyncio.TimeoutError:
                pass
            if self._close_signal.is_set():
                self._close_signal.clear()
                self._poll_wake_signal.set()
            try:
                await self._process_closed_events()
            except Exception as e:
                logger.warning(f"Headhunter feedback loop error (will retry): {e}")
            if self._close_signal is not None and self._close_signal.is_set():
                self._close_signal.clear()
                self._poll_wake_signal.set()

    async def _dispatch_feedback(self, event) -> None:
        """Serialize and route feedback for a single closed headhunter event by VCS context."""
        if event.id in self._feedback_inflight:
            return
        self._feedback_inflight.add(event.id)
        try:
            if await self.blackboard.is_feedback_sent(event.id):
                return
            evidence = event.event.evidence if event.event else None
            if evidence and getattr(evidence, "github_issue_context", None):
                await self._github.post_issue_feedback(event)
            elif evidence and getattr(evidence, "github_context", None):
                await self._github.post_feedback(event)
            elif evidence and getattr(evidence, "gitlab_context", None):
                await self._gitlab.post_feedback(event)
            elif evidence and getattr(evidence, "jira_context", None):
                logger.debug(f"Headhunter feedback not applicable for Jira mission {event.id}; marking sent")
                await self.blackboard.mark_feedback_sent(event.id)
            else:
                logger.warning(f"Headhunter feedback skipped for {event.id}: unknown/missing VCS context")
        finally:
            self._feedback_inflight.discard(event.id)

    async def process_event_feedback(self, event_id: str) -> None:
        """Process feedback for a single closed headhunter event (called by Brain)."""
        if event_id in self._feedback_inflight:
            return
        if await self.blackboard.is_feedback_sent(event_id):
            return
        event = await self.blackboard.get_event(event_id)
        if not event:
            return
        await self._dispatch_feedback(event)

    async def _process_closed_events(self) -> None:
        """Scan closed headhunter events and post platform feedback."""
        closed_events = await self.blackboard.get_recent_closed_by_source("headhunter", minutes=1440)
        if not closed_events:
            return
        for event in closed_events:
            try:
                await self._dispatch_feedback(event)
            except Exception as exc:
                logger.warning(
                    f"Headhunter feedback dispatch failed for {getattr(event, 'id', '?')}: {exc}"
                )

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
