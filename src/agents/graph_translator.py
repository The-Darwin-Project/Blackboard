# BlackBoard/src/agents/graph_translator.py
# @ai-rules:
# 1. [Constraint]: MVP — no LLM in the critical read path. Direct service-name lookup only.
# 2. [Pattern]: Returns list of (entity_type, entity_id) tuples for KG query.
# 3. [Pattern]: Fail-open. Returns empty list on any error.
# 4. [Gotcha]: This is a placeholder for future Flash Lite multi-hop translation.
#    When upgrading: add LLM call to identify cross-service dependencies, cascade entities.
# 5. [Constraint]: Must stay < 10ms latency (no network calls in MVP).
"""
Graph query translator — determines which KG entities to look up.

MVP: direct service-name lookup only (no LLM). Returns entity type + ID
pairs for KnowledgeGraphStore.query_related(). Future upgrade path: Flash
Lite identifies multi-hop query targets from event context.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def translate_to_lookups(
    service: str,
    event_source: str = "",
    domain: str = "",
) -> list[tuple[str, str]]:
    """Determine which graph entities to query for the given event context.

    MVP: single lookup by service name. Returns immediately (no I/O).

    Future: Flash Lite translates event context into multi-hop targets
    (e.g., "what services depend on X?" → cascade queries).
    """
    if not service or service.lower() in ("general", "system", ""):
        return []

    return [("Service", f"service:{service}")]
