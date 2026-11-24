# BlackBoard/src/agents/event_state_tail.py
# @ai-rules:
# 1. [Constraint]: Pure sync formatter only -- ZERO Redis, LLM, Brain, or state imports (<=100 lines).
# 2. [Security]: Every untrusted string MUST pass through prompt_sanitize.sanitize_untrusted_line/block
#    with redact=True so XML fences (</event_state>), PII, Unicode invisibles, and [!call: are neutralized.
# 3. [Pattern]: Emits a single fenced <event_state>...</event_state> block appended to the volatile tail
#    of contents[] so Layer 1+2 (wire_tools + Global Core SI) and Layer 3 history stay byte-immutable.
"""Volatile <event_state> tail formatter for Brain implicit context caching (VMER-2450)."""
from __future__ import annotations

from collections.abc import Sequence

from ..utils.prompt_sanitize import (
    sanitize_untrusted_block,
    sanitize_untrusted_line,
    strip_xml_fences,
)


def _clean_lines(items: Sequence[str] | None, *, max_len: int = 300, redact: bool = True) -> list[str]:
    if not items:
        return []
    out: list[str] = []
    for item in items:
        cleaned = sanitize_untrusted_line(item, max_len=max_len, redact=redact).strip()
        if cleaned:
            out.append(cleaned)
    return out


def format_event_state_tail(
    *,
    compass: str = "",
    status: str = "",
    approved_by: str = "",
    defer_wakeup: str = "",
    authorized_tools: Sequence[str] | None = None,
    maintainers: Sequence[str] | None = None,
    briefing: str = "",
    service_meta: str = "",
    related_events: Sequence[str] | None = None,
    recent_closed: Sequence[str] | None = None,
    journal_entries: Sequence[str] | None = None,
    recalls: Sequence[str] | None = None,
    transient_overlays: Sequence[str] | None = None,
) -> str:
    """Render sanitized volatile event telemetry inside a fenced <event_state> block."""
    sections: list[str] = []

    if compass:
        sections.append(strip_xml_fences(compass).strip())

    meta_bits: list[str] = []
    if status:
        meta_bits.append(f"Status: {sanitize_untrusted_line(status, max_len=64, redact=True)}")
    if approved_by:
        meta_bits.append(f"Approved By: {sanitize_untrusted_line(approved_by, max_len=120, redact=False)}")
    if meta_bits:
        sections.append(" | ".join(meta_bits))

    if defer_wakeup:
        sections.append(sanitize_untrusted_block(defer_wakeup, max_len=1000, redact=True).strip())
    if authorized_tools:
        names = ", ".join(sorted({sanitize_untrusted_line(t, max_len=80, redact=True) for t in authorized_tools if t}))
        if names:
            sections.append(f"Authorized Tools: {names}")
    if maintainers:
        clean_maint = _clean_lines(maintainers, max_len=120, redact=False)
        if clean_maint:
            sections.append(f"Maintainers: {', '.join(clean_maint)}")
    if briefing:
        sections.append(strip_xml_fences(briefing).strip())
    if service_meta:
        sections.append(sanitize_untrusted_block(service_meta, max_len=2000, redact=True).strip())

    for heading, items in (
        ("Related Active Events", _clean_lines(related_events, max_len=300, redact=True)),
        ("Recently Closed Events", _clean_lines(recent_closed, max_len=300, redact=True)),
        ("Recent Service Journal", _clean_lines(journal_entries, max_len=300, redact=True)),
    ):
        if items:
            sections.append(f"### {heading}\n" + "\n".join(f"- {line}" for line in items))

    if recalls:
        clean_recalls = [sanitize_untrusted_block(r, max_len=4000, redact=True).strip() for r in recalls if r]
        if any(clean_recalls):
            sections.append("\n\n".join(r for r in clean_recalls if r))

    if transient_overlays:
        clean_overlays = [strip_xml_fences(ov).strip() for ov in transient_overlays if ov and ov.strip()]
        if clean_overlays:
            sections.append("\n\n".join(clean_overlays))

    body = "\n\n".join(s for s in sections if s)
    return f"<event_state>\n{body}\n</event_state>" if body else "<event_state>\n</event_state>"
