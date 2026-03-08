# BlackBoard/src/auth.py
# @ai-rules:
# 1. [Constraint]: Gated on DEX_ENABLED env var. When false, all functions return anonymous stubs.
# 2. [Pattern]: UserContext is the single identity abstraction -- all consumers use .label for display.
# 3. [Gotcha]: Slack users always have named identity regardless of DEX_ENABLED setting.
# 4. [Pattern]: _validate_jwt() is sync (CPU-bound). JWKS fetched async at startup via fetch_oidc_jwks().
# 5. [Pattern]: JWKS fetched from DEX_INTERNAL_URL/keys (internal), iss validated against DEX_ISSUER_URL (public).
"""User identity via Dex OIDC -- validates JWTs from Dashboard WebSocket and REST.

When dex.enabled=false (default): returns anonymous UserContext for Dashboard users.
When dex.enabled=true:  validates JWT against Dex JWKS, returns named UserContext.

Env vars consumed (wired from Helm when dex.enabled=true):
    DEX_ENABLED=true
    DEX_ISSUER_URL=https://<brain-route>/dex    (public issuer, used for iss claim validation)
    DEX_CLIENT_ID=darwin-dashboard              (audience validation)
    DEX_INTERNAL_URL=https://<release>-dex:5556 (internal Service, used for JWKS fetch)
"""
from __future__ import annotations

import logging
import os
import ssl
from dataclasses import dataclass, field
from typing import Optional

import jwt

_no_verify_ssl = ssl.create_default_context()
_no_verify_ssl.check_hostname = False
_no_verify_ssl.verify_mode = ssl.CERT_NONE

logger = logging.getLogger(__name__)

DEX_ENABLED = os.getenv("DEX_ENABLED", "false").lower() == "true"
DEX_ISSUER_URL = os.getenv("DEX_ISSUER_URL", "")
DEX_CLIENT_ID = os.getenv("DEX_CLIENT_ID", "darwin-dashboard")
DEX_INTERNAL_URL = os.getenv("DEX_INTERNAL_URL", "")

_jwks_client: jwt.PyJWKClient | None = None


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


async def fetch_oidc_jwks() -> None:
    """Fetch and cache JWKS from Dex internal endpoint. Called at Brain startup."""
    global _jwks_client
    if not DEX_ENABLED or not DEX_INTERNAL_URL:
        return

    jwks_url = f"{DEX_INTERNAL_URL}/dex/keys"
    try:
        import httpx
        async with httpx.AsyncClient(verify=False) as client:
            resp = await client.get(jwks_url)
            resp.raise_for_status()

        _jwks_client = jwt.PyJWKClient(jwks_url, ssl_context=_no_verify_ssl)
        logger.info("OIDC JWKS loaded from %s (%s keys)", jwks_url, "ok")
    except Exception as e:
        logger.warning("Failed to fetch OIDC JWKS from %s: %s -- auth will fall back to anonymous", jwks_url, e)
        _jwks_client = None


def _validate_jwt(token: str) -> dict:
    """Decode and validate a JWT against cached JWKS. Sync (CPU-bound).

    Validates: signature (JWKS), iss (DEX_ISSUER_URL), aud (DEX_CLIENT_ID), exp.
    Returns claims dict on success, raises on failure.
    """
    if not _jwks_client:
        raise ValueError("JWKS not loaded")

    signing_key = _jwks_client.get_signing_key_from_jwt(token)
    return jwt.decode(
        token,
        signing_key.key,
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
