# BlackBoard/src/agents/archivist.py
# @ai-rules:
# 1. [Constraint]: archive_event() is fire-and-forget. MUST NOT block event closure.
# 2. [Pattern]: Summarization via GeminiAdapter (create_adapter, shared QuotaTracker). Embeddings stay on direct genai.Client (separate 5M TPM quota).
# 3. [Gotcha]: embed_content returns 768-dim vector. Qdrant collection must match.
# 4. [Pattern]: All errors caught and logged. Failure falls back to existing append_journal().
# 5. [Pattern]: store_feedback() reuses the same embedding pipeline for user feedback on AI responses.
# 6. [Pattern]: _get_adapter() follows Aligner/Headhunter lazy-load pattern. _ensure_initialized() is for embeddings + Qdrant only.
# 7. [Pattern]: correct_memory() overwrites a contaminated event memory with corrected root_cause/fix_action. Uses same deterministic uuid5 point ID.
# 8. [Pattern]: store_lesson()/search_lessons() operate on darwin_lessons collection. Lessons use uuid4 IDs (no natural unique key).
# 9. [Pattern]: Three Qdrant collections: darwin_events (archived summaries), darwin_feedback (quality tracking), darwin_lessons (human-authored patterns).
# 10. [Pattern]: extract_lessons() uses Claude adapter (not Gemini) for document analysis. Only Claude-compatible kwargs (no thinking_level, no top_p).
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
LESSONS_COLLECTION = "darwin_lessons"
EMBEDDING_MODEL = "text-embedding-005"
ARCHIVIST_MODEL = os.getenv("LLM_MODEL_ARCHIVIST", "gemini-3.1-pro-preview")
EXTRACTOR_MODEL = os.getenv("LLM_MODEL_LESSON_EXTRACTOR", "claude-sonnet-4-20250514")

SUMMARIZE_PROMPT = """Summarize this operational event conversation into a structured JSON object for similarity search.
Each turn is timestamped as [HH:MM:SS actor.action]. Use timestamps to derive durations.

Produce fields in THREE categories:

PATTERN FIELDS (component-neutral -- describe the failure TYPE, not the specific instance):
- symptom: What CLASS of failure was observed (one sentence). Use generic terms like
  "CI pipeline failed", "container build failed", "promotion timed out", "deployment stuck".
  Do NOT include MR numbers, image URLs, registry paths, or component names.
- root_cause: What CATEGORY of issue caused it (one sentence, or "unknown"). Use generic terms like
  "infrastructure image pull failure", "rate limiting on git resolution",
  "compliance check failure (missing license)", "merge conflict".
  Do NOT include specific image URLs, registry paths, or task names.
- fix_action: What CLASS of remediation was applied (one sentence). Use generic terms like
  "retested pipeline after transient failure cleared", "escalated to maintainer for upstream fix".
- pattern_keywords: 3-5 abstract keywords describing the failure pattern.
  Good: ["infrastructure", "image-pull", "pipeline", "transient"]
  Bad: ["quay.io/konflux-ci/oras:latest", "sast-shell-check", "virt-launcher"]

TEMPORAL FIELDS (component-specific -- PRESERVED for operational planning):
- service: The affected service name
- turns: Number of conversation turns
- duration_seconds: Total event duration from first to last turn
- operational_timings: Array of observed process durations (e.g., [{{"source": "Platform Services", "process": "pipeline", "duration_seconds": 1800}}])
- defer_patterns: Array of Brain defer actions, each with reason and duration_seconds
- agent_execution_times: Array of agent tasks, each with agent name and duration_seconds
- procedures: Short workflow description (e.g., "retest pipeline, wait for completion, merge MR")
- outcome: Final state -- one of: resolved, escalated, user_closed, force_closed, stale
- domain: Cynefin classification (clear|complicated|complex|chaotic)

INSTANCE FIELDS (component-specific -- for search findability, not shown to Brain):
- instance_keywords: 2-3 component-specific terms that help find this event via search.
  Example: ["kubevirt-plugin", "konflux", "v5-99"]

Example output:
{{"symptom": "CI pipeline failed due to transient infrastructure issue in build task", "root_cause": "Container image pull failure prevented build task from starting", "fix_action": "Retested pipeline after infrastructure issue resolved, merged MR", "pattern_keywords": ["pipeline", "infrastructure", "image-pull", "transient", "retest"], "instance_keywords": ["kubevirt-plugin", "konflux"], "service": "kubevirt-plugin", "turns": 12, "duration_seconds": 1800, "operational_timings": [{{"source": "Platform Services", "process": "pipeline", "duration_seconds": 1800}}], "defer_patterns": [{{"reason": "Waiting for pipeline", "duration_seconds": 1200}}], "agent_execution_times": [{{"agent": "developer", "duration_seconds": 90}}], "procedures": "retest pipeline, defer for completion, verify result, merge MR", "outcome": "resolved", "domain": "complicated"}}

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
            await self._vector_store.ensure_collection(LESSONS_COLLECTION, vector_size=768)
            self._initialized = True
            logger.info("Archivist initialized (embedding + Qdrant, darwin_events + darwin_feedback + darwin_lessons)")
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

            # Ensure service + turns + duration + domain are in the payload
            summary.setdefault("service", event.service)
            summary.setdefault("turns", len(event.conversation))
            summary.setdefault("duration_seconds", duration)
            from ..models import EventEvidence
            evidence = event.event.evidence
            if isinstance(evidence, EventEvidence):
                summary["brain_domain"] = evidence.brain_domain or evidence.domain
                summary["source_domain"] = evidence.domain
            else:
                summary.setdefault("brain_domain", "complicated")
                summary.setdefault("source_domain", "complicated")

            # Step 2: Generate embedding (pattern keywords dominate, instance keywords secondary)
            embed_text = (
                f"{summary.get('symptom', '')} "
                f"{summary.get('root_cause', '')} "
                f"{summary.get('fix_action', '')} "
                f"{' '.join(summary.get('pattern_keywords', summary.get('keywords', [])))} "
                f"{' '.join(summary.get('instance_keywords', []))} "
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

    # =========================================================================
    # Corrective Memory
    # =========================================================================

    async def correct_memory(
        self,
        event_id: str,
        corrected_root_cause: str,
        corrected_fix_action: str,
        correction_note: str = "",
    ) -> bool:
        """Overwrite a contaminated event memory with corrected fields.

        Re-generates the embedding from corrected fields and upserts with the
        same deterministic point ID, replacing the old vector + payload.
        Returns True on success, False on failure.
        """
        try:
            if not await self._ensure_initialized():
                return False

            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"darwin:{event_id}"))
            existing = await self._vector_store.get_points(COLLECTION_NAME, [point_id])
            if not existing:
                logger.warning(f"correct_memory: event {event_id} not found in Qdrant")
                return False

            payload = existing[0].get("payload", {})
            payload["root_cause"] = corrected_root_cause
            payload["fix_action"] = corrected_fix_action
            payload["corrected"] = True
            payload["correction_note"] = correction_note
            payload["corrected_at"] = time.time()

            embed_text = (
                f"{payload.get('symptom', '')} "
                f"{corrected_root_cause} "
                f"{corrected_fix_action} "
                f"{' '.join(payload.get('pattern_keywords', payload.get('keywords', [])))} "
                f"{' '.join(payload.get('instance_keywords', []))} "
                f"{payload.get('procedures', '')} "
                f"{payload.get('outcome', '')}"
            )
            embed_response = await self._client.aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=embed_text,
            )
            vector = embed_response.embeddings[0].values

            await self._vector_store.upsert(
                collection=COLLECTION_NAME,
                point_id=point_id,
                vector=vector,
                payload=payload,
            )
            logger.info(f"Memory corrected: {event_id} (point={point_id})")
            return True

        except Exception as e:
            logger.warning(f"correct_memory failed for {event_id}: {e}")
            return False

    # =========================================================================
    # Lessons Learned
    # =========================================================================

    async def store_lesson(
        self,
        title: str,
        pattern: str,
        anti_pattern: str = "",
        keywords: list[str] | None = None,
        event_references: list[str] | None = None,
    ) -> str | None:
        """Store a human-authored lesson in darwin_lessons. Returns lesson_id or None."""
        try:
            if not await self._ensure_initialized():
                return None

            lesson_id = str(uuid.uuid4())
            payload = {
                "lesson_id": lesson_id,
                "title": title,
                "pattern": pattern,
                "anti_pattern": anti_pattern,
                "keywords": keywords or [],
                "event_references": event_references or [],
                "created_at": time.time(),
            }
            embed_text = (
                f"{title} {pattern} {anti_pattern} "
                f"{' '.join(keywords or [])}"
            )
            embed_response = await self._client.aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=embed_text,
            )
            vector = embed_response.embeddings[0].values

            await self._vector_store.upsert(
                collection=LESSONS_COLLECTION,
                point_id=lesson_id,
                vector=vector,
                payload=payload,
            )
            logger.info(f"Lesson stored: {lesson_id} ({title})")
            return lesson_id

        except Exception as e:
            logger.warning(f"store_lesson failed: {e}")
            return None

    async def search_lessons(self, query: str, limit: int = 3) -> list[dict]:
        """Search darwin_lessons for relevant patterns. Returns list of {score, payload}."""
        try:
            if not await self._ensure_initialized():
                return []

            embed_response = await self._client.aio.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=query,
            )
            vector = embed_response.embeddings[0].values
            return await self._vector_store.search(
                collection=LESSONS_COLLECTION,
                vector=vector,
                limit=limit,
            )
        except Exception as e:
            logger.warning(f"Lesson search failed (non-fatal): {e}")
            return []

    async def list_memories(self, limit: int = 200) -> list[dict]:
        """List all event memories from Qdrant (single-page scroll, capped)."""
        try:
            if not await self._ensure_initialized():
                return []
            points, _ = await self._vector_store.scroll(COLLECTION_NAME, limit=limit)
            return points
        except Exception as e:
            logger.warning(f"list_memories failed: {e}")
            return []

    async def get_memory(self, event_id: str) -> dict | None:
        """Get a single event memory by event_id."""
        try:
            if not await self._ensure_initialized():
                return None
            point_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"darwin:{event_id}"))
            results = await self._vector_store.get_points(COLLECTION_NAME, [point_id])
            return results[0] if results else None
        except Exception as e:
            logger.warning(f"get_memory failed for {event_id}: {e}")
            return None

    async def list_lessons(self, limit: int = 200) -> list[dict]:
        """List all lessons from Qdrant (single-page scroll, capped)."""
        try:
            if not await self._ensure_initialized():
                return []
            points, _ = await self._vector_store.scroll(LESSONS_COLLECTION, limit=limit)
            return points
        except Exception as e:
            logger.warning(f"list_lessons failed: {e}")
            return []

    async def delete_lesson(self, lesson_id: str) -> bool:
        """Remove a lesson by ID. Returns True on success."""
        try:
            if not await self._ensure_initialized():
                return False
            await self._vector_store.delete(LESSONS_COLLECTION, [lesson_id])
            logger.info(f"Lesson deleted: {lesson_id}")
            return True
        except Exception as e:
            logger.warning(f"delete_lesson failed for {lesson_id}: {e}")
            return False

    # =========================================================================
    # Lesson Extraction (Claude)
    # =========================================================================

    EXTRACTION_PROMPT = (
        "You are analyzing a lessons-learned document from an operational incident review.\n"
        "Extract two types of artifacts:\n\n"
        "1. LESSONS: Abstract, environment-agnostic patterns that teach an AI system how to\n"
        "   classify similar incidents correctly. Describe WHAT the correct reasoning is and\n"
        "   WHAT the anti-pattern looks like. Do NOT reference specific component names,\n"
        "   image URLs, or cluster details in the pattern/anti_pattern fields.\n\n"
        "2. CORRECTIONS: For each referenced event where the AI's classification was wrong,\n"
        "   provide the corrected root_cause and fix_action.\n\n"
        "If the document follows a 'Lessons Learned' template with sections like\n"
        "'Failure Modes', 'Root Cause of the Misclassification', 'Recommendations',\n"
        "and 'Event-Level Corrections', extract from those sections directly.\n\n"
        "Respond with JSON only (no markdown fences):\n"
        '{"lessons": [{"title": "...", "pattern": "...", "anti_pattern": "...", '
        '"keywords": [...], "event_references": [...]}], '
        '"corrections": [{"event_id": "...", "current_root_cause": "...", '
        '"corrected_root_cause": "...", "corrected_fix_action": "...", '
        '"correction_note": "..."}]}'
    )

    MAX_EXTRACTION_CHARS = 50_000

    async def extract_lessons(
        self,
        document: str,
        event_reports: dict[str, str] | None = None,
        context_notes: str = "",
    ) -> dict:
        """Extract structured lessons + corrections from a raw document using Claude.

        Returns {"lessons": [...], "corrections": [...]} or {"error": "..."}.
        """
        if len(document) > self.MAX_EXTRACTION_CHARS:
            return {"error": f"Document exceeds {self.MAX_EXTRACTION_CHARS} character limit"}

        try:
            from .llm import create_adapter

            adapter = create_adapter("claude", self.project, self.location, EXTRACTOR_MODEL)

            contents = f"## Document\n\n{document}"
            if event_reports:
                contents += "\n\n## Darwin Event Reports (for cross-reference)\n"
                for eid, report in event_reports.items():
                    contents += f"\n### {eid}\n{report[:3000]}\n"
            if context_notes:
                contents += f"\n\n## Additional Context\n{context_notes}"

            response = await adapter.generate(
                system_prompt=self.EXTRACTION_PROMPT,
                contents=contents,
                temperature=0.3,
                max_output_tokens=8192,
            )

            raw = response.text.strip()
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                logger.warning("Claude extraction returned invalid JSON, retrying once")
                retry = await adapter.generate(
                    system_prompt=self.EXTRACTION_PROMPT + "\nCRITICAL: respond with valid JSON only.",
                    contents=contents,
                    temperature=0.1,
                    max_output_tokens=8192,
                )
                raw = retry.text.strip()
                if raw.startswith("```"):
                    raw = raw.split("\n", 1)[1].rsplit("```", 1)[0].strip()
                result = json.loads(raw)

            result.setdefault("lessons", [])
            result.setdefault("corrections", [])
            logger.info(
                f"Extraction complete: {len(result['lessons'])} lessons, "
                f"{len(result['corrections'])} corrections"
            )
            return result

        except json.JSONDecodeError as e:
            logger.warning(f"Extraction JSON parse failed after retry: {e}")
            return {"error": f"Claude returned invalid JSON: {e}", "raw_text": raw[:500]}
        except Exception as e:
            logger.warning(f"extract_lessons failed: {e}")
            return {"error": str(e)}
