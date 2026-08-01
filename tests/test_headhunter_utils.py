# BlackBoard/tests/test_headhunter_utils.py
# @ai-rules:
# 1. [Constraint]: This module has zero project imports itself (see headhunter_utils.py
#    ai-rules) -- keep these tests import-light too, no headhunter/adapter fixtures needed.
# 2. [Pattern]: sanitize_comment_field() is the injection boundary for close_reason and
#    tracking_link before they hit an externally-visible GitHub/GitLab comment -- these
#    tests are the regression guard for that boundary (see PR #159 HIGH finding).
"""Unit tests for src/agents/headhunter_utils.py sanitization helpers."""
from __future__ import annotations

import pytest

from src.agents.headhunter_utils import sanitize_comment_field


class TestSanitizeCommentFieldMarkdownInjection:
    def test_strips_markdown_link_syntax(self):
        assert sanitize_comment_field("[click me](https://phish.example)") == "click mehttps://phish.example"

    def test_strips_markdown_image_syntax(self):
        assert sanitize_comment_field("![alt](https://phish.example/x.png)") == "althttps://phish.example/x.png"

    def test_no_brackets_parens_or_bangs_survive_combined_payload(self):
        payload = "[click me](https://evil.com) and ![img](https://evil.com/x.png) <script>@user `code`"
        result = sanitize_comment_field(payload)
        for char in "[]()!<>@`":
            assert char not in result

    def test_bare_exclamation_is_stripped(self):
        assert sanitize_comment_field("Great job!") == "Great job"

    def test_nested_and_nonstandard_bracket_pairs_stripped(self):
        assert sanitize_comment_field("[[a]](b(c)d)") == "abcd"


class TestSanitizeCommentFieldQuickActionInjection:
    """sanitize_comment_field must strip \\n/\\r so a crafted close_reason or
    tracking_link cannot inject additional comment lines (e.g. GitLab quick-actions
    like `/close`, `/assign`) under the bot's identity."""

    def test_strips_bare_newline(self):
        assert sanitize_comment_field("resolved\n/close") == "resolved/close"

    def test_strips_bare_carriage_return(self):
        assert sanitize_comment_field("resolved\r/close") == "resolved/close"

    def test_strips_crlf(self):
        assert sanitize_comment_field("resolved\r\n/assign @bot") == "resolved/assign bot"

    def test_strips_multiple_embedded_newlines(self):
        payload = "line one\nline two\r\nline three"
        assert sanitize_comment_field(payload) == "line oneline twoline three"

    def test_quick_action_injection_payload_neutralized(self):
        payload = "self_resolved\n/close\n/assign @maintainer"
        result = sanitize_comment_field(payload)
        assert "\n" not in result
        assert "\r" not in result

    def test_no_breakout_or_injection_chars_survive_combined_payload(self):
        payload = "[click](https://evil.com)\n/close\r\n@user `code` <tag>!"
        result = sanitize_comment_field(payload)
        for char in "[]()!<>@`\n\r":
            assert char not in result


class TestSanitizeCommentFieldPreExistingBehavior:
    def test_strips_angle_brackets(self):
        assert sanitize_comment_field("<script>alert(1)</script>") == "scriptalert1/script"

    def test_strips_at_mentions(self):
        assert sanitize_comment_field("cc @octocat please review") == "cc octocat please review"

    def test_strips_backticks(self):
        assert sanitize_comment_field("run `rm -rf /`") == "run rm -rf /"

    def test_plain_text_is_unaffected(self):
        assert sanitize_comment_field("Resolved after retry, no action needed.") == \
            "Resolved after retry, no action needed."

    def test_caps_length_to_max_len(self):
        result = sanitize_comment_field("a" * 300)
        assert len(result) == 200

    def test_custom_max_len_is_respected(self):
        result = sanitize_comment_field("a" * 50, max_len=10)
        assert len(result) == 10

    def test_length_cap_applies_after_stripping(self):
        # Stripped chars must not count toward the cap -- cap is on the sanitized output.
        payload = "[" * 250 + "b"
        result = sanitize_comment_field(payload, max_len=10)
        assert result == "b"

    def test_empty_string_returns_empty_string(self):
        assert sanitize_comment_field("") == ""


class TestSanitizeCommentFieldRealisticPayloads:
    def test_tracking_link_style_payload(self):
        # tracking_link is normally a plain https:// URL -- must survive untouched.
        url = "https://github.com/org/repo/issues/42"
        assert sanitize_comment_field(url) == url

    def test_close_reason_style_payload(self):
        assert sanitize_comment_field("self_resolved: retried and succeeded") == \
            "self_resolved: retried and succeeded"

    def test_malicious_tracking_link_prompt_injection(self):
        payload = "[Click here for details](https://phish.example/steal?token=abc)"
        result = sanitize_comment_field(payload)
        assert "[" not in result and "]" not in result
        assert "(" not in result and ")" not in result
        # The URL text itself is not required to be removed, only the markdown
        # syntax that would render it as a clickable/embedded link.
