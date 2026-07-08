# BlackBoard/src/agents/headhunter_github.py
# @ai-rules:
# 1. [Pattern]: Implements VcsPlatformPort for GitHub. All GitHub API calls live here.
# 2. [Constraint]: AIR GAP: No kubernetes imports. GitHub API via AsyncGitHubClient only.
# 3. [Pattern]: Dedup by (owner, repo, pr_number). Search API as primary discovery.
# 4. [Pattern]: Brain-facing methods (refresh_pr_state, poll_github_pr_status, extract_github_state_key)
#    are NOT part of VcsPlatformPort — they're GitHub-specific, accessed via Headhunter delegates.
# 5. [Pattern]: _load_github_si() loads from headhunter_skills/github-pr-triage.md with emergency fallback.
# 6. [Gotcha]: mergeable excluded from state_key (flaps during CI runs).
# 7. [Pattern]: Lazy-init auth via get_github_auth() singleton — never raises in constructor.
# 8. [Gotcha]: _list_from_repos only includes PRs where the bot IS in requested_reviewers. No empty-reviewer fallback.
# 9. [Pattern]: 429/5xx propagate to circuit breaker. Only 422 (search not indexed) is silently caught.
"""
GitHub Platform Adapter for Headhunter.

Implements VcsPlatformPort for the GitHub PR polling workflow.
Also exposes Brain-facing methods for refresh_github_context and StateWatcher integration.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import TYPE_CHECKING

import httpx

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

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
        self._client = None
        self._repos: list[str] = []
        repos_env = os.getenv("HEADHUNTER_GITHUB_REPOS", "")
        if repos_env.strip():
            self._repos = [r.strip() for r in repos_env.split(",") if r.strip()]
        self._trigger_reasons: set[str] = set(
            os.getenv("HEADHUNTER_GITHUB_TRIGGER_REASONS", "review_requested").split(",")
        )

    # =========================================================================
    # VcsPlatformPort Implementation
    # =========================================================================

    @property
    def platform_name(self) -> str:
        return "github"

    def enabled(self) -> bool:
        return (
            os.getenv("HEADHUNTER_GITHUB_ENABLED", "false").lower() == "true"
            and bool(os.getenv("GITHUB_APP_ID"))
            and bool(os.getenv("GITHUB_INSTALLATION_ID"))
        )

    def _get_client(self):
        """Lazy-init AsyncGitHubClient. Returns None if auth is unavailable."""
        if self._client is None:
            try:
                from ..utils.github_app import get_github_auth, AsyncGitHubClient
                self._client = AsyncGitHubClient(get_github_auth())
            except Exception as e:
                logger.warning(f"GitHub client init failed: {e}")
                return None
        return self._client

    async def close(self) -> None:
        """Shut down the persistent HTTP client."""
        if self._client:
            await self._client.close()
            self._client = None

    async def get_active_keys(self) -> set[tuple[str, str, int]]:
        """Get (owner, repo, pr_number) for all active/deferred headhunter events with github_context."""
        active_ids = await self.blackboard.get_active_events()
        keys: set[tuple[str, str, int]] = set()
        for eid in active_ids:
            event = await self.blackboard.get_event(eid)
            if not event or event.source != "headhunter":
                continue
            if event.status.value not in ("new", "active", "deferred"):
                continue
            ctx = getattr(event.event.evidence, "github_context", None) if event.event and event.event.evidence else None
            if ctx:
                owner = ctx.get("owner", "") if isinstance(ctx, dict) else getattr(ctx, "owner", "")
                repo = ctx.get("repo", "") if isinstance(ctx, dict) else getattr(ctx, "repo", "")
                pr_num = ctx.get("pr_number", 0) if isinstance(ctx, dict) else getattr(ctx, "pr_number", 0)
                if owner and repo and pr_num:
                    keys.add((owner, repo, pr_num))
        return keys

    async def poll_work_items(self) -> list[dict]:
        """Discover PRs needing attention via GitHub Search API with repo-scoped fallback."""
        client = self._get_client()
        if not client:
            return []

        if self._repos:
            prs = await self._list_from_repos(client)
        else:
            prs = await self._search_review_requested(client)

        active_keys = await self.get_active_keys()
        result = []
        skipped_terminal = 0
        for pr in prs:
            key = (pr["owner"], pr["repo"], pr["number"])
            if key in active_keys:
                continue
            if pr.get("state") in ("closed",):
                skipped_terminal += 1
                continue
            result.append(pr)

        logger.info(
            f"GitHub poll: {len(prs)} discovered, {len(active_keys)} active, "
            f"{skipped_terminal} terminal, {len(result)} new"
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

    async def _list_from_repos(self, client) -> list[dict]:
        """List open PRs from explicitly configured repos.

        When repos are pinned, all open PRs are candidates (the user opted in
        by configuring the repo list). GitHub Apps cannot be requested as
        reviewers via the API, so we don't filter on requested_reviewers here.
        Dedup against active events prevents duplicates.
        """
        prs: list[dict] = []
        for repo_full in self._repos:
            try:
                resp = await client.get(
                    f"/repos/{repo_full}/pulls",
                    params={"state": "open", "per_page": "30"},
                )
                for pr_data in resp.json():
                    prs.append(self._normalize_pr_data(repo_full, pr_data))
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (404, 422):
                    logger.warning(f"GitHub repo list {e.response.status_code} for {repo_full}")
                    continue
                raise
        return prs

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
        }

    @staticmethod
    def _normalize_pr_data(repo_full: str, pr_data: dict) -> dict:
        """Normalize a repo PR list item to our internal work item shape."""
        parts = repo_full.split("/", 1)
        owner = parts[0] if parts else ""
        repo = parts[1] if len(parts) > 1 else ""
        return {
            "owner": owner,
            "repo": repo,
            "number": pr_data["number"],
            "title": pr_data.get("title", ""),
            "state": pr_data.get("state", "open"),
            "user": pr_data.get("user", {}).get("login", ""),
            "labels": [l.get("name", "") for l in pr_data.get("labels", [])],
            "html_url": pr_data.get("html_url", ""),
            "created_at": pr_data.get("created_at", ""),
        }

    async def fetch_context(self, work_item: dict) -> dict:
        """Enrich a PR work item with full context from GitHub API."""
        client = self._get_client()
        if not client:
            return self._minimal_context(work_item)

        owner = work_item["owner"]
        repo = work_item["repo"]
        number = work_item["number"]

        context: dict = {
            "owner": owner,
            "repo": repo,
            "pr_number": number,
            "pr_title": work_item.get("title", ""),
            "pr_state": work_item.get("state", "open"),
            "author": work_item.get("user", ""),
            "labels": work_item.get("labels", []),
            "pr_url": work_item.get("html_url", f"https://github.com/{owner}/{repo}/pull/{number}"),
            "action": "review_requested",
        }

        try:
            pr_resp = await client.get(f"/repos/{owner}/{repo}/pulls/{number}")
            pr = pr_resp.json()
            context["head_sha"] = (pr.get("head") or {}).get("sha", "")
            context["head_branch"] = (pr.get("head") or {}).get("ref", "")
            context["base_branch"] = (pr.get("base") or {}).get("ref", "")
            context["pr_body"] = (pr.get("body") or "")[:2000]
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
                if c.get("user", {}).get("login") == bot_name:
                    continue
                entry = f"[{c.get('user', {}).get('login', '?')}]: {(c.get('body') or '')[:500]}"
                total_len += len(entry)
                if total_len > 2000:
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
        return event_id

    async def post_feedback(self, event: object) -> None:
        """Post resolution feedback as PR comment."""
        gh_ctx = None
        if hasattr(event, "event") and event.event.evidence and hasattr(event.event.evidence, "github_context"):
            gh_ctx = event.event.evidence.github_context
        if not gh_ctx:
            return

        owner = gh_ctx.get("owner", "")
        repo = gh_ctx.get("repo", "")
        pr_number = gh_ctx.get("pr_number", 0)
        if not owner or not repo or not pr_number:
            return

        client = self._get_client()
        if not client:
            logger.warning(f"GitHub feedback skipped (no client) for {event.id}")
            return

        close_turn = event.conversation[-1] if event.conversation else None
        close_reason = (close_turn.evidence or "resolved") if close_turn else "resolved"

        if close_reason in ("stale", "duplicate"):
            await self.blackboard.mark_feedback_sent(event.id)
            return

        comment_body = self._build_feedback_comment(event, close_reason)

        try:
            await client.post(
                f"/repos/{owner}/{repo}/issues/{pr_number}/comments",
                json={"body": comment_body},
            )
            await self.blackboard.mark_feedback_sent(event.id)
            logger.info(f"GitHub feedback posted for {event.id} on #{pr_number}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.info(f"Feedback skip: PR #{pr_number} not found in {owner}/{repo}")
                await self.blackboard.mark_feedback_sent(event.id)
            elif e.response.status_code == 403:
                logger.warning(f"GitHub feedback forbidden for {event.id} (permissions?)")
            else:
                logger.warning(f"GitHub feedback failed ({e.response.status_code}) for {event.id}")
        except Exception as e:
            logger.warning(f"GitHub feedback error for {event.id}: {e}")

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

        client = self._get_client()
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
        client = self._get_client()
        if not client:
            raise RuntimeError("GitHub client unavailable for poll")

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
