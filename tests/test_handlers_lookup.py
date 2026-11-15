# BlackBoard/tests/test_handlers_lookup.py
# @ai-rules:
# 1. [Constraint]: Verify handlers_lookup, the Live API adapter and Archivist tolerate None/str/NaN/inf payload fields.
# 2. [Gotcha]: Every test asserts on rendered output or state -- a bare "does not raise" call proves nothing.
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
async def test_t2_handle_consult_deep_memory_with_none_payload_and_score():
    memories = [{"id": "mem-1", "score": None, "payload": None}]
    lessons = [{"id": "les-1", "score": None, "payload": None}]
    knowledge = [{"id": "k-1", "score": None, "payload": None}]
    ctx = MockToolContext(MockArchivist(memories=memories, lessons=lessons, knowledge=knowledge))

    assert await handle_consult_deep_memory(ctx, "evt-1", {"query": "test"}, []) is True

    assert len(ctx.turns) == 1
    evidence = ctx.turns[0].evidence
    assert "### Reference Facts" in evidence and "### Lessons Learned" in evidence and "### Past Events" in evidence
    assert evidence.count("score: 0.00") == 2  # lesson + past event
    assert "Duration: ?, defers: 0m, timings: [none]" in evidence


@pytest.mark.asyncio
async def test_t2_adapter_neuron_details_tolerate_none_payload():
    archivist = MockArchivist(
        knowledge=[{"id": "k-1", "payload": None}],
        memories=[{"id": "m-1", "payload": None}],
        lessons=[{"id": "l-1", "payload": None}],
    )
    adapter = LiveAPIAdapter(None, archivist, MockPulseTracker(), None)

    for neuron in ("memory:m-1", "knowledge:k-1", "lesson:l-1"):
        out = await adapter._handle_tool_call("get_neuron_details", {"neuron_id": neuron})
        assert out.startswith(f"Neuron: {neuron}"), out
        assert "Error" not in out

    search = await adapter._handle_tool_call("search_deep_memory", {"query": "test"})
    assert "Deep Memory Search" in search


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_until, stale", [
    ("bad_date_format", False),
    (None, False),
    (True, False),
    (1.0, True),               # long past
    (time.time() + 3600, False),
])
async def test_t2_adapter_stale_marker_requires_numeric_valid_until(valid_until, stale):
    archivist = MockArchivist(knowledge=[{"id": "k-2", "payload": {"valid_until": valid_until, "fact": "x"}}])
    adapter = LiveAPIAdapter(None, archivist, MockPulseTracker(), None)
    out = await adapter._handle_tool_call("get_neuron_details", {"neuron_id": "knowledge:k-2"})
    assert out.startswith("Neuron: knowledge:k-2"), out
    assert ("[STALE]" in out) is stale


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


@pytest.mark.parametrize("raw, expected", [
    ("120", 120), (120, 120), (12.9, 12), (None, 0), (True, 0), ("abc", 0),
    (float("nan"), 0), (float("inf"), 0), (float("-inf"), 0), ([], 0), ({}, 0),
])
def test_safe_seconds(raw, expected):
    from src.agents.handlers_lookup import _safe_seconds
    assert _safe_seconds(raw) == expected


@pytest.mark.parametrize("raw, expected", [
    ("0.85", 0.85), (0.5, 0.5), (1, 1.0), (None, 0.0), (True, 0.0), ("abc", 0.0),
    (float("nan"), 0.0), (float("inf"), 0.0), (float("-inf"), 0.0), ([], 0.0), ({}, 0.0),
])
def test_safe_score(raw, expected):
    from src.agents.handlers_lookup import _safe_score
    assert _safe_score(raw) == expected


@pytest.mark.asyncio
@pytest.mark.parametrize("bad", ["abc", float("nan"), float("inf"), None, True])
async def test_consult_deep_memory_non_numeric_scores_render_zero(bad):
    memories = [{"id": "m", "score": bad, "payload": {"symptom": "s", "duration_seconds": bad}}]
    lessons = [{"id": "l", "score": bad, "payload": {"title": "t"}}]
    ctx = MockToolContext(MockArchivist(memories=memories, lessons=lessons))

    assert await handle_consult_deep_memory(ctx, "evt-1", {"query": "q"}, []) is True

    evidence = ctx.turns[0].evidence
    assert evidence.count("score: 0.00") == 2  # lesson + past event
    assert "nan" not in evidence.lower() and "inf" not in evidence.lower()


@pytest.mark.asyncio
async def test_consult_deep_memory_none_defer_and_timing_lists():
    memories = [{"id": "m", "score": 0.5, "payload": {
        "defer_patterns": None, "operational_timings": None, "duration_seconds": "bad",
    }}]
    ctx = MockToolContext(MockArchivist(memories=memories))
    assert await handle_consult_deep_memory(ctx, "evt-1", {"query": "q"}, []) is True
    assert "score: 0.50" in ctx.turns[0].evidence


# ---------------------------------------------------------------------------
# Archivist None-payload / None-keywords guards (touched hunks)
# ---------------------------------------------------------------------------

def _archivist_with_store(points=None, search_results=None):
    from unittest.mock import AsyncMock, MagicMock
    from src.agents.archivist import Archivist

    arch = Archivist()
    arch._ensure_initialized = AsyncMock(return_value=True)
    arch._embed = AsyncMock(return_value=[0.1, 0.2])
    arch._knowledge_ready = True
    arch._vector_store = MagicMock()
    arch._vector_store.get_points = AsyncMock(return_value=points or [])
    arch._vector_store.upsert = AsyncMock()
    arch._vector_store.search = AsyncMock(return_value=search_results or [])
    return arch


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [
    {"symptom": "s", "pattern_keywords": None, "keywords": None, "instance_keywords": None},
    {"symptom": "s", "pattern_keywords": None, "keywords": ["fallback-kw"]},
    {"symptom": "s"},
    None,
])
async def test_correct_memory_tolerates_none_keywords_and_payload(payload):
    arch = _archivist_with_store(points=[{"id": "p", "payload": payload}])

    assert await arch.correct_memory("evt-1", "new root cause", "new fix") is True

    embed_text = arch._embed.await_args.args[0]
    assert "new root cause" in embed_text and "new fix" in embed_text
    if payload and payload.get("keywords") and payload.get("pattern_keywords") is None:
        assert "fallback-kw" in embed_text
    upserted = arch._vector_store.upsert.await_args.kwargs["payload"]
    assert upserted["root_cause"] == "new root cause"
    assert upserted["corrected"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("valid_until, stale", [
    (1.0, True), (None, False), ("soon", False), (True, False), (time.time() + 3600, False),
])
async def test_search_knowledge_stale_flag_numeric_only(valid_until, stale):
    arch = _archivist_with_store(search_results=[{"id": "k", "score": 0.4, "payload": {"valid_until": valid_until}}])
    results = await arch.search_knowledge("q")
    assert len(results) == 1
    assert bool(results[0].get("stale")) is stale


@pytest.mark.asyncio
async def test_search_knowledge_none_payload_does_not_raise():
    arch = _archivist_with_store(search_results=[{"id": "k", "score": 0.4, "payload": None}])
    results = await arch.search_knowledge("q")
    assert len(results) == 1 and not results[0].get("stale")


# ---------------------------------------------------------------------------
# Archivist archive/store summary paths: `or []` guards (pattern/instance keywords, reference_facts)
# ---------------------------------------------------------------------------

def _closed_event():
    from src.models import ConversationTurn, EventDocument

    turns = [ConversationTurn(turn=1, actor="brain", action="think", thoughts="x"),
             ConversationTurn(turn=2, actor="brain", action="close", thoughts="done")]
    return EventDocument(id="evt-arch", source="headhunter", conversation=turns, status="closed",
                         service="svc", event={"reason": "r", "evidence": "e"})


def _archivist_for_summary(summary: dict, *, claude: bool):
    import json
    from types import SimpleNamespace
    from unittest.mock import AsyncMock, MagicMock

    arch = _archivist_with_store()
    arch._extract_and_store_graph = AsyncMock()
    arch.store_knowledge = AsyncMock()
    response = MagicMock()
    response.usage = MagicMock()
    if claude:
        response.function_call = SimpleNamespace(args=dict(summary))
        response.text = ""
    else:
        response.function_call = None
        response.text = json.dumps(summary)
    adapter = MagicMock()
    adapter.generate = AsyncMock(return_value=response)
    arch._get_claude_adapter = AsyncMock(return_value=adapter if claude else None)
    arch._get_adapter = AsyncMock(return_value=adapter)
    return arch


_NULLY_SUMMARY = {
    "symptom": "s", "root_cause": "r", "fix_action": "f", "outcome": "resolved",
    "pattern_keywords": None, "keywords": None, "instance_keywords": None, "reference_facts": None,
}


@pytest.mark.asyncio
@pytest.mark.parametrize("claude", [True, False], ids=["claude_path", "gemini_fallback_path"])
async def test_archive_event_tolerates_null_keywords_and_reference_facts(claude):
    arch = _archivist_for_summary(_NULLY_SUMMARY, claude=claude)

    await arch.archive_event(_closed_event())

    arch._vector_store.upsert.assert_awaited_once()
    embed_text = arch._embed.await_args.args[0]
    assert "None" not in embed_text
    assert embed_text.split() == ["s", "r", "f", "resolved"]
    arch.store_knowledge.assert_not_awaited()
    # Graph extraction runs after the facts loop / summary log line -- proves neither aborted on None.
    arch._extract_and_store_graph.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("claude", [True, False], ids=["claude_path", "gemini_fallback_path"])
async def test_archive_event_stores_reference_facts_and_keyword_fallbacks(claude):
    summary = dict(_NULLY_SUMMARY, pattern_keywords=None, keywords=["kw-a", "kw-b"], instance_keywords=["inst-1"],
                   reference_facts=[{"topic": "t", "scope": "convention", "fact": "f1", "service": "svc"}])
    arch = _archivist_for_summary(summary, claude=claude)

    await arch.archive_event(_closed_event())

    embed_text = arch._embed.await_args.args[0]
    assert "kw-a kw-b" in embed_text and "inst-1" in embed_text
    arch.store_knowledge.assert_awaited_once()
    assert arch.store_knowledge.await_args.kwargs["topic"] == "t"
    arch._extract_and_store_graph.assert_awaited_once()
