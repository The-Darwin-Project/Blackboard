# tests/test_pipeline_and_enforce_casual.py
# @ai-rules:
# 1. [Constraint]: No live GitLab API, no live Redis. httpx mocked; blackboard is AsyncMock/StubBlackboard.
# 2. [Pattern]: Brain fixtures use `Brain(blackboard=bb, agents={...})` + real `_BrainToolContext(brain)`
#    (not a mocked ToolContext) -- matches test_brain_loop_plumbing.py's established convention.
# 3. [Pattern]: `brain._append_and_broadcast`/`brain._broadcast` are mocked directly on the instance to
#    avoid needing live Redis/registry plumbing, mirroring `_make_handler_brain()`.
# 4. [Pattern]: Route tests use a standalone FastAPI() + queue_router + dependency_overrides,
#    mirroring test_nightwatcher_shifts_api.py (lighter than the full src.main.app + lifespan pattern).
"""Tests for Issue #152 (pipeline_id polling) and the Enforce Casual UI feature.

Covers plan Test Specification IDs T-6 through T-18 (T-1..T-5 already covered by
TestObsPlateau in test_tool_gates.py; the two _make_spec fixture updates already
landed in test_state_watcher_probe.py / test_state_watcher_integration.py).
"""
from __future__ import annotations

import os
import time
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.agents.brain import Brain, _BrainToolContext
from src.agents.handlers_integration import handle_refresh_gitlab_context
from src.agents.headhunter import Headhunter
from src.agents.headhunter_gitlab import GitLabPlatform
from src.auth import UserContext, require_auth
from src.dependencies import get_blackboard, get_brain
from src.models import (
    ConversationTurn,
    EventDocument,
    EventEvidence,
    EventInput,
    EventStatus,
)
from src.routes.queue import router as queue_router
from src.scheduling.state_watcher import GitLabPipelineRef, StateWatcher


# ===========================================================================
# Shared fixtures
# ===========================================================================

def _make_event(
    event_id: str = "evt-test",
    status: str = "active",
    source: str = "chat",
    gitlab_context: dict | None = None,
    created_by_email: str | None = "alice@example.com",
) -> EventDocument:
    """Defaults created_by_email to the `authed_client` fixture's user (alice@example.com)
    so route tests exercise "owner acting on their own event" unless a test explicitly
    passes a different value (e.g. to test the ownership-mismatch 403 branch)."""
    evidence = EventEvidence(
        display_text="test", source_type=source, domain="complicated", severity="info",
        gitlab_context=gitlab_context,
    )
    event_input = EventInput(reason="test", evidence=evidence, timeDate="2026-01-01T00:00:00Z")
    return EventDocument(
        id=event_id, source=source, status=EventStatus(status),
        service="test-svc", event=event_input, conversation=[],
        created_by_email=created_by_email,
    )


def _make_gitlab_platform() -> GitLabPlatform:
    with patch.dict(os.environ, {"GITLAB_HOST": "gitlab.example.com"}):
        gl = GitLabPlatform(blackboard=MagicMock())
        gl._gitlab_token = "test-token"
    return gl


def _mock_httpx_get(json_body: dict, status_code: int = 200, raise_for_status_error: Exception | None = None):
    """Patch httpx.AsyncClient so a single GET returns the given JSON body."""
    mock_resp = MagicMock()
    mock_resp.json.return_value = json_body
    mock_resp.status_code = status_code
    if raise_for_status_error:
        mock_resp.raise_for_status.side_effect = raise_for_status_error
    else:
        mock_resp.raise_for_status = MagicMock()
    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)
    return patch("httpx.AsyncClient", return_value=mock_client)


# ===========================================================================
# T-6/T-7: GitLabPlatform.poll_gitlab_pipeline_status
# ===========================================================================

class TestPollGitlabPipelineStatus:
    @pytest.mark.asyncio
    async def test_returns_pipeline_status(self):
        """T-6: mocked 200 {"status": "running"} -> {"pipeline_status": "running"}."""
        gl = _make_gitlab_platform()
        with _mock_httpx_get({"status": "running"}):
            result = await gl.poll_gitlab_pipeline_status(project_id=123, pipeline_id=456)
        assert result == {"pipeline_status": "running"}

    @pytest.mark.asyncio
    async def test_raises_on_http_error(self):
        """T-7: mocked 404 -> raises HTTPStatusError."""
        gl = _make_gitlab_platform()
        error = httpx.HTTPStatusError("404 Not Found", request=MagicMock(), response=MagicMock(status_code=404))
        with _mock_httpx_get({}, raise_for_status_error=error):
            with pytest.raises(httpx.HTTPStatusError):
                await gl.poll_gitlab_pipeline_status(project_id=123, pipeline_id=456)

    def test_extract_pipeline_state_key_defaults(self):
        assert GitLabPlatform.extract_pipeline_state_key({}) == {"pipeline_status": "unknown"}

    def test_extract_pipeline_state_key_present(self):
        key = GitLabPlatform.extract_pipeline_state_key({"pipeline_status": "success", "extra": "ignored"})
        assert key == {"pipeline_status": "success"}
        assert "extra" not in key


# ===========================================================================
# T-15: Headhunter.poll_gitlab_pipeline_status delegate
# ===========================================================================

class TestHeadhunterPipelineDelegate:
    @pytest.mark.asyncio
    async def test_delegates_to_gitlab_adapter(self):
        """T-15: Headhunter.poll_gitlab_pipeline_status calls self._gitlab with identical args."""
        with patch.dict(os.environ, {"GITLAB_HOST": "gitlab.example.com", "MAX_ACTIVE_EVENTS": "20"}):
            hh = Headhunter(MagicMock())
        hh._gitlab.poll_gitlab_pipeline_status = AsyncMock(return_value={"pipeline_status": "success"})

        result = await hh.poll_gitlab_pipeline_status(123, 456)

        hh._gitlab.poll_gitlab_pipeline_status.assert_awaited_once_with(123, 456)
        assert result == {"pipeline_status": "success"}

    def test_extract_pipeline_state_key_delegates(self):
        key = Headhunter.extract_pipeline_state_key({"pipeline_status": "failed"})
        assert key == {"pipeline_status": "failed"}


# ===========================================================================
# T-8: StateWatcher real-object integration with GitLabPipelineRef
# ===========================================================================

class TestGitLabPipelineResource:
    @pytest.mark.asyncio
    async def test_pipeline_state_change_fires_hook(self):
        """T-8: register a REAL GitLabPipelineRef spec against a REAL StateWatcher;
        assert on_change fires once on state transition (not a mock of _poll_resource)."""
        on_change = AsyncMock()
        is_deferred = AsyncMock(return_value=True)
        watcher = StateWatcher(on_change=on_change, is_deferred=is_deferred)

        old_state = {"pipeline_status": "running"}
        new_state = {"pipeline_status": "success"}
        poll_fn = AsyncMock(return_value=new_state)

        from src.scheduling.state_watcher import SubscriptionSpec
        spec = SubscriptionSpec(
            event_id="evt-pipeline-001",
            resource_type="gitlab_pipeline",
            resource_ref=GitLabPipelineRef(project_id=123, pipeline_id=99999),
            poll_fn=poll_fn,
            interval=1,
            state_key=old_state,
            registered_at=time.time(),
            cycle_id="cycle-1",
        )

        assert watcher.register(spec) is True
        await watcher.start()
        try:
            import asyncio
            await asyncio.sleep(2.5)
        finally:
            await watcher.stop()

        on_change.assert_called_once()
        assert on_change.call_args[0][2] == new_state
        poll_fn.assert_awaited_with(project_id=123, pipeline_id=99999)


# ===========================================================================
# T-9/T-10/T-10b/T-16: handle_refresh_gitlab_context pipeline_id path
# ===========================================================================

def _make_brain_for_handler(gl_ctx: dict | None = None, event_id: str = "evt-pipe", state_watcher=None) -> tuple[Brain, object]:
    bb = MagicMock()
    bb.get_event = AsyncMock(return_value=_make_event(event_id=event_id, gitlab_context=gl_ctx))
    brain = Brain(blackboard=bb, agents={})
    brain._append_and_broadcast = AsyncMock(return_value=1)
    brain._broadcast = AsyncMock()
    brain._next_turn_number = AsyncMock(return_value=1)
    brain._state_watcher = state_watcher
    return brain, bb


class TestRefreshGitlabContextPipelineIdPath:
    @pytest.mark.asyncio
    async def test_pipeline_id_returns_status(self):
        """T-9: event with gl_ctx.project_id, args={"pipeline_id":123} -> turn with 'Pipeline Status: ...'."""
        brain, bb = _make_brain_for_handler(gl_ctx={"project_id": 100})
        hh = AsyncMock()
        hh.poll_gitlab_pipeline_status = AsyncMock(return_value={"pipeline_status": "running"})
        brain.agents["_headhunter"] = hh
        ctx = _BrainToolContext(brain)

        result = await handle_refresh_gitlab_context(
            ctx, "evt-pipe", {"pipeline_id": 123, "check_condition": "test"}, None,
        )

        assert result is True
        turn = brain._append_and_broadcast.call_args[0][1]
        assert "Pipeline Status: running" in (turn.evidence or "")
        assert "Pipeline ID: 123" in (turn.evidence or "")

    @pytest.mark.asyncio
    async def test_pipeline_id_with_subscribe_true(self):
        """T-10: args + subscribe=true -> subscription_active=true in evidence."""
        mock_watcher = MagicMock()
        mock_watcher.register = MagicMock(return_value=True)
        brain, bb = _make_brain_for_handler(gl_ctx={"project_id": 100}, state_watcher=mock_watcher)
        hh = AsyncMock()
        hh.poll_gitlab_pipeline_status = AsyncMock(return_value={"pipeline_status": "running"})
        hh.extract_pipeline_state_key = MagicMock(return_value={"pipeline_status": "running"})
        brain.agents["_headhunter"] = hh
        ctx = _BrainToolContext(brain)

        result = await handle_refresh_gitlab_context(
            ctx, "evt-pipe",
            {"pipeline_id": 123, "check_condition": "test", "subscribe": True},
            None,
        )

        assert result is True
        turn = brain._append_and_broadcast.call_args[0][1]
        assert "subscription_active: true" in (turn.evidence or "")
        mock_watcher.register.assert_called_once()

    @pytest.mark.asyncio
    async def test_pipeline_id_zero_rejected_explicitly(self):
        """T-10b: pipeline_id=0 -> explicit rejection, NOT the MR-required error path."""
        brain, bb = _make_brain_for_handler(gl_ctx={"project_id": 100})
        hh = AsyncMock()
        brain.agents["_headhunter"] = hh
        ctx = _BrainToolContext(brain)

        result = await handle_refresh_gitlab_context(
            ctx, "evt-pipe", {"pipeline_id": 0, "check_condition": "test"}, None,
        )

        assert result is True
        turn = brain._append_and_broadcast.call_args[0][1]
        assert "positive integer" in (turn.evidence or "")
        assert "No MR reference" not in (turn.evidence or "")
        hh.poll_gitlab_pipeline_status.assert_not_called()

    @pytest.mark.asyncio
    async def test_pipeline_id_non_numeric_rejected(self):
        """T-16: pipeline_id='abc' -> explicit rejection turn, not an unhandled ValueError."""
        brain, bb = _make_brain_for_handler(gl_ctx={"project_id": 100})
        hh = AsyncMock()
        brain.agents["_headhunter"] = hh
        ctx = _BrainToolContext(brain)

        result = await handle_refresh_gitlab_context(
            ctx, "evt-pipe", {"pipeline_id": "abc", "check_condition": "test"}, None,
        )

        assert result is True
        turn = brain._append_and_broadcast.call_args[0][1]
        assert "positive integer" in (turn.evidence or "")

    @pytest.mark.asyncio
    async def test_pipeline_id_subscribe_with_no_state_watcher(self):
        """subscribe=true while state_watcher is None -> subscription_active=false, no UnboundLocalError."""
        brain, bb = _make_brain_for_handler(gl_ctx={"project_id": 100}, state_watcher=None)
        hh = AsyncMock()
        hh.poll_gitlab_pipeline_status = AsyncMock(return_value={"pipeline_status": "running"})
        brain.agents["_headhunter"] = hh
        ctx = _BrainToolContext(brain)

        result = await handle_refresh_gitlab_context(
            ctx, "evt-pipe",
            {"pipeline_id": 123, "check_condition": "test", "subscribe": True},
            None,
        )

        assert result is True
        turn = brain._append_and_broadcast.call_args[0][1]
        assert "subscription_active: false" in (turn.evidence or "")

    @pytest.mark.asyncio
    async def test_pipeline_id_returns_true_not_none(self):
        """Handler contract: successful pipeline_id call returns True, not None."""
        brain, bb = _make_brain_for_handler(gl_ctx={"project_id": 100})
        hh = AsyncMock()
        hh.poll_gitlab_pipeline_status = AsyncMock(return_value={"pipeline_status": "running"})
        brain.agents["_headhunter"] = hh
        ctx = _BrainToolContext(brain)

        result = await handle_refresh_gitlab_context(
            ctx, "evt-pipe", {"pipeline_id": 123, "check_condition": "test"}, None,
        )
        assert result is True  # not None

    @pytest.mark.asyncio
    async def test_pipeline_id_gitlab_http_error_degrades_gracefully(self):
        """Codereview finding (R1 HIGH / C4 MEDIUM): a GitLab HTTPStatusError
        (e.g. 404 for a stale pipeline_id) must produce a graceful, tagged
        turn -- not an unhandled exception that loses waitingFor and collapses
        into a generic 'Internal error executing ...' fallback."""
        brain, bb = _make_brain_for_handler(gl_ctx={"project_id": 100})
        hh = AsyncMock()
        mock_response = MagicMock(status_code=404)
        hh.poll_gitlab_pipeline_status = AsyncMock(
            side_effect=httpx.HTTPStatusError("404", request=MagicMock(), response=mock_response),
        )
        brain.agents["_headhunter"] = hh
        ctx = _BrainToolContext(brain)

        result = await handle_refresh_gitlab_context(
            ctx, "evt-pipe", {"pipeline_id": 123, "check_condition": "test"}, None,
        )

        assert result is True
        turn = brain._append_and_broadcast.call_args[0][1]
        assert turn.waitingFor == "refresh_gitlab_context"
        assert "404" in (turn.evidence or "")

    @pytest.mark.asyncio
    async def test_pipeline_id_gitlab_timeout_degrades_gracefully(self):
        """Same contract for a network-level httpx.HTTPError (e.g. timeout),
        distinct from an HTTP status error."""
        brain, bb = _make_brain_for_handler(gl_ctx={"project_id": 100})
        hh = AsyncMock()
        hh.poll_gitlab_pipeline_status = AsyncMock(side_effect=httpx.ConnectTimeout("timed out"))
        brain.agents["_headhunter"] = hh
        ctx = _BrainToolContext(brain)

        result = await handle_refresh_gitlab_context(
            ctx, "evt-pipe", {"pipeline_id": 123, "check_condition": "test"}, None,
        )

        assert result is True
        turn = brain._append_and_broadcast.call_args[0][1]
        assert turn.waitingFor == "refresh_gitlab_context"

    @pytest.mark.asyncio
    async def test_pipeline_id_no_project_id_rejected(self):
        """No gitlab_context.project_id available -> explicit error, not a KeyError."""
        brain, bb = _make_brain_for_handler(gl_ctx=None)
        hh = AsyncMock()
        brain.agents["_headhunter"] = hh
        ctx = _BrainToolContext(brain)

        result = await handle_refresh_gitlab_context(
            ctx, "evt-pipe", {"pipeline_id": 123, "check_condition": "test"}, None,
        )

        assert result is True
        turn = brain._append_and_broadcast.call_args[0][1]
        assert "No project_id available" in (turn.evidence or "")


# ===========================================================================
# T-13/T-14/T-17: Brain.enforce_domain_override
# ===========================================================================

def _make_brain_for_override(event_id: str = "evt-override", status: str = "active") -> tuple[Brain, object]:
    bb = MagicMock()
    bb.get_event = AsyncMock(return_value=_make_event(event_id=event_id, status=status))
    bb.update_event_domain = AsyncMock()
    bb.resume_from_approval = AsyncMock()
    brain = Brain(blackboard=bb, agents={})
    brain._append_and_broadcast = AsyncMock(return_value=1)
    brain._broadcast = AsyncMock()
    return brain, bb


class TestEnforceDomainOverride:
    @pytest.mark.asyncio
    async def test_writes_attributed_override_turn_and_directive_turn(self):
        """T-13: writes turn actor=user/action=override/user_name=alice, plus a
        second brain/tool_result directive turn with waitingFor=enforce_domain_override."""
        brain, bb = _make_brain_for_override()
        # Ensure the lock exists (defaultdict auto-creates on .get() miss is False --
        # explicitly touch it so .get() finds a real lock, matching production flow).
        _ = brain._event_locks["evt-override"]

        result = await brain.enforce_domain_override("evt-override", "casual", "test reason", "alice")

        assert result is True
        bb.update_event_domain.assert_awaited_once_with("evt-override", "casual")
        assert brain._append_and_broadcast.await_count == 2
        override_turn = brain._append_and_broadcast.await_args_list[0][0][1]
        directive_turn = brain._append_and_broadcast.await_args_list[1][0][1]
        assert override_turn.actor == "user"
        assert override_turn.action == "override"
        assert override_turn.user_name == "alice"
        assert directive_turn.actor == "brain"
        assert directive_turn.action == "tool_result"
        assert directive_turn.waitingFor == "enforce_domain_override"

    @pytest.mark.asyncio
    async def test_serializes_against_concurrent_lock_holder(self):
        """T-14: a second coroutine holding the event's lock blocks the call until release."""
        import asyncio
        brain, bb = _make_brain_for_override()
        lock = brain._event_locks["evt-override"]

        order: list[str] = []

        async def hold_lock_then_release():
            async with lock:
                order.append("holder-acquired")
                await asyncio.sleep(0.2)
                order.append("holder-released")

        holder_task = asyncio.create_task(hold_lock_then_release())
        await asyncio.sleep(0.05)  # let holder acquire first

        result = await brain.enforce_domain_override("evt-override", "casual", "r", "alice")
        order.append("override-completed")
        await holder_task

        assert result is True
        assert order == ["holder-acquired", "holder-released", "override-completed"], (
            "enforce_domain_override must block until the concurrent lock holder releases"
        )

    @pytest.mark.asyncio
    async def test_returns_false_for_event_closed_mid_request(self):
        """T-17: event closes in the TOCTOU window between the pre-lock status
        check and the in-lock re-check -> returns False, zero mutation performed.

        (Updated for the codereview fix: the method now queries the blackboard
        FIRST, before touching _event_locks, so "pop the lock" no longer
        simulates a close -- the in-lock re-check is what must catch this race.)
        """
        brain, bb = _make_brain_for_override()
        bb.get_event = AsyncMock(side_effect=[
            _make_event(event_id="evt-override", status="active"),   # pre-lock check
            _make_event(event_id="evt-override", status="closed"),   # in-lock re-check
        ])

        result = await brain.enforce_domain_override("evt-override", "casual", "r", "alice")

        assert result is False
        bb.update_event_domain.assert_not_called()
        brain._append_and_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_false_for_already_closed_event(self):
        """Lock exists but event.status is CLOSED (race inside the lock) -> False, no mutation."""
        brain, bb = _make_brain_for_override(status="closed")
        _ = brain._event_locks["evt-override"]

        result = await brain.enforce_domain_override("evt-override", "casual", "r", "alice")

        assert result is False
        bb.update_event_domain.assert_not_called()

    @pytest.mark.asyncio
    async def test_calls_clear_waiting(self):
        """enforce_domain_override must call clear_waiting so an override fired while
        Brain is waiting for the user's next message is actually reconciled."""
        brain, bb = _make_brain_for_override()
        _ = brain._event_locks["evt-override"]
        brain._waiting_for_user["evt-override"] = time.time()

        await brain.enforce_domain_override("evt-override", "casual", "r", "alice")

        assert "evt-override" not in brain._waiting_for_user

    @pytest.mark.asyncio
    async def test_rejects_deferred_event(self):
        """Codereview finding (C6 HIGH): a DEFERRED event has a live external
        subscription and must not be silently domain-overridden -- it would
        orphan the subscription's eventual wake behind the CASUAL gate's
        tool whitelist. Only active/waiting_approval are eligible."""
        brain, bb = _make_brain_for_override(status="deferred")

        result = await brain.enforce_domain_override("evt-override", "casual", "r", "alice")

        assert result is False
        bb.update_event_domain.assert_not_called()
        brain._append_and_broadcast.assert_not_called()

    @pytest.mark.asyncio
    async def test_directive_turn_reflects_actual_domain(self):
        """Codereview finding (C11 HIGH): the directive turn previously hardcoded
        'Domain locked: CASUAL' regardless of the domain argument -- verify it
        now reflects the actual domain passed in."""
        brain, bb = _make_brain_for_override()

        await brain.enforce_domain_override("evt-override", "clear", "r", "alice")

        directive_turn = brain._append_and_broadcast.await_args_list[1][0][1]
        assert "CLEAR" in directive_turn.evidence
        assert "CASUAL" not in directive_turn.evidence

    @pytest.mark.asyncio
    async def test_lock_wait_times_out_instead_of_hanging_forever(self):
        """Codereview finding (C4/C6 HIGH): enforce_domain_override must not
        block indefinitely on a lock held by a long-running Brain LLM cycle --
        it should time out and return False within a bounded window rather
        than hang for the caller. Isolates the timeout-handling branch by
        making asyncio.wait_for raise directly, rather than racing a real
        60s-held lock against a monkeypatched timeout (fragile/flaky)."""
        import asyncio
        brain, bb = _make_brain_for_override()

        with patch("src.agents.brain.asyncio.wait_for", AsyncMock(side_effect=asyncio.TimeoutError)):
            result = await brain.enforce_domain_override("evt-override", "casual", "r", "alice")

        assert result is False
        bb.update_event_domain.assert_not_called()

    @pytest.mark.asyncio
    async def test_resumes_parked_event_and_enqueues(self):
        """T-18 (Brain-level proxy): a WAITING_APPROVAL event is resumed to active and
        re-enqueued on the scheduler -- the mechanism that makes the override 'wake'
        Brain instead of sitting inert until the resync scan."""
        brain, bb = _make_brain_for_override(status="waiting_approval")
        _ = brain._event_locks["evt-override"]
        mock_scheduler = MagicMock()
        mock_scheduler.enqueue = MagicMock()
        brain._scheduler = mock_scheduler
        # resume_if_parked re-fetches the event after the lock body already ran;
        # its own status check must also see WAITING_APPROVAL.
        bb.get_event = AsyncMock(return_value=_make_event(event_id="evt-override", status="waiting_approval"))

        result = await brain.enforce_domain_override("evt-override", "casual", "r", "alice")

        assert result is True
        bb.resume_from_approval.assert_awaited_once_with("evt-override")
        assert mock_scheduler.enqueue.call_count == 2
        mock_scheduler.enqueue.assert_any_call("evt-override")


# ===========================================================================
# T-11/T-11b/T-11c/T-12/T-18: POST /queue/{event_id}/enforce-casual route
# ===========================================================================

@pytest.fixture
def mock_blackboard_route():
    bb = AsyncMock()
    return bb


@pytest.fixture
def mock_brain_route():
    brain = AsyncMock()
    brain.enforce_domain_override = AsyncMock(return_value=True)
    return brain


@pytest.fixture
def authed_client(mock_blackboard_route, mock_brain_route):
    # NOTE: src/routes/queue.py calls `get_brain()` directly (not via Depends()),
    # so `app.dependency_overrides` cannot intercept it -- must patch the name
    # imported into the queue module itself.
    app = FastAPI()
    app.include_router(queue_router)
    app.dependency_overrides[get_blackboard] = lambda: mock_blackboard_route
    app.dependency_overrides[require_auth] = lambda: UserContext(
        user_id="alice", display_name="alice", email="alice@example.com",
    )
    patcher = patch("src.routes.queue.get_brain", AsyncMock(return_value=mock_brain_route))
    patcher.start()
    try:
        yield TestClient(app)
    finally:
        patcher.stop()


@pytest.fixture
def unauthed_client(mock_blackboard_route, mock_brain_route):
    app = FastAPI()
    app.include_router(queue_router)
    app.dependency_overrides[get_blackboard] = lambda: mock_blackboard_route
    patcher = patch("src.routes.queue.get_brain", AsyncMock(return_value=mock_brain_route))
    patcher.start()
    # require_auth left un-overridden: DEX_ENABLED=false (test default) -> anonymous -> 401.
    try:
        yield TestClient(app)
    finally:
        patcher.stop()


class TestEnforceCasualRoute:
    def test_enforces_casual_on_active_chat_event(self, authed_client, mock_blackboard_route):
        """T-11: 200 + domain=casual for a chat-sourced active event."""
        mock_blackboard_route.get_event = AsyncMock(
            return_value=_make_event(event_id="evt-1", status="active", source="chat"),
        )
        resp = authed_client.post("/queue/evt-1/enforce-casual")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "enforced"
        assert data["domain"] == "casual"

    def test_rejects_unauthenticated(self, unauthed_client, mock_blackboard_route):
        """T-11b: no Authorization header -> 401."""
        mock_blackboard_route.get_event = AsyncMock(
            return_value=_make_event(event_id="evt-1", status="active", source="chat"),
        )
        resp = unauthed_client.post("/queue/evt-1/enforce-casual")
        assert resp.status_code == 401

    def test_rejects_non_chat_slack_source(self, authed_client, mock_blackboard_route):
        """T-11c: headhunter-sourced event -> 400."""
        mock_blackboard_route.get_event = AsyncMock(
            return_value=_make_event(event_id="evt-1", status="active", source="headhunter"),
        )
        resp = authed_client.post("/queue/evt-1/enforce-casual")
        assert resp.status_code == 400

    def test_rejects_closed_event(self, authed_client, mock_blackboard_route):
        """T-12: closed event -> 409."""
        mock_blackboard_route.get_event = AsyncMock(
            return_value=_make_event(event_id="evt-1", status="closed", source="chat"),
        )
        resp = authed_client.post("/queue/evt-1/enforce-casual")
        assert resp.status_code == 409

    def test_rejects_owner_mismatch(self, authed_client, mock_blackboard_route, mock_brain_route):
        """Codereview finding (auth-rbac): an authenticated user who does not own the
        event must not be able to force its domain -- 403, and Brain must never be
        invoked. authed_client is alice@example.com; event is owned by bob."""
        mock_blackboard_route.get_event = AsyncMock(
            return_value=_make_event(
                event_id="evt-1", status="active", source="chat",
                created_by_email="bob@example.com",
            ),
        )
        resp = authed_client.post("/queue/evt-1/enforce-casual")
        assert resp.status_code == 403
        mock_brain_route.enforce_domain_override.assert_not_awaited()

    def test_rejects_ownerless_event(self, authed_client, mock_blackboard_route, mock_brain_route):
        """Codereview finding (auth-rbac): deny-by-default for ownerless events -- an
        event with no recorded created_by_email (legacy/automated) must not fall
        through unrestricted just because the caller is authenticated."""
        mock_blackboard_route.get_event = AsyncMock(
            return_value=_make_event(
                event_id="evt-1", status="active", source="chat",
                created_by_email=None,
            ),
        )
        resp = authed_client.post("/queue/evt-1/enforce-casual")
        assert resp.status_code == 403
        mock_brain_route.enforce_domain_override.assert_not_awaited()

    def test_404_for_missing_event(self, authed_client, mock_blackboard_route):
        mock_blackboard_route.get_event = AsyncMock(return_value=None)
        resp = authed_client.post("/queue/evt-missing/enforce-casual")
        assert resp.status_code == 404

    def test_409_when_override_applied_false(self, authed_client, mock_blackboard_route, mock_brain_route):
        """enforce_domain_override returning False (closed mid-request) surfaces as 409, not 200."""
        mock_blackboard_route.get_event = AsyncMock(
            return_value=_make_event(event_id="evt-1", status="active", source="chat"),
        )
        mock_brain_route.enforce_domain_override = AsyncMock(return_value=False)
        resp = authed_client.post("/queue/evt-1/enforce-casual")
        assert resp.status_code == 409

    def test_503_when_brain_unavailable(self, mock_blackboard_route):
        """get_brain() raising RuntimeError -> 503, not a misleading 200."""
        app = FastAPI()
        app.include_router(queue_router)
        app.dependency_overrides[get_blackboard] = lambda: mock_blackboard_route
        mock_blackboard_route.get_event = AsyncMock(
            return_value=_make_event(event_id="evt-1", status="active", source="chat"),
        )
        app.dependency_overrides[require_auth] = lambda: UserContext(
            user_id="alice", display_name="alice", email="alice@example.com",
        )

        async def _raise_runtime_error():
            raise RuntimeError("Brain not initialized")

        with patch("src.routes.queue.get_brain", _raise_runtime_error):
            client = TestClient(app)
            resp = client.post("/queue/evt-1/enforce-casual")
        assert resp.status_code == 503

    def test_attributes_reason_and_user_label(self, authed_client, mock_blackboard_route, mock_brain_route):
        """Reason + authenticated user label are threaded through to Brain.enforce_domain_override."""
        mock_blackboard_route.get_event = AsyncMock(
            return_value=_make_event(event_id="evt-1", status="active", source="slack"),
        )
        resp = authed_client.post("/queue/evt-1/enforce-casual", json={"reason": "customer escalation"})
        assert resp.status_code == 200
        mock_brain_route.enforce_domain_override.assert_awaited_once_with(
            "evt-1", "casual", "customer escalation", "alice",
        )
