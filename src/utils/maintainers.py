# BlackBoard/src/utils/maintainers.py
# @ai-rules:
# 1. [Constraint]: No project imports here -- must be importable from both src/agents/brain.py
#    and src/agents/handlers_integration.py (which itself forbids importing Brain).
# 2. [Pattern]: Single source of truth for maintainer-email resolution, used by the LLM
#    system-prompt template vars, the notify_user_slack tool-schema enum, and the Slack
#    fallback resolver -- so all three pick the same maintainer list for a given event.
"""Shared maintainer-resolution helpers for escalation routing.

Default precedence (prefer_slack_user=False): evidence.gitlab_context.maintainer.emails,
then github_context, then github_issue_context, then ci_context, then the
subject_type-appropriate static env var (JENKINS_OBSERVER_MAINTAINERS for ci_gating
events, HEADHUNTER_MAINTAINERS otherwise), then event.slack_user_id.

When prefer_slack_user=True (idle human escalation), event.slack_user_id takes
precedence over the static env var fallback while evidence VCS/CI context emails
remain highest priority.
"""
from __future__ import annotations

import os
import re
from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from ..models import EventDocument

_CONTEXT_ATTRS = ("gitlab_context", "github_context", "github_issue_context", "ci_context")
_EMAIL_RE = re.compile(r"(?<![A-Za-z0-9_.+-])[A-Za-z0-9_.+-]{1,64}@[A-Za-z0-9.-]{1,253}\.[A-Za-z]{2,24}(?![A-Za-z0-9_-])")
_SLACK_MENTION_RE = re.compile(r"<@(U[A-Z0-9]{8,})(?:\|[^>]+)?>")


def maintainer_env_key(subject_type: str | None) -> str:
    """Env var name holding the static maintainer email CSV for this subject_type."""
    return "JENKINS_OBSERVER_MAINTAINERS" if subject_type == "ci_gating" else "HEADHUNTER_MAINTAINERS"


def _dedupe(items: list[str], *, case_insensitive_emails: bool = False) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if not item:
            continue
        key = item.lower() if (case_insensitive_emails and "@" in item) else item
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _extract_evidence_maintainer_emails(event) -> list[str]:
    """Extract cleaned maintainer emails from the highest-priority evidence context dict."""
    emails: list[str] = []
    evidence = getattr(getattr(event, "event", None), "evidence", None)
    if evidence:
        for attr in _CONTEXT_ATTRS:
            if emails:
                break
            ctx = getattr(evidence, attr, None)
            if isinstance(ctx, dict):
                m = ctx.get("maintainer")
                raw_emails = m.get("emails") if isinstance(m, dict) else []
                raw_list = raw_emails if isinstance(raw_emails, (list, tuple, set)) else []
                emails.extend(e.strip() for e in raw_list if isinstance(e, str) and e.strip())
    return emails


def _resolve_static_env_emails(event) -> list[str]:
    subject_type = getattr(event, "subject_type", None) if event is not None else None
    static = os.getenv(maintainer_env_key(subject_type), "")
    return [e.strip() for e in static.split(",") if e.strip()]


def _resolve_evidence_env_maintainer_emails(event) -> list[str]:
    """Extract deduplicated maintainer emails from event evidence + static env fallback."""
    emails = _extract_evidence_maintainer_emails(event)
    if not emails:
        emails = _resolve_static_env_emails(event)
    return _dedupe(emails)


def resolve_maintainer_emails(event, *, prefer_slack_user: bool = False) -> list[str]:
    """Extract a deduplicated list of maintainer emails from event evidence + static config."""
    emails = _extract_evidence_maintainer_emails(event)
    raw_slack_uid = getattr(event, "slack_user_id", None) if event else None
    slack_user_id = raw_slack_uid.strip() if isinstance(raw_slack_uid, str) and raw_slack_uid.strip() else None
    if prefer_slack_user:
        if slack_user_id:
            emails.append(slack_user_id)
        if not emails:
            emails = _resolve_static_env_emails(event)
    else:
        if not emails:
            emails = _resolve_static_env_emails(event)
        if slack_user_id:
            emails.append(slack_user_id)
    return _dedupe(emails)


def is_slack_recipient_allowed(
    user_email: str, event_doc: Optional[EventDocument],
) -> tuple[bool, list[str]]:
    """Fail-closed allowlist check for notify_user_slack recipients.

    - Missing event or non-str/blank target: fail closed.
    - Automated + 'jarvis' sources (source not in ('chat', 'slack')): strict case-insensitive
      email match solely against evidence+env maintainer emails; raw U... IDs rejected.
    - Authenticated human sources ('chat', 'slack'): allows created_by_email, slack_user_id,
      evidence+env maintainer emails, authenticated actor=='user' turn.user_email, plus
      same-domain emails and framed <@U...> mentions from actor=='user' turn.thoughts/result.
    """
    if event_doc is None:
        return False, []
    if not isinstance(user_email, str) or not user_email.strip():
        return False, []

    target = user_email.strip()
    source = getattr(event_doc, "source", None)

    if source not in ("chat", "slack"):
        allowlist = _dedupe(
            [e for e in _resolve_evidence_env_maintainer_emails(event_doc) if "@" in e],
            case_insensitive_emails=True,
        )
        if not allowlist or "@" not in target:
            return False, allowlist
        allowed_lower = {e.lower() for e in allowlist}
        return target.lower() in allowed_lower, allowlist

    candidates: list[str] = []
    created_by = getattr(event_doc, "created_by_email", None)
    if isinstance(created_by, str) and created_by.strip():
        candidates.append(created_by.strip())
    slack_uid = getattr(event_doc, "slack_user_id", None)
    if isinstance(slack_uid, str) and slack_uid.strip():
        candidates.append(slack_uid.strip())
    candidates.extend(_resolve_evidence_env_maintainer_emails(event_doc))

    allowed_domains: set[str] = set()
    env_domain = os.getenv("SLACK_ACCESS_EMAIL_DOMAIN", "").strip().lstrip("@").lower()
    if env_domain:
        allowed_domains.add(env_domain)
    if isinstance(created_by, str) and "@" in created_by.strip():
        allowed_domains.add(created_by.strip().rsplit("@", 1)[1].lower())

    for turn in getattr(event_doc, "conversation", None) or []:
        actor = turn.get("actor") if isinstance(turn, dict) else getattr(turn, "actor", None)
        if actor != "user":
            continue
        t_email = turn.get("user_email") if isinstance(turn, dict) else getattr(turn, "user_email", None)
        if isinstance(t_email, str) and t_email.strip():
            candidates.append(t_email.strip())
        for field in ("thoughts", "result"):
            text = turn.get(field) if isinstance(turn, dict) else getattr(turn, field, None)
            if not isinstance(text, str) or not text:
                continue
            text_slice = text[:16_384]
            if allowed_domains and "@" in text_slice:
                for email_match in _EMAIL_RE.findall(text_slice):
                    if email_match.rsplit("@", 1)[1].lower() in allowed_domains:
                        candidates.append(email_match)
            if "<@U" in text_slice:
                candidates.extend(_SLACK_MENTION_RE.findall(text_slice))

    allowlist = _dedupe(candidates, case_insensitive_emails=True)
    if "@" in target:
        allowed_emails_lower = {e.lower() for e in allowlist if "@" in e}
        return target.lower() in allowed_emails_lower, allowlist
    allowed_uids = {u for u in allowlist if "@" not in u}
    return target in allowed_uids, allowlist
