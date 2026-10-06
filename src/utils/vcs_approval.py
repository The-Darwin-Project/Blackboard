# BlackBoard/src/utils/vcs_approval.py
# @ai-rules:
# 1. [Pattern]: Resolves live MR/PR HEAD commit SHA from VCS platform APIs at approval time to prevent TOCTOU.
# 2. [Fallback]: Gracefully falls back to cached evidence context if live API query fails or is unconfigured.
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from ..models import EventDocument

logger = logging.getLogger(__name__)


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
        return await _resolve_gitlab_head(gl_ctx)

    gh_ctx = getattr(evidence, "github_context", None)
    if isinstance(gh_ctx, dict) and gh_ctx:
        return await _resolve_github_head(gh_ctx)

    return None, None


async def _resolve_gitlab_head(gl_ctx: dict) -> tuple[str | None, str | None]:
    mr_iid = str(gl_ctx.get("mr_iid") or gl_ctx.get("iid") or "")
    project_id = gl_ctx.get("project_id")
    fallback_sha = gl_ctx.get("head_sha") or gl_ctx.get("sha") or gl_ctx.get("last_commit_id")

    if not project_id or not mr_iid:
        return (mr_iid or None, fallback_sha)

    host = os.getenv("GITLAB_HOST", "").removeprefix("https://").removeprefix("http://").rstrip("/")
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
            async with httpx.AsyncClient(verify=False, timeout=10) as client:
                resp = await client.get(
                    f"https://{host}/api/v4/projects/{project_id}/merge_requests/{mr_iid}",
                    headers={"PRIVATE-TOKEN": token},
                )
                if resp.is_success:
                    mr_data = resp.json()
                    live_sha = mr_data.get("sha") or (mr_data.get("diff_refs") or {}).get("head_sha")
                    if live_sha:
                        return mr_iid, live_sha
        except Exception as e:
            logger.warning("Failed live GitLab HEAD SHA query for MR !%s: %s", mr_iid, e)

    return mr_iid, fallback_sha


async def _resolve_github_head(gh_ctx: dict) -> tuple[str | None, str | None]:
    pr_number = str(gh_ctx.get("pr_number") or gh_ctx.get("number") or "")
    owner = gh_ctx.get("owner")
    repo = gh_ctx.get("repo")
    fallback_sha = gh_ctx.get("head_sha")

    if not owner or not repo or not pr_number:
        return (pr_number or None, fallback_sha)

    token = os.getenv("GITHUB_TOKEN", "")
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        async with httpx.AsyncClient(verify=False, timeout=10) as client:
            resp = await client.get(
                f"https://api.github.com/repos/{owner}/{repo}/pulls/{pr_number}",
                headers=headers,
            )
            if resp.is_success:
                pr_data = resp.json()
                live_sha = (pr_data.get("head") or {}).get("sha")
                if live_sha:
                    return pr_number, live_sha
    except Exception as e:
        logger.warning("Failed live GitHub HEAD SHA query for PR #%s: %s", pr_number, e)

    return pr_number, fallback_sha
