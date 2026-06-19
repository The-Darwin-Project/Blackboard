# @ai-rules:
# 1. [Constraint]: No real GitLab API calls. Pure unit tests for static method.
"""Unit tests for Headhunter.parse_mr_url()."""
from __future__ import annotations

import pytest

from src.agents.headhunter import Headhunter


class TestParseMrUrl:
    """Tests for parse_mr_url static method."""

    def test_api_style_url(self):
        result = Headhunter.parse_mr_url("/projects/12345/merge_requests/29")
        assert result == (12345, 29)

    def test_api_style_url_in_full_url(self):
        result = Headhunter.parse_mr_url(
            "https://gitlab.example.com/api/v4/projects/12345/merge_requests/29"
        )
        assert result == (12345, 29)

    def test_web_url_two_segments(self):
        result = Headhunter.parse_mr_url(
            "https://gitlab.example.com/group/project/-/merge_requests/10"
        )
        assert result == ("group/project", 10)

    def test_web_url_three_segments(self):
        result = Headhunter.parse_mr_url(
            "https://gitlab.example.com/org/sub/project/-/merge_requests/5"
        )
        assert result == ("org/sub/project", 5)

    def test_web_url_four_segments(self):
        result = Headhunter.parse_mr_url(
            "https://gitlab.cee.redhat.com/openshift-virtualization/konflux-builds/v4-23/kubevirt/-/merge_requests/29"
        )
        assert result == (
            "openshift-virtualization/konflux-builds/v4-23/kubevirt",
            29,
        )

    def test_web_url_five_segments(self):
        result = Headhunter.parse_mr_url(
            "https://gitlab.example.com/a/b/c/d/e/-/merge_requests/1"
        )
        assert result == ("a/b/c/d/e", 1)

    def test_web_url_with_query_params(self):
        result = Headhunter.parse_mr_url(
            "https://gitlab.example.com/org/project/-/merge_requests/7?tab=changes"
        )
        assert result == ("org/project", 7)

    def test_web_url_with_fragment(self):
        result = Headhunter.parse_mr_url(
            "https://gitlab.example.com/org/project/-/merge_requests/7#note_123"
        )
        assert result == ("org/project", 7)

    def test_web_url_with_query_and_fragment(self):
        result = Headhunter.parse_mr_url(
            "https://gitlab.example.com/org/project/-/merge_requests/7?tab=changes#note_1"
        )
        assert result == ("org/project", 7)

    def test_invalid_url_returns_none(self):
        assert Headhunter.parse_mr_url("https://gitlab.example.com/some/page") is None

    def test_empty_string_returns_none(self):
        assert Headhunter.parse_mr_url("") is None

    def test_non_numeric_mr_iid_returns_none(self):
        assert Headhunter.parse_mr_url(
            "https://gitlab.example.com/org/project/-/merge_requests/abc"
        ) is None
