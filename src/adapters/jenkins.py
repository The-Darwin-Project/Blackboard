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
"""
Jenkins CI platform adapter -- poll jobs, get build details, restart.

Used by JenkinsObserver for CI gating reconciliation.
"""
from __future__ import annotations

import logging
import time
import urllib.parse
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

import httpx

logger = logging.getLogger(__name__)


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
class ViewScanResult:
    """Result of scanning a Jenkins view."""
    jobs: list[JobResult]
    status_code: int | None  # HTTP status; None = transport / non-404 error


@runtime_checkable
class JenkinsPlatformPort(Protocol):
    """Port for Jenkins CI platform operations."""

    async def scan_view(self, view: str) -> ViewScanResult: ...
    async def get_build_details(self, job: str, build: int) -> BuildDetails | None: ...
    async def restart_job(self, job: str, params: dict[str, str] | None = None) -> bool: ...
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

    async def get_build_details(self, job: str, build: int) -> BuildDetails | None:
        """Fetch build details including parameters and console tail."""
        path = f"/job/{job}/{build}/api/json?tree=result,actions[parameters[name,value]],url"
        resp = await self._request("GET", path)
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
        # Best-effort: an oversized/slow console log must not trip the breaker on its own.
        tail_resp = await self._request(
            "GET", f"/job/{job}/{build}/logText/progressiveText?start=0", count_failures=False
        )
        if tail_resp and tail_resp.status_code == 200:
            text = tail_resp.text
            console_tail = text[-5000:] if len(text) > 5000 else text

        return BuildDetails(
            job_name=job,
            build_number=build,
            result=data.get("result", "UNKNOWN"),
            parameters=params,
            console_tail=console_tail,
            url=data.get("url", ""),
        )

    async def restart_job(self, job: str, params: dict[str, str] | None = None) -> bool:
        """Trigger a new build for a job. Returns True on success."""
        if params:
            path = f"/job/{job}/buildWithParameters"
            resp = await self._request("POST", path, params=params)
        else:
            path = f"/job/{job}/build"
            resp = await self._request("POST", path)
        return resp is not None and resp.status_code in (200, 201, 302)

    async def close(self) -> None:
        """Close the underlying httpx client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None
