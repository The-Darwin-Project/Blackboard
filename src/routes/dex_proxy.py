# BlackBoard/src/routes/dex_proxy.py
# @ai-rules:
# 1. [Pattern]: Infrastructure adapter -- proxies /dex/* to internal Dex Service. No domain logic.
# 2. [Constraint]: follow_redirects=False -- OIDC flows depend on 302 redirects reaching the browser.
# 3. [Constraint]: verify=False -- Dex serves self-signed cert-manager cert (internal, same namespace).
"""Reverse proxy for Dex OIDC endpoints at /dex/*.

Browser PKCE flow hits /dex/auth, /dex/token, /dex/keys etc. through Brain's
Route. This adapter forwards those requests to the internal Dex Service so the
browser never needs direct access to Dex.
"""
from __future__ import annotations

import os
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import Response

logger = logging.getLogger(__name__)

DEX_INTERNAL_URL = os.getenv("DEX_INTERNAL_URL", "")

router = APIRouter(tags=["dex"])

_HOP_BY_HOP = frozenset({
    "connection", "keep-alive", "proxy-authenticate", "proxy-authorization",
    "te", "trailers", "transfer-encoding", "upgrade", "host",
})


@router.api_route("/dex/{path:path}", methods=["GET", "POST", "OPTIONS"])
async def dex_proxy(request: Request, path: str) -> Response:
    """Forward request to internal Dex Service."""
    target = f"{DEX_INTERNAL_URL}/{path}"

    headers = {
        k: v for k, v in request.headers.items()
        if k.lower() not in _HOP_BY_HOP
    }

    async with httpx.AsyncClient(verify=False, follow_redirects=False) as client:
        resp = await client.request(
            method=request.method,
            url=target,
            headers=headers,
            params=dict(request.query_params),
            content=await request.body(),
        )

    response_headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in _HOP_BY_HOP and k.lower() != "content-encoding"
    }

    return Response(
        content=resp.content,
        status_code=resp.status_code,
        headers=response_headers,
    )
