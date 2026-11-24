# src/utils/prompt_sanitize.py
# @ai-rules:
# 1. [Constraint]: Pure, sync, stdlib + intra-utils (.pii_redaction, re-only) -- imported by auth.py,
#    agents/llm/prompt.py, agents/context_parts.py, agents/brain.py, and agents/headhunter.py.
#    Do NOT import from src.agents or src.auth here (import cycles).
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
#    headhunter, handlers_cross_event). It removes the full tag union and LOOPS until unchanged so nested
#    split tags ("</func</functionResponse>tionResponse>") cannot reassemble a fence. Callers that also
#    redact PII MUST strip first, redact second, defang "[!call:" (case/whitespace-insensitive) third,
#    truncate LAST (a fence spliced inside a secret would otherwise defeat redaction and rejoin after strip).
# 7. [Security]: CONTROL_TOKEN_NAMES/CONTROL_TOKEN_PATTERN are the SINGLE definition of model control tokens
#    (<end_of_image>, <start_of_turn>, <thought>, ...; optional "/" and whitespace before ">", case-insensitive).
#    strip_control_tokens is the shared bounded fixed-point stripper (_CONTROL_TOKEN_MAX_PASSES, early exit when
#    unchanged); on non-convergence it deletes every "<" so nothing can reassemble. agents/llm/types.py and
#    gemini_client.py reuse both -- never re-inline a fixed-count strip loop.
"""Sanitize untrusted scalars (display names, CI fields) embedded in Brain/FRIDAY prompts."""
from __future__ import annotations

import re

from .pii_redaction import redact_pii

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
_INVISIBLE_CLASS = (
    "\\x7f-\\x9f\\u00ad\\u034f\\u061c\\u180b-\\u180e\\u200b-\\u200f\\u202a-\\u202e"
    "\\u2060-\\u206f\\ufe00-\\ufe0f\\ufeff\\U000e0000-\\U000e007f\\U000e0100-\\U000e01ef"
)
_STRIP_CHARS = re.compile("[\\x00-\\x1f" + _INVISIBLE_CLASS + "]")

# Multiline-safe variant of _STRIP_CHARS: preserves \t (\x09) and \n (\x0a) for Markdown blocks.
_MULTILINE_STRIP_CHARS = re.compile("[\\x00-\\x08\\x0b-\\x1f" + _INVISIBLE_CLASS + "]")

# Case- and whitespace-insensitive defang for synthetic tool-call syntax (`[!call:`, `[!\tCALL:`, etc.).
_CALL_TAG_RE = re.compile(r"\[\s*!\s*call\s*:", re.IGNORECASE)


def sanitize_prompt_text(value: object, *, max_len: int) -> str:
    """Coerce an untrusted scalar to a single-line, control/format-char-free, length-capped string."""
    text = "" if value is None else str(value)
    text = _LINE_BREAKERS.sub(" ", text)
    text = _STRIP_CHARS.sub("", text)
    return text[:max_len]


# Every delimiter an untrusted string must not be able to forge inside a Brain or Headhunter prompt.
# All XML tag patterns use bounded linear attribute runs ([^<>]{0,512}>)? so matching is O(n) and an
# unclosed opening tag cannot swallow trailing text.
_FENCE_TAGS = (
    "--- CONVERSATION ---",
)
# Linear bounded pattern covering Brain XML prompt fences (open/close/whitespace/attributes).
# Requires closing '>' so nested split tags like '<context<context>>' peel inner-outward per pass.
_BRAIN_FENCE_PATTERN = (
    r"<\s*(?:/\s*)?(?:functionResponse|functionCall|context|blackboard_evidence_reference)\b"
    r"[^<>]{0,512}>"
)
# Decay-reference OPEN tag is also removed if unclosed (bounded, linear).
_EVIDENCE_OPEN = r"<blackboard_evidence_reference[^<>]{0,512}>?"
# Linear bounded pattern covering all 7 Headhunter prompt fences (open/close/whitespace/attributes).
_HEADHUNTER_FENCE_PATTERN = (
    r"<\s*(?:/\s*)?(?:description|job_log|comments|mention_request|issue_body|review_feedback|pr_review_comments)\b"
    r"(?:[^<>]{0,512}>)?"
)
# Model control tokens that must never reach users or prompts. Each matches as <name> or </name>.
CONTROL_TOKEN_NAMES = (
    "end_of_image", "start_of_image", "end_of_turn", "start_of_turn",
    "internal_model_call", "image", "thought", "think",
)
CONTROL_TOKEN_PATTERN = r"<\/?(?:" + "|".join(CONTROL_TOKEN_NAMES) + r")\s*>"
CONTROL_TOKEN_RE = re.compile(CONTROL_TOKEN_PATTERN, re.IGNORECASE)
_FENCE_RE = re.compile(
    "|".join(
        [_EVIDENCE_OPEN, _BRAIN_FENCE_PATTERN, _HEADHUNTER_FENCE_PATTERN, CONTROL_TOKEN_PATTERN]
        + [re.escape(t) for t in sorted(_FENCE_TAGS, key=len, reverse=True)]
    ),
    re.IGNORECASE,
)
_DASH_RUN_RE = re.compile(r"-{3,}")
# Nested-split depth beyond this is adversarial; bounding the passes keeps the sanitizer O(passes * n).
_FENCE_MAX_PASSES = 8


# Nested-wrapper depth beyond this is adversarial (each level needs one pass to peel).
_CONTROL_TOKEN_MAX_PASSES = 8


def strip_control_tokens(text: str) -> str:
    """Remove model control tokens, looping to a fixed point (bounded by _CONTROL_TOKEN_MAX_PASSES).

    One pass is bypassable (``<end_<end_of_image>of_image>`` reassembles a token), so repeat until a
    pass changes nothing -- exiting early on the common clean case. If the cap is hit while a token
    still matches (adversarial nesting deeper than the cap), delete every ``<`` so none can form.
    """
    if not text:
        return text
    for _ in range(_CONTROL_TOKEN_MAX_PASSES):
        cleaned = CONTROL_TOKEN_RE.sub("", text)
        if cleaned == text:
            return cleaned
        text = cleaned
    if CONTROL_TOKEN_RE.search(text):
        return text.replace("<", "")
    return text


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


def _finalize_untrusted(
    text: str, *, max_len: int, pre_cap: int, redact: bool = True,
) -> str:
    """Apply entry pre-cap, fence stripping, optional PII redaction, call-tag defang, and final cap."""
    text = text[:pre_cap]
    text = strip_xml_fences(text)
    if redact:
        text = redact_pii(text)
    text = _CALL_TAG_RE.sub("[call:", text)
    return text[:max_len]


def sanitize_untrusted_block(
    value: object, *, max_len: int = 8000, redact: bool = True,
) -> str:
    """Sanitize multiline untrusted text (e.g. MR/PR descriptions, Bot Instructions, job logs).

    Preserves Markdown \\n and \\t while enforcing @ai-rules #6 pipeline order:
    normalize line endings -> strip invisibles/controls -> pre-cap -> strip XML fences ->
    optional redact PII -> defang "[!call:" -> cap LAST.
    """
    text = "" if value is None else str(value)
    text = text.replace("\r\n", "\n").replace("\r", "\n").replace("\u2028", "\n").replace("\u2029", "\n")
    text = _MULTILINE_STRIP_CHARS.sub("", text)
    return _finalize_untrusted(text, max_len=max_len, pre_cap=max(max_len * 4, 32768), redact=redact)


def sanitize_untrusted_line(
    value: object, *, max_len: int, redact: bool = True,
) -> str:
    """Sanitize single-line untrusted text (e.g. MR/PR titles) with full fence/PII/call defense.

    Pipeline order (@ai-rules #6): collapse line breaks -> strip invisibles/controls ->
    pre-cap (4x) -> strip XML fences -> optional redact PII -> defang "[!call:" -> cap LAST.
    """
    text = "" if value is None else str(value)
    text = _LINE_BREAKERS.sub(" ", text)
    text = _STRIP_CHARS.sub("", text)
    return _finalize_untrusted(text, max_len=max_len, pre_cap=max_len * 4, redact=redact)


_SAFE_KARGO_DNS_RE = re.compile(r"\A[a-z0-9](?:[a-z0-9.-]{0,118}[a-z0-9])?\Z")
_SAFE_KARGO_HEX_RE = re.compile(r"\A[0-9a-fA-F]{4,64}(?:-[0-9a-fA-F]{4,32}){0,6}\Z")

def sanitize_kargo_id(value: object, *, max_len: int = 120) -> str:
    cleaned = sanitize_untrusted_line(value, max_len=max_len, redact=False)
    stripped = cleaned.strip()
    if not stripped:
        return cleaned
    
    is_dns = _SAFE_KARGO_DNS_RE.match(stripped) and not stripped.startswith(("xox", "sk-", "ghp", "glpat"))
    if is_dns or _SAFE_KARGO_HEX_RE.match(stripped):
        return cleaned
    
    return redact_pii(cleaned)

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
