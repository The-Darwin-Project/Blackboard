# BlackBoard/tests/test_redis_client_port.py
# @ai-rules:
# 1. [Constraint]: Handle both integer port strings and Kubernetes tcp:// URL injected schemes.
# 2. [Pattern]: Tests Layer 1 Domain Intent for RedisClient port sanitization without ValueError.
# 3. [Gotcha]: Kubernetes service links inject REDIS_PORT="tcp://<IP>:<PORT>" when service is named 'redis'.
from __future__ import annotations

import os
import pytest
from src.state.redis_client import RedisClient, sanitize_redis_port


class TestRedisClientPortSanitization:
    """Dave Farley 4-Layer ATDD: Redis Port Sanitization Specification."""

    def test_sanitize_redis_port_standard_int(self):
        """Given a standard port integer, returns integer unchanged."""
        assert sanitize_redis_port(6379) == 6379
        assert sanitize_redis_port("6380") == 6380

    def test_sanitize_redis_port_k8s_tcp_scheme(self):
        """Given K8s injected tcp:// URL, extracts terminal port integer without ValueError."""
        assert sanitize_redis_port("tcp://10.96.0.1:6379") == 6379
        assert sanitize_redis_port("tcp://172.30.12.34:6382") == 6382

    def test_redis_client_env_port_resolution(self, monkeypatch):
        """Given REDIS_PORT env with tcp:// scheme, RedisClient parses port cleanly."""
        monkeypatch.setenv("REDIS_PORT", "tcp://10.96.0.1:6379")
        client = RedisClient()
        assert client.port == 6379

    def test_redis_client_explicit_port_precedence(self, monkeypatch):
        """Given explicit port argument, explicit port is used and sanitized."""
        monkeypatch.setenv("REDIS_PORT", "6380")
        client = RedisClient(port=6381)
        assert client.port == 6381

    def test_skill_reconciler_build_redis_client_k8s_port(self, monkeypatch):
        """Given K8s injected REDIS_PORT, skill_reconciler _build_redis_client does not raise ValueError."""
        monkeypatch.setenv("REDIS_PORT", "tcp://10.96.0.1:6379")
        from src.skill_reconciler.reconcile import _build_redis_client
        client = _build_redis_client()
        assert client.connection_pool.connection_kwargs["port"] == 6379
