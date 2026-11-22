# BlackBoard/src/agents/headhunter.py
# @ai-rules:
# 1. [Pattern]: Orchestrator — platform-agnostic loop + LLM analysis + circuit breaker.
# 2. [Pattern]: Delegates platform calls to self._gitlab and self._github adapters.
# 3. [Constraint]: Brain-facing methods (refresh_mr_state, poll_gitlab_mr_status, etc.)
#    remain on this class as thin delegates for backward compatibility.
# 4. [Pattern]: HeadhunterJira secondary head mounted in main loop (own error boundary).
# 5. [Pattern]: Flow gate uses global WIP cap (MAX_ACTIVE_EVENTS). Queries injected
#    Brain.count_global_wip(include_new=True) (subtracts _waiting_for_user), fallback to local.
# 6. [Pattern]: Per-head self-recovering half-open circuit breaker (HeadhunterCircuitBreaker):
#    3 consecutive non-401/403 failures -> open with exponential cooldown (300s/900s/1800s) ->
#    half_open probe -> closed on success. HTTP 401/403 auth/permission errors are exempt on both
#    GitLab and GitHub.
# 7. [Pattern]: Feedback loop uses poll-interval safety net for cross-pod catch-up.
# 8. [Gotcha]: For open MRs, mark_as_done is called in feedback (on close), NOT during poll;
#    terminal (merged/closed) MRs and unauthorized-only @mention todos have no event lifecycle so
#    best-effort dismissal during poll/fetch is allowed.
# 9. [Pattern]: process_event_feedback / _dispatch_feedback route by evidence context
#    (github_issue_context vs github_context vs gitlab_context; jira_context is quietly marked sent).
#    _process_closed_events isolates per-event exceptions so one failure cannot starve remaining events.
# 10. [Pattern]: issue_title and issue metadata sanitized via prompt_sanitize.sanitize_untrusted_line in
#     _build_issue_analysis_prompt; issue body via sanitize_untrusted_block.
# 11. [Pattern]: Phase B uses gate_closed flag — no per-item Redis gate re-check after first closure.
# 12. [Pattern]: _github_pending decremented by newly queued count (avoids double-count in pending_count).
# 13. [Pattern]: Descriptions flow up to _DESC_SAFETY_CAP (default 100,000 chars) via
#     sanitize_untrusted_block(..., max_len=_DESC_SAFETY_CAP) so full text + trailing Bot Instructions reach
#     gemini-4-argon (1M+ context) without 8KB clipping. Output controlled by max_output_tokens.
#     _COMMENT_LIMIT (default 2000) for aggregated notes only.
# 14. [Pattern]: analyze_and_plan returns validated YAML plan_text only (str). Domain classification removed —
#     events land in disorder, FRIDAY classifies during triage.
# 15. [Pattern]: Per-item try/except in unified _drain_platform_phase_ab (GitLab + GitHub PRs) and Phase C
#     Issues isolates one bad item (e.g. None title) from starving the rest of the batch
#     or bubbling out and tripping the platform circuit breaker.
# 16. [Pattern]: Issue queue mirrors PR queue (Phase A promote FIFO, Phase B queue-on-close)
#     but is purely additive — _queue_issue adds darwin-queued without removing darwin-work,
#     since _poll_issues filters server-side on labels=darwin-work.
# 17. [Pattern]: _raise_if_systemic_failure() escalates a fully-failed 2+ item drain-loop
#     batch (Phase A/B, GitLab/GitHub PR and Issue) instead of the cycle "succeeding" silently and
#     resetting the platform breaker. When every failure in the batch is HTTP 401/403 auth-exempt,
#     the original HTTPStatusError is chained via __cause__ so HeadhunterCircuitBreaker stays closed.
#     PR-side Phase A/B escalation propagates to Headhunter.run()'s circuit breaker. Issue-side
#     escalation is caught and logged as WARNING in _github_poll_and_process (see issue #230).
#     A single failing item (poison-pill) never triggers systemic escalation.
# 18. [Pattern]: Phase D (_github_poll_review_feedback) runs after Phase C only when the flow gate
#     is open, behind HEADHUNTER_GITHUB_REVIEW_RESPONSE_ENABLED. Per-item exceptions are isolated;
#     any Phase D error is caught + logged in _github_poll_and_process (non-fatal, resets the
#     pending gauge) and never feeds the GitHub circuit breaker.
#     Feedback is rendered into the triage prompt as a fenced <review_feedback> block via prompt_sanitize.
# 19. [Security]: Untrusted blocks/scalars across _build_analysis_prompt, _build_issue_analysis_prompt,
#     _render_review_feedback, and _emergency_plan go through prompt_sanitize.{sanitize_untrusted_block,
#     sanitize_untrusted_line} (bounded linear XML fence strip for all Brain + Headhunter tags, PII
#     redaction, control stripping, "[!call:" defang). Attribute metacharacters (", <, >, ]) are
#     stripped BEFORE sanitize_untrusted_line so post-strip cannot reassemble "[!call:".
# 20. [Pattern]: analyze_and_plan validates LLM YAML via _NoAliasSafeLoader (yaml.SafeLoader subclass
#     rejecting anchors/aliases, 64KB pre-cap, recognized plan keys). raise_on_error=True (Phase D)
#     raises on adapter unavailable, LLM error, empty/invalid YAML so feedback retries next cycle;
#     raise_on_error=False keeps the _emergency_plan fallback (developer for PR/MR, architect for issues).
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
import dataclasses
import json
import logging
import os
import re
from typing import TYPE_CHECKING, Any

import yaml

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
from .headhunter_models import (
    HeadhunterCircuitBreaker,
    VcsContext,
    VcsWorkItem,
    _redact_error_text,
)
from .headhunter_port import VcsPlatformPort
from ..utils.pii_redaction import redact_pii
from ..utils.prompt_sanitize import sanitize_untrusted_block, sanitize_untrusted_line

logger = logging.getLogger(__name__)

from .headhunter_utils import _COMMENT_LIMIT, _DESC_SAFETY_CAP, _safe_int  # noqa: E402


_SYSTEMIC_FAILURE_MIN_BATCH = 2
_PLAN_MAX_CHARS = 65_536
_OPEN_FENCE_RE = re.compile(r"^```[A-Za-z0-9_-]*\s*$")
_RECOGNIZED_PLAN_KEYS = frozenset({"plan", "steps", "action", "summary", "verdict", "reply"})


class _NoAliasSafeLoader(yaml.SafeLoader):
    """yaml.SafeLoader subclass that rejects YAML anchors and aliases (anti-Billion-Laughs)."""

    def compose_alias(self, anchor: Any) -> Any:  # type: ignore[override]
        raise yaml.YAMLError("YAML anchors/aliases are forbidden in LLM plans")

    def compose_node(self, parent: Any, index: Any) -> Any:  # type: ignore[override]
        if self.check_event(yaml.AliasEvent):
            raise yaml.YAMLError("YAML anchors/aliases are forbidden in LLM plans")
        event = self.peek_event()
        if getattr(event, "anchor", None) is not None:
            raise yaml.YAMLError("YAML anchors/aliases are forbidden in LLM plans")
        return super().compose_node(parent, index)


def _raise_if_systemic_failure(
    phase: str,
    attempted: int,
    failed: int,
    *,
    platform: str = "GitHub",
    errors: list[BaseException] | None = None,
) -> None:
    """Escalate a fully-failed multi-item batch instead of silently swallowing it.

    Per-item try/except exists so one poison-pill item (attempted=1, failed=1)
    can't block the rest of a batch or trip the circuit breaker -- that must stay
    silent (WARNING only). But when 2+ items were attempted and every single one
    failed, N independent bad items is a far less likely explanation than a
    systemic cause (installation token expiry, downstream Blackboard outage) that
    will keep failing every item on every future cycle too. Raising here lets the
    caller's circuit breaker in Headhunter.run see it instead of the cycle silently
    "succeeding" and resetting the failure count.

    When every failure in the batch is HTTP 401/403 auth-exempt, chains the first
    auth exception via __cause__ so HeadhunterCircuitBreaker.is_auth_exempt() keeps
    the breaker closed.
    """
    if attempted >= _SYSTEMIC_FAILURE_MIN_BATCH and failed == attempted:
        if (
            errors
            and len(errors) == failed
            and all(HeadhunterCircuitBreaker.is_auth_exempt(err) for err in errors)
        ):
            raise RuntimeError(
                f"{platform} {phase}: all {attempted} item(s) failed with auth/permission errors"
            ) from errors[0]
        raise RuntimeError(
            f"{platform} {phase}: all {attempted} item(s) failed -- treating as systemic failure"
        )


def _validate_plan_yaml(plan_text: str) -> str:
    """Validate LLM triage plan text using _NoAliasSafeLoader (yaml.SafeLoader) ONLY.

    Enforces a 64KB pre-parse cap, forbids YAML anchors/aliases, extracts a single
    optional markdown code fence (rejecting nested/multiple fences; discarding any
    benign trailing notes after a closed fence), requires column-0 YAML frontmatter
    '---' delimiters (rejecting trailing non-whitespace content after closing '---'),
    and validates a recognized non-empty plan mapping.

    Returns the validated canonical YAML text (never unvalidated trailing prose).
    """
    candidate = (plan_text or "").strip()
    if not candidate:
        raise RuntimeError("LLM triage returned an empty plan")
    if len(candidate) > _PLAN_MAX_CHARS:
        raise ValueError(f"LLM triage plan exceeds {_PLAN_MAX_CHARS} char limit")

    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if not _OPEN_FENCE_RE.match(lines[0]):
            raise ValueError("Invalid opening markdown code fence in LLM plan")
        close_idx: int | None = None
        for idx in range(1, len(lines)):
            stripped = lines[idx].strip()
            if stripped.startswith("```"):
                if stripped != "```":
                    raise ValueError("Nested/malformed markdown code fence in LLM plan")
                close_idx = idx
                break
        if close_idx is None:
            raise ValueError("Unclosed markdown code fence in LLM plan")
        for trailing_line in lines[close_idx + 1 :]:
            if trailing_line.strip().startswith("```"):
                raise ValueError("Multiple markdown code fences in LLM plan")
        candidate = "\n".join(lines[1:close_idx]).strip()

    has_frontmatter = False
    lines = candidate.splitlines()
    if lines and lines[0].rstrip() == "---":
        has_frontmatter = True
        body_lines = lines[1:]
        close_fm_idx: int | None = None
        for idx, line in enumerate(body_lines):
            if line.rstrip() == "---":
                close_fm_idx = idx
                break
        if close_fm_idx is not None:
            trailing_fm = body_lines[close_fm_idx + 1 :]
            if any(ln.strip() for ln in trailing_fm):
                raise ValueError("Unexpected trailing content after closing YAML frontmatter '---'")
            body_lines = body_lines[:close_fm_idx]
        yaml_body = "\n".join(body_lines).strip()
    else:
        yaml_body = candidate

    if not yaml_body:
        raise ValueError("LLM triage plan YAML body is empty")

    parsed = yaml.load(yaml_body, Loader=_NoAliasSafeLoader)
    if not isinstance(parsed, dict) or not parsed or not all(isinstance(k, str) for k in parsed):
        raise ValueError(
            f"LLM triage plan must parse to a non-empty string-keyed YAML mapping, got {type(parsed).__name__}"
        )

    if "plan" in parsed:
        if not isinstance(parsed["plan"], str) or not parsed["plan"].strip():
            raise ValueError("LLM triage plan 'plan' field must be a non-empty string")
    else:
        has_recognized = any(
            k in parsed and parsed[k] not in (None, "", [], {})
            for k in _RECOGNIZED_PLAN_KEYS
        )
        if not has_recognized:
            raise ValueError(
                "LLM triage YAML mapping lacks recognized plan keys "
                f"({', '.join(sorted(_RECOGNIZED_PLAN_KEYS))})"
            )

    return f"---\n{yaml_body}\n---" if has_frontmatter else yaml_body


def on_headhunter_done(task: asyncio.Task) -> None:
    """Done-callback watchdog for the Headhunter background asyncio task."""
    if task.cancelled():
        return
    exc = task.exception()
    if exc is not None:
        safe_msg = _redact_error_text(redact_pii(str(exc)), max_len=400)
        logger.error(
            "Headhunter background task exited unexpectedly (%s): %s",
            type(exc).__name__,
            safe_msg,
        )
    else:
        logger.warning("Headhunter background task exited cleanly without cancellation")


def start_headhunter_task(
    blackboard: "BlackboardState",
    brain: Any,
    close_signal: asyncio.Event | None,
    *,
    gitlab_enabled: bool,
) -> tuple["Headhunter", asyncio.Task]:
    """Create, wire, and launch the Headhunter background task with done watchdog."""
    if close_signal is None:
        raise RuntimeError("headhunter_close_signal not initialized — startup ordering bug")
    headhunter = Headhunter(
        blackboard,
        close_signal=close_signal,
        gitlab_enabled=gitlab_enabled,
    )
    headhunter.set_wip_counter(brain.count_global_wip)
    brain.agents["_headhunter"] = headhunter
    task = asyncio.create_task(headhunter.run())
    task.add_done_callback(on_headhunter_done)
    return headhunter, task


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
        self._gitlab_queued: int = 0
        self._github_pending: int = 0
        self._github_issue_pending: int = 0
        self._github_queued: int = 0
        self._github_issue_queued: int = 0
        self._github_feedback_pending: int = 0

        # Platform adapters
        self._gitlab = GitLabPlatform(blackboard, enabled=gitlab_enabled)
        self._github = GitHubPlatform(blackboard)
        self._jira = HeadhunterJira(blackboard)

        # Self-recovering per-platform half-open circuit breakers
        self._breakers: dict[str, HeadhunterCircuitBreaker] = {
            "gitlab": HeadhunterCircuitBreaker("gitlab"),
            "github": HeadhunterCircuitBreaker("github"),
        }

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

    @staticmethod
    def _is_issue_context(context: VcsContext | dict[str, Any]) -> bool:
        if isinstance(context, VcsContext):
            return context.item_kind == "issue"
        return "issue_number" in context

    @staticmethod
    def _context_title(context: VcsContext | dict[str, Any], default: str = "?") -> str:
        if isinstance(context, VcsContext):
            return context.title or default
        return (
            context.get("mr_title")
            or context.get("pr_title")
            or context.get("issue_title")
            or context.get("title")
            or default
        )

    async def analyze_and_plan(
        self,
        context: VcsContext | dict[str, Any],
        system_instruction: str = "",
        *,
        raise_on_error: bool = False,
    ) -> str:
        """LLM-based triage with full context (accepts VcsContext or legacy dict).

        All work items pass through Flash LLM analysis for consistent evidence quality.
        Emergency inline fallback when LLM is unavailable unless ``raise_on_error=True``
        (used by Phase D so transient LLM outages defer delivery instead of burning a round).
        """
        title_for_log = self._context_title(context)
        adapter = await self._get_adapter()
        if not adapter:
            if raise_on_error:
                raise RuntimeError("LLM adapter unavailable for triage")
            logger.warning(f"Emergency fallback plan for {title_for_log}")
            return self._emergency_plan(context)

        prompt = (
            self._build_issue_analysis_prompt(context)
            if self._is_issue_context(context)
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
            validated_plan = _validate_plan_yaml(plan_text)
            logger.info(f"LLM analysis for {title_for_log}")
            return validated_plan
        except Exception as e:
            if raise_on_error:
                raise
            logger.warning(f"LLM analysis failed, using emergency fallback: {e}")
            return self._emergency_plan(context)

    @staticmethod
    def _format_project(context: VcsContext | dict[str, Any]) -> str:
        """Resolve canonical project/repo string from VcsContext or GitLab/GitHub dict."""
        if isinstance(context, VcsContext):
            return context.project_ref or "unknown"
        return (
            context.get("project_path")
            or (
                f"{context.get('owner')}/{context.get('repo')}"
                if context.get("owner") and context.get("repo")
                else context.get("repo")
            )
            or "unknown"
        )

    @staticmethod
    def _emergency_plan(context: VcsContext | dict[str, Any]) -> str:
        """Minimal YAML plan when LLM is unavailable."""
        is_issue = Headhunter._is_issue_context(context)
        raw_title = Headhunter._context_title(context, "unknown")
        src = context.raw if isinstance(context, VcsContext) else context
        raw_action = src.get("action_name") or src.get("action") or ("issue_triage" if is_issue else "unknown")
        if isinstance(context, VcsContext):
            iid = f"!{context.item_id}" if context.item_kind == "mr" else f"#{context.item_id}"
        else:
            raw_iid = context.get("mr_iid", context.get("pr_number", context.get("issue_number", "?")))
            iid = f"!{raw_iid}" if context.get("mr_iid") else f"#{raw_iid}"

        action = sanitize_untrusted_line(raw_action, max_len=200)
        title = sanitize_untrusted_line(raw_title, max_len=200)
        project = sanitize_untrusted_line(Headhunter._format_project(context), max_len=200)
        agent = "architect" if is_issue else "developer"
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
            f"steps:\n  - id: \"1\"\n    agent: {agent}\n"
            f"    summary: {summary_scalar}\n---"
        )

    @staticmethod
    def _line_list(vals: Any, max_len: int = 120) -> str:
        return ", ".join(sanitize_untrusted_line(v, max_len=max_len) for v in vals)

    def _build_analysis_prompt(self, context: VcsContext | dict[str, Any]) -> str:
        """Build structured prompt with full context for LLM analysis (VcsContext or dict)."""
        extras: dict[str, Any] = context.raw if isinstance(context, VcsContext) else context

        merge_val = extras.get("merge_status") or extras.get("mergeable_state")
        if not merge_val:
            mergeable = extras.get("mergeable")
            if mergeable is None or mergeable == "":
                merge_val = "unknown"
            elif isinstance(mergeable, bool):
                merge_val = "true" if mergeable else "false"
            else:
                merge_val = str(mergeable)

        project = sanitize_untrusted_line(self._format_project(context), max_len=200)
        raw_title = self._context_title(context, "unknown")
        raw_action = extras.get("action_name") or extras.get("action") or "unknown"
        if isinstance(context, VcsContext):
            raw_state = context.state or "unknown"
            raw_src = context.source_branch or "?"
            raw_tgt = context.target_branch or "?"
            raw_author = context.author or "unknown"
            raw_ci = context.ci_status or "unknown"
            raw_desc = context.description or ""
        else:
            raw_state = context.get("mr_state") or context.get("pr_state") or context.get("state") or "unknown"
            raw_src = context.get("source_branch") or context.get("head_branch") or "?"
            raw_tgt = context.get("target_branch") or context.get("base_branch") or "?"
            raw_author = context.get("author") or "unknown"
            raw_ci = context.get("pipeline_status") or context.get("check_status") or context.get("ci_status") or "unknown"
            raw_desc = context.get("mr_description") or context.get("pr_body") or context.get("description") or ""

        parts = [
            f"Action: {sanitize_untrusted_line(raw_action, max_len=80)}",
            f"MR: {sanitize_untrusted_line(raw_title, max_len=200)}",
            f"State: {sanitize_untrusted_line(raw_state, max_len=60)} | "
            f"Merge status: {sanitize_untrusted_line(merge_val, max_len=60)}"
            + (" | Draft: true" if extras.get("draft") else ""),
            f"Branch: {sanitize_untrusted_line(raw_src, max_len=200)} -> {sanitize_untrusted_line(raw_tgt, max_len=200)}",
            f"Author: {sanitize_untrusted_line(raw_author, max_len=120)}",
            f"Pipeline: {sanitize_untrusted_line(raw_ci, max_len=60)}",
        ]
        pipeline_id = extras.get("pipeline_id")
        if pipeline_id:
            parts.append(f"Pipeline ID: {pipeline_id}")
        parts.append(f"Project: {project}")
        if raw_desc:
            desc = sanitize_untrusted_block(raw_desc, max_len=_DESC_SAFETY_CAP)
            parts.append(f"<description>\n{desc}\n</description>")
        changed_files = extras.get("changed_files")
        if changed_files:
            parts.append(f"Changed files ({len(changed_files)}): {self._line_list(changed_files[:10])}")
        labels = extras.get("labels")
        if labels:
            parts.append(f"Labels: {self._line_list(labels)}")
        failed_job_names = extras.get("failed_job_names")
        if failed_job_names:
            parts.append(
                f"Failed jobs ({extras.get('failed_job_count', '?')}/{extras.get('total_job_count', '?')} total): "
                f"{self._line_list(failed_job_names)}"
            )
        failed_checks = extras.get("failed_checks")
        if failed_checks:
            parts.append(f"Failed checks: {self._line_list(failed_checks)}")
        failed_job_log = extras.get("failed_job_log")
        if failed_job_log:
            log = sanitize_untrusted_block(failed_job_log, max_len=MAX_FAILED_LOG_CHARS)
            parts.append(f"<job_log>\n{log}\n</job_log>")
        notes = extras.get("recent_notes") or extras.get("recent_comments") or []
        if notes:
            joined = sanitize_untrusted_block("\n".join(notes), max_len=_COMMENT_LIMIT)
            parts.append(f"<comments>\n{joined}\n</comments>")
        mention_comment = extras.get("mention_comment")
        if mention_comment:
            mention_author = self._attr(extras.get("mention_author") or "unknown", max_len=120)
            comment = sanitize_untrusted_block(mention_comment)
            parts.append(f"<mention_request author=\"{mention_author}\">\n{comment}\n</mention_request>")
        review_feedback = extras.get("review_feedback")
        if review_feedback:
            parts.append(self._render_review_feedback(review_feedback))
        pr_review_comments = extras.get("pr_review_comments")
        if isinstance(pr_review_comments, list) and pr_review_comments:
            rc_lines: list[str] = []
            for entry in pr_review_comments[:20]:
                if not isinstance(entry, dict):
                    continue
                kind = self._attr(entry.get("kind") or "review", max_len=32)
                e_author = self._attr(entry.get("author") or "?", max_len=80)
                meta_bits = [f"{kind} by {e_author}"]
                if entry.get("state"):
                    meta_bits.append(f"state={self._attr(entry['state'], max_len=40)}")
                if entry.get("path"):
                    meta_bits.append(f"path={self._attr(entry['path'], max_len=160)}")
                rc_lines.append("[" + " ".join(meta_bits) + "]")
                if entry.get("diff_hunk"):
                    rc_lines.append(sanitize_untrusted_block(entry["diff_hunk"], max_len=600))
                if entry.get("body"):
                    rc_lines.append(sanitize_untrusted_block(entry["body"], max_len=1000))
            if rc_lines:
                rc_joined = sanitize_untrusted_block("\n".join(rc_lines), max_len=_COMMENT_LIMIT)
                parts.append(f"<pr_review_comments>\n{rc_joined}\n</pr_review_comments>")

        parts.append("\nProduce a YAML frontmatter work plan.")
        return "\n".join(parts)

    @staticmethod
    def _attr(value: object, max_len: int = 200) -> str:
        raw = "" if value is None else str(value)
        for ch in ('"', "<", ">", "]"):
            raw = raw.replace(ch, "")
        return sanitize_untrusted_line(raw, max_len=max_len)

    @staticmethod
    def _render_review_feedback(items: list[dict]) -> str:
        """Render GitHub review feedback as a single fenced block."""
        attr = Headhunter._attr
        lines: list[str] = []
        for it in items:
            head = (
                f'[{attr(it.get("kind"))} id={attr(it.get("id"))} author="{attr(it.get("author"))}" '
                f'assoc={attr(it.get("author_association"))} state={attr(it.get("state"))}'
            )
            if it.get("review_id"):
                head += f' review_id={attr(it["review_id"])}'
            if it.get("in_reply_to_id"):
                head += f' in_reply_to={attr(it["in_reply_to_id"])}'
            if it.get("path"):
                head += f' path="{attr(it["path"])}" line={attr(it.get("line"))}'
            if it.get("html_url"):
                head += f' url={attr(it["html_url"])}'
            lines.append(head + "]")
            if it.get("diff_hunk"):
                lines.append(
                    "diff_hunk:\n" + sanitize_untrusted_block(it["diff_hunk"], max_len=_DESC_SAFETY_CAP)
                )
            lines.append(sanitize_untrusted_block(it.get("body", ""), max_len=_DESC_SAFETY_CAP))
            lines.append("")
        return "<review_feedback>\n" + "\n".join(lines).rstrip() + "\n</review_feedback>"

    @staticmethod
    def _build_issue_analysis_prompt(context: VcsContext | dict[str, Any]) -> str:
        """Build issue-specific prompt. Excludes PR-only fields (branch, pipeline, merge, head_sha)."""
        extras: dict[str, Any] = context.raw if isinstance(context, VcsContext) else context
        if isinstance(context, VcsContext):
            issue_num: Any = context.item_id
            title = sanitize_untrusted_line(context.title or "unknown", max_len=200) or "unknown"
            repo_line = sanitize_untrusted_line(context.project_ref or "?/?", max_len=200) or "?/?"
            state = sanitize_untrusted_line(context.state or "open", max_len=40) or "open"
            author = sanitize_untrusted_line(context.author or "unknown", max_len=120) or "unknown"
            raw_body = context.description or ""
        else:
            issue_num = context.get("issue_number", "?")
            title = sanitize_untrusted_line(context.get("issue_title") or "unknown", max_len=200) or "unknown"
            owner = sanitize_untrusted_line(context.get("owner") or "?", max_len=120) or "?"
            repo = sanitize_untrusted_line(context.get("repo") or "?", max_len=120) or "?"
            repo_line = f"{owner}/{repo}"
            state = sanitize_untrusted_line(context.get("state") or "open", max_len=40) or "open"
            author = sanitize_untrusted_line(context.get("author") or "unknown", max_len=120) or "unknown"
            raw_body = context.get("body", "")

        parts = [
            f"GitHub Issue #{issue_num}: {title}",
            f"Repo: {repo_line}",
            f"State: {state} | Author: {author}",
        ]
        labels = extras.get("labels")
        if labels:
            parts.append(f"Labels: {Headhunter._line_list(labels)}")
        assignees = extras.get("assignees")
        if assignees:
            parts.append(f"Assignees: {Headhunter._line_list(assignees)}")
        body = sanitize_untrusted_block(raw_body, max_len=_DESC_SAFETY_CAP)
        if body:
            parts.append(f"<issue_body>\n{body}\n</issue_body>")
        skill_label = extras.get("skill_label")
        if skill_label:
            safe_skill = sanitize_untrusted_line(skill_label, max_len=120)
            parts.append(f"Skill context: {safe_skill} routing")
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
            + self._gitlab_queued
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
                return await self._wip_counter(include_new=True) < self._wip_cap
            except Exception as e:
                logger.warning("Injected WIP counter failed in check_flow_gate, falling back to local: %s", e)
        try:
            return await self._local_count_wip() < self._wip_cap
        except Exception as local_err:
            logger.error("Local WIP count failed in check_flow_gate, assuming gate closed: %s", local_err)
            return False

    # =========================================================================
    # Main Loop (Circuit Breaker)
    # =========================================================================

    @staticmethod
    def _extract_auth_status(exc: BaseException) -> Any:
        cur: BaseException | None = exc
        seen: set[int] = set()
        while cur is not None and id(cur) not in seen and len(seen) < 8:
            seen.add(id(cur))
            status = getattr(getattr(cur, "response", None), "status_code", None)
            if status in (401, 403):
                return status
            cur = cur.__cause__ if cur.__cause__ is not None else cur.__context__
        return "?"

    async def _run_gitlab_wakeup(self) -> None:
        if hasattr(self._gitlab, "poll_active_events_wakeup"):
            try:
                await self._gitlab.poll_active_events_wakeup()
            except Exception as e:
                logger.warning(f"GitLab active-event wake-up sweep failed (non-fatal): {e}")

    async def _run_platform_head(
        self,
        key: str,
        label: str,
        enabled: bool,
        poll_fn: Callable[[], Awaitable[None]],
        *,
        on_breaker_open: Callable[[], Awaitable[None]] | None = None,
    ) -> None:
        """Execute one platform poll cycle under its half-open circuit breaker."""
        cb = self._breakers[key]
        if not enabled:
            return
        if not cb.should_attempt():
            if on_breaker_open is not None:
                await on_breaker_open()
            return
        try:
            await poll_fn()
            cb.record_success()
        except Exception as e:
            if cb.is_auth_exempt(e):
                status_code = self._extract_auth_status(e)
                logger.error(
                    f"Headhunter {label} auth error ({status_code}) — "
                    "not counting toward circuit breaker"
                )
            else:
                safe_err = _redact_error_text(redact_pii(str(e)), max_len=400)
                opened = cb.record_failure(safe_err)
                logger.error(
                    f"Headhunter {label} poll failed "
                    f"({cb.consecutive_failures}/{cb.max_failures}): {safe_err}"
                )
                if opened:
                    logger.critical(
                        f"Headhunter {label} circuit breaker OPEN "
                        f"(next_retry_at={cb.next_retry_at})"
                    )

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

        try:
            await asyncio.sleep(startup_delay)
            logger.info("Headhunter started")

            if self._close_signal:
                self._feedback_task = asyncio.create_task(self._feedback_loop())
                logger.info("Headhunter feedback loop started (Signal + Poll hybrid)")

            while True:
                # GitLab head (half-open circuit breaker; 401/403 exempt)
                await self._run_platform_head(
                    "gitlab", "GitLab", self._gitlab.enabled(), self._poll_and_process,
                    on_breaker_open=self._run_gitlab_wakeup,
                )

                # GitHub head (half-open circuit breaker; 401/403 exempt)
                await self._run_platform_head(
                    "github", "GitHub", self._github.enabled(), self._github_poll_and_process,
                )

                # Jira head (independent error boundary)
                if self._jira.enabled():
                    try:
                        await self._jira.poll_and_process()
                    except Exception as e:
                        logger.warning(f"Headhunter Jira poll failed (non-fatal): {e}")

                # Unconditionally await _poll_wake_signal alongside poll_interval (even when _close_signal is None)
                wake_task = asyncio.create_task(self._poll_wake_signal.wait())
                sleep_task = asyncio.create_task(asyncio.sleep(self._poll_interval))
                try:
                    done, pending = await asyncio.wait(
                        {wake_task, sleep_task}, return_when=asyncio.FIRST_COMPLETED,
                    )
                    for pending_task in pending:
                        pending_task.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    if sleep_task in done:
                        if sleep_task.cancelled() and wake_task not in done:
                            raise asyncio.CancelledError()
                        if not sleep_task.cancelled():
                            sleep_exc = sleep_task.exception()
                            if sleep_exc is not None:
                                raise sleep_exc
                    if wake_task in done and not wake_task.cancelled():
                        self._poll_wake_signal.clear()
                        logger.debug("Headhunter poll woke early: poll wake signal set")
                except asyncio.CancelledError:
                    wake_task.cancel()
                    sleep_task.cancel()
                    await asyncio.gather(wake_task, sleep_task, return_exceptions=True)
                    raise
        finally:
            if self._feedback_task is not None:
                if not self._feedback_task.done():
                    self._feedback_task.cancel()
                await asyncio.gather(self._feedback_task, return_exceptions=True)
                self._feedback_task = None
            # Close only GitLabPlatform's owned HTTP client (main.py owns GitHub's shared singleton)
            if hasattr(self._gitlab, "close"):
                try:
                    await self._gitlab.close()
                except Exception as close_err:
                    logger.warning(f"Failed to close GitLabPlatform HTTP client: {close_err}")

    @staticmethod
    def _item_label(item: Any) -> str:
        """Short human-readable identifier for logging per-item Phase A/B failures."""
        if isinstance(item, dict):
            if "owner" in item and "repo" in item:
                return f"{item.get('owner')}/{item.get('repo')}#{item.get('number', '?')}"
            target = item.get("target") if isinstance(item.get("target"), dict) else {}
            project = item.get("project") if isinstance(item.get("project"), dict) else {}
            return f"project={project.get('id', '?')}!{target.get('iid', item.get('id', '?'))}"
        return f"{getattr(item, 'project_ref', '?')}#{getattr(item, 'item_id', '?')}"

    @staticmethod
    def _mark_item_queued(item: Any) -> Any:
        if isinstance(item, VcsWorkItem):
            return dataclasses.replace(item, queued=True)
        if isinstance(item, dict):
            return {**item, "queued": True}
        return item

    async def _drain_platform_phase_ab(
        self,
        platform: VcsPlatformPort,
        queued_items: list[Any],
        new_items: list[Any],
        *,
        platform_label: str,
        phase_prefix: str = "",
        queue_fn: Callable[[Any, int], Awaitable[Any]] | None = None,
        on_queue_update: Callable[[list[Any]], None] | None = None,
        gate_closed_initial: bool = False,
    ) -> tuple[list[Any], int]:
        """Unified Phase A (promote queued FIFO) + Phase B (process new / queue on gate close).

        Isolates per-item exceptions (poison pills) and escalates fully-failed 2+ item batches
        via _raise_if_systemic_failure(). Invokes on_queue_update BEFORE raising so pending/queue
        observability reflects reality even across systemic outages.
        """
        si = "" if gate_closed_initial else platform.load_triage_instruction()
        remaining_queued = list(queued_items)

        # Phase A: Promote oldest queued items first (FIFO)
        attempted_a = 0
        failed_a = 0
        errors_a: list[BaseException] = []
        if not gate_closed_initial:
            for item in queued_items:
                if not await self.check_flow_gate():
                    break
                attempted_a += 1
                try:
                    context = await platform.fetch_context(item)
                    if context is None:
                        if hasattr(platform, "remove_queued_item"):
                            await platform.remove_queued_item(item)
                        remaining_queued = [q for q in remaining_queued if q is not item]
                        continue
                    plan_text = await self.analyze_and_plan(context, si)
                    await platform.create_platform_event(item, plan_text, context)
                    # Remove by identity, not position -- a prior item may have failed and been skipped.
                    remaining_queued = [q for q in remaining_queued if q is not item]
                except Exception as e:
                    failed_a += 1
                    errors_a.append(e)
                    logger.warning(
                        f"{platform_label} queued item processing failed for {self._item_label(item)}: {e}"
                    )
                    continue
        if on_queue_update is not None:
            on_queue_update(remaining_queued)
        _raise_if_systemic_failure(
            f"{phase_prefix}Phase A (queued promote)",
            attempted_a,
            failed_a,
            platform=platform_label,
            errors=errors_a,
        )

        # Phase B: Process new items (or queue when gate closes if queue_fn provided)
        gate_closed = gate_closed_initial
        newly_queued_in_phase_b = 0
        attempted_b = 0
        failed_b = 0
        errors_b: list[BaseException] = []
        for item in new_items:
            if gate_closed or not await self.check_flow_gate():
                gate_closed = True
                if queue_fn is None:
                    logger.info(f"Headhunter flow gate closed mid-cycle ({platform_label}) -- stopping")
                    break
                position = len(remaining_queued) + 1
                try:
                    queued_ok = await queue_fn(item, position)
                    if not queued_ok and getattr(queued_ok, "permanent", False):
                        logger.info(
                            f"{platform_label} queue item permanently rejected for "
                            f"{self._item_label(item)} (not counting toward systemic failure)"
                        )
                    elif not queued_ok:
                        attempted_b += 1
                        failed_b += 1
                        logger.warning(
                            f"{platform_label} queue item failed (label rejected) for {self._item_label(item)}"
                        )
                    else:
                        attempted_b += 1
                        remaining_queued.append(self._mark_item_queued(item))
                        newly_queued_in_phase_b += 1
                except Exception as e:
                    attempted_b += 1
                    failed_b += 1
                    errors_b.append(e)
                    logger.warning(
                        f"{platform_label} queue item failed for {self._item_label(item)}: {e}"
                    )
                continue
            attempted_b += 1
            try:
                context = await platform.fetch_context(item)
                if context is None:
                    continue
                plan_text = await self.analyze_and_plan(context, si)
                await platform.create_platform_event(item, plan_text, context)
            except Exception as e:
                failed_b += 1
                errors_b.append(e)
                logger.warning(
                    f"{platform_label} item processing failed for {self._item_label(item)}: {e}"
                )
                continue
        if on_queue_update is not None:
            on_queue_update(remaining_queued)
        _raise_if_systemic_failure(
            f"{phase_prefix}Phase B (new items)",
            attempted_b,
            failed_b,
            platform=platform_label,
            errors=errors_b,
        )
        return remaining_queued, newly_queued_in_phase_b

    async def _poll_and_process(self) -> None:
        """Single GitLab poll cycle (thin delegate over unified _drain_platform_phase_ab)."""
        await self._run_gitlab_wakeup()

        # Always poll regardless of gate state so items queue in Redis FIFO behind closed gate
        todos = await self._gitlab.poll_work_items()
        is_q = lambda t: (isinstance(t, dict) and (t.get("_queued") or t.get("queued"))) or getattr(t, "queued", False)
        queued_items = [t for t in todos if is_q(t)]
        new_items = [t for t in todos if not is_q(t)]
        self._gitlab_pending = len(new_items)

        def _sync_gitlab_queued(remaining: list[Any]) -> None:
            self._gitlab_queued = len(remaining)

        gate_open = await self.check_flow_gate()
        if not todos:
            self._gitlab_queued = 0
            logger.debug("Headhunter GitLab: no actionable items")
            return

        logger.info(
            f"Headhunter GitLab: {len(queued_items)} queued, {len(new_items)} new item(s) "
            f"(gate={'open' if gate_open else 'closed'})"
        )
        _, newly_queued = await self._drain_platform_phase_ab(
            self._gitlab,
            queued_items,
            new_items,
            platform_label="GitLab",
            queue_fn=self._gitlab.queue_item,
            on_queue_update=_sync_gitlab_queued,
            gate_closed_initial=not gate_open,
        )
        self._gitlab_pending = max(0, self._gitlab_pending - newly_queued)

    async def _github_poll_and_process(self) -> None:
        """Poll GitHub PRs (Phase A/B), active HEAD drift, Issues (Phase C), and review feedback (Phase D)."""
        # Reset queued cache at top of cycle
        self._github._last_queued_prs = []

        # Always poll regardless of gate state — UI needs queued count even when gate is closed
        prs = await self._github.poll_work_items()

        # Unconditional active PR HEAD drift clearing (independent of flow gate & Phase D)
        if hasattr(self._github, "check_active_pr_head_drift"):
            try:
                await self._github.check_active_pr_head_drift()
            except Exception as e:
                logger.warning(f"GitHub active PR HEAD drift check failed (non-fatal): {e}")
        queued_items = sorted(
            [p for p in prs if p.get("queued")],
            key=lambda x: x.get("created_at", ""),
        )
        new_items = [p for p in prs if not p.get("queued")]
        self._github_pending = len(new_items)

        def _sync_github_queued(remaining: list[Any]) -> None:
            self._github._last_queued_prs = remaining
            self._github_queued = len(remaining)

        gate_open = await self.check_flow_gate()
        if not gate_open:
            logger.debug("Headhunter flow gate closed -- queuing new PRs, observing queued state")
            self._github_feedback_pending = 0  # Phase D is skipped while the gate is closed

        _, newly_queued_in_phase_b = await self._drain_platform_phase_ab(
            self._github,
            queued_items,
            new_items,
            platform_label="GitHub",
            phase_prefix="PR ",
            queue_fn=self._github.queue_item,
            on_queue_update=_sync_github_queued,
            gate_closed_initial=not gate_open,
        )

        # Subtract newly-queued items from pending — they moved to queued state (avoids double-count)
        self._github_pending = max(0, self._github_pending - newly_queued_in_phase_b)

        if gate_open and not queued_items and not new_items:
            logger.debug("Headhunter GitHub: no actionable PRs")

        # Phase C: Poll Issues (darwin-work label)
        try:
            await self._github_poll_issues()
        except Exception as e:
            logger.warning(f"GitHub issue poll failed (non-fatal): {e}")

        if not gate_open:
            return

        # Phase D: PR review feedback / @mentions (flag-gated, flow-gate gated). Non-fatal like
        # Phase C: an optional feature must never abort _github_poll_and_process or feed the circuit breaker.
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
        """Poll GitHub Issues (darwin-work), queue/promote FIFO, and expose queued cache."""
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

        def _iref(issue: dict) -> str:
            return f"{issue.get('owner')}/{issue.get('repo')}#{issue.get('issue_number')}"

        async def _try_queue_issue(issue: dict, pos: int) -> str:
            try:
                ok = await self._github._queue_issue(issue, pos)
                if not ok and getattr(ok, "permanent", False):
                    logger.info(f"GitHub queue issue permanently rejected for {_iref(issue)}")
                    return "perm"
                return "ok" if ok else "fail"
            except Exception as e:
                logger.warning(f"GitHub queue issue failed for {_iref(issue)}: {e}")
                return "fail"

        if not await self.check_flow_gate():
            logger.debug("Headhunter flow gate closed -- queuing new issues, observing queued state")
            newly_queued: list[dict] = []
            for issue in new_items:
                if await _try_queue_issue(issue, len(queued_items) + len(newly_queued) + 1) == "ok":
                    newly_queued.append({**issue, "queued": True})
            self._github._last_queued_issues = queued_items + newly_queued
            self._github_issue_queued = len(self._github._last_queued_issues)
            self._github_issue_pending = max(0, self._github_issue_pending - len(newly_queued))
            return

        if issues:
            logger.info(f"Headhunter GitHub Issues: {len(issues)} actionable issue(s)")

        async def _process_issue(issue: dict) -> None:
            si, warn = await self._github._load_issue_triage_instruction(issue.get("labels", []))
            plan = await self.analyze_and_plan(issue, si)
            await self._github.create_issue_event({**issue, "_skill_size_warning": warn} if warn else issue, plan)

        # Phase A: Promote oldest queued Issues first (FIFO)
        remaining_queued = list(queued_items)
        attempted_a = 0
        failed_a = 0
        for issue in queued_items:
            if not await self.check_flow_gate():
                break
            attempted_a += 1
            try:
                await _process_issue(issue)
                remaining_queued = [q for q in remaining_queued if q is not issue]
            except Exception as e:
                failed_a += 1
                logger.warning(f"GitHub queued issue failed for {_iref(issue)}: {e}")
        self._github._last_queued_issues = remaining_queued
        self._github_issue_queued = len(remaining_queued)
        _raise_if_systemic_failure("Issue Phase A (queued promote)", attempted_a, failed_a)

        # Phase B: Process new issues (darwin-work label, not yet queued).
        gate_closed = False
        newly_queued_in_phase_b = 0
        attempted_b = 0
        failed_b = 0
        for issue in new_items:
            if gate_closed or not await self.check_flow_gate():
                gate_closed = True
                res = await _try_queue_issue(issue, len(remaining_queued) + 1)
                if res == "ok":
                    attempted_b += 1
                    remaining_queued.append({**issue, "queued": True})
                    newly_queued_in_phase_b += 1
                elif res == "fail":
                    attempted_b += 1
                    failed_b += 1
                continue
            attempted_b += 1
            try:
                await _process_issue(issue)
            except Exception as e:
                failed_b += 1
                logger.warning(f"GitHub issue failed for {_iref(issue)}: {e}")
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

    async def poll_github_run_status(self, owner: str, repo: str, run_id: int) -> dict:
        """Delegate to GitHub adapter. Registered as StateWatcher poll fn."""
        return await self._github.poll_github_run_status(owner, repo, run_id)

    @staticmethod
    def extract_github_run_state_key(state: dict) -> dict:
        """Delegate to GitHub adapter. Used by StateWatcher."""
        return GitHubPlatform.extract_github_run_state_key(state)

    @staticmethod
    def extract_github_state_key(state: dict) -> dict:
        """Delegate to GitHub adapter. Used by StateWatcher."""
        return GitHubPlatform.extract_github_state_key(state)

    @staticmethod
    def parse_pr_url(url: str) -> tuple[str, str, int] | None:
        """Delegate to GitHub adapter. Called by handlers_integration.py."""
        return GitHubPlatform.parse_pr_url(url)
