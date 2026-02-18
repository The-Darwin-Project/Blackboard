# src/agents/llm/claude_client.py
# @ai-rules:
# 1. [Constraint]: Only import anthropic inside this file. Never leak SDK types outside.
# 2. [Pattern]: _build_kwargs() shared by generate() and generate_stream(). tools=None omits tool config.
# 3. [Gotcha]: Claude rejects temperature + top_p together -- only pass temperature (normalized).
# 4. [Pattern]: Temperature normalization: config range 0.0-2.0 -> Claude range 0.0-1.0 (divide by 2).
# 5. [Pattern]: Uses AsyncAnthropicVertex for Vertex AI authentication (same SA key as Brain).
# 6. [Pattern]: _process_stream_response() shared by generate_stream(), chat_send(), chat_report_tool_result().
# 7. [Pattern]: _chats dict stores accumulated messages per session. _pending_tool_use tracks tool_use_id for tool_result pairing.
# 8. [Gotcha]: Every assistant tool_use block MUST be followed by a user tool_result message before the next API call.
"""
ClaudeAdapter -- LLMPort implementation using Anthropic SDK (Vertex AI).

Supports stateless generate/generate_stream and session-based
chat_send/chat_report_tool_result via message list accumulation.
"""
from __future__ import annotations

import logging
import uuid
from collections.abc import AsyncIterator

from .types import FunctionCall, LLMChunk, LLMResponse

logger = logging.getLogger(__name__)


class ClaudeAdapter:
    """Anthropic Claude adapter implementing LLMPort via Vertex AI."""

    def __init__(self, project: str, location: str, model_name: str):
        from anthropic import AsyncAnthropicVertex

        self._client = AsyncAnthropicVertex(
            region=location,
            project_id=project,
        )
        self._model_name = model_name
        self._chats: dict[str, dict] = {}
        self._pending_tool_use: dict[str, str] = {}
        logger.info(f"ClaudeAdapter initialized: {model_name} (region={location})")

    # -----------------------------------------------------------------
    # Shared helpers
    # -----------------------------------------------------------------

    def _build_kwargs(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None,
        temperature: float,
        max_output_tokens: int,
    ) -> dict:
        """Build kwargs dict for messages.create / messages.stream."""
        messages = self._convert_contents(contents)

        kwargs: dict = {
            "model": self._model_name,
            "max_tokens": max_output_tokens,
            "temperature": temperature,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools is not None:
            kwargs["tools"] = self._convert_tools(tools)

        return kwargs

    @staticmethod
    def _convert_tools(schemas: list[dict]) -> list[dict]:
        """Convert to Anthropic tool format (already close to native)."""
        return [
            {
                "name": s["name"],
                "description": s["description"],
                "input_schema": s["input_schema"],
            }
            for s in schemas
        ]

    @staticmethod
    def _convert_contents(contents: str | list) -> list[dict]:
        """Convert provider-agnostic contents to Anthropic messages format."""
        if isinstance(contents, str):
            return [{"role": "user", "content": contents}]

        # Multimodal: list of str / image dicts
        blocks = []
        for item in contents:
            if isinstance(item, str):
                blocks.append({"type": "text", "text": item})
            elif isinstance(item, dict) and "bytes" in item:
                import base64
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": item["mime_type"],
                        "data": base64.b64encode(item["bytes"]).decode(),
                    },
                })
        return [{"role": "user", "content": blocks}]

    # -----------------------------------------------------------------
    # LLMPort: generate (blocking)
    # -----------------------------------------------------------------

    async def generate(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        max_output_tokens: int = 65000,
    ) -> LLMResponse:
        # Normalize temperature: 0.0-2.0 -> 0.0-1.0. Drop top_p (Claude rejects both).
        claude_temp = min(temperature / 2.0, 1.0)
        kwargs = self._build_kwargs(system_prompt, contents, tools, claude_temp, max_output_tokens)

        message = await self._client.messages.create(**kwargs)

        tool_uses = [b for b in message.content if b.type == "tool_use"]
        text_blocks = [b.text for b in message.content if b.type == "text"]

        if tool_uses:
            tc = tool_uses[0]
            return LLMResponse(
                function_call=FunctionCall(name=tc.name, args=tc.input or {}),
                text="\n".join(text_blocks) if text_blocks else None,
            )
        return LLMResponse(text="\n".join(text_blocks) if text_blocks else None)

    # -----------------------------------------------------------------
    # LLMPort: generate_stream (async iterator)
    # -----------------------------------------------------------------

    async def generate_stream(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        max_output_tokens: int = 65000,
    ) -> AsyncIterator[LLMChunk]:
        claude_temp = min(temperature / 2.0, 1.0)
        kwargs = self._build_kwargs(system_prompt, contents, tools, claude_temp, max_output_tokens)

        async for chunk in self._stream_and_yield(kwargs):
            yield chunk

    # -----------------------------------------------------------------
    # Shared: single-pass stream + final message capture
    # -----------------------------------------------------------------

    async def _stream_and_yield(self, kwargs: dict, capture_to: list | None = None) -> AsyncIterator[LLMChunk]:
        """Stream response, yield LLMChunks, optionally capture assistant message.

        When capture_to is provided (a list), the raw assistant message content
        blocks are appended for caller to persist into chat history.
        """
        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield LLMChunk(text=text)

            message = await stream.get_final_message()

            if capture_to is not None:
                capture_to.extend(message.content)

            tool_uses = [b for b in message.content if b.type == "tool_use"]
            if tool_uses:
                tc = tool_uses[0]
                yield LLMChunk(
                    function_call=FunctionCall(name=tc.name, args=tc.input or {}),
                    tool_use_id=tc.id,
                    done=True,
                )
            else:
                yield LLMChunk(done=True)

    # -----------------------------------------------------------------
    # ChatPort: session-based chat (used by Brain)
    # -----------------------------------------------------------------

    def create_chat(
        self,
        system_prompt: str,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        max_output_tokens: int = 65000,
    ) -> str:
        claude_temp = min(temperature / 2.0, 1.0)
        session_id = str(uuid.uuid4())
        self._chats[session_id] = {
            "messages": [],
            "system": system_prompt,
            "tools": self._convert_tools(tools) if tools else None,
            "temperature": claude_temp,
            "max_tokens": max_output_tokens,
        }
        logger.debug(f"Chat session created: {session_id}")
        return session_id

    def _build_chat_kwargs(self, session_id: str) -> dict:
        """Build kwargs for messages.stream from accumulated chat state."""
        state = self._chats[session_id]
        kwargs: dict = {
            "model": self._model_name,
            "max_tokens": state["max_tokens"],
            "temperature": state["temperature"],
            "messages": list(state["messages"]),
        }
        if state["system"]:
            kwargs["system"] = state["system"]
        if state["tools"]:
            kwargs["tools"] = state["tools"]
        return kwargs

    async def chat_send(
        self,
        session_id: str,
        contents: str | list,
    ) -> AsyncIterator[LLMChunk]:
        state = self._chats.get(session_id)
        if not state:
            raise ValueError(f"Unknown chat session: {session_id}")

        if isinstance(contents, str):
            state["messages"].append({"role": "user", "content": contents})
        else:
            blocks = []
            for item in contents:
                if isinstance(item, str):
                    blocks.append({"type": "text", "text": item})
                elif isinstance(item, dict) and "bytes" in item:
                    import base64
                    blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": item["mime_type"],
                            "data": base64.b64encode(item["bytes"]).decode(),
                        },
                    })
            state["messages"].append({"role": "user", "content": blocks})

        kwargs = self._build_chat_kwargs(session_id)
        assistant_content: list = []
        async for chunk in self._stream_and_yield(kwargs, capture_to=assistant_content):
            if chunk.tool_use_id:
                self._pending_tool_use[session_id] = chunk.tool_use_id
            yield chunk

        state["messages"].append({"role": "assistant", "content": assistant_content})

    async def chat_report_tool_result(
        self,
        session_id: str,
        function_name: str,
        result: str,
    ) -> AsyncIterator[LLMChunk]:
        state = self._chats.get(session_id)
        if not state:
            raise ValueError(f"Unknown chat session: {session_id}")

        tool_use_id = self._pending_tool_use.pop(session_id, None)
        if not tool_use_id:
            raise ValueError(f"No pending tool_use for session {session_id}")

        state["messages"].append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": tool_use_id, "content": result}
        ]})

        kwargs = self._build_chat_kwargs(session_id)
        assistant_content: list = []
        async for chunk in self._stream_and_yield(kwargs, capture_to=assistant_content):
            if chunk.tool_use_id:
                self._pending_tool_use[session_id] = chunk.tool_use_id
            yield chunk

        state["messages"].append({"role": "assistant", "content": assistant_content})

    def close_chat(self, session_id: str) -> None:
        self._chats.pop(session_id, None)
        self._pending_tool_use.pop(session_id, None)
        logger.debug(f"Chat session closed: {session_id}")
