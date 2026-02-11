# src/agents/llm/__init__.py
# @ai-rules:
# 1. [Pattern]: Lazy imports -- unused SDK is never loaded (anthropic skipped when provider=gemini).
# 2. [Constraint]: This is the ONLY entry point. Consumers import from .llm, never from .llm.gemini_client.
"""
LLM adapter factory and re-exports.

Usage:
    from .llm import create_adapter, BRAIN_TOOL_SCHEMAS, LLMChunk
    adapter = create_adapter("gemini", project, location, model)
"""
from .types import (
    ALIGNER_TOOL_SCHEMAS,
    BRAIN_TOOL_SCHEMAS,
    FunctionCall,
    LLMChunk,
    LLMPort,
    LLMResponse,
)

__all__ = [
    "create_adapter",
    "FunctionCall",
    "LLMResponse",
    "LLMChunk",
    "LLMPort",
    "BRAIN_TOOL_SCHEMAS",
    "ALIGNER_TOOL_SCHEMAS",
]


def create_adapter(provider: str, project: str, location: str, model_name: str) -> LLMPort:
    """Factory: create the appropriate LLM adapter based on provider string."""
    if provider == "claude":
        from .claude_client import ClaudeAdapter
        return ClaudeAdapter(project, location, model_name)
    else:
        from .gemini_client import GeminiAdapter
        return GeminiAdapter(project, location, model_name)
