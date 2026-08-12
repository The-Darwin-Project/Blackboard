# BlackBoard/src/agents/graph_recall.py
# @ai-rules:
# 1. [Constraint]: Fail-open on ALL errors. Never raises. Returns None on failure.
# 2. [Pattern]: 3s total timeout via asyncio.wait_for. Fail-open on timeout.
# 3. [Constraint]: Output capped at ~2000 tokens (~8000 chars). Truncates oldest relationships.
# 4. [Pattern]: Returns None when graph is empty/insufficient — caller falls back to Qdrant.
# 5. [Gotcha]: kg_store may be None (KG_POSTGRES_URL not set). Check before querying.
# 6. [Pattern]: Uses <prior_knowledge> XML fence for SI injection (volatile=true).
"""
Graph recall module for pre-generation knowledge injection.

Queries the Postgres knowledge graph for entities related to the current
event's service, formats results as structured markdown inside a
<prior_knowledge> fence, and returns it for SI injection. Fail-open:
returns None on any error, letting the caller fall back to Qdrant.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..memory.knowledge_graph import KnowledgeGraphStore

logger = logging.getLogger(__name__)

_GRAPH_RECALL_TIMEOUT = float(os.getenv("GRAPH_RECALL_TIMEOUT", "3"))
_MAX_RESULT_CHARS = int(os.getenv("GRAPH_RECALL_MAX_CHARS", "8000"))
_MIN_USEFUL_ENTITIES = int(os.getenv("GRAPH_RECALL_MIN_ENTITIES", "2"))
_SKIP_SERVICES = frozenset({"general", "system", ""})

_FENCE_CLOSE_RE = re.compile(r"</prior_knowledge>", re.IGNORECASE)

# Entity properties originate from free-text agent output run through an LLM
# extractor that only constrains JSON *shape*, not content, then persist in
# Postgres with no TTL -- stripping only "</prior_knowledge>" is not enough to
# stop tag/fence-based prompt injection (same class of bug as brain.py's
# _sanitize_override_reason). Blanket-strip all tag-like sequences instead.
_TAG_RE = re.compile(r"<[^>]+>")


def _sanitize(text: Any) -> str:
    """Strip tag-like sequences from KG-derived text before it enters the SI fence."""
    if not isinstance(text, str):
        return "" if text is None else _TAG_RE.sub("", str(text))
    return _TAG_RE.sub("", text)


async def get_graph_context(
    kg_store: KnowledgeGraphStore | None,
    service: str,
    event_source: str = "",
    domain: str = "",
) -> str | None:
    """Query the knowledge graph for service-related context.

    Returns a formatted <prior_knowledge> fence block for SI injection,
    or None if the graph is empty/unavailable (triggering Qdrant fallback).
    """
    if not kg_store or not service or service.lower() in _SKIP_SERVICES:
        return None

    from .graph_translator import translate_to_lookups
    lookups = translate_to_lookups(service=service, event_source=event_source, domain=domain)
    if not lookups:
        return None

    try:
        entity_type, entity_id = lookups[0]
        related = await asyncio.wait_for(
            kg_store.query_related(entity_type, entity_id),
            timeout=_GRAPH_RECALL_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning(
            "Graph recall timed out after %ss for service=%s",
            _GRAPH_RECALL_TIMEOUT, service,
        )
        return None
    except Exception as e:
        logger.warning("Graph recall query failed (non-fatal): %s", e)
        return None

    if len(related) < _MIN_USEFUL_ENTITIES:
        logger.debug(
            "Graph recall: insufficient entities (%d) for service=%s, falling back",
            len(related), service,
        )
        return None

    return _format_graph_context(related, service)


def _format_graph_context(
    related: list[dict[str, Any]],
    service: str,
) -> str | None:
    """Format graph query results as a prior_knowledge fence block."""
    lines: list[str] = [
        f"## Knowledge Graph: {_sanitize(service)}",
        "",
    ]

    events: list[dict] = []
    fixes: list[dict] = []
    services: list[dict] = []

    for entity in related:
        etype = entity.get("entity_type", "")
        if etype == "Event":
            events.append(entity)
        elif etype == "Fix":
            fixes.append(entity)
        elif etype == "Service":
            services.append(entity)

    if events:
        lines.append(f"### Past Events ({len(events)})")
        for ev in events:
            props = _parse_props(ev.get("properties"))
            eid = _sanitize(ev.get("entity_id", ""))
            summary = _sanitize(props.get("summary", ""))
            domain_val = _sanitize(props.get("domain", ""))
            outcome = _sanitize(props.get("outcome", ""))
            rel = _sanitize(ev.get("rel_type", ""))
            parts = [f"- **{eid}**"]
            if rel:
                parts[0] += f" ({rel})"
            if summary:
                parts.append(f"  Summary: {summary}")
            if domain_val:
                parts.append(f"  Domain: {domain_val}")
            if outcome:
                parts.append(f"  Outcome: {outcome}")
            lines.extend(parts)
        lines.append("")

    if fixes:
        lines.append(f"### Applied Fixes ({len(fixes)})")
        for fix in fixes:
            props = _parse_props(fix.get("properties"))
            fid = _sanitize(fix.get("entity_id", ""))
            desc = _sanitize(props.get("description", ""))
            fix_type = _sanitize(props.get("fix_type", ""))
            effective = _sanitize(props.get("effective"))
            rel = _sanitize(fix.get("rel_type", ""))
            parts = [f"- **{fid}**"]
            if rel:
                parts[0] += f" ({rel})"
            if fix_type:
                parts.append(f"  Type: {fix_type}")
            if desc:
                parts.append(f"  Description: {desc}")
            if effective:
                parts.append(f"  Effective: {effective}")
            lines.extend(parts)
        lines.append("")

    if services:
        lines.append(f"### Related Services ({len(services)})")
        for svc in services:
            props = _parse_props(svc.get("properties"))
            sid = _sanitize(svc.get("entity_id", ""))
            name = _sanitize(props.get("name", sid))
            ns = _sanitize(props.get("namespace", ""))
            rel = _sanitize(svc.get("rel_type", ""))
            parts = [f"- **{name}**"]
            if rel:
                parts[0] += f" ({rel})"
            if ns:
                parts.append(f"  Namespace: {ns}")
            lines.extend(parts)
        lines.append("")

    body = "\n".join(lines)

    if len(body) > _MAX_RESULT_CHARS:
        body = body[:_MAX_RESULT_CHARS] + "\n\n[... truncated — older relationships omitted]"

    body = _FENCE_CLOSE_RE.sub("", body)

    return (
        '<prior_knowledge source="knowledge_graph" volatile="true">\n'
        f"{body}\n"
        "</prior_knowledge>"
    )


def _parse_props(raw: Any) -> dict[str, Any]:
    """Parse properties from either JSON string or dict."""
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}
