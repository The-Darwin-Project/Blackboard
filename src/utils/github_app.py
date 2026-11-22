# BlackBoard/src/utils/github_app.py
# @ai-rules:
# 1. [Constraint]: GitHubAppAuth.get_token() is thread-safe (threading.Lock).
# 2. [Pattern]: AsyncGitHubClient wraps blocking token refresh via asyncio.to_thread().
# 3. [Pattern]: AsyncGitHubClient uses persistent httpx.AsyncClient; call close() on shutdown.
# 4. [Pattern]: Rate-limit warning at <100 remaining; 2xx backoff on remaining=0 / Retry-After
#    (capped at 60s, opt-out via backoff=False); 304 cache hits and non-2xx responses never sleep.
# 5. [Pattern]: get_github_auth() is the singleton accessor — all consumers use it, not GitHubAppAuth() directly.
# 6. [Pattern]: get/post/delete share the same auth header pattern. delete() calls raise_for_status().
# 7. [Pattern]: MultiInstallationManager owns all per-installation GitHubAppAuth/AsyncGitHubClient
#    instances + the repo->installation_id cache (shared singleton via get_installation_manager(),
#    borrowed by headhunter_github.py and utils/vcs_approval.py; sole teardown owner is main.py
#    lifespan via close_installation_manager(), guarded by _shutting_down).
# 8. [Constraint]: MultiInstallationManager discovery uses the App JWT (installation_id=None on
#    GitHubAppAuth is invalid for GET /app/installations -- needs get_app_jwt() from any instance
#    or a dedicated JWT-only helper). Discovery failure serves stale cache; raises only cold-start.
"""
GitHub App Authentication for GitOps operations.

Generates installation access tokens from GitHub App credentials
for authenticated git operations (clone, push). Also provides an
async HTTP client for GitHub REST API calls.
"""
import asyncio
from collections import OrderedDict
import inspect
import json
import logging
import os
import re
import threading
import time
import urllib.parse
from pathlib import Path
from typing import Any, Optional

import httpx
import jwt
import requests

from .tls import resolve_ca_bundle

logger = logging.getLogger(__name__)

_ETAG_EXCLUDED_RE = re.compile(r"/collaborators/[^/]+/permission(?:\?|$|/)", re.IGNORECASE)
_ETAG_STRIP_HEADERS = frozenset({"content-encoding", "content-length", "transfer-encoding"})
_LINK_ENTRY_RE = re.compile(r"<([^>]+)>\s*([^<]*)")
_LINK_REL_NEXT_RE = re.compile(r'(?:^|;\s*)rel\s*=\s*(?:"next"|next)(?:\s*;|$)', re.IGNORECASE)
_MAX_RATE_LIMIT_SLEEP_S = 60.0
_DEFAULT_MAX_PAGES = 20
_DEFAULT_ETAG_MAX_ENTRIES = 256
_DEFAULT_ETAG_MAX_ENTRY_BYTES = 512 * 1024
_DEFAULT_ETAG_MAX_TOTAL_BYTES = 16 * 1024 * 1024


def _safe_parse_int(value: Any) -> Optional[int]:
    """Parse an HTTP header value as int, returning None for missing/non-int values."""
    if not isinstance(value, (str, int)) or isinstance(value, bool):
        return None
    try:
        return int(str(value).strip())
    except (ValueError, TypeError):
        return None


def parse_github_next_link(link_header: Any) -> Optional[str]:
    """Extract and host-pin the rel="next" URL from a GitHub Link header.

    Parses RFC 8288 <...> entries without splitting inside URLs (preserving
    comma-separated query values like labels=a,b). Only permits canonical
    https://api.github.com (default port None/443) with zero userinfo,
    no ASCII control/whitespace/backslash characters, and no fragment.
    """
    if not isinstance(link_header, str) or not link_header.strip():
        return None
    for m in _LINK_ENTRY_RE.finditer(link_header):
        url = m.group(1)
        params = (m.group(2) or "").rstrip(", \t")
        if not _LINK_REL_NEXT_RE.search(params):
            continue
        if not url or "\\" in url or any(ord(c) <= 0x20 or ord(c) == 0x7F for c in url):
            logger.warning("Rejected malformed/unsafe GitHub Link next URL")
            return None
        try:
            parsed = urllib.parse.urlsplit(url)
            port = parsed.port
        except ValueError:
            logger.warning("Rejected malformed GitHub Link next URL")
            return None
        if (
            parsed.scheme != "https"
            or (parsed.hostname or "").lower() != "api.github.com"
            or port not in (None, 443)
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment != ""
            or (parsed.path and not parsed.path.startswith("/"))
        ):
            logger.warning(
                "Rejected untrusted GitHub Link next URL: host=%s scheme=%s",
                parsed.hostname,
                parsed.scheme,
            )
            return None
        return urllib.parse.urlunsplit(
            ("https", "api.github.com", parsed.path or "/", parsed.query, "")
        )
    return None


async def _handle_rate_limit(headers: Any, *, sleep: bool = True) -> None:
    """Inspect GitHub rate-limit headers safely and optionally back off when exhausted."""
    if headers is None or not hasattr(headers, "get"):
        return
    retry_after = _safe_parse_int(headers.get("Retry-After"))
    if retry_after is not None and retry_after > 0:
        delay = min(float(retry_after), _MAX_RATE_LIMIT_SLEEP_S)
        if sleep:
            logger.warning("GitHub Retry-After header received: backing off %.1fs", delay)
            await asyncio.sleep(delay)
        else:
            logger.warning("GitHub Retry-After header received (%ds; non-blocking)", retry_after)
        return

    remaining = _safe_parse_int(headers.get("X-RateLimit-Remaining"))
    if remaining is None:
        return
    if remaining <= 0:
        reset_ts = _safe_parse_int(headers.get("X-RateLimit-Reset"))
        if reset_ts is not None:
            delay = max(1.0, min(float(reset_ts - time.time()), _MAX_RATE_LIMIT_SLEEP_S))
        else:
            delay = 5.0
        if sleep:
            logger.warning("GitHub rate limit exhausted (0 remaining): backing off %.1fs", delay)
            await asyncio.sleep(delay)
        else:
            logger.warning(
                "GitHub rate limit exhausted (0 remaining; non-blocking, reset in %.1fs)", delay
            )
    elif remaining < 100:
        logger.warning("GitHub rate limit low: %d remaining", remaining)


async def _paginate_github_get(
    get_fn: Any,
    path: str,
    params: dict | None = None,
    *,
    max_pages: int = _DEFAULT_MAX_PAGES,
    use_etag: bool = False,
    backoff: bool = True,
) -> list[httpx.Response]:
    """Follow host-pinned Link: rel='next' headers up to max_pages."""
    try:
        sig_params = inspect.signature(get_fn).parameters
        accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig_params.values())
        pass_etag = accepts_var_kw or "use_etag" in sig_params
        pass_backoff = accepts_var_kw or "backoff" in sig_params
    except (TypeError, ValueError):
        pass_etag = False
        pass_backoff = False

    responses: list[httpx.Response] = []
    cur_path = path
    cur_params: dict | None = dict(params) if params else None
    for _ in range(max(1, max_pages)):
        call_kwargs: dict[str, Any] = {"params": cur_params}
        if pass_etag:
            call_kwargs["use_etag"] = use_etag
        if pass_backoff:
            call_kwargs["backoff"] = backoff
        resp = await get_fn(cur_path, **call_kwargs)
        responses.append(resp)
        link_hdr = (
            resp.headers.get("Link")
            if hasattr(resp, "headers") and resp.headers is not None
            else None
        )
        next_url = parse_github_next_link(link_hdr)
        if not next_url:
            break
        parsed = urllib.parse.urlsplit(next_url)
        cur_path = parsed.path or "/"
        cur_params = dict(urllib.parse.parse_qsl(parsed.query)) if parsed.query else None
    return responses

# GitHub App configuration from environment/secrets
GITHUB_APP_ID = os.getenv("GITHUB_APP_ID")
GITHUB_INSTALLATION_ID = os.getenv("GITHUB_INSTALLATION_ID")
GITHUB_PRIVATE_KEY_PATH = os.getenv("GITHUB_PRIVATE_KEY_PATH", "/secrets/github")


def _find_pem_file(search_path: str) -> str:
    """Find the .pem private key file in a directory or return as-is if it's a file."""
    p = Path(search_path)
    if p.is_file():
        return str(p)
    if p.is_dir():
        pem_files = list(p.glob("*.pem"))
        if pem_files:
            return str(pem_files[0])
    raise ValueError(f"No .pem private key found at {search_path}")


class GitHubAppAuth:
    """
    GitHub App authentication handler.
    
    Generates short-lived installation access tokens for git operations.
    Tokens are valid for 1 hour but we refresh at 50 minutes.
    """
    
    TOKEN_REFRESH_BUFFER_SECONDS = 600  # Refresh 10 min before expiry
    
    def __init__(
        self,
        app_id: Optional[str] = None,
        installation_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
    ):
        self.app_id = app_id or GITHUB_APP_ID
        self.installation_id = installation_id or GITHUB_INSTALLATION_ID
        
        self._token: Optional[str] = None
        self._token_expires_at: float = 0
        self._lock = threading.Lock()
        
        # Validate configuration. installation_id is intentionally NOT required here --
        # App-level JWT calls (get_app_jwt, discover_installations) need only app_id +
        # private_key. installation_id is validated lazily, only when an installation
        # token is actually requested (get_token / _request_installation_token).
        if not self.app_id:
            raise ValueError("GITHUB_APP_ID not configured")
        # Discover .pem file (path may be a directory or a direct file)
        self.private_key_path = _find_pem_file(
            private_key_path or GITHUB_PRIVATE_KEY_PATH
        )
    
    def _load_private_key(self) -> str:
        """Load the GitHub App private key from file."""
        with open(self.private_key_path, "r") as f:
            return f.read()
    
    def _create_jwt(self) -> str:
        """
        Create a JWT for GitHub App authentication.
        
        The JWT is signed with the app's private key and used to
        request installation access tokens.
        """
        now = int(time.time())
        payload = {
            "iat": now - 60,  # Issued 60 seconds ago (clock skew buffer)
            "exp": now + 540,  # Expires in 9 minutes (max 10 min)
            "iss": self.app_id,
        }
        
        private_key = self._load_private_key()
        return jwt.encode(payload, private_key, algorithm="RS256")
    
    def _request_installation_token(self) -> dict:
        """
        Request an installation access token from GitHub.
        
        Returns the token response including:
        - token: The access token
        - expires_at: ISO timestamp when token expires
        """
        if not self.installation_id:
            raise ValueError("GITHUB_INSTALLATION_ID not configured")
        jwt_token = self._create_jwt()
        
        url = f"https://api.github.com/app/installations/{self.installation_id}/access_tokens"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {jwt_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        
        logger.info(f"Requesting installation token for installation {self.installation_id}")
        
        response = requests.post(
            url, headers=headers, timeout=30, verify=resolve_ca_bundle(), allow_redirects=False,
        )
        response.raise_for_status()
        status = getattr(response, "status_code", None)
        if isinstance(status, int) and not (200 <= status < 300):
            raise requests.HTTPError(
                f"Unexpected non-2xx status {status} requesting installation token",
                response=response,
            )

        return response.json()
    
    def get_token(self) -> str:
        """
        Get a valid installation access token.
        
        Returns cached token if still valid, otherwise requests a new one.
        Thread-safe: concurrent callers share one refresh cycle.
        """
        with self._lock:
            now = time.time()
            
            if self._token and now < (self._token_expires_at - self.TOKEN_REFRESH_BUFFER_SECONDS):
                logger.debug("Using cached installation token")
                return self._token
            
            logger.info("Requesting new GitHub installation token")
            token_response = self._request_installation_token()
            
            self._token = token_response["token"]
            expires_at_str = token_response["expires_at"]
            from datetime import datetime
            expires_at_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
            self._token_expires_at = expires_at_dt.timestamp()
            
            logger.info(f"Got new token, expires at {expires_at_str}")
            return self._token
    
    def get_app_jwt(self) -> str:
        """Get a short-lived JWT for GitHub App-level API calls (e.g., GET /app).

        Valid for ~10 minutes. Use get_token() for installation-level access.
        """
        return self._create_jwt()

    def resolve_installation_for_repo(self, repo: str) -> str:
        """Discover the installation ID that covers a given repo (sync, App JWT).

        Calls GET /repos/{owner}/{repo}/installation with the App JWT.
        Caches the result on self.installation_id so subsequent get_token()
        calls use it without re-discovery.

        Args:
            repo: Repository in "owner/repo" format.

        Returns:
            The installation ID as a string.

        Raises:
            ValueError: If the app is not installed on the repo.
        """
        jwt_token = self._create_jwt()
        url = f"https://api.github.com/repos/{repo}/installation"
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {jwt_token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = requests.get(
            url, headers=headers, timeout=30, verify=resolve_ca_bundle(), allow_redirects=False,
        )
        resp.raise_for_status()
        status = getattr(resp, "status_code", None)
        if isinstance(status, int) and not (200 <= status < 300):
            raise requests.HTTPError(
                f"Unexpected non-2xx status {status} resolving installation for {repo}",
                response=resp,
            )
        inst_id = str(resp.json()["id"])
        self.installation_id = inst_id
        logger.info("Resolved installation_id=%s for repo %s", inst_id, repo)
        return inst_id

    def get_clone_url(self, repo: str) -> str:
        """
        Get an authenticated clone URL for a repository.
        
        Args:
            repo: Repository in format "owner/repo" (e.g., "The-Darwin-Project/gitops")
        
        Returns:
            Authenticated HTTPS URL: https://x-access-token:<token>@github.com/owner/repo.git
        """
        token = self.get_token()
        return f"https://x-access-token:{token}@github.com/{repo}.git"
    
    def configure_git_credentials(self, repo_path: str, repo: str) -> None:
        """
        Configure git credentials for a repository.
        
        Sets up the credential helper to use the GitHub App token.
        This allows subsequent git push operations to authenticate.
        
        Uses /tmp/git-creds/credentials which is shared with init container
        via emptyDir volume.
        
        Args:
            repo_path: Path to the local git repository
            repo: Repository in format "owner/repo"
        """
        import subprocess
        
        token = self.get_token()
        
        # Use shared credential path (same as init container)
        credentials_dir = Path("/tmp/git-creds")
        credentials_path = credentials_dir / "credentials"
        
        # Ensure directory exists
        credentials_dir.mkdir(parents=True, exist_ok=True)
        
        # Configure credential helper to use shared credential store
        subprocess.run(
            ["git", "config", "credential.helper", f"store --file={credentials_path}"],
            cwd=repo_path,
            check=True,
        )
        
        # Write fresh credentials to git credential store
        credentials = f"https://x-access-token:{token}@github.com\n"
        
        with open(credentials_path, "w") as f:
            f.write(credentials)
        
        # Set the remote URL with token
        remote_url = self.get_clone_url(repo)
        subprocess.run(
            ["git", "remote", "set-url", "origin", remote_url],
            cwd=repo_path,
            check=True,
        )
        
        logger.info(f"Configured git credentials for {repo}")


# Singleton instance
_github_auth: Optional[GitHubAppAuth] = None


def get_github_auth() -> GitHubAppAuth:
    """Get the GitHub App auth singleton."""
    global _github_auth
    if _github_auth is None:
        _github_auth = GitHubAppAuth()
    return _github_auth


class AsyncGitHubClient:
    """Async wrapper for GitHub App REST API calls via httpx.

    Token refresh runs in a thread (blocking JWT + HTTP) to avoid
    event loop starvation. Uses a persistent httpx.AsyncClient to
    reuse TCP connections across requests.
    """

    def __init__(
        self,
        auth: GitHubAppAuth,
        *,
        etag_max_entries: int = _DEFAULT_ETAG_MAX_ENTRIES,
        etag_max_entry_bytes: int = _DEFAULT_ETAG_MAX_ENTRY_BYTES,
        etag_max_total_bytes: int = _DEFAULT_ETAG_MAX_TOTAL_BYTES,
    ):
        self._auth = auth
        self._client = httpx.AsyncClient(
            timeout=30, verify=resolve_ca_bundle(), follow_redirects=False,
        )
        # Per-client bounded LRU ETag cache: (path, sorted_params) -> (etag, raw_bytes, headers_dict)
        self._etag_cache: OrderedDict[
            tuple[str, tuple[tuple[str, str], ...]],
            tuple[str, bytes, dict[str, str]],
        ] = OrderedDict()
        self._etag_max_entries = max(1, etag_max_entries)
        self._etag_max_entry_bytes = max(1, etag_max_entry_bytes)
        self._etag_max_total_bytes = max(1, etag_max_total_bytes)
        self._etag_total_bytes: int = 0

    async def close(self) -> None:
        """Shut down the persistent HTTP client."""
        self._etag_cache.clear()
        self._etag_total_bytes = 0
        await self._client.aclose()

    async def get_token(self) -> str:
        return await asyncio.to_thread(self._auth.get_token)

    @staticmethod
    def _validate_path(path: str) -> None:
        if not isinstance(path, str) or not path.startswith("/"):
            raise ValueError(f"GitHub API path must start with '/': {path!r}")

    @staticmethod
    def _etag_cache_key(path: str, params: dict | None) -> tuple[str, tuple[tuple[str, str], ...]]:
        norm_params = tuple(sorted((str(k), str(v)) for k, v in (params or {}).items()))
        return (path, norm_params)

    def _store_etag_entry(
        self,
        cache_key: tuple[str, tuple[tuple[str, str], ...]],
        etag: str,
        raw_bytes: bytes,
        sanitized_headers: dict[str, str],
    ) -> None:
        entry_size = len(raw_bytes)
        if entry_size > self._etag_max_entry_bytes or entry_size > self._etag_max_total_bytes:
            return
        existing = self._etag_cache.pop(cache_key, None)
        if existing is not None:
            self._etag_total_bytes = max(0, self._etag_total_bytes - len(existing[1]))
        self._etag_cache[cache_key] = (etag, raw_bytes, sanitized_headers)
        self._etag_total_bytes += entry_size
        while (
            len(self._etag_cache) > self._etag_max_entries
            or self._etag_total_bytes > self._etag_max_total_bytes
        ) and self._etag_cache:
            _, (_, evicted_bytes, _) = self._etag_cache.popitem(last=False)
            self._etag_total_bytes = max(0, self._etag_total_bytes - len(evicted_bytes))

    async def get(
        self,
        path: str,
        params: dict | None = None,
        *,
        use_etag: bool = False,
        backoff: bool = True,
    ) -> httpx.Response:
        self._validate_path(path)
        token = await self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        etag_eligible = bool(use_etag) and not bool(_ETAG_EXCLUDED_RE.search(path))
        cache_key = self._etag_cache_key(path, params) if etag_eligible else None
        cached_entry: tuple[str, bytes, dict[str, str]] | None = None
        if cache_key is not None and cache_key in self._etag_cache:
            self._etag_cache.move_to_end(cache_key)
            cached_entry = self._etag_cache[cache_key]
            headers["If-None-Match"] = cached_entry[0]

        resp = await self._client.get(
            f"https://api.github.com{path}", headers=headers, params=params,
        )

        # 304 Not Modified: return cached decompressed body immediately (never sleep on 304).
        if cache_key is not None and resp.status_code == 304 and cached_entry is not None:
            etag_val, raw_bytes, cached_headers = cached_entry
            if cache_key in self._etag_cache:
                self._etag_cache.move_to_end(cache_key)
            else:
                self._store_etag_entry(cache_key, etag_val, raw_bytes, cached_headers)
            raw_req = getattr(resp, "_request", None)
            req = raw_req if isinstance(raw_req, httpx.Request) else None
            return httpx.Response(
                200,
                content=bytes(raw_bytes),
                headers=dict(cached_headers),
                request=req,
            )

        # Non-2xx: log rate-limit warning non-blockingly and fail fast (never sleep before raise).
        if not (200 <= resp.status_code < 300):
            await _handle_rate_limit(resp.headers, sleep=False)
            resp.raise_for_status()

        await _handle_rate_limit(resp.headers, sleep=backoff)

        if cache_key is not None and resp.status_code == 200:
            etag = resp.headers.get("ETag") or resp.headers.get("etag")
            if isinstance(etag, str) and etag:
                sanitized_headers = {
                    k: v
                    for k, v in resp.headers.items()
                    if k.lower() not in _ETAG_STRIP_HEADERS
                }
                self._store_etag_entry(cache_key, etag, bytes(resp.content), sanitized_headers)

        return resp

    async def get_paginated(
        self,
        path: str,
        params: dict | None = None,
        *,
        max_pages: int = _DEFAULT_MAX_PAGES,
        use_etag: bool = False,
        backoff: bool = True,
    ) -> list[httpx.Response]:
        """Follow host-pinned Link: rel='next' headers up to max_pages."""
        self._validate_path(path)
        return await _paginate_github_get(
            self.get,
            path,
            params=params,
            max_pages=max_pages,
            use_etag=use_etag,
            backoff=backoff,
        )

    async def post(self, path: str, json: dict | None = None) -> httpx.Response:
        self._validate_path(path)
        token = await self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = await self._client.post(
            f"https://api.github.com{path}", headers=headers, json=json,
        )
        await _handle_rate_limit(resp.headers, sleep=False)
        resp.raise_for_status()
        return resp

    async def delete(self, path: str) -> httpx.Response:
        self._validate_path(path)
        token = await self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = await self._client.delete(
            f"https://api.github.com{path}", headers=headers,
        )
        await _handle_rate_limit(resp.headers, sleep=False)
        resp.raise_for_status()
        return resp


class MultiInstallationManager:
    """Discovers and owns all GitHub App installations for this App.

    Single source of truth for per-installation auth/client instances and
    the repo -> installation_id cache. GitHubPlatform delegates ALL client
    resolution to this manager instead of holding a single client.

    Exclusive filter mode: if `filter_installation_id` is set, only that
    installation is ever polled (matches pre-multi-install behavior).
    """

    REFRESH_TTL_SECONDS = 300  # 5-min discovery cache

    def __init__(
        self,
        app_id: Optional[str] = None,
        private_key_path: Optional[str] = None,
        filter_installation_id: Optional[str] = None,
    ):
        self.app_id = app_id or GITHUB_APP_ID
        self.private_key_path = private_key_path or GITHUB_PRIVATE_KEY_PATH
        self.filter_installation_id = filter_installation_id or None

        # App-JWT-only auth instance, used for discovery calls (no installation_id needed).
        self._app_auth = GitHubAppAuth(
            app_id=self.app_id, installation_id=None, private_key_path=self.private_key_path,
        )

        self._clients: dict[str, AsyncGitHubClient] = {}
        self._installations: list[dict] = []
        self._repo_to_installation: dict[str, str] = {}
        self._installation_repos: dict[str, list[str]] = {}

        self._last_refresh: float = 0.0
        self._refresh_lock = asyncio.Lock()

    async def _discover_installations(self) -> list[dict]:
        """App JWT call to GET /app/installations with host-pinned Link pagination."""
        jwt_token = self._app_auth.get_app_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        installations: list[dict] = []
        url: Optional[str] = "https://api.github.com/app/installations"
        params: Optional[dict[str, str]] = {"per_page": "100"}
        async with httpx.AsyncClient(
            timeout=30, verify=resolve_ca_bundle(), follow_redirects=False,
        ) as http:
            for _ in range(_DEFAULT_MAX_PAGES):
                if not url:
                    break
                resp = await http.get(url, headers=headers, params=params)
                await _handle_rate_limit(resp.headers, sleep=False)
                resp.raise_for_status()
                page_data = resp.json()
                if isinstance(page_data, list):
                    installations.extend(page_data)
                url = parse_github_next_link(
                    resp.headers.get("Link") if hasattr(resp, "headers") and resp.headers is not None else None
                )
                params = None
        return installations

    def _get_or_create_client(self, installation_id: str) -> AsyncGitHubClient:
        client = self._clients.get(installation_id)
        if client is None:
            auth = GitHubAppAuth(
                app_id=self.app_id,
                installation_id=installation_id,
                private_key_path=self.private_key_path,
            )
            client = AsyncGitHubClient(auth)
            self._clients[installation_id] = client
        return client

    async def _refresh(self) -> None:
        """Refresh installation list + repo cache. Stale-serve on discovery failure."""
        async with self._refresh_lock:
            now = time.monotonic()
            if self._installations and now < self._last_refresh + self.REFRESH_TTL_SECONDS:
                return  # Another caller already refreshed while we waited on the lock.

            try:
                discovered = await self._discover_installations()
            except Exception as e:
                if self._installations:
                    logger.warning(f"GitHub installation discovery failed, serving stale cache: {e}")
                    return
                raise

            if self.filter_installation_id:
                discovered = [
                    inst for inst in discovered
                    if str(inst.get("id")) == str(self.filter_installation_id)
                ]

            installation_repos: dict[str, list[str]] = {}
            repo_to_installation: dict[str, str] = {}
            for inst in discovered:
                inst_id = str(inst.get("id"))
                client = self._get_or_create_client(inst_id)
                try:
                    full_names: list[str] = []
                    pages = await _paginate_github_get(
                        client.get,
                        "/installation/repositories",
                        params={"per_page": "100"},
                        max_pages=_DEFAULT_MAX_PAGES,
                        use_etag=True,
                        backoff=False,
                    )
                    for resp in pages:
                        repos = resp.json().get("repositories", [])
                        full_names.extend(r["full_name"] for r in repos if not r.get("archived"))
                except Exception as e:
                    logger.warning(f"Repo discovery failed for installation {inst_id}: {e}")
                    full_names = list(self._installation_repos.get(inst_id, []))
                installation_repos[inst_id] = full_names
                for full_name in full_names:
                    repo_to_installation[full_name] = inst_id

            self._installations = discovered
            self._installation_repos = installation_repos
            self._repo_to_installation = repo_to_installation
            self._last_refresh = now
            logger.info(f"Found {len(discovered)} installation(s)")

    async def get_clients_with_repos(
        self, filter_id: Optional[str] = None,
    ) -> list[tuple[str, "AsyncGitHubClient", list[str]]]:
        """Return (installation_id, client, repo_full_names) for all discovered installations.

        When `filter_id` is set, returns ONLY that installation (exclusive filter).
        """
        await self._refresh()
        effective_filter = filter_id or self.filter_installation_id
        result: list[tuple[str, AsyncGitHubClient, list[str]]] = []
        for inst in self._installations:
            inst_id = str(inst.get("id"))
            if effective_filter and inst_id != str(effective_filter):
                continue
            client = self._clients.get(inst_id)
            if client is None:
                continue
            result.append((inst_id, client, self._installation_repos.get(inst_id, [])))
        return result

    async def get_client_for(self, installation_id: str) -> Optional["AsyncGitHubClient"]:
        """Direct lookup by installation ID (no discovery refresh -- caller already knows the ID)."""
        if not self._installations and time.monotonic() >= self._last_refresh + self.REFRESH_TTL_SECONDS:
            await self._refresh()
        return self._clients.get(str(installation_id))

    async def get_client_for_repo(
        self, owner: str, repo: str,
    ) -> Optional[tuple[str, "AsyncGitHubClient"]]:
        """Reverse lookup via the repo -> installation_id cache. None on cache miss."""
        await self._refresh()
        full_name = f"{owner}/{repo}"
        inst_id = self._repo_to_installation.get(full_name)
        if inst_id is None:
            return None
        client = self._clients.get(inst_id)
        if client is None:
            return None
        return inst_id, client

    async def close_all(self) -> None:
        """Shut down all persistent HTTP clients (lifecycle cleanup)."""
        await asyncio.gather(
            *[c.close() for c in self._clients.values()], return_exceptions=True,
        )
        self._clients.clear()


_installation_manager: Optional[MultiInstallationManager] = None
_shutting_down: bool = False


def get_installation_manager() -> Optional[MultiInstallationManager]:
    """Return shared lazy-initialized MultiInstallationManager, reading env vars at call time.

    Assumes single-asyncio-event-loop access (FastAPI/uvicorn main loop).
    The .pem private key is loaded lazily on first JWT/token request (not in __init__).
    Returns None when shutting down, when GITHUB_APP_ID is unset, or when construction fails.
    Never caches None so recovery when env/secrets appear works without restart.
    """
    global _installation_manager
    if _shutting_down:
        return None
    if _installation_manager is not None:
        return _installation_manager
    app_id = os.getenv("GITHUB_APP_ID", "").strip()
    if not app_id:
        return None
    private_key_path = os.getenv("GITHUB_PRIVATE_KEY_PATH", "").strip() or "/secrets/github"
    filter_installation_id = os.getenv("GITHUB_INSTALLATION_ID", "").strip() or None
    try:
        mgr = MultiInstallationManager(
            app_id=app_id,
            private_key_path=private_key_path,
            filter_installation_id=filter_installation_id,
        )
    except Exception as e:
        logger.warning(f"Shared GitHub installation manager init failed: {e}")
        return None
    _installation_manager = mgr
    return _installation_manager


async def close_installation_manager() -> None:
    """Close and clear the shared MultiInstallationManager (owned by main.py lifespan)."""
    global _installation_manager, _shutting_down
    _shutting_down = True
    mgr = _installation_manager
    _installation_manager = None
    if mgr is not None:
        await mgr.close_all()


def is_shared_installation_manager(manager: Any) -> bool:
    """Return True if manager is the process-wide shared MultiInstallationManager singleton."""
    return manager is not None and manager is _installation_manager


def reset_installation_manager() -> None:
    """Synchronous reset helper for pytest teardown fixtures."""
    global _installation_manager, _shutting_down
    _installation_manager = None
    _shutting_down = False
