# src/agents/llm/claude_client.py
# @ai-rules:
# 1. [Constraint]: Import anthropic only here; never leak SDK types.
# 2. [Pattern]: _build_kwargs() shared by generate()/generate_stream(); tools=None omits tools.
# 3. [Gotcha]: Never send temperature+top_p; normalize temperature (0-2 -> 0-1). Claude 5.x omits temperature and downgrades tool_choice "tool"/"any" -> "auto".
# 4. [Pattern]: AsyncAnthropicVertex auth (Brain SA key). _convert_contents handles str | structured | multimodal.
# 5. [Pattern]: _extract_usage sums input + cache_read + cache_creation + output.
# 6. [Gotcha]: priority/thinking_level are LLMPort no-ops; pass tool_choice/priority/thinking_level by keyword.
# 7. [Constraint]: _build_kwargs clamps max_tokens per model family (3.0:4096, 3.5:8192, Opus 4/4.1:32000, 3.7/4.x:64000, 5.x:unclamped); generate() caps unary at 21333.
# 8. [Constraint]: generate_stream delegates to _stream_chunks with SSE liveness heartbeats; _convert_structured drops thought/empty dicts.
"""ClaudeAdapter -- LLMPort implementation via Vertex AI."""
from __future__ import annotations

import logging
import re
from collections.abc import AsyncIterator

from .types import FunctionCall, LLMChunk, LLMResponse, TokenUsage, PRIORITY_NORMAL

logger = logging.getLogger(__name__)

_CLAUDE_5_RE = re.compile(r"(?:sonnet|opus|haiku|fable|mythos)[-.]?5(?!\d)|claude-5(?!\d)")


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
        """Extract TokenUsage from Anthropic message.usage.

        Anthropic bills three distinct input categories:
          input_tokens        — uncached prompt tokens (cache misses)
          cache_read_input_tokens  — served from cache (cache hits)
          cache_creation_input_tokens — written to cache (billed at 1.25x)
        All three are non-overlapping; total = sum of all + output.
        """
        usage = getattr(message, "usage", None)
        if usage is None:
            return None
        input_t = getattr(usage, "input_tokens", None) or 0
        output_t = getattr(usage, "output_tokens", None) or 0
        cache_read = getattr(usage, "cache_read_input_tokens", None) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", None) or 0
        total_input = input_t + cache_read + cache_create
        return TokenUsage(
            input_tokens=total_input,
            output_tokens=output_t,
            cached_tokens=cache_read + cache_create,
            total_tokens=total_input + output_t,
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
        if isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
            max_output_tokens = 65000
        messages = self._convert_contents(contents)
        model_lower = (getattr(self, "_model_name", "") or "").lower()
        clamped_tokens = max_output_tokens
        if any(pat in model_lower for pat in ("claude-3-5", "claude-3.5")):
            clamped_tokens = min(max_output_tokens, 8192)
        elif any(pat in model_lower for pat in ("claude-3-7", "claude-3.7")):
            clamped_tokens = min(max_output_tokens, 64000)
        elif any(
            pat in model_lower
            for pat in ("claude-3-haiku", "claude-3-opus", "claude-3-sonnet", "claude-3.0")
        ):
            clamped_tokens = min(max_output_tokens, 4096)
        elif any(
            pat in model_lower
            for pat in ("opus-4-5", "opus-4.5", "opus-4-6", "opus-4.6")
        ):
            clamped_tokens = min(max_output_tokens, 64000)
        elif any(
            pat in model_lower
            for pat in ("claude-opus-4", "opus-4-0", "opus-4.0", "opus-4-1", "opus-4.1", "opus-4@", "opus-4-20")
        ):
            clamped_tokens = min(max_output_tokens, 32000)
        elif any(
            pat in model_lower
            for pat in ("claude-4", "sonnet-4", "haiku-4", "opus-4")
        ):
            clamped_tokens = min(max_output_tokens, 64000)

        kwargs: dict = {
            "model": self._model_name,
            "max_tokens": clamped_tokens,
            "messages": messages,
        }
        is_claude_5 = bool(_CLAUDE_5_RE.search(model_lower))
        if not is_claude_5:
            kwargs["temperature"] = temperature
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools is not None:
            kwargs["tools"] = self._convert_tools(tools)
            if tool_choice:
                if is_claude_5 and isinstance(tool_choice, dict) and tool_choice.get("type") in ("tool", "any"):
                    logger.warning("Downgrading tool_choice=%s to auto for %s", tool_choice, self._model_name)
                    kwargs["tool_choice"] = {"type": "auto"}
                else:
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
        functionCall parts -> tool_use content blocks tracked in FIFO pending_tool_ids.
        functionResponse parts -> tool_result blocks emitted strictly before text/image blocks.
        """
        import base64

        def _encode_image(part: dict) -> dict:
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": part["mime_type"],
                    "data": base64.b64encode(part["bytes"]).decode(),
                },
            }

        messages: list[dict] = []
        tool_call_counter = 0
        pending_tool_ids: list[str] = []

        for msg in contents:
            role = "assistant" if msg["role"] == "model" else "user"
            parts = msg.get("parts", [])
            blocks: list[dict] = []

            if role == "assistant":
                if not messages or messages[-1]["role"] != "assistant":
                    pending_tool_ids = []
                for p in parts:
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
                        pending_tool_ids.append(tid)
                    elif isinstance(p, dict) and "bytes" in p:
                        blocks.append(_encode_image(p))
                    elif isinstance(p, dict) and not p.get("thought") and p.get("text"):
                        blocks.append({"type": "text", "text": p["text"]})
                    elif isinstance(p, str) and p:
                        blocks.append({"type": "text", "text": p})
            else:
                has_fr = any(isinstance(p, dict) and "functionResponse" in p for p in parts)
                if has_fr:
                    fr_blocks: list[dict] = []
                    other_blocks: list[dict] = []
                    for p in parts:
                        if isinstance(p, dict) and "functionResponse" in p:
                            fr = p["functionResponse"]
                            if pending_tool_ids:
                                tid = pending_tool_ids.pop(0)
                            else:
                                tool_call_counter += 1
                                tid = f"call_{tool_call_counter}"
                            fr_blocks.append({
                                "type": "tool_result",
                                "tool_use_id": tid,
                                "content": str(fr.get("response", "")),
                            })
                        elif isinstance(p, dict) and "bytes" in p:
                            other_blocks.append(_encode_image(p))
                        elif isinstance(p, dict) and not p.get("thought") and p.get("text"):
                            other_blocks.append({"type": "text", "text": p["text"]})
                        elif isinstance(p, str) and p:
                            other_blocks.append({"type": "text", "text": p})
                    while pending_tool_ids:
                        fr_blocks.append({
                            "type": "tool_result",
                            "tool_use_id": pending_tool_ids.pop(0),
                            "content": "(no output)",
                        })
                    blocks = fr_blocks + other_blocks
                elif pending_tool_ids:
                    text_parts: list[str] = []
                    image_blocks: list[dict] = []
                    for p in parts:
                        if isinstance(p, dict) and "bytes" in p:
                            image_blocks.append(_encode_image(p))
                        elif isinstance(p, dict) and not p.get("thought") and p.get("text"):
                            text_parts.append(p["text"])
                        elif isinstance(p, str) and p:
                            text_parts.append(p)
                    wrapped_content = "\n".join(text_parts) if text_parts else "(no output)"
                    for tid in pending_tool_ids:
                        blocks.append({
                            "type": "tool_result",
                            "tool_use_id": tid,
                            "content": wrapped_content,
                        })
                    pending_tool_ids = []
                    blocks.extend(image_blocks)
                else:
                    for p in parts:
                        if isinstance(p, dict) and "bytes" in p:
                            blocks.append(_encode_image(p))
                        elif isinstance(p, dict) and not p.get("thought") and p.get("text"):
                            blocks.append({"type": "text", "text": p["text"]})
                        elif isinstance(p, str) and p:
                            blocks.append({"type": "text", "text": p})

            if blocks:
                if messages and messages[-1]["role"] == role == "user":
                    messages[-1]["content"].extend(blocks)
                    if any(b.get("type") == "tool_result" for b in blocks):
                        tool_results = [b for b in messages[-1]["content"] if b.get("type") == "tool_result"]
                        others = [b for b in messages[-1]["content"] if b.get("type") != "tool_result"]
                        messages[-1]["content"] = tool_results + others
                elif messages and messages[-1]["role"] == role:
                    messages[-1]["content"].extend(blocks)
                else:
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
        thinking_level: str = "",
        tool_choice: dict | None = None,
        priority: int = PRIORITY_NORMAL,
    ) -> LLMResponse:
        # Normalize temperature: 0.0-2.0 -> 0.0-1.0. Drop top_p (Claude rejects both).
        claude_temp = min(temperature / 2.0, 1.0)
        kwargs = self._build_kwargs(system_prompt, contents, tools, claude_temp, max_output_tokens, tool_choice)
        # Anthropic SDK rejects non-streaming messages.create when max_tokens > 128000 / 6 (21333).
        kwargs["max_tokens"] = min(kwargs["max_tokens"], 21333)

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

    def generate_stream(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        max_output_tokens: int = 65000,
        thinking_level: str = "",
        tool_choice: dict | None = None,
        priority: int = PRIORITY_NORMAL,
    ) -> AsyncIterator[LLMChunk]:
        return self._stream_chunks(
            system_prompt=system_prompt,
            contents=contents,
            tools=tools,
            temperature=temperature,
            top_p=top_p,
            max_output_tokens=max_output_tokens,
            thinking_level=thinking_level,
            tool_choice=tool_choice,
            priority=priority,
        )

    async def _stream_chunks(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        max_output_tokens: int = 65000,
        thinking_level: str = "",
        tool_choice: dict | None = None,
        priority: int = PRIORITY_NORMAL,
    ) -> AsyncIterator[LLMChunk]:
        from unittest.mock import NonCallableMock

        claude_temp = min(temperature / 2.0, 1.0)
        kwargs = self._build_kwargs(system_prompt, contents, tools, claude_temp, max_output_tokens, tool_choice)

        async with self._client.messages.stream(**kwargs) as stream:
            use_raw_events = hasattr(stream, "__aiter__") and not (
                isinstance(stream, NonCallableMock)
                and "__aiter__" not in getattr(stream, "__dict__", {})
                and "text_stream" in getattr(stream, "__dict__", {})
            )
            if use_raw_events:
                async for event in stream:
                    if isinstance(event, str):
                        yield LLMChunk(text=event)
                        continue
                    ev_type = getattr(event, "type", None)
                    if ev_type == "content_block_delta":
                        delta = getattr(event, "delta", None)
                        d_type = getattr(delta, "type", None)
                        if d_type == "text_delta":
                            text = getattr(delta, "text", None)
                            if text:
                                yield LLMChunk(text=text)
                            else:
                                yield LLMChunk()
                        elif d_type == "thinking_delta":
                            thinking = getattr(delta, "thinking", None)
                            yield LLMChunk(text=thinking or None, is_thought=True)
                        elif d_type in ("input_json_delta", "signature_delta", "citations_delta"):
                            yield LLMChunk()
                    elif ev_type in ("message_start", "content_block_start"):
                        yield LLMChunk()
            else:
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
