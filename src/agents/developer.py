# BlackBoard/src/agents/developer.py
# @ai-rules:
# 1. [Pattern]: In reverse-WS mode, Brain dispatches developer directly via dispatch_to_agent. process() is legacy-only.
# 2. [Constraint]: Brain IS aware of QE (first-class agent since Manager collapse). Brain coordinates dev/QE sequentially.
# 3. [Gotcha]: process() is DEPRECATED -- only used in non-reverse-WS legacy mode. Flash Manager LLM removed.
# 4. [Pattern]: CancelledError propagation: cancels both dev_task + qe_task to prevent orphaned CLI processes.
# 5. [Pattern]: session_id forwarded: Phase 1 passes Brain's session to dev; Phase 2 + followup() prefer internal sessions.
"""
Developer agent -- thin AgentClient subclass.

DEPRECATED: process() and _flash_decide() are legacy-only (non-reverse-WS mode).
In reverse-WS mode, Brain dispatches developer directly via dispatch_to_agent.
QE is a separate first-class agent dispatched independently by Brain.
"""
from __future__ import annotations

import asyncio
import logging
import os
from typing import Callable, Optional

from .base_client import AgentClient

logger = logging.getLogger(__name__)

MAX_REVIEW_ROUNDS = 2


class Developer(AgentClient):
    """Developer agent. In reverse-WS mode, Brain dispatches directly -- process() is legacy."""

    def __init__(self):
        super().__init__(
            agent_name="developer",
            sidecar_url_env="DEVELOPER_SIDECAR_URL",
            default_url="http://localhost:9093",
            cwd="/data/gitops-developer",
        )
        qe_url = os.getenv("QE_SIDECAR_URL", "")
        self._qe_enabled = bool(qe_url)
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

    def cleanup_event(self, event_id: str) -> None:
        """Clean up per-event state including internal dev/qe session maps."""
        super().cleanup_event(event_id)
        self._dev_sessions.pop(event_id, None)
        self._qe_sessions.pop(event_id, None)

    async def process(
        self,
        event_id: str,
        task: str,
        event_md_path: str = "",
        on_progress: Optional[Callable] = None,
        mode: str = "investigate",
        session_id: Optional[str] = None,
    ) -> tuple[str, Optional[str]]:
        """Dev team dispatch with mode-based routing.

        - implement: Full Huddle -- Dev + QE + Flash Manager
        - execute: Dev solo -- single write actions (post comment, merge MR, tag release)
        - investigate (default): Dev solo -- read-only checks, status reports
        - test: QE solo -- write/run tests independently
        """
        # investigate/execute -> Dev sidecar only, no QE
        if mode in ("investigate", "execute") or not self._qe_enabled:
            return await super().process(event_id, task, event_md_path, on_progress, mode, session_id=session_id)

        # test -> QE sidecar only, no Dev
        if mode == "test":
            return await self.qe.process(event_id, task, event_md_path, on_progress, mode, session_id=session_id)

        # implement (default) -> full Huddle: Dev + QE + Flash Manager

        # QE progress callback -- override actor so UI renders as QE bubble
        async def qe_on_progress(data: dict) -> None:
            if on_progress:
                data["actor"] = "qe"
                await on_progress(data)

        # Phase 1: Fire Dev + QE concurrently
        dev_task = asyncio.create_task(
            super().process(event_id, task, event_md_path, on_progress, mode, session_id=session_id)
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
            note = ""  # Flash Manager removed (deprecated)
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
                decision = {"done": True, "summary": "Flash Manager removed", "dev_action": "none", "qe_action": "none"}
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
                        mode="implement",
                        session_id=dev_session_id,
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
                        mode="implement",
                        session_id=self._qe_sessions.get(event_id),
                    )
                    if qe_sid:
                        self._qe_sessions[event_id] = qe_sid

        except asyncio.CancelledError:
            # Cancel BOTH sub-tasks to prevent orphaned CLI processes
            dev_task.cancel()
            qe_task.cancel()
            await asyncio.gather(dev_task, qe_task, return_exceptions=True)
            logger.info(f"Huddle cancelled for {event_id}: dev+qe tasks killed")
            raise

        # Phase 3: Manager approved -- Dev opens PR and merges if pipeline passes
        if on_progress:
            await on_progress({"actor": "flash", "message": "Manager approved. Developer opening PR.", "event_id": event_id})
        logger.info(f"Huddle {event_id}: Manager approved, sending Dev to open PR + merge")

        pr_result, dev_session_id = await super().process(
            event_id,
            (
                "Manager approved the implementation and QE tests. "
                "Open a Pull Request with your feature branch (code + QE tests are on the branch). "
                "Wait for the pipeline to run. If it passes, merge the PR. "
                "If it fails, fix the issue, push again, and retry. "
                "Report the final PR URL and merge status."
            ),
            event_md_path,
            on_progress,
            mode="execute",
            session_id=dev_session_id,
        )
        if dev_session_id:
            self._dev_sessions[event_id] = dev_session_id

        merged = (
            f"## Developer Result\n{dev_result}\n\n"
            f"## QE Assessment\n{qe_result}\n\n"
            f"## PR & Merge\n{pr_result}"
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
            dev_sid = self._dev_sessions.get(event_id, session_id)
            return await super().followup(event_id, dev_sid, message, on_progress)

        # Flash Manager decides routing to Dev, QE, or both
        decision = {"done": True, "summary": "Flash Manager removed", "dev_action": "none", "qe_action": "none"}
        results = []
        if decision.get("dev_action", "none") != "none":
            dev_sid = self._dev_sessions.get(event_id, session_id)
            results.append(await super().followup(event_id, dev_sid, message, on_progress))
        if decision.get("qe_action", "none") != "none":
            qe_sid = self._qe_sessions.get(event_id, "")
            results.append(await self.qe.followup(event_id, qe_sid, message))
        return "\n".join(results) if results else decision.get("summary", "No action")
