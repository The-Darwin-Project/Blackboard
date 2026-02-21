# BlackBoard/src/agents/dev_team.py
# @ai-rules:
# 1. [Pattern]: Manager (Flash LLM) is the team entry point. Brain dispatches to DevTeam, Manager decides work split.
# 2. [Pattern]: Manager uses function calling (MANAGER_TOOL_SCHEMAS). No raw JSON parsing, no mode routing if/else.
# 3. [Pattern]: CancelledError propagation: cancel all active dispatch asyncio.Tasks on cancel.
# 4. [Pattern]: on_progress with actor="manager" for all Manager decisions. Dev/QE progress uses their own actor names.
# 5. [Constraint]: Max 2 fix rounds, then force approve. Prevents infinite loops.
# 6. [Pattern]: Session affinity via agent_id -- follow-up rounds route to the same agent that did the original work.
"""
Dev Team -- Manager (Flash LLM) coordinates developer + QE agents.

Brain dispatches to DevTeam.process(). The Manager LLM triages the task,
dispatches to developer/QE via function calling, reviews outputs, and
reports the merged result back to Brain.
"""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path
from typing import Callable, Optional

from .dispatch import dispatch_to_agent
from .llm import create_adapter, MANAGER_TOOL_SCHEMAS, LLMPort

logger = logging.getLogger(__name__)

MAX_FIX_ROUNDS = 2
MAX_CONVERSATION_ROUNDS = 10

__all__ = ["DevTeam"]


class DevTeam:
    """Dev Team -- Manager (Flash LLM) coordinates developer + QE agents."""

    def __init__(self):
        self._adapter: LLMPort | None = None
        self._skills_text: str = ""
        self._load_skills()

    def _load_skills(self) -> None:
        """Glob manager_skills/*.md relative to this file. Concatenate with headers."""
        skills_dir = Path(__file__).parent / "manager_skills"
        parts: list[str] = []
        if skills_dir.is_dir():
            for md_file in sorted(skills_dir.glob("*.md")):
                parts.append(f"## {md_file.stem}\n\n{md_file.read_text()}")
        self._skills_text = "\n\n".join(parts)
        logger.info("DevTeam loaded %d manager skill files", len(parts))

    def _get_adapter(self) -> LLMPort:
        """Lazy-init Flash LLM adapter for Manager reasoning."""
        if self._adapter is None:
            self._adapter = create_adapter(
                provider="gemini",
                project=os.getenv("GCP_PROJECT", ""),
                location=os.getenv("GCP_LOCATION", "global"),
                model_name=os.getenv("VERTEX_MODEL_FLASH", "gemini-3-flash-preview"),
            )
        return self._adapter

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def process(
        self,
        event_id: str,
        task: str,
        on_progress: Optional[Callable] = None,
        event_md_path: str = "",
    ) -> tuple[str, str | None]:
        """Multi-turn function-calling loop: triage -> dispatch -> review -> report."""
        adapter = self._get_adapter()
        system_prompt = f"You are the Dev Team Manager.\n\n{self._skills_text}"
        contents: list[dict] = [{"role": "user", "parts": [{"text": task}]}]

        if on_progress:
            await on_progress({"actor": "manager", "event_id": event_id, "message": "Analyzing task..."})

        fix_count = 0

        for _ in range(MAX_CONVERSATION_ROUNDS):
            response = await adapter.generate(
                system_prompt=system_prompt,
                contents=contents,
                tools=MANAGER_TOOL_SCHEMAS,
                temperature=0.7,
            )

            if response.function_call:
                fn = response.function_call
                if on_progress:
                    await on_progress({"actor": "manager", "event_id": event_id, "message": f"Calling {fn.name}..."})

                # Enforce fix-round ceiling
                if fn.name == "request_fix":
                    fix_count += 1
                if fn.name == "request_fix" and fix_count > MAX_FIX_ROUNDS:
                    fn_result = {
                        "status": "max_fixes_reached",
                        "message": f"Fix round limit ({MAX_FIX_ROUNDS}) reached. "
                                   "Force approve and call report_to_brain.",
                    }
                else:
                    fn_result = await self._execute_function(
                        fn.name, fn.args, event_id, on_progress, event_md_path,
                    )

                if fn_result.get("_terminal"):
                    return fn_result["summary"], None

                contents.append({"role": "model", "parts": [{"function_call": {"name": fn.name, "args": fn.args}}]})
                contents.append({"role": "user", "parts": [{"function_response": {"name": fn.name, "response": fn_result}}]})

            elif response.text:
                return response.text, None

        return "DevTeam exceeded max conversation rounds", None

    # ------------------------------------------------------------------
    # Function execution handlers
    # ------------------------------------------------------------------

    async def _execute_function(
        self,
        fn_name: str,
        args: dict,
        event_id: str,
        on_progress: Optional[Callable],
        event_md_path: str = "",
    ) -> dict:
        """Execute a Manager function call against the agent registry."""
        from .dependencies import get_registry_and_bridge
        registry, bridge = get_registry_and_bridge()
        if not registry or not bridge:
            return {"error": "Agent registry not initialized"}

        if fn_name == "dispatch_developer":
            return await self._dispatch_single(
                registry, bridge, "developer", event_id, args["task"],
                on_progress, event_md_path,
            )

        if fn_name == "dispatch_qe":
            return await self._dispatch_single(
                registry, bridge, "qe", event_id, args["task"],
                on_progress, event_md_path,
            )

        if fn_name == "dispatch_both":
            return await self._dispatch_both(
                registry, bridge, event_id, args, on_progress, event_md_path,
            )

        if fn_name == "approve_and_merge":
            agent_id = args.get("dev_agent_id") or None
            result, _ = await dispatch_to_agent(
                registry, bridge, "developer", event_id,
                "Open a Pull Request, wait for pipeline, merge if green. Report PR URL and status.",
                on_progress=on_progress, agent_id=agent_id,
                event_md_path=event_md_path,
            )
            return {"pr_result": result}

        if fn_name == "request_fix":
            agent_id = args.get("agent_id") or None
            role = "qe" if (agent_id or "").startswith("qe") else "developer"
            result, _ = await dispatch_to_agent(
                registry, bridge, role, event_id, args.get("feedback", ""),
                on_progress=on_progress, agent_id=agent_id,
                event_md_path=event_md_path,
            )
            return {"fix_result": result}

        if fn_name == "request_review":
            return {
                "status": "review_complete",
                "dev_output": args.get("dev_output", ""),
                "qe_output": args.get("qe_output", ""),
            }

        if fn_name == "report_to_brain":
            return {
                "_terminal": True,
                "summary": args.get("summary", ""),
                "status": args.get("status", "success"),
            }

        if fn_name == "reply_to_agent":
            # Send reply to an agent's pending HuddleSendMessage via persistent WS
            agent_id = args.get("agent_id", "")
            message = args.get("message", "")
            agent = await registry.get_by_id(agent_id) if agent_id else None
            if agent and agent.ws:
                try:
                    await agent.ws.send_json({
                        "type": "huddle_reply",
                        "task_id": agent.current_task_id or "",
                        "content": message,
                    })
                    logger.info("Huddle reply sent to %s (%d chars)", agent_id, len(message))
                    return {"status": "replied", "agent_id": agent_id}
                except Exception as e:
                    return {"error": f"Failed to send reply: {e}"}
            return {"error": f"Agent {agent_id} not found or not connected"}

        return {"error": f"Unknown function: {fn_name}"}

    # ------------------------------------------------------------------
    # Dispatch helpers
    # ------------------------------------------------------------------

    async def _dispatch_single(
        self, registry, bridge, role: str, event_id: str, task: str,
        on_progress: Optional[Callable], event_md_path: str,
    ) -> dict:
        """Resolve agent, dispatch, return result with agent_id for session affinity."""
        conn = await registry.get_available(role)
        if not conn:
            return {"error": f"No {role} agent available"}
        result, session_id = await dispatch_to_agent(
            registry, bridge, role, event_id, task,
            on_progress=on_progress, agent_id=conn.agent_id,
            event_md_path=event_md_path,
        )
        return {"result": result, "session_id": session_id, "agent_id": conn.agent_id}

    async def _dispatch_both(
        self, registry, bridge, event_id: str, args: dict,
        on_progress: Optional[Callable], event_md_path: str,
    ) -> dict:
        """Concurrent developer + QE dispatch with CancelledError propagation."""
        dev_conn = await registry.get_available("developer")
        qe_conn = await registry.get_available("qe")
        if not dev_conn:
            return {"error": "No developer agent available"}
        if not qe_conn:
            return {"error": "No QE agent available"}

        async def _qe_on_progress(d: dict) -> None:
            if on_progress:
                await on_progress({**d, "actor": "qe"})

        dev_task = asyncio.create_task(dispatch_to_agent(
            registry, bridge, "developer", event_id, args["dev_task"],
            on_progress=on_progress, agent_id=dev_conn.agent_id,
            event_md_path=event_md_path,
        ))
        qe_task = asyncio.create_task(dispatch_to_agent(
            registry, bridge, "qe", event_id, args["qe_task"],
            on_progress=_qe_on_progress, agent_id=qe_conn.agent_id,
            event_md_path=event_md_path,
        ))

        try:
            (dev_result, dev_sid), (qe_result, qe_sid) = await asyncio.gather(
                dev_task, qe_task,
            )
        except asyncio.CancelledError:
            dev_task.cancel()
            qe_task.cancel()
            await asyncio.gather(dev_task, qe_task, return_exceptions=True)
            raise

        return {
            "dev_result": dev_result, "dev_session_id": dev_sid,
            "dev_agent_id": dev_conn.agent_id,
            "qe_result": qe_result, "qe_session_id": qe_sid,
            "qe_agent_id": qe_conn.agent_id,
        }
