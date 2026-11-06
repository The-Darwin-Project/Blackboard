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

import asyncio
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
    sc._progress_locks = {}  # event_id -> asyncio.Lock, serializes post/update/cleanup (TOCTOU fix)
    sc._progress_enabled = False

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
    async def test_top_level_dm_seeds_user_turn(self):
        """B-T7 (evt-996e33ec): top-level DM creates the event WITH its first user turn."""
        sc, captured = _make_channel()
        on_dm = captured["event:message"]

        sc._blackboard.get_event_by_slack_thread.return_value = None
        sc._blackboard.create_event.return_value = "evt-seed0001"

        client = AsyncMock()
        client.users_info.return_value = _user_info_response("Alice")

        await on_dm(_dm_event(text="Hi Friday", thread_ts=None), client)

        seeded = sc._blackboard.create_event.call_args.kwargs["initial_turns"]
        assert len(seeded) == 1
        assert seeded[0].actor == "user"
        assert seeded[0].source == "slack"
        assert seeded[0].thoughts == "Hi Friday"
        assert seeded[0].user_name == "Alice"
        sc._blackboard.append_turn.assert_not_called()

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


class TestSlackEventSeeding:
    """evt-996e33ec: user-initiated Slack events are created with their turns (no append race)."""

    @pytest.mark.asyncio
    async def test_followup_event_seeds_context_and_user_turns(self):
        """B-T8: closed-thread follow-up seeds [brain.context, user.message]; no append_turn."""
        sc, captured = _make_channel()
        on_mention = captured["event:app_mention"]

        closed_doc = _mock_event_doc(event_id="evt-closed01", status="closed")
        sc._blackboard.get_event_by_slack_thread.return_value = "evt-closed01"
        sc._blackboard.get_event.return_value = closed_doc
        sc._blackboard.create_event.return_value = "evt-follow01"

        client = AsyncMock()
        client.users_info.return_value = _user_info_response("Dana")

        await on_mention(
            {
                "channel": "C_INFRA", "user": "U_USER",
                "text": "<@BOT> one more thing", "ts": "1700000002.000001",
                "thread_ts": "1700000001.000001",
            },
            client,
        )

        kwargs = sc._blackboard.create_event.call_args.kwargs
        seeded = kwargs["initial_turns"]
        assert [(t.actor, t.action) for t in seeded] == [("brain", "context"), ("user", "message")]
        assert seeded[0].source == "system"
        assert seeded[1].source == "slack"
        assert seeded[1].thoughts == "one more thing"
        assert seeded[1].user_name == "Dana"
        sc._blackboard.append_turn.assert_not_called()
        sc._blackboard.set_slack_mapping.assert_called_once_with(
            "C_INFRA", "1700000001.000001", "evt-follow01",
        )

    @pytest.mark.asyncio
    async def test_app_mention_passes_slack_context_and_seed(self):
        """B-T9: new @mention event gets slack context + first turn at create time."""
        sc, captured = _make_channel()
        on_mention = captured["event:app_mention"]

        sc._blackboard.get_event_by_slack_thread.return_value = None
        sc._blackboard.create_event.return_value = "evt-mention1"

        client = AsyncMock()
        client.users_info.return_value = _user_info_response("Eve")

        await on_mention(
            {
                "channel": "C_INFRA", "user": "U_USER",
                "text": "<@BOT> please look", "ts": "1700000009.000001",
            },
            client,
        )

        kwargs = sc._blackboard.create_event.call_args.kwargs
        assert kwargs["slack_channel_id"] == "C_INFRA"
        assert kwargs["slack_thread_ts"] == "1700000009.000001"
        assert kwargs["slack_user_id"] == "U_USER"
        assert kwargs["initial_turns"][0].thoughts == "please look"
        sc._blackboard.update_event_slack_context.assert_not_called()
        sc._blackboard.append_turn.assert_not_called()
        sc._blackboard.set_slack_mapping.assert_called_once_with(
            "C_INFRA", "1700000009.000001", "evt-mention1",
        )


class TestSlackCommandAndModalSeeding:
    """evt-996e33ec: slash-command and Home-modal events are created WITH their first turn."""

    @pytest.mark.asyncio
    async def test_slash_command_seeds_user_turn(self):
        sc, captured = _make_channel()
        on_command = captured["command:/darwin"]
        sc._blackboard.create_event.return_value = "evt-slash001"
        client = AsyncMock()
        client.users_info.return_value = _user_info_response("Frank")
        client.chat_postMessage.return_value = {"ts": "1700000010.000001"}
        respond = AsyncMock()

        await on_command(
            AsyncMock(), {"text": " check the store ", "user_id": "U_USER", "channel_id": "C_INFRA"},
            client, respond,
        )

        seeded = sc._blackboard.create_event.call_args.kwargs["initial_turns"]
        assert len(seeded) == 1
        assert (seeded[0].actor, seeded[0].action, seeded[0].source) == ("user", "message", "slack")
        assert seeded[0].thoughts == "check the store"
        assert seeded[0].user_name == "Frank"
        sc._blackboard.append_turn.assert_not_called()

    @pytest.mark.asyncio
    async def test_home_modal_seeds_user_turn(self):
        sc, captured = _make_channel()
        on_modal = captured["view:darwin_create_event_modal"]
        sc._blackboard.create_event.return_value = "evt-modal001"
        client = AsyncMock()
        client.users_info.return_value = _user_info_response("Gina")
        client.chat_postMessage.return_value = {"ts": "1700000011.000001", "channel": "D_GINA"}
        view = {"state": {"values": {"event_description": {"description_input": {"value": "  store is down "}}}}}

        await on_modal(AsyncMock(), {"user": {"id": "U_GINA"}}, client, view)

        seeded = sc._blackboard.create_event.call_args.kwargs["initial_turns"]
        assert len(seeded) == 1
        assert (seeded[0].actor, seeded[0].action, seeded[0].source) == ("user", "message", "slack")
        assert seeded[0].thoughts == "store is down"
        assert seeded[0].user_name == "Gina"
        sc._blackboard.append_turn.assert_not_called()


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
# Test: circuit breaker symmetry (HIGH #2 fix regression coverage)
# ---------------------------------------------------------------------------


class TestCircuitBreakerSymmetry:
    """Pre-fix, only the initial chat_postMessage failure armed _progress_failed;
    a chat_update failure (bubble already posted) was logged but never armed the
    breaker, so outages/rate-limits/deleted-message/revoked-scope errors retried
    on every future tool_result turn. The fix arms the breaker on ANY post/update
    exception -- these tests cover both arms plus the post-arming skip behavior.
    """

    @pytest.mark.asyncio
    async def test_initial_post_failure_arms_breaker(self):
        """T-17: chat_postMessage failure (no bubble yet) arms the breaker."""
        sc, _ = _make_channel()
        eid = "evt-breaker-post-fail"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_enabled = True
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)
        sc._app.client.chat_postMessage = AsyncMock(side_effect=Exception("rate limited"))

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "tool_result",
                     "waitingFor": "consult_deep_memory"},
        })

        assert eid in sc._progress_failed
        assert eid not in sc._progress_ts

    @pytest.mark.asyncio
    async def test_chat_update_failure_arms_breaker(self):
        """T-18: HIGH #2 regression -- a chat_update failure (bubble already exists)
        must also arm the breaker, not just the initial post failure."""
        from src.channels.slack import _TOOL_PROGRESS_PHRASES

        sc, _ = _make_channel()
        eid = "evt-breaker-update-fail"
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
        assert eid not in sc._progress_failed

        first_phrase = _TOOL_PROGRESS_PHRASES.get("consult_deep_memory", "")
        other_tool = next(
            (k for k, v in _TOOL_PROGRESS_PHRASES.items() if v != first_phrase),
            None,
        )
        assert other_tool is not None, "Need a second tool with a distinct phrase to reach chat_update"

        sc._app.client.chat_update = AsyncMock(side_effect=Exception("channel_not_found"))

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 2, "actor": "brain", "action": "tool_result",
                     "waitingFor": other_tool},
        })

        assert eid in sc._progress_failed, (
            "chat_update failure must arm the breaker -- pre-fix this path was silently "
            "retried on every future turn since only the initial-post branch armed it"
        )

    @pytest.mark.asyncio
    async def test_breaker_armed_via_update_failure_stops_further_attempts(self):
        """T-19: once armed (via an update failure), later tool_result turns for the
        same event must not attempt a progress-bubble chat_postMessage/chat_update.

        Uses a tool NOT in _USER_VISIBLE_TOOL_RESULTS so the only chat_postMessage/
        chat_update call site reachable is the progress-bubble one -- otherwise the
        turn's own (unrelated) Block Kit content post would confound the assertion.
        """
        sc, _ = _make_channel()
        eid = "evt-breaker-armed"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_enabled = True
        sc._progress_ts[eid] = "progress_ts_value"
        sc._progress_failed.add(eid)
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 3, "actor": "brain", "action": "tool_result",
                     "waitingFor": "classify_event"},
        })

        sc._app.client.chat_update.assert_not_called()
        sc._app.client.chat_postMessage.assert_not_called()


# ---------------------------------------------------------------------------
# Test: deferred cleanup branch (event_status_changed, HIGH #4 consolidation)
# ---------------------------------------------------------------------------


class TestDeferredCleanupBranch:
    """The event_status_changed/deferred branch had zero test coverage pre-fix.
    It now shares _cleanup_progress_bubble() with the event_closed and response
    teardown sites (HIGH #4); these tests exercise it directly.
    """

    @pytest.mark.asyncio
    async def test_deferred_status_cleans_up_progress_bubble(self):
        """T-20: status='deferred' deletes the open bubble and clears all tracking state."""
        sc, _ = _make_channel()
        eid = "evt-deferred-cleanup"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_ts[eid] = "progress_ts_value"
        sc._progress_last_phrase[eid] = "Checking knowledge base..."
        sc._progress_failed.add(eid)

        await sc.broadcast_handler({
            "type": "event_status_changed", "event_id": eid, "status": "deferred",
        })

        sc._app.client.chat_delete.assert_called_once()
        _, del_kwargs = sc._app.client.chat_delete.call_args
        assert del_kwargs.get("ts") == "progress_ts_value"
        assert del_kwargs.get("channel") == "D_DM"
        assert eid not in sc._progress_ts
        assert eid not in sc._progress_last_phrase
        assert eid not in sc._progress_failed

    @pytest.mark.asyncio
    async def test_deferred_status_noop_when_no_bubble(self):
        """T-21: no open bubble → deferred status change is a silent no-op."""
        sc, _ = _make_channel()
        eid = "evt-deferred-no-bubble"
        sc._dm_context[eid] = _dm_ctx()

        await sc.broadcast_handler({
            "type": "event_status_changed", "event_id": eid, "status": "deferred",
        })

        sc._app.client.chat_delete.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_deferred_status_change_leaves_bubble_untouched(self):
        """T-22: only status=='deferred' triggers cleanup -- other status values must not."""
        sc, _ = _make_channel()
        eid = "evt-status-active"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_ts[eid] = "progress_ts_value"

        await sc.broadcast_handler({
            "type": "event_status_changed", "event_id": eid, "status": "active",
        })

        sc._app.client.chat_delete.assert_not_called()
        assert sc._progress_ts.get(eid) == "progress_ts_value"

    @pytest.mark.asyncio
    async def test_event_title_updated_syncs_dm_thread_title(self):
        """event_title_updated broadcast invokes assistant_threads_setTitle for DMs."""
        sc, _ = _make_channel()
        eid = "evt-title-sync"
        doc = _mock_event_doc(
            event_id=eid,
            slack_channel_id="D123456",
            slack_thread_ts="1234567890.123456",
        )
        sc._blackboard.get_event.return_value = doc
        sc._app.client.assistant_threads_setTitle = AsyncMock()

        await sc.broadcast_handler({
            "type": "event_title_updated",
            "event_id": eid,
            "title": "Investigate High CPU",
            "title_source": "user",
        })

        sc._app.client.assistant_threads_setTitle.assert_awaited_once_with(
            channel_id="D123456",
            thread_ts="1234567890.123456",
            title="Investigate High CPU",
        )

    @pytest.mark.asyncio
    async def test_event_title_updated_ignores_non_dm_channel(self):
        """event_title_updated broadcast does NOT call assistant_threads_setTitle for non-DM channels."""
        sc, _ = _make_channel()
        eid = "evt-title-public"
        doc = _mock_event_doc(
            event_id=eid,
            slack_channel_id="C123456",
            slack_thread_ts="1234567890.123456",
        )
        sc._blackboard.get_event.return_value = doc
        sc._app.client.assistant_threads_setTitle = AsyncMock()

        await sc.broadcast_handler({
            "type": "event_title_updated",
            "event_id": eid,
            "title": "Investigate High CPU",
            "title_source": "user",
        })

        sc._app.client.assistant_threads_setTitle.assert_not_called()


# ---------------------------------------------------------------------------
# Test: stop() shutdown behavior (HIGH #1 fix)
# ---------------------------------------------------------------------------


class TestStopShutdown:
    """Pre-fix, stop() disconnected the Socket Mode handler without cleaning up
    _progress_ts, permanently orphaning any open "FRIDAY is working..." DM on
    graceful shutdown/redeploy. These tests cover the new sweep.
    """

    @pytest.mark.asyncio
    async def test_stop_cleans_up_all_open_progress_bubbles(self):
        """T-23: stop() tears down every open progress bubble across all events."""
        sc, _ = _make_channel()
        eid1, eid2 = "evt-shutdown-1", "evt-shutdown-2"
        sc._dm_context[eid1] = _dm_ctx(channel="D_DM1")
        sc._dm_context[eid2] = _dm_ctx(channel="D_DM2")
        sc._progress_ts[eid1] = "ts1"
        sc._progress_ts[eid2] = "ts2"
        sc._handler = None

        await sc.stop()

        assert sc._app.client.chat_delete.call_count == 2
        deleted_ts = {
            call.kwargs.get("ts") for call in sc._app.client.chat_delete.call_args_list
        }
        assert deleted_ts == {"ts1", "ts2"}
        assert eid1 not in sc._progress_ts
        assert eid2 not in sc._progress_ts

    @pytest.mark.asyncio
    async def test_stop_with_no_open_bubbles_still_disconnects_handler(self):
        """T-24: no open bubbles → no chat_delete calls, but the handler still disconnects."""
        sc, _ = _make_channel()
        sc._handler = AsyncMock()

        await sc.stop()

        sc._app.client.chat_delete.assert_not_called()
        sc._handler.close_async.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_cleans_up_bubbles_before_disconnecting_handler(self):
        """T-25: cleanup must complete before the Socket Mode handler disconnects."""
        sc, _ = _make_channel()
        eid = "evt-shutdown-order"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_ts[eid] = "progress_ts_value"
        sc._handler = AsyncMock()

        call_order: list[str] = []
        sc._app.client.chat_delete.side_effect = lambda **kw: call_order.append("chat_delete")
        sc._handler.close_async.side_effect = lambda: call_order.append("close_async")

        await sc.stop()

        assert call_order == ["chat_delete", "close_async"]

    @pytest.mark.asyncio
    async def test_stop_bubble_delete_failure_does_not_block_handler_disconnect(self):
        """T-26: a chat_delete failure during shutdown sweep must not prevent the
        handler from disconnecting (mirrors the existing response-path resilience test)."""
        sc, _ = _make_channel()
        eid = "evt-shutdown-delete-fail"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_ts[eid] = "progress_ts_value"
        sc._app.client.chat_delete = AsyncMock(side_effect=Exception("API error"))
        sc._handler = AsyncMock()

        await sc.stop()

        sc._handler.close_async.assert_called_once()


# ---------------------------------------------------------------------------
# Test: progress lock serializes concurrent post/update (HIGH #3 TOCTOU fix)
# ---------------------------------------------------------------------------


class TestProgressLockConcurrency:
    """Pre-fix, the 'no ts yet' check and the self._progress_ts[event_id] write were
    separated by an unguarded await on chat_postMessage, so two concurrent tool_result
    turns for the same event_id could both observe "no ts yet" and double-post. The
    fix serializes the whole check-through-write under a per-event asyncio.Lock.
    """

    @pytest.mark.asyncio
    async def test_concurrent_tool_result_turns_do_not_double_post(self):
        """T-27: two tool_result turns racing on the same event_id must result in
        exactly one chat_postMessage; the second (once serialized by the lock) sees
        the ts already populated and updates instead of posting again.

        Uses two tools NOT in _USER_VISIBLE_TOOL_RESULTS (distinct phrases, to avoid
        the dedup check masking the race) so _handle_legacy_turn returns right after
        the progress-bubble block -- otherwise the turn's own (unrelated) Block Kit
        content post would confound the chat_postMessage call-count assertion.
        """
        from src.channels.slack import _TOOL_PROGRESS_PHRASES, _USER_VISIBLE_TOOL_RESULTS

        sc, _ = _make_channel()
        eid = "evt-toctou"
        sc._dm_context[eid] = _dm_ctx()
        sc._progress_enabled = True
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        async def slow_post(**kwargs):
            await asyncio.sleep(0)  # yield control mid-call, simulating network latency
            return {"ts": "progress_ts_value"}

        sc._app.client.chat_postMessage = AsyncMock(side_effect=slow_post)
        sc._app.client.chat_update = AsyncMock()

        tool_a = "classify_event"
        assert tool_a not in _USER_VISIBLE_TOOL_RESULTS
        phrase_a = _TOOL_PROGRESS_PHRASES.get(tool_a, "")
        tool_b = next(
            (k for k, v in _TOOL_PROGRESS_PHRASES.items()
             if v != phrase_a and k not in _USER_VISIBLE_TOOL_RESULTS),
            None,
        )
        assert tool_b is not None, "Need a second tool with a distinct phrase to avoid dedup masking the race"

        await asyncio.gather(
            sc.broadcast_handler({
                "type": "turn", "event_id": eid,
                "turn": {"turn": 1, "actor": "brain", "action": "tool_result", "waitingFor": tool_a},
            }),
            sc.broadcast_handler({
                "type": "turn", "event_id": eid,
                "turn": {"turn": 2, "actor": "brain", "action": "tool_result", "waitingFor": tool_b},
            }),
        )

        assert sc._app.client.chat_postMessage.call_count == 1, (
            "lock must serialize the check-then-post so only one of the two racing "
            "turns ever posts the initial bubble"
        )
        assert sc._app.client.chat_update.call_count == 1, (
            "the second turn, once serialized, should see the ts already set and update"
        )
        assert sc._progress_ts[eid] == "progress_ts_value"


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


# ---------------------------------------------------------------------------
# Test: Table Rejection Fallback Retry
# ---------------------------------------------------------------------------


class TestTableRejectionFallback:
    """Verify SlackApiError on table_blocks triggers monospaced code block retry."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize("error_code", ["invalid_blocks", "invalid_attachments"])
    async def test_table_rejection_fallback_retries_with_code_block(self, error_code):
        from slack_sdk.errors import SlackApiError

        sc, _ = _make_channel()

        first_call_error = SlackApiError(
            message="The request to the Slack API failed.",
            response={"ok": False, "error": error_code},
        )
        sc._app.client.chat_postMessage.side_effect = [
            first_call_error,
            {"ok": True, "ts": "1700000001.000002"},
        ]

        table_blocks = [
            {
                "type": "table",
                "rows": [
                    [{"type": "raw_text", "text": "ColA"}, {"type": "raw_text", "text": "ColB"}],
                    [{"type": "raw_text", "text": "Val1"}, {"type": "raw_text", "text": "Val2"}],
                ],
            }
        ]

        await sc._post_to_thread(
            channel="C_TEST",
            thread_ts="1700000001.000001",
            text="Report with table",
            table_blocks=table_blocks,
        )

        assert sc._app.client.chat_postMessage.call_count == 2

        # First call included table_blocks in attachments
        first_call_kwargs = sc._app.client.chat_postMessage.call_args_list[0].kwargs
        assert first_call_kwargs["channel"] == "C_TEST"
        assert first_call_kwargs["attachments"] == [{"blocks": table_blocks}]

        # Second call removed table_blocks from attachments and appended section code block
        second_call_kwargs = sc._app.client.chat_postMessage.call_args_list[1].kwargs
        assert second_call_kwargs["channel"] == "C_TEST"
        assert second_call_kwargs["thread_ts"] == "1700000001.000001"
        assert second_call_kwargs["text"] == "Report with table"

        # Attachments should no longer have table_blocks
        retry_attachments = second_call_kwargs.get("attachments", [])
        for att in retry_attachments:
            assert att.get("blocks") is not table_blocks

        # Fallback section block must contain ASCII code block with table data
        retry_blocks = second_call_kwargs.get("blocks", [])
        assert len(retry_blocks) >= 1
        fallback_block = retry_blocks[-1]
        assert fallback_block.get("type") == "section"
        block_text = fallback_block.get("text", {}).get("text", "")
        assert block_text.startswith("```")
        assert "ColA" in block_text
        assert "ColB" in block_text
        assert "Val1" in block_text
        assert "Val2" in block_text

    @pytest.mark.asyncio
    async def test_post_to_thread_table_blocks_fallback_with_colored_attachment(self):
        """When attachment_color is set, fallback code block is appended to the colored attachment."""
        from slack_sdk.errors import SlackApiError

        sc, _ = _make_channel()
        error_response = {
            "ok": False,
            "error": "invalid_blocks",
        }
        sc._app.client.chat_postMessage.side_effect = [
            SlackApiError(message="invalid_blocks", response=error_response),
            {"ok": True, "ts": "1700000002.000001"},
        ]

        main_block = {"type": "section", "text": {"type": "mrkdwn", "text": "Agent message"}}
        table_blocks = [
            {
                "type": "table",
                "rows": [
                    [{"type": "raw_text", "text": "Col1"}],
                    [{"type": "raw_text", "text": "Val1"}],
                ],
            }
        ]

        await sc._post_to_thread(
            channel="C_TEST",
            thread_ts="1700000001.000001",
            text="Fallback colored test",
            blocks=[main_block],
            attachment_color="#3b82f6",
            table_blocks=table_blocks,
        )

        assert sc._app.client.chat_postMessage.call_count == 2
        retry_kwargs = sc._app.client.chat_postMessage.call_args_list[1].kwargs

        # Top-level blocks should NOT contain the fallback block (which would render above the colored attachment)
        assert "blocks" not in retry_kwargs

        # Attachment blocks should contain main block followed by the fallback table code block
        attachments = retry_kwargs.get("attachments", [])
        assert len(attachments) == 1
        assert attachments[0]["color"] == "#3b82f6"
        att_blocks = attachments[0]["blocks"]
        assert len(att_blocks) == 2
        assert att_blocks[0] == main_block
        assert att_blocks[1]["type"] == "section"
        assert "Col1" in att_blocks[1]["text"]["text"]


# ---------------------------------------------------------------------------
# Test: Slack Connector Remediation (VMER-2270 / Scenarios T-1 through T-10)
# ---------------------------------------------------------------------------


class TestSlackConnectorRemediation:
    """Acceptance & unit tests for Slack connector noise suppression, thinking lifecycle, and RBAC approval."""

    @pytest.mark.asyncio
    async def test_t1_cognitive_tool_result_suppressed(self):
        """T-1: consult_deep_memory tool_result is suppressed from human chat."""
        sc, _ = _make_channel()
        eid = "evt-c474dfe7"
        sc._dm_context[eid] = _dm_ctx()
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {
                "turn": 10,
                "actor": "brain",
                "action": "tool_result",
                "waitingFor": "consult_deep_memory",
                "evidence": '{"embeddings": [0.1, 0.2], "matches": []}',
            },
        })

        sc._app.client.chat_postMessage.assert_not_called()

    @pytest.mark.asyncio
    async def test_t2_user_confirmation_tool_result_posted(self):
        """T-2: take_note tool_result is user-visible and posted to thread."""
        sc, _ = _make_channel()
        eid = "evt-note-001"
        sc._dm_context[eid] = _dm_ctx()
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {
                "turn": 11,
                "actor": "brain",
                "action": "tool_result",
                "waitingFor": "take_note",
                "evidence": "Note has been saved to blackboard.",
            },
        })

        sc._app.client.chat_postMessage.assert_called()

    @pytest.mark.asyncio
    async def test_t3_subagent_worker_turns_suppressed(self):
        """T-3: explorer.execute and subagent turns suppressed by _INTERNAL_TURNS."""
        sc, _ = _make_channel()
        eid = "evt-subagent-worker"
        sc._dm_context[eid] = _dm_ctx()
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {
                "turn": 25,
                "actor": "explorer",
                "action": "execute",
                "result": "7KB terminal bash dump",
            },
        })

        sc._app.client.chat_postMessage.assert_not_called()

    @pytest.mark.asyncio
    async def test_t4_approve_cold_cache_resolves_email_first(self):
        """T-4: handle_approve resolves email BEFORE checking can_approve_event, stamps turn."""
        from unittest.mock import patch
        sc, captured = _make_channel()
        handle_approve = captured["action:darwin_approve"]
        eid = "evt-abb39748"
        doc = _mock_event_doc(event_id=eid)
        doc.created_by_email = "approver@redhat.com"
        sc._blackboard.get_event.return_value = doc

        client = AsyncMock()
        client.users_info.return_value = {
            "ok": True,
            "user": {
                "profile": {
                    "display_name": "Approver User",
                    "real_name": "Approver User",
                    "email": "approver@redhat.com",
                }
            }
        }

        body = {
            "user": {"id": "U_APPROVER"},
            "channel": {"id": "C_CHAN"},
            "message": {"ts": "1700000000.123", "thread_ts": "1700000000.100"},
            "actions": [{"value": eid}],
        }
        ack = AsyncMock()

        with patch("src.auth.DEX_ENABLED", True):
            await handle_approve(ack, body, client)

        ack.assert_awaited_once()
        sc._blackboard.append_turn.assert_called_once()
        turn_arg = sc._blackboard.append_turn.call_args.args[1]
        assert turn_arg.action == "approve"
        assert turn_arg.user == "Approver User"
        assert turn_arg.user_email == "approver@redhat.com"

    @pytest.mark.asyncio
    async def test_t5_approve_unauthorized_sends_ephemeral_rejection(self):
        """T-5: Unauthorized user approval receives chat_postEphemeral and appends no turn."""
        from unittest.mock import patch
        sc, captured = _make_channel()
        handle_approve = captured["action:darwin_approve"]
        eid = "evt-unauth-001"
        doc = _mock_event_doc(event_id=eid)
        doc.created_by_email = "owner@redhat.com"
        sc._blackboard.get_event.return_value = doc

        client = AsyncMock()
        client.users_info.return_value = {
            "ok": True,
            "user": {
                "profile": {
                    "display_name": "Eve Attacker",
                    "real_name": "Eve Attacker",
                    "email": "eve@unauthorized.com",
                }
            }
        }

        body = {
            "user": {"id": "U_EVE"},
            "channel": {"id": "C_CHAN"},
            "message": {"ts": "1700000000.123", "thread_ts": "1700000000.100"},
            "actions": [{"value": eid}],
        }
        ack = AsyncMock()

        with patch("src.auth.DEX_ENABLED", True):
            await handle_approve(ack, body, client)

        ack.assert_awaited_once()
        sc._blackboard.append_turn.assert_not_called()
        client.chat_postEphemeral.assert_called_once()
        ephemeral_text = client.chat_postEphemeral.call_args.kwargs.get("text", "")
        assert "not authorized to approve" in ephemeral_text

    @pytest.mark.asyncio
    async def test_t6_create_event_passes_created_by_email(self):
        """T-6: Event creation sites resolve and pass created_by_email."""
        from unittest.mock import patch
        sc, captured = _make_channel()
        handle_cmd = captured["command:/darwin"]

        client = AsyncMock()
        client.users_info.return_value = {
            "ok": True,
            "user": {
                "profile": {
                    "display_name": "Alice Bob",
                    "real_name": "Alice Bob",
                    "email": "alice@redhat.com",
                }
            }
        }
        cmd_body = {
            "user_id": "U_ALICE",
            "channel_id": "C_DEV",
            "text": "investigate memory spike",
            "trigger_id": "trig-123",
        }
        ack = AsyncMock()
        respond = AsyncMock()

        sc._blackboard.create_event.return_value = _mock_event_doc(event_id="evt-cmd-001")

        await handle_cmd(ack, cmd_body, client, respond)

        ack.assert_awaited_once()
        sc._blackboard.create_event.assert_called_once()
        call_kwargs = sc._blackboard.create_event.call_args.kwargs
        assert call_kwargs.get("created_by_email") == "alice@redhat.com"

    @pytest.mark.asyncio
    async def test_t7_channel_thread_tool_progress_updates_thinking_msg(self):
        """T-7: Channel thread tool progress updates thinking message in-place."""
        sc, _ = _make_channel()
        eid = "evt-channel-progress"
        doc = _mock_event_doc(event_id=eid, slack_channel_id="C_TEAM", slack_thread_ts="1700.1")
        sc._blackboard.get_event.return_value = doc
        sc._thinking_msg[eid] = ("C_TEAM", "1700.2")

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {
                "turn": 5,
                "actor": "brain",
                "action": "tool_result",
                "waitingFor": "classify_event",
                "evidence": "Analysis started",
            },
        })

        sc._app.client.chat_update.assert_called_once()
        call_kwargs = sc._app.client.chat_update.call_args.kwargs
        assert call_kwargs.get("channel") == "C_TEAM"
        assert call_kwargs.get("ts") == "1700.2"
        assert "Assessing the situation" in call_kwargs.get("text", "")

    @pytest.mark.asyncio
    async def test_t8_event_closed_deletes_thinking_message(self):
        """T-8: Event closed broadcast deletes any remaining thinking message."""
        sc, _ = _make_channel()
        eid = "evt-closed-cleanup"
        sc._thinking_msg[eid] = ("C_TEAM", "1700.99")

        await sc.broadcast_handler({
            "type": "event_closed",
            "event_id": eid,
        })

        sc._app.client.chat_delete.assert_called_once_with(
            channel="C_TEAM",
            ts="1700.99",
        )
        assert eid not in sc._thinking_msg

    @pytest.mark.asyncio
    async def test_t9_brain_route_turn_fires_open_infra_thread(self):
        """T-9: brain.route turn triggers open_infra_thread and is not suppressed."""
        from unittest.mock import patch
        sc, _ = _make_channel()
        eid = "evt-aligner-infra"
        doc = _mock_event_doc(event_id=eid, source="aligner")
        doc.slack_channel_id = None
        doc.slack_thread_ts = None
        sc._blackboard.get_event.return_value = doc

        with patch.object(sc, "open_infra_thread", AsyncMock()) as mock_open:
            await sc.broadcast_handler({
                "type": "turn",
                "event_id": eid,
                "turn": {
                    "turn": 2,
                    "actor": "brain",
                    "action": "route",
                    "thoughts": "Dispatching to aligner agent",
                },
            })
            mock_open.assert_called_once()

    @pytest.mark.asyncio
    async def test_t10_ephemeral_failure_does_not_crash_action_handler(self):
        """T-10: Ephemeral post timeout/failure does not crash handle_approve."""
        from unittest.mock import patch
        sc, captured = _make_channel()
        handle_approve = captured["action:darwin_approve"]
        eid = "evt-timeout-001"
        doc = _mock_event_doc(event_id=eid)
        doc.created_by_email = "owner@redhat.com"
        sc._blackboard.get_event.return_value = doc

        client = AsyncMock()
        client.users_info.return_value = {
            "ok": True,
            "user": {
                "profile": {
                    "display_name": "Eve Attacker",
                    "real_name": "Eve Attacker",
                    "email": "eve@unauthorized.com",
                }
            }
        }
        client.chat_postEphemeral.side_effect = Exception("Slack API Timeout")

        body = {
            "user": {"id": "U_EVE"},
            "channel": {"id": "C_CHAN"},
            "message": {"ts": "1700000000.123", "thread_ts": "1700000000.100"},
            "actions": [{"value": eid}],
        }
        ack = AsyncMock()

        with patch("src.auth.DEX_ENABLED", True):
            await handle_approve(ack, body, client)

        ack.assert_awaited_once()
        sc._blackboard.append_turn.assert_not_called()




# ---------------------------------------------------------------------------
# Test: realistic AsyncSlackResponse handling, RBAC via access gate, created_by_email
# ---------------------------------------------------------------------------


class _FakeAsyncSlackResponse:
    """Mimics slack_sdk AsyncSlackResponse: NOT a dict subclass, but supports .get()/[]."""

    def __init__(self, data: dict) -> None:
        self.data = data

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.data[key]


def _fake_user_info(name: str = "Alice", email: str | None = "alice@redhat.com") -> _FakeAsyncSlackResponse:
    profile: dict[str, Any] = {"display_name": name}
    if email is not None:
        profile["email"] = email
    return _FakeAsyncSlackResponse({"ok": True, "user": {"profile": profile, "real_name": name}})


class TestResolveDisplayNameAsyncSlackResponse:
    """Regression: users_info returns a non-dict AsyncSlackResponse in production."""

    @pytest.mark.asyncio
    async def test_resolves_and_caches_name_and_email_from_non_dict_response(self):
        sc, _ = _make_channel()
        resp = _fake_user_info("Alice Real", "alice@redhat.com")
        assert not isinstance(resp, dict)
        client = AsyncMock()
        client.users_info.return_value = resp

        name = await sc._resolve_display_name(client, "U_ALICE")

        assert name == "Alice Real"
        assert sc._get_cached_email("U_ALICE") == "alice@redhat.com"
        # Second call is served from cache -- no extra API round trip.
        assert await sc._resolve_display_name(client, "U_ALICE") == "Alice Real"
        client.users_info.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_gate_check_allows_maintainer_via_non_dict_response(self):
        """End-to-end of the prod bug: gate must see the email, not 'no_email'."""
        from src.slack_gate import SlackAccessGate

        sc, _ = _make_channel()
        sc._access_gate = SlackAccessGate([], {"alice@redhat.com"})
        client = AsyncMock()
        client.users_info.return_value = _fake_user_info("Alice", "alice@redhat.com")

        assert await sc._gate_check(client, "U_ALICE") is True

    @pytest.mark.asyncio
    async def test_lookup_exception_does_not_cache_empty_email(self):
        sc, _ = _make_channel()
        client = AsyncMock()
        client.users_info.side_effect = Exception("ratelimited")

        assert await sc._resolve_display_name(client, "U_X") == "U_X"
        assert sc._get_cached_email("U_X") is None
        assert "U_X" not in sc._user_name_cache

        # Recovery: next call retries and caches the real email.
        client.users_info.side_effect = None
        client.users_info.return_value = _fake_user_info("Xavier", "x@redhat.com")
        assert await sc._resolve_display_name(client, "U_X") == "Xavier"
        assert sc._get_cached_email("U_X") == "x@redhat.com"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("payload", [
        {"ok": False, "error": "user_not_found"},
        {"ok": True, "user": None},
        {"ok": True, "user": {}},
    ])
    async def test_missing_user_object_does_not_cache_empty_email(self, payload):
        sc, _ = _make_channel()
        client = AsyncMock()
        client.users_info.return_value = _FakeAsyncSlackResponse(payload)

        assert await sc._resolve_display_name(client, "U_Y") == "U_Y"
        assert sc._get_cached_email("U_Y") is None
        assert "U_Y" not in sc._user_name_cache

    @pytest.mark.asyncio
    async def test_profile_without_email_caches_empty_string(self):
        """A resolved profile that genuinely has no email IS cached as '' (checked, none)."""
        sc, _ = _make_channel()
        client = AsyncMock()
        client.users_info.return_value = _fake_user_info("Botty", None)

        assert await sc._resolve_display_name(client, "U_B") == "Botty"
        assert sc._get_cached_email("U_B") == ""


class TestApproveRejectRBAC:
    """RBAC for darwin_approve / darwin_reject (shared _authorize_plan_decision helper)."""

    MAINT = "maint@redhat.com"
    MEMBER = "member@redhat.com"
    OWNER = "owner@redhat.com"

    @staticmethod
    def _gate(maintainers: set[str], members: set[str]):
        from src.slack_gate import SlackAccessGate

        gate = SlackAccessGate(["g"], maintainers)
        gate._allowed_emails = frozenset(members)
        gate._healthy = True
        return gate

    @staticmethod
    def _body(eid: str, user: str = "U_USER") -> dict:
        return {
            "user": {"id": user},
            "channel": {"id": "C_CHAN"},
            "message": {"ts": "1700000000.123", "thread_ts": "1700000000.100"},
            "actions": [{"value": eid}],
        }

    async def _run(
        self,
        verb: str,
        *,
        email: str,
        created_by: str | None,
        status: str = "active",
        gate=None,
        auth: bool = True,
        approver_groups: frozenset = frozenset({"darwin-approvers"}),
        obs_groups: frozenset = frozenset(),
    ):
        from unittest.mock import patch

        sc, captured = _make_channel()
        sc._access_gate = gate
        eid = f"evt-rbac-{verb}"
        doc = _mock_event_doc(event_id=eid, status=status)
        doc.created_by_email = created_by
        sc._blackboard.get_event.return_value = doc
        client = AsyncMock()
        client.users_info.return_value = _fake_user_info("Some User", email)
        handler = captured[f"action:darwin_{verb}"]

        with patch("src.auth.DEX_ENABLED", auth), \
                patch("src.auth.TRUSTED_PROXY_ENABLED", False), \
                patch("src.auth.APPROVER_GROUPS", approver_groups), \
                patch("src.auth.OBS_ADMIN_GROUPS", obs_groups), \
                patch("src.utils.vcs_approval.resolve_live_head_sha", AsyncMock(return_value=(None, None))):
            await handler(AsyncMock(), self._body(eid), client)
        return sc, client, eid

    @staticmethod
    def _assert_allowed(sc, eid):
        sc._blackboard.append_turn.assert_called_once()
        sc._brain.enqueue_for_processing.assert_called_once_with(eid)

    @staticmethod
    def _assert_denied(sc, client, verb):
        sc._blackboard.append_turn.assert_not_called()
        sc._brain.enqueue_for_processing.assert_not_called()
        client.chat_postEphemeral.assert_called_once()
        assert f"not authorized to {verb}" in client.chat_postEphemeral.call_args.kwargs["text"]

    # -- gate / closed-event ------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_gate_denied_user_gets_access_denied(self, verb):
        gate = self._gate({self.MAINT}, set())
        sc, client, _ = await self._run(
            verb, email="stranger@redhat.com", created_by="stranger@redhat.com", gate=gate,
        )
        sc._blackboard.append_turn.assert_not_called()
        sc._brain.enqueue_for_processing.assert_not_called()
        sc._blackboard.get_event.assert_not_awaited()
        client.chat_postEphemeral.assert_called_once()
        assert "Access denied" in client.chat_postEphemeral.call_args.kwargs["text"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_closed_event_returns_early_silently(self, verb):
        sc, client, _ = await self._run(
            verb, email=self.OWNER, created_by=self.OWNER, status="closed",
        )
        sc._blackboard.append_turn.assert_not_called()
        sc._brain.enqueue_for_processing.assert_not_called()
        client.chat_postEphemeral.assert_not_called()

    # -- can_approve_event (no access gate) ---------------------------------

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_non_owner_denied_when_auth_enabled(self, verb):
        sc, client, _ = await self._run(verb, email="eve@redhat.com", created_by=self.OWNER)
        self._assert_denied(sc, client, verb)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_creator_allowed_when_auth_enabled(self, verb):
        sc, client, eid = await self._run(verb, email=self.OWNER, created_by=self.OWNER)
        self._assert_allowed(sc, eid)
        client.chat_postEphemeral.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_creator_match_is_case_insensitive(self, verb):
        sc, _, eid = await self._run(verb, email="Owner@RedHat.com", created_by=self.OWNER)
        self._assert_allowed(sc, eid)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_auth_disabled_is_open(self, verb):
        sc, _, eid = await self._run(verb, email="eve@redhat.com", created_by=self.OWNER, auth=False)
        self._assert_allowed(sc, eid)

    # -- access-gate maintainer -> roles path --------------------------------

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_maintainer_allowed_on_unowned_event(self, verb):
        gate = self._gate({self.MAINT}, {self.MEMBER})
        sc, client, eid = await self._run(verb, email=self.MAINT, created_by=None, gate=gate)
        self._assert_allowed(sc, eid)
        client.chat_postEphemeral.assert_not_called()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_maintainer_allowed_via_obs_admin_groups_fallback(self, verb):
        gate = self._gate({self.MAINT}, set())
        sc, _, eid = await self._run(
            verb, email=self.MAINT, created_by=None, gate=gate,
            approver_groups=frozenset(), obs_groups=frozenset({"obs-admins"}),
        )
        self._assert_allowed(sc, eid)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_non_maintainer_denied_on_unowned_event(self, verb):
        gate = self._gate({self.MAINT}, {self.MEMBER})
        sc, client, _ = await self._run(verb, email=self.MEMBER, created_by=None, gate=gate)
        self._assert_denied(sc, client, verb)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_event_creator_allowed_through_gate(self, verb):
        gate = self._gate({self.MAINT}, {self.MEMBER})
        sc, _, eid = await self._run(verb, email=self.MEMBER, created_by=self.MEMBER, gate=gate)
        self._assert_allowed(sc, eid)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_fail_closed_when_no_approver_groups_configured(self, verb):
        """Both APPROVER_GROUPS and OBS_ADMIN_GROUPS unset: no synthesized role, maintainer denied."""
        gate = self._gate({self.MAINT}, set())
        sc, client, _ = await self._run(
            verb, email=self.MAINT, created_by=None, gate=gate,
            approver_groups=frozenset(), obs_groups=frozenset(),
        )
        self._assert_denied(sc, client, verb)

    @pytest.mark.asyncio
    async def test_maintainer_roles_empty_without_configured_groups(self):
        from unittest.mock import patch

        sc, _ = _make_channel()
        sc._access_gate = self._gate({self.MAINT}, set())
        with patch("src.auth.APPROVER_GROUPS", frozenset()), patch("src.auth.OBS_ADMIN_GROUPS", frozenset()):
            assert sc._maintainer_roles(self.MAINT) == []
        with patch("src.auth.APPROVER_GROUPS", frozenset({"darwin-approvers"})):
            assert sc._maintainer_roles(self.MAINT) == ["darwin-approvers"]
            assert sc._maintainer_roles(self.MEMBER) == []
            assert sc._maintainer_roles("") == []

    # -- log hygiene ---------------------------------------------------------

    @pytest.mark.asyncio
    @pytest.mark.parametrize("verb", ["approve", "reject"])
    async def test_forbidden_log_masks_email(self, verb, caplog):
        import logging

        with caplog.at_level(logging.WARNING, logger="darwin.slack"):
            await self._run(verb, email="eve@redhat.com", created_by=self.OWNER)
        text = caplog.text
        assert "forbidden" in text
        assert "eve@redhat.com" not in text
        assert "e***@redhat.com" in text


class TestCreatedByEmailPropagation:
    """created_by_email reaches create_event on every Slack creation path (non-dict users_info)."""

    @staticmethod
    def _client(email: str | None = "alice@redhat.com"):
        client = AsyncMock()
        client.users_info.return_value = _fake_user_info("Alice", email)
        client.chat_postMessage.return_value = {"ts": "1700000010.000001", "channel": "D_ALICE"}
        return client

    async def _fire(self, path: str, client) -> Any:
        sc, captured = _make_channel()
        sc._blackboard.get_event_by_slack_thread.return_value = None
        sc._blackboard.create_event.return_value = "evt-new-x"

        if path == "app_mention":
            await captured["event:app_mention"](
                {"channel": "C_INFRA", "user": "U_A", "text": "<@BOT> go", "ts": "1700000009.000001"},
                client,
            )
        elif path == "app_mention_followup":
            sc._blackboard.get_event_by_slack_thread.return_value = "evt-closed01"
            sc._blackboard.get_event.return_value = _mock_event_doc(event_id="evt-closed01", status="closed")
            await captured["event:app_mention"](
                {
                    "channel": "C_INFRA", "user": "U_A", "text": "<@BOT> more",
                    "ts": "1700000002.000001", "thread_ts": "1700000001.000001",
                },
                client,
            )
        elif path == "slash_command":
            await captured["command:/darwin"](
                AsyncMock(), {"text": "do it", "user_id": "U_A", "channel_id": "C_INFRA"},
                client, AsyncMock(),
            )
        elif path == "dm":
            await captured["event:message"](_dm_event(user="U_A", thread_ts=None), client)
        elif path == "home_modal":
            view = {"state": {"values": {"event_description": {"description_input": {"value": "x"}}}}}
            await captured["view:darwin_create_event_modal"](
                AsyncMock(), {"user": {"id": "U_A"}}, client, view,
            )
        else:  # pragma: no cover
            raise AssertionError(path)
        return sc

    PATHS = ["app_mention", "app_mention_followup", "slash_command", "dm", "home_modal"]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", PATHS)
    async def test_email_propagates(self, path):
        sc = await self._fire(path, self._client("alice@redhat.com"))
        sc._blackboard.create_event.assert_called_once()
        assert sc._blackboard.create_event.call_args.kwargs["created_by_email"] == "alice@redhat.com"

    @pytest.mark.asyncio
    @pytest.mark.parametrize("path", PATHS)
    async def test_missing_email_yields_none_not_empty_string(self, path):
        sc = await self._fire(path, self._client(None))
        sc._blackboard.create_event.assert_called_once()
        assert sc._blackboard.create_event.call_args.kwargs["created_by_email"] is None


class TestThinkingIndicatorLifecycle:
    @pytest.mark.asyncio
    async def test_transient_chat_update_error_keeps_thinking_msg(self):
        sc, _ = _make_channel()
        eid = "evt-think-1"
        sc._thinking_msg[eid] = ("C_TEAM", "1700.5")
        sc._app.client.chat_update.side_effect = Exception("timeout")
        turn = MagicMock()
        turn.waitingFor = "some_tool"
        doc = _mock_event_doc(event_id=eid)

        await sc._handle_tool_progress(turn, doc)

        assert sc._thinking_msg[eid] == ("C_TEAM", "1700.5")

    @pytest.mark.asyncio
    async def test_message_not_found_drops_thinking_msg(self):
        from slack_sdk.errors import SlackApiError

        sc, _ = _make_channel()
        eid = "evt-think-2"
        sc._thinking_msg[eid] = ("C_TEAM", "1700.5")
        sc._app.client.chat_update.side_effect = SlackApiError(
            "gone", {"ok": False, "error": "message_not_found"},
        )
        turn = MagicMock()
        turn.waitingFor = "some_tool"

        await sc._handle_tool_progress(turn, _mock_event_doc(event_id=eid))

        assert eid not in sc._thinking_msg

    @pytest.mark.asyncio
    async def test_clear_thinking_status_resets_last_tool_phrase(self):
        sc, _ = _make_channel()
        eid = "evt-think-3"
        sc._dm_context[eid] = {**_dm_ctx(), "_last_tool_phrase": "FRIDAY is working..."}

        await sc._clear_thinking_status(eid)

        assert "_last_tool_phrase" not in sc._dm_context[eid]
        sc._app.client.assistant_threads_setStatus.assert_awaited_once()
