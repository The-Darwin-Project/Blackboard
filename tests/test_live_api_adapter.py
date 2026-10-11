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

# T-5: Tool execution exception safety
@pytest.mark.asyncio
async def test_handle_tool_call_exception_safety():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._tool_list_active_events = AsyncMock(side_effect=ValueError("broken"))
    
    result = await adapter._handle_tool_call("list_active_events", {})
    assert result == "Error: broken"

# T-9: Resumption rejection fallback & replay
@pytest.mark.asyncio
async def test_reconnect_resumption_rejection_fallback():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._resumption_handle = "stale-handle"
    adapter._last_pulse_event_id = "evt-1"
    adapter._replay_pending_context = AsyncMock()
    adapter._running = True
    adapter._session = None
    adapter._brain = MagicMock()
    adapter._generating_report = False

    adapter._project = "test"
    adapter._location = "us-central1"
    adapter._model = "test-model"
    
    mock_ctx = AsyncMock()
    mock_ctx.__aenter__.return_value = MagicMock()
    adapter._client = MagicMock()
    
    connect_calls = []
    def mock_connect(*args, **kwargs):
        connect_calls.append(adapter._resumption_handle)
        if len(connect_calls) == 1:
            raise Exception("Invalid session resumption handle")
        return mock_ctx

    adapter._client.aio.live.connect.side_effect = mock_connect

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

    # To trigger the fallback logic, we have to call _try_reconnect
    # because _connect() itself doesn't loop in the executor implementation,
    # _try_reconnect catches exception from _connect and retries.
    # Wait, the system message said "The fallback is implemented inside `_connect()` itself via a 2-attempt loop when `_resumption_handle` fails."
    # If the executor put it inside `_connect()`, we just call `_connect()`.
    await adapter._connect()

    assert connect_calls == ["stale-handle", None]
    assert adapter._resumption_handle is None
    adapter._replay_pending_context.assert_called_once()

@pytest.mark.asyncio
async def test_try_reconnect_does_not_call_replay_pending_context():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._running = True
    adapter._generating_report = False
    adapter._last_pulse_time = 1000.0
    adapter._session = None
    adapter._brain = MagicMock()
    adapter._brain.pending_jarvis_event_ids.return_value = []
    adapter._connect = AsyncMock()
    adapter._replay_pending_context = AsyncMock()

    with patch("time.time", return_value=1050.0), patch("asyncio.sleep", AsyncMock()):
        async def fake_connect():
            adapter._session = MagicMock()
        adapter._connect.side_effect = fake_connect
        await adapter._try_reconnect()

    adapter._connect.assert_called_once()
    adapter._replay_pending_context.assert_not_called()

@pytest.mark.asyncio
async def test_rotate_session_clears_resumption_handle():
    adapter = LiveAPIAdapter.__new__(LiveAPIAdapter)
    adapter._session = MagicMock()
    adapter._session.send = AsyncMock()
    
    async def mock_receive():
        mock_msg = MagicMock()
        mock_msg.text = "Session summary text"
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
    
    current = asyncio.current_task()
    adapter._receive_task = current
    adapter._idle_watchdog_task = None
    
    await adapter._connect()
    
    assert not current.cancelled()

