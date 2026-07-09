# BlackBoard/src/agents/brain_reflex.py
# @ai-rules:
# 1. [Constraint]: Non-blocking. All searches via asyncio.create_task. Never await in feed().
# 2. [Pattern]: Dedup by title (lessons) or topic:scope composite key (knowledge facts). Same hit from different windows fires once.
# 3. [Gotcha]: gather() timeout must be generous enough for late searches but not block the LLM loop.
# 4. [Constraint]: max_searches cap prevents flooding the embedding API during verbose thinking.
# 5. [Pattern]: All errors caught and logged as warnings. Failure = empty results, never crash.
# 6. [Pattern]: Searches both lessons AND knowledge facts in parallel. Pre-embeds query once via embed_query(), shares vector. hasattr guards for test/mock safety.
# 7. [Constraint]: Stale knowledge facts (hit.get("stale")) filtered before dedup key registration.

"""Memory Reflex: real-time lesson search during FRIDAY's thinking stream.

SentenceChunker detects 2-sentence boundaries in streaming tokens.
ReflexSearcher fires async embedding searches and gathers results with timeout.
"""

from __future__ import annotations

import asyncio
import logging
import re

logger = logging.getLogger(__name__)

_BOUNDARY_RE = re.compile(r"[.!?] [A-Z]|\n[^\s]")


class SentenceChunker:
    """Accumulates thinking tokens and emits 2-sentence windows on boundary detection."""

    def __init__(self, min_length: int = 40):
        self._min_length = min_length
        self._buffer: str = ""
        self._sentences: list[str] = []

    def feed(self, token: str) -> str | None:
        """Accept a thinking token. Returns a 2-sentence window on boundary, else None."""
        self._buffer += token

        if len(self._buffer) < self._min_length:
            return None

        match = _BOUNDARY_RE.search(self._buffer)
        if not match:
            return None

        boundary_pos = match.start() + 1
        sentence = self._buffer[:boundary_pos].strip()
        self._buffer = self._buffer[boundary_pos:]

        if sentence:
            self._sentences.append(sentence)

        if len(self._sentences) >= 2:
            window = " ".join(self._sentences[-2:])
            return window

        return None

    def reset(self) -> None:
        """Clear state for reuse."""
        self._buffer = ""
        self._sentences = []

    def flush(self) -> str | None:
        """Flush remaining buffer as final sentence. Call after stream ends."""
        remaining = self._buffer.strip()
        if remaining and len(remaining) >= self._min_length:
            self._sentences.append(remaining)
            self._buffer = ""
            if len(self._sentences) >= 2:
                return " ".join(self._sentences[-2:])
            return remaining
        return None


class ReflexSearcher:
    """Fires async lesson searches and gathers deduplicated results."""

    def __init__(
        self,
        archivist,
        event_id: str,
        score_threshold: float = 0.60,
        max_searches: int = 5,
    ):
        self._archivist = archivist
        self._event_id = event_id
        self._score_threshold = score_threshold
        self._max_searches = max_searches
        self._search_count: int = 0
        self._pending_tasks: list[asyncio.Task] = []
        self._seen_keys: set[str] = set()
        self.matched_lessons: list[dict] = []

    def fire(self, query: str) -> None:
        """Create async search task. No-op if cap reached."""
        if self._search_count >= self._max_searches:
            return
        self._search_count += 1
        task = asyncio.create_task(self._search(query))
        self._pending_tasks.append(task)

    async def _search(self, query: str) -> list[dict]:
        """Execute lesson + knowledge search against the archivist."""
        try:
            vector = None
            if hasattr(self._archivist, "embed_query"):
                try:
                    vector = await self._archivist.embed_query(query)
                except Exception as embed_err:
                    logger.warning(f"Reflex embed_query failed for {self._event_id}, searching without shared vector: {embed_err}")

            tasks = [self._archivist.search_lessons(query, limit=2, vector=vector)]
            if hasattr(self._archivist, "search_knowledge"):
                tasks.append(self._archivist.search_knowledge(query, limit=2, vector=vector))

            results_list = await asyncio.gather(*tasks, return_exceptions=True)

            merged = []
            for result in results_list:
                if isinstance(result, list):
                    merged.extend(result)
                elif isinstance(result, Exception):
                    logger.warning(f"Reflex sub-search failed for {self._event_id}: {result}")
            return merged
        except Exception as e:
            logger.warning(f"Reflex search failed for {self._event_id}: {e}")
            return []

    async def gather(self, timeout: float = 0.5) -> list[dict]:
        """Await pending tasks with timeout, return deduplicated lessons above threshold."""
        if not self._pending_tasks:
            return []

        try:
            done, pending = await asyncio.wait(
                self._pending_tasks, timeout=timeout
            )
            if pending:
                logger.info(
                    f"Reflex gather: {len(pending)} searches timed out for {self._event_id}"
                )
                for task in pending:
                    task.cancel()
        except Exception as e:
            logger.warning(f"Reflex gather error for {self._event_id}: {e}")
            return []

        for task in done:
            try:
                results = task.result()
                for hit in results:
                    score = hit.get("score", 0)
                    if score < self._score_threshold:
                        continue
                    if hit.get("stale"):
                        continue
                    payload = hit.get("payload", {})
                    key = payload.get("title") or f"{payload.get('topic', '')}:{payload.get('scope', '')}"
                    if not key or key == ":" or key in self._seen_keys:
                        continue
                    self._seen_keys.add(key)
                    self.matched_lessons.append(hit)
            except Exception as e:
                logger.warning(f"Reflex task result error: {e}")

        self._pending_tasks = []
        return self.matched_lessons
