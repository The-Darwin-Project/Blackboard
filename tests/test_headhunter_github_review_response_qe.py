# tests/test_headhunter_github_review_response_qe.py
# @ai-rules:
# 1. [Constraint]: QE edge-case extension of test_headhunter_github_review_response.py (issue #340).
#    Reuses that module's fakes/helpers -- do not duplicate them here.
# 2. [Pattern]: Each test encodes an invariant, not an implementation detail:
#    "no trusted feedback item is ever consumed (marked seen / cursor advanced past) without having
#    been delivered to Brain".
"""Issue #340 QE edge cases: over-cap feedback loss, late-submitted pending-review comments."""
from __future__ import annotations

import pytest

from tests.test_headhunter_github_review_response import (  # noqa: F401  (fixtures are re-exported)
    FakeGitHubClient,
    _inline,
    _issue_comment,
    _poll,
    _pr,
    _prime_cursor,
    _wire,
    bb,
    platform,
)

N_ITEMS = 25  # > _FEEDBACK_ITEM_CAP (20)


def _delivered_ids_from_event_item(item: dict) -> set[int]:
    return {f["id"] for f in item["review_feedback"]}


class TestOverCapFeedbackIsNeverLost:
    """>20 trusted items in one poll: items 21+ must not be consumed without being delivered."""

    @pytest.mark.asyncio
    async def test_new_event_path_delivers_or_retains_every_item(self, platform, bb):
        client = FakeGitHubClient(
            issue_comments=[_issue_comment(1000 + i, body=f"nit {i}", age=3600 - i) for i in range(N_ITEMS)]
        )
        _wire(platform, client)
        await _prime_cursor(bb)
        items = await _poll(platform, [_pr()])
        assert len(items) == 1
        item = items[0]
        event_id = await platform.create_review_feedback_event(
            item, "---\nplan: x\n---", await platform.fetch_context(item)
        )
        ev = await bb.get_event(event_id)
        delivered = {f["id"] for f in ev.event.evidence.github_context["review_feedback"]}

        all_ids = {1000 + i for i in range(N_ITEMS)}
        cursor = await bb.get_github_pr_feedback_cursor("org", "repo", 42)
        lost = set()
        for cid in all_ids - delivered:
            seen = await bb.is_github_pr_feedback_seen("org", "repo", 42, "issue_comment", cid)
            past_cursor = cid <= cursor["issue_comment_id"]
            if seen or past_cursor:
                lost.add(cid)
        assert not lost, (
            f"{len(lost)} trusted feedback item(s) were consumed (seen/cursor advanced) but never "
            f"delivered to Brain: {sorted(lost)}"
        )

    @pytest.mark.asyncio
    async def test_active_event_append_path_delivers_or_retains_every_item(self, platform, bb):
        # Seed an active headhunter event on the PR, then deliver >20 new items to it.
        client = FakeGitHubClient(inline=[_inline(501)])
        _wire(platform, client)
        await _prime_cursor(bb)
        first = (await _poll(platform, [_pr()]))[0]
        event_id = await platform.create_review_feedback_event(
            first, "---\nplan: x\n---", await platform.fetch_context(first)
        )
        client.issue_comments = [
            _issue_comment(2000 + i, body=f"later nit {i}", age=3600 - i) for i in range(N_ITEMS)
        ]
        assert await _poll(platform, [_pr()]) == []  # appended, not a new event
        ev = await bb.get_event(event_id)
        appended = "\n".join(t.evidence or "" for t in ev.conversation if t.actor == "headhunter")
        cursor = await bb.get_github_pr_feedback_cursor("org", "repo", 42)
        lost = []
        for i in range(N_ITEMS):
            cid = 2000 + i
            if f"#{cid} " in appended:
                continue
            if await bb.is_github_pr_feedback_seen("org", "repo", 42, "issue_comment", cid) \
                    or cid <= cursor["issue_comment_id"]:
                lost.append(cid)
        assert not lost, f"appended turn dropped consumed feedback items: {lost}"


class TestLateSubmittedPendingReviewComments:
    """An inline comment from a review that was PENDING (drafted) while higher-id comments landed
    gets a LOWER id than the cursor once the review is submitted. The id floor must not skip it."""

    @pytest.mark.asyncio
    async def test_lower_id_comment_surfacing_after_cursor_advance_is_still_detected(self, platform, bb):
        # Cursor already advanced past id 105 (e.g. by Darwin's own in-thread reply or another
        # reviewer's comment). A draft comment id=100 becomes visible only when the review is submitted.
        await _prime_cursor(bb, review_comment_id=105)
        client = FakeGitHubClient(inline=[_inline(100, review_id=900, body="Late draft comment")])
        _wire(platform, client)
        items = await _poll(platform, [_pr()])
        assert items, "late-submitted lower-id review comment was silently skipped by the id cursor"
        assert 100 in _delivered_ids_from_event_item(items[0])
