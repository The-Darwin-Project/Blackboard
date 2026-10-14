# src/agents/llm/gemini_client.py
# @ai-rules:
# 1. [Constraint]: Only import google.genai inside this file. Never leak SDK types outside.
# 2. [Pattern]: _build_config() shared by generate() and generate_stream(). tools=None omits tool config.
# 3. [Gotcha]: generate_content_stream chunk may have .text AND .function_calls -- process both.
# 4. [Pattern]: _convert_tools() converts plain dict schemas to google.genai FunctionDeclaration objects.
# 5. [Gotcha]: Temperature range 0.0-2.0 -- passthrough, no normalization needed.
# 6. [Pattern]: include_thoughts=True enables Gemini's thinking tokens. Check part.thought flag in candidates.
# 7. [Pattern]: _convert_contents() three-way: str (plain) | list[dict] with "role" (structured) | list (multimodal).
# 8. [Pattern]: Structured contents pass through as-is (already Gemini format). Adapter converts image parts to SDK Part objects.
# 9. [Pattern]: QuotaTracker integration: acquire(estimate) pre-request, record(actual) post-response using usage_metadata.total_token_count.
# 10. [Gotcha]: Streaming candidates_token_count is None on final chunk. Always use total_token_count (probe-verified).
# 11. [Pattern]: Google Search grounding removed from adapter-level state. Web search is now a
#     function call tool (google_web_search) with an isolated generateContent handler.
#     Grounding metadata extraction from main session candidates is no longer needed.
# 12. [Pattern]: generate_stream accumulates thought_parts (part.thought=True) separately from last_parts.
#     raw_parts = thought_parts + output_parts (deduped). Provides full context for thought_signature
#     chain preservation across turns. Required for Gemini 3.5+ thought preservation and forward-compatible
#     with models that don't clear thought history.
# 13. [Pattern]: Client init configures explicit HttpRetryOptions (5 attempts, exp backoff, 408/429/5xx).
#     SDK-level retries handle 502/503 before Brain's own retry layer. timeout=180s for long inference.
# 14. [Gotcha]: After the first function_calls chunk, keep consuming the stream (single loop) to capture terminal
#     usage_metadata, thought parts and grounding. The call is held and emitted once in the final done chunk. Drain
#     errors, unreadable trailing chunks (_read_candidates / function_calls parse) and DRAIN_TIMEOUT_S expiry must NOT
#     lose the call (emit it with usage so far); errors before the call still propagate. last_parts is frozen at the
#     function-call chunk (later parts would displace the thought_signature carrier); later text is dropped and extra
#     function calls are logged and dropped.
# 15. [Constraint]: generate_stream closes the SDK stream in the outer finally on EVERY exit (clean end, drain abort,
#     parse error, GeneratorExit, CancelledError) via _close_stream (bounded by ACLOSE_TIMEOUT_S, failures logged).
#     _record_usage runs FIRST in that finally: it is synchronous, so a second cancel cannot skip it. The SDK nests
#     ~6 async generators with bare `async for` (no aclosing), so nothing else closes the HTTP response deterministically.
"""
GeminiAdapter -- LLMPort implementation using google-genai SDK (Vertex AI).

Supports both blocking generate() and streaming generate_stream() via
generate_content / generate_content_stream.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
from collections.abc import AsyncIterator
from typing import Any

from .types import FunctionCall, LLMChunk, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)


def _parse_drain_timeout(raw: str | None, default: float = 15.0) -> float:
    """Parse and validate LLM_STREAM_DRAIN_TIMEOUT_SEC.

    Ensures the value is a valid finite positive float within (0.0, 300.0].
    Falls back to default on parse errors, NaN/Inf, or out-of-bounds values.
    """
    if raw is None or not raw.strip():
        return default
    try:
        val = float(raw)
        if math.isnan(val) or math.isinf(val) or val <= 0.0 or val > 300.0:
            logger.warning(
                "Invalid LLM_STREAM_DRAIN_TIMEOUT_SEC=%r; using default %.1fs",
                raw,
                default,
            )
            return default
        return val
    except (ValueError, TypeError):
        logger.warning(
            "Malformed LLM_STREAM_DRAIN_TIMEOUT_SEC=%r; using default %.1fs",
            raw,
            default,
        )
        return default


class GeminiAdapter:
    """Vertex AI Gemini adapter implementing LLMPort."""

    # Max seconds to wait for the stream tail after a function_call chunk (terminal usage_metadata).
    DRAIN_TIMEOUT_S: float = _parse_drain_timeout(os.getenv("LLM_STREAM_DRAIN_TIMEOUT_SEC"), default=15.0)
    # Bound on closing the SDK stream in generate_stream's finally (same value as Brain's _ACLOSE_TIMEOUT).
    ACLOSE_TIMEOUT_S: float = 5.0

    def __init__(self, project: str, location: str, model_name: str, quota_tracker=None):
        from google import genai
        from google.genai.types import HttpOptions, HttpRetryOptions

        self._client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            http_options=HttpOptions(
                timeout=180 * 1000,
                retry_options=HttpRetryOptions(
                    attempts=5,
                    initial_delay=1.0,
                    max_delay=60.0,
                    exp_base=2.0,
                    http_status_codes=[408, 429, 500, 502, 503, 504],
                ),
            ),
        )
        self._model_name = model_name
        self._tracker = quota_tracker
        logger.info(f"GeminiAdapter initialized: {model_name} (quota_tracker={'yes' if quota_tracker else 'no'})")

    # -----------------------------------------------------------------
    # Quota tracking helpers
    # -----------------------------------------------------------------

    @staticmethod
    def _estimate_tokens(contents: str | list) -> int:
        """Rough pre-request token estimate (char count / 4)."""
        return max(1, len(str(contents)) // 4)

    def _record_usage(self, usage_metadata, estimate: int) -> TokenUsage | None:
        """Extract full TokenUsage from usage_metadata and record with QuotaTracker."""
        if usage_metadata is None:
            return None

        total = getattr(usage_metadata, "total_token_count", None) or 0
        input_t = getattr(usage_metadata, "prompt_token_count", None) or 0
        candidates_t = getattr(usage_metadata, "candidates_token_count", None)
        thinking_t = getattr(usage_metadata, "thoughts_token_count", None) or 0
        cached_t = getattr(usage_metadata, "cached_content_token_count", None) or 0
        tool_use_t = getattr(usage_metadata, "tool_use_prompt_token_count", None) or 0

        # Streaming: candidates_token_count is None on final chunk (@ai-shebang Rule 10).
        # cached_t and tool_use_t are sub-breakdowns OF input_t — don't subtract them.
        if candidates_t is None and total > 0:
            candidates_t = max(0, total - input_t - thinking_t)
        output_t = candidates_t or 0

        if self._tracker and total:
            self._tracker.record(total, estimate)
            stats = self._tracker.get_stats()
            logger.debug(
                f"LLM usage: {total} tokens (est={estimate}), "
                f"bucket={stats['utilization_pct']}%"
            )

        return TokenUsage(
            input_tokens=input_t,
            output_tokens=output_t,
            thinking_tokens=thinking_t,
            cached_tokens=cached_t,
            tool_use_tokens=tool_use_t,
            total_tokens=total,
            model_version=self._model_name,
        )

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
            tool_objects = [self._convert_tools(tools)]
            kwargs["tools"] = tool_objects
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
                    if "thought_signature" in p:
                        import base64
                        restored = dict(p)
                        sig = restored["thought_signature"]
                        try:
                            restored["thought_signature"] = base64.b64decode(sig) if isinstance(sig, str) else sig
                        except Exception:
                            pass
                        parts.append(restored)
                    else:
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
        thinking_level: str = "",
        tool_choice: dict | None = None,
    ) -> LLMResponse:
        config = self._build_config(system_prompt, tools, temperature, top_p, max_output_tokens, thinking_level)

        estimate = self._estimate_tokens(contents)
        if self._tracker:
            await self._tracker.acquire(estimate)

        response = await self._client.aio.models.generate_content(
            model=self._model_name,
            contents=self._convert_contents(contents),
            config=config,
        )

        token_usage = self._record_usage(getattr(response, "usage_metadata", None), estimate)

        raw_parts = None
        if response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    raw_parts = candidate.content.parts

        if response.function_calls:
            fc = response.function_calls[0]
            return LLMResponse(
                function_call=FunctionCall(name=fc.name, args=fc.args or {}),
                text=response.text,
                raw_parts=raw_parts,
                usage=token_usage,
            )
        return LLMResponse(text=response.text, raw_parts=raw_parts, usage=token_usage)

    # -----------------------------------------------------------------
    # LLMPort: generate_stream (async iterator)
    # -----------------------------------------------------------------

    @staticmethod
    def _is_thought_part(part) -> bool:
        return hasattr(part, 'thought') and part.thought

    def _read_candidates(self, chunk) -> tuple[list | None, list, dict | None]:
        """Parse a chunk's candidates without mutating adapter/stream state.

        Returns (parts, thought_parts, grounding): parts of the last candidate that has any (None if none),
        thought parts in wire order, and the last grounding summary (None if none). May raise on malformed
        chunks -- the caller decides whether that is fatal (@ai-rules 14).
        """
        parts = None
        thoughts: list = []
        grounding = None
        for candidate in chunk.candidates or []:
            if candidate.content and candidate.content.parts:
                parts = candidate.content.parts
                thoughts.extend(p for p in parts if self._is_thought_part(p))
            if hasattr(candidate, "grounding_metadata") and candidate.grounding_metadata:
                gm = candidate.grounding_metadata
                grounding = {
                    "queries": list(gm.web_search_queries or []),
                    "chunks": [
                        {"title": c.web.title, "uri": c.web.uri}
                        for c in (gm.grounding_chunks or [])
                        if hasattr(c, "web") and c.web
                    ],
                }
        return parts, thoughts, grounding

    async def _close_stream(self, stream_iter: Any) -> None:
        """Best-effort bounded aclose of the SDK stream; failures are logged, never raised."""
        aclose_fn = getattr(stream_iter, "aclose", None)
        if not callable(aclose_fn):
            return

        async def _bounded_close() -> None:
            try:
                await asyncio.wait_for(aclose_fn(), timeout=self.ACLOSE_TIMEOUT_S)
            except Exception as e:
                logger.warning("Gemini stream close failed (%s: %s)", type(e).__name__, e)

        try:
            close_task = asyncio.create_task(_bounded_close())
            await asyncio.shield(close_task)
        except asyncio.CancelledError as e:
            logger.warning("Gemini stream close failed (%s: %s)", type(e).__name__, e)

    async def generate_stream(
        self,
        system_prompt: str,
        contents: str | list,
        tools: list[dict] | None = None,
        temperature: float = 0.8,
        top_p: float = 0.95,
        max_output_tokens: int = 65000,
        thinking_level: str = "",
        tool_choice: dict | None = None,
    ) -> AsyncIterator[LLMChunk]:
        config = self._build_config(system_prompt, tools, temperature, top_p, max_output_tokens, thinking_level)

        estimate = self._estimate_tokens(contents)
        if self._tracker:
            await self._tracker.acquire(estimate)

        stream = await self._client.aio.models.generate_content_stream(
            model=self._model_name,
            contents=self._convert_contents(contents),
            config=config,
        )
        drain_timeout = _parse_drain_timeout(
            os.getenv("LLM_STREAM_DRAIN_TIMEOUT_SEC"), default=self.DRAIN_TIMEOUT_S
        )
        token_usage: TokenUsage | None = None
        thought_parts: list = []
        last_parts = None
        last_usage = None
        last_grounding = None
        pending_fc = None
        dropped_fcs = 0
        drain_deadline = 0.0
        stream_iter = stream.__aiter__()
        loop = asyncio.get_running_loop()
        try:
            while True:
                try:
                    if pending_fc is None:
                        chunk = await stream_iter.__anext__()
                    else:
                        remaining = drain_deadline - loop.time()
                        if remaining <= 0:
                            logger.warning(
                                "Gemini stream drain timeout expired (%.1fs); emitting function_call without trailing metadata",
                                drain_timeout,
                            )
                            break
                        chunk = await asyncio.wait_for(stream_iter.__anext__(), timeout=remaining)
                except StopAsyncIteration:
                    break
                except (Exception, asyncio.CancelledError) as e:
                    if pending_fc is None:
                        raise
                    # Never lose a received function call to a tail failure or mid-drain cancellation.
                    err_detail = str(e) or ("timed out" if isinstance(e, (asyncio.TimeoutError, TimeoutError)) else "cancelled")
                    logger.warning(
                        "Gemini stream drain interrupted (%s: %s); emitting function_call without trailing metadata",
                        type(e).__name__,
                        err_detail,
                    )
                    break

                # Parse before touching state (and before any yield) so a malformed chunk during the drain
                # can't drop the held call. Terminal usage is captured if present.
                try:
                    if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
                        last_usage = chunk.usage_metadata
                    chunk_parts, chunk_thoughts, chunk_grounding = self._read_candidates(chunk)
                    chunk_fcs = chunk.function_calls or []
                except (Exception, asyncio.CancelledError) as e:
                    if pending_fc is None:
                        raise
                    err_detail = str(e) or ("timed out" if isinstance(e, (asyncio.TimeoutError, TimeoutError)) else "cancelled")
                    logger.warning(
                        "Gemini stream drain candidate parsing failed (%s: %s); emitting function_call without trailing metadata",
                        type(e).__name__,
                        err_detail,
                    )
                    break

                # Frozen once a function call is held: a later chunk's parts would replace the
                # function_call part (carrier of thought_signature) in raw_parts (@ai-rules 14).
                if chunk_parts is not None and pending_fc is None:
                    last_parts = chunk_parts
                thought_parts.extend(chunk_thoughts)
                if chunk_grounding is not None:
                    last_grounding = chunk_grounding
                for part in chunk_thoughts:
                    if hasattr(part, "text") and part.text:
                        yield LLMChunk(text=part.text, is_thought=True)

                if pending_fc is not None:
                    # Draining: only usage, thoughts and grounding are kept; text and extra calls are dropped.
                    dropped_fcs += len(chunk_fcs)
                    continue

                if chunk.text:
                    yield LLMChunk(text=chunk.text)

                if chunk_fcs:
                    pending_fc = chunk_fcs[0]
                    dropped_fcs += len(chunk_fcs) - 1
                    drain_deadline = loop.time() + drain_timeout
        finally:
            # Runs on clean end, drain abort, error, cancel and aclose (@ai-rules 15). Usage first: it is
            # synchronous, so a second cancel can't skip it; then close the SDK stream.
            try:
                token_usage = self._record_usage(last_usage, estimate)
            finally:
                await self._close_stream(stream_iter)

        if dropped_fcs:
            logger.warning(f"Gemini stream returned {dropped_fcs} additional function_call(s); only the first is used")
        if last_grounding:
            logger.debug(f"Google Search grounding: {len(last_grounding.get('chunks', []))} sources, queries={last_grounding.get('queries', [])}")
        output_parts = [p for p in (last_parts or []) if not self._is_thought_part(p)]
        all_parts = thought_parts + output_parts
        yield LLMChunk(
            function_call=FunctionCall(name=pending_fc.name, args=pending_fc.args or {}) if pending_fc else None,
            done=True,
            raw_parts=all_parts,
            grounding_metadata=last_grounding,
            usage=token_usage,
        )
