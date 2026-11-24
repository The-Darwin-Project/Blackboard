# BlackBoard/src/utils/vcs_approval.py
# @ai-rules:
# 1. [Pattern]: Resolves live MR/PR HEAD commit SHA from VCS platform APIs at approval time to prevent TOCTOU.
# 2. [Fail-Closed]: Fails closed returning (mr_iid, None) if live API query fails or is unconfigured
#    -- on any non-2xx response or transport exception so merge guard refuses merge. Both branches log
#    a warning so an outage or expired token is operator-visible. This holds for GitHub too: the
#    cached gh_ctx["head_sha"] is NEVER substituted for a live SHA (it may be stale vs. the pushed HEAD).
# 3. [Security]: TLS verification is NEVER disabled on these calls -- GITLAB_HOST and
#    api.github.com are both CA-signed; verify=False would let a MITM forge the live SHA
#    this module exists to protect against. resolve_ca_bundle() and normalize_gitlab_host() live
#    in utils/tls.py (re-exported here for backward compatibility) as the SINGLE trust/host
#    resolvers shared across every VCS client (this module, github_app.py, headhunter_gitlab.py,
#    headhunter_github.py, and routes/queue.py): resolve_ca_bundle() raises ValueError on
#    GITLAB_SSL_VERIFY=0/false/no and only accepts readable non-empty regular files as CA bundles.
# 4. [Pattern]: verify_merge_guard() is the Python REFERENCE implementation of the approval verdict (out-of-band
#    approval + SHA binding for category 'git_merge'; approval only for 'operational'). The sidecar enforces the same
#    contract in JS (gemini-sidecar/hooks/merge-guard.js approvalVerdict) -- keep the two in lock-step; the parity is
#    covered by tests/test_vcs_approval.py and the sidecar tests. Do not reimplement the comparison elsewhere in Python.
# 5. [Contract]: `approved` must be the boolean True (`is True`): truthy non-booleans ("false", 1) are rejected.
#    'operational' (sysadmin-only; the ROLE gate is the caller's) skips the SHA check; any category other than exactly
#    'operational' is treated as 'git_merge'.
# 6. [Pattern]: HEX_SHA_RE (\A[0-9a-fA-F]{7,64}\Z), extract_context_head_sha(), and check_approval_sha_drift()
#    are the single shared approval-drift primitives across REST, WS, Slack, and Headhunter (fail-closed on
#    CLOSED/RESOLVED, unresolvable live SHA, or expected_sha mismatch).
from __future__ import annotations

import asyncio
from dataclasses import dataclass
import logging
import os
import re
import urllib.parse
from typing import TYPE_CHECKING, Any, Optional

import httpx

from .github_app import get_installation_manager
from .tls import (
    _resolve_ca_bundle,
    _usable_ca_file,
    normalize_gitlab_host,
    resolve_ca_bundle,
)

if TYPE_CHECKING:
    from ..models import EventDocument

logger = logging.getLogger(__name__)

HEX_SHA_RE = re.compile(r"\A[0-9a-fA-F]{7,64}\Z")


def is_stale_verification_gitlab_mirror(event: Any) -> bool:
    """True if gitlab_context is just a best-effort mirror of a Kargo verification failure."""
    ev_obj = getattr(getattr(event, "event", None), "evidence", None)
    if not ev_obj:
        return False
    kc = getattr(ev_obj, "kargo_context", None)
    if not isinstance(kc, dict) or kc.get("failure_type") != "verification":
        return False
    
    gl_ctx = getattr(ev_obj, "gitlab_context", None)
    if not isinstance(gl_ctx, dict):
        return False
        
    kc_url = kc.get("mr_url", "")
    gl_url = gl_ctx.get("target_url", "")
    
    if kc_url and gl_url and kc_url == gl_url:
        return True
        
    # Also check parsed
    if kc_url:
        kc_parsed = parse_mr_url(kc_url)
        if kc_parsed:
            kc_pid, kc_iid = kc_parsed
            if str(gl_ctx.get("project_id")) == str(kc_pid) and str(gl_ctx.get("mr_iid")) == str(kc_iid):
                return True

    return False


def extract_context_head_sha(event: Any) -> str | None:
    """Extract cached HEAD SHA from gitlab_context, github_context, or kargo_context."""
    ev_obj = getattr(getattr(event, "event", None), "evidence", None)
    if not ev_obj:
        return None
    stale_mirror = is_stale_verification_gitlab_mirror(event)
    for attr, keys in (
        ("gitlab_context", ("head_sha", "sha")),
        ("github_context", ("head_sha",)),
        ("kargo_context", ("head_sha", "sha")),
    ):
        ctx = getattr(ev_obj, attr, None)
        if not isinstance(ctx, dict):
            continue
        if attr == "gitlab_context" and stale_mirror:
            continue
        if attr == "kargo_context" and ctx.get("failure_type") == "verification":
            continue
        for k in keys:
            val = ctx.get(k)
            if isinstance(val, str) and val.strip():
                return val.strip()
    return None


def parse_mr_url(url: str) -> tuple[int | str, int] | None:
    """Extract (project_id, mr_iid) from a GitLab MR URL."""
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


async def resolve_live_head_sha(event: Any) -> tuple[str | None, str | None]:
    """Resolve live MR/PR ID and HEAD commit SHA from GitLab/GitHub at approval time.

    Returns:
        (approved_mr_id, approved_mr_sha) or (None, None) if not a VCS-linked event.
    """
    evidence = getattr(getattr(event, "event", None), "evidence", None)
    if not evidence:
        return None, None

    stale_mirror = is_stale_verification_gitlab_mirror(event)

    gl_ctx = getattr(evidence, "gitlab_context", None)
    if not stale_mirror and isinstance(gl_ctx, dict) and gl_ctx:
        project_id = gl_ctx.get("project_id")
        mr_iid = str(gl_ctx.get("mr_iid") or gl_ctx.get("iid") or "")
        if project_id and mr_iid:
            return await _resolve_gitlab_head(gl_ctx)

    gh_ctx = getattr(evidence, "github_context", None)
    if isinstance(gh_ctx, dict) and gh_ctx:
        return await _resolve_github_head(gh_ctx)

    kargo_ctx = getattr(evidence, "kargo_context", None)
    if isinstance(kargo_ctx, dict) and kargo_ctx.get("mr_url") and kargo_ctx.get("failure_type") != "verification":
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

    decoded_pid = urllib.parse.unquote(str(project_id)).strip()
    if not decoded_pid or decoded_pid in (".", "..") or any(
        seg in (".", "..") for seg in decoded_pid.split("/")
    ):
        logger.warning("Rejected invalid GitLab project_id for MR !%s", mr_iid)
        return mr_iid, None
    encoded_project_id = urllib.parse.quote(decoded_pid, safe="")
    host = normalize_gitlab_host(os.getenv("GITLAB_HOST", ""))
    auth = None
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
            mr_url = f"https://{host}/api/v4/projects/{encoded_project_id}/merge_requests/{mr_iid}"
            async with httpx.AsyncClient(timeout=10, verify=ca_bundle, follow_redirects=False) as client:
                resp = await client.get(mr_url, headers={"PRIVATE-TOKEN": token})
                if resp.status_code == 401 and auth is not None and hasattr(auth, "invalidate"):
                    auth.invalidate()
                    try:
                        refreshed = auth.get_token()
                    except Exception:
                        refreshed = ""
                    if refreshed and refreshed != token:
                        resp = await client.get(mr_url, headers={"PRIVATE-TOKEN": refreshed})
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
        async with httpx.AsyncClient(timeout=10, verify=ca_bundle, follow_redirects=False) as client:
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


@dataclass(frozen=True)
class ApprovalDriftResult:
    """Result of evaluating HEAD SHA drift and lifecycle guards prior to human approval."""

    allowed: bool
    code: str  # "ok" | "closed" | "sha_unresolvable" | "sha_drift"
    detail: str
    approval_requested_sha: Optional[str] = None
    live_sha: Optional[str] = None


def _is_vcs_backed_event(event: Any) -> bool:
    ev_obj = getattr(getattr(event, "event", None), "evidence", None)
    if ev_obj is None:
        return False
    stale_mirror = is_stale_verification_gitlab_mirror(event)
    for attr, keys in (("gitlab_context", ("mr_iid", "mr_id")), ("github_context", ("pr_number",)), ("kargo_context", ("mr_url",))):
        ctx = getattr(ev_obj, attr, None)
        if not isinstance(ctx, dict):
            continue
        if attr == "gitlab_context" and stale_mirror:
            continue
        if attr == "kargo_context" and ctx.get("failure_type") == "verification":
            continue
        if any(ctx.get(k) for k in keys):
            return True
    return False


def check_approval_sha_drift(
    event: Any,
    live_sha: Optional[str],
    expected_sha: Optional[str] = None,
) -> ApprovalDriftResult:
    """Enforce closed-event and SHA-pinned drift invariants across REST, WS, and Slack.

    Pure function — zero I/O. Safe on bare MagicMock objects in legacy unit tests.
    """
    raw_status = getattr(event, "status", None)
    status_str = raw_status.value if hasattr(raw_status, "value") else str(raw_status or "")
    if status_str.strip().lower() in ("closed", "resolved"):
        return ApprovalDriftResult(
            allowed=False,
            code="closed",
            detail="Event is already closed and cannot be approved.",
        )

    raw_req = getattr(event, "approval_requested_sha", None)
    req_sha = raw_req.strip() if isinstance(raw_req, str) and raw_req.strip() else None
    clean_live = live_sha.strip() if isinstance(live_sha, str) and live_sha.strip() else None
    clean_expected = (
        expected_sha.strip() if isinstance(expected_sha, str) and expected_sha.strip() else None
    )

    if clean_expected is not None:
        if clean_live is None:
            return ApprovalDriftResult(
                allowed=False,
                code="sha_unresolvable",
                detail=(
                    f"Cannot verify live HEAD SHA for approval "
                    f"(expected {clean_expected[:8]})."
                ),
                approval_requested_sha=req_sha,
                live_sha=None,
            )
        if clean_expected != clean_live:
            return ApprovalDriftResult(
                allowed=False,
                code="sha_drift",
                detail=(
                    f"HEAD SHA changed ({clean_expected[:8]} -> {clean_live[:8]}). "
                    "Confirm approval for the new SHA."
                ),
                approval_requested_sha=req_sha,
                live_sha=clean_live,
            )
        return ApprovalDriftResult(
            allowed=True,
            code="ok",
            detail="Confirmed approval for updated HEAD SHA.",
            approval_requested_sha=req_sha,
            live_sha=clean_live,
        )

    if req_sha is not None:
        if clean_live is None:
            return ApprovalDriftResult(
                allowed=False,
                code="sha_unresolvable",
                detail=(
                    f"Cannot verify live HEAD SHA for approval "
                    f"(requested at {req_sha[:8]})."
                ),
                approval_requested_sha=req_sha,
                live_sha=None,
            )
        if clean_live != req_sha:
            return ApprovalDriftResult(
                allowed=False,
                code="sha_drift",
                detail=(
                    f"HEAD SHA changed since approval was requested "
                    f"({req_sha[:8]} -> {clean_live[:8]}). Confirm approval for the new SHA."
                ),
                approval_requested_sha=req_sha,
                live_sha=clean_live,
            )

    if clean_live is None and _is_vcs_backed_event(event):
        return ApprovalDriftResult(
            allowed=False,
            code="sha_unresolvable",
            detail="Cannot verify live HEAD SHA for VCS-backed approval.",
        )

    return ApprovalDriftResult(
        allowed=True,
        code="ok",
        detail="OK",
        approval_requested_sha=req_sha,
        live_sha=clean_live,
    )


def verify_merge_guard(
    approval_record: dict[str, Any] | None,
    local_head_sha: str | None,
    category: str = "git_merge",
) -> tuple[bool, str]:
    """Verify out-of-band approval (and SHA binding for git_merge) matching sidecar merge-guard.js."""
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
