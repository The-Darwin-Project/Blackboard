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
