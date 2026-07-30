# BlackBoard/src/utils/pii_redaction.py
# @ai-rules:
# 1. [Constraint]: No project imports here -- this module must be importable from both
#    src/agents/ and src/adapters/ without creating a cross-layer dependency in either direction.
# 2. [Constraint]: NOT exhaustive. Covers emails, IPv4 addresses, and named-prefix secrets
#    (Bearer tokens, AWS/Google/GitHub API-key formats) -- categories with distinctive patterns
#    and low false-positive rates. Does NOT cover generic high-entropy strings, unknown secret
#    formats, or free-text PII (names, addresses). Full arbitrary-secret detection is a
#    separately-scoped effort (codereview finding).
"""Shared PII/secret redaction for text eligible for durable external storage.

Used by:
- LiveAPIAdapter (JARVIS): text sent into a Live API session with store_context=True
  persists for the WHOLE session, not just one turn.
- Archivist: text sent to the external Vertex Discovery Engine Ranking API.
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_SECRET_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"Bearer\s+[A-Za-z0-9\-_.]+"), "[redacted-bearer-token]"),
    (re.compile(r"AKIA[0-9A-Z]{16}"), "[redacted-aws-key]"),
    (re.compile(r"AIza[0-9A-Za-z_-]{35}"), "[redacted-google-api-key]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9]{36,}"), "[redacted-github-token]"),
]


def redact_pii(text: str) -> str:
    """Strip email addresses, IPv4 addresses, and common named-prefix secret/token
    patterns before text becomes eligible for durable external storage. See module
    docstring and shebang for exhaustiveness caveats.
    """
    if not text:
        return text
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _IPV4_RE.sub("[redacted-ip]", text)
    for pattern, replacement in _SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text
