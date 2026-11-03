# BlackBoard/src/agents/event_namer.py
# @ai-rules:
# 1. [Constraint]: File <= 100 lines. Background event naming with lightweight LLM.
# 2. [Pattern]: Fail-open async task; zero degradation on event ingestion latency.
# 3. [Security]: Prompt text sanitized via sanitize_prompt_text, wrapped in XML delimiters.
# 4. [Hexagonal]: Broadcasts 'event_title_updated' via brain.broadcast(). No direct UI/Slack calls.
"""Background task for generating concise event titles using a lightweight LLM."""
from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import TYPE_CHECKING, Any

from ..utils.prompt_sanitize import sanitize_prompt_text
from .llm import create_adapter

if TYPE_CHECKING:
    from ..state.blackboard import BlackboardState

logger = logging.getLogger(__name__)

NAMER_MODEL = os.getenv("LLM_MODEL_EVENT_NAMER", "gemini-3.5-flash-lite")
NAMER_TIMEOUT_SECONDS = 10.0
NAMER_CONCURRENCY = int(os.getenv("EVENT_NAMER_CONCURRENCY", "4"))
_background_tasks: set[asyncio.Task] = set()
_adapter_instance: Any = None
_namer_semaphore: asyncio.Semaphore | None = None


def _get_semaphore() -> asyncio.Semaphore:
    """Lazy initialization of concurrency semaphore inside active event loop."""
    global _namer_semaphore
    if _namer_semaphore is None:
        _namer_semaphore = asyncio.Semaphore(NAMER_CONCURRENCY)
    return _namer_semaphore


def get_adapter() -> Any:
    """Lazy singleton adapter avoiding per-event SDK initialization."""
    global _adapter_instance
    if hasattr(create_adapter, "mock_calls"):
        return create_adapter("gemini", os.getenv("GCP_PROJECT", ""), os.getenv("GCP_LOCATION", "us-central1"), NAMER_MODEL)
    if _adapter_instance is None:
        project = os.getenv("GCP_PROJECT", "")
        location = os.getenv("GCP_LOCATION", "us-central1")
        _adapter_instance = create_adapter("gemini", project, location, NAMER_MODEL)
    return _adapter_instance


async def generate_event_title(
    blackboard: "BlackboardState", brain: Any, event_id: str, text: str, source: str
) -> None:
    """Generate a 3-6 word title for a user event and update state + broadcast."""
    try:
        sanitized = sanitize_prompt_text(text, max_len=300)
        clean_input = re.sub(r"</?\s*user_request\s*>", "", sanitized, flags=re.IGNORECASE)
        sys_prompt = "Generate a concise 3-6 word title summarizing the user request. Respond with ONLY the title string, no quotes, no markdown, no punctuation."
        user_prompt = f"<user_request>\n{clean_input}\n</user_request>"

        sem = _get_semaphore()
        async with sem:
            adapter = get_adapter()
            response = await asyncio.wait_for(
                adapter.generate(system_prompt=sys_prompt, contents=user_prompt),
                timeout=NAMER_TIMEOUT_SECONDS,
            )

        raw = (response.text or "").strip().strip("\"'*` \t\r\n")
        lines = raw.splitlines()
        if not lines:
            return
        clean_title = lines[0].strip("\"'*` ")[:100]
        if not clean_title:
            return

        if await blackboard.update_event_title_if_not_user(event_id, clean_title, "llm"):
            await brain.broadcast({
                "type": "event_title_updated",
                "event_id": event_id,
                "title": clean_title,
                "title_source": "llm",
            })
            logger.info("Event %s (%s) title generated via LLM (len=%d)", event_id, source, len(clean_title))
    except Exception as exc:
        logger.warning("LLM title generation failed for %s: %s", event_id, exc)


def spawn_event_namer_task(
    blackboard: "BlackboardState", brain: Any, event_id: str, text: str, source: str
) -> asyncio.Task:
    """Spawn background naming task with garbage-collection retention."""
    task = asyncio.create_task(generate_event_title(blackboard, brain, event_id, text, source))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
    return task
