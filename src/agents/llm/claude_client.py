# src/agents/llm/claude_client.py
# @ai-rules:
# 1. [Constraint]: Only import anthropic inside this file. Never leak SDK types outside.
# 2. [Pattern]: _build_kwargs() shared by generate() and generate_stream(). tools=None omits tool config.
# 3. [Gotcha]: Claude rejects temperature + top_p together -- only pass temperature (normalized).
# 4. [Pattern]: Temperature normalization: config range 0.0-2.0 -> Claude range 0.0-1.0 (divide by 2).
# 5. [Pattern]: Uses AsyncAnthropicVertex for Vertex AI authentication (same SA key as Brain).
# 6. [Pattern]: _convert_contents() three-way: str (plain) | list[dict] with "role" (structured) | list (multimodal).
# 7. [Pattern]: Structured contents map: model->assistant, functionCall->tool_use, functionResponse->tool_result.
# 8. [Pattern]: tool_choice flows through _build_kwargs -> API kwargs. Only sent when tools are present.
"""
ClaudeAdapter -- LLMPort implementation using Anthropic SDK (Vertex AI).

Supports both blocking generate() and streaming generate_stream() via
messages.create / messages.stream.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from .types import FunctionCall, LLMChunk, LLMResponse, TokenUsage

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
        logger.info(f"ClaudeAdapter initialized: {model_name} (region={location})")

    # -----------------------------------------------------------------
    # Token usage extraction
    # -----------------------------------------------------------------

    def _extract_usage(self, message) -> TokenUsage | None:
        """Extract TokenUsage from Anthropic message.usage."""
        usage = getattr(message, "usage", None)
        if usage is None:
            return None
        input_t = getattr(usage, "input_tokens", None) or 0
        output_t = getattr(usage, "output_tokens", None) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", None) or 0
        return TokenUsage(
            input_tokens=input_t + cache_read,
            output_tokens=output_t,
            cached_tokens=cache_read,
            total_tokens=input_t + cache_read + output_t,
            model_version=self._model_name,
        )

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
        tool_choice: dict | None = None,
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
            if tool_choice:
                kwargs["tool_choice"] = tool_choice

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
        """Convert provider-agnostic contents to Anthropic messages format.

        Three input formats:
        - str: plain text (Aligner, simple prompts)
        - list[dict] with "role" key: structured multi-turn (Brain)
        - list[str | dict]: multimodal (text + images)
        """
        if isinstance(contents, str):
            return [{"role": "user", "content": contents}]

        # Structured multi-turn: [{role, parts}]
        if contents and isinstance(contents[0], dict) and "role" in contents[0]:
            return ClaudeAdapter._convert_structured(contents)

        # Multimodal: [text_str, {"bytes": bytes, "mime_type": str}]
        return ClaudeAdapter._convert_multimodal(contents)

    @staticmethod
    def _convert_multimodal(contents: list) -> list[dict]:
        """Convert provider-agnostic multimodal list to Anthropic messages."""
        import base64
        blocks = []
        for item in contents:
            if isinstance(item, str):
                blocks.append({"type": "text", "text": item})
            elif isinstance(item, dict) and "bytes" in item:
                blocks.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": item["mime_type"],
                        "data": base64.b64encode(item["bytes"]).decode(),
                    },
                })
        return [{"role": "user", "content": blocks}]

    @staticmethod
    def _convert_structured(contents: list[dict]) -> list[dict]:
        """Convert Gemini-format structured contents to Anthropic messages.

        Role mapping: model->assistant, user->user.
        functionCall parts -> tool_use content blocks.
        After tool_use, the next user message becomes tool_result (Claude requires this).
        """
        import base64
        messages = []
        tool_call_counter = 0
        pending_tool_id: str | None = None

        for msg in contents:
            role = "assistant" if msg["role"] == "model" else "user"
            blocks = []

            # If previous assistant had tool_use and this is the user response,
            # wrap the entire user message as a tool_result
            if pending_tool_id and role == "user":
                text_parts = []
                for p in msg.get("parts", []):
                    if isinstance(p, dict) and "text" in p:
                        text_parts.append(p["text"])
                    elif isinstance(p, str):
                        text_parts.append(p)
                blocks.append({
                    "type": "tool_result",
                    "tool_use_id": pending_tool_id,
                    "content": "\n".join(text_parts) if text_parts else "(no output)",
                })
                pending_tool_id = None
                messages.append({"role": role, "content": blocks})
                continue

            pending_tool_id = None
            for p in msg.get("parts", []):
                if isinstance(p, dict) and "functionCall" in p:
                    tool_call_counter += 1
                    fc = p["functionCall"]
                    tid = f"call_{tool_call_counter}"
                    blocks.append({
                        "type": "tool_use",
                        "id": tid,
                        "name": fc["name"],
                        "input": fc.get("args", {}),
                    })
                    pending_tool_id = tid
                elif isinstance(p, dict) and "functionResponse" in p:
                    fr = p["functionResponse"]
                    blocks.append({
                        "type": "tool_result",
                        "tool_use_id": f"call_{tool_call_counter}",
                        "content": str(fr.get("response", "")),
                    })
                    pending_tool_id = None
                elif isinstance(p, dict) and "bytes" in p:
                    blocks.append({
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": p["mime_type"],
                            "data": base64.b64encode(p["bytes"]).decode(),
                        },
                    })
                elif isinstance(p, dict) and "text" in p:
                    blocks.append({"type": "text", "text": p["text"]})
                elif isinstance(p, str):
                    blocks.append({"type": "text", "text": p})
            if blocks:
                messages.append({"role": role, "content": blocks})
        return messages

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
        tool_choice: dict | None = None,
    ) -> LLMResponse:
        # Normalize temperature: 0.0-2.0 -> 0.0-1.0. Drop top_p (Claude rejects both).
        claude_temp = min(temperature / 2.0, 1.0)
        kwargs = self._build_kwargs(system_prompt, contents, tools, claude_temp, max_output_tokens, tool_choice)

        message = await self._client.messages.create(**kwargs)
        token_usage = self._extract_usage(message)

        tool_uses = [b for b in message.content if b.type == "tool_use"]
        text_blocks = [b.text for b in message.content if b.type == "text"]

        if tool_uses:
            tc = tool_uses[0]
            return LLMResponse(
                function_call=FunctionCall(name=tc.name, args=tc.input or {}),
                text="\n".join(text_blocks) if text_blocks else None,
                usage=token_usage,
            )
        return LLMResponse(text="\n".join(text_blocks) if text_blocks else None, usage=token_usage)

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
        tool_choice: dict | None = None,
    ) -> AsyncIterator[LLMChunk]:
        claude_temp = min(temperature / 2.0, 1.0)
        kwargs = self._build_kwargs(system_prompt, contents, tools, claude_temp, max_output_tokens, tool_choice)

        async with self._client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                yield LLMChunk(text=text)

            message = await stream.get_final_message()
            token_usage = self._extract_usage(message)
            tool_uses = [b for b in message.content if b.type == "tool_use"]
            if tool_uses:
                tc = tool_uses[0]
                yield LLMChunk(
                    function_call=FunctionCall(name=tc.name, args=tc.input or {}),
                    done=True,
                    usage=token_usage,
                )
            else:
                yield LLMChunk(done=True, usage=token_usage)
