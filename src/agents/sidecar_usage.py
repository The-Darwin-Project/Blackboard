# BlackBoard/src/agents/sidecar_usage.py
# @ai-rules:
# 1. [Constraint]: Zero module-top-level import from src.agents.brain (prevents brain -> dispatch -> sidecar_usage cycle).
# 2. [Security]: Strict non-bool int >= 0 check; clamps oversized frame deltas to SIDECAR_MAX_FRAME_TOKENS; allowlists cli slug.
# 3. [Pattern]: Post-hoc non-blocking recording into TokenMeter + QuotaPoolRegistry (never aborts mid-flight sidecars).
"""Sidecar WS token validation, provider resolution, and post-hoc QuotaPoolRegistry metering."""
from __future__ import annotations

import logging
from typing import Any

from .llm import get_quota_registry, is_enmaas_enabled, record_token_usage
from .llm.quota_registry import parse_tpm_limit
from .llm.types import DEFAULT_SIDECAR_CLI, PROVIDER_ENMAAS, PROVIDER_VERTEX_CLAUDE, PROVIDER_VERTEX_GEMINI, TokenUsage, get_default_role_cli_map

logger = logging.getLogger(__name__)
SIDECAR_MAX_FRAME_TOKENS = parse_tpm_limit("SIDECAR_MAX_FRAME_TOKENS", 500_000)
_ALLOWED_CLIS = frozenset({"agy", "claude"})
_VALID_PROVIDERS = frozenset({PROVIDER_VERTEX_GEMINI, PROVIDER_VERTEX_CLAUDE, PROVIDER_ENMAAS})
_USAGE_KEYS = ("input_tokens", "output_tokens", "thinking_tokens", "cached_tokens", "cache_read_input_tokens", "cache_creation_input_tokens", "total_tokens")

def normalize_sidecar_provider(cli: str = "", raw_provider: str = "") -> str:
    """Resolve physical upstream pool for a sidecar CLI and optional declared provider."""
    c = (cli or "").strip().lower()
    if c == "agy":
        return PROVIDER_VERTEX_GEMINI
    if c == "claude":
        if raw_provider == PROVIDER_VERTEX_CLAUDE:
            return PROVIDER_VERTEX_CLAUDE
        return PROVIDER_ENMAAS if is_enmaas_enabled() else PROVIDER_VERTEX_CLAUDE
    if raw_provider == PROVIDER_ENMAAS:
        return PROVIDER_ENMAAS if is_enmaas_enabled() else PROVIDER_VERTEX_CLAUDE
    return raw_provider if raw_provider in _VALID_PROVIDERS else PROVIDER_VERTEX_GEMINI

def validate_usage_payload(usage_dict: Any, cli: str = "", *, max_tokens: int | None = None) -> tuple[str, TokenUsage] | None:
    """Validate and clamp a WS sidecar usage payload; returns (caller_slug, TokenUsage) or None."""
    if not isinstance(usage_dict, dict):
        return None
    cap = SIDECAR_MAX_FRAME_TOKENS if max_tokens is None else max_tokens
    c = (cli or "").strip().lower()
    caller = f"sidecar:{c}" if c in _ALLOWED_CLIS else "sidecar:unknown"
    vals: dict[str, int] = {}
    clamped = False
    for k in _USAGE_KEYS:
        raw = usage_dict.get(k)
        if raw is None: vals[k] = 0
        elif isinstance(raw, bool) or not isinstance(raw, int) or raw < 0: return None
        else:
            clamped = clamped or (raw > cap)
            vals[k] = min(raw, cap)
    if clamped:
        logger.warning("Clamped oversized sidecar token frame for caller=%s (limit=%d)", caller, cap)
    anth_cache = vals["cache_read_input_tokens"] + vals["cache_creation_input_tokens"]
    has_anth = vals["cached_tokens"] == 0 and anth_cache > 0
    cached = min(cap, anth_cache) if has_anth else vals["cached_tokens"]
    effective_input = min(cap, vals["input_tokens"] + (anth_cache if has_anth else 0))
    total = vals["total_tokens"] or min(cap, effective_input + vals["output_tokens"] + (vals["thinking_tokens"] if c == "agy" else 0))
    return caller, TokenUsage(input_tokens=effective_input, output_tokens=vals["output_tokens"], thinking_tokens=vals["thinking_tokens"], cached_tokens=cached, total_tokens=total)

def record_sidecar_usage(
    *, cli: str = "", raw_provider: str = "", model: str = "",
    usage_dict: Any = None, event_id: str | None = None, team_id: str | None = None,
    parsed: tuple[str, TokenUsage] | None = None,
) -> int:
    """Validate and record sidecar token delta into TokenMeter + QuotaPoolRegistry (non-blocking)."""
    resolved = parsed if parsed is not None else validate_usage_payload(usage_dict, cli)
    if resolved is None:
        return 0
    caller, usage = resolved
    if usage.total_tokens <= 0:
        return 0
    usage.model_version = str(model or "")
    provider = normalize_sidecar_provider(cli, raw_provider)
    record_token_usage(caller, usage, event_id, provider=provider, team_id=team_id)
    get_quota_registry().get(provider).record_post_hoc(usage.total_tokens)
    return usage.total_tokens

async def resolve_sidecar_provider(
    agent_name: str, registry: Any, *, event_id: str = "", role_cli_map: dict[str, str] | None = None,
) -> str:
    """Resolve sidecar upstream pool: connected provider -> connected cli -> role_cli_map."""
    if registry is not None:
        conn = (await registry.get_ephemeral(event_id, agent_name)) if event_id else None
        if conn is None:
            conn = await registry.get_by_role(agent_name)
        if conn is not None:
            raw_prov, conn_cli = getattr(conn, "provider", "") or "", getattr(conn, "cli", "") or ""
            if raw_prov or conn_cli:
                return normalize_sidecar_provider(conn_cli, raw_prov)
    return normalize_sidecar_provider((role_cli_map or get_default_role_cli_map()).get(agent_name, DEFAULT_SIDECAR_CLI), "")

async def is_sidecar_pool_saturated(agent_name: str, registry: Any, *, event_id: str = "", already_deferred: bool = False) -> bool:
    """Return True if the target sidecar pool has reached its 85% normal sustained ceiling."""
    return get_quota_registry().is_normal_saturated(
        await resolve_sidecar_provider(agent_name, registry, event_id=event_id),
        already_deferred=already_deferred,
    )
