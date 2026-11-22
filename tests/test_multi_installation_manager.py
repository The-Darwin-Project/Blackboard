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


# =========================================================================
# Batch 1 ATDD (Step 5 / T-9): Shared GitHub App installation manager
# singleton (call-time env vars, filter_installation_id, eager missing-.pem
# fail-closed, lifecycle teardown)
# =========================================================================


@pytest.fixture(autouse=True)
def _reset_shared_github_manager():
    """Teardown guard ensuring shared manager singleton never leaks across tests."""
    from src.utils.github_app import reset_installation_manager

    reset_installation_manager()
    yield
    reset_installation_manager()


class TestATDDT9SharedInstallationManagerSingleton:
    """Layer 1-4 ATDD scenarios for shared get/close/reset_installation_manager."""

    def test_reads_env_vars_at_call_time_and_returns_none_when_app_id_unset(self, monkeypatch, tmp_path):
        """Given GITHUB_APP_ID is initially unset, then later set via monkeypatch with a .pem
        and GITHUB_INSTALLATION_ID
        When get_installation_manager() is called before and after
        Then unset returns None (not cached as None), and set returns a singleton with
        filter_installation_id propagated."""
        from src.utils.github_app import get_installation_manager

        monkeypatch.delenv("GITHUB_APP_ID", raising=False)
        monkeypatch.delenv("GITHUB_INSTALLATION_ID", raising=False)
        assert get_installation_manager() is None

        pem_file = tmp_path / "app.pem"
        pem_file.write_text("dummy-pem-placeholder")
        monkeypatch.setenv("GITHUB_APP_ID", "999001")
        monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(pem_file))
        monkeypatch.setenv("GITHUB_INSTALLATION_ID", "inst-77")

        mgr = get_installation_manager()
        assert mgr is not None
        assert mgr.app_id == "999001"
        assert mgr.private_key_path == str(pem_file)
        assert mgr.filter_installation_id == "inst-77"
        assert get_installation_manager() is mgr

    def test_missing_pem_path_caught_eagerly_and_not_cached_as_none(self, monkeypatch, tmp_path):
        """Run #5 C-5a Path A: Given GITHUB_APP_ID is set but GITHUB_PRIVATE_KEY_PATH does not
        exist on disk
        When get_installation_manager() runs
        Then _find_pem_file() ValueError in GitHubAppAuth.__init__ is caught, returning None
        without caching None (subsequent valid .pem succeeds)."""
        from src.utils.github_app import get_installation_manager

        missing_path = str(tmp_path / "does-not-exist")
        monkeypatch.setenv("GITHUB_APP_ID", "999002")
        monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", missing_path)
        monkeypatch.delenv("GITHUB_INSTALLATION_ID", raising=False)

        assert get_installation_manager() is None

        pem_file = tmp_path / "recovered.pem"
        pem_file.write_text("dummy-pem")
        monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(pem_file))
        mgr = get_installation_manager()
        assert mgr is not None

    def test_empty_private_key_path_defaults_to_secrets_dir_and_whitespace_inst_id_becomes_none(
        self, monkeypatch, tmp_path
    ):
        """Given GITHUB_PRIVATE_KEY_PATH='' and GITHUB_INSTALLATION_ID='   '
        When get_installation_manager() runs
        Then empty key path defaults to '/secrets/github' (never scans CWD '.') and
        whitespace installation ID normalizes to None."""
        from src.utils.github_app import MultiInstallationManager, get_installation_manager

        captured: dict = {}

        class _StubMgr(MultiInstallationManager):
            def __init__(self, app_id, private_key_path, filter_installation_id=None):
                captured["app_id"] = app_id
                captured["private_key_path"] = private_key_path
                captured["filter_installation_id"] = filter_installation_id
                self.app_id = app_id
                self.private_key_path = private_key_path
                self.filter_installation_id = filter_installation_id

        monkeypatch.setenv("GITHUB_APP_ID", "999004")
        monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", "")
        monkeypatch.setenv("GITHUB_INSTALLATION_ID", "   ")
        with patch("src.utils.github_app.MultiInstallationManager", _StubMgr):
            mgr = get_installation_manager()

        assert mgr is not None
        assert captured["private_key_path"] == "/secrets/github"
        assert captured["filter_installation_id"] is None

    @pytest.mark.asyncio
    async def test_close_installation_manager_sets_shutting_down_guard_and_closes_singleton(
        self, monkeypatch, tmp_path
    ):
        """Given an active shared installation manager
        When close_installation_manager() runs (main.py lifespan teardown)
        Then _shutting_down blocks concurrent/subsequent rebuilds returning None,
        close_all() is awaited, and reset_installation_manager() re-enables construction."""
        from src.utils.github_app import (
            close_installation_manager,
            get_installation_manager,
            reset_installation_manager,
        )

        pem_file = tmp_path / "app.pem"
        pem_file.write_text("dummy-pem")
        monkeypatch.setenv("GITHUB_APP_ID", "999003")
        monkeypatch.setenv("GITHUB_PRIVATE_KEY_PATH", str(pem_file))

        mgr = get_installation_manager()
        assert mgr is not None
        saw_none_during_close = []

        async def _slow_close():
            saw_none_during_close.append(get_installation_manager())

        mgr.close_all = AsyncMock(side_effect=_slow_close)

        await close_installation_manager()
        mgr.close_all.assert_awaited_once()
        assert saw_none_during_close == [None]
        assert get_installation_manager() is None

        reset_installation_manager()
        mgr2 = get_installation_manager()
        assert mgr2 is not None and mgr2 is not mgr

    @pytest.mark.asyncio
    async def test_refresh_repo_discovery_error_preserves_stale_cached_repos(self, tmp_path):
        """Given a warm repo cache for installation '100'
        When a subsequent refresh hits an error on GET /installation/repositories
        Then the previous repo list is preserved instead of being wiped to []."""
        from src.utils.github_app import MultiInstallationManager

        pem_file = tmp_path / "app.pem"
        pem_file.write_text("dummy-pem")
        mgr = MultiInstallationManager(app_id="123", private_key_path=str(pem_file))

        client = MagicMock()
        ok_resp = MagicMock()
        ok_resp.json.return_value = {"repositories": [{"full_name": "org/kept-repo", "archived": False}]}
        client.get = AsyncMock(side_effect=[ok_resp, RuntimeError("GitHub 502")])

        mgr._discover_installations = AsyncMock(return_value=[{"id": 100}])
        mgr._clients["100"] = client

        await mgr._refresh()
        assert mgr._installation_repos["100"] == ["org/kept-repo"]
        assert mgr._repo_to_installation["org/kept-repo"] == "100"

        # Force cache expiry and trigger transient repo discovery error
        mgr._last_refresh = 0.0
        await mgr._refresh()
        assert mgr._installation_repos["100"] == ["org/kept-repo"]
        assert mgr._repo_to_installation["org/kept-repo"] == "100"

