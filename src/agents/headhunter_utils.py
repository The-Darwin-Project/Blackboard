# BlackBoard/src/agents/headhunter_utils.py
# @ai-rules:
# 1. [Constraint]: Zero-import module. No headhunter/adapter/blackboard imports allowed.
# 2. [Pattern]: Shared constants for all Headhunter adapters.
# 3. [Gotcha]: Imported by headhunter.py, headhunter_gitlab.py, and headhunter_github.py
#    — circular imports are fatal if this file imports any of those.
# 4. [Security]: _sanitize_xml_fence is the zero-import Headhunter prompt-fence sanitizer (all 6 named fences:
#    description, job_log, comments, mention_request, issue_body, review_feedback) used for issue_body/review_feedback
#    and re-exported from headhunter.py. For full untrusted-text sanitization (fences + PII + "[!call:" + controls),
#    callers use src/utils/prompt_sanitize.{sanitize_untrusted_block,sanitize_untrusted_line} (keep fence tag lists in sync).
#    Regex MUST stay linear: no adjacent optional \s* around `/`, and the attribute run is [^<>]* (NOT [^>]*, which is
#    quadratic on '<description' * N). Stripping loops are capped at _FENCE_MAX_PASSES; if a nested payload still
#    reassembles a tag, every '<' is dropped in one linear pass.
"""Shared constants for Headhunter adapters. Import-cycle-safe (no sibling imports)."""
from __future__ import annotations

import os
import re


def _safe_int(env_key: str, default: int) -> int:
    """Parse int env var with fallback on invalid values."""
    raw = os.getenv(env_key)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default


_COMMENT_LIMIT = _safe_int("HEADHUNTER_COMMENT_LIMIT", 2000)
_DESC_SAFETY_CAP = _safe_int("HEADHUNTER_DESCRIPTION_CAP", 100_000)


_XML_FENCE_TAG = re.compile(
    r"<\s*(?:/\s*)?(?:description|job_log|comments|mention_request|issue_body|review_feedback)\b"
    r"(?:[^<>]*>)?",
    re.IGNORECASE,
)
# Nested-split depth beyond this is adversarial; bounding the passes keeps the sanitizer O(passes * n).
_FENCE_MAX_PASSES = 8


def _sanitize_xml_fence(text: str) -> str:
    """Strip XML fence tags that could break prompt fencing.

    Removes any case/whitespace variant of opening or closing tags for all prompt fences
    (``</MENTION_REQUEST>``, ``</review_feedback >``, ``< /description>``). Repeats (at most
    ``_FENCE_MAX_PASSES`` times) so nested payloads like ``</review_</review_feedback>feedback>``
    cannot reassemble a tag after one pass. If the cap is hit and a fence tag still matches
    (adversarial nesting), every ``<`` is dropped in one linear pass: without ``<`` no tag can exist.
    """
    if not text:
        return text
    for _ in range(_FENCE_MAX_PASSES):
        stripped = _XML_FENCE_TAG.sub("", text)
        if stripped == text:
            return text
        text = stripped
    if _XML_FENCE_TAG.search(text):
        text = text.replace("<", "")
    return text
