# src/agents/llm/__init__.py
# @ai-rules:
# 1. [Pattern]: Lazy SDK imports -- unused SDK is never loaded (google.genai/anthropic stay inside adapter methods).
# 2. [Constraint]: This is the ONLY entry point. Consumers import from .llm, never from .llm.gemini_client.
# 3. [Pattern]: QuotaPoolRegistry governs Gemini (vertex_gemini), Claude (vertex_claude), and EnMaaS pools via 85%/15% reserve.
# 4. [Constraint]: get_quota_tracker() and _quota_tracker unify on get_quota_registry().get(PROVIDER_VERTEX_GEMINI) (I-1).
# 5. [Pattern]: TokenMeter is a lazy singleton via get_token_meter(). Unlike QuotaTracker, never returns None.
# 6. [Pattern]: Exports QuotaExhaustedError (transient) AND RequestExceedsBurstError (non-transient subclass).
"""LLM adapter factory and re-exports (entry point: `from .llm import create_adapter, ...`)."""
import logging

_logger = logging.getLogger(__name__)

from .quota_registry import (
    DEFAULT_TPM_LIMIT, QuotaPoolRegistry, get_quota_registry,
    is_enmaas_enabled, reset_quota_registry,
)
from .quota_tracker import QuotaExhaustedError, QuotaTracker, RequestExceedsBurstError
from .types import (
    BRAIN_TOOL_SCHEMAS, NIGHTWATCHER_TOOL_SCHEMAS, PRIORITY_HIGH, PRIORITY_NORMAL,
    PROVIDER_ENMAAS, PROVIDER_VERTEX_CLAUDE, PROVIDER_VERTEX_GEMINI,
    FunctionCall, LLMChunk, LLMPort, LLMResponse, TokenUsage,
    LLMStreamInterChunkTimeoutError, LLMStreamTimeoutError, LLMStreamTotalTimeoutError,
    LLMStreamTTFBTimeoutError, derive_llm_priority, get_default_role_cli_map, resolve_stream_timeouts, sanitize_call_syntax,
)

__all__ = [
    "DEFAULT_TPM_LIMIT", "PRIORITY_HIGH", "PRIORITY_NORMAL",
    "PROVIDER_VERTEX_GEMINI", "PROVIDER_VERTEX_CLAUDE", "PROVIDER_ENMAAS",
    "QuotaPoolRegistry", "get_quota_registry", "is_enmaas_enabled", "reset_quota_registry",
    "create_adapter", "get_quota_tracker", "get_token_meter", "record_token_usage",
    "resolve_stream_timeouts", "derive_llm_priority", "get_default_role_cli_map", "sanitize_call_syntax", "FunctionCall", "LLMResponse",
    "LLMChunk", "LLMPort", "TokenUsage", "LLMStreamTimeoutError", "LLMStreamTTFBTimeoutError",
    "LLMStreamInterChunkTimeoutError", "LLMStreamTotalTimeoutError", "BRAIN_TOOL_SCHEMAS",
    "NIGHTWATCHER_TOOL_SCHEMAS", "QuotaTracker", "QuotaExhaustedError", "RequestExceedsBurstError",
]

_quota_tracker: QuotaTracker | None = None
_token_meter: "TokenMeter | None" = None


def get_quota_tracker(provider: str = PROVIDER_VERTEX_GEMINI) -> QuotaTracker:
    """Return the shared QuotaTracker pool from QuotaPoolRegistry (syncs _quota_tracker for Gemini)."""
    global _quota_tracker
    tracker = get_quota_registry().get(provider)
    if provider == PROVIDER_VERTEX_GEMINI:
        _quota_tracker = tracker
    return tracker


def get_token_meter() -> "TokenMeter":
    """Lazy singleton — creates on first call, never returns None."""
    global _token_meter
    if _token_meter is None:
        from .token_meter import TokenMeter
        _token_meter = TokenMeter()
    return _token_meter


def record_token_usage(
    caller: str, usage: "TokenUsage | None", event_id: str | None = None,
    *, provider: str = "", team_id: str | None = None,
) -> None:
    """Best-effort token recording and caller-aware cache telemetry logging. Non-fatal on any failure."""
    if not usage:
        return
    try:
        meter = get_token_meter()
        if provider or team_id is not None:
            meter.record(caller, usage.model_version, usage, event_id, provider=provider, team_id=team_id)
        else:
            meter.record(caller, usage.model_version, usage, event_id)
        in_tok = getattr(usage, "input_tokens", 0) or 0
        cached_tok = getattr(usage, "cached_tokens", 0) or 0
        fields = {
            "caller": caller, "event_id": event_id, "provider": provider, "input_tokens": in_tok,
            "cached_tokens": cached_tok, "cache_hit_pct": round(cached_tok / in_tok * 100.0, 1) if in_tok > 0 else 0.0,
            "thinking_tokens": getattr(usage, "thinking_tokens", 0) or 0, "output_tokens": getattr(usage, "output_tokens", 0) or 0,
        }
        (_logger.info if caller == "brain" else _logger.debug)(
            "LLM tokens caller=%(caller)s provider=%(provider)s event_id=%(event_id)s input_tokens=%(input_tokens)d "
            "cached_tokens=%(cached_tokens)d cache_hit_pct=%(cache_hit_pct).1f%% thinking_tokens=%(thinking_tokens)d output_tokens=%(output_tokens)d",
            fields, extra=fields,
        )
    except Exception:
        _logger.debug("Token recording failed for %s", caller, exc_info=True)


def create_adapter(provider: str, project: str, location: str, model_name: str) -> LLMPort:
    """Factory: create the appropriate LLM adapter (injects shared QuotaPoolRegistry pool)."""
    global _quota_tracker
    if provider == "claude":
        from .claude_client import ClaudeAdapter
        return ClaudeAdapter(project, location, model_name, quota_tracker=get_quota_tracker(PROVIDER_VERTEX_CLAUDE))
    _quota_tracker = get_quota_tracker(PROVIDER_VERTEX_GEMINI)
    from .gemini_client import GeminiAdapter
    return GeminiAdapter(project, location, model_name, quota_tracker=_quota_tracker)
