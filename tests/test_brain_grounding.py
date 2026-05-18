# Blackboard/tests/test_brain_grounding.py
# @ai-rules:
# 1. [Constraint]: Tests Brain._resolve_grounding_urls only -- async static method.
# 2. [Pattern]: Uses httpx mock transport to simulate redirects without network.
# 3. [Pattern]: Follows test_brain_dedup.py structure: class per concern, descriptive names.
"""Unit tests for Brain._resolve_grounding_urls: redirect resolution and dedup."""
from __future__ import annotations

import httpx
import pytest

from src.agents.brain import Brain


REDIRECT_BASE = "https://vertexaisearch.cloud.google.com/grounding-api-redirect/abc123"
RESOLVED_URL = "https://docs.example.com/real-page"


def _make_chunk(title: str, uri: str) -> dict:
    return {"title": title, "uri": uri}


class TestResolveGroundingUrls:
    """Tests for Brain._resolve_grounding_urls."""

    @pytest.mark.asyncio
    async def test_resolves_redirect_urls(self, monkeypatch):
        """Redirect URIs are followed and replaced with final URL."""
        chunks = [_make_chunk("Doc A", REDIRECT_BASE)]

        async def mock_head(self, url, **kwargs):
            return httpx.Response(200, request=httpx.Request("HEAD", RESOLVED_URL))

        monkeypatch.setattr(httpx.AsyncClient, "head", mock_head)
        result = await Brain._resolve_grounding_urls(chunks)

        assert len(result) == 1
        assert result[0]["uri"] == RESOLVED_URL

    @pytest.mark.asyncio
    async def test_passthrough_non_redirect_urls(self, monkeypatch):
        """Non-redirect URIs are returned unchanged."""
        direct_url = "https://docs.example.com/direct"
        chunks = [_make_chunk("Direct", direct_url)]

        async def mock_head(self, url, **kwargs):
            raise AssertionError("Should not be called for non-redirect URLs")

        monkeypatch.setattr(httpx.AsyncClient, "head", mock_head)
        result = await Brain._resolve_grounding_urls(chunks)

        assert len(result) == 1
        assert result[0]["uri"] == direct_url

    @pytest.mark.asyncio
    async def test_deduplicates_resolved_urls(self, monkeypatch):
        """Chunks resolving to same URL are deduped, first wins."""
        chunks = [
            _make_chunk("Doc A", REDIRECT_BASE + "?v=1"),
            _make_chunk("Doc B", REDIRECT_BASE + "?v=2"),
        ]

        async def mock_head(self, url, **kwargs):
            return httpx.Response(200, request=httpx.Request("HEAD", RESOLVED_URL))

        monkeypatch.setattr(httpx.AsyncClient, "head", mock_head)
        result = await Brain._resolve_grounding_urls(chunks)

        assert len(result) == 1
        assert result[0]["title"] == "Doc A"

    @pytest.mark.asyncio
    async def test_failed_resolution_clears_uri(self, monkeypatch):
        """Network errors produce empty URI; chunk still deduped by title."""
        chunks = [_make_chunk("Flaky Doc", REDIRECT_BASE)]

        async def mock_head(self, url, **kwargs):
            raise httpx.ConnectTimeout("timeout")

        monkeypatch.setattr(httpx.AsyncClient, "head", mock_head)
        result = await Brain._resolve_grounding_urls(chunks)

        assert len(result) == 1
        assert result[0]["uri"] == ""

    @pytest.mark.asyncio
    async def test_empty_chunks_returns_empty(self, monkeypatch):
        """Empty input returns empty output without errors."""
        result = await Brain._resolve_grounding_urls([])
        assert result == []
