# BlackBoard/src/utils/jira_context.py
# @ai-rules:
# 1. [Constraint]: Zero imports from src.agents -- hexagonal-clean shared helper for Brain and HeadhunterJira.
# 2. [Pattern]: Single source of truth for Jira context extraction and issue_key normalization (strips ASCII control chars, trims whitespace, uppercases).
"""Shared Jira context extraction and issue-key normalization helpers."""
from __future__ import annotations

import re
from typing import Any

_CTRL_RE = re.compile(r"[\x00-\x1f\x7f]")
JIRA_KEY_RE = re.compile(r"^[A-Z][A-Z0-9_]+-\d+\Z")


def is_valid_jira_key(key: Any) -> bool:
    """Return True iff key is a canonical Jira issue key (e.g. VMER-2464, CNV_1-99)."""
    return isinstance(key, str) and bool(JIRA_KEY_RE.fullmatch(key))


def extract_jira_context(doc: Any) -> tuple[bool, str | None]:
    """Return (is_jira_event, normalized_issue_key) from subject_type and nested jira_context."""
    is_jira = getattr(doc, "subject_type", "service") == "jira"
    ev_obj = getattr(doc, "event", None)
    ev = ev_obj.evidence if (ev_obj and getattr(ev_obj, "evidence", None)) else None
    if isinstance(ev, dict):
        jc = ev.get("jira_context")
    elif ev is not None and not isinstance(ev, str):
        jc = getattr(ev, "jira_context", None)
    else:
        jc = None
    raw_key = jc.get("issue_key") if isinstance(jc, dict) else None
    key: str | None = None
    if isinstance(raw_key, str):
        cleaned = _CTRL_RE.sub("", raw_key).strip().upper()
        if cleaned:
            key = cleaned
    return (is_jira or key is not None), key
