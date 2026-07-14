# tests/test_multi_installation_manager.py
# @ai-rules:
# 1. [Constraint]: No real GitHub API calls. httpx.AsyncClient and AsyncGitHubClient mocked.
# 2. [Pattern]: _make_manager() patches GitHubAppAuth + AsyncGitHubClient construction.
"""Tests for MultiInstallationManager — discovery, TTL, exclusive filter, repo cache."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_manager(filter_installation_id: str | None = None):
    with patch("src.utils.github_app.GitHubAppAuth") as MockAuth:
        MockAuth.return_value = MagicMock()
        from src.utils.github_app import MultiInstallationManager
        manager = MultiInstallationManager(
            app_id="123", private_key_path="/tmp/fake.pem",
            filter_installation_id=filter_installation_id,
        )
    return manager


def _repo_resp(full_names: list[str]):
    resp = MagicMock()
    resp.json.return_value = {"repositories": [{"full_name": n, "archived": False} for n in full_names]}
    return resp


def _patch_get_or_create(manager, clients_by_inst: dict[str, "AsyncMock"]):
    """Wrap _get_or_create_client so the manager's internal _clients dict stays populated."""
    def _side_effect(inst_id):
        client = clients_by_inst[inst_id]
        manager._clients[inst_id] = client
        return client
    return patch.object(manager, "_get_or_create_client", side_effect=_side_effect)


@pytest.mark.asyncio
async def test_two_installations_discovered():
    """(a) get_clients_with_repos() returns both installations with their repos."""
    manager = _make_manager()
    manager._discover_installations = AsyncMock(return_value=[
        {"id": 1, "account": {"login": "org-a"}},
        {"id": 2, "account": {"login": "org-b"}},
    ])
    c1, c2 = AsyncMock(), AsyncMock()
    c1.get = AsyncMock(return_value=_repo_resp(["org-a/repo1"]))
    c2.get = AsyncMock(return_value=_repo_resp(["org-b/repo1"]))

    with _patch_get_or_create(manager, {"1": c1, "2": c2}):
        result = await manager.get_clients_with_repos()

    assert len(result) == 2
    inst_ids = {r[0] for r in result}
    assert inst_ids == {"1", "2"}


@pytest.mark.asyncio
async def test_ttl_expiry_refetches_and_stale_serve_on_failure():
    """(b) TTL expiry re-fetches; discovery failure serves stale cache."""
    manager = _make_manager()
    manager._discover_installations = AsyncMock(return_value=[{"id": 1, "account": {"login": "org-a"}}])
    client = AsyncMock()
    client.get = AsyncMock(return_value=_repo_resp(["org-a/repo1"]))

    with _patch_get_or_create(manager, {"1": client}):
        first = await manager.get_clients_with_repos()
        assert len(first) == 1

        # Force TTL to be considered expired.
        manager._last_refresh = 0.0
        manager._discover_installations = AsyncMock(side_effect=Exception("API down"))

        second = await manager.get_clients_with_repos()
        # Stale cache served -- still 1 installation, no exception raised.
        assert len(second) == 1


@pytest.mark.asyncio
async def test_cold_start_discovery_failure_raises():
    """(f) zero installations + discovery failure with no cache -> raises."""
    manager = _make_manager()
    manager._discover_installations = AsyncMock(side_effect=Exception("API down"))
    with pytest.raises(Exception):
        await manager.get_clients_with_repos()


@pytest.mark.asyncio
async def test_exclusive_filter_returns_one_client():
    """(c) filter_installation_id restricts discovery to a single installation."""
    manager = _make_manager(filter_installation_id="2")
    manager._discover_installations = AsyncMock(return_value=[
        {"id": 1, "account": {"login": "org-a"}},
        {"id": 2, "account": {"login": "org-b"}},
    ])
    client = AsyncMock()
    client.get = AsyncMock(return_value=_repo_resp(["org-b/repo1"]))

    with _patch_get_or_create(manager, {"2": client}):
        result = await manager.get_clients_with_repos()

    assert len(result) == 1
    assert result[0][0] == "2"


@pytest.mark.asyncio
async def test_zero_installations_returns_empty_list():
    """(f) cold-start with zero installations discovered -> empty list, no error."""
    manager = _make_manager()
    manager._discover_installations = AsyncMock(return_value=[])
    result = await manager.get_clients_with_repos()
    assert result == []


@pytest.mark.asyncio
async def test_get_client_for_repo_resolves_from_cache():
    """(d) get_client_for_repo resolves via the repo -> installation cache."""
    manager = _make_manager()
    manager._discover_installations = AsyncMock(return_value=[{"id": 1, "account": {"login": "org-a"}}])
    client = AsyncMock()
    client.get = AsyncMock(return_value=_repo_resp(["org-a/repo1"]))

    with _patch_get_or_create(manager, {"1": client}):
        result = await manager.get_client_for_repo("org-a", "repo1")

    assert result is not None
    inst_id, resolved_client = result
    assert inst_id == "1"
    assert resolved_client is client


@pytest.mark.asyncio
async def test_get_client_for_repo_unknown_repo_returns_none():
    """(e) unknown repo -> None."""
    manager = _make_manager()
    manager._discover_installations = AsyncMock(return_value=[{"id": 1, "account": {"login": "org-a"}}])
    client = AsyncMock()
    client.get = AsyncMock(return_value=_repo_resp(["org-a/repo1"]))

    with _patch_get_or_create(manager, {"1": client}):
        result = await manager.get_client_for_repo("org-z", "unknown-repo")

    assert result is None
