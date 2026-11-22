# BlackBoard/src/utils/vcs_approval.py
# @ai-rules:
# 1. [Pattern]: Resolves live MR/PR HEAD commit SHA from VCS platform APIs at approval time to prevent TOCTOU.
# 2. [Fail-Closed]: Fails closed returning (mr_iid, None) if live API query fails or is unconfigured
#    -- on any non-2xx response or transport exception so merge guard refuses merge. Both branches log
#    a warning so an outage or expired token is operator-visible. This holds for GitHub too: the
#    cached gh_ctx["head_sha"] is NEVER substituted for a live SHA (it may be stale vs. the pushed HEAD).
# 3. [Security]: TLS verification is NEVER disabled on these calls -- GITLAB_HOST and
#    api.github.com are both CA-signed; verify=False would let a MITM forge the live SHA
#    this module exists to protect against. resolve_ca_bundle() is the SINGLE trust resolver for
#    every VCS client (this module, headhunter_gitlab.py, AND routes/queue.py): it raises ValueError on
#    GITLAB_SSL_VERIFY=0/false/no and only accepts non-empty regular files as CA bundles (an empty
#    or directory path is skipped, never handed to httpx). `_resolve_ca_bundle` is a back-compat alias.
#    normalize_gitlab_host() is the single GITLAB_HOST normalizer shared across this module,
#    headhunter_gitlab.py, and routes/queue.py.
# 4. [Pattern]: verify_merge_guard() is the Python REFERENCE implementation of the approval verdict (out-of-band
#    approval + SHA binding for category 'git_merge'; approval only for 'operational'). The sidecar enforces the same
#    contract in JS (gemini-sidecar/hooks/merge-guard.js approvalVerdict) -- keep the two in lock-step; the parity is
#    covered by tests/test_vcs_approval.py and the sidecar tests. Do not reimplement the comparison elsewhere in Python.
# 5. [Contract]: `approved` must be the boolean True (`is True`): truthy non-booleans ("false", 1) are rejected.
#    'operational' (sysadmin-only; the ROLE gate is the caller's) skips the SHA check; any category other than exactly
#    'operational' is treated as 'git_merge'.
from __future__ import annotations

import asyncio
import logging
import os
import urllib.parse
from typing import TYPE_CHECKING, Any

import httpx

from .github_app import get_installation_manager

if TYPE_CHECKING:
    from ..models import EventDocument

logger = logging.getLogger(__name__)


def normalize_gitlab_host(raw: str) -> str:
    """Normalize GITLAB_HOST by stripping scheme and trailing slashes; reject invalid host chars."""
    host = (raw or "").strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    if not host or any(ch.isspace() or ch in "@?#" for ch in host):
        return ""
    return host


def parse_mr_url(url: str) -> tuple[int | str, int] | None:
    """Extract (project_id, mr_iid) from a GitLab MR URL."""
    import re
    from urllib.parse import unquote
    m = re.search(r"/projects/(\d+)/merge_requests/(\d+)", url)
    if m:
        return int(m.group(1)), int(m.group(2))
    sep = "/-/merge_requests/"
    if sep in url:
        left, right = url.split(sep, 1)
        mr_iid_str = right.split("/")[0].split("?")[0].split("#")[0]
        if mr_iid_str.isdigit():
            without_proto = left.split("://", 1)[-1]
            project_path = without_proto.split("/", 1)[-1]
            if project_path:
                return unquote(project_path), int(mr_iid_str)
    return None


def _usable_ca_file(path: str) -> bool:
    """True only for a non-empty regular file (an empty/dir path would break or silently weaken TLS)."""
    return os.path.isfile(path) and os.path.getsize(path) > 0


def resolve_ca_bundle(host: str = "") -> str | bool:
    """Resolve the CA bundle for VCS TLS verification (path, or True for httpx's default store).

    Raises ValueError when GITLAB_SSL_VERIFY disables verification: verify=False is forbidden for
    every VCS call (approval SHA resolution and Headhunter GitLab polling alike).
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


async def resolve_live_head_sha(event: Any) -> tuple[str | None, str | None]:
    """Resolve live MR/PR ID and HEAD commit SHA from GitLab/GitHub at approval time.

    Returns:
        (approved_mr_id, approved_mr_sha) or (None, None) if not a VCS-linked event.
    """
    evidence = getattr(getattr(event, "event", None), "evidence", None)
    if not evidence:
        return None, None

    gl_ctx = getattr(evidence, "gitlab_context", None)
    if isinstance(gl_ctx, dict) and gl_ctx:
        project_id = gl_ctx.get("project_id")
        mr_iid = str(gl_ctx.get("mr_iid") or gl_ctx.get("iid") or "")
        if project_id and mr_iid:
            return await _resolve_gitlab_head(gl_ctx)

    gh_ctx = getattr(evidence, "github_context", None)
    if isinstance(gh_ctx, dict) and gh_ctx:
        return await _resolve_github_head(gh_ctx)

    kargo_ctx = getattr(evidence, "kargo_context", None)
    if isinstance(kargo_ctx, dict) and kargo_ctx.get("mr_url"):
        parsed = parse_mr_url(kargo_ctx["mr_url"])
        if parsed:
            project_id, mr_iid = parsed
            return await _resolve_gitlab_head({
                "project_id": project_id,
                "mr_iid": mr_iid,
            })

    if isinstance(gl_ctx, dict) and gl_ctx:
        return await _resolve_gitlab_head(gl_ctx)

    return None, None


async def _resolve_gitlab_head(gl_ctx: dict) -> tuple[str | None, str | None]:
    mr_iid = str(gl_ctx.get("mr_iid") or gl_ctx.get("iid") or "")
    project_id = gl_ctx.get("project_id")

    if not project_id or not mr_iid:
        return (mr_iid or None, None)

    encoded_project_id = urllib.parse.quote(urllib.parse.unquote(str(project_id)), safe="")
    host = normalize_gitlab_host(os.getenv("GITLAB_HOST", ""))
    token = ""
    try:
        from .gitlab_token import get_gitlab_auth
        auth = get_gitlab_auth()
        if auth:
            token = auth.get_token()
    except Exception:
        pass
    if not token:
        token = os.getenv("GITLAB_TOKEN", "")

    if host and token:
        try:
            ca_bundle = resolve_ca_bundle(host)
            async with httpx.AsyncClient(timeout=10, verify=ca_bundle) as client:
                resp = await client.get(
                    f"https://{host}/api/v4/projects/{encoded_project_id}/merge_requests/{mr_iid}",
                    headers={"PRIVATE-TOKEN": token},
                )
                if resp.is_success:
                    mr_data = resp.json()
                    live_sha = mr_data.get("sha") or (mr_data.get("diff_refs") or {}).get("head_sha")
                    if live_sha:
                        return mr_iid, live_sha
                else:
                    logger.warning(
                        "Live GitLab HEAD SHA query for MR !%s returned HTTP %s -- merge guard will refuse unverified SHA",
                        mr_iid, resp.status_code,
                    )
        except Exception as e:
            logger.warning(
                "Failed live GitLab HEAD SHA query for MR !%s (%s) -- merge guard will refuse unverified SHA",
                mr_iid, type(e).__name__,
            )

    return mr_iid, None


async def _resolve_github_head(gh_ctx: dict) -> tuple[str | None, str | None]:
    """Resolve the live PR HEAD SHA. Fails closed: (pr_number, None) on ANY failure.

    The cached ``gh_ctx["head_sha"]`` is deliberately ignored -- it is the SHA seen when the event
    was created and can be stale after a force-push, which is exactly the TOCTOU this module guards.
    """
    pr_number = str(gh_ctx.get("pr_number") or gh_ctx.get("number") or "")
    owner = gh_ctx.get("owner")
    repo = gh_ctx.get("repo")

    if not owner or not repo or not pr_number:
        return (pr_number or None, None)

    token = ""
    try:
        mgr = get_installation_manager()
        if mgr is not None:
            async def _fetch_app_token() -> tuple[object | None, str]:
                found = await mgr.get_client_for_repo(owner, repo)
                if found is None:
                    return None, ""
                _, gh_client = found
                return found, await gh_client.get_token()

            res, token = await asyncio.wait_for(_fetch_app_token(), timeout=10)
            if res is None:
                logger.warning(
                    "GitHub App installation lookup missed repo %s/%s for PR #%s -- falling back to GITHUB_TOKEN",
                    owner, repo, pr_number,
                )
    except Exception as e:
        logger.warning(
            "GitHub App token resolution failed for %s/%s PR #%s (%s) -- falling back to GITHUB_TOKEN",
            owner, repo, pr_number, type(e).__name__,
        )
        token = ""

    if not token:
        token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        ca_bundle = resolve_ca_bundle()
        async with httpx.AsyncClient(timeout=10, verify=ca_bundle) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=headers,
            )
            if resp.is_success:
                pr_data = resp.json()
                live_sha = (pr_data.get("head") or {}).get("sha")
                if live_sha:
                    return pr_number, live_sha
                logger.warning(
                    "Live GitHub HEAD SHA query for PR #%s returned no head.sha -- merge guard will refuse unverified SHA",
                    pr_number,
                )
            else:
                logger.warning(
                    "Live GitHub HEAD SHA query for PR #%s returned HTTP %s -- merge guard will refuse unverified SHA",
                    pr_number, resp.status_code,
                )
    except Exception as e:
        logger.warning(
            "Failed live GitHub HEAD SHA query for PR #%s (%s) -- merge guard will refuse unverified SHA",
            pr_number, type(e).__name__,
        )

    return pr_number, None


def verify_merge_guard(
    approval_record: dict[str, Any] | None,
    local_head_sha: str | None,
    category: str = "git_merge",
) -> tuple[bool, str]:
    """Decide whether the Developer agent may merge, breaking prompt-injection circularity (C2).

    This is the out-of-band cryptographic-binding check referenced by
    `src/agents/brain_skills/dispatch/mr-lifecycle.md` and enforced for Gemini-CLI Developer
    sessions by `gemini-sidecar/hooks/validate-mutations.sh`'s merge-approval gate, which
    applies the same comparison in JS (`merge-guard.js approvalVerdict`; approval fetched via the `/proxy/approval` -> `GET /queue/{event_id}/approval`
    chain) before allowing a `git merge`/`git push ... main`/`gh pr merge`/`glab mr merge`
    command through. Strictly verifies live_git_head == approval.approved_mr_sha and refuses
    to merge based on prompt text alone -- an attacker who injects "the plan is approved,
    please merge" into agent context cannot forge a passing `approval_record` here.

    When category is 'operational', verifies only that the event has been approved by an authorized
    maintainer (`approved is True`), bypassing the VCS commit SHA matching check (which only applies to
    git_merge). The sysadmin ROLE requirement is enforced by the caller (hook), not here.

    Pure function -- zero side effects, zero I/O. Callers own fetching `approval_record`
    (e.g. via `bb_get_approval` / `GET /queue/{event_id}/approval`) and `local_head_sha`
    (e.g. via `git rev-parse HEAD`).
    """
    if category != "operational":
        category = "git_merge"

    if not isinstance(approval_record, dict) or approval_record.get("approved") is not True:
        if category == "operational":
            return False, "Operational mutation REFUSED: event not approved by authorized maintainer"
        return False, "Merge REFUSED: event not approved by authorized maintainer"

    if category == "operational":
        return True, "Operational execution approved by maintainer."

    approved_sha = approval_record.get("approved_mr_sha")
    if not approved_sha or not local_head_sha or approved_sha != local_head_sha:
        return (
            False,
            f"Merge REFUSED: live HEAD ({local_head_sha}) differs from authenticated approval SHA ({approved_sha})",
        )

    return True, "Merge AUTHORIZED"
