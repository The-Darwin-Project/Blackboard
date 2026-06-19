# BlackBoard/skill-author/poc.py
# @ai-rules:
# 1. [Constraint]: Local-only PoC script. Never commit API keys or SA paths.
# 2. [Pattern]: Runs both Gemini and Claude against the same SI + issue, writes side-by-side output.
# 3. [Gotcha]: Claude uses AnthropicVertex (SA-based), Gemini uses google-genai (API key).
"""
PoC: Compare Gemini 3.5 Flash vs Claude Sonnet 4.6 as Skill Authors.

Usage:
    python3 poc.py <issue_number>

Requires:
    GOOGLE_API_KEY              - for Gemini 3.5 Flash
    GOOGLE_APPLICATION_CREDENTIALS - for Claude Sonnet 4.6 via Vertex AI
    gh CLI                      - for fetching issue content
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

SKILLS_DIR = Path(__file__).parent.parent / "src" / "agents" / "brain_skills"
SI_PATH = Path(__file__).parent / "SYSTEM_INSTRUCTION.md"
OUTPUT_DIR = Path(__file__).parent / "poc-output"

GCP_PROJECT = os.environ.get("GCP_PROJECT_ID", "cnv-ai-insights")
GCP_REGION = os.environ.get("GCP_REGION", "us-east5")


def load_si() -> str:
    return SI_PATH.read_text(encoding="utf-8")


def fetch_issue(issue_number: int) -> dict:
    """Fetch issue title + body via gh CLI."""
    result = subprocess.run(
        ["gh", "issue", "view", str(issue_number), "--json", "title,body,state"],
        capture_output=True, text=True, check=True,
        cwd=str(Path(__file__).parent.parent),
    )
    return json.loads(result.stdout)


def extract_skill_paths(issue_body: str) -> list[str]:
    """Extract referenced skill file paths from issue body."""
    patterns = [
        r'`(always/[\w-]+\.md)`',
        r'`(source/[\w-]+\.md)`',
        r'`(dispatch/[\w-]+\.md)`',
        r'`(close/[\w-]+\.md)`',
        r'`(domain/[\w-]+\.md)`',
        r'`(context/[\w-]+\.md)`',
        r'`(coordination/[\w-]+\.md)`',
        r'`(intermediate/[\w-]+\.md)`',
        r'`(post-agent/[\w-]+\.md)`',
        r'`(waiting/[\w-]+\.md)`',
        r'`(escalate/[\w-]+\.md)`',
        r'`(multi-user/[\w-]+\.md)`',
    ]
    paths = set()
    for pattern in patterns:
        paths.update(re.findall(pattern, issue_body))
    return sorted(paths)


def read_skill_files(rel_paths: list[str]) -> dict[str, str]:
    """Read skill file content from local filesystem."""
    contents = {}
    for rel in rel_paths:
        full = SKILLS_DIR / rel
        if full.exists():
            contents[rel] = full.read_text(encoding="utf-8")
        else:
            contents[rel] = f"[FILE NOT FOUND: {rel}]"
    return contents


def build_prompt(issue: dict, skill_contents: dict[str, str]) -> str:
    """Build the user prompt for the Skill Author LLM."""
    parts = [f"## Issue\n**{issue['title']}**\n\n{issue['body']}"]

    if skill_contents:
        parts.append("\n## Current Skill Content\n")
        for path, content in skill_contents.items():
            parts.append(f"### {path}\n```\n{content}\n```\n")

    parts.append(
        "\n## Task\n"
        "Generate the minimal patch to address the behavioral gap described "
        "in the issue. Follow the Skill Author conventions in your system "
        "instruction. Return Reasoning + Patch sections."
    )
    return "\n".join(parts)


def call_gemini(si: str, prompt: str) -> tuple[str, float]:
    """Call Gemini 3.5 Flash via google-genai SDK."""
    from google import genai

    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        return "[ERROR: GOOGLE_API_KEY not set]", 0.0

    client = genai.Client(api_key=api_key)
    start = time.time()
    response = client.models.generate_content(
        model="gemini-3.5-flash",
        contents=prompt,
        config=genai.types.GenerateContentConfig(
            system_instruction=si,
            temperature=0.3,
            max_output_tokens=8192,
        ),
    )
    elapsed = time.time() - start
    return response.text, elapsed


def call_claude(si: str, prompt: str) -> tuple[str, float]:
    """Call Claude Sonnet 4.6 via Vertex AI."""
    from anthropic import AnthropicVertex

    client = AnthropicVertex(project_id=GCP_PROJECT, region=GCP_REGION)
    start = time.time()
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=8192,
        system=si,
        messages=[{"role": "user", "content": prompt}],
    )
    elapsed = time.time() - start
    return response.content[0].text, elapsed


def main():
    if len(sys.argv) < 2:
        print("Usage: python3 poc.py <issue_number>")
        sys.exit(1)

    issue_number = int(sys.argv[1])
    print(f"Fetching issue #{issue_number}...")
    issue = fetch_issue(issue_number)
    print(f"  Title: {issue['title']}")
    print(f"  State: {issue['state']}")

    skill_paths = extract_skill_paths(issue["body"])
    print(f"  Referenced skills: {skill_paths or 'none detected'}")

    skill_contents = read_skill_files(skill_paths) if skill_paths else {}
    si = load_si()
    prompt = build_prompt(issue, skill_contents)
    print(f"  Prompt tokens (est): ~{len(prompt) // 4}")
    print(f"  SI tokens (est): ~{len(si) // 4}")

    out_dir = OUTPUT_DIR / str(issue_number)
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    print(f"\n  Prompt saved to {out_dir / 'prompt.md'}")

    print("\n--- Gemini 3.5 Flash ---")
    try:
        gemini_result, gemini_time = call_gemini(si, prompt)
        (out_dir / "gemini.md").write_text(gemini_result, encoding="utf-8")
        print(f"  Time: {gemini_time:.1f}s")
        print(f"  Output: {len(gemini_result)} chars")
        print(f"  Saved to {out_dir / 'gemini.md'}")
    except Exception as e:
        print(f"  ERROR: {e}")
        gemini_result = f"[ERROR: {e}]"

    print("\n--- Claude Sonnet 4.6 ---")
    try:
        claude_result, claude_time = call_claude(si, prompt)
        (out_dir / "claude.md").write_text(claude_result, encoding="utf-8")
        print(f"  Time: {claude_time:.1f}s")
        print(f"  Output: {len(claude_result)} chars")
        print(f"  Saved to {out_dir / 'claude.md'}")
    except Exception as e:
        print(f"  ERROR: {e}")
        claude_result = f"[ERROR: {e}]"

    print(f"\n--- Results in {out_dir}/ ---")
    print("  gemini.md  - Gemini 3.5 Flash output")
    print("  claude.md  - Claude Sonnet 4.6 output")
    print("  prompt.md  - Input prompt (for debugging)")


if __name__ == "__main__":
    main()
