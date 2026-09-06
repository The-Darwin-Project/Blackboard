# BlackBoard/tests/test_queue.py
# @ai-rules:
# 1. [Gotcha]: Patch lifespan like test_health.py so app import does not require live Redis.
# 2. [Pattern]: ASGITransport + httpx.AsyncClient for in-process GET tests.
# 3. [Constraint]: Queue headhunter route tests mock GitLab via src.routes.queue.httpx.AsyncClient.
# 4. [Pattern]: Queue active/closed tests mock blackboard.get_active_events + get_event to verify response shape.
# 5. [Pattern]: /headhunter/pending active-GitHub coverage mocks dependencies._blackboard directly
#    (get_active_events_with_status + get_event) since the route calls get_blackboard() itself
#    inside a try/except rather than via Depends() -- GitLab side must still be mocked (empty
#    todos) since the active-event lookup runs after it in the same handler (#233).
# 6. [Pattern]: Per-item get_event() fetch uses asyncio.gather(return_exceptions=True) (#233
#    review, HIGH fix) -- isolation/None-race/no-context/mixed-source/sort tests set
#    get_active_events_with_status() to a multi-id dict and use an AsyncMock side_effect
#    keyed by event_id on get_event() to control each id's outcome independently.
"""Route-level tests for queue API."""
from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from tests.test_headhunter import _make_todo


@pytest.mark.asyncio
async def test_headhunter_pending_filters_merged_and_closed_mrs():
    opened = _make_todo(todo_id=1, mr_iid=1, mr_state="opened", action_name="review_requested")
    merged = _make_todo(todo_id=2, mr_iid=2, mr_state="merged", action_name="review_requested")
    closed = _make_todo(todo_id=3, mr_iid=3, mr_state="closed", action_name="review_requested")
    unknown = _make_todo(todo_id=4, mr_iid=4, action_name="review_requested")
    del unknown["target"]["state"]

    todos = [opened, merged, closed, unknown]

    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = todos

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_auth = MagicMock()
    mock_auth.get_token.return_value = "fake-token"

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        with patch.dict(
            os.environ,
            {"HEADHUNTER_ENABLED": "true", "GITLAB_HOST": "gitlab.example.com"},
            clear=False,
        ):
            with patch("src.utils.gitlab_token.get_gitlab_auth", return_value=mock_auth):
                with patch("httpx.AsyncClient", return_value=mock_client):
                    from src import dependencies
                    from src.main import app

                    original_bb = dependencies._blackboard
                    dependencies._blackboard = MagicMock()
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
    """GET /queue/headhunter/pending with GitLab mocked to return no todos and
    dependencies._blackboard swapped for mock_bb (route calls get_blackboard() itself)."""
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = []

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_auth = MagicMock()
    mock_auth.get_token.return_value = "fake-token"

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        with patch.dict(
            os.environ,
            {"HEADHUNTER_ENABLED": "true", "GITLAB_HOST": "gitlab.example.com"},
            clear=False,
        ):
            with patch("src.utils.gitlab_token.get_gitlab_auth", return_value=mock_auth):
                with patch("httpx.AsyncClient", return_value=mock_client):
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
    assert item["pr_number"] == 233  # issue_number reuses the pr_number field slot
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
    """Final result.sort() interleaves GitLab todos, GitHub queued-cache PRs, and
    Blackboard-active GitHub events chronologically by created_at, not grouped by source
    (#233 review, MEDIUM test-coverage gap #4)."""
    gitlab_todo = _make_todo(todo_id=1, mr_iid=1, mr_state="opened", action_name="review_requested")
    gitlab_todo["created_at"] = "2026-01-01T00:00:00Z"

    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = [gitlab_todo]

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_auth = MagicMock()
    mock_auth.get_token.return_value = "fake-token"

    queued_pr = {
        "number": 99,
        "title": "Queued PR",
        "owner": "The-Darwin-Project",
        "repo": "Blackboard",
        "user": "queued-author",
        "created_at": "2026-01-03T00:00:00Z",
        "html_url": "https://github.com/The-Darwin-Project/Blackboard/pull/99",
    }
    fake_headhunter_agent = SimpleNamespace(_github=SimpleNamespace(queued_prs=[queued_pr]))
    mock_brain = MagicMock()
    mock_brain.agents = {"_headhunter": fake_headhunter_agent}

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
    mock_bb.get_active_events_with_status = AsyncMock(return_value={"evt-sort0001": "active"})
    mock_bb.get_event = AsyncMock(return_value=active_event)

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        with patch.dict(
            os.environ,
            {"HEADHUNTER_ENABLED": "true", "GITLAB_HOST": "gitlab.example.com"},
            clear=False,
        ):
            with patch("src.utils.gitlab_token.get_gitlab_auth", return_value=mock_auth):
                with patch("httpx.AsyncClient", return_value=mock_client):
                    from src import dependencies
                    from src.main import app

                    original_bb = dependencies._blackboard
                    original_brain = dependencies._brain
                    dependencies._blackboard = mock_bb
                    dependencies._brain = mock_brain
                    try:
                        transport = ASGITransport(app=app)
                        async with AsyncClient(transport=transport, base_url="http://test") as client:
                            resp = await client.get("/queue/headhunter/pending")
                    finally:
                        dependencies._blackboard = original_bb
                        dependencies._brain = original_brain

    assert resp.status_code == 200
    data = resp.json()
    assert [item["platform"] for item in data] == ["gitlab", "github", "github"]
    assert [item.get("action") for item in data] == ["review_requested", "active", "queued"]
    assert data[1]["pr_title"] == "Active PR"
    assert data[2]["pr_title"] == "Queued PR"
