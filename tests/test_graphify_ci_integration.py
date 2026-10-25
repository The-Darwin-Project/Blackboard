# tests/test_graphify_ci_integration.py
# @ai-rules:
# 1. [Contract]: Test specification suite for VMER-2188 (Graphify CI & knowledge graph integration).
# 2. [Pattern]: Validates .gitignore, .graphifyignore, .graphifyrc, .cursor/rules/graphify.mdc, .github/workflows/graphify.yaml, and artifacts.
# 3. [Pattern]: Workflow assertions use the PARSED YAML (steps by id/name) and comment-stripped scripts; never raw-substring checks that a comment could satisfy.
# 4. [Behavioral]: TestCommitStepBehavior executes the real `run:` script of the step with id "commit" against a temporary bare git remote (no network). Keep that step id and the script's MAX_RETRIES=5 / $RUNNER_TEMP / `git_remote push origin HEAD:main` contract stable.
# 5. [CI Strictness]: Tests requiring the graphifyy runtime (pinned in requirements-dev.txt) SKIP locally when it is missing but FAIL when CI=true, so CI can never silently skip them.
# 6. [Gotcha]: graphifyy (double-y) is the official PyPI package for Graphify-Labs/graphify (CLI: graphify); it is not a typosquat.
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import stat
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "graphify.yaml"
GRAPHIFYRC_PATH = REPO_ROOT / ".graphifyrc"
GRAPHIFYIGNORE_PATH = REPO_ROOT / ".graphifyignore"
GITIGNORE_PATH = REPO_ROOT / ".gitignore"
MDC_RULE_PATH = REPO_ROOT / ".cursor" / "rules" / "graphify.mdc"
REQUIREMENTS_DEV_PATH = REPO_ROOT / "requirements-dev.txt"
ARTIFACTS_DIR = REPO_ROOT / "graphify-out"

DURABLE_ARTIFACTS = ("graph.json", "graph.html", "GRAPH_REPORT.md")
GRAPHIFY_VERSION_PIN = "0.9.93"

HAS_GRAPHIFY = importlib.util.find_spec("graphify") is not None


def _running_in_ci(env: dict[str, str] | None = None) -> bool:
    return (env if env is not None else os.environ).get("CI", "").lower() == "true"


def _missing_dependency_action(available: bool, ci: bool) -> str:
    """Return 'run', 'skip' (local dev) or 'fail' (CI must never silently skip)."""
    if available:
        return "run"
    return "fail" if ci else "skip"


def _require(available: bool, what: str) -> None:
    action = _missing_dependency_action(available, _running_in_ci())
    if action == "fail":
        pytest.fail(f"{what} is required in CI (CI=true) but is not available; check requirements-dev.txt")
    if action == "skip":
        pytest.skip(f"{what} not available in this environment")


@pytest.fixture
def graphify_runtime() -> None:
    """Skip locally / fail in CI when the graphifyy runtime is not installed."""
    _require(HAS_GRAPHIFY, "graphifyy runtime (pip install -r requirements-dev.txt)")


def _gitignore_lines() -> list[str]:
    return [
        line.strip()
        for line in GITIGNORE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _graphifyignore_lines() -> list[str]:
    return [
        line.strip()
        for line in GRAPHIFYIGNORE_PATH.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]


def _strip_comments(script: str) -> str:
    """Drop full-line shell comments so assertions cannot be satisfied by a comment."""
    return "\n".join(line for line in script.splitlines() if not line.lstrip().startswith("#"))


def _load_workflow() -> dict:
    assert WORKFLOW_PATH.is_file(), f"Workflow file must exist at {WORKFLOW_PATH}"
    data = yaml.safe_load(WORKFLOW_PATH.read_text(encoding="utf-8"))
    assert isinstance(data, dict), f"Failed to parse {WORKFLOW_PATH} as a YAML dictionary"
    return data


def _workflow_triggers(workflow: dict) -> dict:
    # PyYAML (YAML 1.1) parses the bare key `on` as boolean True.
    triggers = workflow.get("on") or workflow.get(True)
    assert triggers, "Workflow must define triggers ('on')"
    return triggers


def _job_steps(workflow: dict) -> list[dict]:
    return workflow["jobs"]["generate-graph"]["steps"]


def _step_by_id(workflow: dict, step_id: str) -> dict:
    matches = [s for s in _job_steps(workflow) if s.get("id") == step_id]
    assert len(matches) == 1, f"Expected exactly one step with id {step_id!r}, found {len(matches)}"
    return matches[0]


def _step_by_uses(workflow: dict, prefix: str) -> dict:
    matches = [s for s in _job_steps(workflow) if str(s.get("uses", "")).startswith(prefix)]
    assert len(matches) == 1, f"Expected exactly one step using {prefix!r}, found {len(matches)}"
    return matches[0]


# ============================================================================
# T-1: Cache directory and manifest git exclusion (.gitignore)
# ============================================================================


class TestT1GitignoreExclusions:
    """T-1: Cache directory and manifest git exclusion in .gitignore."""

    def test_t1_gitignore_contains_required_patterns(self) -> None:
        """Verify .gitignore contains entries for ephemeral cache, manifest, and dotfiles."""
        assert GITIGNORE_PATH.is_file(), f".gitignore must exist at {GITIGNORE_PATH}"
        lines = _gitignore_lines()

        assert "graphify-out/cache/" in lines, "graphify-out/cache/ must be ignored in .gitignore"
        assert "graphify-out/manifest.json" in lines, "graphify-out/manifest.json must be ignored in .gitignore"
        assert "graphify-out/.*" in lines, "graphify-out/.* must be ignored in .gitignore"

    def test_t1_plan_md_ignore_is_scoped_to_probe_data(self) -> None:
        """A repo-wide *.plan.md would silently ignore tracked docs/plans/*.plan.md files."""
        lines = _gitignore_lines()
        assert "*.plan.md" not in lines, "*.plan.md must stay scoped (probe-data/*.plan.md), not repo-wide"
        assert "probe-data/*.plan.md" in lines, "probe-data/*.plan.md must be ignored"

    @pytest.mark.parametrize(
        ("path", "should_ignore"),
        [
            ("graphify-out/cache/", True),
            ("graphify-out/cache/ast_cache.json", True),
            ("graphify-out/manifest.json", True),
            ("graphify-out/.cloud-cta-shown", True),
            ("graphify-out/2026-10-25/", True),
            ("graphify-out/graph.json", False),
            ("graphify-out/graph.html", False),
            ("graphify-out/GRAPH_REPORT.md", False),
            ("docs/plans/memory-reflex.plan.md", False),
            ("probe-data/session.plan.md", True),
        ],
    )
    def test_t1_git_check_ignore_behavior(self, path: str, should_ignore: bool) -> None:
        """Verify .gitignore rules directly (--no-index so tracked files are genuinely evaluated)."""
        _require(shutil.which("git") is not None, "git binary")
        result = subprocess.run(
            ["git", "check-ignore", "--no-index", "-q", path],
            cwd=REPO_ROOT,
            check=False,
        )
        assert result.returncode in (0, 1), f"git check-ignore failed unexpectedly (rc={result.returncode})"
        is_ignored = result.returncode == 0
        assert is_ignored == should_ignore, f"Path {path!r} expected ignored={should_ignore}, but got {is_ignored}"


# ============================================================================
# T-2: File count bounded under 500 (.graphifyignore)
# ============================================================================


REQUIRED_GRAPHIFYIGNORE_PATTERNS = [
    # Test suites and fixtures
    "tests/**",
    "gemini-sidecar/tests/**",
    "ui/src/__tests__/**",
    "**/*.test.ts",
    "**/*.test.tsx",
    "**/*.test.js",
    "**/*.spec.ts",
    "**/*.spec.tsx",
    # Build artifacts & dependencies
    "ui/dist/**",
    "ui/public/**",
    "ui/src/assets/**",
    "node_modules/**",
    ".venv/**",
    "venv/**",
    "__pycache__/**",
    "*.egg-info/**",
    # Infrastructure charts
    "helm/**",
    # Scratch / probe data
    "probe-data/**",
    "scripts/**",
    "skill-author/**",
    ".claude/**",
    ".cursor/prompts/**",
    # Historical review logs and incident reports
    "docs/reviews/**",
    "docs/investigations/**",
    "docs/plans/**",
    "docs/lessons-learned/**",
    "docs/*-Review_*.md",
    "docs/*Review*.md",
    "docs/events/**",
    "docs/evt-*.md",
]


class TestT2GraphifyignoreBounding:
    """T-2: File count bounded under 500 via .graphifyignore."""

    def test_t2_graphifyignore_exists_and_contains_core_patterns(self) -> None:
        """Verify .graphifyignore contains every required exclusion pattern (exact lines)."""
        assert GRAPHIFYIGNORE_PATH.is_file(), f".graphifyignore must exist at {GRAPHIFYIGNORE_PATH}"
        lines = set(_graphifyignore_lines())

        missing = [p for p in REQUIRED_GRAPHIFYIGNORE_PATTERNS if p not in lines]
        assert not missing, f".graphifyignore is missing required patterns: {missing}"

    def test_t2_detect_bounds_file_count_under_500(self, graphify_runtime: None) -> None:
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


class TestT2RuntimeDependencyPolicy:
    """T-2b: graphifyy runtime tests must run (not skip) in CI."""

    def test_missing_dependency_policy_fails_in_ci_and_skips_locally(self) -> None:
        assert _missing_dependency_action(available=True, ci=True) == "run"
        assert _missing_dependency_action(available=True, ci=False) == "run"
        assert _missing_dependency_action(available=False, ci=True) == "fail"
        assert _missing_dependency_action(available=False, ci=False) == "skip"
        assert _running_in_ci({"CI": "true"}) is True
        assert _running_in_ci({"CI": "false"}) is False
        assert _running_in_ci({}) is False

    def test_requirements_dev_pins_graphifyy(self) -> None:
        """requirements-dev.txt (installed by ci.yaml) must pin graphifyy, matching the workflow pin."""
        lines = [
            line.strip()
            for line in REQUIREMENTS_DEV_PATH.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]
        assert f"graphifyy=={GRAPHIFY_VERSION_PIN}" in lines, (
            f"requirements-dev.txt must pin graphifyy=={GRAPHIFY_VERSION_PIN} so CI runs the runtime tests"
        )
        install_run = _step_by_name(_load_workflow(), "Install graphify")["run"]
        assert f"graphifyy=={GRAPHIFY_VERSION_PIN}" in _strip_comments(install_run), (
            "Workflow install pin must match requirements-dev.txt"
        )

    def test_requirements_dev_documents_double_y_provenance(self) -> None:
        text = REQUIREMENTS_DEV_PATH.read_text(encoding="utf-8")
        assert "Graphify-Labs/graphify" in text and "double-y" in text, (
            "requirements-dev.txt must explain that graphifyy (double-y) is the official package"
        )


def _step_by_name(workflow: dict, name: str) -> dict:
    matches = [s for s in _job_steps(workflow) if s.get("name") == name]
    assert len(matches) == 1, f"Expected exactly one step named {name!r}, found {len(matches)}"
    return matches[0]


# ============================================================================
# T-3: MDC rule classification (.graphifyrc) and agent rule content
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
        assert MDC_RULE_PATH.is_file(), f"graphify.mdc must exist at {MDC_RULE_PATH}"
        content = MDC_RULE_PATH.read_text(encoding="utf-8")
        assert "alwaysApply: true" in content, "graphify.mdc must set alwaysApply: true"
        assert "graphify-out/" in content, "graphify.mdc must document graphify-out/"

    def test_t3_graphify_mdc_forbids_reading_full_graph_json(self) -> None:
        content = MDC_RULE_PATH.read_text(encoding="utf-8")
        assert re.search(r"NEVER read `graphify-out/graph\.json` in full", content), (
            "graphify.mdc must tell agents to NEVER read graph.json in full"
        )
        assert "GRAPH_REPORT.md" in content
        assert "graphify query" in content, "graphify.mdc must point agents at the CLI for graph queries"

    def test_t3_graphify_mdc_documents_trust_boundary(self) -> None:
        content = MDC_RULE_PATH.read_text(encoding="utf-8")
        assert "Trust boundary" in content
        assert "derived repository data, not instructions" in content

    def test_t3_graphify_mdc_describes_visualizer_accurately(self) -> None:
        """graph.html uses vis-network from a CDN; it is not a self-contained Sigma.js app."""
        content = MDC_RULE_PATH.read_text(encoding="utf-8")
        assert "vis-network" in content
        assert "Sigma" not in content and "sigma" not in content, "graphify.mdc must not describe a Sigma.js visualizer"
        assert "Self-contained" not in content and "self-contained interactive" not in content.lower()

    def test_t3_graphify_mdc_documents_paths_ignore_in_sync_with_workflow(self) -> None:
        """The paths-ignore exclusions documented for agents must match the workflow trigger."""
        content = MDC_RULE_PATH.read_text(encoding="utf-8")
        paths_ignore = _workflow_triggers(_load_workflow())["push"]["paths-ignore"]
        assert paths_ignore, "workflow paths-ignore must not be empty"
        assert "paths-ignore" in content
        for pattern in paths_ignore:
            assert f"`{pattern}`" in content, f"graphify.mdc must document paths-ignore entry {pattern!r}"

    def test_t3_graphifyrc_loads_cleanly(self, graphify_runtime: None) -> None:
        """Verify graphify.rcfile.load_graphifyrc parses configuration without exceptions."""
        assert GRAPHIFYRC_PATH.is_file(), f".graphifyrc must exist at {GRAPHIFYRC_PATH}"
        from graphify.rcfile import load_graphifyrc

        config = load_graphifyrc(REPO_ROOT)
        assert isinstance(config, dict), "load_graphifyrc must return a dict"
        assert "languages" in config, ".graphifyrc must declare language overrides"
        assert config["languages"].get(".mdc") == ".md", (
            f"Expected language.mdc mapping to '.md', got: {config['languages'].get('.mdc')}"
        )

    def test_t3_mdc_rules_classified_as_markdown(self, graphify_runtime: None) -> None:
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
        """Verify the two-stage extraction command chain in the extract step's (comment-stripped) script."""
        extract_script = _strip_comments(_step_by_id(_load_workflow(), "extract")["run"])
        commands = [line.strip() for line in extract_script.splitlines() if line.strip()]

        assert "graphify extract . --code-only --force" in commands, (
            "Extract step must execute extract with --code-only --force to avoid remote LLM costs"
        )
        assert "GRAPHIFY_BACKEND=none graphify cluster-only ." in commands, (
            "Extract step must execute cluster-only with GRAPHIFY_BACKEND=none"
        )
        assert commands.index("graphify extract . --code-only --force") < commands.index(
            "GRAPHIFY_BACKEND=none graphify cluster-only ."
        ), "extract must run before cluster-only"

    def test_t4_generated_artifacts_validity(self) -> None:
        """Verify committed graph.json, graph.html, and GRAPH_REPORT.md are non-empty and well-formed."""
        for name in DURABLE_ARTIFACTS:
            path = ARTIFACTS_DIR / name
            assert path.is_file(), f"Durable artifact {path} must be committed"
            assert path.stat().st_size > 0, f"{name} must not be empty"

        data = json.loads((ARTIFACTS_DIR / "graph.json").read_text(encoding="utf-8"))
        assert isinstance(data, dict), "graph.json must parse as a JSON object"
        nodes = data.get("nodes")
        assert isinstance(nodes, list) and len(nodes) > 0, "graph.json must contain a non-empty nodes list"
        edges = data.get("links", data.get("edges"))
        assert isinstance(edges, list) and len(edges) > 0, "graph.json must contain a non-empty links/edges list"
        node_ids = {n["id"] for n in nodes}
        assert len(node_ids) == len(nodes), "graph.json node ids must be unique"
        assert all(e["source"] in node_ids and e["target"] in node_ids for e in edges), (
            "every graph.json edge must reference existing nodes"
        )

        html_content = (ARTIFACTS_DIR / "graph.html").read_text(encoding="utf-8")
        assert "<html" in html_content.lower(), "graph.html must contain valid HTML tags"
        assert "vis-network" in html_content, "graph.html is expected to be a vis-network visualizer"

        report_content = (ARTIFACTS_DIR / "GRAPH_REPORT.md").read_text(encoding="utf-8")
        assert report_content.startswith("# Graph Report"), "GRAPH_REPORT.md must start with the report header"


# ============================================================================
# T-5: CI workflow syntax & token strategy (.github/workflows/graphify.yaml)
# ============================================================================


class TestT5WorkflowSyntaxAndTokenStrategy:
    """T-5: CI workflow syntax, permissions, and token strategy."""

    @pytest.fixture
    def workflow_yaml(self) -> dict:
        """Load and parse .github/workflows/graphify.yaml."""
        return _load_workflow()

    def test_t5_workflow_triggers_and_concurrency(self, workflow_yaml: dict) -> None:
        """Verify push to main, cron schedule, manual dispatch, and concurrency group."""
        triggers = _workflow_triggers(workflow_yaml)

        assert "push" in triggers, "Workflow must trigger on push"
        branches = triggers["push"].get("branches", [])
        assert "main" in branches, f"Workflow push must target 'main' branch, got {branches}"

        assert "schedule" in triggers, "Workflow must include recurring schedule trigger"
        schedules = triggers["schedule"]
        assert any(s.get("cron") == "0 2 * * 0" for s in schedules), (
            f"Workflow schedule must run weekly Sunday at 02:00 UTC (cron '0 2 * * 0'), got {schedules}"
        )

        assert "workflow_dispatch" in triggers, "Workflow must allow manual trigger via workflow_dispatch"

        concurrency = workflow_yaml.get("concurrency")
        assert isinstance(concurrency, dict), "Workflow must specify a concurrency mapping"
        assert concurrency.get("group") == "graphify-sync", (
            f"Concurrency group must be 'graphify-sync', got {concurrency.get('group')}"
        )
        assert concurrency.get("cancel-in-progress") is False, "cancel-in-progress must be false"

    def test_t5_workflow_permissions(self, workflow_yaml: dict) -> None:
        """Verify contents: write permission is declared (top-level or job-level)."""
        top_perms = workflow_yaml.get("permissions", {})
        job_perms = workflow_yaml["jobs"]["generate-graph"].get("permissions", {})
        assert top_perms.get("contents") == "write" or job_perms.get("contents") == "write", (
            "Workflow must grant 'contents: write' permission"
        )

    def test_t5_job_is_gated_to_main(self, workflow_yaml: dict) -> None:
        """workflow_dispatch from a non-main ref must not run with write credentials."""
        job = workflow_yaml["jobs"]["generate-graph"]
        assert job.get("if") == "github.ref == 'refs/heads/main'", (
            f"generate-graph must be gated on refs/heads/main, got {job.get('if')!r}"
        )

    def test_t5_job_timeout_and_token_scoping(self, workflow_yaml: dict) -> None:
        """Verify job timeout is bounded, App token is repo-scoped, and checkout pins ref main."""
        job = workflow_yaml["jobs"]["generate-graph"]
        assert job.get("timeout-minutes") == 15, "generate-graph job must set timeout-minutes: 15"

        app_token = _step_by_id(workflow_yaml, "app-token")
        assert app_token["uses"].startswith("actions/create-github-app-token@")
        assert app_token["with"]["repositories"] == "${{ github.event.repository.name }}", (
            "App token must be scoped to current repository"
        )
        assert app_token["with"]["owner"] == "${{ github.repository_owner }}"

        checkout = _step_by_uses(workflow_yaml, "actions/checkout@")
        assert checkout["with"]["ref"] == "main", "actions/checkout must explicitly check out 'ref: main'"

    def test_t5_split_token_auth_strategy(self, workflow_yaml: dict) -> None:
        """Verify GitHub App split-token authentication with fallback to GITHUB_TOKEN."""
        app_token = _step_by_id(workflow_yaml, "app-token")
        assert app_token.get("if") == "vars.USE_GITHUB_APP == 'true'", (
            "App token step must be selected by vars.USE_GITHUB_APP == 'true'"
        )

        expected = "${{ steps.app-token.outputs.token || secrets.GITHUB_TOKEN }}"
        checkout = _step_by_uses(workflow_yaml, "actions/checkout@")
        assert checkout["with"]["token"] == expected, "checkout token must fall back to GITHUB_TOKEN"
        assert _step_by_id(workflow_yaml, "commit")["env"]["GH_TOKEN"] == expected, (
            "commit step must receive the same App-token-or-GITHUB_TOKEN credential"
        )

    def test_t5_checkout_does_not_persist_credentials(self, workflow_yaml: dict) -> None:
        checkout = _step_by_uses(workflow_yaml, "actions/checkout@")
        assert checkout["with"].get("persist-credentials") is False, (
            "checkout must set persist-credentials: false so pip/graphify steps never see write credentials"
        )

    def test_t5_credentials_only_reach_the_commit_step(self, workflow_yaml: dict) -> None:
        """Only checkout (token input) and the commit step may reference the write token."""
        for step in _job_steps(workflow_yaml):
            uses = str(step.get("uses", ""))
            serialized = json.dumps({k: v for k, v in step.items() if k != "name"})
            references_token = "GITHUB_TOKEN" in serialized or "app-token.outputs.token" in serialized
            if not references_token:
                continue
            allowed = (
                step.get("id") == "commit"
                or uses.startswith("actions/checkout@")
            )
            assert allowed, f"Step {step.get('name')!r} must not receive the write token"

    def test_t5_run_scripts_use_runner_temp_env_not_expression(self, workflow_yaml: dict) -> None:
        run_scripts = {s["name"]: s["run"] for s in _job_steps(workflow_yaml) if "run" in s}
        assert run_scripts, "workflow must contain run steps"
        for name, script in run_scripts.items():
            assert "${{" not in _strip_comments(script), (
                f"Step {name!r}: use environment variables instead of ${{{{ }}}} expressions inside run scripts"
            )
        commit_script = _strip_comments(run_scripts["Commit and push graph updates"])
        assert "$RUNNER_TEMP" in commit_script, "commit step must stage artifacts under $RUNNER_TEMP"

    def test_t5_clean_tree_guard_and_retry_loop(self, workflow_yaml: dict) -> None:
        """Verify the (comment-stripped) commit script has the clean-tree guard and 5-attempt retry loop."""
        script = _strip_comments(_step_by_id(workflow_yaml, "commit")["run"])
        lines = [line.strip() for line in script.splitlines()]

        assert "if git diff --staged --quiet; then" in lines, (
            "Commit step must guard against empty commits with 'git diff --staged --quiet'"
        )
        assert "MAX_RETRIES=5" in lines, "Commit step must implement MAX_RETRIES=5"
        assert "if git_remote push origin HEAD:main; then" in lines, (
            "Commit step must push 'origin HEAD:main' (works for detached HEAD checkouts)"
        )
        assert "git_remote fetch origin main" in lines and "git reset --hard origin/main" in lines, (
            "Retries must re-sync to origin/main before re-committing"
        )

    def test_t5_artifact_upload_step(self, workflow_yaml: dict) -> None:
        """Artifact upload must be configured with 30-day retention and gated on the extract step."""
        upload = _step_by_uses(workflow_yaml, "actions/upload-artifact@")
        assert upload["with"]["retention-days"] == 30, "artifact retention-days must be exactly 30"
        assert upload["with"]["name"] == "graphify-artifacts"
        uploaded_paths = upload["with"]["path"].split()
        assert uploaded_paths == [f"graphify-out/{n}" for n in DURABLE_ARTIFACTS], (
            f"upload-artifact must upload exactly the durable artifacts, got {uploaded_paths}"
        )
        condition = upload.get("if", "")
        assert "steps.extract.outcome == 'success'" in condition, (
            "upload-artifact must be gated on the extract step succeeding"
        )

    def test_t5_extract_step_has_stable_id(self, workflow_yaml: dict) -> None:
        extract = _step_by_id(workflow_yaml, "extract")
        steps = _job_steps(workflow_yaml)
        assert steps.index(extract) < steps.index(_step_by_id(workflow_yaml, "commit")), (
            "extract must run before commit"
        )

    def test_t5_install_documents_double_y_provenance(self) -> None:
        """Keep the typosquat false-positive explanation in the workflow's @ai-rules header."""
        header = WORKFLOW_PATH.read_text(encoding="utf-8").split("name:", 1)[0]
        assert "Graphify-Labs/graphify" in header and "double-y" in header, (
            "Workflow @ai-rules must document that graphifyy (double-y) is the official package"
        )

    def test_t5_github_pages_deployment_configuration(self, workflow_yaml: dict) -> None:
        """Verify GitHub Pages artifact upload and deployment job configuration."""
        # 1. upload-pages-artifact in generate-graph
        upload_pages = [
            s for s in _job_steps(workflow_yaml)
            if str(s.get("uses", "")).startswith("actions/upload-pages-artifact@")
        ]
        assert len(upload_pages) == 1, "generate-graph job must include actions/upload-pages-artifact"
        assert "steps.extract.outcome == 'success'" in upload_pages[0].get("if", "")

        # 2. deploy-pages job
        assert "deploy-pages" in workflow_yaml["jobs"], "Workflow must define deploy-pages job"
        deploy_job = workflow_yaml["jobs"]["deploy-pages"]
        assert deploy_job.get("needs") == "generate-graph"
        assert deploy_job.get("if") == "github.ref == 'refs/heads/main'"

        perms = deploy_job.get("permissions", {})
        assert perms.get("pages") == "write"
        assert perms.get("id-token") == "write"

        env = deploy_job.get("environment", {})
        assert env.get("name") == "github-pages"

        deploy_step = [
            s for s in deploy_job.get("steps", [])
            if str(s.get("uses", "")).startswith("actions/deploy-pages@")
        ]
        assert len(deploy_step) == 1, "deploy-pages job must invoke actions/deploy-pages"

    def test_t5_extract_step_configures_viz_node_limit(self, workflow_yaml: dict) -> None:
        """Verify the extract step configures GRAPHIFY_VIZ_NODE_LIMIT to prevent community-meta collapse."""
        extract = _step_by_id(workflow_yaml, "extract")
        step_env = extract.get("env", {})
        assert "GRAPHIFY_VIZ_NODE_LIMIT" in step_env, (
            "Extract step must set GRAPHIFY_VIZ_NODE_LIMIT env var"
        )
        assert int(step_env["GRAPHIFY_VIZ_NODE_LIMIT"]) >= 10000, (
            f"GRAPHIFY_VIZ_NODE_LIMIT must be >= 10,000, got: {step_env['GRAPHIFY_VIZ_NODE_LIMIT']}"
        )


# ============================================================================
# T-6: Anti-recursion git protection (.github/workflows/graphify.yaml)
# ============================================================================


class TestT6AntiRecursionGitProtection:
    """T-6: Anti-recursion git protection via paths-ignore and [skip ci]."""

    def test_t6_paths_ignore_excludes_graphify_outputs(self) -> None:
        """Verify push trigger paths-ignore excludes graphify-out/** to prevent loop recursion."""
        push_config = _workflow_triggers(_load_workflow())["push"]
        paths_ignore = push_config.get("paths-ignore", [])
        assert "graphify-out/**" in paths_ignore, (
            f"paths-ignore must exclude 'graphify-out/**', got: {paths_ignore}"
        )

    def test_t6_bot_commit_message_contains_skip_ci(self) -> None:
        """Verify the actual git commit command's message uses conventional format and [skip ci]."""
        script = _strip_comments(_step_by_id(_load_workflow(), "commit")["run"])
        commit_lines = [
            line.strip() for line in script.splitlines() if line.strip().startswith("git commit")
        ]
        assert commit_lines == ['git commit -m "chore(graphify): update knowledge graph [skip ci]"'], (
            f"Expected a single conventional '[skip ci]' bot commit, got {commit_lines}"
        )


# ============================================================================
# T-7: Behavioral tests of the commit/push step against a temporary bare remote
# ============================================================================

OLD_GRAPH = {
    "directed": False,
    "multigraph": False,
    "graph": {"schema_version": 1},
    "nodes": [{"id": "a"}],
    "links": [],
    "hyperedges": [],
    "built_at_commit": "aaaaaaaa",
}
OLD_REPORT = (
    "# Graph Report - Demo  (2026-01-01)\n\n"
    "## Summary\n- 1 nodes\n\n"
    "## Graph Freshness\n- Built from commit: `aaaaaaaa`\n- Run `git rev-parse HEAD` to compare.\n"
)
OLD_HTML = "<html><script src=\"vis-network.min.js\"></script>v1</html>\n"
BOT_SUBJECT = "chore(graphify): update knowledge graph [skip ci]"


def _artifact_files(*, graph: dict, report: str, html: str) -> dict[str, str]:
    return {
        "graph.json": json.dumps(graph, separators=(",", ":")),
        "graph.html": html,
        "GRAPH_REPORT.md": report,
    }


def _changed_graph() -> dict:
    graph = json.loads(json.dumps(OLD_GRAPH))
    graph["nodes"].append({"id": "b"})
    graph["links"].append({"source": "a", "target": "b"})
    graph["built_at_commit"] = "bbbbbbbb"
    return graph


def _changed_report() -> str:
    return (
        OLD_REPORT.replace("(2026-01-01)", "(2026-02-02)")
        .replace("- 1 nodes", "- 2 nodes")
        .replace("aaaaaaaa", "bbbbbbbb")
    )


def _volatile_only_graph() -> dict:
    graph = json.loads(json.dumps(OLD_GRAPH))
    graph["built_at_commit"] = "cccccccc"
    return graph


def _volatile_only_report() -> str:
    return OLD_REPORT.replace("(2026-01-01)", "(2026-03-03)").replace("aaaaaaaa", "cccccccc")


@dataclass
class Sandbox:
    root: Path
    remote: Path
    work: Path
    other: Path
    runner_temp: Path
    shim_dir: Path
    sleep_log: Path
    script: Path
    env: dict[str, str]

    def git(self, *args: str, cwd: Path | None = None) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=cwd or self.work,
            env=self.env,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def write_artifacts(self, files: dict[str, str], repo: Path | None = None) -> None:
        out = (repo or self.work) / "graphify-out"
        out.mkdir(exist_ok=True)
        for name, content in files.items():
            (out / name).write_text(content, encoding="utf-8")

    def remote_head(self) -> str:
        return self.git("rev-parse", "refs/heads/main", cwd=self.remote)

    def remote_subjects(self) -> list[str]:
        return self.git("log", "--format=%s", "refs/heads/main", cwd=self.remote).splitlines()

    def remote_file(self, path: str) -> str:
        return self.git("show", f"refs/heads/main:{path}", cwd=self.remote)

    def sleeps(self) -> list[str]:
        return self.sleep_log.read_text().split() if self.sleep_log.exists() else []

    def run_step(self, extra_env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        env = {**self.env, **(extra_env or {})}
        # Mirrors GitHub's `shell: bash` invocation: bash --noprofile --norc -eo pipefail {0}
        return subprocess.run(
            ["bash", "--noprofile", "--norc", "-eo", "pipefail", str(self.script)],
            cwd=self.work,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )

    def add_remote_hook(self, name: str, body: str) -> None:
        hook = self.remote / "hooks" / name
        hook.write_text("#!/bin/sh\n" + body)
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC)

    def add_race_hook(self, files: dict[str, str], marker_name: str = "race.done") -> None:
        """On the first push, another writer lands a commit on origin/main so the push is non-fast-forward."""
        marker = self.root / marker_name
        other_files = " ".join(f"graphify-out/{n}" for n in files) if files else "other.txt"
        body = f"""
if [ ! -f "{marker}" ]; then
  touch "{marker}"
  env -u GIT_DIR -u GIT_WORK_TREE -u GIT_INDEX_FILE -u GIT_PREFIX sh -c '
    set -e
    cd "{self.other}"
    git pull -q --ff-only origin main
    echo racer > other.txt
    git add other.txt {other_files}
    git commit -q -m "feat: concurrent commit from another writer"
    git push -q origin HEAD:main
  '
fi
exit 0
"""
        hook = self.work / ".git" / "hooks" / "pre-push"
        hook.write_text("#!/bin/sh\n" + body)
        hook.chmod(hook.stat().st_mode | stat.S_IEXEC)


@pytest.fixture
def commit_script_text() -> str:
    return _step_by_id(_load_workflow(), "commit")["run"]


@pytest.fixture
def sandbox(tmp_path: Path, commit_script_text: str) -> Sandbox:
    for tool in ("git", "bash", "python3"):
        _require(shutil.which(tool) is not None, f"{tool} binary")

    remote = tmp_path / "remote.git"
    work = tmp_path / "work"
    other = tmp_path / "other"
    runner_temp = tmp_path / "runner_temp"
    shim_dir = tmp_path / "shims"
    sleep_log = tmp_path / "sleep.log"
    home = tmp_path / "home"
    for d in (runner_temp, shim_dir, home):
        d.mkdir()

    # `sleep` shim: record the requested delay, never actually wait.
    sleep_shim = shim_dir / "sleep"
    sleep_shim.write_text(f'#!/bin/sh\necho "$1" >> "{sleep_log}"\n')
    sleep_shim.chmod(sleep_shim.stat().st_mode | stat.S_IEXEC)

    script = tmp_path / "commit_step.sh"
    script.write_text(commit_script_text, encoding="utf-8")

    env = {
        "PATH": f"{shim_dir}{os.pathsep}{os.environ['PATH']}",
        "HOME": str(home),
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "RUNNER_TEMP": str(runner_temp),
        "LC_ALL": "C",
    }
    sb = Sandbox(tmp_path, remote, work, other, runner_temp, shim_dir, sleep_log, script, env)

    sb.git("init", "-q", "--bare", "-b", "main", str(remote), cwd=tmp_path)
    sb.git("init", "-q", "-b", "main", str(work), cwd=tmp_path)
    sb.git("config", "user.name", "Fixture", cwd=work)
    sb.git("config", "user.email", "fixture@example.invalid", cwd=work)
    sb.git("remote", "add", "origin", str(remote), cwd=work)
    sb.write_artifacts(_artifact_files(graph=OLD_GRAPH, report=OLD_REPORT, html=OLD_HTML))
    (work / "README.md").write_text("fixture\n", encoding="utf-8")
    sb.git("add", "-A", cwd=work)
    sb.git("commit", "-q", "-m", "initial: graph v1", cwd=work)
    sb.git("push", "-q", "origin", "HEAD:main", cwd=work)

    sb.git("clone", "-q", str(remote), str(other), cwd=tmp_path)
    sb.git("config", "user.name", "Racer", cwd=other)
    sb.git("config", "user.email", "racer@example.invalid", cwd=other)
    return sb


class TestCommitStepBehavior:
    """T-7: Execute the real workflow commit step against a temp bare remote."""

    def test_clean_commit_and_push_when_graph_changed(self, sandbox: Sandbox) -> None:
        sandbox.write_artifacts(_artifact_files(graph=_changed_graph(), report=_changed_report(), html=OLD_HTML + "v2\n"))
        initial = sandbox.remote_head()

        result = sandbox.run_step({"GH_TOKEN": "ghs_FIXTURE_SECRET_TOKEN"})

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Commit attempt 1/5" in result.stdout
        assert "Successfully pushed knowledge graph update." in result.stdout
        assert sandbox.remote_subjects() == [BOT_SUBJECT, "initial: graph v1"]
        changed = sandbox.git("diff", "--name-only", initial, "refs/heads/main", cwd=sandbox.remote).splitlines()
        assert sorted(changed) == sorted(f"graphify-out/{n}" for n in DURABLE_ARTIFACTS)
        assert {n["id"] for n in json.loads(sandbox.remote_file("graphify-out/graph.json"))["nodes"]} == {"a", "b"}
        assert sandbox.sleeps() == [], "no backoff on a first-attempt success"
        # Credentials must never be persisted into the repository config.
        assert "FIXTURE_SECRET" not in (sandbox.work / ".git" / "config").read_text()
        assert "FIXTURE_SECRET" not in result.stdout + result.stderr

    def test_non_fast_forward_race_recovers_by_resync_and_recommit(self, sandbox: Sandbox) -> None:
        sandbox.write_artifacts(_artifact_files(graph=_changed_graph(), report=_changed_report(), html=OLD_HTML + "v2\n"))
        sandbox.add_race_hook(files={})

        result = sandbox.run_step()

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Commit attempt 2/5" in result.stdout
        assert "Successfully pushed knowledge graph update." in result.stdout
        # Linear history: the racer's commit survived and the bot commit sits on top of it.
        assert sandbox.remote_subjects() == [
            BOT_SUBJECT,
            "feat: concurrent commit from another writer",
            "initial: graph v1",
        ]
        assert sandbox.remote_file("other.txt") == "racer"
        assert {n["id"] for n in json.loads(sandbox.remote_file("graphify-out/graph.json"))["nodes"]} == {"a", "b"}
        assert sandbox.remote_file("graphify-out/graph.html") == (OLD_HTML + "v2\n").strip()
        assert (sandbox.runner_temp / "graphify-artifacts" / "graph.json").is_file(), (
            "artifacts must be staged under $RUNNER_TEMP for restoration"
        )
        assert sandbox.sleeps() == ["2"], "exactly one backoff (i*2 = 2s) after the failed first push"

    def test_exhausted_retries_exit_nonzero_without_trailing_sleep(self, sandbox: Sandbox) -> None:
        sandbox.write_artifacts(_artifact_files(graph=_changed_graph(), report=_changed_report(), html=OLD_HTML + "v2\n"))
        attempts = sandbox.root / "push-attempts.log"
        sandbox.add_remote_hook("pre-receive", f'echo attempt >> "{attempts}"\necho "rejected by fixture" >&2\nexit 1\n')
        initial = sandbox.remote_head()

        result = sandbox.run_step()

        assert result.returncode == 1, result.stdout + result.stderr
        assert "Failed to push knowledge graph after 5 attempts." in result.stdout
        assert attempts.read_text().split() == ["attempt"] * 5, "exactly MAX_RETRIES=5 push attempts"
        assert "Commit attempt 5/5" in result.stdout and "Commit attempt 6" not in result.stdout
        # Backoff between attempts only: 2,4,6,8 -- never after the final failure.
        assert sandbox.sleeps() == ["2", "4", "6", "8"]
        assert sandbox.remote_head() == initial, "remote must be untouched when every push is rejected"

    def test_unchanged_graph_is_a_noop(self, sandbox: Sandbox) -> None:
        initial = sandbox.remote_head()
        local_head = sandbox.git("rev-parse", "HEAD")

        result = sandbox.run_step()

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Nothing to commit" in result.stdout
        assert sandbox.remote_head() == initial
        assert sandbox.git("rev-parse", "HEAD") == local_head
        assert sandbox.sleeps() == []
        assert "Commit attempt" not in result.stdout

    def test_volatile_only_changes_do_not_create_a_commit(self, sandbox: Sandbox) -> None:
        """built_at_commit, the report date, and the 'Built from commit' line alone must not cause a ~9 MB commit."""
        sandbox.write_artifacts(
            _artifact_files(graph=_volatile_only_graph(), report=_volatile_only_report(), html=OLD_HTML)
        )
        initial = sandbox.remote_head()
        local_head = sandbox.git("rev-parse", "HEAD")

        result = sandbox.run_step()

        assert result.returncode == 0, result.stdout + result.stderr
        assert "semantically unchanged" in result.stdout
        assert sandbox.remote_head() == initial
        assert sandbox.git("rev-parse", "HEAD") == local_head
        assert sandbox.remote_subjects() == ["initial: graph v1"]

    @pytest.mark.parametrize("which", ["graph.json", "GRAPH_REPORT.md", "graph.html"])
    def test_real_change_in_any_single_artifact_is_committed(self, sandbox: Sandbox, which: str) -> None:
        files = _artifact_files(graph=_volatile_only_graph(), report=_volatile_only_report(), html=OLD_HTML)
        if which == "graph.json":
            graph = _volatile_only_graph()
            graph["nodes"].append({"id": "zzz"})
            files["graph.json"] = json.dumps(graph, separators=(",", ":"))
        elif which == "GRAPH_REPORT.md":
            files["GRAPH_REPORT.md"] = _volatile_only_report().replace("- 1 nodes", "- 99 nodes")
        else:
            files["graph.html"] = OLD_HTML + "changed\n"
        sandbox.write_artifacts(files)

        result = sandbox.run_step()

        assert result.returncode == 0, result.stdout + result.stderr
        assert sandbox.remote_subjects() == [BOT_SUBJECT, "initial: graph v1"]

    def test_race_where_winner_already_pushed_same_graph_makes_no_duplicate_commit(self, sandbox: Sandbox) -> None:
        """After re-syncing, a graph that only differs in volatile fields from origin/main is not re-committed."""
        sandbox.write_artifacts(_artifact_files(graph=_changed_graph(), report=_changed_report(), html=OLD_HTML + "v2\n"))
        winner = _artifact_files(graph=_changed_graph(), report=_changed_report(), html=OLD_HTML + "v2\n")
        winner["graph.json"] = json.dumps({**_changed_graph(), "built_at_commit": "dddddddd"}, separators=(",", ":"))
        winner["GRAPH_REPORT.md"] = _changed_report().replace("(2026-02-02)", "(2026-02-03)")
        sandbox.write_artifacts(winner, repo=sandbox.other)
        sandbox.add_race_hook(files=winner)

        result = sandbox.run_step()

        assert result.returncode == 0, result.stdout + result.stderr
        assert "Commit attempt 2/5" in result.stdout
        assert "already matches" in result.stdout
        assert sandbox.remote_subjects() == [
            "feat: concurrent commit from another writer",
            "initial: graph v1",
        ], "no duplicate bot commit when origin/main already carries the same graph"
