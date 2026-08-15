# src/agents/context_parts.py
# @ai-rules:
# 1. [Constraint]: Pure static/class methods ONLY. No instance state, no Redis, no LLM.
# 2. [Pattern]: All functions operate on structured dicts (Gemini Content format).
# 3. [Gotcha]: Imported by brain.py — zero circular imports. No sibling agent imports.
# 4. [Boundary]: _build_contents stays in brain.py (needs self.blackboard, self._skill_loader).
# 5. [Batch]: build_single_function_response returns ONE dict (not list) for multi-FR assembly.
#    compress_contents uses FC/FR count parity for atomic pruning of batch pairs.
"""Pure-function helpers for conversation content building and compression.

Extracted from brain.py for modularity. These have zero dependencies on
Brain instance state, Redis, or LLM adapters.
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import ConversationTurn

_CONTENT_BUDGET = int(os.environ.get("BRAIN_CONTENT_BUDGET_TOKENS", "800000"))


def _apply_sibling_signature(parts: list[dict]) -> list[dict]:
    """Copy thought_signature onto any functionCall part missing one.

    Source is the first sibling part in the same list that carries a
    thought_signature. Returns the parts unchanged (same list) if no sig
    is found or nothing needs fixing up; otherwise returns a new list
    with only the affected entries replaced (shallow copies).
    """
    sig = None
    for p in parts:
        if p.get("thought_signature"):
            sig = p["thought_signature"]
            break
    if not sig:
        return parts
    fixed = list(parts)
    for i, p in enumerate(fixed):
        if p.get("functionCall") and not p.get("thought_signature"):
            fixed[i] = {**p, "thought_signature": sig}
    return fixed


def extract_model_parts(response_parts: list[dict] | None) -> list[dict]:
    """Extract model-role parts from response_parts for native FC replay.

    Preserves thought parts + functionCall + thought_signature.
    Sibling-sig defense: if a functionCall lacks thought_signature,
    copy from a sibling part in the same response.
    """
    if not response_parts:
        return []
    model_parts = [
        p for p in response_parts
        if p.get("functionCall") or p.get("thought")
    ]
    if not model_parts:
        return []
    return _apply_sibling_signature(model_parts)


def build_function_response(turn: "ConversationTurn", skill_prefix: str = "") -> list[dict]:
    """Synthesize functionResponse from tool_result turn evidence.

    FR name derived from FC part in response_parts (authoritative),
    NOT from turn.waitingFor (unreliable on gate rejections and grounding).
    """
    import logging

    tool_name = "unknown_tool"
    if turn.response_parts:
        for p in turn.response_parts:
            if p.get("functionCall"):
                tool_name = p["functionCall"].get("name", "unknown_tool")
                break
    if tool_name == "unknown_tool" and turn.waitingFor:
        tool_name = turn.waitingFor
    if tool_name == "unknown_tool":
        logging.getLogger("brain").warning(
            "build_function_response: no FC name found (turn %s, waitingFor=%s)",
            getattr(turn, "turn", "?"), turn.waitingFor,
        )

    response_text = turn.evidence or turn.thoughts or ""
    if skill_prefix:
        response_text = f"{skill_prefix}\n{response_text}"
    if response_text:
        response_text = response_text.replace("</functionResponse>", "")
        response_text = response_text.replace("</description>", "")
        response_text = response_text.replace("</job_log>", "")
        response_text = response_text.replace("</comments>", "")
        response_text = response_text.replace("</mention_request>", "")
        response_text = response_text.replace("</issue_body>", "")
    return [{"functionResponse": {"name": tool_name, "response": {"result": response_text}}}]


_XML_FENCE_TAGS = (
    "</functionResponse>", "</description>", "</job_log>",
    "</comments>", "</mention_request>", "</issue_body>",
)


def build_single_function_response(turn: "ConversationTurn", fc_name: str | None = None) -> dict:
    """Build one functionResponse dict for a single turn in a batch.

    Unlike build_function_response (returns list[dict]), this returns a single
    dict for assembly into multi-FR user Content by the batch replay path.
    """
    tool_name = fc_name or "unknown_tool"
    if not fc_name and turn.response_parts:
        for p in turn.response_parts:
            if p.get("functionCall"):
                tool_name = p["functionCall"].get("name", "unknown_tool")
                break
    if tool_name == "unknown_tool" and turn.waitingFor:
        tool_name = turn.waitingFor
    response_text = turn.evidence or turn.thoughts or ""
    for tag in _XML_FENCE_TAGS:
        response_text = response_text.replace(tag, "")
    return {"functionResponse": {"name": tool_name, "response": {"result": response_text}}}


def estimate_msg_tokens(msg: dict) -> int:
    """Char count for a single Content message (text + FC args + FR response + sig)."""
    chars = 0
    for part in msg.get("parts", []):
        chars += len(str(part.get("text", "")))
        fc = part.get("functionCall")
        if fc:
            chars += len(str(fc.get("args", {}))) + len(fc.get("name", ""))
        fr = part.get("functionResponse")
        if fr:
            chars += len(str(fr.get("response", {}))) + len(fr.get("name", ""))
        chars += len(str(part.get("thought_signature", "")))
    return chars


def estimate_tokens(contents: list[dict]) -> int:
    """Rough token estimate: ~4 chars per token."""
    total_chars = sum(estimate_msg_tokens(msg) for msg in contents)
    return total_chars // 4


def compress_contents(contents: list[dict], max_tokens: int = _CONTENT_BUDGET) -> list[dict]:
    """Tail-keep prune: drop oldest conversation turns when over budget.

    First message (event context header) always kept intact.
    No truncation of individual turns — full fidelity until prune threshold.
    When over budget: keep header + last ~200K tokens of conversation from the end.
    FC/FR pairs are pruned atomically — never orphan one without the other.
    """
    if len(contents) <= 3:
        return contents

    if estimate_tokens(contents) < max_tokens:
        return contents

    context_msg = contents[0]
    conv_msgs = contents[1:]

    # Pre-pass: identify FC/FR pair indices (must prune atomically).
    # Batch-aware: only pair when FC count == FR count (count parity).
    pair_buddy: dict[int, int] = {}
    for i in range(len(conv_msgs) - 1):
        msg_i = conv_msgs[i]
        msg_next = conv_msgs[i + 1]
        if msg_i["role"] != "model" or msg_next["role"] != "user":
            continue
        fc_count = sum(1 for p in msg_i.get("parts", []) if p.get("functionCall"))
        fr_count = sum(1 for p in msg_next.get("parts", []) if p.get("functionResponse"))
        if fc_count > 0 and fr_count > 0 and fc_count == fr_count:
            pair_buddy[i] = i + 1
            pair_buddy[i + 1] = i

    tail_budget = 200_000
    kept_indices: list[int] = []
    running_tokens = 0

    for rev_idx in range(len(conv_msgs) - 1, -1, -1):
        if rev_idx in {i for i in kept_indices}:
            continue
        msg = conv_msgs[rev_idx]
        msg_tokens = estimate_msg_tokens(msg) // 4

        buddy_idx = pair_buddy.get(rev_idx)
        pair_tokens = msg_tokens
        if buddy_idx is not None and buddy_idx not in kept_indices:
            pair_tokens += estimate_msg_tokens(conv_msgs[buddy_idx]) // 4

        if running_tokens + pair_tokens > tail_budget and kept_indices:
            break

        kept_indices.append(rev_idx)
        running_tokens += msg_tokens
        if buddy_idx is not None and buddy_idx not in kept_indices:
            kept_indices.append(buddy_idx)
            running_tokens += estimate_msg_tokens(conv_msgs[buddy_idx]) // 4

    kept_indices.sort()
    kept = [conv_msgs[i] for i in kept_indices]

    if kept and kept[0] != conv_msgs[0]:
        pruned_count = len(conv_msgs) - len(kept)
        first_kept_idx = len(conv_msgs) - len(kept) + 1
        marker = {"role": "user", "parts": [{"text": (
            f"[{pruned_count} earlier turns (1-{first_kept_idx - 1}) pruned for context window. "
            f"Use recall_pruned_turns(from_turn, to_turn) to retrieve if needed.]"
        )}]}
        return [context_msg, marker] + kept

    return [context_msg] + kept


def normalize_response_parts(raw_parts: list) -> list[dict]:
    """Normalize SDK Part objects to plain dicts for Redis storage.

    Handles camelCase vs snake_case thought_signature across SDK versions.
    """
    import base64

    preserved = []
    for part in raw_parts:
        p: dict = {}
        if hasattr(part, 'text') and part.text:
            p['text'] = str(part.text)
        if hasattr(part, 'thought') and part.thought:
            p['thought'] = True
        if hasattr(part, 'function_call') and part.function_call:
            fc = part.function_call
            args = {}
            if fc.args:
                args = {str(k): str(v) if isinstance(v, bytes) else v for k, v in dict(fc.args).items()}
            p['functionCall'] = {"name": str(fc.name), "args": args}
        sig = getattr(part, 'thought_signature', None) or getattr(part, 'thoughtSignature', None)
        if sig:
            p['thought_signature'] = base64.b64encode(sig).decode('ascii') if isinstance(sig, bytes) else str(sig)
        if p:
            preserved.append(p)
    return preserved or [{"text": ""}]


def turn_to_parts(turn: "ConversationTurn") -> list[dict]:
    """Convert a single ConversationTurn to semantically-labelled parts.

    Labels: [USER], [SYSTEM tool], [AGENT y], [FRIDAY action].
    Brain's own response_parts are unlabelled (raw passthrough).
    """
    import base64

    if turn.actor == "brain" and turn.action in ("thoughts", "intermediate"):
        return []

    if turn.actor == "dispatcher" and turn.action in ("acknowledge", "connected"):
        return []

    if turn.actor == "brain" and turn.action == "tool_result":
        tool_name = turn.waitingFor or "tool"
        text = f"[SYSTEM {tool_name}]: {turn.evidence or turn.thoughts or ''}"
        parts: list[dict] = [{"text": text}]
        if turn.response_parts:
            for rp in turn.response_parts:
                if rp.get("thought_signature"):
                    parts[0]["thought_signature"] = rp["thought_signature"]
                    break
        return parts

    if turn.actor == "brain" and turn.response_parts:
        # Apply the same sibling-sig defense as extract_model_parts() so a
        # functionCall part missing thought_signature (e.g. one half of a
        # dual-stored FC that lost its sig in an earlier normalization
        # pass) still gets it from a sibling part -- this raw passthrough
        # is also what a later FC-dedup pass may leave standing as the
        # final record for this turn.
        return _apply_sibling_signature(list(turn.response_parts))

    text = ""
    if turn.actor == "brain":
        text = turn.thoughts or ""
        if turn.evidence:
            text = f"{text}\n{turn.evidence}" if text else turn.evidence
        if turn.action not in ("response",):
            text = f"[FRIDAY {turn.action}]: {text}" if text else f"[FRIDAY {turn.action}]"
    elif turn.actor == "user":
        raw = turn.thoughts or turn.result or ""
        if turn.user_name:
            text = f"[USER {turn.user_name}]: {raw}"
        else:
            text = f"[USER]: {raw}"
    elif turn.actor == "jarvis" and turn.action == "message":
        text = (
            f"[AGENT jarvis]: {turn.thoughts or turn.result or ''}\n\n"
            f"JARVIS asked you a question. Send your answer back to JARVIS before doing anything else."
        )
    else:
        raw = turn.evidence or turn.result or turn.thoughts or ""
        text = f"[AGENT {turn.actor}]: {raw}" if raw else f"[AGENT {turn.actor}]"

    parts: list[dict] = [{"text": text}]

    if turn.image:
        try:
            header, b64data = turn.image.split(",", 1)
            mime_type = header.split(":")[1].split(";")[0]
            image_bytes = base64.b64decode(b64data)
            parts.append({"bytes": image_bytes, "mime_type": mime_type})
        except Exception:
            pass

    return parts
