# src/agents/llm/gemini_client.py
# @ai-rules:
# 1. [Constraint]: Only import google.genai inside this file. Never leak SDK types outside.
# 2. [Pattern]: _build_config() shared by generate(), generate_stream(), and create_chat(). tools=None omits tool config.
# 3. [Gotcha]: generate_content_stream chunk may have .text AND .function_calls -- process both.
# 4. [Pattern]: _convert_tools() converts plain dict schemas to google.genai FunctionDeclaration objects.
# 5. [Gotcha]: Temperature range 0.0-2.0 -- passthrough, no normalization needed.
# 6. [Pattern]: include_thoughts=True enables Gemini's thinking tokens. Check part.thought flag in candidates.
# 7. [Pattern]: _process_stream_chunks() shared by generate_stream(), chat_send(), and chat_report_tool_result().
# 8. [Gotcha]: Part.from_function_response must be passed directly to send_message, NOT wrapped in Content().
# 9. [Pattern]: _chats dict stores active AsyncChat sessions. _pending_fc tracks function calls awaiting results.
"""
GeminiAdapter -- LLMPort implementation using google-genai SDK (Vertex AI).

Supports stateless generate/generate_stream and session-based
chat_send/chat_report_tool_result via AsyncChat.
"""
from __future__ import annotations

import logging
import uuid
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
        self._chats: dict = {}
        self._pending_fc: dict[str, FunctionCall] = {}
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
    ):
        """Build GenerateContentConfig from method args."""
        from google.genai import types

        kwargs: dict = {
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_output_tokens,
            # Enable thinking tokens -- streamed as part.thought=True before the response
            "thinking_config": types.ThinkingConfig(include_thoughts=True),
        }
        if system_prompt:
            kwargs["system_instruction"] = system_prompt
        if tools is not None:
            kwargs["tools"] = [self._convert_tools(tools)]
            kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)

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
        """Convert provider-agnostic contents to google-genai format."""
        if isinstance(contents, str):
            return contents
        # Multimodal: (text, {"bytes": bytes, "mime_type": str})
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
    # Shared: chunk processing for all streaming paths
    # -----------------------------------------------------------------

    async def _process_stream_chunks(self, stream) -> AsyncIterator[LLMChunk]:
        """Shared chunk processing for generate_stream, chat_send, chat_report_tool_result."""
        async for chunk in stream:
            if chunk.candidates:
                for candidate in chunk.candidates:
                    if candidate.content and candidate.content.parts:
                        for part in candidate.content.parts:
                            if hasattr(part, 'thought') and part.thought and hasattr(part, 'text') and part.text:
                                yield LLMChunk(text=part.text, is_thought=True)

            if chunk.text:
                yield LLMChunk(text=chunk.text)

            if chunk.function_calls:
                fc = chunk.function_calls[0]
                yield LLMChunk(
                    function_call=FunctionCall(name=fc.name, args=fc.args or {}),
                    done=True,
                )
                return

        yield LLMChunk(done=True)

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
        config = self._build_config(system_prompt, tools, temperature, top_p, max_output_tokens)

        stream = await self._client.aio.models.generate_content_stream(
            model=self._model_name,
            contents=self._convert_contents(contents),
            config=config,
        )
        async for chunk in self._process_stream_chunks(stream):
            yield chunk

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
        config = self._build_config(system_prompt, tools, temperature, top_p, max_output_tokens)
        chat = self._client.aio.chats.create(model=self._model_name, config=config)
        session_id = str(uuid.uuid4())
        self._chats[session_id] = chat
        logger.debug(f"Chat session created: {session_id}")
        return session_id

    async def chat_send(
        self,
        session_id: str,
        contents: str | list,
    ) -> AsyncIterator[LLMChunk]:
        chat = self._chats.get(session_id)
        if not chat:
            raise ValueError(f"Unknown chat session: {session_id}")

        stream = await chat.send_message_stream(self._convert_contents(contents))
        async for chunk in self._process_stream_chunks(stream):
            if chunk.function_call:
                self._pending_fc[session_id] = chunk.function_call
            yield chunk

    async def chat_report_tool_result(
        self,
        session_id: str,
        function_name: str,
        result: str,
    ) -> AsyncIterator[LLMChunk]:
        chat = self._chats.get(session_id)
        if not chat:
            raise ValueError(f"Unknown chat session: {session_id}")
        self._pending_fc.pop(session_id, None)

        from google.genai import types
        part = types.Part.from_function_response(
            name=function_name, response={"result": result},
        )
        stream = await chat.send_message_stream(part)
        async for chunk in self._process_stream_chunks(stream):
            if chunk.function_call:
                self._pending_fc[session_id] = chunk.function_call
            yield chunk

    def close_chat(self, session_id: str) -> None:
        self._chats.pop(session_id, None)
        self._pending_fc.pop(session_id, None)
        logger.debug(f"Chat session closed: {session_id}")
