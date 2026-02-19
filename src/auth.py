# BlackBoard/src/auth.py
# @ai-rules:
# 1. [Constraint]: Gated on DEX_ENABLED env var. When false, all functions return anonymous stubs.
# 2. [Pattern]: UserContext is the single identity abstraction -- all consumers use .label for display.
# 3. [Gotcha]: Slack users always have named identity regardless of DEX_ENABLED setting.
"""User identity abstraction -- plug-and-play for Dex/OIDC integration.

When dex.enabled=false (default): returns anonymous UserContext for Dashboard users.
When dex.enabled=true:  validates JWT from WebSocket handshake, returns named UserContext.

Helm values stub (values.yaml -- scaffolding only, not wired to deployment env yet):
    # dex:
    #   enabled: false
    #   issuerUrl: ""        # e.g., https://dex.darwin.apps.cluster.local
    #   clientId: ""
    #   existingSecret: ""   # Secret with clientSecret key

Env vars consumed (when dex.enabled=true):
    DEX_ENABLED=true
    DEX_ISSUER_URL=https://...
    DEX_CLIENT_ID=darwin-dashboard
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional

DEX_ENABLED = os.getenv("DEX_ENABLED", "false").lower() == "true"


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

    @property
    def label(self) -> str:
        """Display label for conversation turns and Slack messages."""
        return self.display_name or self.user_id


def get_user_from_websocket(websocket) -> UserContext:
    """Extract user identity from WebSocket connection.

    Gated on DEX_ENABLED:
    - false: returns anonymous stub (current behavior, "*(via Dashboard)*" in Slack)
    - true:  reads Bearer token from WS handshake, validates against Dex OIDC discovery,
             extracts claims (sub -> user_id, preferred_username -> display_name, email)

    TODO(dex): Implement JWT validation when dex.enabled=true:
        token = websocket.headers.get("Authorization", "").removeprefix("Bearer ")
        claims = validate_jwt(token, issuer=os.getenv("DEX_ISSUER_URL"))
        return UserContext(
            user_id=claims["sub"],
            display_name=claims.get("preferred_username") or claims.get("name"),
            email=claims.get("email"),
        )
    """
    return UserContext()


def get_user_from_slack(user_id: str, display_name: str, email: str = "") -> UserContext:
    """Create UserContext from Slack user profile (always named, independent of dex setting)."""
    return UserContext(user_id=user_id, display_name=display_name, email=email, source="slack")
