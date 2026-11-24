# BlackBoard/src/agents/headhunter_jira.py
# @ai-rules:
# 1. [Pattern]: Headhunter Jira daemon head; lazy Claude adapter; AIR GAP (httpx only, no k8s).
# 2. [Pattern]: Two-phase poll: Planning -> analyze+comment (caches analysis in Redis), To Do -> Brain event (reuses Redis/bot-comment analysis or resolves label skill).
# 3. [Pattern]: Re-eval gate: watchers @mentioning bot trigger re-analysis (ADF recursive walk).
# 4. [Constraint]: All config from env vars. Label-driven skills (HEADHUNTER_JIRA_SKILL_<LABEL>, 5m cache, 10KB cap -> BA fallback).
# 5. [Pattern]: Global WIP flow gate (MAX_ACTIVE_EVENTS), Redis state (darwin:headhunter:jira:{key}, 7d TTL), and bounded 1-shot duplicate-close recovery (duplicate_retried: True).
# 6. [Pattern]: Cold-start recovery anchors to latest bot comment (0 Jira calls, 10/cycle cap) and runs reeval check same cycle with per-issue try/except isolation.
# 7. [Pattern]: Plan generation uses produce_execution_plan tool with tool_choice={"type": "auto"} (Claude 5.x rejects "tool"/"any"); both tool and YAML-fallback paths fail closed via _validate_plan_yaml().
# 8. [Pattern]: ADF bodies render via utils.adf.adf_to_markdown().
"""Headhunter Jira: polls Jira issues assigned to bot with a label filter."""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from collections.abc import Awaitable, Callable
from typing import TYPE_CHECKING, Any

import httpx

from ..utils.adf import adf_to_markdown
from ..utils.jira_context import extract_jira_context

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# System prompts (from probe_jira_analyst.py -- production versions)
# ---------------------------------------------------------------------------

BUSINESS_ANALYST_SYSTEM_PROMPT = """You are a QE Business Analyst for the KubeVirt OpenShift Console Plugin test automation team.

Your job: analyze a Jira issue and produce a structured validation plan that a QE agent can execute.

## Domain Context

The kubevirt-ui repository contains E2E tests (Playwright) for the KubeVirt OpenShift Console Plugin.
Architecture: Tests -> StepDrivers -> PageObjects -> Clients (KubernetesClient, OcCliClient, VirtctlClient).
Test tiers: gating (< 2 min, smoke), tier1 (< 6 min, CRUD), tier2 (< 6 min, complex multi-resource).

## Key StepDrivers
- VirtualMachinesStepDriver: VM list, tree view, overview tab, bulk ops
- VirtualMachineDetailStepDriver: VM detail tabs (overview, config, events, console, snapshots)
- KubernetesStepDriver: API-driven CRUD, verification, wait
- CatalogStepDriver: Template/IT VM creation, customize wizard
- PageCommonsStepDriver: Sidebar navigation, perspective switcher, common modals

## Your Task

Given a Jira issue, produce:

1. **Issue Summary**: One-line description of what needs verification
2. **Validation Points**: Specific UI behaviors to verify
3. **Test Strategy**: How to verify (which page, which interactions, what assertions)
4. **Preconditions**: Resources needed (VM, namespace, specific template)
5. **Suggested Tier**: gating/tier1/tier2 with justification
6. **Risk Assessment**: What could make this verification fail or be flaky
7. **Environment Constraints**: Single cluster vs ACM, specific storage classes, etc.

## Output Format

Use structured markdown. Be specific -- reference actual UI elements, data-test attributes when inferable, and StepDriver methods when applicable. If the issue links to a PR, note what code change needs verification.

Do NOT invent test code. Your output is a plan for the QE agent to follow, not implementation."""


BRAIN_PLAN_SYSTEM_PROMPT = """You are a workflow planner for the Darwin autonomous operations system.

Given an analysis of a Jira issue, produce a structured execution plan using the produce_execution_plan tool.

## Agent Roles

- architect: code review, analysis, design assessment, plan creation (READ-ONLY)
- developer: implementation, code changes, bug fixes, creating branches/MRs (WRITE access)
- qe: testing, verification, running test suites, validating fixes (READ + EXECUTE tests)
- sysadmin: infrastructure, deployment, cluster operations, pipeline investigation
- security_analyst: vulnerability scanning, CVE remediation, dependency audit, supply chain security
- code_reviewer: dedicated multi-lens review gate for formal pre-merge quality checks -- six parallel specialized subagents (architecture, correctness, maintainability, security, reliability, testing) merged into one severity-graded report (READ-ONLY, ephemeral)

## Rules

- Steps must be independently executable and verifiable
- First step should always be environment verification
- Include the repo URL if the agent needs to clone code
- Use mode=investigate for read-only, mode=test for assertion-based verification
- Use architect (not developer) for code review and analysis steps
- Use developer only when the step requires writing/modifying code
- Keep steps atomic -- one concern per step
- Reference the Jira issue key in relevant step summaries"""


# ---------------------------------------------------------------------------
# Plan tool schema (function calling replaces text-based YAML parsing)
# ---------------------------------------------------------------------------

PLAN_TOOL_SCHEMA = {
    "name": "produce_execution_plan",
    "description": "Submit the structured execution plan for this Jira issue.",
    "input_schema": {
        "type": "object",
        "properties": {
            "plan": {"type": "string", "description": "One-line plan description"},
            "service": {"type": "string", "description": "Service or component name"},
            "repository": {"type": "string", "description": "Git repository URL"},
            "risk": {"type": "string", "enum": ["low", "medium", "high"]},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Short kebab-case step ID"},
                        "agent": {"type": "string", "enum": ["qe", "developer", "architect", "sysadmin", "security_analyst", "code_reviewer"]},
                        "mode": {"type": "string", "enum": ["investigate", "test", "implement", "execute", "review"]},
                        "summary": {"type": "string", "description": "What this step does"},
                    },
                    "required": ["id", "agent", "mode", "summary"],
                },
            },
        },
        "required": ["plan", "service", "repository", "risk", "steps"],
    },
}


# ---------------------------------------------------------------------------
# Jira issue formatter (reused from probe script)
# ---------------------------------------------------------------------------

def format_jira_for_llm(issue: dict) -> str:
    """Format Jira issue into a structured prompt for the LLM."""
    fields = issue.get("fields", {})
    key = issue.get("key", "?")

    parts = [
        f"# Jira Issue: {key}",
        f"**Summary:** {fields.get('summary', 'N/A')}",
        f"**Type:** {fields.get('issuetype', {}).get('name', 'N/A')}",
        f"**Status:** {fields.get('status', {}).get('name', 'N/A')}",
        f"**Priority:** {fields.get('priority', {}).get('name', 'N/A')}",
    ]

    components = [c.get("name", "") for c in fields.get("components", [])]
    if components:
        parts.append(f"**Components:** {', '.join(components)}")

    fix_versions = [v.get("name", "") for v in fields.get("fixVersions", [])]
    if fix_versions:
        parts.append(f"**Fix Versions:** {', '.join(fix_versions)}")

    labels = fields.get("labels", [])
    if labels:
        parts.append(f"**Labels:** {', '.join(labels)}")

    parent = fields.get("parent", {})
    if parent:
        parts.append(f"**Parent:** {parent.get('key', '')} - {parent.get('fields', {}).get('summary', '')}")

    desc = fields.get("description", "")
    if desc:
        if isinstance(desc, dict):
            desc = adf_to_markdown(desc)
        parts.append(f"\n## Description\n\n{desc}")

    comments = fields.get("comment", {}).get("comments", [])
    if comments:
        parts.append("\n## Comments")
        for c in comments[-5:]:
            author = c.get("author", {}).get("displayName", "Unknown")
            body = c.get("body", "")
            if isinstance(body, dict):
                body = adf_to_markdown(body)
            parts.append(f"\n**{author}:**\n{body}")

    links = fields.get("issuelinks", [])
    if links:
        parts.append("\n## Linked Issues")
        for link in links:
            link_type = link.get("type", {}).get("name", "")
            inward = link.get("inwardIssue", {})
            outward = link.get("outwardIssue", {})
            target = inward or outward
            if target:
                parts.append(f"- {link_type}: {target.get('key', '')} - {target.get('fields', {}).get('summary', '')}")

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# ADF (Atlassian Document Format) helpers
# ---------------------------------------------------------------------------

def _walk_adf_mentions(body: dict | list) -> set[str]:
    """Extract all mentioned accountIds from an ADF document body."""
    mentions: set[str] = set()

    def _walk(node: Any) -> None:
        if isinstance(node, dict):
            if node.get("type") == "mention":
                account_id = node.get("attrs", {}).get("id", "")
                if account_id:
                    mentions.add(account_id)
            for child in node.get("content", []):
                _walk(child)
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(body)
    return mentions


# ---------------------------------------------------------------------------
# HeadhunterJira
# ---------------------------------------------------------------------------

class HeadhunterJira:
    """Jira polling head -- two-phase flow for mission analysis and event creation."""

    REDIS_PREFIX = "darwin:headhunter:jira:"
    REDIS_TTL = 604800  # 7 days
    _MAX_RECOVERY_PLAN_FAILURES = 2

    def __init__(self, blackboard: BlackboardState):
        self.blackboard = blackboard
        self._jira_url = os.getenv("JIRA_URL", "")
        self._jira_email = os.getenv("JIRA_EMAIL", "")
        self._jira_token = os.getenv("JIRA_API_TOKEN", "")
        self._bot_account_id = os.getenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "")
        self._jira_label = os.getenv("HEADHUNTER_JIRA_LABEL", "darwin")
        self._model = os.getenv("LLM_MODEL_HEADHUNTER_JIRA", "claude-sonnet-5-5")
        self._wip_cap = int(os.getenv("MAX_ACTIVE_EVENTS", "20"))
        self._wip_counter: Any = None
        self._claude_adapter = None
        # Label-driven skill selection: env HEADHUNTER_JIRA_SKILL_<LABEL>=<git raw url>
        self._skill_urls: dict[str, str] = {}
        for key, value in os.environ.items():
            if key.startswith("HEADHUNTER_JIRA_SKILL_"):
                label = key[len("HEADHUNTER_JIRA_SKILL_"):].lower()
                self._skill_urls[label] = value
        self._skill_cache: dict[str, dict] = {}
        if self._skill_urls:
            logger.info(f"Jira skill labels configured: {list(self._skill_urls.keys())}")
        # Redis-backed state -- survives pod restarts

    def enabled(self) -> bool:
        """Returns True if required env vars are configured."""
        return bool(self._jira_url and self._jira_token and self._bot_account_id)

    # =========================================================================
    # Redis State (durable issue tracking -- survives pod restarts)
    # =========================================================================

    async def _get_issue_state(self, key: str) -> dict | None:
        """Get Redis-backed state for an issue. Returns None if expired or never set."""
        raw = await self.blackboard.redis.get(f"{self.REDIS_PREFIX}{key}")
        if not raw:
            return None
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            raise ValueError(f"Expected dict Redis state for {key}, got {type(parsed).__name__}")
        return parsed

    async def _set_issue_state(self, key: str, state: dict) -> None:
        """Persist issue state to Redis with 7-day TTL."""
        state["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        await self.blackboard.redis.set(
            f"{self.REDIS_PREFIX}{key}", json.dumps(state), ex=self.REDIS_TTL
        )

    # =========================================================================
    # Claude Adapter (lazy-loaded, same pattern as Archivist)
    # =========================================================================

    def _get_claude_adapter(self):
        """Lazy-load Claude adapter via create_adapter factory."""
        if self._claude_adapter is None:
            try:
                from .llm import create_adapter
                project = os.getenv("GCP_PROJECT", "")
                location = os.getenv("GCP_LOCATION", "global")
                self._claude_adapter = create_adapter("claude", project, location, self._model)
                logger.info(f"Jira Claude adapter initialized: {self._model}")
            except Exception as e:
                logger.warning(f"Claude adapter not available for Jira head: {e}")
                return None
        return self._claude_adapter

    # =========================================================================
    # Label-Driven Skill Resolution
    # =========================================================================

    async def _fetch_skill(self, label: str) -> str | None:
        """Fetch skill content from git raw URL. 5-min in-memory cache."""
        url = self._skill_urls.get(label)
        if not url:
            return None
        cached = self._skill_cache.get(label)
        if cached and (time.time() - cached["ts"]) < 300:
            return cached["content"]
        try:
            headers = {}
            gitlab_token_path = os.getenv("GITLAB_TOKEN_PATH", "")
            if gitlab_token_path and "gitlab" in url.lower():
                try:
                    with open(gitlab_token_path) as f:
                        headers["PRIVATE-TOKEN"] = f.read().strip()
                except OSError:
                    pass
            fetch_url = self._to_gitlab_api_url(url) if "gitlab" in url.lower() else url
            async with httpx.AsyncClient(timeout=10, verify=False, follow_redirects=True) as client:
                resp = await client.get(fetch_url, headers=headers)
                if resp.status_code == 200:
                    content = resp.text
                    if content.strip().startswith("<!DOCTYPE") or "<html" in content[:200]:
                        logger.warning(f"Skill fetch for '{label}' returned HTML (login page?) -- token may be expired")
                        return None
                    if len(content) > 10240:
                        logger.warning(
                            f"Skill URL {url} exceeds 10KB ({len(content)} bytes), using fallback"
                        )
                        self._skill_cache[label] = {"content": BUSINESS_ANALYST_SYSTEM_PROMPT, "ts": time.time()}
                        return None
                    self._skill_cache[label] = {"content": content, "ts": time.time()}
                    logger.debug(f"Skill fetched for label '{label}' ({len(content)} chars)")
                    return content
                logger.warning(f"Skill fetch returned {resp.status_code} for '{label}'")
        except Exception as e:
            logger.warning(f"Skill fetch failed for '{label}': {e}")
        return None

    @staticmethod
    def _to_gitlab_api_url(raw_url: str) -> str:
        """Convert GitLab raw file URL to API endpoint format.

        /-/raw/main/path/file.md -> /api/v4/projects/{encoded}/repository/files/{encoded_path}/raw?ref=main
        Already API format -> return as-is.
        """
        if "/api/v4/" in raw_url:
            return raw_url
        import re
        from urllib.parse import quote
        match = re.match(
            r"(https?://[^/]+)/([^/]+/[^/]+)/-/raw/([^/]+)/(.+?)(?:\?.*)?$",
            raw_url,
        )
        if not match:
            return raw_url
        host, project_path, ref, file_path = match.groups()
        encoded_project = quote(project_path, safe="")
        encoded_file = quote(file_path, safe="")
        return f"{host}/api/v4/projects/{encoded_project}/repository/files/{encoded_file}/raw?ref={ref}"

    async def _resolve_system_prompt(self, issue: dict) -> str:
        """Pick system prompt based on issue labels. Falls back to built-in BA prompt."""
        labels = [l.lower() for l in issue.get("fields", {}).get("labels", []) if l.lower() != self._jira_label]
        for label in labels:
            if label in self._skill_urls:
                skill_content = await self._fetch_skill(label)
                if skill_content:
                    logger.info(f"Using skill '{label}' for {issue.get('key', '?')}")
                    return skill_content
        return BUSINESS_ANALYST_SYSTEM_PROMPT

    # =========================================================================
    # Jira REST Client
    # =========================================================================

    def _auth_header(self) -> str:
        return base64.b64encode(f"{self._jira_email}:{self._jira_token}".encode()).decode()

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        """GET request to Jira REST API."""
        url = f"{self._jira_url}{path}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                url,
                headers={"Authorization": f"Basic {self._auth_header()}"},
                params=params,
            )
            resp.raise_for_status()
            return resp

    async def _post(self, path: str, json_body: dict) -> httpx.Response:
        """POST request to Jira REST API."""
        url = f"{self._jira_url}{path}"
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Basic {self._auth_header()}",
                    "Content-Type": "application/json",
                },
                json=json_body,
            )
            resp.raise_for_status()
            return resp

    async def _jql_search(self, jql: str) -> list[dict]:
        """Execute JQL with pagination. Returns all matching issues."""
        issues: list[dict] = []
        start_at = 0
        max_results = 50
        while True:
            resp = await self._get(
                "/rest/api/3/search/jql",
                params={
                    "jql": jql,
                    "startAt": str(start_at),
                    "maxResults": str(max_results),
                    "fields": "summary,description,status,comment,issuelinks,parent,labels,components,fixVersions",
                },
            )
            data = resp.json()
            issues.extend(data.get("issues", []))
            total = data.get("total", 0)
            start_at += max_results
            if start_at >= total:
                break
        return issues

    async def get_watchers(self, issue_key: str) -> set[str]:
        """GET /issue/{key}/watchers -> set of accountIds."""
        resp = await self._get(f"/rest/api/3/issue/{issue_key}/watchers")
        data = resp.json()
        return {w.get("accountId", "") for w in data.get("watchers", []) if w.get("accountId")}

    # =========================================================================
    # Poll Methods
    # =========================================================================

    async def poll_planning(self) -> list[dict]:
        """Fetch issues in Planning status assigned to bot with label."""
        jql = (
            f'assignee="{self._bot_account_id}" '
            f'AND labels="{self._jira_label}" '
            f'AND status="Planning"'
        )
        return await self._jql_search(jql)

    async def poll_todo(self) -> list[dict]:
        """Fetch issues in To Do status assigned to bot with label."""
        jql = (
            f'assignee="{self._bot_account_id}" '
            f'AND labels="{self._jira_label}" '
            f'AND status="To Do"'
        )
        return await self._jql_search(jql)

    # =========================================================================
    # Re-Evaluation Gate
    # =========================================================================

    def _mentions_bot(self, body: dict) -> bool:
        """Check if an ADF comment body mentions the bot account."""
        return self._bot_account_id in _walk_adf_mentions(body)

    async def has_reeval_signal(self, issue: dict, last_comment_id: str) -> bool:
        """Check if a watcher tagged the bot in a comment after our last analysis."""
        issue_key = issue.get("key", "?")
        watchers = await self.get_watchers(issue_key)
        comments = issue.get("fields", {}).get("comment", {}).get("comments", [])

        found_last = False
        scanned = 0
        for comment in comments:
            if comment["id"] == last_comment_id:
                found_last = True
                continue
            if not found_last:
                continue
            scanned += 1
            author_id = comment.get("author", {}).get("accountId", "")
            if author_id == self._bot_account_id:
                continue
            if author_id not in watchers:
                continue
            if self._mentions_bot(comment.get("body", {})):
                logger.info(
                    f"Jira reeval signal for {issue_key}: True "
                    f"(last_comment_id={last_comment_id}, scanned={scanned}, reason=watcher mention found)"
                )
                return True
        reason = "no comments after anchor" if scanned == 0 else "no watcher mentions"
        logger.info(
            f"Jira reeval signal for {issue_key}: False "
            f"(last_comment_id={last_comment_id}, scanned={scanned}, reason={reason})"
        )
        return False

    # =========================================================================
    # Claude Analysis + Comment
    # =========================================================================

    async def _run_claude_analysis(self, jira_content: str, system_prompt: str | None = None) -> str:
        """Run Claude analysis with given system prompt via streaming. Returns analysis text."""
        adapter = self._get_claude_adapter()
        if not adapter:
            raise RuntimeError("Claude adapter not available")
        chunks: list[str] = []
        async for chunk in adapter.generate_stream(
            system_prompt=system_prompt or BUSINESS_ANALYST_SYSTEM_PROMPT,
            contents=f"Analyze this Jira issue and produce a validation plan:\n\n{jira_content}",
        ):
            if chunk.text:
                chunks.append(chunk.text)
            if chunk.usage:
                from .llm import record_token_usage
                record_token_usage("headhunter_jira", chunk.usage)
        return "".join(chunks)

    async def _run_brain_plan(self, jira_content: str, analysis: str) -> str:
        """Run Claude plan generation via function calling. Returns clean YAML."""
        adapter = self._get_claude_adapter()
        if not adapter:
            raise RuntimeError("Claude adapter not available")

        text_chunks: list[str] = []
        function_call = None
        async for chunk in adapter.generate_stream(
            system_prompt=BRAIN_PLAN_SYSTEM_PROMPT,
            contents=(
                f"Produce a Brain execution plan for this approved analysis by calling "
                f"produce_execution_plan.\n\n"
                f"Jira issue context:\n{jira_content}\n\n"
                f"Approved validation plan:\n{analysis}"
            ),
            tools=[PLAN_TOOL_SCHEMA],
            tool_choice={"type": "auto"},
        ):
            if chunk.text and not getattr(chunk, "is_thought", False):
                text_chunks.append(chunk.text)
            if chunk.function_call:
                function_call = chunk.function_call
            if chunk.usage:
                from .llm import record_token_usage
                record_token_usage("headhunter_jira", chunk.usage)

        if function_call and function_call.name == "produce_execution_plan":
            return self._validate_plan_yaml(self._plan_args_to_yaml(function_call.args or {}))

        logger.warning("Claude did not call produce_execution_plan -- falling back to YAML extraction")
        return self._validate_plan_yaml(self._extract_yaml("".join(text_chunks)))

    @staticmethod
    def _validate_plan_yaml(raw_yaml: str) -> str:
        """Fail closed unless raw_yaml parses to a mapping with non-empty plan and valid steps."""
        import yaml

        candidate = (raw_yaml or "").strip()
        if not candidate:
            raise RuntimeError("Brain plan generation returned empty output")
        try:
            doc = yaml.safe_load(candidate)
        except yaml.YAMLError as e:
            raise RuntimeError(f"Brain plan YAML parse error: {e}") from e
        if not isinstance(doc, dict):
            raise RuntimeError("Brain plan output is not a YAML mapping")
        plan = doc.get("plan")
        steps = doc.get("steps")
        if not isinstance(plan, str) or not plan.strip():
            raise RuntimeError("Brain plan missing non-empty 'plan' field")
        if not isinstance(steps, list) or not steps:
            raise RuntimeError("Brain plan missing non-empty 'steps' list")
        for step in steps:
            if (
                not isinstance(step, dict)
                or not isinstance(step.get("agent"), str)
                or not step["agent"].strip()
                or not isinstance(step.get("summary"), str)
                or not step["summary"].strip()
            ):
                raise RuntimeError("Brain plan step missing non-empty 'agent' or 'summary'")
        return candidate

    @staticmethod
    def _plan_args_to_yaml(args: dict) -> str:
        """Convert structured tool args to YAML plan format."""
        import yaml
        plan_doc = {
            "plan": args.get("plan", ""),
            "service": args.get("service", ""),
            "repository": args.get("repository", ""),
            "risk": args.get("risk", "medium"),
            "steps": [
                {
                    "id": s.get("id", ""),
                    "agent": s.get("agent", ""),
                    "mode": s.get("mode", ""),
                    "summary": s.get("summary", ""),
                    "status": "pending",
                }
                for s in args.get("steps", [])
                if isinstance(s, dict)
            ],
        }
        return yaml.dump(plan_doc, default_flow_style=False, sort_keys=False).strip()

    @staticmethod
    def _extract_yaml(raw: str) -> str:
        """Strip markdown code fences and prose preamble from LLM YAML output."""
        lines = raw.strip().splitlines()
        in_fence = False
        yaml_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("```") and not in_fence:
                in_fence = True
                continue
            if stripped.startswith("```") and in_fence:
                in_fence = False
                continue
            if in_fence:
                yaml_lines.append(line)
        if yaml_lines:
            while yaml_lines and yaml_lines[0].strip() in ("---", "..."):
                yaml_lines.pop(0)
            while yaml_lines and yaml_lines[-1].strip() in ("---", "..."):
                yaml_lines.pop()
            return "\n".join(yaml_lines).strip()
        # No fences found -- try to find YAML by looking for '---' delimiters
        start = None
        for i, line in enumerate(lines):
            if line.strip() == "---" and start is None:
                start = i
                continue
            if line.strip() in ("---", "...") and start is not None:
                return "\n".join(lines[start + 1:i]).strip()
        # Last resort: return everything after stripping common LLM preambles
        for i, line in enumerate(lines):
            if line.strip().startswith("plan:"):
                return "\n".join(lines[i:]).strip()
            if line.strip() == "---":
                tail = lines[i + 1:]
                while tail and tail[-1].strip() in ("---", "..."):
                    tail.pop()
                return "\n".join(tail).strip()
        return raw.strip()

    async def analyze_and_comment(self, issue: dict) -> tuple[str, str] | None:
        """Run Claude analysis with label-resolved skill, post as Jira comment.

        Returns (comment_id, analysis_text) on success, None on failure.
        """
        try:
            jira_content = format_jira_for_llm(issue)
            system_prompt = await self._resolve_system_prompt(issue)
            analysis = await self._run_claude_analysis(jira_content, system_prompt)
            comment_id = await self.post_comment(issue["key"], analysis)
            logger.info(f"Jira analysis posted for {issue['key']}, comment_id={comment_id}")
            return comment_id, analysis
        except Exception as e:
            logger.warning(f"Jira analysis failed for {issue['key']}: {e}")
            return None

    async def post_comment(self, issue_key: str, body_text: str) -> str:
        """Post a structured comment to a Jira issue. Converts markdown to ADF."""
        from marklassian import markdown_to_adf
        adf_doc = markdown_to_adf(body_text)
        adf_body = {"body": adf_doc}
        resp = await self._post(f"/rest/api/3/issue/{issue_key}/comment", adf_body)
        return resp.json().get("id", "")

    # =========================================================================
    # Event Creation
    # =========================================================================

    def _resolve_mission_label(self, issue: dict) -> str:
        """Extract the primary non-base label (skill-URL match preferred, else first non-base)."""
        labels = [l.lower() for l in issue.get("fields", {}).get("labels", []) if l.lower() != self._jira_label]
        return next((l for l in labels if l in self._skill_urls), labels[0] if labels else "")

    async def create_jira_event(self, issue: dict, plan_yaml: str, mission_label: str = "") -> str:
        """Create Brain event for an approved Jira mission."""
        from ..models import EventEvidence

        fields = issue.get("fields", {})
        key = issue.get("key", "?")
        summary = fields.get("summary", "")
        display_text = (
            f"Jira mission ({mission_label}): {key} - {summary}"
            if mission_label
            else f"Jira mission: {key} - {summary}"
        )
        evidence = EventEvidence(
            display_text=display_text,
            source_type="headhunter",
            triggered_by="jira-bot",
            domain="disorder",
            domain_confidence="default",
            severity="info",
            jira_context={
                "issue_key": key,
                "issue_url": f"{self._jira_url}/browse/{key}",
                "summary": summary,
                "status": fields.get("status", {}).get("name", ""),
                "priority": fields.get("priority", {}).get("name", ""),
                "components": [c.get("name", "") for c in fields.get("components", [])],
                "labels": fields.get("labels", []),
                "mission_label": mission_label,
            },
        )
        service_name = key.split("-")[0].lower() if "-" in key else "unknown"
        event_id = await self.blackboard.create_event(
            source="headhunter",
            service=service_name,
            subject_type="jira",
            reason=plan_yaml,
            evidence=evidence,
        )
        logger.info(f"Jira event created: {event_id} for {key} (label={mission_label or 'default'})")
        return event_id

    # =========================================================================
    # Active Event Dedup + Flow Gate
    # =========================================================================

    async def _get_active_jira_keys(self) -> set[str]:
        """Get issue keys for all active, deferred, or waiting_approval Jira headhunter events."""
        active_ids = await self.blackboard.get_active_events()
        waiting_ids = await self.blackboard.get_waiting_approval_events()
        all_ids = list(dict.fromkeys(list(active_ids) + list(waiting_ids)))
        keys: set[str] = set()
        for eid in all_ids:
            try:
                event = await self.blackboard.get_event(eid)
            except (json.JSONDecodeError, ValueError, TypeError) as e:
                logger.warning(f"Skipping unreadable event {eid} in active Jira key scan: {e}")
                continue
            if (event and event.source == "headhunter"
                    and getattr(event.status, "value", event.status) in ("new", "active", "deferred", "waiting_approval")):
                is_jira, jira_key = extract_jira_context(event)
                if is_jira and jira_key:
                    keys.add(jira_key)
        return keys

    async def _should_retry_duplicate_event(self, key: str, state: dict[str, Any]) -> bool:
        """Allow a single bounded retry if the prior Brain event was closed as a false duplicate."""
        if state.get("duplicate_retried"):
            logger.debug(f"Jira {key}: duplicate recovery already retried once -- staying parked")
            return False
        event_id = state.get("event_id")
        if not isinstance(event_id, str) or not event_id.strip():
            return False
        event_id = event_id.strip()
        try:
            evt = await self.blackboard.get_event(event_id)
        except Exception as e:
            logger.warning(f"Jira {key}: failed to inspect prior event {event_id} for duplicate recovery: {e}")
            return False
        if evt is None or getattr(evt.status, "value", evt.status) != "closed":
            return False
        for turn in reversed(evt.conversation or []):
            action = turn.get("action") if isinstance(turn, dict) else getattr(turn, "action", None)
            if action == "close":
                evidence = turn.get("evidence") if isinstance(turn, dict) else getattr(turn, "evidence", None)
                return evidence == "duplicate"
        return False

    def set_wip_counter(self, counter: Callable[..., Awaitable[int]] | None) -> None:
        """Inject global WIP counter (e.g. Brain.count_global_wip)."""
        self._wip_counter = counter

    async def _local_count_wip(self) -> int:
        status_map = await self.blackboard.get_active_events_with_status()
        return sum(1 for s in status_map.values() if s in ("new", "active", "deferred"))

    async def check_flow_gate(self) -> bool:
        """Back off when system is at global WIP capacity."""
        if self._wip_counter is not None:
            try:
                wip_used = await self._wip_counter(include_new=True)
            except Exception as e:
                logger.warning(
                    "Injected WIP counter failed in check_flow_gate, falling back to local: %s",
                    e,
                )
                try:
                    wip_used = await self._local_count_wip()
                except Exception as local_err:
                    logger.error(
                        "Local WIP count failed in check_flow_gate, assuming gate closed: %s",
                        local_err,
                    )
                    return False
        else:
            try:
                wip_used = await self._local_count_wip()
            except Exception as local_err:
                logger.error(
                    "Local WIP count failed in check_flow_gate, assuming gate closed: %s",
                    local_err,
                )
                return False
        return wip_used < self._wip_cap

    # =========================================================================
    # Cold-Start Recovery
    # =========================================================================

    def _latest_bot_comment(self, issue: dict, *, skip_non_analysis: bool = False) -> dict | None:
        """Find latest bot-authored comment (optionally skipping re-analyze/self-mention comments)."""
        comment_block = issue.get("fields", {}).get("comment", {})
        comments = comment_block.get("comments", [])
        total = comment_block.get("total", 0)
        if isinstance(total, int) and total > len(comments):
            logger.warning(
                "Embedded Jira comments truncated for %s (%d/%d)",
                issue.get("key", "?"),
                len(comments),
                total,
            )
        for comment in reversed(comments):
            if comment.get("author", {}).get("accountId") != self._bot_account_id:
                continue
            if skip_non_analysis:
                body = comment.get("body", "")
                if isinstance(body, dict) and self._mentions_bot(body):
                    continue
                text = adf_to_markdown(body).strip() if isinstance(body, dict) else str(body).strip()
                if not text or "please re-analyze this issue" in text.lower():
                    continue
            return comment
        return None

    def _find_bot_comment(self, issue: dict) -> str | None:
        """Find latest bot comment ID or None."""
        comment = self._latest_bot_comment(issue)
        return comment.get("id", "") if comment else None

    def _find_bot_comment_text(self, issue: dict) -> str:
        """Return markdown text of latest bot analysis comment, or empty string."""
        comment = self._latest_bot_comment(issue, skip_non_analysis=True)
        if not comment:
            return ""
        body = comment.get("body", "")
        return adf_to_markdown(body).strip() if isinstance(body, dict) else str(body).strip()

    async def _record_analysis(
        self,
        key: str,
        comment_id: str,
        analysis: str,
        *,
        duplicate_retried: bool = False,
    ) -> None:
        """Persist analyzed phase, comment anchor, and analysis text to Redis."""
        state: dict[str, Any] = {"phase": "analyzed", "last_comment_id": comment_id}
        if analysis:
            state["analysis"] = analysis
        if duplicate_retried:
            state["duplicate_retried"] = True
        await self._set_issue_state(key, state)

    async def poll_and_process(self) -> None:
        """Single cycle: handle Planning issues + To Do issues."""
        planning_issues = await self.poll_planning()
        logger.debug(f"Jira Planning issues: {len(planning_issues)}")
        cold_start_checks = 0
        for issue in planning_issues:
            key = issue["key"]
            state = await self._get_issue_state(key)
            if state is None:
                if cold_start_checks < 10:
                    bot_comment_id = self._find_bot_comment(issue)
                    cold_start_checks += 1
                    if bot_comment_id:
                        bot_text = self._find_bot_comment_text(issue)
                        await self._record_analysis(key, bot_comment_id, bot_text)
                        state = await self._get_issue_state(key)
                        logger.info(f"Jira cold-start: anchoring {key} to comment {bot_comment_id}")
                    else:
                        logger.info(f"Jira cold-start: no bot comment found for {key}, running fresh analysis")
                if state is None:
                    result = await self.analyze_and_comment(issue)
                    if result:
                        await self._record_analysis(key, result[0], result[1])
                    continue

            if state and state.get("phase") == "analyzed":
                last_cid = state.get("last_comment_id", "")
                if last_cid:
                    try:
                        reeval_signal = await self.has_reeval_signal(issue, last_cid)
                    except Exception as e:
                        logger.warning(f"Jira reeval check failed for {key}: {e}")
                        continue
                    if reeval_signal:
                        logger.info(f"Jira reeval signal detected for {key} after comment {last_cid}")
                        result = await self.analyze_and_comment(issue)
                        if result:
                            await self._record_analysis(key, result[0], result[1])
                    else:
                        logger.debug(f"Jira reeval check for {key}: no signal (anchor={last_cid})")

        if not await self.check_flow_gate():
            logger.debug("Jira flow gate closed -- skipping event creation")
            return
        todo_issues = await self.poll_todo()
        logger.debug(f"Jira To Do issues: {len(todo_issues)}")
        if not todo_issues:
            return
        active_jira_keys = await self._get_active_jira_keys()
        for issue in todo_issues:
            key = issue["key"]
            norm_key = key.strip().upper()
            if norm_key in active_jira_keys:
                continue
            try:
                state = await self._get_issue_state(key)
                retrying_dup = bool(state and state.get("duplicate_retried"))
                recovering_event_id: str | None = None
                if state and state.get("phase") == "event_created":
                    if not await self._should_retry_duplicate_event(key, state):
                        continue
                    retrying_dup = True
                    recovering_event_id = state.get("event_id")
                if (
                    retrying_dup
                    and state
                    and state.get("phase") == "analyzed"
                    and int(state.get("plan_failures", 0)) >= self._MAX_RECOVERY_PLAN_FAILURES
                ):
                    logger.debug(f"Jira {key}: duplicate recovery plan retries exhausted -- staying parked")
                    continue
            except Exception as e:
                logger.warning(f"Jira {key}: failed to inspect Redis state: {e}")
                continue
            if not await self.check_flow_gate():
                logger.info("Jira flow gate closed mid-cycle -- stopping")
                break
            analyzed_state_written = bool(state and state.get("phase") == "analyzed")
            current_analysis = state.get("analysis", "") if state else ""
            event_created_claimed = False
            try:
                if recovering_event_id:
                    logger.info(
                        f"Jira {key}: recovering from prior duplicate-closed event "
                        f"{recovering_event_id} (1-shot retry)"
                    )
                    await self._set_issue_state(key, {**(state or {}), "duplicate_retried": True})
                jira_content = format_jira_for_llm(issue)
                analysis_text = current_analysis
                if not analysis_text:
                    analysis_text = self._find_bot_comment_text(issue)
                if not analysis_text:
                    system_prompt = await self._resolve_system_prompt(issue)
                    analysis_text = await self._run_claude_analysis(jira_content, system_prompt)
                    await self._record_analysis(
                        key,
                        state.get("last_comment_id", "") if state else "",
                        analysis_text,
                        duplicate_retried=retrying_dup,
                    )
                    analyzed_state_written = True
                    current_analysis = analysis_text
                plan_yaml = await self._run_brain_plan(jira_content, analysis_text)
                mission_label = self._resolve_mission_label(issue)
                if retrying_dup and analyzed_state_written:
                    await self._set_issue_state(
                        key,
                        {"phase": "event_created", "event_id": "", "duplicate_retried": True},
                    )
                    event_created_claimed = True
                event_id = await self.create_jira_event(issue, plan_yaml, mission_label=mission_label)
                new_state: dict[str, Any] = {"phase": "event_created", "event_id": event_id}
                if retrying_dup:
                    new_state["duplicate_retried"] = True
                await self._set_issue_state(key, new_state)
                active_jira_keys.add(norm_key)
            except Exception as e:
                logger.warning(f"Jira event creation failed for {key}: {e}")
                if retrying_dup and analyzed_state_written and not event_created_claimed:
                    try:
                        failures = int((state or {}).get("plan_failures", 0)) + 1
                        failed_state: dict[str, Any] = {
                            "phase": "analyzed",
                            "last_comment_id": (state or {}).get("last_comment_id", ""),
                            "duplicate_retried": True,
                            "plan_failures": failures,
                        }
                        if current_analysis:
                            failed_state["analysis"] = current_analysis
                        await self._set_issue_state(key, failed_state)
                    except Exception as state_err:
                        logger.warning(f"Jira {key}: failed to record recovery plan failure count: {state_err}")
