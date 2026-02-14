# BlackBoard/src/utils/github_app.py
"""
GitHub App Authentication for GitOps operations.

Generates installation access tokens from GitHub App credentials
for authenticated git operations (clone, push).
"""
import json
import logging
import os
import time
from pathlib import Path
from typing import Optional

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
        
        # Validate configuration
        if not self.app_id:
            raise ValueError("GITHUB_APP_ID not configured")
        if not self.installation_id:
            raise ValueError("GITHUB_INSTALLATION_ID not configured")
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
        """
        now = time.time()
        
        # Check if we have a valid cached token
        if self._token and now < (self._token_expires_at - self.TOKEN_REFRESH_BUFFER_SECONDS):
            logger.debug("Using cached installation token")
            return self._token
        
        # Request new token
        logger.info("Requesting new GitHub installation token")
        token_response = self._request_installation_token()
        
        self._token = token_response["token"]
        # Parse ISO timestamp to epoch
        expires_at_str = token_response["expires_at"]
        # Format: 2024-01-15T12:00:00Z
        from datetime import datetime
        expires_at_dt = datetime.fromisoformat(expires_at_str.replace("Z", "+00:00"))
        self._token_expires_at = expires_at_dt.timestamp()
        
        logger.info(f"Got new token, expires at {expires_at_str}")
        return self._token
    
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
