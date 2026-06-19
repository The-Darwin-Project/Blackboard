# /architect-bootstrap: Temporal/Duration Filtering for Deep Memory Search

## Context

`consult_deep_memory` currently searches Qdrant via pure vector similarity. When users ask temporal questions ("what happened yesterday?", "events over 4 hours", "pipeline failures this week"), the search matches semantics but ignores time and duration.

The Qdrant `darwin_events` collection already stores structured payload fields:
- `closed_at` (ISO timestamp string)
- `duration_seconds` (int)
- `service` (string)
- `brain_domain` (string)
- `source` (string)

These fields are available for Qdrant payload filtering alongside vector search.

## What Changed Recently

- `consult_deep_memory` handler in `brain.py` (commit `a41e59f`) now supports query-level dedup and skill pointers in responses
- The tool schema is defined in `src/agents/llm/types.py` (`BRAIN_TOOL_SCHEMAS`)
- Qdrant client is in `src/memory/vector_store.py` (`VectorStore.search()`)
- Archivist search methods: `search()`, `search_lessons()`, `search_knowledge()` in `src/agents/archivist.py`

## Proposed Approach: Structured Filter Parameters on the Tool Schema

Add optional filter parameters to the `consult_deep_memory` tool so FRIDAY can provide structured filters alongside the semantic query:

```python
"consult_deep_memory": {
    "query": "pipeline failures in kubevirt",   # existing (semantic search)
    "time_range_hours": 48,                      # new: filter to last N hours
    "min_duration_minutes": 240,                 # new: events lasting >= N minutes
    "service": "kubevirt",                       # new: filter by service name
}
```

FRIDAY decides what to filter on based on the user's question. We don't parse natural language -- she structures it herself (same pattern as classify_event, defer_event).

## Implementation Scope

1. **Tool schema** (`src/agents/llm/types.py`): Add 3 optional parameters to `consult_deep_memory`
2. **Brain handler** (`src/agents/brain.py`): Extract filter args, build Qdrant filter conditions
3. **Archivist search** (`src/agents/archivist.py`): Accept optional `filters` dict, pass to Qdrant
4. **VectorStore** (`src/memory/vector_store.py`): Wire Qdrant payload filter conditions into search queries
5. **Deep memory skill** (`brain_skills/always/04-deep-memory.md`): Behavioral guidance on when to use filters (principle, not prescription)

## Constraints

- Tool description must NOT list specific filter examples (HOW not WHAT principle)
- Filter parameters are optional -- default behavior (pure semantic search) unchanged
- Qdrant filter syntax: `models.Filter(must=[models.FieldCondition(...)])`
- `closed_at` is stored as ISO string -- need range comparison or convert to epoch at archive time
- `duration_seconds` is already numeric -- direct range filter
- `service` is already a string -- exact match filter

## Key Files to Read

- `src/agents/llm/types.py` -- tool schema definition (~line 165)
- `src/agents/brain.py` -- consult_deep_memory handler (~line 2922)
- `src/agents/archivist.py` -- search methods
- `src/memory/vector_store.py` -- Qdrant search wrapper
- `src/agents/brain_skills/always/04-deep-memory.md` -- deep memory behavioral skill

## Questions for the Architect

1. Should `closed_at` be stored as epoch float in Qdrant payloads (simpler range filtering) or kept as ISO string (human-readable but harder to filter)?
2. Should filters apply to all 3 search methods (events, lessons, knowledge) or only events?
3. Is there a risk of FRIDAY over-filtering (combining too many filters = zero results)?
