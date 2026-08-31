# BlackBoard/src/adapters/jenkins.py
# @ai-rules:
# 1. [Pattern]: Hexagonal adapter -- httpx-based Jenkins REST API client. No domain logic.
# 2. [Constraint]: Auth via Basic (user:token). verify=False for self-signed certs.
# 3. [Pattern]: 3-strike latch circuit breaker (mirrors headhunter.py:271-309).
#    401/403 excluded from strike count. Best-effort fetches (console-log tail) pass
#    count_failures=False -- they must not trip the breaker on their own since they're
#    unrelated to core reachability.
# 3b. [Pattern]: Time-based auto-recovery -- after breaker_cooldown_seconds elapses since
#    the latch tripped, _maybe_reset_breaker() unlatches for a fresh attempt (resets the
#    strike counter). A still-unreachable Jenkins re-latches after breaker_threshold more
#    failures. Prevents a transient outage from requiring a manual pod restart forever.
# 4. [Contract]: breaker_open property for FlowCollector observability.
# 5. [Constraint]: All org-specific values from constructor args (env vars resolved by caller).
# 6. [Pattern]: View-based discovery -- scan_view(view) queries /view/{name}/api/json
#    for all jobs in the view with their lastBuild status in a single HTTP call.
#    404 = view not found (valid health signal). Adapter does NOT own recency/color
#    filtering -- that is observer domain logic.
# 7. [Contract]: No wave-scoped breaker accounting needed -- scan_view is a single
#    HTTP call per view, not a fan-out. _record_success/_record_failure called directly.
# 8. [Design]: No category awareness (smoke/gating/etc.). The adapter polls ALL configured
#    patterns uniformly. Classification is the Brain's/LLM's job, not the observer's.
# 9. [Pattern]: Pipeline noise stripping (`_strip_pipeline_annotations`) happens in the Adapter
#    BEFORE slice, bounded to a fixed pre-strip window -- bounded wire-format cleanup on an
#    attacker-influenceable log body, not business logic.
"""
Jenkins CI platform adapter -- poll jobs, inspect job run state, get build details, restart.

Used by JenkinsObserver for CI gating reconciliation.
"""
from __future__ import annotations

import logging
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable
import re

import httpx

logger = logging.getLogger(__name__)

# Pre-strip window sizing (see _strip_pipeline_annotations): _MAX_BLOB_LEN is
# a hard cap on how long a single `ha:////` match can be, chosen so that
# _MAX_BLOB_LEN + _CONSOLE_TAIL_SIZE <= _PRESTRIP_WINDOW. That inequality is
# the actual safety invariant -- it guarantees that any blob whose position
# could possibly matter (i.e. one that ends close enough to the end of the
# fetched log to threaten the final _CONSOLE_TAIL_SIZE-char output) is
# *provably* short enough to have its `ha:////` header fall inside the
# window too, so it is always fully recognized and stripped rather than
# truncated into a headerless, unmatchable leftover. Before this bound
# existed, that guarantee was just an unverified comment ("4x margin, more
# than enough") resting on an unbounded regex -- see
# TestT22StripPipelineAnnotations::test_max_length_blob_header_at_prestrip_window_start_is_recognized
# in tests/test_jenkins_observer.py for the regression coverage. A real blob
# longer than _MAX_BLOB_LEN (not expected in practice -- Jenkins durable-task
# blobs are a serialized exception, typically well under 1KB) simply isn't
# matched at all and passes through as noise, the same documented,
# accepted trade-off as the F4 secret-abutment case below.
_PRESTRIP_WINDOW = 20000
_CONSOLE_TAIL_SIZE = 5000
_MAX_BLOB_LEN = 8192
# Explicit runtime check, not `assert` -- `assert` is compiled out entirely
# under `python -O`/`PYTHONOPTIMIZE`, which would silently drop this safety
# invariant in an optimized deployment instead of failing loudly at import
# time.
if not (_MAX_BLOB_LEN + _CONSOLE_TAIL_SIZE <= _PRESTRIP_WINDOW):
    raise ValueError(
        "_MAX_BLOB_LEN grew without a matching _PRESTRIP_WINDOW increase -- "
        "the window-start truncation guarantee no longer holds"
    )
# Byte-level (not char-level) pre-decode window for get_build_details' console-log
# fetch -- generous 4x-per-char headroom over _PRESTRIP_WINDOW so a UTF-8 log with
# multi-byte characters throughout still has at least _PRESTRIP_WINDOW *characters*
# available after decoding. _strip_pipeline_annotations applies the authoritative,
# smaller char-based bound afterward regardless.
_DECODE_WINDOW_BYTES = _PRESTRIP_WINDOW * 4

# The `ha:////` durable-task blob body is base64 ([A-Za-z0-9+/]), bounded to
# at most _MAX_BLOB_LEN chars (see above). A match is only accepted as a
# genuine ConsoleNote blob if it terminates via one of three STRUCTURAL
# signals baked into the match itself (not merely asserted via a
# zero-width lookahead, except where noted below): double `==` padding;
# single `=` padding that is ALSO immediately followed by one of the
# traditionally-safe terminators (whitespace, ANSI escape, another
# `ha:////` occurrence, or end-of-string); or a trailing ANSI escape with
# no padding at all. Each padding alternative may optionally consume a
# trailing ANSI escape too. A single optional leading ANSI wrapper (not a
# `*` quantifier -- an unbounded repeated-quantifier around a literal that
# then fails to match is quadratic on long ANSI-only runs, see
# get_build_details' pre-strip window comment) is still allowed.
#
# Bare whitespace and bare end-of-string are deliberately NOT accepted as
# unconditional termination signals (they used to be, via a lookahead
# alternative, until a MEDIUM secret-redaction-bypass finding on this exact
# regex). The base64 alphabet [A-Za-z0-9+/] is a superset of ordinary
# English letters and digits, so it cannot be distinguished from adjacent
# real text using only "where's the next whitespace/EOS" -- an unpadded,
# non-ANSI-wrapped blob immediately abutted by a real secret composed
# entirely of letters/digits (e.g. "ha:////AAAABearer sometoken123", or the
# same thing sitting at the very end of the currently-fetched log tail) let
# the greedy body class silently consume through the real word before
# downstream `_redact_secrets_in_text()`'s literal "bearer"/key-text
# matching in jenkins_observer.py ever got a chance to see it, deleting the
# secret's own redaction trigger along with the blob. ANSI escapes and
# double `==` padding are both structurally impossible to appear inside
# ordinary prose (a raw ESC byte in particular can never be part of
# English text; two literal `=` characters back-to-back never occur in a
# real single-delimiter `KEY=value` string), so either alone is accepted as
# a self-sufficient terminator with no further check.
#
# A SINGLE `=`, however, is exactly the common `KEY=value` secret delimiter
# (see jenkins_observer.py's `_SECRET_TEXT_PATTERN`, which redacts both
# "key: value" and "key=value" forms) and is therefore genuinely
# indistinguishable from real single-char base64 padding using only local
# regex context -- e.g. "ha:////AAAtoken=abc123xyz" is exactly as
# plausible a real base64 blob ending in one padding char as it is a blob
# abutting a "token=" secret delimiter. To resolve the ambiguity, a lone
# `=` is only accepted as a real terminator when a lookahead confirms one
# of the traditionally-safe delimiters immediately follows it (an ANSI
# escape, another `ha:////`, or end-of-string). If that lookahead fails,
# this alternative does not match at this position, the whole match fails,
# and the abutting secret text (including the "token=" delimiter) survives
# untouched for downstream redaction -- the same "leave ambiguous content
# alone" philosophy already applied throughout this fix. This closes the
# gap without reintroducing the F3 (adjacent-blobs) or F4 (colon-delimited
# abutment, safe because `:` is outside the base64 alphabet and so already
# can't be consumed) regressions: each blob is still matched independently
# once it has its own valid terminator, so no separate "or another
# ha:////" alternative is needed outside the single-`=` lookahead itself.
#
# Whitespace was DELIBERATELY REMOVED from that lookahead set (it used to
# be a member, until a MORE SERIOUS follow-on secret-redaction-bypass
# finding on this exact branch). Whitespace after a real `=` is not a rare,
# deliberately-constructed pattern the way an ANSI escape or a chained
# `ha:////` occurrence is -- it is the single most common, completely
# benign way a real secret is ever written in log output or config dumps
# ("KEY= value", "KEY=\nvalue"). Treating "followed by whitespace" as proof
# of genuine base64 padding was backwards: whitespace commonly follows a
# real `=` delimiter too, so its presence proves nothing about which case
# this is, and the old rule silently deleted the "token="/"password="/etc.
# delimiter along with the blob, defeating downstream redaction exactly
# like the un-lookahead-guarded version this branch was meant to fix.
#
# Accepted trade-off (narrower than the prior round's): a genuinely valid
# blob needing exactly one padding character, followed by plain whitespace
# with no ANSI wrapper (i.e. no ANSI escape, no chained blob, and not at
# end-of-string), will no longer be recognized and will show through as
# literal noise instead of being stripped. This narrows an already-narrow
# edge case further -- real Jenkins ConsoleNote blobs are near-universally
# ANSI-wrapped in practice -- and remains cosmetic-only.
_PIPELINE_ANNOTATION_RE = re.compile(
    r"(?:\x1b\[[0-9;]*m)?ha:////[A-Za-z0-9+/]{1," + str(_MAX_BLOB_LEN) + r"}"
    r"(?:==(?:\x1b\[[0-9;]*m)?"
    r"|=(?=\x1b|ha:////|$)(?:\x1b\[[0-9;]*m)?"
    r"|\x1b\[[0-9;]*m)",
)
# Real Jenkins `[Pipeline]` step-boundary markers are always full-line in
# console output (verified against production Jenkins logs). Anchoring to
# line-start (optionally after a Timestamper prefix, e.g.
# "[2026-08-31T11:23:24.854Z] ") means a marker substring that happens to
# appear mid-line in real log text (e.g. "Running [Pipeline] } leftover") is
# never mistaken for a boundary and the whole line is preserved untouched. A
# genuine line-start marker with trailing same-line text is still fully
# consumed -- real Jenkins never emits real content on the same line as one
# of these markers, so this is an accepted, documented assumption. The
# trailing `\b` after the `\w+`/`stage`/`Pipeline` alternatives (but not
# after the bare `{`/`}` literals, which aren't word characters and would
# wrongly reject a legitimate marker immediately followed by a newline)
# stops a marker substring that is merely a PREFIX of a longer real word --
# e.g. "stagecoach", "staged rollback", "End of PipelineExtra: ..." -- from
# being misidentified as a boundary and having its whole line deleted.
_PIPELINE_BOUNDARY_RE = re.compile(
    r"^(?:\[[0-9T:.\-]+Z\]\s*)?\[Pipeline\]\s*(?://\s*\w+\b|End of Pipeline\b|\{|\}|stage\b)[^\r\n]*(?:\r?\n|$)",
    re.MULTILINE,
)
_BLANK_RUN_RE = re.compile(r"(?:\r?\n){3,}")


def _strip_pipeline_annotations(text: str, *, window: int = _PRESTRIP_WINDOW) -> str:
    """Remove Jenkins pipeline flow annotations and step boundary markers.

    Bounds its own input to the last `window` chars before running the
    (attacker-influenceable-input-facing) regexes, so the safety bound lives
    with the regexes it protects instead of being the caller's responsibility
    to remember and re-derive -- see the module-level _PRESTRIP_WINDOW
    comment for the invariant this depends on.
    """
    if not text:
        return text
    if len(text) > window:
        text = text[-window:]
    text = _PIPELINE_ANNOTATION_RE.sub("", text)
    text = _PIPELINE_BOUNDARY_RE.sub("", text)
    text = _BLANK_RUN_RE.sub("\n\n", text)
    return text.strip()


@dataclass
class JobResult:
    """Single Jenkins job poll result."""
    job_name: str
    build_number: int | None = None
    result: str | None = None  # SUCCESS, FAILURE, UNSTABLE, ABORTED, None (running/missing)
    url: str = ""
    timestamp: int | None = None
    color: str = ""


@dataclass
class BuildDetails:
    """Extended build information including parameters and console tail."""
    job_name: str
    build_number: int
    result: str
    parameters: dict[str, str] = field(default_factory=dict)
    console_tail: str = ""
    url: str = ""


@dataclass
class JobRunState:
    """Lightweight job-level run state. Not a full build dump -- no console, no params."""
    building: bool = False
    in_queue: bool = False
    last_build_number: int | None = None


@dataclass
class ViewScanResult:
    """Result of scanning a Jenkins view."""
    jobs: list[JobResult]
    status_code: int | None  # HTTP status; None = transport / non-404 error


@runtime_checkable
class JenkinsPlatformPort(Protocol):
    """Port for Jenkins CI platform operations."""

    async def scan_view(self, view: str) -> ViewScanResult: ...
    async def get_job_run_state(self, job: str, *, count_failures: bool = True) -> JobRunState | None: ...
    async def get_build_details(
        self, job: str, build: int, *, count_failures: bool = True, include_console_tail: bool = True,
    ) -> BuildDetails | None: ...
    async def restart_job(self, job: str, params: dict[str, str] | None = None, *, count_failures: bool = True) -> bool: ...
    def enabled(self) -> bool: ...

    @property
    def breaker_open(self) -> bool: ...


class JenkinsAdapter:
    """httpx-based Jenkins REST adapter with a 3-strike circuit breaker
    (time-based auto-recovery, see breaker_cooldown_seconds)."""

    def __init__(
        self,
        base_url: str,
        user: str,
        token: str,
        *,
        timeout: float = 15.0,
        verify_tls: bool = False,
        breaker_threshold: int = 3,
        breaker_cooldown_seconds: float = 300.0,
    ):
        self._base_url = base_url.rstrip("/")
        self._auth = httpx.BasicAuth(user, token)
        self._timeout = timeout
        self._verify_tls = verify_tls
        self._breaker_threshold = breaker_threshold
        self._breaker_cooldown_seconds = breaker_cooldown_seconds
        self._consecutive_failures = 0
        self._breaker_latched = False
        self._breaker_latched_at: float | None = None
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                auth=self._auth,
                timeout=self._timeout,
                verify=self._verify_tls,
            )
        return self._client

    def _maybe_reset_breaker(self) -> None:
        """Auto-recovery: unlatch once breaker_cooldown_seconds has elapsed since the
        latch tripped, giving Jenkins a fresh attempt instead of requiring a pod restart.

        Only resets latches recorded via _record_failure (breaker_latched_at is set) --
        a latch set directly by a caller/test with no timestamp is left untouched.
        """
        if (
            self._breaker_latched
            and self._breaker_latched_at is not None
            and time.time() - self._breaker_latched_at >= self._breaker_cooldown_seconds
        ):
            logger.warning(
                "JENKINS_BREAKER_RECOVERY: cooldown (%.0fs) elapsed, unlatching for retry",
                self._breaker_cooldown_seconds,
            )
            self._breaker_latched = False
            self._breaker_latched_at = None
            self._consecutive_failures = 0

    @property
    def breaker_open(self) -> bool:
        self._maybe_reset_breaker()
        return self._breaker_latched

    def enabled(self) -> bool:
        self._maybe_reset_breaker()
        return bool(self._base_url) and not self._breaker_latched

    def _record_success(self) -> None:
        self._consecutive_failures = 0

    def _record_failure(self, status_code: int | None = None) -> None:
        """Record a failure. 401/403 excluded from strike count."""
        if status_code in (401, 403):
            logger.warning("Jenkins auth error (%s) — excluded from breaker strike count", status_code)
            return
        self._consecutive_failures += 1
        if self._consecutive_failures >= self._breaker_threshold:
            self._breaker_latched = True
            self._breaker_latched_at = time.time()
            logger.error(
                "JENKINS_BREAKER_OPEN: %d consecutive failures — adapter disabled for %.0fs",
                self._consecutive_failures, self._breaker_cooldown_seconds,
            )

    async def _request(
        self, method: str, path: str, *, count_failures: bool = True,
        pass_through_404: bool = False, **kwargs,
    ) -> httpx.Response | None:
        """Execute HTTP request with circuit breaker guard.

        count_failures=False is used for best-effort fetches (e.g. console-log tail)
        whose failures are unrelated to core Jenkins reachability and must not trip
        the breaker on their own.

        pass_through_404=True returns the raw 404 response to the caller instead of
        swallowing it. Used by pattern-based polling where 404 means "job does not exist"
        (a valid, expected signal) rather than an error -- also counts as a reachability
        success (Jenkins answered), so it resets the failure counter like any 2xx.

        count_failures=False ALSO returns the raw response for 401/403/5xx/other 4xx
        (instead of None) so a caller that wants to do its own outcome accounting --
        e.g. a wave-scoped aggregate across multiple concurrent requests -- can classify
        each attempt itself. Transport-level failures (timeout/connect/invalid-URL) still
        have no response object and always return None regardless of this flag.
        """
        self._maybe_reset_breaker()
        if self._breaker_latched:
            return None
        try:
            client = await self._get_client()
            url = f"{self._base_url}{path}"
            resp = await client.request(method, url, **kwargs)
            if resp.status_code in (401, 403):
                if count_failures:
                    self._record_failure(resp.status_code)
                    return None
                return resp
            if resp.status_code >= 500:
                if count_failures:
                    self._record_failure(resp.status_code)
                    return None
                return resp
            if pass_through_404 and resp.status_code == 404:
                self._record_success()
                return resp
            if resp.status_code >= 400:
                logger.warning("Jenkins %s %s returned %d — client error, not recording as breaker strike",
                               method, path, resp.status_code)
                return None if count_failures else resp
            self._record_success()
            return resp
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError, httpx.InvalidURL) as exc:
            logger.warning("Jenkins request failed: %s %s — %s", method, path, exc)
            if count_failures:
                self._record_failure(None)
            return None

    async def scan_view(self, view: str) -> ViewScanResult:
        """Scan a Jenkins view for all jobs with their last build status.

        Returns ViewScanResult with HTTP status_code for caller health tracking:
        - 200: jobs parsed from view
        - 404: view does not exist (valid signal for observer health)
        - None: transport error or breaker open (no HTTP was made)
        """
        if self.breaker_open:
            return ViewScanResult([], None)

        encoded_view = urllib.parse.quote(view, safe="")
        path = (
            f"/view/{encoded_view}/api/json"
            f"?tree=jobs[name,color,lastBuild[number,result,url,timestamp]]"
        )
        resp = await self._request("GET", path, pass_through_404=True)
        if resp is None:
            return ViewScanResult([], None)
        if resp.status_code == 404:
            return ViewScanResult([], 404)

        try:
            data = resp.json()
        except Exception:
            logger.warning("Jenkins view %s returned malformed JSON", view)
            return ViewScanResult([], None)

        jobs: list[JobResult] = []
        for entry in data.get("jobs", []):
            if not isinstance(entry, dict):
                continue
            name = entry.get("name", "")
            if not name:
                continue
            color = entry.get("color", "")
            lb = entry.get("lastBuild")
            if lb and isinstance(lb, dict):
                jobs.append(JobResult(
                    job_name=name,
                    build_number=lb.get("number"),
                    result=lb.get("result"),
                    url=lb.get("url", ""),
                    timestamp=lb.get("timestamp"),
                    color=color,
                ))
            else:
                jobs.append(JobResult(
                    job_name=name,
                    color=color,
                ))
        return ViewScanResult(jobs, 200)

    async def get_job_run_state(self, job: str, *, count_failures: bool = True) -> JobRunState | None:
        """Fetch lightweight job-level state without console or parameter details."""
        path = (
            f"/job/{urllib.parse.quote(job, safe='')}/api/json"
            f"?tree=color,inQueue,lastBuild[number,result,building]"
        )
        resp = await self._request("GET", path, count_failures=count_failures)
        if not resp or resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        if not isinstance(data, dict):
            return None

        in_queue = bool(data.get("inQueue"))
        building = False
        last_build_number: int | None = None
        last_build = data.get("lastBuild")
        if isinstance(last_build, dict):
            building = bool(last_build.get("building"))
            raw_number = last_build.get("number")
            last_build_number = raw_number if isinstance(raw_number, int) else None
        if str(data.get("color") or "").endswith("_anime"):
            building = True

        return JobRunState(
            building=building,
            in_queue=in_queue,
            last_build_number=last_build_number,
        )

    async def get_build_details(
        self, job: str, build: int, *, count_failures: bool = True, include_console_tail: bool = True,
    ) -> BuildDetails | None:
        """Fetch build details including parameters and, optionally, console tail.

        include_console_tail=False skips the second (console-log) HTTP call for
        callers that only need `.parameters` -- e.g. the retrigger flow, which is
        wall-clock-budgeted and has no use for console output.
        """
        path = f"/job/{urllib.parse.quote(job, safe='')}/{build}/api/json?tree=result,actions[parameters[name,value]],url"
        resp = await self._request("GET", path, count_failures=count_failures)
        if not resp or resp.status_code != 200:
            return None
        try:
            data = resp.json()
        except Exception:
            return None
        params: dict[str, str] = {}
        for action in data.get("actions", []):
            for p in action.get("parameters", []):
                if p.get("name"):
                    params[p["name"]] = str(p.get("value", ""))

        console_tail = ""
        if include_console_tail:
            # Best-effort: an oversized/slow console log must not trip the breaker on its own.
            tail_resp = await self._request(
                "GET",
                f"/job/{urllib.parse.quote(job, safe='')}/{build}/logText/progressiveText?start=0",
                count_failures=False,
            )
            if tail_resp and tail_resp.status_code == 200:
                # `.text` would decode the FULL response body up front --
                # synchronous cost that scales with the true (potentially
                # multi-MB, attacker-influenceable) log size, on the Brain's
                # shared asyncio event loop, before a single byte of it is
                # ever used. Jenkins console logs can be arbitrarily large;
                # since only the tail ends up in console_tail, slice the raw
                # BYTES down to a generous pre-decode window first and decode
                # only that -- decode cost is now bounded regardless of
                # actual log size. A slice boundary can land mid-codepoint;
                # errors="replace" swaps at most one leading char for U+FFFD,
                # which is discarded anyway once _strip_pipeline_annotations
                # applies its own (smaller, char-based) _PRESTRIP_WINDOW bound.
                raw_bytes = tail_resp.content
                if len(raw_bytes) > _DECODE_WINDOW_BYTES:
                    raw_bytes = raw_bytes[-_DECODE_WINDOW_BYTES:]
                try:
                    raw = raw_bytes.decode(tail_resp.encoding or "utf-8", errors="replace")
                except LookupError:
                    # httpx-derived charset name (e.g. from a malformed/unusual
                    # Content-Type header) is not a codec Python recognizes.
                    # This is a best-effort log-tail fetch -- fall back to utf-8
                    # rather than letting an uncaught LookupError escape this path.
                    raw = raw_bytes.decode("utf-8", errors="replace")
                text = _strip_pipeline_annotations(raw)
                console_tail = text[-_CONSOLE_TAIL_SIZE:] if len(text) > _CONSOLE_TAIL_SIZE else text

        return BuildDetails(
            job_name=job,
            build_number=build,
            result=data.get("result", "UNKNOWN"),
            parameters=params,
            console_tail=console_tail,
            url=data.get("url", ""),
        )

    async def restart_job(self, job: str, params: dict[str, str] | None = None, *, count_failures: bool = True) -> bool:
        """Trigger a new build for a job. Returns True on success."""
        safe_job = urllib.parse.quote(job, safe="")
        if params:
            path = f"/job/{safe_job}/buildWithParameters"
            resp = await self._request("POST", path, data=params, count_failures=count_failures)
        else:
            path = f"/job/{safe_job}/build"
            resp = await self._request("POST", path, count_failures=count_failures)
        return resp is not None and resp.status_code in (200, 201, 302)

    async def close(self) -> None:
        """Close the underlying httpx client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
