# BlackBoard/tests/test_queue.py
# @ai-rules:
# 1. [Gotcha]: Patch lifespan like test_health.py so app import does not require live Redis.
# 2. [Pattern]: ASGITransport + httpx.AsyncClient for in-process GET/POST tests.
# 3. [Constraint]: GET /queue/headhunter/pending is pure-Redis (zero outbound httpx calls);
#    tests patch httpx.AsyncClient to raise AssertionError and provide Redis snapshots via mock_bb.get_headhunter_snapshot.
# 4. [Pattern]: Queue active/closed tests mock blackboard.get_active_events + get_event to verify response shape.
# 5. [Pattern]: /headhunter/pending merges Redis snapshots (get_headhunter_snapshot) with active and
#    waiting_approval Blackboard headhunter events (get_active_events_with_status + get_waiting_approval_events + get_event).
# 6. [Pattern]: Per-item get_event() fetch uses asyncio.gather(return_exceptions=True) (#233
#    review, HIGH fix) -- isolation/None-race/no-context/mixed-source/sort tests set
#    get_active_events_with_status() to a multi-id dict and use an AsyncMock side_effect
#    keyed by event_id on get_event() to control each id's outcome independently.
"""Route-level tests for queue API."""
from __future__ import annotations

import asyncio
import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tests.test_headhunter import _make_todo


def _forbid_http_client(*args, **kwargs):
    raise AssertionError("HTTP call forbidden in pure-Redis /pending")


def _make_snapshot(
    platform: str,
    *,
    enabled: bool = True,
    items: list | None = None,
    last_poll_at: float | None = 1_700_000_000.0,
    partial_error: str | None = None,
    breaker_state: str = "closed",
    consecutive_failures: int = 0,
    next_retry_at: float | None = None,
    last_error: str | None = None,
):
    from src.agents.headhunter_models import (
        PlatformBreakerStatus,
        PlatformQueueItem,
        PlatformSnapshot,
    )

    norm_items: list[PlatformQueueItem] = []
    for item in items or []:
        if isinstance(item, PlatformQueueItem):
            norm_items.append(item)
        else:
            norm_items.append(PlatformQueueItem(**item))
    queued_count = sum(1 for i in norm_items if i.status == "queued")
    return PlatformSnapshot(
        platform=platform,
        enabled=enabled,
        pending_count=len(norm_items),
        queued_count=queued_count,
        last_poll_at=last_poll_at,
        partial_error=partial_error,
        breaker=PlatformBreakerStatus(
            state=breaker_state,
            consecutive_failures=consecutive_failures,
            next_retry_at=next_retry_at,
            last_error=last_error,
        ),
        items=norm_items,
    )


@pytest.mark.asyncio
async def test_headhunter_pending_filters_merged_and_closed_mrs():
    """Pure-Redis /pending reads GitLab PlatformSnapshot with zero HTTP calls and excludes merged/closed items."""
    gl_snap = _make_snapshot(
        "gitlab",
        items=[
            {
                "platform": "gitlab",
                "item_kind": "mr",
                "item_id": 1,
                "project_ref": "group/repo",
                "title": "Open MR",
                "author": "alice",
                "url": "https://gitlab.example.com/group/repo/-/merge_requests/1",
                "ci_status": "success",
                "status": "pending",
                "enqueued_at": "2026-09-01T00:00:00Z",
                "raw": {"todo_id": 101, "action": "review_requested"},
            },
            {
                "platform": "gitlab",
                "item_kind": "mr",
                "item_id": 2,
                "project_ref": "group/repo",
                "title": "Merged MR",
                "author": "alice",
                "url": "https://gitlab.example.com/group/repo/-/merge_requests/2",
                "status": "merged",
                "enqueued_at": "2026-09-01T00:01:00Z",
                "raw": {"todo_id": 102, "action": "review_requested", "mr_state": "merged"},
            },
            {
                "platform": "gitlab",
                "item_kind": "mr",
                "item_id": 3,
                "project_ref": "group/repo",
                "title": "Closed MR",
                "author": "alice",
                "url": "https://gitlab.example.com/group/repo/-/merge_requests/3",
                "status": "closed",
                "enqueued_at": "2026-09-01T00:02:00Z",
                "raw": {"todo_id": 103, "action": "review_requested", "mr_state": "closed"},
            },
            {
                "platform": "gitlab",
                "item_kind": "mr",
                "item_id": 4,
                "project_ref": "group/repo",
                "title": "Queued MR",
                "author": "bob",
                "url": "https://gitlab.example.com/group/repo/-/merge_requests/4",
                "status": "queued",
                "queue_position": 1,
                "enqueued_at": "2026-09-01T00:03:00Z",
                "raw": {"todo_id": 104, "action": "review_requested"},
            },
        ],
    )

    mock_bb = AsyncMock()
    mock_bb.get_headhunter_snapshot = AsyncMock(
        side_effect=lambda platform: gl_snap if platform == "gitlab" else None
    )
    mock_bb.get_active_events_with_status = AsyncMock(return_value={})
    mock_bb.get_waiting_approval_events = AsyncMock(return_value=[])

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        with patch.dict(
            os.environ,
            {"HEADHUNTER_ENABLED": "true", "GITLAB_HOST": "gitlab.example.com"},
            clear=False,
        ):
            with patch("httpx.AsyncClient", side_effect=_forbid_http_client):
                from src import dependencies
                from src.main import app

                original_bb = dependencies._blackboard
                dependencies._blackboard = mock_bb
                try:
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        resp = await client.get("/queue/headhunter/pending")
                finally:
                    dependencies._blackboard = original_bb

    assert resp.status_code == 200
    data = resp.json()
    mr_iids = {t["mr_iid"] for t in data}
    assert mr_iids == {1, 4}


def _make_event_document(event_id: str, created_by_email: str | None = None):
    """Build a minimal EventDocument-like MagicMock for queue route tests."""
    from src.models import EventDocument, EventEvidence, EventInput
    return EventDocument(
        id=event_id,
        source="chat",
        service="general",
        event=EventInput(
            reason="test",
            evidence=EventEvidence(
                display_text="test",
                source_type="chat",
                domain="disorder",
                severity="info",
            ),
        ),
        created_by_email=created_by_email,
    )


@pytest.mark.asyncio
async def test_queue_active_includes_created_by_email():
    """GET /queue/active returns created_by_email for each event."""
    evt_with_email = _make_event_document("evt-test0001", created_by_email="dev@redhat.com")
    evt_without_email = _make_event_document("evt-test0002", created_by_email=None)

    mock_bb = AsyncMock()
    mock_bb.get_active_events = AsyncMock(return_value=["evt-test0001", "evt-test0002"])

    async def fake_get_event(eid):
        return {"evt-test0001": evt_with_email, "evt-test0002": evt_without_email}.get(eid)

    mock_bb.get_event = AsyncMock(side_effect=fake_get_event)

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        from src import dependencies
        from src.main import app

        original_bb = dependencies._blackboard
        dependencies._blackboard = mock_bb
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/queue/active")
        finally:
            dependencies._blackboard = original_bb

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2

    by_id = {e["id"]: e for e in data}
    assert by_id["evt-test0001"]["created_by_email"] == "dev@redhat.com"
    assert by_id["evt-test0002"]["created_by_email"] is None


async def _post_with_mocked_deps(path: str, mock_bb, mock_brain, json_body=None):
    """POST to `path` with dependencies.get_blackboard/get_brain overridden."""
    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        from src import dependencies
        from src.main import app

        original_bb = dependencies._blackboard
        original_brain = dependencies._brain
        dependencies._blackboard = mock_bb
        dependencies._brain = mock_brain
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                return await client.post(path, json=json_body or {})
        finally:
            dependencies._blackboard = original_bb
            dependencies._brain = original_brain


@pytest.mark.asyncio
async def test_approve_event_enqueues_for_processing():
    """POST /queue/{id}/approve calls brain.enqueue_for_processing (evt-4eeff00c Fix 1)."""
    event = _make_event_document("evt-appr0001")

    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)

    mock_brain = MagicMock()
    mock_brain.clear_waiting = MagicMock()
    mock_brain.resume_if_parked = AsyncMock(return_value=True)
    mock_brain.enqueue_for_processing = MagicMock(return_value=True)

    resp = await _post_with_mocked_deps("/queue/evt-appr0001/approve", mock_bb, mock_brain)

    assert resp.status_code == 200
    mock_bb.append_turn.assert_awaited_once()
    mock_brain.clear_waiting.assert_called_once_with("evt-appr0001")
    mock_brain.resume_if_parked.assert_awaited_once_with("evt-appr0001")
    mock_brain.enqueue_for_processing.assert_called_once_with("evt-appr0001")


@pytest.mark.asyncio
async def test_reject_event_enqueues_for_processing():
    """POST /queue/{id}/reject calls brain.enqueue_for_processing (evt-4eeff00c Fix 1)."""
    event = _make_event_document("evt-rej00001")

    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)

    mock_brain = MagicMock()
    mock_brain.clear_waiting = MagicMock()
    mock_brain.resume_if_parked = AsyncMock(return_value=True)
    mock_brain.enqueue_for_processing = MagicMock(return_value=True)

    resp = await _post_with_mocked_deps(
        "/queue/evt-rej00001/reject", mock_bb, mock_brain, json_body={"reason": "not now"},
    )

    assert resp.status_code == 200
    mock_bb.append_turn.assert_awaited_once()
    mock_brain.clear_waiting.assert_called_once_with("evt-rej00001")
    mock_brain.resume_if_parked.assert_awaited_once_with("evt-rej00001")
    mock_brain.enqueue_for_processing.assert_called_once_with("evt-rej00001")


@pytest.mark.asyncio
async def test_approve_event_404_skips_enqueue():
    """Unknown event_id returns 404 and never reaches brain.enqueue_for_processing."""
    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=None)

    mock_brain = MagicMock()
    mock_brain.enqueue_for_processing = MagicMock(return_value=True)

    resp = await _post_with_mocked_deps("/queue/evt-missing/approve", mock_bb, mock_brain)

    assert resp.status_code == 404
    mock_brain.enqueue_for_processing.assert_not_called()


@pytest.mark.asyncio
async def test_approve_enqueues_when_not_parked():
    """enqueue_for_processing fires even when resume_if_parked returns False (active, not waiting_approval)."""
    event = _make_event_document("evt-notparked")

    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)

    mock_brain = MagicMock()
    mock_brain.clear_waiting = MagicMock()
    mock_brain.resume_if_parked = AsyncMock(return_value=False)
    mock_brain.enqueue_for_processing = MagicMock(return_value=True)

    resp = await _post_with_mocked_deps("/queue/evt-notparked/approve", mock_bb, mock_brain)

    assert resp.status_code == 200
    mock_brain.resume_if_parked.assert_awaited_once_with("evt-notparked")
    mock_brain.enqueue_for_processing.assert_called_once_with("evt-notparked")


@pytest.mark.asyncio
async def test_reject_enqueues_when_not_parked():
    """enqueue_for_processing fires even when resume_if_parked returns False (active, not waiting_approval)."""
    event = _make_event_document("evt-notparked2")

    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)

    mock_brain = MagicMock()
    mock_brain.clear_waiting = MagicMock()
    mock_brain.resume_if_parked = AsyncMock(return_value=False)
    mock_brain.enqueue_for_processing = MagicMock(return_value=True)

    resp = await _post_with_mocked_deps(
        "/queue/evt-notparked2/reject", mock_bb, mock_brain, json_body={"reason": "nope"},
    )

    assert resp.status_code == 200
    mock_brain.resume_if_parked.assert_awaited_once_with("evt-notparked2")
    mock_brain.enqueue_for_processing.assert_called_once_with("evt-notparked2")


def _make_headhunter_event(
    event_id: str,
    *,
    github_context: dict | None = None,
    github_issue_context: dict | None = None,
):
    """Build a headhunter-sourced EventDocument with GitHub PR or Issue evidence (#233)."""
    from src.models import EventDocument, EventEvidence, EventInput
    return EventDocument(
        id=event_id,
        source="headhunter",
        service="github",
        event=EventInput(
            reason="test",
            evidence=EventEvidence(
                display_text="test",
                source_type="headhunter",
                domain="complicated",
                severity="info",
                github_context=github_context,
                github_issue_context=github_issue_context,
            ),
        ),
    )


async def _get_headhunter_pending(mock_bb):
    """GET /queue/headhunter/pending purely from Redis (zero outbound httpx calls)."""
    if not isinstance(getattr(mock_bb, "get_headhunter_snapshot", None), AsyncMock):
        mock_bb.get_headhunter_snapshot = AsyncMock(return_value=None)
    if not isinstance(getattr(mock_bb, "get_waiting_approval_events", None), AsyncMock):
        mock_bb.get_waiting_approval_events = AsyncMock(return_value=[])

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        with patch.dict(
            os.environ,
            {"HEADHUNTER_ENABLED": "true", "GITLAB_HOST": "gitlab.example.com"},
            clear=False,
        ):
            with patch("httpx.AsyncClient", side_effect=_forbid_http_client):
                from src import dependencies
                from src.main import app

                original_bb = dependencies._blackboard
                dependencies._blackboard = mock_bb
                try:
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        return await client.get("/queue/headhunter/pending")
                finally:
                    dependencies._blackboard = original_bb


@pytest.mark.asyncio
async def test_headhunter_pending_includes_active_github_pr_event():
    """Active headhunter event with github_context (PR) surfaces with action='active' (#233)."""
    event = _make_headhunter_event(
        "evt-pr000001",
        github_context={
            "owner": "The-Darwin-Project",
            "repo": "Blackboard",
            "pr_number": 233,
            "pr_title": "Fix pending widget",
            "author": "octocat",
            "pr_url": "https://github.com/The-Darwin-Project/Blackboard/pull/233",
        },
    )

    mock_bb = AsyncMock()
    mock_bb.get_active_events_with_status = AsyncMock(return_value={"evt-pr000001": "active"})
    mock_bb.get_event = AsyncMock(return_value=event)

    resp = await _get_headhunter_pending(mock_bb)

    assert resp.status_code == 200
    data = resp.json()
    active_items = [item for item in data if item.get("action") == "active"]
    assert len(active_items) == 1
    item = active_items[0]
    assert item["platform"] == "github"
    assert item["pr_number"] == 233
    assert item["project_path"] == "The-Darwin-Project/Blackboard"
    assert item["target_url"] == "https://github.com/The-Darwin-Project/Blackboard/pull/233"


@pytest.mark.asyncio
async def test_headhunter_pending_includes_active_github_issue_event():
    """Active headhunter event with github_issue_context (Issue) surfaces with action='active' (#233)."""
    event = _make_headhunter_event(
        "evt-issue0001",
        github_issue_context={
            "owner": "The-Darwin-Project",
            "repo": "Blackboard",
            "issue_number": 233,
            "title": "Headhunter pending widget drops active GitHub work",
            "author": "octocat",
            "html_url": "https://github.com/The-Darwin-Project/Blackboard/issues/233",
            "created_at": "2026-09-01T00:00:00Z",
        },
    )

    mock_bb = AsyncMock()
    mock_bb.get_active_events_with_status = AsyncMock(return_value={"evt-issue0001": "active"})
    mock_bb.get_event = AsyncMock(return_value=event)

    resp = await _get_headhunter_pending(mock_bb)

    assert resp.status_code == 200
    data = resp.json()
    active_items = [item for item in data if item.get("action") == "active"]
    assert len(active_items) == 1
    item = active_items[0]
    assert item["platform"] == "github"
    assert item["issue_number"] == 233
    assert "pr_number" not in item
    assert item["issue_title"] == "Headhunter pending widget drops active GitHub work"
    assert item["project_path"] == "The-Darwin-Project/Blackboard"
    assert item["target_url"] == "https://github.com/The-Darwin-Project/Blackboard/issues/233"


@pytest.mark.asyncio
async def test_headhunter_pending_omits_closed_github_event():
    """An event no longer in the active set (closed) does not appear in /headhunter/pending (#233)."""
    mock_bb = AsyncMock()
    mock_bb.get_active_events_with_status = AsyncMock(return_value={})
    mock_bb.get_event = AsyncMock(side_effect=AssertionError("get_event should not be called with no active events"))

    resp = await _get_headhunter_pending(mock_bb)

    assert resp.status_code == 200
    data = resp.json()
    assert all(item.get("action") != "active" for item in data)
    assert data == []


@pytest.mark.asyncio
async def test_headhunter_pending_isolates_get_event_failure_per_item():
    """One malformed/broken active-event record must not drop other active GitHub items
    (#233 review, HIGH). get_event() raises for one id, succeeds for another in the same
    status_map -- asyncio.gather(return_exceptions=True) must isolate the failure."""
    good_event = _make_headhunter_event(
        "evt-good0001",
        github_context={
            "owner": "The-Darwin-Project",
            "repo": "Blackboard",
            "pr_number": 233,
            "pr_title": "Surviving PR",
            "author": "octocat",
            "pr_url": "https://github.com/The-Darwin-Project/Blackboard/pull/233",
        },
    )

    async def fake_get_event(eid):
        if eid == "evt-broken01":
            raise ValueError("boom: malformed evidence")
        return good_event

    mock_bb = AsyncMock()
    mock_bb.get_active_events_with_status = AsyncMock(
        return_value={"evt-broken01": "active", "evt-good0001": "active"}
    )
    mock_bb.get_event = AsyncMock(side_effect=fake_get_event)

    resp = await _get_headhunter_pending(mock_bb)

    assert resp.status_code == 200
    data = resp.json()
    active_items = [item for item in data if item.get("action") == "active"]
    assert len(active_items) == 1
    assert active_items[0]["pr_number"] == 233
    assert active_items[0]["pr_title"] == "Surviving PR"


@pytest.mark.asyncio
async def test_headhunter_pending_filters_non_headhunter_active_events():
    """A non-headhunter active event alongside a headhunter one: only the headhunter one
    surfaces -- proves the source filter discriminates rather than just never encountering
    a non-headhunter event (#233 review, MEDIUM test-coverage gap #1)."""
    hh_event = _make_headhunter_event(
        "evt-hh000001",
        github_context={
            "owner": "The-Darwin-Project",
            "repo": "Blackboard",
            "pr_number": 233,
            "pr_title": "Active PR",
            "author": "octocat",
            "pr_url": "https://github.com/The-Darwin-Project/Blackboard/pull/233",
        },
    )
    chat_event = _make_event_document("evt-chat00001")

    events_by_id = {"evt-hh000001": hh_event, "evt-chat00001": chat_event}

    mock_bb = AsyncMock()
    mock_bb.get_active_events_with_status = AsyncMock(
        return_value={"evt-hh000001": "active", "evt-chat00001": "active"}
    )
    mock_bb.get_event = AsyncMock(side_effect=lambda eid: events_by_id[eid])

    resp = await _get_headhunter_pending(mock_bb)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["pr_number"] == 233


@pytest.mark.asyncio
async def test_headhunter_pending_skips_headhunter_event_without_github_context():
    """A headhunter active event with neither github_context nor github_issue_context set
    is silently skipped, not appended as a malformed row (#233 review, MEDIUM test-coverage
    gap #2)."""
    event = _make_headhunter_event("evt-nogh00001")  # both contexts default to None

    mock_bb = AsyncMock()
    mock_bb.get_active_events_with_status = AsyncMock(return_value={"evt-nogh00001": "active"})
    mock_bb.get_event = AsyncMock(return_value=event)

    resp = await _get_headhunter_pending(mock_bb)

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_headhunter_pending_handles_get_event_none_delete_race():
    """get_event() returning None for an id still present in status_map (event deleted
    between the two Blackboard reads) must not crash the endpoint (#233 review, MEDIUM
    test-coverage gap #3 -- exercises the `if not event` guard)."""
    mock_bb = AsyncMock()
    mock_bb.get_active_events_with_status = AsyncMock(return_value={"evt-deleted0001": "active"})
    mock_bb.get_event = AsyncMock(return_value=None)

    resp = await _get_headhunter_pending(mock_bb)

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_headhunter_pending_sorts_all_platforms_by_created_at():
    """Pure-Redis /pending interleaves GitLab snapshot items, GitHub snapshot items, and
    Blackboard-active GitHub events chronologically by created_at (#233)."""
    gl_snap = _make_snapshot(
        "gitlab",
        items=[
            {
                "platform": "gitlab",
                "item_kind": "mr",
                "item_id": 1,
                "project_ref": "group/repo",
                "title": "GitLab MR",
                "author": "gl-author",
                "url": "https://gitlab.example.com/group/repo/-/merge_requests/1",
                "status": "pending",
                "enqueued_at": "2026-01-01T00:00:00Z",
                "raw": {"todo_id": 1, "action": "review_requested"},
            }
        ],
    )
    gh_snap = _make_snapshot(
        "github",
        items=[
            {
                "platform": "github",
                "item_kind": "pr",
                "item_id": 99,
                "project_ref": "The-Darwin-Project/Blackboard",
                "title": "Queued PR",
                "author": "queued-author",
                "url": "https://github.com/The-Darwin-Project/Blackboard/pull/99",
                "status": "queued",
                "queue_position": 1,
                "enqueued_at": "2026-01-03T00:00:00Z",
            }
        ],
    )

    active_event = _make_headhunter_event(
        "evt-sort0001",
        github_context={
            "owner": "The-Darwin-Project",
            "repo": "Blackboard",
            "pr_number": 233,
            "pr_title": "Active PR",
            "author": "active-author",
            "pr_url": "https://github.com/The-Darwin-Project/Blackboard/pull/233",
            "created_at": "2026-01-02T00:00:00Z",
        },
    )
    mock_bb = AsyncMock()
    mock_bb.get_headhunter_snapshot = AsyncMock(
        side_effect=lambda platform: {"gitlab": gl_snap, "github": gh_snap}.get(platform)
    )
    mock_bb.get_active_events_with_status = AsyncMock(return_value={"evt-sort0001": "active"})
    mock_bb.get_waiting_approval_events = AsyncMock(return_value=[])
    mock_bb.get_event = AsyncMock(return_value=active_event)

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        with patch.dict(
            os.environ,
            {
                "HEADHUNTER_ENABLED": "true",
                "HEADHUNTER_GITHUB_ENABLED": "true",
                "GITLAB_HOST": "gitlab.example.com",
            },
            clear=False,
        ):
            with patch("httpx.AsyncClient", side_effect=_forbid_http_client):
                from src import dependencies
                from src.main import app

                original_bb = dependencies._blackboard
                dependencies._blackboard = mock_bb
                try:
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        resp = await client.get("/queue/headhunter/pending")
                finally:
                    dependencies._blackboard = original_bb

    assert resp.status_code == 200
    data = resp.json()
    assert [item["platform"] for item in data] == ["gitlab", "github", "github"]
    assert [item.get("action") for item in data] == ["review_requested", "active", "queued"]
    assert data[1]["pr_title"] == "Active PR"
    assert data[2]["pr_title"] == "Queued PR"


# =============================================================================
# Regression tests for issue #230: /headhunter/pending exposes queued GitHub Issues
# =============================================================================


async def _get_pending_with_github_snapshot(gh_snap):
    """GET /queue/headhunter/pending with GitHub snapshot fixture and zero HTTP calls."""
    mock_bb = AsyncMock()
    mock_bb.get_headhunter_snapshot = AsyncMock(
        side_effect=lambda platform: gh_snap if platform == "github" else None
    )
    mock_bb.get_active_events_with_status = AsyncMock(return_value={})
    mock_bb.get_waiting_approval_events = AsyncMock(return_value=[])

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        with patch.dict(
            os.environ,
            {"HEADHUNTER_ENABLED": "true", "HEADHUNTER_GITHUB_ENABLED": "true"},
            clear=False,
        ):
            with patch("httpx.AsyncClient", side_effect=_forbid_http_client):
                from src import dependencies
                from src.main import app

                original_bb = dependencies._blackboard
                dependencies._blackboard = mock_bb
                try:
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        return await client.get("/queue/headhunter/pending")
                finally:
                    dependencies._blackboard = original_bb


@pytest.mark.asyncio
async def test_headhunter_pending_includes_queued_github_issues():
    """Queued GitHub Issues from Redis snapshot must appear alongside queued PRs, using
    issue-specific field names (issue_number/issue_title)."""
    gh_snap = _make_snapshot(
        "github",
        items=[
            {
                "platform": "github",
                "item_kind": "issue",
                "item_id": 9,
                "project_ref": "o/r",
                "title": "Needs triage",
                "author": "alice",
                "url": "https://github.com/o/r/issues/9",
                "status": "queued",
                "queue_position": 1,
                "enqueued_at": "2026-07-01T00:00:00Z",
            }
        ],
    )

    resp = await _get_pending_with_github_snapshot(gh_snap)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    item = data[0]
    assert item["platform"] == "github"
    assert item["issue_number"] == 9
    assert item["issue_title"] == "Needs triage"
    assert item["project_path"] == "o/r"
    assert item["queue_position"] == 1
    assert item["action"] == "queued"


@pytest.mark.asyncio
async def test_headhunter_pending_merges_and_sorts_queued_prs_and_issues():
    """Queued PRs and queued Issues both surface from Redis snapshot, globally sorted by
    created_at, with independent 1-based queue_position numbering."""
    gh_snap = _make_snapshot(
        "github",
        items=[
            {
                "platform": "github",
                "item_kind": "pr",
                "item_id": 5,
                "project_ref": "o/r",
                "title": "PR fix",
                "author": "bob",
                "url": "https://github.com/o/r/pull/5",
                "status": "queued",
                "queue_position": 1,
                "enqueued_at": "2026-07-02T00:00:00Z",
            },
            {
                "platform": "github",
                "item_kind": "issue",
                "item_id": 9,
                "project_ref": "o/r",
                "title": "Issue triage",
                "author": "alice",
                "url": "https://github.com/o/r/issues/9",
                "status": "queued",
                "queue_position": 1,
                "enqueued_at": "2026-07-01T00:00:00Z",
            },
        ],
    )

    resp = await _get_pending_with_github_snapshot(gh_snap)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    assert data[0]["issue_number"] == 9
    assert data[1]["pr_number"] == 5
    assert data[0]["queue_position"] == 1
    assert data[1]["queue_position"] == 1

@pytest.mark.asyncio
async def test_approve_event_ignores_ownership(monkeypatch):
    """approve_event enforces RBAC under VMER-1949: unprivileged non-owner is rejected (403), maintainer or owner succeeds (200)."""
    monkeypatch.setattr("src.auth.DEX_ENABLED", True)
    # APPROVER_GROUPS fails closed (empty) by default; opt in explicitly for the
    # maintainer-override assertion below, same as a real operator would via env var.
    monkeypatch.setattr("src.auth.APPROVER_GROUPS", frozenset({"maintainers"}))

    event = _make_event_document("evt-appr0002")
    event.created_by_email = "owner@example.com"

    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.append_turn = AsyncMock()
    mock_bb.stamp_event = AsyncMock()

    mock_brain = MagicMock()
    mock_brain.clear_waiting = MagicMock()
    mock_brain.resume_if_parked = AsyncMock(return_value=True)
    mock_brain.enqueue_for_processing = MagicMock(return_value=True)

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        from src import dependencies
        from src.main import app

        app.dependency_overrides[dependencies.get_blackboard] = lambda: mock_bb
        app.dependency_overrides[dependencies.get_brain] = lambda: mock_brain

        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Unprivileged stranger (roles=[]) -> 403 Forbidden
            monkeypatch.setattr("src.auth._validate_jwt", lambda token: {"sub": "u1", "email": "other@example.com", "name": "Op", "groups": []})
            resp_forbidden = await client.post(
                "/queue/evt-appr0002/approve",
                headers={"Authorization": "Bearer valid-jwt"}
            )
            assert resp_forbidden.status_code == 403

            # 2. Maintainer (roles=["maintainers"]) -> 200 OK
            monkeypatch.setattr("src.auth._validate_jwt", lambda token: {"sub": "u1", "email": "other@example.com", "name": "Op", "groups": ["maintainers"]})
            resp_maintainer = await client.post(
                "/queue/evt-appr0002/approve",
                headers={"Authorization": "Bearer valid-jwt"}
            )
            assert resp_maintainer.status_code == 200

            # 3. Owner (roles=[]) -> 200 OK
            monkeypatch.setattr("src.auth._validate_jwt", lambda token: {"sub": "u2", "email": "owner@example.com", "name": "Owner", "groups": []})
            resp_owner = await client.post(
                "/queue/evt-appr0002/approve",
                headers={"Authorization": "Bearer valid-jwt"}
            )
            assert resp_owner.status_code == 200

        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_reject_event_enforces_same_rbac_as_approve(monkeypatch):
    """reject_event is gated by the same can_approve_event() check as approve_event (code
    review finding: rejecting a plan is the same state transition approval requires
    authorization for, so an unauthorized caller must not be able to reject someone else's
    pending plan either). Unprivileged non-owner -> 403; owner or maintainer -> 200, and a
    successful reject clears any prior approval stamp."""
    monkeypatch.setattr("src.auth.DEX_ENABLED", True)
    monkeypatch.setattr("src.auth.APPROVER_GROUPS", frozenset({"maintainers"}))

    event = _make_event_document("evt-rej0002")
    event.created_by_email = "owner@example.com"
    event.approved_by = "owner@example.com"
    event.approved_mr_id = "42"
    event.approved_mr_sha = "stale-sha"

    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.append_turn = AsyncMock()
    mock_bb.stamp_event = AsyncMock()

    mock_brain = MagicMock()
    mock_brain.resume_if_parked = AsyncMock(return_value=True)
    mock_brain.enqueue_for_processing = MagicMock(return_value=True)

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        from src import dependencies
        from src.main import app

        app.dependency_overrides[dependencies.get_blackboard] = lambda: mock_bb
        app.dependency_overrides[dependencies.get_brain] = lambda: mock_brain

        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # 1. Unprivileged stranger (no groups, not the owner) -> 403 Forbidden
            monkeypatch.setattr("src.auth._validate_jwt", lambda token: {"sub": "u1", "email": "other@example.com", "name": "Op", "groups": []})
            resp_forbidden = await client.post(
                "/queue/evt-rej0002/reject",
                json={"reason": "no"},
                headers={"Authorization": "Bearer valid-jwt"}
            )
            assert resp_forbidden.status_code == 403
            mock_bb.stamp_event.assert_not_awaited()

            # 2. Owner -> 200 OK, and the prior approval stamp is cleared
            monkeypatch.setattr("src.auth._validate_jwt", lambda token: {"sub": "u2", "email": "owner@example.com", "name": "Owner", "groups": []})
            resp_owner = await client.post(
                "/queue/evt-rej0002/reject",
                json={"reason": "no"},
                headers={"Authorization": "Bearer valid-jwt"}
            )
            assert resp_owner.status_code == 200
            mock_bb.stamp_event.assert_awaited_with(
                "evt-rej0002",
                approved_by=None,
                approved_mr_id=None,
                approved_mr_sha=None,
                approval_requested_sha=None,
            )

        app.dependency_overrides.clear()

@pytest.mark.asyncio
async def test_close_event_by_user_ignores_ownership(monkeypatch):
    """close_event_by_user has no ownership check today and must NOT gain one."""
    monkeypatch.setattr("src.auth.DEX_ENABLED", True)
    monkeypatch.setattr("src.auth._validate_jwt", lambda token: {"sub": "u1", "email": "other@example.com", "name": "Op"})
    
    event = _make_event_document("evt-close0002")
    event.created_by_email = "owner@example.com"

    mock_bb = AsyncMock()
    mock_bb.get_event = AsyncMock(return_value=event)
    mock_bb.append_turn = AsyncMock()
    
    mock_brain = MagicMock()
    mock_brain.resume_if_parked = AsyncMock(return_value=True)
    mock_brain.enqueue_for_processing = MagicMock(return_value=True)

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        from src import dependencies
        from src.main import app

        app.dependency_overrides[dependencies.get_blackboard] = lambda: mock_bb
        app.dependency_overrides[dependencies.get_brain] = lambda: mock_brain
        
        from httpx import ASGITransport, AsyncClient
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/queue/evt-close0002/close",
                headers={"Authorization": "Bearer valid-jwt"}
            )
            
        app.dependency_overrides.clear()

    assert resp.status_code == 200


# =============================================================================
# 4-Layer Farley ATDD Executable Specification: Scenario T-4
# Plan Step Status Transitions (red_locked, green_verified) & Test Evidence
# =============================================================================
class PlanStepProtocolDriver:
    """Layer 3: Protocol driver adapting FastAPI in-process HTTP requests."""

    def __init__(self, app, mock_bb, mock_brain):
        self.app = app
        self.mock_bb = mock_bb
        self.mock_brain = mock_brain
        self.broadcasted_turns: list[tuple[str, Any]] = []

        async def _append_and_broadcast(event_id: str, turn: Any):
            self.broadcasted_turns.append((event_id, turn))
        self.mock_brain.append_and_broadcast = AsyncMock(side_effect=_append_and_broadcast)

    async def post_plan_step(self, event_id: str, payload: dict) -> tuple[int, dict]:
        from src import dependencies
        self.app.dependency_overrides[dependencies.get_blackboard] = lambda: self.mock_bb
        self.app.dependency_overrides[dependencies.get_brain] = lambda: self.mock_brain
        orig_brain = dependencies._brain
        dependencies._brain = self.mock_brain

        try:
            transport = ASGITransport(app=self.app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.post(f"/queue/{event_id}/plan-step", json=payload)
                return resp.status_code, resp.json() if resp.is_success else {}
        finally:
            dependencies._brain = orig_brain
            self.app.dependency_overrides.clear()


class PlanStepDSL:
    """Layer 2: Domain DSL operations for Farley plan-step verification."""

    def __init__(self, driver: PlanStepProtocolDriver):
        self.driver = driver
        self.last_status_code: int | None = None
        self.last_response: dict | None = None

    def given_active_event_with_red_lock(self, event_id: str, red_locked_at: float | None = None):
        event = _make_event_document(event_id)
        if red_locked_at is not None:
            mock_event = MagicMock(wraps=event)
            mock_event.red_locked_at = red_locked_at
            event = mock_event
        self.driver.mock_bb.get_event = AsyncMock(return_value=event)
        self.driver.mock_brain.next_turn_number = AsyncMock(return_value=5)

    async def when_agent_updates_plan_step(
        self,
        event_id: str,
        step_id: str,
        status: str,
        role: str,
        notes: str = "",
        test_evidence: dict | None = None,
    ):
        payload: dict[str, Any] = {
            "step_id": step_id,
            "status": status,
            "role": role,
            "notes": notes,
        }
        if test_evidence is not None:
            payload["test_evidence"] = test_evidence

        code, resp = await self.driver.post_plan_step(event_id, payload)
        self.last_status_code = code
        self.last_response = resp

    def then_request_succeeded(self):
        assert self.last_status_code == 200, f"Expected 200, got {self.last_status_code}"
        assert self.last_response.get("ok") is True

    def then_broadcast_turn_contains_test_evidence(self, expected_status: str, expected_evidence: dict):
        assert len(self.driver.broadcasted_turns) > 0, "No turn broadcasted"
        _, turn = self.driver.broadcasted_turns[-1]
        task_for_agent = turn.taskForAgent or {}
        assert task_for_agent.get("status") == expected_status, (
            f"Expected status {expected_status!r}, got {task_for_agent.get('status')!r}"
        )
        assert "test_evidence" in task_for_agent, (
            f"Expected 'test_evidence' in turn.taskForAgent, got keys: {list(task_for_agent.keys())}"
        )
        assert task_for_agent["test_evidence"] == expected_evidence

    def then_event_stamped_with_red_locked_at(self, event_id: str):
        stamps = [
            call.kwargs for call in self.driver.mock_bb.stamp_event.await_args_list
            if (call.args and call.args[0] == event_id) or call.kwargs.get("event_id") == event_id
        ]
        assert any("red_locked_at" in s for s in stamps), (
            f"Expected stamp_event to record 'red_locked_at' on {event_id}, calls: {self.driver.mock_bb.stamp_event.await_args_list}"
        )

    def then_event_stamped_with_atdd_cycle_sec(self, event_id: str):
        stamps = [
            call.kwargs for call in self.driver.mock_bb.stamp_event.await_args_list
            if (call.args and call.args[0] == event_id) or call.kwargs.get("event_id") == event_id
        ]
        assert any("atdd_cycle_sec" in s for s in stamps), (
            f"Expected stamp_event to record 'atdd_cycle_sec' on {event_id}, calls: {self.driver.mock_bb.stamp_event.await_args_list}"
        )


class TestPlanStepFarleyATDDScenarioT4:
    """Layer 1: Domain Scenarios for Scenario T-4."""

    @pytest.mark.asyncio
    async def test_red_locked_status_records_evidence_and_stamp(self):
        """
        Scenario: QE agent locks failing test specification with status='red_locked' and test_evidence.
        Given an active event
        When QE posts status='red_locked' with test runner failure evidence
        Then status code is 200, turn includes test_evidence, and red_locked_at is stamped.
        """
        with patch("src.main.lifespan") as mock_lifespan:
            mock_lifespan.return_value.__aenter__ = AsyncMock()
            mock_lifespan.return_value.__aexit__ = AsyncMock()
            from src.main import app

            mock_bb = AsyncMock()
            mock_brain = MagicMock()
            driver = PlanStepProtocolDriver(app, mock_bb, mock_brain)
            dsl = PlanStepDSL(driver)

            dsl.given_active_event_with_red_lock("evt-atdd-01")
            test_evidence = {"runner": "pytest", "exit_code": 1, "failed_assertion": "assert False"}

            await dsl.when_agent_updates_plan_step(
                event_id="evt-atdd-01",
                step_id="step-1",
                status="red_locked",
                role="qe",
                notes="Authoring Farley ATDD red test specification",
                test_evidence=test_evidence,
            )

            dsl.then_request_succeeded()
            dsl.then_broadcast_turn_contains_test_evidence("red_locked", test_evidence)
            dsl.then_event_stamped_with_red_locked_at("evt-atdd-01")

    @pytest.mark.asyncio
    async def test_green_verified_status_computes_cycle_time(self):
        """
        Scenario: Developer agent completes implementation with status='green_verified'.
        Given an active event with red_locked_at stamped
        When Developer posts status='green_verified' with passing evidence
        Then status code is 200, turn includes test_evidence, and atdd_cycle_sec is recorded.
        """
        with patch("src.main.lifespan") as mock_lifespan:
            mock_lifespan.return_value.__aenter__ = AsyncMock()
            mock_lifespan.return_value.__aexit__ = AsyncMock()
            from src.main import app

            mock_bb = AsyncMock()
            mock_brain = MagicMock()
            driver = PlanStepProtocolDriver(app, mock_bb, mock_brain)
            dsl = PlanStepDSL(driver)

            import time
            dsl.given_active_event_with_red_lock("evt-atdd-02", red_locked_at=time.time() - 45.0)
            passing_evidence = {"runner": "pytest", "exit_code": 0, "passed_tests": 12}

            await dsl.when_agent_updates_plan_step(
                event_id="evt-atdd-02",
                step_id="step-1",
                status="green_verified",
                role="developer",
                notes="Implementation complete; all tests passing",
                test_evidence=passing_evidence,
            )

            dsl.then_request_succeeded()
            dsl.then_broadcast_turn_contains_test_evidence("green_verified", passing_evidence)
            dsl.then_event_stamped_with_atdd_cycle_sec("evt-atdd-02")


# =========================================================================
# Batch 1 ATDD (Step 6 / T-10) — Migrated to Pure-Redis Snapshots (Slice 2C)
# =========================================================================


async def _get_headhunter_pending_redis(
    *,
    env: dict[str, str],
    mock_bb: AsyncMock,
    gitlab_snapshot: object = None,
    github_snapshot: object = None,
    gitlab_snapshot_exc: Exception | None = None,
    github_snapshot_exc: Exception | None = None,
):
    """Layer 3 Protocol Driver for pure-Redis GET /queue/headhunter/pending (zero HTTP)."""
    async def _get_snap(platform: str):
        if platform == "gitlab":
            if gitlab_snapshot_exc is not None:
                raise gitlab_snapshot_exc
            return gitlab_snapshot
        if platform == "github":
            if github_snapshot_exc is not None:
                raise github_snapshot_exc
            return github_snapshot
        return None

    mock_bb.get_headhunter_snapshot = AsyncMock(side_effect=_get_snap)
    if not isinstance(getattr(mock_bb, "get_waiting_approval_events", None), AsyncMock):
        mock_bb.get_waiting_approval_events = AsyncMock(return_value=[])

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        with patch.dict(os.environ, env, clear=False):
            with patch("httpx.AsyncClient", side_effect=_forbid_http_client):
                from src import dependencies
                from src.main import app

                original_bb = dependencies._blackboard
                dependencies._blackboard = mock_bb
                try:
                    transport = ASGITransport(app=app)
                    async with AsyncClient(transport=transport, base_url="http://test") as client:
                        return await client.get("/queue/headhunter/pending")
                finally:
                    dependencies._blackboard = original_bb


def _github_pending_fixtures():
    gh_snap = _make_snapshot(
        "github",
        items=[
            {
                "platform": "github",
                "item_kind": "pr",
                "item_id": 77,
                "project_ref": "The-Darwin-Project/BlackBoard",
                "title": "Queued PR",
                "author": "octocat",
                "url": "https://github.com/The-Darwin-Project/BlackBoard/pull/77",
                "status": "queued",
                "queue_position": 1,
                "enqueued_at": "2026-09-01T00:00:00Z",
            }
        ],
    )
    issue_event = _make_headhunter_event(
        "evt-issue-t10",
        github_issue_context={
            "owner": "The-Darwin-Project",
            "repo": "BlackBoard",
            "issue_number": 233,
            "title": "Active issue title",
            "author": "octocat",
            "html_url": "https://github.com/The-Darwin-Project/BlackBoard/issues/233",
            "created_at": "2026-09-01T00:01:00Z",
        },
    )
    mock_bb = AsyncMock()
    mock_bb.get_active_events_with_status = AsyncMock(return_value={"evt-issue-t10": "active"})
    mock_bb.get_waiting_approval_events = AsyncMock(return_value=[])
    mock_bb.get_event = AsyncMock(return_value=issue_event)
    return mock_bb, gh_snap


class TestATDDT10QueuePendingDecoupling:
    """Layer 1-4 ATDD scenarios for T-10 migrated to pure-Redis snapshots."""

    @pytest.mark.asyncio
    async def test_t10a_gitlab_host_unset_still_returns_github_queued_and_active_items(self):
        """Given GITLAB_HOST="" and GitHub Redis snapshot + active issue event
        When GET /queue/headhunter/pending is called
        Then HTTP 200 returns GitHub queued PRs and active Issues with zero outbound HTTP."""
        mock_bb, gh_snap = _github_pending_fixtures()
        resp = await _get_headhunter_pending_redis(
            env={"GITLAB_HOST": "", "HEADHUNTER_ENABLED": "true", "HEADHUNTER_GITHUB_ENABLED": "true"},
            mock_bb=mock_bb,
            github_snapshot=gh_snap,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any(i.get("pr_number") == 77 and i.get("action") == "queued" for i in data)
        issues = [i for i in data if i.get("issue_number") == 233]
        assert len(issues) == 1
        assert issues[0]["issue_title"] == "Active issue title"
        assert "pr_number" not in issues[0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("failure_mode", ["none_snap", "partial_error", "redis_exc"])
    async def test_t10b_gitlab_snapshot_failures_skip_gitlab_and_return_github_items(self, failure_mode):
        """Given GitLab snapshot is missing, reports partial_error, or fails Redis lookup
        When GET /queue/headhunter/pending is called
        Then GitLab is isolated and GitHub queued & active items still appear with zero HTTP calls."""
        mock_bb, gh_snap = _github_pending_fixtures()
        kwargs: dict = {
            "env": {
                "GITLAB_HOST": "gitlab.example.com",
                "HEADHUNTER_ENABLED": "true",
                "HEADHUNTER_GITHUB_ENABLED": "true",
            },
            "mock_bb": mock_bb,
            "github_snapshot": gh_snap,
        }
        if failure_mode == "partial_error":
            kwargs["gitlab_snapshot"] = _make_snapshot(
                "gitlab", partial_error="HTTP 500", breaker_state="open", items=[]
            )
        elif failure_mode == "redis_exc":
            kwargs["gitlab_snapshot_exc"] = RuntimeError("redis timeout")

        resp = await _get_headhunter_pending_redis(**kwargs)
        assert resp.status_code == 200
        data = resp.json()
        assert any(i.get("pr_number") == 77 for i in data), f"GitHub queued PR hidden on {failure_mode}"
        assert any(i.get("issue_number") == 233 for i in data), f"GitHub active Issue hidden on {failure_mode}"

    @pytest.mark.asyncio
    async def test_t10c_headhunter_enabled_false_with_github_enabled_true_returns_github_items(self):
        """Given HEADHUNTER_ENABLED=false and HEADHUNTER_GITHUB_ENABLED=true
        When GET /queue/headhunter/pending is called
        Then GitLab snapshot is skipped (zero HTTP calls) and GitHub items are returned."""
        mock_bb, gh_snap = _github_pending_fixtures()
        gl_snap = _make_snapshot(
            "gitlab",
            items=[
                {
                    "platform": "gitlab",
                    "item_kind": "mr",
                    "item_id": 11,
                    "project_ref": "org/repo",
                    "title": "Hidden GL MR",
                    "status": "pending",
                }
            ],
        )
        resp = await _get_headhunter_pending_redis(
            env={
                "GITLAB_HOST": "gitlab.example.com",
                "HEADHUNTER_ENABLED": "false",
                "HEADHUNTER_GITHUB_ENABLED": "true",
            },
            mock_bb=mock_bb,
            gitlab_snapshot=gl_snap,
            github_snapshot=gh_snap,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert not any(i.get("platform") == "gitlab" for i in data)
        assert any(i.get("pr_number") == 77 for i in data)
        assert any(i.get("issue_number") == 233 for i in data)

    @pytest.mark.asyncio
    async def test_t10d_pure_redis_pending_makes_zero_httpx_calls_even_with_gitlab_host(self):
        """Given GITLAB_HOST and HEADHUNTER_ENABLED=true
        When GET /queue/headhunter/pending runs
        Then zero outbound httpx.AsyncClient calls are made."""
        mock_bb = AsyncMock()
        mock_bb.get_active_events_with_status = AsyncMock(return_value={})
        gl_snap = _make_snapshot(
            "gitlab",
            items=[
                {
                    "platform": "gitlab",
                    "item_kind": "mr",
                    "item_id": 5,
                    "project_ref": "org/repo",
                    "title": "Snapshot MR",
                    "url": "https://gitlab.example.com/org/repo/-/merge_requests/5",
                    "status": "pending",
                    "enqueued_at": "2026-09-01T00:00:00Z",
                    "raw": {"todo_id": 55, "action": "assigned"},
                }
            ],
        )
        resp = await _get_headhunter_pending_redis(
            env={
                "GITLAB_HOST": "https://gitlab.example.com/",
                "HEADHUNTER_ENABLED": "true",
                "HEADHUNTER_GITHUB_ENABLED": "false",
            },
            mock_bb=mock_bb,
            gitlab_snapshot=gl_snap,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["mr_iid"] == 5

    @pytest.mark.asyncio
    async def test_t10e_both_flags_false_returns_empty_list(self):
        """Given HEADHUNTER_ENABLED=false and HEADHUNTER_GITHUB_ENABLED=false
        When GET /queue/headhunter/pending is called
        Then HTTP 200 returns [] with zero outbound HTTP calls."""
        mock_bb, gh_snap = _github_pending_fixtures()
        resp = await _get_headhunter_pending_redis(
            env={
                "GITLAB_HOST": "gitlab.example.com",
                "HEADHUNTER_ENABLED": "false",
                "HEADHUNTER_GITHUB_ENABLED": "false",
            },
            mock_bb=mock_bb,
            github_snapshot=gh_snap,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_t10f_malformed_dict_snapshot_and_missing_fields_do_not_crash_endpoint(self):
        """Malformed snapshot shapes, non-dict elements, non-numeric item_id, and None fields must not raise 500."""
        mock_bb = AsyncMock()
        mock_bb.get_active_events_with_status = AsyncMock(return_value={})

        for bad_snap in ({"unexpected": "shape"}, {"items": "not-a-list"}):
            resp1 = await _get_headhunter_pending_redis(
                env={
                    "GITLAB_HOST": "gitlab.example.com",
                    "HEADHUNTER_ENABLED": "true",
                    "HEADHUNTER_GITHUB_ENABLED": "false",
                },
                mock_bb=mock_bb,
                gitlab_snapshot=bad_snap,
            )
            assert resp1.status_code == 200
            assert resp1.json() == []

        mixed_dict_snap = {
            "platform": "gitlab",
            "enabled": True,
            "items": [
                "not-a-dict",
                None,
                {
                    "platform": "gitlab",
                    "item_kind": "mr",
                    "item_id": "abc",
                    "project_ref": None,
                    "title": None,
                    "author": None,
                    "url": None,
                    "ci_status": None,
                    "status": None,
                    "enqueued_at": None,
                    "raw": None,
                },
                {
                    "platform": "gitlab",
                    "item_kind": "mr",
                    "item_id": 9,
                    "project_ref": "org/repo",
                    "title": "Valid",
                    "url": "https://gitlab.example.com/org/repo/-/merge_requests/9",
                    "status": "pending",
                    "enqueued_at": "2026-09-01T00:00:00Z",
                    "raw": {"todo_id": 2, "action": "assigned"},
                },
            ],
        }
        resp2 = await _get_headhunter_pending_redis(
            env={
                "GITLAB_HOST": "gitlab.example.com",
                "HEADHUNTER_ENABLED": "true",
                "HEADHUNTER_GITHUB_ENABLED": "false",
            },
            mock_bb=mock_bb,
            gitlab_snapshot=mixed_dict_snap,
        )
        assert resp2.status_code == 200
        rows = resp2.json()
        assert any(r.get("mr_iid") == 9 and r.get("todo_id") == 2 for r in rows)
        assert all(isinstance(r, dict) and isinstance(r.get("created_at"), str) for r in rows)


# =========================================================================
# Slice 2C ATDD (Step 8 / T-13): Pure-Redis /pending, /status & /active SHA
# =========================================================================


class HeadhunterQueueProtocolDriver:
    """Layer 3 Protocol Driver for /queue/headhunter/* and /queue/active."""

    def __init__(self, mock_bb: AsyncMock, mock_hh: Any = None):
        self.mock_bb = mock_bb
        self.mock_hh = mock_hh

    async def request(
        self,
        method: str,
        path: str,
        *,
        env: dict[str, str] | None = None,
        json_body: dict | None = None,
        headers: dict[str, str] | None = None,
        forbid_http: bool = True,
    ):
        mock_brain = MagicMock()
        mock_brain.agents = {"_headhunter": self.mock_hh} if self.mock_hh is not None else {}

        env_vars = {
            "HEADHUNTER_ENABLED": "true",
            "HEADHUNTER_GITHUB_ENABLED": "true",
            "GITLAB_HOST": "gitlab.example.com",
        }
        if env:
            env_vars.update(env)

        with patch("src.main.lifespan") as mock_lifespan:
            mock_lifespan.return_value.__aenter__ = AsyncMock()
            mock_lifespan.return_value.__aexit__ = AsyncMock()
            with patch.dict(os.environ, env_vars, clear=False):
                ctx_http = (
                    patch("httpx.AsyncClient", side_effect=_forbid_http_client)
                    if forbid_http
                    else patch("httpx.AsyncClient")
                )
                with ctx_http:
                    from src import dependencies
                    from src.main import app

                    orig_bb = dependencies._blackboard
                    orig_brain = dependencies._brain
                    dependencies._blackboard = self.mock_bb
                    dependencies._brain = mock_brain
                    app.dependency_overrides[dependencies.get_blackboard] = lambda: self.mock_bb
                    app.dependency_overrides[dependencies.get_brain] = lambda: mock_brain
                    try:
                        transport = ASGITransport(app=app)
                        async with AsyncClient(transport=transport, base_url="http://test") as client:
                            return await client.request(
                                method, path, json=json_body, headers=headers or {}
                            )
                    finally:
                        app.dependency_overrides.clear()
                        dependencies._blackboard = orig_bb
                        dependencies._brain = orig_brain


class TestATDDT13PureRedisPendingAndStatus:
    """Layer 1-4 ATDD scenarios for T-13 (pure-Redis /pending, /status, /active SHA)."""

    @pytest.mark.asyncio
    async def test_t13a_pending_merges_snapshots_active_and_waiting_without_duplicating_parked_gitlab_mr(self):
        """Given GitLab snapshot (parked MR !42 + queued MR !99), GitHub snapshot (PR #77),
        active Issue #233, and waiting_approval GitLab MR !42
        When GET /queue/headhunter/pending is called
        Then HTTP 200 returns list[dict] with zero outbound HTTP calls, additive status/check_status fields,
        and MR !42 appears ONCE without duplication."""
        gl_snap = _make_snapshot(
            "gitlab",
            items=[
                {
                    "platform": "gitlab",
                    "item_kind": "mr",
                    "item_id": 42,
                    "project_ref": "group/repo",
                    "title": "Parked MR 42",
                    "author": "alice",
                    "url": "https://gitlab.example.com/group/repo/-/merge_requests/42",
                    "ci_status": "success",
                    "status": "pending",
                    "enqueued_at": "2026-09-01T00:00:00Z",
                    "raw": {"todo_id": 420, "action": "review_requested", "project_id": 100},
                },
                {
                    "platform": "gitlab",
                    "item_kind": "mr",
                    "item_id": 99,
                    "project_ref": "group/repo",
                    "title": "Queued MR 99",
                    "author": "bob",
                    "url": "https://gitlab.example.com/group/repo/-/merge_requests/99",
                    "ci_status": "failed",
                    "status": "queued",
                    "queue_position": 1,
                    "enqueued_at": "2026-09-01T00:02:00Z",
                    "raw": {"todo_id": 421, "action": "assigned", "project_id": 100},
                },
            ],
        )
        gh_snap = _make_snapshot(
            "github",
            items=[
                {
                    "platform": "github",
                    "item_kind": "pr",
                    "item_id": 77,
                    "project_ref": "The-Darwin-Project/BlackBoard",
                    "title": "Queued PR 77",
                    "author": "octocat",
                    "url": "https://github.com/The-Darwin-Project/BlackBoard/pull/77",
                    "ci_status": "success",
                    "status": "queued",
                    "queue_position": 1,
                    "enqueued_at": "2026-09-01T00:01:00Z",
                }
            ],
        )

        from src.models import EventDocument, EventEvidence, EventInput, EventStatus

        parked_gl = EventDocument(
            id="evt-gl-wait42",
            source="headhunter",
            service="repo",
            status=EventStatus.WAITING_APPROVAL,
            event=EventInput(
                reason="parked",
                evidence=EventEvidence(
                    display_text="GitLab MR !42",
                    source_type="headhunter",
                    domain="complicated",
                    severity="info",
                    gitlab_context={
                        "todo_id": 420,
                        "project_id": 100,
                        "project_path": "group/repo",
                        "mr_iid": 42,
                        "mr_title": "Parked MR 42",
                        "author": "alice",
                        "pipeline_status": "success",
                        "target_url": "https://gitlab.example.com/group/repo/-/merge_requests/42",
                        "created_at": "2026-09-01T00:00:00Z",
                    },
                ),
            ),
        )
        active_issue = _make_headhunter_event(
            "evt-gh-issue233",
            github_issue_context={
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "issue_number": 233,
                "title": "Active issue",
                "author": "octocat",
                "html_url": "https://github.com/The-Darwin-Project/BlackBoard/issues/233",
                "created_at": "2026-09-01T00:03:00Z",
            },
        )

        events_by_id = {"evt-gl-wait42": parked_gl, "evt-gh-issue233": active_issue}
        mock_bb = AsyncMock()
        mock_bb.get_headhunter_snapshot = AsyncMock(
            side_effect=lambda p: {"gitlab": gl_snap, "github": gh_snap}.get(p)
        )
        mock_bb.get_active_events_with_status = AsyncMock(return_value={"evt-gh-issue233": "active"})
        mock_bb.get_waiting_approval_events = AsyncMock(return_value=["evt-gl-wait42"])
        mock_bb.get_event = AsyncMock(side_effect=lambda eid: events_by_id.get(eid))

        driver = HeadhunterQueueProtocolDriver(mock_bb)
        resp = await driver.request("GET", "/queue/headhunter/pending")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

        mr42_rows = [r for r in data if r.get("platform") == "gitlab" and r.get("mr_iid") == 42]
        assert len(mr42_rows) == 1, f"Parked GitLab MR !42 duplicated or missing: {mr42_rows}"
        assert (mr42_rows[0].get("status") == "waiting_approval") or (
            mr42_rows[0].get("action") == "waiting_approval"
        )

        mr99_rows = [r for r in data if r.get("platform") == "gitlab" and r.get("mr_iid") == 99]
        assert len(mr99_rows) == 1
        assert mr99_rows[0]["queue_position"] == 1
        assert mr99_rows[0]["pipeline_status"] == "failed"

        pr77_rows = [r for r in data if r.get("platform") == "github" and r.get("pr_number") == 77]
        assert len(pr77_rows) == 1
        assert pr77_rows[0]["check_status"] == "success"
        assert pr77_rows[0]["queue_position"] == 1
        assert pr77_rows[0]["status"] == "queued"

        assert any(r.get("issue_number") == 233 for r in data)

    @pytest.mark.asyncio
    async def test_t13b_cold_start_expired_snapshot_returns_active_and_waiting_and_null_last_poll_at(self):
        """Given expired/missing Redis snapshots (get_headhunter_snapshot returns None)
        When GET /queue/headhunter/pending and GET /queue/headhunter/status are called
        Then /pending returns active + waiting_approval Blackboard events and /status reports last_poll_at: null."""
        from src.models import EventDocument, EventEvidence, EventInput, EventStatus

        waiting_pr = EventDocument(
            id="evt-wait-pr",
            source="headhunter",
            service="BlackBoard",
            status=EventStatus.WAITING_APPROVAL,
            event=EventInput(
                reason="wait",
                evidence=EventEvidence(
                    display_text="PR 88",
                    source_type="headhunter",
                    domain="complicated",
                    severity="info",
                    github_context={
                        "owner": "The-Darwin-Project",
                        "repo": "BlackBoard",
                        "pr_number": 88,
                        "pr_title": "Waiting PR",
                        "author": "octocat",
                        "pr_url": "https://github.com/The-Darwin-Project/BlackBoard/pull/88",
                        "created_at": "2026-09-01T00:00:00Z",
                    },
                ),
            ),
        )
        active_pr = _make_headhunter_event(
            "evt-act-pr",
            github_context={
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "pr_number": 89,
                "pr_title": "Active PR",
                "author": "octocat",
                "pr_url": "https://github.com/The-Darwin-Project/BlackBoard/pull/89",
                "created_at": "2026-09-01T00:01:00Z",
            },
        )
        events = {"evt-wait-pr": waiting_pr, "evt-act-pr": active_pr}
        mock_bb = AsyncMock()
        mock_bb.get_headhunter_snapshot = AsyncMock(return_value=None)
        mock_bb.get_active_events_with_status = AsyncMock(return_value={"evt-act-pr": "active"})
        mock_bb.get_waiting_approval_events = AsyncMock(return_value=["evt-wait-pr"])
        mock_bb.get_event = AsyncMock(side_effect=lambda eid: events.get(eid))

        driver = HeadhunterQueueProtocolDriver(mock_bb)
        pending_resp = await driver.request("GET", "/queue/headhunter/pending")
        assert pending_resp.status_code == 200
        pending = pending_resp.json()
        assert {r.get("pr_number") for r in pending} == {88, 89}

        status_resp = await driver.request("GET", "/queue/headhunter/status")
        assert status_resp.status_code == 200
        status_body = status_resp.json()
        assert status_body["platforms"]["gitlab"]["last_poll_at"] is None
        assert status_body["platforms"]["github"]["last_poll_at"] is None

    @pytest.mark.asyncio
    async def test_t13c_status_redacts_secrets_and_caps_error_strings(self):
        """Given snapshots with token/PEM secrets and >200-char errors
        When GET /queue/headhunter/status is called
        Then secrets are redacted via redact_pii and errors are capped <= 200 chars."""
        long_gl_err = "HTTP 500 PRIVATE-TOKEN: glpat-secret1234567890abcd " + ("x" * 300)
        long_gh_err = "Bearer ghp_secretToken9876543210xyz -----BEGIN RSA PRIVATE KEY----- MIIB " + ("y" * 300)
        gl_snap = _make_snapshot(
            "gitlab",
            enabled=True,
            partial_error=long_gl_err,
            breaker_state="open",
            consecutive_failures=3,
            next_retry_at=1_700_000_300.0,
            last_error=long_gl_err,
        )
        gh_snap = _make_snapshot(
            "github",
            enabled=True,
            partial_error=long_gh_err,
            breaker_state="half_open",
            consecutive_failures=3,
            next_retry_at=1_700_000_900.0,
            last_error=long_gh_err,
        )
        mock_bb = AsyncMock()
        mock_bb.get_headhunter_snapshot = AsyncMock(
            side_effect=lambda p: {"gitlab": gl_snap, "github": gh_snap}.get(p)
        )

        driver = HeadhunterQueueProtocolDriver(mock_bb)
        resp = await driver.request("GET", "/queue/headhunter/status")
        assert resp.status_code == 200
        raw_text = resp.text
        assert "glpat-secret1234567890abcd" not in raw_text
        assert "ghp_secretToken9876543210xyz" not in raw_text
        assert "BEGIN RSA PRIVATE KEY" not in raw_text

        body = resp.json()
        for plat in ("gitlab", "github"):
            pdata = body["platforms"][plat]
            for key in ("enabled", "pending_count", "queued_count", "last_poll_at", "partial_error", "breaker"):
                assert key in pdata
            assert len(pdata["partial_error"] or "") <= 200
            brk = pdata["breaker"]
            for bkey in ("state", "consecutive_failures", "next_retry_at", "last_error"):
                assert bkey in brk
            assert len(brk["last_error"] or "") <= 200

    @pytest.mark.asyncio
    async def test_t13d_queue_active_includes_approval_requested_sha(self):
        """Given active events with and without approval_requested_sha
        When GET /queue/active is called
        Then each row includes approval_requested_sha (SHA string or None)."""
        evt_sha = _make_event_document("evt-sha-01")
        evt_sha.approval_requested_sha = "deadbeef1234567890abcdef1234567890abcdef"
        evt_none = _make_event_document("evt-sha-02")

        mock_bb = AsyncMock()
        mock_bb.get_active_events = AsyncMock(return_value=["evt-sha-01", "evt-sha-02"])
        mock_bb.get_event = AsyncMock(
            side_effect=lambda eid: {"evt-sha-01": evt_sha, "evt-sha-02": evt_none}.get(eid)
        )

        driver = HeadhunterQueueProtocolDriver(mock_bb)
        resp = await driver.request("GET", "/queue/active")
        assert resp.status_code == 200
        by_id = {row["id"]: row for row in resp.json()}
        assert by_id["evt-sha-01"]["approval_requested_sha"] == "deadbeef1234567890abcdef1234567890abcdef"
        assert "approval_requested_sha" in by_id["evt-sha-02"]
        assert by_id["evt-sha-02"]["approval_requested_sha"] is None

    @pytest.mark.asyncio
    async def test_t13e_waiting_approval_includes_approval_requested_sha_and_pending_filters_closed_events(self):
        """Given waiting_approval events with/without approval_requested_sha and a CLOSED headhunter event
        When GET /queue/waiting_approval and GET /queue/headhunter/pending are called
        Then /waiting_approval exposes approval_requested_sha and /pending excludes CLOSED events."""
        from src.models import EventStatus

        evt_wait = _make_headhunter_event(
            "evt-wait-sha-1",
            github_context={
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "pr_number": 501,
                "pr_title": "Waiting PR",
                "author": "octocat",
                "pr_url": "https://github.com/The-Darwin-Project/BlackBoard/pull/501",
            },
        )
        evt_wait.status = EventStatus.WAITING_APPROVAL
        evt_wait.approval_requested_sha = "cafebabe1234567890abcdef1234567890abcdef"

        evt_wait_none = _make_event_document("evt-wait-sha-2")
        evt_wait_none.status = EventStatus.WAITING_APPROVAL

        evt_closed = _make_headhunter_event(
            "evt-closed-hh",
            github_context={
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "pr_number": 502,
                "pr_title": "Closed PR",
                "author": "octocat",
                "pr_url": "https://github.com/The-Darwin-Project/BlackBoard/pull/502",
            },
        )
        evt_closed.status = EventStatus.CLOSED

        by_id_map = {
            "evt-wait-sha-1": evt_wait,
            "evt-wait-sha-2": evt_wait_none,
            "evt-closed-hh": evt_closed,
        }
        mock_bb = AsyncMock()
        mock_bb.get_headhunter_snapshot = AsyncMock(return_value=None)
        mock_bb.get_waiting_approval_events = AsyncMock(return_value=["evt-wait-sha-1", "evt-wait-sha-2"])
        mock_bb.get_active_events_with_status = AsyncMock(return_value={"evt-closed-hh": "active"})
        mock_bb.get_event = AsyncMock(side_effect=lambda eid: by_id_map.get(eid))

        driver = HeadhunterQueueProtocolDriver(mock_bb)
        wait_resp = await driver.request("GET", "/queue/waiting_approval")
        assert wait_resp.status_code == 200
        wait_by_id = {row["id"]: row for row in wait_resp.json()}
        assert wait_by_id["evt-wait-sha-1"]["approval_requested_sha"] == "cafebabe1234567890abcdef1234567890abcdef"
        assert "approval_requested_sha" in wait_by_id["evt-wait-sha-2"]
        assert wait_by_id["evt-wait-sha-2"]["approval_requested_sha"] is None

        pend_resp = await driver.request("GET", "/queue/headhunter/pending")
        assert pend_resp.status_code == 200
        pr_nums = {r.get("pr_number") for r in pend_resp.json()}
        assert 501 in pr_nums
        assert 502 not in pr_nums


# =========================================================================
# Slice 2C ATDD (Step 8 / T-14): Operator Controls & Dynamic Case-Insensitive RBAC
# =========================================================================


def _make_fake_headhunter(mock_bb=None):
    """Construct a real Headhunter instance with mocked VCS network/LLM calls so tests
    exercise real trigger_poll, reset_breaker, operate_item, _with_poll_lock,
    _persist_platform_snapshot, and request_promote boundaries."""
    from src.agents.headhunter import Headhunter

    bb = mock_bb if mock_bb is not None else AsyncMock()
    hh = Headhunter(bb, gitlab_enabled=False)
    hh.analyze_and_plan = AsyncMock(side_effect=AssertionError("analyze_and_plan forbidden on HTTP route"))
    hh._gitlab.dismiss_todo = AsyncMock(return_value=True)
    hh._gitlab.mark_todo_done = AsyncMock(return_value=True)
    hh._gitlab._dismiss_todos_best_effort = AsyncMock(return_value=None)
    hh._github._manager = MagicMock()
    hh._github._manager.get_installation_for_repo = MagicMock(return_value="12345")
    hh._github._add_labels = AsyncMock(return_value=True)
    hh._github._remove_label = AsyncMock(return_value=True)
    hh.request_promote = MagicMock(wraps=hh.request_promote)
    return hh


class TestATDDT14OperatorControlsAndRBAC:
    """Layer 1-4 ATDD scenarios for T-14 (operator controls + RBAC + non-blocking lock)."""

    @pytest.fixture(autouse=True)
    def _advance_clock_between_tests(self, monkeypatch):
        import time as _time

        orig_monotonic = _time.monotonic
        orig_time = _time.time
        if not hasattr(self, "_clock_offset"):
            type(self)._clock_offset = [0.0]
        type(self)._clock_offset[0] += 15.0
        offset = type(self)._clock_offset
        monkeypatch.setattr(_time, "monotonic", lambda: orig_monotonic() + offset[0])
        monkeypatch.setattr(_time, "time", lambda: orig_time() + offset[0])
        self._bump_clock = lambda secs=15.0: offset.__setitem__(0, offset[0] + secs)

    @pytest.mark.asyncio
    async def test_t14a_operator_endpoints_permitted_when_auth_disabled(self, monkeypatch):
        """Given DEX_ENABLED=false and TRUSTED_PROXY_ENABLED=false
        When operator POSTs to /queue/headhunter/poll
        Then dev/local mode permits the call (not 401/403)."""
        monkeypatch.setattr("src.auth.DEX_ENABLED", False)
        monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)

        hh = _make_fake_headhunter()
        mock_bb = AsyncMock()
        driver = HeadhunterQueueProtocolDriver(mock_bb, mock_hh=hh)
        resp = await driver.request("POST", "/queue/headhunter/poll")
        assert resp.status_code in (200, 202)
        assert hh._poll_wake_signal.is_set()

    @pytest.mark.asyncio
    async def test_t14b_operator_rbac_enforces_401_403_mixed_case_and_audit_logs(self, monkeypatch, caplog):
        """Given DEX_ENABLED=true
        When unauthenticated, unauthorized, empty-union, and mixed-case OBS_ADMIN_GROUPS/APPROVER_GROUPS callers hit operator controls
        Then 401/403 fail closed, mixed-case groups match case-insensitively, and BOTH allowed/denied are audit-logged."""
        monkeypatch.setattr("src.auth.DEX_ENABLED", True)
        monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)

        hh = _make_fake_headhunter()
        mock_bb = AsyncMock()
        driver = HeadhunterQueueProtocolDriver(mock_bb, mock_hh=hh)

        with caplog.at_level("INFO"):
            # 1. Unauthenticated -> 401
            r401 = await driver.request("POST", "/queue/headhunter/poll")
            assert r401.status_code == 401

            # 2. Empty union -> 403 fail-closed
            monkeypatch.setattr("src.auth.OBS_ADMIN_GROUPS", frozenset())
            monkeypatch.setattr("src.auth.APPROVER_GROUPS", frozenset())
            monkeypatch.setattr(
                "src.auth._validate_jwt",
                lambda _t: {"sub": "u1", "email": "alice@example.com", "name": "Alice", "groups": ["admins"]},
            )
            r403_empty = await driver.request(
                "POST", "/queue/headhunter/poll", headers={"Authorization": "Bearer jwt-1"}
            )
            assert r403_empty.status_code == 403

            # 3. Non-matching group -> 403
            monkeypatch.setattr("src.auth.OBS_ADMIN_GROUPS", frozenset({"Darwin-Admins"}))
            monkeypatch.setattr("src.auth.APPROVER_GROUPS", frozenset({"Maintainers"}))
            monkeypatch.setattr(
                "src.auth._validate_jwt",
                lambda _t: {"sub": "u2", "email": "bob@example.com", "name": "Bob", "groups": ["viewers"]},
            )
            r403_role = await driver.request(
                "POST", "/queue/headhunter/poll", headers={"Authorization": "Bearer jwt-2"}
            )
            assert r403_role.status_code == 403

            # 4. Mixed-case match on OBS_ADMIN_GROUPS -> allowed
            self._bump_clock(15.0)
            monkeypatch.setattr(
                "src.auth._validate_jwt",
                lambda _t: {"sub": "u3", "email": "admin@example.com", "name": "Admin", "groups": ["darwin-admins"]},
            )
            r_admin = await driver.request(
                "POST", "/queue/headhunter/poll", headers={"Authorization": "Bearer jwt-3"}
            )
            assert r_admin.status_code in (200, 202)

            # 5. Mixed-case match on APPROVER_GROUPS -> allowed
            self._bump_clock(15.0)
            monkeypatch.setattr(
                "src.auth._validate_jwt",
                lambda _t: {"sub": "u4", "email": "approver@example.com", "name": "Appr", "groups": ["MAINTAINERS"]},
            )
            r_appr = await driver.request(
                "POST", "/queue/headhunter/poll", headers={"Authorization": "Bearer jwt-4"}
            )
            assert r_appr.status_code in (200, 202)

        logs_joined = "\n".join(rec.getMessage() for rec in caplog.records)
        assert "bob@example.com" in logs_joined
        assert "admin@example.com" in logs_joined
        assert "approver@example.com" in logs_joined

    @pytest.mark.asyncio
    async def test_t14c_poll_busy_lock_409_wake_and_10s_debounce(self, monkeypatch):
        """Given Headhunter with _poll_lock and _poll_wake_signal
        When _poll_lock is busy -> 409 Retry-After: 5;
        When unlocked -> initial POST sets _poll_wake_signal;
        When repeated within 10s -> debounced without re-setting _poll_wake_signal."""
        monkeypatch.setattr("src.auth.DEX_ENABLED", False)
        monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)

        hh = _make_fake_headhunter()
        mock_bb = AsyncMock()
        driver = HeadhunterQueueProtocolDriver(mock_bb, mock_hh=hh)

        # 1. Busy _poll_lock -> 409 Conflict with Retry-After: 5 (short-circuit wait_for so test is instant)
        await hh._poll_lock.acquire()
        orig_wait_for = asyncio.wait_for

        async def _fast_wait_for(aw, timeout=None):
            return await orig_wait_for(aw, timeout=0.01)

        try:
            with patch("src.routes.queue.asyncio.wait_for", side_effect=_fast_wait_for):
                r_busy = await driver.request("POST", "/queue/headhunter/poll")
        finally:
            hh._poll_lock.release()
        assert r_busy.status_code == 409
        assert r_busy.headers.get("Retry-After") == "5"
        assert not hh._poll_wake_signal.is_set()

        # 2. Initial unblocked poll -> wakes signal
        r_ok = await driver.request("POST", "/queue/headhunter/poll")
        assert r_ok.status_code in (200, 202)
        assert hh._poll_wake_signal.is_set()

        # 3. Immediate repeat within 10s -> debounced (wake signal stays clear)
        hh._poll_wake_signal.clear()
        r_debounced = await driver.request("POST", "/queue/headhunter/poll")
        assert r_debounced.status_code in (200, 202, 409, 429)
        if r_debounced.status_code in (200, 202):
            body = r_debounced.json()
            assert body.get("debounced") is True or body.get("triggered") is False
        assert not hh._poll_wake_signal.is_set()

    @pytest.mark.asyncio
    async def test_t14d_breaker_reset_validates_platform_resets_wakes_and_per_platform_cooldown(self, monkeypatch):
        """Given open GitLab and GitHub breakers
        When POST /queue/headhunter/breaker/{platform}/reset is called
        Then invalid platform -> 422, valid resets to closed + wakes poll, and repeat hits per-platform 10s cooldown."""
        monkeypatch.setattr("src.auth.DEX_ENABLED", False)
        monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)

        hh = _make_fake_headhunter()
        hh._breakers["gitlab"].state = "open"
        hh._breakers["gitlab"].consecutive_failures = 3
        hh._breakers["github"].state = "open"
        hh._breakers["github"].consecutive_failures = 3

        mock_bb = AsyncMock()
        driver = HeadhunterQueueProtocolDriver(mock_bb, mock_hh=hh)

        r_bad = await driver.request("POST", "/queue/headhunter/breaker/bitbucket/reset")
        assert r_bad.status_code == 422

        r_gl = await driver.request("POST", "/queue/headhunter/breaker/gitlab/reset")
        assert r_gl.status_code in (200, 202)
        assert hh._breakers["gitlab"].state == "closed"
        assert hh._breakers["gitlab"].consecutive_failures == 0
        assert hh._poll_wake_signal.is_set()

        # Immediate repeat for gitlab -> debounced; github remains unaffected and succeeds
        hh._poll_wake_signal.clear()
        r_gl_rep = await driver.request("POST", "/queue/headhunter/breaker/gitlab/reset")
        assert r_gl_rep.status_code in (200, 202, 409, 429)
        assert not hh._poll_wake_signal.is_set()

        r_gh = await driver.request("POST", "/queue/headhunter/breaker/github/reset")
        assert r_gh.status_code in (200, 202)
        assert hh._breakers["github"].state == "closed"
        assert hh._poll_wake_signal.is_set()

    @pytest.mark.asyncio
    async def test_t14e_items_action_rejects_ssrf_url_fields_non_queued_and_busy_lock(self, monkeypatch):
        """Given POST /queue/headhunter/items/{action}
        When dot-segments / SSRF characters, non-queued PR on installed repo, or busy _poll_lock are sent
        Then 422, 404/409 membership rejection, zero arbitrary URL fields, and 409 Retry-After: 5 are enforced."""
        monkeypatch.setattr("src.auth.DEX_ENABLED", False)
        monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)

        hh = _make_fake_headhunter()
        gh_snap = _make_snapshot(
            "github",
            items=[
                {
                    "platform": "github",
                    "item_kind": "pr",
                    "item_id": 77,
                    "project_ref": "The-Darwin-Project/BlackBoard",
                    "status": "queued",
                    "queue_position": 1,
                }
            ],
        )
        mock_bb = AsyncMock()
        mock_bb.get_headhunter_snapshot = AsyncMock(
            side_effect=lambda p: gh_snap if p == "github" else None
        )
        driver = HeadhunterQueueProtocolDriver(mock_bb, mock_hh=hh)

        # 1. SSRF / dot-segment / disallowed char inputs -> 422
        bad_payloads = [
            {"platform": "github", "owner": "..", "repo": "BlackBoard", "item_number": 77},
            {"platform": "github", "owner": ".", "repo": "BlackBoard", "item_number": 77},
            {"platform": "github", "owner": "org", "repo": "repo?x=1", "item_number": 77},
            {"platform": "github", "owner": "org", "repo": "repo#frag", "item_number": 77},
            {"platform": "github", "owner": "org@evil", "repo": "repo", "item_number": 77},
            {"platform": "github", "owner": "org", "repo": "bad repo", "item_number": 77},
            {"platform": "gitlab", "project_id": "../secret", "item_number": 42},
        ]
        for payload in bad_payloads:
            r_bad = await driver.request("POST", "/queue/headhunter/items/promote", json_body=payload)
            assert r_bad.status_code == 422, f"Expected 422 for {payload}, got {r_bad.status_code}"

        # 2. Arbitrary URL fields absent from request schema (and rejected if extra=forbid)
        from src.routes import queue as queue_routes

        req_models = [
            obj for obj in vars(queue_routes).values()
            if isinstance(obj, type) and hasattr(obj, "model_fields") and "item_number" in obj.model_fields
        ]
        assert req_models, "Expected Pydantic request model for /queue/headhunter/items/{action}"
        for m in req_models:
            assert not ({"url", "target_url", "html_url", "api_url"} & set(m.model_fields.keys()))

        # 3. Non-queued PR on an installed repo -> 404 or 409 (exact queue/pending membership)
        r_non_q = await driver.request(
            "POST",
            "/queue/headhunter/items/promote",
            json_body={
                "platform": "github",
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "item_number": 999,
            },
        )
        assert r_non_q.status_code in (404, 409)

        # 4. Busy _poll_lock -> 409 Conflict with Retry-After: 5
        await hh._poll_lock.acquire()
        orig_wait_for = asyncio.wait_for

        async def _fast_wait_for(aw, timeout=None):
            return await orig_wait_for(aw, timeout=0.01)

        try:
            with patch("src.routes.queue.asyncio.wait_for", side_effect=_fast_wait_for):
                r_busy = await driver.request(
                    "POST",
                    "/queue/headhunter/items/promote",
                    json_body={
                        "platform": "github",
                        "owner": "The-Darwin-Project",
                        "repo": "BlackBoard",
                        "item_number": 77,
                    },
                )
        finally:
            hh._poll_lock.release()
        assert r_busy.status_code == 409
        assert r_busy.headers.get("Retry-After") == "5"

    @pytest.mark.asyncio
    async def test_t14f_promote_202_async_no_llm_and_dismiss_requeue_platform_mutations(self, monkeypatch):
        """Given queued GitLab MR, GitHub PR, and GitHub Issue in snapshots
        When promote, dismiss, and requeue are called
        Then promote returns 202 async without analyze_and_plan, and dismiss/requeue execute exact
        ordered mutations across all 7 platform/item branches."""
        monkeypatch.setattr("src.auth.DEX_ENABLED", False)
        monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)

        gl_snap = _make_snapshot(
            "gitlab",
            items=[
                {
                    "platform": "gitlab",
                    "item_kind": "mr",
                    "item_id": 42,
                    "project_ref": "group/repo",
                    "status": "queued",
                    "queue_position": 1,
                    "raw": {"todo_id": 420, "_sibling_todo_ids": [420, 425], "project_id": 100},
                }
            ],
        )
        gh_snap = _make_snapshot(
            "github",
            items=[
                {
                    "platform": "github",
                    "item_kind": "pr",
                    "item_id": 77,
                    "project_ref": "The-Darwin-Project/BlackBoard",
                    "status": "queued",
                    "queue_position": 1,
                    "raw": {"installation_id": "12345"},
                },
                {
                    "platform": "github",
                    "item_kind": "issue",
                    "item_id": 88,
                    "project_ref": "The-Darwin-Project/BlackBoard",
                    "status": "queued",
                    "queue_position": 1,
                    "raw": {"installation_id": "12345"},
                },
            ],
        )

        gl_dismiss_order: list[str] = []
        gh_requeue_order: list[tuple[str, object]] = []

        mock_bb = AsyncMock()
        mock_bb.get_headhunter_snapshot = AsyncMock(
            side_effect=lambda p: {"gitlab": gl_snap, "github": gh_snap}.get(p)
        )
        mock_bb.get_gitlab_queue_entry = AsyncMock(return_value={"project_id": 100, "mr_iid": 42})

        async def _remove_gl_queue(pid, iid):
            gl_dismiss_order.append(f"remove_gitlab_queue:{pid}:{iid}")
            return True

        mock_bb.remove_gitlab_queue = AsyncMock(side_effect=_remove_gl_queue)
        mock_bb.enqueue_gitlab_mr = AsyncMock(return_value=True)
        mock_bb.promote_gitlab_queue = AsyncMock(return_value=True)
        mock_bb.delete_gitlab_mr_sha = AsyncMock(return_value=True)
        mock_bb.delete_github_pr_sha = AsyncMock(return_value=True)
        mock_bb.clear_github_issue_processed = AsyncMock(return_value=True)

        hh = _make_fake_headhunter(mock_bb)

        async def _dismiss_todo(tids):
            gl_dismiss_order.append(f"dismiss_todo:{tids}")
            return True

        hh._gitlab.dismiss_todo = AsyncMock(side_effect=_dismiss_todo)

        async def _gh_add_labels(inst_id, owner, repo, num, labels):
            gh_requeue_order.append(("add_labels", list(labels)))
            return True

        async def _gh_remove_label(inst_id, owner, repo, num, label):
            gh_requeue_order.append(("remove_label", label))
            return True

        hh._github._add_labels = AsyncMock(side_effect=_gh_add_labels)
        hh._github._remove_label = AsyncMock(side_effect=_gh_remove_label)

        driver = HeadhunterQueueProtocolDriver(mock_bb, mock_hh=hh)

        # 1a. promote GitLab MR -> 202 async, promote_gitlab_queue + request_promote + wake
        self._bump_clock(15.0)
        r_gl_prom = await driver.request(
            "POST",
            "/queue/headhunter/items/promote",
            json_body={"platform": "gitlab", "project_id": 100, "item_number": 42},
        )
        assert r_gl_prom.status_code == 202
        mock_bb.promote_gitlab_queue.assert_awaited_once_with(100, 42)
        hh.request_promote.assert_called_with("gitlab", project_id=100, item_number=42)
        assert ("gitlab", "mr", 100, 42) in hh._promoted_keys
        hh.analyze_and_plan.assert_not_awaited()
        assert hh._poll_wake_signal.is_set()

        # 1b. promote GitHub PR -> 202 async, NEVER calls analyze_and_plan, wakes poll
        self._bump_clock(15.0)
        hh._poll_wake_signal.clear()
        hh.request_promote.reset_mock()
        r_prom = await driver.request(
            "POST",
            "/queue/headhunter/items/promote",
            json_body={
                "platform": "github",
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "item_number": 77,
                "is_issue": False,
            },
        )
        assert r_prom.status_code == 202
        hh.request_promote.assert_called_once_with(
            "github", owner="The-Darwin-Project", repo="BlackBoard", item_number=77, is_issue=False
        )
        assert ("github", "pr", "the-darwin-project/blackboard", 77) in hh._promoted_keys
        hh.analyze_and_plan.assert_not_awaited()
        assert hh._poll_wake_signal.is_set()

        # 2. dismiss GitLab MR -> dismiss_todo BEFORE remove_gitlab_queue (covers _sibling_todo_ids)
        self._bump_clock(15.0)
        r_gl_dis = await driver.request(
            "POST",
            "/queue/headhunter/items/dismiss",
            json_body={"platform": "gitlab", "project_id": 100, "item_number": 42},
        )
        assert r_gl_dis.status_code in (200, 202)
        assert gl_dismiss_order == [
            "dismiss_todo:[420, 425]",
            "remove_gitlab_queue:100:42",
        ]

        # 3. dismiss GitHub PR -> removes darwin-queued and darwin-review without touching darwin-active
        self._bump_clock(15.0)
        hh._github._remove_label.reset_mock()
        r_gh_dis = await driver.request(
            "POST",
            "/queue/headhunter/items/dismiss",
            json_body={
                "platform": "github",
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "item_number": 77,
                "is_issue": False,
            },
        )
        assert r_gh_dis.status_code in (200, 202)
        removed_pr_labels = [c.args[-1] for c in hh._github._remove_label.await_args_list]
        assert removed_pr_labels == ["darwin-queued", "darwin-review"]
        assert "darwin-active" not in removed_pr_labels

        # 4. dismiss GitHub Issue -> removes darwin-queued and darwin-work
        self._bump_clock(15.0)
        hh._github._remove_label.reset_mock()
        r_ghi_dis = await driver.request(
            "POST",
            "/queue/headhunter/items/dismiss",
            json_body={
                "platform": "github",
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "item_number": 88,
                "is_issue": True,
            },
        )
        assert r_ghi_dis.status_code in (200, 202)
        removed_issue_labels = [c.args[-1] for c in hh._github._remove_label.await_args_list]
        assert removed_issue_labels == ["darwin-queued", "darwin-work"]

        # 5. requeue GitLab MR -> enqueue_gitlab_mr + delete_gitlab_mr_sha + wakes poll
        self._bump_clock(15.0)
        hh._poll_wake_signal.clear()
        r_gl_req = await driver.request(
            "POST",
            "/queue/headhunter/items/requeue",
            json_body={"platform": "gitlab", "project_id": 100, "item_number": 42},
        )
        assert r_gl_req.status_code in (200, 202)
        mock_bb.enqueue_gitlab_mr.assert_awaited_once()
        enq_args = mock_bb.enqueue_gitlab_mr.await_args.args
        assert enq_args[0] == 100 and enq_args[1] == 42 and isinstance(enq_args[2], dict)
        mock_bb.delete_gitlab_mr_sha.assert_awaited_once_with(100, 42)
        assert hh._poll_wake_signal.is_set()

        # 6. requeue GitHub PR -> add darwin-queued BEFORE remove darwin-done & darwin-review + delete_github_pr_sha
        self._bump_clock(15.0)
        hh._poll_wake_signal.clear()
        gh_requeue_order.clear()
        r_gh_req = await driver.request(
            "POST",
            "/queue/headhunter/items/requeue",
            json_body={
                "platform": "github",
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "item_number": 77,
                "is_issue": False,
            },
        )
        assert r_gh_req.status_code in (200, 202)
        assert gh_requeue_order == [
            ("add_labels", ["darwin-queued"]),
            ("remove_label", "darwin-done"),
            ("remove_label", "darwin-review"),
        ]
        mock_bb.delete_github_pr_sha.assert_awaited_once_with("The-Darwin-Project", "BlackBoard", 77)
        assert hh._poll_wake_signal.is_set()

        # 7. requeue GitHub Issue -> _add_labels([work, queued]) + clear_github_issue_processed + wakes poll
        self._bump_clock(15.0)
        hh._poll_wake_signal.clear()
        gh_requeue_order.clear()
        r_ghi_req = await driver.request(
            "POST",
            "/queue/headhunter/items/requeue",
            json_body={
                "platform": "github",
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "item_number": 88,
                "is_issue": True,
            },
        )
        assert r_ghi_req.status_code in (200, 202)
        assert ("add_labels", ["darwin-work", "darwin-queued"]) in gh_requeue_order
        mock_bb.clear_github_issue_processed.assert_awaited_once_with("The-Darwin-Project", "BlackBoard", 88)
        assert hh._poll_wake_signal.is_set()

    @pytest.mark.asyncio
    async def test_t14g_trusted_proxy_spoofed_email_rejected_401_and_rbac_on_reset_and_items(self, monkeypatch):
        """Given TRUSTED_PROXY_ENABLED=true & DEX_ENABLED=false with spoofed X-Forwarded-Email
        When caller hits /poll, /breaker/{platform}/reset, or /items/{action}
        Then REST fails closed with 401; and under DEX_ENABLED=true 401/403 enforce on reset & items."""
        monkeypatch.setattr("src.auth.DEX_ENABLED", False)
        monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", True)

        mock_bb = AsyncMock()
        hh = _make_fake_headhunter(mock_bb)
        driver = HeadhunterQueueProtocolDriver(mock_bb, mock_hh=hh)

        spoof_headers = {"X-Forwarded-Email": "admin@example.com"}
        for method, path, body in (
            ("POST", "/queue/headhunter/poll", None),
            ("POST", "/queue/headhunter/breaker/gitlab/reset", None),
            ("POST", "/queue/headhunter/items/promote", {"platform": "gitlab", "project_id": 100, "item_number": 42}),
        ):
            r = await driver.request(method, path, json_body=body, headers=spoof_headers)
            assert r.status_code == 401, f"Expected 401 for {path} with spoofed proxy header, got {r.status_code}"

        # DEX_ENABLED=true enforces 401/403 on breaker reset and items/{action}
        monkeypatch.setattr("src.auth.DEX_ENABLED", True)
        monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)
        monkeypatch.setattr("src.auth.OBS_ADMIN_GROUPS", frozenset({"ops-admins"}))
        monkeypatch.setattr("src.auth.APPROVER_GROUPS", frozenset({"maintainers"}))

        assert (await driver.request("POST", "/queue/headhunter/breaker/github/reset")).status_code == 401
        assert (
            await driver.request(
                "POST",
                "/queue/headhunter/items/dismiss",
                json_body={"platform": "gitlab", "project_id": 100, "item_number": 42},
            )
        ).status_code == 401

        monkeypatch.setattr(
            "src.auth._validate_jwt",
            lambda _t: {"sub": "u1", "email": "unpriv@example.com", "name": "U", "groups": ["guest"]},
        )
        assert (
            await driver.request(
                "POST",
                "/queue/headhunter/breaker/github/reset",
                headers={"Authorization": "Bearer jwt-unpriv"},
            )
        ).status_code == 403
        assert (
            await driver.request(
                "POST",
                "/queue/headhunter/items/dismiss",
                json_body={"platform": "gitlab", "project_id": 100, "item_number": 42},
                headers={"Authorization": "Bearer jwt-unpriv"},
            )
        ).status_code == 403

    @pytest.mark.asyncio
    async def test_t14h_items_action_extra_forbid_numeric_pid_closed_404_and_error_mappings(self, monkeypatch):
        """Verify extra='forbid' rejects project_path with 422, numeric string project_id works,
        merged/closed snapshot items 404, RedisError -> 503, upstream label/todo failures -> 502,
        and enqueue_gitlab_mr=False -> 409."""
        from redis.exceptions import RedisError

        monkeypatch.setattr("src.auth.DEX_ENABLED", False)
        monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)

        gl_snap = _make_snapshot(
            "gitlab",
            items=[
                {
                    "platform": "gitlab",
                    "item_kind": "mr",
                    "item_id": 42,
                    "project_ref": "group/repo",
                    "status": "pending",
                    "raw": {"todo_id": 420, "project_id": 100},
                },
                {
                    "platform": "gitlab",
                    "item_kind": "mr",
                    "item_id": 43,
                    "project_ref": "group/repo",
                    "status": "merged",
                    "raw": {"todo_id": 421, "project_id": 100, "mr_state": "merged"},
                },
            ],
        )
        gh_snap = _make_snapshot(
            "github",
            items=[
                {
                    "platform": "github",
                    "item_kind": "pr",
                    "item_id": 77,
                    "project_ref": "The-Darwin-Project/BlackBoard",
                    "status": "queued",
                    "queue_position": 1,
                },
            ],
        )
        mock_bb = AsyncMock()
        mock_bb.get_headhunter_snapshot = AsyncMock(
            side_effect=lambda p: {"gitlab": gl_snap, "github": gh_snap}.get(p)
        )
        mock_bb.promote_gitlab_queue = AsyncMock(return_value=True)
        mock_bb.enqueue_gitlab_mr = AsyncMock(return_value=False)

        hh = _make_fake_headhunter(mock_bb)
        driver = HeadhunterQueueProtocolDriver(mock_bb, mock_hh=hh)

        # 1. extra='forbid' rejects unknown field `project_path` with 422
        r_extra = await driver.request(
            "POST",
            "/queue/headhunter/items/promote",
            json_body={
                "platform": "gitlab",
                "project_id": 100,
                "item_number": 42,
                "project_path": "group/repo",
            },
        )
        assert r_extra.status_code == 422

        # 2. numeric string project_id="100" accepted
        self._bump_clock(15.0)
        r_str_pid = await driver.request(
            "POST",
            "/queue/headhunter/items/promote",
            json_body={"platform": "gitlab", "project_id": "100", "item_number": 42},
        )
        assert r_str_pid.status_code == 202

        # 3. merged/closed snapshot item rejected with 404
        r_merged = await driver.request(
            "POST",
            "/queue/headhunter/items/promote",
            json_body={"platform": "gitlab", "project_id": 100, "item_number": 43},
        )
        assert r_merged.status_code == 404

        # 4. GitLab requeue when enqueue_gitlab_mr returns False (and not already queued) -> 409
        mock_bb.get_gitlab_queue_entry = AsyncMock(return_value=None)
        r_cap = await driver.request(
            "POST",
            "/queue/headhunter/items/requeue",
            json_body={"platform": "gitlab", "project_id": 100, "item_number": 42},
        )
        assert r_cap.status_code == 409

        # 5. GitLab dismiss_todo returns False -> 502
        self._bump_clock(15.0)
        hh._gitlab.dismiss_todo = AsyncMock(return_value=False)
        r_gl_502 = await driver.request(
            "POST",
            "/queue/headhunter/items/dismiss",
            json_body={"platform": "gitlab", "project_id": 100, "item_number": 42},
        )
        assert r_gl_502.status_code == 502

        # 6. GitHub label fail on dismiss -> 502
        self._bump_clock(15.0)
        hh._github._remove_label = AsyncMock(return_value=False)
        r_gh_502 = await driver.request(
            "POST",
            "/queue/headhunter/items/dismiss",
            json_body={
                "platform": "github",
                "owner": "The-Darwin-Project",
                "repo": "BlackBoard",
                "item_number": 77,
            },
        )
        assert r_gh_502.status_code == 502

        # 7. RedisError on snapshot lookup -> 503 (never 404)
        mock_bb.get_headhunter_snapshot = AsyncMock(side_effect=RedisError("redis down"))
        r_503 = await driver.request(
            "POST",
            "/queue/headhunter/items/promote",
            json_body={"platform": "gitlab", "project_id": 100, "item_number": 42},
        )
        assert r_503.status_code == 503

    @pytest.mark.asyncio
    async def test_t14i_immediate_state_consistency_after_breaker_reset_and_item_dismiss(self, monkeypatch):
        """Verify POST /breaker/{platform}/reset immediately shows state=='closed' in GET /status,
        and POST /items/dismiss immediately removes the item from GET /pending."""
        monkeypatch.setattr("src.auth.DEX_ENABLED", False)
        monkeypatch.setattr("src.auth.TRUSTED_PROXY_ENABLED", False)

        from src.agents.headhunter_models import PlatformQueueItem

        persisted_snaps: dict[str, dict] = {}

        mock_bb = AsyncMock()
        mock_bb.get_active_events_with_status = AsyncMock(return_value={})
        mock_bb.get_waiting_approval_events = AsyncMock(return_value=[])
        mock_bb.remove_gitlab_queue = AsyncMock(return_value=True)

        async def _save_snap(plat, payload, ttl_seconds=900):
            persisted_snaps[plat] = payload

        async def _get_snap(plat):
            return persisted_snaps.get(plat)

        mock_bb.save_headhunter_snapshot = AsyncMock(side_effect=_save_snap)
        mock_bb.get_headhunter_snapshot = AsyncMock(side_effect=_get_snap)

        hh = _make_fake_headhunter(mock_bb)
        hh._breakers["gitlab"].state = "open"
        hh._breakers["gitlab"].consecutive_failures = 3
        hh._gitlab._last_snapshot_items = [
            PlatformQueueItem(
                platform="gitlab",
                item_kind="mr",
                item_id=42,
                project_ref="group/repo",
                title="Dismissable MR",
                author="alice",
                url="https://gitlab.example.com/group/repo/-/merge_requests/42",
                status="queued",
                queue_position=1,
                enqueued_at="2026-09-01T00:00:00Z",
                raw={"todo_id": 420, "project_id": 100, "action": "assigned"},
            )
        ]
        await hh._persist_platform_snapshot("gitlab")

        driver = HeadhunterQueueProtocolDriver(mock_bb, mock_hh=hh)

        # 1. Breaker reset -> immediate GET /status shows closed
        r_reset = await driver.request("POST", "/queue/headhunter/breaker/gitlab/reset")
        assert r_reset.status_code in (200, 202)
        r_status = await driver.request("GET", "/queue/headhunter/status")
        assert r_status.status_code == 200
        assert r_status.json()["platforms"]["gitlab"]["breaker"]["state"] == "closed"

        # 2. Item dismiss -> immediate GET /pending omits MR 42
        r_pend_before = await driver.request("GET", "/queue/headhunter/pending")
        assert any(row.get("mr_iid") == 42 for row in r_pend_before.json())

        r_dis = await driver.request(
            "POST",
            "/queue/headhunter/items/dismiss",
            json_body={"platform": "gitlab", "project_id": 100, "item_number": 42},
        )
        assert r_dis.status_code in (200, 202)

        r_pend_after = await driver.request("GET", "/queue/headhunter/pending")
        assert r_pend_after.status_code == 200
        assert not any(row.get("mr_iid") == 42 for row in r_pend_after.json())

