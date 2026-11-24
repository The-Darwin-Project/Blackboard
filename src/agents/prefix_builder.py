# BlackBoard/src/agents/prefix_builder.py
# @ai-rules:
# 1. [Constraint]: Pure sync helpers only -- ZERO Redis, LLM, Brain, or state imports (<=100 lines).
# 2. [Pattern]: Vertex AI implicit context caching (VMER-2450) requires an atomic byte-identical
#    static preamble (canonical sorted wire_tools + immutable Global Core system_instruction).
# 3. [Pattern]: GLOBAL_CORE_EXTRA_PATHS are promoted security/governance boundaries resolved with
#    full transitive requires: closure via loader.resolve_dependencies_with_paths and deduplicated.
# 4. [Pattern]: compute_prefix_hashes() emits 8-hex deterministic SHA-256 digests over canonical JSON
#    and UTF-8 strings for per-call cache stability observability.
"""Static preamble assembly and prefix digest helpers for Brain implicit context caching."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from collections.abc import Sequence
from typing import Any

_SAFE_PATH_RE = re.compile(r"[^a-zA-Z0-9._/\-]")

GLOBAL_CORE_EXTRA_PATHS: tuple[str, ...] = (
    "dispatch/execution-method.md",
    "coordination/quality-gate.md",
    "source/headhunter.md",
)


def canonical_wire_tools(schemas: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return an immutable, name-sorted deep copy of tool schemas for wire stability."""
    return sorted((copy.deepcopy(tool) for tool in schemas), key=lambda t: t["name"])


def build_global_core_si(loader: Any) -> str:
    """Assemble Global Core system_instruction: always/ + promoted paths + transitive requires:."""
    always_paths = list(loader.get_all_paths_for_phase("always") or [])
    initial_paths: list[str] = list(always_paths)
    seen_initial = set(initial_paths)
    for extra in GLOBAL_CORE_EXTRA_PATHS:
        if extra not in seen_initial:
            initial_paths.append(extra)
            seen_initial.add(extra)

    resolved_pairs = loader.resolve_dependencies_with_paths(initial_paths)
    sections: list[str] = []
    seen_resolved: set[str] = set()
    for path, body in resolved_pairs:
        if path in seen_resolved:
            continue
        seen_resolved.add(path)
        tag_type = loader.get_tag_type(path)
        safe_path = _SAFE_PATH_RE.sub("_", path).replace("..", "__")
        sections.append(f'<{tag_type} id="{safe_path}">\n{body}\n</{tag_type}>')
    return "\n\n---\n\n".join(sections)


def sha8_text(payload: str) -> str:
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:8]


def sha8_json(obj: Any) -> str:
    return sha8_text(json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str))


def compute_prefix_hashes(
    wire_tools: Sequence[dict[str, Any]],
    system_prompt: str,
    header_text: str,
) -> dict[str, str]:
    """Compute 8-hex SHA-256 digests for wire_tools, system_instruction, and Turn-0 header."""
    return {
        "tools_sha8": sha8_json(list(wire_tools)),
        "si_sha8": sha8_text(system_prompt or ""),
        "hdr_sha8": sha8_text(header_text or ""),
    }
