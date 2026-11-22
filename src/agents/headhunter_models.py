# BlackBoard/src/agents/headhunter_models.py
# @ai-rules:
# 1. [Constraint]: stdlib + typing ONLY. Zero I/O, zero Pydantic, zero async runtime deps,
#    zero relative imports (enforced by static AST fitness gate).
# 2. [Pattern]: Canonical dataclasses shared across VcsPlatformPort, GitLabPlatform,
#    GitHubPlatform, and Headhunter orchestrator.
# 3. [Security]: HeadhunterCircuitBreaker redacts secrets/emails and caps last_error at 200 chars
#    using pure stdlib regex so error telemetry is always safe to expose via /status or /flow.
"""Canonical stdlib domain models and half-open circuit breaker for Headhunter VCS platforms."""
from __future__ import annotations

from dataclasses import dataclass, field
import re
import time
from typing import Any, Literal

BreakerState = Literal["closed", "open", "half_open"]

_REDACT_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"-----BEGIN [A-Z0-9 ]{0,40}PRIVATE KEY-----.*"), "[REDACTED_KEY]"),
    (re.compile(r"://[^/\s?#]{1,1024}@"), "://[REDACTED]@"),
    (
        re.compile(
            r"eyJ[A-Za-z0-9_-]{8,512}\.eyJ[A-Za-z0-9_-]{8,512}\.[A-Za-z0-9_-]{8,512}"
        ),
        "[REDACTED_JWT]",
    ),
    (re.compile(r"github_pat_[A-Za-z0-9_]{1,255}"), "[REDACTED_TOKEN]"),
    (
        re.compile(
            r"gl(?:pat|oas|oa|rt|dt|cbt|ptt|soat|ft|imt|agent)-(?:[A-Za-z0-9_-]|\.(?=[A-Za-z0-9_-])){1,256}"
        ),
        "[REDACTED_TOKEN]",
    ),
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{1,255}"), "[REDACTED_TOKEN]"),
    (re.compile(r"(?i)((?:private_token|access_token)\s*=\s*)[^&\s]{1,256}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(Bearer\s+)\S{1,2048}"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(\bBasic[ \t]+)[A-Za-z0-9+/=_-]{4,2048}(?![A-Za-z0-9+/=_-])"), r"\1[REDACTED]"),
    (re.compile(r"(?i)(PRIVATE-TOKEN\s*[:=]\s*)\S{1,2048}"), r"\1[REDACTED]"),
    (
        re.compile(
            r"[A-Za-z0-9._%+-]{1,64}@[A-Za-z0-9-]{1,255}\.[A-Za-z0-9.-]{1,255}"
        ),
        "[REDACTED_EMAIL]",
    ),
)
_CTRL_WS_RE = re.compile(r"[\r\n\t\x00-\x1f\x7f]+")

_CANONICAL_LEGACY_ALIASES: dict[str, str] = {
    "mr_title": "title",
    "pr_title": "title",
    "issue_title": "title",
    "mr_description": "description",
    "pr_body": "description",
    "body": "description",
    "project_path": "project_ref",
    "repo": "project_ref",
    "pipeline_status": "ci_status",
    "check_status": "ci_status",
    "action_name": "action",
    "target_url": "url",
    "pr_url": "url",
    "html_url": "url",
    "pr_state": "state",
}
_ITEM_ID_KIND_ALIASES: dict[str, str] = {
    "mr_iid": "mr",
    "pr_number": "pr",
    "issue_number": "issue",
}


def _get_canonical_or_alias(obj: Any, key: str, default: Any = None) -> Any:
    """Resolve canonical dataclass fields and narrow explicit legacy aliases (no raw passthrough)."""
    if key != "raw" and key in obj.__dataclass_fields__:
        return getattr(obj, key)
    required_kind = _ITEM_ID_KIND_ALIASES.get(key)
    if required_kind is not None:
        return obj.item_id if getattr(obj, "item_kind", None) == required_kind else default
    canonical = _CANONICAL_LEGACY_ALIASES.get(key)
    if canonical is not None and canonical in obj.__dataclass_fields__:
        return getattr(obj, canonical)
    return default


def _redact_error_text(raw: str, max_len: int = 200) -> str:
    """Redact common tokens/credentials/emails, flatten control whitespace, and cap length."""
    bounded = str(raw or "")[: max(max_len * 4, 2048)]
    text = _CTRL_WS_RE.sub(" ", bounded).strip()
    for pat, repl in _REDACT_PATTERNS:
        text = pat.sub(repl, text)
    if len(text) > max_len:
        text = text[:max_len]
    return text


@dataclass
class VcsWorkItem:
    """Canonical platform-agnostic work item returned by poll_work_items()."""

    platform: Literal["gitlab", "github"]
    item_kind: Literal["mr", "pr", "issue"]
    item_id: int
    project_ref: str
    title: str
    author: str
    action: str
    ci_status: str = ""
    head_sha: str = ""
    url: str = ""
    created_at: str = ""
    queued: bool = False
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Read canonical fields or explicit legacy aliases (never falls through to raw)."""
        return _get_canonical_or_alias(self, key, default)

    def to_dict(self) -> dict[str, Any]:
        """Serialize canonical fields to a plain dict."""
        return {
            "platform": self.platform,
            "item_kind": self.item_kind,
            "item_id": self.item_id,
            "project_ref": self.project_ref,
            "title": self.title,
            "author": self.author,
            "action": self.action,
            "ci_status": self.ci_status,
            "head_sha": self.head_sha,
            "url": self.url,
            "created_at": self.created_at,
            "queued": self.queued,
        }


@dataclass
class VcsContext:
    """Canonical platform-agnostic enriched context returned by fetch_context()."""

    platform: Literal["gitlab", "github"]
    item_kind: Literal["mr", "pr", "issue"]
    item_id: int
    project_ref: str
    title: str
    description: str
    author: str
    source_branch: str
    target_branch: str
    head_sha: str
    state: str
    ci_status: str
    url: str
    raw: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Read canonical fields or explicit legacy aliases (never falls through to raw)."""
        return _get_canonical_or_alias(self, key, default)

    def to_dict(self) -> dict[str, Any]:
        """Serialize canonical fields to a plain dict."""
        return {
            "platform": self.platform,
            "item_kind": self.item_kind,
            "item_id": self.item_id,
            "project_ref": self.project_ref,
            "title": self.title,
            "description": self.description,
            "author": self.author,
            "source_branch": self.source_branch,
            "target_branch": self.target_branch,
            "head_sha": self.head_sha,
            "state": self.state,
            "ci_status": self.ci_status,
            "url": self.url,
        }


@dataclass
class PlatformQueueItem:
    """Normalized pending/queued work item for Redis snapshots and /queue/headhunter/pending."""

    platform: Literal["gitlab", "github"]
    item_kind: Literal["mr", "pr", "issue"]
    item_id: int
    project_ref: str
    title: str = ""
    author: str = ""
    url: str = ""
    head_sha: str = ""
    ci_status: str = ""
    status: str = "queued"
    queue_position: int | None = None
    enqueued_at: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class PlatformBreakerStatus:
    """Read-only telemetry view of a platform circuit breaker."""

    state: BreakerState = "closed"
    consecutive_failures: int = 0
    next_retry_at: float | None = None
    last_error: str | None = None


@dataclass
class PlatformSnapshot:
    """Per-platform poll snapshot persisted to Redis for zero-HTTP read endpoints."""

    platform: Literal["gitlab", "github"]
    enabled: bool = False
    pending_count: int = 0
    queued_count: int = 0
    last_poll_at: float | None = None
    partial_error: str | None = None
    breaker: PlatformBreakerStatus = field(default_factory=PlatformBreakerStatus)
    items: list[PlatformQueueItem] = field(default_factory=list)


class HeadhunterCircuitBreaker:
    """Self-recovering half-open circuit breaker with exponential cooldown.

    Lifecycle:
    - closed -> open after `max_failures` (default 3) consecutive non-401/403 errors.
    - open -> half_open once cooldown elapses (`300s -> 900s -> 1800s` capped).
    - half_open -> closed on successful probe; half_open -> open (next backoff step) on failure.
    - HTTP 401/403 auth/permission errors are exempt on BOTH GitLab and GitHub.
    - `reset()` manually closes the breaker and clears backoff counters immediately.
    """

    DEFAULT_COOLDOWN_SCHEDULE: tuple[float, ...] = (300.0, 900.0, 1800.0)

    def __init__(
        self,
        platform: str,
        *,
        max_failures: int = 3,
        cooldown_schedule: tuple[float, ...] = DEFAULT_COOLDOWN_SCHEDULE,
    ) -> None:
        self.platform = platform
        self.max_failures = max(1, max_failures)
        self.cooldown_schedule = cooldown_schedule or self.DEFAULT_COOLDOWN_SCHEDULE
        self.state: BreakerState = "closed"
        self.consecutive_failures: int = 0
        self.next_retry_at: float | None = None
        self.last_error: str | None = None
        self._open_count: int = 0
        self._open_until_mono: float = 0.0

    @staticmethod
    def is_auth_exempt(exc: BaseException) -> bool:
        """True if exc (or its __cause__/__context__ chain) carries an HTTP 401/403 status."""
        cur: BaseException | None = exc
        seen: set[int] = set()
        while cur is not None and id(cur) not in seen and len(seen) < 8:
            seen.add(id(cur))
            resp = getattr(cur, "response", None)
            status = getattr(resp, "status_code", None)
            if status in (401, 403):
                return True
            cur = cur.__cause__ if cur.__cause__ is not None else cur.__context__
        return False

    def should_attempt(self) -> bool:
        """Return True if this platform should be polled in the current cycle."""
        if self.state == "closed":
            return True
        if self.state == "open":
            if time.monotonic() >= self._open_until_mono:
                self.state = "half_open"
                self.next_retry_at = None
                return True
            return False
        # half_open: permit probe
        return True

    def record_success(self) -> None:
        """Reset failure counters and close the breaker after a clean poll."""
        self.state = "closed"
        self.consecutive_failures = 0
        self._open_count = 0
        self._open_until_mono = 0.0
        self.next_retry_at = None
        self.last_error = None

    def record_failure(self, error: BaseException | str) -> bool:
        """Record a non-exempt failure. Returns True if this failure opened/re-opened the breaker."""
        if isinstance(error, BaseException) and self.is_auth_exempt(error):
            return False

        self.last_error = _redact_error_text(str(error), max_len=200)
        if self.state == "open":
            return False

        self.consecutive_failures += 1

        if self.state == "half_open":
            self._open_count += 1
            return self._enter_open()

        if self.consecutive_failures >= self.max_failures:
            self._open_count = max(1, self._open_count + 1)
            return self._enter_open()

        return False

    def _enter_open(self) -> bool:
        idx = min(max(0, self._open_count - 1), len(self.cooldown_schedule) - 1)
        cooldown = float(self.cooldown_schedule[idx])
        self.state = "open"
        self._open_until_mono = time.monotonic() + cooldown
        self.next_retry_at = time.time() + cooldown
        return True

    def reset(self) -> None:
        """Operator/manual reset returning the breaker to closed immediately."""
        self.record_success()

    def to_status(self) -> PlatformBreakerStatus:
        """Return an immutable-style status snapshot for /status and /flow telemetry."""
        return PlatformBreakerStatus(
            state=self.state,
            consecutive_failures=self.consecutive_failures,
            next_retry_at=self.next_retry_at,
            last_error=self.last_error,
        )
