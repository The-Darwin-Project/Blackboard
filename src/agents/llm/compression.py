# src/agents/llm/compression.py
# @ai-rules:
# 1. [Constraint]: Zero imports from brain.py or chat_session.py. Pure functions operating
#    on list[dict] (provider-agnostic {role, parts} shape). This module is the shared
#    dependency root for BOTH the old path (brain.py, generate_content) and the new
#    Chat Session Bridge path (chat_session.py, Content->dict->Content round-trip).
# 2. [Pattern]: Relocated verbatim from brain.py's Brain._compress_contents /
#    Brain._estimate_tokens / Brain._pair_delete_oldest (classmethods -> module functions).
#    Behavior is byte-for-byte identical to the pre-relocation version -- this is a pure
#    location move, not a rewrite. brain.py's old path imports these same functions.
# 3. [Gotcha]: Atomic pair guard -- a model(functionCall) turn and the immediately
#    following user(functionResponse) turn are NEVER separated into different tiers.
#    FC/FR turns have a summary floor (never skeleton) since structural signal matters
#    more than prose for these turns.
# 4. [Pattern]: 4-tier progressive compression: skeleton (oldest) -> summary (middle) ->
#    full (most recent) -> pair-delete (last resort, drops complete FC/FR pairs oldest
#    first, retains a minimum of 5 pairs).
"""
Provider-agnostic conversation compression.

Pure functions operating on list[dict] ({"role": str, "parts": list[dict]}).
No SDK types, no Brain state, no Chat session state -- safe to import from
either the old generate_content path (brain.py) or the new Chat Session
Bridge path (chat_session.py) without creating a circular import.
"""
from __future__ import annotations

import json

DEFAULT_FULL_TIER_MAX_CHARS = 100_000
_MIN_RETAINED_PAIRS = 5


def estimate_tokens(contents: list[dict]) -> int:
    """Rough token estimate: ~4 chars per token. Handles FC/FR dicts."""
    total_chars = 0
    for msg in contents:
        for part in msg.get("parts", []):
            text = part.get("text")
            if text:
                total_chars += len(text)
            elif "functionCall" in part or "functionResponse" in part:
                total_chars += len(json.dumps(part))
    return total_chars // 4


def compress_contents(
    contents: list[dict],
    max_tokens: int,
    full_tier_max_chars: int = DEFAULT_FULL_TIER_MAX_CHARS,
) -> list[dict]:
    """Progressive compression: skeleton/summary/full tiers. No LLM call.

    First message (event context) always kept intact.
    Atomic pair guard: model(functionCall) + user(functionResponse) never separated.
    FC/FR messages floor=summary (never skeleton -- structural signal matters).
    4th tier: pair-delete oldest FC/FR pairs if still over budget (min 5 retained).
    """
    if len(contents) <= 3:
        return contents

    if estimate_tokens(contents) < max_tokens:
        return contents

    context_msg = contents[0]
    conv_msgs = contents[1:]
    n = len(conv_msgs)

    skeleton_end = max(0, n - 20)
    summary_end = max(skeleton_end, n - 10)

    # Build tier assignment per message, then enforce atomic pairs
    tiers = []
    for i in range(n):
        if i < skeleton_end:
            tiers.append("skeleton")
        elif i < summary_end:
            tiers.append("summary")
        else:
            tiers.append("full")

    # FC/FR floor: messages with functionCall or functionResponse never go below summary
    for i in range(n):
        if tiers[i] == "skeleton":
            msg = conv_msgs[i]
            has_fc_fr = any(
                isinstance(p, dict) and ("functionCall" in p or "functionResponse" in p)
                for p in msg.get("parts", [])
            )
            if has_fc_fr:
                tiers[i] = "summary"

    # Atomic pair guard: if a model msg has functionCall parts, promote
    # it and the next user msg to the same tier (the less compressed one)
    for i in range(n - 1):
        msg = conv_msgs[i]
        if msg["role"] == "model" and any(
            isinstance(p, dict) and ("functionCall" in p or "function_call" in p)
            for p in msg.get("parts", [])
        ):
            better = min(tiers[i], tiers[i + 1], key=["full", "summary", "skeleton"].index)
            tiers[i] = better
            tiers[i + 1] = better

    compressed = [context_msg]
    for i, msg in enumerate(conv_msgs):
        tier = tiers[i]
        if tier == "skeleton":
            role = msg["role"]
            first_text = ""
            for p in msg.get("parts", []):
                if isinstance(p, dict) and "text" in p:
                    first_text = p["text"][:300]
                    break
            compressed.append({"role": role, "parts": [{"text": f"(earlier turn: {first_text}...)"}]})
        elif tier == "summary":
            role = msg["role"]
            parts = []
            for p in msg.get("parts", []):
                if isinstance(p, dict) and "text" in p:
                    sentences = p["text"].split(". ")
                    parts.append({"text": sentences[0] + ("." if len(sentences) > 1 else "")})
                else:
                    parts.append(p)
            compressed.append({"role": role, "parts": parts or msg["parts"]})
        else:
            role = msg["role"]
            parts = []
            for p in msg.get("parts", []):
                if isinstance(p, dict) and "text" in p and len(p["text"]) > full_tier_max_chars:
                    truncated = p["text"][:full_tier_max_chars]
                    parts.append({"text": f"{truncated}\n...(turn truncated at {full_tier_max_chars} chars)"})
                else:
                    parts.append(p)
            compressed.append({"role": role, "parts": parts})

    # 4th tier: pair-delete oldest FC/FR pairs if still over budget
    if estimate_tokens(compressed) >= max_tokens:
        compressed = pair_delete_oldest(compressed, max_tokens)

    return compressed


def pair_delete_oldest(contents: list[dict], max_tokens: int) -> list[dict]:
    """Drop complete FC+FR pairs from oldest first, retaining min 5 most-recent."""
    # Find all FC/FR pair indices (model with FC at i, user with FR at i+1)
    pair_indices: list[tuple[int, int]] = []
    for i in range(1, len(contents) - 1):
        msg = contents[i]
        if msg["role"] == "model" and any(
            isinstance(p, dict) and "functionCall" in p for p in msg.get("parts", [])
        ):
            nxt = contents[i + 1] if i + 1 < len(contents) else None
            if nxt and nxt["role"] == "user" and any(
                isinstance(p, dict) and "functionResponse" in p for p in nxt.get("parts", [])
            ):
                pair_indices.append((i, i + 1))

    if len(pair_indices) <= _MIN_RETAINED_PAIRS:
        return contents

    # Delete from oldest (lowest index) first, skip last 5 pairs
    deletable = pair_indices[:-_MIN_RETAINED_PAIRS]
    indices_to_remove: set[int] = set()
    for fc_idx, fr_idx in deletable:
        indices_to_remove.add(fc_idx)
        indices_to_remove.add(fr_idx)
        # Check if removing brings us under budget
        remaining = [c for i, c in enumerate(contents) if i not in indices_to_remove]
        if estimate_tokens(remaining) < max_tokens:
            break

    return [c for i, c in enumerate(contents) if i not in indices_to_remove]


def dedup_consecutive_fr(contents: list[dict], collapse_threshold: int = 3) -> list[dict]:
    """SPIRAL dedup: collapse 3+ consecutive identical FC/FR pairs into one + annotation.

    An identical pair = same tool name + same args (FC) with the FR immediately following.
    Prevents a historical spiral (pre-migration event, or a since-fixed bug) from being
    replayed verbatim into a fresh Chat session on rebuild_from_redis.
    """
    if len(contents) < collapse_threshold * 2:
        return contents

    def _pair_signature(fc_msg: dict, fr_msg: dict) -> tuple | None:
        fc_part = next((p for p in fc_msg.get("parts", []) if isinstance(p, dict) and "functionCall" in p), None)
        fr_part = next((p for p in fr_msg.get("parts", []) if isinstance(p, dict) and "functionResponse" in p), None)
        if not fc_part or not fr_part:
            return None
        fc = fc_part["functionCall"]
        return (fc.get("name"), json.dumps(fc.get("args", {}), sort_keys=True))

    result: list[dict] = []
    i = 0
    n = len(contents)
    while i < n:
        # Try to find a run of identical FC/FR pairs starting at i
        if i + 1 < n and contents[i].get("role") == "model" and contents[i + 1].get("role") == "user":
            sig = _pair_signature(contents[i], contents[i + 1])
            if sig is not None:
                run_len = 1
                j = i + 2
                while j + 1 < n:
                    next_sig = _pair_signature(contents[j], contents[j + 1]) if contents[j].get("role") == "model" and contents[j + 1].get("role") == "user" else None
                    if next_sig == sig:
                        run_len += 1
                        j += 2
                    else:
                        break

                if run_len >= collapse_threshold:
                    # Keep the LAST occurrence (most recent data), annotate the collapse
                    last_fc = contents[j - 2]
                    last_fr = dict(contents[j - 1])
                    last_fr["parts"] = list(last_fr.get("parts", [])) + [
                        {"text": f"(collapsed {run_len - 1} identical earlier repeats of this tool call)"}
                    ]
                    result.append(last_fc)
                    result.append(last_fr)
                    i = j
                    continue

        result.append(contents[i])
        i += 1

    return result
