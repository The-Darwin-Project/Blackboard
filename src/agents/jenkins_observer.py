# BlackBoard/src/agents/jenkins_observer.py
# @ai-rules:
# 1. [Pattern]: Poll-driven event creation — _drain_once() fires every poll interval,
#    checks Jenkins for failed/missing/unstable CI gating jobs, triages with Flash Lite.
#    Phases are split into named helpers (_poll_and_stage, _recheck_and_filter,
#    _consolidate_floods, _process_candidates) -- mirrors Aligner._drain_once's structure.
# 2. [Pattern]: TimeKeeper lifecycle — start()/stop() own an asyncio.Task running _poll_loop().
# 3. [Constraint]: AIR GAP: No Brain logic. Creates events via blackboard, never routes agents.
# 4. [Pattern]: pending_count is an in-memory property updated at drain cycle start/end.
# 5. [Pattern]: Service naming: {job_name} (pending-queue key). Board-wide outage uses
#    view-outage:{view} as key with result=BOARD_RED. Classification is the Brain's job.
#    checks poll the correct Jenkins view.
# 6. [Pattern]: Lazy skills fetch with 5-min TTL (mirrors headhunter_github._load_issue_triage_instruction).
# 7. [Pattern]: Dry-run default — JENKINS_OBSERVER_DRY_RUN=true logs evidence but skips create_event.
# 8. [Pattern]: Dedup tuple includes waiting_approval (deliberate improvement over Aligner).
# 9. [Pattern]: Flood consolidation merges whole group into ONE event (Aligner pattern).
# 10. [Pattern]: LLM adapter uses the shared `.llm.create_adapter("gemini", ...)` factory
#     (same as Aligner/Headhunter) -- never construct GeminiAdapter directly.
# 11. [Constraint]: Untrusted Jenkins console-log content must be passed through
#     _sanitize_console_tail() before it reaches an LLM prompt (prompt-injection guard).
# 12. [Constraint]: Jenkins build parameters must be passed through
#     _redact_build_parameters() before entering ci_context -- they routinely carry
#     credentials and ci_context is served by GET /queue/{event_id} with no dedicated auth.
# 13. [Constraint]: LLM triage output (from _parse_triage_response) must be passed through
#     _validate_triage_entry() -- it is untrusted (LLM-generated from an attacker-influenceable
#     Jenkins console log) and flows into the Brain/FRIDAY prompt via llm/prompt.py.
# 14. [Constraint]: console_tail must be passed through _prepare_console_tail() which owns
#     the security-invariant order: redact -> strip pipeline noise -> slice -> sanitize.
#     _strip_pipeline_annotations is defined in the adapter (wire-format knowledge) but
#     called here (agents -> adapters is the correct hexagonal direction).
# 15. [Pattern]: _poll_and_stage() only stages FAILURE/UNSTABLE/ABORTED and truly-missing
#     jobs (no build at all). A job with result=None but a build_number is in-progress and
#     must not be staged as a failure signal.
# 16. [Pattern]: Maintainer escalation list from JENKINS_OBSERVER_MAINTAINERS env CSV,
#     injected into ci_context.maintainer matching Headhunter's static-source shape.
# 17. [Constraint]: LLM narrative analysis (from _parse_triage_response) must be passed
#     through _validate_analysis() -- same untrusted-output threat model as
#     _validate_triage_entry (constraint #13): redact_pii -> _redact_secrets_in_text ->
#     _sanitize_console_tail -> html.escape() per string field, then hard length/list caps,
#     before it can reach ci_context["analysis"] and, downstream, llm/prompt.py's second-hop
#     prompt and event_markdown.py's rehype-raw markdown sink (html.escape is the XSS guard
#     for the latter -- that sink has no separate sanitizer).
# 18. [Pattern]: Narrative analysis is feature-flagged via JENKINS_OBSERVER_ANALYSIS_ENABLED
#     (default true, accepts "true"/"1"/"yes" case-insensitive). The flag is read once at
#     JenkinsObserver.__init__ -- flipping it requires `helm upgrade` + pod restart, it is
#     NOT an instant kill-switch. When disabled, _build_triage_prompt() omits the narrative
#     instructions entirely (no request, no extra output tokens), and any analysis lives
#     inside the existing triage try/except -- any failure logs and falls back to the terse
#     (pre-Phase-1) evidence, never blocks event creation.
"""
JenkinsObserver: CI gating reconciliation daemon.

Polls Jenkins for failed/missing gating jobs, triages with Flash Lite,
creates events with source="aligner" + subject_type="ci_gating" for FRIDAY.
"""
from __future__ import annotations

import asyncio
import html
import json
import logging
import math
import os
import re
import time
from typing import TYPE_CHECKING, Optional

import httpx

if TYPE_CHECKING:
    from ..adapters.jenkins import JenkinsAdapter
    from ..state.blackboard import BlackboardState

from ..adapters.jenkins import _strip_pipeline_annotations
from ..models import CIAnalysis, EventEvidence
from ..skills_catalog import download_skill_md
from ..utils.pii_redaction import redact_pii

logger = logging.getLogger(__name__)

_DEDUP_STATUSES = ("new", "active", "deferred", "waiting_approval")

# Sentinel keys for _view_unhealthy -- neither is a real Jenkins view name.
# Both exist because view_unhealthy defaults to healthy (any() over an empty/
# unset dict is False), so every path that skips per-view scanning must
# explicitly opt in to "unhealthy" or the CI-gating-dark condition is masked.
# NOTE: if you ever iterate _view_unhealthy.items() for per-view logging/metrics,
# filter these out -- they are not views.
_VIEWS_UNCONFIGURED_KEY = "__no_views_configured__"
# Set in _drain_once() while self._adapter is None/disabled (missing Jenkins
# config, or circuit breaker open) -- cleared once the adapter is usable again
# so _poll_and_stage() can recompute real per-view health.
_ADAPTER_UNAVAILABLE_KEY = "__adapter_unavailable__"

# Bounds on the one-time legacy pipe-key migration in start() -- this runs on
# the app's critical startup path (awaited before the readiness probe), so it
# must never be allowed to scale with an unbounded backlog.
_LEGACY_MIGRATION_LIMIT = 500
_LEGACY_MIGRATION_TIMEOUT = 10.0  # seconds

_FALLBACK_SI = (
    "You are a CI gating triage assistant. Classify Jenkins job failures as "
    "infrastructure (flaky infra, cluster issues), test (real test failures), "
    "or product (genuine product bugs). Recommend: restart, investigate, or escalate."
)

_FENCE_BREAK = re.compile(r"```")


def _sanitize_console_tail(text: str) -> str:
    """Strip fence-breaking sequences from untrusted Jenkins console log content
    before it is embedded in an LLM prompt (prompt-injection guard)."""
    return _FENCE_BREAK.sub("'''", text) if text else text


_SECRET_PARAM_PATTERN = re.compile(
    r"(token|secret|password|passwd|pwd|key|credential|auth)", re.IGNORECASE
)
_REDACTED = "***REDACTED***"


def _redact_build_parameters(params: dict[str, str]) -> dict[str, str]:
    """Redact Jenkins build parameter values whose name looks secret-bearing.

    Build parameters are build-author controlled and routinely carry credentials
    (API tokens, passwords). ci_context is served via GET /queue/{event_id} with no
    dedicated auth on this route, so raw params must never reach it.
    """
    return {
        name: _REDACTED if _SECRET_PARAM_PATTERN.search(name) else value
        for name, value in params.items()
    }


# key=value / key: value pairs where the key looks secret-bearing (e.g. "TOKEN=abc123",
# "password: hunter2", 'token: 'abc'', '"password": "hunter2"') -- covers the common ways
# CI logs and JSON blobs leak credentials inline. The key may be quoted (JSON) or bare, and
# the value may be double-quoted, single-quoted, or a bare run of non-whitespace/delimiter
# characters. `[:=]` covers both "key: value" and "key=value" separators.
_SECRET_VALUE = r"(\"[^\"]*\"|'[^']*'|[^\s,}\]\"']+)"
_ANSI_CSI_SEQUENCE = r"(?:\x1b\[[0-9;]*m)+"
_SECRET_TEXT_PATTERN = re.compile(
    r"(?im)(\"?(?:token|secret|password|passwd|pwd|api[_-]?key|access[_-]?key|"
    r"private[_-]?key|secret[_-]?key|key|credential|authorization)\"?"
    r"(?:\s*:\s*|\s*=+\s*|" + _ANSI_CSI_SEQUENCE + r"))" + _SECRET_VALUE
)
_BEARER_TEXT_PATTERN = re.compile(
    r"(?i)(bearer(?:\s+|=+|" + _ANSI_CSI_SEQUENCE + r"))" + _SECRET_VALUE
)


def _redact_match(m: "re.Match") -> str:
    """Replace a secret-pattern match, preserving surrounding quotes on the value if any
    (so `password: "hunter2"` becomes `password: "***REDACTED***"`, not `password: "` +
    `***REDACTED***` with the closing quote left dangling)."""
    prefix, value = m.group(1), m.group(2)
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("\"", "'"):
        quote = value[0]
        return f"{prefix}{quote}{_REDACTED}{quote}"
    return prefix + _REDACTED


def _redact_secrets_in_text(text: str) -> str:
    """Redact common inline credential patterns -- bare, single-quoted, double-quoted, or
    JSON-style -- from untrusted free-text Jenkins console log content before it enters
    ci_context (same exposure vector as _redact_build_parameters, but for unstructured log
    text rather than a params dict).

    Bearer-token redaction MUST run before the generic key[:=]value pass -- otherwise
    "Authorization: Bearer <token>" matches the generic pattern first (key="Authorization",
    value="Bearer") and redacts only the literal word "Bearer", leaving the actual token
    in the text.
    """
    if not text:
        return text
    text = _BEARER_TEXT_PATTERN.sub(_redact_match, text)
    text = _SECRET_TEXT_PATTERN.sub(_redact_match, text)
    return text


def _prepare_console_tail(raw: str) -> str:
    """Redact -> strip pipeline noise -> slice.  Order is a security invariant.

    The adapter returns a decoded byte-windowed raw tail; this helper owns the
    production sequencing that closes the pre-strip-window secret leak (HIGH).
    Importing _strip_pipeline_annotations from the adapter is the correct
    hexagonal direction (agents -> adapters); the adapter never imports back.
    """
    if not raw:
        return ""
    redacted = _redact_secrets_in_text(raw)
    stripped = _strip_pipeline_annotations(redacted)
    sliced = stripped[-3000:] if len(stripped) > 3000 else stripped
    return _sanitize_console_tail(sliced)


_VALID_TRIAGE_CLASSIFICATIONS = frozenset({"infrastructure", "test", "product"})
_VALID_TRIAGE_ACTIONS = frozenset({"restart", "investigate", "escalate"})

_JOB_METADATA_KEEP_KEYS = frozenset({
    "version", "type", "name", "factory", "owner", "team", "tier",
})


def _parse_job_metadata(params: dict) -> dict:
    """Parse the JOB_METADATA JSON parameter into a clean subset.

    Returns empty dict on missing/invalid/non-dict content. Keeps only the
    useful fields (version, type, name, factory, owner, team, tier, labels[:20]).
    """
    raw = params.get("JOB_METADATA")
    if not raw or not isinstance(raw, str):
        return {}
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, RecursionError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    result = {k: v for k, v in data.items() if k in _JOB_METADATA_KEEP_KEYS}
    labels = data.get("labels")
    if isinstance(labels, list):
        result["labels"] = labels[:20]
    return result


def _clamp_confidence(value: object, default: float = 0.0) -> float:
    """Coerce untrusted confidence input to a float in [0, 1], defaulting to
    `default` on non-numeric input.

    NaN is explicitly rejected: `float("NaN")` parses successfully (valid JSON
    number literal), and NaN compares False to every bound, so an unguarded
    `max(0.0, min(1.0, nan))` silently promotes it to 1.0 -- the opposite of
    the intended fail-safe default. Shared by _validate_triage_entry and
    _validate_analysis (same duplicated clamp logic, same untrusted input).
    """
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return default
    if math.isnan(confidence):
        return default
    return max(0.0, min(1.0, confidence))


def _validate_triage_entry(entry: object) -> Optional[dict]:
    """Validate + normalize one LLM triage entry before it can reach ci_context and,
    downstream, the Brain/FRIDAY triage prompt (build_event_header in llm/prompt.py).

    LLM output is untrusted -- classification/recommended_action are enum-checked and
    confidence is clamped to a float in [0, 1], so no attacker-controlled free text
    (e.g. injected via a Jenkins console log) survives into the second-hop prompt.
    Unrecognized/extra fields (failed_leaves, owner, component, ...) are dropped since
    nothing downstream consumes them.
    """
    if not isinstance(entry, dict):
        return None

    classification = str(entry.get("classification", "")).strip().lower()
    if classification not in _VALID_TRIAGE_CLASSIFICATIONS:
        classification = "unknown"

    confidence = _clamp_confidence(entry.get("confidence", 0.0))

    recommended_action = str(entry.get("recommended_action", "")).strip().lower()
    if recommended_action not in _VALID_TRIAGE_ACTIONS:
        recommended_action = "investigate"

    return {
        "job_name": str(entry.get("job_name", ""))[:200],
        "classification": classification,
        "confidence": confidence,
        "recommended_action": recommended_action,
    }


_ANALYSIS_SUMMARY_MAX = 500
_ANALYSIS_PROBABLE_CAUSE_MAX = 1000
_ANALYSIS_NEXT_STEP_MAX = 300
_ANALYSIS_SIGNALS_MAX = 10
_ANALYSIS_SIGNAL_MAX = 200
_ANALYSIS_SUMMARY_DISPLAY_MAX = 160


def _sanitize_analysis_text(value: object, max_len: int) -> str:
    """Untrusted-LLM-narrative text pipeline: redact PII -> redact secrets ->
    sanitize (fence-break guard) -> escape HTML -> cap length. Mirrors the
    order used for console_tail in _prepare_console_tail (security invariant:
    redact before any truncation so a straddling secret can't survive a cut).

    html.escape() runs last, before the length cap, because this text (unlike
    console_tail) is rendered into markdown via event_markdown.py, which the UI
    renders with rehype-raw and no separate sanitizer -- an unescaped
    `<img onerror=...>`-style payload echoed by the LLM from attacker-controlled
    Jenkins console logs would otherwise execute as live DOM (stored XSS).
    """
    text = str(value) if value is not None else ""
    text = redact_pii(text)
    text = _redact_secrets_in_text(text)
    text = _sanitize_console_tail(text)
    text = html.escape(text)
    return text[:max_len]


def _validate_analysis(obj: object) -> Optional[dict]:
    """Validate + normalize the LLM's narrative analysis object before it can
    reach ci_context["analysis"] and, downstream, the Brain/FRIDAY prompt.

    Same untrusted-output threat model as _validate_triage_entry (the narrative
    derives from attacker-influenceable Jenkins console logs): every string
    field is redacted, HTML-escaped, and capped; confidence is clamped to
    [0, 1]; signals are capped in count and per-item length; unknown keys are
    dropped by constructing through the typed CIAnalysis model.
    """
    if not isinstance(obj, dict):
        return None

    summary = _sanitize_analysis_text(obj.get("summary", ""), _ANALYSIS_SUMMARY_MAX)
    probable_cause = _sanitize_analysis_text(obj.get("probable_cause", ""), _ANALYSIS_PROBABLE_CAUSE_MAX)
    suggested_next_step = _sanitize_analysis_text(obj.get("suggested_next_step", ""), _ANALYSIS_NEXT_STEP_MAX)

    raw_signals = obj.get("signals", [])
    signals: list[str] = []
    if isinstance(raw_signals, list):
        for s in raw_signals[:_ANALYSIS_SIGNALS_MAX]:
            cleaned = _sanitize_analysis_text(s, _ANALYSIS_SIGNAL_MAX)
            if cleaned:
                signals.append(cleaned)

    confidence = _clamp_confidence(obj.get("confidence", 0.0))

    analysis = CIAnalysis(
        summary=summary,
        probable_cause=probable_cause,
        suggested_next_step=suggested_next_step,
        signals=signals,
        confidence=confidence,
    )
    return analysis.model_dump()


_TRUTHY_ENV_VALUES = ("true", "1", "yes")


def _env_flag(name: str, default: str = "true") -> bool:
    """Parse a boolean-ish env var, accepting common truthy spellings
    ('true', '1', 'yes', case-insensitive). A strict `== "true"` comparison
    silently treats GitOps-overlay-common spellings like "1"/"yes"/"TRUE" as
    disabled -- an untested footgun for kill-switch-style flags."""
    return os.getenv(name, default).strip().lower() in _TRUTHY_ENV_VALUES


class JenkinsObserver:
    """CI gating reconciliation daemon — mirrors Aligner poll pattern."""

    def __init__(
        self,
        blackboard: "BlackboardState",
        jenkins_adapter: Optional["JenkinsAdapter"] = None,
    ):
        self.blackboard = blackboard
        self._adapter = jenkins_adapter
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._pending_count: int = 0

        self._poll_interval = int(os.getenv("JENKINS_OBSERVER_POLL_INTERVAL", "300"))
        self._startup_delay = int(os.getenv("JENKINS_OBSERVER_STARTUP_DELAY", "180"))
        self._dwell_seconds = float(os.getenv("JENKINS_OBSERVER_DWELL_SECONDS", "60"))
        self._flood_threshold = int(os.getenv("JENKINS_OBSERVER_FLOOD_THRESHOLD", "3"))
        self._dry_run = os.getenv("JENKINS_OBSERVER_DRY_RUN", "true").lower() == "true"
        self._wip_cap = int(os.getenv("MAX_ACTIVE_EVENTS", "20"))
        self._views = [
            v.strip() for v in os.getenv("JENKINS_OBSERVER_VIEWS", "").split(",") if v.strip()
        ]
        self._recency_hours = float(os.getenv("JENKINS_OBSERVER_RECENCY_HOURS", "72"))
        self._analysis_enabled = _env_flag("JENKINS_OBSERVER_ANALYSIS_ENABLED")

        self._view_unhealthy: dict[str, bool] = {}

        self._skills_si: str = _FALLBACK_SI
        self._skills_loaded_at: float = 0.0
        self._skills_ttl: float = 300.0  # 5 minutes

        self._llm_adapter = None

    @property
    def pending_count(self) -> int:
        """In-memory pending count updated each drain cycle."""
        return self._pending_count

    @property
    def breaker_open(self) -> bool:
        """Circuit breaker state from the Jenkins adapter."""
        if self._adapter:
            return self._adapter.breaker_open
        return False

    @property
    def view_unhealthy(self) -> bool:
        """True if any configured view returned 404 on last scan."""
        return any(self._view_unhealthy.values())

    async def start(self) -> None:
        """Start the poll loop task. Migrates a bounded batch of legacy pipe-key
        entries on first start (capped by count and wall-clock time so a large
        backlog cannot delay pod readiness past the probe timeout)."""
        if self._running:
            return
        self._running = True
        try:
            await asyncio.wait_for(
                self._migrate_legacy_pipe_keys(), timeout=_LEGACY_MIGRATION_TIMEOUT
            )
        except asyncio.TimeoutError:
            logger.warning(
                "JenkinsObserver: pipe-key cutover exceeded %.0fs timeout, "
                "remaining legacy entries will be retried on next start",
                _LEGACY_MIGRATION_TIMEOUT,
            )
        except Exception as e:
            logger.warning("JenkinsObserver: pipe-key cutover failed (%s), continuing", e)

        self._task = asyncio.create_task(self._poll_loop())
        logger.info(
            "JenkinsObserver started (interval=%ds, dwell=%ds, views=%s, dry_run=%s)",
            self._poll_interval, self._dwell_seconds, self._views, self._dry_run,
        )

    async def _migrate_legacy_pipe_keys(self) -> None:
        """Pipe-key cutover: commit up to _LEGACY_MIGRATION_LIMIT legacy
        {job}|{version} keys left from a prior format. Bounded by count so this
        one-time migration cannot grow unboundedly with the pending queue size."""
        members = await self.blackboard.redis.zrange(
            self.blackboard.JENKINS_PENDING, 0, _LEGACY_MIGRATION_LIMIT - 1
        )
        for item in members:
            # zrange may return tuples (member, score) or bytes/str depending on withscores
            if isinstance(item, tuple):
                member = item[0]
            else:
                member = item
            if isinstance(member, bytes):
                member = member.decode("utf-8")
            if "|" in member:
                await self.blackboard.commit_jenkins_signal(member)
                logger.info("JenkinsObserver: migrated legacy pipe-key %s", member)

    async def stop(self) -> None:
        """Stop the poll loop task."""
        if not self._running:
            return
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self._adapter:
            await self._adapter.close()

    async def _poll_loop(self) -> None:
        """Periodic drain loop with startup delay."""
        await asyncio.sleep(self._startup_delay)
        while self._running:
            try:
                await self._drain_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("JenkinsObserver: drain cycle failed, continuing")
            await asyncio.sleep(self._poll_interval)

    async def _ensure_skills_loaded(self) -> None:
        """Lazy-fetch Skills Catalog SKILL.md texts from ZIP downloads. Never raises."""
        if time.time() - self._skills_loaded_at < self._skills_ttl:
            return
        catalog_url = os.getenv("SKILLS_CATALOG_URL", "")
        skills_csv = os.getenv("SKILLS_CATALOG_SKILLS", "")
        if not catalog_url:
            self._skills_loaded_at = time.time()
            return

        parts: list[str] = []
        async with httpx.AsyncClient(timeout=10, verify=False) as client:
            for slug in skills_csv.split(","):
                slug = slug.strip()
                if not slug:
                    continue
                try:
                    resp = await client.get(f"{catalog_url}/api/v1/skills/{slug}/download")
                    if resp.status_code != 200:
                        logger.warning("JenkinsObserver: Catalog slug '%s' returned %s", slug, resp.status_code)
                        continue
                    md = download_skill_md(resp.content, slug)
                    if md:
                        parts.append(_sanitize_console_tail(md[:10000]))
                    else:
                        logger.warning("JenkinsObserver: No SKILL.md in ZIP for slug '%s'", slug)
                except Exception as e:
                    logger.warning("JenkinsObserver: Catalog fetch failed for slug '%s' (%s)", slug, e)
        if parts:
            self._skills_si = "\n\n---\n\n".join(parts)
        self._skills_loaded_at = time.time()

    async def _get_llm_adapter(self):
        """Lazy-load a Gemini adapter via the shared factory for Flash Lite triage."""
        if self._llm_adapter is None:
            from .llm import create_adapter
            project = os.getenv("GCP_PROJECT")
            location = os.getenv("GCP_LOCATION", "us-central1")
            model = os.getenv("LLM_MODEL_JENKINS_OBSERVER", "gemini-3.5-flash-lite")
            self._llm_adapter = create_adapter("gemini", project, location, model)
        return self._llm_adapter

    async def _get_wip_headroom(self) -> int:
        """Query current WIP usage and return available headroom."""
        try:
            status_map = await self.blackboard.get_active_events_with_status()
            wip_used = sum(1 for s in status_map.values() if s in ("new", "active", "deferred"))
            return max(0, self._wip_cap - wip_used)
        except Exception as e:
            logger.warning("JenkinsObserver: WIP headroom query failed (%s), defaulting to 5", e)
            return 5

    async def _drain_once(self) -> None:
        """Single drain cycle: poll → stage → dwell → triage → create.

        Delegates to phase helpers (mirrors Aligner._drain_once's structure) so each
        phase can be reasoned about and tested independently.
        """
        await self._ensure_skills_loaded()

        if not self._adapter or not self._adapter.enabled():
            logger.error(
                "JenkinsObserver: adapter %s -- CI gating discovery is completely "
                "dark. Marking unhealthy.",
                "not configured" if not self._adapter else "disabled (breaker open?)",
            )
            self._view_unhealthy[_ADAPTER_UNAVAILABLE_KEY] = True
            return
        # Adapter is back up -- let _poll_and_stage() recompute real per-view health
        # instead of leaving this sentinel stuck true from a since-recovered outage.
        self._view_unhealthy.pop(_ADAPTER_UNAVAILABLE_KEY, None)

        await self._poll_and_stage()

        expired_keys = await self.blackboard.drain_jenkins_pending(self._dwell_seconds)
        self._pending_count = await self.blackboard.count_jenkins_pending()
        if not expired_keys:
            return

        candidates = await self._recheck_and_filter(expired_keys)
        self._pending_count = await self.blackboard.count_jenkins_pending()
        if not candidates:
            return

        groups = self._consolidate_floods(candidates)
        await self._process_candidates(groups)
        self._pending_count = await self.blackboard.count_jenkins_pending()

    async def _poll_and_stage(self) -> None:
        """Phase 1: poll Jenkins views and stage failing/missing jobs.

        Keys are {job_name}. Board-wide-red uses view-outage:{view}.
        The observer does not classify jobs into categories -- it discovers broadly
        and lets the Brain classify from content.
        """
        if not self._views:
            logger.error(
                "JenkinsObserver: JENKINS_OBSERVER_VIEWS is empty while the observer is "
                "enabled -- CI gating discovery is completely dark. Marking unhealthy."
            )
            self._view_unhealthy[_VIEWS_UNCONFIGURED_KEY] = True
            return
        for view in self._views:
            scan = await self._adapter.scan_view(view)

            if scan.status_code == 404:
                logger.error("JenkinsObserver: view %r returned 404 — marking unhealthy", view)
                self._view_unhealthy[view] = True
                continue
            if scan.status_code is None and not scan.jobs:
                self._view_unhealthy[view] = False
                continue
            self._view_unhealthy[view] = False

            # Filter out disabled/notbuilt and in-progress jobs
            eligible: list = []
            for job in scan.jobs:
                if job.color in ("disabled", "notbuilt", "disabled_anime", "notbuilt_anime"):
                    continue
                if job.result is None and job.build_number is not None:
                    continue
                eligible.append(job)

            # Recency filter: drop SUCCESS-only when stale
            recency_cutoff_ms = time.time() * 1000 - (self._recency_hours * 3600 * 1000)
            post_recency: list = []
            for job in eligible:
                if job.result == "SUCCESS":
                    if job.timestamp is not None and job.timestamp < recency_cutoff_ms:
                        continue
                post_recency.append(job)

            # Board-wide-red detection (post-color AND post-recency)
            # Only triggers when a significant portion of the view (>70%) is failing
            # and there are enough jobs for "board-wide" to be meaningful (>= 3)
            active = [j for j in post_recency if not (j.result is None and j.build_number is not None)]
            failing = [
                j for j in active
                if j.result in ("FAILURE", "UNSTABLE", "ABORTED") or j.result is None
            ]
            if len(active) >= 3 and len(failing) / len(active) > 0.7:
                key = f"view-outage:{view}"
                metadata = {
                    "job_name": key,
                    "version": "multi",
                    "view": view,
                    "result": "BOARD_RED",
                    "build_number": None,
                    "url": "",
                    "staged_at": time.time(),
                    "failing_count": len(failing),
                    "active_count": len(active),
                }
                await self.blackboard.stage_jenkins_signal(key, metadata)
                continue

            # Stage each failing/missing job individually
            for job in post_recency:
                if job.result in ("FAILURE", "UNSTABLE", "ABORTED") or job.result is None:
                    if job.build_number is not None:
                        last_alert = await self.blackboard.get_jenkins_last_alerted_build(job.job_name)
                        if job.build_number <= last_alert:
                            logger.debug("JenkinsObserver: skipping already-alerted build %s for %s", job.build_number, job.job_name)
                            continue

                    version = self._extract_version_from_name(job.job_name)
                    key = job.job_name
                    metadata = {
                        "job_name": job.job_name,
                        "version": version,
                        "view": view,
                        "result": job.result or "MISSING",
                        "build_number": job.build_number,
                        "url": job.url,
                        "staged_at": time.time(),
                    }
                    await self.blackboard.stage_jenkins_signal(key, metadata)

    @staticmethod
    def _extract_version_from_name(name: str) -> str:
        """Extract a version like '4.22' from a job name, or 'unknown'."""
        match = re.search(r"(\d+\.\d+)", name)
        return match.group(1) if match else "unknown"

    async def _recheck_and_filter(self, expired_keys: list[str]) -> list[tuple[str, dict]]:
        """Phase 2: load metadata for expired keys and discard self-resolved jobs.

        Recheck polls are cached per view so an N-signal flood costs one scan, not N.
        Malformed/missing metadata is evicted (committed) rather than raising, so a single
        poison-pill entry can't block the drain cycle forever. Missing 'view' key in meta
        is treated as a poison-pill (legacy pipe-key format).
        """
        metas: dict[str, dict] = {}
        for key in expired_keys:
            raw = await self.blackboard.redis.hget(self.blackboard.JENKINS_PENDING_META, key)
            if not raw:
                await self.blackboard.commit_jenkins_signal(key)
                continue
            try:
                metas[key] = json.loads(raw)
            except (json.JSONDecodeError, TypeError, ValueError) as e:
                logger.warning("JenkinsObserver: malformed pending metadata for %s (%s), evicting", key, e)
                await self.blackboard.commit_jenkins_signal(key)

        if not metas:
            return []

        recheck_cache: dict[str, list] = {}
        candidates: list[tuple[str, dict]] = []
        for key, meta in metas.items():
            job_name = meta.get("job_name", "")
            view = meta.get("view", "")

            # Poison-pill: no view key means legacy pipe-key format
            if not view:
                logger.warning("JenkinsObserver: no 'view' in metadata for %s, evicting (poison-pill)", key)
                await self.blackboard.commit_jenkins_signal(key)
                continue

            # BOARD_RED entries skip recheck (aggregate, not per-job)
            if meta.get("result") == "BOARD_RED":
                candidates.append((key, meta))
                continue

            if self._adapter and job_name:
                if view not in recheck_cache:
                    scan = await self._adapter.scan_view(view)
                    recheck_cache[view] = scan.jobs if scan.jobs else []
                resolved = any(
                    j.job_name == job_name and j.result == "SUCCESS"
                    for j in recheck_cache[view]
                )
                if resolved:
                    await self.blackboard.commit_jenkins_signal(key)
                    continue

            candidates.append((key, meta))

        return candidates

    def _consolidate_floods(
        self, candidates: list[tuple[str, dict]]
    ) -> list[list[tuple[str, dict]]]:
        """Phase 3: group candidates by version, consolidating floods into one group each."""
        by_version: dict[str, list[tuple[str, dict]]] = {}
        for key, meta in candidates:
            v = meta.get("version", "unknown")
            by_version.setdefault(v, []).append((key, meta))

        groups: list[list[tuple[str, dict]]] = []
        for version, signals in by_version.items():
            if len(signals) > self._flood_threshold:
                groups.append(signals)
            else:
                groups.extend([signal] for signal in signals)
        return groups

    async def _is_duplicate_or_escalated(self, service_name: str) -> bool:
        """Active-event dedup (Layer 1) + escalation-gate (Layer 3) checks.

        Raises on Redis/blackboard errors instead of fail-open -- the caller treats any
        exception as "unknown", restaging the signal for the next cycle rather than
        risking a duplicate event.
        """
        status_map = await self.blackboard.get_active_events_with_status()
        for eid, status in status_map.items():
            if status in _DEDUP_STATUSES:
                evt = await self.blackboard.get_event(eid)
                if evt and evt.service == service_name:
                    return True

        flag = await self.blackboard.get_escalation_flag(service_name, scope="jenkins")
        return bool(flag)

    async def _process_candidates(self, groups: list[list[tuple[str, dict]]]) -> None:
        """Phase 4: per-group dedup/escalation/WIP gating, triage, and event creation."""
        available = await self._get_wip_headroom()

        for signals in groups:
            if len(signals) > 1:
                service_name = f"ci-gating-flood|{signals[0][1].get('version', '')}"
            else:
                k, m = signals[0]
                if m.get("result") == "BOARD_RED":
                    service_name = f"ci-gating-outage|{m.get('view', '')}"
                else:
                    version = m.get("version", "")
                    service_name = f"{m.get('job_name', k)}|{version}" if version else m.get("job_name", k)

            try:
                if await self._is_duplicate_or_escalated(service_name):
                    for key, _ in signals:
                        await self.blackboard.commit_jenkins_signal(key)
                    continue
            except Exception:
                logger.exception(
                    "JenkinsObserver: dedup/escalation check failed for %s, restaging", service_name
                )
                for key, meta in signals:
                    await self.blackboard.restage_jenkins_signal(key, meta)
                continue

            if available <= 0:
                for key, meta in signals:
                    await self.blackboard.restage_jenkins_signal(key, meta)
                continue
            available -= 1

            evidence_obj = await self._triage_and_build_evidence(signals)

            if self._dry_run:
                logger.info(
                    "JenkinsObserver DRY-RUN: would create event for service=%s evidence=%s",
                    service_name, json.dumps(evidence_obj.model_dump(), default=str)[:500],
                )
                for key, _ in signals:
                    await self.blackboard.commit_jenkins_signal(key)
                continue

            try:
                reason = f"CI gating failure: {service_name}"
                await self.blackboard.create_event(
                    source="aligner",
                    service=service_name,
                    reason=reason,
                    evidence=evidence_obj,
                    subject_type="ci_gating",
                )
                
                for _, meta in signals:
                    bn = meta.get("build_number")
                    jn = meta.get("job_name", "")
                    if bn is not None and jn:
                        try:
                            await self.blackboard.set_jenkins_last_alerted_build(jn, bn)
                            logger.debug(
                                "JenkinsObserver: committed last_alerted_build %s for %s", bn, jn,
                            )
                        except Exception as e:
                            logger.warning("Failed to set last_alerted_build for %s: %s", jn, e, exc_info=True)

                for key, _ in signals:
                    await self.blackboard.commit_jenkins_signal(key)
            except Exception:
                logger.exception("JenkinsObserver: event creation failed for %s, restaging", service_name)
                for key, meta in signals:
                    await self.blackboard.restage_jenkins_signal(key, meta)

    async def _triage_and_build_evidence(
        self, signals: list[tuple[str, dict]]
    ) -> EventEvidence:
        """Run Flash Lite triage on failed jobs and build structured evidence."""
        failed_jobs = []
        missing_jobs = []
        version = signals[0][1].get("version", "") if signals else ""
        jenkins_url = os.getenv("JENKINS_URL", "")

        details_fetched = 0
        for _, meta in signals:
            result = meta.get("result", "UNKNOWN")
            job_entry = {
                "job_name": meta.get("job_name", ""),
                "build_number": meta.get("build_number"),
                "result": result,
                "jenkins_link": meta.get("url", ""),
            }
            if result == "MISSING" or meta.get("build_number") is None:
                missing_jobs.append({
                    "job_name": meta.get("job_name", ""),
                    "last_build_number": meta.get("build_number"),
                    "last_result": result,
                })
            else:
                if self._adapter and meta.get("build_number") and details_fetched < 10:
                    details = await self._adapter.get_build_details(
                        meta["job_name"], meta["build_number"]
                    )
                    details_fetched += 1
                    if details:
                        job_entry["console_tail"] = _prepare_console_tail(details.console_tail or "")
                        redacted_params = _redact_build_parameters(details.parameters)
                        job_metadata = _parse_job_metadata(redacted_params)
                        if job_metadata:
                            job_entry["job_metadata"] = job_metadata
                            if job_metadata.get("version"):
                                version = job_metadata["version"]
                        # Strip raw JOB_METADATA and CI_MESSAGE from parameters
                        cleaned_params = {
                            k: v for k, v in redacted_params.items()
                            if k not in ("JOB_METADATA", "CI_MESSAGE")
                        }
                        job_entry["parameters"] = cleaned_params
                failed_jobs.append(job_entry)

        # LLM triage (+ narrative analysis, when enabled)
        llm_triage = []
        analysis: Optional[dict] = None
        try:
            adapter = await self._get_llm_adapter()
            prompt = self._build_triage_prompt(
                failed_jobs, missing_jobs, version, include_analysis=self._analysis_enabled
            )
            response = await adapter.generate(
                system_prompt=self._skills_si,
                contents=prompt,
                temperature=float(os.getenv("LLM_TEMPERATURE_JENKINS_OBSERVER", "0.3")),
                max_output_tokens=int(os.getenv("LLM_MAX_TOKENS_JENKINS_OBSERVER", "4096")),
            )
            from .llm import record_token_usage
            record_token_usage("jenkins_observer", response.usage if response else None)
            if response and response.text:
                llm_triage, parsed_analysis = self._parse_triage_response(response.text)
                if self._analysis_enabled:
                    analysis = parsed_analysis
        except Exception as e:
            logger.warning("JenkinsObserver: LLM triage failed (%s), continuing without", e)

        maintainer_csv = os.getenv("JENKINS_OBSERVER_MAINTAINERS", "")
        maintainer_emails = [e.strip() for e in maintainer_csv.split(",") if e.strip()]

        ci_context = {
            "cnv_version": version,
            "jenkins_url": jenkins_url,
            "failed_jobs": failed_jobs,
            "missing_jobs": missing_jobs,
            "llm_triage": llm_triage,
            "maintainer": {"source": "static", "emails": maintainer_emails},
        }
        if analysis and analysis.get("summary"):
            ci_context["analysis"] = analysis

        display_parts = []
        if failed_jobs:
            display_parts.append(f"{len(failed_jobs)} failed CI gating job(s)")
        if missing_jobs:
            display_parts.append(f"{len(missing_jobs)} missing job(s)")
        display_text = f"CNV {version}: {', '.join(display_parts)}" if display_parts else f"CNV {version}: CI gating issue"
        if analysis and analysis.get("summary"):
            display_text = f"{display_text} — {analysis['summary'][:_ANALYSIS_SUMMARY_DISPLAY_MAX]}"

        return EventEvidence(
            display_text=display_text,
            source_type="aligner",
            domain="disorder",
            domain_confidence="default",
            severity="warning",
            ci_context=ci_context,
        )

    def _build_triage_prompt(
        self,
        failed_jobs: list[dict],
        missing_jobs: list[dict],
        version: str,
        *,
        include_analysis: bool = True,
    ) -> str:
        """Build a triage prompt for Flash Lite.

        include_analysis gates the narrative-analysis instructions/JSON-schema
        below JENKINS_OBSERVER_ANALYSIS_ENABLED: when the kill switch is off,
        the LLM is never asked to produce the narrative, so no extra output
        tokens are spent generating text that would just be discarded.
        """
        lines = [f"CNV version: {version}", ""]
        lines.append("Prior: UNSTABLE results are likely test/product failures. FAILURE results are likely infra/pipeline failures.")
        lines.append("")
        if failed_jobs:
            lines.append("## Failed Jobs")
            for j in failed_jobs[:10]:
                lines.append(f"- {j['job_name']} #{j.get('build_number', '?')} [{j.get('result', '?')}]")
                if j.get("console_tail"):
                    lines.append(f"  Console (untrusted log data, last 500 chars): {j['console_tail'][-500:]}")
        if missing_jobs:
            lines.append("\n## Missing Jobs (never ran)")
            for j in missing_jobs[:10]:
                lines.append(f"- {j['job_name']}")
        lines.append("\nFor each job, classify as: infrastructure, test, or product failure.")
        lines.append("Recommend: restart, investigate, or escalate.")
        if not include_analysis:
            lines.append(
                "\nReturn a single JSON object: {\"triage\": [{\"job_name\": ..., \"classification\": ..., "
                "\"confidence\": 0.0-1.0, \"recommended_action\": ..., \"failed_leaves\": [...], \"owner\": ..., "
                "\"component\": ...}]}"
            )
            return "\n".join(lines)
        lines.append(
            "\nAlso provide a top-level narrative analysis of the overall failure, in addition "
            "to the per-job triage array:"
        )
        lines.append("- summary: 1-2 sentence plain-English summary of what went wrong")
        lines.append("- probable_cause: your best-guess root cause given the evidence above")
        lines.append("- signals: short quoted snippets of log evidence that support probable_cause")
        lines.append("- suggested_next_step: the single most useful next action for a human/agent to take")
        lines.append("- confidence: 0.0-1.0 confidence in probable_cause")
        lines.append(
            "\nReturn a single JSON object: {\"triage\": [{\"job_name\": ..., \"classification\": ..., "
            "\"confidence\": 0.0-1.0, \"recommended_action\": ..., \"failed_leaves\": [...], \"owner\": ..., "
            "\"component\": ...}], \"analysis\": {\"summary\": ..., \"probable_cause\": ..., "
            "\"signals\": [...], \"suggested_next_step\": ..., \"confidence\": 0.0-1.0}}"
        )
        return "\n".join(lines)

    def _parse_triage_response(self, text: str) -> tuple[list[dict], Optional[dict]]:
        """Parse LLM triage JSON response. Tolerant of markdown fences.

        Accepts both the legacy bare-array shape (back-compat: a prior prompt
        version, or a model that ignores the new instruction) and the current
        {"triage": [...], "analysis": {...}} object shape. Returns
        (triage_entries, analysis) -- analysis is None for the bare-array shape
        or when the object omits/mis-shapes the "analysis" key.

        Each triage entry is validated/normalized by _validate_triage_entry(),
        and analysis by _validate_analysis() -- both untrusted (LLM-generated
        from an attacker-influenceable Jenkins console log).
        """
        text = text.strip()
        if text.startswith("```"):
            lines = text.split("\n")
            text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
        try:
            result = json.loads(text)
        except json.JSONDecodeError:
            return [], None

        if isinstance(result, list):
            validated = (_validate_triage_entry(entry) for entry in result[:10])
            return [entry for entry in validated if entry is not None], None

        if isinstance(result, dict):
            raw_triage = result.get("triage", [])
            triage = []
            if isinstance(raw_triage, list):
                validated = (_validate_triage_entry(entry) for entry in raw_triage[:10])
                triage = [entry for entry in validated if entry is not None]
            analysis = _validate_analysis(result.get("analysis"))
            return triage, analysis

        return [], None
