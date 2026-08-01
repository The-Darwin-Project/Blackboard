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


class TestCloseSummaryPrefixedInMrFeedbackComment:
    """close_summary must be prefixed with 'Summary: ' (commit a712fc02) so a value
    that starts with a slash cannot be misread as the first line of a GitLab
    quick-action/slash-command by PaC/GitOps bots scanning the comment body."""

    def test_close_summary_line_is_prefixed(self):
        event = SimpleNamespace(conversation=[_bfc_turn(thoughts="Root cause fixed.")])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "Summary: Root cause fixed." in comment

    def test_leading_slash_in_close_summary_is_not_first_char_on_its_line(self):
        # Even a maximally-adversarial close_summary starting with "/" must not
        # appear as the first character of its own line once prefixed.
        event = SimpleNamespace(conversation=[_bfc_turn(thoughts="/close")])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        summary_line = next(line for line in comment.split("\n") if "close" in line and "Darwin" not in line)
        assert not summary_line.startswith("/")
        assert summary_line == "Summary: /close"

    def test_tracking_link_line_is_unaffected_by_summary_prefix(self):
        event = SimpleNamespace(conversation=[_bfc_turn(result="VMER-1234", thoughts="Root cause fixed.")])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "**Tracking:** VMER-1234" in comment
        assert "Summary: VMER-1234" not in comment


class TestCloseSummarySanitizedInMrFeedbackComment:
    """close_summary is LLM-controlled free text (close_turn.thoughts) -- it must be
    routed through sanitize_comment_field() before landing in a bot-authored MR
    comment, same as tracking_link (commit 7dcb3108)."""

    def test_markdown_link_syntax_stripped_from_close_summary(self):
        event = SimpleNamespace(conversation=[_bfc_turn(thoughts="[click me](https://phish.example)")])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "[click me]" not in comment
        assert "click mehttps://phish.example" in comment

    def test_newline_quick_action_injection_stripped_from_close_summary(self):
        event = SimpleNamespace(conversation=[_bfc_turn(thoughts="resolved\n/close\n/assign @maintainer")])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "\n/close" not in comment
        assert "\n/assign" not in comment

    def test_at_mention_and_backtick_breakout_stripped_from_close_summary(self):
        event = SimpleNamespace(conversation=[_bfc_turn(thoughts="cc @octocat `rm -rf /`")])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "@octocat" not in comment
        assert "`" not in comment

    def test_clean_close_summary_is_unaffected(self):
        event = SimpleNamespace(conversation=[_bfc_turn(thoughts="Root cause fixed after retry.")])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "Root cause fixed after retry." in comment

    def test_close_summary_and_tracking_link_both_sanitized_independently(self):
        event = SimpleNamespace(conversation=[_bfc_turn(
            result="[evil](https://phish.example)",
            thoughts="![img](https://phish.example/x.png)\n/close",
        )])
        comment = GitLabPlatform._build_feedback_comment(event, "resolved")
        assert "[evil]" not in comment
        assert "![img]" not in comment
        assert "\n/close" not in comment
        assert "imghttps://phish.example/x.png/close" in comment
        assert "**Tracking:** evilhttps://phish.example" in comment
