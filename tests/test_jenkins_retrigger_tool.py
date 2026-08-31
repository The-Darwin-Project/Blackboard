# tests/test_jenkins_retrigger_tool.py
# @ai-rules:
# 1. [Pattern]: Tool handler tests for retrigger_jenkins_build. No Redis, no Brain import.
# 2. [Constraint]: Handler under test is in src/agents/handlers_integration.py. Mock ToolContext, adapter, and Redis.
# 3. [Pattern]: ToolContext mocked via AsyncMock with next_turn_number/append_and_broadcast stubs.
# 4. [Gotcha]: asyncio_mode=auto in pytest.ini — no @pytest.mark.asyncio needed.
# 5. [Contract]: Tests assert planned public interface from plan Step 8, NOT implementation internals.
# 6. [Gotcha]: `_make_adapter` distinguishes the sentinel default (IDLE run state)
#    from an explicit `run_state=None` (adapter returns None to exercise the
#    unreachable/unavailable branch). Do not collapse these back together.
#    This is a required change for the C4 HIGH increment's run-state guard in `_do_retrigger` --
#    without it, a bare AsyncMock's `.building` child attribute is truthy and every
#    happy-path test would silently skip `restart_job`.
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
    slack_channel=None,
) -> AsyncMock:
    """Build a minimal ToolContext mock matching the Protocol in tool_router.py."""
    ctx = AsyncMock()
    ctx.next_turn_number = AsyncMock(return_value=1)
    ctx.append_and_broadcast = AsyncMock(return_value=1)
    ctx.emit_pulse = AsyncMock()
    # get_slack_channel is a sync method on the Protocol -- must be a MagicMock
    # (not the default AsyncMock attribute) or callers get an unawaited coroutine
    # back instead of None/a channel object.
    ctx.get_slack_channel = MagicMock(return_value=slack_channel)

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


def _make_run_state(*, building: bool = False, in_queue: bool = False, last_build_number=254):
    """Build a mock JobRunState-shaped object (planned dataclass in src/adapters/jenkins.py).

    Uses MagicMock with explicit attributes rather than importing the dataclass
    directly, since this test file must not depend on the code executor's
    parallel implementation landing first.
    """
    state = MagicMock()
    state.building = building
    state.in_queue = in_queue
    state.last_build_number = last_build_number
    return state


_IDLE_RUN_STATE = object()


def _make_adapter(
    *,
    enabled: bool = True,
    restart_result: bool = True,
    build_details=None,
    breaker_open: bool = False,
    run_state=_IDLE_RUN_STATE,
):
    """Build a mock JenkinsAdapter.

    `breaker_open` is set explicitly (not left as AsyncMock's auto-truthy child
    attribute) so tests can distinguish the "not configured" vs "circuit breaker
    open" message branches in `_do_retrigger`.

    `run_state` uses a private sentinel default to mean IDLE
    (building=False, in_queue=False). Passing `run_state=None` is distinct and
    makes `get_job_run_state` return None so tests can exercise the unreachable
    Jenkins branch explicitly. This sentinel split is REQUIRED for all existing
    happy-path tests to keep passing once `_do_retrigger` gates on
    `get_job_run_state` before `restart_job` -- a bare AsyncMock's
    auto-generated `.building` child attribute is truthy, which would make every
    happy-path test silently skip the retrigger POST (a regression, not a pass).
    """
    adapter = AsyncMock()
    adapter.enabled = MagicMock(return_value=enabled)
    adapter.breaker_open = breaker_open
    adapter.restart_job = AsyncMock(return_value=restart_result)
    adapter.get_build_details = AsyncMock(return_value=build_details)
    adapter.get_job_run_state = AsyncMock(
        return_value=_make_run_state() if run_state is _IDLE_RUN_STATE else run_state
    )
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
        adapter.get_build_details.assert_called_once_with(
            "verify-cnv-4.22.z-build", 254, include_console_tail=False
        )
        # restart_job is the mutating build-trigger POST -- it must count toward the
        # shared circuit breaker. Regression test for the HIGH fix in PR #218.
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

        adapter.get_build_details.assert_called_once_with(
            "verify-cnv-4.22.z-build", 254, include_console_tail=False
        )
        restart_call_params = adapter.restart_job.call_args[0][1]
        assert "***REDACTED***" not in restart_call_params.values()
        assert restart_call_params["TOKEN"] == "real-value"


# ---------------------------------------------------------------------------
# Test: get_job_run_state guard (C4 HIGH increment) -- T-IF-1..5
#
# Spec: inside the `_do_retrigger` timeout, BEFORE `get_build_details` +
# `restart_job`, the handler must call `adapter.get_job_run_state(job_name)`:
#   - None                          -> escalate, RELEASE cooldown (redis.delete called)
#   - building=True OR in_queue=True -> skip POST, KEEP cooldown (redis.delete NOT called)
#   - idle (both False)             -> existing retrigger path unchanged
# The guard is job-level, not wrapper-type-gated (T-IF-5 proves this explicitly).
# ---------------------------------------------------------------------------

class TestRetriggerRunStateGuard:
    """T-IF-1..5: get_job_run_state pre-check gates the retrigger POST."""

    async def test_idle_job_still_retriggers(self):
        """T-IF-1: get_job_run_state idle -> existing retrigger path proceeds
        unchanged (restart_job called, cooldown retained). Likely already
        covered by TestRetriggerHappyPath.test_successful_retrigger once
        `_make_adapter` defaults to idle -- kept here as an explicit,
        spec-ID-traceable duplicate for the new run-state contract."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        fresh_details = _make_build_details()
        adapter = _make_adapter(
            build_details=fresh_details,
            restart_result=True,
            run_state=_make_run_state(building=False, in_queue=False, last_build_number=254),
        )
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0100", args, None)

        assert result is True
        adapter.get_job_run_state.assert_called_once_with("verify-cnv-4.22.z-build")
        adapter.restart_job.assert_called_once()
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_not_called()

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "success" in turn_text.lower() or "trigger" in turn_text.lower() or "retrigger" in turn_text.lower()

    async def test_building_job_skips_post_keeps_cooldown(self):
        """T-IF-2: building=True -> restart_job and get_build_details are NOT
        called, redis.delete is NOT called (cooldown retained), and the
        message mentions the job is already running/queued AND the cooldown."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter(
            run_state=_make_run_state(building=True, in_queue=False, last_build_number=300)
        )
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0101", args, None)

        assert result is True
        adapter.get_build_details.assert_not_called()
        adapter.restart_job.assert_not_called()
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_not_called()

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower = turn_text.lower()
        assert "running" in lower or "queued" in lower or "in progress" in lower or "building" in lower
        assert "cooldown" in lower

    async def test_queued_job_skips_post_keeps_cooldown(self):
        """T-IF-3: in_queue=True (building=False) -> same no-POST/keep-cooldown
        behavior as T-IF-2 -- proves the guard checks both fields."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter(
            run_state=_make_run_state(building=False, in_queue=True, last_build_number=254)
        )
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0102", args, None)

        assert result is True
        adapter.get_build_details.assert_not_called()
        adapter.restart_job.assert_not_called()
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_not_called()

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower = turn_text.lower()
        assert "running" in lower or "queued" in lower or "in progress" in lower or "building" in lower
        assert "cooldown" in lower

    async def test_run_state_none_releases_cooldown(self):
        """T-IF-4: get_job_run_state returns None (fetch failed / Jenkins
        unreachable) -> restart_job NOT called, cooldown key IS released
        (redis.delete called), and the message escalates as unreachable."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter(run_state=None)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0103", args, None)

        assert result is True
        adapter.get_build_details.assert_not_called()
        adapter.restart_job.assert_not_called()
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called_once_with("darwin:jenkins:retrigger:verify-cnv-4.22.z-build")

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower = turn_text.lower()
        assert "unreachable" in lower or "escalate" in lower or "could not" in lower or "unable" in lower

    async def test_wrapper_job_building_also_skips(self):
        """T-IF-5: A wrapper-type job (job_metadata.type='wrapper') that is
        building=True must ALSO skip the POST and keep the per-job cooldown --
        proves the run-state guard applies at the job level, not only to
        non-wrapper (leaf) jobs. Must NOT restore any assertion that wrapper
        retrigger is categorically blocked -- this is the run-state guard, not
        a wrapper-type block.

        Regression coverage for the wrapper-lock-leak fix: the wrapper-global
        lock acquired earlier in `_do_retrigger` must be released here since
        no wrapper retrigger was actually posted -- only the per-job cooldown
        key stays held (correctly, the job really is still running)."""
        from src.agents.handlers_integration import (
            _JENKINS_WRAPPER_RETRIGGER_LOCK_KEY,
            handle_retrigger_jenkins_build,
        )

        failed_jobs = [
            {
                "job_name": "verify-cnv-4.22.z-build",
                "build_number": 254,
                "parameters": {},
                "job_metadata": {"type": "wrapper", "version": "4.22"},
            },
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter(
            run_state=_make_run_state(building=True, in_queue=False, last_build_number=254)
        )
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0104", args, None)

        assert result is True
        adapter.get_build_details.assert_not_called()
        adapter.restart_job.assert_not_called()
        bb = ctx.get_blackboard()
        # Wrapper-global lock released (no-op, nothing was actually retriggered);
        # per-job cooldown key is NOT among the deletions (it stays held).
        bb.redis.delete.assert_called_once_with(_JENKINS_WRAPPER_RETRIGGER_LOCK_KEY)

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower = turn_text.lower()
        assert "running" in lower or "queued" in lower or "in progress" in lower or "building" in lower
        assert "cooldown" in lower


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
        assert "successfully retriggered" in lower
        adapter.restart_job.assert_called_once()
        adapter.get_build_details.assert_called_once()
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_not_called()

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
        adapter.restart_job.assert_called_once()

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

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower = turn_text.lower()
        assert "wrapper" not in lower


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

    async def test_get_job_run_state_exception_releases_key(self):
        """An exception raised directly from get_job_run_state (not get_build_details)
        must also release the cooldown key -- MEDIUM testing-gap fix: this call had
        no dedicated failure-injection coverage before."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()
        adapter.get_job_run_state.side_effect = ConnectionError("Mocked Jenkins connection failure")
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0091", args, None)

        assert result is True
        adapter.get_build_details.assert_not_called()
        adapter.restart_job.assert_not_called()
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called_once_with("darwin:jenkins:retrigger:verify-cnv-4.22.z-build")

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "internal error" in turn_text.lower() or "escalate" in turn_text.lower()


# ---------------------------------------------------------------------------
# Test: real asyncio.timeout firing from cumulative elapsed wall-clock time
# (HIGH fix: previously only a mocked side_effect=TimeoutError was exercised)
# ---------------------------------------------------------------------------

class TestRetriggerRealTimeout:
    """Shrinks the module-level timeout constant and makes one mocked Jenkins
    call genuinely sleep past it, so asyncio.timeout's real cancellation path
    fires -- not a raised TimeoutError side_effect standing in for it."""

    async def test_real_timeout_fires_from_cumulative_elapsed_time(self, monkeypatch):
        import asyncio as asyncio_module

        from src.agents import handlers_integration
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        monkeypatch.setattr(handlers_integration, "_JENKINS_RETRIGGER_HANDLER_TIMEOUT", 0.05)

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()

        async def _slow_run_state(*_args, **_kwargs):
            await asyncio_module.sleep(0.2)
            return _make_run_state()

        adapter.get_job_run_state = AsyncMock(side_effect=_slow_run_state)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0230", args, None)

        assert result is True
        adapter.get_build_details.assert_not_called()
        adapter.restart_job.assert_not_called()
        bb = ctx.get_blackboard()
        bb.redis.delete.assert_called_once_with("darwin:jenkins:retrigger:verify-cnv-4.22.z-build")

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "timed out" in turn_text.lower()


# ---------------------------------------------------------------------------
# Test: wrapper-specific system-wide rate limit (HIGH fix -- restores a
# code-level control for wrapper jobs, distinct from the per-job cooldown)
# ---------------------------------------------------------------------------

class TestRetriggerWrapperRateLimit:
    """A separate, system-wide lock caps how often ANY wrapper job can be
    retriggered, independent of the per-job cooldown."""

    async def test_wrapper_global_lock_blocks_a_different_wrapper_job(self):
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {
                "job_name": "verify-cnv-4.23.z-build",
                "build_number": 900,
                "parameters": {},
                "job_metadata": {"type": "wrapper", "version": "4.23"},
            },
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()
        ctx = _make_ctx(event=event_doc, adapter=adapter)
        bb = ctx.get_blackboard()
        # First SET (per-job cooldown) succeeds; second SET (wrapper global lock)
        # fails because a different wrapper job is already within its cooldown.
        bb.redis.set = AsyncMock(side_effect=[True, False])
        bb.redis.get = AsyncMock(return_value="verify-cnv-4.22.z-build")

        args = {"job_name": "verify-cnv-4.23.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0200", args, None)

        assert result is True
        adapter.get_job_run_state.assert_not_called()
        adapter.restart_job.assert_not_called()
        # No actual retrigger happened -- the per-job cooldown key acquired at the
        # top of the handler must be released, not left dangling.
        bb.redis.delete.assert_called_once_with(
            "darwin:jenkins:retrigger:verify-cnv-4.23.z-build"
        )

        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower = turn_text.lower()
        assert "wrapper" in lower
        assert "verify-cnv-4.22.z-build" in turn_text

    async def test_leaf_job_never_touches_wrapper_lock(self):
        """A leaf (non-wrapper) job only ever performs the one per-job cooldown
        SET -- the wrapper-specific gate must not apply to it."""
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build-tier1", "build_number": 100, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        fresh_details = _make_build_details(job_name="verify-cnv-4.22.z-build-tier1", build_number=100)
        adapter = _make_adapter(build_details=fresh_details, restart_result=True)
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build-tier1"}
        await handle_retrigger_jenkins_build(ctx, "evt-test0201", args, None)

        bb = ctx.get_blackboard()
        assert bb.redis.set.call_count == 1

    async def test_noop_wrapper_lock_does_not_block_a_different_wrappers_genuine_retrigger(self):
        """End-to-end regression test against a real (fake) Redis backend --
        not mocked call-counting -- for the wrapper-lock-leak fix: a wrapper
        job observed already-building (no-op, nothing retriggered) must not
        leave the system-wide wrapper lock held, or a completely unrelated
        wrapper job's later GENUINE retrigger would be wrongly blocked for the
        full cooldown window."""
        import fakeredis.aioredis

        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        redis = fakeredis.aioredis.FakeRedis(decode_responses=True)

        # --- Call 1: wrapper job A is observed already building -> no-op ---
        failed_jobs_a = [
            {
                "job_name": "verify-cnv-4.22.z-build",
                "build_number": 254,
                "parameters": {},
                "job_metadata": {"type": "wrapper", "version": "4.22"},
            },
        ]
        event_doc_a = _make_event_doc(failed_jobs=failed_jobs_a)
        adapter_a = _make_adapter(
            run_state=_make_run_state(building=True, in_queue=False, last_build_number=254)
        )
        ctx_a = _make_ctx(event=event_doc_a, adapter=adapter_a)
        ctx_a.get_blackboard().redis = redis

        result_a = await handle_retrigger_jenkins_build(
            ctx_a, "evt-noop-a", {"job_name": "verify-cnv-4.22.z-build"}, None
        )
        assert result_a is True
        adapter_a.restart_job.assert_not_called()

        # --- Call 2: a DIFFERENT wrapper job attempts a genuine retrigger ---
        failed_jobs_b = [
            {
                "job_name": "verify-cnv-4.23.z-build",
                "build_number": 900,
                "parameters": {},
                "job_metadata": {"type": "wrapper", "version": "4.23"},
            },
        ]
        event_doc_b = _make_event_doc(failed_jobs=failed_jobs_b)
        fresh_details = _make_build_details(job_name="verify-cnv-4.23.z-build", build_number=900)
        adapter_b = _make_adapter(build_details=fresh_details, restart_result=True)
        ctx_b = _make_ctx(event=event_doc_b, adapter=adapter_b)
        ctx_b.get_blackboard().redis = redis

        result_b = await handle_retrigger_jenkins_build(
            ctx_b, "evt-noop-b", {"job_name": "verify-cnv-4.23.z-build"}, None
        )
        assert result_b is True

        # The bug would have left job A's no-op holding the global wrapper
        # lock, blocking this genuine retrigger for job B entirely.
        adapter_b.restart_job.assert_called_once()
        turn_b = _captured_turn(ctx_b)
        turn_b_text = (turn_b.thoughts or "") + (turn_b.evidence or "")
        assert "successfully retriggered" in turn_b_text.lower()

        await redis.aclose()


# ---------------------------------------------------------------------------
# Test: structured alerting for actual wrapper retriggers (HIGH fix)
# ---------------------------------------------------------------------------

class TestRetriggerWrapperAlerting:
    """A successful wrapper retrigger posts a best-effort alert to the infra
    Slack channel; a leaf retrigger does not."""

    async def test_wrapper_retrigger_posts_infra_alert(self):
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

        slack_channel = MagicMock()
        slack_channel._infra_channel = "C123INFRA"
        slack_channel._app.client.chat_postMessage = AsyncMock(return_value={"ok": True})
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True, slack_channel=slack_channel)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        await handle_retrigger_jenkins_build(ctx, "evt-test0210", args, None)

        slack_channel._app.client.chat_postMessage.assert_called_once()
        _, kwargs = slack_channel._app.client.chat_postMessage.call_args
        assert kwargs["channel"] == "C123INFRA"
        assert "verify-cnv-4.22.z-build" in kwargs["text"]

    async def test_leaf_retrigger_does_not_alert(self):
        from src.agents.handlers_integration import handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build-tier1", "build_number": 100, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        fresh_details = _make_build_details(job_name="verify-cnv-4.22.z-build-tier1", build_number=100)
        adapter = _make_adapter(build_details=fresh_details, restart_result=True)

        slack_channel = MagicMock()
        slack_channel._infra_channel = "C123INFRA"
        slack_channel._app.client.chat_postMessage = AsyncMock(return_value={"ok": True})
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True, slack_channel=slack_channel)

        args = {"job_name": "verify-cnv-4.22.z-build-tier1"}
        await handle_retrigger_jenkins_build(ctx, "evt-test0211", args, None)

        slack_channel._app.client.chat_postMessage.assert_not_called()

    async def test_wrapper_alert_failure_does_not_affect_result(self):
        """A Slack post failure during the alert must not change the retrigger's
        own success result -- alerting is best-effort."""
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

        slack_channel = MagicMock()
        slack_channel._infra_channel = "C123INFRA"
        slack_channel._app.client.chat_postMessage = AsyncMock(side_effect=RuntimeError("Slack down"))
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True, slack_channel=slack_channel)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0212", args, None)

        assert result is True
        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        assert "successfully retriggered" in turn_text.lower()


# ---------------------------------------------------------------------------
# Test: no-op (observed-running) cooldown messaging (MEDIUM fix -- success
# no longer conflates "actually POSTed" with "observed already running")
# ---------------------------------------------------------------------------

class TestRetriggerNoopCooldownMessaging:
    async def test_building_job_tags_cooldown_as_observed_running(self):
        """The skip-POST path re-tags the cooldown value (xx=True, keepttl=True)
        so a later blocked caller isn't told a retrigger happened when none did."""
        from src.agents.handlers_integration import _NOOP_COOLDOWN_MARKER, handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter(
            run_state=_make_run_state(building=True, in_queue=False, last_build_number=300)
        )
        ctx = _make_ctx(event=event_doc, adapter=adapter, redis_set_result=True)

        args = {"job_name": "verify-cnv-4.22.z-build"}
        await handle_retrigger_jenkins_build(ctx, "evt-test0221", args, None)

        bb = ctx.get_blackboard()
        tag_call = bb.redis.set.call_args_list[-1]
        assert tag_call[0] == (
            "darwin:jenkins:retrigger:verify-cnv-4.22.z-build",
            f"evt-test0221{_NOOP_COOLDOWN_MARKER}",
        )
        assert tag_call[1] == {"xx": True, "keepttl": True}

    async def test_observed_running_does_not_claim_retriggered(self):
        """A caller blocked by a cooldown key tagged as observed-running must not
        be told the job 'was already retriggered' -- that never happened."""
        from src.agents.handlers_integration import _NOOP_COOLDOWN_MARKER, handle_retrigger_jenkins_build

        failed_jobs = [
            {"job_name": "verify-cnv-4.22.z-build", "build_number": 254, "parameters": {}},
        ]
        event_doc = _make_event_doc(failed_jobs=failed_jobs)
        adapter = _make_adapter()
        ctx = _make_ctx(
            event=event_doc,
            adapter=adapter,
            redis_set_result=False,
            redis_get_result=f"evt-original{_NOOP_COOLDOWN_MARKER}",
        )

        args = {"job_name": "verify-cnv-4.22.z-build"}
        result = await handle_retrigger_jenkins_build(ctx, "evt-test0220", args, None)

        assert result is True
        turn = _captured_turn(ctx)
        turn_text = (turn.thoughts or "") + (turn.evidence or "")
        lower = turn_text.lower()
        assert "was already retriggered" not in lower
        assert "evt-original" in turn_text
        assert "running" in lower or "queued" in lower
        adapter.restart_job.assert_not_called()

