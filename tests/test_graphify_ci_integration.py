# tests/test_graphify_ci_integration.py
# @ai-rules:
# 1. [Contract]: Test specification suite for VMER-2188 (Graphify CI & knowledge graph integration).
# 2. [Pattern]: Validates .gitignore, .graphifyignore, .graphifyrc, .github/workflows/graphify.yaml, and artifacts.
# 3. [Coverage]: Implements T-1 through T-6 from Section 7a of BlackBoard/.plan.md.
# 4. [Independent Specification]: Tests specify expected behavior independently from parallel code executor.
# 5. [Graceful CI Degradation]: Tests requiring graphifyy runtime gracefully skip in standard CI environments lacking graphifyy.
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "graphify.yaml"
GRAPHIFYRC_PATH = REPO_ROOT / ".graphifyrc"
GRAPHIFYIGNORE_PATH = REPO_ROOT / ".graphifyignore"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"
ARTIFACTS_DIR = REPO_ROOT / "graphify-out"

ARTIFACTS_PRESENT = (
    (ARTIFACTS_DIR / "graph.json").is_file()
    and (ARTIFACTS_DIR / "graph.html").is_file()
    and (ARTIFACTS_DIR / "GRAPH_REPORT.md").is_file()
)

HAS_GRAPHIFY = importlib.util.find_spec("graphify") is not None


# ============================================================================
# T-1: Cache directory and manifest git exclusion (.gitignore)
# ============================================================================


class TestT1GitignoreExclusions:
    """T-1: Cache directory and manifest git exclusion in .gitignore."""

    def test_t1_gitignore_contains_required_patterns(self) -> None:
        """Verify .gitignore contains entries for ephemeral cache, manifest, and dotfiles."""
        assert GITIGNORE_PATH.is_file(), f".gitignore must exist at {GITIGNORE_PATH}"
        content = GITIGNORE_PATH.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

        assert "graphify-out/cache/" in lines, "graphify-out/cache/ must be ignored in .gitignore"
        assert "graphify-out/manifest.json" in lines, "graphify-out/manifest.json must be ignored in .gitignore"
        assert "graphify-out/.*" in lines, "graphify-out/.* must be ignored in .gitignore"

    @pytest.mark.parametrize(
        ("path", "should_ignore"),
        [
            ("graphify-out/cache/", True),
            ("graphify-out/cache/ast_cache.json", True),
            ("graphify-out/manifest.json", True),
            ("graphify-out/.cloud-cta-shown", True),
            ("graphify-out/graph.json", False),
            ("graphify-out/graph.html", False),
            ("graphify-out/GRAPH_REPORT.md", False),
        ],
    )
    def test_t1_git_check_ignore_behavior(self, path: str, should_ignore: bool) -> None:
        """Verify git check-ignore matches ephemeral paths and allows durable artifacts."""
        try:
            result = subprocess.run(
                ["git", "check-ignore", "-q", path],
                cwd=REPO_ROOT,
                check=False,
            )
            is_ignored = result.returncode == 0
            assert is_ignored == should_ignore, (
                f"Path {path!r} expected ignored={should_ignore}, but got {is_ignored}"
            )
        except FileNotFoundError:
            pytest.skip("git binary not available in environment")


# ============================================================================
# T-2: File count bounded under 500 (.graphifyignore)
# ============================================================================


class TestT2GraphifyignoreBounding:
    """T-2: File count bounded under 500 via .graphifyignore."""

    def test_t2_graphifyignore_exists_and_contains_core_patterns(self) -> None:
        """Verify .graphifyignore exists and contains essential exclusion categories."""
        assert GRAPHIFYIGNORE_PATH.is_file(), f".graphifyignore must exist at {GRAPHIFYIGNORE_PATH}"
        content = GRAPHIFYIGNORE_PATH.read_text(encoding="utf-8")
        lines = [line.strip() for line in content.splitlines() if line.strip() and not line.startswith("#")]

        # Test suites
        assert "tests/**" in lines, "tests/** must be excluded"
        assert "gemini-sidecar/tests/**" in lines, "gemini-sidecar/tests/** must be excluded"
        assert "ui/src/__tests__/**" in lines, "ui/src/__tests__/** must be excluded"
        assert "**/*.test.ts" in lines or "**/*.test.*" in lines, "TypeScript unit test files must be excluded"
        assert "**/*.test.tsx" in lines or "**/*.test.*" in lines, "React test files must be excluded"

        # Build artifacts
        assert "node_modules/**" in lines, "node_modules/** must be excluded"
        assert ".venv/**" in lines, ".venv/** must be excluded"
        assert "ui/dist/**" in lines, "ui/dist/** must be excluded"

        # Historical review and plan dumps
        assert "docs/reviews/**" in lines, "docs/reviews/** must be excluded"
        assert "docs/investigations/**" in lines, "docs/investigations/** must be excluded"
        assert "docs/plans/**" in lines, "docs/plans/** must be excluded"
        assert "docs/*-Review_*.md" in lines or "docs/*Review*.md" in lines, "docs review files must be excluded"

    @pytest.mark.skipif(not HAS_GRAPHIFY, reason="graphifyy not installed in environment")
    def test_t2_detect_bounds_file_count_under_500(self) -> None:
        """Verify graphify.detect with .graphifyignore keeps total files <= 500 (target ~450-480)."""
        assert GRAPHIFYIGNORE_PATH.is_file(), f".graphifyignore must exist at {GRAPHIFYIGNORE_PATH}"
        from graphify.detect import detect

        scan_result = detect(REPO_ROOT)
        total_files = scan_result["total_files"]

        assert total_files > 0, "detect must index a non-empty set of codebase files"
        assert total_files <= 500, (
            f"Expected total indexed files to be <= 500 (target ~450-480), but got {total_files}. "
            "Update .graphifyignore to prune additional unneeded files."
        )
        # Upper threshold warning should not trigger
        assert scan_result.get("warning") is None or "Large corpus" not in scan_result.get("warning", ""), (
            f"Upper threshold warning unexpectedly triggered: {scan_result.get('warning')}"
        )


# ============================================================================
# T-3: MDC rule classification (.graphifyrc)
# ============================================================================


class TestT3GraphifyrcClassification:
    """T-3: MDC rule classification via .graphifyrc."""

    def test_t3_graphifyrc_syntax_no_section_headers(self) -> None:
        """Verify .graphifyrc uses flat key-value pairs without INI section headers (AMD-01)."""
        assert GRAPHIFYRC_PATH.is_file(), f".graphifyrc must exist at {GRAPHIFYRC_PATH}"
        content = GRAPHIFYRC_PATH.read_text(encoding="utf-8")

        for line in content.splitlines():
            stripped = line.strip()
            assert not (stripped.startswith("[") and stripped.endswith("]")), (
                f"Section header {stripped!r} forbidden in .graphifyrc: rcfile.py expects flat key=value pairs"
            )

    def test_t3_graphify_mdc_rule_exists(self) -> None:
        """Verify .cursor/rules/graphify.mdc exists and has alwaysApply: true."""
        rule_path = REPO_ROOT / ".cursor" / "rules" / "graphify.mdc"
        assert rule_path.is_file(), f"graphify.mdc must exist at {rule_path}"
        content = rule_path.read_text(encoding="utf-8")
        assert "alwaysApply: true" in content, "graphify.mdc must set alwaysApply: true"
        assert "graphify-out/" in content, "graphify.mdc must document graphify-out/"

    @pytest.mark.skipif(not HAS_GRAPHIFY, reason="graphifyy not installed in environment")
    def test_t3_graphifyrc_loads_cleanly(self) -> None:
        """Verify graphify.rcfile.load_graphifyrc parses configuration without exceptions."""
        assert GRAPHIFYRC_PATH.is_file(), f".graphifyrc must exist at {GRAPHIFYRC_PATH}"
        from graphify.rcfile import load_graphifyrc

        config = load_graphifyrc(REPO_ROOT)
        assert isinstance(config, dict), "load_graphifyrc must return a dict"
        assert "languages" in config, ".graphifyrc must declare language overrides"
        assert config["languages"].get(".mdc") == ".md", (
            f"Expected language.mdc mapping to '.md', got: {config['languages'].get('.mdc')}"
        )

    @pytest.mark.skipif(not HAS_GRAPHIFY, reason="graphifyy not installed in environment")
    def test_t3_mdc_rules_classified_as_markdown(self) -> None:
        """Verify .cursor/rules/*.mdc are classified as FileType.DOCUMENT via active language overrides."""
        assert GRAPHIFYRC_PATH.is_file(), f".graphifyrc must exist at {GRAPHIFYRC_PATH}"
        from graphify.detect import FileType, classify_file, effective_suffix
        from graphify.rcfile import activate_language_overrides

        active_map = activate_language_overrides(REPO_ROOT)
        assert active_map.get(".mdc") == ".md", f"Expected active override .mdc -> .md, got: {active_map}"

        rules_dir = REPO_ROOT / ".cursor" / "rules"
        assert rules_dir.is_dir(), f"Cursor rules directory must exist at {rules_dir}"

        mdc_files = list(rules_dir.glob("*.mdc"))
        assert len(mdc_files) > 0, "At least one .mdc rule must exist in .cursor/rules"

        for mdc_path in mdc_files:
            eff = effective_suffix(mdc_path)
            assert eff == ".md", f"effective_suffix for {mdc_path.name} must be '.md', got {eff}"
            ftype = classify_file(mdc_path)
            assert ftype == FileType.DOCUMENT, (
                f"{mdc_path.name} must be classified as FileType.DOCUMENT, got {ftype}"
            )


# ============================================================================
# T-4: Deterministic headless extraction & clustering (CLI / artifacts)
# ============================================================================


class TestT4ExtractionArtifactsAndContracts:
    """T-4: Deterministic headless extraction & clustering artifacts."""

    def test_t4_command_chain_contract(self) -> None:
        """Verify the two-stage extraction command chain contract in .github/workflows/graphify.yaml."""
        assert WORKFLOW_PATH.is_file(), f"Workflow file must exist at {WORKFLOW_PATH}"
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        assert "graphify extract . --code-only --force" in workflow_text, (
            "Workflow must execute extract with --code-only --force to avoid remote LLM costs"
        )
        assert "GRAPHIFY_BACKEND=none graphify cluster-only . --no-label" in workflow_text, (
            "Workflow must execute cluster-only with GRAPHIFY_BACKEND=none and --no-label"
        )

    @pytest.mark.skipif(
        not ARTIFACTS_PRESENT,
        reason="graphify-out durable artifacts not yet generated (requires local probe Step 6 or CI run)",
    )
    def test_t4_generated_artifacts_validity(self) -> None:
        """Verify graph.json, graph.html, and GRAPH_REPORT.md are non-empty and well-formed."""
        graph_json_path = ARTIFACTS_DIR / "graph.json"
        graph_html_path = ARTIFACTS_DIR / "graph.html"
        graph_report_path = ARTIFACTS_DIR / "GRAPH_REPORT.md"

        assert graph_json_path.stat().st_size > 0, "graph.json must not be empty"
        assert graph_html_path.stat().st_size > 0, "graph.html must not be empty"
        assert graph_report_path.stat().st_size > 0, "GRAPH_REPORT.md must not be empty"

        # Validate JSON structure
        with open(graph_json_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert isinstance(data, dict), "graph.json must parse as a JSON object"
        assert "nodes" in data or "elements" in data, "graph.json must contain graph nodes"

        # Validate HTML visualizer
        html_content = graph_html_path.read_text(encoding="utf-8")
        assert "<html" in html_content.lower(), "graph.html must contain valid HTML tags"
        assert "sigma" in html_content.lower() or "graph" in html_content.lower() or "canvas" in html_content.lower()

        # Validate Markdown report
        report_content = graph_report_path.read_text(encoding="utf-8")
        assert report_content.startswith("#"), "GRAPH_REPORT.md must start with a markdown header"


# ============================================================================
# T-5: CI workflow syntax & token strategy (.github/workflows/graphify.yaml)
# ============================================================================


class TestT5WorkflowSyntaxAndTokenStrategy:
    """T-5: CI workflow syntax, permissions, and token strategy."""

    @pytest.fixture
    def workflow_yaml(self) -> dict:
        """Load and parse .github/workflows/graphify.yaml."""
        if not WORKFLOW_PATH.is_file():
            pytest.fail(f"Workflow file must exist at {WORKFLOW_PATH}")
        content = WORKFLOW_PATH.read_text(encoding="utf-8")
        data = yaml.safe_load(content)
        assert isinstance(data, dict), f"Failed to parse {WORKFLOW_PATH} as a YAML dictionary"
        return data

    def test_t5_workflow_triggers_and_concurrency(self, workflow_yaml: dict) -> None:
        """Verify push to main, cron schedule, manual dispatch, and concurrency group."""
        triggers = workflow_yaml.get("on") or workflow_yaml.get(True)
        assert triggers, "Workflow must define triggers ('on')"

        # Check push to main
        assert "push" in triggers, "Workflow must trigger on push"
        push_config = triggers["push"]
        branches = push_config.get("branches", [])
        assert "main" in branches, f"Workflow push must target 'main' branch, got {branches}"

        # Check schedule
        assert "schedule" in triggers, "Workflow must include recurring schedule trigger"
        schedules = triggers["schedule"]
        assert any("0 2 * * 0" in s.get("cron", "") for s in schedules), (
            f"Workflow schedule must run weekly Sunday at 02:00 UTC (cron '0 2 * * 0'), got {schedules}"
        )

        # Check workflow_dispatch
        assert "workflow_dispatch" in triggers, "Workflow must allow manual trigger via workflow_dispatch"

        # Check concurrency group
        concurrency = workflow_yaml.get("concurrency")
        assert concurrency, "Workflow must specify concurrency group"
        if isinstance(concurrency, dict):
            assert concurrency.get("group") == "graphify-sync", (
                f"Concurrency group must be 'graphify-sync', got {concurrency.get('group')}"
            )
            assert concurrency.get("cancel-in-progress") is False, "cancel-in-progress must be false"

    def test_t5_workflow_permissions(self, workflow_yaml: dict) -> None:
        """Verify contents: write permission is declared (top-level or job-level)."""
        top_perms = workflow_yaml.get("permissions", {})
        job_perms = {}
        jobs = workflow_yaml.get("jobs", {})
        for job in jobs.values():
            if isinstance(job, dict) and "permissions" in job:
                job_perms.update(job["permissions"])

        has_contents_write = (
            top_perms.get("contents") == "write"
            or job_perms.get("contents") == "write"
        )
        assert has_contents_write, "Workflow must grant 'contents: write' permission"

    def test_t5_job_timeout_and_token_scoping(self, workflow_yaml: dict) -> None:
        """Verify job timeout is bounded and GitHub App token is scoped to repository."""
        jobs = workflow_yaml.get("jobs", {})
        gen_job = jobs.get("generate-graph", {})
        assert gen_job.get("timeout-minutes") == 15, "generate-graph job must set timeout-minutes: 15"

        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        assert "repositories: ${{ github.event.repository.name }}" in workflow_text, (
            "App token must be scoped to current repository"
        )
        assert "ref: main" in workflow_text, (
            "actions/checkout must explicitly check out 'ref: main'"
        )

    def test_t5_split_token_auth_strategy(self, workflow_yaml: dict) -> None:
        """Verify GitHub App split-token authentication with fallback to GITHUB_TOKEN."""
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        assert "vars.USE_GITHUB_APP" in workflow_text, (
            "Workflow must inspect vars.USE_GITHUB_APP to select GitHub App token"
        )
        assert "GITHUB_TOKEN" in workflow_text, (
            "Workflow must retain GITHUB_TOKEN fallback"
        )

    def test_t5_clean_tree_guard_and_retry_loop(self) -> None:
        """Verify clean-tree guard (git diff --staged --quiet) and 5-attempt retry loop."""
        assert WORKFLOW_PATH.is_file(), f"Workflow file must exist at {WORKFLOW_PATH}"
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        # Clean-tree guard
        assert "git diff --staged --quiet" in workflow_text, (
            "Workflow must execute 'git diff --staged --quiet' to prevent empty commit errors on clean runs"
        )

        # 5-attempt retry loop with HEAD:main push and temp dir
        assert "MAX_RETRIES=5" in workflow_text, "Workflow must implement MAX_RETRIES=5"
        assert "git push origin HEAD:main" in workflow_text, (
            "Workflow must execute 'git push origin HEAD:main' to handle detached HEAD checkouts"
        )
        assert "runner.temp" in workflow_text, (
            "Workflow must use runner.temp for artifact staging"
        )

        # Artifact upload step
        assert "actions/upload-artifact" in workflow_text, "Workflow must upload graphify-out artifacts"
        assert "retention-days: 30" in workflow_text or "retention-days" in workflow_text, (
            "Workflow artifact retention must be configured"
        )


# ============================================================================
# T-6: Anti-recursion git protection (.github/workflows/graphify.yaml)
# ============================================================================


class TestT6AntiRecursionGitProtection:
    """T-6: Anti-recursion git protection via paths-ignore and [skip ci]."""

    def test_t6_paths_ignore_excludes_graphify_outputs(self) -> None:
        """Verify push trigger paths-ignore excludes graphify-out/** to prevent loop recursion."""
        assert WORKFLOW_PATH.is_file(), f"Workflow file must exist at {WORKFLOW_PATH}"
        data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
        triggers = data.get("on") or data.get(True) or {}
        push_config = triggers.get("push", {})

        paths_ignore = push_config.get("paths-ignore", [])
        assert "graphify-out/**" in paths_ignore, (
            f"paths-ignore must exclude 'graphify-out/**', got: {paths_ignore}"
        )

    def test_t6_bot_commit_message_contains_skip_ci(self) -> None:
        """Verify automated bot commit message includes [skip ci] annotation."""
        assert WORKFLOW_PATH.is_file(), f"Workflow file must exist at {WORKFLOW_PATH}"
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        assert "[skip ci]" in workflow_text, (
            "Bot commit message must contain '[skip ci]' annotation to prevent triggering recursive CI builds"
        )
        assert "chore(graphify)" in workflow_text, (
            "Bot commit message must adhere to conventional commit format 'chore(graphify): ...'"
        )
