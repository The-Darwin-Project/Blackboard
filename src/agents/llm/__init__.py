# src/agents/llm/__init__.py
# @ai-rules:
# 1. [Pattern]: Lazy imports -- unused SDK is never loaded (anthropic skipped when provider=gemini).
# 2. [Constraint]: This is the ONLY entry point. Consumers import from .llm, never from .llm.gemini_client.
# 3. [Pattern]: QuotaTracker is a module-level singleton. Created lazily on first Gemini create_adapter() call.
# 4. [Constraint]: Claude adapter skips QuotaTracker (separate Anthropic quota via Vertex AI).
"""
LLM adapter factory and re-exports.

Usage:
    from .llm import create_adapter, BRAIN_TOOL_SCHEMAS, LLMChunk
    adapter = create_adapter("gemini", project, location, model)
"""
import os

from .types import (
    ALIGNER_TOOL_SCHEMAS,
    BRAIN_TOOL_SCHEMAS,
    FunctionCall,
    LLMChunk,
    LLMPort,
    LLMResponse,
)
from .quota_tracker import QuotaExhaustedError, QuotaTracker

__all__ = [
    "create_adapter",
    "get_quota_tracker",
    "FunctionCall",
    "LLMResponse",
    "LLMChunk",
    "LLMPort",
    "BRAIN_TOOL_SCHEMAS",
    "ALIGNER_TOOL_SCHEMAS",
    "QuotaTracker",
    "QuotaExhaustedError",
]

_quota_tracker: QuotaTracker | None = None


def get_quota_tracker() -> QuotaTracker | None:
    """Return the shared QuotaTracker singleton (None if not yet initialized)."""
    return _quota_tracker


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
