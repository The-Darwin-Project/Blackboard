# BlackBoard/src/utils/github_app.py
# @ai-rules:
# 1. [Constraint]: GitHubAppAuth.get_token() is thread-safe (threading.Lock).
# 2. [Pattern]: AsyncGitHubClient wraps blocking token refresh via asyncio.to_thread().
# 3. [Pattern]: AsyncGitHubClient uses persistent httpx.AsyncClient; call close() on shutdown.
# 4. [Pattern]: Rate-limit warning at 100 remaining (GitHub soft-gate is at 0).
# 5. [Pattern]: get_github_auth() is the singleton accessor — all consumers use it, not GitHubAppAuth() directly.
# 6. [Pattern]: get/post/delete share the same auth header pattern. delete() calls raise_for_status().
# 7. [Pattern]: MultiInstallationManager owns all per-installation GitHubAppAuth/AsyncGitHubClient
#    instances + the repo->installation_id cache (single source of truth for GitHubPlatform).
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
import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Optional

import httpx
import jwt
import requests

logger = logging.getLogger(__name__)

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
        
        response = requests.post(url, headers=headers, timeout=30)
        response.raise_for_status()
        
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
        resp = requests.get(url, headers=headers, timeout=30)
        resp.raise_for_status()
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

    def __init__(self, auth: GitHubAppAuth):
        self._auth = auth
        self._client = httpx.AsyncClient(timeout=30)

    async def close(self) -> None:
        """Shut down the persistent HTTP client."""
        await self._client.aclose()

    async def get_token(self) -> str:
        return await asyncio.to_thread(self._auth.get_token)

    async def get(self, path: str, params: dict | None = None) -> httpx.Response:
        token = await self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = await self._client.get(
            f"https://api.github.com{path}", headers=headers, params=params,
        )
        remaining = resp.headers.get("X-RateLimit-Remaining")
        if remaining and int(remaining) < 100:
            logger.warning(f"GitHub rate limit low: {remaining} remaining")
        resp.raise_for_status()
        return resp

    async def post(self, path: str, json: dict | None = None) -> httpx.Response:
        token = await self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = await self._client.post(
            f"https://api.github.com{path}", headers=headers, json=json,
        )
        resp.raise_for_status()
        return resp

    async def delete(self, path: str) -> httpx.Response:
        token = await self.get_token()
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        resp = await self._client.delete(
            f"https://api.github.com{path}", headers=headers,
        )
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
        """App JWT call to GET /app/installations. Returns list of installation dicts."""
        jwt_token = self._app_auth.get_app_jwt()
        headers = {
            "Authorization": f"Bearer {jwt_token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        async with httpx.AsyncClient(timeout=30) as http:
            resp = await http.get(
                "https://api.github.com/app/installations",
                headers=headers, params={"per_page": "100"},
            )
            resp.raise_for_status()
            return resp.json()

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
                    resp = await client.get(
                        "/installation/repositories", params={"per_page": "100"},
                    )
                    repos = resp.json().get("repositories", [])
                    full_names = [r["full_name"] for r in repos if not r.get("archived")]
                except Exception as e:
                    logger.warning(f"Repo discovery failed for installation {inst_id}: {e}")
                    full_names = []
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
