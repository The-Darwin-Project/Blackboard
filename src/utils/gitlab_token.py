# BlackBoard/src/utils/gitlab_token.py
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
import subprocess
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

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

        # Validate configuration
        if not self.host:
            raise ValueError("GITLAB_HOST not configured")
        if not Path(self.token_path).exists():
            raise ValueError(f"GitLab token not found at {self.token_path}")

    def get_token(self) -> str:
        """
        Read the GitLab access token from the mounted secret.

        Caches the token in memory after first read.
        """
        if self._token:
            return self._token

        logger.info(f"Reading GitLab token from {self.token_path}")
        with open(self.token_path, "r") as f:
            self._token = f.read().strip()

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
            project_path: GitLab project path (e.g., "openshift-virtualization/release-app")
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
