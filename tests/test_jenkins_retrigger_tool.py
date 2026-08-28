# tests/test_jenkins_retrigger_tool.py
# @ai-rules:
# 1. [Pattern]: Tool handler tests for retrigger_jenkins_build. No Redis, no Brain import.
# 2. [Constraint]: Handler under test is in src/agents/handlers_integration.py. Mock ToolContext, adapter, and Redis.
# 3. [Pattern]: ToolContext mocked via AsyncMock with next_turn_number/append_and_broadcast stubs.
# 4. [Gotcha]: asyncio_mode=auto in pytest.ini — no @pytest.mark.asyncio needed.
# 5. [Contract]: Tests assert planned public interface from plan Step 8, NOT implementation internals.
"""
Step 8: retrigger_jenkins_build handler tests.

Covers: scoping (IDOR), rate-cap, happy path, get_build_details fallback,
restart_job failure, disabled adapter, and wrapper vs leaf messaging.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(
    *,
    event=None,
    adapter=None,
    observer=None,
    redis_set_result=True,
) -> AsyncMock:
    """Build a minimal ToolContext mock matching the Protocol in tool_router.py."""
    ctx = AsyncMock()
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock(return_value=1)
    ctx.emit_pulse = AsyncMock()

    bb = AsyncMock()
    bb.get_event = AsyncMock(return_value=event)
    bb.redis = AsyncMock()
    bb.redis.set = AsyncMock(return_value=redis_set_result)
    bb.redis.delete = AsyncMock()
    ctx.get_blackboard = MagicMock(return_value=bb)

    if observer is None:
        observer = MagicMock()
        observer._adapter = adapter
    ctx.get_agent_instance = MagicMock(return_value=observer)

    return ctx


def _captured_turn(ctx: AsyncMock):
    """Extract the ConversationTurn passed to append_and_broadcast."""
    assert ctx.append_and_broadcast.call_count >= 1, "append_and_broadcast was never called"
    return ctx.append_and_broadcast.call_args[0][1]


def _make_event_doc(failed_jobs: list[dict] | None = None):
    """Build a minimal EventDocument-like mock with ci_context."""
    event_doc = MagicMock()
    event_input = MagicMock()
    evidence = MagicMock()

    ci_context = {
        "cnv_version": "4.22",
        "jenkins_url": "https://jenkins.example.com",
        "failed_jobs": failed_jobs or [],
        "missing_jobs": [],
        "llm_triage": [],
        "maintainer": {"source": "static", "emails": []},
    }
    evidence.ci_context = ci_context
    event_input.evidence = evidence
    event_doc.event = event_input
    return event_doc


def _make_adapter(*, enabled: bool = True, restart_result: bool = True, build_details=None):
    """Build a mock JenkinsAdapter."""
    adapter = AsyncMock()
    adapter.enabled = MagicMock(return_value=enabled)
    adapter.restart_job = AsyncMock(return_value=restart_result)
    adapter.get_build_details = AsyncMock(return_value=build_details)
    return adapter


def _make_build_details(job_name="verify-cnv-4.22.z-build", build_number=254):
    """Build a mock BuildDetails dataclass-like object."""
    details = MagicMock()
    details.job_name = job_name
    details.build_number = build_number
    details.result = "FAILURE"
    details.parameters = {"CNV_VERSION": "4.22", "SOME_SECRET_TOKEN": "real-secret-value"}
    details.console_tail = ""
    details.url = f"https://jenkins.example.com/job/{job_name}/{build_number}/"
    return details


# ---------------------------------------------------------------------------
# Test: Job not in event's failed_jobs -> rejected (scoping / IDOR test)
# ---------------------------------------------------------------------------

class TestRetriggerScopingReject:
    """Job not present in this event's ci_context.failed_jobs is rejected."""

    async def test_job_not_in_failed_jobs_is_rejected(self):
        """Calling retrigger with a job_name not in the event's failed_jobs -> rejection."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()
        ctx = _make_ctx(event=event_doc, adapter=adapter)

        args = {"job_name": "some-other-job-not-in-event"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0001", args, None)

        assert result is True
        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "not" in turn_text.lower() or "reject" in turn_text.lower() or "scope" in turn_text.lower()
        adapter.restart_job.assert_not_called()

    async def test_empty_failed_jobs_is_rejected(self):
        """Event has ci_context but failed_jobs is empty -> rejection."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        event_doc = _make_event_doc(failed_jobs=[])
        adapter = _make_adapter()
        ctx = _make_ctx(event=event_doc, adapter=adapter)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0002", args, None)

        assert result is True
        adapter.restart_job.assert_not_called()

    async def test_no_ci_context_is_rejected(self):
        """Event has no ci_context at all -> rejection."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        event_doc = MagicMock()
        event_doc.event = MagicMock()
        event_doc.event.evidence = MagicMock()
        event_doc.event.evidence.ci_context = None
        adapter = _make_adapter()
        ctx = _make_ctx(event=event_doc, adapter=adapter)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0003", args, None)

        assert result is True
        adapter.restart_job.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Rate-limit cooldown blocks a second call
# ---------------------------------------------------------------------------

class TestRetriggerRateLimit:
    """Redis SET NX EX controls per-job retrigger cooldown."""

    async def test_cooldown_blocks_second_call(self):
        """Second call within cooldown window is rejected."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter(build_details=_make_build_details())
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=False)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0010", args, None)

        assert result is True
        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "cooldown" in turn_text.lower() or "retri" in turn_text.lower() or "recently" in turn_text.lower()
        adapter.restart_job.assert_not_called()

    async def test_first_call_sets_redis_key(self):
        """First call (SET NX returns True) proceeds to retrigger."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        build_details = _make_build_details()
        adapter = _make_adapter(build_details=build_details, restart_result=True)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0011", args, None)

        assert result is True
        bb = ctx.get_blackboard()
        bb.redis.set.assert_called_once()
        call_kwargs = bb.redis.set.call_args
        assert call_kwargs[1].get("nx") is True or (len(call_kwargs[0]) > 2)
        adapter.restart_job.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Happy path — fresh parameters fetched, restart_job called
# ---------------------------------------------------------------------------

class TestRetriggerHappyPath:
    """Successful retrigger: scoping passes, cooldown clear, fresh params fetched."""

    async def test_successful_retrigger(self):
        """Full happy path: job in scope, cooldown clear, fresh params, restart succeeds."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {"REDACTED": "***REDACTED***"}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        fresh_details = _make_build_details()
        fresh_details.parameters = {"CNV_VERSION": "4.22", "REAL_TOKEN": "actual-secret"}
        adapter = _make_adapter(build_details=fresh_details, restart_result=True)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0020", args, None)

        assert result is True
        adapter.get_build_details.assert_called_once_with("verify-cnv-4.22.z-build", 254, count_failures=False)
        adapter.restart_job.assert_called_once_with(
            "verify-cnv-4.22.z-build", fresh_details.parameters, count_failures=False
        )
        turn = _captured_turn(ctx)
        assert turn.actor == "brain"
        assert turn.action == "tool_result"
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "success" in turn_text.lower() or "trigger" in turn_text.lower() or "retrigger" in turn_text.lower()

    async def test_uses_fresh_params_not_event_params(self):
        """Handler must call get_build_details for fresh params (event params are redacted)."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {"TOKEN": "***REDACTED***"}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        fresh_details = _make_build_details()
        fresh_details.parameters = {"TOKEN": "real-value", "CNV_VERSION": "4.22"}
        adapter = _make_adapter(build_details=fresh_details, restart_result=True)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        await handle_retrigger_jenkins_build(ctx, "evt-test0021", args, None)

        adapter.get_build_details.assert_called_once_with("verify-cnv-4.22.z-build", 254, count_failures=False)
        restart_call_params = adapter.restart_job.call_args[0][1]
        assert "***REDACTED***" not in restart_call_params.values()
        assert restart_call_params["TOKEN"] == "real-value"


# ---------------------------------------------------------------------------
# Test: get_build_details returns None -> graceful message, rate-limit released
# ---------------------------------------------------------------------------

class TestRetriggerBuildDetailsNone:
    """get_build_details returning None -> graceful failure, key released."""

    async def test_build_details_none_releases_key(self):
        """When get_build_details returns None, rate-limit key is deleted."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter(build_details=None, restart_result=True)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0030", args, None)

        assert result is True
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called()
        adapter.restart_job.assert_not_called()

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "fail" in turn_text.lower() or "could not" in turn_text.lower() or "unable" in turn_text.lower()


# ---------------------------------------------------------------------------
# Test: restart_job returns False -> graceful message, rate-limit released
# ---------------------------------------------------------------------------

class TestRetriggerRestartFails:
    """restart_job returning False -> rate-limit key released, graceful message."""

    async def test_restart_false_releases_key(self):
        """When restart_job returns False, rate-limit key is deleted."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        fresh_details = _make_build_details()
        adapter = _make_adapter(build_details=fresh_details, restart_result=False)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0040", args, None)

        assert result is True
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called()

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "fail" in turn_text.lower() or "error" in turn_text.lower() or "unsuccessful" in turn_text.lower()

    async def test_restart_true_retains_key(self):
        """When restart_job returns True, rate-limit key is NOT deleted (retained)."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        fresh_details = _make_build_details()
        adapter = _make_adapter(build_details=fresh_details, restart_result=True)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        await handle_retrigger_jenkins_build(ctx, "evt-test0041", args, None)

        bb = ctx.get_blackboard()
        bb.redis.delete.assert_not_called()


# ---------------------------------------------------------------------------
# Test: Adapter None / enabled() == False -> graceful message, key released
# ---------------------------------------------------------------------------

class TestRetriggerAdapterUnavailable:
    """Adapter missing or disabled -> graceful message, rate-limit key released."""

    async def test_adapter_none_releases_key(self):
        """Observer has no _adapter attribute -> graceful rejection, key released."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        observer = MagicMock()
        observer._adapter = None
        ctx = _make_ctx(event=event_doc, observer=observer, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0050", args, None)

        assert result is True
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called()

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "not configured" in turn_text.lower() or "unavailable" in turn_text.lower() or "not available" in turn_text.lower()

    async def test_adapter_disabled_releases_key(self):
        """Adapter exists but enabled() returns False -> graceful rejection, key released."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter(enabled=False)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0051", args, None)

        assert result is True
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called()

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "not configured" in turn_text.lower() or "disabled" in turn_text.lower() or "breaker" in turn_text.lower() or "unavailable" in turn_text.lower()

    async def test_observer_none_releases_key(self):
        """get_agent_instance returns None -> graceful rejection, key released."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        ctx = _make_ctx(event=event_doc, redis_set_result=True)
        ctx.get_agent_instance = MagicMock(return_value=None)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0052", args, None)

        assert result is True
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called()


# ---------------------------------------------------------------------------
# Test: Wrapper vs leaf messaging
# ---------------------------------------------------------------------------

class TestRetriggerWrapperLeafMessaging:
    """tool_result turn reflects job_metadata.type when present."""

    async def test_wrapper_job_mentioned_in_turn(self):
        """When job_metadata.type == 'wrapper', turn text mentions wrapper/all lanes."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {
                "job_name": "verify-cnv-4.22.z-build",
                "build_number": 254,
                "parameters": {},
                "job_metadata": {"type": "wrapper", "version": "4.22"},
            },
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        fresh_details = _make_build_details()
        adapter = _make_adapter(build_details=fresh_details, restart_result=True)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        await handle_retrigger_jenkins_build(ctx, "evt-test0060", args, None)

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower = turn_text.lower()
        assert "wrapper" in lower or "all lane" in lower or "all sub" in lower

    async def test_leaf_job_no_wrapper_mention(self):
        """When job_metadata.type != 'wrapper' or absent, no wrapper/lanes text."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {
                "job_name": "verify-cnv-4.22.z-build-tier1",
                "build_number": 100,
                "parameters": {},
                "job_metadata": {"type": "leaf", "version": "4.22"},
            },
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        fresh_details = _make_build_details(
            job_name="verify-cnv-4.22.z-build-tier1", build_number=100
        )
        adapter = _make_adapter(build_details=fresh_details, restart_result=True)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build-tier1"}
        await handle_retrigger_jenkins_build(ctx, "evt-test0061", args, None)

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower = turn_text.lower()
        assert "wrapper" not in lower

    async def test_no_job_metadata_graceful(self):
        """When job_metadata is absent entirely, retrigger still works."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        fresh_details = _make_build_details()
        adapter = _make_adapter(build_details=fresh_details, restart_result=True)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0062", args, None)

        assert result is True
        adapter.restart_job.assert_called_once()


# ---------------------------------------------------------------------------
# Test: Handler returns True (re-invoke LLM)
# ---------------------------------------------------------------------------

class TestRetriggerReturnValue:
    """Handler must always return True (re-invoke LLM, matching greenwave/ask_release_ai)."""

    async def test_all_paths_return_true(self):
        """Even rejection paths return True (data-retrieval-style result, not terminal)."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        event_doc = _make_event_doc(failed_jobs=[])
        adapter = _make_adapter()
        ctx = _make_ctx(event=event_doc, adapter=adapter)

        args = {"job_name": "nonexistent"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0070", args, None)
        assert result is True

# ---------------------------------------------------------------------------
# Test: Exception handling and empty job name
# ---------------------------------------------------------------------------

class TestRetriggerExceptions:
    """Covers unexpected exceptions and missing required parameters."""

    async def test_empty_job_name(self):
        """Empty job_name is rejected immediately, no key set."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build
        
        ctx = _make_ctx()
        args = {"job_name": "   "}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0080", args, None)
        assert result is True
        bb = ctx.get_blackboard()
        bb.redis.set.assert_not_called()

    async def test_unexpected_exception_releases_key(self):
        """If an exception is raised mid-flight, key is released and graceful message returned."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()
        # Mock adapter to raise an exception
        adapter.get_build_details.side_effect = ValueError("Mocked unexpected exception")
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0081", args, None)
        
        assert result is True
        bb = ctx.get_blackboard()
        # Exception caught, key released
        bb.redis.delete.assert_called()
        
        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "internal error" in turn_text.lower() or "escalate" in turn_text.lower()

