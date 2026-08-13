# tests/test_reviewer_subagent_hooks.py
# @ai-rules:
# 1. [Pattern]: Structural guard, not behavioral -- parses YAML frontmatter of every file in
#    gemini-sidecar/agents/reviewers/*.md and asserts hook wiring, independent of hook content.
# 2. [Contract]: Any subagent whose `tools:` includes Bash MUST wire PreToolUse ->
#    validate-reviewer-bash.sh. Catches the exact regression C6 flagged: a future subagent
#    (or an edit to an existing one) that copy-pastes frontmatter and drops the hooks: block
#    silently ships unrestricted Bash access with no other signal.
"""Structural guard: every reviewer subagent with Bash access has the PreToolUse hook wired.

No Redis, no Brain, no live Claude CLI -- pure filesystem + YAML parsing against the
committed gemini-sidecar/agents/reviewers/*.md files.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

REVIEWERS_DIR = Path(__file__).resolve().parents[1] / "gemini-sidecar" / "agents" / "reviewers"
HOOK_PATH = "/app/hooks/validate-reviewer-bash.sh"

_FRONTMATTER_RE = re.compile(r"^---\n(.*?)\n---\n", re.DOTALL)


def _reviewer_files() -> list[Path]:
    if not REVIEWERS_DIR.is_dir():
        return []
    return sorted(REVIEWERS_DIR.glob("*.md"))


def _parse_frontmatter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    match = _FRONTMATTER_RE.match(text)
    assert match is not None, f"{path.name} has no YAML frontmatter block"
    return yaml.safe_load(match.group(1)) or {}


class TestReviewerSubagentHookWiring:
    def test_reviewer_files_exist(self):
        """Sanity check the fixture path itself resolves -- a silently-empty glob would
        make every other test in this class vacuously pass."""
        files = _reviewer_files()
        assert len(files) == 6, (
            f"Expected 6 reviewer subagent files, found {len(files)} in {REVIEWERS_DIR}"
        )

    @pytest.mark.parametrize("path", _reviewer_files(), ids=lambda p: p.name)
    def test_bash_tool_implies_hook_wired(self, path: Path):
        meta = _parse_frontmatter(path)
        tools = meta.get("tools", "")
        tool_list = [t.strip() for t in tools.split(",")] if isinstance(tools, str) else tools
        if "Bash" not in tool_list:
            pytest.skip(f"{path.name} does not declare Bash -- hook wiring not required")

        hooks = meta.get("hooks", {})
        pre_tool_use = hooks.get("PreToolUse", [])
        assert pre_tool_use, f"{path.name} has Bash but no hooks.PreToolUse block"

        matched_bash_hook = False
        for entry in pre_tool_use:
            if entry.get("matcher") != "Bash":
                continue
            for hook in entry.get("hooks", []):
                if hook.get("type") == "command" and hook.get("command") == HOOK_PATH:
                    matched_bash_hook = True
        assert matched_bash_hook, (
            f"{path.name} declares Bash but its PreToolUse.Bash matcher does not point at "
            f"{HOOK_PATH}"
        )

    @pytest.mark.parametrize("path", _reviewer_files(), ids=lambda p: p.name)
    def test_no_write_edit_tools(self, path: Path):
        """Second half of the hexagonal-boundary check: no reviewer subagent should ever
        gain Write/Edit/NotebookEdit -- that would make it a mutator, not a reviewer."""
        meta = _parse_frontmatter(path)
        tools = meta.get("tools", "")
        tool_list = [t.strip() for t in tools.split(",")] if isinstance(tools, str) else tools
        for forbidden in ("Write", "Edit", "NotebookEdit"):
            assert forbidden not in tool_list, f"{path.name} unexpectedly declares {forbidden}"

    @pytest.mark.parametrize("path", _reviewer_files(), ids=lambda p: p.name)
    def test_no_mcp_tool_access(self, path: Path):
        """Reviewer subagents report only through the orchestrating process
        (code_reviewer.md's stated design) -- no MCP tool should appear in their frontmatter."""
        meta = _parse_frontmatter(path)
        tools = meta.get("tools", "")
        tool_list = [t.strip() for t in tools.split(",")] if isinstance(tools, str) else tools
        assert not any(t.startswith("mcp__") for t in tool_list), (
            f"{path.name} unexpectedly declares MCP tool access"
        )


class TestCodeReviewerPermissionsFile:
    """The native Claude Code permission layer (--settings, engine-enforced) referenced by
    cli-executor.js ROLE_SETTINGS_FILE must exist, be valid JSON, and actually deny the
    categories the hook also covers -- this is layer 2 of 3. cli-executor.js now fails
    CLOSED (throws) if this file is missing at runtime rather than silently degrading to
    layer 3 (the hook) alone -- this test guards the file's committed presence/content so
    that fail-closed behavior is a deploy-time safety net, not the routine path.
    """

    SETTINGS_PATH = (
        Path(__file__).resolve().parents[1]
        / "gemini-sidecar"
        / "claude-settings"
        / "code-reviewer-permissions.json"
    )

    def test_settings_file_exists_and_parses(self):
        import json

        assert self.SETTINGS_PATH.is_file(), f"Missing {self.SETTINGS_PATH}"
        data = json.loads(self.SETTINGS_PATH.read_text(encoding="utf-8"))
        assert "permissions" in data
        assert "deny" in data["permissions"]

    def test_denies_edit_write_and_core_mutation_verbs(self):
        import json

        data = json.loads(self.SETTINGS_PATH.read_text(encoding="utf-8"))
        deny = data["permissions"]["deny"]
        for required in (
            "Edit", "Write", "NotebookEdit",
            "Bash(git commit *)", "Bash(git push *)", "Bash(git config *)",
            "Bash(rm *)", "Bash(dd *)", "Bash(cp *)",
            "Bash(curl *)", "Bash(wget *)",
            "Bash(scp *)", "Bash(ssh *)", "Bash(rsync *)", "Bash(sftp *)",
            "Bash(npm install *)", "Bash(pip install *)", "Bash(make *)",
            "Read(//tmp/git-creds-*)", "Read(//tmp/gh-token-map*)", "Read(~/.ssh/**)",
        ):
            assert required in deny, f"Expected deny rule {required!r} missing"

    def test_denies_token_map_read(self):
        """T-13: Multi-org token map must be blocked from CodeReviewer read access.
        The gh-token-map file contains installation tokens for all discovered GitHub
        orgs — a reviewer subagent reading it could exfiltrate cross-org credentials."""
        import json

        data = json.loads(self.SETTINGS_PATH.read_text(encoding="utf-8"))
        deny = data["permissions"]["deny"]
        assert "Read(//tmp/gh-token-map*)" in deny, (
            "Expected deny rule 'Read(//tmp/gh-token-map*)' missing from "
            "code-reviewer-permissions.json — multi-org token map must not be "
            "readable by reviewer subagents"
        )
