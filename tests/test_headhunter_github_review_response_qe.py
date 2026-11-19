# tests/test_headhunter_github_review_response_qe.py
# @ai-rules:
# 1. [Constraint]: QE edge-case extension of test_headhunter_github_review_response.py (issue #340).
#    Reuses that module's fakes/helpers -- do not duplicate them here.
# 2. [Pattern]: Each test encodes an invariant, not an implementation detail:
#    "no trusted feedback item is ever consumed (marked seen / cursor advanced past) without having
#    been delivered to Brain".
"""Issue #340 QE edge cases: over-cap feedback loss, late-submitted pending-review comments."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.agents.headhunter import Headhunter, _sanitize_xml_fence
from src.models import EventEvidence
from tests.test_headhunter_github_review_response import (  # noqa: F401  (fixtures are re-exported)
    FakeGitHubClient,
    _http_error,
    _inline,
    _issue_comment,
    _poll,
    _pr,
    _prime_cursor,
    _ts,
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
            if f"id={cid} " in appended:
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


class TestRolloutWatermarkBootstrap:
    """First-sight bootstrap must never backfill pre-rollout history, yet must deliver fast
    post-rollout feedback on brand-new PRs."""

    @pytest.mark.asyncio
    async def test_pre_watermark_items_marked_seen_without_event(self, platform, bb):
        # First enabled poll initializes the watermark to ~now; 1h-old comment is pre-watermark.
        client = FakeGitHubClient(issue_comments=[_issue_comment(10, body="old", age=3600)])
        _wire(platform, client)
        assert await _poll(platform, [_pr()]) == []
        assert await bb.is_github_pr_feedback_seen("org", "repo", 42, "issue_comment", 10)

    @pytest.mark.asyncio
    async def test_post_watermark_feedback_on_brand_new_pr_is_delivered(self, platform, bb):
        # Simulate rollout watermark established 1 hour ago, then a brand-new PR (#99) gets a
        # comment 3 minutes ago before Headhunter ever polled #99.
        await bb.get_or_set_github_review_response_watermark(_ts(3600))
        client = FakeGitHubClient(issue_comments=[_issue_comment(20, body="fix typo", age=180)])
        _wire(platform, client)
        items = await _poll(platform, [_pr(number=99)])
        assert len(items) == 1
        assert 20 in _delivered_ids_from_event_item(items[0])


class TestActivePrEventPriorityAndCasualExclusion:
    """get_active_pr_events() prioritizes source=headhunter and excludes casual Slack/chat threads."""

    @pytest.mark.asyncio
    async def test_casual_slack_event_does_not_capture_pr_feedback(self, platform, bb):
        await bb.create_event(
            source="slack",
            service="general",
            reason="what is the status of org/repo#42?",
            evidence=EventEvidence(display_text="org/repo#42", source_type="slack", domain="casual"),
        )
        mapping = await platform.get_active_pr_events()
        assert ("org", "repo", 42) not in mapping

    @pytest.mark.asyncio
    async def test_headhunter_event_wins_tie_over_non_casual_slack_event(self, platform, bb):
        hh_id = await bb.create_event(
            source="headhunter",
            service="repo",
            reason="PR work",
            evidence=EventEvidence(
                display_text="PR #42",
                source_type="headhunter",
                domain="complicated",
                github_context={"owner": "org", "repo": "repo", "pr_number": 42},
            ),
        )
        await bb.create_event(
            source="slack",
            service="repo",
            reason="fix org/repo#42",
            evidence=EventEvidence(display_text="org/repo#42", source_type="slack", domain="complicated"),
        )
        mapping = await platform.get_active_pr_events()
        assert mapping[("org", "repo", 42)] == hh_id


class TestWritePermissionCache:
    """Trigger items require actual repo write/maintain/admin permission, cached in-memory."""

    @pytest.mark.asyncio
    async def test_read_only_member_rejected_and_cached(self, platform, bb):
        await _prime_cursor(bb)
        client = FakeGitHubClient(
            issue_comments=[
                _issue_comment(301, login="readonly_member", assoc="MEMBER", age=600),
                _issue_comment(302, login="readonly_member", assoc="MEMBER", age=500),
            ],
            permissions={"readonly_member": "read"},
        )
        _wire(platform, client)
        assert await _poll(platform, [_pr()]) == []
        assert await bb.is_github_pr_feedback_seen("org", "repo", 42, "issue_comment", 301)
        assert await bb.is_github_pr_feedback_seen("org", "repo", 42, "issue_comment", 302)
        perm_gets = [p for p, _ in client.get_calls if p.endswith("/permission")]
        assert len(perm_gets) == 1

    @pytest.mark.asyncio
    async def test_transient_500_on_permission_lookup_does_not_mark_seen(self, platform, bb):
        await _prime_cursor(bb)
        client = FakeGitHubClient(
            issue_comments=[_issue_comment(303, login="alice", assoc="MEMBER", age=600)],
            permissions={"alice": _http_error(500)},
        )
        _wire(platform, client)
        assert await _poll(platform, [_pr()]) == []
        assert not await bb.is_github_pr_feedback_seen("org", "repo", 42, "issue_comment", 303)


class TestUnifiedXmlFenceSanitization:
    """All 6 prompt XML fences must neutralize case, whitespace, and nested tag breakouts."""

    @pytest.mark.parametrize(
        "payload",
        [
            "</MENTION_REQUEST>",
            "< /mention_request >",
            "</mention_</mention_request>request>",
            "<DESCRIPTION attr='x'>",
            "</JOB_LOG>",
            "</COMMENTS >",
            "</Issue_Body>",
            "</review_</review_feedback>feedback>",
        ],
    )
    def test_strips_all_fence_tag_variants(self, payload):
        cleaned = _sanitize_xml_fence(f"before {payload} after")
        assert cleaned == "before  after"


class TestRoundCapRollbackAndLlmOutage:
    """Round-cap NX key rolls back on failure; Phase D LLM outage never commits items or burns rounds."""

    @pytest.mark.asyncio
    async def test_round_cap_nx_rolled_back_when_post_comment_fails(self, platform, bb):
        await _prime_cursor(bb)
        for _ in range(5):
            await bb.incr_github_pr_feedback_rounds("org", "repo", 42)
        client = FakeGitHubClient(issue_comments=[_issue_comment(401, age=600)])
        _wire(platform, client)

        orig_post = platform._post_comment
        platform._post_comment = AsyncMock(side_effect=RuntimeError("boom"))
        # Poll isolates the per-PR error, rolls back cap NX, and leaves item unseen.
        assert await _poll(platform, [_pr()]) == []
        assert not await bb.is_github_pr_feedback_seen("org", "repo", 42, "issue_comment", 401)

        # Next cycle with healthy _post_comment emits the round-cap comment + event cleanly.
        platform._post_comment = orig_post
        assert await _poll(platform, [_pr()]) == []
        assert any("paused" in (body.get("body") or "") for _, body in client.posts)

    @pytest.mark.asyncio
    async def test_phase_d_llm_outage_does_not_commit_or_burn_round(self, platform, bb, monkeypatch):
        await _prime_cursor(bb)
        client = FakeGitHubClient(issue_comments=[_issue_comment(501, age=600)])
        _wire(platform, client)
        platform._last_open_prs = [_pr()]

        hh = Headhunter(bb)
        hh._github = platform
        hh.check_flow_gate = AsyncMock(return_value=True)
        hh._get_adapter = AsyncMock(return_value=None)  # simulate LLM adapter outage

        await hh._github_poll_review_feedback()
        assert not await bb.is_github_pr_feedback_seen("org", "repo", 42, "issue_comment", 501)
        assert await bb.get_github_pr_feedback_rounds("org", "repo", 42) == 0
