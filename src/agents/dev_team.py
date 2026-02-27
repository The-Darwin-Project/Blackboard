# BlackBoard/src/agents/dev_team.py
# @ai-rules:
# 1. [Pattern]: Manager LLM is the team entry point. Brain dispatches to DevTeam, Manager decides work split.
# 2. [Pattern]: Manager uses function calling (MANAGER_TOOL_SCHEMAS). No raw JSON parsing, no mode routing if/else.
# 3. [Pattern]: CancelledError propagation: cancel all active dispatch asyncio.Tasks on cancel.
# 4. [Pattern]: on_progress with actor="manager" for all Manager decisions. Dev/QE progress uses their own actor names.
# 5. [Constraint]: MAX_FIX_ROUNDS caps fix iterations, then force approve. Prevents infinite loops.
# 6. [Pattern]: Session affinity via agent_id -- follow-up rounds route to the same agent that did the original work.
# 7. [Pattern]: Concurrent huddle drain in ALL dispatch paths via _dispatch_with_drain and _drain_loop.
"""
Dev Team -- Manager LLM coordinates developer + QE agents.

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

MAX_FIX_ROUNDS = 20
MAX_CONVERSATION_ROUNDS = 100
MAX_HUDDLE_REPLIES = 50

__all__ = ["DevTeam"]


class DevTeam:
    """Dev Team -- Manager LLM coordinates developer + QE agents."""

    def __init__(self):
        self._adapter: LLMPort | None = None
        self._skills_text: str = ""
        self._sessions: dict[str, dict[str, str | None]] = {}
        self._pending_huddles: dict[str, asyncio.Queue] = {}
        self._load_skills()

    def cleanup_event(self, event_id: str) -> None:
        """Release session and huddle caches for a closed event."""
        self._sessions.pop(event_id, None)
        self._pending_huddles.pop(event_id, None)

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
        """Lazy-init Manager LLM adapter (model from LLM_MODEL_MANAGER)."""
        if self._adapter is None:
            self._adapter = create_adapter(
                provider="gemini",
                project=os.getenv("GCP_PROJECT", ""),
                location=os.getenv("GCP_LOCATION", "global"),
                model_name=os.getenv("LLM_MODEL_MANAGER", "gemini-3.1-pro-preview"),
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

        for round_num in range(MAX_CONVERSATION_ROUNDS):
            try:
                response = await adapter.generate(
                    system_prompt=system_prompt,
                    contents=contents,
                    tools=MANAGER_TOOL_SCHEMAS,
                    temperature=float(os.getenv("LLM_TEMPERATURE_MANAGER", "0.4")),
                    thinking_level=os.getenv("LLM_THINKING_MANAGER", "low"),
                )
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.error("Manager LLM call failed (round %d, event %s): %s", round_num, event_id, exc)
                if contents and contents[-1].get("role") != "user":
                    contents.append({"role": "user", "parts": [
                        {"text": "[system: LLM error, please call report_to_brain with current status]"}]})
                continue

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
                        contents=contents, adapter=adapter,
                        system_prompt=system_prompt,
                    )

                if fn_result.get("_terminal"):
                    status = fn_result.get("status", "success")
                    rec = fn_result.get("recommendation", "")
                    summary = fn_result["summary"]
                    if rec:
                        summary = f"{summary}\n\n## Recommendation\n{rec}"
                    return summary, status

                model_parts = self._extract_model_parts(response, fn)
                if contents and contents[-1].get("role") == "model":
                    contents.append({"role": "user", "parts": [
                        {"text": "[system: dispatch completed, resuming Manager conversation]"}]})
                contents.append({"role": "model", "parts": model_parts})
                contents.append({"role": "user", "parts": [{"function_response": {"name": fn.name, "response": fn_result}}]})

                await self._drain_huddles(event_id, contents, adapter, system_prompt, on_progress)

            elif response.text:
                return response.text, None

        self._pending_huddles.pop(event_id, None)
        return "DevTeam exceeded max conversation rounds", None

    @staticmethod
    def _extract_model_parts(response, fn) -> list[dict]:
        """Build model parts preserving thought_signature from raw response.
        Gemini 3 requires thought_signature on function_call parts in multi-turn replay.
        """
        if response.raw_parts:
            import base64
            parts = []
            for part in response.raw_parts:
                p: dict = {}
                if hasattr(part, 'thought') and part.thought and hasattr(part, 'text') and part.text:
                    p['text'] = str(part.text)
                    p['thought'] = True
                if hasattr(part, 'function_call') and part.function_call:
                    p['functionCall'] = {"name": fn.name, "args": fn.args}
                sig = getattr(part, 'thought_signature', None) or getattr(part, 'thoughtSignature', None)
                if sig:
                    p['thought_signature'] = base64.b64encode(sig).decode('ascii') if isinstance(sig, bytes) else str(sig)
                if p:
                    parts.append(p)
            if parts:
                return parts
        return [{"functionCall": {"name": fn.name, "args": fn.args}}]

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
        *,
        contents: list | None = None,
        adapter: LLMPort | None = None,
        system_prompt: str = "",
    ) -> dict:
        """Execute a Manager function call against the agent registry."""
        from ..dependencies import get_registry_and_bridge
        registry, bridge = get_registry_and_bridge()
        if not registry or not bridge:
            return {"error": "Agent registry not initialized"}

        if fn_name == "dispatch_developer":
            return await self._dispatch_single(
                registry, bridge, "developer", event_id, args["task"],
                on_progress, event_md_path,
                contents=contents, adapter=adapter, system_prompt=system_prompt,
            )

        if fn_name == "dispatch_qe":
            return await self._dispatch_single(
                registry, bridge, "qe", event_id, args["task"],
                on_progress, event_md_path,
                contents=contents, adapter=adapter, system_prompt=system_prompt,
            )

        if fn_name == "dispatch_both":
            return await self._dispatch_both(
                registry, bridge, event_id, args, on_progress, event_md_path,
                contents=contents, adapter=adapter, system_prompt=system_prompt,
            )

        if fn_name == "approve_and_merge":
            agent_id = args.get("dev_agent_id") or None
            prev_sid = self._sessions.get(event_id, {}).get("developer")
            result, sid = await self._dispatch_with_drain(
                event_id,
                dispatch_to_agent(
                    registry, bridge, "developer", event_id,
                    "Open a Pull Request, wait for pipeline, merge if green. Report PR URL and status.",
                    on_progress=on_progress, on_huddle=self._make_on_huddle(event_id),
                    agent_id=agent_id, session_id=prev_sid, event_md_path=event_md_path,
                ),
                contents, adapter, system_prompt, on_progress,
            )
            self._sessions.setdefault(event_id, {})["developer"] = sid
            return {"pr_result": result}

        if fn_name == "request_fix":
            agent_id = args.get("agent_id") or None
            role = "qe" if (agent_id or "").startswith("qe") else "developer"
            prev_sid = self._sessions.get(event_id, {}).get(role)
            result, sid = await self._dispatch_with_drain(
                event_id,
                dispatch_to_agent(
                    registry, bridge, role, event_id, args.get("feedback", ""),
                    on_progress=on_progress, on_huddle=self._make_on_huddle(event_id),
                    agent_id=agent_id, session_id=prev_sid, event_md_path=event_md_path,
                ),
                contents, adapter, system_prompt, on_progress,
            )
            self._sessions.setdefault(event_id, {})[role] = sid
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
                "recommendation": args.get("recommendation", ""),
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

        if fn_name == "message_agent":
            agent_id = args.get("agent_id", "")
            message = args.get("message", "")
            agent = await registry.get_by_id(agent_id) if agent_id else None
            if agent and agent.ws:
                try:
                    await agent.ws.send_json({
                        "type": "proactive_message",
                        "from": "manager",
                        "content": message,
                    })
                    logger.info("Proactive message sent to %s (%d chars)", agent_id, len(message))
                    if on_progress:
                        await on_progress({"actor": "manager", "event_id": event_id,
                                           "message": f"[proactive] -> {agent_id}: {message[:80]}"})
                    return {"status": "sent", "agent_id": agent_id}
                except Exception as e:
                    return {"error": f"Failed to send: {e}"}
            return {"error": f"Agent {agent_id} not found or not connected"}

        return {"error": f"Unknown function: {fn_name}"}

    # ------------------------------------------------------------------
    # Huddle support
    # ------------------------------------------------------------------

    def _make_on_huddle(self, event_id: str) -> Callable:
        """Create an on_huddle callback that queues messages for the Manager."""
        queue = self._pending_huddles.setdefault(event_id, asyncio.Queue())
        async def on_huddle(data: dict) -> None:
            await queue.put(data)
            logger.info("Huddle message queued from %s for %s", data.get("agent_id", "?"), event_id)
        return on_huddle

    async def _process_huddle_message(
        self, event_id: str, msg: dict, contents: list,
        adapter, system_prompt: str, on_progress,
    ) -> bool:
        """Process one huddle message through Manager LLM. Returns True if reply sent."""
        agent_id = msg.get("agent_id", "")
        content = msg.get("content", "")
        if on_progress:
            await on_progress({"actor": "manager", "event_id": event_id,
                               "message": f"Huddle from {agent_id}: {content[:80]}"})
        contents.append({"role": "user", "parts": [{"text":
            f"[HUDDLE from {agent_id}]: {content}\n\n"
            f"You MUST reply using reply_to_agent(agent_id=\"{agent_id}\", message=\"your response\"). "
            f"Do NOT call any dispatch or report function -- the agent is waiting for your reply."}]})
        try:
            resp = await adapter.generate(
                system_prompt=system_prompt, contents=contents,
                tools=MANAGER_TOOL_SCHEMAS,
                temperature=float(os.getenv("LLM_TEMPERATURE_MANAGER", "0.4")),
                thinking_level=os.getenv("LLM_THINKING_MANAGER", "low"),
            )
        except Exception:
            contents.pop()
            raise
        if resp.function_call and resp.function_call.name == "reply_to_agent":
            fn_result = await self._execute_function(
                resp.function_call.name, resp.function_call.args,
                event_id, on_progress,
            )
            model_parts = self._extract_model_parts(resp, resp.function_call)
            contents.append({"role": "model", "parts": model_parts})
            contents.append({"role": "user", "parts": [
                {"function_response": {"name": "reply_to_agent", "response": fn_result}}]})
            return True
        elif resp.function_call:
            logger.warning("Drain: ignoring %s during huddle", resp.function_call.name)
            contents.append({"role": "model", "parts": [
                {"text": f"[deferred: {resp.function_call.name} not allowed during huddle drain]"}]})
        elif resp.text:
            contents.append({"role": "model", "parts": [{"text": resp.text}]})
        return False

    async def _drain_huddles(self, event_id: str, contents: list, adapter, system_prompt: str, on_progress) -> None:
        """Process any already-queued huddle messages (non-blocking, no wait)."""
        queue = self._pending_huddles.get(event_id)
        if not queue:
            return
        while not queue.empty():
            msg = queue.get_nowait()
            try:
                await self._process_huddle_message(event_id, msg, contents, adapter, system_prompt, on_progress)
            except Exception as exc:
                logger.warning("Drain huddles error for %s: %s", event_id, exc)

    async def _drain_loop(
        self, event_id: str, watched_tasks: list[asyncio.Task],
        contents: list | None, adapter, system_prompt: str, on_progress,
    ) -> None:
        """Concurrent drain: process huddles while watched tasks run.

        Concurrency safety: the caller is suspended at an await (gather or single task).
        This loop is the sole contents writer. Exits when all watched tasks complete.
        """
        queue = self._pending_huddles.get(event_id)
        if not queue or not contents or not adapter:
            return
        replies = 0
        while replies < MAX_HUDDLE_REPLIES:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=5.0)
            except asyncio.TimeoutError:
                if all(t.done() for t in watched_tasks):
                    break
                continue
            try:
                replied = await self._process_huddle_message(
                    event_id, msg, contents, adapter, system_prompt, on_progress,
                )
                if replied:
                    replies += 1
            except asyncio.CancelledError:
                contents.append({"role": "model", "parts": [{"text": "[drain cancelled]"}]})
                raise
            except Exception as exc:
                logger.warning("Drain loop error for %s: %s", event_id, exc)
        logger.info("Drain loop: %d huddle replies for event %s", replies, event_id)

    async def _dispatch_with_drain(
        self, event_id: str, dispatch_coro: asyncio.coroutines,
        contents: list | None, adapter: LLMPort | None,
        system_prompt: str, on_progress: Optional[Callable],
    ) -> tuple[str, str | None]:
        """Run a dispatch coroutine as a task with concurrent huddle drain.

        Returns the dispatch result. CancelledError-safe with proper cleanup.
        """
        agent_task = asyncio.create_task(dispatch_coro)
        drain_task = asyncio.create_task(self._drain_loop(
            event_id, [agent_task], contents, adapter, system_prompt, on_progress,
        ))
        try:
            return await agent_task
        except asyncio.CancelledError:
            agent_task.cancel()
            drain_task.cancel()
            await asyncio.gather(agent_task, drain_task, return_exceptions=True)
            raise
        finally:
            drain_task.cancel()
            await asyncio.gather(drain_task, return_exceptions=True)

    # ------------------------------------------------------------------
    # Dispatch helpers
    # ------------------------------------------------------------------

    async def _dispatch_single(
        self, registry, bridge, role: str, event_id: str, task: str,
        on_progress: Optional[Callable], event_md_path: str,
        *,
        contents: list | None = None,
        adapter: LLMPort | None = None,
        system_prompt: str = "",
    ) -> dict:
        """Resolve agent, dispatch with concurrent huddle drain, return result."""
        conn = await registry.get_available(role)
        if not conn:
            return {"error": f"No {role} agent available"}
        prev_session = self._sessions.get(event_id, {}).get(role)

        result, session_id = await self._dispatch_with_drain(
            event_id,
            dispatch_to_agent(
                registry, bridge, role, event_id, task,
                on_progress=on_progress, on_huddle=self._make_on_huddle(event_id),
                agent_id=conn.agent_id,
                session_id=prev_session,
                event_md_path=event_md_path,
            ),
            contents, adapter, system_prompt, on_progress,
        )

        self._sessions.setdefault(event_id, {})[role] = session_id
        return {"result": result, "session_id": session_id, "agent_id": conn.agent_id}

    async def _dispatch_both(
        self, registry, bridge, event_id: str, args: dict,
        on_progress: Optional[Callable], event_md_path: str,
        *,
        contents: list | None = None,
        adapter: LLMPort | None = None,
        system_prompt: str = "",
    ) -> dict:
        """Concurrent developer + QE dispatch with huddle drain.

        Safety: during asyncio.gather, process() is suspended at the await chain.
        The drain loop is the sole writer to contents. After gather returns, drain
        is cancelled and process() resumes as sole writer.
        """
        dev_conn = await registry.get_available("developer")
        qe_conn = await registry.get_available("qe")
        if not dev_conn:
            return {"error": "No developer agent available"}
        if not qe_conn:
            return {"error": "No QE agent available"}

        async def _qe_on_progress(d: dict) -> None:
            if on_progress:
                await on_progress({**d, "actor": "qe"})

        prev = self._sessions.get(event_id, {})
        huddle_cb = self._make_on_huddle(event_id)
        dev_task = asyncio.create_task(dispatch_to_agent(
            registry, bridge, "developer", event_id, args["dev_task"],
            on_progress=on_progress, on_huddle=huddle_cb,
            agent_id=dev_conn.agent_id,
            session_id=prev.get("developer"),
            event_md_path=event_md_path,
        ))
        qe_task = asyncio.create_task(dispatch_to_agent(
            registry, bridge, "qe", event_id, args["qe_task"],
            on_progress=_qe_on_progress, on_huddle=huddle_cb,
            agent_id=qe_conn.agent_id,
            session_id=prev.get("qe"),
            event_md_path=event_md_path,
        ))

        drain_task = asyncio.create_task(self._drain_loop(
            event_id, [dev_task, qe_task], contents, adapter, system_prompt, on_progress,
        ))

        try:
            (dev_result, dev_sid), (qe_result, qe_sid) = await asyncio.gather(
                dev_task, qe_task,
            )
        except asyncio.CancelledError:
            dev_task.cancel()
            qe_task.cancel()
            drain_task.cancel()
            await asyncio.gather(dev_task, qe_task, drain_task, return_exceptions=True)
            raise
        finally:
            drain_task.cancel()
            await asyncio.gather(drain_task, return_exceptions=True)

        self._sessions.setdefault(event_id, {}).update({"developer": dev_sid, "qe": qe_sid})
        return {
            "dev_result": dev_result, "dev_session_id": dev_sid,
            "dev_agent_id": dev_conn.agent_id,
            "qe_result": qe_result, "qe_session_id": qe_sid,
            "qe_agent_id": qe_conn.agent_id,
        }
