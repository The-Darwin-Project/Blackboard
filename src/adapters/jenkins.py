# BlackBoard/src/adapters/jenkins.py
# @ai-rules:
# 1. [Pattern]: Hexagonal adapter -- httpx-based Jenkins REST API client. No domain logic.
# 2. [Constraint]: Auth via Basic (user:token). verify=False for self-signed certs.
# 3. [Pattern]: 3-strike permanent-latch circuit breaker (mirrors headhunter.py:271-309).
#    401/403 excluded from strike count. No auto-recovery — latch until pod restart.
# 4. [Contract]: breaker_open property for FlowCollector observability.
# 5. [Constraint]: All org-specific values from constructor args (env vars resolved by caller).
"""
Jenkins CI platform adapter -- poll jobs, get build details, restart.

Used by JenkinsObserver for CI gating reconciliation.
"""
from __future__ import annotations

import logging
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


@dataclass
class BuildDetails:
    """Extended build information including parameters and console tail."""
    job_name: str
    build_number: int
    result: str
    parameters: dict[str, str] = field(default_factory=dict)
    console_tail: str = ""
    url: str = ""


@runtime_checkable
class JenkinsPlatformPort(Protocol):
    """Port for Jenkins CI platform operations."""

    async def poll_smoke_jobs(self, version: str) -> list[JobResult]: ...
    async def poll_gating_jobs(self, version: str) -> list[JobResult]: ...
    async def get_build_details(self, job: str, build: int) -> BuildDetails | None: ...
    async def restart_job(self, job: str, params: dict[str, str] | None = None) -> bool: ...
    def enabled(self) -> bool: ...

    @property
    def breaker_open(self) -> bool: ...


class JenkinsAdapter:
    """httpx-based Jenkins REST adapter with 3-strike permanent-latch circuit breaker."""

    def __init__(
        self,
        base_url: str,
        user: str,
        token: str,
        *,
        timeout: float = 15.0,
        verify_tls: bool = False,
        breaker_threshold: int = 3,
    ):
        self._base_url = base_url.rstrip("/")
        self._auth = httpx.BasicAuth(user, token)
        self._timeout = timeout
        self._verify_tls = verify_tls
        self._breaker_threshold = breaker_threshold
        self._consecutive_failures = 0
        self._breaker_latched = False
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                auth=self._auth,
                timeout=self._timeout,
                verify=self._verify_tls,
            )
        return self._client

    @property
    def breaker_open(self) -> bool:
        return self._breaker_latched

    def enabled(self) -> bool:
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
            logger.error(
                "JENKINS_BREAKER_OPEN: %d consecutive failures — adapter permanently disabled until pod restart",
                self._consecutive_failures,
            )

    async def _request(self, method: str, path: str, **kwargs) -> httpx.Response | None:
        """Execute HTTP request with circuit breaker guard."""
        if self._breaker_latched:
            return None
        try:
            client = await self._get_client()
            url = f"{self._base_url}{path}"
            resp = await client.request(method, url, **kwargs)
            if resp.status_code in (401, 403):
                self._record_failure(resp.status_code)
                return None
            if resp.status_code >= 500:
                self._record_failure(resp.status_code)
                return None
            if resp.status_code >= 400:
                logger.warning("Jenkins %s %s returned %d — client error, not recording as breaker strike",
                               method, path, resp.status_code)
                return None
            self._record_success()
            return resp
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError) as exc:
            logger.warning("Jenkins request failed: %s %s — %s", method, path, exc)
            self._record_failure(None)
            return None

    async def poll_smoke_jobs(self, version: str) -> list[JobResult]:
        """Poll smoke-test jobs for a CNV version."""
        return await self._poll_view_jobs(version, "smoke")

    async def poll_gating_jobs(self, version: str) -> list[JobResult]:
        """Poll gating jobs for a CNV version."""
        return await self._poll_view_jobs(version, "gating")

    async def _poll_view_jobs(self, version: str, category: str) -> list[JobResult]:
        """Poll jobs by constructing the Jenkins API path for the version view."""
        path = f"/job/cnv-{version.replace('.', '-')}-{category}/api/json?tree=jobs[name,lastBuild[number,result,url]]"
        resp = await self._request("GET", path)
        if not resp or resp.status_code != 200:
            return []
        try:
            data = resp.json()
        except Exception:
            return []
        results: list[JobResult] = []
        for job in data.get("jobs", []):
            lb = job.get("lastBuild") or {}
            results.append(JobResult(
                job_name=job.get("name", ""),
                build_number=lb.get("number"),
                result=lb.get("result"),
                url=lb.get("url", ""),
            ))
        return results

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
        tail_resp = await self._request("GET", f"/job/{job}/{build}/logText/progressiveText?start=0")
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
