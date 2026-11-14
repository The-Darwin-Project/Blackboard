# src/agents/context_parts.py
# @ai-rules:
# 1. [Constraint]: Pure static/class methods ONLY. No instance state, no Redis, no LLM.
# 2. [Pattern]: All functions operate on structured dicts (Gemini Content format).
# 3. [Gotcha]: Imported by brain.py — zero circular imports. No sibling agent imports.
# 4. [Boundary]: _build_contents stays in brain.py (needs self.blackboard, self._skill_loader).
# 5. [Batch]: build_single_function_response returns ONE dict (not list) for multi-FR assembly.
#    compress_contents uses FC/FR count parity for atomic pruning of batch pairs.
# 6. [Constraint]: _get_part_sig validates snake_case and camelCase keys independently (rejecting bool and blank str).
#    _apply_sibling_signature propagates standalone carrier signatures onto unsigned FCs or the last thought=True part
#    without mutating caller dicts or emitting empty {} dicts; turn_to_parts filters thought=True and empty "" text.
# 7. [Budget]: Default _CONTENT_BUDGET=60000, _TAIL_BUDGET=40000 tokens (env-configurable, clamped [2000, 1000000]).
# 8. [Decay]: Tool turns older than DEFAULT_TURN_DECAY_DISTANCE (10, src/utils/turn_decay.py) turns whose payload is
#    > DECAY_MIN_CHARS (400) decay into XML-fenced reference tags (<blackboard_evidence_reference>) to shed context
#    while preserving skill prefixes and recall pointers. Callers decide `decay`; recall_pruned_turns results are
#    exempted by brain.py (they must not ping-pong back into decay).
# 9. [Security]: ALL untrusted turn text goes through prompt_sanitize.strip_xml_fences (looped, full tag union).
#    Do NOT reintroduce a local fence list. contents_have_pruned_or_decayed relies on that: a decay tag outside the
#    event-header part can only come from real decay.
# 10. [Pattern]: The prune notice is ONE canonical part (format_prune_notice) folded into Message 0. compress_contents
#    lifts notices from an earlier pass and merges their counts, so compress(compress(x)) never stacks notices. The
#    count is conversation ENTRIES (messages), not Blackboard turn numbers -- the notice carries no turn range.
"""Pure-function helpers for conversation content building and compression.

Extracted from brain.py for modularity. These have zero dependencies on
Brain instance state, Redis, or LLM adapters.
"""
from __future__ import annotations

import base64
import html
import logging
import os
import re
from typing import TYPE_CHECKING

from src.utils.jarvis_ack import is_jarvis_acknowledgment
from src.utils.prompt_sanitize import PROMPT_NAME_MAX_LEN, sanitize_prompt_text, strip_xml_fences
from src.utils.turn_decay import DECAY_MIN_CHARS

if TYPE_CHECKING:
    from src.models import ConversationTurn

logger = logging.getLogger("darwin.brain")


def _parse_budget_env(name: str, default: int, min_val: int = 2000, max_val: int = 1_000_000) -> int:
    val_str = os.environ.get(name)
    if not val_str:
        return default
    try:
        val = int(val_str)
    except (ValueError, TypeError):
        logger.warning("Invalid %s=%r; falling back to default %d", name, val_str, default)
        return default
    if val < min_val or val > max_val:
        clamped = max(min_val, min(val, max_val))
        logger.warning("%s=%d outside [%d, %d]; clamped to %d", name, val, min_val, max_val, clamped)
        return clamped
    return val


_CONTENT_BUDGET = _parse_budget_env("BRAIN_CONTENT_BUDGET_TOKENS", 60000)
_TAIL_BUDGET = min(_parse_budget_env("BRAIN_TAIL_BUDGET_TOKENS", 40000), _CONTENT_BUDGET)

def _valid_sig(val) -> str | bytes | None:
    """Validate a single thought signature value (rejecting bool and whitespace-only strings)."""
    if not val or isinstance(val, bool) or not isinstance(val, (str, bytes, bytearray)):
        return None
    if isinstance(val, str) and not val.strip():
        return None
    return bytes(val) if isinstance(val, bytearray) else val


def _get_part_sig(p: dict) -> str | bytes | None:
    """Read a non-empty thought signature (snake_case or camelCase) from a part dict."""
    s = _valid_sig(p.get("thought_signature"))
    if s is not None:
        return s
    return _valid_sig(p.get("thoughtSignature"))


def _is_empty_carrier_dict(p: dict) -> bool:
    """True when ``p`` is a standalone empty-text thought-signature carrier dict."""
    return (
        _get_part_sig(p) is not None
        and not p.get("thought")
        and not p.get("functionCall")
        and not p.get("function_call")
        and not p.get("text")
        and "bytes" not in p
        and not p.get("inline_data")
        and not p.get("file_data")
        and not p.get("executable_code")
        and not p.get("code_execution_result")
        and not p.get("functionResponse")
        and not p.get("function_response")
    )


def _apply_sibling_signature(parts: list[dict]) -> list[dict]:
    """Copy thought_signature onto unsigned functionCall (or trailing thought) parts.

    Source is the first sibling part in the same list that carries a valid
    thought_signature or thoughtSignature. Normalizes camelCase ``thoughtSignature``
    to ``thought_signature`` on shallow copies without mutating caller dicts in place,
    and omits parts that become empty ``{}`` after stripping invalid signature keys.
    """
    sig = None
    for p in parts:
        s = _get_part_sig(p)
        if s is not None:
            sig = s
            break
    has_camel_or_bad = any(
        "thoughtSignature" in p or ("thought_signature" in p and _valid_sig(p.get("thought_signature")) is None)
        for p in parts
    )
    if sig is None and not has_camel_or_bad:
        return parts

    has_fc = any(p.get("functionCall") for p in parts)
    last_thought_idx = -1
    if sig is not None and not has_fc:
        non_carrier_has_sig = any(
            _get_part_sig(p) is not None
            for p in parts
            if not _is_empty_carrier_dict(p)
        )
        if not non_carrier_has_sig:
            for idx, p in enumerate(parts):
                if p.get("thought"):
                    last_thought_idx = idx

    fixed: list[dict] = []
    changed = False
    for idx, p in enumerate(parts):
        p_has_camel_or_bad = (
            "thoughtSignature" in p
            or ("thought_signature" in p and _valid_sig(p.get("thought_signature")) is None)
        )
        p_sig = _get_part_sig(p)
        needs_sig = bool(
            sig is not None
            and p_sig is None
            and (p.get("functionCall") or idx == last_thought_idx)
        )
        if p_has_camel_or_bad or needs_sig:
            new_p = {k: v for k, v in p.items() if k not in ("thoughtSignature", "thought_signature")}
            effective_sig = p_sig if p_sig is not None else (sig if needs_sig else None)
            if effective_sig is not None:
                new_p["thought_signature"] = effective_sig
            if new_p:
                fixed.append(new_p)
            changed = True
        else:
            fixed.append(p)
    return fixed if changed else parts


def extract_model_parts(response_parts: list[dict] | None) -> list[dict]:
    """Extract model-role parts from response_parts for native FC replay.

    Preserves thought parts + functionCall + thought_signature.
    Retains standalone signature carriers during sibling-signature propagation
    so unsigned functionCall parts inherit the signature before empty carriers
    are stripped.
    """
    if not response_parts:
        return []
    if not any(p.get("functionCall") or p.get("thought") for p in response_parts):
        return []
    candidates = [
        p for p in response_parts
        if p.get("functionCall") or p.get("thought") or _get_part_sig(p)
    ]
    signed = _apply_sibling_signature(candidates)
    return [p for p in signed if p.get("functionCall") or p.get("thought")]


def format_evidence_decay_reference(turn_index: int, tool_name: str, char_count: int) -> str:
    """Format XML-fenced reference for decayed historical tool evidence."""
    safe_tool = html.escape(sanitize_prompt_text(str(tool_name or "tool"), max_len=PROMPT_NAME_MAX_LEN), quote=True)
    return (
        f'<blackboard_evidence_reference turn="{turn_index}" tool="{safe_tool}" chars="{char_count}">\n'
        f'Raw tool output stored in Blackboard Turn {turn_index}. '
        f'Call recall_pruned_turns(from_turn={turn_index}, to_turn={turn_index}) to retrieve full un-decayed payload.\n'
        f'</blackboard_evidence_reference>'
    )


def build_function_response(
    turn: "ConversationTurn",
    skill_prefix: str = "",
    decay_evidence: bool = False,
    turn_index: int = 0,
) -> list[dict]:
    """Synthesize functionResponse from tool_result turn evidence.

    FR name derived from FC part in response_parts (authoritative),
    NOT from turn.waitingFor (unreliable on gate rejections and grounding).
    """
    tool_name = "unknown_tool"
    if turn.response_parts:
        for p in turn.response_parts:
            if p.get("functionCall"):
                tool_name = p["functionCall"].get("name", "unknown_tool")
                break
    if tool_name == "unknown_tool" and turn.waitingFor:
        tool_name = turn.waitingFor
    if tool_name == "unknown_tool":
        logger.warning(
            "build_function_response: no FC name found (turn %s, waitingFor=%s)",
            getattr(turn, "turn", "?"), turn.waitingFor,
        )

    response_text = turn.evidence or turn.thoughts or ""
    raw_chars = len(response_text)
    if decay_evidence and raw_chars > DECAY_MIN_CHARS:
        turn_idx = turn_index or getattr(turn, "turn", 0)
        ref = format_evidence_decay_reference(turn_idx, tool_name, raw_chars)
        response_text = f"{skill_prefix}\n{ref}" if skill_prefix else ref
    else:
        response_text = strip_xml_fences(response_text)
        if skill_prefix:
            response_text = f"{skill_prefix}\n{response_text}"
    return [{"functionResponse": {"name": tool_name, "response": {"result": response_text}}}]


def build_single_function_response(
    turn: "ConversationTurn",
    fc_name: str | None = None,
    decay_evidence: bool = False,
    turn_index: int = 0,
) -> dict:
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
    raw_chars = len(response_text)
    if decay_evidence and raw_chars > DECAY_MIN_CHARS:
        turn_idx = turn_index or getattr(turn, "turn", 0)
        response_text = format_evidence_decay_reference(turn_idx, tool_name, raw_chars)
    else:
        response_text = strip_xml_fences(response_text)
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
            res = fr.get("response", {})
            if isinstance(res, dict) and len(res) == 1 and "result" in res and isinstance(res["result"], str):
                chars += len(res["result"]) + 14 + len(fr.get("name", ""))
            else:
                chars += len(str(res)) + len(fr.get("name", ""))
        sig = _get_part_sig(part) or ""
        chars += len(str(sig))
    return chars


def estimate_tokens(contents: list[dict]) -> int:
    """Rough token estimate: ~4 chars per token."""
    total_chars = sum(estimate_msg_tokens(msg) for msg in contents)
    return total_chars // 4


# Prune notice (folded into Message 0). One canonical shape so compress_contents can recognise a
# notice from an earlier pass and MERGE counts instead of stacking a second, contradictory notice.
PRUNE_NOTICE_PREFIX = "[Context pruned:"
_PRUNE_NOTICE_COUNT_RE = re.compile(r"\[Context pruned: (\d{1,9}) earlier conversation entries")
_DECAY_REF_TAG = "<blackboard_evidence_reference"


def format_prune_notice(count: int) -> dict:
    """Prune-notice part. ``count`` is conversation entries (messages), NOT Blackboard turn numbers."""
    return {
        "text": (
            f"\n\n{PRUNE_NOTICE_PREFIX} {count} earlier conversation entries pruned for context window. "
            f"Use recall_pruned_turns(from_turn, to_turn) to retrieve earlier turns by Blackboard turn number if needed.]"
        )
    }


def prune_notice_count(part: dict) -> int | None:
    """Pruned-entry count if ``part`` is a prune notice, else None. Anchored and length-capped (linear)."""
    text = part.get("text") if isinstance(part, dict) else None
    if not isinstance(text, str):
        return None
    m = _PRUNE_NOTICE_COUNT_RE.match(text[:96].lstrip())
    return int(m.group(1)) if m else None


def contents_have_pruned_or_decayed(contents: list[dict]) -> bool:
    """True when ``contents`` carries a real prune notice or a decayed-evidence reference.

    Tight on purpose (gates recall_pruned_turns): a notice only counts as the START of a Message 0 part,
    and the event header part (which embeds unsanitized event fields) is never scanned for decay tags.
    Turn text has its fences stripped upstream, so a decay tag elsewhere can only come from real decay.
    """
    if not contents:
        return False
    if any(prune_notice_count(p) is not None for p in contents[0].get("parts", [])):
        return True
    for mi, msg in enumerate(contents):
        for pi, part in enumerate(msg.get("parts", [])):
            if mi == 0 and pi == 0:
                continue
            if _DECAY_REF_TAG in str(part.get("text") or ""):
                return True
            fr = part.get("functionResponse")
            if isinstance(fr, dict):
                res = fr.get("response")
                if isinstance(res, dict) and _DECAY_REF_TAG in str(res.get("result") or ""):
                    return True
    return False


def compress_contents(
    contents: list[dict],
    max_tokens: int | None = None,
    tail_budget: int | None = None,
) -> list[dict]:
    """Tail-keep prune: drop oldest conversation turns when over budget.

    First message (event context header) always kept intact.
    No truncation of individual turns — full fidelity until prune threshold.
    When over budget: keep header + last ~tail_budget tokens of conversation from the end.
    FC/FR pairs are pruned atomically — never orphan one without the other.
    """
    resolved_max = _CONTENT_BUDGET if max_tokens is None else max_tokens
    resolved_tail = _TAIL_BUDGET if tail_budget is None else tail_budget

    if not contents or estimate_tokens(contents) < resolved_max:
        return contents

    if len(contents) == 1:
        last_msg = dict(contents[0])
        parts = list(last_msg.get("parts", []))
        if len(parts) <= 3:
            return contents
        if any("functionCall" in p or "functionResponse" in p for p in parts):
            return contents

        header_len = 2 if len(parts) > 2 and "--- CONVERSATION ---" in str(parts[1].get("text", "")) else 1
        header_parts = parts[:header_len]
        action_parts = parts[-1:]
        # Notices from an earlier pass are lifted out (and their counts carried) so they are never
        # pruned/kept as ordinary conversation parts and never stack with the new one.
        conv_parts = []
        prior_pruned = 0
        for cp in parts[header_len:-1]:
            prior_count = prune_notice_count(cp)
            if prior_count is None:
                conv_parts.append(cp)
            else:
                prior_pruned += prior_count
        if not conv_parts:
            return contents

        tail_budget_chars = min(resolved_tail, resolved_max) * 4
        running_chars = sum(len(str(p.get("text", ""))) for p in header_parts + action_parts)
        kept_parts = []
        for p in reversed(conv_parts):
            p_chars = len(str(p.get("text", "")))
            if running_chars + p_chars > tail_budget_chars and kept_parts:
                break
            kept_parts.append(p)
            running_chars += p_chars
        kept_parts.reverse()

        if len(kept_parts) < len(conv_parts):
            pruned_count = prior_pruned + len(conv_parts) - len(kept_parts)
            last_msg["parts"] = header_parts + [format_prune_notice(pruned_count)] + kept_parts + action_parts
            return [last_msg]
        return contents

    context_msg = dict(contents[0])
    # Lift prune notices left by an earlier pass out of Message 0 (idempotence): their counts merge into
    # the single notice re-inserted below, at the position the earlier one held.
    header_parts: list[dict] = []
    prior_pruned = 0
    notice_at: int | None = None
    for hp in contents[0].get("parts", []):
        prior_count = prune_notice_count(hp)
        if prior_count is None:
            header_parts.append(hp)
        else:
            prior_pruned += prior_count
            if notice_at is None:
                notice_at = len(header_parts)
    context_msg["parts"] = header_parts
    conv_msgs = list(contents[1:])

    # Trailing standalone prompt protection:
    trailing_prompt_msg = None
    if (
        len(conv_msgs) >= 2
        and conv_msgs[-1].get("role") == "user"
        and not any("functionResponse" in p for p in conv_msgs[-1].get("parts", []))
        and (
            conv_msgs[-2].get("role") == "user"
            or (estimate_msg_tokens(conv_msgs[-1]) // 4) <= 250
        )
    ):
        trailing_prompt_msg = {"role": "user", "parts": list(conv_msgs[-1].get("parts", []))}
        conv_msgs = conv_msgs[:-1]

    header_tokens = estimate_msg_tokens(context_msg) // 4
    trailing_tokens = (estimate_msg_tokens(trailing_prompt_msg) // 4) if trailing_prompt_msg else 0
    effective_tail = min(resolved_tail, max(0, resolved_max - header_tokens - trailing_tokens - 50))

    _sig_v2 = os.environ.get("BRAIN_THOUGHT_SIG_V2", "false").lower() in ("true", "1", "yes")
    pair_buddy: dict[int, int] = {}
    for i in range(len(conv_msgs) - 1):
        msg_i = conv_msgs[i]
        msg_next = conv_msgs[i + 1]
        if msg_i.get("role") != "model" or msg_next.get("role") != "user":
            continue
        fc_count = sum(1 for p in msg_i.get("parts", []) if p.get("functionCall"))
        fr_count = sum(1 for p in msg_next.get("parts", []) if p.get("functionResponse"))
        if _sig_v2:
            if fc_count > 0 and fr_count > 0 and fc_count == fr_count:
                pair_buddy[i] = i + 1
                pair_buddy[i + 1] = i
        else:
            if fc_count > 0 and fr_count > 0:
                pair_buddy[i] = i + 1
                pair_buddy[i + 1] = i

    kept_indices: list[int] = []
    kept_set: set[int] = set()
    running_tokens = 0

    for rev_idx in range(len(conv_msgs) - 1, -1, -1):
        if rev_idx in kept_set:
            continue
        msg = conv_msgs[rev_idx]
        msg_tokens = estimate_msg_tokens(msg) // 4

        buddy_idx = pair_buddy.get(rev_idx)
        pair_tokens = msg_tokens
        if buddy_idx is not None and buddy_idx not in kept_set:
            pair_tokens += estimate_msg_tokens(conv_msgs[buddy_idx]) // 4

        if running_tokens + pair_tokens > effective_tail and kept_indices:
            break

        kept_indices.append(rev_idx)
        kept_set.add(rev_idx)
        running_tokens += msg_tokens
        if buddy_idx is not None and buddy_idx not in kept_set:
            kept_indices.append(buddy_idx)
            kept_set.add(buddy_idx)
            running_tokens += estimate_msg_tokens(conv_msgs[buddy_idx]) // 4

    kept_indices.sort()
    kept = [conv_msgs[i] for i in kept_indices]

    newly_pruned = len(conv_msgs) - len(kept)
    notice_pos = len(context_msg["parts"]) if notice_at is None else notice_at
    if newly_pruned:
        # Cut Boundary Alternation Alignment:
        # Guarantee [context_msg] + kept never has consecutive user messages or orphaned FR
        while kept and kept[0].get("role") == "user":
            if any("functionResponse" in p for p in kept[0].get("parts", [])):
                kept.pop(0)
                newly_pruned += 1  # dropped orphan FR is pruned too: keep the notice count honest
            else:
                context_msg["parts"].extend(kept.pop(0).get("parts", []))

    total_pruned = prior_pruned + newly_pruned
    if total_pruned:
        context_msg["parts"].insert(notice_pos, format_prune_notice(total_pruned))

    result = [context_msg] + kept
    if trailing_prompt_msg:
        if result and result[-1].get("role") == "user":
            merged_last = dict(result[-1])
            merged_last["parts"] = list(result[-1].get("parts", [])) + list(trailing_prompt_msg.get("parts", []))
            result[-1] = merged_last
        else:
            result.append(trailing_prompt_msg)

    return result


def normalize_response_parts(raw_parts: list) -> list[dict]:
    """Normalize SDK Part objects or plain dicts to plain dicts for Redis storage.

    Handles camelCase vs snake_case thought_signature across SDK versions.
    """
    preserved = []
    for part in raw_parts:
        p: dict = {}
        if isinstance(part, dict):
            if part.get("text"):
                p["text"] = str(part["text"])
            if part.get("thought"):
                p["thought"] = True
            fc = part.get("functionCall") or part.get("function_call")
            if fc:
                raw_args = fc.get("args") if isinstance(fc, dict) else getattr(fc, "args", None)
                fc_name = fc.get("name") if isinstance(fc, dict) else getattr(fc, "name", "")
                args = {}
                if raw_args:
                    args = {str(k): str(v) if isinstance(v, bytes) else v for k, v in dict(raw_args).items()}
                p["functionCall"] = {"name": str(fc_name), "args": args}
            sig = _get_part_sig(part)
        else:
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
            sig = _valid_sig(getattr(part, 'thought_signature', None))
            if sig is None:
                sig = _valid_sig(getattr(part, 'thoughtSignature', None))
        if sig is not None:
            p['thought_signature'] = (
                base64.b64encode(bytes(sig)).decode('ascii')
                if isinstance(sig, (bytes, bytearray))
                else str(sig)
            )
        if p:
            preserved.append(p)
    return preserved or [{"text": ""}]


def turn_to_parts(
    turn: "ConversationTurn",
    decay_evidence: bool = False,
    turn_index: int = 0,
) -> list[dict]:
    """Convert a single ConversationTurn to semantically-labelled parts.

    Labels: [USER], [SYSTEM tool], [AGENT y], [FRIDAY action].
    Brain's own response_parts are unlabelled (raw passthrough).
    """
    if turn.actor == "brain" and turn.action in ("thoughts", "intermediate"):
        return []

    if turn.actor == "dispatcher" and turn.action in ("acknowledge", "connected"):
        return []

    if turn.actor == "brain" and turn.action == "tool_result":
        tool_name = turn.waitingFor or "tool"
        raw_text = turn.evidence or turn.thoughts or ""
        if decay_evidence and len(raw_text) > DECAY_MIN_CHARS:
            turn_idx = turn_index or getattr(turn, "turn", 0)
            text = f"[SYSTEM {tool_name}]: {format_evidence_decay_reference(turn_idx, tool_name, len(raw_text))}"
        else:
            raw_text = strip_xml_fences(raw_text)
            text = f"[SYSTEM {tool_name}]: {raw_text}"
        return [{"text": text}]

    if (
        turn.actor == "brain"
        and turn.response_parts
        and any(p.get("functionCall") for p in turn.response_parts)
    ):
        # Apply the same sibling-sig defense as extract_model_parts() so a
        # functionCall part missing thought_signature (e.g. one half of a
        # dual-stored FC that lost its sig in an earlier normalization
        # pass) still gets it from a sibling part -- this raw passthrough
        # is also what a later FC-dedup pass may leave standing as the
        # final record for this turn.
        signed = _apply_sibling_signature(list(turn.response_parts))
        non_carriers = [p for p in signed if not _is_empty_carrier_dict(p)]
        return non_carriers if non_carriers else signed

    if turn.actor == "brain" and turn.action == "response":
        text = turn.thoughts or ""
        if not text and turn.response_parts:
            text = "".join(
                p.get("text", "") for p in turn.response_parts if "text" in p and not p.get("thought")
            )
        if turn.evidence:
            text = f"{text}\n{turn.evidence}" if text else turn.evidence
        text = strip_xml_fences(text)
        if not text:
            return []
        parts: list[dict] = [{"text": text}]
        if turn.response_parts:
            for rp in turn.response_parts:
                sig = _get_part_sig(rp)
                if sig:
                    parts[0]["thought_signature"] = sig
                    break
        return parts

    text = ""
    if turn.actor == "brain":
        text = turn.thoughts or ""
        if turn.evidence:
            raw_ev = turn.evidence
            if decay_evidence and len(raw_ev) > DECAY_MIN_CHARS:
                turn_idx = turn_index or getattr(turn, "turn", 0)
                raw_ev = format_evidence_decay_reference(turn_idx, turn.action, len(raw_ev))
            else:
                raw_ev = strip_xml_fences(raw_ev)
            text = f"{text}\n{raw_ev}" if text else raw_ev
        else:
            text = strip_xml_fences(text)
        if turn.action not in ("response",):
            text = f"[FRIDAY {turn.action}]: {text}" if text else f"[FRIDAY {turn.action}]"
    elif turn.actor == "user":
        raw = turn.thoughts or turn.result or ""
        raw = strip_xml_fences(raw)
        action_suffix = f" ({turn.action})" if turn.action and turn.action != "message" else ""
        # user_name is operator/Slack-supplied: sanitize + cap so a crafted display name
        # cannot break out of the [USER ...] prefix or inject lines into the turn text.
        safe_name = sanitize_prompt_text(turn.user_name, max_len=PROMPT_NAME_MAX_LEN).strip()
        if safe_name:
            prefix = f"[USER {safe_name}{action_suffix}]"
        else:
            prefix = f"[USER{action_suffix}]"
        text = f"{prefix}: {raw}" if raw else prefix
    elif turn.actor == "jarvis" and turn.action == "message":
        raw = turn.thoughts or turn.result or ""
        raw = strip_xml_fences(raw)
        if is_jarvis_acknowledgment(raw):
            text = f"[AGENT jarvis]: {raw}" if raw else "[AGENT jarvis]"
        elif "?" in raw or any(
            raw.lower().lstrip().startswith(prefix)
            for prefix in ("could you", "can you", "what", "why", "how", "where", "when", "who", "please")
        ):
            text = (
                f"[AGENT jarvis]: {raw}\n\n"
                f"JARVIS asked you a question. Send your answer back to JARVIS before doing anything else."
            )
        else:
            text = f"[AGENT jarvis]: {raw}" if raw else "[AGENT jarvis]"
    else:
        raw = turn.evidence or turn.result or turn.thoughts or ""
        if decay_evidence and len(raw) > DECAY_MIN_CHARS:
            turn_idx = turn_index or getattr(turn, "turn", 0)
            raw = format_evidence_decay_reference(turn_idx, turn.actor, len(raw))
        else:
            raw = strip_xml_fences(raw)
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
