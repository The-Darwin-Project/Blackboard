# src/agents/llm/raw_genai_meter.py
# @ai-rules:
# 1. [Constraint]: Zero google.genai SDK import; inspects usage_metadata via duck typing only.
# 2. [Pattern]: Event-loop only -- blocking asyncio.to_thread callers must acquire before and finalize after on loop.
# 3. [Pattern]: Unifies raw genai.Client callers onto QuotaPoolRegistry + TokenMeter without adapter overhead.
"""Shared metering and QuotaPoolRegistry governance for raw google.genai.Client callers."""
from __future__ import annotations

from typing import Any

from . import get_quota_registry, record_token_usage
from .types import PRIORITY_NORMAL, PROVIDER_VERTEX_GEMINI, TokenUsage


def _int_field(meta: Any, attr: str) -> int | None:
    v = getattr(meta, attr, None)
    return v if isinstance(v, int) and not isinstance(v, bool) else None


def extract_genai_usage(usage_metadata: Any, model: str = "") -> TokenUsage | None:
    """Convert google.genai usage_metadata into provider-agnostic TokenUsage."""
    if usage_metadata is None:
        return None
    input_t = _int_field(usage_metadata, "prompt_token_count") or 0
    candidates_t = _int_field(usage_metadata, "candidates_token_count")
    thinking_t = _int_field(usage_metadata, "thoughts_token_count") or 0
    cached_t = _int_field(usage_metadata, "cached_content_token_count") or 0
    tool_use_t = _int_field(usage_metadata, "tool_use_prompt_token_count") or 0
    total = _int_field(usage_metadata, "total_token_count") or 0
    if candidates_t is None and total > 0:
        candidates_t = max(0, total - input_t - thinking_t)
    output_t = candidates_t or 0
    total = total if total > 0 else (input_t + output_t + thinking_t)
    if total <= 0:
        return None
    return TokenUsage(
        input_tokens=input_t, output_tokens=output_t, thinking_tokens=thinking_t,
        cached_tokens=cached_t, tool_use_tokens=tool_use_t, total_tokens=total, model_version=model,
    )


async def acquire_raw_genai(
    contents: Any, *, priority: int = PRIORITY_NORMAL, provider: str = PROVIDER_VERTEX_GEMINI,
) -> tuple[int, Any, str]:
    """Acquire a QuotaPoolRegistry reservation on the active event loop before calling genai."""
    estimate = max(1, len(str(contents)) // 4)
    reservation = await get_quota_registry().get(provider).acquire(estimate, max_wait_seconds=30.0, priority=priority)
    return (estimate, reservation, provider)


def finalize_raw_genai(
    caller: str, model: str, usage_metadata: Any, res_state: tuple[int, Any, str] | None,
    *, event_id: str | None = None, team_id: str | None = None,
) -> TokenUsage | None:
    """Finalize reservation with actual usage (or rollback) and record in TokenMeter."""
    estimate, reservation, provider = res_state or (0, None, PROVIDER_VERTEX_GEMINI)
    usage = extract_genai_usage(usage_metadata, model=model)
    tracker = get_quota_registry().get(provider)
    if usage is not None and usage.total_tokens > 0:
        if reservation is not None:
            tracker.record(usage.total_tokens, estimate, reservation=reservation)
        else:
            tracker.record_post_hoc(usage.total_tokens)
        record_token_usage(caller, usage, event_id, provider=provider, team_id=team_id)
    elif reservation is not None:
        tracker.rollback(reservation)
    return usage


def rollback_raw_genai(res_state: tuple[int, Any, str] | None) -> None:
    """Rollback reservation on exception/timeout on the active event loop."""
    if res_state and res_state[1] is not None:
        get_quota_registry().get(res_state[2]).rollback(res_state[1])


def record_raw_genai_post_hoc(
    caller: str, model: str, usage_metadata: Any,
    *, event_id: str | None = None, provider: str = PROVIDER_VERTEX_GEMINI, team_id: str | None = None,
) -> TokenUsage | None:
    """Record post-hoc usage (e.g. Live API WS server messages) into pool + TokenMeter."""
    usage = extract_genai_usage(usage_metadata, model=model)
    if usage is not None and usage.total_tokens > 0:
        get_quota_registry().get(provider).record_post_hoc(usage.total_tokens)
        record_token_usage(caller, usage, event_id, provider=provider, team_id=team_id)
    return usage
