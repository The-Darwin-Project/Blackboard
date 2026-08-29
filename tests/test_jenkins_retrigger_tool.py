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

from src.agents.handlers_integration import _JENKINS_RETRIGGER_COOLDOWN


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ctx(
    *,
    event=None,
    adapter=None,
    observer=None,
    redis_set_result=True,
    redis_get_result=None,
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
    bb.redis.get = AsyncMock(return_value=redis_get_result)
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


def _make_adapter(
    *,
    enabled: bool = True,
    restart_result: bool = True,
    build_details=None,
    breaker_open: bool = False,
):
    """Build a mock JenkinsAdapter.

    `breaker_open` is set explicitly (not left as AsyncMock's auto-truthy child
    attribute) so tests can distinguish the "not configured" vs "circuit breaker
    open" message branches in `_do_retrigger`.
    """
    adapter = AsyncMock()
    adapter.enabled = MagicMock(return_value=enabled)
    adapter.breaker_open = breaker_open
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

    async def test_cooldown_blocked_by_different_event_names_holder(self):
        """Cross-event cooldown rejection must explicitly name the other event and
        distinguish 'abuse prevented' from 'unrelated new failure suppressed' --
        regression for the cooldown-key-scoping MEDIUM fix."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()
        ctx = _make_ctx(
            event=event_doc,
            adapter=adapter,
            redis_set_result=False,
            redis_get_result="evt-other-holder",
        )

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0012", args, None)

        assert result is True
        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "evt-other-holder" in turn_text
        assert "different event" in turn_text.lower() or "unrelated" in turn_text.lower()
        adapter.restart_job.assert_not_called()

    async def test_cooldown_blocked_by_same_event_uses_generic_message(self):
        """When the cooldown holder IS this event (e.g. a retry), the message must
        not claim a 'different event' triggered it."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()
        ctx = _make_ctx(
            event=event_doc,
            adapter=adapter,
            redis_set_result=False,
            redis_get_result="evt-test0013",
        )

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0013", args, None)

        assert result is True
        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "different event" not in turn_text.lower()
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
        bb.redis.set.assert_called_once_with(
            "darwin:jenkins:retrigger:verify-cnv-4.22.z-build",
            "evt-test0011",
            nx=True,
            ex=_JENKINS_RETRIGGER_COOLDOWN,
        )
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
        # restart_job is the mutating build-trigger POST -- it must count toward the
        # shared circuit breaker (no count_failures=False), unlike the best-effort
        # get_build_details call above. Regression test for the HIGH fix in PR #218.
        adapter.restart_job.assert_called_once_with(
            "verify-cnv-4.22.z-build", fresh_details.parameters
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
# Test: matched.get("build_number") is falsy/0 -> escalation, no adapter calls
# ---------------------------------------------------------------------------

class TestRetriggerBuildNumberMissing:
    """`if not build_number:` in `_do_retrigger` treats a missing OR 0 build_number
    as 'cannot fetch fresh parameters'. Every other fixture in this file hardcodes
    build_number=254, so this branch had zero coverage before this PR."""

    async def test_build_number_zero_is_treated_as_missing(self):
        """build_number: 0 hits the same escalation path as a missing key (falsy
        check, not an is-None check) -- documents current behavior."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 0, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0025", args, None)

        assert result is True
        adapter.get_build_details.assert_not_called()
        adapter.restart_job.assert_not_called()
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called_once_with("darwin:jenkins:retrigger:verify-cnv-4.22.z-build")

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "build_number" in turn_text or "build number" in turn_text.lower()

    async def test_build_number_missing_key_is_treated_as_missing(self):
        """No 'build_number' key at all in the matched failed_job dict -> same
        escalation path as build_number=0 or None."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0026", args, None)

        assert result is True
        adapter.get_build_details.assert_not_called()
        adapter.restart_job.assert_not_called()
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called_once_with("darwin:jenkins:retrigger:verify-cnv-4.22.z-build")


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
        bb.redis.delete.assert_called_once_with("darwin:jenkins:retrigger:verify-cnv-4.22.z-build")
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
        bb.redis.delete.assert_called_once_with("darwin:jenkins:retrigger:verify-cnv-4.22.z-build")

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
        # True end-to-end positive: the key set at the top of the handler used the
        # right key/TTL, not just "some delete didn't happen".
        bb.redis.set.assert_called_once_with(
            "darwin:jenkins:retrigger:verify-cnv-4.22.z-build",
            "evt-test0041",
            nx=True,
            ex=_JENKINS_RETRIGGER_COOLDOWN,
        )


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

    async def test_adapter_not_configured_releases_key(self):
        """Adapter disabled with breaker_open=False -> 'not configured' message, not
        the circuit-breaker message. Previously `_make_adapter` left `breaker_open`
        as an AsyncMock auto-truthy child attribute, so this branch could never be
        distinguished from test_adapter_breaker_open_releases_key below."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter(enabled=False, breaker_open=False)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0051", args, None)

        assert result is True
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called()

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "not configured" in turn_text.lower()
        assert "breaker" not in turn_text.lower()

    async def test_adapter_breaker_open_releases_key(self):
        """Adapter disabled with breaker_open=True -> circuit-breaker message,
        distinct from the 'not configured' message above."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter(enabled=False, breaker_open=True)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0051b", args, None)

        assert result is True
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called()

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "breaker" in turn_text.lower()
        assert "not configured" not in turn_text.lower()

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
        # Code-level guard (PR #218 MEDIUM fix): wrapper jobs are rejected BEFORE
        # the mutating call, not just labeled after the fact.
        adapter.restart_job.assert_not_called()
        adapter.get_build_details.assert_not_called()
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called_once_with("darwin:jenkins:retrigger:verify-cnv-4.22.z-build")

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


    async def test_timeout_error_is_caught_and_handled(self):
        """TimeoutError during the external call releases the key and returns a graceful message."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build
        
        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()
        
        # Make the adapter call raise a TimeoutError
        adapter.get_build_details.side_effect = TimeoutError("Connection timed out")
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)
        
        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0090", args, None)
        
        assert result is True
        bb = ctx.get_blackboard()
        
        # The key should be released
        bb.redis.delete.assert_called_once_with("darwin:jenkins:retrigger:verify-cnv-4.22.z-build")
        
        # Turn should contain a timeout message
        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "timed out" in turn_text.lower() or "timeout" in turn_text.lower()

