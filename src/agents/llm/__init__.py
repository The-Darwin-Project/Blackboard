# src/agents/llm/__init__.py
# @ai-rules:
# 1. [Pattern]: Lazy imports -- unused SDK is never loaded (anthropic skipped when provider=gemini).
# 2. [Constraint]: This is the ONLY entry point. Consumers import from .llm, never from .llm.gemini_client.
# 3. [Pattern]: QuotaTracker is a module-level singleton. Created lazily on first Gemini create_adapter() call.
# 4. [Constraint]: Claude adapter skips QuotaTracker (separate Anthropic quota via Vertex AI).
# 5. [Pattern]: TokenMeter is a lazy singleton via get_token_meter(). Unlike QuotaTracker, never returns None.
"""
LLM adapter factory and re-exports.

Usage:
    from .llm import create_adapter, BRAIN_TOOL_SCHEMAS, LLMChunk
    adapter = create_adapter("gemini", project, location, model)
"""
import logging
import os

_logger = logging.getLogger(__name__)

from .types import (
    ALIGNER_TOOL_SCHEMAS,
    BRAIN_TOOL_SCHEMAS,
    NIGHTWATCHER_TOOL_SCHEMAS,
    FunctionCall,
    LLMChunk,
    LLMPort,
    LLMResponse,
    TokenUsage,
)
from .quota_tracker import QuotaExhaustedError, QuotaTracker

__all__ = [
    "create_adapter",
    "get_quota_tracker",
    "get_token_meter",
    "record_token_usage",
    "FunctionCall",
    "LLMResponse",
    "LLMChunk",
    "LLMPort",
    "TokenUsage",
    "BRAIN_TOOL_SCHEMAS",
    "ALIGNER_TOOL_SCHEMAS",
    "NIGHTWATCHER_TOOL_SCHEMAS",
    "QuotaTracker",
    "QuotaExhaustedError",
]

_quota_tracker: QuotaTracker | None = None
_token_meter: "TokenMeter | None" = None


def get_quota_tracker() -> QuotaTracker | None:
    """Return the shared QuotaTracker singleton (None if not yet initialized)."""
    return _quota_tracker


def get_token_meter() -> "TokenMeter":
    """Lazy singleton — creates on first call, never returns None."""
    global _token_meter
    if _token_meter is None:
        from .token_meter import TokenMeter
        _token_meter = TokenMeter()
    return _token_meter


def record_token_usage(caller: str, usage: "TokenUsage | None", event_id: str | None = None) -> None:
    """Best-effort token recording. Non-fatal on any failure."""
    if not usage:
        return
    try:
        get_token_meter().record(caller, usage.model_version, usage, event_id)
    except Exception:
        _logger.debug("Token recording failed for %s", caller, exc_info=True)


def create_adapter(provider: str, project: str, location: str, model_name: str) -> LLMPort:
    """Factory: create the appropriate LLM adapter based on provider string.

    For Gemini adapters, injects the shared QuotaTracker singleton (created
    lazily on first call from LLM_TPM_LIMIT env var).
    """
    global _quota_tracker

    if provider == "claude":
        from .claude_client import ClaudeAdapter
        return ClaudeAdapter(project, location, model_name)

    if _quota_tracker is None:
        tpm = int(os.getenv("LLM_TPM_LIMIT", "500000"))
        _quota_tracker = QuotaTracker(tpm_limit=tpm)

    from .gemini_client import GeminiAdapter
    return GeminiAdapter(project, location, model_name, quota_tracker=_quota_tracker)
