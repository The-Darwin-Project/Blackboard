# BlackBoard/src/agents/headhunter_gitlab.py
# @ai-rules:
# 1. [Pattern]: Implements VcsPlatformPort for GitLab. All GitLab API calls live here.
# 2. [Constraint]: AIR GAP: No kubernetes imports. GitLab API via httpx only.
# 3. [Pattern]: Dedup by (project_id, mr_iid). Priority-based action selection for multi-todo MRs.
# 4. [Pattern]: Brain-facing methods (refresh_mr_state, poll_gitlab_mr_status, extract_gitlab_state_key)
#    are NOT part of VcsPlatformPort — they're GitLab-specific, accessed via Headhunter delegates.
# 5. [Pattern]: _load_gitlab_si() loads from headhunter_skills/gitlab-mr-triage.md with emergency fallback.
# 6. [Gotcha]: merge_status excluded from state_key (flaps during active pipelines).
# 7. [Pattern]: GITLAB_HOST normalization: strip scheme BEFORE trailing slash.
# 8. [Security]: Persistent httpx.AsyncClient (lazy init, closed via close(), auto-reinitialized on
#    subsequent Brain/StateWatcher calls) uses verify=self._verify (utils/tls.resolve_ca_bundle) and
#    follow_redirects=False. TLS verification is NEVER disabled; __init__ calls resolve_ca_bundle()
#    once so an insecure GITLAB_SSL_VERIFY=false raises ValueError at startup instead of at first poll.
# 9. [Gotcha]: project_id may be a numeric id OR a path ("group/proj", seeded by Kargo gitlab_context). Any
#    URL that interpolates a gitlab_context/StateWatcher project_id MUST go through _enc_project_id()
#    (quote(unquote(...), safe="")); a raw "/" would split the API path.
# 10. [Pattern]: Todo dismissal & feedback lifecycle — open MRs dismiss sibling todo_ids on event close via
#     three-phase post_feedback() (Phase 1 MR comment -> Phase 2 sibling mark_as_done -> Phase 3 live MR
#     SHA update/delete + best-effort darwin-done label -> mark_feedback_sent). stale/duplicate closes skip
#     Phase 1 comment and Phase 3 darwin-done label PUT while still updating/deleting mr_sha so synthetic
#     SHA-sweep events never infinite-loop; transient Phase 3 HTTP/Redis failures return early to retry.
#     Terminal MRs and unauthorized @mentions are best-effort dismissed via _dismiss_todos_best_effort().
"""
GitLab Platform Adapter for Headhunter.

Implements VcsPlatformPort for the GitLab todo polling workflow.
Also exposes Brain-facing methods for refresh_gitlab_context and StateWatcher integration.
"""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING, Any

import httpx

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

from ..utils import vcs_approval as _vcs_approval
from ..utils.prompt_sanitize import sanitize_untrusted_block, sanitize_untrusted_line
from .headhunter_models import PlatformBreakerStatus, PlatformQueueItem, PlatformSnapshot
from .headhunter_utils import BoolOutcome as _QueueResult, _DESC_SAFETY_CAP

logger = logging.getLogger(__name__)

V1_ACTIONABLE = {"assigned", "build_failed", "approval_required", "review_requested", "unmergeable", "directly_addressed"}

ACTION_PRIORITY = {
    "build_failed": 0,
    "unmergeable": 1,
    "assigned": 2,
    "approval_required": 3,
    "review_requested": 3,
    "directly_addressed": 4,
    "mentioned": 5,
    "new_commits": 6,
}

_SHA_SWEEP_MAX_AGE_S = 30 * 86400
_SHA_SWEEP_CONCURRENCY = 5
_WAKEUP_CURSOR_TTL = 7 * 86400


def _valid_positive_int(value: object) -> int | None:
    """Coerce a positive integer (rejecting bool, <=0, and non-numeric values)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        iv = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return iv if iv > 0 else None


def _parse_ts_epoch(value: object) -> float | None:
    """Parse an epoch float/int or ISO-8601 timestamp string to UTC epoch seconds."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value) if value > 0 else None
    if isinstance(value, str):
        s = value.strip()
        if not s:
            return None
        try:
            fv = float(s)
            return fv if fv > 0 else None
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None

MAX_CHANGED_FILES = 20
FAILED_LOG_TAIL = 50
MAX_FAILED_LOG_CHARS = 12000
MAX_CI_NOTES = 10

_SKILLS_DIR = Path(__file__).parent / "headhunter_skills"

_EMERGENCY_SI = """\
You are a triage agent for GitLab MRs. Read the MR context and produce ONLY
a YAML frontmatter plan wrapped in --- delimiters. Nothing else.

```yaml
---
plan: "[Action verb] [target] in [repository]"
service: [component name]
repository: [GitLab project path]
risk: [low|medium|high]
reasoning: "[One sentence -- include any constraints from MR description]"
steps:
  - id: "1"
    agent: [sysadmin|developer|qe|architect|security_analyst|code_reviewer]
    summary: "[What this step accomplishes -- include MR IID, branch, error details]"
---
```

Agents: sysadmin (k8s/gitops), developer (code/MR/pipeline), qe (test/verify), architect (analysis/review), security_analyst (CVE/vulnerability/EC failures/supply chain), code_reviewer (dedicated multi-lens review gate for formal pre-merge quality checks, six parallel subagents merged into one severity-graded report).
Risk drives plan shape: low (1-3 steps), medium (2-4 steps), high (1-2 probe steps).
If the MR description contains "Bot Instructions" or "DARWIN Instructions", those override built-in rules. Parse constraints first.
"""


def _get_static_maintainer_emails() -> list[str]:
    """Read maintainer CSV from env at call time."""
    return [e.strip() for e in os.getenv("HEADHUNTER_MAINTAINERS", "").split(",") if e.strip()]


def _get_allowed_mention_authors() -> set[str]:
    """Build set of lowercased GitLab usernames allowed to instruct Darwin via @mentions."""
    authors: set[str] = set()
    emails = _get_static_maintainer_emails()
    for e in emails:
        if "@" in e:
            user = e.split("@")[0].strip().lower()
            if user:
                authors.add(user)
    explicit = os.getenv("HEADHUNTER_ALLOWED_AUTHORS", "")
    if explicit.strip() == "*":
        return set()
    for name in explicit.split(","):
        name = name.strip().lower()
        if name:
            authors.add(name)
    return authors or {"_nobody_"}


_RETRYABLE_STATUSES = (401, 408, 429)


class GitLabPlatform:
    """GitLab platform adapter implementing VcsPlatformPort.

    Handles: todo polling, MR context fetching, event creation with gitlab_context,
    feedback posting (MR comment + mark_as_done), and Brain-facing state tools.
    """

    def __init__(self, blackboard: "BlackboardState", *, enabled: bool = True):
        self.blackboard = blackboard
        self._enabled_flag = enabled
        self._gitlab_host = _vcs_approval.normalize_gitlab_host(os.getenv("GITLAB_HOST", ""))
        self._client: httpx.AsyncClient | None = None
        self._wakeup_seen_notes_mem: dict[str, set[int]] = {}
        self._wakeup_seen_sha_mem: dict[str, str] = {}
        self._last_snapshot_items: list[PlatformQueueItem] = []
        self._last_poll_at: float | None = None
        self._last_partial_error: str | None = None
        # Fail fast: GITLAB_SSL_VERIFY=false/0/no raises ValueError here, at startup.
        _vcs_approval.resolve_ca_bundle(self._gitlab_host)

    @property
    def _verify(self) -> str | bool:
        return _vcs_approval.resolve_ca_bundle(self._gitlab_host)

    def _get_client(self) -> httpx.AsyncClient:
        """Lazily initialize persistent httpx.AsyncClient; safely re-initializes post-close()."""
        existing = getattr(self, "_client", None)
        if existing is not None and not getattr(existing, "is_closed", False):
            return existing
        client = httpx.AsyncClient(
            verify=self._verify, timeout=30.0, follow_redirects=False,
        )
        if type(client).__module__.startswith("httpx"):
            self._client = client
        return client

    async def close(self) -> None:
        """Close the persistent HTTP client (subsequent Brain calls lazily re-initialize)."""
        client = getattr(self, "_client", None)
        self._client = None
        if client is not None:
            await client.aclose()

    def _invalidate_token(self) -> bool:
        """Invalidate GitLabTokenAuth cache if active (returns True if invalidated)."""
        if self.__dict__.get("_gitlab_token"):
            return False
        try:
            from ..utils.gitlab_token import get_gitlab_auth

            auth = get_gitlab_auth()
            if auth is not None and hasattr(auth, "invalidate"):
                auth.invalidate()
                return True
        except Exception:
            pass
        return False

    async def _send_get(
        self,
        http: httpx.AsyncClient,
        url: str,
        kwargs: dict,
        *,
        allow_reinit: bool,
    ) -> httpx.Response:
        try:
            return await http.get(url, **kwargs)
        except RuntimeError as exc:
            if allow_reinit and "closed" in str(exc).lower():
                if self._client is http:
                    self._client = None
                fresh = self._get_client()
                return await fresh.get(url, **kwargs)
            raise

    async def _get(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        timeout: float | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> httpx.Response:
        """Execute an idempotent GitLab GET with single 401 token-invalidate retry."""
        http = client or self._get_client()
        allow_reinit = client is None
        old_token = self._get_token()
        kwargs: dict = {"headers": {"PRIVATE-TOKEN": old_token}}
        if params is not None:
            kwargs["params"] = params
        if timeout is not None:
            kwargs["timeout"] = timeout
        resp = await self._send_get(http, url, kwargs, allow_reinit=allow_reinit)
        if getattr(resp, "status_code", None) == 401 and self._invalidate_token():
            try:
                new_token = self._get_token()
            except Exception as exc:
                logger.warning(f"GitLabPlatform: post-401 token reload failed: {exc}")
                return resp
            if new_token and new_token != old_token:
                kwargs["headers"] = {"PRIVATE-TOKEN": new_token}
                retry_http = client or self._get_client()
                resp = await self._send_get(retry_http, url, kwargs, allow_reinit=allow_reinit)
        return resp

    @staticmethod
    def _parse_next_page(headers: object, current_page: int) -> int | None:
        """Parse numeric ASCII X-Next-Page header strictly > current_page (never follows Link URLs)."""
        if headers is None or not hasattr(headers, "get"):
            return None
        raw = headers.get("X-Next-Page") or headers.get("x-next-page")
        if not isinstance(raw, str):
            return None
        cleaned = raw.strip()
        if not (cleaned.isascii() and cleaned.isdigit()) or len(cleaned) > 10:
            return None
        nxt = int(cleaned)
        return nxt if nxt > current_page else None

    async def _get_paginated_list(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        max_pages: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> tuple[list[dict], httpx.Response]:
        """Fetch a paginated GitLab list endpoint using bounded numeric X-Next-Page only."""
        items: list[dict] = []
        page = 1
        last_resp: httpx.Response | None = None
        for _ in range(max(1, max_pages)):
            req_params = dict(params) if params else {}
            if page > 1:
                req_params["page"] = str(page)
            resp = await self._get(
                url,
                params=req_params if req_params else None,
                client=client,
            )
            last_resp = resp
            if not resp.is_success:
                if page > 1:
                    logger.warning(
                        "GitLabPlatform: paginated fetch %s failed on page %d with HTTP %s",
                        url,
                        page,
                        getattr(resp, "status_code", "?"),
                    )
                return items, resp
            data = resp.json()
            if isinstance(data, list):
                items.extend(data)
            next_page = self._parse_next_page(getattr(resp, "headers", None), page)
            if next_page is None:
                break
            page = next_page
        assert last_resp is not None
        return items, last_resp

    @staticmethod
    def _enc_project_id(project_id: int | str) -> str:
        """URL-encode a numeric id or path-style project id exactly once (idempotent on %2F).

        Rejects empty values and dot-segments ('.' / '..') after unquoting.
        """
        decoded = urllib.parse.unquote(str(project_id)).strip()
        if not decoded or decoded in (".", "..") or any(seg in (".", "..") for seg in decoded.split("/")):
            raise ValueError(f"Invalid GitLab project_id: {project_id!r}")
        return urllib.parse.quote(decoded, safe="")

    # =========================================================================
    # VcsPlatformPort Implementation
    # =========================================================================

    @property
    def platform_name(self) -> str:
        return "gitlab"

    @staticmethod
    def _work_item_to_snapshot_item(
        item: Any,
        *,
        status: str,
        queue_position: int | None = None,
    ) -> PlatformQueueItem | None:
        wi = GitLabPlatform._unwrap_work_item(item)
        pid, iid = GitLabPlatform._extract_work_item_key(wi)
        if not pid or not iid:
            return None
        project = wi.get("project") if isinstance(wi.get("project"), dict) else {}
        target = wi.get("target") if isinstance(wi.get("target"), dict) else {}
        pipeline = target.get("pipeline") if isinstance(target.get("pipeline"), dict) else {}
        author_obj = target.get("author") if isinstance(target.get("author"), dict) else {}
        project_ref = str(
            project.get("path_with_namespace")
            or wi.get("project_path")
            or getattr(item, "project_ref", "")
            or pid
        )
        title = str(target.get("title") or wi.get("title") or getattr(item, "title", "") or "")
        author = str(
            (author_obj.get("username") if isinstance(author_obj, dict) else "")
            or wi.get("author")
            or getattr(item, "author", "")
            or ""
        )
        url = str(wi.get("target_url") or wi.get("url") or getattr(item, "url", "") or "")
        head_sha = GitLabPlatform._extract_work_item_sha(wi)
        ci_status = str(
            (pipeline.get("status") if isinstance(pipeline, dict) else "")
            or wi.get("ci_status")
            or getattr(item, "ci_status", "")
            or ""
        )
        enqueued_at = str(wi.get("created_at") or wi.get("enqueued_at") or getattr(item, "created_at", "") or "")
        raw: dict[str, Any] = {
            "todo_id": wi.get("id"),
            "_sibling_todo_ids": list(
                wi.get("_sibling_todo_ids") or ([wi.get("id")] if wi.get("id") else [])
            ),
            "action": wi.get("action_name") or getattr(item, "action", None) or "assigned",
            "project_id": pid,
        }
        if target.get("state"):
            raw["mr_state"] = target["state"]
        return PlatformQueueItem(
            platform="gitlab",
            item_kind="mr",
            item_id=iid,
            project_ref=project_ref,
            title=title,
            author=author,
            url=url,
            head_sha=head_sha,
            ci_status=ci_status,
            status=status,
            queue_position=queue_position,
            enqueued_at=enqueued_at,
            raw=raw,
        )

    def get_platform_snapshot(self) -> PlatformSnapshot:
        """Return an immutable-style point-in-time snapshot of GitLab pending/queued items."""
        items = list(getattr(self, "_last_snapshot_items", []))
        queued_count = sum(1 for item in items if item.status == "queued")
        return PlatformSnapshot(
            platform="gitlab",
            enabled=bool(self.enabled()),
            pending_count=len(items),
            queued_count=queued_count,
            last_poll_at=getattr(self, "_last_poll_at", None),
            partial_error=getattr(self, "_last_partial_error", None),
            breaker=PlatformBreakerStatus(),
            items=items,
        )

    async def dismiss_todo(self, todo_id: int | list[int]) -> bool:
        """Dismiss pending GitLab todo(s). Returns True only on HTTP 2xx/304/404; False on 4xx/5xx/error."""
        raw_ids = todo_id if isinstance(todo_id, (list, tuple, set)) else [todo_id]
        tids = list(dict.fromkeys(
            tid for raw_id in raw_ids if (tid := _valid_positive_int(raw_id)) is not None
        ))
        if not tids:
            return False
        try:
            client = self._get_client()
            headers = self._headers()
        except Exception as exc:
            logger.warning("GitLabPlatform: dismiss_todo client/auth init failed (%s)", type(exc).__name__)
            return False

        all_ok = True
        for tid in tids:
            try:
                resp = await client.post(
                    self._api_url(f"/todos/{tid}/mark_as_done"),
                    headers=headers,
                    timeout=10.0,
                )
            except Exception as exc:
                logger.warning("GitLabPlatform: dismiss_todo %s failed (%s)", tid, type(exc).__name__)
                return False
            status = getattr(resp, "status_code", None)
            if status == 401:
                self._invalidate_token()
                logger.warning("GitLabPlatform: dismiss_todo %s returned HTTP 401", tid)
                return False
            if getattr(resp, "is_success", False) or status in (304, 404):
                continue
            logger.warning("GitLabPlatform: dismiss_todo %s returned HTTP %s", tid, status)
            all_ok = False
            if status in (403, 429):
                return False
        return all_ok

    async def dismiss_work_item(
        self,
        project_key: int | str,
        item_number: int,
        *,
        owner: str = "",
        repo: str = "",
        is_issue: bool = False,
        matched_raw: dict[str, Any] | None = None,
        installation_id: str = "",
    ) -> tuple[bool, str]:
        """VcsPlatformPort operator dismiss: dismiss sibling/primary GitLab todo(s)."""
        raw_dict = matched_raw if isinstance(matched_raw, dict) else {}
        todo_ids: list[int] = []
        raw_sibs = raw_dict.get("_sibling_todo_ids")
        if isinstance(raw_sibs, list):
            for raw_tid in raw_sibs:
                tid = _valid_positive_int(raw_tid)
                if tid is not None and tid not in todo_ids:
                    todo_ids.append(tid)
        primary_tid = _valid_positive_int(raw_dict.get("todo_id"))
        if primary_tid is not None and primary_tid not in todo_ids:
            todo_ids.append(primary_tid)
        if not todo_ids:
            return True, ""
        dismiss_arg: int | list[int] = todo_ids[0] if len(todo_ids) == 1 else todo_ids
        ok = await self.dismiss_todo(dismiss_arg)
        if not ok:
            return False, f"Failed to dismiss GitLab todo(s) for MR !{item_number}"
        return True, ""

    async def requeue_work_item(
        self,
        project_key: int | str,
        item_number: int,
        *,
        owner: str = "",
        repo: str = "",
        is_issue: bool = False,
        matched_item: object = None,
        matched_raw: dict[str, Any] | None = None,
        installation_id: str = "",
    ) -> tuple[bool, str]:
        """VcsPlatformPort operator requeue (GitLab queue/SHA state lives in Blackboard Redis)."""
        return True, ""

    def remove_from_snapshot_cache(
        self,
        project_key: int | str,
        item_number: int,
        *,
        owner: str = "",
        repo: str = "",
        is_issue: bool = False,
    ) -> None:
        """Remove (pid, iid) from _last_snapshot_items if present."""
        pid = _valid_positive_int(project_key)
        iid = _valid_positive_int(item_number)
        if not pid or not iid or not hasattr(self, "_last_snapshot_items"):
            return
        self._last_snapshot_items = [
            cur
            for cur in self._last_snapshot_items
            if not (_valid_positive_int(cur.raw.get("project_id")) == pid and cur.item_id == iid)
        ]

    def mark_snapshot_item_queued(
        self,
        project_key: int | str,
        item_number: int,
        *,
        owner: str = "",
        repo: str = "",
        matched_item: object = None,
        is_issue: bool = False,
    ) -> None:
        """Mark (pid, iid) as queued in _last_snapshot_items (or keep position if already queued)."""
        pid = _valid_positive_int(project_key)
        iid = _valid_positive_int(item_number)
        if not pid or not iid or not hasattr(self, "_last_snapshot_items"):
            return
        max_pos = max(
            (cur.queue_position or 0 for cur in self._last_snapshot_items if cur.status == "queued"),
            default=0,
        )
        updated: list[PlatformQueueItem] = []
        found = False
        for cur in self._last_snapshot_items:
            if _valid_positive_int(cur.raw.get("project_id")) == pid and cur.item_id == iid:
                found = True
                pos = cur.queue_position if cur.status == "queued" and cur.queue_position is not None else max_pos + 1
                raw = dict(cur.raw)
                raw.setdefault("action", "queued")
                updated.append(PlatformQueueItem(
                    platform=cur.platform,
                    item_kind=cur.item_kind,
                    item_id=cur.item_id,
                    project_ref=cur.project_ref,
                    title=cur.title,
                    author=cur.author,
                    url=cur.url,
                    head_sha=cur.head_sha,
                    ci_status=cur.ci_status,
                    status="queued",
                    queue_position=pos,
                    enqueued_at=cur.enqueued_at,
                    raw=raw,
                ))
            else:
                updated.append(cur)
        if not found and isinstance(matched_item, PlatformQueueItem):
            raw = dict(matched_item.raw)
            raw.setdefault("action", "queued")
            updated.append(PlatformQueueItem(
                platform=matched_item.platform,
                item_kind=matched_item.item_kind,
                item_id=matched_item.item_id,
                project_ref=matched_item.project_ref,
                title=matched_item.title,
                author=matched_item.author,
                url=matched_item.url,
                head_sha=matched_item.head_sha,
                ci_status=matched_item.ci_status,
                status="queued",
                queue_position=max_pos + 1,
                enqueued_at=matched_item.enqueued_at,
                raw=raw,
            ))
        self._last_snapshot_items = updated

    def enabled(self) -> bool:
        return self._enabled_flag and bool(self._gitlab_host)

    async def get_active_keys(self) -> set[tuple[int, int]]:
        """Get (project_id, mr_iid) for all active/deferred/waiting_approval headhunter events."""
        active_ids = await self.blackboard.get_active_events()
        waiting_ids = await self.blackboard.get_waiting_approval_events()
        keys: set[tuple[int, int]] = set()
        for eid in dict.fromkeys(list(active_ids) + list(waiting_ids)):
            event = await self.blackboard.get_event(eid)
            if not event or event.source != "headhunter":
                continue
            if event.status.value not in ("new", "active", "deferred", "waiting_approval"):
                continue
            ctx = getattr(event.event.evidence, "gitlab_context", None) if event.event and event.event.evidence else None
            if ctx:
                raw_pid = ctx.get("project_id", 0) if isinstance(ctx, dict) else getattr(ctx, "project_id", 0)
                raw_iid = ctx.get("mr_iid", 0) if isinstance(ctx, dict) else getattr(ctx, "mr_iid", 0)
                pid = _valid_positive_int(raw_pid)
                iid = _valid_positive_int(raw_iid)
                if pid and iid:
                    keys.add((pid, iid))
        return keys

    @staticmethod
    def _unwrap_work_item(work_item: Any) -> dict:
        if isinstance(work_item, dict):
            return work_item
        raw = getattr(work_item, "raw", None)
        if isinstance(raw, dict) and raw:
            return raw
        if hasattr(work_item, "to_dict"):
            return work_item.to_dict()
        return {}

    @staticmethod
    def _extract_work_item_key(work_item: Any) -> tuple[int, int]:
        """Extract numeric (project_id, mr_iid) from a GitLab todo, queue dict, or VcsWorkItem."""
        wi = GitLabPlatform._unwrap_work_item(work_item)
        if "project" in wi and "target" in wi:
            pid = _valid_positive_int((wi.get("project") or {}).get("id")) or 0
            iid = _valid_positive_int((wi.get("target") or {}).get("iid")) or 0
            return pid, iid
        pid = _valid_positive_int(wi.get("project_id")) or 0
        iid = _valid_positive_int(wi.get("mr_iid")) or 0
        return pid, iid

    @staticmethod
    def _extract_work_item_sha(work_item: dict) -> str:
        target = work_item.get("target") or {}
        return (
            target.get("sha")
            or (target.get("diff_refs") or {}).get("head_sha")
            or work_item.get("head_sha")
            or ""
        )

    @staticmethod
    def _truncate_work_item_for_queue(work_item: dict) -> dict:
        """Return a shallow copy of work_item with target.description capped to _DESC_SAFETY_CAP."""
        copy_wi = dict(work_item)
        target = copy_wi.get("target")
        if isinstance(target, dict) and isinstance(target.get("description"), str):
            target_copy = dict(target)
            target_copy["description"] = target_copy["description"][:_DESC_SAFETY_CAP]
            copy_wi["target"] = target_copy
        return copy_wi

    @staticmethod
    def _extract_project_path_from_mr(mr_data: dict, fallback_pid: int) -> str:
        refs = mr_data.get("references") or {}
        full_ref = refs.get("full") or ""
        if isinstance(full_ref, str) and "!" in full_ref:
            path = full_ref.split("!", 1)[0].strip()
            if path:
                return path
        web_url = mr_data.get("web_url") or ""
        if "/-/merge_requests/" in web_url:
            prefix = web_url.split("/-/merge_requests/", 1)[0]
            parsed = urllib.parse.urlsplit(prefix)
            path = parsed.path.strip("/")
            if path:
                return path
        return str(fallback_pid)

    async def _enqueue_gitlab_mr(self, pid: int, iid: int, meta: dict) -> bool:
        """Delegate enqueue_gitlab_mr passing ACTION_PRIORITY when supported by the repository."""
        if not hasattr(self.blackboard, "enqueue_gitlab_mr"):
            return True
        try:
            return bool(await self.blackboard.enqueue_gitlab_mr(pid, iid, meta, action_priority=ACTION_PRIORITY))
        except TypeError:
            return bool(await self.blackboard.enqueue_gitlab_mr(pid, iid, meta))

    @staticmethod
    def _is_mention_authorized(work_item: dict) -> bool:
        if work_item.get("action_name", "") not in ("directly_addressed", "mentioned"):
            return True
        author = ((work_item.get("author") or {}).get("username") or "").strip().lower()
        if not author:
            return True
        bot = os.getenv("GITLAB_BOT_USERNAME", "darwin-bot").lower()
        allowed = _get_allowed_mention_authors()
        return author != bot and (not allowed or author in allowed)

    async def _reject_unauthorized_mention(
        self,
        todo_id: Any,
        project_id: int | str,
        mr_iid: int,
        log_msg: str,
    ) -> None:
        """Dismiss own unauthorized mention todo, prune snapshot cache, and log."""
        own_ids = [todo_id] if todo_id is not None else []
        await self._dismiss_todos_best_effort(
            self._get_client(), self._headers(), own_ids, "unauthorized mention",
        )
        self.remove_from_snapshot_cache(project_id, mr_iid)
        logger.info(log_msg)

    async def _drop_stale_mr_from_queue_and_cache(
        self,
        project_id: int | str,
        mr_iid: int,
        log_msg: str | None = None,
    ) -> None:
        """Evict terminal/missing MR from Redis FIFO queue and snapshot cache."""
        if hasattr(self.blackboard, "remove_gitlab_queue"):
            await self.blackboard.remove_gitlab_queue(project_id, mr_iid)
        self.remove_from_snapshot_cache(project_id, mr_iid)
        if log_msg:
            logger.info(log_msg)

    async def queue_item(self, work_item: Any, position: int = 1) -> bool | _QueueResult:
        """Park a GitLab MR work item in Redis FIFO queue and snapshot cache (no MR note to avoid auto-resolving GitLab todos)."""
        wi = self._unwrap_work_item(work_item)
        pid, iid = self._extract_work_item_key(wi)
        if not pid or not iid:
            return False

        if not self._is_mention_authorized(wi):
            await self._reject_unauthorized_mention(
                wi.get("id"),
                pid,
                iid,
                f"GitLabPlatform: queue_item rejected unauthorized mention on !{iid}; dismissed todo [{wi.get('id')}]",
            )
            return _QueueResult(False, permanent=True)

        raw_sibs = wi.get("_sibling_todo_ids")
        sibs = (
            [s for s in (_valid_positive_int(x) for x in raw_sibs) if s is not None]
            if isinstance(raw_sibs, list)
            else ([sid] if (sid := _valid_positive_int(wi.get("id"))) is not None else [])
        )

        # O(1) lookup for existing queue entry before mutating (avoids O(N) list_gitlab_queue scan)
        existing_entry: dict | None = None
        if hasattr(self.blackboard, "get_gitlab_queue_entry"):
            try:
                existing_entry = await self.blackboard.get_gitlab_queue_entry(pid, iid)
            except Exception:
                existing_entry = None
        elif hasattr(self.blackboard, "list_gitlab_queue"):
            try:
                for entry in await self.blackboard.list_gitlab_queue():
                    if _valid_positive_int(entry.get("project_id")) == pid and _valid_positive_int(entry.get("mr_iid")) == iid:
                        existing_entry = entry
                        break
            except Exception:
                pass

        stored_wi = self._truncate_work_item_for_queue(wi)
        meta = {
            "project_id": pid,
            "mr_iid": iid,
            "action_name": wi.get("action_name", "assigned"),
            "head_sha": self._extract_work_item_sha(wi),
            "_sibling_todo_ids": sibs,
            "work_item": stored_wi,
        }
        enqueued = await self._enqueue_gitlab_mr(pid, iid, meta)
        if existing_entry is None and not enqueued:
            return _QueueResult(False, permanent=True)

        snap_item = self._work_item_to_snapshot_item(wi, status="queued", queue_position=position)
        if snap_item is not None:
            existing = list(getattr(self, "_last_snapshot_items", []))
            replaced = False
            updated: list[PlatformQueueItem] = []
            for cur in existing:
                if cur.raw.get("project_id") == pid and cur.item_id == iid:
                    updated.append(snap_item)
                    replaced = True
                else:
                    updated.append(cur)
            if not replaced:
                updated.append(snap_item)
            self._last_snapshot_items = updated
        return True

    async def remove_queued_item(self, work_item: Any) -> None:
        """Remove a GitLab MR work item from the Redis FIFO queue and snapshot cache."""
        pid, iid = self._extract_work_item_key(work_item)
        if pid and iid and hasattr(self.blackboard, "remove_gitlab_queue"):
            try:
                await self.blackboard.remove_gitlab_queue(pid, iid)
            except Exception:
                pass
        if pid and iid:
            self.remove_from_snapshot_cache(pid, iid)

    async def get_queued_items(self) -> list[dict]:
        """Return queued GitLab work items in FIFO order from Redis."""
        if not hasattr(self.blackboard, "list_gitlab_queue"):
            return []
        entries = await self.blackboard.list_gitlab_queue()
        items: list[dict] = []
        for entry in entries:
            wi = entry.get("work_item")
            if isinstance(wi, dict):
                item = dict(wi)
                if entry.get("_sibling_todo_ids") is not None:
                    item["_sibling_todo_ids"] = list(entry["_sibling_todo_ids"])
                if entry.get("action_name"):
                    item["action_name"] = entry["action_name"]
                item["queued"] = True
                items.append(item)
            else:
                item = dict(entry)
                item["queued"] = True
                items.append(item)
        return items

    async def _sweep_gitlab_mr_shas(
        self,
        active_mr_keys: set[tuple[int, int]],
        seen_keys: set[tuple[int, int]],
    ) -> list[dict]:
        """Bounded live-HEAD sweep ONLY for MRs tracked in darwin:gitlab:mr_sha (zero scope=all)."""
        if not hasattr(self.blackboard, "get_all_gitlab_mr_shas"):
            return []
        all_shas = await self.blackboard.get_all_gitlab_mr_shas()
        if not all_shas:
            return []

        now = time.time()
        try:
            max_entries = max(1, int(os.getenv("HEADHUNTER_GITLAB_SHA_MAX_ENTRIES", "500")))
        except (TypeError, ValueError):
            max_entries = 500

        valid_entries: list[tuple[int, int, str, float]] = []
        for member, info in all_shas.items():
            try:
                pid_s, iid_s = str(member).split(":", 1)
                pid = _valid_positive_int(pid_s)
                iid = _valid_positive_int(iid_s)
            except (TypeError, ValueError):
                continue
            if not pid or not iid:
                continue
            sha = info.get("sha") if isinstance(info, dict) else str(info or "")
            try:
                recorded_at = float(info.get("recorded_at") or 0.0) if isinstance(info, dict) else 0.0
            except (TypeError, ValueError):
                recorded_at = 0.0
            if recorded_at > 0 and (now - recorded_at) > _SHA_SWEEP_MAX_AGE_S:
                try:
                    await self.blackboard.delete_gitlab_mr_sha(pid, iid)
                except Exception:
                    pass
                continue
            valid_entries.append((pid, iid, str(sha or ""), recorded_at))

        if len(valid_entries) > max_entries:
            valid_entries.sort(key=lambda e: e[3])
            excess = len(valid_entries) - max_entries
            for pid, iid, _, _ in valid_entries[:excess]:
                try:
                    await self.blackboard.delete_gitlab_mr_sha(pid, iid)
                except Exception:
                    pass
            valid_entries = valid_entries[excess:]

        candidates = [
            (pid, iid, sha)
            for pid, iid, sha, _ in valid_entries
            if (pid, iid) not in active_mr_keys and (pid, iid) not in seen_keys
        ]
        if not candidates:
            return []

        sem = asyncio.Semaphore(_SHA_SWEEP_CONCURRENCY)
        rate_limited = asyncio.Event()

        async def _check_one(pid: int, iid: int, stored_sha: str) -> dict | None:
            if rate_limited.is_set():
                return None
            async with sem:
                if rate_limited.is_set():
                    return None
                enc_pid = self._enc_project_id(pid)
                try:
                    resp = await self._get(
                        self._api_url(f"/projects/{enc_pid}/merge_requests/{iid}"),
                    )
                except Exception as exc:
                    logger.debug(f"GitLabPlatform: SHA sweep GET failed for {pid}!{iid}: {exc}")
                    return None
                if resp.status_code == 429:
                    rate_limited.set()
                    logger.warning("GitLabPlatform: SHA sweep hit HTTP 429; aborting remaining checks")
                    return None
                if resp.status_code == 404:
                    try:
                        await self.blackboard.delete_gitlab_mr_sha(pid, iid)
                    except Exception as exc:
                        logger.debug(f"GitLabPlatform: delete_gitlab_mr_sha failed for {pid}!{iid}: {exc}")
                    return None
                if resp.status_code == 403:
                    logger.debug(f"GitLabPlatform: SHA sweep 403 for {pid}!{iid} (skipping without strike)")
                    return None
                if not resp.is_success:
                    return None
                try:
                    mr_data = resp.json()
                except ValueError:
                    return None
                if not isinstance(mr_data, dict):
                    return None
                mr_state = mr_data.get("state", "")
                if mr_state in ("merged", "closed"):
                    try:
                        await self.blackboard.delete_gitlab_mr_sha(pid, iid)
                    except Exception as exc:
                        logger.debug(f"GitLabPlatform: delete_gitlab_mr_sha failed for {pid}!{iid}: {exc}")
                    return None
                live_sha = mr_data.get("sha") or (mr_data.get("diff_refs") or {}).get("head_sha") or ""
                if not (stored_sha and live_sha and live_sha != stored_sha):
                    return None

                # Best-effort remove visual darwin-done label on re-trigger (403 tolerated)
                try:
                    labels = mr_data.get("labels") or []
                    if not labels or "darwin-done" in labels:
                        await self._get_client().put(
                            self._api_url(f"/projects/{enc_pid}/merge_requests/{iid}"),
                            headers=self._headers(),
                            json={"remove_labels": "darwin-done"},
                        )
                except Exception:
                    pass

                live_pid = _valid_positive_int(mr_data.get("project_id")) or pid
                return self._build_synthetic_work_item(mr_data, live_pid, iid, live_sha)

        results = await asyncio.gather(
            *(_check_one(p, i, s) for p, i, s in candidates),
            return_exceptions=True,
        )
        items: list[dict] = []
        for r in results:
            if isinstance(r, BaseException):
                logger.warning(f"GitLabPlatform: SHA sweep worker raised: {r}")
            elif r is not None:
                items.append(r)
        return items

    @classmethod
    def _build_synthetic_work_item(
        cls,
        mr_data: dict,
        pid: int,
        iid: int,
        live_sha: str,
        *,
        action_name: str = "new_commits",
    ) -> dict:
        """Construct a synthetic todo-shaped work_item dict from a GitLab MR payload."""
        live_pid = _valid_positive_int(mr_data.get("project_id")) or pid
        project_path = cls._extract_project_path_from_mr(mr_data, live_pid)
        mr_state = mr_data.get("state") or "opened"
        return {
            "id": None,
            "action_name": action_name,
            "created_at": mr_data.get("updated_at") or "",
            "target_type": "MergeRequest",
            "target_url": mr_data.get("web_url") or "",
            "project": {
                "id": live_pid,
                "path_with_namespace": project_path,
            },
            "target": {
                "iid": iid,
                "title": mr_data.get("title") or f"MR !{iid}",
                "state": mr_state,
                "sha": live_sha,
                "diff_refs": {"head_sha": live_sha},
                "merge_status": mr_data.get("detailed_merge_status") or mr_data.get("merge_status") or "",
                "source_branch": mr_data.get("source_branch") or "",
                "target_branch": mr_data.get("target_branch") or "",
                "description": (mr_data.get("description") or "")[:_DESC_SAFETY_CAP],
                "author": mr_data.get("author") or {},
                "labels": mr_data.get("labels") or [],
                "milestone": mr_data.get("milestone"),
            },
            "_sibling_todo_ids": [],
            "_synthetic_sha_sweep": True,
        }

    async def poll_work_items(self) -> list[dict]:
        """Fetch pending GitLab todos, reconcile FIFO queue, and run bounded SHA sweep."""
        all_todos: list[dict] = []
        page = 1
        per_page = 100
        max_pages = 20
        while page <= max_pages:
            resp = await self._get(
                self._api_url("/todos"),
                params={
                    "state": "pending", "type": "MergeRequest",
                    "sort": "asc", "page": str(page), "per_page": str(per_page),
                },
            )
            resp.raise_for_status()
            batch = resp.json()
            all_todos.extend(batch)
            if len(batch) < per_page:
                break
            page += 1
        else:
            logger.warning(f"GitLabPlatform: hit max_pages ({max_pages}), {len(all_todos)} todos fetched")

        actionable = [t for t in all_todos if t.get("action_name") in V1_ACTIONABLE]
        actionable.sort(key=lambda t: t.get("created_at", ""))

        active_mr_keys = await self.get_active_keys()
        grouped = self._group_by_mr(actionable)
        allowed_mention_authors = _get_allowed_mention_authors()
        darwin_bot_lower = os.getenv("GITLAB_BOT_USERNAME", "darwin-bot").lower()

        def _todo_selection_key(t: dict) -> tuple[int, int]:
            action_name = t.get("action_name", "")
            prio = ACTION_PRIORITY.get(action_name, 99)
            if action_name in ("directly_addressed", "mentioned"):
                author = ((t.get("author") or {}).get("username") or "").strip().lower()
                if not author:
                    return (prio, 1)
                if author == darwin_bot_lower or (
                    allowed_mention_authors and author not in allowed_mention_authors
                ):
                    return (prio + 10, 2)
                return (prio, 0)
            return (prio, 0)

        live_by_key: dict[tuple[int, int], dict] = {}
        skipped_terminal = 0
        terminal_todo_ids: list[int] = []
        unauthorized_todo_ids: list[int] = []
        for key, group in grouped.items():
            if key in active_mr_keys:
                continue
            best = min(group, key=_todo_selection_key)
            mr_state = best.get("target", {}).get("state", "")
            if mr_state in ("merged", "closed"):
                skipped_terminal += 1
                terminal_todo_ids.extend(t["id"] for t in group if t.get("id"))
                logger.debug(f"GitLabPlatform: skipping terminal MR {key} (state={mr_state})")
                continue
            if best.get("action_name") in ("directly_addressed", "mentioned") and not self._is_mention_authorized(best):
                todo_author = ((best.get("author") or {}).get("username") or "").strip()
                if best.get("id") is not None:
                    unauthorized_todo_ids.append(best["id"])
                logger.info(
                    f"GitLabPlatform: dropping unauthorized @{os.getenv('GITLAB_BOT_USERNAME', 'darwin-bot')} "
                    f"todo from {todo_author or 'unknown'} on {key}; queuing todo [{best.get('id')}] for dismissal"
                )
                continue
            best["_sibling_todo_ids"] = [t["id"] for t in group if t.get("id") is not None]
            live_by_key[key] = best

        if terminal_todo_ids:
            try:
                await self._dismiss_todos_best_effort(
                    self._get_client(), self._headers(), terminal_todo_ids, "terminal MR",
                )
            except Exception as exc:
                logger.debug(f"GitLabPlatform: best-effort terminal todo cleanup failed: {exc}")

        if unauthorized_todo_ids:
            try:
                await self._dismiss_todos_best_effort(
                    self._get_client(), self._headers(), unauthorized_todo_ids, "unauthorized mention",
                )
            except Exception as exc:
                logger.debug(f"GitLabPlatform: best-effort unauthorized todo cleanup failed: {exc}")

        # Reconcile Redis FIFO queue against live todos
        reconciled_queued: list[dict] = []
        reconciled_keys: set[tuple[int, int]] = set()
        if hasattr(self.blackboard, "list_gitlab_queue"):
            queued_entries = await self.blackboard.list_gitlab_queue()
            ordered_slots: list[dict | None] = [None] * len(queued_entries)
            synthetic_tasks: list[tuple[int, int, int, dict]] = []
            for idx, qentry in enumerate(queued_entries):
                pid = _valid_positive_int(qentry.get("project_id"))
                iid = _valid_positive_int(qentry.get("mr_iid"))
                if not pid or not iid:
                    continue
                key = (pid, iid)
                if key in active_mr_keys:
                    await self.blackboard.remove_gitlab_queue(pid, iid)
                    continue
                if key in live_by_key:
                    live_item = live_by_key[key]
                    q_sibs = qentry.get("_sibling_todo_ids") if isinstance(qentry.get("_sibling_todo_ids"), list) else []
                    l_sibs = live_item.get("_sibling_todo_ids") if isinstance(live_item.get("_sibling_todo_ids"), list) else []
                    merged_sibs = list(dict.fromkeys(
                        [s for s in (_valid_positive_int(x) for x in q_sibs) if s is not None]
                        + [s for s in (_valid_positive_int(x) for x in l_sibs) if s is not None]
                    ))
                    live_item["_sibling_todo_ids"] = merged_sibs
                    q_action = qentry.get("action_name")
                    l_action = live_item.get("action_name", "assigned")
                    if q_action and ACTION_PRIORITY.get(str(q_action), 99) < ACTION_PRIORITY.get(str(l_action), 99):
                        live_item["action_name"] = q_action
                    live_item["queued"] = True
                    await self._enqueue_gitlab_mr(
                        pid,
                        iid,
                        {
                            "project_id": pid,
                            "mr_iid": iid,
                            "action_name": live_item.get("action_name", "assigned"),
                            "head_sha": self._extract_work_item_sha(live_item),
                            "_sibling_todo_ids": merged_sibs,
                            "work_item": self._truncate_work_item_for_queue(live_item),
                            "comment_posted": bool(qentry.get("comment_posted", False)),
                        },
                    )
                    ordered_slots[idx] = live_item
                    reconciled_keys.add(key)
                elif qentry.get("action_name") == "new_commits" and not qentry.get("_sibling_todo_ids"):
                    synthetic_tasks.append((idx, pid, iid, qentry))
                else:
                    # Todo dismissed or MR merged/closed -> evict from FIFO queue
                    await self.blackboard.remove_gitlab_queue(pid, iid)

            if synthetic_tasks:
                synth_sem = asyncio.Semaphore(_SHA_SWEEP_CONCURRENCY)

                async def _reconcile_synthetic(slot_idx: int, pid: int, iid: int, qentry: dict) -> None:
                    async with synth_sem:
                        enc_pid = self._enc_project_id(pid)
                        still_open = True
                        refreshed_sha = ""
                        mr_data: dict | None = None
                        try:
                            mr_resp = await self._get(self._api_url(f"/projects/{enc_pid}/merge_requests/{iid}"))
                            if mr_resp.status_code == 404:
                                still_open = False
                            elif mr_resp.is_success:
                                parsed = mr_resp.json()
                                if isinstance(parsed, dict):
                                    mr_data = parsed
                                    if mr_data.get("state") in ("merged", "closed"):
                                        still_open = False
                                    else:
                                        refreshed_sha = (
                                            mr_data.get("sha")
                                            or (mr_data.get("diff_refs") or {}).get("head_sha")
                                            or ""
                                        )
                        except Exception:
                            still_open = True
                        if still_open:
                            wi = dict(qentry["work_item"]) if isinstance(qentry.get("work_item"), dict) else None
                            if wi is None and qentry.get("action_name") == "new_commits":
                                live_sha = refreshed_sha or str(qentry.get("head_sha") or "")
                                if isinstance(mr_data, dict):
                                    wi = self._build_synthetic_work_item(
                                        mr_data, pid, iid, live_sha, action_name="new_commits",
                                    )
                                else:
                                    wi = {
                                        "id": None,
                                        "action_name": "new_commits",
                                        "created_at": "",
                                        "target_type": "MergeRequest",
                                        "target_url": "",
                                        "project": {"id": pid, "path_with_namespace": str(pid)},
                                        "target": {
                                            "iid": iid,
                                            "title": f"MR !{iid}",
                                            "state": "opened",
                                            "sha": live_sha,
                                            "diff_refs": {"head_sha": live_sha} if live_sha else {},
                                        },
                                        "_sibling_todo_ids": [],
                                        "_synthetic_sha_sweep": True,
                                    }
                            if wi is not None:
                                if refreshed_sha:
                                    target = dict(wi.get("target") or {})
                                    target["sha"] = refreshed_sha
                                    target["diff_refs"] = {"head_sha": refreshed_sha}
                                    wi["target"] = target
                                    wi["head_sha"] = refreshed_sha
                                wi["queued"] = True
                                ordered_slots[slot_idx] = wi
                                reconciled_keys.add((pid, iid))
                                return
                        await self.blackboard.remove_gitlab_queue(pid, iid)

                synth_results = await asyncio.gather(
                    *(_reconcile_synthetic(i, p, m, qe) for i, p, m, qe in synthetic_tasks),
                    return_exceptions=True,
                )
                for sr in synth_results:
                    if isinstance(sr, BaseException):
                        logger.warning(f"GitLabPlatform: synthetic queue reconcile error: {sr}")

            reconciled_queued = [item for item in ordered_slots if item is not None]

        new_items = [item for key, item in live_by_key.items() if key not in reconciled_keys]
        new_items.sort(key=lambda t: t.get("created_at", ""))

        seen_keys = reconciled_keys | set(live_by_key.keys())
        sweep_items = await self._sweep_gitlab_mr_shas(active_mr_keys, seen_keys)

        result = reconciled_queued + new_items + sweep_items
        snapshot_items: list[PlatformQueueItem] = []
        for idx, q_item in enumerate(reconciled_queued, start=1):
            snap_q = self._work_item_to_snapshot_item(q_item, status="queued", queue_position=idx)
            if snap_q is not None:
                snapshot_items.append(snap_q)
        for p_item in new_items + sweep_items:
            snap_p = self._work_item_to_snapshot_item(p_item, status="pending", queue_position=None)
            if snap_p is not None:
                snapshot_items.append(snap_p)
        self._last_snapshot_items = snapshot_items
        self._last_poll_at = time.time()
        self._last_partial_error = None
        logger.info(
            f"GitLab poll: {len(all_todos)} total, {len(actionable)} actionable, "
            f"{len(active_mr_keys)} active, {skipped_terminal} terminal, "
            f"{len(reconciled_queued)} queued, {len(new_items)} new, {len(sweep_items)} sha_retrigger"
        )
        return result

    async def _get_wakeup_sha(self, event_id: str) -> str | None:
        if hasattr(self.blackboard, "get_wakeup_sha"):
            return await self.blackboard.get_wakeup_sha("gitlab", event_id)
        return self._wakeup_seen_sha_mem.get(event_id)

    async def _set_wakeup_sha(self, event_id: str, sha: str) -> None:
        if hasattr(self.blackboard, "set_wakeup_sha"):
            await self.blackboard.set_wakeup_sha("gitlab", event_id, sha, ttl_s=_WAKEUP_CURSOR_TTL)
        else:
            self._wakeup_seen_sha_mem[event_id] = sha

    async def _is_wakeup_note_seen(self, event_id: str, note_id: str) -> bool:
        if hasattr(self.blackboard, "is_wakeup_note_seen"):
            return await self.blackboard.is_wakeup_note_seen("gitlab", event_id, note_id)
        return str(note_id) in {str(x) for x in self._wakeup_seen_notes_mem.get(event_id, set())}

    async def _mark_wakeup_notes_seen(self, event_id: str, note_ids: list[str]) -> None:
        if not note_ids:
            return
        if hasattr(self.blackboard, "mark_wakeup_notes_seen"):
            await self.blackboard.mark_wakeup_notes_seen("gitlab", event_id, note_ids, ttl_s=_WAKEUP_CURSOR_TTL)
        else:
            seen_set = self._wakeup_seen_notes_mem.setdefault(event_id, set())
            for nid_str in note_ids:
                try:
                    seen_set.add(int(nid_str))
                except (TypeError, ValueError):
                    pass

    async def poll_active_events_wakeup(self) -> int:
        """Poll active/deferred/waiting_approval GitLab MR events for allowlisted notes & hex-SHA pushes."""
        from ..models import ConversationTurn

        active_ids = await self.blackboard.get_active_events()
        waiting_ids = await self.blackboard.get_waiting_approval_events()
        event_ids = list(dict.fromkeys(list(active_ids) + list(waiting_ids)))
        if not event_ids:
            return 0

        allowed_authors = _get_allowed_mention_authors()
        darwin_bot_lower = os.getenv("GITLAB_BOT_USERNAME", "darwin-bot").lower()
        appended_count = 0

        for eid in event_ids:
            try:
                event = await self.blackboard.get_event(eid)
            except Exception:
                continue
            if not event or not getattr(event, "event", None) or not getattr(event.event, "evidence", None):
                continue
            status_val = event.status.value if hasattr(event.status, "value") else str(event.status)
            if status_val not in ("active", "deferred", "waiting_approval"):
                continue
            gl_ctx = getattr(event.event.evidence, "gitlab_context", None)
            if not isinstance(gl_ctx, dict):
                continue
            project_id = gl_ctx.get("project_id")
            mr_iid = _valid_positive_int(gl_ctx.get("mr_iid"))
            if not project_id or not mr_iid:
                continue

            try:
                enc_pid = self._enc_project_id(project_id)
            except ValueError:
                continue

            # 1. Live HEAD SHA check (push wake-up + active approval drift clearing)
            try:
                mr_resp = await self._get(
                    self._api_url(f"/projects/{enc_pid}/merge_requests/{mr_iid}"),
                )
                if mr_resp.is_success:
                    mr_data = mr_resp.json()
                    if isinstance(mr_data, dict):
                        live_sha = (
                            mr_data.get("sha")
                            or (mr_data.get("diff_refs") or {}).get("head_sha")
                            or ""
                        )
                        if isinstance(live_sha, str) and _vcs_approval.HEX_SHA_RE.match(live_sha):
                            # Unconditionally clear stale active/deferred approval even if refresh_mr_state updated ctx head_sha
                            approved_sha = getattr(event, "approved_mr_sha", None)
                            if (
                                status_val in ("active", "deferred")
                                and isinstance(approved_sha, str)
                                and approved_sha
                                and live_sha != approved_sha
                                and hasattr(self.blackboard, "clear_event_approval")
                            ):
                                await self.blackboard.clear_event_approval(eid)

                            prev_sha = await self._get_wakeup_sha(eid)
                            if not prev_sha:
                                prev_sha = gl_ctx.get("head_sha") or gl_ctx.get("sha") or ""

                            if prev_sha and live_sha != prev_sha:
                                if status_val in ("active", "deferred") and (
                                    getattr(event, "approved_by", None)
                                    or getattr(event, "approved_mr_sha", None)
                                ):
                                    if hasattr(self.blackboard, "clear_event_approval"):
                                        await self.blackboard.clear_event_approval(eid)

                                push_turn = ConversationTurn(
                                    turn=0,
                                    actor="headhunter",
                                    action="evidence",
                                    thoughts=f"New commits pushed to GitLab MR !{mr_iid} (HEAD: {live_sha[:8]})",
                                    evidence=f"GitLab MR !{mr_iid} HEAD updated to {live_sha}",
                                )
                                try:
                                    await self.blackboard.append_turn(eid, push_turn)
                                except Exception as exc:
                                    logger.warning(f"GitLab wake-up push turn write failed for {eid}: {exc}")
                                else:
                                    if hasattr(self.blackboard, "update_event_gitlab_context"):
                                        try:
                                            await self.blackboard.update_event_gitlab_context(
                                                eid, {"head_sha": live_sha, "sha": live_sha},
                                            )
                                        except Exception:
                                            pass
                                    await self._set_wakeup_sha(eid, live_sha)
                                    appended_count += 1
                            elif not prev_sha:
                                await self._set_wakeup_sha(eid, live_sha)
            except Exception as exc:
                logger.debug(f"GitLab wake-up MR fetch failed for {eid}: {exc}")

            # 2. Allowlisted human notes check (deduped via EventRepository notes cursor)
            try:
                notes_resp = await self._get(
                    self._api_url(f"/projects/{enc_pid}/merge_requests/{mr_iid}/notes"),
                    params={"sort": "desc", "per_page": "20"},
                )
                if not notes_resp.is_success:
                    continue
                notes_data = notes_resp.json()
                if not isinstance(notes_data, list):
                    continue

                baseline_ts = _parse_ts_epoch(getattr(event, "queued_at", None)) or _parse_ts_epoch(
                    getattr(getattr(event, "event", None), "timeDate", None)
                )
                new_formatted: list[str] = []
                new_note_ids: list[str] = []
                historical_note_ids: list[str] = []

                for note in notes_data:
                    if not isinstance(note, dict) or note.get("system"):
                        continue
                    note_id = note.get("id")
                    if note_id is None:
                        continue
                    author_obj = note.get("author") or {}
                    if isinstance(author_obj, dict) and author_obj.get("bot") is True:
                        continue
                    author_raw = (author_obj.get("username") or "").strip() if isinstance(author_obj, dict) else ""
                    author_lower = author_raw.lower()
                    if not author_lower or author_lower == darwin_bot_lower:
                        continue
                    # Fail closed: never allow empty/* allowlist to open wake-up note ingestion
                    if not allowed_authors or author_lower not in allowed_authors:
                        continue

                    nid_str = str(note_id)
                    if await self._is_wakeup_note_seen(eid, nid_str):
                        continue

                    note_ts = _parse_ts_epoch(note.get("created_at"))
                    if baseline_ts is not None and note_ts is not None and note_ts < (baseline_ts - 1.0):
                        historical_note_ids.append(nid_str)
                        continue

                    safe_author = sanitize_untrusted_line(author_raw, max_len=80)
                    safe_body = sanitize_untrusted_block(note.get("body") or "", max_len=2000)
                    if not safe_body.strip():
                        continue
                    new_note_ids.append(nid_str)
                    new_formatted.append(f"[{safe_author}]: {safe_body}")

                if historical_note_ids:
                    await self._mark_wakeup_notes_seen(eid, historical_note_ids)

                if new_formatted:
                    chronological = list(reversed(new_formatted))
                    framed = (
                        f"New GitLab MR !{mr_iid} human comment(s) (untrusted data):\n"
                        f"<comments>\n" + "\n\n".join(chronological) + "\n</comments>"
                    )
                    note_turn = ConversationTurn(
                        turn=0,
                        actor="headhunter",
                        action="evidence",
                        thoughts=f"New allowlisted comment on GitLab MR !{mr_iid}",
                        evidence=framed,
                    )
                    try:
                        await self.blackboard.append_turn(eid, note_turn)
                    except Exception as exc:
                        logger.warning(f"GitLab wake-up note turn write failed for {eid}: {exc}")
                    else:
                        await self._mark_wakeup_notes_seen(eid, new_note_ids)
                        appended_count += 1
            except Exception as exc:
                logger.debug(f"GitLab wake-up notes fetch failed for {eid}: {exc}")

        return appended_count

    async def _dismiss_todos_best_effort(
        self,
        client: httpx.AsyncClient,
        headers: dict[str, str],
        todo_ids: list[int],
        reason: str,
        *,
        max_items: int = 20,
        timeout: float = 10.0,
    ) -> None:
        """Best-effort bounded todo dismissal; stops early on 401, 403, 429, or timeout."""
        for tid in todo_ids[:max_items]:
            try:
                dismiss_resp = await client.post(
                    self._api_url(f"/todos/{tid}/mark_as_done"),
                    headers=headers,
                    timeout=timeout,
                )
                if dismiss_resp.status_code == 401:
                    self._invalidate_token()
                    logger.debug(
                        f"GitLabPlatform: stopping {reason} todo dismissal after HTTP 401 on todo {tid}"
                    )
                    break
                if dismiss_resp.status_code in (403, 429):
                    logger.debug(
                        f"GitLabPlatform: stopping {reason} todo dismissal after HTTP {dismiss_resp.status_code} on todo {tid}"
                    )
                    break
                if not dismiss_resp.is_success:
                    logger.debug(
                        f"GitLabPlatform: best-effort {reason} todo {tid} dismiss returned {dismiss_resp.status_code}"
                    )
            except httpx.TimeoutException as exc:
                logger.debug(f"GitLabPlatform: stopping {reason} todo dismissal after timeout on todo {tid}: {exc}")
                break
            except Exception as exc:
                logger.debug(f"GitLabPlatform: best-effort {reason} todo {tid} dismiss failed: {exc}")

    async def _fetch_latest_pipeline(
        self,
        enc_pid: str,
        mr_iid: int,
        source_branch: str,
    ) -> list[dict]:
        """Fetch latest MR pipeline (single GET, per_page=1) with guarded branch-ref fallback."""
        pipelines: list[dict] = []
        try:
            mr_pipe_resp = await self._get(
                self._api_url(f"/projects/{enc_pid}/merge_requests/{mr_iid}/pipelines"),
                params={"per_page": "1"},
            )
            if mr_pipe_resp.is_success:
                data = mr_pipe_resp.json()
                if isinstance(data, list):
                    pipelines = data
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(f"GitLabPlatform: MR !{mr_iid} pipeline fetch failed (falling back): {exc}")

        if not pipelines and source_branch:
            try:
                pipe_resp = await self._get(
                    self._api_url(f"/projects/{enc_pid}/pipelines"),
                    params={"ref": source_branch, "order_by": "updated_at", "per_page": "1"},
                )
                if pipe_resp.is_success:
                    data = pipe_resp.json()
                    if isinstance(data, list):
                        pipelines = data
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    f"GitLabPlatform: branch pipeline fallback failed for !{mr_iid} (ref={source_branch}): {exc}"
                )
        return pipelines

    async def _fetch_failed_job_log(
        self,
        enc_pid: str,
        pipe_id: int,
        context: dict,
    ) -> str:
        """Fetch failed pipeline jobs (paginated via X-Next-Page) and tail traces; isolates per-job errors."""
        try:
            all_jobs, jobs_resp = await self._get_paginated_list(
                self._api_url(f"/projects/{enc_pid}/pipelines/{pipe_id}/jobs"),
                params={"per_page": "100"},
                max_pages=10,
            )
            if not jobs_resp.is_success:
                return ""
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(f"GitLabPlatform: failed jobs fetch failed for pipeline {pipe_id}: {exc}")
            return ""

        failed_jobs = [j for j in all_jobs if isinstance(j, dict) and j.get("status") == "failed"]
        context["failed_job_count"] = len(failed_jobs)
        context["total_job_count"] = len(all_jobs)
        if not failed_jobs:
            return ""

        context["failed_job_names"] = [j.get("name", "unknown") for j in failed_jobs]
        job_traces: list[tuple[str, str]] = []
        for job in failed_jobs[:3]:
            job_id = job.get("id")
            if not job_id:
                continue
            try:
                trace_resp = await self._get(
                    self._api_url(f"/projects/{enc_pid}/jobs/{job_id}/trace"),
                )
                if trace_resp.is_success:
                    lines = trace_resp.text.splitlines()
                    tail = "\n".join(lines[-FAILED_LOG_TAIL:])
                    job_traces.append((job.get("name", "unknown"), tail))
            except (httpx.HTTPError, ValueError) as exc:
                logger.warning(
                    f"GitLabPlatform: trace fetch failed for job {job_id} (pipeline {pipe_id}): {exc}"
                )
        if not job_traces:
            return ""

        sep = "\n\n"
        section_headers = [f"=== Job: {name} ===\n" for name, _ in job_traces]
        overhead = sum(len(h) for h in section_headers) + len(sep) * (len(job_traces) - 1)
        per_job_budget = max(0, MAX_FAILED_LOG_CHARS - overhead) // len(job_traces)
        sections = []
        for hdr, (_, tail) in zip(section_headers, job_traces):
            if per_job_budget <= 0:
                body_part = ""
            elif len(tail) > per_job_budget:
                body_part = tail[-per_job_budget:]
            else:
                body_part = tail
            sections.append(f"{hdr}{body_part}")
        return sep.join(sections)[:MAX_FAILED_LOG_CHARS]

    async def fetch_context(self, work_item: dict) -> dict | None:
        """Enrich GitLab todo with MR diff, pipeline status, failed job log, CI notes."""
        todo = work_item
        target = todo.get("target", {})
        project_id = todo["project"]["id"]
        enc_pid = self._enc_project_id(project_id)
        mr_iid = target["iid"]
        action = todo["action_name"]

        context: dict = {
            "action_name": action,
            "mr_iid": target.get("iid"),
            "mr_title": target.get("title", ""),
            "mr_description": (target.get("description") or "")[:_DESC_SAFETY_CAP],
            "mr_state": target.get("state", ""),
            "merge_status": target.get("detailed_merge_status") or target.get("merge_status", ""),
            "source_branch": target.get("source_branch", ""),
            "target_branch": target.get("target_branch", ""),
            "author": target.get("author", {}).get("username", ""),
            "labels": target.get("labels", []),
            "milestone": (target.get("milestone") or {}).get("title"),
            "project_path": todo["project"].get("path_with_namespace", ""),
            "target_url": todo.get("target_url", "").split("#")[0],
        }

        darwin_bot = os.getenv("GITLAB_BOT_USERNAME", "darwin-bot")
        darwin_bot_lower = darwin_bot.lower()
        is_mention_action = action in ("directly_addressed", "mentioned")
        allowed_authors = _get_allowed_mention_authors() if is_mention_action else set()
        own_todo_ids = [work_item["id"]] if work_item.get("id") else []

        if not self._is_mention_authorized(work_item):
            todo_author = ((work_item.get("author") or {}).get("username") or "").strip()
            await self._reject_unauthorized_mention(
                work_item.get("id"),
                project_id,
                mr_iid,
                f"GitLabPlatform: rejecting @{darwin_bot} todo from unauthorized author "
                f"{todo_author} on !{mr_iid}; dismissed todo {own_todo_ids}",
            )
            return None

        # Live MR freshness guard: skip stale/mid-flight merged or closed MRs cleanly
        mr_404_empty = False
        try:
            mr_resp = await self._get(
                self._api_url(f"/projects/{enc_pid}/merge_requests/{mr_iid}"),
            )
            if mr_resp.status_code == 404:
                if mr_resp.content:
                    await self._drop_stale_mr_from_queue_and_cache(
                        project_id, mr_iid,
                        f"GitLabPlatform: MR !{mr_iid} returned 404 during fetch_context; skipping",
                    )
                    return None
                mr_404_empty = True
            elif mr_resp.is_success:
                mr_data = mr_resp.json()
                if isinstance(mr_data, dict):
                    live_state = mr_data.get("state", "")
                    if live_state in ("merged", "closed"):
                        await self._drop_stale_mr_from_queue_and_cache(
                            project_id, mr_iid,
                            f"GitLabPlatform: MR !{mr_iid} became {live_state} mid-flight; skipping",
                        )
                        return None
                    if live_state:
                        context["mr_state"] = live_state
                    live_merge = mr_data.get("detailed_merge_status") or mr_data.get("merge_status")
                    if live_merge:
                        context["merge_status"] = live_merge
                    live_sha = mr_data.get("sha") or (mr_data.get("diff_refs") or {}).get("head_sha")
                    if live_sha:
                        context["head_sha"] = live_sha
        except Exception as exc:
            logger.debug(f"GitLabPlatform: live MR freshness check skipped for !{mr_iid}: {exc}")

        diffs_resp = await self._get(
            self._api_url(f"/projects/{enc_pid}/merge_requests/{mr_iid}/diffs"),
        )
        if mr_404_empty and diffs_resp.status_code == 404:
            await self._drop_stale_mr_from_queue_and_cache(project_id, mr_iid)
            return None
        if diffs_resp.is_success:
            diffs_data = diffs_resp.json()
            if isinstance(diffs_data, list):
                diffs = diffs_data
            elif isinstance(diffs_data, dict):
                raw_changes = diffs_data.get("changes")
                diffs = raw_changes if isinstance(raw_changes, list) else []
            else:
                diffs = []
            context["changed_files"] = [
                c.get("new_path", "") for c in diffs[:MAX_CHANGED_FILES] if isinstance(c, dict)
            ]
        else:
            context["changed_files"] = []

        pipelines = await self._fetch_latest_pipeline(
            enc_pid, mr_iid, target.get("source_branch", ""),
        )

        pipeline_status = "unknown"
        failed_job_log = ""
        if pipelines:
            pipeline_status = pipelines[0].get("status", "unknown")
            context["pipeline_id"] = pipelines[0].get("id")
            if pipeline_status == "failed":
                pipe_id = context.get("pipeline_id")
                if pipe_id:
                    failed_job_log = await self._fetch_failed_job_log(
                        enc_pid, pipe_id, context,
                    )

        context["pipeline_status"] = pipeline_status
        context["failed_job_log"] = failed_job_log

        all_notes, notes_resp = await self._get_paginated_list(
            self._api_url(f"/projects/{enc_pid}/merge_requests/{mr_iid}/notes"),
            params={"sort": "desc", "per_page": "100"},
            max_pages=2,
        )
        if not notes_resp.is_success:
            if is_mention_action:
                logger.warning(
                    f"GitLabPlatform: notes fetch failed ({notes_resp.status_code}) on mention for !{mr_iid}; failing closed without dismissing todo"
                )
                return None
        else:
            ci_notes: list[str] = []
            authorized_mention_found = False
            unauthorized_mention_seen = False
            mention_needle = f"@{darwin_bot_lower}"

            anchor_note_id: int | None = None
            raw_target_url = work_item.get("target_url") or ""
            if "#note_" in raw_target_url:
                anchor_frag = raw_target_url.split("#note_", 1)[1].split("&")[0].split("/")[0]
                if anchor_frag.isdigit():
                    anchor_note_id = int(anchor_frag)

            if is_mention_action and anchor_note_id is not None:
                matched_anchor = next(
                    (n for n in all_notes if n.get("id") == anchor_note_id),
                    None,
                )
                if matched_anchor is not None and not matched_anchor.get("system"):
                    body = matched_anchor.get("body", "")
                    note_author = ((matched_anchor.get("author") or {}).get("username") or "")
                    if note_author.lower() != darwin_bot_lower and mention_needle in body.lower():
                        is_authorized = (not allowed_authors) or (note_author.lower() in allowed_authors)
                        if is_authorized:
                            context["mention_comment"] = body[:5000]
                            context["mention_author"] = note_author
                            authorized_mention_found = True
                        else:
                            logger.info(f"Ignoring @mention from {note_author} (not in maintainer list)")
                            unauthorized_mention_seen = True
                if authorized_mention_found:
                    for note in all_notes:
                        if note.get("system") or note.get("id") == anchor_note_id:
                            continue
                        note_author = ((note.get("author") or {}).get("username") or "")
                        if note_author.lower() == darwin_bot_lower:
                            continue
                        if len(ci_notes) < MAX_CI_NOTES:
                            ci_notes.append(f"[{note_author}]: {note.get('body', '')[:500]}")
            else:
                for note in all_notes:
                    if note.get("system"):
                        continue
                    body = note.get("body", "")
                    note_author = ((note.get("author") or {}).get("username") or "")
                    if note_author.lower() == darwin_bot_lower:
                        continue
                    if is_mention_action and mention_needle in body.lower():
                        is_authorized = (not allowed_authors) or (note_author.lower() in allowed_authors)
                        if not is_authorized:
                            logger.info(f"Ignoring @mention from {note_author} (not in maintainer list)")
                            unauthorized_mention_seen = True
                            break
                        context["mention_comment"] = body[:5000]
                        context["mention_author"] = note_author
                        authorized_mention_found = True
                        break
                    if len(ci_notes) < MAX_CI_NOTES:
                        ci_notes.append(f"[{note_author}]: {body[:500]}")

            if is_mention_action and not authorized_mention_found and not unauthorized_mention_seen and anchor_note_id is None:
                mr_desc = target.get("description") or ""
                mr_author = ((target.get("author") or {}).get("username") or "")
                if mention_needle in mr_desc.lower() and mr_author.lower() != darwin_bot_lower:
                    is_authorized = (not allowed_authors) or (mr_author.lower() in allowed_authors)
                    if is_authorized:
                        context["mention_comment"] = mr_desc[:5000]
                        context["mention_author"] = mr_author
                        authorized_mention_found = True
                    else:
                        logger.info(f"Ignoring @mention in MR description from {mr_author} (not in maintainer list)")
                        unauthorized_mention_seen = True

            if is_mention_action and not authorized_mention_found:
                if unauthorized_mention_seen:
                    await self._reject_unauthorized_mention(
                        work_item.get("id"),
                        project_id,
                        mr_iid,
                        f"GitLabPlatform: unauthorized @{darwin_bot} mention on !{mr_iid}; dismissed todo {own_todo_ids} and skipping",
                    )
                else:
                    logger.warning(
                        f"GitLabPlatform: no @{darwin_bot} mention found in recent notes window on !{mr_iid}; skipping without dismissing todos"
                    )
                return None
            if ci_notes:
                context["recent_notes"] = ci_notes
            seen_note_ids = [
                str(n["id"]) for n in all_notes
                if isinstance(n, dict) and n.get("id") is not None
            ]
            if seen_note_ids:
                context["_seen_note_ids"] = seen_note_ids

        return context

    def load_triage_instruction(self) -> str:
        """Load GitLab MR triage system instruction from skills directory."""
        skill_path = _SKILLS_DIR / "gitlab-mr-triage.md"
        try:
            content = skill_path.read_text(encoding="utf-8")
            if content.strip():
                return content
            logger.warning("GitLab MR triage skill file is empty, using emergency fallback")
            return _EMERGENCY_SI
        except OSError as e:
            logger.warning(f"GitLab MR triage skill not loadable ({e}), using emergency fallback")
            return _EMERGENCY_SI

    @staticmethod
    def classify_severity(action: str, status: str) -> str:
        """Map GitLab MR action + pipeline status to event severity."""
        if action == "build_failed":
            return "warning"
        if action == "unmergeable":
            return "warning"
        if status == "failed":
            return "warning"
        return "info"

    async def create_platform_event(
        self,
        work_item: dict,
        plan_text: str,
        context: dict,
    ) -> str:
        """Push event to Brain queue with gitlab_context evidence."""
        from ..models import EventEvidence

        todo = work_item
        target = todo["target"]
        project = todo["project"]
        project_path = project.get("path_with_namespace", "")
        action_name = todo["action_name"]
        pipeline_status = context.get("pipeline_status", "unknown")
        severity = self.classify_severity(action_name, pipeline_status)
        maintainer = await self.resolve_maintainer(project_path, todo)
        logger.info(f"GitLab severity: {severity} for {action_name}/{pipeline_status}")
        head_sha = (
            context.get("head_sha")
            or target.get("sha")
            or (target.get("diff_refs") or {}).get("head_sha")
        )
        todo_id = todo.get("id")
        raw_siblings = todo.get("_sibling_todo_ids")
        if isinstance(raw_siblings, list):
            todo_ids = [s for s in raw_siblings if s is not None]
        elif todo_id is not None:
            todo_ids = [todo_id]
        else:
            todo_ids = []
        evidence = EventEvidence(
            display_text=f"GitLab: {action_name} on !{target['iid']} in {project_path}",
            source_type="headhunter",
            triggered_by="gitlab-bot",
            domain="disorder",
            domain_confidence="default",
            severity=severity,
            gitlab_context={
                "todo_id": todo_id,
                "todo_ids": todo_ids,
                "action_name": action_name,
                "project_id": project["id"],
                "project_path": project_path,
                "mr_iid": target["iid"],
                "mr_title": target["title"],
                "mr_state": target.get("state", ""),
                "merge_status": context.get("merge_status", ""),
                "source_branch": target.get("source_branch", ""),
                "target_branch": target.get("target_branch", ""),
                "author": target.get("author", {}).get("username", ""),
                "target_url": todo.get("target_url", "").split("#")[0],
                "pipeline_status": pipeline_status,
                "pipeline_id": context.get("pipeline_id"),
                "todo_created_at": todo.get("created_at", ""),
                "mr_description": (target.get("description") or "")[:_DESC_SAFETY_CAP],
                "maintainer": maintainer,
                "head_sha": head_sha,
                "sha": head_sha,
            },
        )
        resolved_service = await self._resolve_service(project_path)
        clean_plan = plan_text.strip()
        if clean_plan.startswith("```"):
            clean_plan = clean_plan.split("\n", 1)[1] if "\n" in clean_plan else clean_plan
        if clean_plan.endswith("```"):
            clean_plan = clean_plan[:-3].rstrip()
        event_id = await self.blackboard.create_event(
            source="headhunter",
            service=resolved_service,
            reason=clean_plan,
            evidence=evidence,
        )
        seen_note_ids = context.get("_seen_note_ids")
        if isinstance(seen_note_ids, list) and seen_note_ids:
            try:
                await self._mark_wakeup_notes_seen(event_id, [str(x) for x in seen_note_ids])
            except Exception as exc:
                logger.debug(f"GitLabPlatform: seeding wake-up notes cursor failed for {event_id}: {exc}")
        if hasattr(self.blackboard, "remove_gitlab_queue"):
            try:
                await self.blackboard.remove_gitlab_queue(project["id"], target["iid"])
            except Exception:
                pass
        pid_val = _valid_positive_int(project.get("id"))
        iid_val = _valid_positive_int(target.get("iid"))
        if pid_val and iid_val:
            self.remove_from_snapshot_cache(pid_val, iid_val)
        logger.info(f"GitLab event created: {event_id} for {todo['action_name']} on !{target['iid']}")
        return event_id

    async def post_feedback(self, event: object) -> None:
        """Post GitLab feedback (comment + mark_as_done + live MR SHA sync) for a closed event."""
        if await self.blackboard.is_feedback_sent(event.id):
            return

        gl_ctx = None
        if hasattr(event, "event") and event.event.evidence and hasattr(event.event.evidence, "gitlab_context"):
            gl_ctx = event.event.evidence.gitlab_context
        if not gl_ctx:
            return

        raw_todo_ids = gl_ctx.get("todo_ids")
        if isinstance(raw_todo_ids, list):
            todo_ids = [t for t in raw_todo_ids if t is not None]
        elif gl_ctx.get("todo_id") is not None:
            todo_ids = [gl_ctx["todo_id"]]
        else:
            todo_ids = []
        project_id = gl_ctx.get("project_id")
        mr_iid = _valid_positive_int(gl_ctx.get("mr_iid"))
        if not project_id or not mr_iid:
            return

        close_turn = event.conversation[-1] if event.conversation else None
        close_reason = (close_turn.evidence or "resolved") if close_turn else "resolved"
        encoded_project_id = self._enc_project_id(project_id)
        numeric_pid = _valid_positive_int(project_id)

        if close_reason in ("stale", "duplicate") and not todo_ids:
            tracked_sha = (
                await self.blackboard.get_gitlab_mr_sha(numeric_pid, mr_iid)
                if numeric_pid is not None and hasattr(self.blackboard, "get_gitlab_mr_sha")
                else None
            )
            if not tracked_sha and gl_ctx.get("action_name") != "new_commits":
                if not await self.blackboard.is_feedback_note_sent(event.id):
                    await self.blackboard.mark_feedback_note_sent(event.id)
                await self.blackboard.mark_feedback_sent(event.id)
                logger.info(f"GitLab duplicate/stale: no todo_id for {event.id} ({close_reason}) on !{mr_iid}")
                return

        client = self._get_client()
        headers = self._headers()

        # Phase 1: MR Note (suppressed for stale/duplicate; retryable on 401/408/429/5xx/network error; NEVER replayed inline)
        if close_reason in ("stale", "duplicate"):
            if not await self.blackboard.is_feedback_note_sent(event.id):
                await self.blackboard.mark_feedback_note_sent(event.id)
        elif not await self.blackboard.is_feedback_note_sent(event.id):
            outcome = self._build_feedback_comment(event, close_reason)
            try:
                resp = await client.post(
                    self._api_url(f"/projects/{encoded_project_id}/merge_requests/{mr_iid}/notes"),
                    headers=headers,
                    json={"body": outcome},
                )
            except Exception as exc:
                logger.warning(f"GitLab MR comment request failed for {event.id}: {exc}")
                return
            if resp.status_code in _RETRYABLE_STATUSES or resp.status_code >= 500:
                if resp.status_code == 401:
                    self._invalidate_token()
                logger.warning(f"GitLab MR comment transient failure ({resp.status_code}) for {event.id}")
                return
            if resp.status_code == 404:
                logger.info(f"Feedback skip: MR !{mr_iid} not found (deleted?)")
            elif resp.status_code == 403:
                logger.warning(f"MR comment forbidden (403) for {event.id}: {resp.text[:200]}")
            elif 400 <= resp.status_code < 500:
                logger.warning(
                    f"MR comment permanent client error ({resp.status_code}) for {event.id}: {resp.text[:200]}"
                )
            elif not resp.is_success:
                logger.warning(f"MR comment failed ({resp.status_code}): {resp.text[:200]}")
                return
            await self.blackboard.mark_feedback_note_sent(event.id)

        # Phase 2: Todo Dismissal (all sibling todo_ids; retryable on 401/408/429/5xx/network error)
        for tid in todo_ids:
            try:
                done_resp = await client.post(
                    self._api_url(f"/todos/{tid}/mark_as_done"), headers=headers,
                )
            except Exception as exc:
                logger.warning(f"GitLab mark_as_done request failed for todo {tid} ({event.id}): {exc}")
                return
            if done_resp.status_code in _RETRYABLE_STATUSES or done_resp.status_code >= 500:
                if done_resp.status_code == 401:
                    self._invalidate_token()
                logger.warning(f"GitLab mark_as_done transient failure ({done_resp.status_code}) for todo {tid} ({event.id})")
                return
            if done_resp.status_code == 304:
                logger.debug(f"GitLab feedback: todo {tid} already done (304) for {event.id}")
            elif done_resp.status_code == 404:
                logger.info(f"GitLab feedback: todo {tid} not found for {event.id}")
            elif done_resp.status_code == 403:
                logger.warning(f"GitLab mark_as_done forbidden (403) for todo {tid} ({event.id})")
            elif 400 <= done_resp.status_code < 500:
                logger.warning(
                    f"GitLab mark_as_done permanent client error ({done_resp.status_code}) for todo {tid} ({event.id})"
                )
            elif not done_resp.is_success:
                logger.warning(f"GitLab mark_as_done failed ({done_resp.status_code}) for todo {tid} ({event.id})")
                return

        # Phase 3: Fetch live MR state BEFORE recording SHA for bounded sweep (runs even on stale/duplicate
        # so synthetic SHA-sweep events update mr_sha and never infinite-loop). Transient HTTP/Redis errors
        # return early before mark_feedback_sent so feedback retries cleanly.
        try:
            live_resp = await self._get(
                self._api_url(f"/projects/{encoded_project_id}/merge_requests/{mr_iid}"),
            )
        except Exception as live_exc:
            logger.warning(f"GitLab post_feedback Phase 3 live MR GET failed for {event.id}: {live_exc}")
            return

        status_code = live_resp.status_code
        if isinstance(status_code, int) and (status_code in _RETRYABLE_STATUSES or status_code >= 500):
            if status_code == 401:
                self._invalidate_token()
            logger.warning(f"GitLab post_feedback Phase 3 transient HTTP {status_code} for {event.id}")
            return

        try:
            if status_code == 404:
                if numeric_pid is not None and hasattr(self.blackboard, "delete_gitlab_mr_sha"):
                    await self.blackboard.delete_gitlab_mr_sha(numeric_pid, mr_iid)
            elif live_resp.is_success:
                mr_data = live_resp.json()
                if isinstance(mr_data, dict):
                    live_pid = _valid_positive_int(mr_data.get("project_id"))
                    if live_pid is not None:
                        numeric_pid = live_pid
                    mr_state = mr_data.get("state", "")
                    if mr_state in ("merged", "closed"):
                        if numeric_pid is not None and hasattr(self.blackboard, "delete_gitlab_mr_sha"):
                            await self.blackboard.delete_gitlab_mr_sha(numeric_pid, mr_iid)
                    else:
                        live_sha = (
                            mr_data.get("sha")
                            or (mr_data.get("diff_refs") or {}).get("head_sha")
                            or gl_ctx.get("head_sha")
                            or gl_ctx.get("sha")
                            or ""
                        )
                        if numeric_pid is not None and live_sha and hasattr(self.blackboard, "set_gitlab_mr_sha"):
                            await self.blackboard.set_gitlab_mr_sha(numeric_pid, mr_iid, str(live_sha))
                        # Optional visual darwin-done label (skipped for stale/duplicate; best-effort 403 tolerated)
                        if close_reason not in ("stale", "duplicate"):
                            try:
                                lbl_resp = await client.put(
                                    self._api_url(f"/projects/{encoded_project_id}/merge_requests/{mr_iid}"),
                                    headers=headers,
                                    json={"add_labels": "darwin-done"},
                                )
                                if lbl_resp.status_code == 403:
                                    logger.debug(f"GitLab darwin-done label 403 on !{mr_iid} (best-effort skip)")
                            except Exception as lbl_exc:
                                logger.debug(f"GitLab darwin-done label PUT failed on !{mr_iid}: {lbl_exc}")
        except Exception as sha_exc:
            logger.warning(f"GitLab post_feedback Phase 3 SHA persistence failed for {event.id}: {sha_exc}")
            return

        await self.blackboard.mark_feedback_sent(event.id)
        logger.info(f"GitLab feedback posted for {event.id}: {close_reason} on !{mr_iid}")

    # =========================================================================
    # Brain-Facing Methods (NOT part of VcsPlatformPort)
    # =========================================================================

    async def refresh_mr_state(self, event_id: str, *,
                               override_project_id: int | None = None,
                               override_mr_iid: int | None = None) -> dict:
        """Re-fetch current MR/pipeline state from GitLab and update event evidence."""
        event = await self.blackboard.get_event(event_id)
        if not event:
            return {"error": f"Event {event_id} not found"}

        gl_ctx = None
        if event.event.evidence and hasattr(event.event.evidence, "gitlab_context"):
            gl_ctx = event.event.evidence.gitlab_context

        project_id = override_project_id or (gl_ctx.get("project_id") if gl_ctx else None)
        mr_iid = override_mr_iid or (gl_ctx.get("mr_iid") if gl_ctx else None)
        source_branch = (gl_ctx.get("source_branch", "") if gl_ctx else "")
        if not project_id or not mr_iid:
            return {"error": "No MR reference available. Supply mr_url or ensure the event has gitlab_context."}

        encoded_project_id = self._enc_project_id(project_id)
        state_changed_at = ""
        head_sha = (gl_ctx or {}).get("head_sha") or (gl_ctx or {}).get("sha")
        try:
            mr_resp = await self._get(
                self._api_url(f"/projects/{encoded_project_id}/merge_requests/{mr_iid}"),
            )
            if mr_resp.status_code == 404:
                return {"error": "MR not found (deleted?)", "pipeline_status": "unknown",
                        "mr_state": "closed", "merge_status": "unknown", "severity": "info"}
            if mr_resp.status_code == 429:
                _fallback = gl_ctx or {}
                return {"error": "GitLab rate limited", "pipeline_status": _fallback.get("pipeline_status", "unknown"),
                        "mr_state": _fallback.get("mr_state", "unknown"), "merge_status": _fallback.get("merge_status", "unknown"),
                        "severity": event.event.evidence.severity if event.event.evidence else "warning"}

            mr_state = "unknown"
            merge_status = "unknown"
            if mr_resp.is_success:
                mr_data = mr_resp.json()
                mr_state = mr_data.get("state", "unknown")
                merge_status = mr_data.get("detailed_merge_status") or mr_data.get("merge_status", "unknown")
                head_sha = mr_data.get("sha") or (mr_data.get("diff_refs") or {}).get("head_sha") or head_sha
                if not source_branch:
                    source_branch = mr_data.get("source_branch", "")
                if mr_state in ("merged", "closed"):
                    state_changed_at = mr_data.get("merged_at") or mr_data.get("closed_at") or ""
            else:
                _fallback = gl_ctx or {}
                return {
                    "error": f"MR fetch failed: HTTP {mr_resp.status_code}",
                    "pipeline_status": _fallback.get("pipeline_status", "unknown"),
                    "mr_state": _fallback.get("mr_state", "unknown"),
                    "merge_status": _fallback.get("merge_status", "unknown"),
                    "severity": event.event.evidence.severity if event.event.evidence else "warning",
                }

            pipeline_id = (gl_ctx or {}).get("pipeline_id")
            pipelines = await self._fetch_latest_pipeline(
                encoded_project_id, mr_iid, source_branch,
            )
            pipeline_status = "unknown"
            if pipelines:
                pipeline_status = pipelines[0].get("status", "unknown")
                pipeline_id = pipelines[0].get("id")

        except Exception as e:
            logger.warning(f"refresh_mr_state: GitLab API error for {event_id}: {e}")
            return {"error": f"GitLab API unavailable: {e}", "pipeline_status": "unknown",
                    "mr_state": "unknown", "merge_status": "unknown", "severity": "warning"}

        action_name = (gl_ctx or {}).get("action_name", "assigned")
        severity = self.classify_severity(action_name, pipeline_status)
        result = {
            "pipeline_status": pipeline_status,
            "pipeline_id": pipeline_id,
            "mr_state": mr_state,
            "merge_status": merge_status,
            "severity": severity,
        }
        if head_sha:
            result["head_sha"] = head_sha
            result["sha"] = head_sha
        if mr_state in ("merged", "closed"):
            result["merge_status"] = mr_state
            if state_changed_at:
                result["state_changed_at"] = state_changed_at

        await self.blackboard.update_event_gitlab_context(event_id, result)
        logger.info(f"Refreshed MR state for {event_id}: pipeline={pipeline_status}, mr={mr_state}")
        return result

    async def poll_gitlab_mr_status(self, project_id: int | str, mr_iid: int) -> dict:
        """Lightweight read-only poll for StateWatcher. Raises on HTTP errors."""
        encoded_project_id = self._enc_project_id(project_id)
        mr_resp = await self._get(
            self._api_url(f"/projects/{encoded_project_id}/merge_requests/{mr_iid}"),
        )
        mr_resp.raise_for_status()
        pipe_resp = await self._get(
            self._api_url(f"/projects/{encoded_project_id}/merge_requests/{mr_iid}/pipelines"),
            params={"per_page": "1"},
        )
        pipe_resp.raise_for_status()
        mr = mr_resp.json()
        pipelines = pipe_resp.json()
        latest_pipeline = pipelines[0] if isinstance(pipelines, list) and pipelines else {}
        return {
            "mr_state": mr.get("state", "unknown"),
            "pipeline_status": latest_pipeline.get("status", "unknown"),
        }

    @staticmethod
    def extract_gitlab_state_key(state: dict) -> dict:
        """Canonical state_key builder. merge_status excluded (flaps during active pipelines)."""
        return {
            "mr_state": state.get("mr_state", "unknown"),
            "pipeline_status": state.get("pipeline_status", "unknown"),
        }

    async def poll_gitlab_pipeline_status(self, project_id: int | str, pipeline_id: int) -> dict:
        """Lightweight read-only poll for StateWatcher. Returns pipeline status."""
        encoded_project_id = self._enc_project_id(project_id)
        resp = await self._get(
            self._api_url(f"/projects/{encoded_project_id}/pipelines/{pipeline_id}"),
        )
        resp.raise_for_status()
        pipeline = resp.json()
        return {
            "pipeline_status": pipeline.get("status", "unknown"),
        }

    @staticmethod
    def extract_pipeline_state_key(state: dict) -> dict:
        """Canonical state_key builder for pipeline-only polling."""
        return {"pipeline_status": state.get("pipeline_status", "unknown")}

    @staticmethod
    def parse_mr_url(url: str) -> tuple[int | str, int] | None:
        """Extract (project_id, mr_iid) from a GitLab MR URL."""
        from ..utils.vcs_approval import parse_mr_url
        return parse_mr_url(url)

    async def resolve_project_id(self, path_or_id) -> int | None:
        """Resolve a namespace/project path to a numeric project ID via GitLab API."""
        if isinstance(path_or_id, int):
            return path_or_id
        try:
            pid = int(path_or_id)
            return pid
        except (ValueError, TypeError):
            pass
        try:
            encoded = self._enc_project_id(path_or_id)
        except ValueError as e:
            logger.warning(f"resolve_project_id rejected invalid path {path_or_id!r}: {e}")
            return None
        try:
            resp = await self._get(
                self._api_url(f"/projects/{encoded}"),
                timeout=15.0,
            )
            if resp.is_success:
                return resp.json().get("id")
        except Exception as e:
            logger.warning(f"resolve_project_id failed for {path_or_id}: {e}")
        return None

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    def _get_token(self) -> str:
        """Read GitLab token fresh from GitLabTokenAuth (no secondary cache)."""
        override = self.__dict__.get("_gitlab_token")
        if override:
            return override
        from ..utils.gitlab_token import get_gitlab_auth
        auth = get_gitlab_auth()
        if not auth:
            raise RuntimeError("GitLab auth not configured (GITLAB_HOST or token missing)")
        return auth.get_token()

    def _headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self._get_token()}

    def _api_url(self, path: str) -> str:
        return f"https://{self._gitlab_host}/api/v4{path}"

    @staticmethod
    def _group_by_mr(todos: list[dict]) -> dict[tuple[int, int], list[dict]]:
        """Group todos by (project_id, mr_iid)."""
        grouped: dict[tuple[int, int], list[dict]] = {}
        for todo in todos:
            target = todo.get("target", {})
            key = (todo.get("project", {}).get("id", 0), target.get("iid", 0))
            grouped.setdefault(key, []).append(todo)
        return grouped

    async def resolve_maintainer(self, project_path: str, todo: dict) -> dict:
        """Resolve maintainer for escalation."""
        static_emails = _get_static_maintainer_emails()
        if static_emails:
            return {"source": "static", "emails": static_emails}

        target = todo.get("target", {})
        assignee = target.get("assignee") or target.get("author", {})
        if assignee and assignee.get("username"):
            email = await self._resolve_email_from_gitlab(assignee["username"])
            emails = [email] if email else []
            return {"source": "mr_metadata", "emails": emails, "name": assignee["username"]}

        return {"source": "static", "emails": []}

    async def _resolve_email_from_gitlab(self, username: str) -> str | None:
        """Lookup a GitLab user's email by username."""
        try:
            resp = await self._get(
                self._api_url("/users"),
                params={"username": username},
                timeout=10.0,
            )
            if resp.is_success:
                users = resp.json()
                if users and users[0].get("public_email"):
                    return users[0]["public_email"]
                if users and users[0].get("email"):
                    return users[0]["email"]
        except Exception as e:
            logger.debug(f"GitLab email lookup failed for {username}: {e}")
        return None

    async def _resolve_service(self, project_path: str) -> str:
        """Map GitLab project path to Darwin service name."""
        try:
            services = await self.blackboard.get_services()
            for svc in services.values():
                repo_url = getattr(svc, "source_repo_url", "") or ""
                gitops_url = getattr(svc, "gitops_repo_url", "") or ""
                if project_path in repo_url or project_path in gitops_url:
                    return svc.name
        except Exception:
            pass
        return project_path.rsplit("/", 1)[-1] if "/" in project_path else project_path or "general"

    @staticmethod
    def _build_feedback_comment(event, close_reason: str) -> str:
        """Build structured GitLab MR comment from event outcome."""
        actions = []
        for t in event.conversation:
            if t.actor in ("user", "brain"):
                continue
            if t.action == "execute" and t.result:
                ts = time.strftime("%H:%M", time.gmtime(t.timestamp)) if t.timestamp else ""
                first_line = t.result.strip().split("\n")[0].replace("#", "").strip()
                actions.append(f"- `{ts}` {first_line[:150]}")

        close_turn = event.conversation[-1] if event.conversation else None
        close_summary = (close_turn.thoughts or "") if close_turn else ""

        turns = len(event.conversation)
        lines = [f"**Darwin** ({turns} turns)"]
        if close_summary:
            lines.append(f"\n{close_summary}")
        if actions:
            lines.append("\n**Trace (UTC):**")
            lines.extend(actions[:5])

        return "\n".join(lines)
