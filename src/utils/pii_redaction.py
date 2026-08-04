# BlackBoard/src/utils/pii_redaction.py
# @ai-rules:
# 1. [Constraint]: No project imports here -- this module must be importable from both
#    src/agents/ and src/adapters/ without creating a cross-layer dependency in either direction.
# 2. [Constraint]: NOT exhaustive. Covers emails, IPv4 addresses, JWTs, and named-prefix secrets
#    (Bearer tokens, AWS/GitHub/Slack/Google API-key formats, generic key=value/key: value pairs
#    for api_key/secret/password/token fields, matched via negative lookbehind so
#    SCREAMING_SNAKE_CASE names like DB_PASSWORD= are caught, not just space/start-prefixed
#    ones) -- categories with distinctive patterns and low false-positive rates. Value charset
#    intentionally excludes whitespace (unbounded on the right with no terminator otherwise) but
#    includes common password punctuation. Does NOT cover unrecognized/unnamed high-entropy
#    strings or free-text PII (names, addresses, space-containing secret values). Full
#    arbitrary-secret detection is a separately-scoped effort.
# 3. [Pattern]: Consolidated from two independent fixes for the same codereview HIGH finding on
#    PR #151 -- this repo's own Darwin agent (darwin-agent@darwin-project.io) autonomously pushed
#    a fix to live_api_adapter.py in parallel with a manually-driven session fix that additionally
#    extracted the utility to this shared module (so Archivist's Ranking API calls get the same
#    coverage). Merged: shared-module placement (manual fix) + fuller pattern set (Darwin's fix).
"""Shared PII/secret redaction for text eligible for durable external storage.

Used by:
- LiveAPIAdapter (JARVIS): text sent into a Live API session with store_context=True
  persists for the WHOLE session, not just one turn.

Archivist Ranking API redaction is a separate restore (not wired on this branch).
"""
from __future__ import annotations

import re

_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_IPV4_RE = re.compile(r"\b(?:\d{1,3}\.){3}\d{1,3}\b")
_JWT_RE = re.compile(r"\beyJ[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\.[A-Za-z0-9_-]{5,}\b")
_AWS_ACCESS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")
_GOOGLE_API_KEY_RE = re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")
_GITHUB_TOKEN_RE = re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")
_SLACK_TOKEN_RE = re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")
_BEARER_TOKEN_RE = re.compile(r"\bBearer\s+[A-Za-z0-9\-._~+/!@#$%^&*]{8,}=*", re.IGNORECASE)
# Catch-all for "key=value"/"key: value" secrets (api_key, token, secret, password, ...).
# Codereview finding: `\b` before the keyword failed on SCREAMING_SNAKE_CASE names
# (DB_PASSWORD=, AWS_SECRET_ACCESS_KEY=) because '_' and the keyword's first letter are
# both \w chars, so \b never fires at that boundary. A negative lookbehind for
# alnum-only (letting '_', string-start, and punctuation all count as separators)
# fixes the common real-world naming convention without over-matching compound words
# like "MYPASSWORD" (still requires a non-alnum/underscore boundary immediately before).
# Value charset widened (space excluded -- unbounded on the right with no terminator --
# but common password punctuation included) per codereview finding on charset coverage.
_KEYED_SECRET_RE = re.compile(
    r"(?<![A-Za-z0-9])(api[_-]?key|access[_-]?key|secret|password|passwd|token|authorization)"
    r"([:=])\s*(['\"]?)[A-Za-z0-9\-._~+/!@#$%^&*]{8,}=*\3",
    re.IGNORECASE,
)


def redact_pii(text: str) -> str:
    """Strip email addresses, IPv4 addresses, JWTs, and common named-prefix/keyed secret
    patterns before text becomes eligible for durable external storage. See module
    docstring and shebang for exhaustiveness caveats.
    """
    if not text:
        return text
    text = _EMAIL_RE.sub("[redacted-email]", text)
    text = _JWT_RE.sub("[redacted-jwt]", text)
    text = _AWS_ACCESS_KEY_RE.sub("[redacted-aws-key]", text)
    text = _GOOGLE_API_KEY_RE.sub("[redacted-google-api-key]", text)
    text = _GITHUB_TOKEN_RE.sub("[redacted-github-token]", text)
    text = _SLACK_TOKEN_RE.sub("[redacted-slack-token]", text)
    text = _BEARER_TOKEN_RE.sub("Bearer [redacted-token]", text)
    # Preserve the original separator (':' or '=') instead of always rewriting to '='
    # (codereview cosmetic finding).
    text = _KEYED_SECRET_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}[redacted-secret]", text)
    text = _IPV4_RE.sub("[redacted-ip]", text)
    return text
