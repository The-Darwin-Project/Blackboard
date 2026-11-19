# BlackBoard/src/agents/llm_error_classifier.py
# @ai-rules:
# 1. [Constraint]: Zero google.*/anthropic.*/.llm.gemini_client/.llm.types imports.
#    QuotaExhaustedError and RequestExceedsBurstError are imported lazily from .llm to preserve hexagonal boundaries.
# 2. [Pattern]: Pure stateless LLM error classification for Brain retry, backoff, and JARVIS stabilization.
# 3. [Invariant]: PEP 409 exception-graph walk + fail-closed precedence — any non-retryable cause anywhere in the
#    graph (timeouts, SSL/mTLS, LocalProtocolError, OS/cert-file errors, non-transport GoogleAuthError, 4xx codes
#    or client-error tokens) overrides transient/rate-limit signals.
"""Stateless transient, rate-limit, and error-turn classifiers for Brain LLM calls."""
from __future__ import annotations

import re
import ssl
from typing import Any

import httpx

_aiohttp: Any = None
try:
    import aiohttp as _aiohttp
except ImportError:  # pragma: no cover - optional in minimal test envs
    pass

_httpx2: Any = None
try:
    import httpx2 as _httpx2
except ImportError:  # pragma: no cover - optional transitive SDK transport
    pass

# Token-bounded HTTP status regexes (avoid matching token counts, float durations, or event IDs).
_TRANSIENT_HTTP_CODE_RE = re.compile(
    r"(?<![0-9a-zA-Z_.-])(?:408|429|500|502|503|504|529)(?![0-9a-zA-Z_.-])"
)
_RATE_LIMIT_429_RE = re.compile(r"(?<![0-9a-zA-Z_.-])429(?![0-9a-zA-Z_.-])")

# Non-transient client-error indicators (4xx HTTP and canonical gRPC client error codes).
_NON_TRANSIENT_CLIENT_ERR_RE = re.compile(
    r"(?<![0-9a-zA-Z_.-])(?:400|401|403|404|409|413|422|INVALID_ARGUMENT|PERMISSION_DENIED|UNAUTHENTICATED|NOT_FOUND)(?![0-9a-zA-Z_.-])"
)

# Canonical transient status tokens (gRPC and cloud service errors).
_TRANSIENT_STATUS_TOKENS = (
    "RESOURCE_EXHAUSTED",
    "UNAVAILABLE",
    "INTERNAL",
    "DEADLINE_EXCEEDED",
)

# Structured HTTP status codes considered transient.
_TRANSIENT_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504, 529})

# Transport disconnect phrases matched by both is_transient() and JARVIS stabilization.
_TRANSIENT_TRANSPORT_TOKENS = ("Server disconnected",)

# Markers matched on persisted brain.error turns by is_transient_llm_error_turn() without
# exposing stream-timeout phrases to is_transient() (timeouts use dedicated timeout_retries).
_TRANSIENT_STREAM_MARKERS = (
    "(transient):",
    *_TRANSIENT_TRANSPORT_TOKENS,
    "TTFB timed out",
    "inter-chunk timed out",
)


def _optional_exc_types(mod: Any, *names: str) -> tuple[type[BaseException], ...]:
    """Collect exception classes from an optionally imported transport module."""
    if mod is None:
        return ()
    return tuple(cls for name in names if isinstance(cls := getattr(mod, name, None), type))


_NON_RETRYABLE_DIRECT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    # Timeouts (handled by dedicated timeout_retries, not transient transport retry)
    TimeoutError,
    httpx.TimeoutException,
    # SSL / TLS / certificate verification errors
    ssl.SSLError,
    # Client-side protocol errors
    httpx.LocalProtocolError,
    # Local OS / cert-file errors
    FileNotFoundError,
    PermissionError,
    # Optional aiohttp non-retryable SSL / timeout errors
    *_optional_exc_types(_aiohttp, "ClientSSLError", "ServerFingerprintMismatch", "ServerTimeoutError"),
    # Optional httpx2 non-retryable timeout / protocol errors
    *_optional_exc_types(_httpx2, "TimeoutException", "LocalProtocolError"),
)

# MRO-matched non-retryable exceptions from SDK-owned dependencies (prefix-matched on module).
_NON_RETRYABLE_MRO_TARGETS = frozenset({
    ("requests.exceptions", "SSLError"),
    ("urllib3.exceptions", "SSLError"),
    ("google.auth.exceptions", "MutualTLSChannelError"),
    ("google.auth.exceptions", "ClientCertError"),
    ("requests.exceptions", "Timeout"),
    ("google.auth.exceptions", "TimeoutError"),
    ("urllib3.exceptions", "ReadTimeoutError"),
    ("httpcore", "TimeoutException"),
    ("httpcore2", "TimeoutException"),
    ("httpcore", "LocalProtocolError"),
    ("httpcore2", "LocalProtocolError"),
    ("anthropic", "APITimeoutError"),
})

_TRANSIENT_TRANSPORT_EXCEPTIONS: tuple[type[BaseException], ...] = (
    ConnectionError,
    httpx.NetworkError,
    httpx.RemoteProtocolError,
    *_optional_exc_types(
        _aiohttp,
        "ServerDisconnectedError",
        "ClientConnectorError",
        "ClientOSError",
        "ClientPayloadError",
    ),
    *_optional_exc_types(_httpx2, "NetworkError", "RemoteProtocolError"),
)


def _matches_mro(mro: tuple[type, ...], mod_prefix: str, name: str) -> bool:
    """True if any class in mro matches name and belongs to mod_prefix or a submodule of it."""
    prefix = f"{mod_prefix}."
    return any(
        cls.__name__ == name and (cls.__module__ == mod_prefix or cls.__module__.startswith(prefix))
        for cls in mro
    )


def _is_google_auth_transport_error(exc: BaseException, mro: tuple[type, ...] | None = None) -> bool:
    """True when exc is a google.auth.exceptions.TransportError without importing google.auth."""
    resolved_mro = type(exc).__mro__ if mro is None else mro
    return _matches_mro(resolved_mro, "google.auth.exceptions", "TransportError")


def _iter_exception_chain(exc: BaseException):
    """Cycle-safe exception graph walker honoring PEP 409 cause/context and transport wrappers."""
    stack: list[BaseException] = [exc]
    seen: set[int] = set()
    while stack:
        cur = stack.pop()
        obj_id = id(cur)
        if obj_id in seen:
            continue
        seen.add(obj_id)
        yield cur

        cause = cur.__cause__
        if isinstance(cause, BaseException):
            stack.append(cause)
        elif not getattr(cur, "__suppress_context__", False) and isinstance(cur.__context__, BaseException):
            stack.append(cur.__context__)

        for attr in ("os_error", "_os_error", "reason"):
            try:
                child = getattr(cur, attr, None)
            except Exception:
                child = None
            if isinstance(child, BaseException):
                stack.append(child)

        try:
            sub_exceptions = getattr(cur, "exceptions", None)
        except Exception:
            sub_exceptions = None
        if isinstance(sub_exceptions, tuple):
            for child in sub_exceptions:
                if isinstance(child, BaseException):
                    stack.append(child)

        for arg in getattr(cur, "args", ()):
            if isinstance(arg, BaseException):
                stack.append(arg)


def _extract_status_code(exc: BaseException) -> int | None:
    """Extract an integer HTTP status code from exc or exc.response without triggering deprecated .code."""
    try:
        response = getattr(exc, "response", None)
    except Exception:
        response = None
    for target in (exc, response):
        if target is None:
            continue
        for attr in ("status_code", "status", "code"):
            try:
                val = getattr(target, attr, None)
                if callable(val):
                    val = val()
            except Exception:
                val = None
            if isinstance(val, int) and not isinstance(val, bool):
                return val
    return None


def _has_non_retryable_cause(chain: tuple[BaseException, ...]) -> bool:
    """Fail-closed check across a materialized exception graph for non-retryable causes."""
    for node in chain:
        if isinstance(node, _NON_RETRYABLE_DIRECT_EXCEPTIONS):
            return True
        mro = type(node).__mro__
        if any(_matches_mro(mro, mod, name) for mod, name in _NON_RETRYABLE_MRO_TARGETS):
            return True
        if (
            _matches_mro(mro, "google.auth.exceptions", "GoogleAuthError")
            and not _is_google_auth_transport_error(node, mro)
        ):
            return True
        code = _extract_status_code(node)
        if code is not None and 400 <= code < 500 and code not in _TRANSIENT_STATUS_CODES:
            return True
        if _NON_TRANSIENT_CLIENT_ERR_RE.search(str(node)):
            return True
    return False


def is_rate_limit(e: Exception) -> bool:
    """Check if exception is specifically a 429 / quota rate-limit error (uses 30s base backoff)."""
    from .llm import QuotaExhaustedError, RequestExceedsBurstError

    if isinstance(e, (RequestExceedsBurstError, TimeoutError)):
        return False
    if isinstance(e, QuotaExhaustedError):
        return True

    chain = tuple(_iter_exception_chain(e))
    if _has_non_retryable_cause(chain):
        return False

    top_status = _extract_status_code(e)
    if top_status == 429:
        return True
    if top_status is not None and 400 <= top_status < 600:
        return False

    if any(_extract_status_code(node) == 429 for node in chain):
        return True

    for node in chain:
        err_str = str(node)
        err_lower = err_str.lower()
        if (
            "resource_exhausted" in err_lower
            or "quota exhausted" in err_lower
            or "too many requests" in err_lower
            or _RATE_LIMIT_429_RE.search(err_str)
        ):
            return True
    return False


def is_transient(e: Exception) -> bool:
    """Check if exception is a transient rate-limit, availability, or transport-disconnect error."""
    from .llm import QuotaExhaustedError, RequestExceedsBurstError

    if isinstance(e, RequestExceedsBurstError):
        return False  # Non-retryable burst overflow
    if isinstance(e, QuotaExhaustedError):
        return True

    chain = tuple(_iter_exception_chain(e))
    if _has_non_retryable_cause(chain):
        return False  # Fail closed on timeouts, SSL/mTLS, LocalProtocolError, OS/auth/4xx causes

    # Structured status code inspection across the chain (.status_code, .status, .code; plus .response)
    if any(_extract_status_code(node) in _TRANSIENT_STATUS_CODES for node in chain):
        return True

    # Chain-matched transport disconnects (GeminiAdapter aiohttp/httpx2 and ClaudeAdapter APIConnectionError)
    if any(
        isinstance(node, _TRANSIENT_TRANSPORT_EXCEPTIONS) or _is_google_auth_transport_error(node)
        for node in chain
    ):
        return True

    # Canonical transient status/transport tokens and bounded HTTP status codes across the chain
    tokens = (*_TRANSIENT_STATUS_TOKENS, *_TRANSIENT_TRANSPORT_TOKENS)
    for node in chain:
        err_str = str(node)
        if any(token in err_str for token in tokens) or _TRANSIENT_HTTP_CODE_RE.search(err_str):
            return True
    return False


def is_transient_llm_error_turn(turn: Any) -> bool:
    """True if ``turn`` is a brain.error turn whose text describes a transient LLM/quota failure.

    Recognizes the canonical ``"(transient):"`` marker emitted by Brain's exhausted error-turn path
    (guaranteeing parity with ``is_transient(last_error)`` for all transport disconnects), alongside
    ``_TRANSIENT_STREAM_MARKERS``, ``_TRANSIENT_STATUS_TOKENS``, and bounded ``_TRANSIENT_HTTP_CODE_RE``,
    guarded fail-closed by ``_NON_TRANSIENT_CLIENT_ERR_RE``. Accepts ConversationTurn objects or dicts.
    """
    if not turn:
        return False
    if isinstance(turn, dict):
        actor, action, thoughts = turn.get("actor"), turn.get("action"), turn.get("thoughts")
    else:
        actor = getattr(turn, "actor", None)
        action = getattr(turn, "action", None)
        thoughts = getattr(turn, "thoughts", None)
    if actor != "brain" or action != "error":
        return False
    text = str(thoughts or "")
    if not text:
        return False
    if "Quota exhausted" in text:
        # A single request larger than the burst limit is never fixed by waiting for stability.
        return "exceeds the burst limit" not in text
    if _NON_TRANSIENT_CLIENT_ERR_RE.search(text):
        return False
    if any(token in text for token in _TRANSIENT_STATUS_TOKENS):
        return True
    if any(marker in text for marker in _TRANSIENT_STREAM_MARKERS):
        return True
    return bool(_TRANSIENT_HTTP_CODE_RE.search(text))
