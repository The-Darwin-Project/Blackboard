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
#    Teams self-serve by updating rules in their own repo. Fallback: built-in BA prompt.
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


BRAIN_PLAN_SYSTEM_PROMPT = """You are a QE workflow planner for the Darwin autonomous operations system.

Given a Business Analyst validation plan for a Jira issue, produce a YAML execution plan that Darwin's Brain can track step-by-step.

## Output Format (EXACT -- Brain parses this)

```
---
plan: "<one-line description>"
service: <service-name>
repository: <repo-url>
domain: <CLEAR|COMPLICATED|COMPLEX>
risk: <low|medium|high>
steps:
  - id: <short-kebab-id>
    agent: <qe|developer|architect|sysAdmin>
    mode: <investigate|test|implement|execute|review>
    summary: "<what this step does>"
    status: pending
  - id: ...
---
```

## Rules

- Steps must be independently executable and verifiable
- First step should always be environment verification
- Include the repo URL if the agent needs to clone code
- Use mode=investigate for read-only, mode=test for assertion-based verification
- Keep steps atomic -- one concern per step
- Reference the Jira issue key and PR in relevant step summaries"""


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

    def __init__(self, blackboard: BlackboardState):
        self.blackboard = blackboard
        self._jira_url = os.getenv("JIRA_URL", "")
        self._jira_email = os.getenv("JIRA_EMAIL", "")
        self._jira_token = os.getenv("JIRA_API_TOKEN", "")
        self._bot_account_id = os.getenv("HEADHUNTER_JIRA_BOT_ACCOUNT_ID", "")
        self._jira_label = os.getenv("HEADHUNTER_JIRA_LABEL", "darwin")
        self._model = os.getenv("LLM_MODEL_HEADHUNTER_JIRA", "claude-sonnet-4-6")
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
        # In-memory state: tracks which issues have been analyzed or event-created
        self._analyzed_issues: dict[str, dict[str, str]] = {}

    def enabled(self) -> bool:
        """Returns True if required env vars are configured."""
        return bool(self._jira_url and self._jira_token and self._bot_account_id)

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
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
                if resp.status_code == 200:
                    content = resp.text
                    self._skill_cache[label] = {"content": content, "ts": time.time()}
                    logger.debug(f"Skill fetched for label '{label}' ({len(content)} chars)")
                    return content
                logger.warning(f"Skill fetch returned {resp.status_code} for '{label}'")
        except Exception as e:
            logger.warning(f"Skill fetch failed for '{label}': {e}")
        return None

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
                "/rest/api/3/search",
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
        """Run Claude analysis with given system prompt. Returns analysis text."""
        adapter = self._get_claude_adapter()
        if not adapter:
            raise RuntimeError("Claude adapter not available")
        response = await adapter.generate(
            prompt=f"Analyze this Jira issue and produce a validation plan:\n\n{jira_content}",
            system_instruction=system_prompt or BUSINESS_ANALYST_SYSTEM_PROMPT,
        )
        return response.text

    async def _run_brain_plan(self, jira_content: str, analysis: str) -> str:
        """Run Claude plan generation. Returns YAML plan text."""
        adapter = self._get_claude_adapter()
        if not adapter:
            raise RuntimeError("Claude adapter not available")
        response = await adapter.generate(
            prompt=(
                f"Produce a Brain execution plan for this approved analysis.\n\n"
                f"Jira issue context:\n{jira_content}\n\n"
                f"Approved validation plan:\n{analysis}"
            ),
            system_instruction=BRAIN_PLAN_SYSTEM_PROMPT,
        )
        return response.text

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
        """Post a plain-text comment to a Jira issue. Returns the comment ID."""
        adf_body = {
            "body": {
                "version": 1,
                "type": "doc",
                "content": [
                    {
                        "type": "paragraph",
                        "content": [{"type": "text", "text": body_text}],
                    }
                ],
            }
        }
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
    # Main Poll Cycle
    # =========================================================================

    async def poll_and_process(self) -> None:
        """Single cycle: handle Planning issues + To Do issues."""
        # Phase 1: Analyze Planning issues
        planning_issues = await self.poll_planning()
        logger.debug(f"Jira Planning issues: {len(planning_issues)}")
        for issue in planning_issues:
            key = issue["key"]
            if key not in self._analyzed_issues:
                result = await self.analyze_and_comment(issue)
                if result:
                    comment_id, analysis = result
                    self._analyzed_issues[key] = {"last_comment_id": comment_id, "analysis": analysis, "phase": "analyzed"}
            elif await self.has_reeval_signal(issue, self._analyzed_issues[key]["last_comment_id"]):
                result = await self.analyze_and_comment(issue)
                if result:
                    comment_id, analysis = result
                    self._analyzed_issues[key]["last_comment_id"] = comment_id
                    self._analyzed_issues[key]["analysis"] = analysis

        # Phase 2: Create events for To Do issues
        todo_issues = await self.poll_todo()
        logger.debug(f"Jira To Do issues: {len(todo_issues)}")
        for issue in todo_issues:
            key = issue["key"]
            if self._analyzed_issues.get(key, {}).get("phase") == "event_created":
                continue
            try:
                jira_content = format_jira_for_llm(issue)
                analysis_text = self._analyzed_issues.get(key, {}).get("analysis", "")
                if not analysis_text:
                    analysis_text = await self._run_claude_analysis(jira_content)
                plan_yaml = await self._run_brain_plan(jira_content, analysis_text)
                await self.create_qe_event(issue, plan_yaml)
                self._analyzed_issues[key] = {"last_comment_id": "", "analysis": "", "phase": "event_created"}
            except Exception as e:
                logger.warning(f"Jira event creation failed for {key}: {e}")
