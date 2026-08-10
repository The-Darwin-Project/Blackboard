# BlackBoard/src/agents/entity_extractor.py
# @ai-rules:
# 1. [Constraint]: Uses gemini-3.5-flash-lite with responseSchema (not prompt-based JSON).
# 2. [Pattern]: Fail-open. Returns empty KnowledgeGraphEntities on any error.
# 3. [Constraint]: Entity types limited to Service, Event, Fix (narrow scope for Phase 1).
# 4. [Gotcha]: Must handle events with no clear service (source=chat/slack) gracefully.
# 5. [Pattern]: Natural keys for MERGE: Service.name, Event.event_id, Fix derived from event_id+type.
# 6. [Pattern]: 30s timeout. Returns empty on timeout -- never blocks archive.
"""
Entity extraction for the Knowledge Graph.

Extracts Service, Event, and Fix entities from archived event summaries
using Flash Lite with native structured output (responseSchema).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

KG_EXTRACTOR_MODEL = os.getenv("LLM_MODEL_KG_EXTRACTOR", "gemini-3.5-flash-lite")
KG_EXTRACTOR_TIMEOUT = float(os.getenv("KG_EXTRACTOR_TIMEOUT", "30"))


class Entity(BaseModel):
    type: str = Field(description="Entity type: Service, Event, or Fix")
    id: str = Field(description="Composite key: service:{name}, event:{evt-id}, fix:{evt-id}:{type}")
    properties: dict[str, Any] = Field(default_factory=dict)


class Relationship(BaseModel):
    from_type: str
    from_id: str
    rel_type: str
    to_type: str
    to_id: str


class KnowledgeGraphEntities(BaseModel):
    entities: list[Entity] = Field(default_factory=list)
    relationships: list[Relationship] = Field(default_factory=list)


_RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "entities": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "type": {"type": "STRING", "enum": ["Service", "Event", "Fix"]},
                    "id": {"type": "STRING"},
                    "properties": {
                        "type": "OBJECT",
                        "properties": {
                            "name": {"type": "STRING"},
                            "namespace": {"type": "STRING"},
                            "summary": {"type": "STRING"},
                            "domain": {"type": "STRING"},
                            "outcome": {"type": "STRING"},
                            "description": {"type": "STRING"},
                            "fix_type": {"type": "STRING"},
                            "effective": {"type": "BOOLEAN"},
                        },
                    },
                },
                "required": ["type", "id"],
            },
        },
        "relationships": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "from_type": {"type": "STRING"},
                    "from_id": {"type": "STRING"},
                    "rel_type": {"type": "STRING"},
                    "to_type": {"type": "STRING"},
                    "to_id": {"type": "STRING"},
                },
                "required": ["from_type", "from_id", "rel_type", "to_type", "to_id"],
            },
        },
    },
    "required": ["entities", "relationships"],
}

_EXTRACTION_PROMPT = (
    "Extract entities and relationships from this archived event summary.\n\n"
    "Entity types (use composite keys):\n"
    "- Service: id = 'service:{name}' (e.g., 'service:kubevirt-plugin')\n"
    "- Event: id = 'event:{event_id}' (e.g., 'event:evt-a1b2c3d4')\n"
    "- Fix: id = 'fix:{event_id}:{type}' where type is gitops|code|config|manual\n\n"
    "Relationship types:\n"
    "- AFFECTED: Event -> Service\n"
    "- APPLIED_TO: Fix -> Service\n"
    "- RESOLVED_BY: Event -> Fix\n\n"
    "Be precise with service names -- use the exact canonical name.\n"
    "If no service is identifiable, omit the Service entity."
)

_client = None


def _get_client():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(
            vertexai=True,
            project=os.getenv("GCP_PROJECT", ""),
            location=os.getenv("GCP_LOCATION", "global"),
        )
    return _client


async def extract_entities(
    event_summary: dict[str, Any],
    service: str | None = None,
) -> KnowledgeGraphEntities:
    """Extract entities from an event summary using Flash Lite.

    Returns empty KnowledgeGraphEntities on any failure (fail-open).
    """
    empty = KnowledgeGraphEntities()
    try:
        summary_text = (
            f"Event: {event_summary.get('event_id', 'unknown')}\n"
            f"Service: {service or event_summary.get('service', 'unknown')}\n"
            f"Symptom: {event_summary.get('symptom', 'unknown')}\n"
            f"Root Cause: {event_summary.get('root_cause', 'unknown')}\n"
            f"Fix Action: {event_summary.get('fix_action', 'unknown')}\n"
            f"Domain: {event_summary.get('domain', 'unknown')}\n"
            f"Outcome: {event_summary.get('outcome', 'unknown')}\n"
            f"Procedures: {event_summary.get('procedures', 'unknown')}\n"
        )

        client = _get_client()
        from google.genai import types

        response = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=KG_EXTRACTOR_MODEL,
                contents=f"{_EXTRACTION_PROMPT}\n\n---\n{summary_text}",
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    response_mime_type="application/json",
                    response_schema=_RESPONSE_SCHEMA,
                ),
            ),
            timeout=KG_EXTRACTOR_TIMEOUT,
        )

        result = json.loads(response.text)

        entities = [Entity(**e) for e in result.get("entities", [])]
        relationships = [Relationship(**r) for r in result.get("relationships", [])]

        return KnowledgeGraphEntities(entities=entities, relationships=relationships)

    except asyncio.TimeoutError:
        logger.warning(
            "Entity extraction timed out after %ss for %s",
            KG_EXTRACTOR_TIMEOUT,
            event_summary.get("event_id", "unknown"),
        )
        return empty
    except Exception as e:
        logger.warning(
            "Entity extraction failed for %s (non-fatal): %s",
            event_summary.get("event_id", "unknown"), e,
        )
        return empty
