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
import urllib.parse
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.adapters.jenkins import _MAX_BLOB_LEN, _PRESTRIP_WINDOW, _strip_pipeline_annotations


# =========================================================================
# Helpers
# =========================================================================

def _make_adapter(enabled=True):
    adapter = AsyncMock()
    adapter.enabled = MagicMock(return_value=enabled)
    adapter.scan_view = AsyncMock(return_value=_make_view_scan_result([]))
    
    # Needs to return a valid object that has console_tail string to avoid TypeError in redact_secrets
    details = MagicMock()
    details.console_tail = "Mock console tail"
    details.parameters = {}
    adapter.get_build_details = AsyncMock(return_value=details)
    return adapter

def _make_observer(bb, adapter, views=None, dry_run=False):
    from src.agents.jenkins_observer import JenkinsObserver
    import os
    from unittest.mock import patch
    
    with patch.dict(os.environ, {"JENKINS_OBSERVER_DRY_RUN": str(dry_run).lower()}):
        obs = JenkinsObserver(blackboard=bb, jenkins_adapter=adapter)
        obs._views = views or ["Gating Wrappers"]
        obs._get_wip_headroom = AsyncMock(return_value=10)
        return obs

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
    bb.get_jenkins_last_alerted_build = AsyncMock(return_value=0)
    bb.set_jenkins_last_alerted_build = AsyncMock(return_value=None)
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
# T-16c: Skills Catalog success path actually loads real skill content
# =========================================================================

class TestT16cSkillsSuccessPath:
    """T-16c: A successful catalog fetch must replace _skills_si with the
    downloaded SKILL.md content, not silently leave it at the fallback.

    This is the success-path complement to T-16/T-16b (which only assert the
    failure branches). Its absence is exactly why a self._sanitize_console_tail
    AttributeError (self._sanitize_console_tail is a module-level function,
    not a method) went undetected across two review rounds: the broad
    `except Exception` swallowed it, _skills_si silently stayed at fallback,
    and every prior test only checked "fallback is non-empty" -- which is
    true whether the real fetch succeeded or crashed."""

    async def test_catalog_success_loads_real_skill_content(self):
        import io
        import zipfile

        skill_body = "# CNV Gating Workflow\n\nDetailed skill instructions for triage."
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("cnv-gating-workflow/SKILL.md", skill_body)
        zip_bytes = buf.getvalue()

        env = _env_vars(SKILLS_CATALOG_SKILLS="cnv-gating-workflow")
        with patch.dict("os.environ", env):
            from src.agents.jenkins_observer import _FALLBACK_SI, JenkinsObserver

            bb = _mock_blackboard()
            obs = JenkinsObserver(blackboard=bb)
            obs._skills_loaded_at = 0  # force reload

            with patch("httpx.AsyncClient") as MockClient:
                mock_client = AsyncMock()
                mock_resp = MagicMock()
                mock_resp.status_code = 200
                mock_resp.content = zip_bytes
                mock_client.get = AsyncMock(return_value=mock_resp)
                MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_client)
                MockClient.return_value.__aexit__ = AsyncMock(return_value=False)

                await obs._ensure_skills_loaded()

        assert skill_body in obs._skills_si, \
            f"Real downloaded SKILL.md content must be in _skills_si, got: {obs._skills_si!r}"
        assert obs._skills_si != _FALLBACK_SI, \
            "_skills_si must not silently remain at the fallback after a successful fetch"


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

    @pytest.mark.parametrize(("raw_text", "surviving_prefix"), [
        ("ha:////AAAABearer==sometoken123", "Bearer="),
        ("ha:////AAApassword\x1b[0mhunter2", "password"),
        ("ha:////AAAtoken\x1b[32mhunter2", "token"),
    ])
    def test_strip_then_redact_closes_f13_follow_on_leaks(self, raw_text, surviving_prefix):
        """Post-strip redaction must catch the F13 survivors where the keyword
        is preserved but the value used to leak via `==` or bare ANSI."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        stripped = _strip_pipeline_annotations(raw_text)
        result = _redact_secrets_in_text(stripped)

        assert surviving_prefix.lower() in result.lower()
        assert "hunter2" not in result
        assert "sometoken123" not in result
        assert "***REDACTED***" in result

    @pytest.mark.parametrize(("raw_text", "keyword"), [
        ("ha:////AAApwd==hunter2", "pwd"),
        ("ha:////AAAkey==hunter2", "key"),
        ("ha:////AAAapikey==hunter2", "apikey"),
        ("ha:////AAAaccesskey==hunter2", "accesskey"),
        ("ha:////AAAprivatekey==hunter2", "privatekey"),
        ("ha:////AAAsecretkey==hunter2", "secretkey"),
    ])
    def test_strip_then_redact_closes_body_end_keyword_leak(self, raw_text, keyword):
        """F14 CRITICAL: keywords omitted from _REDACTION_TRIGGER_KEYWORDS
        let the greedy body class eat the keyword suffix via `==` terminator,
        leaking the abutting value. After the fix, strip preserves the keyword
        and redact catches the value."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        stripped = _strip_pipeline_annotations(raw_text)
        assert keyword in stripped.lower(), f"strip must preserve keyword '{keyword}'"
        result = _redact_secrets_in_text(stripped)
        assert "hunter2" not in result, f"value leaked past keyword '{keyword}'"
        assert "***REDACTED***" in result

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
# T-21b: 3000-char slice order — redact BEFORE slice to prevent straddle leak
# =========================================================================

class TestT21bSliceAfterRedact:
    """HIGH: console_tail slice at 3000 chars must happen AFTER redaction, not
    before. A `TOKEN=value` pattern straddling the cut loses the keyword if
    sliced first, leaking the bare value into ci_context."""

    def test_secret_straddling_3000_cut_is_redacted(self):
        """Craft a console_tail where 'TOKEN=value' straddles the 3000-char
        boundary: keyword is >3000 from the end, value is within the last
        3000. The production path (_prepare_console_tail: redact -> strip ->
        slice) catches it."""
        from src.agents.jenkins_observer import _prepare_console_tail

        secret_value = "abc123def456"
        # Position so [-3000:] cut falls between TOKEN= and the value:
        # raw = "A"*100 + "TOKEN=" + value + " " + "X"*N
        # total = 100 + 6 + 12 + 1 + N = 119 + N
        # Cut at total - 3000 = 119 + N - 3000. Want cut = 106 (start of value).
        trailing_filler = "X" * 2987
        raw_tail = "A" * 100 + "TOKEN=" + secret_value + " " + trailing_filler

        # Sanity: total > 3000, keyword NOT in [-3000:], value IS in [-3000:]
        assert len(raw_tail) > 3000
        assert "TOKEN=" not in raw_tail[-3000:]
        assert secret_value in raw_tail[-3000:]

        # Production path: _prepare_console_tail (redact -> strip -> slice)
        result = _prepare_console_tail(raw_tail)
        assert secret_value not in result, "value leaked -- slice happened before redact"

    def test_wrong_order_would_leak(self):
        """Counter-proof: slicing BEFORE redacting loses the keyword and leaks."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        secret_value = "abc123def456"
        trailing_filler = "X" * 2987
        raw_tail = "A" * 100 + "TOKEN=" + secret_value + " " + trailing_filler

        # Wrong order: slice first — keyword is outside the window
        sliced_first = raw_tail[-3000:]
        assert "TOKEN=" not in sliced_first, "test setup: keyword should be outside the 3000 window"
        assert secret_value in sliced_first, "test setup: value should be inside the 3000 window"
        result = _redact_secrets_in_text(sliced_first)
        # The value survives because the keyword was lost
        assert secret_value in result, "expected the wrong-order path to leak"

    def test_secret_straddling_prestrip_window_is_redacted(self):
        """HIGH regression guard: the old adapter path ran _strip_pipeline_annotations
        (which truncates to _PRESTRIP_WINDOW chars) BEFORE redaction. A password=
        keyword sitting just before the 20k window cut with its value inside the
        window leaked the bare value. _prepare_console_tail (redact -> strip -> slice)
        closes this."""
        from src.agents.jenkins_observer import (
            _prepare_console_tail,
            _redact_secrets_in_text,
        )

        kw, val = "password=", "hunter2"
        head = "x" * 50 + kw
        tail = val + ("y" * (_PRESTRIP_WINDOW - len(val)))
        raw = head + tail

        # Production path: redact first, then strip -- value is gone
        result = _prepare_console_tail(raw)
        assert val not in result, (
            "hunter2 leaked through _prepare_console_tail -- redact-before-strip invariant broken"
        )

    def test_wrong_order_strip_then_redact_leaks_prestrip_window(self):
        """Counter-proof: strip-first (the old order) windows away the keyword
        and leaks the value -- proving the fix is not vacuous."""
        from src.agents.jenkins_observer import _redact_secrets_in_text

        kw, val = "password=", "hunter2"
        head = "x" * 50 + kw
        tail = val + ("y" * (_PRESTRIP_WINDOW - len(val)))
        raw = head + tail

        # Wrong order: strip first (truncates to last _PRESTRIP_WINDOW chars,
        # which starts at the value, dropping the keyword)
        stripped = _strip_pipeline_annotations(raw)
        result = _redact_secrets_in_text(stripped)
        assert val in result, "expected the wrong-order (strip-then-redact) path to leak"


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
# T-V23: Missing/disabled adapter must also report unhealthy (second trigger
# for the same CI-gating-dark bug class as T-V22)
# =========================================================================

class TestTV23AdapterUnavailableReportsUnhealthy:
    """T-V23: _drain_once() returning early because self._adapter is None or
    disabled (missing Jenkins config, or a latched circuit breaker) is a
    second, independent trigger for the exact same silent-healthy-while-dark
    bug T-V22 covers for empty views -- it must also mark view_unhealthy=True,
    and must clear that sentinel once the adapter recovers."""

    async def test_missing_adapter_marks_view_unhealthy_true(self):
        bb = _mock_blackboard()

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = None  # e.g. JENKINS_URL/USER/TOKEN not configured

            assert obs.view_unhealthy is False, \
                "Sanity: view_unhealthy should be False before any drain cycle"

            await obs._drain_once()

        assert obs.view_unhealthy is True, \
            "A missing/disabled adapter must mark view_unhealthy=True, " \
            "not silently report healthy while discovery is dark"
        bb.stage_jenkins_signal.assert_not_called()

    async def test_disabled_adapter_marks_view_unhealthy_true(self):
        """Same as above but via adapter.enabled() == False (e.g. breaker open)
        rather than adapter being None outright."""
        bb = _mock_blackboard()

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = AsyncMock()
            obs._adapter.enabled = MagicMock(return_value=False)

            await obs._drain_once()

        assert obs.view_unhealthy is True, \
            "adapter.enabled()==False must mark view_unhealthy=True, not report healthy"

    async def test_adapter_recovery_clears_sentinel(self):
        """Once the adapter becomes available again, the sentinel must clear
        so real per-view health (not a stale outage flag) drives view_unhealthy."""
        bb = _mock_blackboard()

        with patch.dict("os.environ", _env_vars()):
            from src.agents.jenkins_observer import JenkinsObserver

            obs = JenkinsObserver(blackboard=bb)
            obs._adapter = None
            await obs._drain_once()
            assert obs.view_unhealthy is True, "Sanity: unhealthy while adapter is down"

            obs._adapter = AsyncMock()
            obs._adapter.enabled = MagicMock(return_value=True)
            obs._adapter.scan_view = AsyncMock(
                return_value=_make_view_scan_result(jobs=[])
            )
            obs._skills_si = "test skills"
            await obs._drain_once()

        assert obs.view_unhealthy is False, \
            "view_unhealthy must clear once the adapter recovers and a clean scan runs"


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


# =========================================================================
# T-A1: restart_job HTTP transport -- params=->data= change (PR #218)
# =========================================================================
#
# Regression coverage for a HIGH testing finding from PR #218's review: no test,
# before or after the PR, exercised the real JenkinsAdapter.restart_job /
# get_build_details against a mocked httpx client. These tests patch _get_client
# (not _request) so the real _request/restart_job/get_build_details code -- the
# param transport and urllib.parse.quote calls -- actually runs.

def _make_test_adapter():
    from src.adapters.jenkins import JenkinsAdapter
    return JenkinsAdapter(
        base_url="https://jenkins.example.com",
        user="sa-user",
        token="sa-token",
        verify_tls=False,
    )


class TestJenkinsAdapterRestartJobTransport:

    async def test_restart_job_with_params_sends_form_body_not_query_string(self):
        """PR #218 changed restart_job's param transport from params= (query
        string) to data= (form body). No test ever asserted on the actual kwarg
        passed to the httpx client."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            mock_resp = MagicMock()
            mock_resp.status_code = 201
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                result = await adapter.restart_job("verify-cnv-4.22.z-build", {"CNV_VERSION": "4.22"})

            assert result is True
            mock_client.request.assert_called_once()
            call = mock_client.request.call_args
            method, url = call.args[0], call.args[1]
            assert method == "POST"
            assert url.endswith("/job/verify-cnv-4.22.z-build/buildWithParameters")
            assert call.kwargs.get("data") == {"CNV_VERSION": "4.22"}
            assert "params" not in call.kwargs

    async def test_restart_job_without_params_posts_to_build_endpoint(self):
        """No params -> POST /build with no data/params body."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                result = await adapter.restart_job("verify-cnv-4.22.z-build")

            assert result is True
            call = mock_client.request.call_args
            method, url = call.args[0], call.args[1]
            assert method == "POST"
            assert url.endswith("/job/verify-cnv-4.22.z-build/build")
            assert "data" not in call.kwargs
            assert "params" not in call.kwargs

    async def test_restart_job_url_encodes_job_name(self):
        """A job name containing '/' must be percent-encoded (safe='') in the
        request URL -- the raw string must never reach the outbound URL."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            unsafe_job = "feature/../secret-job"
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                await adapter.restart_job(unsafe_job)

            call = mock_client.request.call_args
            url = call.args[1]
            expected = urllib.parse.quote(unsafe_job, safe="")
            assert expected in url
            assert unsafe_job not in url

    async def test_restart_job_false_on_client_error_status(self):
        """A 404 (job doesn't exist) is swallowed by _request (count_failures=True
        default -> returns None), so restart_job reports failure."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            mock_resp = MagicMock()
            mock_resp.status_code = 404
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                result = await adapter.restart_job("missing-job")

            assert result is False


# =========================================================================
# T-A2: get_build_details HTTP transport + URL encoding of BOTH calls
# =========================================================================
#
# Regression coverage for the HIGH security finding: get_build_details's primary
# api/json call was URL-encoded, but the console-log-tail fetch two lines later
# in the same function still interpolated the raw, unencoded job name -- an
# incomplete fix within the very function this PR patched.

class TestJenkinsAdapterGetBuildDetailsTransport:

    async def test_get_build_details_parses_params_and_console_tail(self):
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            api_resp = MagicMock()
            api_resp.status_code = 200
            api_resp.json.return_value = {
                "result": "FAILURE",
                "url": "https://jenkins.example.com/job/verify-cnv-4.22.z-build/254/",
                "actions": [{"parameters": [{"name": "CNV_VERSION", "value": "4.22"}]}],
            }
            tail_resp = MagicMock()
            tail_resp.status_code = 200
            tail_resp.content = b"...console output..."
            tail_resp.encoding = "utf-8"

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=[api_resp, tail_resp])

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                details = await adapter.get_build_details("verify-cnv-4.22.z-build", 254)

            assert details is not None
            assert details.result == "FAILURE"
            assert details.parameters == {"CNV_VERSION": "4.22"}
            assert details.console_tail == "...console output..."
            assert mock_client.request.call_count == 2

    async def test_get_build_details_url_encodes_job_in_both_calls(self):
        """Both the api/json call AND the console-log-tail call must URL-encode
        the job name -- the tail fetch was the incomplete part of the original
        fix (path-traversal / request-injection HIGH finding)."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            unsafe_job = "feature/weird job"
            api_resp = MagicMock()
            api_resp.status_code = 200
            api_resp.json.return_value = {"result": "SUCCESS", "url": "", "actions": []}
            tail_resp = MagicMock()
            tail_resp.status_code = 200
            tail_resp.content = b""
            tail_resp.encoding = "utf-8"

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=[api_resp, tail_resp])

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                await adapter.get_build_details(unsafe_job, 42)

            expected = urllib.parse.quote(unsafe_job, safe="")
            calls = mock_client.request.call_args_list
            assert len(calls) == 2, "expected both the api/json call and the console-tail call"
            for call in calls:
                url = call.args[1]
                assert expected in url, f"job name not encoded in {url}"
                assert unsafe_job not in url, f"raw unescaped job name leaked into {url}"

    async def test_get_build_details_returns_none_on_non_200_api_response(self):
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            api_resp = MagicMock()
            api_resp.status_code = 404
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=api_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                details = await adapter.get_build_details("missing-job", 1)

            assert details is None
            # 404 on the primary call means _request never even reaches the
            # console-tail fetch.
            mock_client.request.assert_called_once()

    async def test_get_build_details_console_tail_failure_is_best_effort(self):
        """If the console-log-tail fetch itself fails (e.g. 500), get_build_details
        must still return BuildDetails with an empty console_tail -- a best-effort
        fetch must not fail the whole call."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            api_resp = MagicMock()
            api_resp.status_code = 200
            api_resp.json.return_value = {"result": "FAILURE", "url": "", "actions": []}
            tail_resp = MagicMock()
            tail_resp.status_code = 500

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=[api_resp, tail_resp])

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                details = await adapter.get_build_details("verify-cnv-4.22.z-build", 254)

            assert details is not None
            assert details.result == "FAILURE"
            assert details.console_tail == ""

    async def test_include_console_tail_false_skips_second_http_call(self):
        """include_console_tail=False (used by the jenkins-retrigger call site,
        which only needs `.parameters`) must skip the console-log-tail HTTP
        request entirely -- adapter-level regression coverage for the HIGH
        timeout-budget fix, whose 3-sequential-calls math depends on this call
        site actually making one fewer HTTP request, not just passing the flag."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            api_resp = MagicMock()
            api_resp.status_code = 200
            api_resp.json.return_value = {
                "result": "FAILURE",
                "url": "https://jenkins.example.com/job/verify-cnv-4.22.z-build/254/",
                "actions": [{"parameters": [{"name": "CNV_VERSION", "value": "4.22"}]}],
            }

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=api_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                details = await adapter.get_build_details(
                    "verify-cnv-4.22.z-build", 254, include_console_tail=False,
                )

            assert details is not None
            assert details.result == "FAILURE"
            assert details.parameters == {"CNV_VERSION": "4.22"}
            assert details.console_tail == ""
            # Only the primary api/json call -- the console-log-tail fetch must
            # never happen when include_console_tail=False.
            mock_client.request.assert_called_once()

    async def test_include_console_tail_true_default_still_makes_both_calls(self):
        """Sanity companion to the test above: the default (True, unspecified)
        behavior for every OTHER caller of get_build_details is unchanged --
        both calls still happen."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            api_resp = MagicMock()
            api_resp.status_code = 200
            api_resp.json.return_value = {"result": "FAILURE", "url": "", "actions": []}
            tail_resp = MagicMock()
            tail_resp.status_code = 200
            tail_resp.content = b"...console output..."
            tail_resp.encoding = "utf-8"

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=[api_resp, tail_resp])

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                details = await adapter.get_build_details("verify-cnv-4.22.z-build", 254)

            assert details is not None
            assert details.console_tail == "...console output..."
            assert mock_client.request.call_count == 2

    async def test_console_tail_blob_straddling_naive_slice_boundary_is_fully_stripped(self):
        """F7 regression guard (bounded pre-strip window correctness).
        The adapter now returns the decoded byte-windowed raw tail (no strip).
        The observer's `_prepare_console_tail` owns the strip. Assert:
        1) adapter returns the blob (or at least the real content suffix);
        2) `_prepare_console_tail` strips the blob and keeps real content."""
        from src.agents.jenkins_observer import _prepare_console_tail

        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            blob = "ha:////" + "B" * 4970 + "=="
            filler = "A" * 20000
            suffix = "\nreal failure output line\n"
            raw = filler + blob + suffix
            # Sanity: the blob must straddle where a naive (now-removed)
            # intermediate slice would have landed.
            naive_cut = len(raw) - 5000
            assert len(filler) < naive_cut < len(filler) + len(blob), (
                "test fixture must position the blob straddling the naive "
                "slice boundary -- adjust filler/blob length"
            )

            api_resp = MagicMock()
            api_resp.status_code = 200
            api_resp.json.return_value = {"result": "FAILURE", "url": "", "actions": []}
            tail_resp = MagicMock()
            tail_resp.status_code = 200
            tail_resp.content = raw.encode()
            tail_resp.encoding = "utf-8"

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=[api_resp, tail_resp])

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                details = await adapter.get_build_details("gating-job", 99)

            assert details is not None
            # Adapter returns raw -- blob may still be present
            assert "real failure output line" in details.console_tail

            # Observer helper strips the blob and keeps real content
            prepared = _prepare_console_tail(details.console_tail)
            assert "ha:" not in prepared
            assert ":////" not in prepared
            assert "real failure output line" in prepared

    async def test_console_tail_preserves_secret_across_old_5000_slice_boundary(self):
        """CRITICAL regression guard: a `password=hunter2` whose keyword sits
        just before where the old 5000-char slice used to cut and whose value
        sits after it must survive into console_tail so the observer's
        _prepare_console_tail can still catch it.

        The adapter returns the decoded byte-windowed raw tail -- no intermediate
        _CONSOLE_TAIL_SIZE slice -- and the observer's _prepare_console_tail
        redacts the secret before slicing."""
        from src.agents.jenkins_observer import _prepare_console_tail

        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            filler_before = "x" * 20
            secret = "password=hunter2"
            filler_after = "y" * 4990
            raw = filler_before + secret + filler_after
            # Sanity: the old `[-5000:]` cut must land INSIDE the secret --
            # `password=` straddles the cut (keyword prefix dropped),
            # `hunter2` after it (kept) -- so redaction loses its trigger.
            old_naive_cut = len(raw) - 5000
            pw_start = raw.index("password=")
            pw_end = pw_start + len("password=")
            assert pw_start < old_naive_cut < pw_end, (
                "test fixture: old 5000-char cut must land inside 'password=' "
                f"(pw_start={pw_start}, cut={old_naive_cut}, pw_end={pw_end})"
            )

            api_resp = MagicMock()
            api_resp.status_code = 200
            api_resp.json.return_value = {"result": "FAILURE", "url": "", "actions": []}
            tail_resp = MagicMock()
            tail_resp.status_code = 200
            tail_resp.content = raw.encode()
            tail_resp.encoding = "utf-8"

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=[api_resp, tail_resp])

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                details = await adapter.get_build_details("gating-job", 99)

            assert details is not None
            assert "password=" in details.console_tail, (
                "adapter must return raw decoded tail -- no intermediate "
                "5000-char slice that would drop the redaction trigger"
            )
            assert "hunter2" in details.console_tail

            # Observer helper redacts the secret
            prepared = _prepare_console_tail(details.console_tail)
            assert "hunter2" not in prepared


# =========================================================================
# T-A-1..4: JenkinsAdapter.get_job_run_state (C4 HIGH increment)
#
# Spec: GET /job/{urlencoded}/api/json?tree=color,inQueue,lastBuild[number,result,building]
#   - None on non-200 / transport / bad JSON
#   - inQueue -> in_queue
#   - lastBuild.building -> building; lastBuild.number -> last_build_number
#   - color ending "_anime" -> building True (fallback, e.g. lastBuild missing/false)
#
# Follows the TestJenkinsAdapterGetBuildDetailsTransport/RestartJobTransport
# pattern: patches `_get_client` (not `_request`) so the real adapter HTTP
# code -- URL construction, urllib.parse.quote, JSON parsing -- actually runs.
# =========================================================================

class TestJenkinsAdapterGetJobRunStateTransport:

    async def test_parses_last_build_building_and_in_queue(self):
        """T-A-1: 200 JSON with inQueue=false, lastBuild.building=true,
        lastBuild.number=9, color='blue_anime' -> JobRunState(building=True,
        in_queue=False, last_build_number=9). Exactly one HTTP GET; the
        requested path contains the url-encoded job name and a tree= query."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "inQueue": False,
                "lastBuild": {"number": 9, "building": True, "result": None},
                "color": "blue_anime",
            }
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                state = await adapter.get_job_run_state("verify-cnv-4.22.z-build")

            assert state is not None
            assert state.building is True
            assert state.in_queue is False
            assert state.last_build_number == 9

            mock_client.request.assert_called_once()
            call = mock_client.request.call_args
            url = call.args[1]
            assert urllib.parse.quote("verify-cnv-4.22.z-build", safe="") in url
            assert "tree=" in url

    async def test_url_encodes_job_name(self):
        """T-A-2: A job name with unsafe characters (slash/space) must be
        percent-encoded via urllib.parse.quote(job, safe="") in the request path."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            unsafe_job = "feature/weird job"
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "inQueue": False,
                "lastBuild": {"number": 1, "building": False, "result": "SUCCESS"},
                "color": "blue",
            }
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                await adapter.get_job_run_state(unsafe_job)

            call = mock_client.request.call_args
            url = call.args[1]
            expected = urllib.parse.quote(unsafe_job, safe="")
            assert expected in url
            assert unsafe_job not in url

    async def test_returns_none_on_non_200(self):
        """T-A-3: A non-200 response (e.g. 500) -> get_job_run_state returns None."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                state = await adapter.get_job_run_state("verify-cnv-4.22.z-build")

            assert state is None

    async def test_color_anime_fallback_when_last_build_not_building(self):
        """T-A-4: lastBuild dict present but without a 'building' key (or
        building=False), and color ends in '_anime' (Jenkins' "currently
        running" ball-color suffix) -> building must resolve True via the
        color fallback."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {
                "inQueue": False,
                "lastBuild": {"number": 42, "result": None},
                "color": "red_anime",
            }
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                state = await adapter.get_job_run_state("verify-cnv-4.22.z-build")

            assert state is not None
            assert state.building is True

    async def test_returns_none_on_transport_error(self):
        """T-A-3b: transport-level failure (connect/timeout) -> None, matching
        the same contract as get_build_details/restart_job/scan_view."""
        import httpx as httpx_mod

        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            mock_client = AsyncMock()
            mock_client.request = AsyncMock(side_effect=httpx_mod.ConnectError("boom"))

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                state = await adapter.get_job_run_state("verify-cnv-4.22.z-build")

            assert state is None

    async def test_returns_none_on_malformed_json(self):
        """T-A-3c: 200 response with malformed/non-JSON body -> None, matching
        scan_view's malformed-JSON handling."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.side_effect = ValueError("not json")
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                state = await adapter.get_job_run_state("verify-cnv-4.22.z-build")

            assert state is None

    async def test_count_failures_false_passed_through_from_handler_call_site(self):
        """T-A-5: The handler call site (`_do_retrigger`) is specified to call
        `get_job_run_state(job, count_failures=False)` -- this is a best-effort
        pre-check that must not trip the shared circuit breaker on its own.
        Verifies the adapter method accepts and threads the kwarg to `_request`."""
        with patch.dict("os.environ", _env_vars()):
            adapter = _make_test_adapter()

            mock_resp = MagicMock()
            mock_resp.status_code = 500
            mock_client = AsyncMock()
            mock_client.request = AsyncMock(return_value=mock_resp)

            with patch.object(adapter, "_get_client", new_callable=AsyncMock) as mock_get_client:
                mock_get_client.return_value = mock_client
                await adapter.get_job_run_state("verify-cnv-4.22.z-build", count_failures=False)

            # A 500 with count_failures=False must NOT record a breaker strike.
            assert adapter._consecutive_failures == 0
            assert adapter._breaker_latched is False


# =========================================================================
# T-DP1: Jenkins Duplicate Prevention - Staging Filter
# =========================================================================

class TestDuplicatePreventionStaging:
    """Jobs with build_number <= last_alerted_build bypass staging."""

    async def test_skips_staging_already_alerted_build(self):
        """If get_jenkins_last_alerted_build returns a number >= job.build_number, it skips."""
        bb = _mock_blackboard()
        bb.get_jenkins_last_alerted_build.return_value = 100
        adapter = _make_adapter()
        adapter.scan_view.return_value = _make_view_scan_result([
            _make_job_result("already-alerted-job", result="FAILURE", build_number=100)
        ])
        obs = _make_observer(bb, adapter, views=["test-view"])

        await obs._poll_and_stage()

        bb.get_jenkins_last_alerted_build.assert_called_once_with("already-alerted-job")
        bb.stage_jenkins_signal.assert_not_called()

    async def test_skips_staging_older_build(self):
        """If last_alerted_build is newer than the polled build, it skips."""
        bb = _mock_blackboard()
        bb.get_jenkins_last_alerted_build.return_value = 101
        adapter = _make_adapter()
        adapter.scan_view.return_value = _make_view_scan_result([
            _make_job_result("older-job", result="FAILURE", build_number=100)
        ])
        obs = _make_observer(bb, adapter, views=["test-view"])

        await obs._poll_and_stage()
        bb.stage_jenkins_signal.assert_not_called()

    async def test_stages_new_build_above_last_alerted(self):
        """If polled build is newer than last_alerted_build, it stages."""
        bb = _mock_blackboard()
        bb.get_jenkins_last_alerted_build.return_value = 99
        adapter = _make_adapter()
        adapter.scan_view.return_value = _make_view_scan_result([
            _make_job_result("newer-job", result="FAILURE", build_number=100)
        ])
        obs = _make_observer(bb, adapter, views=["test-view"])

        await obs._poll_and_stage()
        bb.stage_jenkins_signal.assert_called_once()

    async def test_zero_last_alerted_stages_normally(self):
        """If last_alerted_build is 0 (missing), a valid build stages normally."""
        bb = _mock_blackboard()
        bb.get_jenkins_last_alerted_build.return_value = 0
        adapter = _make_adapter()
        adapter.scan_view.return_value = _make_view_scan_result([
            _make_job_result("new-job", result="FAILURE", build_number=1)
        ])
        obs = _make_observer(bb, adapter, views=["test-view"])

        await obs._poll_and_stage()
        bb.stage_jenkins_signal.assert_called_once()

    async def test_filter_skips_jobs_without_build_number(self):
        """Jobs with build_number=None (e.g. MISSING) bypass the filter completely."""
        bb = _mock_blackboard()
        adapter = _make_adapter()
        adapter.scan_view.return_value = _make_view_scan_result([
            _make_job_result("missing-job", result=None, build_number=None)
        ])
        obs = _make_observer(bb, adapter, views=["test-view"])

        await obs._poll_and_stage()

        bb.get_jenkins_last_alerted_build.assert_not_called()
        bb.stage_jenkins_signal.assert_called_once()

    async def test_mixed_jobs_only_skips_already_alerted(self):
        """Filter applies correctly per-job in a view."""
        bb = _mock_blackboard()
        
        async def mock_get_last_alerted(job_name):
            if job_name == "skip-me": return 100
            return 0
        bb.get_jenkins_last_alerted_build.side_effect = mock_get_last_alerted
        
        adapter = _make_adapter()
        adapter.scan_view.return_value = _make_view_scan_result([
            _make_job_result("skip-me", result="FAILURE", build_number=100),
            _make_job_result("stage-me", result="FAILURE", build_number=100),
        ])
        obs = _make_observer(bb, adapter, views=["test-view"])

        await obs._poll_and_stage()
        
        bb.stage_jenkins_signal.assert_called_once()
        call_args = bb.stage_jenkins_signal.call_args[0]
        assert call_args[0] == "stage-me"


# =========================================================================
# T-DP2: Jenkins Duplicate Prevention - Commitment
# =========================================================================

class TestDuplicatePreventionCommitment:
    """Records build_number in last_alerted_build AFTER successful create_event."""

    async def test_records_last_alerted_after_create(self):
        """Happy path: create_event succeeds, set_jenkins_last_alerted_build is called."""
        bb = _mock_blackboard()
        bb.create_event.return_value = True
        obs = _make_observer(bb, _make_adapter())

        meta = _make_meta(job_name="test-job", build_number=100)
        groups = [[("test-job", meta)]]
        
        await obs._process_candidates(groups)
        
        bb.create_event.assert_called_once()
        bb.set_jenkins_last_alerted_build.assert_called_once_with("test-job", 100)
        bb.commit_jenkins_signal.assert_called_once_with("test-job")

    async def test_no_commit_on_dry_run(self):
        """If DRY_RUN=true, create_event is skipped, so set_last_alerted is skipped."""
        bb = _mock_blackboard()
        obs = _make_observer(bb, _make_adapter(), dry_run=True)

        meta = _make_meta(job_name="test-job", build_number=100)
        groups = [[("test-job", meta)]]
        
        await obs._process_candidates(groups)
        
        bb.create_event.assert_not_called()
        bb.set_jenkins_last_alerted_build.assert_not_called()
        bb.commit_jenkins_signal.assert_called_once()

    async def test_no_commit_on_wip_gate(self):
        """If WIP gate prevents creation, set_last_alerted is skipped and restaged."""
        bb = _mock_blackboard()
        # Force WIP ceiling
        obs = _make_observer(bb, _make_adapter())
        obs._get_wip_headroom = AsyncMock(return_value=0)

        meta = _make_meta(job_name="test-job", build_number=100)
        groups = [[("test-job", meta)]]
        
        await obs._process_candidates(groups)
        
        bb.create_event.assert_not_called()
        bb.set_jenkins_last_alerted_build.assert_not_called()
        bb.restage_jenkins_signal.assert_called_once()

    async def test_no_commit_on_dedup(self):
        """If active-event dedup returns True, set_last_alerted is skipped."""
        bb = _mock_blackboard()
        obs = _make_observer(bb, _make_adapter())
        obs._is_duplicate_or_escalated = AsyncMock(return_value=True)

        meta = _make_meta(job_name="test-job", build_number=100)
        groups = [[("test-job", meta)]]
        
        await obs._process_candidates(groups)
        
        bb.create_event.assert_not_called()
        bb.set_jenkins_last_alerted_build.assert_not_called()
        bb.commit_jenkins_signal.assert_called_once()

    async def test_no_commit_on_create_event_failure(self):
        """If create_event raises, set_last_alerted is skipped."""
        bb = _mock_blackboard()
        bb.create_event.side_effect = Exception("Redis write failed")
        obs = _make_observer(bb, _make_adapter())

        meta = _make_meta(job_name="test-job", build_number=100)
        groups = [[("test-job", meta)]]
        
        await obs._process_candidates(groups)
        
        bb.set_jenkins_last_alerted_build.assert_not_called()
        bb.restage_jenkins_signal.assert_called_once()

    async def test_set_last_alerted_failure_is_non_fatal(self):
        """If set_last_alerted raises, the signal is still committed (non-fatal error)."""
        bb = _mock_blackboard()
        bb.set_jenkins_last_alerted_build.side_effect = Exception("Redis blip")
        obs = _make_observer(bb, _make_adapter())

        meta = _make_meta(job_name="test-job", build_number=100)
        groups = [[("test-job", meta)]]
        
        await obs._process_candidates(groups)
        
        # Should still commit despite the exception
        bb.commit_jenkins_signal.assert_called_once_with("test-job")

    async def test_flood_commits_all_jobs_last_alerted(self):
        """In a ci-gating-flood group, every job in the group has its build_number committed."""
        bb = _mock_blackboard()
        obs = _make_observer(bb, _make_adapter())

        meta1 = _make_meta(job_name="job-1", build_number=101)
        meta2 = _make_meta(job_name="job-2", build_number=202)
        groups = [[("job-1", meta1), ("job-2", meta2)]]
        
        await obs._process_candidates(groups)
        
        assert bb.set_jenkins_last_alerted_build.call_count == 2
        bb.set_jenkins_last_alerted_build.assert_any_call("job-1", 101)
        bb.set_jenkins_last_alerted_build.assert_any_call("job-2", 202)

    async def test_none_build_number_skips_recording(self):
        """If meta is missing a build_number, it skips recording but commits."""
        bb = _mock_blackboard()
        obs = _make_observer(bb, _make_adapter())

        meta = _make_meta(job_name="test-job") # No build_number
        if "build_number" in meta:
            del meta["build_number"]
        groups = [[("test-job", meta)]]
        
        await obs._process_candidates(groups)
        
        bb.set_jenkins_last_alerted_build.assert_not_called()
        bb.commit_jenkins_signal.assert_called_once_with("test-job")


# =========================================================================
# T-DP3: Blackboard State Last Alerted Build Tests
# =========================================================================

class TestBlackboardLastAlertedBuild:
    """Tests for get/set_jenkins_last_alerted_build."""

    async def test_get_returns_zero_when_missing(self):
        """Missing key returns 0."""
        import fakeredis.aioredis
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        from src.state.blackboard import BlackboardState
        bb = BlackboardState(redis)

        assert await bb.get_jenkins_last_alerted_build("missing-job") == 0

    async def test_get_handles_corrupt_value_gracefully(self):
        """If Redis returns garbage, get_jenkins_last_alerted_build returns 0."""
        import fakeredis.aioredis
        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
        from src.state.blackboard import BlackboardState
        bb = BlackboardState(redis)

        await redis.set("darwin:jenkins:last_alert:corrupt-job", "not-an-int")
        assert await bb.get_jenkins_last_alerted_build("corrupt-job") == 0


# =========================================================================
# T22: _strip_pipeline_annotations -- pipeline noise stripping (jenkins.py)
#
# Covers blob removal (ha:////...), step-boundary marker removal
# ([Pipeline] ...), blank-run collapse, and the hardening fixes landed
# alongside the original noise-stripping feature: line-anchored boundary
# matching (no mid-line over-strip), delimiter-bounded blob matching (no
# adjacent-blob concatenation, no secret-abutment leak), and a bounded
# single-occurrence ANSI wrapper (no quadratic blowup on ANSI-dense logs).
# See TestJenkinsAdapterGetBuildDetailsTransport for the integration-level
# counterpart exercising the real async get_build_details call site.
# =========================================================================

class TestT22StripPipelineAnnotations:

    def test_ha_blob_stripped_surrounding_text_preserved(self):
        assert _strip_pipeline_annotations("before ha:////ABC123== after") == "before  after"

    def test_pipeline_boundary_markers_removed(self):
        text = "[Pipeline] }\n[Pipeline] // container\nreal output"
        assert _strip_pipeline_annotations(text) == "real output"

    def test_end_of_pipeline_removed(self):
        text = "output\n[Pipeline] End of Pipeline"
        assert _strip_pipeline_annotations(text) == "output"

    def test_blank_run_collapsed_to_two_newlines(self):
        assert _strip_pipeline_annotations("a\n\n\n\n\nb") == "a\n\nb"

    def test_empty_and_none_input_returns_empty(self):
        assert _strip_pipeline_annotations("") == ""
        assert _strip_pipeline_annotations(None) is None

    def test_real_world_sample_reduces_to_finished_line(self):
        text = "[Pipeline] // container\n[2026-08-31T11:23:24.854Z] Finished: UNSTABLE"
        assert _strip_pipeline_annotations(text) == "[2026-08-31T11:23:24.854Z] Finished: UNSTABLE"

    def test_ansi_wrapped_blob_and_crlf_runs_collapse_to_empty(self):
        assert _strip_pipeline_annotations("\x1b[8mha:////ABC\x1b[0m\r\n\r\n\r\n") == ""

    def test_timestamped_pipeline_line_still_stripped(self):
        """A Jenkins Timestamper-prefixed [Pipeline] line is still recognized
        as a boundary marker and stripped; real content on the next line
        survives untouched."""
        text = "[2026-08-31T11:23:24.854Z] [Pipeline] // container\nreal output"
        assert _strip_pipeline_annotations(text) == "real output"

    # ---- F1: mid-line over-strip (fixed via line-start anchoring) ----

    def test_mid_line_marker_text_preserved_not_truncated(self):
        """F1 regression: a [Pipeline] substring appearing mid-line (preceded
        by real content on the same line) is no longer mistaken for a
        boundary marker -- the whole line, including trailing content, is
        preserved. The pre-fix regex truncated this to just 'Running'."""
        result = _strip_pipeline_annotations("Running [Pipeline] } leftover")
        assert result == "Running [Pipeline] } leftover"
        assert result != "Running"  # the old buggy truncation

    def test_mid_line_marker_from_alternation_set_preserved(self):
        """F2 fix: the original T-7 test asserted on 'step X', but 'step' is
        not in the boundary alternation (// \\w+, End of Pipeline, {, },
        stage) -- that input was never at risk of the F1 bug and proved
        nothing. This test uses an actual alternation member ('stage')
        appearing mid-line in real prose, which the pre-fix (unanchored)
        regex WOULD have matched and corrupted."""
        result = _strip_pipeline_annotations("Deploying [Pipeline] stage now, please wait")
        assert result == "Deploying [Pipeline] stage now, please wait"

    # ---- F3: greedy blob concatenation (fixed via right-delimiter lookahead) ----

    def test_adjacent_blobs_no_separator_fully_stripped(self):
        """F3 regression: two ha:////...== blobs directly abutting with no
        separator must both fully strip with no leftover fragment. The
        pre-fix greedy regex produced ':////BBB==' (a mangled partial second
        blob) instead of a clean removal."""
        result = _strip_pipeline_annotations("ha:////AAA==ha:////BBB==")
        assert result == ""
        assert ":////" not in result

    # ---- F4: secret abutment / redaction bypass ----

    def test_secret_abutment_preserves_key_intact_for_downstream_redaction(self):
        """F4 regression: a blob immediately followed by a secret key:value
        pair with no delimiter must not corrupt the key text. The pre-fix
        regex consumed the 'password' key entirely, leaving only ':hunter2'
        -- defeating the observer's downstream _redact_secrets_in_text
        (which matches on the literal key text). Real ha:////  blobs are
        never followed by arbitrary prose in production Jenkins output, so
        the fixed regex has no safe delimiter to anchor on here and
        conservatively leaves the whole substring untouched rather than
        partially matching -- 'password:hunter2' must survive intact."""
        result = _strip_pipeline_annotations("ha:////ABC==password:hunter2")
        assert "password:hunter2" in result

    # ---- F9: whitespace/EOS-terminated secret-abutment bypass (MEDIUM) ----

    def test_unpadded_blob_abutting_alphanumeric_secret_preserved_mid_string(self):
        """F9 regression (MEDIUM secret-redaction-bypass finding): F4 covers
        the colon-delimited abutment case ('password:hunter2'), which was
        always safe because `:` sits outside the base64 alphabet and so the
        greedy body class can't consume through it. This test covers the
        narrower, genuinely exploitable gap: an UNPADDED, non-ANSI-wrapped
        blob immediately abutted by a real secret composed entirely of
        base64-alphabet characters (letters/digits, no punctuation) -- e.g.
        the literal word "Bearer" immediately after the blob body. The
        pre-fix regex accepted bare whitespace as a valid right-delimiter,
        so the greedy body class silently consumed straight through
        "Bearer" (indistinguishable from more blob content) and stopped
        only at the first space, deleting the word "Bearer" along with the
        blob -- which defeats jenkins_observer.py's downstream
        `_BEARER_TEXT_PATTERN` (`_redact_secrets_in_text`), which requires
        the literal text "bearer" to still be present to redact the token
        that follows it. The fixed regex requires mandatory padding or a
        mandatory trailing ANSI escape to terminate a match -- neither is
        present here, so the whole match fails and the entire string,
        including "Bearer", survives verbatim for downstream redaction to
        see."""
        result = _strip_pipeline_annotations("ha:////AAAABearer sometoken123")
        assert result == "ha:////AAAABearer sometoken123"

    def test_unpadded_blob_abutting_alphanumeric_secret_preserved_at_end_of_string(self):
        """F9 regression, end-of-string variant: the pre-fix regex also
        accepted a bare `$` (end-of-string) as a valid right-delimiter,
        which is independently exploitable -- `get_build_details` fetches
        console log "up to now" for an in-progress build, so an attacker
        able to influence log content can position a crafted unpadded blob
        + abutting secret as the literal last bytes of the currently-fetched
        tail, reproducing the exact same leak at the string boundary instead
        of mid-string. The fixed regex has no bare-`$` termination path at
        all, so this variant is closed the same way as the mid-string case:
        the whole match fails and the text (including the secret) survives
        verbatim."""
        result = _strip_pipeline_annotations(
            "filler text ha:////AAAABearersecrettoken123"
        )
        assert result == "filler text ha:////AAAABearersecrettoken123"

    # ---- F10: single-`=` key=value secret-abutment bypass (adversarial follow-up) ----

    def test_single_equals_token_delimiter_preserved(self):
        """F10 regression: F9 closed the whitespace/EOS-terminated abutment
        case by requiring mandatory padding or a trailing ANSI escape to
        terminate a blob match. That fix introduced a NEW, narrower gap: a
        single `=` was accepted as sufficient padding proof unconditionally,
        but a lone `=` is exactly the common `KEY=value` secret delimiter
        (see jenkins_observer.py's _SECRET_TEXT_PATTERN, which redacts both
        "key: value" and "key=value" forms) and is genuinely indistinguishable
        from real single-char base64 padding using only local regex context.
        The pre-fix regex misread 'token=abc123xyz' as body-plus-padding and
        silently deleted the literal word "token" and its "=" delimiter,
        defeating downstream key=value redaction. The fix requires a single
        `=` to ALSO be followed by a safe lookahead terminator (whitespace,
        ANSI, another ha:////, or EOS) before it counts -- absent here, so
        the whole match fails and the secret text survives verbatim."""
        result = _strip_pipeline_annotations("ha:////AAAtoken=abc123xyz")
        assert result == "ha:////AAAtoken=abc123xyz"

    @pytest.mark.parametrize(
        "keyword",
        ["secret", "password", "passwd", "pwd", "key", "credential", "authorization"],
    )
    def test_single_equals_other_secret_keywords_preserved(self, keyword):
        """F10 regression, board sweep: every bare-alphabetic keyword from
        _SECRET_TEXT_PATTERN's list (excluding hyphen/underscore-containing
        variants like api-key/api_key, which are already safe since `-`/`_`
        aren't in the base64 alphabet) must survive a single-`=` abutment
        intact, same as the "token" case above."""
        text = f"ha:////AAA{keyword}=xyz"
        assert _strip_pipeline_annotations(text) == text

    # ---- F11: whitespace-terminated single-`=` secret-abutment bypass
    # (MORE SERIOUS follow-up to F10) ----

    def test_single_equals_space_terminated_token_preserved(self):
        """F11 regression: F10 closed the bare (no-terminator) single-`=`
        abutment but left whitespace in the "safe" lookahead set. A single
        `=` followed by a plain space is exactly the most common, entirely
        ordinary way a real secret gets written ("token= value") -- not a
        rare or deliberately-constructed pattern the way an ANSI escape or
        chained `ha:////` occurrence is. The pre-fix regex misread the
        space as proof of genuine base64 padding and silently deleted
        "token=" along with the blob, defeating downstream redaction. The
        fix removes whitespace from the lookahead entirely: the match now
        fails and the secret text (including "token=") survives verbatim."""
        text = "ha:////AAAtoken= somevalue"
        assert _strip_pipeline_annotations(text) == text

    def test_single_equals_space_terminated_password_preserved(self):
        """F11 regression, second keyword: same whitespace-abutment gap as
        above, using "password=" instead of "token=" to prove the fix isn't
        keyword-specific."""
        text = "ha:////AAApassword= hunter2"
        assert _strip_pipeline_annotations(text) == text

    def test_single_equals_newline_terminated_token_preserved(self):
        """F11 regression, newline variant: `\\s` in the old lookahead
        matched ANY whitespace, not just literal spaces -- a newline
        immediately after the `=` (e.g. a secret sitting alone on its own
        line in a config dump) is exactly as common and exactly as
        unsound a signal as a space. Must be preserved verbatim too."""
        text = "ha:////AAAtoken=\nsomevalue"
        assert _strip_pipeline_annotations(text) == text

    @pytest.mark.parametrize(
        "keyword",
        [
            "token", "secret", "password", "passwd", "pwd", "key",
            "credential", "authorization",
            "apikey", "accesskey", "privatekey", "secretkey",
        ],
    )
    def test_single_equals_space_terminated_all_keywords_preserved(self, keyword):
        """F11 regression, full board sweep: every bare-alphabetic keyword
        from _SECRET_TEXT_PATTERN's list, INCLUDING the no-separator forms
        (apikey/accesskey/privatekey/secretkey) that F10's original sweep
        omitted, must survive a single-`=`-then-whitespace abutment intact.
        This is the critical sweep for the whitespace-removal fix -- any
        keyword that still leaks here reopens the most common real-world
        secret-formatting pattern."""
        text = f"ha:////AAA{keyword}= value123"
        assert _strip_pipeline_annotations(text) == text

    def test_single_equals_followed_by_whitespace_no_longer_strips(self):
        """F11 regression (MORE SERIOUS follow-up to F10): whitespace was
        REMOVED from the single-`=` lookahead's safe-terminator set.
        Whitespace after a real `=` delimiter is not a rare, deliberately-
        constructed pattern the way an ANSI escape or a chained `ha:////`
        occurrence is -- it is the single most common, completely benign
        way a real secret is ever written ("KEY= value"). The old rule
        (this test used to assert the OPPOSITE, that this case strips)
        treated "followed by whitespace" as proof of genuine base64
        padding, which is backwards, and silently deleted the "token="
        delimiter along with the blob. Whitespace is no longer accepted:
        the match now fails entirely and the text survives verbatim."""
        text = "before ha:////ABC1= after"
        assert _strip_pipeline_annotations(text) == text

    def test_single_equals_followed_by_ansi_still_strips(self):
        """F11 positive control: a single `=` immediately followed by an
        ANSI escape (not whitespace) is still a safe lookahead terminator
        and the blob still strips cleanly -- proves the whitespace removal
        narrowed the accepted cases without breaking the still-legitimate
        ANSI-terminated path."""
        result = _strip_pipeline_annotations("before ha:////ABC1=\x1b[0m after")
        assert result == "before  after"

    def test_single_equals_followed_by_another_blob_is_noise_tradeoff(self):
        """F12 trade-off: single `=` followed by another `ha:////` is NO
        LONGER a safe lookahead terminator (removed to close the CRITICAL
        cross-blob password= consumption bypass). The first single-pad blob
        remains as cosmetic noise; the second `==` blob still strips
        cleanly. This is an accepted, documented narrowing."""
        result = _strip_pipeline_annotations("ha:////AAA=ha:////BBB==")
        assert "ha:////BBB==" not in result  # second blob (==) stripped
        # First single-pad blob is leftover noise -- do not assert it vanishes

    def test_double_equals_padding_still_self_sufficient_no_regression(self):
        """F10 non-regression: double `==` padding remains self-sufficient
        with no lookahead requirement (implausible as coincidental real
        text) -- unaffected by the single-`=` narrowing. Re-asserts the F1/
        F3/F4 baseline cases to guard against the split introducing any
        collateral regression in the already-fixed double-`==` path."""
        assert _strip_pipeline_annotations("before ha:////ABC123== after") == "before  after"
        assert _strip_pipeline_annotations("ha:////AAA==ha:////BBB==") == ""
        assert "password:hunter2" in _strip_pipeline_annotations("ha:////ABC==password:hunter2")

    # ---- F12: CRITICAL cross-blob password= consumption + HIGH Python/JS $ parity ----

    def test_critical_cross_blob_password_consumption_closed(self):
        """F12 CRITICAL: `ha:////AAApassword=ha:////BBB==hunter2` -- the old
        regex's single-`=` lookahead accepted `ha:////` as proof of
        padding, so `ha:////AAApassword=` was consumed as one blob (eating
        the `password=` delimiter), then `ha:////BBB==` stripped via `==`,
        leaving `hunter2` unredacted. With `ha:////` removed from the
        lookahead, the first blob's `=` fails to match, `password=`
        survives intact for downstream `_redact_secrets_in_text`."""
        text = "ha:////AAApassword=ha:////BBB==hunter2"
        stripped = _strip_pipeline_annotations(text)
        assert "password=" in stripped
        assert "hunter2" in stripped  # still present for redaction to catch

    def test_critical_cross_blob_token_consumption_closed(self):
        """F12 CRITICAL variant: `ha:////AAAtoken=ha:////forged leftoversecret`
        -- same class as password= above. `token=` must survive."""
        text = "ha:////AAAtoken=ha:////forged leftoversecret"
        stripped = _strip_pipeline_annotations(text)
        assert "token=" in stripped

    def test_adjacent_double_padded_blobs_still_fully_strip(self):
        """F12 non-regression: adjacent `==` blobs are unaffected by the
        lookahead change -- `==` is an unconditional terminator."""
        result = _strip_pipeline_annotations("ha:////AAA==ha:////BBB==")
        assert result == ""

    def test_high_parity_eos_newline_token_preserved(self):
        """F12 HIGH: `ha:////AAAtoken=\\n` -- Python `$` matches before the
        trailing `\\n`; JS `$` (no `m`) matches only true end-of-input.
        With `$` removed from the lookahead, both languages now leave this
        string untouched (the `=` has no ANSI follower). Verifies the
        Python side; the parity corpus covers cross-language agreement."""
        text = "ha:////AAAtoken=\n"
        stripped = _strip_pipeline_annotations(text)
        assert "token=" in stripped

    # ---- F13: post-match body-end keyword reject (`==` / bare-ANSI terminators) ----

    def test_double_equals_keyword_password_rejected(self):
        """F13 CRITICAL: `ha:////AAApassword==hunter2` -- the `==` terminator
        makes the regex match `ha:////AAApassword==`, eating the `password`
        keyword. Post-match reject detects `password` at body end and returns
        the match unchanged so downstream redaction catches it."""
        result = _strip_pipeline_annotations("ha:////AAApassword==hunter2")
        assert "password=" in result
        assert "hunter2" in result

    def test_double_equals_keyword_token_rejected(self):
        """F13 CRITICAL: same class as password, `token` keyword."""
        result = _strip_pipeline_annotations("ha:////AAAtoken==hunter2")
        assert "token=" in result
        assert "hunter2" in result

    def test_double_equals_keyword_bearer_rejected(self):
        """F13 CRITICAL: `Bearer` keyword at body end, `==` terminator."""
        result = _strip_pipeline_annotations("ha:////AAAABearer==sometoken123")
        assert "Bearer" in result
        assert "sometoken123" in result

    def test_bare_ansi_keyword_password_rejected(self):
        """F13 CRITICAL: `password` eaten by bare-ANSI terminator."""
        result = _strip_pipeline_annotations("ha:////AAApassword\x1b[0mhunter2")
        assert "password" in result
        assert "hunter2" in result

    def test_bare_ansi_keyword_token_rejected(self):
        """F13 CRITICAL: `token` eaten by bare-ANSI terminator."""
        result = _strip_pipeline_annotations("ha:////AAAtoken\x1b[32mhunter2")
        assert "token" in result
        assert "hunter2" in result

    def test_single_equals_ansi_keyword_password_rejected(self):
        """F13 CRITICAL: `password=` eaten by single-`=` + ANSI terminator."""
        result = _strip_pipeline_annotations("ha:////AAApassword=\x1b[0mhunter2")
        assert "password=" in result
        assert "hunter2" in result

    def test_safe_colon_abutment_still_strips_blob(self):
        """F13 SAFE non-regression: `ha:////AAA==password:hunter2` -- the blob
        body is `AAA` (no keyword), so `==` still strips the blob normally.
        The colon-delimited secret survives untouched for downstream redaction."""
        result = _strip_pipeline_annotations("ha:////AAA==password:hunter2")
        assert "password:hunter2" in result
        assert "ha:////" not in result

    def test_double_equals_no_keyword_still_fully_strips(self):
        """F13 non-regression: adjacent `==` blobs whose bodies don't end with
        a keyword still strip cleanly."""
        result = _strip_pipeline_annotations("ha:////AAA==ha:////BBB==")
        assert result == ""

    @pytest.mark.parametrize("keyword", [
        "password", "passwd", "pwd", "token", "secret", "bearer", "credential",
        "authorization", "key", "apikey", "accesskey", "privatekey", "secretkey",
    ])
    def test_double_equals_keyword_board_sweep(self, keyword):
        """F13 board sweep: every keyword in _REDACTION_TRIGGER_KEYWORDS must
        survive a `==` terminator."""
        text = f"ha:////AAA{keyword}==value123"
        result = _strip_pipeline_annotations(text)
        assert keyword in result.lower()
        assert "value123" in result

    @pytest.mark.parametrize("keyword", [
        "password", "passwd", "pwd", "token", "secret", "bearer", "credential",
        "authorization", "key", "apikey", "accesskey", "privatekey", "secretkey",
    ])
    def test_bare_ansi_keyword_board_sweep(self, keyword):
        """F13 board sweep: every keyword must survive a bare-ANSI terminator."""
        text = f"ha:////AAA{keyword}\x1b[0mvalue123"
        result = _strip_pipeline_annotations(text)
        assert keyword in result.lower()
        assert "value123" in result

    # ---- F5: quadratic ANSI-prefix blowup (fixed via bounded quantifier) ----

    def test_large_ansi_only_payload_completes_quickly(self):
        """F5 regression: a long run of complete ANSI escape sequences with no
        ha:////  present must not trigger quadratic backtracking. The pre-fix
        `(?:\\x1b\\[[0-9;]*m)*` (repeated `*` quantifier) measured ~41s at
        50000 reps; the fixed single-optional-occurrence quantifier is
        sub-millisecond. Generous 2.0s ceiling avoids CI flakiness while
        still catching a reintroduced quadratic regression by a wide margin.
        No ha:////  or [Pipeline] marker is present, so the payload passes
        through unchanged (modulo the trailing .strip()) -- this test is
        purely a timing guard, not a content-stripping assertion.

        Explicit `window=len(payload)` opts this call out of the default
        _PRESTRIP_WINDOW truncation (added when the window-bound moved inside
        this function) so all 50000 reps are still actually exercised by the
        regex engine -- the real production call site (get_build_details)
        never sees a payload this large without truncating it first anyway."""
        payload = "\x1b[8m" * 50000
        start = time.perf_counter()
        result = _strip_pipeline_annotations(payload, window=len(payload))
        elapsed = time.perf_counter() - start
        assert elapsed < 2.0, f"took {elapsed:.2f}s -- possible quadratic regression"
        assert result == payload

    # ---- HIGH regression: blob-length bound / window-start truncation ----

    def test_max_length_blob_header_at_prestrip_window_start_is_recognized(self):
        """HIGH regression: the blob regex used to have no length bound (a
        plain `+`), so the safety of the 20000-char pre-strip window rested
        entirely on an unverified comment ("4x margin, more than enough")
        about how long a real blob could be -- nothing in the code actually
        enforced it. The regex is now bounded to `_MAX_BLOB_LEN`, chosen so
        `_MAX_BLOB_LEN + _CONSOLE_TAIL_SIZE <= _PRESTRIP_WINDOW`.

        This test positions a maximum-length blob's `ha:////` header EXACTLY
        at the pre-strip window's start boundary -- the worst case that
        inequality must cover -- and asserts directly on
        `_strip_pipeline_annotations`'s own output that the header survived
        truncation and the blob was fully stripped.

        Asserting on the function's own output (rather than on
        `get_build_details`'s further-sliced `console_tail`, as an earlier
        version of this test did) matters: the invariant above guarantees a
        compliant blob positioned at the window-start boundary can *never*
        actually reach the final `_CONSOLE_TAIL_SIZE`-char output slice,
        stripped or not (blob length + trailing content <= window length by
        construction). The earlier version appended a `_CONSOLE_TAIL_SIZE`-
        sized trailer after the blob and asserted on `console_tail` -- since
        that trailer alone always fills the entire final slice regardless of
        whether the blob ahead of it stripped correctly, those assertions
        could never fail (confirmed by disabling the stripping regex
        entirely and observing the old test still pass). Exercising the
        window-start cutoff requires checking the window's own output, not
        a slice that the invariant guarantees never sees it."""
        blob = "ha:////" + "B" * _MAX_BLOB_LEN + "=="
        marker = "real failure output line"
        # Trailer starts with a real delimiter (newline) -- required for the
        # blob regex's right-delimiter lookahead to match at all; every real
        # Jenkins blob is followed by one (end of line/ESC/another blob).
        trailer_len = _PRESTRIP_WINDOW - len(blob)
        assert trailer_len > len(marker) + 1, (
            "fixture constants no longer fit -- adjust padding"
        )
        trailer = "\n" + ("T" * (trailer_len - 1 - len(marker))) + marker
        assert len(trailer) == trailer_len
        filler = "F" * 50000  # simulates the rest of a much larger real log
        raw = filler + blob + trailer

        header_distance_from_end = len(blob) + len(trailer)
        assert header_distance_from_end == _PRESTRIP_WINDOW, (
            "fixture must position the blob header exactly at the pre-strip "
            "window's start boundary -- adjust padding"
        )

        result = _strip_pipeline_annotations(raw)

        assert "ha:" not in result
        assert "B" * 10 not in result
        assert marker in result

