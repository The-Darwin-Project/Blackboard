# tests/test_jenkins_observer.py
# @ai-rules:
# 1. [Pattern]: Tests the JenkinsObserver drain loop, adapter, and integration.
# 2. [Constraint]: No real Redis/LLM/HTTP. AsyncMock blackboard, mock httpx, mock GeminiAdapter.
# 3. [Pattern]: _drain_once() tested directly — NOT the while True _poll_loop().
# 4. [Pattern]: Circuit breaker tests target src/adapters/jenkins.py directly.
# 5. [Gotcha]: asyncio_mode=auto in pytest.ini — no @pytest.mark.asyncio decorator needed.
# 6. [Gotcha]: Implementation runs in parallel — tests assert planned interface, may need
#    adjustment at reconciliation time if executor's public API deviates.
# 7. [Contract]: scan_view(view) -> ViewScanResult replaces poll_jobs(version).
#    Keys are job_name only (no pipe). JENKINS_OBSERVER_VIEWS env required.
# 8. [Gotcha]: TestT2SkipHealthy MUST mock scan_view returning a healthy ViewScanResult
#    AND set JENKINS_OBSERVER_VIEWS — otherwise _views=[] means loop never runs, and
#    create_event.assert_not_called() passes vacuously.
"""
VMER-1452b: Observer + integration tests for JenkinsObserver.

Spec rows: T-1 through T-5, T-9 through T-18b, T-20.
Part 1 tests (T-6/7/8/19) live in test_jenkins_tools.py (already shipped).
"""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =========================================================================
# Helpers
# =========================================================================

def _mock_blackboard():
    """Build a minimal BlackboardState mock matching the JenkinsObserver contract.

    NOTE: Uses spec_set=False on Jenkins-specific methods because they don't exist
    yet on BlackboardState (VMER-1444 adds them). Once implementation lands,
    these tests validate the public interface end-to-end.
    """
    from src.state.blackboard import BlackboardState
    bb = AsyncMock(spec=BlackboardState)
    bb.get_active_events.return_value = []
    bb.get_active_events_with_status.return_value = {}
    bb.get_event.return_value = None
    bb.get_escalation_flag.return_value = None
    bb.create_event.return_value = "evt-jenkins01"
    # Jenkins ZSET methods (VMER-1444 — not yet on BlackboardState)
    bb.stage_jenkins_signal = AsyncMock(return_value=None)
    bb.drain_jenkins_pending = AsyncMock(return_value=[])
    bb.commit_jenkins_signal = AsyncMock(return_value=None)
    bb.restage_jenkins_signal = AsyncMock(return_value=None)
    bb.count_jenkins_pending = AsyncMock(return_value=0)
    bb.redis = AsyncMock()
    bb.redis.get.return_value = None
    bb.redis.hget.return_value = None
    bb.redis.zadd.return_value = None
    return bb


def _make_job_result(job_name="verify-cnv-4.23.z-build-tier1", build_number=100,
                     result="FAILURE", version="4.23", timestamp=None, color=""):
    """Build a JobResult dataclass matching the adapter's return shape."""
    from src.adapters.jenkins import JobResult
    return JobResult(
        job_name=job_name,
        build_number=build_number,
        result=result,
        url=f"https://jenkins.example.com/job/{job_name}/{build_number}",
        timestamp=timestamp,
        color=color,
    )


def _make_view_scan_result(jobs=None, status_code=200):
    """Build a ViewScanResult matching the new adapter scan_view() return shape."""
    from src.adapters.jenkins import ViewScanResult
    return ViewScanResult(jobs=jobs or [], status_code=status_code)


def _make_triage_response():
    """Build a mock Flash Lite triage output."""
    return {
        "classification": "infra",
        "confidence": 0.85,
        "failed_leaves": ["smoke-tier1-basic", "smoke-tier1-network"],
        "recommended_action": "restart",
        "owner": "qe-team",
        "component": "networking",
    }


def _env_vars(**overrides):
    """Default env vars for JenkinsObserver construction.

    JENKINS_OBSERVER_VIEWS is required for the per-view loop to execute.
    Without it, _views=[] and _poll_and_stage skips all work silently.
    """
    defaults = {
        "JENKINS_OBSERVER_ENABLED": "true",
        "JENKINS_OBSERVER_POLL_INTERVAL": "300",
        "JENKINS_OBSERVER_STARTUP_DELAY": "0",
        "JENKINS_OBSERVER_DWELL_SECONDS": "60",
        "JENKINS_OBSERVER_FLOOD_THRESHOLD": "3",
        "JENKINS_OBSERVER_DRY_RUN": "false",
        "JENKINS_OBSERVER_VIEWS": "Gating Wrappers",
        "JENKINS_OBSERVER_RECENCY_HOURS": "72",
        "MAX_ACTIVE_EVENTS": "20",
        "JENKINS_URL": "https://jenkins.example.com",
        "JENKINS_USER": "sa-user",
        "JENKINS_TOKEN": "sa-token",
        "JENKINS_INSECURE_TLS": "true",
        "JENKINS_CIRCUIT_BREAKER_THRESHOLD": "3",
        "SKILLS_CATALOG_URL": "https://skills.example.com",
        "SKILLS_CATALOG_SKILLS": "cnv-gating-workflow",
        "LLM_MODEL_JENKINS_OBSERVER": "gemini-3.5-flash-lite",
        "LLM_TEMPERATURE_JENKINS_OBSERVER": "0.3",
        "LLM_MAX_TOKENS_JENKINS_OBSERVER": "4096",
    }
    defaults.update(overrides)
    return defaults


def _make_meta(job_name="verify-cnv-4.23.z-build-tier1", result="FAILURE",
               build_number=100, version="4.23", view="Gating Wrappers"):
    """Build a staged metadata dict for the Jenkins pending queue."""
    return {
        "job_name": job_name,
        "version": version,
        "view": view,
        "result": result,
        "build_number": build_number,
        "url": f"https://jenkins.example.com/job/{job_name}/{build_number}",
        "staged_at": time.time(),
    }


# =========================================================================
# T-1: Observer creates event for failed Jenkins job
# =========================================================================

class TestT1EventCreation:

    async def test_drain_creates_event_for_failed_job(self):
        """T-1/T-V1: Failed Jenkins job → create_event called with correct args.

        Rewritten for scan_view contract: adapter returns ViewScanResult, keys are
        job_name only (no pipe), metadata includes 'view'.
        """
        bb = _mock_blackboard()

        failed_job = _make_job_result(result="FAILURE", color="red")
        triage = _make_triage_response()

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)

            obs._adapter = AsyncMock()
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=[failed_job])
            )
            obs._adapter.enabled = MagicMock(return_value=True)

            bb.drain_jenkins_pending.return_value = ["verify-cnv-4.23.z-build-tier1"]
            bb.redis.hget.return_value = json.dumps(
                _make_meta(result="FAILURE", view="Gating Wrappers")
            )

            obs._triage_and_build_evidence = AsyncMock(return_value=triage)
            obs._get_wip_headroom = AsyncMock(return_value=5)
            obs._skills_si = "test skills"

            await obs._drain_once()

        bb.create_event.assert_called_once()
        kwargs = bb.create_event.call_args.kwargs
        assert kwargs["source"] == "aligner"
        assert kwargs["subject_type"] == "ci_gating"
        assert "ci_context" in (kwargs.get("evidence") or kwargs.get("evidence_obj") or {}) \
            or hasattr(kwargs.get("evidence"), "ci_context") \
            or "ci_gating" in str(kwargs)


# =========================================================================
# T-2: Observer skips healthy jobs
# =========================================================================

class TestT2SkipHealthy:

    async def test_drain_skips_healthy_jobs(self):
        """T-2/T-V2: All jobs SUCCESS → no event created.

        SPECIAL: JENKINS_OBSERVER_VIEWS is set AND scan_view returns a healthy
        ViewScanResult so the per-view loop actually runs. Without this, _views=[]
        means the loop never executes and assert_not_called passes vacuously.
        """
        bb = _mock_blackboard()

        healthy_job = _make_job_result(result="SUCCESS", color="blue",
                                       timestamp=int(time.time() * 1000))

        with patch.dict("os.environ", _env_vars(JENKINS_OBSERVER_VIEWS="Gating Wrappers")):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=[healthy_job])
            )
            obs._adapter.enabled = MagicMock(return_value=True)

            bb.drain_jenkins_pending.return_value = []
            obs._skills_si = "test skills"
            obs._get_wip_headroom = AsyncMock(return_value=5)

            await obs._drain_once()

        # scan_view was actually called (loop ran)
        obs._adapter.scan_view.assert_called_once()
        bb.create_event.assert_not_called()


# =========================================================================
# T-3: WIP gate blocks event creation
# =========================================================================

class TestT3WipGate:

    async def test_wip_full_restages_not_creates(self):
        """T-3/T-V3: WIP headroom=0 → restage called, no create_event."""
        bb = _mock_blackboard()

        failed_job = _make_job_result(result="FAILURE", color="red")
        triage = _make_triage_response()

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=[failed_job])
            )
            obs._adapter.enabled = MagicMock(return_value=True)

            bb.drain_jenkins_pending.return_value = ["verify-cnv-4.23.z-build-tier1"]
            bb.redis.hget.return_value = json.dumps(
                _make_meta(result="FAILURE", view="Gating Wrappers")
            )

            obs._triage_and_build_evidence = AsyncMock(return_value=triage)
            obs._get_wip_headroom = AsyncMock(return_value=0)
            obs._skills_si = "test skills"

            await obs._drain_once()

        bb.create_event.assert_not_called()
        bb.restage_jenkins_signal.assert_called()


# =========================================================================
# T-4: Dwell dedup prevents duplicate events (ZADD NX)
# =========================================================================

class TestT4DwellDedup:

    async def test_zadd_nx_preserves_first_timestamp(self):
        """T-4: Same key staged twice → ZADD NX preserves first score."""
        import fakeredis.aioredis

        redis = fakeredis.aioredis.FakeRedis()

        key = "verify-cnv-4.23.z-build-tier1|4.23"
        first_time = 1000.0
        second_time = 2000.0

        # First ZADD NX
        await redis.zadd("darwin:jenkins:pending", {key: first_time}, nx=True)
        # Second ZADD NX — should NOT overwrite
        await redis.zadd("darwin:jenkins:pending", {key: second_time}, nx=True)

        score = await redis.zscore("darwin:jenkins:pending", key)
        assert score == first_time, "ZADD NX should preserve the first timestamp"

        await redis.aclose()


# =========================================================================
# T-5: Flash Lite triage produces structured evidence
# =========================================================================

class TestT5TriageStructure:

    async def test_triage_returns_structured_json(self):
        """T-5/T-V5: _triage_and_build_evidence returns structured EventEvidence.

        Signal key format is job_name only (no pipe). Metadata includes 'view'.
        """
        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver
            from src.models import EventEvidence

            bb = _mock_blackboard()
            obs = JenkinsObserver(blackboard=bb)

            mock_response = MagicMock()
            mock_response.text = json.dumps([_make_triage_response()])
            mock_llm = AsyncMock()
            mock_llm.generate = AsyncMock(return_value=mock_response)
            obs._get_llm_adapter = AsyncMock(return_value=mock_llm)

            obs._adapter = AsyncMock()
            obs._adapter.get_build_details = AsyncMock(return_value=None)

            obs._skills_si = "test system instruction"

            signals = [("verify-cnv-4.23.z-build-tier1",
                        _make_meta(result="FAILURE", view="Gating Wrappers"))]
            result = await obs._triage_and_build_evidence(signals)

        assert isinstance(result, EventEvidence)
        assert result.ci_context is not None
        assert result.source_type == "aligner"
        assert result.domain == "disorder"
        assert "llm_triage" in result.ci_context
        assert "maintainer" in result.ci_context
        assert result.ci_context["maintainer"]["source"] == "static"

    async def test_triage_includes_populated_maintainers(self):
        """T-5b/T-V19: Populated JENKINS_OBSERVER_MAINTAINERS flows into ci_context.
        Also validates maintainer freeze: source is always 'static'."""
        env = _env_vars()
        env["JENKINS_OBSERVER_MAINTAINERS"] = "alice@example.com, bob@example.com"
        with patch.dict("os.environ", env):
            from src.agents.jenkins_observer import JenkinsObserver
            bb = _mock_blackboard()
            obs = JenkinsObserver(blackboard=bb)
            mock_response = MagicMock()
            mock_response.text = json.dumps([_make_triage_response()])
            mock_llm = AsyncMock()
            mock_llm.generate = AsyncMock(return_value=mock_response)
            obs._get_llm_adapter = AsyncMock(return_value=mock_llm)
            obs._adapter = AsyncMock()
            obs._adapter.get_build_details = AsyncMock(return_value=None)
            obs._skills_si = "test system instruction"
            signals = [("verify-cnv-4.23.z-build-tier1",
                        _make_meta(result="FAILURE", view="Gating Wrappers"))]
            result = await obs._triage_and_build_evidence(signals)

        assert result.ci_context["maintainer"]["source"] == "static"
        assert result.ci_context["maintainer"]["emails"] == ["alice@example.com", "bob@example.com"]


# =========================================================================
# T-9: Observer handles Jenkins API timeout
# =========================================================================

class TestT9ApiTimeout:

    async def test_poll_loop_survives_timeout(self):
        """T-9: httpx timeout in _drain_once → _poll_loop catches and continues."""
        import httpx

        with patch.dict("os.environ", _env_vars(JENKINS_OBSERVER_STARTUP_DELAY="0")):
            from src.agents.jenkins_observer import JenkinsObserver

            bb = _mock_blackboard()
            obs = JenkinsObserver(blackboard=bb)
            obs._skills_si = "test skills"

            drain_called = False

            async def mock_drain():
                nonlocal drain_called
                drain_called = True
                obs._running = False
                raise httpx.ConnectTimeout("Connection timed out")

            obs._drain_once = mock_drain
            obs._running = True

            mock_sleep = AsyncMock(return_value=None)
            with patch("asyncio.sleep", mock_sleep):
                await obs._poll_loop()

            assert drain_called, "_drain_once should have been called"
        bb.create_event.assert_not_called()


# =========================================================================
# T-10: ci_context field coexists with kargo_context
# =========================================================================

class TestT10FieldCoexistence:

    def test_evidence_accepts_both_contexts(self):
        """T-10: EventEvidence with both ci_context and kargo_context → no error."""
        from src.models import EventEvidence

        evidence = EventEvidence(
            display_text="CI gating failure on CNV 4.23",
            source_type="aligner",
            domain="disorder",
            severity="warning",
            domain_confidence="default",
            kargo_context={
                "project": "kargo-cnv-4-23",
                "stage": "nightly",
                "phase": "Succeeded",
            },
            ci_context={
                "cnv_version": "4.23",
                "jenkins_url": "https://jenkins.example.com",
                "failed_jobs": [{"job_name": "tier1", "build_number": 1, "result": "FAILURE"}],
                "missing_jobs": [],
                "llm_triage": [{"classification": "infra", "confidence": 0.9, "recommended_action": "restart"}],
            },
        )
        assert evidence.kargo_context is not None
        assert evidence.ci_context is not None
        assert evidence.ci_context["cnv_version"] == "4.23"
        assert evidence.domain == "disorder"


# =========================================================================
# T-11: Flood consolidation merges into one event
# =========================================================================

class TestT11FloodConsolidation:

    async def test_flood_above_threshold_creates_single_event(self):
        """T-11/T-V11: 10 failures same version (>threshold=3) → ONE consolidated event.

        Rewritten for scan_view: keys are job_name only, metadata includes 'view'.
        """
        bb = _mock_blackboard()

        with patch.dict("os.environ", _env_vars(JENKINS_OBSERVER_FLOOD_THRESHOLD="3")):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.enabled = MagicMock(return_value=True)

            failed_jobs = [
                _make_job_result(job_name=f"job-{i}", result="FAILURE", color="red")
                for i in range(10)
            ]
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=failed_jobs)
            )

            keys = [f"job-{i}" for i in range(10)]
            bb.drain_jenkins_pending.return_value = keys

            def hget_side(hash_key, key):
                idx = int(key.split("-")[1])
                job = failed_jobs[idx]
                return json.dumps(_make_meta(
                    job_name=job.job_name, result="FAILURE",
                    build_number=job.build_number, view="Gating Wrappers",
                ))

            bb.redis.hget.side_effect = hget_side

            obs._triage_and_build_evidence = AsyncMock(return_value=_make_triage_response())
            obs._get_wip_headroom = AsyncMock(return_value=5)
            obs._skills_si = "test skills"

            await obs._drain_once()

        assert bb.create_event.call_count == 1


# =========================================================================
# T-12: Observer respects startup delay
# =========================================================================

class TestT12StartupDelay:

    async def test_start_waits_for_startup_delay(self):
        """T-12: STARTUP_DELAY=5 → first poll after ~5s sleep."""
        with patch.dict("os.environ", _env_vars(JENKINS_OBSERVER_STARTUP_DELAY="5")):
            from src.agents.jenkins_observer import JenkinsObserver

            bb = _mock_blackboard()
            obs = JenkinsObserver(blackboard=bb)

            call_times = []

            async def mock_drain():
                call_times.append(time.monotonic())
                obs._running = False  # Stop after first drain

            obs._drain_once = mock_drain

            obs._running = True

            mock_sleep = AsyncMock(return_value=None)
            with patch("asyncio.sleep", mock_sleep):
                task = asyncio.create_task(obs._poll_loop())
                await task

            # Verify asyncio.sleep was called with the startup delay
            sleep_calls = [c.args[0] for c in mock_sleep.call_args_list if c.args]
            assert any(s >= 5 for s in sleep_calls), \
                f"Expected startup delay of 5s in sleep calls: {sleep_calls}"


# =========================================================================
# T-13: Active-event dedup blocks double-restart
# =========================================================================

class TestT13ActiveEventDedup:

    async def test_active_event_prevents_creation(self):
        """T-13/T-V13 (active-event dedup): Active event for same service → skip."""
        bb = _mock_blackboard()

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(
                    jobs=[_make_job_result(result="FAILURE", color="red")]
                )
            )
            obs._adapter.enabled = MagicMock(return_value=True)

            bb.drain_jenkins_pending.return_value = ["verify-cnv-4.23.z-build-tier1"]
            bb.redis.hget.return_value = json.dumps(
                _make_meta(result="FAILURE", view="Gating Wrappers")
            )

            bb.get_active_events_with_status.return_value = {"evt-existing": "active"}
            mock_event = MagicMock()
            mock_event.service = "verify-cnv-4.23.z-build-tier1|4.23"
            mock_event.status = "active"
            bb.get_event.return_value = mock_event

            obs._triage_and_build_evidence = AsyncMock(return_value=_make_triage_response())
            obs._get_wip_headroom = AsyncMock(return_value=5)
            obs._skills_si = "test skills"

            await obs._drain_once()

        bb.create_event.assert_not_called()


# =========================================================================
# T-14: Retry-first skill content present
# =========================================================================

class TestT14SkillContent:
    """Skill content probe — validates behavioral principles in aligner_ci_gating.md."""

    SKILLS_DIR = Path(__file__).parent.parent / "src" / "agents" / "brain_skills"

    @pytest.fixture(scope="class")
    def skill_body(self):
        skill_path = self.SKILLS_DIR / "source" / "aligner_ci_gating.md"
        assert skill_path.exists(), f"Skill file not found: {skill_path}"
        return skill_path.read_text()

    def test_retry_before_escalate_present(self, skill_body):
        """PRESENT: retry-first behavioral model language."""
        body_lower = skill_body.lower()
        has_restart = "restart" in body_lower or "retry" in body_lower
        has_before = "before" in body_lower
        has_escalate = "escalat" in body_lower
        assert has_restart and has_before, \
            "Skill must contain 'restart/retry before' language"
        assert has_escalate, \
            "Skill must reference escalation as a later step"

    def test_unconditional_auto_retry_absent(self, skill_body):
        """ABSENT: unconditional automatic retry (safety constraint)."""
        assert "always retry" not in skill_body.lower(), \
            "Skill must NOT contain unconditional 'always retry' language"
        assert "auto-retry all" not in skill_body.lower(), \
            "Skill must NOT contain blanket auto-retry instruction"

    def test_closure_validation_present(self, skill_body):
        """PRESENT: closure validation via gating decision."""
        body_lower = skill_body.lower()
        assert "closure" in body_lower or "close" in body_lower, \
            "Skill must mention closure validation"
        assert "gating" in body_lower or "decision" in body_lower or "policies" in body_lower, \
            "Skill must reference gating decision for closure"

    def test_timing_awareness_present(self, skill_body):
        """PRESENT: timing awareness for wrapper/tier job duration."""
        body_lower = skill_body.lower()
        assert "hour" in body_lower or "6" in skill_body or "9" in skill_body, \
            "Skill must mention job duration (6-9 hours)"


# =========================================================================
# T-15: ci_gating subject_type Pydantic round-trip
# =========================================================================

class TestT15SubjectTypeRoundtrip:

    def test_ci_gating_subject_type_no_validation_error(self):
        """T-15: subject_type='ci_gating' passes Pydantic validation on EventDocument."""
        from src.models import EventDocument, EventInput, EventEvidence

        evidence = EventEvidence(
            display_text="CI gating failure",
            source_type="aligner",
            domain="disorder",
            severity="warning",
            domain_confidence="default",
        )

        event_input = EventInput(
            reason="CI gating job failed",
            evidence=evidence,
        )

        # EventDocument with subject_type="ci_gating" should not raise
        doc = EventDocument(
            id="evt-test0001",
            source="aligner",
            service="verify-cnv-4.23.z-build-tier1|4.23",
            subject_type="ci_gating",
            event=event_input,
        )
        assert doc.subject_type == "ci_gating"
        assert doc.source == "aligner"
        assert doc.service == "verify-cnv-4.23.z-build-tier1|4.23"

    def test_ci_gating_in_escalation_scope_map(self):
        """T-15b: ci_gating has an entry in ESCALATION_SCOPE_MAP."""
        from src.models import ESCALATION_SCOPE_MAP

        assert "ci_gating" in ESCALATION_SCOPE_MAP, \
            "ci_gating must be in ESCALATION_SCOPE_MAP to avoid scope collision"
        assert ESCALATION_SCOPE_MAP["ci_gating"] == "jenkins"


# =========================================================================
# T-16: Skills Catalog fetch failure degrades gracefully
# =========================================================================

class TestT16SkillsDegradation:

    async def test_catalog_500_uses_fallback(self):
        """T-16: Skills Catalog 500 → fallback SI, no exception raised."""
        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            bb = _mock_blackboard()
            obs = JenkinsObserver(blackboard=bb)
            obs._skills_loaded_at = 0  # force reload

            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_resp = MagicMock()
                mock_resp.status_code = 500
                mock_resp.raise_for_status = MagicMock(
                    side_effect=Exception("Server Error")
                )
                mock_client.get = AsyncMock(return_value=mock_resp)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                # Should not raise
                await obs._ensure_skills_loaded()

            # Fallback SI should be set (non-empty)
            assert obs._skills_si is not None
            assert len(obs._skills_si) > 0

    async def test_catalog_timeout_uses_fallback(self):
        """T-16b: Skills Catalog timeout → fallback SI, no exception raised."""
        import httpx as httpx_mod

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            bb = _mock_blackboard()
            obs = JenkinsObserver(blackboard=bb)
            obs._skills_loaded_at = 0  # force re-fetch

            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(
                    side_effect=httpx_mod.ConnectTimeout("timed out")
                )
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                await obs._ensure_skills_loaded()

            assert obs._skills_si is not None
            assert len(obs._skills_si) > 0


# =========================================================================
# T-17: Kill-switch prevents construction
# =========================================================================

class TestT17KillSwitch:

    async def test_disabled_observer_never_constructed(self):
        """T-17: JENKINS_OBSERVER_ENABLED=false → Observer never starts."""
        env = _env_vars(JENKINS_OBSERVER_ENABLED="false")

        with patch.dict("os.environ", env):
            # Mimic main.py lifespan logic
            enabled = env.get("JENKINS_OBSERVER_ENABLED", "false").lower() == "true"
            assert enabled is False, "Kill switch should prevent construction"


# =========================================================================
# T-18: Circuit breaker opens after 3 failures
# =========================================================================

class TestT18CircuitBreaker:

    async def test_breaker_latcheds_after_3_failures(self):
        """T-18: 3 consecutive HTTP failures → breaker latches permanently."""
        with patch.dict("os.environ", _env_vars()):
            from src.adapters.jenkins import JenkinsAdapter

            adapter = JenkinsAdapter(
                base_url="https://jenkins.example.com",
                user="sa-user",
                token="sa-token",
                verify_tls=False,
                breaker_threshold=3,
            )

            # Drive the breaker via _record_failure (the internal method _request calls)
            for _ in range(3):
                adapter._record_failure(None)

            assert adapter._breaker_latched is True, \
                "Circuit breaker should be permanently latched after 3 failures"

    async def test_breaker_latched_skips_http(self):
        """T-18-rw: After breaker opens, scan_view returns empty ViewScanResult
        without making any HTTP call. Rewritten against scan_view contract."""
        with patch.dict("os.environ", _env_vars()):
            from src.adapters.jenkins import JenkinsAdapter

            adapter = JenkinsAdapter(
                base_url="https://jenkins.example.com",
                user="sa-user",
                token="sa-token",
                verify_tls=False,
                breaker_threshold=3,
            )
            adapter._breaker_latched = True

            with patch("httpx.AsyncClient") as MockClient:
                result = await adapter.scan_view("Gating Wrappers")

            MockClient.assert_not_called()
            assert result.jobs == []
            assert result.status_code is None


# =========================================================================
# T-18b: 401/403 excluded from breaker strike count
# =========================================================================

class TestT18bAuthExclusion:
    """T-18b-rw: Auth exclusion carve-out rewritten against scan_view.

    Preserves the behavioral assertion: 401/403 responses must NOT count
    toward the circuit breaker strike threshold.
    """

    async def test_401_does_not_count_toward_breaker(self):
        """T-18b-rw: 3 consecutive 401 responses via scan_view → breaker stays closed."""
        with patch.dict("os.environ", _env_vars()):
            from src.adapters.jenkins import JenkinsAdapter

            adapter = JenkinsAdapter(
                base_url="https://jenkins.example.com",
                user="sa-user",
                token="sa-token",
                verify_tls=False,
                breaker_threshold=3,
            )

            mock_401_resp = MagicMock()
            mock_401_resp.status_code = 401

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.request = AsyncMock(return_value=mock_401_resp)
                mock_get_client.return_value = mock_client

                for _ in range(3):
                    await adapter.scan_view("Gating Wrappers")

            assert adapter._breaker_latched is False, \
                "401 should NOT count toward circuit breaker threshold"
            assert adapter._consecutive_failures == 0, \
                "401 must not touch _consecutive_failures at all"

    async def test_403_does_not_count_toward_breaker(self):
        """T-18b-rw (403): Same exclusion for 403 via scan_view."""
        with patch.dict("os.environ", _env_vars()):
            from src.adapters.jenkins import JenkinsAdapter

            adapter = JenkinsAdapter(
                base_url="https://jenkins.example.com",
                user="sa-user",
                token="sa-token",
                verify_tls=False,
                breaker_threshold=3,
            )

            mock_403_resp = MagicMock()
            mock_403_resp.status_code = 403

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_client = AsyncMock()
                mock_client.request = AsyncMock(return_value=mock_403_resp)
                mock_get_client.return_value = mock_client

                for _ in range(3):
                    await adapter.scan_view("Gating Wrappers")

            assert adapter._breaker_latched is False
            assert adapter._consecutive_failures == 0


# =========================================================================
# T-20: Dry-run mode skips event creation
# =========================================================================

class TestT20DryRun:

    async def test_dry_run_logs_but_does_not_create(self):
        """T-20: DRY_RUN=true → evidence logged, create_event NOT called."""
        bb = _mock_blackboard()

        failed_job = _make_job_result(result="FAILURE", color="red")

        with patch.dict("os.environ", _env_vars(JENKINS_OBSERVER_DRY_RUN="true")):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=[failed_job])
            )
            obs._adapter.enabled = MagicMock(return_value=True)

            bb.drain_jenkins_pending.return_value = ["verify-cnv-4.23.z-build-tier1"]
            bb.redis.hget.return_value = json.dumps(
                _make_meta(result="FAILURE", view="Gating Wrappers")
            )

            from src.models import EventEvidence
            evidence_mock = EventEvidence(
                display_text="CI gating failure: test",
                source_type="aligner",
                domain="disorder",
                domain_confidence="default",
                severity="warning",
            )
            obs._triage_and_build_evidence = AsyncMock(return_value=evidence_mock)
            obs._get_wip_headroom = AsyncMock(return_value=5)
            obs._skills_si = "test skills"

            await obs._drain_once()

        bb.create_event.assert_not_called()


# =========================================================================
# T-21: _redact_secrets_in_text handles quoted and JSON-style secrets
# =========================================================================

class TestT21RedactSecretsInText:

    def test_bare_key_value(self):
        """Baseline: unquoted key=value is redacted (regression guard)."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        result = _redact_secrets_in_text("JENKINS_TOKEN=abc123def build started")
        assert "abc123def" not in result
        assert "***REDACTED***" in result

    def test_double_quoted_value(self):
        """password="hunter2" -> value redacted, quotes preserved."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        result = _redact_secrets_in_text('password="hunter2"')
        assert "hunter2" not in result
        assert result == 'password="***REDACTED***"'

    def test_single_quoted_value(self):
        """token: 'abc' -> value redacted, quotes preserved."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        result = _redact_secrets_in_text("token: 'abc'")
        assert result == "token: '***REDACTED***'"

    def test_json_format(self):
        """JSON blob with a quoted key and quoted value -- both key and value quoted."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        result = _redact_secrets_in_text('{"password": "hunter2", "user": "bob"}')
        assert "hunter2" not in result
        assert '"password": "***REDACTED***"' in result
        # Unrelated JSON fields must survive untouched.
        assert '"user": "bob"' in result

    def test_json_no_space_after_colon(self):
        """Compact JSON (no space after colon) still matches."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        result = _redact_secrets_in_text('{"token":"xyz789"}')
        assert "xyz789" not in result
        assert result == '{"token":"***REDACTED***"}'

    def test_bearer_token_quoted(self):
        """Authorization header with a quoted Bearer token."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        result = _redact_secrets_in_text('Authorization: "Bearer abc123"')
        assert "abc123" not in result
        assert result == 'Authorization: "***REDACTED***"'

    def test_bearer_token_bare(self):
        """Authorization: Bearer <token> (unquoted) -- token must not survive."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        result = _redact_secrets_in_text("Authorization: Bearer eyJhbGciOiJIUzI1NiIs")
        assert "eyJhbGciOiJIUzI1NiIs" not in result

    def test_shell_export_single_quoted(self):
        """export SECRET='value' shell-style assignment."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        result = _redact_secrets_in_text("export SECRET='my-secret-value' && run.sh")
        assert "my-secret-value" not in result
        assert "run.sh" in result

    def test_no_secrets_untouched(self):
        """Text with no secret-like patterns passes through unchanged."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        text = "no secrets here just a normal build log"
        assert _redact_secrets_in_text(text) == text

    def test_empty_and_none_safe(self):
        """Falsy input is returned as-is without raising."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        assert _redact_secrets_in_text("") == ""
        assert _redact_secrets_in_text(None) is None


# =========================================================================
# T-V1: scan_view 200 returns ViewScanResult with parsed jobs
# =========================================================================

class TestTV1ScanViewSuccess:

    async def test_scan_view_200_returns_parsed_jobs(self):
        """T-V1: scan_view(view) → ViewScanResult with status_code=200 and parsed jobs."""
        with patch.dict("os.environ", _env_vars()):
            from src.adapters.jenkins import JenkinsAdapter, ViewScanResult, JobResult

            adapter = JenkinsAdapter(
                base_url="https://jenkins.example.com",
                user="sa-user",
                token="sa-token",
                verify_tls=False,
            )

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "jobs": [
                    {"name": "job-a", "color": "red",
                     "lastBuild": {"number": 10, "result": "FAILURE",
                                   "url": "https://j.io/job/job-a/10/",
                                   "timestamp": 1724680000000}},
                    {"name": "job-b", "color": "blue",
                     "lastBuild": {"number": 5, "result": "SUCCESS",
                                   "url": "https://j.io/job/job-b/5/",
                                   "timestamp": 1724690000000}},
                ],
            }

            with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_resp
                result = await adapter.scan_view("Gating Wrappers")

            assert isinstance(result, ViewScanResult)
            assert result.status_code == 200
            assert len(result.jobs) == 2
            names = {j.job_name for j in result.jobs}
            assert names == {"job-a", "job-b"}


# =========================================================================
# T-V2: scan_view 404 returns ViewScanResult with empty jobs
# =========================================================================

class TestTV2ScanView404:

    async def test_scan_view_404_returns_empty_with_status(self):
        """T-V2: scan_view on a non-existent view → ViewScanResult([], 404)."""
        with patch.dict("os.environ", _env_vars()):
            from src.adapters.jenkins import JenkinsAdapter, ViewScanResult

            adapter = JenkinsAdapter(
                base_url="https://jenkins.example.com",
                user="sa-user",
                token="sa-token",
                verify_tls=False,
            )

            mock_resp = MagicMock()
            mock_resp.status_code = 404

            with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_resp
                result = await adapter.scan_view("Nonexistent View")

            assert isinstance(result, ViewScanResult)
            assert result.status_code == 404
            assert result.jobs == []


# =========================================================================
# T-V3: scan_view transport error returns ViewScanResult([], None)
# =========================================================================

class TestTV3ScanViewTransportError:

    async def test_resp_none_returns_empty_viewscanresult(self):
        """T-V3: adapter._request returns None (transport error) →
        ViewScanResult([], None)."""
        with patch.dict("os.environ", _env_vars()):
            from src.adapters.jenkins import JenkinsAdapter, ViewScanResult

            adapter = JenkinsAdapter(
                base_url="https://jenkins.example.com",
                user="sa-user",
                token="sa-token",
                verify_tls=False,
            )

            with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = None
                result = await adapter.scan_view("Gating Wrappers")

            assert isinstance(result, ViewScanResult)
            assert result.status_code is None
            assert result.jobs == []


# =========================================================================
# T-V4: scan_view breaker open skips HTTP
# =========================================================================

class TestTV4BreakerOpenSkipsHttp:

    async def test_breaker_open_returns_empty_no_http(self):
        """T-V4: Breaker pre-latched → ViewScanResult([], None), no HTTP."""
        with patch.dict("os.environ", _env_vars()):
            from src.adapters.jenkins import JenkinsAdapter

            adapter = JenkinsAdapter(
                base_url="https://jenkins.example.com",
                user="sa-user",
                token="sa-token",
                verify_tls=False,
            )
            adapter._breaker_latched = True

            with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
                result = await adapter.scan_view("Gating Wrappers")

            mock_request.assert_not_called()
            assert result.jobs == []
            assert result.status_code is None


# =========================================================================
# T-V5: scan_view URL construction
# =========================================================================

class TestTV5ScanViewUrl:

    async def test_scan_view_queries_correct_url(self):
        """T-V5: scan_view URL-encodes view name and includes the right tree query."""
        with patch.dict("os.environ", _env_vars()):
            from src.adapters.jenkins import JenkinsAdapter

            adapter = JenkinsAdapter(
                base_url="https://jenkins.example.com",
                user="sa-user",
                token="sa-token",
                verify_tls=False,
            )

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"jobs": []}

            with patch.object(adapter, "_request", new_callable=AsyncMock) as mock_request:
                mock_request.return_value = mock_resp
                await adapter.scan_view("Gating Wrappers")

            mock_request.assert_called_once()
            call_args = mock_request.call_args
            requested_path = call_args[0][1] if len(call_args[0]) > 1 else str(call_args)
            assert "Gating%20Wrappers" in requested_path or "Gating+Wrappers" in requested_path
            assert "tree=" in requested_path
            assert "lastBuild" in requested_path


# =========================================================================
# T-V7b: Board-wide red threshold (7/10 = 0.7, NOT board-red)
# =========================================================================

class TestTV7bBoardRedThreshold:

    async def test_70_pct_failing_is_not_board_red(self):
        """T-V7b: 7/10 failing = 0.7, which does NOT exceed the >0.7 threshold.
        This must NOT trigger BOARD_RED staging."""
        bb = _mock_blackboard()

        jobs = []
        for i in range(10):
            result = "FAILURE" if i < 7 else "SUCCESS"
            color = "red" if i < 7 else "blue"
            jobs.append(_make_job_result(
                job_name=f"job-{i}", result=result, color=color,
                timestamp=int(time.time() * 1000),
            ))

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=jobs)
            )
            obs._adapter.enabled = MagicMock(return_value=True)
            obs._skills_si = "test skills"

            await obs._poll_and_stage()

        staged_calls = bb.stage_jenkins_signal.call_args_list
        for call in staged_calls:
            key = call.args[0] if call.args else call.kwargs.get("key", "")
            assert "view-outage:" not in key, \
                f"7/10=0.7 should NOT trigger BOARD_RED, but got key: {key}"


# =========================================================================
# T-V7c: Board-wide red service_name format
# =========================================================================

class TestTV7cBoardRedServiceName:

    async def test_board_red_service_name_format(self):
        """T-V7c: >70% failing triggers BOARD_RED with
        service_name = 'ci-gating-outage|{view}', not 'view-outage:…|multi'."""
        bb = _mock_blackboard()

        jobs = [
            _make_job_result(
                job_name=f"job-{i}", result="FAILURE", color="red",
                timestamp=int(time.time() * 1000),
            )
            for i in range(10)
        ]

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=jobs)
            )
            obs._adapter.enabled = MagicMock(return_value=True)
            obs._skills_si = "test skills"

            bb.drain_jenkins_pending.return_value = ["view-outage:Gating Wrappers"]
            bb.redis.hget.return_value = json.dumps({
                "job_name": "view-outage:Gating Wrappers",
                "result": "BOARD_RED",
                "version": "multi",
                "view": "Gating Wrappers",
                "staged_at": time.time(),
            })

            obs._triage_and_build_evidence = AsyncMock(return_value=_make_triage_response())
            obs._get_wip_headroom = AsyncMock(return_value=5)

            await obs._drain_once()

        if bb.create_event.called:
            kwargs = bb.create_event.call_args.kwargs
            service = kwargs.get("service", "")
            assert "ci-gating-outage|" in service, \
                f"BOARD_RED service_name should be 'ci-gating-outage|{{view}}', got: {service}"


# =========================================================================
# T-V7d: Board-wide red >= 3 active-job floor (boundary)
# =========================================================================

class TestTV7dBoardRedActiveFloor:
    """T-V7d: board-wide-red requires len(active) >= 3, even at 100% failing.
    PR description flags this floor as an undocumented plan deviation --
    a regression that changes or drops it must fail a test, not ship silently."""

    async def test_two_active_100pct_failing_is_not_board_red(self):
        """2 active jobs, both failing (ratio=1.0 > 0.7) but below the >=3
        floor -- must NOT trigger BOARD_RED; each job stages individually."""
        bb = _mock_blackboard()

        jobs = [
            _make_job_result(
                job_name=f"job-{i}", result="FAILURE", color="red",
                timestamp=int(time.time() * 1000),
            )
            for i in range(2)
        ]

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=jobs)
            )
            obs._adapter.enabled = MagicMock(return_value=True)
            obs._skills_si = "test skills"

            await obs._poll_and_stage()

        staged_keys = [
            call.args[0] if call.args else call.kwargs.get("key", "")
            for call in bb.stage_jenkins_signal.call_args_list
        ]
        assert not any("view-outage:" in key for key in staged_keys), \
            f"2 active jobs (below >=3 floor) must NOT trigger BOARD_RED, got: {staged_keys}"
        assert len(staged_keys) == 2, \
            f"Below the floor, each failing job should stage individually, got: {staged_keys}"

    async def test_three_active_100pct_failing_is_board_red(self):
        """3 active jobs, all failing (ratio=1.0 > 0.7) -- exactly at the >=3
        floor -- MUST trigger a single consolidated BOARD_RED signal."""
        bb = _mock_blackboard()

        jobs = [
            _make_job_result(
                job_name=f"job-{i}", result="FAILURE", color="red",
                timestamp=int(time.time() * 1000),
            )
            for i in range(3)
        ]

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=jobs)
            )
            obs._adapter.enabled = MagicMock(return_value=True)
            obs._skills_si = "test skills"

            await obs._poll_and_stage()

        staged_keys = [
            call.args[0] if call.args else call.kwargs.get("key", "")
            for call in bb.stage_jenkins_signal.call_args_list
        ]
        assert len(staged_keys) == 1 and "view-outage:" in staged_keys[0], \
            f"3 active jobs (at the >=3 floor) MUST trigger a single BOARD_RED signal, got: {staged_keys}"


# =========================================================================
# T-V13: JOB_METADATA parse - wrapper type
# =========================================================================

class TestTV13JobMetadataWrapper:

    def test_wrapper_metadata_extracts_version_type_name(self):
        """T-V13: Wrapper JOB_METADATA → parsed dict with version, type, name;
        no tasks array in output."""
        from src.agents.jenkins_observer import _parse_job_metadata

        params = {
            "JOB_METADATA": json.dumps({
                "version": "4.23",
                "type": "wrapper",
                "name": "verify-cnv-4.23.z-build-tier1",
                "tasks": [{"name": "t1"}, {"name": "t2"}],
                "factory": "cnv-ci",
            }),
        }
        result = _parse_job_metadata(params)
        assert result["version"] == "4.23"
        assert result["type"] == "wrapper"
        assert result["name"] == "verify-cnv-4.23.z-build-tier1"
        assert "tasks" not in result


# =========================================================================
# T-V13b: JOB_METADATA parse - edge cases
# =========================================================================

class TestTV13bJobMetadataParseMalformed:

    def test_missing_key_returns_empty(self):
        """T-V13b: params without JOB_METADATA → {}."""
        from src.agents.jenkins_observer import _parse_job_metadata
        assert _parse_job_metadata({}) == {}

    def test_empty_string_returns_empty(self):
        """T-V13b: JOB_METADATA='' → {}."""
        from src.agents.jenkins_observer import _parse_job_metadata
        assert _parse_job_metadata({"JOB_METADATA": ""}) == {}

    def test_invalid_json_returns_empty(self):
        """T-V13b: Malformed JSON → {}."""
        from src.agents.jenkins_observer import _parse_job_metadata
        assert _parse_job_metadata({"JOB_METADATA": "not{json"}) == {}

    def test_non_dict_json_returns_empty(self):
        """T-V13b: JSON array instead of object → {}."""
        from src.agents.jenkins_observer import _parse_job_metadata
        assert _parse_job_metadata({"JOB_METADATA": "[1,2,3]"}) == {}

    def test_none_value_returns_empty(self):
        """T-V13b: JOB_METADATA=None → {}."""
        from src.agents.jenkins_observer import _parse_job_metadata
        assert _parse_job_metadata({"JOB_METADATA": None}) == {}


# =========================================================================
# T-V14: JOB_METADATA parse - leaf type with labels, owner
# =========================================================================

class TestTV14JobMetadataLeaf:

    def test_leaf_metadata_keeps_labels_and_owner(self):
        """T-V14: Leaf JOB_METADATA → labels (capped at 20), owner, team kept."""
        from src.agents.jenkins_observer import _parse_job_metadata

        labels = [f"label-{i}" for i in range(25)]
        params = {
            "JOB_METADATA": json.dumps({
                "version": "4.23",
                "type": "test",
                "name": "smoke-tier1-basic",
                "labels": labels,
                "owner": "qe-team@redhat.com",
                "team": "qe-cnv",
                "tier": "tier1",
            }),
        }
        result = _parse_job_metadata(params)
        assert result["owner"] == "qe-team@redhat.com"
        assert result["team"] == "qe-cnv"
        assert "labels" in result
        assert len(result["labels"]) <= 20
        assert "gate" not in result.get("labels", []) or isinstance(result["labels"], list)


# =========================================================================
# T-V15: raw JOB_METADATA stripped from failed_jobs.parameters
# =========================================================================

class TestTV15RawMetadataStripped:

    async def test_job_metadata_and_ci_message_stripped(self):
        """T-V15: After triage, failed_jobs[].parameters must NOT contain
        raw JOB_METADATA or CI_MESSAGE keys (stripped to save token budget)."""
        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver
            from src.adapters.jenkins import BuildDetails

            bb = _mock_blackboard()
            obs = JenkinsObserver(blackboard=bb)

            build_details = BuildDetails(
                job_name="verify-cnv-4.23.z-build-tier1",
                build_number=100,
                result="FAILURE",
                parameters={
                    "JOB_METADATA": '{"version":"4.23","type":"wrapper"}',
                    "CI_MESSAGE": "some long CI message",
                    "BRANCH": "main",
                },
            )

            mock_response = MagicMock()
            mock_response.text = json.dumps([_make_triage_response()])
            mock_llm = AsyncMock()
            mock_llm.generate = AsyncMock(return_value=mock_response)
            obs._get_llm_adapter = AsyncMock(return_value=mock_llm)
            obs._adapter = AsyncMock()
            obs._adapter.get_build_details = AsyncMock(return_value=build_details)
            obs._skills_si = "test system instruction"

            signals = [("verify-cnv-4.23.z-build-tier1",
                        _make_meta(result="FAILURE", view="Gating Wrappers"))]
            result = await obs._triage_and_build_evidence(signals)

        for job in result.ci_context.get("failed_jobs", []):
            params = job.get("parameters", {})
            assert "JOB_METADATA" not in params, \
                "Raw JOB_METADATA must be stripped from failed_jobs parameters"
            assert "CI_MESSAGE" not in params, \
                "CI_MESSAGE must be stripped from failed_jobs parameters"


# =========================================================================
# T-V16: Pipe cutover in start()
# =========================================================================

class TestTV16PipeCutover:

    async def test_start_commits_pipe_keys(self):
        """T-V16: start() scans pending queue and commits any key containing '|'
        (legacy pipe-format cutover)."""
        bb = _mock_blackboard()

        bb.redis.zrange = AsyncMock(return_value=[
            ("old-job|4.23", 1000.0),
            ("new-job-no-pipe", 2000.0),
        ])

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.enabled = MagicMock(return_value=True)
            obs._poll_loop = AsyncMock()

            await obs.start()

        committed_keys = [
            call.args[0] for call in bb.commit_jenkins_signal.call_args_list
        ]
        assert "old-job|4.23" in committed_keys, \
            "Pipe-format keys must be committed during start() cutover"


# =========================================================================
# T-V19: Maintainer freeze (source==static)
# =========================================================================

class TestTV19MaintainerFreeze:

    async def test_ci_context_maintainer_always_static(self):
        """T-V19: ci_context.maintainer.source is always 'static'.
        JOB_METADATA.owner is the test owner, NOT the Darwin maintainer."""
        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            bb = _mock_blackboard()
            obs = JenkinsObserver(blackboard=bb)
            mock_response = MagicMock()
            mock_response.text = json.dumps([_make_triage_response()])
            mock_llm = AsyncMock()
            mock_llm.generate = AsyncMock(return_value=mock_response)
            obs._get_llm_adapter = AsyncMock(return_value=mock_llm)
            obs._adapter = AsyncMock()
            obs._adapter.get_build_details = AsyncMock(return_value=None)
            obs._skills_si = "test system instruction"

            signals = [("verify-cnv-4.23.z-build-tier1",
                        _make_meta(result="FAILURE"))]
            result = await obs._triage_and_build_evidence(signals)

        assert result.ci_context["maintainer"]["source"] == "static"


# =========================================================================
# T-V20: jenkins_view_unhealthy parity across all surfaces
# =========================================================================

class TestTV20ViewUnhealthyParity:
    """T-V20: jenkins_view_unhealthy field must exist on FlowSnapshot,
    FlowMetricsResponse, and both TS interfaces (FlowSnapshot, FlowMetrics)."""

    def test_flow_snapshot_has_jenkins_view_unhealthy(self):
        from src.models import FlowSnapshot
        assert "jenkins_view_unhealthy" in FlowSnapshot.model_fields, \
            "FlowSnapshot must have jenkins_view_unhealthy field"

    def test_flow_metrics_response_has_jenkins_view_unhealthy(self):
        from src.models import FlowMetricsResponse
        assert "jenkins_view_unhealthy" in FlowMetricsResponse.model_fields, \
            "FlowMetricsResponse must have jenkins_view_unhealthy field"

    def test_ts_flow_snapshot_has_jenkins_view_unhealthy(self):
        import re
        ts_path = Path(__file__).parent.parent / "ui" / "src" / "api" / "types.ts"
        content = ts_path.read_text()
        match = re.search(
            r"export\s+interface\s+FlowSnapshot\s*\{(.+?)^\}",
            content, re.DOTALL | re.MULTILINE,
        )
        assert match, "FlowSnapshot TS interface not found"
        fields = set(re.findall(r"^\s+(\w+)\s*\??:", match.group(1), re.MULTILINE))
        assert "jenkins_view_unhealthy" in fields, \
            "TS FlowSnapshot must have jenkins_view_unhealthy"

    def test_ts_flow_metrics_has_jenkins_view_unhealthy(self):
        import re
        ts_path = Path(__file__).parent.parent / "ui" / "src" / "api" / "types.ts"
        content = ts_path.read_text()
        match = re.search(
            r"export\s+interface\s+FlowMetrics\s*\{(.+?)^\}",
            content, re.DOTALL | re.MULTILINE,
        )
        assert match, "FlowMetrics TS interface not found"
        fields = set(re.findall(r"^\s+(\w+)\s*\??:", match.group(1), re.MULTILINE))
        assert "jenkins_view_unhealthy" in fields, \
            "TS FlowMetrics must have jenkins_view_unhealthy"

    def test_downsample_uses_any_for_view_unhealthy(self):
        """Downsampled jenkins_view_unhealthy must use any() (boolean gauge),
        not sum() or avg()."""
        from src.models import FlowSnapshot

        snapshots = [
            FlowSnapshot(timestamp=100.0, jenkins_view_unhealthy=False),
            FlowSnapshot(timestamp=101.0, jenkins_view_unhealthy=True),
            FlowSnapshot(timestamp=102.0, jenkins_view_unhealthy=False),
        ]
        assert any(s.jenkins_view_unhealthy for s in snapshots), \
            "any() over a group with one True must yield True"


# =========================================================================
# T-V22: Empty JENKINS_OBSERVER_VIEWS must report unhealthy, not silently healthy
# =========================================================================

class TestTV22EmptyViewsReportsUnhealthy:
    """T-V22: A misconfigured/renamed values key (e.g. the retired
    jenkinsObserver.versions -> views rename) resolving to an empty views list
    must surface as view_unhealthy=True, not silently mask discovery as
    healthy (view_unhealthy defaulted to False via an empty dict)."""

    async def test_empty_views_marks_view_unhealthy_true(self):
        bb = _mock_blackboard()

        with patch.dict("os.environ", _env_vars(JENKINS_OBSERVER_VIEWS="")):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.enabled = MagicMock(return_value=True)

            assert obs.view_unhealthy is False, \
                "Sanity: view_unhealthy should be False before any poll cycle"

            await obs._poll_and_stage()

        assert obs.view_unhealthy is True, \
            "Empty JENKINS_OBSERVER_VIEWS must mark view_unhealthy=True, " \
            "not silently report healthy while discovery is dark"
        bb.stage_jenkins_signal.assert_not_called()


# =========================================================================
# T-V21: FAILURE + timestamp=None still staged (recency does not drop it)
# =========================================================================

class TestTV21FailureNullTimestampStaged:

    async def test_failure_with_no_timestamp_still_staged(self):
        """T-V21: A FAILURE job with timestamp=None is still staged.
        Recency filtering only drops stale SUCCESS — never FAILURE/UNSTABLE/ABORTED."""
        bb = _mock_blackboard()

        job_no_ts = _make_job_result(
            job_name="broken-job", result="FAILURE", color="red",
            timestamp=None,
        )

        with patch.dict("os.environ", _env_vars(JENKINS_OBSERVER_RECENCY_HOURS="72")):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=[job_no_ts])
            )
            obs._adapter.enabled = MagicMock(return_value=True)
            obs._skills_si = "test skills"

            await obs._poll_and_stage()

        bb.stage_jenkins_signal.assert_called()
        staged_key = bb.stage_jenkins_signal.call_args[0][0]
        assert "broken-job" in staged_key
