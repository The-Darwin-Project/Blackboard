# BlackBoard/src/adapters/oidc_adapter.py
# @ai-rules:
# 1. [Constraint]: ALL SSL/self-signed cert handling lives here exclusively. No other module touches ssl.
# 2. [Pattern]: get_signing_key() is a pure dict lookup on the hot path -- zero network calls.
# 3. [Pattern]: Background refresh via asyncio.Task. Configurable interval, default 60 min.
# 4. [Gotcha]: Key rotation fallback -- if kid not in cache, synchronous refetch with short timeout.
# 5. [Constraint]: This adapter is the single point of contact with Dex's internal HTTPS endpoint.
"""OIDC JWKS key adapter -- fetches and caches signing keys from Dex internal service.

Isolates the self-signed TLS concern (cert-manager) from the JWT validation domain.
The Brain's auth module calls get_signing_key(kid) which is a pure in-memory lookup.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any

import httpx
from jwt.algorithms import RSAAlgorithm, ECAlgorithm

logger = logging.getLogger(__name__)

_REFRESH_INTERVAL = int(os.getenv("OIDC_KEY_REFRESH_INTERVAL", "3600"))


class OIDCKeyAdapter:
    """Fetches JWKS from Dex and caches signing keys in memory.

    Usage:
        adapter = OIDCKeyAdapter(jwks_url)
        await adapter.start()       # initial fetch + background refresh
        key = adapter.get_signing_key(kid)  # pure lookup
        await adapter.stop()        # cancel background task
    """

    def __init__(self, jwks_url: str) -> None:
        self._jwks_url = jwks_url
        self._keys: dict[str, Any] = {}
        self._refresh_task: asyncio.Task | None = None

    async def start(self) -> None:
        await self._fetch_keys()
        self._refresh_task = asyncio.create_task(self._refresh_loop())
        logger.info("OIDCKeyAdapter started: %d keys cached from %s", len(self._keys), self._jwks_url)

    async def stop(self) -> None:
        if self._refresh_task and not self._refresh_task.done():
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
        logger.info("OIDCKeyAdapter stopped")

    def get_signing_key(self, kid: str) -> Any:
        """Pure in-memory lookup. Raises KeyError if kid not cached."""
        key = self._keys.get(kid)
        if key:
            return key
        self._sync_refetch()
        key = self._keys.get(kid)
        if not key:
            raise KeyError(f"Signing key '{kid}' not found in JWKS (have: {list(self._keys.keys())})")
        logger.warning("Key '%s' found after synchronous refetch (rotation detected)", kid)
        return key

    @property
    def loaded(self) -> bool:
        return len(self._keys) > 0

    async def _fetch_keys(self) -> None:
        try:
            async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
                resp = await client.get(self._jwks_url)
                resp.raise_for_status()
            jwks = resp.json()
            self._keys = self._parse_jwks(jwks)
            logger.debug("JWKS refreshed: %d keys from %s", len(self._keys), self._jwks_url)
        except Exception as e:
            logger.warning("Failed to fetch JWKS from %s: %s", self._jwks_url, e)

    def _sync_refetch(self) -> None:
        """Blocking fallback for key rotation -- called when kid not in cache."""
        try:
            with httpx.Client(verify=False, timeout=5.0) as client:
                resp = client.get(self._jwks_url)
                resp.raise_for_status()
            jwks = resp.json()
            self._keys = self._parse_jwks(jwks)
        except Exception as e:
            logger.warning("Sync JWKS refetch failed: %s", e)

    async def _refresh_loop(self) -> None:
        while True:
            await asyncio.sleep(_REFRESH_INTERVAL)
            await self._fetch_keys()

    @staticmethod
    def _parse_jwks(jwks: dict) -> dict[str, Any]:
        """Parse JWKS JSON into {kid: cryptographic_key} dict."""
        keys: dict[str, Any] = {}
        for jwk in jwks.get("keys", []):
            kid = jwk.get("kid")
            if not kid:
                continue
            kty = jwk.get("kty", "")
            try:
                if kty == "RSA":
                    keys[kid] = RSAAlgorithm.from_jwk(json.dumps(jwk))
                elif kty == "EC":
                    keys[kid] = ECAlgorithm.from_jwk(json.dumps(jwk))
            except Exception as e:
                logger.warning("Failed to parse key %s (kty=%s): %s", kid, kty, e)
        return keys
