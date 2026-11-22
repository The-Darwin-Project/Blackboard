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


# =============================================================================
# Regression tests for issue #230: /headhunter/pending exposes queued GitHub Issues
# =============================================================================


async def _get_pending_with_mocked_github(hh_mock):
    """GET /queue/headhunter/pending with GitLab returning no todos and
    dependencies._brain.agents['_headhunter'] wired to hh_mock, so only the
    GitHub queued-PR/queued-Issue append path is exercised."""
    mock_resp = MagicMock()
    mock_resp.is_success = True
    mock_resp.json.return_value = []

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_resp)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    mock_auth = MagicMock()
    mock_auth.get_token.return_value = "fake-token"

    mock_brain = MagicMock()
    mock_brain.agents = {"_headhunter": hh_mock}

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
                    dependencies._blackboard = MagicMock()
                    dependencies._brain = mock_brain
                    try:
                        transport = ASGITransport(app=app)
                        async with AsyncClient(transport=transport, base_url="http://test") as client:
                            return await client.get("/queue/headhunter/pending")
                    finally:
                        dependencies._blackboard = original_bb
                        dependencies._brain = original_brain


@pytest.mark.asyncio
async def test_headhunter_pending_includes_queued_github_issues():
    """Queued GitHub Issues must appear alongside queued PRs, using
    issue-specific field names (issue_number/issue_title)."""
    hh = MagicMock()
    hh._github.queued_prs = []
    hh._github.queued_issues = [{
        "owner": "o", "repo": "r", "issue_number": 9, "issue_title": "Needs triage",
        "author": "alice", "created_at": "2026-07-01T00:00:00Z",
        "html_url": "https://github.com/o/r/issues/9",
    }]

    resp = await _get_pending_with_mocked_github(hh)

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
    """Queued PRs and queued Issues both surface, are globally sorted by
    created_at (FIFO across platforms), and each keeps its own independent
    1-based queue_position numbering within its own platform list."""
    hh = MagicMock()
    hh._github.queued_prs = [{
        "number": 5, "title": "PR fix", "owner": "o", "repo": "r",
        "user": "bob", "created_at": "2026-07-02T00:00:00Z",
        "html_url": "https://github.com/o/r/pull/5",
    }]
    hh._github.queued_issues = [{
        "owner": "o", "repo": "r", "issue_number": 9, "issue_title": "Issue triage",
        "author": "alice", "created_at": "2026-07-01T00:00:00Z",
        "html_url": "https://github.com/o/r/issues/9",
    }]

    resp = await _get_pending_with_mocked_github(hh)

    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 2
    # Global sort by created_at: the issue (07-01) precedes the PR (07-02)
    assert data[0]["issue_number"] == 9
    assert data[1]["pr_number"] == 5
    # queue_position is numbered independently per platform list (both start at 1)
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
                "evt-rej0002", approved_by=None, approved_mr_id=None, approved_mr_sha=None,
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
# Batch 1 ATDD (Step 6 / T-10): /queue/headhunter/pending decoupling,
# independent env gates, 4 GitLab skip paths, CA bundle & host normalization
# =========================================================================


async def _get_headhunter_pending_http(
    *,
    env: dict[str, str],
    mock_bb: AsyncMock,
    mock_brain: MagicMock | None = None,
    gitlab_auth: object = "DEFAULT",
    gitlab_auth_exc: Exception | None = None,
    gitlab_resp: MagicMock | None = None,
    gitlab_get_exc: Exception | None = None,
    capture_httpx_kwargs: list[dict] | None = None,
    capture_get_urls: list[str] | None = None,
):
    """Layer 3 Protocol Driver for GET /queue/headhunter/pending."""
    if gitlab_resp is None:
        gitlab_resp = MagicMock()
        gitlab_resp.is_success = True
        gitlab_resp.json.return_value = []

    mock_client = AsyncMock()
    if gitlab_get_exc is not None:
        mock_client.get = AsyncMock(side_effect=gitlab_get_exc)
    else:
        async def _capture_get(url, **kwargs):
            if capture_get_urls is not None:
                capture_get_urls.append(str(url))
            return gitlab_resp
        mock_client.get = AsyncMock(side_effect=_capture_get)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=False)

    def _client_factory(*args, **kwargs):
        if capture_httpx_kwargs is not None:
            capture_httpx_kwargs.append(kwargs)
        return mock_client

    if gitlab_auth == "DEFAULT":
        mock_auth = MagicMock()
        if gitlab_auth_exc is not None:
            mock_auth.get_token.side_effect = gitlab_auth_exc
        else:
            mock_auth.get_token.return_value = "fake-token"
    else:
        mock_auth = gitlab_auth

    with patch("src.main.lifespan") as mock_lifespan:
        mock_lifespan.return_value.__aenter__ = AsyncMock()
        mock_lifespan.return_value.__aexit__ = AsyncMock()
        with patch.dict(os.environ, env, clear=False):
            with patch("src.utils.gitlab_token.get_gitlab_auth", return_value=mock_auth):
                with patch("httpx.AsyncClient", side_effect=_client_factory):
                    from src import dependencies
                    from src.main import app

                    original_bb = dependencies._blackboard
                    original_brain = dependencies._brain
                    dependencies._blackboard = mock_bb
                    if mock_brain is not None:
                        dependencies._brain = mock_brain
                    try:
                        transport = ASGITransport(app=app)
                        async with AsyncClient(transport=transport, base_url="http://test") as client:
                            return await client.get("/queue/headhunter/pending")
                    finally:
                        dependencies._blackboard = original_bb
                        dependencies._brain = original_brain


def _github_pending_fixtures():
    queued_pr = {
        "number": 77,
        "title": "Queued PR",
        "owner": "The-Darwin-Project",
        "repo": "BlackBoard",
        "user": "octocat",
        "created_at": "2026-09-01T00:00:00Z",
        "html_url": "https://github.com/The-Darwin-Project/BlackBoard/pull/77",
    }
    fake_hh = SimpleNamespace(_github=SimpleNamespace(queued_prs=[queued_pr], queued_issues=[]))
    mock_brain = MagicMock()
    mock_brain.agents = {"_headhunter": fake_hh}

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
    mock_bb.get_event = AsyncMock(return_value=issue_event)
    return mock_bb, mock_brain


class TestATDDT10QueuePendingDecoupling:
    """Layer 1-4 ATDD scenarios for T-10 (/queue/headhunter/pending)."""

    @pytest.mark.asyncio
    async def test_t10a_gitlab_host_unset_still_returns_github_queued_and_active_items(self):
        """Given GITLAB_HOST="" and HEADHUNTER_GITHUB_ENABLED=true
        When GET /queue/headhunter/pending is called
        Then HTTP 200 returns GitHub queued PRs and active Issues with issue_number/issue_title."""
        mock_bb, mock_brain = _github_pending_fixtures()
        resp = await _get_headhunter_pending_http(
            env={"GITLAB_HOST": "", "HEADHUNTER_ENABLED": "true", "HEADHUNTER_GITHUB_ENABLED": "true"},
            mock_bb=mock_bb,
            mock_brain=mock_brain,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert any(i.get("pr_number") == 77 and i.get("action") == "queued" for i in data)
        issues = [i for i in data if i.get("issue_number") == 233]
        assert len(issues) == 1
        assert issues[0]["issue_title"] == "Active issue title"
        assert "pr_number" not in issues[0]

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "failure_mode",
        ["no_auth", "token_exc", "http_500", "connect_exc"],
    )
    async def test_t10b_all_four_gitlab_failures_skip_gitlab_and_return_github_items(self, failure_mode):
        """Given GitLab hits any of the 4 failure modes (no auth, token exception, HTTP 500,
        httpx/TLS error)
        When GET /queue/headhunter/pending is called
        Then GitLab is skipped without early-returning and GitHub queued & active items still appear."""
        import httpx as httpx_mod

        mock_bb, mock_brain = _github_pending_fixtures()
        kwargs: dict = {
            "env": {
                "GITLAB_HOST": "gitlab.example.com",
                "HEADHUNTER_ENABLED": "true",
                "HEADHUNTER_GITHUB_ENABLED": "true",
            },
            "mock_bb": mock_bb,
            "mock_brain": mock_brain,
        }
        if failure_mode == "no_auth":
            kwargs["gitlab_auth"] = None
        elif failure_mode == "token_exc":
            kwargs["gitlab_auth_exc"] = RuntimeError("vault unavailable")
        elif failure_mode == "http_500":
            err_resp = MagicMock()
            err_resp.is_success = False
            err_resp.status_code = 500
            kwargs["gitlab_resp"] = err_resp
        elif failure_mode == "connect_exc":
            kwargs["gitlab_get_exc"] = httpx_mod.ConnectError("TLS handshake failed")

        resp = await _get_headhunter_pending_http(**kwargs)
        assert resp.status_code == 200
        data = resp.json()
        assert any(i.get("pr_number") == 77 for i in data), f"GitHub queued PR hidden on {failure_mode}"
        assert any(i.get("issue_number") == 233 for i in data), f"GitHub active Issue hidden on {failure_mode}"

    @pytest.mark.asyncio
    async def test_t10c_headhunter_enabled_false_with_github_enabled_true_returns_github_items(self):
        """Given HEADHUNTER_ENABLED=false and HEADHUNTER_GITHUB_ENABLED=true
        When GET /queue/headhunter/pending is called
        Then GitLab is skipped (0 GitLab HTTP calls) and GitHub items are still returned."""
        mock_bb, mock_brain = _github_pending_fixtures()
        captured_urls: list[str] = []
        resp = await _get_headhunter_pending_http(
            env={
                "GITLAB_HOST": "gitlab.example.com",
                "HEADHUNTER_ENABLED": "false",
                "HEADHUNTER_GITHUB_ENABLED": "true",
            },
            mock_bb=mock_bb,
            mock_brain=mock_brain,
            capture_get_urls=captured_urls,
        )
        assert resp.status_code == 200
        assert captured_urls == []
        data = resp.json()
        assert any(i.get("pr_number") == 77 for i in data)
        assert any(i.get("issue_number") == 233 for i in data)

    @pytest.mark.asyncio
    async def test_t10d_gitlab_call_normalizes_host_and_uses_resolve_ca_bundle_never_verify_false(self, tmp_path):
        """Given GITLAB_HOST='https://gitlab.example.com/' and a CA bundle
        When GET /queue/headhunter/pending queries GitLab
        Then host is normalized (no double scheme/slash) and httpx.AsyncClient uses resolve_ca_bundle,
        never verify=False."""
        ca = str(tmp_path / "ca.pem")
        (tmp_path / "ca.pem").write_text("cert")
        mock_bb = AsyncMock()
        mock_bb.get_active_events_with_status = AsyncMock(return_value={})
        captured_kwargs: list[dict] = []
        captured_urls: list[str] = []

        with patch("src.routes.queue.resolve_ca_bundle", return_value=ca) as mock_ca:
            resp = await _get_headhunter_pending_http(
                env={
                    "GITLAB_HOST": "https://gitlab.example.com/",
                    "HEADHUNTER_ENABLED": "true",
                    "HEADHUNTER_GITHUB_ENABLED": "false",
                },
                mock_bb=mock_bb,
                capture_httpx_kwargs=captured_kwargs,
                capture_get_urls=captured_urls,
            )

        assert resp.status_code == 200
        mock_ca.assert_called_once_with("gitlab.example.com")
        assert captured_kwargs and captured_kwargs[0].get("verify") == ca
        assert captured_kwargs[0].get("verify") is not False
        assert captured_urls == ["https://gitlab.example.com/api/v4/todos"]

    @pytest.mark.asyncio
    async def test_t10e_both_flags_false_returns_empty_list(self):
        """F-19: Given HEADHUNTER_ENABLED=false and HEADHUNTER_GITHUB_ENABLED=false
        When GET /queue/headhunter/pending is called
        Then HTTP 200 returns [] with zero GitLab calls."""
        mock_bb, mock_brain = _github_pending_fixtures()
        captured_urls: list[str] = []
        resp = await _get_headhunter_pending_http(
            env={
                "GITLAB_HOST": "gitlab.example.com",
                "HEADHUNTER_ENABLED": "false",
                "HEADHUNTER_GITHUB_ENABLED": "false",
            },
            mock_bb=mock_bb,
            mock_brain=mock_brain,
            capture_get_urls=captured_urls,
        )
        assert resp.status_code == 200
        assert resp.json() == []
        assert captured_urls == []

    @pytest.mark.asyncio
    async def test_t10f_gitlab_ssl_verify_false_logs_error_and_still_returns_github_items(self, caplog):
        """F-16: Given GITLAB_SSL_VERIFY=false raises ValueError in resolve_ca_bundle()
        When GET /queue/headhunter/pending runs
        Then an ERROR is logged for TLS policy block and GitHub items are still returned."""
        mock_bb, mock_brain = _github_pending_fixtures()
        with caplog.at_level("ERROR"):
            resp = await _get_headhunter_pending_http(
                env={
                    "GITLAB_HOST": "gitlab.example.com",
                    "GITLAB_SSL_VERIFY": "false",
                    "HEADHUNTER_ENABLED": "true",
                    "HEADHUNTER_GITHUB_ENABLED": "true",
                },
                mock_bb=mock_bb,
                mock_brain=mock_brain,
            )
        assert resp.status_code == 200
        data = resp.json()
        assert any(i.get("pr_number") == 77 for i in data)
        assert any(i.get("issue_number") == 233 for i in data)
        assert any(
            r.levelname == "ERROR" and "TLS policy" in r.message
            for r in caplog.records
        )

    @pytest.mark.asyncio
    async def test_t10g_malformed_gitlab_payload_and_none_fields_do_not_crash_endpoint(self):
        """F-16: Non-list JSON payload, target=None, and created_at=None must not raise 500."""
        mock_bb = AsyncMock()
        mock_bb.get_active_events_with_status = AsyncMock(return_value={})

        non_list_resp = MagicMock()
        non_list_resp.is_success = True
        non_list_resp.json.return_value = {"message": "unexpected dict"}
        resp1 = await _get_headhunter_pending_http(
            env={
                "GITLAB_HOST": "gitlab.example.com",
                "HEADHUNTER_ENABLED": "true",
                "HEADHUNTER_GITHUB_ENABLED": "false",
            },
            mock_bb=mock_bb,
            gitlab_resp=non_list_resp,
        )
        assert resp1.status_code == 200
        assert resp1.json() == []

        weird_todos_resp = MagicMock()
        weird_todos_resp.is_success = True
        weird_todos_resp.json.return_value = [
            "not-a-dict",
            {
                "id": 1,
                "action_name": "assigned",
                "target": None,
                "project": None,
                "created_at": None,
                "target_url": None,
            },
            {
                "id": 2,
                "action_name": "assigned",
                "target": {"iid": 9, "title": "Valid", "state": "opened", "author": None, "pipeline": None},
                "project": {"path_with_namespace": "org/repo"},
                "created_at": "2026-09-01T00:00:00Z",
                "target_url": "https://gitlab.example.com/org/repo/-/merge_requests/9",
            },
        ]
        resp2 = await _get_headhunter_pending_http(
            env={
                "GITLAB_HOST": "gitlab.example.com",
                "HEADHUNTER_ENABLED": "true",
                "HEADHUNTER_GITHUB_ENABLED": "false",
            },
            mock_bb=mock_bb,
            gitlab_resp=weird_todos_resp,
        )
        assert resp2.status_code == 200
        rows = resp2.json()
        assert len(rows) == 2
        assert rows[0]["todo_id"] == 1 and rows[0]["created_at"] == ""
        assert rows[1]["todo_id"] == 2 and rows[1]["mr_iid"] == 9

