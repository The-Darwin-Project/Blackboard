# tests/test_slack_channel.py
# @ai-rules:
# 1. [Constraint]: Tests invoke actual SlackChannel methods — _should_stream(), broadcast_handler(),
#    _start_stream(), _cleanup_stream(), _ensure_dm_context(), _refresh_thinking_status(), and
#    captured on_dm_message callback. No re-implementation of production logic.
# 2. [Pattern]: Mock AsyncApp with decorator-capturing factory. _register_handlers() populates
#    captured dict. Callbacks invoked directly with mock event payloads.
# 3. [Pattern]: Assert on STATE CHANGES: _dm_context, _stream_delivered, _active_streams,
#    _stream_eligible, _coalesce_buffer, _thinking_msg — not on mock call args.
# 4. [Pattern]: Use pytest-asyncio mode="auto". AsyncMock for all awaitable dependencies.
# 5. [Gotcha]: _access_gate = None bypasses gate checks. Pre-populate _dm_context to avoid
#    _ensure_dm_context blackboard queries in tests that don't test hydration.
"""Unit tests for SlackChannel — agent_view DM handling, streaming, and dedup."""
from __future__ import annotations

import time
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_channel(*, streaming_enabled: bool = False) -> tuple:
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
    sc._active_streams = {}
    sc._stream_eligible = {}
    sc._stream_delivered = {}
    sc._coalesce_buffer = {}
    sc._coalesce_last_flush = {}
    sc._stream_ts = {}
    sc._streaming_enabled = streaming_enabled

    sc._register_handlers()

    return sc, captured


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
    slack_thread_ts: str = "1700000001.000001",
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
# Test: broadcast_handler dedup and turn routing
# ---------------------------------------------------------------------------


class TestBroadcastDedup:
    """Invoke broadcast_handler to verify dedup guard and turn routing."""

    @pytest.mark.asyncio
    async def test_dedup_guard_skips_response(self):
        """_stream_delivered set → brain.response Block Kit skipped, flag consumed."""
        sc, _ = _make_channel(streaming_enabled=True)
        eid = "evt-streamed"

        sc._dm_context[eid] = {
            "channel": "D_DM", "thread_ts": "1700000001.000001",
            "user_id": "U_USER", "team_id": "T_TEAM", "_last_status_at": 0,
        }
        sc._stream_delivered[eid] = True
        sc._blackboard.get_event.return_value = _mock_event_doc(event_id=eid)

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "response",
                     "thoughts": "Done."},
        })

        assert eid not in sc._stream_delivered
        sc._app.client.chat_postMessage.assert_not_called()

    @pytest.mark.asyncio
    async def test_dedup_guard_passes_wait(self):
        """brain.wait turns NOT skipped even when _stream_delivered set."""
        sc, _ = _make_channel(streaming_enabled=True)
        eid = "evt-wait"

        sc._dm_context[eid] = {
            "channel": "D_DM", "thread_ts": "1700000001.000001",
            "user_id": "U_USER", "team_id": "T_TEAM", "_last_status_at": 0,
        }
        sc._stream_delivered[eid] = True
        event_doc = _mock_event_doc(event_id=eid)
        sc._blackboard.get_event.return_value = event_doc

        await sc.broadcast_handler({
            "type": "turn",
            "event_id": eid,
            "turn": {"turn": 1, "actor": "brain", "action": "wait",
                     "thoughts": "Waiting for approval..."},
        })

        assert sc._stream_delivered[eid] is True


# ---------------------------------------------------------------------------
# Test: broadcast_handler stale-flag and cycle management
# ---------------------------------------------------------------------------


class TestBroadcastCycleManagement:
    """Verify stale-flag clear and circuit breaker reset on new cycle."""

    @pytest.mark.asyncio
    async def test_stale_dedup_cleared_on_empty_text(self):
        """Any brain_thinking with empty text clears stale dedup + circuit breaker (F9)."""
        sc, _ = _make_channel(streaming_enabled=True)
        eid = "evt-stale"

        sc._dm_context[eid] = {
            "channel": "D_DM", "thread_ts": "1700000001.000001",
            "user_id": "U_USER", "team_id": "T_TEAM", "_last_status_at": 0,
        }
        sc._stream_delivered[eid] = True
        sc._stream_eligible[eid] = False

        await sc.broadcast_handler({
            "type": "brain_thinking",
            "event_id": eid,
            "text": "",
            "is_thought": False,
        })

        assert eid not in sc._stream_delivered
        assert eid not in sc._stream_eligible

    @pytest.mark.asyncio
    async def test_event_closed_cleans_all_state(self):
        """event_closed → stream stopped, all state dicts cleaned including _thinking_msg."""
        sc, _ = _make_channel(streaming_enabled=True)
        eid = "evt-closing"

        mock_stream = AsyncMock()
        sc._active_streams[eid] = mock_stream
        sc._dm_context[eid] = {
            "channel": "D_DM", "thread_ts": "1700000001.000001",
            "user_id": "U_USER", "team_id": "T_TEAM", "_last_status_at": 0,
        }
        sc._stream_eligible[eid] = True
        sc._stream_delivered[eid] = True
        sc._stream_ts[eid] = "1700000001.000002"
        sc._thinking_msg[eid] = ("D_DM", "1700000001.000003")
        sc._coalesce_buffer[eid] = "pending"
        sc._coalesce_last_flush[eid] = time.time()

        event_doc = _mock_event_doc(event_id=eid)
        sc._blackboard.get_event.return_value = event_doc

        await sc.broadcast_handler({
            "type": "event_closed",
            "event_id": eid,
            "summary": "resolved",
        })

        for store in (sc._active_streams, sc._dm_context, sc._stream_eligible,
                      sc._stream_delivered, sc._stream_ts, sc._thinking_msg,
                      sc._coalesce_buffer, sc._coalesce_last_flush):
            assert eid not in store


# ---------------------------------------------------------------------------
# Test: _should_stream caching behavior
# ---------------------------------------------------------------------------


class TestShouldStream:
    """Invoke sc._should_stream() directly to verify caching and eligibility."""

    def test_caches_eligible_result(self):
        sc, _ = _make_channel(streaming_enabled=True)
        eid = "evt-cache"
        sc._dm_context[eid] = {
            "channel": "D_DM", "thread_ts": "1700000001.000001",
            "user_id": "U_USER", "team_id": "T_TEAM", "_last_status_at": 0,
        }

        assert sc._should_stream(eid) is True
        assert sc._stream_eligible[eid] is True

        del sc._dm_context[eid]
        assert sc._should_stream(eid) is True

    def test_false_when_disabled(self):
        sc, _ = _make_channel(streaming_enabled=False)
        sc._dm_context["evt-x"] = {
            "thread_ts": "1.2", "channel": "D", "user_id": "U",
            "team_id": "T", "_last_status_at": 0,
        }
        assert sc._should_stream("evt-x") is False

    def test_false_when_no_context(self):
        sc, _ = _make_channel(streaming_enabled=True)
        assert sc._should_stream("evt-noctx") is False
        assert sc._stream_eligible["evt-noctx"] is False

    def test_false_when_empty_thread_ts(self):
        sc, _ = _make_channel(streaming_enabled=True)
        sc._dm_context["evt-no-ts"] = {
            "channel": "D_DM", "thread_ts": "",
            "user_id": "U_USER", "team_id": "T_TEAM", "_last_status_at": 0,
        }
        assert sc._should_stream("evt-no-ts") is False


# ---------------------------------------------------------------------------
# Test: _start_stream and _cleanup_stream
# ---------------------------------------------------------------------------


class TestStreamLifecycle:
    """Invoke _start_stream and _cleanup_stream directly."""

    @pytest.mark.asyncio
    async def test_start_stream_failure_sets_breaker_and_clears_buffer(self):
        """chat_stream failure → None, circuit breaker set, buffer cleared (F5, F13)."""
        sc, _ = _make_channel(streaming_enabled=True)
        eid = "evt-failstr"

        sc._dm_context[eid] = {
            "channel": "D_DM", "thread_ts": "1700000001.000001",
            "user_id": "U_USER", "team_id": "T_TEAM", "_last_status_at": 0,
        }
        sc._coalesce_buffer[eid] = "buffered"
        sc._app.client.chat_stream = AsyncMock(side_effect=Exception("scope_missing"))

        result = await sc._start_stream(eid)

        assert result is None
        assert sc._stream_eligible[eid] is False
        assert eid not in sc._coalesce_buffer

    @pytest.mark.asyncio
    async def test_start_stream_success_stores_ts(self):
        """Successful chat_stream → stream_ts stored (F7)."""
        sc, _ = _make_channel(streaming_enabled=True)
        eid = "evt-ok"

        sc._dm_context[eid] = {
            "channel": "D_DM", "thread_ts": "1700000001.000001",
            "user_id": "U_USER", "team_id": "T_TEAM", "_last_status_at": 0,
        }
        mock_stream = AsyncMock()
        mock_stream.ts = "1700000001.000099"
        sc._app.client.chat_stream = AsyncMock(return_value=mock_stream)

        result = await sc._start_stream(eid)

        assert result is mock_stream
        assert sc._stream_ts[eid] == "1700000001.000099"

    @pytest.mark.asyncio
    async def test_cleanup_stream_stops_and_cleans(self):
        """Normal cleanup → stream stopped, buffer/flush/ts cleared."""
        sc, _ = _make_channel(streaming_enabled=True)
        eid = "evt-clean"

        mock_stream = AsyncMock()
        sc._active_streams[eid] = mock_stream
        sc._stream_ts[eid] = "1700000001.000099"
        sc._coalesce_buffer[eid] = "buf"
        sc._coalesce_last_flush[eid] = time.time()

        await sc._cleanup_stream(eid)

        assert eid not in sc._active_streams
        assert eid not in sc._stream_ts
        assert eid not in sc._coalesce_buffer
        assert eid not in sc._coalesce_last_flush
        mock_stream.stop.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_cleanup_broken_pill_deletes_message(self):
        """stream.stop fails → broken message deleted via chat_delete (F7)."""
        sc, _ = _make_channel(streaming_enabled=True)
        eid = "evt-broken"

        mock_stream = AsyncMock()
        mock_stream.stop = AsyncMock(side_effect=Exception("broken"))
        sc._active_streams[eid] = mock_stream
        sc._stream_ts[eid] = "1700000001.000099"
        sc._dm_context[eid] = {
            "channel": "D_DM", "thread_ts": "1700000001.000001",
            "user_id": "U_USER", "team_id": "T_TEAM", "_last_status_at": 0,
        }

        await sc._cleanup_stream(eid)

        sc._app.client.chat_delete.assert_awaited_once_with(
            channel="D_DM", ts="1700000001.000099",
        )
        assert eid not in sc._active_streams


# ---------------------------------------------------------------------------
# Test: _ensure_dm_context lazy hydration (F2)
# ---------------------------------------------------------------------------


class TestEnsureDmContext:
    """Invoke _ensure_dm_context to verify lazy hydration from blackboard."""

    @pytest.mark.asyncio
    async def test_returns_true_if_already_populated(self):
        sc, _ = _make_channel()
        sc._dm_context["evt-x"] = {
            "channel": "D_DM", "thread_ts": "1.1",
            "user_id": "U", "team_id": "T", "_last_status_at": 0,
        }

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

        redirect_call = None
        for call in client.chat_postMessage.call_args_list:
            kwargs = call[1] if call[1] else {}
            if "Continue in #darwin-infra" in kwargs.get("text", ""):
                redirect_call = kwargs
        assert redirect_call is not None
        assert redirect_call["channel"] == "D_DM"
        assert "C_INFRA" in redirect_call["text"]
