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
# 11. [Pattern]: search_enabled/grounding_corpus are per-call keyword args, NOT adapter-instance state.
#     Singleton shared across N concurrent ReconcileScheduler workers — instance-attribute toggles would race.
# 12. [Pattern]: generate_stream uses shared _map_one_chunk from chat_session.py. It KEEPS its early-return
#     on FC (old path behavior preserved). ChatSessionManager.send_stream does NOT early-return (new path).
#     This is the behavioral split documented in the Chat Session Bridge plan.
# 13. [Pattern]: Client init configures explicit HttpRetryOptions (5 attempts, exp backoff, 408/429/5xx).
# 14. [Pattern]: `client` property exposes the genai.Client for ChatSessionManager to borrow (single pool).
"""
GeminiAdapter -- LLMPort implementation using google-genai SDK (Vertex AI).

Supports both blocking generate() and streaming generate_stream() via
generate_content / generate_content_stream.
"""
from __future__ import annotations

import logging
from collections.abc import AsyncIterator

from .chat_session import _is_thought_part, _map_one_chunk, _MAX_GROUNDING_FIELD_LEN, _truncate_field
from .types import FunctionCall, LLMChunk, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)

_MAX_GROUNDING_CHUNKS = 20  # defense-in-depth cap on untrusted grounding_chunks count
# _MAX_GROUNDING_FIELD_LEN imported from chat_session (shared constant)


class GeminiAdapter:
    """Vertex AI Gemini adapter implementing LLMPort."""

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

    @property
    def client(self):
        """Public accessor for ChatSessionManager to borrow the shared genai.Client."""
        return self._client

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
        search_enabled: bool = False,
        grounding_corpus: str | None = None,
    ):
        """Build GenerateContentConfig from method args.

        search_enabled/grounding_corpus are explicit per-call params (not adapter state) --
        this adapter instance is shared across concurrent calls for different events.
        """
        from google.genai import types

        # Self-enforced mutual exclusion (codereview finding): the untested 3-way tool
        # combination (functions + google_search + retrieval) must never be assembled,
        # regardless of caller discipline. Brain's _resolve_grounding_mode() already
        # resolves this before calling in, but this adapter is a shared, provider-level
        # boundary -- it must not rely solely on one caller's correctness, mirroring how
        # LiveAPIAdapter._build_live_tools() self-enforces the same invariant internally.
        if search_enabled and grounding_corpus:
            logger.warning(
                "GeminiAdapter._build_config: search_enabled and grounding_corpus both set -- "
                "dropping grounding_corpus to avoid the untested 3-way tool combination "
                "(caller should resolve this via Brain._resolve_grounding_mode-style logic)",
            )
            grounding_corpus = None

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
            if search_enabled:
                tool_objects.append(types.Tool(google_search=types.GoogleSearch()))
            if grounding_corpus:
                tool_objects.append(self._build_rag_tool(types, grounding_corpus))
            kwargs["tools"] = tool_objects
            kwargs["automatic_function_calling"] = types.AutomaticFunctionCallingConfig(disable=True)
            kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(mode="AUTO")
            )
        elif search_enabled:
            # grounding_corpus is guaranteed None here -- the mutual-exclusion guard above
            # already nulls it whenever search_enabled is True (codereview finding: the
            # prior version of this branch had a dead `if grounding_corpus:` check).
            kwargs["tools"] = [types.Tool(google_search=types.GoogleSearch())]
        elif grounding_corpus:
            kwargs["tools"] = [self._build_rag_tool(types, grounding_corpus)]

        return types.GenerateContentConfig(**kwargs)

    @staticmethod
    def _build_rag_tool(types, grounding_corpus: str):
        """Build Tool(retrieval=VertexRagStore) for RAG Engine grounding (no store_context)."""
        return types.Tool(retrieval=types.Retrieval(
            vertex_rag_store=types.VertexRagStore(
                rag_resources=[types.VertexRagStoreRagResource(
                    rag_corpus=grounding_corpus,
                )],
            ),
        ))

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
        search_enabled: bool = False,
        grounding_corpus: str | None = None,
    ) -> LLMResponse:
        config = self._build_config(
            system_prompt, tools, temperature, top_p, max_output_tokens, thinking_level,
            search_enabled=search_enabled, grounding_corpus=grounding_corpus,
        )

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
        search_enabled: bool = False,
        grounding_corpus: str | None = None,
    ) -> AsyncIterator[LLMChunk]:
        config = self._build_config(
            system_prompt, tools, temperature, top_p, max_output_tokens, thinking_level,
            search_enabled=search_enabled, grounding_corpus=grounding_corpus,
        )

        estimate = self._estimate_tokens(contents)
        if self._tracker:
            await self._tracker.acquire(estimate)

        stream = await self._client.aio.models.generate_content_stream(
            model=self._model_name,
            contents=self._convert_contents(contents),
            config=config,
        )
        thought_parts: list = []
        last_parts_ref: list = [None]
        last_usage_ref: list = [None]
        last_grounding_ref: list = [None]

        async for chunk in stream:
            mapped = _map_one_chunk(
                chunk,
                thought_parts=thought_parts,
                last_parts_ref=last_parts_ref,
                last_usage_ref=last_usage_ref,
                last_grounding_ref=last_grounding_ref,
                estimate=estimate,
                record_usage_fn=self._record_usage,
            )
            if mapped:
                for llm_chunk in mapped:
                    yield llm_chunk
                    # OLD PATH: early-return on FC (preserved — this is the
                    # behavioral split the plan documents)
                    if llm_chunk.function_call:
                        return

        token_usage = self._record_usage(last_usage_ref[0], estimate)
        if last_grounding_ref[0] and last_grounding_ref[0].get("chunks"):
            logger.debug(f"Grounding: {len(last_grounding_ref[0].get('chunks', []))} sources, queries={last_grounding_ref[0].get('queries', [])}")
        elif search_enabled or grounding_corpus:
            logger.info(
                "Grounding attempted (search_enabled=%s, corpus=%s) but no chunks returned",
                search_enabled, bool(grounding_corpus),
            )
        output_parts = [p for p in (last_parts_ref[0] or []) if not _is_thought_part(p)]
        all_parts = thought_parts + output_parts
        yield LLMChunk(done=True, raw_parts=all_parts, grounding_metadata=last_grounding_ref[0], usage=token_usage)
