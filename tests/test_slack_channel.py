# tests/test_slack_channel.py
# @ai-rules:
# 1. [Constraint]: Tests invoke actual SlackChannel methods — broadcast_handler(), _handle_legacy_turn()
#    (via broadcast_handler), _ensure_dm_context(), _refresh_thinking_status(), and captured
#    on_dm_message callback. No re-implementation of production logic.
# 2. [Pattern]: Mock AsyncApp with decorator-capturing factory. _register_handlers() populates
#    captured dict. Callbacks invoked directly with mock event payloads.
# 3. [Pattern]: Assert on STATE CHANGES: _dm_context, _thinking_msg, _progress_ts,
#    _progress_last_phrase — not just on mock call args, though call args are inspected for
#    progress bubble text/target since chat_postMessage/chat_update/chat_delete are the only
#    externally-observable side effects of the progress-bubble mechanism.
# 4. [Pattern]: Use pytest-asyncio mode="auto". AsyncMock for all awaitable dependencies.
# 5. [Gotcha]: _access_gate = None bypasses gate checks. Pre-populate _dm_context to avoid
#    _ensure_dm_context blackboard queries in tests that don't test hydration.
# 6. [Pattern]: Post-streaming-removal (slack-port-unification), progress feedback during
#    tool_result turns is a single-bubble post/update/delete lifecycle (_progress_ts,
#    _progress_last_phrase, _TOOL_PROGRESS_PHRASES) gated by _progress_enabled and
#    turn.waitingFor truthiness — not the old chat_stream-based token streaming.
"""Unit tests for SlackChannel — agent_view DM handling and progress-bubble messaging."""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_channel() -> tuple:
    """Create a SlackChannel with mocked deps and captured handler callbacks.

    Returns (sc, captured) where captured maps "event:message" etc. to callbacks.
    """
    from src.channels.slack import SlackChannel

    captured: dict[str, Any] = {}

    mock_app = MagicMock()
    mock_app.client = AsyncMock()

    def _make_registrar(kind: str):
        def registrar(name: str):
            def decorator(fn):
                captured[f"{kind}:{name}"] = fn
                return fn
            return decorator
        return registrar

    mock_app.event = _make_registrar("event")
    mock_app.command = _make_registrar("command")
    mock_app.action = _make_registrar("action")
    mock_app.view = _make_registrar("view")

    sc = SlackChannel.__new__(SlackChannel)
    sc._app = mock_app
    sc._app_token = "xapp-test"
    sc._access_gate = None
    sc._infra_channel = "C_INFRA"
    sc._mr_fallback_channel = "C_MR"
    sc._blackboard = AsyncMock()
    sc._brain = MagicMock()
    sc._brain.clear_waiting = MagicMock()
    sc._brain.resume_if_parked = AsyncMock()
    sc._handler = None
    sc._user_name_cache = {}
    sc._user_email_cache = {}
    sc._USER_CACHE_TTL = 3600
    sc._thinking_msg = {}
    sc._quiet_events = set()
    sc._dm_context = {}

    # Progress-bubble state (replaces the removed streaming state post slack-port-unification).
    sc._progress_ts = {}
    sc._progress_last_phrase = {}
    sc._progress_failed = set()
    sc._progress_enabled = True

    sc._register_handlers()

    return sc, captured


def _dm_ctx(
    channel: str = "D_DM",
    thread_ts: str = "1700000001.000001",
    user_id: str = "U_USER",
) -> dict:
    """Build a _dm_context entry."""
    return {
        "channel": channel, "thread_ts": thread_ts,
        "user_id": user_id, "team_id": "T_TEAM", "_last_status_at": 0,
    }


def _dm_event(
    *,
    text: str = "hello",
    channel: str = "D_DM",
    user: str = "U_USER",
    ts: str = "1700000001.000001",
    thread_ts: str | None = None,
    channel_type: str = "im",
    team: str = "T_TEAM",
) -> dict:
    """Build a Slack message event payload for DM testing."""
    ev: dict[str, Any] = {
        "text": text,
        "channel": channel,
        "user": user,
        "ts": ts,
        "channel_type": channel_type,
        "team": team,
    }
    if thread_ts is not None:
        ev["thread_ts"] = thread_ts
    return ev


def _mock_event_doc(
    *,
    event_id: str = "evt-abc12345",
    status: str = "active",
    source: str = "slack",
    slack_channel_id: str = "D_DM",
    slack_thread_ts: str | None = "1700000001.000001",
    slack_user_id: str = "U_USER",
    conversation: list | None = None,
):
    """Build a mock event document."""
    doc = MagicMock()
    doc.id = event_id
    doc.status = status
    doc.source = source
    doc.slack_channel_id = slack_channel_id
    doc.slack_thread_ts = slack_thread_ts
    doc.slack_user_id = slack_user_id
    doc.conversation = conversation or []
    doc.service = "general"
    doc.event = MagicMock()
    doc.event.reason = "test event"
    return doc


def _user_info_response(name: str = "Alice", email: str = "alice@example.com") -> dict:
    """Build a users_info API response."""
    return {
        "user": {
            "profile": {"display_name": name, "email": email},
            "real_name": name,
        }
    }


def _find_call_with_text(mock_calls: list, needle: str) -> dict | None:
    """Return the kwargs of the first call whose 'text' kwarg contains needle, else None."""
    for call in mock_calls:
        kwargs = call[1] if call[1] else {}
        if needle in kwargs.get("text", ""):
            return kwargs
    return None


# ---------------------------------------------------------------------------
# Test: on_dm_message handler (captured from _register_handlers)
# ---------------------------------------------------------------------------


class TestOnDmMessage:
    """Invoke the actual on_dm_message callback with mock payloads."""

    @pytest.mark.asyncio
    async def test_top_level_dm_creates_event(self):
        """Top-level DM (thread_ts=None) → event created, _dm_context populated."""
        sc, captured = _make_channel()
        on_dm = captured["event:message"]

        sc._blackboard.get_event_by_slack_thread.return_value = None
        sc._blackboard.create_event.return_value = "evt-new00001"

        client = AsyncMock()
        client.users_info.return_value = _user_info_response()

        await on_dm(_dm_event(thread_ts=None), client)

        assert "evt-new00001" in sc._dm_context
        ctx = sc._dm_context["evt-new00001"]
        assert ctx["channel"] == "D_DM"
        assert ctx["thread_ts"] == "1700000001.000001"
        assert ctx["user_id"] == "U_USER"
        assert ctx["team_id"] == "T_TEAM"
        sc._blackboard.create_event.assert_called_once()
        sc._blackboard.set_slack_mapping.assert_called_once_with(
            "D_DM", "1700000001.000001", "evt-new00001",
        )

    @pytest.mark.asyncio
    async def test_im_with_thread_ts_no_mapping_creates_event(self):
        """IM with thread_ts but no slack mapping → creates event (widened cutover gate)."""
        sc, captured = _make_channel()
        on_dm = captured["event:message"]

        sc._blackboard.get_event_by_slack_thread.return_value = None
        sc._blackboard.create_event.return_value = "evt-cutover1"

        client = AsyncMock()
        client.users_info.return_value = _user_info_response("Bob", "bob@ex.com")

        await on_dm(_dm_event(thread_ts="1700000001.000001"), client)

        assert "evt-cutover1" in sc._dm_context
        sc._blackboard.create_event.assert_called_once()

    @pytest.mark.asyncio
    async def test_threaded_reply_appends_turn_and_hydrates_context(self):
        """Reply in known thread → turn appended, _dm_context hydrated, brain resumed."""
        sc, captured = _make_channel()
        on_dm = captured["event:message"]

        event_doc = _mock_event_doc(event_id="evt-exist01", status="active")
        sc._blackboard.get_event_by_slack_thread.return_value = "evt-exist01"
        sc._blackboard.get_event.return_value = event_doc

        client = AsyncMock()
        client.users_info.return_value = _user_info_response("Charlie")

        await on_dm(
            _dm_event(text="follow up", thread_ts="1700000001.000001"),
            client,
        )

        assert "evt-exist01" in sc._dm_context
        sc._blackboard.append_turn.assert_called_once()
        appended_turn = sc._blackboard.append_turn.call_args[0][1]
        assert appended_turn.actor == "user"
        assert appended_turn.thoughts == "follow up"
        sc._brain.clear_waiting.assert_called_once_with("evt-exist01")
        sc._brain.resume_if_parked.assert_called_once_with("evt-exist01")
        sc._brain.enqueue_for_processing.assert_called_once_with("evt-exist01")

    @pytest.mark.asyncio
    async def test_non_im_no_thread_drops(self):
        """Non-IM channel with no thread_ts → silently dropped."""
        sc, captured = _make_channel()
        on_dm = captured["event:message"]

        client = AsyncMock()
        await on_dm(
            _dm_event(thread_ts=None, channel_type="channel", channel="C_RANDOM"),
            client,
        )

        sc._blackboard.create_event.assert_not_called()
        sc._blackboard.get_event_by_slack_thread.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_im_non_infra_with_thread_drops(self):
        """Non-IM, non-infra channel (even with thread_ts) → early return."""
        sc, captured = _make_channel()
        on_dm = captured["event:message"]

        client = AsyncMock()
        await on_dm(
            _dm_event(
                thread_ts="1700000001.000001",
                channel_type="channel",
                channel="C_RANDOM",
            ),
            client,
        )

        sc._blackboard.create_event.assert_not_called()


# ---------------------------------------------------------------------------
# Test: message ingestion paths call enqueue_for_processing (evt-4eeff00c Fix 1)
# ---------------------------------------------------------------------------


class TestAppMentionReplyEnqueues:
    """@mention reply on an existing open event (RC-1 ingestion path #1)."""

    @pytest.mark.asyncio
    async def test_reply_on_open_event_enqueues(self):
        sc, captured = _make_channel()
        on_mention = captured["event:app_mention"]

        event_doc = _mock_event_doc(event_id="evt-open0001", status="active")
        sc._blackboard.get_event_by_slack_thread.return_value = "evt-open0001"
        sc._blackboard.get_event.return_value = event_doc

        client = AsyncMock()
        client.users_info.return_value = _user_info_response("Dana")

        await on_mention(
            {
                "channel": "C_INFRA",
                "user": "U_USER",
                "text": "<@BOT> follow up question",
                "ts": "1700000002.000001",
                "thread_ts": "1700000001.000001",
            },
            client,
        )

        sc._blackboard.append_turn.assert_called_once()
        sc._brain.clear_waiting.assert_called_once_with("evt-open0001")
        sc._brain.resume_if_parked.assert_called_once_with("evt-open0001")
        sc._brain.enqueue_for_processing.assert_called_once_with("evt-open0001")


class TestApproveRejectActionsEnqueue:
    """darwin_approve / darwin_reject Block Kit actions (RC-1 ingestion paths #2, #3)."""

    @staticmethod
    def _action_body(event_id: str = "evt-appr0001") -> dict:
        return {
            "user": {"id": "U_USER"},
            "channel": {"id": "C_INFRA"},
            "message": {"ts": "1700000001.000001"},
            "actions": [{"value": event_id}],
        }

    @pytest.mark.asyncio
    async def test_approve_enqueues(self):
        sc, captured = _make_channel()
        handle_approve = captured["action:darwin_approve"]
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id="evt-appr0001")
        ack = AsyncMock()
        client = AsyncMock()

        await handle_approve(ack, self._action_body(), client)

        ack.assert_awaited_once()
        sc._blackboard.append_turn.assert_called_once()
        sc._brain.clear_waiting.assert_called_once_with("evt-appr0001")
        sc._brain.resume_if_parked.assert_called_once_with("evt-appr0001")
        sc._brain.enqueue_for_processing.assert_called_once_with("evt-appr0001")

    @pytest.mark.asyncio
    async def test_reject_enqueues(self):
        sc, captured = _make_channel()
        handle_reject = captured["action:darwin_reject"]
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id="evt-rej00001")
        ack = AsyncMock()
        client = AsyncMock()

        await handle_reject(ack, self._action_body(event_id="evt-rej00001"), client)

        ack.assert_awaited_once()
        sc._blackboard.append_turn.assert_called_once()
        sc._brain.clear_waiting.assert_called_once_with("evt-rej00001")
        sc._brain.resume_if_parked.assert_called_once_with("evt-rej00001")
        sc._brain.enqueue_for_processing.assert_called_once_with("evt-rej00001")

    @pytest.mark.asyncio
    async def test_approve_no_enqueue_when_event_missing(self):
        sc, captured = _make_channel()
        handle_approve = captured["action:darwin_approve"]
        sc._blackboard.get_event.return_value = None
        ack = AsyncMock()
        client = AsyncMock()

        await handle_approve(ack, self._action_body(), client)

        sc._brain.enqueue_for_processing.assert_not_called()


# ---------------------------------------------------------------------------
# Test: legacy turn routing — brain.response / brain.thoughts (T-1, T-2)
# ---------------------------------------------------------------------------


class TestLegacyTurnRouting:
    """Post-unification: no stream-delivered dedup guard remains on brain.response."""

    @pytest.mark.asyncio
    async def test_response_always_posts_block_kit(self):
        """T-1: brain.response always posts Block Kit — no dedup gating."""
        sc, _ = _make_channel()
        eid = "evt-resp-always"
        sc._dm_context[eid] = _dm_ctx()
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "response", "thoughts": "Done."},
        })

        sc._app.client.chat_postMessage.assert_called()

    @pytest.mark.asyncio
    async def test_thoughts_turn_suppressed(self):
        """T-2: brain.thoughts never reaches Slack."""
        sc, _ = _make_channel()
        eid = "evt-thoughts-suppressed"
        sc._dm_context[eid] = _dm_ctx()
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "thoughts", "thoughts": "Internal reasoning"},
        })

        sc._app.client.chat_postMessage.assert_not_called()
        sc._app.client.chat_update.assert_not_called()


# ---------------------------------------------------------------------------
# Test: brain_thinking status refresh + event_closed cleanup (T-3, T-4, T-5)
# ---------------------------------------------------------------------------


class TestBrainThinkingAndClosure:
    """Streaming removed: brain_thinking is now setStatus-only; closure clears progress too."""

    @pytest.mark.asyncio
    async def test_empty_text_brain_thinking_preserves_set_status(self):
        """T-3: empty-text brain_thinking for a DM still refreshes setStatus."""
        sc, _ = _make_channel()
        eid = "evt-thinking-empty"
        sc._dm_context[eid] = _dm_ctx()
        sc._refresh_thinking_status = AsyncMock()

        await sc.broadcast_handler({
            "type": "brain_thinking", "event_id": eid, "text": "", "is_thought": False,
        })

        sc._refresh_thinking_status.assert_called_once_with(eid)

    @pytest.mark.asyncio
    async def test_brain_thinking_with_text_is_noop(self):
        """T-4: brain_thinking WITH text is a no-op — no streaming call remains (net-new)."""
        sc, _ = _make_channel()
        eid = "evt-thinking-text"
        sc._dm_context[eid] = _dm_ctx()

        await sc.broadcast_handler({
            "type": "brain_thinking", "event_id": eid, "text": "Hello", "is_thought": False,
        })

        sc._app.client.chat_postMessage.assert_not_called()
        sc._app.client.chat_update.assert_not_called()
        assert not hasattr(sc._app.client, "chat_stream") or not sc._app.client.chat_stream.called

    @pytest.mark.asyncio
    async def test_event_closed_cleans_all_state_incl_progress(self):
        """T-5: event_closed clears _dm_context, _thinking_msg, _progress_ts; deletes progress msg."""
        sc, _ = _make_channel()
        eid = "evt-closing-progress"
        sc._dm_context[eid] = _dm_ctx()
        sc._thinking_msg[eid] = ("D_DM", "1700000001.000003")
        sc._progress_ts[eid] = "progress_ts_value"

        event_doc = _mock_event_doc(event_id=eid, slack_thread_ts=None)
        sc._blackboard.get_event.return_value = event_doc

        await sc.broadcast_handler({
            "type": "event_closed", "event_id": eid, "summary": "resolved",
        })

        assert eid not in sc._dm_context
        assert eid not in sc._thinking_msg
        assert eid not in sc._progress_ts
        sc._app.client.chat_delete.assert_called_once()
        _, del_kwargs = sc._app.client.chat_delete.call_args
        assert del_kwargs.get("ts") == "progress_ts_value"
        assert del_kwargs.get("channel") == "D_DM"


# ---------------------------------------------------------------------------
# Test: progress-bubble lifecycle for tool_result turns (T-6..T-16)
# ---------------------------------------------------------------------------


class TestProgressMessages:
    """Post/update/delete lifecycle of the single tool_result progress bubble."""

    @pytest.mark.asyncio
    async def test_progress_posted_on_first_tool_result(self):
        """T-6: DM + progress enabled + first tool_result → chat_postMessage with mapped phrase."""
        sc, _ = _make_channel()
        eid = "evt-progress-first"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_enabled = True
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)
        sc._app.client.chat_postMessage = AsyncMock(return_value={"ts": "progress_ts_value"})

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "tool_result",
                     "waitingFor": "consult_deep_memory"},
        })

        progress_call = _find_call_with_text(
            sc._app.client.chat_postMessage.call_args_list, "Checking knowledge base...",
        )
        assert progress_call is not None, "Expected a progress bubble post with the mapped phrase"
        assert progress_call.get("channel") == "D_DM"
        assert sc._progress_ts[eid] == "progress_ts_value"

    @pytest.mark.asyncio
    async def test_progress_updated_on_subsequent_tool_result(self):
        """T-7: second (different) tool_result while a bubble exists → chat_update, new phrase."""
        from src.channels.slack import _TOOL_PROGRESS_PHRASES

        sc, _ = _make_channel()
        eid = "evt-progress-update"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_enabled = True
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)
        sc._app.client.chat_postMessage = AsyncMock(return_value={"ts": "progress_ts_value"})

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "tool_result",
                     "waitingFor": "consult_deep_memory"},
        })
        assert sc._progress_ts[eid] == "progress_ts_value"

        first_phrase = _TOOL_PROGRESS_PHRASES.get("consult_deep_memory", "")
        other_tool = next(
            (k for k, v in _TOOL_PROGRESS_PHRASES.items() if v != first_phrase),
            None,
        )
        assert other_tool is not None, "Need a second tool with a distinct phrase to test update"

        sc._app.client.chat_update = AsyncMock()
        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 2, "actor": "brain", "action": "tool_result",
                     "waitingFor": other_tool},
        })

        sc._app.client.chat_update.assert_called_once()
        _, update_kwargs = sc._app.client.chat_update.call_args
        assert update_kwargs.get("ts") == "progress_ts_value"
        assert update_kwargs.get("channel") == "D_DM"
        assert _TOOL_PROGRESS_PHRASES[other_tool] in update_kwargs.get("text", "")

    @pytest.mark.asyncio
    async def test_progress_deleted_and_response_posted(self):
        """T-8: brain.response with a lingering progress bubble → delete, then post Block Kit."""
        sc, _ = _make_channel()
        eid = "evt-progress-response"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_ts[eid] = "progress_ts_value"
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 2, "actor": "brain", "action": "response",
                     "thoughts": "Here's the answer."},
        })

        sc._app.client.chat_delete.assert_called_once()
        _, del_kwargs = sc._app.client.chat_delete.call_args
        assert del_kwargs.get("ts") == "progress_ts_value"
        sc._app.client.chat_postMessage.assert_called()
        assert eid not in sc._progress_ts

    @pytest.mark.asyncio
    async def test_chat_delete_failure_does_not_block_response(self):
        """T-9: chat_delete raising must not prevent the Block Kit response from posting."""
        sc, _ = _make_channel()
        eid = "evt-progress-delete-fail"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_ts[eid] = "progress_ts_value"
        sc._app.client.chat_delete = AsyncMock(side_effect=Exception("API error"))
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 2, "actor": "brain", "action": "response",
                     "thoughts": "Here's the answer."},
        })

        sc._app.client.chat_postMessage.assert_called()

    @pytest.mark.asyncio
    async def test_progress_cleaned_on_event_closed_orphan(self):
        """T-10: lingering progress bubble (no thinking indicator) is still deleted on close."""
        sc, _ = _make_channel()
        eid = "evt-orphan-progress"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_ts[eid] = "orphan_ts_value"

        event_doc = _mock_event_doc(event_id=eid, slack_thread_ts=None)
        sc._blackboard.get_event.return_value = event_doc

        await sc.broadcast_handler({
            "type": "event_closed", "event_id": eid, "summary": "resolved",
        })

        sc._app.client.chat_delete.assert_called_once()
        _, del_kwargs = sc._app.client.chat_delete.call_args
        assert del_kwargs.get("ts") == "orphan_ts_value"
        assert eid not in sc._progress_ts

    @pytest.mark.asyncio
    async def test_progress_not_posted_for_non_dm(self):
        """T-11: no _dm_context (non-DM/legacy thread) → progress bubble never posted."""
        sc, _ = _make_channel()
        eid = "evt-non-dm-progress"
        sc._progress_enabled = True
        sc._blackboard.get_event.return_value = _mock_event_doc(
            event_id=eid, source="aligner", slack_channel_id="C_INFRA", slack_thread_ts=None,
        )

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "tool_result",
                     "waitingFor": "some_new_tool"},
        })

        sc._app.client.chat_postMessage.assert_not_called()
        assert eid not in sc._progress_ts

    @pytest.mark.asyncio
    async def test_unknown_tool_uses_default_phrase(self):
        """T-12: waitingFor not in _TOOL_PROGRESS_PHRASES → falls back to the default phrase."""
        sc, _ = _make_channel()
        eid = "evt-unknown-tool"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_enabled = True
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)
        sc._app.client.chat_postMessage = AsyncMock(return_value={"ts": "progress_ts_value"})

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "tool_result",
                     "waitingFor": "some_new_tool"},
        })

        progress_call = _find_call_with_text(
            sc._app.client.chat_postMessage.call_args_list, "FRIDAY is working...",
        )
        assert progress_call is not None, "Expected default progress phrase for unmapped tool"

    @pytest.mark.asyncio
    async def test_progress_survives_brain_thinking_done(self):
        """T-13: brain_thinking_done must NOT clear the progress bubble state."""
        sc, _ = _make_channel()
        eid = "evt-progress-survives"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_ts[eid] = "progress_ts_value"

        await sc.broadcast_handler({"type": "brain_thinking_done", "event_id": eid})

        assert sc._progress_ts.get(eid) == "progress_ts_value"

    @pytest.mark.asyncio
    async def test_progress_not_posted_when_disabled(self):
        """T-14: _progress_enabled=False → no progress bubble posted."""
        sc, _ = _make_channel()
        eid = "evt-progress-disabled"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_enabled = False
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "tool_result",
                     "waitingFor": "some_new_tool"},
        })

        sc._app.client.chat_postMessage.assert_not_called()
        assert eid not in sc._progress_ts

    @pytest.mark.asyncio
    async def test_phrase_dedup_skips_identical_update(self):
        """T-15: same tool reported twice → second update is skipped (phrase unchanged)."""
        sc, _ = _make_channel()
        eid = "evt-progress-dedup"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_enabled = True
        sc._progress_ts[eid] = "progress_ts_value"  # bubble already posted
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)
        sc._app.client.chat_update = AsyncMock()

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "tool_result",
                     "waitingFor": "some_new_tool"},
        })
        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 2, "actor": "brain", "action": "tool_result",
                     "waitingFor": "some_new_tool"},
        })

        sc._app.client.chat_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_gate_rejection_empty_waiting_for_no_progress(self):
        """T-16: falsy waitingFor filters gate-rejection turns → no progress bubble."""
        sc, _ = _make_channel()
        eid = "evt-empty-waitingfor"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_enabled = True
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "tool_result", "waitingFor": None},
        })

        sc._app.client.chat_postMessage.assert_not_called()
        assert eid not in sc._progress_ts


# ---------------------------------------------------------------------------
# Test: _ensure_dm_context lazy hydration (F2)
# ---------------------------------------------------------------------------


class TestEnsureDmContext:
    """Invoke _ensure_dm_context to verify lazy hydration from blackboard."""

    @pytest.mark.asyncio
    async def test_returns_true_if_already_populated(self):
        sc, _ = _make_channel()
        sc._dm_context["evt-x"] = _dm_ctx(thread_ts="1.1")

        result = await sc._ensure_dm_context("evt-x")

        assert result is True
        sc._blackboard.get_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_hydrates_from_event_doc(self):
        """Missing _dm_context + DM event → hydrated from blackboard (F2)."""
        sc, _ = _make_channel()
        event_doc = _mock_event_doc(
            event_id="evt-race",
            source="slack",
            slack_channel_id="D_RACE",
            slack_thread_ts="1700000002.000001",
            slack_user_id="U_FAST",
        )
        sc._blackboard.get_event.return_value = event_doc

        result = await sc._ensure_dm_context("evt-race")

        assert result is True
        ctx = sc._dm_context["evt-race"]
        assert ctx["channel"] == "D_RACE"
        assert ctx["thread_ts"] == "1700000002.000001"
        assert ctx["user_id"] == "U_FAST"

    @pytest.mark.asyncio
    async def test_returns_false_for_non_dm_event(self):
        """Non-DM event (channel doesn't start with D) → not hydrated."""
        sc, _ = _make_channel()
        event_doc = _mock_event_doc(
            source="aligner",
            slack_channel_id="C_INFRA",
        )
        sc._blackboard.get_event.return_value = event_doc

        result = await sc._ensure_dm_context("evt-infra")

        assert result is False
        assert "evt-infra" not in sc._dm_context

    @pytest.mark.asyncio
    async def test_returns_false_for_missing_event(self):
        sc, _ = _make_channel()
        sc._blackboard.get_event.return_value = None

        result = await sc._ensure_dm_context("evt-gone")

        assert result is False


# ---------------------------------------------------------------------------
# Test: _refresh_thinking_status debounce (F4)
# ---------------------------------------------------------------------------


class TestRefreshThinkingStatus:
    """Invoke _refresh_thinking_status to verify debounce + timestamp-before-try."""

    @pytest.mark.asyncio
    async def test_debounce_bumps_before_api_call(self):
        """Timestamp bumped BEFORE API call — failure still prevents retry storm (F4)."""
        sc, _ = _make_channel()
        eid = "evt-debounce"
        sc._dm_context[eid] = {
            "channel": "D_DM", "thread_ts": "1.1",
            "user_id": "U", "team_id": "T",
            "_last_status_at": 0,
        }

        sc._app.client.assistant_threads_setStatus = AsyncMock(
            side_effect=Exception("rate_limited"),
        )

        before = time.time()
        await sc._refresh_thinking_status(eid)

        assert sc._dm_context[eid]["_last_status_at"] >= before

        await sc._refresh_thinking_status(eid)
        sc._app.client.assistant_threads_setStatus.assert_called_once()

    @pytest.mark.asyncio
    async def test_debounce_skips_within_window(self):
        sc, _ = _make_channel()
        eid = "evt-skip"
        sc._dm_context[eid] = {
            "channel": "D_DM", "thread_ts": "1.1",
            "user_id": "U", "team_id": "T",
            "_last_status_at": time.time(),
        }

        await sc._refresh_thinking_status(eid)

        sc._app.client.assistant_threads_setStatus.assert_not_called()


# ---------------------------------------------------------------------------
# Test: System-initiated DM context population (F8)
# ---------------------------------------------------------------------------


class TestSystemInitiatedDmContext:
    """Verify _dm_context populated for system-initiated DMs."""

    @pytest.mark.asyncio
    async def test_open_dm_thread_populates_context(self):
        """open_dm_thread → _dm_context populated (F8)."""
        sc, _ = _make_channel()
        event_doc = _mock_event_doc(event_id="evt-sysdm")

        sc._app.client.conversations_open = AsyncMock(
            return_value={"channel": {"id": "D_SYSDM"}},
        )
        sc._app.client.chat_postMessage = AsyncMock(
            return_value={"ts": "1700000003.000001", "channel": "D_SYSDM"},
        )

        await sc.open_dm_thread("U_TARGET", event_doc, "Alert triggered")

        assert "evt-sysdm" in sc._dm_context
        ctx = sc._dm_context["evt-sysdm"]
        assert ctx["channel"] == "D_SYSDM"
        assert ctx["thread_ts"] == "1700000003.000001"
        assert ctx["user_id"] == "U_TARGET"

    @pytest.mark.asyncio
    async def test_create_event_modal_populates_context(self):
        """handle_create_event_modal → _dm_context populated (F8)."""
        sc, captured = _make_channel()
        modal_handler = captured["view:darwin_create_event_modal"]

        sc._blackboard.create_event.return_value = "evt-modal1"
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id="evt-modal1")

        ack = AsyncMock()
        client = AsyncMock()
        client.users_info.return_value = _user_info_response()
        client.chat_postMessage = AsyncMock(return_value={
            "ts": "1700000004.000001",
            "channel": "D_MODAL",
        })

        body = {"user": {"id": "U_USER"}}
        view = {
            "state": {
                "values": {
                    "event_description": {
                        "description_input": {"value": "test issue"},
                    },
                },
            },
        }

        await modal_handler(ack, body, client, view)

        assert "evt-modal1" in sc._dm_context
        ctx = sc._dm_context["evt-modal1"]
        assert ctx["channel"] == "D_MODAL"
        assert ctx["thread_ts"] == "1700000004.000001"
        assert ctx["user_id"] == "U_USER"


# ---------------------------------------------------------------------------
# Test: Cross-thread redirect ack
# ---------------------------------------------------------------------------


class TestCrossThreadRedirectAck:
    """Verify DM reply on event with different slack_channel_id → redirect posted."""

    @pytest.mark.asyncio
    async def test_cross_thread_redirect_posts_link(self):
        sc, captured = _make_channel()
        on_dm = captured["event:message"]

        event_doc = _mock_event_doc(
            event_id="evt-redirect",
            status="active",
            slack_channel_id="C_INFRA",
            slack_thread_ts="1700000002.000001",
        )
        sc._blackboard.get_event_by_slack_thread.return_value = "evt-redirect"
        sc._blackboard.get_event.return_value = event_doc

        client = AsyncMock()
        client.users_info.return_value = _user_info_response("Dave")

        await on_dm(
            _dm_event(text="any update?", channel="D_DM",
                      thread_ts="1700000001.000001"),
            client,
        )

        redirect_call = _find_call_with_text(
            client.chat_postMessage.call_args_list, "Continue in #darwin-infra",
        )
        assert redirect_call is not None
        assert redirect_call["channel"] == "D_DM"
        assert "C_INFRA" in redirect_call["text"]
