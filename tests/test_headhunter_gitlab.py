# tests/test_headhunter_gitlab.py
# @ai-rules:
# 1. [Constraint]: No real GitLab API calls. _build_feedback_comment is a @staticmethod --
#    call it directly on the class, no platform instantiation required.
# 2. [Pattern]: Written against plan spec (terminal-state-close-gate, Step 5): GitLab's
#    tracking_link append is scoped to _build_feedback_comment only -- no close_reason
#    humanization here (close_reason is control-flow-only in this file, never displayed).
"""Tests for GitLabPlatform's tracking_link surfacing in MR feedback comments (T-18 GitLab half)."""
from __future__ import annotations

from types import SimpleNamespace

from src.agents.headhunter_gitlab import GitLabPlatform


def _bfc_turn(result=None, thoughts="Done", timestamp=1719849600.0):
    """Minimal close-turn stub -- _build_feedback_comment only reads
    actor/action/result/thoughts/timestamp off event.conversation[-1]."""
    return SimpleNamespace(actor="brain", action="close", result=result, thoughts=thoughts, timestamp=timestamp)


class TestTrackingLinkInMrFeedbackComment:
    """T-18 (GitLab half): _build_feedback_comment surfaces close_turn.result
    as the tracking link, omitted cleanly when absent."""

    def test_tracking_link_included_when_present(self):
        event = SimpleNamespace(conversation=[_bfc_turn(result="VMER-1234")])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "VMER-1234" in comment

    def test_tracking_link_omitted_when_result_none(self):
        event = SimpleNamespace(conversation=[_bfc_turn(result=None)])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "Tracking" not in comment

    def test_tracking_link_omitted_when_no_close_turn(self):
        event = SimpleNamespace(conversation=[])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "Tracking" not in comment

    def test_close_summary_still_present_alongside_tracking_link(self):
        """Tracking link is additive -- the existing close-summary line must survive."""
        event = SimpleNamespace(conversation=[_bfc_turn(result="VMER-1234", thoughts="Root cause fixed.")])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "Root cause fixed." in comment
        assert "VMER-1234" in comment
