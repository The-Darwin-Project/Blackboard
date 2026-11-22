# BlackBoard/src/utils/gitlab_token.py
# @ai-rules:
# 1. [Constraint]: GitLabTokenAuth.get_token() is thread-safe (threading.Lock) and validates
#    (st_mtime_ns, st_ino, st_size) via os.fstat() to detect same-second K8s Secret atomic swaps.
# 2. [Security]: Only regular files (S_ISREG) are read, capped at 8192 bytes; empty reads raise
#    ValueError and NEVER poison the cache. Call invalidate() on HTTP 401 to force immediate reload.
# 3. [Pattern]: get_gitlab_auth() is the process-wide singleton accessor.
"""
GitLab Token Authentication for GitOps operations.

Reads a GitLab access token (PAT / Service Account token) from a
mounted Kubernetes secret and configures git credentials for
authenticated operations against a GitLab instance.

Unlike GitHub App auth (JWT -> installation token exchange), GitLab
uses a static token directly -- no exchange needed.
"""
import logging
import os
import stat
import subprocess
import threading
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_TOKEN_BYTES = 8192

# GitLab configuration from environment/secrets
GITLAB_TOKEN_PATH = os.getenv("GITLAB_TOKEN_PATH", "/secrets/gitlab/token")
GITLAB_HOST = os.getenv("GITLAB_HOST", "")


class GitLabTokenAuth:
    """
    GitLab token authentication handler.

    Reads a static access token from a mounted K8s secret.
    Token must have scopes: api, read_repository, write_repository.
    """

    def __init__(
        self,
        token_path: Optional[str] = None,
        host: Optional[str] = None,
    ):
        self.token_path = token_path or GITLAB_TOKEN_PATH
        self.host = host or GITLAB_HOST
        self._token: Optional[str] = None
        self._stat_key: Optional[tuple[int, int, int]] = None
        self._lock = threading.Lock()

        # Validate configuration
        if not self.host:
            raise ValueError("GITLAB_HOST not configured")
        if not Path(self.token_path).exists():
            raise ValueError(f"GitLab token not found at {self.token_path}")

    def invalidate(self) -> None:
        """Clear cached token so the next get_token() re-reads from disk."""
        with self._lock:
            self._token = None
            self._stat_key = None

    def get_token(self) -> str:
        """Read the GitLab access token from the mounted secret.

        Re-reads automatically when (st_mtime_ns, st_ino, st_size) changes
        (including same-second Kubernetes Secret ..data atomic swaps).
        Never caches empty token reads.
        """
        with self._lock:
            st = os.stat(self.token_path)
            if not stat.S_ISREG(st.st_mode):
                raise ValueError(f"GitLab token path {self.token_path} is not a regular file")
            stat_key = (st.st_mtime_ns, st.st_ino, st.st_size)
            if self._token is not None and self._stat_key == stat_key:
                return self._token

            logger.info(f"Reading GitLab token from {self.token_path}")
            with open(self.token_path, "r", encoding="utf-8") as f:
                fst = os.fstat(f.fileno())
                if not stat.S_ISREG(fst.st_mode):
                    raise ValueError(f"GitLab token path {self.token_path} is not a regular file")
                token = f.read(_MAX_TOKEN_BYTES).strip()
                f_stat_key = (fst.st_mtime_ns, fst.st_ino, fst.st_size)

            if not token:
                self._token = None
                self._stat_key = None
                raise ValueError(f"GitLab token at {self.token_path} is empty")

            self._token = token
            self._stat_key = f_stat_key
            logger.info(f"GitLab token loaded for {self.host}")
            return self._token

    def get_clone_url(self, project_path: str) -> str:
        """
        Get an authenticated clone URL for a GitLab project.

        Args:
            project_path: Project path (e.g., "my-group/my-project")

        Returns:
            Authenticated HTTPS URL: https://darwin-agent:<token>@<host>/path.git
        """
        token = self.get_token()
        suffix = "" if project_path.endswith(".git") else ".git"
        return f"https://darwin-agent:{token}@{self.host}/{project_path}{suffix}"

    def configure_git_credentials(self, repo_path: str, project_path: str) -> None:
        """
        Configure git credentials for a GitLab repository.

        Sets up the credential helper to use the GitLab token.
        Uses /tmp/git-creds/credentials shared with sidecar via emptyDir volume.

        Args:
            repo_path: Path to the local git repository
            project_path: GitLab project path (e.g., "org/project")
        """
        token = self.get_token()

        # Use shared credential path
        credentials_dir = Path("/tmp/git-creds")
        credentials_path = credentials_dir / "credentials-gitlab"

        # Ensure directory exists
        credentials_dir.mkdir(parents=True, exist_ok=True)

        # Configure credential helper for GitLab host
        subprocess.run(
            ["git", "config", "credential.helper", f"store --file={credentials_path}"],
            cwd=repo_path,
            check=True,
        )

        # Write GitLab credentials to store
        credentials = f"https://darwin-agent:{token}@{self.host}\n"

        with open(credentials_path, "w") as f:
            f.write(credentials)

        # Set the remote URL with token
        remote_url = self.get_clone_url(project_path)
        subprocess.run(
            ["git", "remote", "set-url", "origin", remote_url],
            cwd=repo_path,
            check=True,
        )

        logger.info(f"Configured git credentials for {self.host}/{project_path}")


# Singleton instance
_gitlab_auth: Optional[GitLabTokenAuth] = None


def get_gitlab_auth() -> Optional[GitLabTokenAuth]:
    """
    Get the GitLab auth singleton.

    Returns None if GitLab token is not available (optional dependency).
    """
    global _gitlab_auth
    if _gitlab_auth is None:
        try:
            _gitlab_auth = GitLabTokenAuth()
        except ValueError as e:
            logger.info(f"GitLab auth not available: {e}")
            return None
    return _gitlab_auth
