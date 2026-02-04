# BlackBoard/src/state/redis_client.py
"""
Redis async client for Darwin Blackboard.

Uses validated redis.asyncio pattern with from_url().
"""
from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

import redis.asyncio as redis

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# Global client instance (singleton)
_redis_client: Redis | None = None


class RedisClient:
    """
    Async Redis client wrapper with health check.
    
    Usage:
        client = RedisClient()
        await client.connect()
        await client.ping()
        await client.close()
    """
    
    def __init__(
        self,
        host: str | None = None,
        port: int = 6379,
        password: str | None = None,
        db: int = 0,
    ):
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port
        self.password = password or os.getenv("REDIS_PASSWORD", "")
        self.db = db
        self._client: Redis | None = None
    
    @property
    def url(self) -> str:
        """Build Redis connection URL."""
        if self.password:
            return f"redis://:{self.password}@{self.host}:{self.port}/{self.db}"
        return f"redis://{self.host}:{self.port}/{self.db}"
    
    async def connect(self) -> Redis:
        """
        Connect to Redis using validated async pattern.
        
        Returns the Redis client instance.
        """
        if self._client is None:
            logger.info(f"Connecting to Redis at {self.host}:{self.port}")
            self._client = redis.Redis.from_url(
                self.url,
                decode_responses=True,  # Return strings instead of bytes
            )
            # Verify connection
            await self.ping()
            logger.info("Redis connection established")
        return self._client
    
    async def ping(self) -> bool:
        """
        Health check - test Redis connectivity.
        
        Returns True if Redis responds to PING.
        Raises ConnectionError if Redis is unavailable.
        """
        if self._client is None:
            raise ConnectionError("Redis client not connected")
        
        try:
            result = await self._client.ping()
            return result
        except redis.ConnectionError as e:
            logger.error(f"Redis health check failed: {e}")
            raise ConnectionError(f"Redis unavailable: {e}") from e
    
    async def close(self) -> None:
        """Close Redis connection and cleanup."""
        if self._client is not None:
            logger.info("Closing Redis connection")
            await self._client.aclose()
            self._client = None
    
    @property
    def client(self) -> Redis:
        """Get the Redis client instance (must be connected first)."""
        if self._client is None:
            raise ConnectionError("Redis client not connected. Call connect() first.")
        return self._client


async def get_redis() -> Redis:
    """
    Get the global Redis client instance.
    
    Creates a new connection if one doesn't exist.
    Used as FastAPI dependency.
    """
    global _redis_client
    
    if _redis_client is None:
        client = RedisClient()
        _redis_client = await client.connect()
    
    return _redis_client


async def close_redis() -> None:
    """Close the global Redis connection."""
    global _redis_client
    
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
