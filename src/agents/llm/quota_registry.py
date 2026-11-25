# src/agents/llm/quota_registry.py
# @ai-rules:
# 1. [Constraint]: Zero import from llm.__init__ -- owns DEFAULT_TPM_LIMIT + parse_tpm_limit to prevent cycles.
# 2. [Pattern]: 3 physical upstream pools (vertex_gemini, vertex_claude, enmaas) with 85% normal sustained ceiling.
# 3. [Gotcha]: Dormant enmaas pool is excluded from global denominator unless ENMAAS_ENABLED=true or active usage > 0.
"""Multi-provider QuotaPoolRegistry managing Vertex Gemini, Vertex Claude, and EnMaaS TPM pools."""
from __future__ import annotations

import logging
import os

from .quota_tracker import QuotaTracker
from .types import PROVIDER_ENMAAS, PROVIDER_VERTEX_CLAUDE, PROVIDER_VERTEX_GEMINI

_logger = logging.getLogger(__name__)
DEFAULT_TPM_LIMIT = 3_500_000
DEFAULT_CLAUDE_TPM_LIMIT = 2_000_000
DEFAULT_ENMAAS_TPM_LIMIT = 2_000_000
DEFAULT_NORMAL_CEILING_RATIO = 0.85
_registry: QuotaPoolRegistry | None = None


def is_enmaas_enabled() -> bool:
    """Single SSOT for whether the EnMaaS pool is enabled."""
    return os.getenv("ENMAAS_ENABLED", "false").lower() == "true"

def parse_tpm_limit(env_key: str = "LLM_TPM_LIMIT", default: int = DEFAULT_TPM_LIMIT) -> int:
    """Parse a positive integer TPM limit from env with fallback to default."""
    raw = os.getenv(env_key)
    if raw and raw.strip():
        try:
            if (val := int(raw.strip())) > 0:
                return val
        except ValueError:
            pass
        _logger.warning("Invalid/non-positive %s=%r; falling back to %d", env_key, raw, default)
    return default

def _parse_ceiling_ratio() -> float:
    raw = os.getenv("LLM_TPM_NORMAL_CEILING_RATIO")
    if raw and raw.strip():
        try:
            if 0.0 < (val := float(raw.strip())) <= 1.0:
                return val
        except ValueError:
            pass
        _logger.warning("Invalid LLM_TPM_NORMAL_CEILING_RATIO=%r; using %.2f", raw, DEFAULT_NORMAL_CEILING_RATIO)
    return DEFAULT_NORMAL_CEILING_RATIO

class QuotaPoolRegistry:
    """Registry of per-provider QuotaTracker buckets sharing an 85%/15% priority reserve."""

    def __init__(self) -> None:
        ratio = _parse_ceiling_ratio()
        self._pools: dict[str, QuotaTracker] = {
            PROVIDER_VERTEX_GEMINI: QuotaTracker(parse_tpm_limit("LLM_TPM_LIMIT", DEFAULT_TPM_LIMIT), ratio, enforce_sustained_for_normal=True),
            PROVIDER_VERTEX_CLAUDE: QuotaTracker(parse_tpm_limit("LLM_TPM_LIMIT_CLAUDE", DEFAULT_CLAUDE_TPM_LIMIT), ratio, enforce_sustained_for_normal=True),
            PROVIDER_ENMAAS: QuotaTracker(parse_tpm_limit("LLM_TPM_LIMIT_ENMAAS", DEFAULT_ENMAAS_TPM_LIMIT), ratio, enforce_sustained_for_normal=True),
        }

    def get(self, provider: str = PROVIDER_VERTEX_GEMINI) -> QuotaTracker:
        if provider in self._pools:
            return self._pools[provider]
        _logger.warning("Unknown quota provider %r; falling back to %s", provider, PROVIDER_VERTEX_GEMINI)
        return self._pools[PROVIDER_VERTEX_GEMINI]

    def is_normal_saturated(self, provider: str = PROVIDER_VERTEX_GEMINI) -> bool:
        stats = self.get(provider).get_stats()
        sustained = stats.get("sustained_limit", 0)
        return True if sustained <= 0 else stats["tokens_used_60s"] >= sustained

    def get_all_stats(self, enmaas_enabled: bool | None = None) -> dict:
        enmaas_on = is_enmaas_enabled() if enmaas_enabled is None else enmaas_enabled
        pools = {prov: tracker.get_stats() for prov, tracker in self._pools.items()}
        enmaas = pools[PROVIDER_ENMAAS]
        enmaas_active = enmaas_on or enmaas["total_requests"] > 0 or enmaas["tokens_used_60s"] > 0
        active_keys = [PROVIDER_VERTEX_GEMINI, PROVIDER_VERTEX_CLAUDE] + ([PROVIDER_ENMAAS] if enmaas_active else [])
        sum_keys = ("tokens_used_60s", "tpm_limit", "sustained_limit", "reserve_tokens", "tokens_remaining",
                    "active_reservations", "high_priority_waiters", "total_requests", "total_tokens", "throttle_events")
        global_stats = {k: sum(pools[p][k] for p in active_keys) for k in sum_keys}
        lim = global_stats["tpm_limit"]
        global_stats["utilization_pct"] = round(global_stats["tokens_used_60s"] / lim * 100, 1) if lim else 0.0
        global_stats["peak_pool_utilization_pct"] = max((pools[p]["utilization_pct"] for p in active_keys), default=0.0)
        return {"global": global_stats, "pools": pools, "enmaas_active": enmaas_active}

def get_quota_registry() -> QuotaPoolRegistry:
    """Return the lazy process-wide QuotaPoolRegistry singleton."""
    global _registry
    if _registry is None:
        _registry = QuotaPoolRegistry()
    return _registry

def reset_quota_registry() -> None:
    """Reset the QuotaPoolRegistry singleton (tests / env re-read)."""
    global _registry
    _registry = None
