# BlackBoard/tests/test_live_api_adapter.py
"""Tests for LiveAPIAdapter duplicate review handling."""
import pytest
import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch, ANY
from src.adapters.live_api_adapter import LiveAPIAdapter

@pytest.mark.asyncio
async def test_duplicate_system_review_returns_existing():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._shadow = False
    adapter._brain = None
    adapter._blackboard = MagicMock()
    adapter._blackboard.get_active_events = AsyncMock(return_value=["evt-1"])
    adapter._blackboard.find_active_event_by_source = AsyncMock(return_value="evt-12345")
    adapter._blackboard.get_event = AsyncMock(return_value=MagicMock(status="active"))
    
    result = await adapter._tool_create_system_review(reason="test review pattern")
    assert "evt-12345" in result
    assert "Review already active" in result

# T-1: BLOCKING behavior injection
def test_build_live_tools_blocking():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._rag_enabled = False
    adapter._rag_corpus_id = ""
    
    try:
        from google.genai import types
        tools = adapter._build_live_tools(types)
        assert len(tools) >= 1
        funcs = tools[0].function_declarations
        assert len(funcs) == 11
        for f in funcs:
            assert f.behavior == types.Behavior.BLOCKING
    except ImportError:
        class MockTypes:
            Tool = MagicMock()
            FunctionDeclaration = MagicMock()
            Behavior = MagicMock(side_effect=lambda x: f"Behavior.{x}")
            Behavior.BLOCKING = "Behavior.BLOCKING"
                
        adapter._build_live_tools(MockTypes)
        assert MockTypes.FunctionDeclaration.call_count == 11
        for call in MockTypes.FunctionDeclaration.call_args_list:
            assert call.kwargs.get("behavior") == MockTypes.Behavior.BLOCKING

# T-2: LiveConnectConfig construction (fresh)
@pytest.mark.asyncio
async def test_connect_fresh():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._project = "test"
    adapter._location = "us-central1"
    adapter._model = "test-model"
    
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = MagicMock()
    adapter._client = MagicMock()
    adapter._client.aio.live.connect.return_value = mock_ctx
    
    adapter._connect_lock = asyncio.Lock()
    adapter._resumption_handle = None
    adapter._idle_watchdog_task = None
    adapter._receive_task = None
    adapter._blackboard = MagicMock()
    adapter._blackboard.find_active_event_by_source = AsyncMock(return_value=None)
    adapter._broadcast_status = AsyncMock()
    adapter._load_neuron_labels = AsyncMock()
    adapter._shadow = False
    adapter._neuron_labels = {}
    adapter._build_live_tools = MagicMock(return_value=[])
    
    adapter._receive_loop = AsyncMock()
    adapter._idle_watchdog = AsyncMock()

    await adapter._connect()

    adapter._client.aio.live.connect.assert_called_once()
    config = adapter._client.aio.live.connect.call_args.kwargs["config"]
    assert "TEXT" in [m.name for m in config.response_modalities]
    assert config.session_resumption is None
    assert config.thinking_config.include_thoughts is True
    
    # Wait for the mocked tasks to complete
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_connect_fresh_gemini_3_8_live():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._project = "test"
    adapter._location = "eu"
    adapter._model = "gemini-3.8-live"
    
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = MagicMock()
    adapter._client = MagicMock()
    adapter._client.aio.live.connect.return_value = mock_ctx
    
    adapter._connect_lock = asyncio.Lock()
    adapter._resumption_handle = None
    adapter._idle_watchdog_task = None
    adapter._receive_task = None
    adapter._blackboard = MagicMock()
    adapter._blackboard.find_active_event_by_source = AsyncMock(return_value=None)
    adapter._broadcast_status = AsyncMock()
    adapter._load_neuron_labels = AsyncMock()
    adapter._shadow = False
    adapter._neuron_labels = {}
    adapter._build_live_tools = MagicMock(return_value=[])
    
    adapter._receive_loop = AsyncMock()
    adapter._idle_watchdog = AsyncMock()

    await adapter._connect()

    adapter._client.aio.live.connect.assert_called_once()
    config = adapter._client.aio.live.connect.call_args.kwargs["config"]
    assert config.output_audio_transcription is not None
    assert config.response_modalities is None
    assert config.session_resumption is None
    assert config.thinking_config.include_thoughts is True
    assert config.context_window_compression is not None
    
    await asyncio.sleep(0.01)

# T-3: LiveConnectConfig resumption
@pytest.mark.asyncio
async def test_connect_resumption():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._project = "test"
    adapter._location = "us-central1"
    adapter._model = "test-model"
    
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = MagicMock()
    adapter._client = MagicMock()
    adapter._client.aio.live.connect.return_value = mock_ctx
    
    adapter._connect_lock = asyncio.Lock()
    adapter._resumption_handle = "h123"
    adapter._idle_watchdog_task = None
    adapter._receive_task = None
    adapter._blackboard = MagicMock()
    adapter._blackboard.find_active_event_by_source = AsyncMock(return_value=None)
    adapter._broadcast_status = AsyncMock()
    adapter._load_neuron_labels = AsyncMock()
    adapter._shadow = False
    adapter._neuron_labels = {}
    adapter._build_live_tools = MagicMock(return_value=[])

    adapter._receive_loop = AsyncMock()
    adapter._idle_watchdog = AsyncMock()

    await adapter._connect()

    adapter._client.aio.live.connect.assert_called_once()
    config = adapter._client.aio.live.connect.call_args.kwargs["config"]
    assert config.session_resumption.handle == "h123"

    await asyncio.sleep(0.01)

# T-4: Thought vs text demuxing
@pytest.mark.asyncio
async def test_process_message_demuxes_interleaved_parts():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._text_buffer = []
    adapter._broadcast = AsyncMock()
    adapter._last_pulse_event_id = "evt-1"
    adapter._active_meta_event_id = None
    adapter._collecting_handoff = False
    adapter._awaiting_jarvis_reply = False

    msg = MagicMock()
    msg.server_content.model_turn.parts = [
        MagicMock(thought=True, text="thinking"),
        MagicMock(thought=False, text="hello")
    ]
    msg.server_content.turn_complete = False
    msg.text = None
    msg.tool_call = None
    msg.go_away = None
    msg.session_resumption_update = None

    part1 = MagicMock()
    part1.thought = True
    part1.text = "thinking"
    
    part2 = MagicMock()
    part2.thought = False
    part2.text = "hello"
    
    msg.server_content.model_turn.parts = [part1, part2]

    await adapter._process_message(msg)

    adapter._broadcast.assert_any_call({
        "type": "cortex_thinking",
        "thought": "thinking",
        "event_id": "evt-1"
    })
    
    assert adapter._text_buffer == ["hello"]


@pytest.mark.asyncio
async def test_process_message_thought_only_does_not_leak_to_text_buffer():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._collecting_handoff = False
    adapter._handoff_buffer = []
    adapter._text_buffer = []
    adapter._broadcast = AsyncMock()
    adapter._active_meta_event_id = "evt-1"
    adapter._awaiting_jarvis_reply = False

    msg = MagicMock()
    part = MagicMock()
    part.thought = True
    part.text = "internal thought reasoning"
    msg.server_content.model_turn.parts = [part]
    msg.server_content.turn_complete = False
    msg.text = "internal thought reasoning"
    msg.tool_call = None
    msg.go_away = None
    msg.session_resumption_update = None

    await adapter._process_message(msg)

    adapter._broadcast.assert_called_once_with({
        "type": "cortex_thinking",
        "thought": "internal thought reasoning",
        "event_id": "evt-1"
    })
    assert adapter._text_buffer == []


# T-5: Tool execution exception safety
@pytest.mark.asyncio
async def test_handle_tool_call_exception_safety():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._tool_list_active_events = AsyncMock(side_effect=ValueError("broken"))
    
    result = await adapter._handle_tool_call("list_active_events", {})
    assert result == "Error: broken"

def _make_connect_adapter(handle=None, failures=0):
    """Adapter wired so _connect() runs against a mocked Live API client."""
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._project = "test"
    adapter._location = "us-central1"
    adapter._model = "test-model"
    adapter._resumption_handle = handle
    adapter._handle_connect_failures = failures
    adapter._last_pulse_event_id = "evt-1"
    adapter._replay_pending_context = AsyncMock()
    adapter._running = True
    adapter._session = None
    adapter._session_ctx = None
    adapter._idle_watchdog_task = None
    adapter._receive_task = None
    adapter._client = MagicMock()
    adapter._blackboard = MagicMock()
    adapter._blackboard.find_active_event_by_source = AsyncMock(return_value=None)
    adapter._broadcast_status = AsyncMock()
    adapter._load_neuron_labels = AsyncMock()
    adapter._shadow = False
    adapter._neuron_labels = {}
    adapter._build_live_tools = MagicMock(return_value=[])
    adapter._receive_loop = AsyncMock()
    adapter._idle_watchdog = AsyncMock()
    return adapter


def _mock_ctx():
    ctx = AsyncMock()
    ctx.__aenter__.return_value = MagicMock()
    return ctx


# T-9: Resumption handle is only dropped after consecutive failures
@pytest.mark.asyncio
async def test_reconnect_resumption_rejection_fallback():
    """Second consecutive failure with a handle presumes it stale and retries fresh in the same call."""
    adapter = _make_connect_adapter(handle="stale-handle", failures=1)
    mock_ctx = _mock_ctx()

    connect_calls = []
    def mock_connect(*args, **kwargs):
        connect_calls.append(adapter._resumption_handle)
        if len(connect_calls) == 1:
            raise Exception("Invalid session resumption handle")
        return mock_ctx

    adapter._client.aio.live.connect.side_effect = mock_connect

    await adapter._connect()

    assert connect_calls == ["stale-handle", None]
    assert adapter._resumption_handle is None
    assert adapter._handle_connect_failures == 0
    assert adapter._session is not None
    # Replay is owned by _try_reconnect, never by _connect
    adapter._replay_pending_context.assert_not_called()
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_connect_keeps_handle_on_single_transient_failure():
    adapter = _make_connect_adapter(handle="good-handle", failures=0)
    adapter._client.aio.live.connect.side_effect = Exception("503 backend unavailable")

    await adapter._connect()

    # No zero-backoff retry, handle retained, failure counted, session left unset
    adapter._client.aio.live.connect.assert_called_once()
    assert adapter._resumption_handle == "good-handle"
    assert adapter._handle_connect_failures == 1
    assert adapter._session is None
    adapter._replay_pending_context.assert_not_called()


@pytest.mark.asyncio
async def test_connect_drops_handle_only_on_second_consecutive_failure():
    adapter = _make_connect_adapter(handle="h", failures=0)
    handles = []
    def failing_connect(*args, **kwargs):
        handles.append(adapter._resumption_handle)
        raise Exception("down")
    adapter._client.aio.live.connect.side_effect = failing_connect

    await adapter._connect()  # failure 1: handle kept, no retry
    assert handles == ["h"]
    assert adapter._resumption_handle == "h"

    await adapter._connect()  # failure 2: handle dropped, one fresh retry (which also fails)
    assert handles == ["h", "h", None]
    assert adapter._resumption_handle is None
    assert adapter._handle_connect_failures == 0
    assert adapter._session is None


@pytest.mark.asyncio
async def test_connect_success_resets_failure_counter():
    adapter = _make_connect_adapter(handle="h", failures=1)
    adapter._client.aio.live.connect.return_value = _mock_ctx()

    await adapter._connect()

    assert adapter._resumption_handle == "h"
    assert adapter._handle_connect_failures == 0
    assert adapter._session is not None
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_connect_without_handle_does_not_retry_on_failure():
    adapter = _make_connect_adapter(handle=None)
    adapter._client.aio.live.connect.side_effect = Exception("down")

    await adapter._connect()

    adapter._client.aio.live.connect.assert_called_once()
    assert adapter._session is None
    assert adapter._handle_connect_failures == 0


# Session leak: a failure after the session opened must close it before any retry
@pytest.mark.asyncio
async def test_connect_closes_session_opened_before_retry():
    adapter = _make_connect_adapter(handle="stale-handle", failures=1)
    ctx1, ctx2 = _mock_ctx(), _mock_ctx()
    events = []

    async def exit1(*args):
        events.append("exit1")
    ctx1.__aexit__.side_effect = exit1

    async def enter2(*args):
        events.append("enter2")
        return MagicMock()
    ctx2.__aenter__.side_effect = enter2

    adapter._client.aio.live.connect.side_effect = [ctx1, ctx2]
    adapter._start_tasks = MagicMock(side_effect=[Exception("tasks failed"), None])

    await adapter._connect()

    assert adapter._client.aio.live.connect.call_count == 2
    ctx1.__aexit__.assert_awaited_once()
    ctx2.__aexit__.assert_not_awaited()
    # First session torn down before the retry opened the second
    assert events == ["exit1", "enter2"]
    assert adapter._session_ctx is ctx2
    assert adapter._resumption_handle is None
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_connect_closes_partial_session_without_retry():
    adapter = _make_connect_adapter(handle=None)
    ctx = _mock_ctx()
    adapter._client.aio.live.connect.return_value = ctx
    
    def failing_start_tasks():
        adapter._receive_task = MagicMock(done=MagicMock(return_value=True))
        adapter._idle_watchdog_task = MagicMock(done=MagicMock(return_value=True))
        raise Exception("tasks failed")

    adapter._start_tasks = MagicMock(side_effect=failing_start_tasks)

    await adapter._connect()
    await asyncio.sleep(0.01)

    ctx.__aexit__.assert_awaited_once()
    assert adapter._session is None
    assert adapter._session_ctx is None
    assert adapter._receive_task.done()
    assert adapter._idle_watchdog_task.done()


@pytest.mark.asyncio
async def test_abort_partial_connect_swallows_close_error():
    adapter = _make_connect_adapter()
    ctx = _mock_ctx()
    ctx.__aexit__.side_effect = RuntimeError("already closed")
    adapter._session_ctx = ctx
    adapter._session = MagicMock()

    await adapter._abort_partial_connect()

    assert adapter._session is None
    assert adapter._session_ctx is None


def _make_reconnect_adapter():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._running = True
    adapter._generating_report = False
    adapter._last_pulse_time = 1000.0
    adapter._session = None
    adapter._brain = MagicMock()
    adapter._brain.pending_jarvis_event_ids.return_value = ["evt-1"]
    adapter._connect = AsyncMock()
    adapter._replay_pending_context = AsyncMock()
    return adapter


@pytest.mark.asyncio
async def test_try_reconnect_calls_replay_pending_context_once():
    adapter = _make_reconnect_adapter()

    async def fake_connect():
        adapter._session = MagicMock()
    adapter._connect.side_effect = fake_connect

    with patch("time.time", return_value=1050.0), patch("asyncio.sleep", AsyncMock()):
        await adapter._try_reconnect()

    adapter._connect.assert_called_once()
    adapter._brain.clear_jarvis_wait.assert_called_once_with("evt-1")
    adapter._replay_pending_context.assert_called_once()


@pytest.mark.asyncio
async def test_try_reconnect_replays_once_after_retry_succeeds():
    adapter = _make_reconnect_adapter()
    attempts = []

    async def flaky_connect():
        attempts.append(1)
        if len(attempts) == 2:
            adapter._session = MagicMock()
    adapter._connect.side_effect = flaky_connect

    with patch("time.time", return_value=1050.0), patch("asyncio.sleep", AsyncMock()):
        await adapter._try_reconnect()

    assert len(attempts) == 2
    adapter._replay_pending_context.assert_called_once()


@pytest.mark.asyncio
async def test_try_reconnect_no_replay_when_connect_fails():
    adapter = _make_reconnect_adapter()  # _connect leaves _session unset

    with patch("time.time", return_value=1050.0), patch("asyncio.sleep", AsyncMock()):
        await adapter._try_reconnect()

    assert adapter._connect.call_count == 3
    adapter._replay_pending_context.assert_not_called()


@pytest.mark.asyncio
async def test_rotate_session_clears_resumption_handle():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._session = MagicMock()
    adapter._session.send = AsyncMock()
    
    async def mock_receive():
        mock_msg = MagicMock()
        mock_part = MagicMock()
        mock_part.thought = False
        mock_part.text = "Session summary text"
        mock_msg.server_content.model_turn.parts = [mock_part]
        mock_msg.server_content.turn_complete = True
        yield mock_msg
        
    adapter._session.receive = mock_receive
    adapter._resumption_handle = "active-handle"
    adapter._disconnect = AsyncMock()
    
    handles_during_connect = []
    async def mock_connect():
        handles_during_connect.append(adapter._resumption_handle)
    adapter._connect = AsyncMock(side_effect=mock_connect)

    await adapter._rotate_session()

    assert handles_during_connect == [None]
    assert adapter._resumption_handle is None

@pytest.mark.asyncio
async def test_handle_tool_call_timeout():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._tool_timeout = 0.05

    async def slow_tool():
        await asyncio.sleep(0.5)
        return "done"

    adapter._tool_list_active_events = slow_tool
    result = await adapter._handle_tool_call("list_active_events", {})
    assert "timed out after" in result

@pytest.mark.asyncio
async def test_connect_does_not_cancel_current_task():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._project = "test"
    adapter._location = "us-central1"
    adapter._model = "test-model"
    adapter._resumption_handle = None
    adapter._last_pulse_event_id = None
    adapter._shadow = False
    adapter._neuron_labels = {}
    adapter._build_live_tools = MagicMock(return_value=[])
    adapter._blackboard = MagicMock()
    adapter._blackboard.find_active_event_by_source = AsyncMock(return_value=None)
    adapter._broadcast_status = AsyncMock()
    adapter._load_neuron_labels = AsyncMock()
    adapter._receive_loop = AsyncMock()
    adapter._idle_watchdog = AsyncMock()
    
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = MagicMock()
    adapter._client = MagicMock()
    adapter._client.aio.live.connect.return_value = mock_ctx
    
    adapter._connect_lock = asyncio.Lock()
    current = asyncio.current_task()
    adapter._receive_task = current
    adapter._idle_watchdog_task = None
    
    await adapter._connect()
    
    assert not current.cancelled()


@pytest.mark.asyncio
async def test_connect_failure_cleans_up_transport_and_resets_running():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._project = "test"
    adapter._location = "us-central1"
    adapter._model = "test-model"
    adapter._connect_lock = asyncio.Lock()
    adapter._resumption_handle = None
    adapter._idle_watchdog_task = None
    adapter._receive_task = None
    adapter._build_live_tools = MagicMock(return_value=[])

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.side_effect = TimeoutError("Connection timed out")
    mock_ctx.__aexit__ = AsyncMock()
    adapter._client = MagicMock()
    adapter._client.aio.live.connect.return_value = mock_ctx

    await adapter._connect()

    assert adapter._session is None
    assert adapter._running is False
    assert adapter._session_ctx is None
    mock_ctx.__aexit__.assert_awaited_once_with(None, None, None)


@pytest.mark.asyncio
async def test_handle_tool_call_mutating_direct():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._tool_timeout = 60.0
    adapter._tool_send_event_message = AsyncMock(return_value="Message sent")

    result = await adapter._handle_tool_call("send_event_message", {"event_id": "evt-1", "message": "hello"})
    assert result == "Message sent"
    adapter._tool_send_event_message.assert_awaited_once_with("evt-1", "hello")


@pytest.mark.asyncio
async def test_connect_cancelled_cleans_up_and_reraises():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._project = "test"
    adapter._location = "us-central1"
    adapter._model = "test-model"
    adapter._connect_lock = asyncio.Lock()
    adapter._resumption_handle = None
    adapter._idle_watchdog_task = None
    adapter._receive_task = None
    adapter._build_live_tools = MagicMock(return_value=[])

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.side_effect = asyncio.CancelledError()
    mock_ctx.__aexit__ = AsyncMock()
    adapter._client = MagicMock()
    adapter._client.aio.live.connect.return_value = mock_ctx

    with pytest.raises(asyncio.CancelledError):
        await adapter._connect()

    assert adapter._session is None
    assert adapter._running is False
    assert adapter._session_ctx is None
    mock_ctx.__aexit__.assert_awaited_once_with(None, None, None)


@pytest.mark.asyncio
async def test_propose_enhancement_idempotent():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._blackboard = MagicMock()
    adapter._blackboard.redis = AsyncMock()

    existing_entry = json.dumps({
        "event_id": "evt-dup",
        "title": "Fix memory leak",
        "description": "Duplicate proposal",
        "severity": "blocking",
        "status": "pending",
    })
    adapter._blackboard.redis.lrange.return_value = [existing_entry]

    result = await adapter._tool_propose_enhancement(
        event_id="evt-dup",
        title="Fix memory leak",
        description="Duplicate proposal",
        severity="blocking",
    )

    assert "already pending review" in result
    adapter._blackboard.redis.rpush.assert_not_called()


@pytest.mark.asyncio
async def test_propose_enhancement_allows_updated_revision():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._blackboard = MagicMock()
    adapter._blackboard.redis = AsyncMock()
    adapter._broadcast = AsyncMock()

    existing_entry = json.dumps({
        "event_id": "evt-dup",
        "title": "Fix memory leak",
        "description": "Original description",
        "severity": "nice_to_have",
        "status": "pending",
    })
    adapter._blackboard.redis.lrange.return_value = [existing_entry]

    result = await adapter._tool_propose_enhancement(
        event_id="evt-dup",
        title="Fix memory leak",
        description="Escalated description with root cause",
        severity="blocking",
    )

    assert "stored for operator review" in result
    adapter._blackboard.redis.rpush.assert_awaited_once()


@pytest.mark.asyncio
async def test_generate_session_report_filters_thoughts():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._broadcast = AsyncMock()
    adapter._store_handoff_report = AsyncMock()

    thought_part = MagicMock()
    thought_part.thought = True
    thought_part.text = "Internal chain of thought reasoning that should NOT leak"

    content_part = MagicMock()
    content_part.thought = False
    content_part.text = "Actual session summary report"

    turn_complete_content = MagicMock()
    turn_complete_content.turn_complete = True

    msg1 = MagicMock()
    msg1.text = None
    msg1.server_content.model_turn.parts = [thought_part, content_part]
    msg1.server_content.turn_complete = False

    msg2 = MagicMock()
    msg2.text = None
    msg2.server_content = turn_complete_content

    async def mock_receive():
        yield msg1
        yield msg2

    mock_session = MagicMock()
    mock_session.send = AsyncMock()
    mock_session.receive = mock_receive

    await adapter._generate_session_report_on(mock_session)

    adapter._broadcast.assert_awaited_once()
    broadcast_call = adapter._broadcast.call_args[0][0]
    assert broadcast_call["type"] == "cortex_session_report"
    assert "Internal chain of thought reasoning" not in broadcast_call["report"]
    assert "Actual session summary report" in broadcast_call["report"]


@pytest.mark.asyncio
async def test_stop_prevents_connect_resurrection():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._stopped = False
    adapter._running = True
    adapter._connect_lock = asyncio.Lock()
    adapter._session = MagicMock()
    adapter._disconnect = AsyncMock()

    await adapter.stop()

    assert adapter._stopped is True
    assert adapter._running is False
    adapter._disconnect.assert_awaited_once()

    # Calling _connect() after stop() must immediately return without connecting
    adapter._client = MagicMock()
    await adapter._connect()
    adapter._client.aio.live.connect.assert_not_called()


@pytest.mark.asyncio
async def test_process_message_output_transcription():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._collecting_handoff = False
    adapter._handoff_buffer = []
    adapter._text_buffer = []
    adapter._broadcast = AsyncMock()
    adapter._active_meta_event_id = "evt-1"
    adapter._awaiting_jarvis_reply = False

    msg = MagicMock()
    msg.server_content.model_turn = None
    msg.server_content.output_transcription.text = "chunk of live text"
    msg.server_content.turn_complete = False
    msg.tool_call = None
    msg.go_away = None
    msg.session_resumption_update = None
    msg.text = None

    await adapter._process_message(msg)

    assert adapter._text_buffer == ["chunk of live text"]


def test_location_resolution():
    import os
    from unittest.mock import patch

    with patch.dict(os.environ, {"GCP_LOCATION": "global", "LLM_MODEL_SYSTEM2": "gemini-3.8-live"}, clear=True):
        adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
        adapter._model = "gemini-3.8-live"
        sys2_loc = os.getenv("GCP_LOCATION_SYSTEM2")
        if sys2_loc:
            adapter._location = sys2_loc
        elif adapter._model.startswith("gemini-3.8-live") and os.getenv("GCP_LOCATION", "global") == "global":
            adapter._location = "eu"
        else:
            adapter._location = os.getenv("GCP_LOCATION", "eu")
        assert adapter._location == "eu"

    with patch.dict(os.environ, {"GCP_LOCATION_SYSTEM2": "europe-west4", "GCP_LOCATION": "global"}, clear=True):
        adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
        adapter._model = "gemini-3.8-live"
        sys2_loc = os.getenv("GCP_LOCATION_SYSTEM2")
        if sys2_loc:
            adapter._location = sys2_loc
        elif adapter._model.startswith("gemini-3.8-live") and os.getenv("GCP_LOCATION", "global") == "global":
            adapter._location = "eu"
        else:
            adapter._location = os.getenv("GCP_LOCATION", "eu")
        assert adapter._location == "europe-west4"


# =============================================================================
# T-1 through T-4, T-6: Live API Adapter Tool Call & Orphan Lifecycle Tests
# =============================================================================


@pytest.mark.asyncio
async def test_process_message_single_tool_call():
    """T-1: Single tool call dispatches send_tool_response with 1:1 call ID parity."""
    from google.genai import types

    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._awaiting_jarvis_reply = True
    adapter._awaiting_jarvis_event_id = "evt-await"
    adapter._collecting_handoff = False
    adapter._handoff_buffer = []
    adapter._text_buffer = []
    adapter._last_pulse_event_id = "evt-100"
    adapter._broadcast = AsyncMock()
    adapter._session = MagicMock()
    adapter._session.send_tool_response = AsyncMock()
    adapter._handle_tool_call = AsyncMock(return_value="Handoff notes summary")

    fc = types.FunctionCall(name="recall_handoff_notes", id="call-1", args={"last_n": 3})

    msg = MagicMock()
    msg.server_content = None
    msg.go_away = None
    msg.session_resumption_update = None
    msg.text = None
    msg.tool_call = MagicMock()
    msg.tool_call.function_calls = [fc]

    await adapter._process_message(msg)

    assert adapter._awaiting_jarvis_reply is False
    assert adapter._awaiting_jarvis_event_id is None
    adapter._handle_tool_call.assert_awaited_once_with("recall_handoff_notes", {"last_n": 3})

    adapter._session.send_tool_response.assert_awaited_once()
    _, kwargs = adapter._session.send_tool_response.call_args
    assert "function_responses" in kwargs
    responses = kwargs["function_responses"]
    assert len(responses) == 1
    resp = responses[0]
    assert resp.name == "recall_handoff_notes"
    assert resp.id == "call-1"
    assert "Handoff notes summary" in resp.response.get("result", "")


@pytest.mark.asyncio
async def test_process_message_parallel_tool_calls():
    """T-2: Parallel tool calls are batched atomically into single send_tool_response."""
    from google.genai import types

    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._awaiting_jarvis_reply = False
    adapter._awaiting_jarvis_event_id = None
    adapter._collecting_handoff = False
    adapter._handoff_buffer = []
    adapter._text_buffer = []
    adapter._last_pulse_event_id = "evt-200"
    adapter._broadcast = AsyncMock()
    adapter._session = MagicMock()
    adapter._session.send_tool_response = AsyncMock()

    async def mock_handle_tool(name, args):
        if name == "recall_handoff_notes":
            return "Handoff notes result"
        elif name == "list_active_events":
            return "Active events: [evt-1, evt-2]"
        return "Unknown"

    adapter._handle_tool_call = AsyncMock(side_effect=mock_handle_tool)

    fc1 = types.FunctionCall(name="recall_handoff_notes", id="c1", args={"last_n": 2})
    fc2 = types.FunctionCall(name="list_active_events", id="c2", args={})

    msg = MagicMock()
    msg.server_content = None
    msg.go_away = None
    msg.session_resumption_update = None
    msg.text = None
    msg.tool_call = MagicMock()
    msg.tool_call.function_calls = [fc1, fc2]

    await adapter._process_message(msg)

    adapter._session.send_tool_response.assert_awaited_once()
    _, kwargs = adapter._session.send_tool_response.call_args
    assert "function_responses" in kwargs
    responses = kwargs["function_responses"]
    assert len(responses) == 2

    assert responses[0].id == "c1"
    assert responses[0].name == "recall_handoff_notes"
    assert "Handoff notes result" in responses[0].response.get("result", "")

    assert responses[1].id == "c2"
    assert responses[1].name == "list_active_events"
    assert "Active events: [evt-1, evt-2]" in responses[1].response.get("result", "")


@pytest.mark.asyncio
async def test_process_message_tool_execution_error():
    """T-3: Tool execution timeout or failure returns error string in FunctionResponse with matching id."""
    from google.genai import types

    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._awaiting_jarvis_reply = False
    adapter._awaiting_jarvis_event_id = None
    adapter._collecting_handoff = False
    adapter._handoff_buffer = []
    adapter._text_buffer = []
    adapter._last_pulse_event_id = "evt-300"
    adapter._broadcast = AsyncMock()
    adapter._session = MagicMock()
    adapter._session.send_tool_response = AsyncMock()
    adapter._handle_tool_call = AsyncMock(return_value="Error: Tool execution timed out after 60s")

    fc = types.FunctionCall(name="list_active_events", id="call-timeout-1", args={})

    msg = MagicMock()
    msg.server_content = None
    msg.go_away = None
    msg.session_resumption_update = None
    msg.text = None
    msg.tool_call = MagicMock()
    msg.tool_call.function_calls = [fc]

    await adapter._process_message(msg)

    adapter._session.send_tool_response.assert_awaited_once()
    _, kwargs = adapter._session.send_tool_response.call_args
    assert "function_responses" in kwargs
    responses = kwargs["function_responses"]
    assert len(responses) == 1
    resp = responses[0]
    assert resp.id == "call-timeout-1"
    assert resp.name == "list_active_events"
    assert "Error: Tool execution timed out after 60s" in resp.response.get("result", "")


@pytest.mark.asyncio
async def test_process_message_tool_execution_exception_fallback():
    """T-3: Tool execution exception caught by per-tool boundary and emits fallback FunctionResponse."""
    from google.genai import types

    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._awaiting_jarvis_reply = False
    adapter._awaiting_jarvis_event_id = None
    adapter._collecting_handoff = False
    adapter._handoff_buffer = []
    adapter._text_buffer = []
    adapter._last_pulse_event_id = "evt-301"
    adapter._broadcast = AsyncMock()
    adapter._session = MagicMock()
    adapter._session.send_tool_response = AsyncMock()
    adapter._handle_tool_call = AsyncMock(
        side_effect=RuntimeError("Handler crashed with secret: api_key=sk-1234567890abcdef and user@secret.com")
    )

    fc = types.FunctionCall(name="google_web_search", id="call-exc-1", args={"query": "k8s"})

    msg = MagicMock()
    msg.server_content = None
    msg.go_away = None
    msg.session_resumption_update = None
    msg.text = None
    msg.tool_call = MagicMock()
    msg.tool_call.function_calls = [fc]

    await adapter._process_message(msg)

    adapter._session.send_tool_response.assert_awaited_once()
    _, kwargs = adapter._session.send_tool_response.call_args
    assert "function_responses" in kwargs
    responses = kwargs["function_responses"]
    assert len(responses) == 1
    resp = responses[0]
    assert resp.id == "call-exc-1"
    assert resp.name == "google_web_search"
    result_str = resp.response.get("result", "")
    assert "Handler crashed with secret:" in result_str
    assert "api_key=[redacted-secret]" in result_str
    assert "[redacted-email]" in result_str
    assert "sk-1234567890abcdef" not in result_str
    assert "user@secret.com" not in result_str


@pytest.mark.asyncio
async def test_process_message_formatting_error_fallback():
    """Formatting or PII redaction failure falls back to error FunctionResponse with call_id preserved."""
    from google.genai import types

    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._awaiting_jarvis_reply = False
    adapter._awaiting_jarvis_event_id = None
    adapter._collecting_handoff = False
    adapter._handoff_buffer = []
    adapter._text_buffer = []
    adapter._last_pulse_event_id = "evt-400"
    adapter._broadcast = AsyncMock()
    adapter._session = MagicMock()
    adapter._session.send_tool_response = AsyncMock()
    adapter._handle_tool_call = AsyncMock(return_value="valid raw result")

    fc = types.FunctionCall(name="recall_handoff_notes", id="call-fmt-err", args={"last_n": 1})

    msg = MagicMock()
    msg.server_content = None
    msg.go_away = None
    msg.session_resumption_update = None
    msg.text = None
    msg.tool_call = MagicMock()
    msg.tool_call.function_calls = [fc]

    with patch("src.adapters.live_api_adapter._redact_pii", side_effect=ValueError("PII redactor corrupted")):
        await adapter._process_message(msg)

    adapter._session.send_tool_response.assert_awaited_once()
    _, kwargs = adapter._session.send_tool_response.call_args
    assert "function_responses" in kwargs
    responses = kwargs["function_responses"]
    assert len(responses) == 1
    resp = responses[0]
    assert resp.id == "call-fmt-err"
    assert resp.name == "recall_handoff_notes"
    assert resp.response.get("result", "") == "Error: Tool execution failed"


@pytest.mark.asyncio
async def test_process_message_send_failure_resilience():
    """T-4: send_tool_response failure logs warning and does not crash _process_message."""
    from google.genai import types

    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._awaiting_jarvis_reply = False
    adapter._awaiting_jarvis_event_id = None
    adapter._collecting_handoff = False
    adapter._handoff_buffer = []
    adapter._text_buffer = []
    adapter._last_pulse_event_id = "evt-500"
    adapter._broadcast = AsyncMock()
    adapter._session = MagicMock()
    adapter._session.send_tool_response = AsyncMock(side_effect=RuntimeError("WebSocket dropped"))
    adapter._handle_tool_call = AsyncMock(return_value="some result")

    fc = types.FunctionCall(name="list_active_events", id="call-drop-1", args={})

    msg = MagicMock()
    msg.server_content = None
    msg.go_away = None
    msg.session_resumption_update = None
    msg.text = None
    msg.tool_call = MagicMock()
    msg.tool_call.function_calls = [fc]

    # Must complete cleanly without raising
    await adapter._process_message(msg)
    adapter._session.send_tool_response.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_message_empty_function_calls():
    """Empty or None function_calls does not invoke send_tool_response."""
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._awaiting_jarvis_reply = False
    adapter._awaiting_jarvis_event_id = None
    adapter._collecting_handoff = False
    adapter._handoff_buffer = []
    adapter._text_buffer = []
    adapter._last_pulse_event_id = "evt-600"
    adapter._broadcast = AsyncMock()
    adapter._session = MagicMock()
    adapter._session.send_tool_response = AsyncMock()

    msg = MagicMock()
    msg.server_content = None
    msg.go_away = None
    msg.session_resumption_update = None
    msg.text = None
    msg.tool_call = MagicMock()
    msg.tool_call.function_calls = []

    await adapter._process_message(msg)
    adapter._session.send_tool_response.assert_not_called()

    # Also test msg.tool_call.function_calls is None
    msg.tool_call.function_calls = None
    await adapter._process_message(msg)
    adapter._session.send_tool_response.assert_not_called()


@pytest.mark.asyncio
async def test_create_system_review_ignores_stale_closed_orphan():
    """T-6: If active meta-event orphan is closed, clears state, resets parked set, and creates review."""
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._shadow = False
    adapter._brain = None
    adapter._active_meta_event_id = "evt-stale-closed"
    adapter._meta_event_parked_set = frozenset(["evt-stale-closed", "evt-other"])
    adapter._blackboard = MagicMock()
    adapter._blackboard.get_active_events = AsyncMock(return_value=["evt-active-1"])
    adapter._blackboard.find_active_event_by_source = AsyncMock(return_value=None)

    stale_event = MagicMock()
    stale_event.status.value = "closed"

    active_event = MagicMock()
    active_event.conversation = []
    active_event.brain_phase = "analysis"
    active_event.status = MagicMock()
    active_event.status.value = "active"
    active_event.queued_at = time.time()

    async def mock_get_event(eid):
        if eid == "evt-stale-closed":
            return stale_event
        return active_event

    adapter._blackboard.get_event = AsyncMock(side_effect=mock_get_event)
    adapter._blackboard.create_event = AsyncMock(return_value="evt-new-999")

    result = await adapter._tool_create_system_review(reason="Cross-event stall detected")

    assert "System review created: evt-new-999" in result
    assert adapter._active_meta_event_id == "evt-new-999"
    assert adapter._meta_event_parked_set == frozenset(["evt-active-1"])
    adapter._blackboard.create_event.assert_awaited_once()


@pytest.mark.asyncio
async def test_connect_discards_closed_orphan_and_resets_parked_set():
    """Step 4: _connect validates orphan against get_event, resetting parked set if closed."""
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._project = "test"
    adapter._location = "us-central1"
    adapter._model = "test-model"
    adapter._connect_lock = asyncio.Lock()
    adapter._resumption_handle = None
    adapter._idle_watchdog_task = None
    adapter._receive_task = None
    adapter._shadow = False
    adapter._neuron_labels = {}
    adapter._broadcast_status = AsyncMock()
    adapter._load_neuron_labels = AsyncMock()
    adapter._build_live_tools = MagicMock(return_value=[])
    adapter._receive_loop = AsyncMock()
    adapter._idle_watchdog = AsyncMock()

    adapter._active_meta_event_id = "evt-old-orphan"
    adapter._meta_event_parked_set = frozenset(["evt-1"])

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = MagicMock()
    adapter._client = MagicMock()
    adapter._client.aio.live.connect.return_value = mock_ctx

    stale_event = MagicMock()
    stale_event.status = "closed"

    adapter._blackboard = MagicMock()
    adapter._blackboard.find_active_event_by_source = AsyncMock(return_value="evt-old-orphan")
    adapter._blackboard.get_event = AsyncMock(return_value=stale_event)
    adapter._blackboard.get_active_events = AsyncMock(return_value=[])

    await adapter._connect()

    assert adapter._active_meta_event_id is None
    assert adapter._meta_event_parked_set == frozenset()
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_is_event_closed_or_missing():
    """Unit test for _is_event_closed_or_missing verifying dicts, exceptions, and missing attributes."""
    from src.adapters.live_api_adapter import _is_event_closed_or_missing

    # Returns True for dict {"status": "closed"}
    bb_closed = MagicMock()
    bb_closed.get_event = AsyncMock(return_value={"status": "closed"})
    assert await _is_event_closed_or_missing(bb_closed, "evt-closed") is True

    # Returns False for dict {"status": "active"}
    bb_active = MagicMock()
    bb_active.get_event = AsyncMock(return_value={"status": "active"})
    assert await _is_event_closed_or_missing(bb_active, "evt-active") is False

    # Returns True when get_event raises an Exception (fail-safe)
    bb_err = MagicMock()
    bb_err.get_event = AsyncMock(side_effect=RuntimeError("Transient DB error"))
    assert await _is_event_closed_or_missing(bb_err, "evt-err") is True

    # Returns True when blackboard has no get_event
    assert await _is_event_closed_or_missing(object(), "evt-no-method") is True
    assert await _is_event_closed_or_missing(None, "evt-none-bb") is True


# ---------------------------------------------------------------------------
# Test: Receive loop clean closure vs unexpected error handling
# ---------------------------------------------------------------------------


class TestReceiveLoopClosure:
    """Verify code 1000/GoAway clean closure logs INFO without traceback and triggers single reconnect."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "exc,go_away_flag",
        [
            (Exception("1000: GoAway deadline exceeded"), False),
            (Exception("ConnectionClosedOK: 1000"), False),
            (Exception("Normal disconnect"), True),
        ],
    )
    async def test_clean_closure_logs_info_without_traceback_and_reconnects(self, exc, go_away_flag):
        adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
        adapter._running = True
        adapter._go_away_received = go_away_flag
        adapter._try_reconnect = AsyncMock()

        async def stop_running():
            adapter._running = False
        adapter._try_reconnect.side_effect = stop_running

        class CleanSession:
            def receive(self):
                async def _gen():
                    raise exc
                    yield
                return _gen()

        adapter._session = CleanSession()

        with patch("src.adapters.live_api_adapter.logger") as mock_logger:
            await adapter._receive_loop()

            info_calls = [call for call in mock_logger.info.call_args_list if "connection closed cleanly" in str(call)]
            assert len(info_calls) >= 1

            warn_calls = [call for call in mock_logger.warning.call_args_list if "receive loop error" in str(call)]
            assert len(warn_calls) == 0

            assert adapter._go_away_received is False
            adapter._try_reconnect.assert_called_once()

    @pytest.mark.asyncio
    async def test_non_clean_exception_logs_warning_with_traceback(self):
        adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
        adapter._running = True
        adapter._go_away_received = False
        adapter._try_reconnect = AsyncMock()

        async def stop_running():
            adapter._running = False
        adapter._try_reconnect.side_effect = stop_running

        class ErrorSession:
            def receive(self):
                async def _gen():
                    raise RuntimeError("500 Internal Server Error")
                    yield
                return _gen()

        adapter._session = ErrorSession()

        with patch("src.adapters.live_api_adapter.logger") as mock_logger:
            await adapter._receive_loop()

            warn_calls = [call for call in mock_logger.warning.call_args_list if "receive loop error" in str(call)]
            assert len(warn_calls) >= 1
            call_kwargs = warn_calls[0].kwargs
            assert call_kwargs.get("exc_info") is True

            adapter._try_reconnect.assert_called_once()

