# BlackBoard/src/agents/developer.py
# @ai-rules:
# 1. [Pattern]: QE is opt-in via QE_SIDECAR_URL. Without it, behavior is pre-probe baseline.
# 2. [Pattern]: asyncio.wait(FIRST_COMPLETED) runs dev+qe concurrently. Flash Manager moderates.
# 3. [Pattern]: as_completed processes first finisher immediately (flash_note).
# 4. [Constraint]: Brain is unaware of QE. developer.process() returns merged result.
# 5. [Gotcha]: flash_decide may fail to parse JSON. Fallback: done=True with raw text.
# 6. [Pattern]: CancelledError propagation: cancels both dev_task + qe_task to prevent orphaned CLI processes.
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
        self._dev_sessions: dict[str, str] = {}   # event_id -> dev CLI session_id
        self._qe_sessions: dict[str, str] = {}    # event_id -> qe CLI session_id
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
        mode: str = "implement",
    ) -> tuple[str, Optional[str]]:
        """Dev team dispatch with mode-based routing.

        - implement (default): Full Huddle -- Dev + QE + Flash Manager
        - investigate: Dev solo -- no QE, no Flash Manager
        - test: QE solo -- no Dev, no Flash Manager
        """
        # investigate -> Dev sidecar only, no QE
        if mode == "investigate" or not self._qe_enabled:
            return await super().process(event_id, task, event_md_path, on_progress, mode)

        # test -> QE sidecar only, no Dev
        if mode == "test":
            return await self.qe.process(event_id, task, event_md_path, on_progress, mode)

        # implement (default) -> full Huddle: Dev + QE + Flash Manager

        # QE progress callback -- override actor so UI renders as QE bubble
        async def qe_on_progress(data: dict) -> None:
            if on_progress:
                data["actor"] = "qe"
                await on_progress(data)

        # Phase 1: Fire Dev + QE concurrently
        dev_task = asyncio.create_task(
            super().process(event_id, task, event_md_path, on_progress, mode)
        )
        qe_task = asyncio.create_task(
            self.qe.process(event_id, task, event_md_path, qe_on_progress, mode)
        )

        dev_result = None
        dev_session_id: Optional[str] = None
        qe_result = None

        try:
            # Collect results as they arrive
            done, pending = await asyncio.wait(
                [dev_task, qe_task], return_when=asyncio.FIRST_COMPLETED,
            )
            for t in done:
                raw = t.result() if not t.cancelled() else ("Error: cancelled", None)
                if isinstance(raw, Exception):
                    raw = (f"Error: {raw}", None)
                result_text, sid = raw if isinstance(raw, tuple) else (str(raw), None)
                if t is dev_task:
                    dev_result = str(result_text)
                    dev_session_id = sid
                    first_agent = "Developer"
                else:
                    qe_result = str(result_text)
                    if sid:
                        self._qe_sessions[event_id] = sid
                    first_agent = "QE"

            # Flash quick note on first finisher
            note = await self._flash_note(first_agent, dev_result or qe_result or "")
            if note and on_progress:
                await on_progress({"actor": "flash", "message": note, "event_id": event_id})
            logger.info(f"Huddle {event_id}: {first_agent} finished first. Flash: {note[:100]}")

            # Wait for second finisher
            for t in pending:
                raw = await t
                if isinstance(raw, Exception):
                    raw = (f"Error: {raw}", None)
                result_text, sid = raw if isinstance(raw, tuple) else (str(raw), None)
                if t is dev_task:
                    dev_result = str(result_text)
                    dev_session_id = sid
                else:
                    qe_result = str(result_text)
                    if sid:
                        self._qe_sessions[event_id] = sid

            # Track dev session
            if dev_session_id:
                self._dev_sessions[event_id] = dev_session_id

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
                    dev_result, dev_session_id = await super().process(
                        event_id,
                        f"Your QE partner has feedback:\n\n{msg}\n\nAddress the issues.",
                        event_md_path,
                        on_progress,
                    )
                    if dev_session_id:
                        self._dev_sessions[event_id] = dev_session_id

                # Follow-up: QE verify
                if qe_act in ("verify", "review"):
                    msg = decision.get("qe_message", "Verify Dev changes.")
                    qe_result, qe_sid = await self.qe.process(
                        event_id,
                        f"The Developer has updated their work:\n\n{msg}\n\nVerify and report.",
                        event_md_path,
                        qe_on_progress,
                    )
                    if qe_sid:
                        self._qe_sessions[event_id] = qe_sid

        except asyncio.CancelledError:
            # Cancel BOTH sub-tasks to prevent orphaned CLI processes
            dev_task.cancel()
            qe_task.cancel()
            # Wait briefly for cleanup to propagate (WS close -> SIGTERM)
            await asyncio.gather(dev_task, qe_task, return_exceptions=True)
            logger.info(f"Huddle cancelled for {event_id}: dev+qe tasks killed")
            raise  # Re-raise so Brain sees the cancellation

        merged = (
            f"## Developer Result\n{dev_result}\n\n"
            f"## QE Assessment\n{qe_result}"
        )
        return merged, dev_session_id

    async def followup(
        self,
        event_id: str,
        session_id: str,
        message: str,
        on_progress: Optional[Callable] = None,
    ) -> str:
        """Follow-up with Flash Manager routing for Huddle sessions.

        When QE is enabled, Flash Manager decides whether the follow-up goes to
        Dev, QE, or both. Brain calls this uniformly -- Huddle complexity stays encapsulated.
        """
        if not self._qe_enabled:
            return await super().followup(event_id, session_id, message, on_progress)

        # Flash Manager decides routing to Dev, QE, or both
        decision = await self._flash_decide(
            f"User says: {message}", "Huddle active (dev+qe working)", round_num=0)
        results = []
        if decision.get("dev_action", "none") != "none":
            results.append(await super().followup(event_id, session_id, message, on_progress))
        if decision.get("qe_action", "none") != "none":
            qe_sid = self._qe_sessions.get(event_id, "")
            results.append(await self.qe.followup(event_id, qe_sid, message))
        return "\n".join(results) if results else decision.get("summary", "No action")
