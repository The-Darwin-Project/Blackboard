# BlackBoard/src/agents/headhunter_github.py
# @ai-rules:
# 1. [Pattern]: Implements VcsPlatformPort for GitHub. All GitHub API calls live here.
# 2. [Constraint]: AIR GAP: No kubernetes imports. GitHub API via AsyncGitHubClient only.
# 3. [Pattern]: Dedup by (owner, repo, pr_number). Label truth table: active>review>queued>done.
#    github_issue_context.issue_number also covered by get_active_keys() + Redis dedup.
# 4. [Pattern]: Brain-facing methods (refresh_pr_state, poll_github_pr_status, extract_github_state_key)
#    are NOT part of VcsPlatformPort — they're GitHub-specific, accessed via Headhunter delegates.
# 5. [Pattern]: _load_github_si() loads from headhunter_skills/github-pr-triage.md with emergency fallback.
#    _load_issue_triage_instruction() loads from URL (HEADHUNTER_GITHUB_SKILL_<LABEL>), 5-min cache.
# 6. [Gotcha]: mergeable excluded from state_key (flaps during CI runs).
# 7. [Pattern]: Lazy-init MultiInstallationManager via _get_manager() — never raises in constructor.
#    _resolve_client(installation_id, owner, repo) is the unified client resolution helper used by
#    ALL label/comment/context call sites -- direct ID lookup, falling back to repo->installation cache.
# 8. [Pattern]: Label/comment helpers are best-effort (never raise). URL-encode labels in DELETE path.
# 9. [Pattern]: 429/5xx propagate to circuit breaker. Only 422 (search not indexed) is silently caught.
# 10. [Pattern]: Re-trigger via darwin-done + SHA comparison (Redis HASH darwin:github:pr_sha).
# 11. [Pattern]: _queue_pr() ADD new label BEFORE removing old (prevents orphan on partial failure).
# 12. [Pattern]: queued_prs @property exposes _last_queued_prs for /headhunter/pending REST endpoint.
# 13. [Gotcha]: Issue dedup uses separate Redis namespace darwin:github:issue:{owner}:{repo}:{number}.
# 14. [Constraint]: Skill URL 10KB cap -- >10240 bytes falls back to _EMERGENCY_ISSUE_SI + returns warning.
# 15. [Pattern]: close_reason sanitized via re.sub([<>@`])[:200] before posting to GitHub.
# 16. [Pattern]: post_issue_feedback guards via is_feedback_sent() at entry (defense-in-depth dedup).
# 17. [Pattern]: set_github_issue_processed called BEFORE label swap -- dedup survives label API failures.
# 18. [Pattern]: domain_confidence is always "assessed" -- headhunter always runs LLM triage.
"""
GitHub Platform Adapter for Headhunter.

Implements VcsPlatformPort for the GitHub PR polling workflow.
Also exposes Brain-facing methods for refresh_github_context and StateWatcher integration.
"""
from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import urllib.parse
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

from .headhunter_utils import _COMMENT_LIMIT

logger = logging.getLogger(__name__)

_SKILLS_DIR = Path(__file__).parent / "headhunter_skills"

_EMERGENCY_SI = """\
You are a triage agent for GitHub PRs. Read the PR context and produce ONLY
a YAML frontmatter plan wrapped in --- delimiters. Nothing else.

```yaml
---
plan: "[Action verb] [target] in [repository]"
service: [component name]
repository: [owner/repo]
domain: [CLEAR|COMPLICATED|COMPLEX]
risk: [low|medium|high]
reasoning: "[One sentence]"
steps:
  - id: "1"
    agent: [sysadmin|developer|qe|architect]
    summary: "[What this step accomplishes -- include PR number, branch, error details]"
---
```

Agents: sysadmin (k8s/gitops), developer (code/PR/CI), qe (test/verify), architect (analysis/review).
Domain: CLEAR (known fix, 1-3 steps), COMPLICATED (needs analysis, 2-4 steps), COMPLEX (novel, 1-2 probes).
"""

_EMERGENCY_ISSUE_SI = """\
You are a triage agent for GitHub Issues. Read the issue context and produce ONLY
a YAML frontmatter plan wrapped in --- delimiters. Nothing else.

```yaml
---
plan: "[Action verb] [issue title summary]"
service: [component name]
repository: [owner/repo]
domain: [CLEAR|COMPLICATED|COMPLEX]
risk: [low|medium|high]
reasoning: "[One sentence]"
steps:
  - id: "1"
    agent: [sysadmin|developer|qe|architect]
    summary: "[What this step accomplishes — include issue number and key details]"
---
```

Agents: sysadmin (k8s/gitops), developer (code/implementation), qe (test/verify), architect (analysis/design).
Domain: CLEAR (known fix, 1-3 steps), COMPLICATED (needs analysis, 2-4 steps), COMPLEX (novel, 1-2 probes).
"""

# GitHub App slug for the bot (used in search queries)
_APP_SLUG = os.getenv("GITHUB_APP_SLUG", "darwin-project-ai")


def _get_static_maintainer_emails() -> list[str]:
    """Read maintainer CSV from env at call time."""
    return [e.strip() for e in os.getenv("HEADHUNTER_MAINTAINERS", "").split(",") if e.strip()]


class GitHubPlatform:
    """GitHub platform adapter implementing VcsPlatformPort.

    Handles: PR discovery via search API, context fetching, event creation
    with github_context, feedback posting (PR comment), and Brain-facing state tools.
    """

    def __init__(self, blackboard: "BlackboardState"):
        self.blackboard = blackboard
        self._manager = None  # lazy-init in _get_manager(); never raises here
        self._repos: list[str] = []
        repos_env = os.getenv("HEADHUNTER_GITHUB_REPOS", "")
        if repos_env.strip():
            self._repos = [r.strip() for r in repos_env.split(",") if r.strip()]
        self._trigger_reasons: set[str] = set(
            os.getenv("HEADHUNTER_GITHUB_TRIGGER_REASONS", "review_requested").split(",")
        )
        self._trigger_label = os.getenv("HEADHUNTER_GITHUB_LABEL", "darwin-review")
        self._active_label = os.getenv("HEADHUNTER_GITHUB_LABEL_ACTIVE", "darwin-active")
        self._done_label = os.getenv("HEADHUNTER_GITHUB_LABEL_DONE", "darwin-done")
        self._queued_label = os.getenv("HEADHUNTER_GITHUB_LABEL_QUEUED", "darwin-queued")
        self._work_label = os.getenv("HEADHUNTER_GITHUB_LABEL_WORK", "darwin-work")
        self._last_queued_prs: list[dict] = []
        # Skill URL map: populated from HEADHUNTER_GITHUB_SKILL_<LABEL> env vars at runtime.
        # Both env-var key (underscores) and label lookup (hyphens→underscores) normalize identically.
        self._issue_skill_urls: dict[str, str] = {
            k[len("HEADHUNTER_GITHUB_SKILL_"):].lower().replace("-", "_"): v
            for k, v in os.environ.items()
            if k.startswith("HEADHUNTER_GITHUB_SKILL_") and v.strip()
        }
        # label → (content, expiry_epoch): 5-min TTL, 404 does NOT reset TTL
        self._issue_skill_cache: dict[str, tuple[str, float]] = {}

    # =========================================================================
    # VcsPlatformPort Implementation
    # =========================================================================

    @property
    def platform_name(self) -> str:
        return "github"

    @property
    def queued_prs(self) -> list[dict]:
        """Snapshot of queued PRs from the last poll cycle (for /headhunter/pending)."""
        return list(self._last_queued_prs)

    def enabled(self) -> bool:
        return (
            os.getenv("HEADHUNTER_GITHUB_ENABLED", "false").lower() == "true"
            and bool(os.getenv("GITHUB_APP_ID"))
        )

    def _get_manager(self):
        """Lazy-init MultiInstallationManager. Returns None if auth is unavailable."""
        if self._manager is None:
            try:
                from ..utils.github_app import MultiInstallationManager
                self._manager = MultiInstallationManager(
                    filter_installation_id=os.getenv("GITHUB_INSTALLATION_ID") or None,
                )
            except Exception as e:
                logger.warning(f"GitHub manager init failed: {e}")
                return None
        return self._manager

    async def _get_client_for(self, installation_id: str):
        """Direct lookup by installation_id. None if manager/installation unavailable."""
        if not installation_id:
            return None
        manager = self._get_manager()
        if not manager:
            return None
        return await manager.get_client_for(installation_id)

    async def _get_client_for_repo(self, owner: str, repo: str):
        """Reverse lookup via the repo -> installation_id cache. None on cache miss."""
        manager = self._get_manager()
        if not manager:
            return None
        result = await manager.get_client_for_repo(owner, repo)
        return result[1] if result else None

    async def _resolve_client(self, installation_id: str, owner: str, repo: str):
        """Unified client resolution: direct ID lookup, else fall back to repo cache.

        Backward compat: pre-existing events with no installation_id in evidence
        resolve via the repo -> installation_id cache instead.
        """
        if installation_id:
            client = await self._get_client_for(installation_id)
            if client:
                return client
        return await self._get_client_for_repo(owner, repo)

    async def close(self) -> None:
        """Shut down all persistent HTTP clients."""
        if self._manager:
            await self._manager.close_all()
            self._manager = None

    async def get_active_keys(self) -> set[tuple[str, str, int]]:
        """Get (owner, repo, number) for all active/deferred headhunter events.

        Reads both github_context (PR) and github_issue_context (Issue).
        3-tuple format is safe: GitHub issues and PRs share a monotonic counter per repo.
        """
        active_ids = await self.blackboard.get_active_events()
        keys: set[tuple[str, str, int]] = set()
        for eid in active_ids:
            event = await self.blackboard.get_event(eid)
            if not event or event.source != "headhunter":
                continue
            if event.status.value not in ("new", "active", "deferred"):
                continue
            evidence = event.event.evidence if event.event else None
            if evidence is None:
                continue
            # PR context
            ctx = getattr(evidence, "github_context", None)
            if ctx:
                owner = ctx.get("owner", "") if isinstance(ctx, dict) else getattr(ctx, "owner", "")
                repo = ctx.get("repo", "") if isinstance(ctx, dict) else getattr(ctx, "repo", "")
                pr_num = ctx.get("pr_number", 0) if isinstance(ctx, dict) else getattr(ctx, "pr_number", 0)
                if owner and repo and pr_num:
                    keys.add((owner, repo, pr_num))
            # Issue context
            issue_ctx = getattr(evidence, "github_issue_context", None)
            if issue_ctx:
                owner = issue_ctx.get("owner", "") if isinstance(issue_ctx, dict) else getattr(issue_ctx, "owner", "")
                repo = issue_ctx.get("repo", "") if isinstance(issue_ctx, dict) else getattr(issue_ctx, "repo", "")
                issue_num = issue_ctx.get("issue_number", 0) if isinstance(issue_ctx, dict) else getattr(issue_ctx, "issue_number", 0)
                if owner and repo and issue_num:
                    keys.add((owner, repo, issue_num))
        return keys

    async def poll_work_items(self) -> list[dict]:
        """Discover PRs from all repos across all discovered installations.

        Fan-out via asyncio.gather, one call per installation. Per-installation
        errors are isolated (logged + skipped) so one bad installation cannot
        take down polling for the rest. Fallback: if repos are pinned via env,
        intersect with each installation's repo set.
        """
        manager = self._get_manager()
        if not manager:
            return []

        installations = await manager.get_clients_with_repos()

        async def _poll_one(inst_id: str, client, inst_repos: list[str]) -> list[dict]:
            effective_repos = (
                [r for r in inst_repos if r in set(self._repos)] if self._repos else inst_repos
            )
            if not effective_repos:
                return []
            try:
                return await self._list_from_repos(client, effective_repos, inst_id)
            except Exception as e:
                logger.warning(f"GitHub PR poll failed for installation {inst_id}: {e}")
                return []

        results = await asyncio.gather(
            *[_poll_one(inst_id, client, repos) for inst_id, client, repos in installations],
        )
        prs = [pr for batch in results for pr in batch]

        active_keys = await self.get_active_keys()
        result: list[dict] = []
        seen_keys: set[tuple[str, str, int]] = set()
        skipped_terminal = 0
        skipped_no_label = 0
        skipped_same_sha = 0
        for pr in prs:
            key = (pr["owner"], pr["repo"], pr["number"])
            if key in active_keys or key in seen_keys:
                continue
            if pr.get("state") in ("closed", "merged"):
                skipped_terminal += 1
                continue

            labels = set(pr.get("labels", []))
            if self._active_label in labels:
                continue

            if self._trigger_label in labels:
                result.append(pr)
                seen_keys.add(key)
            elif self._queued_label in labels:
                # Already queued — expose for promote logic in orchestrator
                result.append({**pr, "queued": True})
                seen_keys.add(key)
            elif self._done_label in labels:
                stored_sha = await self.blackboard.get_github_pr_sha(pr["owner"], pr["repo"], pr["number"])
                if stored_sha is not None and stored_sha == pr.get("head_sha", ""):
                    skipped_same_sha += 1
                else:
                    result.append(pr)
                    seen_keys.add(key)
            else:
                skipped_no_label += 1

        logger.info(
            f"GitHub poll: {len(prs)} discovered, {len(active_keys)} active, "
            f"{skipped_terminal} terminal, {skipped_no_label} no-label, "
            f"{skipped_same_sha} same-sha, {len(result)} new"
        )
        return result

    async def _search_review_requested(self, client) -> list[dict]:
        """Use GitHub Search API: is:pr is:open review-requested:<bot>."""
        query = f"is:pr is:open review-requested:{_APP_SLUG}[bot]"
        try:
            resp = await client.get("/search/issues", params={"q": query, "per_page": "50"})
            items = resp.json().get("items", [])
            results = [self._normalize_search_item(item) for item in items]
            if self._repos:
                allowed = set(self._repos)
                results = [pr for pr in results if f"{pr['owner']}/{pr['repo']}" in allowed]
            return results
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 422:
                logger.warning("GitHub search returned 422 — app slug may not be indexed yet")
                return []
            raise

    async def _list_from_repos(self, client, repos: list[str], installation_id: str) -> list[dict]:
        """List open PRs from the given repos.

        All open PRs are candidates — dedup against active events prevents
        flooding. Users opt in by installing the App on their repo.
        """
        prs: list[dict] = []
        for repo_full in repos:
            try:
                resp = await client.get(
                    f"/repos/{repo_full}/pulls",
                    params={"state": "open", "per_page": "30"},
                )
                for pr_data in resp.json():
                    prs.append(self._normalize_pr_data(repo_full, pr_data, installation_id))
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (404, 422):
                    logger.warning(f"GitHub repo list {e.response.status_code} for {repo_full}")
                    continue
                raise
        return prs

    async def poll_issues_all_installations(self) -> list[dict]:
        """Fan out Issue polling across all discovered installations.

        Encapsulates the multi-installation fan-out pattern (hexagonal boundary --
        the orchestrator calls this single method, it never iterates clients itself).
        """
        manager = self._get_manager()
        if not manager:
            return []

        installations = await manager.get_clients_with_repos()

        async def _poll_one(inst_id: str, client, inst_repos: list[str]) -> list[dict]:
            effective_repos = (
                [r for r in inst_repos if r in set(self._repos)] if self._repos else inst_repos
            )
            if not effective_repos:
                return []
            try:
                return await self._poll_issues(client, effective_repos, inst_id)
            except Exception as e:
                logger.warning(f"GitHub issue poll failed for installation {inst_id}: {e}")
                return []

        results = await asyncio.gather(
            *[_poll_one(inst_id, client, repos) for inst_id, client, repos in installations],
        )
        return [issue for batch in results for issue in batch]

    async def _poll_issues(self, client, repos: list[str], installation_id: str) -> list[dict]:
        """Poll open Issues with darwin-work label from the given repos.

        Uses sort=created&direction=asc for oldest-first FIFO ordering.
        Filters out items with a `pull_request` key (GitHub /issues API returns PRs too).
        Per-repo try/except for 404/422 resilience.
        Also deduplicates against active event keys and Redis processed set.
        """
        issues: list[dict] = []
        active_keys = await self.get_active_keys()
        for repo_full in repos:
            try:
                resp = await client.get(
                    f"/repos/{repo_full}/issues",
                    params={
                        "labels": self._work_label,
                        "state": "open",
                        "sort": "created",
                        "direction": "asc",
                        "per_page": "30",
                    },
                )
                for item in resp.json():
                    if "pull_request" in item:
                        continue
                    normalized = self._normalize_issue_data(repo_full, item, installation_id)
                    key = (normalized["owner"], normalized["repo"], normalized["issue_number"])
                    if key in active_keys:
                        continue
                    already = await self.blackboard.get_github_issue_processed(
                        normalized["owner"], normalized["repo"], normalized["issue_number"]
                    )
                    if already:
                        continue
                    issues.append(normalized)
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (404, 422):
                    logger.warning(f"GitHub issues list {e.response.status_code} for {repo_full}")
                    continue
                raise
        logger.info(f"GitHub issue poll: {len(issues)} actionable issue(s) across {len(repos)} repo(s)")
        return issues

    @staticmethod
    def _normalize_issue_data(repo_full: str, issue_data: dict, installation_id: str) -> dict:
        """Normalize a GitHub Issues API item to our internal issue shape."""
        parts = repo_full.split("/", 1)
        owner = parts[0] if parts else ""
        repo = parts[1] if len(parts) > 1 else ""
        return {
            "owner": owner,
            "repo": repo,
            "installation_id": installation_id,
            "issue_number": issue_data["number"],
            "issue_title": issue_data.get("title", ""),
            "state": issue_data.get("state", "open"),
            "author": (issue_data.get("user") or {}).get("login", ""),
            "labels": [l.get("name", "") for l in issue_data.get("labels", [])],
            "assignees": [(a or {}).get("login", "") for a in issue_data.get("assignees", [])],
            "html_url": issue_data.get("html_url", ""),
            "created_at": issue_data.get("created_at", ""),
            "body": issue_data.get("body") or "",
        }

    async def _load_issue_triage_instruction(self, labels: list[str]) -> tuple[str, str | None]:
        """Load issue triage SI from skill URL cache (5-min TTL).

        Returns (si_content, skill_size_warning | None).
        Matches issue labels against _issue_skill_urls (HEADHUNTER_GITHUB_SKILL_<LABEL> env vars).
        404 does NOT reset TTL — avoids hammering a missing URL on every cycle.
        >10KB content falls back to _EMERGENCY_ISSUE_SI and returns a user-facing warning string.
        Falls back to _EMERGENCY_ISSUE_SI on any failure (no warning on fallback-only paths).
        """
        now = time.monotonic()
        for label in labels:
            label_key = label.lower().replace("-", "_")
            url = self._issue_skill_urls.get(label_key)
            if not url:
                continue
            cached = self._issue_skill_cache.get(label_key)
            if cached and now < cached[1]:
                return cached[0], None
            # Redact query params before logging — credentials may appear in query string
            log_url = url.split("?")[0] + ("?..." if "?" in url else "")
            try:
                async with httpx.AsyncClient(timeout=10.0) as http:
                    resp = await http.get(url)
                    resp.raise_for_status()
                    content = resp.text.strip()
                    if content:
                        if len(content) > 10240:
                            logger.warning(
                                f"Skill URL {log_url} exceeds 10KB ({len(content)} bytes), using fallback"
                            )
                            self._issue_skill_cache[label_key] = (_EMERGENCY_ISSUE_SI, now + 300)
                            warning = (
                                f"Darwin skill file at `{url}` exceeds the 10KB size limit. "
                                "Using default triage. Please reduce the skill file size."
                            )
                            return _EMERGENCY_ISSUE_SI, warning
                        self._issue_skill_cache[label_key] = (content, now + 300)
                        return content, None
                    logger.warning(f"Issue skill URL returned empty content for {label_key}")
            except httpx.HTTPStatusError as e:
                # 404: log once + cache sentinel (full 5-min TTL prevents re-logging every cycle)
                if e.response.status_code == 404:
                    logger.warning(f"Skill URL 404 for label {label_key}: {log_url}")
                    self._issue_skill_cache[label_key] = (_EMERGENCY_ISSUE_SI, now + 300)
                else:
                    # 5xx / other: cache with short 60s TTL to prevent hammering every cycle
                    logger.warning(f"Issue skill fetch failed ({e.response.status_code}) for {label_key}")
                    self._issue_skill_cache[label_key] = (_EMERGENCY_ISSUE_SI, now + 60)
            except Exception as e:
                logger.warning(f"Issue skill fetch error for {label_key}: {e}")
        return _EMERGENCY_ISSUE_SI, None

    @staticmethod
    def _normalize_search_item(item: dict) -> dict:
        """Normalize a search API result to our internal work item shape."""
        repo_url = item.get("repository_url", "")
        parts = repo_url.rstrip("/").split("/")
        owner = parts[-2] if len(parts) >= 2 else ""
        repo = parts[-1] if len(parts) >= 1 else ""
        return {
            "owner": owner,
            "repo": repo,
            "number": item["number"],
            "title": item.get("title", ""),
            "state": item.get("state", "open"),
            "user": item.get("user", {}).get("login", ""),
            "labels": [l.get("name", "") for l in item.get("labels", [])],
            "html_url": item.get("html_url", ""),
            "created_at": item.get("created_at", ""),
            "head_sha": "",
        }

    @staticmethod
    def _normalize_pr_data(repo_full: str, pr_data: dict, installation_id: str = "") -> dict:
        """Normalize a repo PR list item to our internal work item shape."""
        parts = repo_full.split("/", 1)
        owner = parts[0] if parts else ""
        repo = parts[1] if len(parts) > 1 else ""
        return {
            "owner": owner,
            "repo": repo,
            "installation_id": installation_id,
            "number": pr_data["number"],
            "title": pr_data.get("title", ""),
            "state": pr_data.get("state", "open"),
            "user": pr_data.get("user", {}).get("login", ""),
            "labels": [l.get("name", "") for l in pr_data.get("labels", [])],
            "html_url": pr_data.get("html_url", ""),
            "created_at": pr_data.get("created_at", ""),
            "head_sha": (pr_data.get("head") or {}).get("sha", ""),
        }

    async def fetch_context(self, work_item: dict) -> dict:
        """Enrich a PR work item with full context from GitHub API."""
        owner = work_item["owner"]
        repo = work_item["repo"]
        number = work_item["number"]

        client = await self._resolve_client(work_item.get("installation_id", ""), owner, repo)
        if not client:
            return self._minimal_context(work_item)

        context: dict = {
            "owner": owner,
            "repo": repo,
            "pr_number": number,
            "pr_title": work_item.get("title", ""),
            "pr_state": work_item.get("state", "open"),
            "author": work_item.get("user", ""),
            "labels": work_item.get("labels", []),
            "pr_url": work_item.get("html_url", f"https://github.com/{owner}/{repo}/pull/{number}"),
            "head_sha": work_item.get("head_sha", ""),
            "action": "review_requested",
        }

        try:
            pr_resp = await client.get(f"/repos/{owner}/{repo}/pulls/{number}")
            pr = pr_resp.json()
            context["head_sha"] = (pr.get("head") or {}).get("sha", "")
            context["head_branch"] = (pr.get("head") or {}).get("ref", "")
            context["base_branch"] = (pr.get("base") or {}).get("ref", "")
            context["pr_body"] = pr.get("body") or ""
            context["mergeable"] = pr.get("mergeable")
            context["changed_files"] = []

            files_resp = await client.get(
                f"/repos/{owner}/{repo}/pulls/{number}/files",
                params={"per_page": "30"},
            )
            context["changed_files"] = [f.get("filename", "") for f in files_resp.json()[:20]]
        except Exception as e:
            logger.warning(f"GitHub PR detail fetch failed for {owner}/{repo}#{number}: {e}")

        head_sha = context.get("head_sha")
        if head_sha:
            try:
                check_resp = await client.get(
                    f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
                    params={"per_page": "50"},
                )
                check_data = check_resp.json()
                check_runs = check_data.get("check_runs", [])
                failed = [cr for cr in check_runs if cr.get("conclusion") == "failure"]
                context["check_status"] = self._aggregate_check_status(check_runs)
                if failed:
                    context["check_run_url"] = failed[0].get("html_url", "")
                    context["failed_checks"] = [cr.get("name", "") for cr in failed[:5]]
            except Exception as e:
                logger.debug(f"GitHub check-runs fetch failed: {e}")
                context["check_status"] = "unknown"
        else:
            context["check_status"] = "unknown"

        try:
            comments_resp = await client.get(
                f"/repos/{owner}/{repo}/issues/{number}/comments",
                params={"per_page": "10", "direction": "desc"},
            )
            comments = comments_resp.json()
            bot_name = f"{_APP_SLUG}[bot]"
            recent = []
            total_len = 0
            for c in comments:
                login = c.get("user", {}).get("login", "")
                is_bot = login.endswith("[bot]")
                if is_bot and login != bot_name:
                    continue
                entry = f"[{login or '?'}]: {(c.get('body') or '')[:500]}"
                total_len += len(entry)
                if total_len > _COMMENT_LIMIT:
                    break
                recent.append(entry)
                if len(recent) >= 5:
                    break
            if recent:
                context["recent_comments"] = recent
        except Exception as e:
            logger.debug(f"GitHub comments fetch failed: {e}")

        return context

    @staticmethod
    def _minimal_context(work_item: dict) -> dict:
        """Fallback when client is unavailable."""
        return {
            "owner": work_item.get("owner", ""),
            "repo": work_item.get("repo", ""),
            "pr_number": work_item.get("number", 0),
            "pr_title": work_item.get("title", ""),
            "pr_state": work_item.get("state", "open"),
            "author": work_item.get("user", ""),
            "labels": work_item.get("labels", []),
            "action": "review_requested",
            "check_status": "unknown",
        }

    @staticmethod
    def _aggregate_check_status(check_runs: list[dict]) -> str:
        """Reduce multiple check runs to a single status string."""
        if not check_runs:
            return "unknown"
        conclusions = [cr.get("conclusion") for cr in check_runs if cr.get("conclusion")]
        statuses = [cr.get("status") for cr in check_runs]
        if any(c in ("failure", "cancelled", "timed_out", "action_required") for c in conclusions):
            return "failure"
        if any(s == "in_progress" for s in statuses):
            return "pending"
        if any(s == "queued" for s in statuses):
            return "pending"
        if all(c in ("success", "neutral", "skipped") for c in conclusions if c):
            return "success"
        return "pending"

    def load_triage_instruction(self) -> str:
        """Load GitHub PR triage system instruction from skills directory."""
        skill_path = _SKILLS_DIR / "github-pr-triage.md"
        try:
            content = skill_path.read_text(encoding="utf-8")
            if content.strip():
                return content
            logger.warning("GitHub PR triage skill file is empty, using emergency fallback")
            return _EMERGENCY_SI
        except OSError as e:
            logger.warning(f"GitHub PR triage skill not loadable ({e}), using emergency fallback")
            return _EMERGENCY_SI

    @staticmethod
    def classify_severity(action: str, status: str) -> str:
        """Map GitHub action + check status to event severity."""
        if status == "failure":
            return "warning"
        return "info"

    async def create_platform_event(
        self,
        work_item: dict,
        plan_text: str,
        domain: str,
        context: dict,
    ) -> str:
        """Push event to Brain queue with github_context evidence."""
        from ..models import EventEvidence

        owner = work_item["owner"]
        repo = work_item["repo"]
        pr_number = work_item["number"]
        installation_id = work_item.get("installation_id", "")
        action = context.get("action", "review_requested")
        check_status = context.get("check_status", "unknown")
        severity = self.classify_severity(action, check_status)
        maintainer = self._resolve_maintainer()

        evidence = EventEvidence(
            display_text=f"GitHub: {action} on #{pr_number} in {owner}/{repo}",
            source_type="headhunter",
            triggered_by="github-app",
            domain=domain,
            domain_confidence="assessed",
            severity=severity,
            github_context={
                "owner": owner,
                "repo": repo,
                "installation_id": installation_id,
                "pr_number": pr_number,
                "pr_title": context.get("pr_title", ""),
                "pr_state": context.get("pr_state", "open"),
                "pr_url": context.get("pr_url", f"https://github.com/{owner}/{repo}/pull/{pr_number}"),
                "action": action,
                "check_status": check_status,
                "check_run_url": context.get("check_run_url", ""),
                "head_sha": context.get("head_sha", ""),
                "head_branch": context.get("head_branch", ""),
                "base_branch": context.get("base_branch", ""),
                "author": context.get("author", ""),
                "labels": context.get("labels", []),
                "changed_files": context.get("changed_files", []),
                "maintainer": maintainer,
            },
        )

        service = repo or "general"
        clean_plan = plan_text.strip()
        if clean_plan.startswith("```"):
            clean_plan = clean_plan.split("\n", 1)[1] if "\n" in clean_plan else clean_plan
        if clean_plan.endswith("```"):
            clean_plan = clean_plan[:-3].rstrip()

        event_id = await self.blackboard.create_event(
            source="headhunter",
            service=service,
            reason=clean_plan,
            evidence=evidence,
        )
        logger.info(f"GitHub event created: {event_id} for {action} on #{pr_number} in {owner}/{repo}")

        await self._remove_label(installation_id, owner, repo, pr_number, self._trigger_label)
        await self._remove_label(installation_id, owner, repo, pr_number, self._done_label)
        await self._remove_label(installation_id, owner, repo, pr_number, self._queued_label)
        await self._add_labels(installation_id, owner, repo, pr_number, [self._active_label])
        cortex_url = os.getenv("DARWIN_CORTEX_URL", "")
        if cortex_url and cortex_url.startswith(("https://", "http://")):
            link = f" [{event_id}]({cortex_url}/events/{event_id})"
        else:
            link = f" `{event_id}`"
        await self._post_comment(installation_id, owner, repo, pr_number,
            f"**Darwin** is reviewing this PR. Tracking as{link}.")

        return event_id

    async def create_issue_event(
        self,
        issue: dict,
        plan_text: str | None = None,
        domain: str | None = None,
    ) -> str:
        """Create a Darwin event for a GitHub Issue (darwin-work label trigger).

        plan_text/domain come from the orchestrator's analyze_and_plan call.
        When omitted (legacy/emergency path), a stub plan is generated inline.
        Label ordering: ADD darwin-active BEFORE removing darwin-work (prevents orphan).
        Issue body truncated to 2000 chars with XML fence (prompt injection defense).
        Returns event ID.
        """
        from ..models import EventEvidence

        owner = issue["owner"]
        repo = issue["repo"]
        number = issue["issue_number"]
        installation_id = issue.get("installation_id", "")
        labels = issue.get("labels", [])
        skill_label = next(
            (l.lower().replace("-", "_") for l in labels if l.lower().replace("-", "_") in self._issue_skill_urls),
            None,
        )
        # Warning string injected by _github_poll_issues when skill URL exceeded 10KB cap
        skill_size_warning: str | None = issue.get("_skill_size_warning")
        # domain_confidence is always "assessed" -- headhunter always runs LLM triage
        # (emergency inline stub is still a classification, per event-evidence-contract)
        domain_confidence = "assessed"
        body_sanitized = issue.get("body", "")
        # Sanitize before XML fence to prevent prompt injection via </issue_body> in body content
        body_sanitized = body_sanitized.replace("</issue_body>", "")

        evidence = EventEvidence(
            display_text=f"GitHub Issue #{number}: {issue.get('issue_title', '')} in {owner}/{repo}",
            source_type="headhunter",
            triggered_by="github-issue",
            domain=domain or "complicated",
            domain_confidence=domain_confidence,
            severity="info",
            github_issue_context={
                "owner": owner,
                "repo": repo,
                "installation_id": installation_id,
                "issue_number": number,
                "title": issue.get("issue_title", ""),
                "body": f"<issue_body>{body_sanitized}</issue_body>",
                "labels": labels,
                "assignees": issue.get("assignees", []),
                "html_url": issue.get("html_url", f"https://github.com/{owner}/{repo}/issues/{number}"),
                "state": issue.get("state", "open"),
                "author": issue.get("author", ""),
                "created_at": issue.get("created_at", ""),
                "skill_label": skill_label,
            },
        )

        service = repo or "general"
        if not domain:
            domain = "complicated"
        if not plan_text:
            plan_text = (
                f"---\nplan: Triage GitHub Issue #{number}: {issue.get('issue_title', '')}\n"
                f"service: {service}\nrepository: {owner}/{repo}\n"
                f"domain: COMPLICATED\nrisk: medium\n"
                f"reasoning: GitHub issue requires triage\n"
                f"steps:\n  - id: \"1\"\n    agent: architect\n"
                f"    summary: \"Analyse issue #{number} in {owner}/{repo}\"\n---"
            )

        event_id = await self.blackboard.create_event(
            source="headhunter",
            service=service,
            reason=plan_text,
            evidence=evidence,
            subject_type="github_issue",
        )
        logger.info(f"GitHub issue event created: {event_id} for #{number} in {owner}/{repo}")

        # Mark processed BEFORE label swap — dedup survives a label API failure on next cycle
        await self.blackboard.set_github_issue_processed(owner, repo, number)

        # Label swap: ADD active BEFORE removing work
        await self._add_labels(installation_id, owner, repo, number, [self._active_label])
        await self._remove_label(installation_id, owner, repo, number, self._work_label)

        cortex_url = os.getenv("DARWIN_CORTEX_URL", "")
        if cortex_url and cortex_url.startswith(("https://", "http://")):
            link = f" [{event_id}]({cortex_url}/events/{event_id})"
        else:
            link = f" `{event_id}`"
        await self._post_comment(installation_id, owner, repo, number,
            f"**Darwin** is triaging this issue. Tracking as{link}.")
        if skill_size_warning:
            await self._post_comment(installation_id, owner, repo, number, skill_size_warning)

        return event_id

    async def post_issue_feedback(self, event: object) -> None:
        """Post resolution feedback on a GitHub Issue (active→done label + close comment)."""
        if await self.blackboard.is_feedback_sent(event.id):
            return
        issue_ctx = None
        if hasattr(event, "event") and event.event.evidence and hasattr(event.event.evidence, "github_issue_context"):
            issue_ctx = event.event.evidence.github_issue_context
        if not issue_ctx:
            return

        owner = issue_ctx.get("owner", "")
        repo = issue_ctx.get("repo", "")
        number = issue_ctx.get("issue_number", 0)
        installation_id = issue_ctx.get("installation_id", "")
        if not owner or not repo or not number:
            return

        # Label swap: ADD done BEFORE removing active
        await self._add_labels(installation_id, owner, repo, number, [self._done_label])
        await self._remove_label(installation_id, owner, repo, number, self._active_label)

        close_turn = event.conversation[-1] if event.conversation else None
        close_reason = (close_turn.evidence or "resolved") if close_turn else "resolved"
        close_reason = re.sub(r'[<>@`]', '', close_reason)[:200]
        if close_reason not in ("stale", "duplicate"):
            turns = len(event.conversation)
            await self._post_comment(installation_id, owner, repo, number,
                f"**Darwin** closed this issue ({turns} turns). Outcome: {close_reason}")

        await self.blackboard.mark_feedback_sent(event.id)

    async def post_feedback(self, event: object) -> None:
        """Post resolution feedback as PR comment + label lifecycle (active→done)."""
        gh_ctx = None
        if hasattr(event, "event") and event.event.evidence and hasattr(event.event.evidence, "github_context"):
            gh_ctx = event.event.evidence.github_context
        if not gh_ctx:
            return

        owner = gh_ctx.get("owner", "")
        repo = gh_ctx.get("repo", "")
        pr_number = gh_ctx.get("pr_number", 0)
        installation_id = gh_ctx.get("installation_id", "")
        if not owner or not repo or not pr_number:
            return

        close_turn = event.conversation[-1] if event.conversation else None
        close_reason = (close_turn.evidence or "resolved") if close_turn else "resolved"
        close_reason = re.sub(r'[<>@`]', '', close_reason)[:200]

        await self._remove_label(installation_id, owner, repo, pr_number, self._active_label)
        await self._add_labels(installation_id, owner, repo, pr_number, [self._done_label])

        head_sha = gh_ctx.get("head_sha", "")
        if head_sha:
            try:
                await self.blackboard.set_github_pr_sha(owner, repo, pr_number, head_sha)
            except Exception as e:
                logger.warning(f"SHA store failed for {owner}/{repo}#{pr_number}: {e}")

        if close_reason not in ("stale", "duplicate"):
            comment_body = self._build_feedback_comment(event, close_reason)
            await self._post_comment(installation_id, owner, repo, pr_number, comment_body)

        await self.blackboard.mark_feedback_sent(event.id)

    # =========================================================================
    # Brain-Facing Methods (NOT part of VcsPlatformPort)
    # =========================================================================

    async def refresh_pr_state(self, event_id: str, *,
                               override_owner: str | None = None,
                               override_repo: str | None = None,
                               override_pr_number: int | None = None) -> dict:
        """Re-fetch current PR/check state from GitHub and update event evidence."""
        event = await self.blackboard.get_event(event_id)
        if not event:
            return {"error": f"Event {event_id} not found"}

        gh_ctx = None
        if event.event.evidence and hasattr(event.event.evidence, "github_context"):
            gh_ctx = event.event.evidence.github_context

        owner = override_owner or (gh_ctx.get("owner") if gh_ctx else None)
        repo = override_repo or (gh_ctx.get("repo") if gh_ctx else None)
        pr_number = override_pr_number or (gh_ctx.get("pr_number") if gh_ctx else None)

        if not owner or not repo or not pr_number:
            return {"error": "No PR reference available. Supply pr_url or ensure the event has github_context."}

        client = await self._get_client_for_repo(owner, repo)
        if not client:
            return {"error": "GitHub client unavailable"}

        try:
            pr_resp = await client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
            pr = pr_resp.json()
            pr_state = pr.get("state", "unknown")
            head_sha = pr.get("head", {}).get("sha", "")

            check_resp = await client.get(
                f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
                params={"per_page": "50"},
            )
            check_runs = check_resp.json().get("check_runs", [])
            check_status = self._aggregate_check_status(check_runs)
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                result = {"error": "PR not found", "pr_state": "closed", "check_status": "unknown", "severity": "info"}
                await self.blackboard.update_event_github_context(event_id, result)
                return result
            return {"error": f"GitHub API error: {e.response.status_code}", "pr_state": "unknown",
                    "check_status": "unknown", "severity": "warning"}
        except Exception as e:
            return {"error": f"GitHub API unavailable: {e}", "pr_state": "unknown",
                    "check_status": "unknown", "severity": "warning"}

        action = (gh_ctx or {}).get("action", "review_requested")
        severity = self.classify_severity(action, check_status)
        result = {
            "pr_state": pr_state,
            "check_status": check_status,
            "severity": severity,
        }

        await self.blackboard.update_event_github_context(event_id, result)
        logger.info(f"Refreshed PR state for {event_id}: check={check_status}, pr={pr_state}")
        return result

    async def poll_github_pr_status(self, owner: str, repo: str, pr_number: int) -> dict:
        """Lightweight read-only poll for StateWatcher. Raises on HTTP errors."""
        client = await self._get_client_for_repo(owner, repo)
        if not client:
            raise RuntimeError(f"No installation found for {owner}/{repo}")

        pr_resp = await client.get(f"/repos/{owner}/{repo}/pulls/{pr_number}")
        pr = pr_resp.json()
        head_sha = pr.get("head", {}).get("sha", "")

        check_resp = await client.get(
            f"/repos/{owner}/{repo}/commits/{head_sha}/check-runs",
            params={"per_page": "50"},
        )
        check_runs = check_resp.json().get("check_runs", [])
        return {
            "pr_state": pr.get("state", "unknown"),
            "check_status": self._aggregate_check_status(check_runs),
        }

    @staticmethod
    def extract_github_state_key(state: dict) -> dict:
        """Canonical state_key builder. mergeable excluded (flaps during CI runs)."""
        return {
            "pr_state": state.get("pr_state", "unknown"),
            "check_status": state.get("check_status", "unknown"),
        }

    @staticmethod
    def parse_pr_url(url: str) -> tuple[str, str, int] | None:
        """Extract (owner, repo, pr_number) from a GitHub PR URL.

        Supports: https://github.com/owner/repo/pull/123
        Only accepts github.com as host (defense-in-depth).
        """
        sep = "/pull/"
        if sep not in url:
            return None
        left, right = url.split(sep, 1)
        pr_str = right.split("/")[0].split("?")[0].split("#")[0]
        if not pr_str.isdigit():
            return None
        without_proto = left.split("://", 1)[-1]
        path_parts = without_proto.split("/")
        if len(path_parts) < 3:
            return None
        host = path_parts[0]
        if host not in ("github.com", "www.github.com"):
            return None
        owner = path_parts[1]
        repo = path_parts[2]
        if ".." in owner or ".." in repo or "/" in owner or "/" in repo:
            return None
        return owner, repo, int(pr_str)

    # =========================================================================
    # Queue Helpers
    # =========================================================================

    async def _queue_pr(self, pr: dict, position: int) -> None:
        """Acknowledge a PR into the darwin-queued state.

        Label ordering: ADD darwin-queued BEFORE removing darwin-review (prevents orphan).
        Comment is informational — failure is silent (best-effort).
        Idempotency: if darwin-queued already present (pod restart), skip comment.
        """
        owner = pr["owner"]
        repo = pr["repo"]
        number = pr["number"]
        installation_id = pr.get("installation_id", "")
        labels = set(pr.get("labels", []))
        already_queued = self._queued_label in labels

        await self._add_labels(installation_id, owner, repo, number, [self._queued_label])
        await self._remove_label(installation_id, owner, repo, number, self._trigger_label)

        if not already_queued:
            await self._post_comment(
                installation_id, owner, repo, number,
                f"**Darwin** acknowledged your PR — queued at position {position}. "
                "FIFO processing when capacity opens.",
            )

    # =========================================================================
    # Label / Comment Helpers (best-effort, never raise)
    # =========================================================================

    async def _ensure_label_exists(self, installation_id: str, owner: str, repo: str, label: str, color: str = "7C3AED") -> None:
        """Create label on repo if missing. Only silences 'already_exists' 422 and 409."""
        client = await self._resolve_client(installation_id, owner, repo)
        if not client:
            return
        try:
            await client.post(f"/repos/{owner}/{repo}/labels", json={
                "name": label, "color": color, "description": "Darwin PR lifecycle",
            })
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 409:
                pass
            elif e.response.status_code == 422:
                body = e.response.json() if e.response.content else {}
                errors = body.get("errors", [])
                if not any(err.get("code") == "already_exists" for err in errors):
                    logger.warning(f"Label create validation failed for {owner}/{repo}: {label} — {body}")
            else:
                logger.debug(f"Label ensure failed ({e.response.status_code}) for {owner}/{repo}: {label}")
        except Exception:
            pass

    async def _add_labels(self, installation_id: str, owner: str, repo: str, pr_number: int, labels: list[str]) -> None:
        """Best-effort: ensure labels exist on repo, then add to PR."""
        client = await self._resolve_client(installation_id, owner, repo)
        if not client:
            return
        for label in labels:
            await self._ensure_label_exists(installation_id, owner, repo, label)
        try:
            await client.post(f"/repos/{owner}/{repo}/issues/{pr_number}/labels", json={"labels": labels})
        except httpx.HTTPStatusError as e:
            logger.warning(f"Label add failed ({e.response.status_code}) for {owner}/{repo}#{pr_number}: {labels}")
        except Exception as e:
            logger.warning(f"Label add error for {owner}/{repo}#{pr_number}: {e}")

    async def _remove_label(self, installation_id: str, owner: str, repo: str, pr_number: int, label: str) -> None:
        """Best-effort: remove label from PR. 404 is expected and silenced."""
        client = await self._resolve_client(installation_id, owner, repo)
        if not client:
            return
        encoded = urllib.parse.quote(label, safe="")
        try:
            await client.delete(f"/repos/{owner}/{repo}/issues/{pr_number}/labels/{encoded}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code != 404:
                logger.warning(f"Label remove failed ({e.response.status_code}) for {owner}/{repo}#{pr_number}: {label}")
        except Exception as e:
            logger.warning(f"Label remove error for {owner}/{repo}#{pr_number}: {e}")

    async def _post_comment(self, installation_id: str, owner: str, repo: str, pr_number: int, body: str) -> None:
        """Best-effort: post comment on PR."""
        client = await self._resolve_client(installation_id, owner, repo)
        if not client:
            return
        try:
            await client.post(f"/repos/{owner}/{repo}/issues/{pr_number}/comments", json={"body": body})
        except httpx.HTTPStatusError as e:
            logger.warning(f"Comment post failed ({e.response.status_code}) for {owner}/{repo}#{pr_number}")
        except Exception as e:
            logger.warning(f"Comment error for {owner}/{repo}#{pr_number}: {e}")

    # =========================================================================
    # Internal Helpers
    # =========================================================================

    @staticmethod
    def _resolve_maintainer() -> dict:
        """Resolve maintainer for escalation (static fallback for v1)."""
        emails = _get_static_maintainer_emails()
        if emails:
            return {"source": "static", "emails": emails}
        return {"source": "static", "emails": []}

    @staticmethod
    def _build_feedback_comment(event, close_reason: str) -> str:
        """Build structured GitHub PR comment from event outcome."""
        import time as _time
        actions = []
        for t in event.conversation:
            if t.actor in ("user", "brain"):
                continue
            if t.action == "execute" and t.result:
                ts = _time.strftime("%H:%M", _time.gmtime(t.timestamp)) if t.timestamp else ""
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
