"""Tests for LiveAPIAdapter duplicate review handling."""
import pytest
import asyncio
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
    
    result = await adapter._tool_create_system_review(reason="test review pattern")
    assert "evt-12345" in result
    assert "Review already active" in result

# T-1: BLOCKING behavior injection
def test_build_live_tools_blocking():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._rag_enabled = False
    adapter._rag_corpus_id = ""
    
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
    adapter._load_neuron_labels = AsyncMock(side_effect=[Exception("labels failed"), None])

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
    adapter._load_neuron_labels = AsyncMock(side_effect=Exception("labels failed"))

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
    adapter._tool_timeout = 60.0
    adapter._tool_list_active_events = AsyncMock()
    
    with patch("asyncio.timeout", side_effect=TimeoutError):
        result = await adapter._handle_tool_call("list_active_events", {})
        assert "timed out" in result

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
async def test_handle_tool_call_mutating_shielded():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._tool_timeout = 60.0
    adapter._tool_send_event_message = AsyncMock(return_value="Message sent")

    result = await adapter._handle_tool_call("send_event_message", {"event_id": "evt-1", "message": "hello"})
    assert result == "Message sent"
    adapter._tool_send_event_message.assert_awaited_once_with("evt-1", "hello")

