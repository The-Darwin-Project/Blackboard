# BlackBoard/src/agents/archivist.py
# @ai-rules:
# 1. [Constraint]: archive_event() is fire-and-forget. MUST NOT block event closure.
# 2. [Pattern]: Summarization via GeminiAdapter (create_adapter, shared QuotaTracker). Embeddings stay on direct genai.Client (separate 5M TPM quota).
# 3. [Gotcha]: embed_content returns 768-dim vector. Qdrant collection must match.
# 4. [Pattern]: All errors caught and logged. Failure falls back to existing append_journal().
# 5. [Pattern]: store_feedback() reuses the same embedding pipeline for user feedback on AI responses.
# 6. [Pattern]: _get_adapter() follows Aligner/Headhunter lazy-load pattern. _ensure_initialized() is for embeddings + Qdrant only.
"""
Archivist: Summarizes closed events into vectorized deep memory.

Triggered by Brain._close_and_broadcast(). Runs async, non-blocking.
Uses Gemini (LLM_MODEL_ARCHIVIST) for summarization, text-embedding-005 for vectors,
and Qdrant for storage.
"""
from __future__ import annotations

import json
import logging
import os
import time
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..models import EventDocument

logger = logging.getLogger(__name__)

COLLECTION_NAME = "darwin_events"
FEEDBACK_COLLECTION = "darwin_feedback"
EMBEDDING_MODEL = "text-embedding-005"
ARCHIVIST_MODEL = os.getenv("LLM_MODEL_ARCHIVIST", "gemini-3.1-pro-preview")

SUMMARIZE_PROMPT = """Summarize this operational event conversation into a structured JSON object, this will be used to create a vector for similarity search.
Each turn is timestamped as [HH:MM:SS actor.action]. Use timestamps to derive durations.

Include these fields:
- symptom: What was observed (one sentence)
- root_cause: What caused it (one sentence, or "unknown")
- fix_action: What was done to fix it (one sentence)
- keywords: Array of 3-5 relevant keywords
- service: The affected service name
- turns: Number of conversation turns
- duration_seconds: Total event duration from first to last turn
- operational_timings: Array of observed process durations (e.g., [{"source": "Platform Services", "process": "pipeline", "duration_seconds": 1800}])
- defer_patterns: Array of Brain defer actions, each with reason and duration_seconds
- agent_execution_times: Array of agent tasks, each with agent name and duration_seconds (route to execute)
- procedures: Short workflow description (e.g., "retest pipeline, wait for completion, merge MR")
- outcome: Final state -- one of: resolved, escalated, user_closed, force_closed, stale

Example output:
{{"symptom": "pipeline failed for MR !289", "root_cause": "Transient Platform Services infrastructure issue", "fix_action": "Retested pipeline, merged MR after pass", "keywords": ["Platform Services", "pipeline", "kubevirt-plugin", "retest"], "service": "kubevirt-plugin", "turns": 12, "duration_seconds": 1800, "operational_timings": [{{"source": "Platform Services", "process": "pipeline", "duration_seconds": 1800}}], "defer_patterns": [{{"reason": "Waiting for pipeline", "duration_seconds": 1200}}], "agent_execution_times": [{{"agent": "developer", "duration_seconds": 90}}], "procedures": "retest pipeline, defer for completion, verify result, merge MR", "outcome": "resolved"}}

Respond with JSON only, no markdown fences."""


class Archivist:
    """Processes closed events into deep memory vectors."""

    def __init__(self):
        self._client = None
        self._adapter = None
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
            await self._vector_store.ensure_collection(FEEDBACK_COLLECTION, vector_size=768)
            self._initialized = True
            logger.info("Archivist initialized (embedding + Qdrant, darwin_events + darwin_feedback)")
            return True
        except Exception as e:
            logger.warning(f"Archivist init failed (non-fatal): {e}")
            return False

    async def _get_adapter(self):
        """Lazy-load LLM adapter for summarization (Gemini, ARCHIVIST model)."""
        if self._adapter is None:
            try:
                from .llm import create_adapter

                self._adapter = create_adapter("gemini", self.project, self.location, ARCHIVIST_MODEL)
                logger.info(f"Archivist LLM adapter initialized: gemini/{ARCHIVIST_MODEL}")
            except Exception as e:
                logger.warning(f"LLM adapter not available for Archivist: {e}")
                self._adapter = None
        return self._adapter

    async def archive_event(self, event: EventDocument) -> None:
        """
        Summarize and vectorize a closed event. Fire-and-forget.
        
        Called from Brain._close_and_broadcast(). Must NEVER raise --
        all errors are caught and logged.
        """
        try:
            if not await self._ensure_initialized():
                return

            conv_lines = []
            for turn in event.conversation:
                ts = datetime.fromtimestamp(turn.timestamp).strftime("%H:%M:%S")
                line = f"[{ts} {turn.actor}.{turn.action}]"
                if turn.thoughts:
                    line += f" {turn.thoughts}"
                if turn.result:
                    line += f" Result: {turn.result}"
                conv_lines.append(line)
            conversation_text = "\n".join(conv_lines)

            # Calculate duration
            duration = 0
            if event.conversation:
                first_ts = event.conversation[0].timestamp
                last_ts = event.conversation[-1].timestamp
                duration = int(last_ts - first_ts)

            # Step 1: Summarize with LLM adapter (shared QuotaTracker)
            adapter = await self._get_adapter()
            if not adapter:
                logger.warning(f"Archivist LLM unavailable, skipping summarization for {event.id}")
                return

            response = await adapter.generate(
                system_prompt=SUMMARIZE_PROMPT,
                contents=conversation_text,
                temperature=float(os.getenv("LLM_TEMPERATURE_ARCHIVIST", "0.3")),
                max_output_tokens=int(os.getenv("LLM_MAX_TOKENS_ARCHIVIST", "4096")),
                thinking_level=os.getenv("LLM_THINKING_ARCHIVIST", "high"),
            )

            summary_text = response.text.strip()
            if summary_text.startswith("```"):
                summary_text = summary_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            try:
                summary = json.loads(summary_text)
            except json.JSONDecodeError:
                summary = {
                    "symptom": event.event.reason,
                    "root_cause": "unknown",
                    "fix_action": summary_text,
                    "keywords": [event.service],
                    "service": event.service,
                    "turns": len(event.conversation),
                    "duration_seconds": duration,
                    "operational_timings": [],
                    "defer_patterns": [],
                    "agent_execution_times": [],
                    "procedures": "unknown",
                    "outcome": "unknown",
                }

            # Ensure service + turns + duration are in the payload
            summary.setdefault("service", event.service)
            summary.setdefault("turns", len(event.conversation))
            summary.setdefault("duration_seconds", duration)

            # Step 2: Generate embedding
            timings = summary.get("operational_timings", [])
            embed_text = (
                f"{summary.get('symptom', '')} "
                f"{summary.get('root_cause', '')} "
                f"{summary.get('fix_action', '')} "
                f"{' '.join(summary.get('keywords', []))} "
                f"{' '.join(str(t) for t in timings) if isinstance(timings, list) else ''} "
                f"{summary.get('procedures', '')} "
                f"{summary.get('outcome', '')}"
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

    async def store_feedback(
        self,
        event_id: str,
        turn_number: int,
        rating: str,
        turn_text: str,
        comment: str = "",
    ) -> bool:
        """Store user feedback on an AI response to Qdrant for quality tracking.

        Returns True on success, False on failure (non-fatal).
        """
        try:
            if not await self._ensure_initialized():
                return False

            embed_response = await self._client.aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=turn_text[:500],
            )
            vector = embed_response.embeddings[0].values
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"feedback:{event_id}:{turn_number}"))
            payload = {
                "event_id": event_id,
                "turn_number": turn_number,
                "rating": rating,
                "comment": comment,
                "turn_text": turn_text[:500],
                "timestamp": time.time(),
            }
            await self._vector_store.upsert(
                collection=FEEDBACK_COLLECTION,
                point_id=point_id,
                vector=vector,
                payload=payload,
            )
            logger.info(f"Feedback stored: event={event_id} turn={turn_number} rating={rating}")
            return True
        except Exception as e:
            logger.warning(f"Feedback storage failed (non-fatal): {e}")
            return False
