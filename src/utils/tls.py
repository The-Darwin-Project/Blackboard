# BlackBoard/src/utils/tls.py
# @ai-rules:
# 1. [Constraint]: Leaf stdlib-only TLS/host helper module. NEVER import src.agents, src.state,
#    src.routes, or src.auth (breaks the vcs_approval <-> github_app circular dependency).
# 2. [Security]: TLS verification is NEVER disabled -- resolve_ca_bundle() raises ValueError on
#    GITLAB_SSL_VERIFY=0/false/no and only accepts non-empty regular files as CA bundles.
# 3. [Pattern]: Single source of truth for resolve_ca_bundle(), _usable_ca_file(), and
#    normalize_gitlab_host() shared across vcs_approval.py, github_app.py, headhunter_gitlab.py,
#    headhunter_github.py, and routes/queue.py.
from __future__ import annotations

import logging
import os
import stat

logger = logging.getLogger(__name__)


def normalize_gitlab_host(raw: str) -> str:
    """Normalize GITLAB_HOST by stripping scheme and trailing slashes; reject invalid host chars."""
    host = (raw or "").strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    if not host or any(ch.isspace() or ch in "@?#" for ch in host):
        return ""
    return host


def _usable_ca_file(path: str) -> bool:
    """True only for a readable non-empty regular file (returns False on OSError)."""
    try:
        if not os.path.isfile(path):
            return False
        st = os.stat(path)
    except OSError:
        return False
    return stat.S_ISREG(st.st_mode) and st.st_size > 0 and os.access(path, os.R_OK)


def resolve_ca_bundle(host: str = "") -> str | bool:
    """Resolve the CA bundle for VCS TLS verification (path, or True for httpx's default store).

    Raises ValueError when GITLAB_SSL_VERIFY disables verification: verify=False is forbidden for
    every VCS call (approval SHA resolution, GitHub App clients, and Headhunter polling alike).
    """
    verify_env = os.getenv("GITLAB_SSL_VERIFY")
    if verify_env is not None:
        cleaned = verify_env.strip().lower()
        if cleaned in ("0", "false", "no"):
            raise ValueError(
                f"Insecure TLS verification (GITLAB_SSL_VERIFY={verify_env}) is forbidden for VCS API calls"
            )
        if cleaned in ("1", "true", "yes"):
            pass
        elif _usable_ca_file(verify_env.strip()):
            return verify_env.strip()
        else:
            logger.warning(
                "GITLAB_SSL_VERIFY path %s does not exist or is not a non-empty file; "
                "falling back to standard CA search", verify_env,
            )

    for env_var in ("REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        val = os.getenv(env_var)
        if val:
            val_clean = val.strip()
            if _usable_ca_file(val_clean):
                return val_clean
            logger.warning(
                "%s path %s does not exist or is not a non-empty file; falling back to standard CA search",
                env_var, val,
            )

    for std_path in (
        "/etc/pki/ca-trust/extracted/pem/tls-ca-bundle.pem",
        "/etc/pki/tls/certs/ca-bundle.crt",
        "/etc/ssl/certs/ca-certificates.crt",
    ):
        if _usable_ca_file(std_path):
            return std_path

    return True


# Back-compat alias (tests / older call sites import the underscore name).
_resolve_ca_bundle = resolve_ca_bundle
