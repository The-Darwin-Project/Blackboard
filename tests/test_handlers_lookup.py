# BlackBoard/tests/test_handlers_lookup.py
# @ai-rules:
# 1. [Constraint]: Verify handlers lookup gracefully handles None/str/NaN inputs.
import pytest
import time
from src.agents.handlers_lookup import handle_consult_deep_memory
from src.adapters.live_api_adapter import LiveAPIAdapter

class MockTurn:
    def __init__(self, action, evidence):
        self.action = action
        self.evidence = evidence

class MockEvent:
    def __init__(self, source="chat", conversation=None, service="test-svc"):
        self.source = source
        self.conversation = conversation or []
        self.service = service

class MockBlackboard:
    async def get_event(self, event_id):
        return MockEvent()

class MockPulseTracker:
    async def get_heat(self):
        return {}

class MockArchivist:
    def __init__(self, knowledge=None, lessons=None, memories=None):
        self.knowledge = knowledge or []
        self.lessons = lessons or []
        self.memories = memories or []

    async def get_memory(self, nid):
        for m in self.memories:
            if m["id"] == nid: return m
        return None

    async def get_knowledge(self, nid):
        for m in self.knowledge:
            if m["id"] == nid: return m
        return None

    async def get_lesson(self, nid):
        for m in self.lessons:
            if m["id"] == nid: return m
        return None

    async def search(self, query, **kwargs):
        return self.memories
    
    async def search_knowledge(self, query, **kwargs):
        return self.knowledge

    async def search_lessons(self, query, **kwargs):
        return self.lessons

    async def embed_query(self, query):
        return [0.1, 0.2]

class MockToolContext:
    def __init__(self, archivist):
        self.archivist = archivist
        self.turns = []

    def get_blackboard(self):
        return MockBlackboard()

    def get_agent_instance(self, name):
        if name == "_archivist_memory":
            return self.archivist
        return None

    async def next_turn_number(self, event_id):
        return 1

    async def append_and_broadcast(self, event_id, turn):
        self.turns.append(turn)


@pytest.mark.asyncio
async def test_t1_handle_consult_deep_memory_explicit_none_durations():
    memories = [{
        "id": "mem-1",
        "score": 0.85,
        "payload": {
            "duration_seconds": None,
            "defer_patterns": [{"duration_seconds": None}],
            "operational_timings": [{"process": "test", "duration_seconds": None}]
        }
    }]
    ctx = MockToolContext(MockArchivist(memories=memories))
    
    # Should raise TypeError without fix
    result = await handle_consult_deep_memory(ctx, "evt-1", {"query": "test"}, [])
    
    assert result is True
    assert len(ctx.turns) == 1
    evidence = ctx.turns[0].evidence
    assert "0m total" in evidence or "0m" in evidence


@pytest.mark.asyncio
async def test_t2_handle_consult_deep_memory_and_helpers_with_none_payload():
    # 1. handle_consult_deep_memory
    memories = [{
        "id": "mem-1",
        "score": None,
        "payload": None
    }]
    ctx = MockToolContext(MockArchivist(memories=memories))
    
    # Should raise AttributeError or TypeError without fix
    await handle_consult_deep_memory(ctx, "evt-1", {"query": "test"}, [])
    
    # 2. LiveAPIAdapter._tool_get_neuron_details
    archivist = MockArchivist(
        knowledge=[{"id": "k-1", "payload": None}],
        memories=[{"id": "m-1", "payload": None}],
        lessons=[{"id": "l-1", "payload": None}]
    )
    # Monkeypatch hasattr check in live_api_adapter
    adapter = LiveAPIAdapter(None, archivist, MockPulseTracker(), None)
    
    await adapter._handle_tool_call("get_neuron_details", {"neuron_id": "memory:m-1"})
    await adapter._handle_tool_call("get_neuron_details", {"neuron_id": "knowledge:k-1"})
    await adapter._handle_tool_call("get_neuron_details", {"neuron_id": "lesson:l-1"})
    
    # 3. LiveAPIAdapter._tool_search_deep_memory
    await adapter._handle_tool_call("search_deep_memory", {"query": "test"})
    
    # 4. Archivist helper sites - let's import it and test passing malformed valid_until
    from src.agents.archivist import Archivist
    # "valid_until is None / malformed string"
    archivist_bad_valid = MockArchivist(
        knowledge=[{"id": "k-2", "payload": {"valid_until": "bad_date_format", "fact": "x"}}]
    )
    adapter2 = LiveAPIAdapter(None, archivist_bad_valid, MockPulseTracker(), None)
    # The adapter._tool_get_neuron_details does: `payload["valid_until"] < time.time()`
    # If it's a string, this raises TypeError
    await adapter2._handle_tool_call("get_neuron_details", {"neuron_id": "knowledge:k-2"})


@pytest.mark.asyncio
async def test_t3_handle_consult_deep_memory_regression():
    memories = [{
        "id": "mem-1",
        "score": 0.95,
        "payload": {
            "duration_seconds": 540,
            "defer_patterns": [{"duration_seconds": 180}],
            "operational_timings": [{"process": "test", "duration_seconds": 360}]
        }
    }]
    ctx = MockToolContext(MockArchivist(memories=memories))
    
    await handle_consult_deep_memory(ctx, "evt-1", {"query": "test"}, [])
    
    assert len(ctx.turns) == 1
    evidence = ctx.turns[0].evidence
    assert "9m" in evidence
    assert "3m" in evidence
    assert "test=6m" in evidence


@pytest.mark.asyncio
async def test_safe_seconds_and_score():
    from src.agents.handlers_lookup import _safe_seconds, _safe_score
    import math
    assert _safe_seconds('120') == 120
    assert _safe_score('0.85') == 0.85
    assert _safe_seconds(float('nan')) == 0
    assert _safe_score(float('nan')) == 0.0
    assert _safe_score(float('inf')) == 0.0
    assert _safe_seconds('abc') == 0
    assert _safe_score('abc') == 0.0

