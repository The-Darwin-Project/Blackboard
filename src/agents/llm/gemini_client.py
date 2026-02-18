# src/agents/llm/gemini_client.py
# @ai-rules:
# 1. [Constraint]: Only import google.genai inside this file. Never leak SDK types outside.
# 2. [Pattern]: _build_config() shared by generate() and generate_stream(). tools=None omits tool config.
# 3. [Gotcha]: generate_content_stream chunk may have .text AND .function_calls -- process both.
# 6. [Pattern]: include_thoughts=True enables Gemini's thinking tokens. Check part.thought flag in candidates.
# 4. [Pattern]: _convert_tools() converts plain dict schemas to google.genai FunctionDeclaration objects.
# 5. [Gotcha]: Temperature range 0.0-2.0 -- passthrough, no normalization needed.
# 7. [Pattern]: _convert_contents() three-way: str (plain) | list[dict] with "role" (structured) | list (multimodal).
# 8. [Pattern]: Structured contents pass through as-is (already Gemini format). Adapter converts image parts to SDK Part objects.
"""
GeminiAdapter -- LLMPort implementation using google-genai SDK (Vertex AI).

Supports both blocking generate() and streaming generate_stream() via
generate_content / generate_content_stream.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from .types import FunctionCall, LLMChunk, LLMResponse

logger = logging.getLogger(__name__)


class GeminiAdapter:
    """Vertex AI Gemini adapter implementing LLMPort."""

    def __init__(self, project: str, location: str, model_name: str):
        from google import genai

        self._client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
        )
        self._model_name = model_name
        logger.info(f"GeminiAdapter initialized: {model_name}")

    # -----------------------------------------------------------------
    # Shared helpers
    # -----------------------------------------------------------------

    def _build_config(
        self,
        system_prompt: str,
        tools: list[dict] | None,
        temperature: float,
        top_p: float,
        max_output_tokens: int,
        thinking_level: str = "",
    ):
        """Build GenerateContentConfig from method args."""
        from google.genai import types

        thinking_kwargs: dict = {"include_thoughts": True}
        if thinking_level:
            thinking_kwargs["thinking_level"] = thinking_level

        kwargs: dict = {
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_output_tokens,
            "thinking_config": types.ThinkingConfig(**thinking_kwargs),
        }
        if system_prompt:
            kwargs["system_instruction"] = system_prompt
        if tools is not None:
            kwargs["tools"] = [self._convert_tools(tools)]
            kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
            kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            )

        return types.GenerateContentConfig(**kwargs)

    @staticmethod
    def _convert_tools(schemas: list[dict]):
        """Convert plain dict tool schemas to google-genai Tool object."""
        from google.genai import types

        declarations = []
        for s in schemas:
            declarations.append(types.FunctionDeclaration(
                name=s["name"],
                description=s["description"],
                parameters_json_schema=s["input_schema"],
            ))
        return types.Tool(function_declarations=declarations)

    def _convert_contents(self, contents: str | list):
        """Convert provider-agnostic contents to google-genai format.

        Three input formats:
        - str: plain text (Aligner, simple prompts)
        - list[dict] with "role" key: structured multi-turn (Brain)
        - list[str | dict]: multimodal (text + images)
        """
        if isinstance(contents, str):
            return contents

        # Structured multi-turn: [{role, parts}] -- convert image parts, pass through rest
        if contents and isinstance(contents[0], dict) and "role" in contents[0]:
            return self._convert_structured(contents)

        # Multimodal: [text_str, {"bytes": bytes, "mime_type": str}]
        return self._convert_multimodal(contents)

    def _convert_multimodal(self, contents: list):
        """Convert provider-agnostic multimodal list to google-genai Parts."""
        from google.genai import types
        parts = []
        for item in contents:
            if isinstance(item, str):
                parts.append(types.Part.from_text(text=item))
            elif isinstance(item, dict) and "bytes" in item:
                parts.append(types.Part.from_bytes(
                    data=item["bytes"],
                    mime_type=item["mime_type"],
                ))
        return parts

    def _convert_structured(self, contents: list[dict]):
        """Convert structured [{role, parts}] to google-genai Content objects.

        Text and thought_signature parts pass through as dicts (SDK accepts them).
        Image parts ({"bytes": ...}) are converted to SDK Part objects.
        """
        from google.genai import types
        converted = []
        for msg in contents:
            role = msg["role"]
            parts = []
            for p in msg.get("parts", []):
                if isinstance(p, dict) and "bytes" in p:
                    parts.append(types.Part.from_bytes(
                        data=p["bytes"], mime_type=p["mime_type"],
                    ))
                elif isinstance(p, dict):
                    parts.append(p)
                else:
                    parts.append(p)
            converted.append(types.Content(role=role, parts=parts))
        return converted

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
        config = self._build_config(system_prompt, tools, temperature, top_p, max_output_tokens)

        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=self._convert_contents(contents),
            config=config,
        )

        if response.function_calls:
            fc = response.function_calls[0]
            return LLMResponse(
                function_call=FunctionCall(name=fc.name, args=fc.args or {}),
                text=response.text,
            )
        return LLMResponse(text=response.text)

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
        thinking_level: str = "",
    ) -> AsyncIterator[LLMChunk]:
        config = self._build_config(system_prompt, tools, temperature, top_p, max_output_tokens, thinking_level)

        stream = await self._client.aio.models.generate_content_stream(
            model=self._model_name,
            contents=self._convert_contents(contents),
            config=config,
        )
        last_parts = None
        async for chunk in stream:
            # Accumulate last candidate parts for thought_signature preservation
            if chunk.candidates:
                for candidate in chunk.candidates:
                    if candidate.content and candidate.content.parts:
                        last_parts = candidate.content.parts
                        for part in candidate.content.parts:
                            if hasattr(part, 'thought') and part.thought and hasattr(part, 'text') and part.text:
                                yield LLMChunk(text=part.text, is_thought=True)

            # Regular text chunks (non-thought)
            if chunk.text:
                yield LLMChunk(text=chunk.text)

            # Function call (final chunk)
            if chunk.function_calls:
                fc = chunk.function_calls[0]
                yield LLMChunk(
                    function_call=FunctionCall(name=fc.name, args=fc.args or {}),
                    done=True,
                    raw_parts=last_parts,
                )
                return

        yield LLMChunk(done=True, raw_parts=last_parts)
