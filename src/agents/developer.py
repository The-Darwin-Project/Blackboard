# BlackBoard/src/agents/developer.py
# @ai-rules:
# 1. [Pattern]: QE is opt-in via QE_SIDECAR_URL. Without it, behavior is pre-probe baseline.
# 2. [Pattern]: asyncio.gather runs dev+qe concurrently. Flash Manager moderates.
# 3. [Pattern]: as_completed processes first finisher immediately (flash_note).
# 4. [Constraint]: Brain is unaware of QE. developer.process() returns merged result.
# 5. [Gotcha]: flash_decide may fail to parse JSON. Fallback: done=True with raw text.
"""
Developer agent with optional concurrent QE pair + Flash Manager moderation.

When QE_SIDECAR_URL is set:
  Phase 1: Fire Dev + QE concurrently (asyncio.gather)
  Phase 2: Flash Manager reviews, triggers fix/verify rounds (max 2)
  Returns merged result to Brain.

When QE_SIDECAR_URL is not set:
  Unchanged thin AgentClient subclass behavior.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Callable, Optional

from .base_client import AgentClient

logger = logging.getLogger(__name__)

FLASH_MODEL = os.getenv("VERTEX_MODEL_FLASH", "gemini-3-flash-preview")
MAX_REVIEW_ROUNDS = 2

MANAGER_SYSTEM = """You are the Huddle Manager moderating a Developer + QE pair.
Review their outputs and decide the next action.

Respond with JSON only:
{
  "done": true/false,
  "dev_action": "none" | "fix" | "review",
  "qe_action": "none" | "verify" | "review",
  "dev_message": "instruction for dev (if action != none)",
  "qe_message": "instruction for qe (if action != none)",
  "summary": "one-line status"
}

Rules:
- If QE found real issues that Dev should address: dev_action="fix"
- If Dev made changes that QE should verify: qe_action="verify"
- If both outputs look good and complementary: done=true
- Keep messages concise and actionable -- they go directly to CLI agents.
- After round 2, force done=true with a merged summary.
- Do NOT wrap JSON in markdown code fences."""


class Developer(AgentClient):
    """Developer agent with optional QE pair and Flash Manager."""

    def __init__(self):
        super().__init__(
            agent_name="developer",
            sidecar_url_env="DEVELOPER_SIDECAR_URL",
            default_url="http://localhost:9093",
            cwd="/data/gitops-developer",
        )
        qe_url = os.getenv("QE_SIDECAR_URL", "")
        self._qe_enabled = bool(qe_url)
        self._flash_client = None
        if self._qe_enabled:
            self.qe = AgentClient(
                agent_name="qe",
                sidecar_url_env="QE_SIDECAR_URL",
                default_url="http://localhost:9094",
                cwd="/data/gitops-qe",
            )
            logger.info("QE pair enabled (concurrent dev + qe + Flash Manager)")

    async def _get_flash_client(self):
        """Lazy-init google-genai client for Flash Manager calls."""
        if self._flash_client is None:
            try:
                from google import genai
                self._flash_client = genai.Client(
                    vertexai=True,
                    project=os.getenv("GCP_PROJECT", ""),
                    location=os.getenv("GCP_LOCATION", "global"),
                )
            except Exception as e:
                logger.warning(f"Flash Manager init failed: {e}")
        return self._flash_client

    async def _flash_decide(
        self, dev_output: str, qe_output: str, round_num: int,
    ) -> dict:
        """Call Gemini Flash to review both outputs and decide next action."""
        client = await self._get_flash_client()
        if not client:
            return {"done": True, "summary": "Flash unavailable", "dev_action": "none", "qe_action": "none"}

        from google.genai import types
        prompt = (
            f"## Review Round {round_num}\n\n"
            f"## Developer Output\n{dev_output[:4000]}\n\n"
            f"## QE Output\n{qe_output[:4000]}"
        )
        try:
            response = await client.aio.models.generate_content(
                model=FLASH_MODEL, contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction=MANAGER_SYSTEM,
                    temperature=0.7,
                    max_output_tokens=65000,
                ),
            )
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()
            return json.loads(text)
        except (json.JSONDecodeError, Exception) as e:
            logger.warning(f"Flash decide parse error: {e}")
            return {"done": True, "summary": "Flash parse error", "dev_action": "none", "qe_action": "none"}

    async def _flash_note(self, agent: str, output: str) -> str:
        """Quick Flash note when first agent finishes."""
        client = await self._get_flash_client()
        if not client:
            return ""
        from google.genai import types
        try:
            response = await client.aio.models.generate_content(
                model=FLASH_MODEL,
                contents=f"The {agent} agent just finished. One-sentence quality assessment:\n\n{output[:2000]}",
                config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=65000),
            )
            return response.text.strip()
        except Exception:
            return ""

    async def process(
        self,
        event_id: str,
        task: str,
        event_md_path: str = "",
        on_progress: Optional[Callable] = None,
    ) -> str:
        """Dev + optional QE pair with Flash Manager moderation."""
        if not self._qe_enabled:
            return await super().process(event_id, task, event_md_path, on_progress)

        # QE progress callback -- override actor so UI renders as QE bubble
        async def qe_on_progress(data: dict) -> None:
            if on_progress:
                data["actor"] = "qe"
                await on_progress(data)

        # Phase 1: Fire Dev + QE concurrently
        dev_task = asyncio.create_task(
            super().process(event_id, task, event_md_path, on_progress)
        )
        qe_task = asyncio.create_task(
            self.qe.process(event_id, task, event_md_path, qe_on_progress)
        )

        dev_result = None
        qe_result = None

        # Collect results as they arrive
        done, pending = await asyncio.wait(
            [dev_task, qe_task], return_when=asyncio.FIRST_COMPLETED,
        )
        for t in done:
            result = t.result() if not t.cancelled() else "Error: cancelled"
            if isinstance(result, Exception):
                result = f"Error: {result}"
            if t is dev_task:
                dev_result = str(result)
                first_agent = "Developer"
            else:
                qe_result = str(result)
                first_agent = "QE"

        # Flash quick note on first finisher
        note = await self._flash_note(first_agent, dev_result or qe_result or "")
        if note and on_progress:
            await on_progress({"actor": "flash", "message": note, "event_id": event_id})
        logger.info(f"Huddle {event_id}: {first_agent} finished first. Flash: {note[:100]}")

        # Wait for second finisher
        for t in pending:
            result = await t
            if isinstance(result, Exception):
                result = f"Error: {result}"
            if t is dev_task:
                dev_result = str(result)
            else:
                qe_result = str(result)

        # Phase 2: Flash Manager review + rounds
        for round_num in range(1, MAX_REVIEW_ROUNDS + 1):
            decision = await self._flash_decide(dev_result, qe_result, round_num)
            summary = decision.get("summary", "")
            dev_act = decision.get("dev_action", "none")
            qe_act = decision.get("qe_action", "none")

            if on_progress:
                await on_progress({"actor": "flash", "message": summary, "event_id": event_id})
            logger.info(f"Huddle {event_id} R{round_num}: {summary} (dev={dev_act}, qe={qe_act})")

            if decision.get("done", False):
                break

            # Follow-up: Dev fix
            if dev_act in ("fix", "review"):
                msg = decision.get("dev_message", "Review QE findings.")
                dev_result = await super().process(
                    event_id,
                    f"Your QE partner has feedback:\n\n{msg}\n\nAddress the issues.",
                    event_md_path,
                    on_progress,
                )

            # Follow-up: QE verify
            if qe_act in ("verify", "review"):
                msg = decision.get("qe_message", "Verify Dev changes.")
                qe_result = await self.qe.process(
                    event_id,
                    f"The Developer has updated their work:\n\n{msg}\n\nVerify and report.",
                    event_md_path,
                    qe_on_progress,
                )

        return (
            f"## Developer Result\n{dev_result}\n\n"
            f"## QE Assessment\n{qe_result}"
        )
