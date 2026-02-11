# BlackBoard/src/agents/archivist.py
# @ai-rules:
# 1. [Constraint]: archive_event() is fire-and-forget. MUST NOT block event closure.
# 2. [Pattern]: Uses google-genai SDK for both LLM summarization (Flash) and embedding (text-embedding-005).
# 3. [Gotcha]: embed_content returns 768-dim vector. Qdrant collection must match.
# 4. [Pattern]: All errors caught and logged. Failure falls back to existing append_journal().
"""
Archivist: Summarizes closed events into vectorized deep memory.

Triggered by Brain._close_and_broadcast(). Runs async, non-blocking.
Uses Gemini Flash for summarization, text-embedding-005 for vectors,
and Qdrant for storage.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import EventDocument

logger = logging.getLogger(__name__)

COLLECTION_NAME = "darwin_events"
EMBEDDING_MODEL = "text-embedding-005"
FLASH_MODEL = os.getenv("VERTEX_MODEL_FLASH", "gemini-3-flash-preview")

SUMMARIZE_PROMPT = """Summarize this incident conversation into a structured JSON object.
Include these fields:
- symptom: What was observed (one sentence)
- root_cause: What caused it (one sentence, or "unknown")
- fix_action: What was done to fix it (one sentence)
- keywords: Array of 3-5 relevant keywords
- service: The affected service name
- turns: Number of conversation turns
- duration_seconds: How long the event lasted

Respond with JSON only, no markdown fences.

Conversation:
{conversation}"""


class Archivist:
    """Processes closed events into deep memory vectors."""

    def __init__(self):
        self._client = None
        self._vector_store = None
        self._initialized = False
        self.project = os.getenv("GCP_PROJECT", "")
        self.location = os.getenv("GCP_LOCATION", "global")

    async def _ensure_initialized(self) -> bool:
        """Lazy-init google-genai client and vector store."""
        if self._initialized:
            return True
        try:
            from google import genai
            from ..memory.vector_store import VectorStore

            self._client = genai.Client(
                vertexai=True,
                project=self.project,
                location=self.location,
            )
            self._vector_store = VectorStore()
            await self._vector_store.ensure_collection(COLLECTION_NAME, vector_size=768)
            self._initialized = True
            logger.info("Archivist initialized (Flash + embedding + Qdrant)")
            return True
        except Exception as e:
            logger.warning(f"Archivist init failed (non-fatal): {e}")
            return False

    async def archive_event(self, event: EventDocument) -> None:
        """
        Summarize and vectorize a closed event. Fire-and-forget.
        
        Called from Brain._close_and_broadcast(). Must NEVER raise --
        all errors are caught and logged.
        """
        try:
            if not await self._ensure_initialized():
                return

            # Build conversation text for summarization
            conv_lines = []
            for turn in event.conversation:
                line = f"[{turn.actor}.{turn.action}]"
                if turn.thoughts:
                    line += f" {turn.thoughts[:300]}"
                if turn.result:
                    line += f" Result: {turn.result[:300]}"
                conv_lines.append(line)
            conversation_text = "\n".join(conv_lines)

            # Calculate duration
            duration = 0
            if event.conversation:
                first_ts = event.conversation[0].timestamp
                last_ts = event.conversation[-1].timestamp
                duration = int(last_ts - first_ts)

            # Step 1: Summarize with Flash
            from google.genai import types

            prompt = SUMMARIZE_PROMPT.format(conversation=conversation_text[:5000])
            response = await self._client.aio.models.generate_content(
                model=FLASH_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=1024,
                ),
            )

            summary_text = response.text.strip()
            if summary_text.startswith("```"):
                summary_text = summary_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            try:
                summary = json.loads(summary_text)
            except json.JSONDecodeError:
                summary = {
                    "symptom": event.event.reason[:200],
                    "root_cause": "unknown",
                    "fix_action": summary_text[:200],
                    "keywords": [event.service],
                    "service": event.service,
                    "turns": len(event.conversation),
                    "duration_seconds": duration,
                }

            # Ensure service + turns + duration are in the payload
            summary.setdefault("service", event.service)
            summary.setdefault("turns", len(event.conversation))
            summary.setdefault("duration_seconds", duration)

            # Step 2: Generate embedding
            embed_text = (
                f"{summary.get('symptom', '')} "
                f"{summary.get('root_cause', '')} "
                f"{summary.get('fix_action', '')} "
                f"{' '.join(summary.get('keywords', []))}"
            )
            embed_response = await self._client.aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=embed_text,
            )
            vector = embed_response.embeddings[0].values

            # Step 3: Store in Qdrant
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"darwin:{event.id}"))
            summary["event_id"] = event.id
            summary["closed_at"] = time.time()

            await self._vector_store.upsert(
                collection=COLLECTION_NAME,
                point_id=point_id,
                vector=vector,
                payload=summary,
            )

            logger.info(
                f"Archived event {event.id} -> Qdrant "
                f"(service={event.service}, turns={len(event.conversation)})"
            )

        except Exception as e:
            logger.warning(f"Archivist failed for event {event.id} (non-fatal): {e}")

    async def search(self, query: str, limit: int = 5) -> list[dict]:
        """
        Search deep memory for similar past events.
        
        Returns list of {score, payload} dicts.
        """
        try:
            if not await self._ensure_initialized():
                return []

            # Generate query embedding
            embed_response = await self._client.aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=query,
            )
            vector = embed_response.embeddings[0].values

            results = await self._vector_store.search(
                collection=COLLECTION_NAME,
                vector=vector,
                limit=limit,
            )
            return results

        except Exception as e:
            logger.warning(f"Deep memory search failed (non-fatal): {e}")
            return []
