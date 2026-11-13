# src/agents/llm/gemini_client.py
# @ai-rules:
# 1. [Constraint]: Only import google.genai inside this file. Never leak SDK types outside.
# 2. [Pattern]: _build_config() shared by generate() and generate_stream(). tools=None omits tool config.
# 3. [Gotcha]: generate_content_stream chunk may have .text AND .function_calls -- process both.
# 4. [Pattern]: _convert_tools() converts plain dict schemas to google.genai FunctionDeclaration objects.
# 5. [Gotcha]: Temperature range 0.0-2.0 -- passthrough, no normalization needed.
# 6. [Pattern]: include_thoughts=True enables Gemini's thinking tokens. Check part.thought flag in candidates.
# 7. [Pattern]: _convert_contents() three-way: str (plain) | list[dict] with "role" (structured) | list (multimodal).
# 8. [Pattern]: _convert_structured owns Gemini wire-protocol shaping; Brain._build_contents stays
#    provider-agnostic. It sanitizes thought signatures on non-'model' turns, propagates standalone
#    empty-carrier signatures onto model siblings and drops empty/invalid {} parts, splits mixed FR/text
#    user turns, merges consecutive same-kind user/model turns (parts validated via types.Content
#    so no raw dict leaks into Content.parts), inserts a synthetic model "Acknowledged." bridge
#    between non-mergeable consecutive user turns, and closes a trailing model turn (synthetic
#    FR + "Proceed." user turn).
# 9. [Pattern]: QuotaTracker integration: acquire_stream_reservation pre-acquires outside stream TTFB timers
#    (returning mutable [estimate, reservation, handed_off]), and _record_usage records total_token_count post-response.
# 10. [Gotcha]: Streaming candidates_token_count is None on final chunk. Always use total_token_count (probe-verified).
# 11. [Pattern]: Google Search grounding removed from adapter-level state. Web search is now a
#     function call tool (google_web_search) with an isolated generateContent handler.
#     Grounding metadata extraction from main session candidates is no longer needed.
# 12. [Pattern]: generate_stream accumulates thought_parts (part.thought=True) separately from last_parts.
#     raw_parts = thought_parts + output_parts (deduped). Provides full context for thought_signature
#     chain preservation across turns. Required for Gemini 3.5+ thought preservation and forward-compatible
#     with models that don't clear thought history.
# 13. [Pattern]: Client init configures explicit HttpRetryOptions (5 attempts, exp backoff, 408/429/5xx) for unary calls,
#     while generate_stream() overrides per-call HttpRetryOptions(attempts=1..10) via _build_config(http_options=...) so Brain
#     owns stream retry timing (LLM_STREAM_SDK_RETRY_ATTEMPTS override, default 1). HttpOptions.timeout is in MILLISECONDS
#     from LLM_HTTP_TIMEOUT_SEC (default 240s) via types.parse_timeout_env, with class-level _http_timeout_ms fallback for
#     __new__ test fixtures. Ordering invariant: DRAIN (15s) << min(TTFB 35s, INTER 30s) and TOTAL (180s) < HTTP (240s);
#     types.resolve_stream_timeouts resolves (ttfb, inter_chunk, total).
# 14. [Gotcha]: After the first function_calls chunk, keep consuming the stream (single loop) to capture terminal
#     usage_metadata, thought parts, grounding, and trailing thoughtSignature carriers. The call is held and emitted once in
#     the final done chunk. Drain errors, unreadable trailing chunks, and DRAIN_TIMEOUT_S expiry must NOT lose the call.
#     last_parts is frozen at the function-call chunk, except trailing thoughtSignature/thought-carrier chunks clone and
#     attach onto unsigned FC / text / thought parts without mutating SDK Part objects or caller dicts in place.
# 15. [Constraint]: generate_stream is a sync method returning _stream_chunks directly (so await gen.aclose() reaches the
#     async generator without wrapper indirection), recording usage before terminal yield or in outer finally, and closing
#     the SDK stream via _close_stream.
# 16. [Constraint]: Fallback [!call:...!] text is parsed only via types.scan_call_syntax (linear, no regex backtracking).
#     _extract_call_syntax enforces the tool allowlist fail-closed whenever tools is not None (tools=[] allows nothing),
#     walks every tag (first declared + JSON-object wins) and never lets raw syntax into returned text. On streaming
#     holdback overflow the fragment is discarded, later text is suppressed, and the fallback call is NOT executed.
# 17. [Constraint]: Output-token ceilings differ by model generation. On Gemini 4, generate() defaults silently to 65536 via
#     _UNSET_MAX_OUTPUT_TOKENS, pre-acquires quota before stream_start, and streams internally via
#     _stream_chunks(preserve_sdk_retries=True) using total_timeout (180s) on Chunk 0 when TTFB/chunk env vars are unset or
#     equal DEFAULT_STREAM_TTFB_TIMEOUT_S (35s) (preserving the 5-attempt SDK 429/503 retry window under Helm defaults, while
#     clamping any non-default override to min(ttfb_timeout, total_timeout)), breaking on done=True, propagating external
#     task.cancel(), and reassembling multi-chunk visible text in raw_parts; on earlier Gemini models, generate() clamps unary
#     generate_content to 32768.
"""
GeminiAdapter -- LLMPort implementation using google-genai SDK (Vertex AI).

Supports both blocking generate() and streaming generate_stream() via
generate_content / generate_content_stream.
"""
from __future__ import annotations

import asyncio
import copy
import json
import logging
import math
import os
from collections.abc import AsyncIterator
from typing import Any

from .quota_tracker import Reservation
from .types import (
    DEFAULT_CHUNK_TIMEOUT_S,
    DEFAULT_DRAIN_TIMEOUT_S,
    DEFAULT_HTTP_TIMEOUT_S,
    DEFAULT_STREAM_INTER_CHUNK_TIMEOUT_S,
    DEFAULT_STREAM_TOTAL_TIMEOUT_S,
    DEFAULT_STREAM_TTFB_TIMEOUT_S,
    FunctionCall,
    LLMChunk,
    LLMResponse,
    LLMStreamInterChunkTimeoutError,
    LLMStreamTotalTimeoutError,
    LLMStreamTTFBTimeoutError,
    MAX_STREAM_CALL_SYNTAX_BUFFER,
    PRIORITY_NORMAL,
    TokenUsage,
    _MAX_TIMEOUT_ENV_S,
    parse_timeout_env,
    resolve_stream_timeouts,
    sanitize_call_syntax,
    scan_call_syntax,
    split_stream_call_syntax,
    warn_on_timeout_misordering,
)

logger = logging.getLogger(__name__)

# Unary generate_content output-token ceiling (non-Gemini-4). Gemini 4 generate() streams up to 65536.
# Thinking tokens (include_thoughts=True) are counted against max_output_tokens.
_GEMINI_UNARY_MAX_OUTPUT_TOKENS = 32768
_GEMINI_4_MAX_OUTPUT_TOKENS = 65536
_UNSET_MAX_OUTPUT_TOKENS: Any = object()

# Synthetic turn texts used to keep the Gemini wire protocol valid (strict user/model alternation).
_SYNTHETIC_BRIDGE_TEXT = "Acknowledged."
_SYNTHETIC_PROCEED_TEXT = "Proceed."

_NON_CARRIER_PART_FIELDS = (
    "inline_data",
    "file_data",
    "executable_code",
    "code_execution_result",
    "function_response",
    "functionResponse",
)


def _decode_sig_bytes(sig: Any) -> bytes | None:
    """Decode a non-empty thought signature to raw bytes (with UTF-8 fallback)."""
    if not sig or isinstance(sig, bool) or not isinstance(sig, (bytes, bytearray, str)):
        return None
    if isinstance(sig, (bytes, bytearray)):
        return bytes(sig)
    if not sig.strip():
        return None
    import base64
    import binascii

    try:
        return base64.b64decode(sig, validate=True)
    except (ValueError, binascii.Error):
        return sig.encode("utf-8")


def _extract_part_signature(part: Any) -> bytes | None:
    """Extract and decode thought_signature / thoughtSignature from a dict or SDK Part."""
    if isinstance(part, dict):
        return _decode_sig_bytes(part.get("thought_signature")) or _decode_sig_bytes(part.get("thoughtSignature"))
    return _decode_sig_bytes(getattr(part, "thought_signature", None)) or _decode_sig_bytes(
        getattr(part, "thoughtSignature", None)
    )


def _part_has_fc(part: Any) -> bool:
    """True when ``part`` carries a function_call / functionCall."""
    if isinstance(part, dict):
        return bool(part.get("functionCall") or part.get("function_call"))
    return getattr(part, "function_call", None) is not None or getattr(part, "functionCall", None) is not None


def _is_empty_sig_carrier(part: Any) -> bool:
    """True iff ``part`` is an empty-text non-thought non-FC signature carrier."""
    if _extract_part_signature(part) is None:
        return False
    if GeminiAdapter._is_thought_part(part):
        return False
    if _part_has_fc(part):
        return False
    if isinstance(part, dict):
        if "bytes" in part or any(part.get(k) for k in _NON_CARRIER_PART_FIELDS):
            return False
        text = part.get("text")
    else:
        if any(getattr(part, k, None) for k in _NON_CARRIER_PART_FIELDS):
            return False
        text = getattr(part, "text", None)
    return not text


def _clone_part_with_sig(part: Any, sig_bytes: bytes) -> Any:
    """Clone ``part`` with ``thought_signature=sig_bytes`` without mutating the original."""
    if isinstance(part, dict):
        cloned = {k: v for k, v in part.items() if k != "thoughtSignature"}
        cloned["thought_signature"] = sig_bytes
        return cloned
    if hasattr(part, "model_copy"):
        return part.model_copy(update={"thought_signature": sig_bytes})
    cloned = copy.copy(part)
    setattr(cloned, "thought_signature", sig_bytes)
    return cloned


def _attach_signature_to_parts(parts: list, sig_bytes: bytes) -> list:
    """Clone target part(s) in ``parts`` and attach ``thought_signature=sig_bytes``."""
    if not parts:
        return parts
    if any(_part_has_fc(p) for p in parts):
        return [
            _clone_part_with_sig(p, sig_bytes)
            if (_part_has_fc(p) and _extract_part_signature(p) is None)
            else p
            for p in parts
        ]
    non_thought_indices = [
        i for i, p in enumerate(parts)
        if not GeminiAdapter._is_thought_part(p) and not _is_empty_sig_carrier(p)
    ]
    if non_thought_indices:
        target_idx = non_thought_indices[-1]
        if _extract_part_signature(parts[target_idx]) is None:
            updated = list(parts)
            updated[target_idx] = _clone_part_with_sig(parts[target_idx], sig_bytes)
            return updated
        return parts
    if _extract_part_signature(parts[-1]) is None:
        updated = list(parts)
        updated[-1] = _clone_part_with_sig(parts[-1], sig_bytes)
        return updated
    return parts


def _is_function_response_part(part: Any) -> bool:
    """True for a functionResponse/function_response dict or an SDK Part carrying one."""
    if isinstance(part, dict):
        return "function_response" in part or "functionResponse" in part
    return getattr(part, "function_response", None) is not None


def _strip_user_thought_signature(part: Any) -> Any:
    """Strip thought_signature and thoughtSignature from user-bound parts.

    Under Gemini wire protocol, thought signatures are valid strictly on
    role: 'model'. User turns carrying them trigger 400 INVALID_ARGUMENT.
    Preserves the internal 'thought' boolean used for turn merge tracking.
    """
    from google.genai import types

    if isinstance(part, dict):
        cleaned = {
            k: v
            for k, v in part.items()
            if k not in ("thought_signature", "thoughtSignature")
        }
        # If part only carried signature and has no functional keys left, drop it
        if not cleaned:
            return None
        return cleaned

    if isinstance(part, types.Part):
        if hasattr(part, "model_copy"):
            return part.model_copy(update={"thought_signature": None})
        p_copy = copy.copy(part)
        if hasattr(p_copy, "thought_signature"):
            p_copy.thought_signature = None
        return p_copy

    if hasattr(part, "thought_signature") or hasattr(part, "thoughtSignature"):
        p_copy = copy.copy(part)
        for attr in ("thought_signature", "thoughtSignature"):
            if hasattr(p_copy, attr):
                try:
                    setattr(p_copy, attr, None)
                except (AttributeError, TypeError):
                    pass
        return p_copy

    return part


def _coerce_part(part: Any) -> Any:
    """Normalize one structured part for the Gemini SDK.

    Image dicts and tool-response dicts become SDK ``types.Part`` objects; ``thought_signature``
    strings are base64-decoded. Anything else is returned unchanged (``_validated_parts`` is
    responsible for the final dict -> ``types.Part`` validation).
    """
    from google.genai import types

    if isinstance(part, types.Part) or not isinstance(part, dict):
        return part
    if "bytes" in part:
        return types.Part.from_bytes(data=part["bytes"], mime_type=part["mime_type"])
    for key in ("functionResponse", "function_response"):
        if key in part:
            fr = part[key]
            return types.Part.from_function_response(
                name=fr.get("name") or "tool",
                response=fr.get("response") or {},
            )
    if "thoughtSignature" in part or "thought_signature" in part:
        part = dict(part)
        sig_snake = part.pop("thought_signature", None)
        sig_camel = part.pop("thoughtSignature", None)
        decoded = _decode_sig_bytes(sig_snake) or _decode_sig_bytes(sig_camel)
        if decoded is not None:
            part["thought_signature"] = decoded
            return part
        if not part or (set(part.keys()) == {"text"} and not part.get("text")):
            return None
    if not part:
        return None
    if "text" in part and len(part) == 1:
        return types.Part.from_text(text=part["text"])
    return part


def _validated_parts(role: str, parts: list) -> list:
    """Coerce ``parts`` to validated ``types.Part`` objects via ``types.Content``.

    ``list.extend`` on an already-built ``Content.parts`` does not re-validate, so any raw dict
    (e.g. camelCase ``functionCall``) would stay a dict and serialize as ``{}`` on the wire.
    """
    from google.genai import types

    return types.Content(role=role, parts=parts).parts or []


def _append_user_turn(converted: list, u_parts: list, has_fr: bool) -> None:
    """Append user parts, merging with or bridging from the previous user turn.

    A functionResponse-only user turn must not mix with text parts: same-kind consecutive
    user turns merge; different-kind ones are separated by a synthetic model bridge turn.
    """
    from google.genai import types

    if not u_parts:
        return
    if converted and converted[-1].role == "user":
        last_has_fr = any(_is_function_response_part(p) for p in converted[-1].parts or [])
        if last_has_fr == has_fr:
            converted[-1].parts.extend(_validated_parts("user", u_parts))
            return
        logger.debug(
            "Gemini wire adapter: inserting synthetic model bridge between user turns "
            "(previous has_fr=%s, next has_fr=%s)", last_has_fr, has_fr,
        )
        converted.append(
            types.Content(role="model", parts=[types.Part.from_text(text=_SYNTHETIC_BRIDGE_TEXT)])
        )
    converted.append(types.Content(role="user", parts=u_parts))


def _extract_call_syntax(
    text: str | None,
    tools: list[dict] | None = None,
    *,
    warn_unterminated: bool = True,
) -> tuple[FunctionCall | None, str | None]:
    """Parse fallback [!call:name:{args}!] syntax emitted as text by the model.

    Walks EVERY complete tag in order and returns the first one that is both declared and
    carries a JSON-object argument, so an undeclared/invalid earlier tag cannot mask a later
    valid call. When ``tools`` is not None the allowlist is enforced fail-closed (an empty
    list or entries without a name allow nothing); ``tools=None`` means no tool config was
    sent to the model and no allowlist is applied. Returns (FunctionCall | None, cleaned_text);
    cleaned_text never contains any [!call: syntax. Set warn_unterminated=False when the
    caller already logged the unterminated-fragment strip for this response.
    """
    if not text:
        return None, text
    cleaned, calls, tail = scan_call_syntax(text)
    if tail and warn_unterminated:
        logger.warning(
            "Gemini wire adapter: stripped unterminated [!call: fragment (length %d)",
            len(tail),
        )
    cleaned_text = cleaned.strip() or None

    declared_names: set[str] | None = None
    if tools is not None:
        declared_names = {
            s.get("name") if isinstance(s, dict) else getattr(s, "name", None)
            for s in tools
        }
        declared_names.discard(None)

    for fn_name, raw_args in calls:
        if declared_names is not None and fn_name not in declared_names:
            logger.warning(
                "Gemini wire adapter: fallback [!call:%s:...] not in declared tools (%s), ignoring",
                fn_name,
                sorted(declared_names),
            )
            continue
        try:
            parsed_args = json.loads(raw_args)
        except Exception as e:
            logger.warning(
                "Gemini wire adapter: failed to parse fallback [!call:%s:...]: %s",
                fn_name,
                e,
            )
            continue
        if isinstance(parsed_args, dict):
            logger.warning(
                "Gemini wire adapter: parsed fallback [!call:%s:...] from text",
                fn_name,
            )
            return FunctionCall(name=fn_name, args=parsed_args), cleaned_text
        logger.warning(
            "Gemini wire adapter: fallback [!call:%s:...] args not a JSON object (length %d)",
            fn_name,
            len(raw_args),
        )
    return None, cleaned_text


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


DEFAULT_TTFB_TIMEOUT_S: float = DEFAULT_STREAM_TTFB_TIMEOUT_S
DEFAULT_INTER_CHUNK_TIMEOUT_S: float = DEFAULT_STREAM_INTER_CHUNK_TIMEOUT_S
DEFAULT_TOTAL_TIMEOUT_S: float = DEFAULT_STREAM_TOTAL_TIMEOUT_S
_TIMEOUT_ENV_WARNED: set[tuple[str, str | None]] = set()
_TIMEOUT_ORDER_WARNED: set[tuple[float, float, float]] = set()


class GeminiAdapter:
    """Vertex AI Gemini adapter implementing LLMPort."""

    # Max seconds to wait for the stream tail after a function_call chunk (terminal usage_metadata).
    DRAIN_TIMEOUT_S: float = _parse_drain_timeout(os.getenv("LLM_STREAM_DRAIN_TIMEOUT_SEC"), default=DEFAULT_DRAIN_TIMEOUT_S)
    # Bound on closing the SDK stream in generate_stream's finally (same value as Brain's _ACLOSE_TIMEOUT).
    ACLOSE_TIMEOUT_S: float = 5.0
    # Class-level fallbacks for GeminiAdapter.__new__(GeminiAdapter) test fixtures.
    _http_timeout_ms: int = int(DEFAULT_HTTP_TIMEOUT_S * 1000)
    _model_name: str = ""
    _tracker: Any = None

    def __init__(self, project: str, location: str, model_name: str, quota_tracker=None):
        from google import genai
        from google.genai.types import HttpOptions, HttpRetryOptions

        http_timeout_s = parse_timeout_env("LLM_HTTP_TIMEOUT_SEC", os.getenv("LLM_HTTP_TIMEOUT_SEC"), DEFAULT_HTTP_TIMEOUT_S)
        raw_chunk_env = os.getenv("LLM_STREAM_CHUNK_TIMEOUT_SEC")
        if raw_chunk_env is not None and raw_chunk_env.strip():
            chunk_timeout_s = parse_timeout_env("LLM_STREAM_CHUNK_TIMEOUT_SEC", raw_chunk_env, DEFAULT_CHUNK_TIMEOUT_S)
            warn_on_timeout_misordering(self.DRAIN_TIMEOUT_S, chunk_timeout_s, http_timeout_s)
        else:
            ttfb_s, inter_s, total_s = resolve_stream_timeouts()
            warn_on_timeout_misordering(
                self.DRAIN_TIMEOUT_S,
                min(ttfb_s, inter_s),
                float("inf"),
                chunk_label="min(LLM_STREAM_TTFB_TIMEOUT_SEC, LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC)",
            )
            warn_on_timeout_misordering(
                0.0,
                total_s,
                http_timeout_s,
                chunk_label="LLM_STREAM_TOTAL_TIMEOUT_SEC",
            )
            max_phase_s = max(ttfb_s, inter_s)
            if total_s < max_phase_s:
                phase_key = (-1.0, total_s, max_phase_s)
                if phase_key not in _TIMEOUT_ORDER_WARNED:
                    _TIMEOUT_ORDER_WARNED.add(phase_key)
                    logger.warning(
                        "LLM_STREAM_TOTAL_TIMEOUT_SEC (%.1fs) < max(LLM_STREAM_TTFB_TIMEOUT_SEC, "
                        "LLM_STREAM_INTER_CHUNK_TIMEOUT_SEC) (%.1fs): total ceiling is shorter than per-phase timeout",
                        total_s, max_phase_s,
                    )
        http_timeout_ms = int(http_timeout_s * 1000)  # google-genai HttpOptions.timeout is milliseconds
        self._http_timeout_ms = http_timeout_ms
        self._client = genai.Client(
            vertexai=True,
            project=project,
            location=location,
            http_options=HttpOptions(
                timeout=http_timeout_ms,
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

    async def acquire_stream_reservation(
        self, contents: str | list, priority: int = PRIORITY_NORMAL
    ) -> list:
        """Pre-acquire QuotaTracker reservation outside stream TTFB timers.

        Returns mutable ``[estimate, reservation, handed_off]`` state list.
        """
        estimate = self._estimate_tokens(contents)
        reservation = None
        tracker = getattr(self, "_tracker", None)
        if tracker:
            reservation = await tracker.acquire(
                estimate, max_wait_seconds=30.0, priority=priority
            )
        return [estimate, reservation, False]

    def _record_usage(self, usage_metadata, estimate: int, reservation: Reservation | None = None) -> TokenUsage | None:
        """Extract full TokenUsage from usage_metadata and record with QuotaTracker."""
        if usage_metadata is None:
            if self._tracker and isinstance(reservation, Reservation):
                self._tracker.rollback(reservation)
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

        if self._tracker:
            if total > 0:
                if isinstance(reservation, Reservation):
                    self._tracker.record(total, estimate, reservation=reservation)
                else:
                    self._tracker.record(total, estimate)
                stats = self._tracker.get_stats()
                logger.debug(
                    f"LLM usage: {total} tokens (est={estimate}), "
                    f"bucket={stats['utilization_pct']}%"
                )
            elif isinstance(reservation, Reservation):
                self._tracker.rollback(reservation)

        if total <= 0:
            return None

        return TokenUsage(
            input_tokens=input_t,
            output_tokens=output_t,
            thinking_tokens=thinking_t,
            cached_tokens=cached_t,
            tool_use_tokens=tool_use_t,
            total_tokens=total,
            model_version=getattr(self, "_model_name", "") or "",
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
        *,
        http_options: Any = None,
    ):
        """Build GenerateContentConfig from method args."""
        from google.genai import types

        if isinstance(max_output_tokens, bool) or not isinstance(max_output_tokens, int) or max_output_tokens <= 0:
            max_output_tokens = 65000

        model_lower = (getattr(self, "_model_name", "") or "").lower()
        if "gemini-4" in model_lower:
            max_output_tokens = min(max_output_tokens, _GEMINI_4_MAX_OUTPUT_TOKENS)
        elif any(pat in model_lower for pat in ("gemini-1.5", "gemini-2.0")):
            max_output_tokens = min(max_output_tokens, 8192)

        thinking_kwargs: dict = {"include_thoughts": True}
        if "gemini-4" in model_lower:
            raw_level = (thinking_level or "").strip().upper()
            if raw_level in ("MINIMAL", "NONE"):
                thinking_kwargs["thinking_level"] = "LOW"
            elif raw_level in ("LOW", "MEDIUM", "HIGH"):
                thinking_kwargs["thinking_level"] = raw_level
            elif raw_level:
                logger.warning(
                    "Gemini 4 unsupported thinking_level=%r for model %s; normalizing to 'LOW'",
                    thinking_level,
                    getattr(self, "_model_name", ""),
                )
                thinking_kwargs["thinking_level"] = "LOW"
            thinking_kwargs.pop("thinking_budget", None)
        elif thinking_level:
            thinking_kwargs["thinking_level"] = thinking_level

        kwargs: dict = {
            "temperature": temperature,
            "top_p": top_p,
            "max_output_tokens": max_output_tokens,
            "thinking_config": types.ThinkingConfig(**thinking_kwargs),
        }
        if http_options is not None:
            kwargs["http_options"] = http_options
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

        This method owns Gemini wire-protocol shaping (``Brain._build_contents`` stays
        provider-agnostic):

        - Image dicts and functionResponse/function_response dicts become SDK ``types.Part``.
        - User turns mixing functionResponse and text parts are split by kind.
        - Consecutive same-kind user turns (all-FR or all-text) and consecutive model turns are
          merged; merged parts are validated through ``types.Content`` so no raw dict leaks into
          an existing ``Content.parts`` (which would serialize as ``{}``).
        - Consecutive non-mergeable user turns (FR then text, or text then FR) are separated by a
          synthetic model bridge turn ("Acknowledged.").
        - A trailing model turn is closed with synthetic functionResponse / "Proceed." user turns.
        """
        from google.genai import types

        converted: list[types.Content] = []
        for msg in contents:
            role = msg["role"]
            raw_parts = msg.get("parts") or []

            # Gemini wire protocol: user turns with functionResponse MUST NOT contain text parts,
            # and consecutive user turns must alternate with model turns or merge cleanly.
            # In addition, thought and thought_signature are strictly valid only on role: "model".
            if role != "model":
                sanitized_parts = []
                for p in raw_parts:
                    cleaned = _strip_user_thought_signature(p)
                    if cleaned is not None:
                        sanitized_parts.append(cleaned)
                parts = [
                    cp for p in sanitized_parts
                    if (cp := _coerce_part(p)) is not None and cp != {}
                ]
                if role == "user":
                    fr_parts = [p for p in parts if _is_function_response_part(p)]
                    non_fr_parts = [p for p in parts if not _is_function_response_part(p)]
                    _append_user_turn(converted, fr_parts, has_fr=True)
                    _append_user_turn(converted, non_fr_parts, has_fr=False)
                elif parts:
                    converted.append(types.Content(role=role, parts=parts))
            else:
                model_raw = list(raw_parts)
                if any(_is_empty_sig_carrier(p) for p in model_raw):
                    carrier_sig = next(
                        (
                            s
                            for p in model_raw
                            if _is_empty_sig_carrier(p) and (s := _extract_part_signature(p)) is not None
                        ),
                        None,
                    )
                    non_carriers = [p for p in model_raw if not _is_empty_sig_carrier(p)]
                    siblings = [
                        cp for p in non_carriers
                        if (cp := _coerce_part(p)) is not None and cp != {}
                    ]
                    parts = (
                        _attach_signature_to_parts(siblings, carrier_sig)
                        if (siblings and carrier_sig is not None)
                        else siblings
                    )
                else:
                    parts = [
                        cp for p in model_raw
                        if (cp := _coerce_part(p)) is not None and cp != {}
                    ]
                if not parts:
                    continue
                if converted and converted[-1].role == "model":
                    converted[-1].parts.extend(_validated_parts("model", parts))
                else:
                    converted.append(types.Content(role="model", parts=parts))

        # Protocol safety net: requests ending with a model turn are rejected by Gemini with 400.
        if converted and converted[-1].role == "model":
            logger.warning(
                "Gemini wire adapter: trailing model turn detected in payload; "
                "synthesizing user completion."
            )
            unanswered = [
                p.function_call.name
                for p in converted[-1].parts or []
                if getattr(p, "function_call", None) is not None
            ]
            if unanswered:
                frs = [
                    types.Part.from_function_response(
                        name=name or "tool",
                        response={"result": "unknown -- synthetic completion"},
                    )
                    for name in unanswered
                ]
                converted.append(types.Content(role="user", parts=frs))
                converted.append(
                    types.Content(
                        role="model",
                        parts=[types.Part.from_text(text=_SYNTHETIC_BRIDGE_TEXT)],
                    )
                )
            converted.append(
                types.Content(role="user", parts=[types.Part.from_text(text=_SYNTHETIC_PROCEED_TEXT)])
            )

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
        max_output_tokens: int = _UNSET_MAX_OUTPUT_TOKENS,
        thinking_level: str = "",
        tool_choice: dict | None = None,
        priority: int = PRIORITY_NORMAL,
    ) -> LLMResponse:
        """Blocking generateContent call (streams internally on Gemini 4).

        On Gemini 4, defaults silently to 65536 and streams via _stream_chunks(preserve_sdk_retries=True)
        with adaptive timeouts so thinking heartbeats prevent HTTP stalls. On earlier Gemini models,
        clamps unary generate_content to _GEMINI_UNARY_MAX_OUTPUT_TOKENS (32768).
        """
        model_name = getattr(self, "_model_name", "") or ""
        is_gemini_4 = "gemini-4" in model_name.lower()
        ceiling = _GEMINI_4_MAX_OUTPUT_TOKENS if is_gemini_4 else _GEMINI_UNARY_MAX_OUTPUT_TOKENS

        if max_output_tokens is _UNSET_MAX_OUTPUT_TOKENS:
            resolved_tokens = ceiling
        elif not isinstance(max_output_tokens, int) or isinstance(max_output_tokens, bool) or max_output_tokens <= 0:
            logger.warning(
                "Gemini generate(): invalid max_output_tokens=%r for model %s; using default %d",
                max_output_tokens, model_name, ceiling,
            )
            resolved_tokens = ceiling
        elif max_output_tokens > ceiling:
            suffix = "" if is_gemini_4 else "; use generate_stream() for larger outputs"
            logger.warning(
                "Gemini generate(): max_output_tokens clamped for model %s (requested=%d, clamped=%d)%s",
                model_name, max_output_tokens, ceiling, suffix,
            )
            resolved_tokens = ceiling
        else:
            resolved_tokens = max_output_tokens

        if is_gemini_4:
            import contextlib
            import time
            from google.genai import types

            ttfb_timeout, inter_chunk_timeout, total_timeout = resolve_stream_timeouts()
            raw_ttfb_env = (os.getenv("LLM_STREAM_TTFB_TIMEOUT_SEC") or "").strip()
            raw_chunk_env = (os.getenv("LLM_STREAM_CHUNK_TIMEOUT_SEC") or "").strip()
            explicit_ttfb = (
                bool(raw_ttfb_env and ttfb_timeout != DEFAULT_STREAM_TTFB_TIMEOUT_S)
                or bool(raw_chunk_env)
            )
            effective_ttfb = min(ttfb_timeout, total_timeout) if explicit_ttfb else total_timeout
            visible_chunks: list[str] = []
            done_chunk: LLMChunk | None = None
            preacquired = await self.acquire_stream_reservation(contents, priority=priority)
            try:
                stream_gen = self._stream_chunks(
                    system_prompt=system_prompt,
                    contents=contents,
                    tools=tools,
                    temperature=temperature,
                    top_p=top_p,
                    max_output_tokens=resolved_tokens,
                    thinking_level=thinking_level,
                    tool_choice=tool_choice,
                    priority=priority,
                    preserve_sdk_retries=True,
                    _preacquired=preacquired,
                )
                async with contextlib.aclosing(stream_gen) as stream:
                    it = stream.__aiter__()
                    stream_start = time.monotonic()
                    chunk_idx = 0
                    while True:
                        elapsed = 0.0 if chunk_idx == 0 else (time.monotonic() - stream_start)
                        remaining_total = total_timeout - elapsed
                        if remaining_total <= 0:
                            raise LLMStreamTotalTimeoutError(
                                f"Gemini generate() stream exceeded total timeout ({total_timeout}s) for {model_name}"
                            )
                        is_ttfb = chunk_idx == 0
                        phase_timeout = effective_ttfb if is_ttfb else inter_chunk_timeout
                        wait_budget = min(phase_timeout, remaining_total)
                        if is_ttfb:
                            timeout_phase = "ttfb"
                            last_wait_budget = wait_budget
                        elif remaining_total <= phase_timeout:
                            timeout_phase = "total"
                            last_wait_budget = total_timeout
                        else:
                            timeout_phase = "inter-chunk"
                            last_wait_budget = phase_timeout
                        curr_task = asyncio.current_task()
                        pre_cancels = curr_task.cancelling() if curr_task and hasattr(curr_task, "cancelling") else 0
                        try:
                            chunk = await asyncio.wait_for(it.__anext__(), timeout=wait_budget)
                        except StopAsyncIteration:
                            break
                        except asyncio.TimeoutError as te:
                            if curr_task and hasattr(curr_task, "cancelling") and curr_task.cancelling() > pre_cancels:
                                raise asyncio.CancelledError() from None
                            if timeout_phase == "total":
                                raise LLMStreamTotalTimeoutError(
                                    f"Gemini generate() stream exceeded total timeout ({total_timeout}s) for {model_name}"
                                ) from te
                            if timeout_phase == "ttfb":
                                raise LLMStreamTTFBTimeoutError(
                                    f"Gemini generate() stream TTFB timed out after {last_wait_budget}s for {model_name}"
                                ) from te
                            raise LLMStreamInterChunkTimeoutError(
                                f"Gemini generate() stream inter-chunk timed out after {last_wait_budget}s for {model_name}"
                            ) from te
                        if curr_task and hasattr(curr_task, "cancelling") and curr_task.cancelling() > pre_cancels:
                            raise asyncio.CancelledError()
                        chunk_idx += 1
                        if chunk.text and not chunk.is_thought:
                            visible_chunks.append(chunk.text)
                        if chunk.done:
                            done_chunk = chunk
                            break
            finally:
                if getattr(self, "_tracker", None) and preacquired[1] is not None and not preacquired[2]:
                    self._tracker.rollback(preacquired[1])

            visible_text = "".join(visible_chunks) if visible_chunks else None
            clean_text = sanitize_call_syntax(visible_text, warn=False)
            assembled_raw_parts = done_chunk.raw_parts if done_chunk else None
            if (
                done_chunk is not None
                and done_chunk.function_call is None
                and clean_text
                and assembled_raw_parts is not None
            ):
                thoughts_only = [p for p in assembled_raw_parts if self._is_thought_part(p)]
                other_non_text = [
                    p
                    for p in assembled_raw_parts
                    if not self._is_thought_part(p)
                    and not _is_empty_sig_carrier(p)
                    and not (
                        (isinstance(p, dict) and "text" in p and not _part_has_fc(p))
                        or (not isinstance(p, dict) and getattr(p, "text", None) is not None and not _part_has_fc(p))
                    )
                ]
                sig_bytes = next(
                    (
                        s
                        for p in reversed(assembled_raw_parts)
                        if not self._is_thought_part(p) and (s := _extract_part_signature(p)) is not None
                    ),
                    None,
                )
                if sig_bytes is None:
                    sig_bytes = next(
                        (s for p in reversed(thoughts_only) if (s := _extract_part_signature(p)) is not None),
                        None,
                    )
                full_text_part = types.Part(text=clean_text, thought_signature=sig_bytes)
                assembled_raw_parts = thoughts_only + other_non_text + [full_text_part]
            return LLMResponse(
                function_call=done_chunk.function_call if done_chunk else None,
                text=clean_text,
                raw_parts=assembled_raw_parts,
                usage=done_chunk.usage if done_chunk else None,
            )

        config = self._build_config(system_prompt, tools, temperature, top_p, resolved_tokens, thinking_level)

        estimate = self._estimate_tokens(contents)
        reservation = None
        if self._tracker:
            reservation = await self._tracker.acquire(
                estimate, max_wait_seconds=30.0, priority=priority
            )

        reservation_recorded = False
        try:
            response = await self._client.aio.models.generate_content(
                model=self._model_name,
                contents=self._convert_contents(contents),
                config=config,
            )
            token_usage = self._record_usage(getattr(response, "usage_metadata", None), estimate, reservation=reservation)
            reservation_recorded = True
        finally:
            if not reservation_recorded and self._tracker and reservation:
                self._tracker.rollback(reservation)

        raw_parts = None
        if response.candidates:
            for candidate in response.candidates:
                if candidate.content and candidate.content.parts:
                    raw_parts = candidate.content.parts

        if response.function_calls:
            fc = response.function_calls[0]
            clean_text = sanitize_call_syntax(response.text) if response.text else response.text
            return LLMResponse(
                function_call=FunctionCall(name=fc.name, args=fc.args or {}),
                text=clean_text or None,
                raw_parts=raw_parts,
                usage=token_usage,
            )

        fallback_fc, clean_text = _extract_call_syntax(response.text, tools=tools)
        if fallback_fc:
            return LLMResponse(
                function_call=fallback_fc,
                text=clean_text,
                raw_parts=raw_parts,
                usage=token_usage,
            )
        return LLMResponse(text=clean_text, raw_parts=raw_parts, usage=token_usage)

    # -----------------------------------------------------------------
    # LLMPort: generate_stream (async iterator)
    # -----------------------------------------------------------------

    @staticmethod
    def _is_thought_part(part: Any) -> bool:
        if isinstance(part, dict):
            return bool(part.get("thought"))
        return getattr(part, "thought", None) is True

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
        *,
        _preacquired: list | None = None,
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
            preserve_sdk_retries=False,
            _preacquired=_preacquired,
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
        *,
        preserve_sdk_retries: bool = False,
        _preacquired: list | None = None,
    ) -> AsyncIterator[LLMChunk]:
        stream_iter = None
        last_usage = None
        reservation_recorded = False
        estimate = 0
        reservation = None
        if _preacquired is not None:
            estimate, reservation = _preacquired[0], _preacquired[1]
            _preacquired[2] = True
        try:
            http_opts = None
            if not preserve_sdk_retries:
                from google.genai.types import HttpOptions, HttpRetryOptions

                http_timeout_ms = getattr(self, "_http_timeout_ms", int(DEFAULT_HTTP_TIMEOUT_S * 1000))
                raw_attempts = os.getenv("LLM_STREAM_SDK_RETRY_ATTEMPTS", "1")
                try:
                    stream_attempts = min(max(1, int(raw_attempts)), 10)
                except (ValueError, TypeError, OverflowError):
                    stream_attempts = 1
                http_opts = HttpOptions(
                    timeout=http_timeout_ms,
                    retry_options=HttpRetryOptions(attempts=stream_attempts),
                )
            config = self._build_config(
                system_prompt, tools, temperature, top_p, max_output_tokens, thinking_level, http_options=http_opts
            )

            if _preacquired is None:
                estimate, reservation, _ = await self.acquire_stream_reservation(contents, priority=priority)

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
            trailing_sig_bytes: bytes | None = None
            last_grounding = None
            pending_fc = None
            same_chunk_extra_fcs = 0
            drain_dropped_fcs = 0
            drain_deadline = 0.0
            accumulated_stream_text = ""
            stream_text_buffer = ""
            call_syntax_overflowed = False
            stream_iter = stream.__aiter__()
            loop = asyncio.get_running_loop()
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
                    has_substantive = any(
                        not self._is_thought_part(p) and not _is_empty_sig_carrier(p)
                        for p in chunk_parts
                    )
                    last_has_substantive = bool(
                        last_parts
                        and any(not self._is_thought_part(p) and not _is_empty_sig_carrier(p) for p in last_parts)
                    )
                    if not has_substantive and last_has_substantive:
                        carrier_sig = next(
                            (s for p in chunk_parts if (s := _extract_part_signature(p)) is not None),
                            None,
                        )
                        if carrier_sig is not None:
                            trailing_sig_bytes = carrier_sig
                            last_parts = _attach_signature_to_parts(last_parts, carrier_sig)
                    else:
                        if not has_substantive:
                            carrier_sig = next(
                                (s for p in chunk_parts if (s := _extract_part_signature(p)) is not None),
                                None,
                            )
                            if carrier_sig is not None:
                                trailing_sig_bytes = carrier_sig
                        last_parts = chunk_parts
                thought_parts.extend(chunk_thoughts)
                if chunk_grounding is not None:
                    last_grounding = chunk_grounding
                for part in chunk_thoughts:
                    t_text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
                    if t_text:
                        yield LLMChunk(text=t_text, is_thought=True)

                if pending_fc is not None:
                    # Draining: capture any trailing thoughtSignature onto last_parts; drop extra text/FCs.
                    drain_sig = next(
                        (
                            s
                            for p in list(chunk_parts or []) + list(chunk_thoughts or [])
                            if (s := _extract_part_signature(p)) is not None
                        ),
                        None,
                    )
                    if drain_sig is not None:
                        trailing_sig_bytes = drain_sig
                        if last_parts:
                            last_parts = _attach_signature_to_parts(last_parts, drain_sig)
                    drain_dropped_fcs += len(chunk_fcs)
                    continue

                if chunk.text and not call_syntax_overflowed:
                    accumulated_stream_text += chunk.text
                    stream_text_buffer += chunk.text
                    to_yield, stream_text_buffer, overflowed = split_stream_call_syntax(stream_text_buffer)
                    if overflowed:
                        # Oversized unterminated [!call: tail: drop it (never stream it, never execute it)
                        # and ignore all further text for this response (@ai-rules 16).
                        call_syntax_overflowed = True
                        _, _, discarded = scan_call_syntax(accumulated_stream_text)
                        accumulated_stream_text = accumulated_stream_text[: len(accumulated_stream_text) - len(discarded)]
                        logger.warning(
                            "Gemini stream: unterminated [!call: fragment exceeded %d chars; discarded it and "
                            "suppressed the rest of the text stream",
                            MAX_STREAM_CALL_SYNTAX_BUFFER,
                        )
                    if to_yield:
                        yield LLMChunk(text=to_yield)

                if chunk_fcs:
                    pending_fc = chunk_fcs[0]
                    same_chunk_extra_fcs += len(chunk_fcs) - 1
                    drain_deadline = loop.time() + drain_timeout

            unterminated_logged = call_syntax_overflowed
            if stream_text_buffer:
                clean_tail, _, held_fragment = scan_call_syntax(stream_text_buffer)
                if held_fragment:
                    unterminated_logged = True
                    logger.warning(
                        "Gemini stream: stripped unterminated [!call: fragment at stream end (length %d)",
                        len(held_fragment),
                    )
                if clean_tail:
                    yield LLMChunk(text=clean_tail)
                stream_text_buffer = ""

            _sig_v2 = os.environ.get("BRAIN_THOUGHT_SIG_V2", "false").lower() in ("true", "1", "yes")
            effective_dropped_fcs = drain_dropped_fcs + (0 if _sig_v2 else same_chunk_extra_fcs)
            if effective_dropped_fcs:
                logger.warning(
                    f"Gemini stream returned {effective_dropped_fcs} additional function_call(s); only the first is used"
                )
            if last_grounding:
                logger.debug(f"Google Search grounding: {len(last_grounding.get('chunks', []))} sources, queries={last_grounding.get('queries', [])}")

            fallback_sig = trailing_sig_bytes
            if fallback_sig is None:
                fallback_sig = next(
                    (
                        s
                        for p in list(last_parts or []) + list(thought_parts)
                        if (s := _extract_part_signature(p)) is not None
                    ),
                    None,
                )
            non_thought_parts = [p for p in (last_parts or []) if not self._is_thought_part(p)]
            if fallback_sig is not None and non_thought_parts:
                non_thought_parts = _attach_signature_to_parts(non_thought_parts, fallback_sig)
            non_carriers = [p for p in non_thought_parts if not _is_empty_sig_carrier(p)]
            if non_carriers:
                output_parts = non_carriers
            elif thought_parts:
                output_parts = []
                if fallback_sig is not None and _extract_part_signature(thought_parts[-1]) is None:
                    thought_parts = _attach_signature_to_parts(thought_parts, fallback_sig)
            else:
                output_parts = non_thought_parts
            all_parts = thought_parts + output_parts

            if pending_fc is None and accumulated_stream_text and not call_syntax_overflowed:
                fallback_fc, _ = _extract_call_syntax(
                    accumulated_stream_text, tools=tools, warn_unterminated=not unterminated_logged
                )
                if fallback_fc:
                    pending_fc = fallback_fc

            token_usage = self._record_usage(last_usage, estimate, reservation=reservation)
            reservation_recorded = True

            fc_obj = None
            if pending_fc:
                if isinstance(pending_fc, FunctionCall):
                    fc_obj = pending_fc
                else:
                    fc_obj = FunctionCall(name=pending_fc.name, args=pending_fc.args or {})

            yield LLMChunk(
                function_call=fc_obj,
                done=True,
                raw_parts=all_parts,
                grounding_metadata=last_grounding,
                usage=token_usage,
            )
        finally:
            # Runs on clean end, drain abort, error, cancel, GeneratorExit and aclose (@ai-rules 15).
            try:
                if not reservation_recorded:
                    self._record_usage(last_usage, estimate, reservation=reservation)
            finally:
                if stream_iter is not None:
                    await self._close_stream(stream_iter)
