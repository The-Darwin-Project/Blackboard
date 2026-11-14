# src/utils/prompt_sanitize.py
# @ai-rules:
# 1. [Constraint]: Pure, sync, dependency-free -- imported by auth.py, agents/llm/prompt.py and
#    agents/context_parts.py. Do NOT import from src.agents or src.auth here (import cycles).
# 2. [Pattern]: Line-breaking chars (\t \n \r \v \f, C1 NEL, U+2028/U+2029) become a single space so
#    text stays on one line; every other control/format char is dropped. Length cap is applied LAST.
#    Dropped set: C0/DEL/C1 controls, soft hyphen, ALM, CGJ (034F), Mongolian FVS/vowel separator
#    (180B-180E), zero-width/bidi/invisible-operator marks (200B-200F, 202A-202E, 2060-206F), variation
#    selectors (FE00-FE0F, E0100-E01EF), BOM, and Unicode Tags (E0000-E007F, invisible payload smuggling).
# 3. [Gotcha]: Stripping happens before the length cap, so invisible chars never consume the budget
#    and a cap boundary cannot leave half of a stripped sequence behind.
# 4. [Gotcha]: Patterns use explicit \u escapes on purpose -- literal invisible chars in source are
#    unreviewable.
# 5. [Pattern]: sanitize_title/fallback_title are the single title pipeline (PATCH validator, LLM namer,
#    chat/slack fallbacks): line breaks -> space FIRST, then strip invisibles, then collapse \s+, cap LAST.
# 6. [Security]: strip_xml_fences is the SINGLE prompt-fence sanitizer (context_parts, prompt, brain,
#    handlers_cross_event). It removes the full tag union and LOOPS until unchanged so nested split tags
#    ("</func</functionResponse>tionResponse>") cannot reassemble a fence. Callers that also redact PII MUST
#    strip first, redact second, defang "[!call:" third, truncate LAST (a fence spliced inside a secret
#    would otherwise defeat redaction and rejoin after the strip).
"""Sanitize untrusted scalars (display names, CI fields) embedded in Brain/FRIDAY prompts."""
from __future__ import annotations

import re

# Cap for human display names rendered into prompts / [USER <name>] turn prefixes.
PROMPT_NAME_MAX_LEN = 80

# Whitespace-like line breakers -> single space (keeps the value on one prompt line).
_LINE_BREAKERS = re.compile("[\\t\\n\\r\\x0b\\x0c\\x85\\u2028\\u2029]")

# Dropped outright: ASCII C0 + DEL + C1 controls, soft hyphen, Arabic letter mark, combining grapheme
# joiner (034F), Mongolian free variation selectors + vowel separator (180B-180E), zero-width
# space/joiners, LRM/RLM, bidi embeds/overrides (202A-202E), word joiner and invisible operators
# (2060-206F, includes bidi isolates 2066-2069), variation selectors (FE00-FE0F), the BOM/ZWNBSP,
# Unicode Tag chars (E0000-E007F, used to smuggle invisible ASCII payloads) and the variation
# selectors supplement (E0100-E01EF).
_STRIP_CHARS = re.compile(
    "[\\x00-\\x1f\\x7f-\\x9f\\u00ad\\u034f\\u061c\\u180b-\\u180e\\u200b-\\u200f\\u202a-\\u202e"
    "\\u2060-\\u206f\\ufe00-\\ufe0f\\ufeff\\U000e0000-\\U000e007f\\U000e0100-\\U000e01ef]"
)


def sanitize_prompt_text(value: object, *, max_len: int) -> str:
    """Coerce an untrusted scalar to a single-line, control/format-char-free, length-capped string."""
    text = "" if value is None else str(value)
    text = _LINE_BREAKERS.sub(" ", text)
    text = _STRIP_CHARS.sub("", text)
    return text[:max_len]


# Every delimiter an untrusted string must not be able to forge inside a Brain prompt. Union of the
# per-module lists that previously diverged (context_parts, prompt, brain). Literal alternation only
# (no quantifiers), so matching is linear in the input length.
_FENCE_TAGS = (
    "</blackboard_evidence_reference>",
    "<functionResponse>", "</functionResponse>",
    "<functionCall>", "</functionCall>",
    "<context>", "</context>",
    "<description>", "</description>",
    "</job_log>", "</comments>", "</mention_request>", "</issue_body>",
    "--- CONVERSATION ---",
)
# The decay-reference OPEN tag is removed WITH its attributes (bounded, no nested quantifier): leaving
# `turn="9" tool="x">` behind would splice garbage into whatever the tag was embedded in.
_EVIDENCE_OPEN = r"<blackboard_evidence_reference[^<>]{0,512}>?"
_FENCE_RE = re.compile(
    "|".join([_EVIDENCE_OPEN] + [re.escape(t) for t in sorted(_FENCE_TAGS, key=len, reverse=True)])
)
_DASH_RUN_RE = re.compile(r"-{3,}")
# Nested-split depth beyond this is adversarial; bounding the passes keeps the sanitizer O(passes * n).
_FENCE_MAX_PASSES = 8


def strip_xml_fences(text: str) -> str:
    """Remove prompt-fence tags/delimiters, looping until a pass changes nothing.

    A single pass is bypassable: removing the inner tag of ``<context<context>>`` reassembles
    ``<context>``. When the pass cap is hit without converging (adversarial nesting), fall back to
    deleting every ``<`` and collapsing ``---`` runs, which cannot form any fence tag or delimiter.
    """
    if not text:
        return ""
    for _ in range(_FENCE_MAX_PASSES):
        cleaned = _FENCE_RE.sub("", text)
        if cleaned == text:
            return cleaned
        text = cleaned
    return _DASH_RUN_RE.sub("--", text.replace("<", ""))


UNTITLED_EVENT = "Untitled Event"
FALLBACK_TITLE_MAX_LEN = 60


def sanitize_title(value: object, *, max_len: int | None = None) -> str:
    """Normalize an event title: breaks->space, strip invisibles, collapse whitespace, optional cap.

    Returns "" when nothing visible remains (e.g. zero-width-only input) so callers can reject it.
    """
    text = "" if value is None else str(value)
    text = _STRIP_CHARS.sub("", _LINE_BREAKERS.sub(" ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text if max_len is None else text[:max_len].strip()


def fallback_title(value: object) -> str:
    """Immediate (pre-LLM) event title derived from the first message text."""
    return sanitize_title(value, max_len=FALLBACK_TITLE_MAX_LEN) or UNTITLED_EVENT
