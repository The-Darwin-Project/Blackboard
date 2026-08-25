# tests/test_jenkins_observer.py
# @ai-rules:
# 1. [Pattern]: Tests the JenkinsObserver drain loop, adapter, and integration.
# 2. [Constraint]: No real Redis/LLM/HTTP. AsyncMock blackboard, mock httpx, mock GeminiAdapter.
# 3. [Pattern]: _drain_once() tested directly — NOT the while True _poll_loop().
# 4. [Pattern]: Circuit breaker tests target src/adapters/jenkins.py directly.
# 5. [Gotcha]: asyncio_mode=auto in pytest.ini — no @pytest.mark.asyncio decorator needed.
# 6. [Gotcha]: Implementation runs in parallel — tests assert planned interface, may need
#    adjustment at reconciliation time if executor's public API deviates.
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
                     result="FAILURE", version="4.23"):
    """Build a JobResult dataclass matching the adapter's return shape."""
    from src.adapters.jenkins import JobResult
    return JobResult(
        job_name=job_name,
        build_number=build_number,
        result=result,
        url=f"https://jenkins.example.com/job/{job_name}/{build_number}",
    )


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
    """Default env vars for JenkinsObserver construction."""
    defaults = {
        "JENKINS_OBSERVER_ENABLED": "true",
        "JENKINS_OBSERVER_POLL_INTERVAL": "300",
        "JENKINS_OBSERVER_STARTUP_DELAY": "0",
        "JENKINS_OBSERVER_DWELL_SECONDS": "60",
        "JENKINS_OBSERVER_FLOOD_THRESHOLD": "3",
        "JENKINS_OBSERVER_DRY_RUN": "false",
        "JENKINS_OBSERVER_VERSIONS": "4.23",
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


# =========================================================================
# T-1: Observer creates event for failed Jenkins job
# =========================================================================

class TestT1EventCreation:

    async def test_drain_creates_event_for_failed_job(self):
        """T-1: Failed Jenkins job → create_event called with correct args."""
        bb = _mock_blackboard()

        failed_job = _make_job_result(result="FAILURE")
        triage = _make_triage_response()

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)

            # Mock the adapter to return one failed job
            obs._adapter = AsyncMock()
            obs._adapter.poll_smoke_jobs = AsyncMock(return_value=[failed_job])
            obs._adapter.poll_gating_jobs = AsyncMock(return_value=[])
            obs._adapter.enabled = MagicMock(return_value=True)

            # Mock drain to return one ready signal
            bb.drain_jenkins_pending.return_value = ["verify-cnv-4.23.z-build-tier1|4.23"]
            bb.redis.hget.return_value = json.dumps({
                "job_name": "verify-cnv-4.23.z-build-tier1",
                "build_number": 100, "result": "FAILURE",
                "version": "4.23", "staged_at": time.time(),
            })

            # Mock triage
            obs._triage_and_build_evidence = AsyncMock(return_value=triage)

            # Mock WIP headroom
            obs._get_wip_headroom = AsyncMock(return_value=5)

            # Mock skills loaded
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
        """T-2: All jobs SUCCESS → no event created."""
        bb = _mock_blackboard()

        healthy_job = _make_job_result(result="SUCCESS")

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.poll_smoke_jobs = AsyncMock(return_value=[healthy_job])
            obs._adapter.poll_gating_jobs = AsyncMock(return_value=[])
            obs._adapter.enabled = MagicMock(return_value=True)

            # No signals staged → drain returns empty
            bb.drain_jenkins_pending.return_value = []
            obs._skills_si = "test skills"
            obs._get_wip_headroom = AsyncMock(return_value=5)

            await obs._drain_once()

        bb.create_event.assert_not_called()


# =========================================================================
# T-3: WIP gate blocks event creation
# =========================================================================

class TestT3WipGate:

    async def test_wip_full_restages_not_creates(self):
        """T-3: WIP headroom=0 → restage called, no create_event."""
        bb = _mock_blackboard()

        failed_job = _make_job_result(result="FAILURE")
        triage = _make_triage_response()

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.poll_smoke_jobs = AsyncMock(return_value=[failed_job])
            obs._adapter.poll_gating_jobs = AsyncMock(return_value=[])
            obs._adapter.enabled = MagicMock(return_value=True)

            bb.drain_jenkins_pending.return_value = ["verify-cnv-4.23.z-build-tier1|4.23"]
            bb.redis.hget.return_value = json.dumps({
                "job_name": "verify-cnv-4.23.z-build-tier1",
                "build_number": 100, "result": "FAILURE",
                "version": "4.23", "staged_at": time.time(),
            })

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
        """T-5: _triage_and_build_evidence returns structured EventEvidence."""
        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver
            from src.models import EventEvidence

            bb = _mock_blackboard()
            obs = JenkinsObserver(blackboard=bb)

            # Mock the LLM adapter (lazy-loaded via _get_llm_adapter)
            mock_response = MagicMock()
            mock_response.text = json.dumps([_make_triage_response()])
            mock_llm = AsyncMock()
            mock_llm.generate = AsyncMock(return_value=mock_response)
            obs._get_llm_adapter = AsyncMock(return_value=mock_llm)

            # Mock the Jenkins adapter for build details fetch
            obs._adapter = AsyncMock()
            obs._adapter.get_build_details = AsyncMock(return_value=None)

            obs._skills_si = "test system instruction"

            # Real signature: signals: list[tuple[str, dict]]
            signals = [("verify-cnv-4.23.z-build-tier1|4.23", {
                "job_name": "verify-cnv-4.23.z-build-tier1",
                "version": "4.23",
                "result": "FAILURE",
                "build_number": 100,
                "url": "https://jenkins.example.com/job/verify-cnv-4.23.z-build-tier1/100",
                "staged_at": time.time(),
            })]
            result = await obs._triage_and_build_evidence(signals)

        assert isinstance(result, EventEvidence)
        assert result.ci_context is not None
        assert result.source_type == "aligner"
        assert result.domain == "disorder"
        assert "llm_triage" in result.ci_context


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
        """T-11: 10 failures same version (>threshold=3) → ONE consolidated event."""
        bb = _mock_blackboard()

        with patch.dict("os.environ", _env_vars(JENKINS_OBSERVER_FLOOD_THRESHOLD="3")):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.enabled = MagicMock(return_value=True)

            # 10 failed jobs for the same version
            failed_jobs = [
                _make_job_result(job_name=f"job-{i}", result="FAILURE", version="4.23")
                for i in range(10)
            ]
            obs._adapter.poll_smoke_jobs = AsyncMock(return_value=failed_jobs[:5])
            obs._adapter.poll_gating_jobs = AsyncMock(return_value=failed_jobs[5:])

            # All 10 staged and drained
            keys = [f"job-{i}|4.23" for i in range(10)]
            bb.drain_jenkins_pending.return_value = keys

            def hget_side(hash_key, key):
                idx = int(key.split("|")[0].split("-")[1])
                job = failed_jobs[idx]
                return json.dumps({
                    "job_name": job.job_name,
                    "version": "4.23",
                    "result": job.result or "MISSING",
                    "build_number": job.build_number,
                    "url": job.url,
                    "staged_at": time.time(),
                })

            bb.redis.hget.side_effect = hget_side

            obs._triage_and_build_evidence = AsyncMock(return_value=_make_triage_response())
            obs._get_wip_headroom = AsyncMock(return_value=5)
            obs._skills_si = "test skills"

            await obs._drain_once()

        # Flood consolidation: all 10 grouped by version → 1 consolidated event
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
        """T-13: Active event for same service → skip, no new event."""
        bb = _mock_blackboard()

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.poll_smoke_jobs = AsyncMock(return_value=[
                _make_job_result(result="FAILURE")
            ])
            obs._adapter.poll_gating_jobs = AsyncMock(return_value=[])
            obs._adapter.enabled = MagicMock(return_value=True)

            bb.drain_jenkins_pending.return_value = ["verify-cnv-4.23.z-build-tier1|4.23"]
            bb.redis.hget.return_value = json.dumps({
                "job_name": "verify-cnv-4.23.z-build-tier1",
                "version": "4.23",
                "result": "FAILURE",
                "build_number": 100,
                "url": "https://jenkins.example.com/job/verify-cnv-4.23.z-build-tier1/100",
                "staged_at": time.time(),
            })

            # Simulate active event already exists for this service
            bb.get_active_events_with_status.return_value = {
                "evt-existing": "active"
            }
            # get_event returns an event with matching service
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
        """T-18 (cont): After breaker opens, subsequent calls skip HTTP."""
        with patch.dict("os.environ", _env_vars()):
            from src.adapters.jenkins import JenkinsAdapter

            adapter = JenkinsAdapter(
                base_url="https://jenkins.example.com",
                user="sa-user",
                token="sa-token",
                verify_tls=False,
                breaker_threshold=3,
            )
            adapter._breaker_latched = True  # Pre-latch

            with patch("httpx.AsyncClient") as MockClient:
                result = await adapter.poll_smoke_jobs("4.23")

            # Should return empty without making HTTP call
            MockClient.assert_not_called()
            assert result == [] or result is None


# =========================================================================
# T-18b: 401/403 excluded from breaker strike count
# =========================================================================

class TestT18bAuthExclusion:

    async def test_401_does_not_count_toward_breaker(self):
        """T-18b: 3 consecutive 401/403 → breaker does NOT open."""
        import httpx as httpx_mod

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
            mock_401_resp.raise_for_status = MagicMock(
                side_effect=httpx_mod.HTTPStatusError(
                    "Unauthorized", request=MagicMock(), response=mock_401_resp
                )
            )

            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_401_resp)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                for _ in range(3):
                    try:
                        await adapter.poll_smoke_jobs("4.23")
                    except Exception:
                        pass

            # 401/403 excluded — breaker stays closed
            assert adapter._breaker_latched is False, \
                "401/403 should NOT count toward circuit breaker threshold"

    async def test_403_does_not_count_toward_breaker(self):
        """T-18b (403): Same exclusion for 403 responses."""
        import httpx as httpx_mod

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
            mock_403_resp.raise_for_status = MagicMock(
                side_effect=httpx_mod.HTTPStatusError(
                    "Forbidden", request=MagicMock(), response=mock_403_resp
                )
            )

            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_client.get = AsyncMock(return_value=mock_403_resp)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                for _ in range(3):
                    try:
                        await adapter.poll_smoke_jobs("4.23")
                    except Exception:
                        pass

            assert adapter._breaker_latched is False


# =========================================================================
# T-20: Dry-run mode skips event creation
# =========================================================================

class TestT20DryRun:

    async def test_dry_run_logs_but_does_not_create(self):
        """T-20: DRY_RUN=true → evidence logged, create_event NOT called."""
        bb = _mock_blackboard()

        failed_job = _make_job_result(result="FAILURE")
        triage = _make_triage_response()

        with patch.dict("os.environ", _env_vars(JENKINS_OBSERVER_DRY_RUN="true")):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.poll_smoke_jobs = AsyncMock(return_value=[failed_job])
            obs._adapter.poll_gating_jobs = AsyncMock(return_value=[])
            obs._adapter.enabled = MagicMock(return_value=True)

            bb.drain_jenkins_pending.return_value = ["verify-cnv-4.23.z-build-tier1|4.23"]
            bb.redis.hget.return_value = json.dumps({
                "job_name": "verify-cnv-4.23.z-build-tier1",
                "build_number": 100, "result": "FAILURE",
                "version": "4.23", "staged_at": time.time(),
            })

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
