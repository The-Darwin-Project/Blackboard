# tests/test_knowledge_graph_acquire.py
# @ai-rules:
# 1. [Purpose]: Regression coverage for the HIGH finding fixed in ac4f086 -- _acquire()
#    used to wrap `pool.acquire().__aenter__()` in asyncio.wait_for(), which could leak a
#    pooled connection if the wait_for timeout fired after asyncpg had internally claimed
#    a connection but before __aenter__ returned it (since __aexit__ was then never
#    reached). The fix uses asyncpg's native `pool.acquire(timeout=...)` kwarg instead.
# 2. [Pattern]: _acquire() is tested directly (not through a store method) so the
#    acquire/release contract is verified independent of any specific KG query.
"""Tests for KnowledgeGraphStore._acquire() -- the pooled-connection helper."""
from __future__ import annotations

import asyncio

import pytest
from unittest.mock import AsyncMock, MagicMock

from src.memory.knowledge_graph import KG_ACQUIRE_TIMEOUT_SECONDS, _acquire


def _mock_acquire_context(conn):
    """A stand-in for asyncpg's PoolAcquireContext (supports `async with`)."""
    ctx = MagicMock()
    ctx.__aenter__ = AsyncMock(return_value=conn)
    ctx.__aexit__ = AsyncMock(return_value=False)
    return ctx


@pytest.mark.asyncio
class TestAcquire:
    async def test_passes_timeout_kwarg_to_native_pool_acquire(self):
        """The fix relies on asyncpg applying the timeout internally -- verify the
        kwarg is actually forwarded, not silently dropped."""
        conn = object()
        pool = MagicMock()
        pool.acquire.return_value = _mock_acquire_context(conn)

        async with _acquire(pool) as acquired:
            assert acquired is conn

        pool.acquire.assert_called_once_with(timeout=KG_ACQUIRE_TIMEOUT_SECONDS)

    async def test_releases_connection_on_normal_exit(self):
        conn = object()
        pool = MagicMock()
        ctx = _mock_acquire_context(conn)
        pool.acquire.return_value = ctx

        async with _acquire(pool):
            pass

        ctx.__aexit__.assert_awaited_once()

    async def test_releases_connection_when_body_raises(self):
        """A failure inside the `async with` block must still release the connection."""
        conn = object()
        pool = MagicMock()
        ctx = _mock_acquire_context(conn)
        pool.acquire.return_value = ctx

        with pytest.raises(ValueError):
            async with _acquire(pool):
                raise ValueError("query failed")

        ctx.__aexit__.assert_awaited_once()

    async def test_timeout_propagates_without_leaking(self):
        """If asyncpg's own acquire() times out (raises inside __aenter__, before a
        connection is handed back), the exception must propagate and __aexit__ must
        never be invoked -- there is no connection to release, and asyncpg guarantees
        it did not leave one claimed. This is the exact leak window the old
        wait_for(acquire_ctx.__aenter__()) pattern could hit; the fix delegates
        timeout handling entirely to asyncpg so that guarantee holds."""
        pool = MagicMock()
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(side_effect=asyncio.TimeoutError("pool exhausted"))
        ctx.__aexit__ = AsyncMock(return_value=False)
        pool.acquire.return_value = ctx

        with pytest.raises(asyncio.TimeoutError):
            async with _acquire(pool):
                pytest.fail("body must not run when acquire times out")

        ctx.__aexit__.assert_not_awaited()

    async def test_no_asyncio_wait_for_wrapping(self):
        """Locks in the fix's approach: _acquire's executable body must not reach for
        asyncio.wait_for -- that was the source of the leak window. (The docstring
        mentions wait_for by name to explain the old bug, so only the code below the
        docstring is checked.)"""
        import ast
        import inspect
        import textwrap

        from src.memory import knowledge_graph

        source = textwrap.dedent(inspect.getsource(knowledge_graph._acquire))
        tree = ast.parse(source)
        func_def = tree.body[0]
        body_without_docstring = ast.get_source_segment(source, func_def.body[-1])
        assert "wait_for" not in body_without_docstring
