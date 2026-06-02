# BlackBoard/scripts/probe_jira_analyst.py
# @ai-rules:
# 1. [Constraint]: Standalone probe script -- no imports from src/. Uses raw SDK only.
# 2. [Pattern]: Reads GCP_PROJECT, GCP_LOCATION from env. Requires GOOGLE_APPLICATION_CREDENTIALS.
# 3. [Pattern]: Fetches Jira issue via REST API (JIRA_EMAIL + JIRA_API_TOKEN env vars).
# 4. [Purpose]: Validate Claude Sonnet analysis quality on a CNV Jira bug using Business Analyst rules.
"""
Probe: Jira Issue -> Claude Sonnet Business Analyst Analysis

Fetches a CNV Jira issue, feeds it to Claude Sonnet 4 via Vertex AI
with the kubevirt-ui Business Analyst rules as system prompt, and
prints the structured validation plan output.

Usage:
    source ~/.oh-my-bash/custom/jira-env.bash
    export GOOGLE_APPLICATION_CREDENTIALS=/path/to/sa-key.json
    export GCP_PROJECT=cnv-ai-insights
    export GCP_LOCATION=global

    python scripts/probe_jira_analyst.py CNV-85192
    python scripts/probe_jira_analyst.py CNV-85192 --output docs/New-features/testing-ai-agents/probe-output.md
"""
import asyncio
import base64
import json
import os
import sys

import httpx

JIRA_BASE_URL = os.getenv("JIRA_URL", "https://redhat.atlassian.net")
JIRA_EMAIL = os.getenv("JIRA_EMAIL", "")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN", "")
GCP_PROJECT = os.getenv("GCP_PROJECT", "")
GCP_LOCATION = os.getenv("GCP_LOCATION", "global")
MODEL = os.getenv("LLM_MODEL_HEADHUNTER_JIRA", "claude-sonnet-4-6")

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
2. **Validation Points**: Specific UI behaviors to verify (extracted from description, steps to reproduce, expected results, linked PRs)
3. **Test Strategy**: How to verify (which page, which interactions, what assertions)
4. **Preconditions**: Resources needed (VM, namespace, specific template)
5. **Suggested Tier**: gating/tier1/tier2 with justification
6. **Risk Assessment**: What could make this verification fail or be flaky
7. **Environment Constraints**: Single cluster vs ACM, specific storage classes, etc.

## Output Format

Use structured markdown. Be specific -- reference actual UI elements, data-test attributes when inferable, and StepDriver methods when applicable. If the issue links to a PR, note what code change needs verification.

Do NOT invent test code. Your output is a plan for the QE agent to follow, not implementation."""


async def fetch_jira_issue(issue_key: str) -> dict:
    """Fetch Jira issue details via REST API."""
    if not JIRA_EMAIL or not JIRA_API_TOKEN:
        print("ERROR: JIRA_EMAIL and JIRA_API_TOKEN env vars required.")
        print("       source ~/.oh-my-bash/custom/jira-env.bash")
        sys.exit(1)

    auth = base64.b64encode(f"{JIRA_EMAIL}:{JIRA_API_TOKEN}".encode()).decode()
    url = f"{JIRA_BASE_URL}/rest/api/3/issue/{issue_key}"
    params = {"fields": "summary,description,status,issuetype,priority,comment,issuelinks,parent,subtasks,labels,components,fixVersions"}

    async with httpx.AsyncClient(timeout=15) as client:
        resp = await client.get(url, headers={"Authorization": f"Basic {auth}"})
        if resp.status_code != 200:
            print(f"ERROR: Jira API returned {resp.status_code}: {resp.text[:200]}")
            sys.exit(1)
        return resp.json()


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
    agent: <qe|developer|architect|sysadmin|security_analyst>
    mode: <investigate|test|implement|execute|review>
    summary: "<what this step does -- include specifics from the analysis>"
    status: pending
  - id: ...
---
```

## Rules

- Steps must be independently executable and verifiable
- First step should always be environment verification (cluster access, correct build version)
- Include the repo URL if the agent needs to clone code
- Include specific validation points from the analysis in step summaries
- Use mode=investigate for read-only exploration, mode=test for assertion-based verification
- Do NOT include approval steps -- the plan is already approved when Brain receives it
- Keep steps atomic -- one concern per step
- Reference the Jira issue key and PR in relevant step summaries"""


async def run_claude_analysis(jira_content: str) -> tuple[str, str]:
    """Run Claude Sonnet analysis + plan generation via Vertex AI. Returns (analysis, brain_plan)."""
    from anthropic import AsyncAnthropicVertex

    client = AsyncAnthropicVertex(
        region=GCP_LOCATION,
        project_id=GCP_PROJECT,
    )

    print(f"  Sending to Claude ({MODEL}) via Vertex AI ({GCP_PROJECT}/{GCP_LOCATION})...")

    # Step 1: Business Analyst analysis (for Jira comment)
    print(f"  [a] Business Analyst analysis...")
    response = await client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=BUSINESS_ANALYST_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Analyze this Jira issue and produce a validation plan:\n\n{jira_content}"}],
    )
    analysis = response.content[0].text

    # Step 2: Brain execution plan (for event creation)
    print(f"  [b] Brain execution plan...")
    response = await client.messages.create(
        model=MODEL,
        max_tokens=2048,
        system=BRAIN_PLAN_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": f"Produce a Brain execution plan for this approved analysis.\n\nJira issue context:\n{jira_content}\n\nApproved validation plan:\n{analysis}"}],
    )
    brain_plan = response.content[0].text

    return analysis, brain_plan


async def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/probe_jira_analyst.py <ISSUE_KEY> [--output <path>]")
        print("Example: python scripts/probe_jira_analyst.py CNV-85192")
        sys.exit(1)

    issue_key = sys.argv[1]
    output_path = None
    if "--output" in sys.argv:
        idx = sys.argv.index("--output")
        if idx + 1 < len(sys.argv):
            output_path = sys.argv[idx + 1]

    print(f"[1/3] Fetching {issue_key} from Jira...")
    issue = await fetch_jira_issue(issue_key)
    print(f"  Got: {issue.get('fields', {}).get('summary', '?')}")

    print(f"[2/3] Formatting for LLM...")
    jira_content = format_jira_for_llm(issue)
    print(f"  Content length: {len(jira_content)} chars")

    print(f"[3/4] Running Claude Business Analyst analysis...")
    analysis, brain_plan = await run_claude_analysis(jira_content)

    separator = "=" * 80

    print(f"[4/4] Assembling output...")
    output = f"""# Probe Output: {issue_key} Business Analyst Analysis + Brain Execution Plan

**Model:** {MODEL}
**Issue:** {issue.get('fields', {}).get('summary', '?')}
**Status:** {issue.get('fields', {}).get('status', {}).get('name', '?')}

{separator}

## Input (Jira Issue Content)

{jira_content}

{separator}

## Output 1: Business Analyst Validation Plan (→ Jira Comment)

This is what the Headhunter posts as a Jira comment during the "planning" phase.
Human reviews, edits, adds constraints, then moves to "to-do" to approve.

{analysis}

{separator}

## Output 2: Brain Execution Plan (→ Event reason field)

This is what the Headhunter puts in the event `reason` field when creating a Brain event
after the human approves (moves issue to "to-do"). Brain tracks execution step-by-step.

{brain_plan}
"""

    if output_path:
        os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
        with open(output_path, "w") as f:
            f.write(output)
        print(f"\n  Output saved to: {output_path}")
    else:
        print(f"\n{output}")

    print("\nDone. Review the validation plan quality and send to Bruno for feedback.")


if __name__ == "__main__":
    asyncio.run(main())
