# BlackBoard/src/agents/headhunter_jira.py
# @ai-rules:
# 1. [Pattern]: Follows Headhunter pattern -- in-process daemon head, lazy-loaded Claude adapter.
# 2. [Constraint]: AIR GAP: No kubernetes imports. Jira API via httpx only.
# 3. [Pattern]: Two-phase poll: Planning issues -> analyze+comment, To Do issues -> create Brain event.
# 4. [Pattern]: Re-eval gate: watchers who @mention bot trigger re-analysis.
# 5. [Pattern]: ADF (Atlassian Document Format) mention parsing via recursive tree walk.
# 6. [Pattern]: Circuit breaker: 3 consecutive Jira poll failures -> disable head.
# 7. [Gotcha]: Jira Cloud comments use ADF (nested JSON), not plain text.
# 8. [Constraint]: No hardcoded emails, URLs, or tokens -- all from env vars.
# 9. [Pattern]: Label-driven skill selection: HEADHUNTER_JIRA_SKILL_<LABEL>=<git raw url>.
#    Labels on issue (beyond base "darwin") map to system prompts fetched from git. 5-min cache.
# 10. [Pattern]: Flow gate uses global WIP cap (MAX_ACTIVE_EVENTS). Counts new+active+deferred
#     conservatively (no _waiting_for_user subtraction). Backs off when system full.
#    Teams self-serve by updating rules in their own repo. Fallback: built-in BA prompt.
# 10. [Pattern]: Redis-backed state (darwin:headhunter:jira:{key}, 7d TTL) replaces in-memory dict.
#     _get_issue_state/_set_issue_state are the canonical accessors.
# 11. [Pattern]: _get_active_jira_keys() mirrors GitLab headhunter's _get_active_mr_keys() for dedup.
# 12. [Pattern]: Cold-start recovery: _find_bot_comment() reconstructs Redis state from existing comments.
#     Capped at 10 comment checks per cycle to avoid Jira rate limits.
# 13. [Pattern]: Plan generation uses function calling (produce_execution_plan tool), not text parsing.
#     _plan_args_to_yaml() converts structured args to YAML. _extract_yaml() kept as fallback.
# 14. [Constraint]: Skill URL 10KB cap -- len(content) > 10240 → cache BUSINESS_ANALYST_SYSTEM_PROMPT
#     + return None (caller falls back to BUSINESS_ANALYST_SYSTEM_PROMPT, symmetric with GitHub adapter).
"""
Headhunter Jira: polls Jira issues assigned to bot with a label filter.

Two-phase flow:
  1. Planning issues -> Claude BA analysis -> post Jira comment
  2. To Do issues (human-approved) -> Claude plan generation -> Brain event
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from typing import TYPE_CHECKING, Any

import httpx

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
            "domain": {"type": "string", "enum": ["CLEAR", "COMPLICATED", "COMPLEX"]},
            "risk": {"type": "string", "enum": ["low", "medium", "high"]},
            "steps": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "string", "description": "Short kebab-case step ID"},
                        "agent": {"type": "string", "enum": ["qe", "developer", "architect", "sysadmin", "security_analyst"]},
                        "mode": {"type": "string", "enum": ["investigate", "test", "implement", "execute", "review"]},
                        "summary": {"type": "string", "description": "What this step does"},
                    },
                    "required": ["id", "agent", "mode", "summary"],
                },
            },
        },
        "required": ["plan", "service", "repository", "domain", "risk", "steps"],
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
            desc = json.dumps(desc, indent=2)
        parts.append(f"\n## Description\n\n{desc}")

    comments = fields.get("comment", {}).get("comments", [])
    if comments:
        parts.append("\n## Comments")
        for c in comments[-5:]:
            author = c.get("author", {}).get("displayName", "Unknown")
            body = c.get("body", "")
            if isinstance(body, dict):
                body = json.dumps(body, indent=2)
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
    """Jira polling head -- two-phase flow for QE mission analysis and event creation."""

    REDIS_PREFIX = "darwin:headhunter:jira:"
    REDIS_TTL = 604800  # 7 days

    def __init__(self, blackboard: BlackboardState):
        self.blackboard = blackboard
        self._jira_url = os.getenv("JIRA_URL", "")
        self._jira_email = os.getenv("JIRA_EMAIL", "")
        self._jira_token = os.getenv("JIRA_API_TOKEN", "")
        self._bot_account_id = os.getenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "")
        self._jira_label = os.getenv("HEADHUNTER_JIRA_LABEL", "darwin")
        self._model = os.getenv("LLM_MODEL_HEADHUNTER_JIRA", "claude-sonnet-5")
        self._wip_cap = int(os.getenv("MAX_ACTIVE_EVENTS", "20"))
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
        return json.loads(raw) if raw else None

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
        watchers = await self.get_watchers(issue["key"])
        comments = issue.get("fields", {}).get("comment", {}).get("comments", [])

        found_last = False
        for comment in comments:
            if comment["id"] == last_comment_id:
                found_last = True
                continue
            if not found_last:
                continue
            author_id = comment.get("author", {}).get("accountId", "")
            if author_id == self._bot_account_id:
                continue
            if author_id not in watchers:
                continue
            if self._mentions_bot(comment.get("body", {})):
                return True
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
                f"Produce a Brain execution plan for this approved analysis.\n\n"
                f"Jira issue context:\n{jira_content}\n\n"
                f"Approved validation plan:\n{analysis}"
            ),
            tools=[PLAN_TOOL_SCHEMA],
            tool_choice={"type": "tool", "name": "produce_execution_plan"},
        ):
            if chunk.text:
                text_chunks.append(chunk.text)
            if chunk.function_call:
                function_call = chunk.function_call
            if chunk.usage:
                from .llm import record_token_usage
                record_token_usage("headhunter_jira", chunk.usage)

        if function_call and function_call.name == "produce_execution_plan":
            return self._plan_args_to_yaml(function_call.args)

        logger.warning("Claude did not use produce_execution_plan tool -- falling back to text parsing")
        return self._extract_yaml("".join(text_chunks))

    @staticmethod
    def _plan_args_to_yaml(args: dict) -> str:
        """Convert structured tool args to YAML plan format."""
        import yaml
        plan_doc = {
            "plan": args.get("plan", ""),
            "service": args.get("service", ""),
            "repository": args.get("repository", ""),
            "domain": args.get("domain", "COMPLICATED"),
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
            ],
        }
        return yaml.dump(plan_doc, default_flow_style=False, sort_keys=False).strip()

    # TODO: Remove _extract_yaml() after 7 days of production monitoring confirms
    # zero "did not use produce_execution_plan tool" warnings in logs.
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
            return "\n".join(yaml_lines).strip()
        # No fences found -- try to find YAML by looking for '---' delimiters
        start = None
        for i, line in enumerate(lines):
            if line.strip() == "---" and start is None:
                start = i
                continue
            if line.strip() == "---" and start is not None:
                return "\n".join(lines[start:i + 1]).strip()
        # Last resort: return everything after stripping common LLM preambles
        for i, line in enumerate(lines):
            if line.strip().startswith("plan:") or line.strip() == "---":
                return "\n".join(lines[i:]).strip()
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

    async def create_qe_event(self, issue: dict, plan_yaml: str) -> str:
        """Create Brain event for an approved QE mission."""
        from ..models import EventEvidence

        fields = issue.get("fields", {})
        key = issue.get("key", "?")
        summary = fields.get("summary", "")
        evidence = EventEvidence(
            display_text=f"Jira QE mission: {key} - {summary}",
            source_type="headhunter",
            triggered_by="jira-bot",
            domain="complicated",
            domain_confidence="assessed",
            severity="info",
            jira_context={
                "issue_key": key,
                "issue_url": f"{self._jira_url}/browse/{key}",
                "summary": summary,
                "status": fields.get("status", {}).get("name", ""),
                "priority": fields.get("priority", {}).get("name", ""),
                "components": [c.get("name", "") for c in fields.get("components", [])],
                "labels": fields.get("labels", []),
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
        logger.info(f"QE mission event created: {event_id} for {key}")
        return event_id

    # =========================================================================
    # Active Event Dedup + Flow Gate
    # =========================================================================

    async def _get_active_jira_keys(self) -> set[str]:
        """Get issue keys for all active/deferred Jira headhunter events."""
        active_ids = await self.blackboard.get_active_events()
        keys: set[str] = set()
        for eid in active_ids:
            event = await self.blackboard.get_event(eid)
            if (event and event.source == "headhunter"
                    and getattr(event, "subject_type", "service") == "jira"
                    and event.status.value in ("new", "active", "deferred")):
                jira_ctx = getattr(event.event.evidence, "jira_context", None) if event.event and event.event.evidence else None
                if jira_ctx and isinstance(jira_ctx, dict):
                    keys.add(jira_ctx.get("issue_key", ""))
        return keys - {""}

    async def check_flow_gate(self) -> bool:
        """Back off when system is at global WIP capacity (conservative count)."""
        status_map = await self.blackboard.get_active_events_with_status()
        wip_used = sum(1 for s in status_map.values() if s in ("new", "active", "deferred"))
        return wip_used < self._wip_cap

    # =========================================================================
    # Cold-Start Recovery
    # =========================================================================

    def _find_bot_comment(self, issue: dict) -> str | None:
        """Find the latest comment posted by the bot. Returns comment ID or None."""
        comments = issue.get("fields", {}).get("comment", {}).get("comments", [])
        for comment in reversed(comments):
            if comment.get("author", {}).get("accountId") == self._bot_account_id:
                return comment.get("id", "")
        return None

    # =========================================================================
    # Main Poll Cycle
    # =========================================================================

    async def poll_and_process(self) -> None:
        """Single cycle: handle Planning issues + To Do issues."""
        # Phase 1: Analyze Planning issues (no flow gate -- analysis doesn't create events)
        planning_issues = await self.poll_planning()
        logger.debug(f"Jira Planning issues: {len(planning_issues)}")
        cold_start_checks = 0
        for issue in planning_issues:
            key = issue["key"]
            state = await self._get_issue_state(key)
            if state is None:
                # Cold-start: reconstruct from bot comments if they exist
                if cold_start_checks < 10:
                    bot_comment_id = self._find_bot_comment(issue)
                    cold_start_checks += 1
                    if bot_comment_id:
                        await self._set_issue_state(key, {"phase": "analyzed", "last_comment_id": bot_comment_id})
                        continue
                result = await self.analyze_and_comment(issue)
                if result:
                    comment_id, _analysis = result
                    await self._set_issue_state(key, {"phase": "analyzed", "last_comment_id": comment_id})
            elif state.get("phase") == "analyzed":
                last_cid = state.get("last_comment_id", "")
                if last_cid and await self.has_reeval_signal(issue, last_cid):
                    result = await self.analyze_and_comment(issue)
                    if result:
                        comment_id, _analysis = result
                        await self._set_issue_state(key, {"phase": "analyzed", "last_comment_id": comment_id})

        # Phase 2: Create events for To Do issues (gated by global WIP cap)
        if not await self.check_flow_gate():
            logger.debug("Jira flow gate closed -- skipping event creation")
            return
        active_jira_keys = await self._get_active_jira_keys()
        todo_issues = await self.poll_todo()
        logger.debug(f"Jira To Do issues: {len(todo_issues)}")
        for issue in todo_issues:
            key = issue["key"]
            if key in active_jira_keys:
                continue
            state = await self._get_issue_state(key)
            if state and state.get("phase") == "event_created":
                continue
            if not await self.check_flow_gate():
                logger.info("Jira flow gate closed mid-cycle -- stopping")
                break
            try:
                jira_content = format_jira_for_llm(issue)
                analysis_text = state.get("analysis", "") if state else ""
                if not analysis_text:
                    analysis_text = await self._run_claude_analysis(jira_content)
                plan_yaml = await self._run_brain_plan(jira_content, analysis_text)
                event_id = await self.create_qe_event(issue, plan_yaml)
                await self._set_issue_state(key, {"phase": "event_created", "event_id": event_id})
                active_jira_keys.add(key)
            except Exception as e:
                logger.warning(f"Jira event creation failed for {key}: {e}")
