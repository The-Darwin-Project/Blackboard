# BlackBoard/src/auth.py
# @ai-rules:
# 1. [Constraint]: Gated on DEX_ENABLED env var. When false, all functions return anonymous stubs.
# 2. [Pattern]: UserContext is the single identity abstraction -- all consumers use .label for display.
# 3. [Gotcha]: Slack users always have named identity regardless of DEX_ENABLED setting.
# 4. [Pattern]: _validate_jwt() is pure crypto -- zero network calls. Keys provided by OIDCKeyAdapter.
# 5. [Pattern]: get_user_from_request/get_user_from_slack are forward-looking scaffolding (RBAC v2).
# 6. [Pattern]: require_auth is a FastAPI Depends() that enforces named identity (raises 401 if anonymous).
"""User identity domain -- pure JWT validation and UserContext abstraction.

When dex.enabled=false (default): returns anonymous UserContext for Dashboard users.
When dex.enabled=true:  validates JWT against pre-cached keys, returns named UserContext.

Network concerns (JWKS fetch, SSL) live in adapters/oidc_adapter.py, not here.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

import jwt
from starlette.requests import Request

if TYPE_CHECKING:
    from .adapters.oidc_adapter import OIDCKeyAdapter

logger = logging.getLogger(__name__)

DEX_ENABLED = os.getenv("DEX_ENABLED", "false").lower() == "true"
DEX_ISSUER_URL = os.getenv("DEX_ISSUER_URL", "")
DEX_CLIENT_ID = os.getenv("DEX_CLIENT_ID", "darwin-dashboard")

_oidc_adapter: OIDCKeyAdapter | None = None


def set_oidc_adapter(adapter: OIDCKeyAdapter) -> None:
    """Inject the OIDC key adapter at startup. Called from main.py lifespan."""
    global _oidc_adapter
    _oidc_adapter = adapter


@dataclass
class UserContext:
    """Authenticated user identity.

    dex.enabled=false: user_id="anonymous", display_name=None -> label returns "anonymous"
    dex.enabled=true:  populated from JWT claims -> label returns the user's real name
    Slack source:      always populated from Slack user profile regardless of dex setting
    """
    user_id: str = "anonymous"
    display_name: Optional[str] = None
    email: Optional[str] = None
    source: str = "dashboard"
    roles: list[str] = field(default_factory=list)

    @property
    def label(self) -> str:
        return self.display_name or self.user_id


def _validate_jwt(token: str) -> dict:
    """Decode and validate a JWT against cached signing keys. Pure crypto, zero network.

    Validates: signature (pre-cached JWKS key), iss (DEX_ISSUER_URL), aud (DEX_CLIENT_ID), exp.
    Returns claims dict on success, raises on failure.
    """
    if not _oidc_adapter or not _oidc_adapter.loaded:
        raise ValueError("OIDC keys not loaded")

    header = jwt.get_unverified_header(token)
    kid = header.get("kid", "")
    key = _oidc_adapter.get_signing_key(kid)

    return jwt.decode(
        token,
        key,
        algorithms=["RS256", "ES256"],
        issuer=DEX_ISSUER_URL,
        audience=DEX_CLIENT_ID,
        options={"verify_exp": True},
    )


def _claims_to_user(claims: dict) -> UserContext:
    """Map JWT claims to UserContext."""
    return UserContext(
        user_id=claims.get("sub", "unknown"),
        display_name=claims.get("preferred_username") or claims.get("name") or claims.get("email"),
        email=claims.get("email"),
        source="dashboard",
        roles=claims.get("groups", []),
    )


def get_user_from_websocket(websocket) -> UserContext:
    """Extract user identity from WebSocket query param ?token=<JWT>.

    When DEX_ENABLED=false: returns anonymous stub.
    When DEX_ENABLED=true: validates JWT, returns named UserContext.
    On validation failure: returns anonymous (caller decides whether to reject).
    """
    if not DEX_ENABLED:
        return UserContext()

    token = websocket.query_params.get("token", "")
    if not token:
        return UserContext()

    try:
        claims = _validate_jwt(token)
        return _claims_to_user(claims)
    except Exception as e:
        logger.debug("JWT validation failed for WS: %s", e)
        return UserContext()


def get_user_from_request(request) -> UserContext:
    """Extract user identity from REST Authorization: Bearer header.

    When DEX_ENABLED=false: returns anonymous stub.
    When DEX_ENABLED=true: validates JWT, returns named UserContext.
    """
    if not DEX_ENABLED:
        return UserContext()

    auth_header = request.headers.get("authorization", "")
    if not auth_header.lower().startswith("bearer "):
        return UserContext()

    token = auth_header[7:]
    try:
        claims = _validate_jwt(token)
        return _claims_to_user(claims)
    except Exception as e:
        logger.debug("JWT validation failed for REST: %s", e)
        return UserContext()


def get_user_from_slack(user_id: str, display_name: str, email: str = "") -> UserContext:
    """Create UserContext from Slack user profile (always named, independent of dex setting)."""
    return UserContext(user_id=user_id, display_name=display_name, email=email, source="slack")


async def require_auth(request: Request) -> UserContext:
    """FastAPI Depends() -- enforces named identity. Raises 401 if user has no email (anonymous).

    Use on mutation endpoints that need owner attribution (e.g., TimeKeeper CRUD).
    Read-only endpoints can use get_user_from_request() directly for graceful degradation.
    """
    from fastapi import HTTPException

    user = get_user_from_request(request)
    if not user.email:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user
