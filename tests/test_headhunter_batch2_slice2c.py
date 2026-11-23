# BlackBoard/tests/test_headhunter_batch2_slice2c.py
# @ai-rules:
# 1. [Pattern]: 4-Layer Farley ATDD Specification for Batch 2 Slice 2C:
#    T-13 (Redis snapshot persistence), NO_GITHUB_CONTEXT + Brain gated github skill follow-up,
#    T-17 (darwin-github-ops skill, MR decoupling, rules 1:1 mirror, brain_skills, 07-headhunter.mdc),
#    T-18 (Helm CLI lint/template matrix), T-20 (static AST boundary, main.py LOC, verify=False, graphify).
# 2. [Constraint]: Zero live network or Redis; Helm tests require real `helm` CLI if installed.
"""
4-Layer Farley ATDD Executable Specification — Batch 2 Slice 2C
Covers T-13 (snapshot persistence), NO_GITHUB_CONTEXT follow-up, T-17, T-18, and T-20.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent


# =============================================================================
# Layer 3: Protocol Drivers (Redis Snapshot, Gate/Skill, Helm CLI, AST/FS)
# =============================================================================


class SnapshotPersistenceDriver:
    """Layer 3 Driver for Headhunter snapshot building and Redis TTL persistence."""

    def __init__(self) -> None:
        self.redis_set_calls: list[tuple[str, str, int | None]] = []

    def make_blackboard_with_mock_redis(self):
        from src.state.blackboard import BlackboardState

        bb = BlackboardState.__new__(BlackboardState)
        bb.redis = AsyncMock()

        async def _set(key: str, value: str, ex: int | None = None, **kwargs):
            self.redis_set_calls.append((key, value, ex))
            return True

        bb.redis.set = AsyncMock(side_effect=_set)
        bb.redis.get = AsyncMock(return_value=None)
        return bb


class HelmCliDriver:
    """Layer 3 Driver invoking real `helm` CLI for lint and template dry-runs."""

    def __init__(self, helm_bin: str) -> None:
        self.helm_bin = helm_bin
        self.chart_dir = REPO_ROOT / "helm"

    def lint(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.helm_bin, "lint", str(self.chart_dir)],
            capture_output=True,
            text=True,
            check=False,
        )

    def template(self, extra_args: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [self.helm_bin, "template", "test-rel", str(self.chart_dir), "--set", "gcp.project=test", *extra_args],
            capture_output=True,
            text=True,
            check=False,
        )


def _helm_bin_or_skip() -> str:
    helm_bin = shutil.which("helm")
    if not helm_bin:
        if os.getenv("CI", "").lower() == "true":
            pytest.fail("helm binary must be installed in CI for T-18")
        pytest.skip("helm binary not installed locally")
    return helm_bin


# =============================================================================
# T-13: VcsPlatformPort.get_platform_snapshot() & Redacted Redis Persistence
# =============================================================================


class TestATDDT13SnapshotPersistence:
    """Layer 1-4 ATDD scenarios for T-13 snapshot persistence."""

    def test_t13_port_and_adapters_expose_get_platform_snapshot(self):
        """Given VcsPlatformPort, GitLabPlatform, and GitHubPlatform
        When get_platform_snapshot() is inspected and invoked
        Then VcsPlatformPort declares it and both adapters return PlatformSnapshot."""
        from src.agents.headhunter_github import GitHubPlatform
        from src.agents.headhunter_gitlab import GitLabPlatform
        from src.agents.headhunter_models import PlatformSnapshot
        from src.agents.headhunter_port import VcsPlatformPort

        assert "get_platform_snapshot" in VcsPlatformPort.__protocol_attrs__ if hasattr(
            VcsPlatformPort, "__protocol_attrs__"
        ) else hasattr(VcsPlatformPort, "get_platform_snapshot")
        assert hasattr(VcsPlatformPort, "get_platform_snapshot")

        mock_bb = MagicMock()
        gl = GitLabPlatform(mock_bb, enabled=False)
        gh = GitHubPlatform(mock_bb)

        gl_snap = gl.get_platform_snapshot()
        gh_snap = gh.get_platform_snapshot()
        assert isinstance(gl_snap, PlatformSnapshot) and gl_snap.platform == "gitlab"
        assert isinstance(gh_snap, PlatformSnapshot) and gh_snap.platform == "github"

    @pytest.mark.asyncio
    async def test_t13_headhunter_persists_redacted_snapshots_with_3x_poll_ttl(self):
        """Given Headhunter with poll_interval=300 and a secret-bearing error string >200 chars
        When Headhunter persists platform snapshots at end of a poll cycle
        Then darwin:headhunter:snapshot:{platform} is written with ex=900 (3*poll_interval),
        secrets are redacted, and error strings are <=200 chars."""
        from src.agents.headhunter import Headhunter
        from src.agents.headhunter_models import PlatformBreakerStatus, PlatformSnapshot

        driver = SnapshotPersistenceDriver()
        bb = driver.make_blackboard_with_mock_redis()

        with patch.dict(os.environ, {"HEADHUNTER_POLL_INTERVAL": "300"}, clear=False):
            hh = Headhunter(bb, gitlab_enabled=False)

        secret_err = "HTTP 500 token=glpat-secretToken1234567890 Bearer eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.sig12345 " + ("Z" * 260)
        hh._breakers["gitlab"].state = "open"
        hh._breakers["gitlab"].consecutive_failures = 3
        hh._breakers["gitlab"].last_error = secret_err

        raw_snap = PlatformSnapshot(
            platform="gitlab",
            enabled=True,
            pending_count=1,
            queued_count=0,
            last_poll_at=1_700_000_000.0,
            partial_error=secret_err,
            breaker=PlatformBreakerStatus(state="open", consecutive_failures=3, last_error=secret_err),
            items=[],
        )
        hh._gitlab.get_platform_snapshot = MagicMock(return_value=raw_snap)
        hh._github.get_platform_snapshot = MagicMock(
            return_value=PlatformSnapshot(platform="github", enabled=False)
        )

        # Persist via Headhunter's snapshot persistence path (and verify Blackboard save_headhunter_snapshot)
        assert hasattr(bb, "save_headhunter_snapshot"), "BlackboardState missing save_headhunter_snapshot()"
        assert hasattr(bb, "get_headhunter_snapshot"), "BlackboardState missing get_headhunter_snapshot()"
        await hh._persist_platform_snapshot("gitlab")

        gl_writes = [c for c in driver.redis_set_calls if c[0] == "darwin:headhunter:snapshot:gitlab"]
        assert len(gl_writes) == 1
        key, payload_raw, ex_ttl = gl_writes[0]
        assert key == "darwin:headhunter:snapshot:gitlab"
        assert ex_ttl == 900
        assert "glpat-secretToken1234567890" not in payload_raw
        assert "eyJhbGciOiJIUzI1NiJ9" not in payload_raw
        payload = json.loads(payload_raw)
        assert len(payload.get("partial_error") or "") <= 200
        assert len((payload.get("breaker") or {}).get("last_error") or "") <= 200

    @pytest.mark.asyncio
    async def test_t13_adapters_populate_real_items_and_blackboard_snapshot_roundtrip_and_corrupt_recovery(self):
        """Given real pending/queued items on GitLabPlatform & GitHubPlatform
        When get_platform_snapshot(), save_headhunter_snapshot(), and get_headhunter_snapshot() run
        Then counts and items match accurately, Redis roundtrip succeeds, and corrupt JSON returns None."""
        from src.agents.headhunter_github import GitHubPlatform
        from src.agents.headhunter_gitlab import GitLabPlatform
        from src.agents.headhunter_models import PlatformQueueItem

        store: dict[str, str] = {}
        from src.state.blackboard import BlackboardState

        bb = BlackboardState.__new__(BlackboardState)
        bb.redis = AsyncMock()
        bb.redis.set = AsyncMock(side_effect=lambda k, v, ex=None: store.__setitem__(k, v) or True)
        bb.redis.get = AsyncMock(side_effect=lambda k: store.get(k))

        gl = GitLabPlatform(bb, enabled=False)
        gl._last_snapshot_items = [
            PlatformQueueItem(
                platform="gitlab", item_kind="mr", item_id=10, project_ref="g/r", status="queued", queue_position=1
            ),
            PlatformQueueItem(
                platform="gitlab", item_kind="mr", item_id=11, project_ref="g/r", status="pending"
            ),
        ]
        gl_snap = gl.get_platform_snapshot()
        assert gl_snap.pending_count == 2
        assert gl_snap.queued_count == 1
        assert [i.item_id for i in gl_snap.items] == [10, 11]

        gh = GitHubPlatform(bb)
        gh._last_queued_prs = [{"number": 7, "owner": "o", "repo": "r", "title": "Q PR", "user": "u"}]
        gh._last_queued_issues = [{"issue_number": 8, "owner": "o", "repo": "r", "issue_title": "Q Issue", "author": "u"}]
        gh._last_pending_prs = [{"number": 9, "owner": "o", "repo": "r", "title": "P PR", "user": "u"}]
        gh._last_pending_issues = []
        gh_snap = gh.get_platform_snapshot()
        assert gh_snap.pending_count == 3
        assert gh_snap.queued_count == 2
        assert {(i.item_kind, i.item_id, i.status) for i in gh_snap.items} == {
            ("pr", 7, "queued"),
            ("issue", 8, "queued"),
            ("pr", 9, "pending"),
        }

        await bb.save_headhunter_snapshot("github", gh_snap, ttl_seconds=600)
        loaded = await bb.get_headhunter_snapshot("github")
        assert isinstance(loaded, dict) and loaded["pending_count"] == 3 and loaded["queued_count"] == 2

        store["darwin:headhunter:snapshot:github"] = "{corrupt-json"
        assert await bb.get_headhunter_snapshot("github") is None

    @pytest.mark.asyncio
    async def test_t13_promote_gitlab_queue_watch_retry_and_request_promote_eviction(self):
        """Verify BlackboardState.promote_gitlab_queue retries WatchError and succeeds, and
        Headhunter.request_promote / _prioritize_promoted_items handle prioritization,
        consumed eviction, and FIFO cap eviction."""
        from redis.exceptions import WatchError
        from src.agents.headhunter import Headhunter, _PROMOTED_KEY_MAX_ENTRIES
        from src.state.blackboard import BlackboardState

        bb = BlackboardState.__new__(BlackboardState)
        pipe = AsyncMock()
        pipe.__aenter__ = AsyncMock(return_value=pipe)
        pipe.__aexit__ = AsyncMock(return_value=False)
        pipe.watch = AsyncMock()
        pipe.zrange = AsyncMock(return_value=[(b"100:5", 10.0)])
        pipe.hget = AsyncMock(return_value=json.dumps({"project_id": 100, "mr_iid": 42}).encode())
        pipe.multi = MagicMock()
        pipe.zadd = MagicMock()
        pipe.hset = MagicMock()
        pipe.execute = AsyncMock(side_effect=[WatchError("race"), [1, 1]])
        bb.redis = MagicMock()
        bb.redis.pipeline = MagicMock(return_value=pipe)

        ok = await bb.promote_gitlab_queue(100, 42, max_retries=3)
        assert ok is True
        assert pipe.execute.await_count == 2
        assert pipe.zadd.call_args.args[1]["100:42"] == 0.0  # min(0.0, 10.0 - 1.0)

        hh = Headhunter(MagicMock(), gitlab_enabled=False)
        for i in range(1, _PROMOTED_KEY_MAX_ENTRIES + 5):
            hh.request_promote("github", owner="o", repo="r", item_number=i)
        assert len(hh._promoted_keys) == _PROMOTED_KEY_MAX_ENTRIES
        assert ("github", "pr", "o/r", 1) not in hh._promoted_keys
        assert ("github", "pr", "o/r", _PROMOTED_KEY_MAX_ENTRIES + 4) in hh._promoted_keys

        items = [
            {"owner": "o", "repo": "r", "number": 1},
            {"owner": "o", "repo": "r", "number": _PROMOTED_KEY_MAX_ENTRIES + 4},
        ]
        ordered = hh._prioritize_promoted_items("github", items)
        assert ordered[0]["number"] == _PROMOTED_KEY_MAX_ENTRIES + 4
        hh._consume_promoted_key("github", ordered[0])
        assert ("github", "pr", "o/r", _PROMOTED_KEY_MAX_ENTRIES + 4) not in hh._promoted_keys

    @pytest.mark.asyncio
    async def test_t13_dismissed_keys_poll_skip_dismiss_todo_bool_and_run_platform_head_snapshot(self):
        """Verify _dismissed_keys skips in-flight poll items until TTL expiry, GitLabPlatform.dismiss_todo
        returns True on 2xx/404 and False on 500, and _run_platform_head persists snapshot on failure & open breaker."""
        import httpx
        from src.agents.headhunter import Headhunter
        from src.agents.headhunter_gitlab import GitLabPlatform
        from src.agents.headhunter_models import PlatformSnapshot

        driver = SnapshotPersistenceDriver()
        bb = driver.make_blackboard_with_mock_redis()

        # 1. GitLabPlatform.dismiss_todo real bool return (2xx / 404 -> True, 500 -> False)
        def _gl_handler(request: httpx.Request) -> httpx.Response:
            if request.url.path.endswith("/todos/10/mark_as_done"):
                return httpx.Response(200, json={"id": 10})
            if request.url.path.endswith("/todos/11/mark_as_done"):
                return httpx.Response(404, json={"message": "Not found"})
            return httpx.Response(500, json={"error": "boom"})

        gl_client = httpx.AsyncClient(transport=httpx.MockTransport(_gl_handler))
        with patch.dict(os.environ, {"GITLAB_HOST": "gitlab.example.com"}, clear=False):
            with patch("src.utils.vcs_approval.resolve_ca_bundle", return_value=True):
                gl = GitLabPlatform(bb, enabled=True)
        gl._get_token = MagicMock(return_value="gl-tok")
        gl._client = gl_client
        try:
            assert await gl.dismiss_todo(10) is True
            assert await gl.dismiss_todo(11) is True
            assert await gl.dismiss_todo(12) is False
        finally:
            await gl_client.aclose()

        # 2. _dismissed_keys poll-race skip + TTL expiry
        hh = Headhunter(bb, gitlab_enabled=False)
        item = {"owner": "o", "repo": "r", "number": 77}
        key = hh._item_key("github", item)
        hh._record_dismissed_key(key, ttl_s=300.0)
        assert hh._is_dismissed("github", item) is True
        hh._dismissed_keys[key] = 0.0  # expired monotonic timestamp
        assert hh._is_dismissed("github", item) is False

        # 3. _run_platform_head persists snapshot on poll failure and when breaker is open
        hh._github.get_platform_snapshot = MagicMock(
            return_value=PlatformSnapshot(platform="github", enabled=True)
        )
        await hh._run_platform_head(
            "github", "GitHub", True, AsyncMock(side_effect=RuntimeError("boom glpat-secret123456"))
        )
        assert any(c[0] == "darwin:headhunter:snapshot:github" for c in driver.redis_set_calls)

        driver.redis_set_calls.clear()
        hh._breakers["github"].state = "open"
        hh._breakers["github"].next_retry_at = 9e12
        hh._breakers["github"]._open_until_mono = 9e12
        hh._breakers["github"].last_error = "open breaker err"
        await hh._run_platform_head("github", "GitHub", True, AsyncMock())
        gh_writes = [c for c in driver.redis_set_calls if c[0] == "darwin:headhunter:snapshot:github"]
        assert len(gh_writes) == 1
        assert json.loads(gh_writes[0][1])["breaker"]["state"] == "open"


# =============================================================================
# Follow-up: NO_GITHUB_CONTEXT Gate & Brain Gated "github" Skill Injection
# =============================================================================


class TestIssueContextGateAndSkillFollowup:
    """Verify github_issue_context activates refresh_github_context gate and gated github skill."""

    def test_evaluate_gates_permits_refresh_github_context_for_github_issue_context_only(self):
        """Given an EventDocument with ONLY github_issue_context set (github_context=None)
        When evaluate_gates() runs in triage phase
        Then refresh_github_context is NOT stripped by NO_GITHUB_CONTEXT."""
        from src.agents.tool_gates import build_gate_context, evaluate_gates
        from src.models import EventDocument, EventEvidence, EventInput

        event = EventDocument(
            id="evt-gh-issue-gate",
            source="headhunter",
            service="BlackBoard",
            brain_phase="triage",
            event=EventInput(
                reason="triage issue",
                evidence=EventEvidence(
                    display_text="Issue #233",
                    source_type="headhunter",
                    domain="complicated",
                    severity="info",
                    github_issue_context={
                        "owner": "The-Darwin-Project",
                        "repo": "BlackBoard",
                        "issue_number": 233,
                        "title": "Test issue",
                    },
                ),
            ),
        )
        ctx = build_gate_context(event, "triage", {"brain_has_classified": True}, is_defer_wake=False, iteration=0)
        assert ctx.has_github_context is True
        surviving = evaluate_gates(
            [{"name": "refresh_github_context"}, {"name": "classify_event"}],
            ctx,
        )
        assert any(t["name"] == "refresh_github_context" for t in surviving)

    @pytest.mark.asyncio
    async def test_brain_injects_gated_github_skill_for_github_issue_context_only(self):
        """Given an EventDocument with ONLY github_issue_context set (github_context=None)
        When Brain._build_system_prompt() assembles gated evidence skills
        Then the gated 'github' skill (github-environment.md) is injected."""
        from src.agents.brain import Brain
        from src.agents.brain_skill_loader import BrainSkillLoader
        from src.models import EventDocument, EventEvidence, EventInput

        loader = BrainSkillLoader(str(REPO_ROOT / "src" / "agents" / "brain_skills"))

        brain = Brain.__new__(Brain)
        brain._skill_loader = loader
        brain._recall_lessons = {}
        brain._build_event_state_header = MagicMock(return_value="[EVENT STATE HEADER]")

        event = EventDocument(
            id="evt-gh-issue-skill",
            source="headhunter",
            service="BlackBoard",
            brain_phase="triage",
            event=EventInput(
                reason="triage issue",
                evidence=EventEvidence(
                    display_text="Issue #233",
                    source_type="headhunter",
                    domain="complicated",
                    severity="info",
                    github_issue_context={
                        "owner": "The-Darwin-Project",
                        "repo": "BlackBoard",
                        "issue_number": 233,
                        "title": "Test issue",
                    },
                ),
            ),
        )
        prompt = await brain._build_system_prompt(event, ["always", "triage"], context_flags={}, graph_recall=None)
        assert "github-environment" in prompt or "refresh_github_context" in prompt


# =============================================================================
# T-17: Sidecar darwin-github-ops, MR Decoupling, Rules 1:1 Mirror & Docs Sync
# =============================================================================


class TestATDDT17SidecarSkillsAndRuleParity:
    """Layer 1-4 ATDD scenarios for T-17."""

    def test_t17a_darwin_github_ops_skill_exists_and_covers_required_operations(self):
        """Given gemini-sidecar/skills/darwin-github-ops/SKILL.md
        When inspected
        Then it covers token map, MCP server, GraphQL auto-merge, reply endpoint, check-runs, and Prow ban."""
        skill_path = REPO_ROOT / "gemini-sidecar" / "skills" / "darwin-github-ops" / "SKILL.md"
        assert skill_path.is_file(), f"Missing {skill_path}"
        text = skill_path.read_text()
        for required in (
            "/tmp/gh-token-map.json",
            "github-mcp-server",
            "autoMergeRequest",
            "disablePullRequestAutoMerge",
            "/pulls/",
            "/comments/",
            "/replies",
            "check-runs",
            "/lgtm",
            "/approve",
        ):
            assert required in text, f"darwin-github-ops/SKILL.md missing {required!r}"

    @pytest.mark.parametrize(
        "skill_name",
        [
            "darwin-mr-lifecycle",
            "darwin-mr-triage",
            "darwin-mr-conversation",
            "darwin-pipeline-debug",
            "darwin-pipelines-as-code",
            "darwin-investigate",
        ],
    )
    def test_t17b_six_sidecar_skills_decoupled_from_gitlab_only_requirement(self, skill_name: str):
        """Given the 6 MR/pipeline/investigation sidecar skills
        When frontmatter and body are parsed
        Then requires does NOT force darwin-gitlab-ops and body handles both gitlab_context and github_context."""
        skill_path = REPO_ROOT / "gemini-sidecar" / "skills" / skill_name / "SKILL.md"
        text = skill_path.read_text()
        fm_match = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
        assert fm_match, f"{skill_path} missing YAML frontmatter"
        meta = yaml.safe_load(fm_match.group(1))
        requires = meta.get("requires") or []
        assert "darwin-gitlab-ops" not in requires, (
            f"{skill_name}/SKILL.md still requires GitLab-only darwin-gitlab-ops: {requires}"
        )
        assert "gitlab_context" in text and "github_context" in text, (
            f"{skill_name}/SKILL.md must branch cleanly on gitlab_context vs github_context"
        )

    @pytest.mark.parametrize("role_name", ["architect", "code_reviewer", "developer", "sysadmin"])
    def test_t17c_four_rules_reference_darwin_github_ops_and_match_helm_files_byte_for_byte(self, role_name: str):
        """Given gemini-sidecar/rules/{role}.md and helm/files/{role}.md
        When compared
        Then both reference darwin-github-ops alongside darwin-gitlab-ops and match byte-for-byte."""
        sidecar_rule = REPO_ROOT / "gemini-sidecar" / "rules" / f"{role_name}.md"
        helm_rule = REPO_ROOT / "helm" / "files" / f"{role_name}.md"
        assert sidecar_rule.is_file() and helm_rule.is_file()
        text = sidecar_rule.read_text()
        assert "darwin-github-ops" in text, f"{sidecar_rule} missing darwin-github-ops"
        assert "darwin-gitlab-ops" in text, f"{sidecar_rule} missing darwin-gitlab-ops"
        assert sidecar_rule.read_bytes() == helm_rule.read_bytes(), (
            f"{sidecar_rule} and {helm_rule} drifted"
        )

    def test_t17d_brain_skill_and_cursor_rule_reflect_batch2_parity(self):
        """Given src/agents/brain_skills/source/headhunter.md and .cursor/rules/07-headhunter.mdc
        When inspected
        Then brain skill reflects GitLab + GitHub parity and 07-headhunter.mdc reflects 7 fence tags,
        three-phase post_feedback, and Redis FIFO/mr_sha/wake-up."""
        hh_skill = (REPO_ROOT / "src" / "agents" / "brain_skills" / "source" / "headhunter.md").read_text()
        assert "structured GitLab or GitHub context" in hh_skill or (
            "GitLab and GitHub" in hh_skill and "structured GitLab context in the evidence" not in hh_skill
        )

        cursor_rule = (REPO_ROOT / ".cursor" / "rules" / "07-headhunter.mdc").read_text()
        assert "pr_review_comments" in cursor_rule
        assert "darwin:gitlab:mr_sha" in cursor_rule
        assert "darwin:gitlab:queue" in cursor_rule
        assert "post_feedback" in cursor_rule and ("three-phase" in cursor_rule.lower() or "3-phase" in cursor_rule.lower())
        assert "smartsheet" not in cursor_rule.lower()


# =============================================================================
# T-18: Helm CLI Lint, Fail-Fast Guards, Env Parity & Sprig Zero Guards
# =============================================================================


class TestATDDT18HelmParity:
    """Layer 1-4 ATDD scenarios for T-18 using real `helm` CLI."""

    def test_t18a_helm_lint_passes(self):
        """Given BlackBoard/helm chart
        When `helm lint helm/` runs
        Then exit code is 0."""
        driver = HelmCliDriver(_helm_bin_or_skip())
        proc = driver.lint()
        assert proc.returncode == 0, f"helm lint failed:\n{proc.stdout}\n{proc.stderr}"

    def test_t18b_github_enabled_without_existing_secret_fails_fast(self):
        """Given headhunter.github.enabled=true and empty github.existingSecret
        When `helm template` renders
        Then rendering fails fast with non-zero exit code."""
        driver = HelmCliDriver(_helm_bin_or_skip())
        proc = driver.template(["--set", "headhunter.github.enabled=true"])
        assert proc.returncode != 0, "Expected helm template to fail when headhunter.github.enabled=true without github.existingSecret"

    @pytest.mark.parametrize("bad_ssl", ["false", "0", "no", "off", "  false  "])
    def test_t18c_gitlab_ssl_verify_disabling_fails_fast_at_template_time(self, bad_ssl: str):
        """Given gitlab.enabled=true, gitlab.existingSecret=gl, and gitlab.sslVerify=false/0/no/off/padded
        When `helm template` renders
        Then rendering fails fast at template time."""
        driver = HelmCliDriver(_helm_bin_or_skip())
        proc = driver.template([
            "--set", "gitlab.enabled=true",
            "--set", "gitlab.existingSecret=gl",
            "--set-string", f"gitlab.sslVerify={bad_ssl}",
        ])
        assert proc.returncode != 0, f"Expected helm template fail-fast for gitlab.sslVerify={bad_ssl!r}"

    def test_t18c_string_false_github_enabled_does_not_trigger_secret_fail_fast(self):
        """Given headhunter.github.enabled='false' (string) and empty github.existingSecret
        When `helm template` renders
        Then secret-github.yaml does NOT fail fast."""
        driver = HelmCliDriver(_helm_bin_or_skip())
        proc = driver.template(["--set-string", "headhunter.github.enabled=false"])
        assert proc.returncode == 0, f"Unexpected fail-fast for string 'false': {proc.stderr}"

    def test_t18d_gitlab_only_cortex_url_fallback_env_parity_and_dead_vars_removed(self):
        """Given GitLab-only config with headhunter.github.cortexUrl fallback and GitHub-enabled config
        When `helm template` renders
        Then DARWIN_CORTEX_URL renders on GitLab-only, empty GITLAB_SSL_VERIFY & dead vars are omitted,
        new parity env vars render, and triggerReasons defaults to 'review_feedback,mention'."""
        driver = HelmCliDriver(_helm_bin_or_skip())
        proc_gl = driver.template([
            "--set", "gitlab.enabled=true",
            "--set", "gitlab.existingSecret=gl",
            "--set", "headhunter.github.cortexUrl=https://cortex.example.com",
        ])
        assert proc_gl.returncode == 0, proc_gl.stderr
        docs_gl = [d for d in yaml.safe_load_all(proc_gl.stdout) if d]
        dep_gl = next(d for d in docs_gl if d.get("kind") == "Deployment")
        env_gl = {e["name"]: e for e in dep_gl["spec"]["template"]["spec"]["containers"][0]["env"]}

        assert env_gl["DARWIN_CORTEX_URL"]["value"] == "https://cortex.example.com"
        assert "GITLAB_SSL_VERIFY" not in env_gl
        assert "HEADHUNTER_GITHUB_POLL_INTERVAL" not in env_gl
        assert "HEADHUNTER_MAINTAINER_SOURCE" not in env_gl
        for expected_var in (
            "GITLAB_BOT_USERNAME",
            "HEADHUNTER_ALLOWED_AUTHORS",
            "HEADHUNTER_DESCRIPTION_CAP",
            "GITHUB_APP_SLUG",
            "HEADHUNTER_GITLAB_QUEUE_MAX_ENTRIES",
            "HEADHUNTER_GITLAB_SHA_MAX_ENTRIES",
        ):
            assert expected_var in env_gl, f"Missing env var {expected_var} in Deployment template"

        proc_gh = driver.template([
            "--set", "headhunter.github.enabled=true",
            "--set", "github.existingSecret=gh",
        ])
        assert proc_gh.returncode == 0, proc_gh.stderr
        docs_gh = [d for d in yaml.safe_load_all(proc_gh.stdout) if d]
        dep_gh = next(d for d in docs_gh if d.get("kind") == "Deployment")
        env_gh = {e["name"]: e for e in dep_gh["spec"]["template"]["spec"]["containers"][0]["env"]}
        assert env_gh["HEADHUNTER_GITHUB_TRIGGER_REASONS"]["value"] == "review_feedback,mention"

    def test_t18e_explicit_zero_numeric_values_survive_sprig_default_traps(self):
        """Given explicit 0 on timekeeper.chatStaleTtl, nightwatcher.batchTimeoutSeconds,
        slackAccess.syncIntervalSeconds, ephemeralAgents.cleanup.keep, and keepSince
        When `helm template` renders
        Then '0' / 0 is preserved instead of falling back to Sprig defaults."""
        driver = HelmCliDriver(_helm_bin_or_skip())

        # Render with global.namespace=test-ns -> checks Deployment + Namespace
        proc_ns = driver.template([
            "--set", "global.namespace=test-ns",
            "--set", "timekeeper.chatStaleTtl=0",
            "--set", "nightwatcher.batchTimeoutSeconds=0",
            "--set", "slackAccess.enabled=true",
            "--set", "slackAccess.syncIntervalSeconds=0",
            "--set", "ephemeralAgents.enabled=true",
            "--set", "ephemeralAgents.cleanup.strategy=keep-since",
            "--set", "ephemeralAgents.cleanup.keepSince=0",
        ])
        assert proc_ns.returncode == 0, proc_ns.stderr
        docs_ns = [d for d in yaml.safe_load_all(proc_ns.stdout) if d]
        dep = next(d for d in docs_ns if d.get("kind") == "Deployment")
        env = {e["name"]: e for e in dep["spec"]["template"]["spec"]["containers"][0]["env"]}
        assert env["CHAT_STALE_TTL"]["value"] == "0"
        assert env["NIGHTWATCHER_BATCH_TIMEOUT_SECONDS"]["value"] == "0"
        assert env["SLACK_ACCESS_SYNC_INTERVAL"]["value"] == "0"

        ns = next(d for d in docs_ns if d.get("kind") == "Namespace")
        assert ns["metadata"]["annotations"]["operator.tekton.dev/prune.keep-since"] == "0"

        # Render with keep strategy + global.namespace=test-ns
        proc_keep = driver.template([
            "--set", "global.namespace=test-ns",
            "--set", "ephemeralAgents.enabled=true",
            "--set", "ephemeralAgents.cleanup.strategy=keep",
            "--set", "ephemeralAgents.cleanup.keep=0",
        ])
        assert proc_keep.returncode == 0, proc_keep.stderr
        ns_keep = next(
            d for d in yaml.safe_load_all(proc_keep.stdout) if d and d.get("kind") == "Namespace"
        )
        assert ns_keep["metadata"]["annotations"]["operator.tekton.dev/prune.keep"] == "0"

        # Render without global.namespace -> checks tekton-pruner-config.yaml
        proc_pruner_since = driver.template([
            "--set", "ephemeralAgents.enabled=true",
            "--set", "ephemeralAgents.cleanup.strategy=keep-since",
            "--set", "ephemeralAgents.cleanup.keepSince=0",
        ])
        assert proc_pruner_since.returncode == 0, proc_pruner_since.stderr
        cm_since = next(
            d
            for d in yaml.safe_load_all(proc_pruner_since.stdout)
            if d and d.get("kind") == "ConfigMap" and d["metadata"]["name"] == "tekton-pruner-namespace-spec"
        )
        assert "ttlSecondsAfterFinished: 0" in cm_since["data"]["ns-config"]

        proc_pruner_keep = driver.template([
            "--set", "ephemeralAgents.enabled=true",
            "--set", "ephemeralAgents.cleanup.strategy=keep",
            "--set", "ephemeralAgents.cleanup.keep=0",
        ])
        assert proc_pruner_keep.returncode == 0, proc_pruner_keep.stderr
        cm_keep = next(
            d
            for d in yaml.safe_load_all(proc_pruner_keep.stdout)
            if d and d.get("kind") == "ConfigMap" and d["metadata"]["name"] == "tekton-pruner-namespace-spec"
        )
        assert "historyLimit: 0" in cm_keep["data"]["ns-config"]


# =============================================================================
# T-20: Static Boundary, Security, LOC & Graphify Corpus Fitness Gates
# =============================================================================


class TestATDDT20BoundariesAndCorpusFitness:
    """Layer 1-4 ATDD fitness scenarios for T-20."""

    def test_t20a_main_py_under_1000_lines(self):
        """src/main.py must remain strictly under 1,000 lines."""
        line_count = len((REPO_ROOT / "src" / "main.py").read_text().splitlines())
        assert line_count < 1000, f"src/main.py exceeded 1000 lines ({line_count})"

    def test_t20b_static_ast_hexagonal_and_stdlib_boundaries(self):
        """Verify src/utils/, headhunter_utils.py, headhunter_models.py, and headhunter_port.py AST imports."""
        utils_dir = REPO_ROOT / "src" / "utils"
        forbidden_prefixes = ("src.agents", "src.state", "src.routes", "src.auth")
        for py_file in sorted(utils_dir.glob("*.py")):
            tree = ast.parse(py_file.read_text(), filename=str(py_file))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        assert not alias.name.startswith(forbidden_prefixes), (
                            f"{py_file} imports forbidden module {alias.name}"
                        )
                elif isinstance(node, ast.ImportFrom):
                    mod = node.module or ""
                    assert not mod.startswith(forbidden_prefixes), (
                        f"{py_file} imports forbidden module {mod}"
                    )
                    if node.level >= 2:
                        assert not any(
                            p in mod for p in ("agents", "state", "routes", "auth")
                        ), f"{py_file} relative-imports forbidden package {mod}"

        # headhunter_utils.py: zero-import (__future__, os, re only)
        hh_utils_tree = ast.parse((REPO_ROOT / "src" / "agents" / "headhunter_utils.py").read_text())
        for node in ast.walk(hh_utils_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in ("os", "re"), f"headhunter_utils.py unexpected import {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0 and node.module in ("__future__", "os", "re"), (
                    f"headhunter_utils.py unexpected import-from {node.module}"
                )

        # headhunter_models.py & headhunter_port.py: stdlib + typing (+ .headhunter_models / TYPE_CHECKING ..models on port)
        stdlib_allowed = {"__future__", "dataclasses", "re", "time", "typing", "collections.abc"}
        models_tree = ast.parse((REPO_ROOT / "src" / "agents" / "headhunter_models.py").read_text())
        for node in ast.walk(models_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in stdlib_allowed, f"headhunter_models.py non-stdlib import {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                assert node.level == 0 and node.module in stdlib_allowed, (
                    f"headhunter_models.py non-stdlib import-from {node.module}"
                )

        port_tree = ast.parse((REPO_ROOT / "src" / "agents" / "headhunter_port.py").read_text())
        for node in ast.walk(port_tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name in stdlib_allowed, f"headhunter_port.py non-stdlib import {alias.name}"
            elif isinstance(node, ast.ImportFrom):
                if node.level == 1 and node.module == "headhunter_models":
                    continue
                if node.level == 2 and node.module == "models":
                    continue
                assert node.level == 0 and node.module in stdlib_allowed, (
                    f"headhunter_port.py unexpected import-from level={node.level} mod={node.module}"
                )

    def test_t20c_zero_verify_false_in_vcs_modules(self):
        """Zero verify=False keyword arguments allowed in VCS HTTP modules (AST check)."""
        targets = [
            REPO_ROOT / "src" / "utils" / "tls.py",
            REPO_ROOT / "src" / "utils" / "vcs_approval.py",
            REPO_ROOT / "src" / "utils" / "github_app.py",
            REPO_ROOT / "src" / "routes" / "queue.py",
            REPO_ROOT / "src" / "agents" / "headhunter.py",
            REPO_ROOT / "src" / "agents" / "headhunter_gitlab.py",
            REPO_ROOT / "src" / "agents" / "headhunter_github.py",
            REPO_ROOT / "src" / "agents" / "headhunter_models.py",
            REPO_ROOT / "src" / "agents" / "headhunter_port.py",
            REPO_ROOT / "src" / "agents" / "headhunter_utils.py",
        ]
        for path in targets:
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    for kw in node.keywords:
                        if kw.arg == "verify" and isinstance(kw.value, ast.Constant) and kw.value.value is False:
                            pytest.fail(f"Insecure verify=False call found in {path}:{node.lineno}")

    def test_t20d_graphify_corpus_within_500_files_and_500k_words(self):
        """graphify.detect keeps total_files <= 500, total_words < 500_000, and no Large corpus warning."""
        if importlib.util.find_spec("graphify") is None:
            if os.getenv("CI", "").lower() == "true":
                pytest.fail("graphifyy runtime must be installed in CI")
            pytest.skip("graphify runtime not installed locally")

        from graphify.detect import detect

        scan = detect(REPO_ROOT)
        assert scan["total_files"] <= 500, f"graphify total_files={scan['total_files']} > 500"
        assert scan["total_words"] < 500_000, f"graphify total_words={scan['total_words']} >= 500000"
        warning = scan.get("warning") or ""
        assert "Large corpus" not in warning, f"graphify Large corpus warning triggered: {warning}"
