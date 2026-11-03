# BlackBoard/tests/test_event_markdown_escape.py
# @ai-rules:
# 1. [Constraint]: Tests for title HTML-escaping in event_markdown.py (T-SEC-4).
# 2. [Security]: Verifies script tags and HTML in event.title are escaped with _esc().
"""Tests for title escaping in event_to_markdown."""
from __future__ import annotations

from src.models import EventDocument, EventEvidence, EventInput, Service
from src.utils.event_markdown import event_to_markdown


def test_event_title_escaped_in_markdown():
    """T-SEC-4: Title containing HTML/script tags is escaped via _esc to prevent stored XSS."""
    malicious_title = "<script>alert('XSS')</script>"
    event = EventDocument(
        id="evt-xss01",
        source="chat",
        service="security-test",
        title=malicious_title,
        title_source="user",
        event=EventInput(
            reason="testing title escape",
            evidence=EventEvidence(
                display_text="clean evidence",
                source_type="chat",
                domain="clear",
                severity="info",
            ),
        ),
    )

    md = event_to_markdown(event)

    # Must contain HTML-escaped script tags
    assert "&lt;script&gt;alert(&#x27;XSS&#x27;)&lt;/script&gt;" in md or "&lt;script&gt;alert('XSS')&lt;/script&gt;" in md
    # Must NOT contain raw unescaped script tags
    assert "<script>" not in md
    assert "</script>" not in md
